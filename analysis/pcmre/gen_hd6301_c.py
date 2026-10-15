"""Generate the C HD6301 core's instruction switch from the Python opcode table.

    PYTHONPATH=analysis uv run python -m pcmre.gen_hd6301_c --write

The single source of truth for opcodes, addressing modes and cycle counts is
``pcmre.hd6301.OPCODES`` and ``emu.cpu`` (cycle counts: HD6301, MAME-verified; MC6801 for the
D151801). This writes ``hardware/ecu-emu/core/hd6301_ops.inc``: one ``case`` per defined opcode,
fully specialised (no runtime decode of mode or mnemonic), for the RP2350 CPU-replacement
firmware; and ``hd6301_timing.inc``: the cycle and data-access-cycle tables for both timings.
tests/test_hd6301_c.py runs the C core against the Python one.
"""

from __future__ import annotations

import argparse
import sys

from emu.cpu import HD6301, FlatBus
from pcmre.hd6301 import BIT_DIR, BIT_IDX, DIR, EXT, IDX, IMM8, IMM16, INH, OPCODES, REL

from .roundtrip import ROOT

OUT = ROOT / "hardware/ecu-emu/core/hd6301_ops.inc"
OUT_TIMING = ROOT / "hardware/ecu-emu/core/hd6301_timing.inc"

_RMW = {"neg", "com", "lsr", "ror", "asr", "asl", "rol", "dec", "inc"}
_ALU = {"add", "adc", "sub", "sbc", "cmp", "and", "bit", "eor", "ora", "lda"}
_NOT_ACC = {"aba", "sba", "cba", "tab", "tba", "tpa", "daa", "xgdx", "psha", "pshb", "pula", "pulb"}
_COND = {
    "bra": "1", "brn": "0", "bhi": "!(CC & (F_C | F_Z))", "bls": "(CC & (F_C | F_Z))",
    "bcc": "!(CC & F_C)", "bcs": "(CC & F_C)", "bne": "!(CC & F_Z)", "beq": "(CC & F_Z)",
    "bvc": "!(CC & F_V)", "bvs": "(CC & F_V)", "bpl": "!(CC & F_N)", "bmi": "(CC & F_N)",
    "bge": "!NXV", "blt": "NXV", "bgt": "(!(CC & F_Z) && !NXV)", "ble": "((CC & F_Z) || NXV)",
    "bsr": "1",
}  # fmt: skip
_INH = {
    "nop": "", "lsrd": "op_lsrd(c);", "asld": "op_asld(c);",
    "tap": "c->cc = (uint8_t)(c->a | CC_FIXED); c->irq_inhibit = 1;", "tpa": "c->a = c->cc;",
    "inx": "c->x++; SETF(F_Z, c->x == 0);", "dex": "c->x--; SETF(F_Z, c->x == 0);",
    "clv": "CC &= ~F_V;", "sev": "CC |= F_V;", "clc": "CC &= ~F_C;", "sec": "CC |= F_C;",
    "cli": "CC &= ~F_I; c->irq_inhibit = 1;", "sei": "CC |= F_I;",
    "sba": "c->a = sub8(c, c->a, c->b, 0);", "cba": "(void)sub8(c, c->a, c->b, 0);",
    "aba": "c->a = add8(c, c->a, c->b, 0, 1);", "tab": "c->b = logic(c, c->a);", "tba": "c->a = logic(c, c->b);",
    "xgdx": "{ uint16_t t = D; SET_D(c->x); c->x = t; }", "daa": "op_daa(c);", "slp": "c->sleeping = 1;",
    "tsx": "c->x = (uint16_t)(c->s + 1);", "txs": "c->s = (uint16_t)(c->x - 1);", "ins": "c->s++;", "des": "c->s--;",
    "pula": "c->a = PULL();", "pulb": "c->b = PULL();", "psha": "PUSH(c->a);", "pshb": "PUSH(c->b);",
    "pulx": "c->x = PULL16();", "pshx": "PUSH16(c->x);", "rts": "c->pc = PULL16();",
    "abx": "c->x = (uint16_t)(c->x + c->b);",
    "rti": "c->cc = (uint8_t)(PULL() | CC_FIXED); c->b = PULL(); c->a = PULL(); c->x = PULL16(); c->pc = PULL16();",
    "mul": "{ uint16_t r = (uint16_t)(c->a * c->b); SETF(F_C, r & 0x80); SET_D(r); }",
    "wai": "stack_all(c); c->waiting = 1;",
    "swi": "stack_all(c); CC |= F_I; c->pc = RD16(HD6301_VEC_SWI);",
}  # fmt: skip


def _ea(mode: str) -> str:
    return {DIR: "uint16_t ea = FETCH();", EXT: "uint16_t ea = FETCH16();",
            IDX: "uint16_t ea = (uint16_t)(c->x + FETCH());"}[mode]  # fmt: skip


def body(mnem: str, mode: str) -> str:
    if mode == REL:
        push = "PUSH16(c->pc); " if mnem == "bsr" else ""
        return f"{{ int8_t off = (int8_t)FETCH(); {push}if ({_COND[mnem]}) c->pc = (uint16_t)(c->pc + off); }}"
    if mnem == "jmp":
        return f"{{ {_ea(mode)} c->pc = ea; }}"
    if mnem == "jsr":
        return f"{{ {_ea(mode)} PUSH16(c->pc); c->pc = ea; }}"
    if mode in (BIT_DIR, BIT_IDX):
        addr = "FETCH()" if mode == BIT_DIR else "(uint16_t)(c->x + FETCH())"
        op = {"aim": "&", "oim": "|", "eim": "^", "tim": "&"}[mnem]
        wb = "" if mnem == "tim" else " WR(ea, r);"
        calc = f"uint8_t r = (uint8_t)(RD(ea) {op} imm); (void)logic(c, r);"
        return f"{{ uint8_t imm = FETCH(); uint16_t ea = {addr}; {calc}{wb} }}"
    if mode in (IDX, EXT) and mnem in _RMW | {"tst", "clr"}:
        if mnem == "tst":
            return f"{{ {_ea(mode)} (void)u_tst(c, RD(ea)); }}"
        return f"{{ {_ea(mode)} uint8_t r = u_{mnem}(c, RD(ea)); WR(ea, r); }}"
    acc = mnem[-1] if mnem[-1] in "ab" and mnem not in _NOT_ACC else None
    base = mnem[:-1] if acc else mnem
    if mode == INH and acc:
        return f"c->{acc} = u_{base}(c, c->{acc});" if base != "tst" else f"(void)u_tst(c, c->{acc});"
    if acc and base in _ALU:
        src = "FETCH()" if mode == IMM8 else "RD(ea)"
        pre = "" if mode == IMM8 else _ea(mode) + " "
        r = f"c->{acc}"
        expr = {
            "add": f"{r} = add8(c, {r}, m, 0, 1);", "adc": f"{r} = add8(c, {r}, m, CC & F_C, 1);",
            "sub": f"{r} = sub8(c, {r}, m, 0);", "sbc": f"{r} = sub8(c, {r}, m, CC & F_C);",
            "cmp": f"(void)sub8(c, {r}, m, 0);", "and": f"{r} = logic(c, {r} & m);",
            "bit": f"(void)logic(c, {r} & m);", "eor": f"{r} = logic(c, {r} ^ m);",
            "ora": f"{r} = logic(c, {r} | m);", "lda": f"{r} = logic(c, m);",
        }[base]  # fmt: skip
        return f"{{ {pre}uint8_t m = {src}; {expr} }}"
    if acc and base == "sta":
        return f"{{ (void)logic(c, c->{acc}); {_ea(mode)} WR(ea, c->{acc}); }}"
    if mnem in ("ldd", "ldx", "lds", "addd", "subd", "cpx"):
        src = "FETCH16()" if mode == IMM16 else "RD16(ea)"
        pre = "" if mode == IMM16 else _ea(mode) + " "
        op = {
            "ldd": "SET_D(m); nz16(c, m); CC &= ~F_V;", "ldx": "c->x = m; nz16(c, m); CC &= ~F_V;",
            "lds": "c->s = m; nz16(c, m); CC &= ~F_V;", "addd": "SET_D(add16(c, D, m));",
            "subd": "SET_D(sub16(c, D, m));", "cpx": "(void)sub16(c, c->x, m);",
        }[mnem]  # fmt: skip
        return f"{{ {pre}uint16_t m = {src}; {op} }}"
    if mnem in ("std", "stx", "sts"):
        reg = {"std": "D", "stx": "c->x", "sts": "c->s"}[mnem]
        return f"{{ uint16_t v = {reg}; nz16(c, v); CC &= ~F_V; {_ea(mode)} WR16(ea, v); }}"
    return _INH[mnem]


def build() -> str:
    lines = [
        "/* Generated by `python -m pcmre.gen_hd6301_c --write` from pcmre.hd6301.OPCODES and",
        " * emu.cpu. Do not edit. One case per defined HD6301 opcode; undefined opcodes fall to",
        " * the TRAP default in hd6301.c. Cycle counts come from the core's timing table. */",
    ]
    for op in sorted(OPCODES):
        mnem, mode = OPCODES[op]
        lines.append(f"case 0x{op:02X}: /* {mnem} {mode} */ {body(mnem, mode)} n = c->cyc[0x{op:02X}]; break;")
    return "\n".join(lines) + "\n"


def build_timing() -> str:
    lines = [
        "/* Generated by `python -m pcmre.gen_hd6301_c --write` from emu.cpu (HD6301 handbook counts,",
        " * MAME-verified; MC6801 counts from MAME cycles_6803, which the D151801 runs). Do not edit.",
        " * ACC_*: the cycle (0 = opcode fetch) of an instruction's 1st and 2nd data access. */",
    ]
    for timing in ("6301", "6801"):
        cpu = HD6301(FlatBus(), timing=timing)
        cyc = [cpu._cyc.get(op, 0) for op in range(256)]
        acc = [cpu.access_offsets(op) for op in range(256)]
        lines.append(f"static const uint8_t CYC_{timing}[256] = {{")
        lines += ["    " + ", ".join(str(v) for v in cyc[r : r + 16]) + "," for r in range(0, 256, 16)]
        lines.append("};")
        lines.append(f"static const uint8_t ACC_{timing}[256][2] = {{")
        lines += ["    " + ", ".join(f"{{{a}, {b}}}" for a, b in acc[r : r + 8]) + "," for r in range(0, 256, 8)]
        lines.append("};")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    src, timing = build(), build_timing()
    if a.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(src)
        OUT_TIMING.write_text(timing)
        print(f"wrote {OUT.relative_to(ROOT)} ({len(OPCODES)} opcodes) and {OUT_TIMING.relative_to(ROOT)}")
    else:
        print(src)
    return 0


if __name__ == "__main__":
    sys.exit(main())
