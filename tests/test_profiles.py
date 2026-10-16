"""ECU input profiles: the Bluetop wiring is unchanged, and a MAP-sensor (D-type) profile works."""

from __future__ import annotations

import pytest

from emu.engine import BLUETOP, EcuProfile, mr2_dtype
from emu.sensors import pim_points, pim_raw, pim_volts
from emu.sim import Simulation


def test_pim_model_matches_the_ewd_points():
    for kpa, volts, note in pim_points():
        tol = 0.25 if "ambiguous" in note else 0.05  # the 100 kPa scan digit is 6 or 8
        assert pim_volts(kpa) == pytest.approx(volts, abs=tol), (kpa, volts)
    assert pim_raw(20) < pim_raw(60) < pim_raw(100) < pim_raw(112)


def test_bluetop_profile_is_the_default_wiring():
    s = Simulation()
    assert s.engine.profile is BLUETOP
    i = s.inputs
    i.tps_raw, i.battery_v, i.pwr_raw = 0x40, 12.5, 0x22
    s.engine.update_sensors()
    adc = s.periph.adc
    assert (adc[0], adc[1], adc[4]) == (0x40, round(12.5 * 255 / 25), 0x22)


def test_dtype_profile_puts_pim_on_its_channel_and_drops_the_airflow_edge():
    prof = mr2_dtype({0: "tps", 1: "batt", 2: "tha", 3: "thw", 4: "pim", 5: "co"}, thw_table=(0xFEF0, 0xFF28))
    s = Simulation(profile=prof)
    ic1_high = []
    set_pin = s.periph.set_pin
    s.periph.set_pin = lambda port, bit, v: (
        (ic1_high.append(1) if (port, bit, v) == (2, 0, 1) else None) or set_pin(port, bit, v)
    )
    s.inputs.map_kpa, s.inputs.mixture_raw = 45.0, 0x90
    s.inputs.rpm, s.inputs.idl = 2000, False
    s.engine.update_sensors()
    s.run_ms(300)
    assert s.periph.adc[4] == pim_raw(45.0) and s.periph.adc[5] == 0x90
    assert s.engine.falls and s.engine.sparks  # crank signals and ignition still run
    assert not ic1_high  # no SE056 airflow edge on IC1


def test_profiles_reject_bad_wiring():
    with pytest.raises(ValueError):
        EcuProfile("x", {0: "nonsense"}, None, True)
    with pytest.raises(ValueError):
        mr2_dtype({0: "tps"}, None)


def test_rom_base_follows_the_image_size():
    rom = bytes(0x1000) + Simulation().rom  # an 8 KB image ending at $FFFF
    s = Simulation(rom=rom)
    assert s.rom_base == 0xE000 and s.periph.read(0xF000) == rom[0x1000]
