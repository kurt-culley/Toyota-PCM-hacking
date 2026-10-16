"""The in-car firmware's logic (hardware/ecu-emu/car/car.h), without a car.

A host program runs car.h exactly as the firmware does: an input ring sampled once per
microsecond, an output ring played once per microsecond, and car_poll in between. The "ECU
board" around it is the chip test's engine model (chipdiff.h's cd_word / cd_sample: crank
schedule, ADC hybrid, IGF echo), wired through the car pin map (pins.h) instead of the chip
test's. The log it prints is in the chip test's format, so emu.chipdiff's analysis replays the
inputs the board applied into a fresh emulator and checks every output edge:

- with the safety hold off, every output pin must match at one constant latency, CAR_LOUT: the
  glue (input events, capture timestamps, output and drive-mask timing, the pin maps) adds a fixed
  delay and nothing else;
- with the hold on (the build that goes in the car), IGT and the injector never move while every
  other pin still matches, and the emulator's own spark and injection counts show they would have.

The Python simulator also confirms the key-on, engine-off expectation used for the hold level.
"""

from __future__ import annotations

import re
import shutil
import subprocess

import pytest

from emu import chipdiff
from emu.engine17140 import ROM_17140, Engine17140, Inputs17140
from emu.sim import Simulation
from pcmre.roundtrip import ROOT

CC = shutil.which("cc") or shutil.which("gcc")
CORE = ROOT / "hardware/ecu-emu/core"
LOOP = ROOT / "hardware/ecu-emu/loopback"
CD = ROOT / "hardware/ecu-emu/chipdiff"
CAR = ROOT / "hardware/ecu-emu/car"
LOUT = 100
CYCLES = 7_000_000  # 6 s cranking at 200 rpm with the idle contact closed, then 1 s at 800 rpm

HOST = r"""
#include <stdio.h>
#include <stdlib.h>
#include "board.h"
#include "expected.h"
#include "engine.h"
#define CD_LAT_PORT 0  /* the "chip" is seen at the pins: reactions are timed from there */
#define CD_LAT_OC 0
#include "chipdiff.h"
#include "car.h"

static uint32_t in_ring[CAR_IN_N], out_ring[CAR_OUT_N];
static car_t car;
static uint32_t oe;
static void set_oe(car_t *c, uint32_t m) { (void)c; oe = m; }
static int cd_of_car[32];

static uint32_t to_cd(uint32_t w) {  // car-layout word -> chip-test layout, by (port, bit)
    uint32_t r = 0;
    for (int g = 0; g < 32; g++)
        if (cd_of_car[g] >= 0 && (w >> g & 1u)) r |= 1u << cd_of_car[g];
    return r;
}

int main(int argc, char **argv) {
    static unsigned char rom[4096];
    FILE *f = fopen(argv[1], "rb");
    if (argc < 4 || !f || fread(rom, 1, 4096, f) != 4096) return 2;
    fclose(f);
    int64_t n = atoll(argv[2]), res_at = atoll(argv[3]);
    for (int g = 0; g < 32; g++) cd_of_car[g] = -1;
#define MAP_(g, port, bit, dir) { int k = car_gpio((port), (bit)); if (k >= 0) cd_of_car[k] = (g); }
    CD_PINS(MAP_)
    car_init(&car, rom, in_ring, out_ring, set_oe);
    static cd_t cd;
    cd_init(&cd);
    uint32_t lastlog = 0xFFFFFFFFu;
    for (int64_t k = 0; k < n; k++) {
        uint32_t wcd = cd_word(&cd, k);
        uint32_t played = out_ring[(uint64_t)k % CAR_OUT_N];
        uint32_t view = (played & oe) | (car.out_mask & ~oe);  // undriven outputs read high
        uint32_t sample = 0;
        for (int i = 0; i < CAR_NPINS; i++) {
            const car_pin_t *p = &CAR_TAB[i];
            uint32_t bit = p->dir == CAR_D_IN ? (wcd >> cd_of_car[p->g] & 1u) : (view >> p->g & 1u);
            sample |= bit << p->g;
        }
        if (!(res_at > 0 && k >= res_at && k < res_at + 50)) sample |= car.res_mask;
        in_ring[(uint64_t)k % CAR_IN_N] = sample;
        uint32_t pins = (wcd & CD_IN_MASK) | to_cd(view & car.out_mask);
        cd_sample(&cd, k, pins);
        if (pins != lastlog) printf("%llx %x\n", (unsigned long long)k, pins);
        lastlog = pins;
        car_poll(&car, k + 1, k + 1);
    }
    printf("# car runs=%u resets=%u late=%u qfull=%u oeqfull=%u lost=%u traps=%u lag_max=%lld spark=%u inj=%u "
           "inj_last=%u adc_n=%u,%u,%u,%u,%u,%u,%u,%u adc_us=%u,%u,%u,%u,%u,%u,%u,%u\n",
           car.runs, car.resets, car.late, car.qfull, car.oeqfull, car.lost, car.traps, (long long)car.lag_max,
           car.spark_n, car.inj_n, car.inj_last_us, car.adc_n[0], car.adc_n[1], car.adc_n[2], car.adc_n[3],
           car.adc_n[4], car.adc_n[5], car.adc_n[6], car.adc_n[7], car.adc_us[0], car.adc_us[1], car.adc_us[2],
           car.adc_us[3], car.adc_us[4], car.adc_us[5], car.adc_us[6], car.adc_us[7]);
    printf("END cycles=%lld late=%u qfull=%u\n", (long long)n, cd.late, cd.qfull);
    return 0;
}
"""

pytestmark = pytest.mark.skipif(CC is None, reason="no host C compiler")


def build(tmp_path, hold: int):
    (tmp_path / "host.c").write_text(HOST)
    exe = tmp_path / f"host{hold}"
    flags = ["-O2", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", f"-DCAR_HOLD={hold}",
             f"-DCAR_LOUT={LOUT}", f"-I{CORE}", f"-I{LOOP}", f"-I{CD}", f"-I{CAR}"]  # fmt: skip
    srcs = [str(tmp_path / "host.c"), *(str(CORE / s) for s in ("hd6301.c", "d151801.c", "board.c"))]
    subprocess.run([CC, *flags, "-o", str(exe), *srcs, "-lm"], check=True)
    return exe


def run(exe, cycles: int, res_at: int = 0) -> str:
    p = subprocess.run([str(exe), str(ROM_17140), str(cycles), str(res_at)], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout


def stats(log: chipdiff.Log) -> dict[str, str]:
    line = next(m for m in log.meta if m.startswith("# car "))
    return dict(re.findall(r"(\w+)=([\d,-]+)", line))


@pytest.fixture(scope="module")
def free_log(tmp_path_factory) -> chipdiff.Log:
    return chipdiff.parse_log(run(build(tmp_path_factory.mktemp("car0"), 0), CYCLES))


@pytest.fixture(scope="module")
def held_log(tmp_path_factory) -> chipdiff.Log:
    return chipdiff.parse_log(run(build(tmp_path_factory.mktemp("car1"), 1), 3_000_000))


def test_glue_is_a_constant_delay(free_log):
    """Hold off: the emulator behind car.h behaves exactly like the emulator alone, CAR_LOUT later."""
    s = stats(free_log)
    assert s["late"] == "0" and s["qfull"] == "0" and s["lost"] == "0" and s["traps"] == "0"
    assert int(s["lag_max"]) < LOUT  # the emulator never fell behind its own output slots
    assert "late=0 qfull=0" in free_log.summary
    offset, res = chipdiff.analyse(free_log, offset=0)
    bad = [(r.pin.name, r.first_bad, dict(r.latency)) for r in res if not r.ok]
    assert not bad, bad
    for r in res:
        if r.chip_n:
            assert set(r.latency) == {LOUT}, (r.pin.name, r.latency)
    names = {r.pin.name: r.chip_n for r in res}
    assert names["P11"] > 100 and names["P21"] > 50 and names["P15"] > 1000  # spark, injector, ADC all ran


def test_hold_keeps_igt_and_injector_still(held_log):
    """Hold on (the car build): IGT and the injector never move, everything else still matches."""
    s = stats(held_log)
    # The emulator still sparks; with IGT held the board never echoes IGF, so the ROM's
    # missing-IGF fail-safe stops injection after the first pulses, as the stock ECU would.
    assert int(s["spark"]) > 10 and 1 <= int(s["inj"]) <= 4
    offset, res = chipdiff.analyse(held_log, offset=0)
    by = {r.pin.name: r for r in res}
    assert by["P11"].chip_n == 0 and by["P21"].chip_n == 0
    assert by["P11"].emu_n > 10 and by["P21"].emu_n >= 2
    others = [(r.pin.name, r.first_bad, dict(r.latency)) for r in res if r.pin.name not in ("P11", "P21") and not r.ok]
    assert not others, others


def test_adc_times_at_the_pins(free_log):
    """The conversion times car.h reports are the board's (chipdiff.h: 30 us + 200 us per volt)."""
    s = stats(free_log)
    n = [int(x) for x in s["adc_n"].split(",")]
    us = [int(x) for x in s["adc_us"].split(",")]
    assert min(n) > 50
    assert abs(us[0] - 30) <= 1  # channel 0: 0 V
    assert abs(us[7] - (30 + 200 * 5.0)) <= 2  # channel 7: the 5 V reference of the chip-test schedule


def test_reset_pulse_restarts_the_chip(tmp_path):
    """/RES low for 50 us mid-run: one reset, outputs released, the ROM boots again and runs on."""
    log = chipdiff.parse_log(run(build(tmp_path, 1), 400_000, res_at=200_000))
    s = stats(log)
    assert s["runs"] == "2" and s["resets"] == "1" and s["traps"] == "0" and s["lost"] == "0"


def test_koeo_no_spark_or_fuel():
    """Key on, engine not turning: the ROM makes no IGT or injector edge in 5 s, and the lamp
    output (P24) goes low at once; the hold level (1) is what the ROM leaves on both pins."""
    edges: list[tuple[int, str, int]] = []
    s = Simulation(ROM_17140.read_bytes(), inputs=Inputs17140(rpm=0), engine=Engine17140)
    s.periph.listeners.append(lambda name, level, t: edges.append((t, name, level)))
    s.engine.update_sensors()
    s.run_ms(5000)
    names = {n for _, n, _ in edges}
    assert "P1-1" not in names and "P2-1" not in names
    assert (s.periph._out(0) >> 1) & 1 == 1 and (s.periph._out(1) >> 1) & 1 == 1
    assert [lv for _, n, lv in edges if n == "P2-4"] == [0]
