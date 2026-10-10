"""P2: arithmetic in the Bluetop fuel chain, proven in the emulator (docs/bluetop/fuel_chain.md)."""

import random

from emu.harness import call
from pcmre.roundtrip import TARGETS

ROM = TARGETS["bluetop"]["rom"].read_bytes()
CALC72 = 0xF6FC
THACORR, WORD_72 = 0x8A, 0x72


def calc72_model(x: int, t: int) -> int:
    """Calc72: word_72 = x; m = (2x * ThAcorr) >> 8; result = ((m + x) >> 1 + x) >> 1 (16-bit)."""
    m = (((x << 1) & 0xFFFF) * t) >> 8
    s = ((m + x) & 0xFFFF) >> 1
    return ((s + x) & 0xFFFF) >> 1


def test_calc72_matches_emulator():
    rng = random.Random(72)
    for _ in range(600):
        x, t = rng.randrange(0x8000), rng.randrange(256)
        r = call(ROM, CALC72, a=x >> 8, b=x & 0xFF, ram={THACORR: t})
        assert r.d == calc72_model(x, t), (hex(x), t)
        assert r.ram(WORD_72, 2) == x  # Calc72 stores its input in word_72


def test_calc72_is_a_blend_not_a_pure_multiply():
    # ThAcorr = 128 (x1.0) leaves the value unchanged; the ThA term carries only a quarter of the weight.
    assert calc72_model(0x0800, 128) == 0x0800
    assert calc72_model(0x0800, 255) < 0x0800 * 1.26  # full-scale ThAcorr adds at most ~25 %
