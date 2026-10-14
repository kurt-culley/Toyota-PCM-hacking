"""Labelled source for a ROM that has no IDA listing (the MR2 17140), from a symbols file.

    PYTHONPATH=analysis uv run python -m pcmre.symlisting mr2_17140            # check round trip
    PYTHONPATH=analysis uv run python -m pcmre.symlisting mr2_17140 --write    # also write the outputs

The symbols file ``analysis/<name>/symbols.yaml`` is the single hand-maintained record of
what we know about the program: names and notes for RAM, ROM routines and data blocks.
Everything else comes from the ROM bytes. The code/data split is the trace from the vectors
(``pcmre.xref``); bytes no path reaches are emitted as data. Outputs:

- ``analysis/<name>/<name>.asm``: asl source; the round trip proves it reassembles to the
  identical image;
- ``analysis/<name>/xref.md``: cross-references and call graph with the same names.

Symbols file layout (all keys optional)::

    rom: {file: AW11 MR2 PCM/89661-17140.bin}
    ram:     {0x40: {name: Foo, note: "..."}, ...}        # or 0x40: Foo
    labels:  {0xF2BE: {name: Reset, note: "...", block: "multi-line header"}}
    data:    [{start: 0xF000, end: 0xF002, kind: byte|word, name: Tbl, note: "..."}]
    notes:   {0xF2C0: "comment on one statement"}
"""

from __future__ import annotations

import argparse
import sys

import yaml

from . import xref
from .emit import emit_asl
from .idalisting import Item, Listing
from .roundtrip import ROOT, assemble_asl

# HD6301V1 internal registers ($00-$1F), Hitachi handbook names.
REGISTERS = {
    0x00: "DDR1", 0x01: "DDR2", 0x02: "PORT1", 0x03: "PORT2", 0x04: "DDR3", 0x05: "DDR4",
    0x06: "PORT3", 0x07: "PORT4", 0x08: "TCSR", 0x09: "FRCH", 0x0A: "FRCL", 0x0B: "OCRH",
    0x0C: "OCRL", 0x0D: "ICRH", 0x0E: "ICRL", 0x0F: "P3CSR", 0x10: "RMCR", 0x11: "TRCSR",
    0x12: "RDR", 0x13: "TDR", 0x14: "RAMCR",
    # D151801 second timer channel (Bluetop listing: TmrCntStat2 / OutCmp2 / InpCap2)
    0x18: "TCSR2", 0x1B: "OCR2H", 0x1C: "OCR2L", 0x1D: "ICR2H", 0x1E: "ICR2L",
}  # fmt: skip


def _entry(v) -> dict:
    return v if isinstance(v, dict) else {"name": v}


def load(name: str) -> tuple[dict, bytes]:
    spec = yaml.safe_load((ROOT / "analysis" / name / "symbols.yaml").read_text()) or {}
    rom = (ROOT / spec["rom"]["file"]).read_bytes()
    return spec, rom


def build(spec: dict, rom: bytes) -> tuple[Listing, xref.Xref]:
    org = 0x10000 - len(rom)
    ram = dict(REGISTERS)
    ram.update({a: _entry(v)["name"] for a, v in (spec.get("ram") or {}).items()})
    labels = {a: [_entry(v)["name"]] for a, v in (spec.get("labels") or {}).items()}
    for d in spec.get("data") or []:
        if d.get("name"):
            labels.setdefault(d["start"], [d["name"]])
    x = xref.analyse(rom, Listing(ram_labels=ram, labels=labels, items=[], org=org))

    notes = {a: [str(v)] for a, v in (spec.get("notes") or {}).items()}
    for a, v in (spec.get("labels") or {}).items():
        if _entry(v).get("note"):
            notes.setdefault(a, []).insert(0, _entry(v)["note"])
    blocks = {
        a: str(_entry(v)["block"]).splitlines() for a, v in (spec.get("labels") or {}).items() if _entry(v).get("block")
    }
    words: set[int] = set()
    for d in spec.get("data") or []:
        if d.get("note"):
            blocks.setdefault(d["start"], []).append(d["note"])
        if d.get("kind") == "word":
            words.update(range(d["start"], d["end"] + 1))

    # Instruction starts that do not overlap an earlier instruction ("skip" tricks keep the first).
    code: dict[int, int] = {}
    covered = -1
    for a in sorted(x.instrs):
        if a <= covered:
            continue
        code[a] = x.instrs[a].length
        covered = a + x.instrs[a].length - 1
    breaks = set(code) | set(labels) | {d["start"] for d in spec.get("data") or []}
    breaks |= {d["end"] + 1 for d in spec.get("data") or []}

    items: list[Item] = []
    a, end = org, org + len(rom)
    while a < end:
        if a in code:
            n = code[a]
            it = Item(a, n, "code", x.instrs[a].mnemonic)
        else:
            kind = "word" if a in words and a + 1 < end and a + 1 in words else "byte"
            step = 2 if kind == "word" else 1
            n = step
            while n < 8 and a + n < end and a + n not in breaks and a + n not in code:
                if (a + n in words) != (kind == "word"):
                    break
                n += step
            it = Item(a, n, kind, "")
        it.comment = notes.get(a, [])
        it.pre = blocks.get(a, [])
        items.append(it)
        a += n
    return Listing(ram_labels=ram, labels=labels, items=items, org=org), x


def dropped_labels(spec: dict, listing: Listing) -> list[int]:
    """Symbols-file labels that fall inside an instruction, so the listing cannot show them."""
    starts = {it.addr for it in listing.items}
    wanted = set(spec.get("labels") or {}) | {d["start"] for d in spec.get("data") or []}
    wanted |= set(spec.get("notes") or {})
    return sorted(a for a in wanted if a not in starts)


def run(name: str, write: bool) -> bool:
    spec, rom = load(name)
    listing, x = build(spec, rom)
    title = spec.get("title", f"{name}: generated source")
    src = emit_asl(listing, rom, title).replace(
        "; Labels and comments imported from the IDA 4.9 listing; bytes from the ROM.",
        f"; Names and notes from analysis/{name}/symbols.yaml; bytes from the ROM.",
    )
    got = assemble_asl(src, listing.org, 0xFFFF)
    ok = got == rom
    for a in dropped_labels(spec, listing):
        print(f"warning: ${a:04X} is inside an instruction; its label/note is not shown", file=sys.stderr)
    print(f"{name}: {len(x.routines)} routines, {len(x.instrs)} instructions; asl round trip "
          f"{'IDENTICAL' if ok else 'MISMATCH'}")  # fmt: skip
    if write and ok:
        out = ROOT / "analysis" / name
        (out / f"{name}.asm").write_text(src)
        (out / "xref.md").write_text(xref.render(x, listing, title))
        print(f"wrote analysis/{name}/{name}.asm and xref.md")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    return 0 if run(a.name, a.write) else 1


if __name__ == "__main__":
    sys.exit(main())
