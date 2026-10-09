"""P2: whole-ROM simulation of the Bluetop (analysis/emu/sim.py) against the ROM's own arithmetic.

Each test boots cap.bin from reset with a simulated engine and checks the ECU's outputs
(injector pulses, spark timing) against values worked out independently from the code.
About 1 s of CPU time per simulated second.
"""

import pytest

from emu.cpu import VEC_ICF, VEC_OCF, VEC_SCI
from emu.sim import Simulation
from pcmre.tables import lookup_3d


def sim_at(ms=1500, **inputs):
    s = Simulation()
    for k, v in inputs.items():
        setattr(s.inputs, k, v)
    s.engine.update_sensors()
    s.run_ms(ms)
    return s, s.periph.now - 300_000  # the last 300 ms


def advance_from_rom_formula(base: int, thw_adv: int, idl_adv: int, delta_ne: int) -> float:
    """Spark angle BTDC from the ROM's own sum and µs conversion [ROM:$F8D0-$F90E].

    sum clamped to $1F..$B8, minus $1C; AdvanceinUS = (deltaNE*(b+1))>>9 + 256 - deltaNE/16.
    The spark is AdvanceinUS before the NE falling edge, which is 10° BTDC; 180° per deltaNE.
    """
    total = min(max(base + thw_adv + idl_adv, 0x1F), 0xB8)
    b = total - 0x1C
    adv_us = ((delta_ne * (b + 1)) >> 9) + 256 - (delta_ne >> 4)
    return 10 + adv_us * 180 / delta_ne


def test_boot_runs_all_interrupts_and_reads_sensors():
    s, _ = sim_at(rpm=900, coolant_f=150, battery_v=13.0)
    assert {VEC_ICF, VEC_OCF, VEC_SCI} <= set(s.irq_counts)
    assert abs(s.ram("ADC_ThW") - 150) <= 1  # coolant reaches the ROM in °F via the inverted $FEF0 table
    assert s.ram("ADC_12V") == round(13.0 * 255 / 25)
    assert s.engine.sparks and s.engine.inj["#10"] and s.engine.inj["#20"]


@pytest.mark.parametrize("rpm", [900, 2400, 4800])
def test_rpm_variables_match_the_stimulus(rpm):
    s, _ = sim_at(ms=800, rpm=rpm, idl=False)
    assert s.ram("deltaNE", 2) == pytest.approx(30e6 / rpm, abs=1)
    assert s.ram("lilRPM") == pytest.approx(rpm / 25, abs=1)
    assert (s.ram("RPMish") + 32) * 25 == pytest.approx(rpm, abs=25)


def test_warm_injection_is_grouped_and_doubled():
    """Above 80 °F: each group fires once per crank revolution with 2 x InjLoadPulse + dead time."""
    s, since = sim_at(rpm=1200, coolant_f=176)
    expect = 2 * s.ram("InjLoadPulse", 2) + s.ram("InjDeadTime", 2)
    for g in ("#10", "#20"):
        pulses = s.injector_pulses(g, since)
        assert len(pulses) == pytest.approx(0.3 * 1200 / 60, abs=1)  # once per revolution
        assert pulses[-1] == pytest.approx(expect, abs=15)
    lp = s.ram("SE056plstime", 2) * s.ram("FuelRatioH", 2) >> 8  # [ROM:$F1F8-$F217]
    assert s.ram("InjLoadPulse", 2) == pytest.approx(lp, abs=2)


def test_cold_injection_is_simultaneous_every_edge():
    """At or below 72 °F: both groups fire on every NE edge with InjLoadPulse + dead time [ROM:$F534, $F131]."""
    s, since = sim_at(rpm=1200, coolant_f=50)
    expect = s.ram("InjLoadPulse", 2) + s.ram("InjDeadTime", 2)
    for g in ("#10", "#20"):
        pulses = s.injector_pulses(g, since)
        assert len(pulses) == pytest.approx(0.3 * 1200 / 30, abs=1)  # every 180°
        assert pulses[-1] == pytest.approx(expect, abs=15)


@pytest.mark.parametrize(("rpm", "airflow"), [(1600, 1200), (2400, 1500), (4800, 1400)])
def test_off_idle_advance_follows_the_3d_map(rpm, airflow):
    s, since = sim_at(ms=1200, rpm=rpm, airflow_us=airflow, idl=False)
    t = s.rom[0xFF40 - 0xF000 : 0xFF40 - 0xF000 + 6 * 14 + 2]
    tvis = 8 if s.ram("TVIScounter") < 0x80 else 0  # +8 while T-VIS is off [ROM:$F89D]
    assert s.ram("BaseAdvance") == lookup_3d(t, 14, s.ram("RPMish"), s.ram("Load", 2)) + tvis
    want = advance_from_rom_formula(s.ram("BaseAdvance"), s.ram("ThW_tADV"), s.ram("IDLcompADV"), s.ram("deltaNE", 2))
    got = s.spark_advance(since)
    assert got and all(a == pytest.approx(want, abs=0.15) for a in got[-5:])


def test_idle_advance_and_t_terminal_ten_degrees():
    s, since = sim_at(rpm=900)
    assert s.ram("BaseAdvance") == 0x2D  # fixed idle value [ROM:$F84A]
    want = advance_from_rom_formula(0x2D, s.ram("ThW_tADV"), s.ram("IDLcompADV"), s.ram("deltaNE", 2))
    assert s.spark_advance(since)[-1] == pytest.approx(want, abs=0.15)
    s, since = sim_at(rpm=900, t_shorted=True)
    assert s.spark_advance(since)[-1] == pytest.approx(10, abs=0.5)  # factory: 10° BTDC with T-E1 shorted


def test_rev_limiter_cuts_fuel_and_recovers():
    s, since = sim_at(rpm=7600, idl=False, airflow_us=900)
    assert not s.injector_pulses("#10", since) and not s.injector_pulses("#20", since)
    assert s.engine.sparks[-1] > since  # spark continues: fuel-only cut
    s.inputs.rpm = 6000
    s.engine.update_sensors()
    s.run_ms(500)
    assert s.injector_pulses("#10", s.periph.now - 200_000)


def test_missing_igf_cuts_fuel():
    s, since = sim_at(rpm=900, igf=False)
    assert not s.injector_pulses("#10", since) and not s.injector_pulses("#20", since)
    assert s.ram("SatCount_98") >= 0x80
