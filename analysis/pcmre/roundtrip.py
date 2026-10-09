"""Round-trip gate: regenerate source from a ROM + IDA listing and prove it
reassembles to the identical bytes.

    uv run python -m pcmre.roundtrip            # Bluetop cap.bin (default)
    uv run python -m pcmre.roundtrip --write    # also refresh analysis/bluetop/cap.s

Assemblers are built by ``tools/setup_assemblers.sh`` into ``.tools/``.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

from .emit import emit
from .idalisting import parse

ROOT = Path(__file__).resolve().parents[2]
ASL = ROOT / ".tools/asl/asl"
P2BIN = ROOT / ".tools/asl/p2bin"
DASM = ROOT / ".tools/dasm/dasm"

TARGETS = {
    "bluetop": dict(
        rom=ROOT / "TOYOTA Bluetop PCM/cap.bin",
        listing=ROOT / "TOYOTA Bluetop PCM/cap.asm",
        out=ROOT / "analysis/bluetop/cap.s",
        title="AE86 Bluetop D151801-0642 (cap.bin), HD6301, $F000-$FFFF",
    ),
}


def assemble_asl(source: str, start: int, end: int) -> bytes:
    with tempfile.TemporaryDirectory() as td:
        src, obj, binf = Path(td, "src.asm"), Path(td, "src.p"), Path(td, "src.bin")
        src.write_text(source)
        r = subprocess.run([str(ASL), "-q", "-U", "-o", str(obj), str(src)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"asl failed:\n{r.stdout}\n{r.stderr}")
        r = subprocess.run(
            [str(P2BIN), "-q", "-r", f"${start:X}-${end:X}", str(obj), str(binf)], capture_output=True, text=True
        )
        if r.returncode != 0:
            raise RuntimeError(f"p2bin failed:\n{r.stdout}\n{r.stderr}")
        return binf.read_bytes()


def assemble_dasm(source: str, start: int, end: int) -> bytes:
    with tempfile.TemporaryDirectory() as td:
        src, binf = Path(td, "src.asm"), Path(td, "src.bin")
        src.write_text(source)
        # -f3: raw image from the first origin, no header
        r = subprocess.run([str(DASM), str(src), f"-o{binf}", "-f3"], capture_output=True, text=True)
        if r.returncode != 0 or not binf.exists():
            raise RuntimeError(f"dasm failed:\n{r.stdout}\n{r.stderr}")
        return binf.read_bytes()


def _compare(label: str, got: bytes, rom: bytes, org: int) -> bool:
    ok = got == rom
    print(f"  {label:5s}: {'IDENTICAL' if ok else 'MISMATCH'}")
    if not ok:
        n = min(len(got), len(rom))
        diff = next((i for i in range(n) if got[i] != rom[i]), n)
        print(f"         first difference at ${org + diff:04X} (got {len(got)} bytes, want {len(rom)})")
    return ok


def run(name: str, write: bool) -> bool:
    t = TARGETS[name]
    rom = t["rom"].read_bytes()
    listing = parse(t["listing"], rom)
    source = emit(listing, rom, t["title"], "asl")
    if write:
        t["out"].parent.mkdir(parents=True, exist_ok=True)
        t["out"].write_text(source)
    end = listing.org + len(rom) - 1
    sha = hashlib.sha256(rom).hexdigest()
    print(f"{name}: {len(rom)} bytes, sha256 {sha}")
    ok = _compare("asl", assemble_asl(source, listing.org, end), rom, listing.org)
    ok &= _compare("dasm", assemble_dasm(emit(listing, rom, t["title"], "dasm"), listing.org, end), rom, listing.org)
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?", default="bluetop", choices=sorted(TARGETS))
    ap.add_argument("--write", action="store_true", help="write the generated source to analysis/")
    a = ap.parse_args()
    return 0 if run(a.target, a.write) else 1


if __name__ == "__main__":
    sys.exit(main())
