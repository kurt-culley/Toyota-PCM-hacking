"""P4 Tier-B pass: Ross's "Lifting the Lid" claims checked against the 17140 ROM (docs/ross/claims.md).

Two kinds of evidence:
- **Table decodes** read the ROM bytes through the lookup arithmetic of $F11D-$F16A (byte tables
  [offset, max, data...] stepped by 256 / A input counts), or run the ROM's own code in the routine
  harness.
- **Behaviour** runs in the whole-ROM simulator. These tests use the C-backed ``CSimulation``,
  which tests/test_d151801_c.py holds bit-identical to the Python simulator, because it is faster.

Units: RpmIndex `$73` = rpm / 25 and RpmWord `$77` = rpm x 0.32 (docs/mr2/maps.md); a fuel factor v
multiplies by (v + 410) / 512, so 102 = x1.00. ``ref_v=3.0`` selects the 256-counts-per-5-V ADC
scale argued in docs/ross/claims.md (R-F05, STATUS conflicts log); every other run uses the
simulator's default scale.
"""

from __future__ import annotations

import shutil

import pytest

from pcmre.emu.engine17140 import ROM_17140, Inputs17140
from pcmre.emu.harness import call, run

ROM = ROM_17140.read_bytes()
needs_cc = pytest.mark.skipif(not (shutil.which("cc") or shutil.which("gcc")), reason="no host C compiler")


def byte(a: int) -> int:
    return ROM[a - 0xF000]


def table(addr: int, mult: int) -> tuple[list[int], list[int]]:
    """A byte table read through L_F132 with A = ``mult``: (sites in input counts, values)."""
    off, mx = byte(addr), byte(addr + 1)
    n = mult * mx // 256 + 1
    return [off + i * 256 // mult for i in range(n)], [byte(addr + 2 + i) for i in range(n)]


def pct(v: float) -> float:
    """A fuel factor as a percentage change."""
    return (v + 410) / 512 * 100 - 100


def sim(ms: float = 600, **kw):
    from pcmre.emu.cboard import CSimulation

    s = CSimulation(inputs=Inputs17140(**kw))
    s.engine.update_sensors()
    s.run_ms(ms)
    return s


def mem(s, a: int, width: int = 1) -> int:
    v = 0
    for k in range(width):
        v = v << 8 | s.periph.mem[a + k]
    return v


# ---- fuel ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("rpmword", "table_addr"), [(0x03FF, 0xF0FF), (0x0400, 0xF10B)])
def test_density_maps_split_at_3200_rpm(rpmword, table_addr):
    """R-F02/R-F04: DensityLookup takes the second map from RpmWord $0400 (3200 rpm); base = map x 32."""
    load = 0x0200
    r = call(ROM, 0xF9F0, x=0xF0FF, ram={0x77: rpmword >> 8, 0x78: rpmword & 0xFF, 0x46: load >> 8, 0x47: load & 0xFF})
    i, frac = divmod(load * 4 - 0x03A4, 256)
    lo, hi = byte(table_addr + 3 + i), byte(table_addr + 4 + i)
    assert r.d == pytest.approx((lo + frac * (hi - lo) / 256) * 32, abs=32)


def test_density_maps_have_nine_sites_and_a_steeper_top_site():
    """R-F03: 9 sites, not 11. R-F05: the top site sits about 5 % above the line through sites 3-8."""
    for a in (0xF0FF, 0xF10B):
        assert byte(a + 2) == 8  # max index 8 -> 9 sites
        d = list(ROM[a - 0xF000 + 3 : a - 0xF000 + 12])
        steps = [d[k + 1] - d[k] for k in range(8)]
        assert steps[-1] > 1.25 * max(steps[2:7])
        slope = (d[7] - d[2]) / 5
        assert d[8] / (d[7] + slope) > 1.03


def speed_factor(rpm: float) -> int:
    """Run the speed-map lookup of FuelPulse [ROM:$FA55-$FA6C] for one engine speed."""
    w = round(rpm * 0.32)
    return run(ROM, 0xFA55, 0xFA6E, ram={0x77: w >> 8, 0x78: w & 0xFF}).a


def test_speed_correction_below_3200_leans_off_at_low_rpm():
    """R-F06/R-F08: sites 600/800/1000/1200, then every 400 rpm to 3200; -13.5 % at 600, -5.9 % at 800."""
    sites = [600, 800, 1000, 1200, 1600, 2000, 2400, 2800]
    assert [speed_factor(r) for r in sites] == [33, 72, 89, 88, 108, 117, 127, 132]
    assert pct(speed_factor(600)) == pytest.approx(-13.5, abs=0.1)
    assert pct(speed_factor(800)) == pytest.approx(-5.9, abs=0.1)


def test_speed_correction_above_3200_differs_from_the_17030():
    """R-F07: -4.5 % to +4.1 %, zero at 3600 rpm, a peak at 4000 and a dip at 4400 (17030: -10..+8 %, zero 5200)."""
    sites = range(3200, 7201, 400)
    v = [speed_factor(r) for r in sites]
    assert v == [79, 102, 114, 104, 115, 123, 115, 115, 112, 95, 97]
    assert min(map(pct, v)) == pytest.approx(-4.5, abs=0.1)
    assert max(map(pct, v)) == pytest.approx(4.1, abs=0.1)


def stair(walk_base: int) -> list[tuple[int, int]]:
    """Staircase entries [rpm word, factor] from walk_base + 3 up to the $FFFF end marker."""
    out, a = [], walk_base + 3
    while True:
        w = byte(a) << 8 | byte(a + 1)
        out.append((w, byte(a + 2)))
        if w == 0xFFFF:
            return out
        a += 3


def test_hard_driving_staircase_sites():
    """R-F09/R-F10: 3500/4500/5100/5700/6100/6500 rpm on the 17140 (17030: 1800 ... 6650)."""
    e = stair(0xF1D7)
    assert [round(w / 0.32) for w, _ in e[:-1]] == [3500, 4500, 5100, 5700, 6100, 6500]
    assert [f for _, f in e] == [90, 81, 101, 85, 109, 77, 92]
    assert [round(w / 0.32) for w, _ in stair(0xF1C5)[:-1]] == [600, 650, 950, 1100, 1150]


@needs_cc
def test_hard_driving_staircase_does_not_interpolate():
    """R-F10: at full load the factor jumps between sites; at mid load it is a fixed x1.00 [ROM:$FA75-$FA8F]."""
    got = {rpm: mem(sim(600, rpm=rpm, map_kpa=100, tps_v=4.0, ref_v=3.0), 0xB8) for rpm in (3400, 3600, 4400, 4600)}
    assert got == pytest.approx({3400: 90, 3600: 81, 4400: 81, 4600: 101}, abs=1)
    assert mem(sim(600, rpm=4600, map_kpa=60, ref_v=3.0), 0xB8) == pytest.approx(102, abs=1)


def test_air_temperature_correction_matches_ross_values():
    """R-F11: 4 sites, -9.4/-2.3/+2.9/+9.4 % from hot to cold air (Ross p6: -9.4/-2.4/+2.9/+9.2 %)."""
    sites, v = table(0xF083, 4)
    assert sites == [35, 99, 163, 227]
    assert [round(pct(x), 1) for x in v] == [-9.4, -2.3, 2.9, 9.4]


@needs_cc
def test_colder_air_gets_more_fuel():
    hot, cold = sim(500, rpm=2000, map_kpa=60, tha_v=1.0), sim(500, rpm=2000, map_kpa=60, tha_v=3.5)
    assert mem(cold, 0x5E) > mem(hot, 0x5E)
    assert mem(cold, 0x88, 2) > mem(hot, 0x88, 2)


@needs_cc
@pytest.mark.parametrize(("rpm", "ratio"), [(1000, 1.0), (2800, 1.051)])
def test_p34_low_multiplies_fuel_by_the_secret_rpm_correction(rpm, ratio):
    """R-F12: P34 = 0 multiplies the pulse by table $F117 (x1.00/1.025/1.05 at 1200/2000/2800 rpm)."""
    a, b = sim(500, rpm=rpm, map_kpa=60, p34=1), sim(500, rpm=rpm, map_kpa=60, p34=0)
    assert mem(b, 0x88, 2) / mem(a, 0x88, 2) == pytest.approx(ratio, abs=0.003)


@needs_cc
def test_global_factor_steps_up_at_6300_rpm():
    """R-F13/R-F14: at high load the region state $62 goes to 0 from 6300 rpm (back below 6100) and $60 rises."""
    s = sim(3000, rpm=6250, map_kpa=100, tps_v=4.0)  # after-start term $5C gone after about 3 s
    assert (mem(s, 0x62), mem(s, 0x60), mem(s, 0x5C)) == (1, 36, 0)
    before = mem(s, 0x88, 2)
    s.inputs.rpm = 6350
    s.run_ms(300)
    assert (mem(s, 0x62), mem(s, 0x60)) == (0, 50)
    assert mem(s, 0x88, 2) / before == pytest.approx(178 / 164, abs=0.01)  # ($5D + $60) ratio, $5D = 128
    s.inputs.rpm = 6150
    s.run_ms(300)
    assert mem(s, 0x62) == 0  # hysteresis
    s.inputs.rpm = 6050
    s.run_ms(300)
    assert mem(s, 0x62) == 1


@needs_cc
def test_global_factor_drops_below_the_throttle_threshold():
    """R-F13/R-F15: TpsOpen >= $3D raises $60 (light load: 8 -> 36); the factor is $5D + $5C + $60 (+ transient)."""
    lo, hi = (
        sim(1500, rpm=3000, map_kpa=50, tps_v=2.0, ref_v=3.0),
        sim(1500, rpm=3000, map_kpa=50, tps_v=2.2, ref_v=3.0),
    )
    assert mem(lo, 0x44) < 0x3D <= mem(hi, 0x44)
    assert (mem(lo, 0x60), mem(hi, 0x60)) == (8, 36)
    terms = [mem(x, 0x5D) + mem(x, 0x5C) + mem(x, 0x60) for x in (lo, hi)]
    assert mem(hi, 0x88, 2) / mem(lo, 0x88, 2) == pytest.approx(terms[1] / terms[0], abs=0.005)


@needs_cc
def test_throttle_snap_gives_a_brief_enrichment():
    """R-F19: a snap from 40 to 95 kPa first overshoots the settled pulse, then decays."""
    s = sim(2500, rpm=2400, map_kpa=40, tps_v=0.9)
    s.inputs.map_kpa, s.inputs.tps_v = 95, 4.0
    peak = 0
    for _ in range(10):
        s.run_ms(10)
        peak = max(peak, mem(s, 0x88, 2))
    s.run_ms(1500)
    assert peak / mem(s, 0x88, 2) > 1.2


@needs_cc
def test_dead_time_rises_as_the_battery_voltage_falls():
    """R-F17: InjDeadTime $8A from table $F0A4 (ADC ch4), added once when the pulse is scheduled."""
    dead = [mem(sim(400, rpm=2000, map_kpa=60, batt_v=v), 0x8A, 2) for v in (3.0, 3.5, 4.0)]
    assert dead[0] > dead[1] > dead[2]


@needs_cc
def test_double_pulse_every_other_revolution_above_6000_rpm():
    """R-F24: above 6000 rpm one pulse of 2 x InjPulse + one dead time every other revolution; back below 5600."""

    def window(s, rpm):
        s.inputs.rpm = rpm
        s.run_ms(400)
        t0 = s.periph.now - 200_000
        p = [(a, b) for a, b in s.engine.inj["Tout1"] if a >= t0]
        return len(p) / (0.2 * rpm / 60), p[-1][1] - p[-1][0]

    s = sim(600, rpm=5800, map_kpa=95, tps_v=4.0)
    per_rev, _ = window(s, 5800)
    assert per_rev == pytest.approx(1, abs=0.1)
    per_rev, width = window(s, 6200)
    assert per_rev == pytest.approx(0.5, abs=0.1)
    assert width == pytest.approx(2 * mem(s, 0x88, 2) + mem(s, 0x8A, 2), abs=40)
    assert window(s, 5700)[0] == pytest.approx(0.5, abs=0.1)  # hysteresis
    assert window(s, 5550)[0] == pytest.approx(1, abs=0.1)


@needs_cc
def test_decel_fuel_cut_and_return():
    """R-F25: throttle closed (P1-6 low): cut above 1800 rpm, fuel back at 1400 (warm, standing, P3-7 low)."""
    s = sim(5600, rpm=2600, map_kpa=30, idl_closed=True, p37=0)

    def fuelled(rpm):
        s.inputs.rpm = rpm
        s.run_ms(250)
        return not mem(s, 0x99) & 0x02 and len(s.injector_pulses("Tout1", s.periph.now - 120_000)) > 0

    assert [fuelled(r) for r in (2600, 1500, 1425, 1375, 1750, 1800, 1850)] == [
        False, False, False, True, True, True, False,
    ]  # fmt: skip
    s.inputs.p37 = 1  # floor $3C: back at 1500, cut above about 1900 (the 1988 RM's A/C-on figures)
    s.engine.update_sensors()
    assert [fuelled(r) for r in (1850, 1525, 1475, 1875, 1950)] == [False, False, True, True, False]


@needs_cc
def test_mixture_screw_correction():
    """R-M03/R-M04/R-F16: the pulse changes by (Mixture - 128) x MX2 / 32 us, below 3600 rpm and MapRaw 154."""
    _, mx2 = table(0xF0BD, 8)
    for rpm, kpa, expect_mx2 in ((1000, 60, mx2[0]), (3400, 60, mx2[-1]), (3700, 60, 0), (1000, 115, 0)):
        a, b = sim(400, rpm=rpm, map_kpa=kpa, vaf_v=2.5), sim(400, rpm=rpm, map_kpa=kpa, vaf_v=4.5)
        delta = mem(b, 0x88, 2) - mem(a, 0x88, 2)
        assert delta == pytest.approx((mem(b, 0x8C) - mem(a, 0x8C)) * expect_mx2 / 32, abs=1)


@needs_cc
def test_mixture_screw_end_stops_read_as_zero_correction():
    """R-M06 and R-M01: readings below 10 or from 248 give Mixture = 128 (zero); mid travel reads about 128."""
    got = [mem(sim(400, rpm=1000, map_kpa=50, vaf_v=v, ref_v=3.0), 0x8C) for v in (0.15, 0.25, 2.5, 4.8, 4.9)]
    assert got[0] == got[4] == 128
    assert got[1] < 40 and got[3] > 200
    assert got[2] == pytest.approx(128, abs=4)


def test_mixture_tables():
    """R-M01/R-M02/R-M06: limits, the 3-piece remap and MX2.

    MX2 holds 128/113/96/81/64 at 1000/1800/2600/3400/4200 rpm; the input clamp at RpmIndex 144
    (3600 rpm) stops it at 76, so the 64 is never reached. Ross p17 shows the same five values at
    1000/1650/2300/2950/3600 rpm.
    """
    assert (byte(0xF00E), byte(0xF00D)) == (10, 248)  # valid reading 10 <= r < 248 [ROM:$F01E via $FC6D]
    assert (byte(0xF00F), byte(0xF010), byte(0xF011), byte(0xF012)) == (0x9A, 0x90, 0x96, 0x88)
    assert list(ROM[0xF0BF - 0xF000 : 0xF0C4 - 0xF000]) == [128, 113, 96, 81, 64]

    def mx2(rpm: int) -> int:  # the ROM's own lookup, as FuelPulse calls it [ROM:$FAEC-$FAF1]
        return call(ROM, 0xF12C, x=0xF0BD, b=rpm // 25).a

    assert [mx2(r) for r in (800, 1000, 1800, 2600, 3400)] == [128, 128, 113, 96, 81]
    assert mx2(3500) == 78 and mx2(3600) == mx2(4500) == 76
    # mid-range remap passes through 128 at a reading of 128
    sites, v = table(0xF0AB, 4)
    assert sites[:2] == [48, 112] and v[1] + (v[2] - v[1]) * (128 - 112) / 64 == 128


# ---- ignition ---------------------------------------------------------------------------------------


def lookup2d(rpmword: int, load: int, addr: int = 0xF1EF) -> int:
    return call(ROM, 0xF16A, x=addr, a=rpmword >> 8, b=rpmword & 0xFF, ram={0xAF: load >> 8, 0xB0: load & 0xFF}).a


def test_ignition_map_interpolates_in_rpm_and_load():
    """R-I05: Lookup2D blends both axes. Map A, 4000/4400 rpm (cols 8/9), load rows 5/6."""
    col = lambda c: 256 + 128 * c  # noqa: E731  RpmWord of column c
    row = lambda r: 297 + 64 * r  # noqa: E731  Load of row r
    assert lookup2d(col(8), row(5)) == 104
    assert lookup2d(round(col(8.5)), row(5)) == pytest.approx((104 + 116) / 2, abs=1)
    assert lookup2d(col(8), round(row(5.5))) == pytest.approx((104 + 92) / 2, abs=1)
    assert lookup2d(round(col(8.5)), round(row(5.5))) == pytest.approx((104 + 116 + 92 + 102) / 4, abs=1)


def test_idle_ignition_table_matches_ross():
    """R-I07: $F0FA, 3 sites at 1200/1600/2000 rpm, values 68/98/162: Ross p14 reads 68/98/162."""
    sites, v = table(0xF0FA, 16)
    assert [s * 25 for s in sites] == [1200, 1600, 2000]
    assert v == [68, 98, 162]


@needs_cc
@pytest.mark.parametrize(("rpm", "base"), [(900, 68), (1600, 98), (3000, 162)])
def test_closed_throttle_uses_the_idle_ignition_table(rpm, base):
    s = sim(1200, rpm=rpm, map_kpa=35, idl_closed=True)
    assert mem(s, 0x99) & 0x80
    assert mem(s, 0xA8) == base


@needs_cc
def test_t_terminal_fixed_sum_only_with_the_throttle_closed():
    """The fixed sum $00AA replaces the maps only with T shorted AND the throttle closed [ROM:$F7F2-$F800]."""

    def spark(**kw):
        s = sim(1200, rpm=900, **kw)
        return s.engine.spark_tooth_offsets(s.periph.now - 100_000)[-1]

    fixed = spark(map_kpa=30, idl_closed=True, test_terminal=True)
    assert spark(map_kpa=45, idl_closed=True, test_terminal=True) == pytest.approx(fixed, abs=0.01)
    idle = spark(map_kpa=30, idl_closed=True)
    assert fixed - idle == pytest.approx((2 * 68 + 85 - 0xAA) * 15 / 128, abs=0.05)  # warm idle, T open
    assert spark(map_kpa=35, test_terminal=True) == pytest.approx(spark(map_kpa=35), abs=0.01)


def test_tvis_and_6000_rpm_thresholds_in_code():
    """R-I10: P41 on above RpmIndex $BA (4650 rpm), off at $AA (4250). R-F24: $F0/$E0 = 6000/5600 rpm."""
    assert (byte(0xFBAD) * 25, byte(0xFBA7) * 25) == (4650, 4250)
    assert (byte(0xF45C) * 25, byte(0xF458) * 25) == (6000, 5600)


@needs_cc
def test_tvis_output_and_delayed_advance_step():
    """R-I09/R-I10: P4-1 switches at 4650/4250 rpm; +13 map counts (3.0 deg) follow after about 0.2 s."""
    s = sim(600, rpm=4500, map_kpa=60, tps_v=2.0)
    ev: list[tuple[int, int]] = []
    s.periph.listeners.append(lambda n, lvl, t: ev.append((t, lvl)) if n == "P4-1" else None)
    for on_rpm in range(4500, 4800, 10):
        s.inputs.rpm = on_rpm
        s.run_ms(100)
        if ev:
            break
    assert ev[-1][1] == 1 and 4650 <= on_rpm <= 4700
    t_on, base = ev[-1][0], mem(s, 0xA8)
    while mem(s, 0xA8) == base and s.periph.now - t_on < 500_000:
        s.run_ms(5)
    assert mem(s, 0xA8) - base == 13
    assert 0.15 < (s.periph.now - t_on) / 1e6 < 0.3
    for r in range(on_rpm, 4000, -10):
        s.inputs.rpm = r
        s.run_ms(100)
        if ev[-1][1] == 0:
            break
    assert 4250 <= r <= 4275


def test_warm_up_and_over_temperature_advance_tables():
    """R-I11: $F0EC adds up to +60 sum counts (7.0 deg) cold, 0 when warm. R-I12: $F0F2 drops to 17 (-8.0 deg)."""
    sites, v = table(0xF0EC, 8)
    assert sites == [99, 131, 163, 195] and v == [85, 127, 132, 145]
    assert (v[-1] - v[0]) * 15 / 128 == pytest.approx(7.0, abs=0.05)
    sites, v = table(0xF0F2, 0x40)
    assert sites == [14, 18] and v == [17, 85]
    assert (v[0] - v[1]) * 15 / 128 == pytest.approx(-8.0, abs=0.05)


@needs_cc
def test_over_temperature_retard_only_at_high_load():
    hot_hi, hot_lo = sim(500, rpm=2500, map_kpa=100, thw_v=0.3, tps_v=3.0), sim(500, rpm=2500, map_kpa=60, thw_v=0.3)
    warm_hi = sim(500, rpm=2500, map_kpa=100, thw_v=0.5, tps_v=3.0)
    assert (mem(hot_hi, 0xA9), mem(hot_lo, 0xA9), mem(warm_hi, 0xA9)) == (17, 85, 85)


@needs_cc
def test_idle_stability_advance_on_an_rpm_dip():
    """R-I13: closed throttle, a 50 rpm dip adds advance ($AA, max 68 from table $F0F6) that decays away."""
    assert table(0xF0F6, 16) == ([0, 16], [0, 68])
    s = sim(2500, rpm=900, map_kpa=35, idl_closed=True)
    assert mem(s, 0xAA) == 0
    s.inputs.rpm = 850
    trace = []
    for _ in range(40):
        s.run_ms(20)
        trace.append(mem(s, 0xAA))
    assert 0 < max(trace) <= 68
    assert trace[-1] < max(trace)  # decays while the dip lasts


def test_fault_codes_survive_a_reset_and_nothing_is_learned():
    """R-I14: $40-$43 (fault codes, value + complement, $5A signature) survive; $44-$CB is cleared."""
    ram = {0x03: 0xE0, 0x06: 0xFF, 0x02: 0xFF, 0x40: 0x5B, 0x41: 0xA4, 0x42: 0x12, 0x43: 0xED, 0x45: 0x20, 0x8C: 0x99}
    r = run(ROM, 0xF2BE, 0xF371, ram=ram)  # reset code up to MainLoop
    r = run(ROM, 0xF3CC, 0xF403, ram={a: r.mem[a] for a in range(0x40, 0x100)})  # standby-RAM check
    assert [r.mem[a] for a in (0x40, 0x41, 0x42, 0x43)] == [0x5B, 0xA4, 0x12, 0xED]
    assert r.mem[0x45] == 0x2C and r.mem[0x8C] == 0  # TPS zero back to its default; RAM cleared
    ram[0x43] = 0xEC  # broken complement -> reinitialised
    r = run(ROM, 0xF2BE, 0xF371, ram=ram)
    r = run(ROM, 0xF3CC, 0xF403, ram={a: r.mem[a] for a in range(0x40, 0x100)})
    assert [r.mem[a] for a in (0x40, 0x41, 0x42, 0x43)] == [0x5A, 0xA5, 0x00, 0xFF]


@pytest.mark.parametrize(("p16", "p37", "bit"), [(0, 0, 0), (0, 1, 2), (1, 0, 2), (1, 1, 2)])
@pytest.mark.parametrize("p17", [0, 1])
def test_code_51_check_ors_idl_open_with_p37(p16, p37, bit, p17):
    """With T shorted (P30 = 0) $F769-$F797 puts P16 OR P37 into bit 1 of the value stored at $AB.

    Clear only with the throttle closed (P16 low) and P37 low: Toyota's code 51, "IDL off or A/C
    on with T-E1 shorted", so P37 high = A/C on (LIKELY). P17 does not take part.
    """
    ram = {0x02: p17 << 7 | p16 << 6, 0x06: p37 << 7, 0x40: 0, 0x42: 0}  # PORT1, PORT3 (bit 0 = T shorted)
    r = run(ROM, 0xF769, 0xF797, ram=ram)
    assert r.a == bit


def crank_then_idle(idle_s: float, **kw):
    """Crank at 200 rpm with P1-7 held low for 1.5 s, then raise P1-7 and idle at 900 rpm.

    Returns the simulation, the P1-7 rise time and the P3-1 / P2-2 edges as (seconds, pin, level).
    """
    from pcmre.emu.cboard import CSimulation

    s = CSimulation(inputs=Inputs17140(rpm=200, map_kpa=90, idl_closed=True, ref_v=3.0, **kw))
    ev: list[tuple[float, str, int]] = []
    s.periph.listeners.append(lambda n, lvl, t: ev.append((t / 1e6, n, lvl)) if n in ("P3-1", "P2-2") else None)
    s.engine.update_sensors()
    s.periph.set_pin(1, 7, 0)
    s.run_ms(1500)
    s.periph.set_pin(1, 7, 1)
    s.inputs.rpm, s.inputs.map_kpa = 900, 35
    s.engine.update_sensors()
    rise = s.periph.now / 1e6
    s.run_ms(idle_s * 1000)
    return s, rise, ev


def last_edge(ev, pin: str, level: int, after: float = 0.01) -> list[float]:
    return [t for t, n, lvl in ev if n == pin and lvl == level and t > after]


@needs_cc
def test_hot_crank_p31_timer_and_port2_bit2():
    """R-I08 / Q2: P31 is on until 20-21 s after P1-7 rises (21 one-second ticks of $71; 20.5 s for
    a rise at 1.5 s, as here) [ROM:$F3A2-$F3CC]; after a hot crank
    (Coolant 15, Tha 51) PORT2 bit 2 goes low at about 0.18 s and back high at about 92 s [ROM:$F478-$F49F,
    $F654-$F672]."""
    s, rise, ev = crank_then_idle(93, thw_v=0.3, tha_v=1.0)
    assert (mem(s, 0x53), mem(s, 0x5F)) == (15, 51)
    off = last_edge(ev, "P3-1", 0)
    assert len(off) == 1 and off[0] - rise == pytest.approx(20.5, abs=0.3)
    assert [round(t, 1) for t in last_edge(ev, "P2-2", 0)] == [0.2]
    assert [t for t in last_edge(ev, "P2-2", 1)] == [pytest.approx(92, abs=1)]


@needs_cc
def test_warmer_crank_keeps_port2_bit2_high():
    """R-I08: with Coolant above $18 the hot-start output stays high; the P31 timer is the same."""
    s, rise, ev = crank_then_idle(22, thw_v=0.5, tha_v=2.5)
    assert mem(s, 0x53) > 0x18
    assert last_edge(ev, "P2-2", 0) == []
    assert last_edge(ev, "P3-1", 0)[0] - rise == pytest.approx(20.5, abs=0.3)


# ---- ADC scale (evidence for the kPa conflict) ------------------------------------------------------


def test_adc_reference_table_is_ratiometric():
    """$F044: (AdcRef + 410) x reference time is constant, so a reading = 153.7 x V / V_ch7."""
    products = [(byte(0xF047 + i) + 410) * (0x2068 + 256 * i) / 16 for i in range(15)]
    assert max(products) / min(products) < 1.002
    assert sum(products) / len(products) / 2048 == pytest.approx(153.7, abs=0.1)


@needs_cc
def test_load_tables_top_out_at_one_atmosphere_on_a_256_per_5v_scale():
    """With 256 counts per 5 V, 101.3 kPa reads Load 745: the top row of both ignition maps and the density map."""
    tops = {
        (h[0] << 8 | h[1]) / 4 + 64 * h[2] for h in (ROM[a - 0xF000 + 3 : a - 0xF000 + 6] for a in (0xF1EF, 0xF25D))
    }
    tops.add(((byte(0xF0FF) << 8 | byte(0xF100)) + 256 * byte(0xF101)) / 4)
    assert tops == {745}
    assert mem(sim(400, rpm=2000, map_kpa=101.3, ref_v=3.0), 0x46, 2) == pytest.approx(745, abs=3)
