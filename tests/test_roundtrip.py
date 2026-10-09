"""P0 gate: the Bluetop ROM regenerates to byte-identical source (see docs/RE_PLAN.md)."""

import hashlib

import pytest

from pcmre.emit import emit
from pcmre.idalisting import ListingMismatch, parse
from pcmre.roundtrip import ASL, DASM, ROOT, TARGETS, assemble_asl, assemble_dasm

BLUETOP = TARGETS["bluetop"]
CAP_SHA256 = "62b2a3f29039ddddc90eff2ce847e0b1c3af15dea4999408f74a48eed7c087f2"


@pytest.fixture(scope="module")
def rom():
    data = BLUETOP["rom"].read_bytes()
    assert hashlib.sha256(data).hexdigest() == CAP_SHA256, "original dump changed - never modify dumps"
    return data


@pytest.fixture(scope="module")
def listing(rom):
    return parse(BLUETOP["listing"], rom)


def test_listing_import(listing):
    assert listing.org == 0xF000
    assert sum(it.size for it in listing.items) == 0x1000
    assert listing.ram_labels[0x11] == "TxRxCntStat"
    assert listing.ram_labels[0x57] == "ADC_ThW"
    assert listing.labels[0xF000] == ["reset"]
    kinds = {k: sum(1 for it in listing.items if it.kind == k) for k in ("code", "byte", "word")}
    assert kinds == {"code": 1980, "byte": 312, "word": 19}


def test_listing_mismatch_is_detected(rom):
    corrupt = bytearray(rom)
    corrupt[0] = 0x01  # 'sei' at reset becomes 'nop'
    with pytest.raises(ListingMismatch):
        parse(BLUETOP["listing"], bytes(corrupt))


def test_committed_source_is_current(listing, rom):
    assert BLUETOP["out"].read_text() == emit(listing, rom, BLUETOP["title"], "asl"), (
        "analysis/bluetop/cap.s is stale: run `uv run python -m pcmre.roundtrip --write`"
    )


@pytest.mark.skipif(not ASL.exists(), reason="run tools/setup_assemblers.sh first")
def test_asl_roundtrip_identical(listing, rom):
    src = emit(listing, rom, BLUETOP["title"], "asl")
    assert assemble_asl(src, 0xF000, 0xFFFF) == rom


@pytest.mark.skipif(not DASM.exists(), reason="run tools/setup_assemblers.sh first")
def test_dasm_crosscheck_identical(listing, rom):
    src = emit(listing, rom, BLUETOP["title"], "dasm")
    assert assemble_dasm(src, 0xF000, 0xFFFF) == rom


def test_output_is_ascii(listing, rom):
    emit(listing, rom, "", "asl").encode("ascii")
    assert ROOT.joinpath("analysis/bluetop/cap.s").read_bytes().isascii()
