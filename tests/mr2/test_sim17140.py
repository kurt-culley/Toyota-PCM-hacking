"""P4 step 3: the 17140 ROM in the whole-ROM simulator (src/pcmre/emu/engine17140.py).

These pin down the units used in docs/mr2/maps.md: RpmWord = rpm x 0.32, the injector pulse
= InjPulse + dead time in us, and 15/64 degree of spark per count of the ignition map.
"""

from __future__ import annotations

from functools import cache

import pytest

from pcmre.emu.engine17140 import ROM_17140, Engine17140, Inputs17140
from pcmre.emu.sim import Simulation

ROM = ROM_17140.read_bytes()


@cache
def run(rpm: int, kpa: float, p34: int = 1, ms: int = 900) -> Simulation:
    s = Simulation(ROM, inputs=Inputs17140(rpm=rpm, map_kpa=kpa, p34=p34), engine=Engine17140)
    s.engine.update_sensors()
    s.run_ms(ms)
    return s


def mem(s: Simulation, a: int, width: int = 1) -> int:
    v = 0
    for k in range(width):
        v = v << 8 | s.periph.mem[a + k]
    return v


def spark(s: Simulation) -> float:
    return s.engine.spark_tooth_offsets(s.periph.now - 150_000)[-1]


@pytest.mark.parametrize("rpm", [1200, 2000, 3600, 5200])
def test_rpmword_is_rpm_times_0_32(rpm):
    assert mem(run(rpm, 60), 0x77, 2) == pytest.approx(rpm * 0.32, abs=2)


def test_two_sparks_and_one_injection_per_revolution():
    s = run(2000, 60)
    since = s.periph.now - 300_000
    revs = 0.3 * 2000 / 60
    assert len([t for t in s.engine.sparks if t > since]) == pytest.approx(2 * revs, abs=1)
    pulses = [(a, b) for a, b in s.engine.inj["Tout1"] if a > since]
    assert len(pulses) == pytest.approx(revs, abs=1)
    a, b = pulses[-1]
    assert b - a == pytest.approx(mem(s, 0x88, 2) + mem(s, 0x8A, 2), abs=40)  # InjPulse + dead time, in us


@pytest.mark.parametrize("rpm", [1200, 2000, 3600, 5200])
def test_spark_moves_15_64_degree_per_map_count(rpm):
    lo, hi = run(rpm, 30), run(rpm, 90)
    counts = mem(lo, 0xA8) - mem(hi, 0xA8)
    assert counts > 10
    assert (spark(hi) - spark(lo)) / counts == pytest.approx(15 / 64, abs=0.005)


def test_load_is_linear_in_map_pressure():
    loads = [mem(run(2000, k), 0x46, 2) for k in (40, 70, 100)]
    assert loads[1] - loads[0] == pytest.approx(loads[2] - loads[1], abs=3)
    assert (loads[2] - loads[0]) / 60 == pytest.approx(4.98, abs=0.1)


def test_p34_selects_the_map():
    a, b = run(2000, 60, p34=1), run(2000, 60, p34=0)
    assert mem(a, 0xA8) != mem(b, 0xA8)


def test_readable_maps_current():
    from pcmre.readable17140 import DOC, build

    assert DOC.read_text() == build(), "stale: rerun python -m pcmre.readable17140 --write"
