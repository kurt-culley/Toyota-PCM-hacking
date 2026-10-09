import subprocess

import pytest

from pcmre.hd6301 import (
    BIT_DIR,
    BIT_IDX,
    DIR,
    EXT,
    IDX,
    IMM8,
    IMM16,
    INH,
    OPCODES,
    REL,
    decode,
    normalise_mnemonic,
)
from pcmre.roundtrip import ASL, P2BIN

needs_asl = pytest.mark.skipif(not ASL.exists(), reason="run tools/setup_assemblers.sh first")


def test_table_size_and_hitachi_extras():
    # 6801 has 220 defined opcodes; the HD6301 adds XGDX, SLP and 8 bit-manipulation ops.
    assert len(OPCODES) == 230
    assert OPCODES[0x18] == ("xgdx", INH)
    assert OPCODES[0x1A] == ("slp", INH)
    assert OPCODES[0x61] == ("aim", BIT_IDX)
    assert OPCODES[0x7B] == ("tim", BIT_DIR)
    assert OPCODES[0x8D] == ("bsr", REL)
    for undefined in (0x00, 0x02, 0x87, 0x8F, 0xC7, 0xCD, 0xCF):
        assert undefined not in OPCODES


def test_decode_relative_and_bitops():
    mem = bytes([0x20, 0xFE, 0x26, 0x02, 0x61, 0x12, 0x03, 0x71, 0x80, 0x40, 0xBD, 0xFF, 0x28])
    bra = decode(mem, 0xF000, 0xF000)
    assert (bra.mnemonic, bra.operand, bra.length) == ("bra", 0xF000, 2)  # branch to self
    assert decode(mem, 0xF002, 0xF000).operand == 0xF006
    aim = decode(mem, 0xF004, 0xF000)
    assert (aim.mnemonic, aim.imm, aim.operand, aim.length) == ("aim", 0x12, 0x03, 3)
    assert decode(mem, 0xF007, 0xF000).mode == BIT_DIR
    jsr = decode(mem, 0xF00A, 0xF000)
    assert (jsr.mnemonic, jsr.mode, jsr.operand) == ("jsr", EXT, 0xFF28)
    assert decode(bytes([0x00]), 0, 0) is None
    assert decode(bytes([0xBD, 0xFF]), 0, 0) is None  # truncated


def test_ida_aliases():
    assert normalise_mnemonic("ORA") == "oraa"
    assert normalise_mnemonic("lsld") == "asld"
    assert normalise_mnemonic("ldd") == "ldd"


@needs_asl
def test_every_opcode_matches_asl(tmp_path):
    """Assemble one instance of every opcode with asl and compare to the table."""
    operand = {INH: "", IMM8: "#$12", IMM16: "#$1234", DIR: "$12", EXT: "$1234", IDX: "$12,x",
               REL: "*+2", BIT_DIR: "#$12,$34", BIT_IDX: "#$12,$34,x"}  # fmt: skip
    raw = {INH: b"", IMM8: b"\x12", IMM16: b"\x12\x34", DIR: b"\x12", EXT: b"\x12\x34", IDX: b"\x12",
           REL: b"\x00", BIT_DIR: b"\x12\x34", BIT_IDX: b"\x12\x34"}  # fmt: skip
    lines = ["\tcpu 6301", "\torg $1000"]
    want = bytearray()
    for op, (m, mode) in sorted(OPCODES.items()):
        lines.append(f"\t{m}\t{operand[mode]}")
        want += bytes([op]) + raw[mode]
    src = tmp_path / "all.asm"
    src.write_text("\n".join(lines) + "\n")
    subprocess.run([str(ASL), "-q", "-o", str(tmp_path / "all.p"), str(src)], check=True)
    subprocess.run([str(P2BIN), "-q", str(tmp_path / "all.p"), str(tmp_path / "all.bin")], check=True)
    assert (tmp_path / "all.bin").read_bytes() == bytes(want)
