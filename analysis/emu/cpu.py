"""HD6301V1 CPU core (instruction set, cycle counts, interrupt entry).

Written from the Hitachi HD6301/HD6303 Series Handbook (1989), tables 3-2-1 to
3-2-4 (instruction semantics, flags and cycle counts). It is checked
instruction-by-instruction against MAME's hd6301 core in
``tests/test_emu_cpu.py`` (see ``tools/setup_mame_ref.sh``).

Peripherals (timer, SCI, ports) are not part of the core: they sit behind the
``Bus`` and call ``irq()`` / ``nmi()``. Undefined opcodes take the TRAP
vector ($FFEE), as the HD6301 does.

Usage::

    cpu = HD6301(FlatBus(rom_image_at_0))
    cpu.reset()
    while True:
        cpu.step()          # returns E-clock cycles used
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from pcmre.hd6301 import BIT_DIR, BIT_IDX, DIR, EXT, IDX, IMM8, IMM16, INH, OPCODES, REL

H, I, N, Z, V, C = 0x20, 0x10, 0x08, 0x04, 0x02, 0x01  # noqa: E741 - the CCR flag names
CC_FIXED = 0xC0  # bits 7 and 6 of the CCR always read as 1

VEC_TRAP, VEC_SCI, VEC_TOF, VEC_OCF, VEC_ICF, VEC_IRQ1, VEC_SWI, VEC_NMI, VEC_RES = (
    0xFFEE,
    0xFFF0,
    0xFFF2,
    0xFFF4,
    0xFFF6,
    0xFFF8,
    0xFFFA,
    0xFFFC,
    0xFFFE,
)


class Bus(Protocol):
    def read(self, addr: int) -> int: ...
    def write(self, addr: int, value: int) -> None: ...


class FlatBus:
    """64 KB of plain RAM, optionally preloaded (e.g. a ROM image at its address)."""

    def __init__(self, image: bytes | None = None, base: int = 0):
        self.mem = bytearray(0x10000)
        if image:
            self.mem[base : base + len(image)] = image

    def read(self, addr: int) -> int:
        return self.mem[addr]

    def write(self, addr: int, value: int) -> None:
        self.mem[addr] = value


# --- cycle counts (handbook tables 3-2-1 .. 3-2-4) ---------------------------
_WIDE = {"subd", "addd", "ldd", "cpx", "ldx", "lds"}  # 16-bit operand: +1 cycle
_STORE16 = {"std", "stx", "sts"}
_RMW = {"neg", "com", "lsr", "ror", "asr", "asl", "rol", "dec", "inc"}
_INHERENT_CYCLES = {
    "daa": 2, "mul": 7, "psha": 4, "pshb": 4, "pula": 3, "pulb": 3, "pshx": 5, "pulx": 4,
    "xgdx": 2, "rti": 10, "rts": 5, "swi": 12, "wai": 9, "slp": 4,
}  # fmt: skip


def _cycles(mnem: str, mode: str) -> int:
    if mode == INH:
        return _INHERENT_CYCLES.get(mnem, 1)
    if mode == REL:
        return 5 if mnem == "bsr" else 3
    if mnem == "jmp":
        return 3
    if mnem == "jsr":
        return {DIR: 5, IDX: 5, EXT: 6}[mode]
    if mode in (BIT_DIR, BIT_IDX):
        base = 4 if mnem == "tim" else 6
        return base + (mode == BIT_IDX)
    if mnem in _RMW:
        return 6
    if mnem == "tst":
        return 4
    if mnem == "clr":
        return 5
    extra = 1 if (mnem in _WIDE or mnem in _STORE16) else 0
    return {IMM8: 2, IMM16: 2, DIR: 3, IDX: 4, EXT: 4}[mode] + extra


class HD6301:
    def __init__(self, bus: Bus):
        self.bus = bus
        self.a = self.b = 0
        self.x = self.s = self.pc = 0
        self._cc = CC_FIXED | I
        self.cycles = 0  # total E-clock cycles executed
        self.waiting = False  # after WAI (registers already stacked)
        self.sleeping = False  # after SLP
        self.irq_inhibit = False  # one-instruction IRQ delay after CLI/TAP
        self._ops: dict[int, Callable[[], None]] = {}
        self._cyc: dict[int, int] = {}
        self._build()

    # -- registers -------------------------------------------------------------
    @property
    def cc(self) -> int:
        return self._cc

    @cc.setter
    def cc(self, v: int) -> None:
        self._cc = (v & 0x3F) | CC_FIXED

    @property
    def d(self) -> int:
        return (self.a << 8) | self.b

    @d.setter
    def d(self, v: int) -> None:
        self.a, self.b = (v >> 8) & 0xFF, v & 0xFF

    # -- memory helpers ----------------------------------------------------------
    def rd(self, a: int) -> int:
        return self.bus.read(a & 0xFFFF)

    def wr(self, a: int, v: int) -> None:
        self.bus.write(a & 0xFFFF, v & 0xFF)

    def rd16(self, a: int) -> int:
        return (self.rd(a) << 8) | self.rd(a + 1)

    def wr16(self, a: int, v: int) -> None:
        self.wr(a, v >> 8)
        self.wr(a + 1, v)

    def push(self, v: int) -> None:
        self.wr(self.s, v)
        self.s = (self.s - 1) & 0xFFFF

    def pull(self) -> int:
        self.s = (self.s + 1) & 0xFFFF
        return self.rd(self.s)

    def push16(self, v: int) -> None:
        self.push(v & 0xFF)
        self.push(v >> 8)

    def pull16(self) -> int:
        hi = self.pull()
        return (hi << 8) | self.pull()

    def fetch(self) -> int:
        v = self.rd(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return v

    def fetch16(self) -> int:
        hi = self.fetch()
        return (hi << 8) | self.fetch()

    # -- flags -------------------------------------------------------------------
    def _set(self, mask: int, cond: bool) -> None:
        self._cc = (self._cc | mask) if cond else (self._cc & ~mask)

    def _nz8(self, r: int) -> None:
        self._set(N, r & 0x80)
        self._set(Z, (r & 0xFF) == 0)

    def _nz16(self, r: int) -> None:
        self._set(N, r & 0x8000)
        self._set(Z, (r & 0xFFFF) == 0)

    def _add8(self, a: int, b: int, carry: int = 0, half: bool = True) -> int:
        r = a + b + carry
        if half:
            self._set(H, (a ^ b ^ r) & 0x10)
        self._nz8(r)
        self._set(V, (~(a ^ b) & (a ^ r)) & 0x80)
        self._set(C, r & 0x100)
        return r & 0xFF

    def _sub8(self, a: int, b: int, borrow: int = 0) -> int:
        r = a - b - borrow
        self._nz8(r)
        self._set(V, ((a ^ b) & (a ^ r)) & 0x80)
        self._set(C, r & 0x100)
        return r & 0xFF

    def _add16(self, a: int, b: int) -> int:
        r = a + b
        self._nz16(r)
        self._set(V, (~(a ^ b) & (a ^ r)) & 0x8000)
        self._set(C, r & 0x10000)
        return r & 0xFFFF

    def _sub16(self, a: int, b: int) -> int:
        r = a - b
        self._nz16(r)
        self._set(V, ((a ^ b) & (a ^ r)) & 0x8000)
        self._set(C, r & 0x10000)
        return r & 0xFFFF

    def _logic(self, r: int) -> int:
        self._nz8(r)
        self._set(V, False)
        return r & 0xFF

    def _nxc(self) -> None:
        """V = N xor C (shifts and rotates, handbook note 6)."""
        self._set(V, bool(self._cc & N) != bool(self._cc & C))

    # -- read-modify-write and accumulator unary ops ------------------------------
    def _unary(self, mnem: str, v: int) -> int:
        c = self._cc & C
        if mnem == "neg":
            r = self._sub8(0, v)
        elif mnem == "com":
            r = self._logic(~v)
            self._set(C, True)
        elif mnem == "lsr":
            self._set(C, v & 1)
            r = v >> 1
            self._nz8(r)
            self._nxc()
        elif mnem == "ror":
            self._set(C, v & 1)
            r = (v >> 1) | (c << 7)
            self._nz8(r)
            self._nxc()
        elif mnem == "asr":
            self._set(C, v & 1)
            r = (v >> 1) | (v & 0x80)
            self._nz8(r)
            self._nxc()
        elif mnem == "asl":
            self._set(C, v & 0x80)
            r = (v << 1) & 0xFF
            self._nz8(r)
            self._nxc()
        elif mnem == "rol":
            self._set(C, v & 0x80)
            r = ((v << 1) | c) & 0xFF
            self._nz8(r)
            self._nxc()
        elif mnem == "dec":
            r = (v - 1) & 0xFF
            self._nz8(r)
            self._set(V, v == 0x80)
        elif mnem == "inc":
            r = (v + 1) & 0xFF
            self._nz8(r)
            self._set(V, v == 0x7F)
        elif mnem == "tst":
            r = self._logic(v)
            self._set(C, False)
            return v  # no write-back
        elif mnem == "clr":
            r = 0
            self._cc = (self._cc & ~(N | V | C)) | Z
        else:
            raise AssertionError(mnem)
        return r

    # -- interrupts --------------------------------------------------------------
    def _stack_all(self) -> None:
        self.push16(self.pc)
        self.push16(self.x)
        self.push(self.a)
        self.push(self.b)
        self.push(self._cc)

    def interrupt(self, vector: int) -> int:
        """Enter an interrupt (or TRAP/SWI) through ``vector``; returns cycles used.

        After WAI the registers are already stacked (WAI's 9 cycles include the seven
        stack writes, handbook table 3-3-1), so only the vector fetch remains: 4 cycles,
        as in MAME.
        """
        cycles = 4 if self.waiting else 12
        if not self.waiting:
            self._stack_all()
        self.waiting = self.sleeping = False
        self._set(I, True)
        self.pc = self.rd16(vector)
        return cycles

    def irq(self, vector: int) -> bool:
        """Request a maskable interrupt; taken if I is clear. Returns True if taken.

        A masked request still ends SLP: the CPU leaves sleep mode and carries on with the
        next instruction (handbook section 2.12). WAI with I set is only ended by NMI.
        """
        if self._cc & I or self.irq_inhibit:
            self.sleeping = False
            return False
        self.cycles += self.interrupt(vector)
        return True

    def nmi(self) -> None:
        self.cycles += self.interrupt(VEC_NMI)

    def reset(self) -> None:
        self.pc = self.rd16(VEC_RES)
        self.cc = I
        self.waiting = self.sleeping = self.irq_inhibit = False

    # -- execution ---------------------------------------------------------------
    def step(self) -> int:
        """Execute one instruction; return its cycle count (0 while waiting or asleep)."""
        if self.waiting or self.sleeping:
            return 0
        self.irq_inhibit = False
        op = self.fetch()
        fn = self._ops.get(op)
        if fn is None:  # undefined opcode: TRAP
            self.pc = (self.pc - 1) & 0xFFFF
            n = self.interrupt(VEC_TRAP)
        else:
            fn()
            n = self._cyc[op]
        self.cycles += n
        return n

    def _build(self) -> None:
        for op, (mnem, mode) in OPCODES.items():
            self._ops[op] = self._make(mnem, mode)
            self._cyc[op] = _cycles(mnem, mode)

    def _make(self, mnem: str, mode: str) -> Callable[[], None]:
        cpu = self

        # Effective-address helpers (read the operand bytes, return the address).
        def ea() -> int:
            if mode == DIR:
                return cpu.fetch()
            if mode == EXT:
                return cpu.fetch16()
            if mode == IDX:
                return (cpu.x + cpu.fetch()) & 0xFFFF
            raise AssertionError(mode)

        def operand8() -> int:
            return cpu.fetch() if mode == IMM8 else cpu.rd(ea())

        def operand16() -> int:
            return cpu.fetch16() if mode == IMM16 else cpu.rd16(ea())

        acc = None
        if mnem.endswith(("a", "b")) and mnem not in ("aba", "sba", "cba", "tab", "tba", "daa", "xgdx", "psha",
                                                        "pshb", "pula", "pulb", "tsta", "tstb"):  # fmt: skip
            acc = mnem[-1]
        if mnem in ("tsta", "tstb"):
            acc = mnem[-1]

        def get(r: str) -> int:
            return cpu.a if r == "a" else cpu.b

        def put(r: str, v: int) -> None:
            if r == "a":
                cpu.a = v & 0xFF
            else:
                cpu.b = v & 0xFF

        base = mnem[:-1] if acc else mnem

        # Branches
        if mode == REL:
            cond = _BRANCH_COND[mnem]

            def branch() -> None:
                off = cpu.fetch()
                if mnem == "bsr":
                    cpu.push16(cpu.pc)
                if cond(cpu._cc):
                    cpu.pc = (cpu.pc + (off - 0x100 if off & 0x80 else off)) & 0xFFFF

            return branch

        if mnem == "jmp":

            def jmp() -> None:
                cpu.pc = ea()

            return jmp
        if mnem == "jsr":

            def jsr() -> None:
                t = ea()
                cpu.push16(cpu.pc)
                cpu.pc = t

            return jsr

        # HD6301 bit-manipulation group: aim/oim/eim/tim #imm,addr
        if mode in (BIT_DIR, BIT_IDX):

            def bitop() -> None:
                imm = cpu.fetch()
                off = cpu.fetch()
                a = off if mode == BIT_DIR else (cpu.x + off) & 0xFFFF
                v = cpu.rd(a)
                r = {"aim": v & imm, "oim": v | imm, "eim": v ^ imm, "tim": v & imm}[mnem]
                cpu._logic(r)
                if mnem != "tim":
                    cpu.wr(a, r)

            return bitop

        # Memory read-modify-write (and tst/clr on memory)
        if mode in (IDX, EXT) and mnem in _RMW | {"tst", "clr"}:

            def rmw() -> None:
                a = ea()
                v = cpu.rd(a)
                r = cpu._unary(mnem, v)
                if mnem != "tst":
                    cpu.wr(a, r)

            return rmw

        # Accumulator unary ops (nega, asla, tstb ...)
        if mode == INH and acc and base in _RMW | {"tst", "clr"}:

            def unary_acc() -> None:
                r = cpu._unary(base, get(acc))
                put(acc, r)

            return unary_acc

        # 8-bit accumulator/memory ops
        if acc and base in ("add", "adc", "sub", "sbc", "cmp", "and", "bit", "eor", "ora", "lda"):

            def alu8() -> None:
                m = operand8()
                v = get(acc)
                c = cpu._cc & C
                if base == "add":
                    put(acc, cpu._add8(v, m))
                elif base == "adc":
                    put(acc, cpu._add8(v, m, c))
                elif base == "sub":
                    put(acc, cpu._sub8(v, m))
                elif base == "sbc":
                    put(acc, cpu._sub8(v, m, c))
                elif base == "cmp":
                    cpu._sub8(v, m)
                elif base == "and":
                    put(acc, cpu._logic(v & m))
                elif base == "bit":
                    cpu._logic(v & m)
                elif base == "eor":
                    put(acc, cpu._logic(v ^ m))
                elif base == "ora":
                    put(acc, cpu._logic(v | m))
                elif base == "lda":
                    put(acc, cpu._logic(m))

            return alu8

        if acc and base == "sta":

            def sta() -> None:
                v = get(acc)
                cpu._logic(v)
                cpu.wr(ea(), v)

            return sta

        # 16-bit loads, stores, arithmetic and compare
        reg16 = {"ldd": "d", "ldx": "x", "lds": "s", "std": "d", "stx": "x", "sts": "s"}
        if mnem in ("ldd", "ldx", "lds"):

            def ld16() -> None:
                v = operand16()
                setattr(cpu, reg16[mnem], v)
                cpu._nz16(v)
                cpu._set(V, False)

            return ld16
        if mnem in ("std", "stx", "sts"):

            def st16() -> None:
                v = getattr(cpu, reg16[mnem])
                cpu._nz16(v)
                cpu._set(V, False)
                cpu.wr16(ea(), v)

            return st16
        if mnem in ("addd", "subd"):

            def arith16() -> None:
                m = operand16()
                cpu.d = cpu._add16(cpu.d, m) if mnem == "addd" else cpu._sub16(cpu.d, m)

            return arith16
        if mnem == "cpx":

            def cpx() -> None:
                cpu._sub16(cpu.x, operand16())

            return cpx

        # Inherent instructions
        return _INHERENT[mnem].__get__(cpu)


# --- branch conditions ----------------------------------------------------------
def _nxv(cc: int) -> bool:
    return bool(cc & N) != bool(cc & V)


_BRANCH_COND: dict[str, Callable[[int], bool]] = {
    "bra": lambda cc: True,
    "brn": lambda cc: False,
    "bhi": lambda cc: not (cc & (C | Z)),
    "bls": lambda cc: bool(cc & (C | Z)),
    "bcc": lambda cc: not (cc & C),
    "bcs": lambda cc: bool(cc & C),
    "bne": lambda cc: not (cc & Z),
    "beq": lambda cc: bool(cc & Z),
    "bvc": lambda cc: not (cc & V),
    "bvs": lambda cc: bool(cc & V),
    "bpl": lambda cc: not (cc & N),
    "bmi": lambda cc: bool(cc & N),
    "bge": lambda cc: not _nxv(cc),
    "blt": lambda cc: _nxv(cc),
    "bgt": lambda cc: not (cc & Z) and not _nxv(cc),
    "ble": lambda cc: bool(cc & Z) or _nxv(cc),
    "bsr": lambda cc: True,
}


# --- inherent instructions (methods bound to the CPU at build time) ---------------
def _nop(c: HD6301) -> None:
    pass


def _lsrd(c: HD6301) -> None:
    d = c.d
    c._set(C, d & 1)
    d >>= 1
    c._nz16(d)
    c._nxc()
    c.d = d


def _asld(c: HD6301) -> None:
    d = c.d
    c._set(C, d & 0x8000)
    d = (d << 1) & 0xFFFF
    c._nz16(d)
    c._nxc()
    c.d = d


def _tap(c: HD6301) -> None:
    c.cc = c.a
    c.irq_inhibit = True


def _tpa(c: HD6301) -> None:
    c.a = c.cc


def _inx(c: HD6301) -> None:
    c.x = (c.x + 1) & 0xFFFF
    c._set(Z, c.x == 0)


def _dex(c: HD6301) -> None:
    c.x = (c.x - 1) & 0xFFFF
    c._set(Z, c.x == 0)


def _flag(mask: int, value: bool, inhibit: bool = False):
    def f(c: HD6301) -> None:
        c._set(mask, value)
        if inhibit:
            c.irq_inhibit = True

    return f


def _sba(c: HD6301) -> None:
    c.a = c._sub8(c.a, c.b)


def _cba(c: HD6301) -> None:
    c._sub8(c.a, c.b)


def _aba(c: HD6301) -> None:
    c.a = c._add8(c.a, c.b)


def _tab(c: HD6301) -> None:
    c.b = c._logic(c.a)


def _tba(c: HD6301) -> None:
    c.a = c._logic(c.b)


def _xgdx(c: HD6301) -> None:
    c.d, c.x = c.x, c.d


def _daa(c: HD6301) -> None:
    a, cf = c.a, 0
    msn, lsn = a & 0xF0, a & 0x0F
    if lsn > 9 or c._cc & H:
        cf |= 0x06
    if (msn > 0x80 and lsn > 9) or msn > 0x90 or c._cc & C:
        cf |= 0x60
    t = a + cf
    c._nz8(t)
    c._set(V, False)  # the handbook contradicts itself on V (STATUS conflicts log); MAME clears it
    if t & 0x100:
        c._set(C, True)  # handbook note 3: C is not cleared if previously set
    c.a = t & 0xFF


def _tsx(c: HD6301) -> None:
    c.x = (c.s + 1) & 0xFFFF


def _txs(c: HD6301) -> None:
    c.s = (c.x - 1) & 0xFFFF


def _ins(c: HD6301) -> None:
    c.s = (c.s + 1) & 0xFFFF


def _des(c: HD6301) -> None:
    c.s = (c.s - 1) & 0xFFFF


def _psha(c: HD6301) -> None:
    c.push(c.a)


def _pshb(c: HD6301) -> None:
    c.push(c.b)


def _pula(c: HD6301) -> None:
    c.a = c.pull()


def _pulb(c: HD6301) -> None:
    c.b = c.pull()


def _pshx(c: HD6301) -> None:
    c.push16(c.x)


def _pulx(c: HD6301) -> None:
    c.x = c.pull16()


def _rts(c: HD6301) -> None:
    c.pc = c.pull16()


def _abx(c: HD6301) -> None:
    c.x = (c.x + c.b) & 0xFFFF


def _rti(c: HD6301) -> None:
    c.cc = c.pull()
    c.b = c.pull()
    c.a = c.pull()
    c.x = c.pull16()
    c.pc = c.pull16()


def _mul(c: HD6301) -> None:
    r = c.a * c.b
    c._set(C, r & 0x80)
    c.d = r


def _wai(c: HD6301) -> None:
    c._stack_all()
    c.waiting = True


def _swi(c: HD6301) -> None:
    c._stack_all()
    c._set(I, True)
    c.pc = c.rd16(VEC_SWI)


def _slp(c: HD6301) -> None:
    c.sleeping = True


_INHERENT = {
    "nop": _nop, "lsrd": _lsrd, "asld": _asld, "tap": _tap, "tpa": _tpa, "inx": _inx, "dex": _dex,
    "clv": _flag(V, False), "sev": _flag(V, True), "clc": _flag(C, False), "sec": _flag(C, True),
    "cli": _flag(I, False, inhibit=True), "sei": _flag(I, True), "sba": _sba, "cba": _cba, "tab": _tab,
    "tba": _tba, "xgdx": _xgdx, "daa": _daa, "slp": _slp, "aba": _aba, "tsx": _tsx, "ins": _ins,
    "pula": _pula, "pulb": _pulb, "des": _des, "txs": _txs, "psha": _psha, "pshb": _pshb, "pulx": _pulx,
    "rts": _rts, "abx": _abx, "rti": _rti, "pshx": _pshx, "mul": _mul, "wai": _wai, "swi": _swi,
}  # fmt: skip
