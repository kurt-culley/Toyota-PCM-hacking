"""P3: the firmware's C decode rule (decode.h) matches the Python reference model.

Both run the same random event streams (reset assert/release, read and write cycles
biased towards the interesting addresses); every drive/listen decision must agree.
"""

from __future__ import annotations

import random
import shutil
import subprocess

import pytest

from pcmre.readerdecode import ReaderDecode
from pcmre.romdump import assemble
from pcmre.roundtrip import ASL, ROOT

CC = shutil.which("cc") or shutil.which("gcc")
pytestmark = [
    pytest.mark.skipif(CC is None, reason="no host C compiler"),
    pytest.mark.skipif(not ASL.exists(), reason="asl not built (tools/setup_assemblers.sh)"),
]
SRC = ROOT / "hardware/rp2350-reader/firmware/src"

HARNESS = r"""
#include <stdio.h>
#include "decode.h"
int main(void) {
    static uint8_t page[256];
    for (int i = 0; i < 256; i++) page[i] = (uint8_t)getchar();
    decode_t d;
    decode_init(&d, page, 0xC0C0);
    char op; unsigned a;
    while (scanf(" %c %x", &op, &a) == 2) {
        if (op == 'A') decode_assert_reset(&d);
        else if (op == 'L') decode_release_reset(&d);
        else printf("%d\n", decode_cycle(&d, (uint16_t)a, op == 'R'));
    }
    return 0;
}
"""

HOT = [0xFFFE, 0xFFFF, 0xC0C0, 0xC000, 0xC0FF, 0x0003, 0x0011, 0xF000, 0xE000, 0xBFFF, 0xC100]


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    d = tmp_path_factory.mktemp("dec")
    (d / "h.c").write_text(HARNESS)
    exe = d / "h"
    subprocess.run([CC, "-std=c11", "-Wall", "-Werror", "-I", str(SRC), "-o", str(exe), str(d / "h.c")], check=True)
    return exe


def events(seed: int, n: int = 3000):
    rng = random.Random(seed)
    out = [("L", 0)]
    for _ in range(n):
        r = rng.random()
        if r < 0.01:
            out.append(("A", 0))
        elif r < 0.03:
            out.append(("L", 0))
        else:
            a = rng.choice(HOT) if rng.random() < 0.7 else rng.randrange(0x10000)
            out.append(("R" if rng.random() < 0.85 else "W", a))
    return out


@pytest.mark.parametrize("seed", range(5))
def test_c_matches_python(harness, seed):
    page = assemble("romdump")
    ev = events(seed)
    stdin = page + "".join(f"{op} {a:x}\n" for op, a in ev).encode()
    got = [int(x) for x in subprocess.run([str(harness)], input=stdin, capture_output=True, check=True).stdout.split()]
    model = ReaderDecode(page)
    want = []
    for op, a in ev:
        if op == "A":
            model.assert_reset()
        elif op == "L":
            model.release_reset()
        else:
            v = model.cycle(a, op == "R")
            want.append(-1 if v is None else v)
    assert got == want
    assert any(v == 0xC0 for v in want)  # the stream did exercise the vector window
