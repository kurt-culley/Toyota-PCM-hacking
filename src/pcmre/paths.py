"""Every repository path the tooling uses, in one place.

The layout:

- ``roms/<name>/``: one folder per ROM. The dump, its definition files (``defs.yaml``,
  ``symbols.yaml``) and the files generated from them (source, cross-reference, maps).
- ``data/``: measured and transcribed data (sensor curves, bench captures).
- ``reference/``: data books and articles (PDF).
- ``docs/``: the documentation; generators write some pages and pictures there.
- ``hardware/``: firmware and the C emulator core.
- ``tools/``: setup scripts and vendored legacy tools; ``.tools/`` holds their builds (git-ignored).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ROMS = ROOT / "roms"
DATA = ROOT / "data"
DOCS = ROOT / "docs"
HARDWARE = ROOT / "hardware"
REFERENCE = ROOT / "reference"
TOOLS = ROOT / ".tools"


def rom_dir(name: str) -> Path:
    """The folder of one ROM: ``roms/<name>/``."""
    return ROMS / name


# ROM dumps and the IDA listing of the AE86 reference ROM
ROM_17140 = ROMS / "mr2_17140/89661-17140.bin"
ROM_BLUETOP = ROMS / "bluetop/cap.bin"
LISTING_BLUETOP = ROMS / "bluetop/cap.asm"
ROM_BLUETOP_2860 = ROMS / "bluetop_2860/cap2-151801-2860.bin"

# data
SENSORS = DATA / "sensors"
CAPTURES = DATA / "captures"

# reference documents
ROSS_PDF = REFERENCE / "ross_lifting_the_lid_mk1_mr2_ecu.pdf"

# assemblers and references built by tools/setup_*.sh
ASL = TOOLS / "asl/asl"
P2BIN = TOOLS / "asl/p2bin"
DASM = TOOLS / "dasm/dasm"
MAME_REF = TOOLS / "mame-ref/hd6301ref"
DASM_SUITE_6303 = ROOT / "tools/vendor/dasm/test/suite6303.bin.ref"

# firmware and the C emulator
EMU_CORE = HARDWARE / "ecu-emu/core"
LOOPBACK = HARDWARE / "ecu-emu/loopback"
CHIPDIFF = HARDWARE / "ecu-emu/chipdiff"
CAR = HARDWARE / "ecu-emu/car"
READER = HARDWARE / "rp2350-reader"
PEEK_LOGGER = HARDWARE / "peek-logger/firmware"

# generated documentation pages and pictures
DOC_IGNITION_TABLE_AE86 = DOCS / "bluetop/ignition_table.md"
DOC_IGNITION_MAPS_17140 = DOCS / "mr2/ignition_maps.md"
DOC_READER_GUIDE = DOCS / "hardware/rp2350_reader_guide.md"
DOC_CHIP_TEST = DOCS / "hardware/chip_diff_test.md"
DOC_CAR_RIG = DOCS / "mr2/cpu_replacement.md"
PICS_READER = DOCS / "hardware/photos/rp2350_reader"
PICS_CHIP_TEST = DOCS / "hardware/photos/chip_diff_test"
PICS_CAR_RIG = DOCS / "hardware/photos/car_rig"
ROSS_FIGURES = DOCS / "ross/figures"
