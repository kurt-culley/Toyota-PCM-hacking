"""The C emulator (CPU + D151801 peripherals, hardware/ecu-emu/core) against the Python simulator.

Same ROM, same engine model, same inputs: every spark, every injector edge, every ADC
conversion, the interrupt counts and the whole RAM must come out identical. This is step 3 of
the validation path in docs/emulator/validation.md.
"""

from __future__ import annotations

import shutil

import pytest

from pcmre.emu.cboard import CSimulation
from pcmre.emu.engine17140 import ROM_17140, Engine17140, Inputs17140
from pcmre.emu.sim import Simulation

pytestmark = pytest.mark.skipif(not (shutil.which("cc") or shutil.which("gcc")), reason="no host C compiler")
ROM = ROM_17140.read_bytes()

CASES = {
    "idle": dict(rpm=800, map_kpa=35),
    "cruise": dict(rpm=2500, map_kpa=50, tps_v=1.5),
    "full load": dict(rpm=5000, map_kpa=95, tps_v=4.0),
    "rev limit": dict(rpm=7700, map_kpa=95, tps_v=4.0),
    "cranking": dict(rpm=250, map_kpa=95),
    "cold, map B": dict(rpm=1500, map_kpa=45, thw_v=3.5, p34=0),
    "no IGF": dict(rpm=3000, map_kpa=60, igf=False),
    "test terminal": dict(rpm=900, map_kpa=35, test_terminal=True),
}


def outputs(sim) -> dict:
    e = sim.engine
    return {
        "sparks": list(e.sparks),
        "dwell": list(e.dwell_starts),
        "inj": {k: list(v) for k, v in e.inj.items()},
        "adc": list(e.adc_log),
        "ram": bytes(sim.periph.mem[0x40:0x100]),
    }


@pytest.mark.parametrize("name", CASES)
def test_c_emulator_matches_the_simulator(name):
    inp = CASES[name]
    py = Simulation(ROM, inputs=Inputs17140(**inp), engine=Engine17140)
    c = CSimulation(ROM, inputs=Inputs17140(**inp))
    for sim in (py, c):
        sim.engine.update_sensors()
        sim.run_ms(600)
    a, b = outputs(py), outputs(c)
    assert len(a["sparks"]) > 0 or name == "cranking"
    for key in a:
        assert b[key] == a[key], f"{name}: {key} differs"
    assert py.cpu.cycles == c.cycles
    assert py.irq_counts == c.irq_counts()
