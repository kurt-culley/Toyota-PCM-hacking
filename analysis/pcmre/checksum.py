"""Bluetop ROM checksum: the 16-bit sum of the big-endian words $F000-$FFFF must be $AA55.

The ROM checks this in its diagnostic path [ROM:$FE50 ChkSumLoop / subd #$AA55]. A
mismatch flags a fault instead of running the RAM test. The TRAP vector at $FFEE is never
used by the code, so Denso set it to whatever word balances the sum (cap.asm: "illegal
opcode trap vector is used to force ROM checksum to equal AA55"). An edited ROM must be
re-balanced the same way before it goes back in a car:

    PYTHONPATH=analysis uv run python -m pcmre.checksum edited.bin --fix
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TARGET = 0xAA55
BALANCE_ADDR = 0xFFEE  # TRAP vector word
BASE = 0xF000


def rom_sum(rom: bytes) -> int:
    if len(rom) % 2:
        raise ValueError("ROM length must be even")
    return sum(int.from_bytes(rom[i : i + 2], "big") for i in range(0, len(rom), 2)) & 0xFFFF


def fix_checksum(rom: bytes, *, base: int = BASE, slot: int = BALANCE_ADDR, target: int = TARGET) -> bytes:
    """Return ``rom`` with the word at ``slot`` changed so that ``rom_sum`` equals ``target``."""
    out = bytearray(rom)
    off = slot - base
    old = int.from_bytes(out[off : off + 2], "big")
    new = (old + target - rom_sum(rom)) & 0xFFFF
    out[off : off + 2] = new.to_bytes(2, "big")
    return bytes(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom", type=Path)
    ap.add_argument("--fix", action="store_true", help="rewrite the file with a balanced $FFEE word")
    a = ap.parse_args()
    rom = a.rom.read_bytes()
    print(f"sum ${rom_sum(rom):04X} (want ${TARGET:04X})")
    if a.fix and rom_sum(rom) != TARGET:
        a.rom.write_bytes(fix_checksum(rom))
        print(f"fixed: ${BALANCE_ADDR:04X} rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
