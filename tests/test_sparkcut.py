"""Spark-cut rev limiter prototype (analysis/patches/bluetop_sparkcut.asm) in the whole-ROM simulator.

The simulator imposes the rpm (no engine dynamics) and models no spark from outside the
CPU in normal running, so these tests cover the ECU's outputs only: which NE passes get a
spark and which get fuel.
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

PATCH = ROOT / "analysis/patches/bluetop_sparkcut.asm"
HOOKS = {*range(0xF1F2, 0xF1F4), *range(0xF252, 0xF256), *range(0xF387, 0xF38B), *range(0xF42D, 0xF431)}


@cache
def patched(reload: int | None = None):
    rom = bytearray(BLUETOP_ROM.read_bytes())
    if reload is not None:
        rom[0xF42C - 0xF000] = reload
    return build(PATCH, bytes(rom))


def run(rpm: int, *, patch: bool = True, igf: bool = True, ms: int = 800, reload: int | None = None) -> Simulation:
    s = Simulation(patched(reload).rom, extra=patched(reload).extra) if patch else Simulation()
    s.inputs.rpm, s.inputs.idl, s.inputs.airflow_us, s.inputs.igf = rpm, False, 900, igf
    s.engine.update_sensors()
    s.run_ms(ms)
    return s


def recent(events: list[int], s: Simulation, window: int = 200_000) -> list[int]:
    return [t for t in events if t > s.periph.now - window]


def fuel_starts(s: Simulation, window: int = 200_000) -> list[int]:
    return [on for g in ("#10", "#20") for on, _ in s.engine.inj[g] if on > s.periph.now - window]


def passes(s: Simulation, rpm: int, n: int) -> list[tuple[bool, bool]]:
    """Step to ``rpm`` and return (spark, fuel) for each of the next ``n`` NE passes."""
    s.inputs.rpm = rpm
    s.engine.update_sensors()
    f0 = len(s.engine.falls)
    while len(s.engine.falls) < f0 + n + 1:
        s.step()
    falls = s.engine.falls[f0:]
    ons = [on for g in ("#10", "#20") for on, _ in s.engine.inj[g]]
    return [
        (any(a < t <= b for t in s.engine.sparks), any(a < t <= b for t in ons))
        for a, b in zip(falls, falls[1:], strict=False)
    ]


def test_patch_touches_only_the_hooks_and_keeps_the_checksum():
    p = patched()
    assert set(p.changed) <= HOOKS
    assert rom_sum(p.rom) == TARGET
    assert list(p.extra) == [0xE000] and len(p.extra[0xE000]) < 64


def test_above_limit_no_spark_but_fuel_continues():
    s = run(7600)
    assert not recent(s.engine.sparks, s) and not recent(s.engine.hw_sparks, s)
    assert len(fuel_starts(s)) > 0
    assert s.ram("SatCount_97") >= 0x80 and s.ram("SatCount_98") < 0x80  # IGF cut held off
    stock = run(7600, patch=False)
    assert recent(stock.engine.sparks, stock) and not fuel_starts(stock)  # stock: the opposite


@pytest.mark.parametrize("rpm", [3000, 7300])
def test_below_limit_identical_to_stock(rpm):
    # The hooks lengthen two interrupts by a few cycles. That shifts sampled timer values by
    # a few µs and the phase of slow, main-loop-paced loops (after-start decay, feedback),
    # so pulse widths agree to within 1 % rather than exactly; spark timing is identical.
    a, b = run(rpm, ms=3000), run(rpm, patch=False, ms=3000)
    assert a.spark_advance(a.periph.now - 200_000) == b.spark_advance(b.periph.now - 200_000)
    pa, pb = (x.injector_pulses("#10", x.periph.now - 200_000) for x in (a, b))
    assert len(pa) == len(pb) and all(abs(x - y) <= 0.01 * y for x, y in zip(pa, pb, strict=True))
    assert len(recent(a.engine.sparks, a)) == len(recent(b.engine.sparks, b))


def test_igf_safety_cut_still_works_below_limit():
    s = run(3000, igf=False)
    assert not fuel_starts(s) and s.ram("SatCount_98") >= 0x80


@pytest.mark.parametrize(("reload", "max_sparks"), [(None, 7), (0x7E, 2)])
def test_cut_engages_and_releases_with_fuel_throughout(reload, max_sparks):
    """Stock reload: 6 passes above the limit; $7E: 1. Both plus one pass of NE measurement lag."""
    s = run(7300, ms=600, reload=reload)
    up = passes(s, 7600, 14)
    first_cut = next(i for i, (spark, _) in enumerate(up) if not spark)
    assert first_cut <= max_sparks and not any(spark for spark, _ in up[first_cut:])
    down = passes(s, 7300, 10)
    first_spark = next(i for i, (spark, _) in enumerate(down) if spark)
    assert first_spark <= 2 and all(spark for spark, _ in down[first_spark:])
    assert all(fuel for _, fuel in up[:-1] + down[:-1])  # the last window may end before injection
