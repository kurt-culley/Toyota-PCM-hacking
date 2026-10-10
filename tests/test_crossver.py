"""Cross-version analysis: Bluetop 0642 (cap.bin) against 2860 (cap2), and the ported 2860 definitions."""

from __future__ import annotations

from functools import cache

import yaml

from pcmre import crossver as cv
from pcmre.defs import ROOT, generate, load
from pcmre.idalisting import parse


@cache
def analysis():
    rom_a, rom_b = cv.ROM_A.read_bytes(), cv.ROM_B.read_bytes()
    xa, xb = cv.trace(rom_a, parse(cv.LISTING_A, rom_a)), cv.trace(rom_b)
    al = cv.align(xa, xb)
    ports = cv.port_maps(yaml.safe_load(cv.DEFS_A.read_text()), xa, xb, al)
    return rom_a, rom_b, xa, xb, al, ports


def test_every_map_ports_and_is_identical():
    rom_a, rom_b, *_, ports = analysis()
    assert ports and all(p.status == "CONFIRMED" for p in ports), [(p.id, p.status) for p in ports]
    for p in ports:
        a = rom_a[p.addr_a - cv.ORG : p.addr_a - cv.ORG + p.size]
        b = rom_b[p.addr_b - cv.ORG : p.addr_b - cv.ORG + p.size]
        assert a == b, p.id
    assert {p.id: p.addr_b for p in ports}["ign_base"] == 0xFF5A


def test_ram_remap():
    *_, al, _ = analysis()
    assert al.ram == {0x96: 0x9D, 0x97: 0x96, 0x98: 0x97, 0x99: 0x98, 0x9A: 0x99, 0x9B: 0x9A, 0x9C: 0x9B, 0x9D: 0x9C}


def test_code_differences_are_classified():
    _, _, xa, xb, al, _ = analysis()
    g = cv.classify(xa, xb, al)
    assert (len(g["behaviour"]), len(g["moved"]), len(g["relocated"])) == (17, 1, 18)
    # the A/C idle advance now depends on coolant >= 218 F (ADC_ThW $57 vs $DA)
    added = [bb for tag, aa, bb in g["behaviour"] if tag == "insert"]
    assert any(xb.instrs[b].mnemonic == "cmpb" and xb.instrs[b].operand == 0xDA for bb in added for b in bb)


def test_every_data_difference_is_explained():
    _, _, xa, xb, al, ports = analysis()
    hows = {how for *_, how in cv.data_diffs(xa, xb, al, ports)}
    assert hows <= {"code pointer, follows its target", "checksum balance word (`$FFEE`)"}, hows


def test_ram_init_differences():
    _, _, xa, xb, al, _ = analysis()
    ia, ib = cv.ram_init_table(xa)[2], cv.ram_init_table(xb)[2]
    inv = {v: k for k, v in al.ram.items()}
    b_in_a = {inv.get(r, r): v for r, v in ib.items()}
    assert {r for r in set(ia) | set(b_in_a) if ia.get(r) != b_in_a.get(r)} == {0x4C, 0x54}


def test_generated_outputs_are_current():
    text, ports = cv.run()
    hint = (
        "run: PYTHONPATH=analysis uv run python -m pcmre.crossver --write && python -m pcmre.defs bluetop_2860 --write"
    )
    assert cv.REPORT.read_text() == text, hint
    *_, al, _ = analysis()
    spec_text = cv.ported_defs(yaml.safe_load(cv.DEFS_A.read_text()), ports, al, cv.ROM_B.read_bytes())
    assert cv.DEFS_B.read_text() == spec_text, hint
    spec, rom = load("bluetop_2860")
    gen = generate(spec, rom)
    base = ROOT / "analysis/bluetop_2860"
    assert (base / "maps.md").read_text() == gen.markdown, hint
    assert (base / "bluetop_2860.xdf").read_text() == gen.xdf, hint
    for mid, csv in gen.csvs.items():
        assert (base / "maps" / f"{mid}.csv").read_text() == csv, mid
