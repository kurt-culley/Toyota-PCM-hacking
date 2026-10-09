"""Emit re-assemblable HD6301 source from a ROM image plus an imported listing.

Output targets the Macroassembler AS (``asl``, ``cpu 6301``). All data bytes
come from the ROM itself and every instruction is re-decoded from the ROM, so
the listing only contributes names, comments and the code/data split. The
round-trip gate (``pcmre.roundtrip``) proves the result assembles back to the
identical image.
"""

from __future__ import annotations

import bisect
import re

from .hd6301 import BIT_DIR, BIT_IDX, DIR, EXT, IDX, IMM8, IMM16, INH, REL, decode
from .idalisting import Item, Listing

_SYM = re.compile(r"^#?([A-Za-z_][\w]*)$")


def _ascii(s: str) -> str:
    return "".join(ch if 32 <= ord(ch) < 127 or ch == "\t" else "?" for ch in s)


def _comment(parts: list[str]) -> str:
    # IDA appends a one-character ASCII rendering to many byte values ("; O",
    # "; '?'"); it is noise in source form, so drop it.
    keep = [_ascii(c) for c in parts if not (len(c) == 1 or re.fullmatch(r"'.'", c))]
    text = " | ".join(keep).rstrip()
    # asl treats a trailing backslash as a line continuation.
    while text.endswith("\\"):
        text = text[:-1].rstrip()
    return f"; {text}" if text else ""


def _hex8(v: int) -> str:
    return f"${v:02X}"


def _hex16(v: int) -> str:
    return f"${v:04X}"


class _Symbols:
    def __init__(self, listing: Listing, rom_len: int):
        self.rom_lo = listing.org
        self.rom_hi = listing.org + rom_len
        self.ram = dict(listing.ram_labels)
        self.rom = {a: names[0] for a, names in listing.labels.items()}
        self.by_name = {n: a for a, n in self.ram.items()}
        for a, names in listing.labels.items():
            for n in names:
                self.by_name[n] = a
        self.starts = sorted(it.addr for it in listing.items)
        self.extra: dict[int, str] = {}  # labels we had to invent (unlabelled branch targets)

    def code_ref(self, addr: int) -> str:
        """Symbolic name for a ROM address used as a jump/branch target."""
        if addr in self.rom:
            return self.rom[addr]
        if self.rom_lo <= addr < self.rom_hi:
            # Targets inside another statement (Denso "skip" tricks such as a
            # CPX # whose operand is itself a BSR) become "label+offset".
            i = bisect.bisect_right(self.starts, addr) - 1
            start = self.starts[i]
            if start in self.rom:
                name = self.rom[start]
            else:
                name = self.extra.setdefault(start, f"L_{start:04X}")
            return name if start == addr else f"{name}+{addr - start}"
        return _hex16(addr)

    def data_ref(self, addr: int, width: int) -> str:
        if addr in self.ram:
            return self.ram[addr]
        if addr in self.rom:
            return self.rom[addr]
        return _hex8(addr) if width == 1 else _hex16(addr)


def _ida_symbol(it: Item) -> str | None:
    parts = it.ida_text.split(None, 1)
    if len(parts) < 2:
        return None
    m = _SYM.match(parts[1].strip())
    return m.group(1) if m else None


def _operand(it: Item, ins, sym: _Symbols) -> tuple[str, bool]:
    """Return (operand text, needs forced extended addressing)."""
    text = _operand_text(it, ins, sym)
    force = ins.mode == EXT and ins.operand < 0x100
    return text, force


def _operand_text(it: Item, ins, sym: _Symbols) -> str:
    mode, v = ins.mode, ins.operand
    if mode == INH:
        return ""
    if mode in (IMM8, IMM16):
        # Keep IDA's symbolic immediate (e.g. "#JumpTable") when it names this value.
        s = _ida_symbol(it)
        if s and sym.by_name.get(s) == v:
            return f"#{s}"
        return "#" + (_hex8(v) if mode == IMM8 else _hex16(v))
    if mode == DIR:
        return sym.data_ref(v, 1)
    if mode == EXT:
        if ins.mnemonic in ("jmp", "jsr"):
            ref = sym.code_ref(v)
        else:
            ref = sym.data_ref(v, 2)
        # A zero-page address used with extended addressing must be forced
        # (see _operand), or the assembler would shorten it to direct mode.
        return ref
    if mode == IDX:
        return f"{_hex8(v)},x"
    if mode == REL:
        return sym.code_ref(v)
    if mode == BIT_DIR:
        return f"#{_hex8(ins.imm)},{sym.data_ref(v, 1)}"
    if mode == BIT_IDX:
        return f"#{_hex8(ins.imm)},{_hex8(v)},x"
    raise AssertionError(mode)


DIALECTS = ("asl", "dasm")


def emit_asl(listing: Listing, rom: bytes, title: str = "") -> str:
    return emit(listing, rom, title, "asl")


def emit(listing: Listing, rom: bytes, title: str = "", dialect: str = "asl") -> str:
    """Generate source for ``asl`` (primary) or legacy ``dasm`` (cross-check).

    dasm's 6303 table mis-encodes the HD6301 AIM/OIM/EIM/TIM group, so a ROM
    that uses them can only be cross-checked with asl.
    """
    if dialect not in DIALECTS:
        raise ValueError(dialect)
    asl = dialect == "asl"
    db, dw = ("db", "dw") if asl else ("dc.b", "dc.w")
    sym = _Symbols(listing, len(rom))
    body: list[str] = []

    for it in listing.items:
        for c in it.pre:
            body.append(f"; {_ascii(c)}" if c else ";")
        for name in listing.labels.get(it.addr, []):
            body.append(f"{name}:")
        body.append(f"@@LABEL {it.addr}")  # placeholder for invented labels
        comment = _comment(it.comment)

        if it.kind == "code":
            ins = decode(rom, it.addr, listing.org)
            if not asl and ins.mode in (BIT_DIR, BIT_IDX):
                raise ValueError(f"dasm cannot encode {ins.mnemonic} at ${it.addr:04X}")
            text, force = _operand(it, ins, sym)
            if force:
                mnem, text = (ins.mnemonic, f">{text}") if asl else (f"{ins.mnemonic}.e", text)
            else:
                mnem = ins.mnemonic
            stmt = f"\t{mnem}\t{text}".rstrip()
        elif it.kind == "byte":
            data = rom[it.addr - listing.org : it.addr - listing.org + it.size]
            stmt = f"\t{db}\t" + ",".join(_hex8(b) for b in data)
        else:
            words = []
            for k in range(0, it.size, 2):
                off = it.addr - listing.org + k
                w = (rom[off] << 8) | rom[off + 1]
                words.append(sym.code_ref(w) if w in sym.rom else _hex16(w))
            stmt = f"\t{dw}\t" + ",".join(words)
        body.append(f"{stmt}\t\t{comment}" if comment else stmt)

    # Place the invented labels (always on statement starts, see code_ref).
    out_body = []
    for line in body:
        if line.startswith("@@LABEL "):
            a = int(line.split()[1])
            if a in sym.extra:
                out_body.append(f"{sym.extra[a]}:")
            continue
        out_body.append(line)

    head = [
        f"; {title}" if title else "; generated source",
        "; Generated by analysis/pcmre (do not edit by hand; regenerate instead).",
        "; Labels and comments imported from the IDA 4.9 listing; bytes from the ROM.",
        "",
        *(["\tcpu\t6301", "\tpage\t0"] if asl else ["\tprocessor\thd6303"]),
        "",
        "; ---- RAM / special function registers (from the listing's RegRAM segment)",
    ]
    for a in sorted(sym.ram):
        head.append(f"{sym.ram[a]}\tequ\t{_hex8(a)}")
    head += ["", "; ---- ROM", f"\torg\t{_hex16(listing.org)}", ""]
    return "\n".join(head + out_body + (["", "\tend", ""] if asl else [""]))
