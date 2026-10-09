"""P2: the routine-call harness runs Bluetop helpers exactly as the ROM calls them."""

import random

import pytest

from emu.harness import RoutineTimeout, call
from pcmre.roundtrip import TARGETS

ROM = TARGETS["bluetop"]["rom"].read_bytes()
DIV_D_BY_16 = 0xFC7D
BOUND_DATA = 0xFB46
MUL_D_BY_STACK = 0xF6E9


@pytest.mark.parametrize("d", [0x0000, 0x0123, 0xFFFF, 0x8000, 0x1234])
def test_div_d_by_16(d):
    r = call(ROM, DIV_D_BY_16, a=d >> 8, b=d & 0xFF)
    assert r.d == d >> 4


def test_bound_data_inline_limits():
    # jsr boundData / db upper, lower  -> clamp A to [lower, upper]; carry set when clipped.
    upper, lower = 0xA0, 0x14
    for a in range(256):
        r = call(ROM, BOUND_DATA, a=a, inline=bytes([upper, lower]))
        assert r.a == min(max(a, lower), upper), a
        assert r.carry == (a > upper or a < lower), a


def test_mul_d_by_stack_returns_top_16_bits():
    rng = random.Random(6301)
    for _ in range(300):
        d, m = rng.randrange(0x10000), rng.randrange(0x100)
        r = call(ROM, MUL_D_BY_STACK, a=d >> 8, b=d & 0xFF, stack=bytes([m]))
        assert r.d == (d * m) >> 8, (hex(d), hex(m))
        assert r.s == 0x00FF  # the stacked argument was removed by the routine


def test_runaway_routine_times_out():
    with pytest.raises(RoutineTimeout):
        call(ROM, 0xF064, max_steps=500)  # Main_Loop never returns
