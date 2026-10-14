"""Decode a serial-link log from the Pico 2 W logger into physical units.

    PYTHONPATH=analysis uv run python -m pcmre.peeklog capture.txt            # table on screen
    PYTHONPATH=analysis uv run python -m pcmre.peeklog capture.txt -o log.csv # CSV

The logger (hardware/peek-logger) prints ``D,<ms>,<addr>,<word>`` for each reply, plus
``S,<ms>,<state>`` and ``M,<ms>,<addr>`` lines (docs/mr2/serial_link.md). Each row of the
output is one pass over the polled list, holding the latest value of every variable.

Scalings and their confidence come from docs/mr2/maps.md; GUESS ones are marked in the
column header. A byte variable is the high byte of the reply.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Var:
    name: str
    word: bool
    unit: str
    scale: Callable[[int], float]
    note: str = ""


VARS: dict[int, Var] = {
    0x77: Var("rpm", True, "rpm", lambda v: v / 0.32),
    0x82: Var("rpm_from_period", True, "rpm", lambda v: 15e6 / v if v else 0.0),
    0x46: Var("map_kpa", True, "kPa", lambda v: (v - 98.6) / 4.98, "GUESS: ADC ch7 = 5 V"),
    0x4A: Var("map_raw", False, "raw", float),
    0x44: Var("tps_open", False, "raw", float),
    0x53: Var("coolant_raw", False, "raw", float, "scaling to calibrate"),
    0x5F: Var("tha_raw", False, "raw", float, "scaling to calibrate"),
    0x8C: Var("mixture", False, "raw", float, "$80 = centre"),
    0x88: Var("inj_pulse_us", True, "us", float),
    0x8A: Var("dead_time_us", False, "us", float),
    0xA8: Var("ign_base", False, "deg", lambda v: v * 15 / 64, "map value x 15/64"),
    0xA9: Var("ign_coolant", False, "raw", float),
    0x06: Var("port3", False, "hex", float),
    0x95: Var("fuel_cut", False, "flag", float, "bit 3 = rev limit"),
    0x40: Var("faults_40", True, "hex", float),
    0x42: Var("faults_42", True, "hex", float),
}


def raw_value(addr: int, word: int) -> int:
    v = VARS.get(addr)
    return word if v is None or v.word else word >> 8


def column(addr: int) -> str:
    v = VARS.get(addr)
    if v is None:
        return f"x{addr:02X}"
    return f"{v.name} [{v.unit}{', GUESS' if 'GUESS' in v.note else ''}]"


def physical(addr: int, word: int) -> float:
    v = VARS.get(addr)
    r = raw_value(addr, word)
    return float(r) if v is None else v.scale(r)


def parse(lines: Iterable[str]) -> list[dict[str, float | str]]:
    """Rows of the latest value per variable, one row per pass over the polled list."""
    rows: list[dict[str, float | str]] = []
    cur: dict[str, float | str] = {}
    first: int | None = None
    for line in lines:
        f = line.strip().split(",")
        if len(f) != 4 or f[0] != "D":
            continue
        ms, addr, word = int(f[1]), int(f[2], 16), int(f[3], 16)
        if first is None:
            first = addr
        elif addr == first and cur:
            rows.append(cur)
            cur = dict(cur)
        cur["ms"] = ms
        cur[column(addr)] = round(physical(addr, word), 2)
    if cur:
        rows.append(cur)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    a = ap.parse_args()
    rows = parse(a.log.read_text(errors="replace").splitlines())
    if not rows:
        print("no D lines in the log", file=sys.stderr)
        return 1
    cols = list(dict.fromkeys(k for r in rows for k in r))
    if a.out:
        with a.out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, cols)
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {len(rows)} rows to {a.out}")
    else:
        print("\t".join(cols))
        for r in rows:
            print("\t".join(str(r.get(c, "")) for c in cols))
    return 0


if __name__ == "__main__":
    sys.exit(main())
