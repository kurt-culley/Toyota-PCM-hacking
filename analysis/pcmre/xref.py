"""Cross-references and call graphs for an HD6301 ROM.

The analyser walks the code from the interrupt vectors, the same way the CPU
would, rather than trusting the listing's code/data split. Hand-written Denso
code leans on tricks that a plain disassembler cannot follow, so the walk
carries a small abstract state:

* **X and B as small value sets.** This resolves indexed calls through a fixed
  base (``ldx #$FFCF`` / ``jsr $14,x`` calls ``$FFE3``), indexed accesses
  that wrap past ``$FFFF`` into RAM (the same base makes ``ldaa $FF,x`` read
  ``$00CE``), and jump tables indexed by a masked B
  (``andb #$06`` / ``abx`` / ``ldx $00,x`` / ``jsr $00,x``).
* **A symbolic stack** in which the routine's return address is a symbol.
  This follows routines that take inline parameters after the call and
  return with ``pulx`` / ``jmp $02,x`` (``boundData``), and routines that
  pop the caller's stacked arguments before returning (``mulDbyStack``).

Each routine is analysed once per distinct X value it is called with. A call
returns to the caller with the routine's exit X, at the return offset and
with the extra stack pops the routine was found to use.

Limits: loops are not enumerated. When a back edge changes X or B the value
becomes unknown, so an indexed access inside a loop is resolved for the
first pass through the loop only.

    PYTHONPATH=analysis uv run python -m pcmre.xref            # report
    PYTHONPATH=analysis uv run python -m pcmre.xref --write    # refresh analysis/bluetop/xref.md
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass, field

from .hd6301 import BIT_DIR, BIT_IDX, DIR, EXT, IDX, IMM8, IMM16, REL, Instr, decode
from .idalisting import Listing

# HD6301V1 vector table (Hitachi HD6301/HD6303 Series Handbook).
VECTORS = {
    0xFFEE: "TRAP",
    0xFFF0: "SCI",
    0xFFF2: "TOF",
    0xFFF4: "OCF",
    0xFFF6: "ICF",
    0xFFF8: "IRQ1",
    0xFFFA: "SWI",
    0xFFFC: "NMI",
    0xFFFE: "RES",
}

WIDE = {"ldd", "std", "ldx", "stx", "lds", "sts", "cpx", "subd", "addd"}
WRITE_ONLY = {"staa", "stab", "std", "stx", "sts", "clr"}
READ_WRITE = {"neg", "com", "lsr", "ror", "asr", "asl", "rol", "dec", "inc", "aim", "oim", "eim"}
B_CLOBBER = {
    "ldab", "addb", "adcb", "subb", "sbcb", "orab", "eorb", "clrb", "incb", "decb", "negb", "comb",
    "lsrb", "rolb", "rorb", "asrb", "aslb", "tab", "pulb", "mul", "ldd", "addd", "subd", "xgdx",
    "lsrd", "asld",
}  # fmt: skip
MAX_SET = 16  # larger value sets become unknown

# Abstract values. A register value is None (unknown) or a frozenset of atoms;
# an atom is an int or ("ret", k), meaning "the routine's return address + k".
# Stack bytes are an int, ("reth", k) / ("retl", k) (halves of return address
# + k), or None.


def _vs(*atoms) -> frozenset:
    return frozenset(atoms)


def _add(v, k: int):
    if v is None:
        return None
    return frozenset((a + k) & 0xFFFF if isinstance(a, int) else ("ret", a[1] + k) for a in v)


def _ints(v) -> list[int] | None:
    """The value's possible addresses, if all of them are concrete."""
    if v is None or not all(isinstance(a, int) for a in v):
        return None
    return sorted(v)


def _concrete(v):
    """X passed into a callee: return-relative atoms belong to the caller, so drop them."""
    if v is None or any(isinstance(a, tuple) for a in v):
        return None
    return v


def _union(a, b):
    if a is None or b is None:
        return None
    u = a | b
    return u if len(u) <= MAX_SET else None


@dataclass(frozen=True)
class State:
    x: frozenset | None
    b: frozenset | None
    stack: tuple  # bytes pushed since routine entry (last = top)
    below: int  # bytes popped from below the routine's entry stack pointer

    def push(self, *vals) -> State:
        return State(self.x, self.b, self.stack + vals, self.below)

    def pop(self) -> tuple[object, State]:
        if self.stack:
            return self.stack[-1], State(self.x, self.b, self.stack[:-1], self.below)
        val = ("reth", 0) if self.below == 0 else ("retl", 0) if self.below == 1 else None
        return val, State(self.x, self.b, (), self.below + 1)

    def pop_word(self) -> tuple[object, State]:
        hi, s = self.pop()
        lo, s = s.pop()
        if isinstance(hi, int) and isinstance(lo, int):
            return _vs((hi << 8) | lo), s
        if isinstance(hi, tuple) and isinstance(lo, tuple) and hi[0] == "reth" and lo == ("retl", hi[1]):
            return _vs(("ret", hi[1])), s
        return None, s

    def with_(self, **kw) -> State:
        d = dict(x=self.x, b=self.b, stack=self.stack, below=self.below)
        d.update(kw)
        return State(**d)


def _merge(old: State, new: State, back_edge: bool) -> State | None:
    """Merged state, or None if it equals ``old``. Back edges widen X/B to unknown."""

    def reg(a, b):
        if a == b:
            return a
        return None if back_edge else _union(a, b)

    if len(old.stack) != len(new.stack) or old.below != new.below:
        return None  # unbalanced paths: keep the first state (reported as a warning)
    stack = tuple(p if p == q else None for p, q in zip(old.stack, new.stack, strict=True))
    merged = State(reg(old.x, new.x), reg(old.b, new.b), stack, old.below)
    return None if merged == old else merged


@dataclass(frozen=True)
class Access:
    site: int  # address of the accessing instruction
    routine: int  # routine entry the site was reached from
    addr: int  # effective address
    kind: str  # "r", "w", "rw" or "ptr" (16-bit immediate pointing into ROM)
    width: int  # 1 or 2 bytes
    via_x: bool  # resolved through a known X


@dataclass(frozen=True)
class Call:
    site: int
    caller: int
    callee: int
    how: str  # "jsr", "bsr", "jsr,x" or "jmp" (tail call into another routine)


@dataclass(frozen=True)
class Exit:
    offset: int  # returns to the call site's next instruction + offset (inline parameters)
    extra: int  # bytes of the caller's stack popped besides the return address
    x: frozenset | None  # X on exit (atoms relative to the routine's return address)


@dataclass
class Xref:
    org: int
    rom: bytes
    names: dict[int, str]  # address -> best name (RAM and ROM)
    roots: dict[int, list[str]]  # routine entry -> vector names
    routines: dict[int, set[int]] = field(default_factory=dict)  # entry -> instruction addresses
    exits: dict[int, set[Exit]] = field(default_factory=dict)  # entry -> how it returns
    instrs: dict[int, Instr] = field(default_factory=dict)
    calls: set[Call] = field(default_factory=set)
    accesses: set[Access] = field(default_factory=set)
    jumps: set[tuple[int, int]] = field(default_factory=set)  # (site, target) for branches/jmp
    indirect: set[tuple[int, int, str]] = field(default_factory=set)  # (site, routine, mnemonic)
    # Indexed data accesses reached at least once with X unknown (including loops after the first pass).
    idx_unknown: set[int] = field(default_factory=set)
    errors: set[str] = field(default_factory=set)

    def name(self, addr: int) -> str:
        if addr in self.names:
            return self.names[addr]
        return f"${addr:04X}" if addr >= 0x100 else f"${addr:02X}"

    def routine_name(self, entry: int) -> str:
        if entry in self.names:
            return self.names[entry]
        # An entry inside labelled code (e.g. a computed call into DivDby16) is named label+offset.
        below = [a for a in self.names if self.org <= a < entry and entry - a <= 16]
        if below:
            a = max(below)
            return f"{self.names[a]}+{entry - a}"
        return f"sub_{entry:04X}"


def _is_rom(x: Xref, addr: int) -> bool:
    return x.org <= addr < x.org + len(x.rom)


def _data_kind(mnem: str) -> str:
    if mnem in WRITE_ONLY:
        return "w"
    if mnem in READ_WRITE:
        return "rw"
    return "r"


def _submasks(m: int) -> frozenset | None:
    bits = [1 << i for i in range(8) if m >> i & 1]
    if len(bits) > 4:
        return None
    out = set()
    for n in range(1 << len(bits)):
        out.add(sum(b for i, b in enumerate(bits) if n >> i & 1))
    return frozenset(out)


class _Analyser:
    def __init__(self, rom: bytes, org: int, names: dict[int, str], entries: set[int]):
        self.rom, self.org = rom, org
        roots: dict[int, list[str]] = defaultdict(list)
        for vaddr, vname in VECTORS.items():
            off = vaddr - org
            if 0 <= off < len(rom) - 1:
                target = (rom[off] << 8) | rom[off + 1]
                if org <= target < org + len(rom):
                    roots[target].append(vname)
        self.x = Xref(org, rom, names, dict(roots))
        self.entries = set(roots) | entries  # known routine entries (for tail calls)
        self.summaries: dict[tuple[int, object], frozenset[Exit]] = {}
        self.in_progress: set[tuple[int, object]] = set()

    def run(self) -> Xref:
        for entry in self.x.roots:
            self.analyse(entry, None)
        return self.x

    # -- one routine context -------------------------------------------------
    def analyse(self, entry: int, x_in) -> frozenset[Exit]:
        key = (entry, x_in)
        if key in self.summaries:
            return self.summaries[key]
        if key in self.in_progress:
            return frozenset({Exit(0, 0, None)})  # recursion: assume a plain return
        self.in_progress.add(key)
        self.x.routines.setdefault(entry, set())

        states: dict[int, State] = {entry: State(x_in, None, (), 0)}
        work = [entry]
        exits: set[Exit] = set()
        while work:
            pc = work.pop()
            st = states[pc]
            ins = decode(self.rom, pc, self.org)
            if ins is None:
                self.x.errors.add(f"undecodable byte at ${pc:04X} reached from {self.x.routine_name(entry)}")
                continue
            self.x.instrs[pc] = ins
            self.x.routines[entry].add(pc)
            for nxt_pc, nxt_st in self.step(entry, ins, st, exits):
                if not _is_rom(self.x, nxt_pc):
                    self.x.errors.add(f"flow leaves ROM at ${ins.addr:04X} -> ${nxt_pc:04X}")
                    continue
                if nxt_pc not in states:
                    states[nxt_pc] = nxt_st
                    work.append(nxt_pc)
                    continue
                old = states[nxt_pc]
                if len(old.stack) != len(nxt_st.stack) or old.below != nxt_st.below:
                    self.x.errors.add(
                        f"stack depth differs where paths join at ${nxt_pc:04X} in {self.x.routine_name(entry)}"
                    )
                merged = _merge(old, nxt_st, back_edge=nxt_pc <= ins.addr)
                if merged is not None:
                    states[nxt_pc] = merged
                    work.append(nxt_pc)

        result = frozenset(exits)
        self.in_progress.discard(key)
        self.summaries[key] = result
        self.x.exits.setdefault(entry, set()).update(result)
        return result

    # -- transfer function ----------------------------------------------------
    def call(self, entry: int, ins: Instr, target: int, how: str, st: State, nxt: int) -> list[tuple[int, State]]:
        self.x.calls.add(Call(ins.addr, entry, target, how))
        out = []
        exits = self.analyse(target, _concrete(st.x))
        if not exits:
            return []  # never returns
        for ex in exits:
            s = st
            for _ in range(ex.extra):
                _, s = s.pop()
            # Callee's X atoms relative to its return address become concrete here.
            xo = None
            if ex.x is not None:
                xo = frozenset((nxt + a[1]) & 0xFFFF if isinstance(a, tuple) else a for a in ex.x)
            out.append((nxt + ex.offset, s.with_(x=xo, b=None)))
        return out

    def tail(self, entry: int, ins: Instr, target: int, st: State, exits: set[Exit]) -> None:
        """A jmp into another routine: its exits become ours."""
        self.x.calls.add(Call(ins.addr, entry, target, "jmp"))
        sub = self.analyse(target, _concrete(st.x))
        if st.stack or st.below:
            self.x.errors.add(f"tail call at ${ins.addr:04X} with a modified stack")
        exits.update(sub)

    def ret(self, entry: int, ins: Instr, st: State, exits: set[Exit]) -> list[tuple[int, State]]:
        """rts: return through whatever word is on top of the stack."""
        word, s = st.pop_word()
        out = []
        if word is None:
            self.x.indirect.add((ins.addr, entry, "rts"))
            return out
        for a in word:
            if isinstance(a, tuple):
                exits.add(Exit(a[1], s.below - 2, st.x))
            elif _is_rom(self.x, a):
                out.append((a, s))  # pushed address + rts = computed jump
        return out

    def step(self, entry: int, ins: Instr, st: State, exits: set[Exit]) -> list[tuple[int, State]]:
        m, mode, nxt = ins.mnemonic, ins.mode, ins.addr + ins.length

        # Effective addresses of a memory operand.
        eas, via_x = None, False
        if mode in (DIR, EXT, BIT_DIR):
            eas = [ins.operand]
        elif mode in (IDX, BIT_IDX):
            eas, via_x = _ints(_add(st.x, ins.operand)), True
            if eas is None and m not in ("jsr", "jmp"):
                self.x.idx_unknown.add(ins.addr)

        # ---- control flow
        if m == "rts":
            return self.ret(entry, ins, st, exits)
        if m == "rti":
            exits.add(Exit(0, 0, st.x))
            return []
        if m == "swi":
            return []
        if m in ("bsr", "jsr"):
            if mode == REL:
                return self.call(entry, ins, ins.operand, "bsr", st, nxt)
            if eas is None:
                self.x.indirect.add((ins.addr, entry, m))
                return [(nxt, st.with_(x=None, b=None))]
            out = []
            for t in eas:
                out += self.call(entry, ins, t, "jsr,x" if via_x else "jsr", st, nxt)
            return out
        if mode == REL:
            self.x.jumps.add((ins.addr, ins.operand))
            if m == "bra":
                return [(ins.operand, st)]
            if m == "brn":
                return [(nxt, st)]
            return [(nxt, st), (ins.operand, st)]
        if m == "jmp":
            if mode == IDX and st.x is not None:
                out = []
                for a in _add(st.x, ins.operand):
                    if isinstance(a, tuple):  # jmp k,x with X = return address + j
                        exits.add(Exit(a[1], st.below - 2, st.x))
                    elif a in self.entries:
                        self.tail(entry, ins, a, st, exits)
                    else:
                        self.x.jumps.add((ins.addr, a))
                        out.append((a, st))
                return out
            if eas is None:
                self.x.indirect.add((ins.addr, entry, m))
                return []
            t = eas[0]
            if t in self.entries and t != entry:
                self.tail(entry, ins, t, st, exits)
                return []
            self.x.jumps.add((ins.addr, t))
            return [(t, st)]

        # ---- data accesses
        if eas is not None:
            kind = "r" if m == "tim" else _data_kind(m)
            width = 2 if m in WIDE else 1
            for ea in eas:
                # A 16-bit access touches both bytes; record each so both rows show it.
                for k in range(width):
                    self.x.accesses.add(Access(ins.addr, entry, (ea + k) & 0xFFFF, kind, width, via_x))
        elif mode == IMM16 and _is_rom(self.x, ins.operand) and m in ("ldx", "ldd"):
            self.x.accesses.add(Access(ins.addr, entry, ins.operand, "ptr", 2, False))

        # ---- register and stack effects
        s = st
        if m in ("psha", "des"):
            s = s.push(None)
        elif m == "pshb":
            s = s.push(next(iter(st.b)) if st.b is not None and len(st.b) == 1 else None)
        elif m == "pshx":
            if st.x is not None and len(st.x) == 1:
                (a,) = st.x
                # PSHX pushes the low byte first, so the high byte ends up on top (as JSR does).
                s = s.push(a & 0xFF, a >> 8) if isinstance(a, int) else s.push(("retl", a[1]), ("reth", a[1]))
            else:
                s = s.push(None, None)
        elif m in ("pula", "ins"):
            _, s = s.pop()
        elif m == "pulb":
            v, s = s.pop()
            s = s.with_(b=_vs(v) if isinstance(v, int) else None)
        elif m == "pulx":
            v, s = s.pop_word()
            s = s.with_(x=v)
        elif m in ("txs", "lds"):
            self.x.errors.add(f"stack pointer reloaded at ${ins.addr:04X} in {self.x.routine_name(entry)}")
            s = s.with_(stack=(), below=0)
        if m == "ldx":
            s = s.with_(x=_vs(ins.operand) if mode == IMM16 else None)
            # ldx from a table in ROM (e.g. a jump table): X is one of the stored words.
            in_rom = eas is not None and all(_is_rom(self.x, a) and _is_rom(self.x, a + 1) for a in eas)
            if mode != IMM16 and in_rom and len(eas) <= MAX_SET:
                words = {(self.rom[a - self.org] << 8) | self.rom[a - self.org + 1] for a in eas}
                s = s.with_(x=frozenset(words))
        elif m == "inx":
            s = s.with_(x=_add(st.x, 1))
        elif m == "dex":
            s = s.with_(x=_add(st.x, -1))
        elif m == "abx":
            xs, bs = _ints(st.x), _ints(st.b)
            v = None
            if xs is not None and bs is not None and len(xs) * len(bs) <= MAX_SET:
                v = frozenset((a + b) & 0xFFFF for a in xs for b in bs)
            s = s.with_(x=v)
        elif m in ("tsx", "xgdx"):
            s = s.with_(x=None)
        if m == "ldab" and mode == IMM8:
            s = s.with_(b=_vs(ins.operand))
        elif m == "ldd" and mode == IMM16:
            s = s.with_(b=_vs(ins.operand & 0xFF))
        elif m == "clrb":
            s = s.with_(b=_vs(0))
        elif m == "andb" and mode != IMM8:
            s = s.with_(b=None)
        elif m == "andb":
            bs = _ints(st.b)
            s = s.with_(b=frozenset(b & ins.operand for b in bs) if bs is not None else _submasks(ins.operand))
        elif m in B_CLOBBER and m != "pulb":
            s = s.with_(b=None)
        return [(nxt, s)]


def analyse(rom: bytes, listing: Listing) -> Xref:
    names: dict[int, str] = dict(listing.ram_labels)
    for a, n in listing.labels.items():
        names[a] = n[0]
    # Two rounds: the first discovers every call target, so the second can
    # recognise a jmp into any routine as a tail call regardless of walk order.
    first = _Analyser(rom, listing.org, names, set()).run()
    return _Analyser(rom, listing.org, names, {c.callee for c in first.calls}).run()


# ---------------------------------------------------------------------------
# Report


def _md_list(items: list[str], limit: int = 12) -> str:
    if not items:
        return "–"
    if len(items) > limit:
        return ", ".join(items[:limit]) + f", … (+{len(items) - limit})"
    return ", ".join(items)


def _mermaid_id(addr: int) -> str:
    return f"r{addr:04X}"


def _call_graph(x: Xref, root: int, edges: dict[int, set[int]]) -> list[str]:
    seen, order, stack = {root}, [root], [root]
    while stack:
        a = stack.pop()
        for b in sorted(edges.get(a, ())):
            if b not in seen:
                seen.add(b)
                order.append(b)
                stack.append(b)
    lines = ["```mermaid", "flowchart LR"]
    for a in order:
        label = x.routine_name(a)
        lines.append(f'  {_mermaid_id(a)}["{label}<br/>${a:04X}"]')
    for a in order:
        for b in sorted(edges.get(a, ())):
            lines.append(f"  {_mermaid_id(a)} --> {_mermaid_id(b)}")
    lines.append("```")
    return lines


def render(x: Xref, listing: Listing, title: str) -> str:
    callers: dict[int, set[int]] = defaultdict(set)
    callees: dict[int, set[int]] = defaultdict(set)
    for c in x.calls:
        callers[c.callee].add(c.caller)
        callees[c.caller].add(c.callee)

    unresolved_idx = sorted(x.idx_unknown)
    listed_code = {it.addr for it in listing.items if it.kind == "code"}
    listed_data = {it.addr for it in listing.items if it.kind != "code"}
    reached = set(x.instrs)
    unreached = sorted(listed_code - reached)
    code_in_data = sorted(a for a in reached if a in listed_data)

    out = [
        f"# Cross-references: {title}",
        "",
        "Generated by `analysis/pcmre/xref.py`. **Do not edit by hand**; regenerate with",
        "`PYTHONPATH=analysis uv run python -m pcmre.xref --write`. A test fails if this file is stale.",
        "",
        "The analyser follows the code from the interrupt vectors and tracks the X register when it holds a",
        "constant, so it resolves Denso's indexed calls (`ldx #$FFCF` / `jsr $14,x`) and indexed accesses that",
        "wrap past `$FFFF` into RAM. Accesses marked † were resolved that way. IDA's own `XREF` comments in",
        "`cap.asm` are checked against this analysis by `tests/test_xref.py`.",
        "",
        "## Summary",
        "",
        "| Item | Count |",
        "|---|---|",
        f"| Routines (vector entries + call targets) | {len(x.routines)} |",
        f"| Instructions reached | {len(reached)} |",
        f"| Call edges (unique caller → callee) | {len({(c.caller, c.callee) for c in x.calls})} |",
        f"| Memory accesses resolved | {len(x.accesses)} |",
        f"| Indirect calls/jumps not resolved | {len(x.indirect)} |",
        f"| Indexed data sites reached with X unknown, wholly or after a loop's first pass | {len(unresolved_idx)} |",
        f"| Listing code lines never reached | {len(unreached)} |",
        f"| Reached instructions the listing calls data | {len(code_in_data)} |",
        "",
    ]

    # Vectors
    out += ["## Vectors", "", "| Vector | Address | Handler |", "|---|---|---|"]
    for vaddr, vname in VECTORS.items():
        off = vaddr - x.org
        target = (x.rom[off] << 8) | x.rom[off + 1]
        handler = x.routine_name(target) if target in x.routines else "outside ROM (not code)"
        out.append(f"| {vname} | `${vaddr:04X}` | `${target:04X}` {handler} |")
    out.append("")

    # Routines
    out += [
        "## Routines",
        "",
        "Instruction counts include code shared with other routines (fall-through tails).",
        "",
        "| Entry | Routine | Instrs | Called by | Calls |",
        "|---|---|---|---|---|",
    ]
    for entry in sorted(x.routines):
        roots = x.roots.get(entry)
        name = x.routine_name(entry) + (f" ({', '.join(roots)} vector)" if roots else "")
        out.append(
            f"| `${entry:04X}` | {name} | {len(x.routines[entry])} | "
            f"{_md_list(sorted(x.routine_name(c) for c in callers[entry]))} | "
            f"{_md_list(sorted(x.routine_name(c) for c in callees[entry]))} |"
        )
    out.append("")

    # Non-standard returns
    odd = {e: ex for e, ex in x.exits.items() if any(v.offset or v.extra for v in ex)}
    out += [
        "## Routines with non-standard returns",
        "",
        "`inline` = bytes of parameters placed after the call, skipped on return; `pops` = bytes of the",
        "caller's stack removed besides the return address.",
        "",
        "| Entry | Routine | Inline bytes | Pops |",
        "|---|---|---|---|",
    ]
    for entry in sorted(odd):
        ex = odd[entry]
        offs = "/".join(str(v) for v in sorted({v.offset for v in ex}))
        pops = "/".join(str(v) for v in sorted({v.extra for v in ex}))
        out.append(f"| `${entry:04X}` | {x.routine_name(entry)} | {offs} | {pops} |")
    out.append("")

    # RAM and registers
    by_addr: dict[int, list[Access]] = defaultdict(list)
    for acc in x.accesses:
        by_addr[acc.addr].append(acc)

    def who(accs: list[Access], kinds: set[str]) -> str:
        names = sorted({x.routine_name(a.routine) + ("†" if a.via_x else "") for a in accs if a.kind in kinds})
        return _md_list(names)

    out += [
        "## RAM and I/O registers",
        "",
        "`$00`–`$1F` are the HD6301 on-chip registers; `$80`–`$FF` is on-chip RAM; `$40`–`$7F` is external",
        "RAM on this board. Read-modify-write instructions (`inc`, `aim` …) count as both, and a 16-bit",
        "access (`ldd`, `std`, `ldx` …) is listed on both of its bytes.",
        "",
        "**These lists are not complete.** A dash means no access was *resolved*, not that none exists:",
        "",
        "- indexed accesses with an unknown X (for example the ADC result store at `$54` + channel) are not",
        "  attributed;",
        "- in a loop that walks X, only the first pass is attributed. For example, reset's RAM clear",
        "  (`clr $4B,x` / `dex` loop at `$F02B`) shows up only on `$FF`, and the RAM and ROM self-tests only on",
        "  their first address.",
        "",
        f"Both kinds are counted in the summary; the sites are: "
        f"{_md_list([f'`${a:04X}`' for a in unresolved_idx], limit=40)}.",
        "",
        "| Address | Name | Width | Read by | Written by |",
        "|---|---|---|---|---|",
    ]
    for a in sorted(k for k in by_addr if not _is_rom(x, k)):
        accs = by_addr[a]
        width = max(acc.width for acc in accs)
        out.append(
            f"| `${a:02X}` | {x.name(a) if a in x.names else '–'} | {width} | "
            f"{who(accs, {'r', 'rw'})} | {who(accs, {'w', 'rw'})} |"
        )
    out.append("")

    # ROM data
    out += [
        "## ROM data and tables",
        "",
        "Direct reads of ROM, and 16-bit immediates that point into ROM (`ptr`, usually a table base or an",
        "X base for an indexed call). Code addresses that are only used as call or jump targets are not listed.",
        "",
        "| Address | Name | How | Used by |",
        "|---|---|---|---|",
    ]
    for a in sorted(k for k in by_addr if _is_rom(x, k)):
        accs = by_addr[a]
        hows = "/".join(sorted({acc.kind for acc in accs}))
        out.append(f"| `${a:04X}` | {x.name(a) if a in x.names else '–'} | {hows} | {who(accs, {'r', 'ptr'})} |")
    out.append("")

    # Indirect
    out += [
        "## Unresolved indirect calls and jumps",
        "",
        "A site listed here may also have resolved calls from paths where X was still known (see Routines).",
        "",
        "| Site | Routine | Instruction |",
        "|---|---|---|",
    ]
    for site, entry, m in sorted(x.indirect):
        ins = x.instrs[site]
        out.append(f"| `${site:04X}` | {x.routine_name(entry)} | `{m} ${ins.operand:02X},x` |")
    out.append("")

    # Coverage
    out += [
        "## Coverage against the IDA listing",
        "",
        "Listing code lines never reached from a vector (dead code, or reached only through an unresolved",
        "indirect jump):",
        "",
    ]
    out.append(_md_list([f"`${a:04X}`" for a in unreached], limit=60) if unreached else "None.")
    out += [
        "",
        "Reached instructions that the listing marks as data. These are Denso skip tricks: a one-byte opcode",
        "(`ldx #`, `brn`) whose operand bytes hide the next instruction, so one path executes the hidden",
        "instruction and the other skips it:",
        "",
    ]
    out.append(_md_list([f"`${a:04X}`" for a in code_in_data], limit=60) if code_in_data else "None.")
    out.append("")
    if x.errors:
        out += ["Analysis warnings:", ""] + [f"- {e}" for e in sorted(set(x.errors))] + [""]

    # Call graphs
    out += ["## Call graphs", "", "One graph per vector. Tail calls (`jmp` into another routine) count as calls.", ""]
    for root in sorted(x.roots):
        out += [f"### {', '.join(x.roots[root])}: {x.routine_name(root)}", ""]
        out += _call_graph(x, root, callees)
        out.append("")
    return "\n".join(out)


def report(rom: bytes, listing: Listing, title: str) -> tuple[Xref, str]:
    x = analyse(rom, listing)
    return x, render(x, listing, title)


def main() -> int:
    from .idalisting import parse
    from .roundtrip import ROOT, TARGETS

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?", default="bluetop", choices=sorted(TARGETS))
    ap.add_argument("--write", action="store_true", help="write the report to analysis/<target>/xref.md")
    a = ap.parse_args()
    t = TARGETS[a.target]
    rom = t["rom"].read_bytes()
    listing = parse(t["listing"], rom)
    x, md = report(rom, listing, t["title"])
    print(
        f"{a.target}: {len(x.routines)} routines, {len(x.instrs)} instructions, "
        f"{len(x.accesses)} accesses, {len(x.indirect)} unresolved indirect, {len(x.errors)} warnings"
    )
    if a.write:
        out = ROOT / "analysis" / a.target / "xref.md"
        out.write_text(md)
        print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
