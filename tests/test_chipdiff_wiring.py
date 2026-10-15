"""The chip-in-isolation breadboard layout (pcmre.chipdiff_wiring) against the firmware's chipdiff.h."""

from __future__ import annotations

from pcmre import chipdiff_wiring as C
from pcmre import wiring as W
from pcmre.roundtrip import ROOT

DOC = (ROOT / "docs/hardware/chip_diff_test.md").read_text()


def same_strip(hole: str, part_hole: tuple[str, int]) -> bool:
    col, row = part_hole
    half = "abcde" if col in "abcde" else "fghij"
    return hole[0] in half and int(hole[1:]) == row


def test_doc_table_current():
    assert C.table() in DOC, "stale: rerun python -m pcmre.chipdiff_wiring --png and paste the table"


def test_every_gpio_lands_on_its_chip_pin():
    wires, parts, status = C.layout()
    sig = {w[0]: w for w in wires if not W.is_rail(w[2])}
    gp = C.gpio_pins()
    assert len(gp) == 26
    for g, (pin, _) in gp.items():
        pp = W.PICO_PIN[f"GP{g}"]
        tag = next(t for t, w in sig.items() if f"(Pico pin {pp})" in w[3] and "'" not in t)
        if g in C.SERIES_ROWS:  # Pico -> left strip, 1 kΩ across the gap, right strip -> chip
            r = C.SERIES_ROWS[g]
            _, pico, left, _ = sig[tag]
            _, right, chip, _ = sig[tag + "'"]
            assert same_strip(pico, W.pico_hole(pp)) and same_strip(left, ("a", r)) and same_strip(right, ("j", r))
            assert (f"1 kΩ (GP{g})", f"e{r}", f"f{r}") in parts
        else:
            _, chip, pico, _ = sig[tag]
            assert same_strip(pico, W.pico_hole(pp))
        assert same_strip(chip, W.chip_hole(pin))


def test_holes_unique_and_free():
    wires, parts, _ = C.layout()
    holes = [h for _, a, b, _ in wires for h in (a, b)] + [h for _, a, b in parts for h in (a, b)]
    assert len(holes) == len(set(holes)), "a hole is used twice"
    occupied = {f"{c}{r}" for p in W.DIP for c, r in [W.chip_hole(p)]}
    occupied |= {f"{c}{r}" for p in range(1, 41) for c, r in [W.pico_hole(p)]}
    assert not set(holes) & occupied, "a wire lands under a part"
    assert not any(W.is_rail(h) and W._row(h) in C.RAIL_BREAK for h in holes), "a rail hole where the strip breaks"


def test_straps_and_pullups():
    _, parts, _ = C.layout()
    to = {a: b for _, a, b in parts}
    for pin in (*C.MODE_PINS, C.PULLUP_NEW, *C.STRAPS_HIGH):
        hole = W._free(W.chip_hole(pin), 1 if pin < 21 else 2)
        assert to[hole].split("@")[0] in ("j+", "a+"), pin
    assert to[W._free(W.chip_hole(C.STRAP_LOW), 2)].startswith("a-")
    # the reader's mode straps to − are gone
    assert not any(b.startswith("j-") for _, a, b in parts)


def test_only_moves_and_additions():
    """Every reader GPIO is reused; the Pico end of every reader wire stays put."""
    new, old = C.gpio_pins(), C.reader_pins()
    assert set(old) <= set(new)
    moved = sorted(g for g in old if old[g] != new[g][0])
    assert moved == [6, 12, 13, 14, 15, 16, 17, 20]
