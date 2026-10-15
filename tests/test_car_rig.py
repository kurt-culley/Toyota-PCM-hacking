"""The in-car test rig (pcmre.car_rig_diagram) against chipdiff.h and the doc."""

from __future__ import annotations

from pcmre import car_rig_diagram as R
from pcmre import chipdiff_wiring as C
from pcmre import wiring as BB
from pcmre.roundtrip import ROOT


def test_doc_table_current():
    doc = (ROOT / "docs/mr2/cpu_replacement.md").read_text()
    table = "\n".join("  " + line if line else line for line in R.table().splitlines())
    assert table in doc, "stale: rerun python -m pcmre.car_rig_diagram --table and paste it"


def test_every_used_pin_once():
    wires = R.car_wires()
    pins = [p for p, *_ in wires]
    assert len(pins) == len(set(pins)) == 26
    assert 1 in pins and 3 not in pins  # ground in, EXTAL out (the ECU's crystal)
    assert set(pins) - {1} == {pin for pin, _ in C.gpio_pins().values()} - {3}
    assert not set(pins) & {2, 4, 5, 7, 21, 31}  # supplies and straps stay the ECU board's


def test_each_jumper_starts_on_its_gpio():
    """Each jumper's hole is in its Pico pin's strip, or past the 1 kΩ for GP26-28; holes unique."""
    wires, parts = R.car_layout()
    holes = [h for *_, h in R.car_wires()]
    assert len(holes) == len(set(holes))
    by_pin = {pin: g for g, (pin, _) in C.gpio_pins().items()}
    for pin, _, _, hole in R.car_wires():
        if pin == 1:
            assert hole == BB._free(BB.pico_hole(R.GND_PICO_PIN)) and BB.PICO[R.GND_PICO_PIN] == "GND"
            continue
        g = by_pin[pin]
        if g in C.SERIES_ROWS:
            r = C.SERIES_ROWS[g]
            assert hole == f"j{r}" and (f"1 kΩ (GP{g})", f"e{r}", f"f{r}") in parts
            assert any(a == BB._free(BB.pico_hole(BB.PICO_PIN[f"GP{g}"])) and b == f"b{r}" for _, a, b, _ in wires)
        else:
            col, row = BB.pico_hole(BB.PICO_PIN[f"GP{g}"])
            assert int(hole[1:]) == row and (hole[0] in "ab") == (col == "c")


def test_small_board_has_no_rails():
    wires, parts = R.car_layout()
    holes = [h for _, a, b, _ in wires for h in (a, b)] + [h for _, a, b in parts for h in (a, b)]
    holes += [h for *_, h in R.car_wires()]
    assert not any(BB.is_rail(h) for h in holes)
    assert all(int(h[1:]) <= R.ROWS for h in holes)
