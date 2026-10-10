"""The readable ignition table matches the simulator and is current."""

from __future__ import annotations

import pytest

from emu.sim import Simulation
from pcmre import readable
from pcmre.defs import load


def test_generated_files_are_current():
    md, csv = readable.build()
    hint = "run: PYTHONPATH=analysis uv run python -m pcmre.readable --write"
    assert readable.DOC.read_text() == md, hint
    assert readable.CSV.read_text() == csv, hint


@pytest.mark.parametrize(("rpm", "row"), [(3200, 3), (4800, 2)])
def test_table_degrees_match_the_simulated_spark(rpm, row):
    """Drive the simulator exactly onto a map cell; its spark must match the table (plus the 256 µs lead)."""
    spec, rom = load("bluetop")
    m = next(m for m in spec["maps"] if m["id"] == "ign_base")
    col = m["col_axis"]["physical"].index(rpm)
    cell = rom[m["addr"] - spec["base"] + row * m["cols"] + col]
    target = m["row_axis"]["raw"][row]
    s = Simulation()
    s.inputs.rpm, s.inputs.idl, s.inputs.airflow_us = rpm, False, 1500
    s.engine.update_sensors()
    s.run_ms(300)
    s.inputs.airflow_us = round(target / (0.75 + s.ram("ThAcorr") / 512))  # Load = x * (3/4 + ThAcorr/512)
    s.engine.update_sensors()
    s.run_ms(1200)
    assert abs(s.ram("Load", 2) - target) <= 4
    tvis = s.ram("TVIScounter") < 0x80
    assert tvis == (rpm > readable.TVIS_RPM)
    want = readable.degrees(cell, rpm, tvis, lead=True)
    got = s.spark_advance(s.periph.now - 200_000)
    assert got and all(a == pytest.approx(want, abs=0.4) for a in got[-5:])


def test_full_load_line_matches_the_simulator():
    spec, rom = load("bluetop")
    for rpm in (800, 3200, 6400):
        s = Simulation()
        s.inputs.rpm, s.inputs.idl, s.inputs.airflow_us = rpm, False, 1500
        s.engine.update_sensors()
        s.run_ms(500)
        assert abs(readable.full_load_us(rom, spec, rpm) - s.ram("SE056Maxtime", 2)) <= 2
