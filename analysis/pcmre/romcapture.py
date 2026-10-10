"""Capture a ROM from the RP2350 reader over USB serial and check it (P3).

    PYTHONPATH=analysis uv run --with pyserial python -m pcmre.romcapture /dev/ttyACM0
    PYTHONPATH=analysis uv run python -m pcmre.romcapture --from-log console.txt

The reader prints the ROM as Intel HEX between the `dump` command and `DONE OK`. This
tool sends `dump` (or reads a saved console log), parses the HEX, and writes
``AW11 MR2 PCM/89661-17140.bin`` plus a ``.sha256`` file. It reports the SHA-256, the
16-bit word sum (the Bluetop convention is $AA55, balanced at $FFEE) and the vectors.
An existing file is never overwritten with different bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from .checksum import rom_sum
from .roundtrip import ROOT

OUT = ROOT / "AW11 MR2 PCM/89661-17140.bin"
VECTORS = ["TRAP (balance)", "SCI", "TOF", "OCF", "ICF", "IRQ1", "SWI", "NMI", "RES"]  # from $FFEE


def parse_intel_hex(lines: list[str]) -> tuple[int, bytes]:
    """Return (start address, data) from type-00 records; checks every record checksum."""
    data: dict[int, int] = {}
    for ln in lines:
        ln = ln.strip()
        if not ln.startswith(":"):
            continue
        rec = bytes.fromhex(ln[1:])
        if sum(rec) & 0xFF:
            raise ValueError(f"bad checksum: {ln}")
        n, addr, kind = rec[0], rec[1] << 8 | rec[2], rec[3]
        if len(rec) != n + 5:
            raise ValueError(f"bad length: {ln}")
        if kind == 1:
            break
        if kind == 0:
            for i, b in enumerate(rec[4 : 4 + n]):
                data[addr + i] = b
    if not data:
        raise ValueError("no data records")
    lo, hi = min(data), max(data)
    if len(data) != hi - lo + 1:
        raise ValueError("gaps in the HEX data")
    return lo, bytes(data[a] for a in range(lo, hi + 1))


def console_section(text: str) -> list[str]:
    """The lines of the last `dump` result; raise unless it ended DONE OK."""
    lines = text.splitlines()
    end = max((i for i, ln in enumerate(lines) if ln.startswith("DONE")), default=None)
    if end is None:
        raise ValueError("no DONE line: the dump did not finish")
    if not lines[end].startswith("DONE OK"):
        raise ValueError(f"reader reported: {lines[end]}")
    start = max((i for i in range(end) if lines[i].startswith("run 1:")), default=0)
    return lines[start:end]


def report(start: int, rom: bytes) -> str:
    out = [f"${start:04X}-${start + len(rom) - 1:04X}, {len(rom)} bytes"]
    out.append(f"SHA-256 {hashlib.sha256(rom).hexdigest()}")
    if start == 0xF000 and len(rom) == 0x1000:
        s = rom_sum(rom)
        out.append(f"word sum ${s:04X} ({'matches' if s == 0xAA55 else 'differs from'} the Bluetop $AA55 convention)")
    for k, name in enumerate(VECTORS):
        a = 0xFFEE + 2 * k
        if start <= a < start + len(rom) - 1:
            off = a - start
            out.append(f"  ${a:04X} {name:12s} ${rom[off] << 8 | rom[off + 1]:04X}")
    return "\n".join(out)


def check_dump_image(start: int, rom: bytes) -> None:
    """Only a `dump` result ($F000-$FFFF) is saved as the ROM; a `size` run is not."""
    if (start, len(rom)) != (0xF000, 0x1000):
        raise SystemExit(f"image is ${start:04X}, {len(rom)} bytes, not a $F000-$FFFF dump (a `size` run?): not saved")


def save(rom: bytes, path: Path) -> None:
    if path.exists() and path.read_bytes() != rom:
        raise SystemExit(f"{path} already exists with different bytes: not overwriting. Compare the two dumps.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(rom)
    path.with_suffix(".bin.sha256").write_text(f"{hashlib.sha256(rom).hexdigest()}  {path.name}\n")


def capture_serial(port: str, timeout_s: float = 30.0) -> str:
    import serial  # pyserial, only needed for a live capture

    with serial.Serial(port, 115200, timeout=timeout_s) as s:
        s.reset_input_buffer()
        s.write(b"dump\r")
        buf = []
        while True:
            ln = s.readline().decode("ascii", "replace")
            if not ln:
                raise SystemExit("timed out waiting for the reader")
            buf.append(ln.rstrip("\r\n"))
            if not buf[-1].startswith(":"):
                print(buf[-1])
            if buf[-1].startswith("DONE"):
                return "\n".join(buf)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("port", nargs="?", help="serial port of the reader, e.g. /dev/ttyACM0 or COM5")
    ap.add_argument("--from-log", type=Path, help="parse a saved console log instead")
    ap.add_argument("-o", "--out", type=Path, default=OUT)
    a = ap.parse_args()
    if not (a.port or a.from_log):
        ap.error("give a serial port or --from-log")
    text = a.from_log.read_text() if a.from_log else capture_serial(a.port)
    start, rom = parse_intel_hex(console_section(text))
    print(report(start, rom))
    check_dump_image(start, rom)
    save(rom, a.out)
    print(f"saved {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
