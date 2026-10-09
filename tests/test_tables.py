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


IGN_MAP = 0xFF40  # Bluetop base ignition map (ldx #$FF40 at $F880)
LOOKUP_3D, AFTER_3D = 0xF86C, 0xF89F  # lookup3dTable .. ldab TVIScounter
RPMISH, LOAD = 0x64, 0x7F


def test_ram_names_for_3d_axes():
    L = parse(T["listing"], ROM)
    assert L.ram_labels[RPMISH] == "RPMish"
    assert L.ram_labels[LOAD] == "Load"


def test_3d_ignition_lookup_matches_emulator():
    from emu.harness import run
    from pcmre.tables import lookup_3d

    table = table_at(IGN_MAP, 6 * 14 + 16)  # the last column reads one byte past its row, as the ROM does
    rng = random.Random(3)
    cases = [(r, ld) for r in range(0, 256, 5) for ld in (0, 0x1FF, 0x200, 0x2FF, 0x500, 0x7FF, 0xBFF, 0xC00, 0xFFFF)]
    cases += [(rng.randrange(256), rng.randrange(0x10000)) for _ in range(800)]
    for rpmish, load in cases:
        if rpmish > 208:  # the ROM bounds RPMish to <= 208 (14 columns); beyond it reads the next row
            continue
        r = run(ROM, LOOKUP_3D, AFTER_3D, ram={RPMISH: rpmish, LOAD: load >> 8, LOAD + 1: load & 0xFF})
        assert r.a == lookup_3d(table, 14, rpmish, load), (rpmish, hex(load))
