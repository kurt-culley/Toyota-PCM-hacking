"""Overlay an asl patch source onto a ROM image (prototype patches for the simulator).

    from pcmre.patch import build
    p = build(Path("analysis/patches/bluetop_sparkcut.asm"), cap_bin)
    p.rom      # the 4 KB ROM with the hooks applied and its $AA55 checksum re-balanced
    p.extra    # {address: bytes} for code outside the ROM (external memory on P7)

The source is assembled once and converted twice with different filler bytes; a byte
that is the same in both images was defined by the source. Bytes in the ROM's own range
overlay the ROM, everything else is returned as external blocks.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .checksum import fix_checksum
from .roundtrip import ASL, P2BIN


@dataclass
class Patched:
    rom: bytes
    extra: dict[int, bytes] = field(default_factory=dict)
    changed: list[int] = field(default_factory=list)  # ROM addresses the hooks changed


def _image(obj: Path, out: Path, fill: int) -> bytes:
    r = subprocess.run(
        [str(P2BIN), "-q", "-r", "$0000-$FFFF", "-l", f"${fill:02X}", str(obj), str(out)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"p2bin failed:\n{r.stdout}\n{r.stderr}")
    return out.read_bytes()


def build(source: Path, rom: bytes, rom_base: int = 0xF000, fix: bool = True) -> Patched:
    with tempfile.TemporaryDirectory() as td:
        src, obj = Path(td, "p.asm"), Path(td, "p.p")
        src.write_text(source.read_text())
        r = subprocess.run([str(ASL), "-q", "-U", "-o", str(obj), str(src)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"asl failed:\n{r.stdout}\n{r.stderr}")
        a, b = _image(obj, Path(td, "a.bin"), 0x00), _image(obj, Path(td, "b.bin"), 0xFF)
    defined = [i for i in range(0x10000) if a[i] == b[i]]
    out = bytearray(rom)
    changed, extra, run_start, run = [], {}, None, bytearray()
    for addr in defined:
        if rom_base <= addr < rom_base + len(rom):
            if out[addr - rom_base] != a[addr]:
                changed.append(addr)
            out[addr - rom_base] = a[addr]
            continue
        if run_start is not None and addr == run_start + len(run):
            run.append(a[addr])
        else:
            if run_start is not None:
                extra[run_start] = bytes(run)
            run_start, run = addr, bytearray([a[addr]])
    if run_start is not None:
        extra[run_start] = bytes(run)
    rom_out = fix_checksum(bytes(out)) if fix else bytes(out)
    return Patched(rom_out, extra, changed)
