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
