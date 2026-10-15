"""The emulator against the owner's real D151801 (chip-in-isolation run 3, 2026-10-15).

analysis/captures/chipdiff_17140_run3_2026-10-15.log is the Pico's record of 6 s (one 800 rpm phase)
of the chip running its own 17140 ROM on the breadboard, with the loopback's engine around it.
Replaying exactly its inputs into the C emulator must reproduce its outputs: every pin the same
number of edges, sparks (P11), the injector (P21) and the ADC selects (P12-P14) all at a constant
offset, and the ADC hold line (P15) on all but 7 of 3001 edges (open: STATUS, chip-in-isolation).
"""

from __future__ import annotations

import shutil

import pytest

from emu import chipdiff
from pcmre.roundtrip import ROOT

LOG = ROOT / "analysis/captures/chipdiff_17140_run3_2026-10-15.log"
pytestmark = pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None, reason="no C compiler")


@pytest.fixture(scope="module")
def result():
    log = chipdiff.parse_log(LOG.read_text())
    assert log.end == 6_000_000 and "dropped=0" in log.summary
    _, res = chipdiff.analyse(log, offset=0)
    return {r.pin.name: r for r in res}


def test_every_output_pin_has_the_chips_edge_count(result):
    for name, r in result.items():
        assert r.chip_n == r.emu_n, name


def test_sparks_injector_and_adc_selects_are_exact(result):
    assert dict(result["P11"].latency) == {2: 318}
    assert dict(result["P21"].latency) == {2: 162}
    for name in ("P12", "P13", "P14", "P22", "P23", "P24", "P31", "P40", "P41"):
        assert set(result[name].latency) == {3}, name


def test_adc_hold_line_nearly_exact(result):
    lat = result["P15"].latency
    assert lat[3] >= 2994 and sum(lat.values()) == 3001


RUN5 = ROOT / "analysis/captures/chipdiff_17140_run5_6phase_2026-10-15.log"


def test_closed_loop_spark_and_fuel_identical_to_the_chip():
    """Run 5 (all three points, 36 s, every engine reaction on time): the emulator running closed loop, as
    in the car, gives every spark and injector edge of the real chip at a constant offset."""
    log = chipdiff.parse_log(RUN5.read_text())
    assert log.end == 36_000_000 and "late=0" in log.summary and "dropped=0" in log.summary
    res = chipdiff.closed_loop(log)
    for pin, n in (("P11", 6238), ("P21", 3130)):
        nc, ne, lat = res[pin]
        assert nc == ne == n and set(lat) == {2}, pin
    for pin in ("P12", "P13", "P14", "P15"):  # ADC sequencing: all but a few conversions (open item)
        nc, ne, lat = res[pin]
        assert nc == ne and lat[3] >= 0.99 * nc, pin
