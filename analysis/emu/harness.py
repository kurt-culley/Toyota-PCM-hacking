"""Run one ROM routine in the emulator, the way the ROM itself calls it.

A small stub is placed at ``STUB`` in otherwise unused address space::

    STUB:   jsr  <routine>
            <inline bytes>          ; for routines that read parameters after the call
    DONE:                           ; execution stops when PC reaches here

so routines that return past inline parameters (``boundData``) or pop extra
stack bytes (``mulDbyStack``) are handled exactly as in the ROM. RAM and the
registers can be preset; the result reports registers, flags, every memory
write and the cycle count.

    from emu.harness import call
    r = call(rom, 0xFC7D, a=0x12, b=0x34)     # DivDby16
    r.d  -> 0x0123
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .cpu import HD6301, FlatBus

STUB = 0x0400  # external address space the Bluetop never uses
STACK_TOP = 0x00FF


class RoutineTimeout(RuntimeError):
    pass


class _RecordingBus(FlatBus):
    def __init__(self, image: bytes, base: int):
        super().__init__(image, base)
        self.writes: list[tuple[int, int]] = []

    def write(self, addr: int, value: int) -> None:
        super().write(addr, value)
        self.writes.append((addr, value))


@dataclass
class Result:
    a: int
    b: int
    x: int
    s: int
    cc: int
    cycles: int
    steps: int
    writes: list[tuple[int, int]] = field(default_factory=list)
    mem: bytearray = field(default_factory=bytearray, repr=False)

    @property
    def d(self) -> int:
        return (self.a << 8) | self.b

    @property
    def carry(self) -> bool:
        return bool(self.cc & 0x01)

    def ram(self, addr: int, width: int = 1) -> int:
        v = 0
        for k in range(width):
            v = (v << 8) | self.mem[addr + k]
        return v


def call(
    rom: bytes,
    routine: int,
    *,
    a: int = 0,
    b: int = 0,
    x: int = 0,
    cc: int = 0,
    ram: dict[int, int] | None = None,
    inline: bytes = b"",
    stack: bytes = b"",
    rom_base: int = 0xF000,
    max_steps: int = 100_000,
) -> Result:
    """Call ``routine`` with the given registers and RAM; return when it returns to the stub.

    ``stack`` bytes are pushed before the call (first byte pushed first), for routines that
    take arguments on the stack.
    """
    bus = _RecordingBus(rom, rom_base)
    for addr, value in (ram or {}).items():
        bus.mem[addr] = value & 0xFF
    stub = bytes([0xBD, routine >> 8, routine & 0xFF]) + inline
    bus.mem[STUB : STUB + len(stub)] = stub
    done = STUB + len(stub)

    cpu = HD6301(bus)
    cpu.s = STACK_TOP
    for byte in stack:
        cpu.push(byte)
    cpu.a, cpu.b, cpu.x, cpu.cc, cpu.pc = a & 0xFF, b & 0xFF, x & 0xFFFF, cc, STUB
    bus.writes.clear()
    steps = 0
    while cpu.pc != done:
        if steps >= max_steps:
            raise RoutineTimeout(f"routine ${routine:04X} did not return within {max_steps} steps (PC ${cpu.pc:04X})")
        cpu.step()
        steps += 1
    return Result(cpu.a, cpu.b, cpu.x, cpu.s, cpu.cc, cpu.cycles, steps, list(bus.writes), bus.mem)


def run(
    rom: bytes,
    start: int,
    stop: int,
    *,
    a: int = 0,
    b: int = 0,
    x: int = 0,
    cc: int = 0,
    ram: dict[int, int] | None = None,
    rom_base: int = 0xF000,
    max_steps: int = 100_000,
) -> Result:
    """Run straight-line ROM code from ``start`` until PC reaches ``stop`` (for code inside a routine)."""
    bus = _RecordingBus(rom, rom_base)
    for addr, value in (ram or {}).items():
        bus.mem[addr] = value & 0xFF
    cpu = HD6301(bus)
    cpu.s = STACK_TOP
    cpu.a, cpu.b, cpu.x, cpu.cc, cpu.pc = a & 0xFF, b & 0xFF, x & 0xFFFF, cc, start
    steps = 0
    while cpu.pc != stop:
        if steps >= max_steps:
            raise RoutineTimeout(f"${start:04X} did not reach ${stop:04X} within {max_steps} steps (PC ${cpu.pc:04X})")
        cpu.step()
        steps += 1
    return Result(cpu.a, cpu.b, cpu.x, cpu.s, cpu.cc, cpu.cycles, steps, list(bus.writes), bus.mem)
