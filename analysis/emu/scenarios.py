"""Bluetop warm-up experiments on the whole-ROM simulation (goal 1 rehearsal).

    PYTHONPATH=analysis uv run python -m emu.scenarios            # print a summary
    PYTHONPATH=analysis uv run python -m emu.scenarios --write    # also write analysis/bluetop/sim/*.csv

Two experiments, both with a fixed idle airflow signal and fixed rpm, so that only
the coolant temperature and time since start change:

1. ``start_and_idle``: crank at 250 rpm for 1.5 s with STA high, then idle, logging every
   0.5 s for ``run_s`` seconds. This shows the after-start enrichment decaying.
2. ``steady_sweep``: the same start at each coolant temperature, reading the values
   after ``settle_s`` seconds, when the after-start terms have run out.

The fixed airflow signal is a stand-in (GUESS) because the SE056's volts-to-delay
relation is unknown. So read the fuel results as **ratios against the warm engine**,
not as absolute fuel mass. Pulse widths in µs are what the ROM commands for that
airflow signal.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from .sim import Simulation

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis/bluetop/sim"

FIELDS = [
    "t_s", "coolant_f", "coolant_c", "rpm", "mode", "fuel_ratio", "inj_load_pulse_us", "pulse_us",
    "dead_time_us", "inj_per_rev", "fuel_us_per_cycle", "advance_deg", "thw_tadv",
    "byte_83", "byte_84", "byte_8B", "word_8C",
]  # fmt: skip


def sample(sim: Simulation, window_us: int = 500_000) -> dict:
    """Averages over the last ``window_us`` of simulated time, plus the ROM state now."""
    now = sim.periph.now
    since = now - window_us
    pulses = sim.injector_pulses("#10", since)
    dead = sim.ram("InjDeadTime", 2)
    rpm = sim.inputs.rpm
    revs = window_us * rpm / 60e6
    inj_per_rev = len(pulses) / revs if revs else 0.0
    # open time beyond the dead time, per 720° engine cycle, for one injector
    fuel = sum(max(0, p - dead) for p in pulses) / revs * 2 if revs else 0.0
    adv = sim.spark_advance(since)
    return {
        "t_s": round(now / 1e6, 2),
        "coolant_f": sim.inputs.coolant_f,
        "coolant_c": round((sim.inputs.coolant_f - 32) / 1.8, 1),
        "rpm": rpm,
        "mode": "grouped" if sim.ram("byte_69") >= 0x80 else "simultaneous",
        "fuel_ratio": round(sim.ram("FuelRatioH", 2) / 256, 3),
        "inj_load_pulse_us": sim.ram("InjLoadPulse", 2),
        "pulse_us": round(sum(pulses) / len(pulses)) if pulses else 0,
        "dead_time_us": dead,
        "inj_per_rev": round(inj_per_rev, 2),
        "fuel_us_per_cycle": round(fuel),
        "advance_deg": round(sum(adv) / len(adv), 1) if adv else "",
        "thw_tadv": sim.ram("ThW_tADV"),
        "byte_83": sim.ram("byte_83"),
        "byte_84": sim.ram("byte_84"),
        "byte_8B": sim.ram("byte_8B"),
        "word_8C": sim.ram("word_8C", 2),
    }


def start(coolant_f: float, *, idle_rpm: float = 1000, airflow_us: float = 800) -> Simulation:
    sim = Simulation()
    i = sim.inputs
    i.coolant_f = i.intake_f = coolant_f
    i.airflow_us = airflow_us
    sim.engine.update_sensors()
    sim.run_ms(300)  # key on
    i.starter, i.rpm = True, 250
    sim.engine.update_sensors()
    sim.run_ms(1500)  # crank
    i.starter, i.rpm = False, idle_rpm
    sim.engine.update_sensors()
    return sim


def start_and_idle(coolant_f: float, run_s: float = 60, step_ms: float = 500, **kw) -> list[dict]:
    sim = start(coolant_f, **kw)
    rows = []
    for _ in range(round(run_s * 1000 / step_ms)):
        sim.run_ms(step_ms)
        rows.append(sample(sim, round(step_ms * 1000)))
    return rows


def steady_point(coolant_f: float, settle_s: float = 60, **kw) -> dict:
    sim = start(coolant_f, **kw)
    sim.run_ms(settle_s * 1000)
    return sample(sim, 2_000_000)


def steady_sweep(temps_f: list[float], settle_s: float = 60, **kw) -> list[dict]:
    return [steady_point(f, settle_s, **kw) for f in temps_f]


def to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


AFTERSTART_TEMPS_F = [14, 32, 68, 104, 176]  # -10, 0, 20, 40, 80 °C
STEADY_TEMPS_F = [14, 32, 50, 68, 86, 104, 122, 140, 158, 176, 194, 212]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    with ProcessPoolExecutor() as pool:  # each run is independent; about 1 s of CPU per simulated second
        steady_f = pool.map(steady_point, STEADY_TEMPS_F)
        after_f = pool.map(start_and_idle, AFTERSTART_TEMPS_F)
        steady, after = list(steady_f), list(after_f)
    print(to_csv(steady))
    for f, rows in zip(AFTERSTART_TEMPS_F, after, strict=True):
        print(f"after-start {f} °F: fuel ratio {rows[0]['fuel_ratio']} -> {rows[-1]['fuel_ratio']}")
    if a.write:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "steady_vs_coolant.csv").write_text(to_csv(steady))
        for f, rows in zip(AFTERSTART_TEMPS_F, after, strict=True):
            (OUT / f"afterstart_{f}F.csv").write_text(to_csv(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
