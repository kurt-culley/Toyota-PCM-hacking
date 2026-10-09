"""Sanity checks on sensor curves transcribed from the factory EWD (analysis/sensors/)."""

import csv
from pathlib import Path

import pytest

SENSORS = Path(__file__).resolve().parents[1] / "analysis/sensors"


def load(name):
    with (SENSORS / name).open() as f:
        rows = [line for line in f if not line.startswith("#")]
    return list(csv.DictReader(rows))


@pytest.mark.parametrize("name", ["thw_ntc.csv", "tha_ntc.csv"])
def test_ntc_resistance_falls_with_temperature(name):
    rows = load(name)
    temps = [float(r["temp_c"]) for r in rows]
    mids = [(float(r["r_min_kohm"]) + float(r["r_max_kohm"])) / 2 for r in rows]
    assert temps == sorted(temps)
    assert all(a > b for a, b in zip(mids, mids[1:], strict=False)), "NTC resistance must fall as temperature rises"
    assert all(float(r["r_min_kohm"]) <= float(r["r_max_kohm"]) for r in rows)


def test_pim_rises_with_pressure_and_units_agree():
    rows = load("pim_map.csv")
    mmhg = [float(r["pressure_mmhg_abs"]) for r in rows]
    volts = [float(r["volts"]) for r in rows]
    assert mmhg == sorted(mmhg)
    assert all(a < b for a, b in zip(volts, volts[1:], strict=False))
    for r in rows:  # 1 mmHg = 0.133322 kPa
        assert float(r["pressure_kpa_abs"]) == pytest.approx(float(r["pressure_mmhg_abs"]) * 0.133322, abs=0.1)
