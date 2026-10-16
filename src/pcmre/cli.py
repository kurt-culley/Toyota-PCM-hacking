"""The ``pcmre`` command: one entry point for every tool.

    uv run pcmre                     # list the commands
    uv run pcmre <command> --help    # help for one command

Each command runs the module's own command line, so ``uv run pcmre xref --write`` is the
same as ``uv run python -m pcmre.xref --write``.
"""

from __future__ import annotations

import runpy
import sys

COMMANDS: dict[str, tuple[str, str]] = {
    # disassembly and generated source
    "roundtrip": ("pcmre.roundtrip", "AE86 ROM: generated source reassembles to the same bytes"),
    "xref": ("pcmre.xref", "cross-reference and call graph of a ROM"),
    "symlisting": ("pcmre.symlisting", "MR2 ROM: labelled source and cross-reference from symbols.yaml"),
    "ingest": ("pcmre.ingest", "first report on a new ROM dump"),
    "crossver": ("pcmre.crossver", "AE86 ROM: compare two software versions and port the maps"),
    # maps
    "defs": ("pcmre.defs", "map pages, CSV files and TunerPro XDF from roms/<name>/defs.yaml"),
    "readable": ("pcmre.readable", "AE86 ignition table in degrees"),
    "readable17140": ("pcmre.readable17140", "MR2 ignition maps in degrees"),
    "checksum": ("pcmre.checksum", "check or correct the ROM word sum"),
    # hardware support
    "romdump": ("pcmre.romdump", "assemble the ROM-reader programs into the firmware header"),
    "romcapture": ("pcmre.romcapture", "capture a ROM from the reader over USB"),
    "peeklog": ("pcmre.peeklog", "decode a serial-link log into physical units"),
    "wiring": ("pcmre.wiring", "ROM-reader wiring tables and pictures"),
    "chipdiff-wiring": ("pcmre.chipdiff_wiring", "chip-test breadboard layout"),
    "car-rig": ("pcmre.car_rig_diagram", "in-car rig wiring table and pictures"),
    "gen-hd6301-c": ("pcmre.gen_hd6301_c", "generate the C emulator's opcode and timing tables"),
    # emulator
    "chipdiff": ("pcmre.emu.chipdiff", "capture and compare the chip test against the emulator"),
    "loopback-ref": ("pcmre.emu.loopback_ref", "reference checksums for the loopback firmware"),
    # reference data
    "digitise": ("pcmre.ross.digitise", "digitise the figures of the Ross articles"),
}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] in ("-h", "--help") or args[0] not in COMMANDS:
        width = max(map(len, COMMANDS))
        print("usage: pcmre <command> [options]\n\ncommands:")
        for name, (_, about) in COMMANDS.items():
            print(f"  {name:<{width}}  {about}")
        return 0 if not args or args[0] in ("-h", "--help") else 2
    module, _ = COMMANDS[args[0]]
    sys.argv = [f"pcmre {args[0]}", *args[1:]]
    try:
        runpy.run_module(module, run_name="__main__", alter_sys=True)
    except SystemExit as e:
        return int(e.code or 0) if not isinstance(e.code, str) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
