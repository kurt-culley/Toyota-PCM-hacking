"""Overrun fuel and retard prototype (analysis/patches/bluetop_overrun.asm) in the whole-ROM simulator.

The simulator imposes rpm and airflow (no engine dynamics), so these tests cover the ECU's
outputs only: injector pulses and spark timing, patched against stock.
"""

from __future__ import annotations

from functools import cache

import pytest

from emu.engine import BLUETOP_ROM
from emu.sim import Simulation
from pcmre.checksum import TARGET, rom_sum
from pcmre.patch import build
from pcmre.roundtrip import ASL, ROOT

pytestmark = pytest.mark.skipif(not ASL.exists(), reason="asl not built (tools/setup_assemblers.sh)")

PATCH = ROOT / "analysis/patches/bluetop_overrun.asm"
HOOKS = {*range(0xF512, 0xF51A), *range(0xF8AD, 0xF8B1)}
OB_RPM, OB_ADV = 4000, 38


@cache
def patched():
    return build(PATCH, BLUETOP_ROM.read_bytes())


def run(rpm: int, idl: bool, *, patch: bool = True, airflow: float = 500.0, ms: int = 1500) -> Simulation:
    s = Simulation(patched().rom, extra=patched().extra) if patch else Simulation()
    s.inputs.rpm, s.inputs.idl, s.inputs.airflow_us = rpm, idl, airflow
    s.engine.update_sensors()
    s.run_ms(ms)
    return s


def pulses(s: Simulation, window: int = 300_000) -> list[int]:
    since = s.periph.now - window
    return s.injector_pulses("#10", since) + s.injector_pulses("#20", since)


def sparks(s: Simulation, window: int = 300_000) -> list[float]:
    return s.spark_advance(s.periph.now - window)


def test_patch_touches_only_the_hooks_and_keeps_the_checksum():
    p = patched()
    assert set(p.changed) <= HOOKS
    assert rom_sum(p.rom) == TARGET
    assert list(p.extra) == [0xE000] and len(p.extra[0xE000]) < 64


@pytest.mark.parametrize("rpm", [4500, 6000])
def test_overrun_window_fuels_and_retards(rpm):
    stock = run(rpm, idl=True, patch=False)
    assert not pulses(stock)  # stock: decel fuel cut
    s = run(rpm, idl=True)
    driven = run(rpm, idl=False, patch=False)
    assert len(pulses(s)) == pytest.approx(len(pulses(driven)), abs=2)  # same injection pattern as on throttle
    assert s.ram("BaseAdvance") == OB_ADV and s.ram("IDLcompADV") == 0
    # warm (ThW_tADV 28): map arithmetic OB_ADV * 90/256 - 0.9 deg, plus the 256 us lead the simulator measures
    lead = 256e-6 * rpm / 60 * 360
    assert all(a == pytest.approx(OB_ADV * 90 / 256 - 0.9 + lead, abs=0.3) for a in sparks(s)[-5:])


@pytest.mark.parametrize(("rpm", "idl", "airflow"), [(900, True, 800.0), (3000, True, 500.0), (4500, False, 900.0)])
def test_outside_the_window_identical_to_stock(rpm, idl, airflow):
    """Idle, overrun below OB_RPM (stock cut) and open throttle above it."""
    a, b = run(rpm, idl, airflow=airflow), run(rpm, idl, patch=False, airflow=airflow)
    assert sparks(a) == pytest.approx(sparks(b), abs=0.05)
    pa, pb = pulses(a), pulses(b)
    assert len(pa) == len(pb) and all(abs(x - y) <= 0.01 * y for x, y in zip(pa, pb, strict=True))
    assert a.ram("BaseAdvance") == b.ram("BaseAdvance")


def test_leaving_the_window_restores_the_stock_cut():
    s = run(4500, idl=True)
    assert pulses(s)
    s.inputs.rpm = 3000
    s.engine.update_sensors()
    s.run_ms(500)
    assert not pulses(s, 200_000) and s.ram("BaseAdvance") == 45
