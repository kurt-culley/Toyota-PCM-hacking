"""The in-car test rig's pin map (hardware/ecu-emu/car/pins.h, read by pcmre.car_rig_diagram):
against the ROM's port directions, the RP2350's 5 V rule, the chip test's pins and the doc."""

from __future__ import annotations

import re
import shutil
import subprocess

import pytest

from pcmre import car_rig_diagram as R
from pcmre import chipdiff_wiring as C
from pcmre.roundtrip import ROOT

ROM = ROOT / "AW11 MR2 PCM/89661-17140.bin"
CC = shutil.which("cc") or shutil.which("gcc")


def test_doc_table_current():
    doc = (ROOT / "docs/mr2/cpu_replacement.md").read_text()
    table = "\n".join("  " + line if line else line for line in R.table().splitlines())
    assert table in doc, "stale: rerun python -m pcmre.car_rig_diagram --table and paste it"


def test_every_used_pin_once():
    wires = R.car_wires()
    pins = [p for p, *_ in wires]
    assert len(pins) == len(set(pins)) == 26
    assert 1 in pins and 3 not in pins  # ground in, EXTAL out (the ECU's crystal)
    # the same CPU pins as the chip test, which validates the emulator on them
    assert set(pins) - {1} == {pin for pin, _ in C.gpio_pins().values()} - {3}
    assert not set(pins) & {2, 4, 5, 7, 21, 31}  # supplies and straps stay the ECU board's
    assert R.BB.PICO[R.gnd_pico_pin()] == "GND"


def test_5v_rule():
    """Everything the ECU board can drive is on GP0-22; GP26-28 carry only CPU outputs."""
    for g, (pin, name, d) in R.pins().items():
        if d != "OUT":
            assert g <= 22, f"{name} (pin {pin}) can be driven at 5 V but sits on GP{g}"
    assert {g for g, (_, _, d) in R.pins().items() if g in R.NOT_5V and d == "OUT"} == set(R.NOT_5V)


@pytest.mark.skipif(not ROM.exists(), reason="17140 ROM not present")
def test_directions_match_the_rom():
    """Each port pin's direction is what the ROM's DDR writes make it [ROM:$F2CA-$F2EB, $F371-$F380]."""
    rom = ROM.read_bytes()

    def writes(addr: int) -> list[int]:  # LDD #imm ; STD <addr  ->  the two DDR bytes written
        out = []
        for i in range(len(rom) - 4):
            if rom[i] == 0xCC and rom[i + 3] == 0xDD and rom[i + 4] == addr:
                out.append(rom[i + 1] << 8 | rom[i + 2])
        return out

    ddr = {1: [w >> 8 for w in writes(0x00)], 2: [w & 0xFF for w in writes(0x00)],
           3: [w >> 8 for w in writes(0x04)], 4: [w & 0xFF for w in writes(0x04)]}  # fmt: skip
    # (the main loop's DDR3/DDR4 write has STAA P3CSR between its LDD and STD, so only the reset one
    # matches here; it loads the same $0203)
    assert ddr == {1: [0x3E, 0x3E], 2: [0xF2, 0xFE], 3: [0x02], 4: [0x03]}
    text = R.PINS_H.read_text()
    for m in re.finditer(r"X\((\d+), (\d), (\d), (IN|OUT|IO)\)", text):
        port, bit, d = int(m[2]), int(m[3]), m[4]
        if port == 0:
            assert d == "IN"  # SC1 is the IS3 strobe input
            continue
        levels = {(v >> bit) & 1 for v in ddr[port]}
        assert d == {frozenset({1}): "OUT", frozenset({0}): "IN", frozenset({0, 1}): "IO"}[frozenset(levels)], m[0]


@pytest.mark.skipif(CC is None, reason="no C compiler")
def test_header_static_assert(tmp_path):
    """pins.h compiles, so its own 5 V check holds for the firmware too."""
    src = tmp_path / "t.c"
    src.write_text('#include "pins.h"\nint main(void) { return 0; }\n')
    subprocess.run([CC, "-std=c11", "-fsyntax-only", "-I", str(R.PINS_H.parent), str(src)], check=True)
