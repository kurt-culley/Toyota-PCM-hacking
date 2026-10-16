"""Physical sensor models for the simulator, from the factory data in ``analysis/sensors``.

PIM (vacuum / MAP sensor), EWD 1984 p25, terminals 1-4 [analysis/sensors/pim_map.csv]:

    kPa abs:  20   60   100   112
    volts:   1.2  2.4  3.8?  4.0

The 100 kPa point is a scan ambiguity (6 or 8). The other three points lie exactly on
V = 0.6 + 0.03 * kPa, which also gives 3.6 V at 100 kPa. That straight line is used here
(LIKELY), to be confirmed on the bench (P8).
"""

from __future__ import annotations

import csv
from functools import cache
from pathlib import Path

SENSORS = Path(__file__).resolve().parents[1] / "sensors"
PIM_OFFSET_V, PIM_SLOPE_V_PER_KPA = 0.6, 0.03


@cache
def pim_points() -> tuple[tuple[float, float, str], ...]:
    """(kPa abs, volts, note) from the EWD transcription."""
    with (SENSORS / "pim_map.csv").open() as f:
        rows = [r for r in csv.reader(line for line in f if not line.startswith("#"))]
    head, data = rows[0], rows[1:]
    k, v, n = head.index("pressure_kpa_abs"), head.index("volts"), head.index("note")
    return tuple((float(r[k]), float(r[v]), r[n]) for r in data)


def pim_volts(kpa_abs: float) -> float:
    """PIM output for an absolute manifold pressure (LIKELY: straight line through the EWD points)."""
    return max(0.0, min(5.0, PIM_OFFSET_V + PIM_SLOPE_V_PER_KPA * kpa_abs))


def adc_raw(volts: float, full_scale: float = 5.0) -> int:
    """8-bit ADC reading of ``volts`` against ``full_scale``."""
    return max(0, min(255, round(volts * 255 / full_scale)))


def pim_raw(kpa_abs: float) -> int:
    return adc_raw(pim_volts(kpa_abs))
