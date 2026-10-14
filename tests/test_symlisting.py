"""P4: the 17140 labelled source reassembles to the dumped ROM, and the committed outputs are current."""

from __future__ import annotations

import pytest

from pcmre import xref
from pcmre.emit import emit_asl
from pcmre.roundtrip import ASL, ROOT, assemble_asl
from pcmre.symlisting import build, load

pytestmark = pytest.mark.skipif(not ASL.exists(), reason="asl not built (tools/setup_assemblers.sh)")


def test_17140_source_round_trips_and_is_current():
    spec, rom = load("mr2_17140")
    listing, x = build(spec, rom)
    src = emit_asl(listing, rom, spec["title"]).replace(
        "; Labels and comments imported from the IDA 4.9 listing; bytes from the ROM.",
        "; Names and notes from analysis/mr2_17140/symbols.yaml; bytes from the ROM.",
    )
    assert assemble_asl(src, listing.org, 0xFFFF) == rom
    out = ROOT / "analysis/mr2_17140"
    assert (out / "mr2_17140.asm").read_text() == src, "stale: rerun python -m pcmre.symlisting mr2_17140 --write"
    assert (out / "xref.md").read_text() == xref.render(x, listing, spec["title"])


def test_17140_vectors_and_mode_check():
    _, rom = load("mr2_17140")
    word = lambda a: rom[a - 0xF000] << 8 | rom[a - 0xF000 + 1]  # noqa: E731
    assert word(0xFFFE) == 0xF2BE and word(0xFFF4) == 0xFE36 and word(0xFFF6) == 0xFEB4
    # Reset accepts mode 7 ($E0) or mode 2 ($40): LDAB $03 / ANDB #$E0 / CMPB #$E0 / BEQ / CMPB #$40 / BNE *
    assert rom[0x2BE:0x2CA] == bytes.fromhex("D603C4E0C1E02704C14026FE")


def test_17140_no_label_or_note_falls_inside_an_instruction():
    from pcmre.symlisting import dropped_labels

    spec, rom = load("mr2_17140")
    listing, _ = build(spec, rom)
    assert dropped_labels(spec, listing) == []
