"""P3: the reader guide's wiring tables match the firmware's pins.h."""

from __future__ import annotations

from pcmre.roundtrip import ROOT
from pcmre.wiring import BOARDS, board_pins, local_table, table

GUIDE = (ROOT / "docs/hardware/rp2350_reader_guide.md").read_text()


def test_guide_tables_current():
    for b in BOARDS:
        assert table(b) in GUIDE, f"{b} table stale: rerun python -m pcmre.wiring"
    assert local_table() in GUIDE


def test_pins_avoid_board_resources():
    bb48 = set(board_pins("bb48").values())
    # BB48R: UEXT/Qwiic 0-7, PSRAM CS 8, microSD 9-11 and 24, LED 25, ADC (not 5 V tolerant) 40-47
    assert not bb48 & ({*range(0, 12), 24, 25} | set(range(40, 48)))
    pico = set(board_pins("pico2w").values())
    # Pico 2 W: 23-25 and 29 belong to the wireless chip; 26-28 are ADC pins
    assert not pico & {23, 24, 25, 26, 27, 28, 29}
    for b in BOARDS:
        assert len(set(board_pins(b).values())) == 22  # no GPIO used twice
