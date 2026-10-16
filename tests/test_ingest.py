"""Day-one ingest toolkit (pcmre.ingest): on 2860, on a synthetic larger ROM, and on hand-made code."""

from __future__ import annotations

import random
from functools import cache

import pytest

from pcmre import crossver as cv
from pcmre import ingest
from pcmre.roundtrip import ASL, ROOT

pytestmark = pytest.mark.skipif(not ASL.exists(), reason="asl not built")
B2860 = ROOT / "TOYOTA Bluetop PCM/cap2-151801-2860.bin"


@cache
def report_2860() -> str:
    return ingest.run(B2860, "test2860")[0]


def test_2860_ports_every_map_and_finds_the_known_constants():
    rep = report_2860()
    assert rep.count("| CONFIRMED |") == 19
    for want in ("= 7400 rpm (rev-limit-like)", "= 3950 rpm", "= 4350 rpm", "= 1500 rpm", "subd #$AA55"):
        assert want in rep, want
    assert "base `$54` — **in an SCI-transmitting routine: ADC result array**" in rep


def test_ported_defs_for_a_new_rom_load_and_generate():
    import yaml

    from pcmre.defs import generate

    _, ported = ingest.run(B2860, "test2860")
    spec = yaml.safe_load(ported)
    assert spec["rom"] == "test2860" and len(spec["maps"]) == 19
    gen = generate(spec, B2860.read_bytes())
    assert "ign_base" in gen.csvs


def planted_rom(noise: int = 0, layout_map_major: bool = True) -> tuple[bytes, int]:
    """8 KB image: $E000-$EFFF padding with Ross's table planted at $E200, then the Bluetop ROM."""
    t = ingest.ross_ignition()
    flat = [t[r][c] for c in range(8) for r in range(17)] if layout_map_major else [v for row in t for v in row]
    rng = random.Random(1)
    flat = [max(0, min(255, v + rng.randint(-noise, noise))) for v in flat]
    low = bytearray([0xFF] * 0x1000)
    low[0x200 : 0x200 + len(flat)] = bytes(flat)
    return bytes(low) + cv.ROM_A.read_bytes(), 0xE200


@pytest.mark.parametrize(("noise", "major"), [(0, True), (0, False), (4, True)])
def test_ross_ignition_table_is_found_in_a_larger_rom(tmp_path, noise, major):
    rom, at = planted_rom(noise, major)
    b = ingest.basics(rom)
    assert (b.size, b.org) == (0x2000, 0xE000)
    best = ingest.match_ignition(rom, b.org, set())[0]
    assert best.addr == at and best.mean_abs_diff <= noise
    assert best.layout == ("8 MAP rows x 17 rpm" if major else "17 rpm rows x 8 MAP")
    path = tmp_path / "fake.bin"
    path.write_bytes(rom)
    rep, _ = ingest.run(path, "fake")
    assert "`$E000`–`$FFFF`" in rep and f"| `${at:04X}` |" in rep
    assert rep.count("| CONFIRMED |") == 19  # the Bluetop code at $F000 still ports


def test_finders_on_hand_made_code():
    """ldaa $5A / suba #$80 (mixture-screw style), ldx $66 / cpx #$0D04 (rev limit at ~9000 rpm)."""
    code = bytes.fromhex("965A 8080 9760 DE66 8C0D04 2500 20FE".replace(" ", ""))
    rom = bytearray([0x01] * 0x1000)
    rom[: len(code)] = code
    for k in range(9):  # every vector -> $F000
        rom[0xFEE + 2 * k : 0xFEE + 2 * k + 2] = b"\xf0\x00"
    x = cv.trace(bytes(rom))
    assert ingest.mixture_candidates(x) == [(0xF002, 0x5A, "ldaa $5A … suba #$80")]
    rpm = ingest.rpm_constants(x, {})
    assert any("cpx #$0D04 = 9004 rpm" in s for _, s in rpm)
