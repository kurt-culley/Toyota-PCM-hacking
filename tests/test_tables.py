"""P2: the Python table-lookup model equals the ROM's helper, run in the emulator."""

import random

import pytest

from emu.harness import call
from pcmre.idalisting import parse
from pcmre.roundtrip import TARGETS
from pcmre.tables import ENTRIES_1D, entries_needed, find_1d_uses, lookup_1d
from pcmre.xref import analyse

T = TARGETS["bluetop"]
ROM = T["rom"].read_bytes()
ORG = 0xF000


@pytest.fixture(scope="module")
def uses():
    return find_1d_uses(analyse(ROM, parse(T["listing"], ROM)), ROM)


def table_at(base: int, length: int = 260) -> bytes:
    off = base - ORG
    return ROM[off : off + length] + bytes(max(0, off + length - len(ROM)))


def test_entries_needed():
    assert entries_needed(0xFF1B) == 7
    assert entries_needed(0xFF25) == 9
    assert entries_needed(0xFF28) == 17
    assert entries_needed(0xFF2D) is None


def test_finds_the_rom_table_calls(uses):
    assert len(uses) >= 15
    assert {u.entry for u in uses} <= set(ENTRIES_1D)
    assert any(u.base == 0xFEB6 and u.entry == 0xFF1B for u in uses)  # ldx #$FEB6 / jsr $65,x


def test_model_matches_emulator_for_every_rom_table(uses):
    rng = random.Random(1)
    checked = 0
    for u in {(u.base, u.entry) for u in uses}:
        base, entry = u
        shift, clear_b, thw = ENTRIES_1D[entry]
        if clear_b:
            inputs = [(a, 0) for a in range(256)]
        else:
            # 16-bit input: keep the segment inside a plausible table (the callers bound it).
            a_max = min(256, 16 << shift)  # up to 16 segments
            inputs = [(rng.randrange(a_max), rng.randrange(256)) for _ in range(300)]
        for a, b in inputs:
            ram = {0x57: a} if thw else {}
            r = call(ROM, entry, a=a, b=b, x=base, ram=ram)
            assert r.a == lookup_1d(table_at(base), a, b, entry=entry), (hex(base), hex(entry), a, b)
            checked += 1
    assert checked > 3000
