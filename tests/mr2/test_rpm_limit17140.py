"""The 17140's rev limiter in the whole-ROM simulator (docs/mr2/rev_limiter.md).

Fuel only: the cut flag $95 bit 3 stops SchedInj. The limit is NEsum <= $07B6 (7600 rpm), or
$07EB (7400 rpm) after a fast climb through 6000 rpm [ROM:$FA03-$FA3E, $FFB7-$FFC1].
"""

from __future__ import annotations

from pcmre.emu.engine17140 import ROM_17140, Engine17140, Inputs17140
from pcmre.emu.sim import Simulation

ROM = ROM_17140.read_bytes()


def drive(
    steps: list[tuple[int, int]], start: int, igf: bool = True, sim: list | None = None
) -> list[tuple[int, int, int]]:
    """Run (rpm, ms) steps at full load; return (rpm, injections, $95) for each step."""
    s = Simulation(ROM, inputs=Inputs17140(rpm=start, map_kpa=90, tps_v=4.0, igf=igf), engine=Engine17140)
    s.run_ms(400)
    out = []
    for rpm, ms in steps:
        s.inputs.rpm = rpm
        t0 = s.periph.now
        s.run_ms(ms)
        out.append((rpm, len(s.injector_pulses("Tout1", t0)), s.periph.mem[0x95]))
    if sim is not None:
        sim.append(s)
    return out


def test_fuel_cut_at_7600_with_no_hysteresis():
    r = drive([(7500, 300), (7650, 300), (7500, 300)], start=7300)
    assert r[0][1] > 10 and r[0][2] == 0
    assert r[1][1] <= 2 and r[1][2] == 0x08
    assert r[2][1] > 10 and r[2][2] == 0


def test_fast_climb_through_6000_lowers_the_limit_to_7400():
    climb = [(6000 + 200 * k, 20) for k in range(1, 8)]  # 10 000 rpm/s
    r = drive([(5900, 200), *climb, (7500, 300)], start=5900)
    assert r[-1][1] <= 2 and r[-1][2] == 0x08


def test_slow_climb_through_6000_keeps_the_7600_limit():
    climb = [(6000 + 40 * k, 20) for k in range(1, 38)]  # 2000 rpm/s
    sims: list = []
    r = drive([(5900, 200), *climb, (7500, 300)], start=5900, sim=sims)
    assert sims[0].ram(0xB9, 2) == 0x07B6
    assert r[-1][1] > 10 and r[-1][2] == 0


def test_missing_igf_stops_injection_but_not_the_spark():
    sims: list = []
    r = drive([(3000, 300)], start=3000, igf=False, sim=sims)
    s = sims[0]
    assert r[0][1] == 0
    assert len([t for t in s.engine.sparks if t >= s.periph.now - 300_000]) > 20
    assert s.periph.mem[0xA7] == 4  # StartCount saturates at 4
