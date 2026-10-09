"""P0: the Python HD6301 core agrees with MAME's hd6301 instruction handlers.

``tools/setup_mame_ref.sh`` builds ``.tools/mame-ref/hd6301ref``, which runs
MAME's handlers (unchanged) on random single-instruction cases. Each case is
replayed here on ``emu.cpu.HD6301`` with the same initial memory and registers,
and the final registers, flags, memory writes and cycle count must match.

Deliberate differences (documented in analysis/README.md):
- CCR bits 7-6 always read as 1 on the HD6301 (handbook); MAME keeps whatever
  TAP or RTI wrote. Only bits 5-0 are compared.
- $12/$13: MAME runs undocumented 6801 behaviour; the HD6301 traps
  (handbook: undefined op-codes cause a TRAP). The handbook is followed.
- TRAP cycle count: MAME's value is a placeholder, so it is not compared.
"""

import subprocess

import pytest

from emu.cpu import HD6301
from pcmre.hd6301 import OPCODES
from pcmre.roundtrip import ROOT

REF = ROOT / ".tools/mame-ref/hd6301ref"
SEED = 0x6301
CASES = 64  # per opcode
SKIP = {0x12, 0x13}  # undocumented on the 6801; the HD6301 traps (see module docstring)


def mix(seed: int, addr: int) -> int:
    """Same hash as tools/mame_ref/harness.cpp."""
    m = 0xFFFFFFFF
    h = (seed * 0x9E3779B1 + addr * 0x85EBCA77) & m
    h ^= h >> 15
    h = (h * 0x2C1B3C6D) & m
    h ^= h >> 12
    h = (h * 0x297A2D39) & m
    h ^= h >> 15
    return h


class LazyBus:
    """64 KB whose initial contents are mix(case_seed, addr); records writes."""

    def __init__(self, case_seed: int, op_addr: int, op: int):
        self.cs, self.mem, self.writes = case_seed, {op_addr: op}, []

    def read(self, addr: int) -> int:
        if addr not in self.mem:
            self.mem[addr] = mix(self.cs, addr) & 0xFF
        return self.mem[addr]

    def write(self, addr: int, value: int) -> None:
        self.mem[addr] = value
        self.writes.append((addr, value))


@pytest.fixture(scope="module")
def ref_cases():
    if not REF.exists():
        pytest.skip("run tools/setup_mame_ref.sh first")
    out = subprocess.run([str(REF), str(SEED), str(CASES)], capture_output=True, text=True, check=True).stdout
    cases = []
    for line in out.splitlines():
        before, after = line.split("->")
        op, cs, pc, s, x, d, cc = (int(v, 16) for v in before.split())
        f = after.split()
        fin = [int(v, 16) for v in f[:5]]
        cyc, nw = int(f[5]), int(f[6])
        writes = [(int(a, 16), int(v, 16)) for a, v in (w.split("=") for w in f[7 : 7 + nw])]
        cases.append((op, cs, (pc, s, x, d, cc), fin, cyc, writes))
    assert len(cases) == 256 * CASES
    return cases


_CPU = HD6301(LazyBus(0, 0, 0))  # reused: building the dispatch table per case is slow


def run_case(op, cs, init):
    pc, s, x, d, cc = init
    bus = LazyBus(cs, pc, op)
    cpu = _CPU
    cpu.bus = bus
    cpu.waiting = cpu.sleeping = False
    cpu.pc, cpu.s, cpu.x, cpu.d, cpu.cc = pc, s, x, d, cc
    cycles = cpu.step()
    return cpu, bus, cycles


def test_every_opcode_matches_mame(ref_cases):
    failures: dict[int, str] = {}
    for op, cs, init, fin, cyc, writes in ref_cases:
        if op in SKIP or op in failures:
            continue
        cpu, bus, cycles = run_case(op, cs, init)
        got = [cpu.pc, cpu.s, cpu.x, cpu.d, cpu.cc & 0x3F]
        want = fin[:4] + [fin[4] & 0x3F]
        problems = []
        if got != want:
            names = ["pc", "s", "x", "d", "cc"]
            problems += [f"{n} {g:04X}!={w:04X}" for n, g, w in zip(names, got, want, strict=True) if g != w]
        if dict(bus.writes) != dict(writes):
            problems.append(f"writes {bus.writes} != {writes}")
        if op in OPCODES and cycles != cyc:
            problems.append(f"cycles {cycles} != {cyc}")
        if problems:
            mnem = OPCODES.get(op, ("trap",))[0]
            failures[op] = f"${op:02X} {mnem} case {cs:08X} init {[hex(v) for v in init]}: " + "; ".join(problems)
    assert not failures, "\n".join(failures.values())


def test_all_documented_opcodes_covered(ref_cases):
    ops = {c[0] for c in ref_cases}
    assert set(OPCODES) <= ops


def test_cycle_table_matches_handbook_examples():
    # Spot values from handbook tables 3-2-1..3-2-4 (independent of MAME).
    cpu = HD6301(type("B", (), {"read": lambda s, a: 0, "write": lambda s, a, v: None})())
    expect = {0x86: 2, 0xCC: 3, 0xDD: 4, 0x6C: 6, 0x6F: 5, 0x6D: 4, 0x71: 6, 0x61: 7, 0x7B: 4, 0x6B: 5,
              0x3D: 7, 0x3C: 5, 0x38: 4, 0x3B: 10, 0x3F: 12, 0x3E: 9, 0x1A: 4, 0x18: 2, 0x19: 2,
              0x8D: 5, 0x9D: 5, 0xAD: 5, 0xBD: 6, 0x6E: 3, 0x7E: 3, 0x20: 3, 0x39: 5}  # fmt: skip
    assert {op: cpu._cyc[op] for op in expect} == expect


def test_bluetop_reaches_main_loop():
    """Smoke test: with no peripherals modelled, the Bluetop runs its reset code (CPU mode test,
    RAM clear, init table) and settles into Main_Loop ($F064) without a TRAP or a stray jump."""
    from emu.cpu import FlatBus

    rom = (ROOT / "TOYOTA Bluetop PCM/cap.bin").read_bytes()
    cpu = HD6301(FlatBus(rom, 0xF000))
    cpu.reset()
    assert cpu.pc == 0xF000
    main_loop = 0
    for _ in range(20000):
        assert cpu.pc >= 0xF000, f"left ROM: ${cpu.pc:04X}"
        main_loop += cpu.pc == 0xF064
        cpu.step()
    assert main_loop > 100
    assert cpu.s == 0x00FF  # stack balanced at the top of RAM


def test_suite6303_instructions_step():
    """Every instruction in dasm's suite6303 (an encoding suite) executes with the right length."""
    from emu.cpu import FlatBus
    from pcmre.hd6301 import REL, decode

    raw = (ROOT / "TOYOTA Bluetop PCM/dasm/test/suite6303.bin.ref").read_bytes()
    assert raw[:2] == b"\x00\x00"  # dasm -f1 header: origin $0000 (little-endian)
    image = raw[2:]
    cpu = HD6301(FlatBus(image, 0))
    control = {"jmp", "jsr", "bsr", "rts", "rti", "swi", "wai", "slp"}
    addr = n = 0
    while addr < len(image):
        ins = decode(image, addr)
        assert ins is not None, f"undefined opcode ${image[addr]:02X} at {addr:#x}"
        cpu.pc, cpu.waiting, cpu.sleeping = addr, False, False
        cpu.step()
        if ins.mnemonic not in control and ins.mode != REL:
            assert cpu.pc == addr + ins.length, f"{ins.mnemonic} at {addr:#x}"
        addr += ins.length
        n += 1
    assert n > 200
