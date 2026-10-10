"""Whole-ROM simulation: CPU + peripherals + engine stimulus.

    from emu.sim import Simulation
    sim = Simulation()                       # Bluetop cap.bin, booted from reset
    sim.inputs.rpm = 900; sim.inputs.coolant_f = 50; sim.engine.update_sensors()
    sim.run_ms(500)
    sim.ram("FuelRatioH", 2), sim.injector_pulses("#20")[-1], sim.advance_deg()

Times are E-clock cycles (µs; the E clock is 1 MHz [ROM:$F168 CalcInjOffTime]).
See docs/bluetop/simulation.md for what is modelled and what is GUESS.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

from .cpu import HD6301, VEC_TRAP
from .engine import BLUETOP_ROM, Engine, EngineInputs
from .periph import Peripherals

ROOT = Path(__file__).resolve().parents[2]
LISTING = ROOT / "analysis/bluetop/cap.s"


class SimulationError(RuntimeError):
    pass


@cache
def symbols(listing: Path = LISTING) -> dict[str, int]:
    """RAM and register names from the ``name equ $addr`` lines of the listing (code labels are not needed)."""
    out = {}
    for line in listing.read_text().splitlines():
        m = re.match(r"^(\w+)\s+equ\s+\$([0-9A-Fa-f]+)", line)
        if m:
            out[m.group(1)] = int(m.group(2), 16)
    return out


class Simulation:
    def __init__(
        self, rom: bytes | None = None, inputs: EngineInputs | None = None, extra: dict[int, bytes] | None = None
    ):
        """``extra`` maps addresses to code or data outside the ROM (external memory, as on the P7 board)."""
        self.rom = rom if rom is not None else BLUETOP_ROM.read_bytes()
        self.periph = Peripherals(self.rom)
        for addr, data in (extra or {}).items():
            self.periph.mem[addr : addr + len(data)] = data
        self.cpu = HD6301(self.periph)
        self.engine = Engine(self.periph, self.rom, inputs)
        self.inputs = self.engine.inputs
        self.irq_counts: dict[int, int] = {}
        self.cpu.reset()

    # -- running ---------------------------------------------------------------------------
    def step(self) -> None:
        cpu, p = self.cpu, self.periph
        before = cpu.cycles
        if cpu.waiting or cpu.sleeping:
            t = p.next_event_time()
            cpu.cycles += max(1, (t - p.now) if t is not None else 1)
        else:
            if cpu.pc == self.rom[VEC_TRAP - 0xF000] << 8 | self.rom[VEC_TRAP - 0xF000 + 1]:
                raise SimulationError(f"TRAP taken (undefined opcode) at cycle {p.now}")
            cpu.step()
        p.advance(cpu.cycles - before)
        vec = p.irq_vector()
        if vec is not None:
            before = cpu.cycles
            if cpu.irq(vec):
                self.irq_counts[vec] = self.irq_counts.get(vec, 0) + 1
                p.advance(cpu.cycles - before)

    def run_until(self, t: int) -> None:
        while self.periph.now < t:
            self.step()

    def run_ms(self, ms: float) -> None:
        self.run_until(self.periph.now + round(ms * 1000))

    # -- probes ------------------------------------------------------------------------------
    def ram(self, name_or_addr: str | int, width: int = 1) -> int:
        a = symbols()[name_or_addr] if isinstance(name_or_addr, str) else name_or_addr
        v = 0
        for k in range(width):
            v = (v << 8) | self.periph.mem[a + k]
        return v

    def injector_pulses(self, group: str, since: int = 0) -> list[int]:
        """Open times (µs) of injector group ``#10`` or ``#20`` for pulses starting after ``since``."""
        return [off - on for on, off in self.engine.inj[group] if on >= since]

    def spark_advance(self, since: int = 0) -> list[float]:
        """Crank degrees BTDC of each spark after ``since``.

        Each spark is measured against the next NE falling edge, which is 10° BTDC; one NE
        period is 180° of crank.
        """
        e = self.engine
        out = []
        falls = e.falls
        j = 0
        for s in e.sparks:
            if s < since:
                continue
            while j < len(falls) and falls[j] < s:
                j += 1
            if j == 0 or j >= len(falls):
                continue
            period = falls[j] - falls[j - 1]
            nxt = falls[j]
            prev = falls[j - 1]
            # nearest reference edge: spark before the edge = advance beyond 10°
            if nxt - s <= s - prev:
                out.append(10 + (nxt - s) * 180 / period)
            else:
                out.append(10 - (s - prev) * 180 / period)
        return out

    def dwell_us(self, since: int = 0) -> list[int]:
        e = self.engine
        out = []
        for s in e.sparks:
            if s < since:
                continue
            starts = [d for d in e.dwell_starts if d < s]
            if starts:
                out.append(s - starts[-1])
        return out
