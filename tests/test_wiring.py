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


def test_breadboard_layout():
    from pcmre.wiring import DIP, PICO_PIN, breadboard, breadboard_table, chip_hole, is_rail, pico_hole

    assert breadboard_table() in GUIDE, "breadboard table stale: rerun python -m pcmre.wiring"
    wires, parts = breadboard()
    sig = board_pins("pico2w")
    holes = [h for _, a, b, _ in wires for h in (a, b) if not is_rail(h)]
    holes += [h for _, a, b in parts for h in (a, b) if not is_rail(h)]
    assert len(holes) == len(set(holes)), "a hole is used twice"
    occupied = {f"{c}{r}" for pin in DIP for c, r in [chip_hole(pin)]} | {
        f"{c}{r}" for p in range(1, 41) for c, r in [pico_hole(p)]
    }
    assert not set(holes) & occupied, "a wire lands in a hole under a part"

    def same_strip(hole: str, part_hole: tuple[str, int]) -> bool:
        col, row = part_hole
        half = "abcde" if col in "abcde" else "fghij"
        return hole[0] in half and int(hole[1:]) == row

    signal = {w[3].split(" ")[0]: w for w in wires if not is_rail(w[2])}
    assert len(signal) == 22
    for name, (_, chip, pico, _) in signal.items():
        pin = next(p for p, n in DIP.items() if n == name)
        assert same_strip(chip, chip_hole(pin))
        assert same_strip(pico, pico_hole(PICO_PIN[f"GP{sig[name]}"]))
    rails = {w[0]: w for w in wires}
    assert same_strip(rails["5V"][1], pico_hole(40)) and rails["5V"][2].startswith("j+")  # VBUS
    assert same_strip(rails["G1"][1], pico_hole(3)) and same_strip(rails["G2"][1], pico_hole(38))  # GND pins
    assert same_strip(rails["Vcc"][1], chip_hole(21)) and same_strip(rails["Vss"][1], chip_hole(1))
