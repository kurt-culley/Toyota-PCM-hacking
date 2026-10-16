"""The chip-in-isolation breadboard layout (pcmre.chipdiff_wiring) against the firmware's chipdiff.h."""

from __future__ import annotations

from pcmre import chipdiff_wiring as C
from pcmre import wiring as W
from pcmre.paths import ROOT

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
    wires, parts, _ = C.layout()
    to = {a: b for _, a, b in parts}
    for pin in C.MODE_PINS:  # the reader's three mode straps, now to +
        assert to[W._free(W.chip_hole(pin), 1)].startswith("j+"), pin
    assert not any(b.startswith("j-") for _, a, b in parts)  # none left on −
    # P42-P47: the six strips joined by jumpers, one resistor to +
    rows = sorted(W.chip_hole(p)[1] for p in C.STRAPS_HIGH)
    links = {(int(a[1:]), int(b[1:])) for t, a, b, _ in wires if t.startswith("S")}
    assert links == set(zip(rows, rows[1:], strict=False))
    assert [b for _, a, b in parts if a == W._free(W.chip_hole(C.STRAPS_HIGH[0]), 2)][0].startswith("a+")
    # P36: a wire to −; no resistor on P23 (the Pico's pull-up)
    p36 = next(w for w in wires if w[0] == "P36")
    assert same_strip(p36[1], W.chip_hole(C.STRAP_LOW)) and p36[2].startswith("a-")
    assert not any(same_strip(a, W.chip_hole(11)) for _, a, _ in parts)
    assert sum("kΩ" in p and "1 kΩ" not in p for p, _, _ in parts) == 2 + 3 + 1  # /RES, P24; mode straps; P4x


def test_only_moves_and_additions():
    """Every reader GPIO is reused; the Pico end of every reader wire stays put."""
    new, old = C.gpio_pins(), C.reader_pins()
    assert set(old) <= set(new)
    moved = sorted(g for g in old if old[g] != new[g][0])
    assert moved == [6, 12, 13, 14, 15, 16, 17, 20]
