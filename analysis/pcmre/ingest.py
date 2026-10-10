"""Day-one ingest of a new D151801-family ROM (built for the 17140; works on any size).

    PYTHONPATH=analysis uv run python -m pcmre.ingest "AW11 MR2 PCM/89661-17140.bin" --name mr2_17140
    ... --write   # analysis/<name>/ingest.md and analysis/defs/<name>.yaml (auto-ported maps)

One command turns a fresh dump into a first map of the program:

1. **Basics:** size and origin (the ROM ends at $FFFF), SHA-256, vectors, and the
   word-sum check against the Bluetop's $AA55 convention.
2. **Trace and port:** the code is traced from the vectors (``pcmre.xref``) and aligned with
   the Bluetop 0642 program (``pcmre.crossver``). Every Bluetop map is followed through the
   code that reads it; RAM moves and behaviour changes are listed.
3. **Data index:** every pointer from code into data, with its size up to the next
   referenced address: the candidate tables.
4. **Ross matches:** Ross's transcribed 17030 ignition table (17 x 8 raw bytes) is searched
   byte for byte in every layout, and his digitised density and speed maps are matched by
   shape (correlation) against the candidate tables.
5. **Inputs and constants:** the serial-ADC result variables, mixture-screw candidates
   (Ross: MX1 = reading - 128), and rpm-like constants (rev limit, T-VIS switching).

Everything found is a lead with its evidence, not a conclusion: the confidence column says
how much each finding rests on. Day one of P4 is reviewing this report.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import crossver as cv
from . import xref
from .checksum import rom_sum
from .idalisting import parse
from .roundtrip import ROOT

ROSS = ROOT / "docs/ross/figures"
VECTORS = ["TRAP", "SCI", "TOF", "OCF", "ICF", "IRQ1", "SWI", "NMI", "RES"]  # from $FFEE
RDR = 0x12  # SCI receive data: the serial ADC replies here


# -- basics ---------------------------------------------------------------------------------


@dataclass
class Basics:
    size: int
    org: int
    sha256: str
    word_sum: int
    vectors: dict[str, int]


def basics(rom: bytes) -> Basics:
    if len(rom) % 0x400 or len(rom) > 0x10000:
        raise ValueError(f"unexpected ROM size {len(rom)} bytes")
    org = 0x10000 - len(rom)
    vec = {n: rom[0xFFEE + 2 * k - org] << 8 | rom[0xFFEF + 2 * k - org] for k, n in enumerate(VECTORS)}
    return Basics(len(rom), org, hashlib.sha256(rom).hexdigest(), rom_sum(rom), vec)


# -- data index -------------------------------------------------------------------------------


def code_bytes(x: xref.Xref) -> set[int]:
    return {a + k for a, i in x.instrs.items() for k in range(i.length)}


def data_regions(x: xref.Xref) -> list[tuple[int, int]]:
    """Runs of ROM bytes the tracer never reached as code (vectors excluded): [start, end)."""
    code = code_bytes(x)
    out, start = [], None
    for a in range(x.org, 0xFFEE):
        if a not in code and start is None:
            start = a
        elif a in code and start is not None:
            out.append((start, a))
            start = None
    if start is not None:
        out.append((start, 0xFFEE))
    return out


@dataclass
class DataRef:
    target: int
    sites: list[int]
    size: int  # bytes up to the next referenced address or the end of the data run
    helper: str  # the routine called right after the pointer is loaded, if any


def data_refs(x: xref.Xref) -> list[DataRef]:
    """Every 16-bit operand that points into data, grouped by target."""
    code = code_bytes(x)
    starts = sorted(x.instrs)
    callee = {c.site: c.callee for c in x.calls}
    by_target: dict[int, list[int]] = {}
    for a in starts:
        i = x.instrs[a]
        if (
            i.mode in ("imm16", "ext")
            and i.operand is not None
            and x.org <= i.operand < 0xFFEE
            and i.operand not in code
        ):
            by_target.setdefault(i.operand, []).append(a)
    regions = data_regions(x)
    targets = sorted(by_target)
    out = []
    for k, t in enumerate(targets):
        end = next((e for s, e in regions if s <= t < e), t + 1)
        nxt = targets[k + 1] if k + 1 < len(targets) and targets[k + 1] < end else end
        helpers = set()
        for s in by_target[t]:
            n = starts.index(s)
            for follow in starts[n + 1 : n + 4]:
                if follow in callee:
                    helpers.add(x.routine_name(callee[follow]))
                    break
        out.append(DataRef(t, by_target[t], nxt - t, ", ".join(sorted(helpers))))
    return out


# -- Ross matching ------------------------------------------------------------------------------


def _ross_csv(name: str) -> tuple[list[str], list[list[str]]]:
    with (ROSS / name).open() as f:
        rows = list(csv.reader(line for line in f if not line.startswith("#")))
    return rows[0], rows[1:]


def ross_ignition() -> list[list[int]]:
    """Ross's 17030 ignition table: 17 rpm rows x 8 MAP columns of raw bytes."""
    _, rows = _ross_csv("p12_ignition_table_17030_raw.csv")
    return [[int(v) for v in r[1:]] for r in rows]


def ross_curves() -> dict[str, list[float | None]]:
    out = {}
    head, rows = _ross_csv("p04_density_map.csv")
    for k, col in enumerate(head[1:], start=1):
        out[f"density map ({col})"] = [float(r[k]) if r[k] else None for r in rows]
    for name, label in (("p05_speed_corr_above_3200.csv", "above"), ("p05_speed_corr_below_3200.csv", "below")):
        _, rows = _ross_csv(name)
        out[f"speed map ({label} 3200 rpm)"] = [float(r[1]) for r in rows]
    return out


@dataclass
class TableMatch:
    addr: int
    layout: str
    mean_abs_diff: float
    code_overlap: int = 0


def match_ignition(rom: bytes, org: int, code: set[int], top: int = 3) -> list[TableMatch]:
    """Slide Ross's 136-byte table over the whole ROM in both storage orders (mean absolute difference).

    The whole ROM is scanned, not just the traced data runs, because helper routines can sit
    between tables; ``code_overlap`` in the result says how many bytes of a window were traced
    as code (a real table has none).
    """
    t = ross_ignition()
    layouts = {
        "17 rpm rows x 8 MAP": [v for row in t for v in row],
        "8 MAP rows x 17 rpm": [t[r][c] for c in range(8) for r in range(17)],
    }
    found = []
    for name, flat in layouts.items():
        n = len(flat)
        for off in range(len(rom) - n + 1):
            w = rom[off : off + n]
            mad = sum(abs(x - y) for x, y in zip(w, flat, strict=True)) / n
            found.append(TableMatch(org + off, name, mad))
    best = sorted(found, key=lambda m: m.mean_abs_diff)[:top]
    for m in best:
        m.code_overlap = sum(1 for a in range(m.addr, m.addr + 136) if a in code)
    return best


def _pearson(xs: list[float], ys: list[float]) -> float:
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / (sx * sy)


def match_curve(rom: bytes, org: int, refs: list[DataRef], values: list[float | None]) -> list[tuple[float, int]]:
    """Correlation of a Ross curve with each referenced table of at least its length (shape only)."""
    keep = [k for k, v in enumerate(values) if v is not None]
    out = []
    for r in refs:
        if r.size < len(values):
            continue
        w = rom[r.target - org : r.target - org + len(values)]
        out.append((_pearson([w[k] for k in keep], [values[k] for k in keep]), r.target))
    return sorted(out, reverse=True)[:3]


# -- inputs and constants --------------------------------------------------------------------------


def _last_load(x: xref.Xref, starts: list[int], k: int, reg: str, back: int = 5):
    """The most recent ``ldaa``/``ldab`` (reg ``a``/``b``) within ``back`` instructions before index k."""
    for b in reversed(starts[max(0, k - back) : k]):
        j = x.instrs[b]
        if j.mnemonic == f"ld{reg}" or j.mnemonic == f"lda{reg}":
            return j
        if j.mnemonic in ("ldd", "pul" + reg, "t" + ("ba" if reg == "a" else "ab")):
            return None
    return None


def ram_arrays(x: xref.Xref) -> list[tuple[int, int, bool]]:
    """``ldx #$00nn / abx`` sites: indexed RAM arrays. (site, base, the routine also transmits on the SCI).

    On the Bluetop the serial-ADC results are stored this way at $54 + channel, in the routine
    that sends the next channel request through TDR ($13) [ROM:$FABB].
    """
    starts = sorted(x.instrs)
    tx = {
        e
        for e, body in x.routines.items()
        if any(
            x.instrs[a].mnemonic.startswith("st") and x.instrs[a].mode == "dir" and x.instrs[a].operand == 0x13
            for a in body
        )
    }
    calls: dict[int, set[int]] = {}
    for c in x.calls:
        calls.setdefault(c.caller, set()).add(c.callee)
    out = []
    for k, a in enumerate(starts[:-1]):
        i, j = x.instrs[a], x.instrs[starts[k + 1]]
        if i.mnemonic == "ldx" and i.mode == "imm16" and i.operand < 0x100 and j.mnemonic == "abx":
            r = next((e for e, body in x.routines.items() if a in body), None)
            sends = (r in tx or bool(calls.get(r, set()) & tx)) and i.operand != 0  # base 0: a plain RAM pointer
            out.append((a, i.operand, sends))
    return out


def mixture_candidates(x: xref.Xref) -> list[tuple[int, int, str]]:
    """Ross R-M01: MX1 = reading - 128. #$80 arithmetic on a value just loaded from RAM into the same register."""
    starts = sorted(x.instrs)
    out = []
    for k, a in enumerate(starts):
        i = x.instrs[a]
        if (
            i.mode == "imm8"
            and i.operand == 0x80
            and i.mnemonic[:3] in ("sub", "add", "eor")
            and i.mnemonic[-1] in "ab"
        ):
            src = _last_load(x, starts, k, i.mnemonic[-1], back=3)
            if src is not None and src.mode == "dir":
                out.append((a, src.operand, f"{src.mnemonic} ${src.operand:02X} … {i.mnemonic} #$80"))
    return out


def rpm_constants(x: xref.Xref, ram: dict[int, int]) -> list[tuple[int, str]]:
    """Rev-limit and T-VIS-like constants, read against the rpm variables ported from the Bluetop.

    ``ram`` is the Bluetop -> this ROM RAM remap. lilRPM (Bluetop $65) is rpm/25; deltaNE
    (Bluetop $66) is µs per 180°, so rpm = 30e6/value.
    """
    lil, dne = ram.get(0x65, 0x65), ram.get(0x66, 0x66)
    starts = sorted(x.instrs)
    out = []
    for k, a in enumerate(starts):
        i = x.instrs[a]
        if i.mnemonic == "cpx" and i.mode == "imm16" and k:
            prev = x.instrs[starts[k - 1]]
            if prev.mnemonic == "ldx" and prev.mode == "dir" and prev.operand == dne and i.operand:
                out.append((a, f"ldx deltaNE / cpx #${i.operand:04X} = {30e6 / i.operand:.0f} rpm (rev-limit-like)"))
        if i.mnemonic in ("cmpa", "cmpb") and i.mode == "imm8":
            src = _last_load(x, starts, k, i.mnemonic[-1])
            if src is not None and src.mode == "dir" and src.operand == lil:
                out.append((a, f"lilRPM vs #${i.operand:02X} = {i.operand * 25} rpm"))
        if i.mnemonic == "subd" and i.mode == "imm16" and i.operand == 0xAA55:
            out.append((a, "subd #$AA55: the Bluetop checksum convention"))
    return out


# -- report ---------------------------------------------------------------------------------------


def run(path: Path, name: str) -> tuple[str, str]:
    rom_b = path.read_bytes()
    bb = basics(rom_b)
    rom_a = cv.ROM_A.read_bytes()
    xa = cv.trace(rom_a, parse(cv.LISTING_A, rom_a))
    xb = cv.trace(rom_b)
    al = cv.align(xa, xb)
    spec = yaml.safe_load(cv.DEFS_A.read_text())
    ports = cv.port_maps(spec, xa, xb, al)
    refs = data_refs(xb)
    inv = {v: k for k, v in al.ram.items()}

    def ram_name(addr: int) -> str:
        a = inv.get(addr, addr)
        n = xa.name(a)
        return f"{n} (Bluetop ${a:02X})" if not n.startswith("$") else n

    aligned = len(al.a_to_b) / max(1, len(xa.instrs))
    lines = [
        f"# Ingest report: `{path.name}` ({name})",
        "",
        "Generated by `python -m pcmre.ingest`. Every finding is a lead for P4 review, not a conclusion.",
        "",
        "## Basics",
        "",
        "| | |",
        "|---|---|",
        f"| Size | {bb.size} bytes, `${bb.org:04X}`–`$FFFF` |",
        f"| SHA-256 | `{bb.sha256}` |",
        f"| Word sum | `${bb.word_sum:04X}` "
        f"({'matches' if bb.word_sum == 0xAA55 else 'differs from'} the Bluetop `$AA55` convention) |",
        "| Vectors | " + ", ".join(f"{n} `${v:04X}`" for n, v in bb.vectors.items()) + " |",
        f"| Code reached from the vectors | {len(xb.instrs)} instructions, {len(xb.routines)} routines, "
        f"{len(code_bytes(xb))} bytes |",
        f"| Tracer errors | {len(xb.errors)} |",
        "",
        "## Against the Bluetop program",
        "",
        f"{len(al.a_to_b)} of {len(xa.instrs)} Bluetop instructions align ({aligned:.0%}). "
        + (
            "The same program family: map ports below are meaningful."
            if aligned >= 0.5
            else "**Low alignment: a different program; treat the map ports with caution.**"
        ),
        "",
        "| Bluetop map | Bluetop | This ROM | Port |",
        "|---|---|---|---|",
    ]
    for p in ports:
        lines.append(
            f"| `{p.id}` | `${p.addr_a:04X}` | {'—' if p.addr_b is None else f'`${p.addr_b:04X}`'} | {p.status} |"
        )
    lines += [
        "",
        f"RAM variables that moved: {len(al.ram)}. "
        + ", ".join(f"`${a:02X}`→`${b:02X}`" for a, b in sorted(al.ram.items())),
        "",
    ]
    groups = cv.classify(xa, xb, al)
    wd = [w for w in cv.wide_operand_diffs(xa, xb, al, ports) if w[5] is None]
    lines += [
        f"Behaviour-change candidates against the Bluetop: {len(groups['behaviour'])} instruction blocks, "
        f"{len(wd)} changed 16-bit constants. Full list: `python -m pcmre.crossver`-style report via "
        "`pcmre.crossver.render` (run on demand).",
        "",
        "## Candidate tables (pointers from code into data)",
        "",
        "| Address | Size to next | Read via | Referenced from |",
        "|---|---|---|---|",
    ]
    for r in refs:
        lines.append(
            f"| `${r.target:04X}` | {r.size} | {r.helper or '—'} | "
            + ", ".join(f"`${s:04X}`" for s in r.sites[:4])
            + " |"
        )
    lines += ["", "## Ross's tables", ""]
    best = match_ignition(rom_b, bb.org, code_bytes(xb))
    lines += ["**17030 ignition table** (136 raw bytes, Ross p12), best windows by mean absolute difference:", ""]
    lines += ["| Address | Layout | Mean abs diff (counts) | Bytes traced as code |", "|---|---|---|---|"]
    lines += [f"| `${m.addr:04X}` | {m.layout} | {m.mean_abs_diff:.1f} | {m.code_overlap} |" for m in best]
    lines += [
        "",
        "Below about 5 counts: the same table, or a close calibration. Above 20: not present as such.",
        "",
        "**Digitised curves** (shape only; Ross's units are physical, the ROM's raw):",
        "",
        "| Curve | Best tables (correlation) |",
        "|---|---|",
    ]
    for cname, values in ross_curves().items():
        m = match_curve(rom_b, bb.org, refs, values)
        lines.append(f"| {cname} | " + ", ".join(f"`${a:04X}` ({r:.2f})" for r, a in m) + " |")
    lines += [
        "",
        "Correlation near 1.0 on a table of the right length is a lead; monotonic curves correlate with many tables.",
        "",
        "## Inputs and constants",
        "",
        "**Indexed RAM arrays** (`ldx #$00nn / abx`; on the Bluetop the ADC results are `$54` + channel, "
        "stored by the routine that also transmits the channel request):",
        "",
    ]
    arr = ram_arrays(xb)
    lines += [
        f"- `${a:04X}`: base `${base:02X}`"
        + (" — **in an SCI-transmitting routine: ADC result array**" if sends else "")
        for a, base, sends in arr
    ] or ["- none found"]
    lines += ["", "**Mixture-screw candidates** (reading − 128, Ross R-M01):", ""]
    lines += [f"- `${a:04X}`: {s} — source {ram_name(src)}" for a, src, s in mixture_candidates(xb)] or ["- none found"]
    lines += ["", "**rpm constants** (against the ported rpm variables):", ""]
    lines += [f"- `${a:04X}`: {s}" for a, s in rpm_constants(xb, al.ram)] or ["- none found"]
    lines.append("")

    ported = cv.ported_defs(
        spec,
        ports,
        al,
        rom_b,
        rom_name=name,
        rom_file=path,
        head=(
            f"# Map definitions for {path.name}, AUTO-PORTED from analysis/defs/bluetop.yaml by\n"
            "# `python -m pcmre.ingest`. A starting point for P4: review every map before trusting it,\n"
            "# then curate this file by hand (it is not regenerated once curation starts).\n"
        ),
        skip_unported=True,
    )
    return "\n".join(lines), ported


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom", type=Path)
    ap.add_argument("--name", required=True, help="short name, e.g. mr2_17140")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    report, ported = run(a.rom.resolve(), a.name)
    if a.write:
        out = ROOT / "analysis" / a.name
        out.mkdir(parents=True, exist_ok=True)
        (out / "ingest.md").write_text(report)
        defs = ROOT / "analysis/defs" / f"{a.name}.yaml"
        if defs.exists():
            print(f"{defs.relative_to(ROOT)} exists (curated?): not overwritten")
        else:
            defs.write_text(ported)
        print(f"wrote analysis/{a.name}/ingest.md")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
