"""Breadboard layout for the chip-in-isolation test, as changes to the ROM reader's layout.

    PYTHONPATH=analysis uv run python -m pcmre.chipdiff_wiring          # print the tables
    PYTHONPATH=analysis uv run python -m pcmre.chipdiff_wiring --png    # also redraw the picture

The test (docs/hardware/chip_diff_test.md) runs the D151801 in single-chip mode on the same
breadboard as the reader (pcmre.wiring). The pin map comes from the firmware's chipdiff.h, the
reader's from its pins.h, so this layout lists exactly what to change: wires that stay, wires
whose chip end moves, new wires, and the resistors that change. tests/test_chipdiff_wiring.py
checks the layout and that the guide's table is current.
"""

from __future__ import annotations

import argparse
import itertools
import re
import sys

from . import wiring as W
from .roundtrip import ROOT

CHIPDIFF_H = ROOT / "hardware/ecu-emu/chipdiff/chipdiff.h"
PNG = ROOT / "docs/hardware/photos/chip_diff_test/breadboard_chipdiff.png"

# Pin names in single-chip mode (mode 7): the reader's bus pins become ports 3 and 4
DIP7 = {
    **W.DIP,
    **{30 + i: f"P3{7 - i}" for i in range(8)},
    **{22 + i: f"P4{7 - i}" for i in range(8)},
    12: "P24",
    38: "SC2",
    39: "SC1",
}
SERIES_ROWS = {26: 21, 27: 22, 28: 23}  # GP26-28 (ADC pins, not 5 V tolerant): 1 kΩ across the gap in this row
RAIL_BREAK = range(30, 33)  # rail holes left alone where the strips usually break
# P47-P42 are inputs only (the ROM writes DDR4 = $03): short jumpers join their strips and ONE
# resistor (any value 1-100 kΩ) pulls them all high, the simulator's default level. The resistor
# (not a bare wire) limits the current if the chip were ever strapped into a bus mode by mistake.
STRAPS_HIGH = (22, 23, 24, 25, 26, 27)
STRAP_LOW = 31  # P36, input only (DDR3 = $02): a plain wire to −
MODE_PINS = (8, 9, 10)  # P20-P22: the reader's three 10 kΩ, moved from − to + (mode 7)
# P23 (pin 11) needs no resistor: the firmware enables the Pico's own pull-up on GP22, so the chip
# reads it high at reset and the serial link stays off.

KEEP, MOVE, NEW = "keep", "MOVE", "NEW"
COLOUR = {KEEP: (110, 110, 110), MOVE: (230, 120, 0), NEW: (0, 150, 60)}


def gpio_pins() -> dict[int, tuple[int, str]]:
    """GPIO -> (chip pin, signal), from chipdiff.h, plus /RES, EXTAL and E."""
    out = {8: (6, "/RES"), 9: (3, "EXTAL"), 19: (40, "E")}
    for m in re.finditer(r"X\((\d+), \d, \d, (IN|OUT)\)\s*/\*\s*(.+?)\s+pin (\d+)", CHIPDIFF_H.read_text()):
        out[int(m[1])] = (int(m[4]), " ".join(m[3].split()))
    return out


def reader_pins() -> dict[int, int]:
    """GPIO -> chip pin in the reader layout."""
    by_name = {n: p for p, n in W.DIP.items()}
    return {g: by_name[name] for name, g in W.board_pins("pico2w").items()}


def _assign(rows: list[int], free: list[int]) -> list[int]:
    """Rail rows for parts whose chip rows are `rows` (ascending): no crossings, shortest legs."""
    best = None
    near = [r for r in free if min(rows) - 8 <= r <= max(rows) + 8]
    for combo in itertools.combinations(near, len(rows)):
        d = [abs(a - b) for a, b in zip(rows, combo, strict=True)]
        cost = (max(d), sum(d))
        if best is None or cost < best[0]:
            best = (cost, list(combo))
    if best is None:
        raise ValueError(f"no free rail holes near rows {rows}")
    return best[1]


def layout() -> tuple[list[tuple[str, str, str, str]], list[tuple[str, str, str]], dict[str, str]]:
    """(wires, parts, status): the reader's layout format, plus a status per wire tag / part label."""
    rw, rp = W.breadboard()
    new, old = gpio_pins(), reader_pins()
    wires: list[tuple[str, str, str, str]] = []
    parts: list[tuple[str, str, str]] = []
    status: dict[str, str] = {}
    old_hole = {g: W._free(W.chip_hole(p), 1 if p > 20 else 0) for g, p in old.items()}

    order = sorted(new, key=lambda g: (g not in old, W.PICO_PIN[f"GP{g}"]))
    for n, g in enumerate(order, 1):
        pin, what = new[g]
        what = " ".join(what.split()[1:])  # drop the signal name, already given as `name`
        pp = W.PICO_PIN[f"GP{g}"]
        tag = str(n)
        pico, chip = W._free(W.pico_hole(pp)), W._free(W.chip_hole(pin), 1 if pin > 20 else 0)
        name = DIP7[pin]
        if g in SERIES_ROWS:
            r = SERIES_ROWS[g]
            wires.append(
                (
                    tag,
                    pico,
                    f"b{r}",
                    f"GP{g} (Pico pin {pp}) → 1 kΩ in row {r} → {name} (pin {pin}){' ' + what if what else ''}",
                )
            )
            wires.append((tag + "'", f"j{r}", chip, f"… 1 kΩ in row {r} → {name} (pin {pin})"))
            parts.append((f"1 kΩ (GP{g})", f"e{r}", f"f{r}"))
            status[tag] = status[tag + "'"] = status[f"1 kΩ (GP{g})"] = NEW
            continue
        st = KEEP if old.get(g) == pin else MOVE if g in old else NEW
        desc = f"{name} (pin {pin}){' ' + what if what else ''} → GP{g} (Pico pin {pp})"
        if st == MOVE:
            desc += f"   [move the chip end from {old_hole[g]}]"
        wires.append((tag, chip, pico, desc))
        status[tag] = st

    # power and ground: exactly the reader's
    wires += [w for w in rw if W.is_rail(w[2])]
    # the reader's parts that stay: capacitors, EXTAL pull-up, /RES and P24 pull-ups (mode straps are redone)
    mode_holes = {W._free(W.chip_hole(p), 1) for p in MODE_PINS}
    parts += [pt for pt in rp if pt[1] not in mode_holes]

    used = {h for _, a, b, _ in wires for h in (a, b) if W.is_rail(h)}
    used |= {h for _, a, b in parts for h in (a, b) if W.is_rail(h)}

    def to_rail(rail: str, pins: list[int], k: int, label, st) -> None:
        pins = sorted(pins, key=lambda p: W._row(W._free(W.chip_hole(p), k)))
        holes = [W._free(W.chip_hole(p), k) for p in pins]
        rows = [W._row(h) for h in holes]
        free = [r for r in range(1, 64) if W._rail(rail, r) not in used and r not in RAIL_BREAK]
        for pin, hole, r in zip(pins, holes, _assign(rows, free), strict=True):
            lab = label(pin)
            parts.append((lab, hole, W._rail(rail, r)))
            used.add(W._rail(rail, r))
            status[lab] = st

    to_rail("j+", list(MODE_PINS), 1, lambda p: f"10 kΩ, {DIP7[p]} (pin {p}) mode strap, now to +", MOVE)

    # P47-P42: a zigzag of short jumpers (b, a, b, a, b) joins the six strips; one resistor to +
    rows = [W.chip_hole(p)[1] for p in sorted(STRAPS_HIGH)]
    for i, (r0, r1) in enumerate(itertools.pairwise(rows)):
        col = "ba"[i % 2]
        tag = f"S{i + 1}"
        wires.append((tag, f"{col}{r0}", f"{col}{r1}", f"link the P4 strap strips: row {r0} ↔ row {r1}"))
        status[tag] = NEW
    lab = "1 resistor, any 1–100 kΩ: P42–P47 (pins 22–27) to +"
    to_rail("a+", [STRAPS_HIGH[0]], 2, lambda p: lab, NEW)
    # P36: a plain wire to −
    hole = W._free(W.chip_hole(STRAP_LOW), 2)
    wires.append(("P36", hole, W._rail("a-", W._row(hole)), f"{DIP7[STRAP_LOW]} (pin {STRAP_LOW}) → − rail beside a"))
    status["P36"] = NEW
    return wires, parts, status


def table() -> str:
    wires, parts, status = layout()
    rows = ["| Wire | Change | From | To | What |", "|---|---|---|---|---|"]
    rows += [f"| {t} | {status[t]} | {W.hole_name(a)} | {W.hole_name(b)} | {w} |" for t, a, b, w in wires
             if not W.is_rail(b) or status.get(t) == NEW]  # fmt: skip
    rows += ["", "| Part | Change | From | To |", "|---|---|---|---|"]
    rows += [f"| {p} | {status.get(p, KEEP)} | {W.hole_name(a)} | {W.hole_name(b)} |" for p, a, b in parts]
    return "\n".join(rows)


def draw(out=PNG) -> None:
    from PIL import ImageFont

    wires, parts, status = layout()

    def font(size: int, bold: bool = False):
        try:
            return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)
        except OSError:
            return ImageFont.load_default()

    head = [
        ("Chip-in-isolation test: breadboard layout (Pico 2 W, D151801 in single-chip mode)", font(22, True), "black"),
        ("The ROM reader's board, changed. Generated from chipdiff.h (python -m pcmre.chipdiff_wiring --png).",
         font(15), "black"),
        ("GREY = wire stays.  ORANGE = same Pico hole, move the chip end (see the list).  GREEN = new.", font(15, True),
         (0, 0, 0)),
        ("Resistors: ORANGE = mode straps move from − to +.  GREEN = new.  Tan = as on the reader.", font(15, True),
         (0, 0, 0)),
        ("Chip NOTCH points DOWN (towards row 44). All changes with USB out and the 5 V jumper out.", font(15, True),
         (190, 0, 0)),
        ("Pink wire = the 5 V jumper: last in, first out. GP26-28 go through 1 kΩ (rows 21-23, across the gap).",
         font(15, True), (190, 0, 0)),
    ]  # fmt: skip

    def wire_colour(tag: str, what: str):
        return COLOUR[status.get(tag, KEEP)]

    def part_colour(part: str):
        st = status.get(part)
        return {MOVE: (240, 150, 40), NEW: (60, 190, 90)}.get(st, (225, 200, 150))

    W.draw_breadboard(out, layout=(wires, parts), head=head, dip=DIP7, wire_colour=wire_colour, part_colour=part_colour)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--png", action="store_true")
    a = ap.parse_args()
    print(table())
    if a.png:
        draw()
        print(f"wrote {PNG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
