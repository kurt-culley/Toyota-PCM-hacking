"""Readable 17140 ignition maps: advance in degrees over rpm and manifold pressure (kPa).

    uv run python -m pcmre.readable17140 --write   # docs/mr2/ignition_maps.md

Units come from the 17140 simulator (tests/mr2/test_sim17140.py) and the code (docs/mr2/maps.md):

- columns: RpmWord x 2 - $0200, one column per 256, RpmWord = rpm x 0.32 -> 800-5600 rpm in
  400 rpm steps;
- rows: Load x 4 - offset, one row per 256. Two kPa scales (docs/mr2/maps.md, STATUS kPa-scale
  conflict): the simulator default Load = 4.98 x kPa + 98.6, which rests on the factory PIM curve
  (V = 0.6 + 0.03 kPa, LIKELY) and the GUESS converter constant ``adc_k``; and the LIKELY
  256-counts-per-5-V scale Load = 6.14 x kPa + 123, on which the top row is one atmosphere;
- degrees: 15/64 degree per map count [EMU]. Anchored at the T-terminal check (fixed sum 170 =
  the factory 10 degrees BTDC), a warm untrimmed map cell is about its own advance, v x 15/64
  degrees BTDC (LIKELY, docs/mr2/maps.md).
"""

from __future__ import annotations

import argparse
import sys

from .paths import DOC_IGNITION_MAPS_17140, ROM_17140, ROOT

ROM = ROM_17140
DOC = DOC_IGNITION_MAPS_17140
LOAD_PER_KPA, LOAD_AT_0 = 4.98, 98.6  # simulator default scale
LIKELY_PER_KPA, LIKELY_AT_0 = 6.14, 123.0  # 256 counts per 5 V (LIKELY)
MAPS = {"A": (0xF1EF, "P34 = 1"), "B": (0xF25D, "P34 = 0")}


def degrees(v: int) -> float:
    """A warm, untrimmed map cell in degrees BTDC (LIKELY: within 0.04 degrees of the anchored sum)."""
    return v * 15 / 64


def table(rom: bytes, addr: int) -> tuple[list[int], list[float], list[float], list[list[int]]]:
    h = rom[addr - 0xF000 : addr - 0xF000 + 6]
    off1, max1, off2, max2 = h[0] << 8 | h[1], h[2], h[3] << 8 | h[4], h[5]
    cols, rows = max1 + 1, max2 + 1
    rpm = [round((off1 + 256 * c) / 2 / 0.32) for c in range(cols)]
    load = [(off2 + 256 * r) / 4 for r in range(rows)]
    kpa = [(x - LOAD_AT_0) / LOAD_PER_KPA for x in load]
    likely = [(x - LIKELY_AT_0) / LIKELY_PER_KPA for x in load]
    data = rom[addr - 0xF000 + 6 : addr - 0xF000 + 6 + cols * rows]
    return rpm, kpa, likely, [list(data[r * cols : (r + 1) * cols]) for r in range(rows)]


def build() -> str:
    rom = ROM.read_bytes()
    out = [
        "# 17140 ignition maps in degrees",
        "",
        "This page comes from `uv run pcmre readable17140 --write` "
        "([`src/pcmre/readable17140.py`](../../src/pcmre/readable17140.py)). Do not edit it by hand.",
        "",
        "## Summary",
        "",
        "The 17140 has two base ignition maps. Jumper J8 (P34) selects one of them. "
        "This page gives each cell in degrees BTDC, for a warm engine with no trims. "
        "The rows are manifold pressure in kPa (absolute), on two scales. The columns are engine speed in rpm.",
        "",
        "<details>",
        "<summary>Accuracy of the values</summary>",
        "",
        "- **Degree scale (CONFIRMED in the simulator):** one map count is 15/64°. The simulator measured this "
        "at four engine speeds [EMU:tests/mr2/test_sim17140.py].",
        "- **Absolute degrees (LIKELY):** each cell is value × 15/64° BTDC. The anchor is the T-terminal check. "
        "With the throttle closed and T connected to E1, the ROM uses a fixed sum. The factory sets this to "
        "10° BTDC. Warm and with no trims, a map cell is then within 0.04° of its own advance. A warm idle "
        "with T open uses the idle table and gives 16.0° BTDC "
        "[EMU:tests/mr2/test_ross17140.py::test_t_terminal_fixed_sum_only_with_the_throttle_closed]. "
        "Coolant and trim terms add to the value. A timing light at a warm idle with T open must show "
        "about 16° ([`maps.md`](maps.md)).",
        "- **kPa scale (two scales, open item):** the LIKELY scale is Load ≈ 6.14 × kPa + 123 (256 counts "
        "for 5 V). On this scale the top row is one atmosphere. The simulator default (the first number in "
        "each row) is Load ≈ 4.98 × kPa + 98.6. It uses the factory MAP sensor curve and a GUESS converter "
        "constant. The Load value at key-on, engine off, decides between them "
        "([open items](../project/open_items.md)).",
        "- High load is at the top of each table, as on a tuning screen. 100 kPa is approximately wide-open "
        "throttle at sea level.",
        "",
        "</details>",
        "",
    ]
    for name, (addr, sel) in MAPS.items():
        rpm, kpa, likely, rows = table(rom, addr)
        out += [
            f"## Map {name} `${addr:04X}` ({sel})",
            "",
            "| kPa (default / LIKELY) \\ rpm | " + " | ".join(str(r) for r in rpm) + " |",
            "|---|" + "---|" * len(rpm),
        ]
        for r in range(len(rows) - 1, -1, -1):
            label = f"**{kpa[r]:.0f}** / {likely[r]:.0f}"
            out.append(f"| {label} | " + " | ".join(f"{degrees(v):.1f}" for v in rows[r]) + " |")
        out.append("")
    out += [
        "Between sites the ECU interpolates in both rpm and pressure. Outside the table it holds the edge values.",
        "On a naturally aspirated engine the manifold cannot exceed about 100 kPa. On the LIKELY scale the "
        "top row of both maps is one atmosphere (101 kPa), so every row is used. On the simulator default "
        "the 117 and 130 kPa rows would never be reached, which is one reason that scale is doubted (maps.md).",
        "",
    ]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    md = build()
    if a.write:
        DOC.write_text(md)
        print(f"wrote {DOC.relative_to(ROOT)}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
