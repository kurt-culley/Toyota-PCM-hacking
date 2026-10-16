"""The chip-in-isolation test pipeline (hardware/ecu-emu/chipdiff, emu.chipdiff), without a chip.

A host program runs chipdiff.h exactly as the firmware does, one E cycle at a time, but with
the C emulator standing in for the real D151801: inputs computed ahead with cd_word, pins
sampled each cycle into cd_sample, and every pin change logged in the firmware's format. The
analysis must then find offset 0 and match every output edge with latency 0; a log with one
spark moved by a cycle must FAIL at that edge.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from emu import chipdiff
from emu.engine17140 import ROM_17140
from pcmre.roundtrip import ROOT

CC = shutil.which("cc") or shutil.which("gcc")
pytestmark = pytest.mark.skipif(CC is None, reason="no host C compiler")
CORE = ROOT / "hardware/ecu-emu/core"
LOOP = ROOT / "hardware/ecu-emu/loopback"
CD = ROOT / "hardware/ecu-emu/chipdiff"
CYCLES = 7_000_000  # the 6 s cranking phase and the first second of idle (emu.loopback_ref.SCHEDULE)
LOOKAHEAD = 16  # longer than any instruction, so every input is queued before it is due; reactions come >= 30 later

HOST = r"""
#include <stdio.h>
#include <stdlib.h>
#include "board.h"
#include "expected.h"
#include "engine.h"
#define CD_LAT_PORT 0  /* the "chip" here is the emulator: its edges are seen at their own time */
#define CD_LAT_OC 0
#include "chipdiff.h"

typedef struct { int64_t t; uint32_t w; } iw_t;
static iw_t inq[4096]; static unsigned qh, qt;   // input words for the board, time order
static uint32_t applied;                          // input levels the emulator has
typedef struct { int64_t t; int g, level; } oe_t;
static oe_t oq[4096]; static unsigned oh, ot;     // output edges not yet sampled
static board_t b;

static int64_t next_ev(void *ctx) { (void)ctx; return qt != qh ? inq[qt % 4096].t : -1; }
static void apply(uint32_t w) {
    uint32_t ch = w ^ applied;
#define AP(g, port, bit, dir) \
    if (CD_DIR_##dir && (ch >> (g) & 1u)) { \
        int lv = (int)(w >> (g) & 1u); \
        if ((port) == 0) { if (!lv) d_is3_edge(&b.io); } else d_set_pin(&b.io, (port), (bit), lv); }
    CD_PINS(AP)
    applied = w;
}
static void run_ev(void *ctx) { (void)ctx; apply(inq[qt++ % 4096].w); }
static void on_output(void *ctx, int port, int bit, int level, int64_t t) {
    (void)ctx;
#define OE(g, p, bt, dir) if (!CD_DIR_##dir && port == (p) && bit == (bt)) { oq[oh++ % 4096] = (oe_t){t, (g), level}; }
    CD_PINS(OE)
}

int main(int argc, char **argv) {
    static unsigned char rom[4096];
    FILE *f = fopen(argv[1], "rb");
    if (argc < 4 || !f || fread(rom, 1, 4096, f) != 4096) return 2;
    fclose(f);
    int64_t n = atoll(argv[2]), L = atoll(argv[3]);
    b.io.on_output = on_output; b.next_ev = next_ev; b.run_ev = run_ev;
    board_init(&b, rom, 4096);
    applied = CD_IN_MASK;
    d_set_pin(&b.io, 3, 6, 0);  // the P36 strap
    static cd_t cd;
    cd_init(&cd);
    static uint32_t tx[1024];
    uint32_t outw = CD_OUT_MASK, lastq = applied, lastlog = 0xFFFFFFFFu;
    int64_t F = 0;
    for (int64_t k = 0; k < n; k++) {
        while (F <= k + L) {
            uint32_t w = cd_word(&cd, F);
            tx[F % 1024] = w;
            if (F == 0) apply(w);
            else if (w != lastq) inq[qh++ % 4096] = (iw_t){F, w};
            lastq = w;
            F++;
        }
        while (b.io.now <= k)
            if (board_step(&b) < 0) return 3;
        unsigned m = oh - ot;  // edges with t <= k, in any order among pins
        for (unsigned i = 0; i < m; i++) {
            oe_t e = oq[ot++ % 4096];
            if (e.t <= k) outw = e.level ? (outw | (1u << e.g)) : (outw & ~(1u << e.g));
            else oq[oh++ % 4096] = e;
        }
        uint32_t pins = (tx[k % 1024] & CD_IN_MASK) | outw;
        cd_sample(&cd, k, pins);
        if (pins != lastlog) printf("%llx %x\n", (unsigned long long)k, pins);
        lastlog = pins;
    }
    printf("END cycles=%lld late=%u qfull=%u\n", (long long)n, cd.late, cd.qfull);
    return 0;
}
"""


@pytest.fixture(scope="module")
def host_log(tmp_path_factory) -> str:
    d = tmp_path_factory.mktemp("chipdiff")
    (d / "host.c").write_text(HOST)
    exe = d / "host"
    flags = ["-O2", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", f"-I{CORE}", f"-I{LOOP}", f"-I{CD}"]
    srcs = [str(d / "host.c"), *(str(CORE / s) for s in ("hd6301.c", "d151801.c", "board.c"))]
    subprocess.run([CC, *flags, "-o", str(exe), *srcs, "-lm"], check=True)
    p = subprocess.run([str(exe), str(ROM_17140), str(CYCLES), str(LOOKAHEAD)], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout


def test_pin_table_matches_the_header():
    assert len(chipdiff.PINS) == 23
    assert chipdiff.IN_MASK & chipdiff.OUT_MASK == 0
    names = {p.name for p in chipdiff.PINS}
    assert {"P10", "P11", "P15", "P20", "P21", "SC1"} <= names
    used = {p.gpio for p in chipdiff.PINS} | {8, 9, 19}  # + RES, EXTAL, E
    assert used == set(range(23)) | {26, 27, 28}  # every usable Pico 2 W GPIO, nothing else


def test_engine_runs_and_reacts_on_time(host_log):
    log = chipdiff.parse_log(host_log)
    assert "late=0 qfull=0" in log.summary
    edges = chipdiff.chip_edges(log, log.end)
    assert len(edges[14]) >= 10  # spark edges (P11)
    assert len(edges[6]) > 100  # ADC conversions (P15)


def test_emulator_as_chip_matches_itself_exactly(host_log):
    log = chipdiff.parse_log(host_log)
    offset, res = chipdiff.analyse(log, offset=0)
    assert offset == 0
    bad = [(r.pin.name, r.first_bad, dict(r.latency)) for r in res if not r.ok]
    assert not bad, chipdiff.report(offset, res)
    assert all(set(r.latency) <= {0} for r in res)


def test_offset_search_finds_zero(host_log):
    log = chipdiff.parse_log(host_log)
    offset, _ = chipdiff.find_offset(log, span=150_000, search=range(-3, 4))
    assert offset == 0


def test_one_spark_moved_by_a_cycle_fails(host_log):
    lines = host_log.splitlines()
    log = chipdiff.parse_log(host_log)
    k_spark = chipdiff.chip_edges(log, log.end)[14][10][0]  # an IGT edge mid-run
    i = next(j for j, ln in enumerate(lines) if ln.startswith(f"{k_spark:x} "))
    lines[i] = f"{k_spark + 1:x} {lines[i].split()[1]}"  # the chip shows it one cycle later
    if i + 1 < len(lines) and lines[i + 1].startswith(f"{k_spark + 1:x} "):
        pytest.skip("another pin changes in the next cycle")
    offset, res = chipdiff.analyse(chipdiff.parse_log("\n".join(lines)), offset=0)
    igt = next(r for r in res if r.pin.name == "P11")
    assert not igt.ok and igt.first_bad[0] == k_spark + 1
    assert "FAIL" in chipdiff.report(offset, res)


def test_closed_loop_of_the_emulator_as_chip_is_exact(host_log):
    """With on-time reactions the chip's run equals the emulator running closed loop through the schedule."""
    log = chipdiff.parse_log(host_log)
    for name, (nc, ne, lat) in chipdiff.closed_loop(log).items():
        assert nc == ne and set(lat) <= {0}, name
