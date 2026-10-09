"""HD6301/HD6303 instruction set: opcode table and single-instruction decoder.

The HD6301 is the MC6801 instruction set plus six Hitachi additions:
XGDX ($18), SLP ($1A) and the bit-manipulation group AIM/OIM/EIM/TIM
($61/$62/$65/$6B indexed, $71/$72/$75/$7B direct). Source: Hitachi
HD6301/HD6303 Series Handbook (1989), in the repo root.

Mnemonics follow Motorola 6801 conventions as accepted by the Macroassembler
AS (``cpu 6301``). The IDA 4.9 listings in this repo use 68HC11-style
aliases (``ora``, ``lsld`` ...); ``IDA_ALIASES`` maps those back.
"""

from __future__ import annotations

from dataclasses import dataclass

# Addressing modes
INH = "inh"  # no operand
IMM8 = "imm8"  # #nn
IMM16 = "imm16"  # #nnnn
DIR = "dir"  # nn (zero page)
EXT = "ext"  # nnnn
IDX = "idx"  # nn,x
REL = "rel"  # branch, signed 8-bit offset
BIT_DIR = "bit_dir"  # aim #nn,dd   (opcode, imm, direct addr)
BIT_IDX = "bit_idx"  # aim #nn,dd,x (opcode, imm, index offset)

OPERAND_BYTES = {INH: 0, IMM8: 1, IMM16: 2, DIR: 1, EXT: 2, IDX: 1, REL: 1, BIT_DIR: 2, BIT_IDX: 2}


def _build() -> dict[int, tuple[str, str]]:
    t: dict[int, tuple[str, str]] = {}
    inherent = {
        0x01: "nop", 0x04: "lsrd", 0x05: "asld", 0x06: "tap", 0x07: "tpa",
        0x08: "inx", 0x09: "dex", 0x0A: "clv", 0x0B: "sev", 0x0C: "clc",
        0x0D: "sec", 0x0E: "cli", 0x0F: "sei", 0x10: "sba", 0x11: "cba",
        0x16: "tab", 0x17: "tba", 0x18: "xgdx", 0x19: "daa", 0x1A: "slp",
        0x1B: "aba", 0x30: "tsx", 0x31: "ins", 0x32: "pula", 0x33: "pulb",
        0x34: "des", 0x35: "txs", 0x36: "psha", 0x37: "pshb", 0x38: "pulx",
        0x39: "rts", 0x3A: "abx", 0x3B: "rti", 0x3C: "pshx", 0x3D: "mul",
        0x3E: "wai", 0x3F: "swi",
    }  # fmt: skip
    for op, m in inherent.items():
        t[op] = (m, INH)

    branches = ["bra", "brn", "bhi", "bls", "bcc", "bcs", "bne", "beq",
                "bvc", "bvs", "bpl", "bmi", "bge", "blt", "bgt", "ble"]  # fmt: skip
    for i, m in enumerate(branches):
        t[0x20 + i] = (m, REL)
    t[0x8D] = ("bsr", REL)

    # Read-modify-write group: $4x (A), $5x (B), $6x (indexed), $7x (extended)
    rmw = {0x0: "neg", 0x3: "com", 0x4: "lsr", 0x6: "ror", 0x7: "asr",
           0x8: "asl", 0x9: "rol", 0xA: "dec", 0xC: "inc", 0xD: "tst", 0xF: "clr"}  # fmt: skip
    for lo, m in rmw.items():
        t[0x40 + lo] = (m + "a", INH)
        t[0x50 + lo] = (m + "b", INH)
        t[0x60 + lo] = (m, IDX)
        t[0x70 + lo] = (m, EXT)
    t[0x6E] = ("jmp", IDX)
    t[0x7E] = ("jmp", EXT)
    # HD6301 bit-manipulation additions
    for lo, m in {0x1: "aim", 0x2: "oim", 0x5: "eim", 0xB: "tim"}.items():
        t[0x60 + lo] = (m, BIT_IDX)
        t[0x70 + lo] = (m, BIT_DIR)

    # Accumulator/register group: $8x-$Bx (A, X/S/D), $Cx-$Fx (B, D/X)
    acc_a = {0x0: "suba", 0x1: "cmpa", 0x2: "sbca", 0x3: "subd", 0x4: "anda",
             0x5: "bita", 0x6: "ldaa", 0x7: "staa", 0x8: "eora", 0x9: "adca",
             0xA: "oraa", 0xB: "adda", 0xC: "cpx", 0xD: "jsr", 0xE: "lds", 0xF: "sts"}  # fmt: skip
    acc_b = {0x0: "subb", 0x1: "cmpb", 0x2: "sbcb", 0x3: "addd", 0x4: "andb",
             0x5: "bitb", 0x6: "ldab", 0x7: "stab", 0x8: "eorb", 0x9: "adcb",
             0xA: "orab", 0xB: "addb", 0xC: "ldd", 0xD: "std", 0xE: "ldx", 0xF: "stx"}  # fmt: skip
    wide = {"subd", "cpx", "lds", "addd", "ldd", "ldx"}
    for base, table in ((0x80, acc_a), (0xC0, acc_b)):
        for lo, m in table.items():
            if m not in ("staa", "stab", "sts", "std", "stx", "jsr"):
                t[base + lo] = (m, IMM16 if m in wide else IMM8)
            t[base + 0x10 + lo] = (m, DIR)
            t[base + 0x20 + lo] = (m, IDX)
            t[base + 0x30 + lo] = (m, EXT)
    # $8D is BSR (set above), not "jsr #"; no immediate stores exist.
    t[0x8D] = ("bsr", REL)
    return t


OPCODES: dict[int, tuple[str, str]] = _build()

# IDA 4.9 (68HC11 processor module) spellings -> HD6301 spellings used here.
IDA_ALIASES = {
    "ora": "oraa", "orb": "orab", "lsld": "asld", "lsla": "asla", "lslb": "aslb",
    "lsl": "asl", "bhs": "bcc", "blo": "bcs", "ldaa": "ldaa",
}  # fmt: skip


@dataclass(frozen=True)
class Instr:
    addr: int
    opcode: int
    mnemonic: str
    mode: str
    raw: bytes
    operand: int | None = None  # address/immediate/offset (rel: absolute target)
    imm: int | None = None  # immediate byte for AIM/OIM/EIM/TIM

    @property
    def length(self) -> int:
        return len(self.raw)


def decode(mem: bytes, addr: int, base: int = 0) -> Instr | None:
    """Decode one instruction at ``addr`` from ``mem`` loaded at ``base``.

    Returns None for an undefined opcode or if the instruction runs past the
    end of ``mem``.
    """
    off = addr - base
    if off < 0 or off >= len(mem):
        return None
    op = mem[off]
    if op not in OPCODES:
        return None
    mnem, mode = OPCODES[op]
    n = OPERAND_BYTES[mode]
    if off + 1 + n > len(mem):
        return None
    raw = bytes(mem[off : off + 1 + n])
    operand = imm = None
    if mode in (IMM8, DIR, IDX):
        operand = raw[1]
    elif mode in (IMM16, EXT):
        operand = (raw[1] << 8) | raw[2]
    elif mode == REL:
        disp = raw[1] - 0x100 if raw[1] & 0x80 else raw[1]
        operand = (addr + 2 + disp) & 0xFFFF
    elif mode in (BIT_DIR, BIT_IDX):
        imm, operand = raw[1], raw[2]
    return Instr(addr, op, mnem, mode, raw, operand, imm)


def normalise_mnemonic(m: str) -> str:
    m = m.lower()
    return IDA_ALIASES.get(m, m)
