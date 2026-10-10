"""Cross-version analysis of two ROMs of the same program (Bluetop 0642 against 2860).

    PYTHONPATH=analysis uv run python -m pcmre.crossver          # report to stdout
    PYTHONPATH=analysis uv run python -m pcmre.crossver --write  # analysis/bluetop/crossver_2860.md

Both ROMs are traced with ``pcmre.xref`` (code is what the tracer reaches from the
vectors). The two instruction streams are aligned with ``difflib`` on tokens that keep
everything except 16-bit operands, relative-branch targets and extended addresses (which
move when code shifts). A map is ported by its references: every instruction in ROM A
whose 16-bit operand points into the map is followed to its aligned instruction in ROM B,
and B's operand there, minus the same offset, is the map's address in B. A port is
CONFIRMED when every reference agrees, and is flagged otherwise.

The same method ports the 17140 ROM once it is dumped.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from dataclasses import dataclass, field

import yaml

from . import xref
from .hd6301 import Instr
from .idalisting import Listing, parse
from .roundtrip import ROOT

ROM_A = ROOT / "TOYOTA Bluetop PCM/cap.bin"
LISTING_A = ROOT / "TOYOTA Bluetop PCM/cap.asm"
ROM_B = ROOT / "TOYOTA Bluetop PCM/cap2-151801-2860.bin"
DEFS_A = ROOT / "analysis/defs/bluetop.yaml"
REPORT = ROOT / "analysis/bluetop/crossver_2860.md"
ORG = 0xF000

WIDE = {"imm16", "ext", "rel"}  # operands that move with the code


def token(i: Instr, ram: dict[int, int] | None = None) -> tuple:
    op = None if i.mode in WIDE else i.operand
    if ram and i.mode == "dir" and op in ram:
        op = ram[op]
    return (i.mnemonic, i.mode, op, i.imm)


def trace(rom: bytes, listing: Listing | None = None) -> xref.Xref:
    if listing is None:
        listing = Listing(
            ram_labels=dict(parse(LISTING_A, ROM_A.read_bytes()).ram_labels), labels={}, items=[], org=ORG
        )
    return xref.analyse(rom, listing)


@dataclass
class Alignment:
    a_to_b: dict[int, int]  # instruction address in A -> aligned instruction in B
    ops: list[tuple[str, list[int], list[int]]]  # non-equal blocks: (tag, A addresses, B addresses)
    ram: dict[int, int] = field(default_factory=dict)  # direct-page address in A -> B, where it moved


def _align(xa: xref.Xref, xb: xref.Xref, ram: dict[int, int]) -> Alignment:
    ia, ib = sorted(xa.instrs), sorted(xb.instrs)
    ta, tb = [token(xa.instrs[a], ram) for a in ia], [token(xb.instrs[b]) for b in ib]
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    a_to_b, ops = {}, []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            a_to_b.update(zip(ia[i1:i2], ib[j1:j2], strict=True))
        else:
            ops.append((tag, ia[i1:i2], ib[j1:j2]))
            if tag == "replace" and i2 - i1 == j2 - j1:  # same shape, different detail
                a_to_b.update(zip(ia[i1:i2], ib[j1:j2], strict=True))
    return Alignment(a_to_b, ops, ram)


def infer_ram_map(xa: xref.Xref, xb: xref.Xref, al: Alignment) -> dict[int, int]:
    """Direct-page addresses that moved: majority vote over aligned same-instruction pairs."""
    votes: dict[int, dict[int, int]] = {}
    for a, b in al.a_to_b.items():
        ia, ib = xa.instrs[a], xb.instrs[b]
        if ia.mode == ib.mode == "dir" and ia.mnemonic == ib.mnemonic:
            v = votes.setdefault(ia.operand, {})
            v[ib.operand] = v.get(ib.operand, 0) + 1
    out = {}
    for a, v in votes.items():
        b, n = max(v.items(), key=lambda kv: kv[1])
        if b != a and n * 2 > sum(v.values()):
            out[a] = b
    return out


def align(xa: xref.Xref, xb: xref.Xref) -> Alignment:
    """Align, learn which RAM addresses moved, then align again with them mapped."""
    al = _align(xa, xb, {})
    for _ in range(3):
        ram = infer_ram_map(xa, xb, al)
        if ram == al.ram:
            break
        al = _align(xa, xb, ram)
    return al


def map_size(m: dict) -> int:
    if m["kind"] == "3d":
        return m["rows"] * m["cols"]
    return m["length"]


@dataclass
class Port:
    id: str
    addr_a: int
    size: int
    addr_b: int | None
    refs: list[tuple[int, int | None, int | None]] = field(default_factory=list)  # (site A, site B, addr B)
    status: str = ""
    entry_b: int | None = None
    aliased: list[tuple[int, int | None, int | None]] = field(default_factory=list)  # pointers, not reads


def evidence_sites(evidence: str) -> list[tuple[int, int]]:
    """ROM addresses named in a map's evidence: ``[ROM:$F86C-$F89F]``, ``[ROM:$FBDA]``, lists of either."""
    import re

    out = []
    for tag in re.findall(r"\[ROM:([^\]]*)\]", evidence):
        for lo, hi in re.findall(r"\$([0-9A-Fa-f]{4})(?:-\$([0-9A-Fa-f]{4}))?", tag):
            lo_i = int(lo, 16)
            hi_i = int(hi, 16) if hi else lo_i
            out.append((lo_i - 8, hi_i + 8))  # a single site names the lookup; the ldx is just before it
    return out


def port_maps(spec: dict, xa: xref.Xref, xb: xref.Xref, al: Alignment) -> list[Port]:
    out = []
    for m in spec["maps"]:
        lo, size = m["addr"], map_size(m)
        p = Port(m["id"], lo, size, None)
        for a, ins in sorted(xa.instrs.items()):
            if ins.mode not in ("imm16", "ext") or ins.operand is None or not lo <= ins.operand < lo + size:
                continue
            b = al.a_to_b.get(a)
            ib = xb.instrs.get(b) if b is not None else None
            if ib is None or ib.mode != ins.mode or ib.mnemonic != ins.mnemonic:
                p.refs.append((a, None, None))
                continue
            p.refs.append((a, b, ib.operand - (ins.operand - lo)))
        sites = evidence_sites(str(m.get("evidence", "")))
        primary = [r for r in p.refs if any(lo_s <= r[0] <= hi_s for lo_s, hi_s in sites)]
        if primary and len(primary) < len(p.refs):
            p.aliased = [r for r in p.refs if r not in primary]
            p.refs = primary
        found = {r[2] for r in p.refs if r[2] is not None}
        if not p.refs:
            p.status = "no direct reference in A"
        elif len(found) == 1 and all(r[2] is not None for r in p.refs):
            p.addr_b, p.status = found.pop(), "CONFIRMED"
        elif len(found) == 1:
            p.addr_b, p.status = found.pop(), "LIKELY (some references not aligned)"
        else:
            p.status = f"CONFLICT {sorted(hex(f) for f in found)}" if found else "not found"
        if m.get("entry"):
            p.entry_b = port_address(m["entry"], xa, xb, al)
        out.append(p)
    return out


def port_address(addr_a: int, xa: xref.Xref, xb: xref.Xref, al: Alignment) -> int | None:
    """A code address (helper entry) in A -> B, through the aligned instruction at or below it."""
    if addr_a in al.a_to_b:
        return al.a_to_b[addr_a]
    below = [a for a in al.a_to_b if a <= addr_a and addr_a - a < 4]
    return al.a_to_b[max(below)] + (addr_a - max(below)) if below else None


def routine_of(x: xref.Xref, addr: int) -> int | None:
    for entry, body in x.routines.items():
        if addr in body:
            return entry
    return None


def render(
    spec: dict, rom_a: bytes, rom_b: bytes, xa: xref.Xref, xb: xref.Xref, al: Alignment, ports: list[Port]
) -> str:
    def name_a(addr: int) -> str:
        r = routine_of(xa, addr)
        return xa.routine_name(r) if r is not None else "?"

    code_a = {a + k for a, i in xa.instrs.items() for k in range(i.length)}
    code_b = {b + k for b, i in xb.instrs.items() for k in range(i.length)}
    lines = [
        "# Bluetop cross-version analysis: D151801-0642 (`cap.bin`) against D151801-2860 (`cap2`)",
        "",
        "Generated by `python -m pcmre.crossver --write` ([`../pcmre/crossver.py`](../pcmre/crossver.py)). "
        "Do not edit.",
        "",
        "## Summary",
        "",
        "| | 0642 (`cap.bin`) | 2860 (`cap2`) |",
        "|---|---|---|",
        f"| Instructions reached from the vectors | {len(xa.instrs)} | {len(xb.instrs)} |",
        f"| Routines | {len(xa.routines)} | {len(xb.routines)} |",
        f"| Code bytes | {len(code_a)} | {len(code_b)} |",
        f"| Data bytes (not reached as code) | {4096 - len(code_a)} | {4096 - len(code_b)} |",
        "",
        f"Instruction streams: {len(al.a_to_b)} of {len(xa.instrs)} instructions in 0642 align to 2860; "
        f"{len(al.ops)} blocks differ.",
        "",
        "## RAM addresses that moved",
        "",
        "Direct-page variables at a different address in 2860 (majority of aligned uses). "
        "Names are from the 0642 listing.",
        "",
        "| 0642 | 2860 | Name |",
        "|---|---|---|",
        *[f"| `${a:02X}` | `${b:02X}` | {xa.name(a)} |" for a, b in sorted(al.ram.items())],
        "",
        "## Maps ported to 2860",
        "",
        "| Map | 0642 | 2860 | Port | Contents |",
        "|---|---|---|---|---|",
    ]
    for p in ports:
        if p.addr_b is None:
            lines.append(f"| `{p.id}` | `${p.addr_a:04X}` | — | {p.status} | — |")
            continue
        va = rom_a[p.addr_a - ORG : p.addr_a - ORG + p.size]
        vb = rom_b[p.addr_b - ORG : p.addr_b - ORG + p.size]
        n = sum(x != y for x, y in zip(va, vb, strict=True))
        what = "identical" if n == 0 else f"**{n} of {p.size} cells differ**"
        note = f"; {len(p.aliased)} helper pointer(s) ignored" if p.aliased else ""
        lines.append(
            f"| `{p.id}` | `${p.addr_a:04X}` | `${p.addr_b:04X}` | {p.status} ({len(p.refs)} refs{note}) | {what} |"
        )
    lines += ["", "### Differing maps, cell by cell", ""]
    for p in ports:
        if p.addr_b is None:
            continue
        va = list(rom_a[p.addr_a - ORG : p.addr_a - ORG + p.size])
        vb = list(rom_b[p.addr_b - ORG : p.addr_b - ORG + p.size])
        if va == vb:
            continue
        lines += [f"**`{p.id}`**", "", "```", "0642: " + " ".join(f"{v:3d}" for v in va)]
        lines += ["2860: " + " ".join(f"{v:3d}" for v in vb), "```", ""]

    def fmt(x: xref.Xref, addrs: list[int]) -> str:
        return "; ".join(_fmt(x.instrs[a]) for a in addrs[:6]) + (" …" if len(addrs) > 6 else "")

    dd = data_diffs(xa, xb, al, ports)
    lines += ["## Data bytes outside the known maps", ""]
    if dd:
        lines += ["| 0642 | 2860 | 0642 value | 2860 value | Mapped by |", "|---|---|---|---|---|"]
        for a, b, va, vb, how in dd:
            w = 4 if how.startswith("code pointer") else 2
            lines.append(f"| `${a:04X}` | `${b:04X}` | `${va:0{w}X}` | `${vb:0{w}X}` | {how} |")
    else:
        lines.append("None differ.")
    lines.append("")
    ia, ib = ram_init_table(xa), ram_init_table(xb)
    if ia and ib:
        lines += [
            "## RAM start-up values",
            "",
            f"From the reset routine's initialisation table (0642 `${ia[0]:04X}`, 2860 `${ib[0]:04X}`), "
            "compared through the RAM remap. Only differences are listed.",
            "",
            "| RAM (0642) | RAM (2860) | Name | 0642 | 2860 |",
            "|---|---|---|---|---|",
        ]
        inv = {v: k for k, v in al.ram.items()}
        for ra in sorted(set(ia[2]) | {inv.get(r, r) for r in ib[2]}):
            rb = al.ram.get(ra, ra)
            va, vb = ia[2].get(ra), ib[2].get(rb)
            if va != vb:
                fa = "—" if va is None else f"`${va:02X}`"
                fb = "—" if vb is None else f"`${vb:02X}`"
                lines.append(f"| `${ra:02X}` | `${rb:02X}` | {xa.name(ra)} | {fa} | {fb} |")
        lines.append("")
    groups = classify(xa, xb, al)
    titles = {
        "relocated": "Calls whose target moved (same routine, different address or helper entry offset)",
        "moved": "Blocks that moved (same instructions at a different place)",
        "behaviour": "Behaviour-change candidates",
    }
    lines += ["## Code differences", ""]
    for kind in ("behaviour", "moved", "relocated"):
        lines += [f"### {titles[kind]} ({len(groups[kind])})", ""]
        if not groups[kind]:
            lines += ["None.", ""]
            continue
        lines += ["| 0642 | 2860 | Routine (0642) | 0642 code | 2860 code |", "|---|---|---|---|---|"]
        for _tag, aa, bb in groups[kind]:
            a0 = f"`${aa[0]:04X}`" if aa else "—"
            b0 = f"`${bb[0]:04X}`" if bb else "—"
            where = name_a(aa[0]) if aa else (name_a(_prev(al, bb[0])) if bb else "?")
            lines.append(f"| {a0} | {b0} | {where} | {fmt(xa, aa) or '—'} | {fmt(xb, bb) or '—'} |")
        lines.append("")
    return "\n".join(lines)


def ram_init_table(x: xref.Xref) -> tuple[int, int, dict[int, int]] | None:
    """The reset routine's RAM initialisation table: (first byte, end, {RAM address: value}).

    Located by its loader: ``ldx #table-1 / inx / ldab 0,x / beq``. The table is
    ``address, value, value, ..., $00`` repeated, ending with a lone ``$00``.
    """
    addrs = sorted(x.instrs)
    for k, a in enumerate(addrs[:-2]):
        i0, i1, i2 = x.instrs[a], x.instrs[addrs[k + 1]], x.instrs[addrs[k + 2]]
        loader = i0.mnemonic == "ldx" and i0.mode == "imm16" and i1.mnemonic == "inx" and i2.mnemonic == "ldab"
        if loader and i2.mode == "idx" and i2.operand == 0:
            start = p = i0.operand + 1
            out = {}
            while (ram := x.rom[p - ORG]) != 0:
                p += 1
                while (v := x.rom[p - ORG]) != 0:
                    out[ram] = v
                    ram, p = ram + 1, p + 1
                p += 1
            return start, p + 1, out
    return None


def data_diffs(xa: xref.Xref, xb: xref.Xref, al: Alignment, ports: list[Port]) -> list[tuple[int, int, int, int, str]]:
    """Non-code bytes of A that differ in B: (addr A, addr B, value A, value B, how mapped).

    Bytes just after an instruction (inline parameters such as ``jsr boundData / db lo, hi``)
    are mapped through that instruction; bytes inside a ported map are covered by the map
    table; everything else is mapped by a byte-level alignment of the two ROMs.
    """
    code_a = {a + k for a, i in xa.instrs.items() for k in range(i.length)}
    in_map = {p.addr_a + k for p in ports for k in range(p.size)}
    sm = difflib.SequenceMatcher(None, xa.rom, xb.rom, autojunk=False)
    byte_map = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            byte_map.update({ORG + i: ORG + j for i, j in zip(range(i1, i2), range(j1, j2), strict=True)})
    init = ram_init_table(xa)
    in_init = set(range(init[0], init[1])) if init else set()
    starts = sorted(xa.instrs)
    out = []
    skip = set()
    for d in range(ORG, ORG + len(xa.rom) - 1):  # code pointers (jump tables, vectors)
        if d in code_a or d in in_map or d + 1 in code_a:
            continue
        wa = xa.rom[d - ORG] << 8 | xa.rom[d + 1 - ORG]
        if wa in al.a_to_b:
            b = byte_map.get(d)
            if b is not None and (xb.rom[b - ORG] << 8 | xb.rom[b + 1 - ORG]) == al.a_to_b[wa] and wa != al.a_to_b[wa]:
                out.append((d, b, wa, al.a_to_b[wa], "code pointer, follows its target"))
                skip.update({d, d + 1})
    for d in range(ORG, ORG + len(xa.rom)):
        if d in code_a or d in in_map or d in in_init or d in skip:
            continue
        prev = [a for a in starts[-1::-1] if a < d][:1]
        if prev and d - prev[0] - xa.instrs[prev[0]].length < 4 and prev[0] in al.a_to_b:
            b, how = al.a_to_b[prev[0]] + (d - prev[0]), "inline after instruction"
        elif d in byte_map:
            b, how = byte_map[d], "byte alignment"
        else:
            continue
        va, vb = xa.rom[d - ORG], xb.rom[b - ORG]
        if va != vb:
            if d in (0xFFEE, 0xFFEF):
                how = "checksum balance word (`$FFEE`)"
            out.append((d, b, va, vb, how))
    return out


def classify(xa: xref.Xref, xb: xref.Xref, al: Alignment) -> dict[str, list]:
    """Sort the differing blocks: calls to a moved routine, moved blocks, and the rest."""
    callee_a = {c.site: c.callee for c in xa.calls}
    callee_b = {c.site: c.callee for c in xb.calls}
    groups: dict[str, list] = {"relocated": [], "moved": [], "behaviour": []}
    deleted = [op for op in al.ops if op[0] == "delete"]
    inserted = [op for op in al.ops if op[0] == "insert"]

    def toks(x, addrs, ram=None):
        return [token(x.instrs[a], ram) for a in addrs]

    moved = set()
    for d in deleted:
        for i in inserted:
            if id(i) not in moved and toks(xa, d[1], al.ram) == toks(xb, i[2]):
                moved.update({id(d), id(i)})
                groups["moved"].append(("moved", d[1], i[2]))
                break
    for op in al.ops:
        if id(op) in moved:
            continue
        tag, aa, bb = op
        if (
            tag == "replace"
            and len(aa) == len(bb)
            and all(
                a in callee_a and b in callee_b and port_address(callee_a[a], xa, xb, al) == callee_b[b]
                for a, b in zip(aa, bb, strict=True)
            )
        ):
            groups["relocated"].append(op)
        else:
            groups["behaviour"].append(op)
    return groups


def _prev(al: Alignment, b: int) -> int:
    inv = {v: k for k, v in al.a_to_b.items()}
    before = [x for x in inv if x < b]
    return inv[max(before)] if before else ORG


def _fmt(i: Instr) -> str:
    if i.operand is None:
        return i.mnemonic
    if i.mode in ("imm8", "imm16"):
        return f"{i.mnemonic} #${i.operand:0{2 if i.mode == 'imm8' else 4}X}"
    if i.mode == "idx":
        return f"{i.mnemonic} ${i.operand:02X},x"
    if i.mode == "dir":
        return f"{i.mnemonic} ${i.operand:02X}"
    return f"{i.mnemonic} ${i.operand:04X}"


DEFS_B = ROOT / "analysis/defs/bluetop_2860.yaml"


def ported_defs(spec: dict, ports: list[Port], al: Alignment, rom_b: bytes) -> str:
    """The 0642 definition file with every map moved to its ported 2860 address."""
    import copy
    import hashlib

    out = copy.deepcopy(spec)
    out["rom"], out["file"] = "bluetop_2860", str(ROM_B.relative_to(ROOT))
    out["sha256"] = hashlib.sha256(rom_b).hexdigest()
    for v in out["variables"].values():
        v["addr"] = al.ram.get(v["addr"], v["addr"])
    by_id = {p.id: p for p in ports}
    for m in out["maps"]:
        p = by_id[m["id"]]
        if p.addr_b is None:
            raise ValueError(f"{m['id']} did not port: {p.status}")
        m["evidence"] = f"[PORT:pcmre.crossver {p.status}, from 0642 ${p.addr_a:04X}] " + str(m.get("evidence", ""))
        m["addr"] = p.addr_b
        if "entry" in m and p.entry_b is not None:
            m["entry"] = p.entry_b
    head = (
        "# Map definitions for the AE86 Bluetop ROM D151801-2860 (cap2-151801-2860.bin).\n"
        "# GENERATED by `python -m pcmre.crossver --write` from analysis/defs/bluetop.yaml: every map\n"
        "# is ported by following the 0642 code that reads it. Do not edit; fix bluetop.yaml or\n"
        "# pcmre/crossver.py instead. Names and notes are copied from 0642, so addresses quoted in\n"
        "# them (overlaps, evidence) are 0642 addresses; `addr` and `entry` are 2860's.\n"
    )
    return head + yaml.safe_dump(out, sort_keys=False, width=110, allow_unicode=True)


def run() -> tuple[str, list[Port]]:
    rom_a, rom_b = ROM_A.read_bytes(), ROM_B.read_bytes()
    xa = trace(rom_a, parse(LISTING_A, rom_a))
    xb = trace(rom_b)
    al = align(xa, xb)
    spec = yaml.safe_load(DEFS_A.read_text())
    ports = port_maps(spec, xa, xb, al)
    return render(spec, rom_a, rom_b, xa, xb, al, ports), ports


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    text, ports = run()
    if a.write:
        REPORT.write_text(text)
        rom_a, rom_b = ROM_A.read_bytes(), ROM_B.read_bytes()
        al = align(trace(rom_a, parse(LISTING_A, rom_a)), trace(rom_b))
        DEFS_B.write_text(ported_defs(yaml.safe_load(DEFS_A.read_text()), ports, al, rom_b))
        print(f"wrote {REPORT.relative_to(ROOT)} and {DEFS_B.relative_to(ROOT)}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
