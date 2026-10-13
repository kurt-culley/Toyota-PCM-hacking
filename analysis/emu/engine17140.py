"""Engine and sensor stimulus for the MR2 89661-17140 ROM (P4 step 3).

The 17140 is wired differently from the Bluetop (docs/mr2/architecture.md, maps.md), so it
has its own model. Every signal is what the ECU's input circuits are assumed to deliver to
the CPU pins; the ROM fixes most of it, the rest is marked GUESS.

- **NE on IC2 (P1-0), rising edges.** TCSR2 is written with IEDG = 1 [ROM:$F2DD, $FE42].
  The ROM counts 6 edges per group and turns three 2-edge intervals into RpmWord (rpm x
  0.32); that only gives a sensible engine speed if **one edge is 30 degrees of crank**
  (24 per 720 degrees, the 4A-GE's NE rotor), LIKELY.
- **G on P3-5.** At every 6th edge the ROM restarts its count only while P3-5 is high
  [ROM:$FEC7-$FEDF]. The model raises P3-5 for one tooth around every 6th edge (each 180
  degrees). Whether the ECU sees G once per 180 or 720 degrees is GUESS; the ROM only
  needs it at the group boundary.
- **Timed ADC on IC1 (P2-0), falling edge.** PORT1 bit 5 high holds the converter; when the
  OC1 tick clears it [ROM:$FE8B] the conversion starts, and P2-0 falls ``adc_k * volts +
  adc_offset`` us later, which the ROM captures (TCSR1 IEDG = 0) and times against its
  start stamp [ROM:$FC32]. P2-0 goes high again when bit 5 is set for the next channel.
  The channel is PORT1 bits 2-4 at the start. The linear time-per-volt converter and its
  constants are GUESS; the ROM subtracts channel 0 and divides by channel 7 (the
  reference), so the results depend on volts relative to the reference, not on adc_k.
  **Channel 7 is taken as the 5 V sensor supply (GUESS)**, which makes the readings
  ratiometric like the sensors.
- **Outputs.** P1-1 is OC2's pin: the ROM schedules it from the NE edge plus the spark
  delay [ROM:$FF85-$FF94], so its **falling edge is taken as the spark** (IGT high =
  dwell, LIKELY). P2-1 is OC1's pin (Tout1), logged as the injector drive (LIKELY; the
  active level is read from the logs).
- **IGF.** Each spark gets an IS3 echo 20 us later, as on the Bluetop.
- **Switch inputs.** P3-0 low (the ROM uses fixed timing when it is high [ROM:$F7F6]), P3-4 =
  ``p34`` (jumper J8: map select), P3-3 vehicle-speed pulses off, P3-6 low (no self-test),
  P1-7 high, PORT4 inputs high (trim code 11 = 0). Their meanings are LIKELY/GUESS as noted
  in docs/mr2/maps.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from .engine import ROOT
from .periph import Peripherals
from .sensors import pim_volts

ROM_17140 = ROOT / "AW11 MR2 PCM/89661-17140.bin"
DEG_PER_TOOTH = 30


@dataclass
class Inputs17140:
    rpm: float = 0.0
    map_kpa: float = 100.0
    tps_v: float = 0.6  # closed throttle (GUESS sensor range)
    vaf_v: float = 2.5  # mixture-adjust resistor mid position
    batt_v: float = 3.5  # +B as seen at the ADC pin (GUESS divider)
    thw_v: float = 0.5  # coolant sensor pin volts (hot engine, GUESS)
    tha_v: float = 2.5  # intake air sensor pin volts (about 20 C, GUESS)
    ref_v: float = 5.0  # channel 7 reference (GUESS: the 5 V supply)
    zero_v: float = 0.0  # channel 0
    p34: int = 1  # jumper J8 level: 1 -> map $F1EF, 0 -> map $F25D
    test_terminal: bool = False  # P3-0 high: fixed timing
    igf: bool = True
    ne_duty: float = 0.5


class Engine17140:
    adc_k = 200.0  # us per volt (GUESS)
    adc_offset = 20  # us (GUESS)

    def __init__(self, periph: Peripherals, rom: bytes, inputs: Inputs17140 | None = None, profile=None):
        self.p = periph
        self.rom = rom
        self.inputs = inputs or Inputs17140()
        self.edge = 0
        self.teeth: list[int] = []  # NE rising-edge times
        self.falls = self.teeth  # alias used by Simulation.spark_advance-style helpers
        self.sparks: list[int] = []  # P1-1 falling edges
        self.dwell_starts: list[int] = []  # P1-1 rising edges
        self.hw_sparks: list[int] = []
        self.inj: dict[str, list[tuple[int, int]]] = {"Tout1": [], "Tout1_high": []}
        self._tout_edge: tuple[int, int] | None = None
        self.adc_log: list[tuple[int, int, int]] = []  # (start time, channel, end time)
        self._adc_hold = True
        self._running = False
        periph.listeners.append(self._on_output)
        self.update_sensors()

    # -- sensors ------------------------------------------------------------------------------
    def channel_volts(self, ch: int) -> float:
        i = self.inputs
        return [i.zero_v, pim_volts(i.map_kpa), i.tps_v, i.vaf_v, i.batt_v, i.thw_v, i.tha_v, i.ref_v][ch]

    def update_sensors(self) -> None:
        p, i = self.p, self.inputs
        p.set_pin(3, 0, 1 if i.test_terminal else 0)
        p.set_pin(3, 4, 1 if i.p34 else 0)
        p.set_pin(3, 6, 0)
        p.set_pin(3, 5, 0)
        if i.rpm > 0 and not self._running:
            self._running = True
            p.at(p.now + 1000, self._tooth)

    # -- crank ---------------------------------------------------------------------------------
    def tooth_period(self) -> int:
        return round(60e6 / self.inputs.rpm / (720 / DEG_PER_TOOTH) * 2)  # 30 deg of crank

    def _tooth(self) -> None:
        if self.inputs.rpm <= 0:
            self._running = False
            return
        p, t, T = self.p, self.p.now, self.tooth_period()
        self.edge += 1
        g = self.edge % 6 == 0
        if g:
            p.set_pin(3, 5, 1)  # G window around this edge
            p.at(t + T // 2, lambda: p.set_pin(3, 5, 0))
        self.teeth.append(t)
        p.set_pin(1, 0, 1)  # NE rising edge -> IC2
        p.at(t + round(T * self.inputs.ne_duty), lambda: p.set_pin(1, 0, 0))
        p.at(t + T, self._tooth)

    # -- outputs -------------------------------------------------------------------------------
    def _on_output(self, name: str, level: int, t: int) -> None:
        p = self.p
        if name == "P1-5":  # ADC hold (high) / start (falling)
            if level:
                self._adc_hold = True
                p.set_pin(2, 0, 1)
            elif self._adc_hold:
                self._adc_hold = False
                ch = (p._out(0) >> 2) & 7
                dt = max(1, round(self.adc_offset + self.adc_k * self.channel_volts(ch)))
                self.adc_log.append((t, ch, t + dt))
                p.at(t + dt, lambda: (not self._adc_hold) and p.set_pin(2, 0, 0))
        elif name == "P1-1":  # IGT
            if level == 0:
                self.sparks.append(t)
                if self.inputs.igf:
                    p.at(t + 20, p.is3_falling_edge)
            else:
                self.dwell_starts.append(t)
        elif name == "P2-1":  # Tout1: injector drive (level logged both ways)
            if self._tout_edge is not None:
                t0, lvl = self._tout_edge
                self.inj["Tout1" if lvl == 0 else "Tout1_high"].append((t0, t))
            self._tout_edge = (t, level)

    # -- measurements --------------------------------------------------------------------------
    def spark_tooth_offsets(self, since: int = 0) -> list[float]:
        """Each spark as degrees after the most recent NE rising edge (the ROM's own reference)."""
        out = []
        j = 0
        for s in self.sparks:
            if s < since:
                continue
            while j + 1 < len(self.teeth) and self.teeth[j + 1] <= s:
                j += 1
            if j + 1 >= len(self.teeth) or self.teeth[j] > s:
                continue
            T = self.teeth[j + 1] - self.teeth[j]
            g_phase = self._edge_index(j)
            out.append(g_phase * DEG_PER_TOOTH + (s - self.teeth[j]) * DEG_PER_TOOTH / T)
        return out

    def _edge_index(self, j: int) -> int:
        """Edge number within the 6-edge (180 degree) group: 0 at the G edge."""
        return (j + 1) % 6
