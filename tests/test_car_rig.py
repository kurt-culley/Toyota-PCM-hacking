"""The in-car test rig's wire table (pcmre.car_rig_diagram) against chipdiff.h and the doc."""

from __future__ import annotations

from pcmre import car_rig_diagram as R
from pcmre import chipdiff_wiring as C
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


def test_car_layout_has_no_5v():
    """The reworked board carries nothing on the + rails, and no EXTAL wire, strap or pull-up."""
    wires, parts = R.car_layout()
    holes = [h for _, a, b, _ in wires for h in (a, b)] + [h for _, a, b in parts for h in (a, b)]
    assert not any(R.BB.is_rail(h) and "+" in h for h in holes)
    assert not any("EXTAL" in w or t.startswith("S") or t == "P36" for t, _, _, w in wires)
    assert [p for p, _, _ in parts] == [f"1 kΩ (GP{g})" for g in (26, 27, 28)]
    signals = [t for t, a, b, _ in wires if not R.BB.is_rail(b)]
    assert len(signals) == 25 + 3  # every GPIO but EXTAL, plus the three 1 kΩ second halves
