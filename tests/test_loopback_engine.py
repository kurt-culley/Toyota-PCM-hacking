"""The loopback's C engine model (hardware/ecu-emu/loopback/engine.h) against the simulator.

engine.h is what the RP2350 loopback firmware runs in real time. Here it runs on the host with
the C emulator, as fast as it goes, through the same 6-phase schedule; every phase must
reproduce the simulator's checksums in expected.h (output edges, RAM, injector pulses) bit for
bit. Plus a staleness check: expected.h must be what emu.loopback_ref generates now.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from emu.engine17140 import ROM_17140
from emu.loopback_ref import OUT, header, run
from pcmre.roundtrip import ROOT

CC = shutil.which("cc") or shutil.which("gcc")
pytestmark = pytest.mark.skipif(CC is None, reason="no host C compiler")
CORE = ROOT / "hardware/ecu-emu/core"
LOOP = ROOT / "hardware/ecu-emu/loopback"

HOST = r"""
#include <stdio.h>
#include "board.h"
#include "expected.h"
#include "engine.h"
int main(int argc, char **argv) {
    static unsigned char rom[4096];
    FILE *f = fopen(argv[1], "rb");
    if (argc < 2 || !f || fread(rom, 1, 4096, f) != 4096) return 2;
    fclose(f);
    static board_t b;
    static eng_t e;
    eng_attach(&e, &b);
    board_init(&b, rom, 4096);
    eng_set_switches(&e);
    int64_t boundary = REF_PHASE_US;
    int fails = 0;
    for (int phase = 0; phase < REF_PHASES;) {
        eng_crank_fill(&e, b.io.now + 2000);
        board_step(&b);
        if (b.io.now >= boundary) {
            eng_result_t r;
            eng_phase_end(&e, &r);
            int ok = eng_result_ok(&r, &REF[phase]);
            printf("phase %d %s\n", phase + 1, ok ? "PASS" : "FAIL");
            fails += !ok;
            phase++;
            boundary += REF_PHASE_US;
        }
    }
    return fails;
}
"""


def test_expected_header_is_current():
    assert OUT.read_text() == header(run()), "stale: rerun python -m emu.loopback_ref --write"


def test_engine_model_reproduces_the_simulator_bit_for_bit(tmp_path):
    (tmp_path / "host.c").write_text(HOST)
    exe = tmp_path / "host"
    subprocess.run([CC, "-O2", "-Wall", "-Wextra", "-Werror", f"-I{CORE}", f"-I{LOOP}", "-o", str(exe),
                    str(tmp_path / "host.c"), *(str(CORE / s) for s in ("hd6301.c", "d151801.c", "board.c")),
                    "-lm"], check=True)  # fmt: skip
    p = subprocess.run([str(exe), str(ROM_17140)], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout
    assert p.stdout.count("PASS") == 6
