"""HD6301V1 on-chip peripherals plus the D151801's second timer channel.

This is the memory map the Bluetop ROM sees in single-chip mode 7:

    $00-$07  port DDRs and data registers (ports 1-4)
    $08-$0E  timer 1: TCSR1, free-running counter (FRC), OCR1, ICR1
    $0F      port 3 control/status (IS3 flag)
    $10-$13  SCI: RMCR, TRCSR, RDR, TDR
    $14      RAM control
    $18-$1E  timer 2 (D151801 extra): TCSR2 $18, OCR2 $1B, ICR2 $1D
    $40-$FF  internal RAM
    $F000-   mask ROM

Sources:
- Timer 1, SCI and port 3 behaviour follow the HD6301/HD6303 Series Handbook (1989),
  sections 2.5 and 2.6: TCSR bits ICF b7, OCF b6, TOF b5, EICI b4, EOCI b3, ETOI b2,
  IEDG b1, OLVL b0. Flags clear by reading TCSR with the flag set, then reading ICR
  (ICF), writing OCR (OCF) or reading the FRC (TOF). A write to the FRC high byte
  presets $FFF8; a following low-byte write loads the whole word.
- **Timer 2 is a GUESS** from how the ROM uses it: TCSR2 has the same bit layout as
  TCSR1, ICF2 shares the ICF vector, OCF2 shares the OCF vector, IC2's input is P1-0 and
  OC2's output is P1-1 [ROM:$F1B1, $F242, $F370, $F3B9]. Its edge bit, output level and
  flags are all used exactly as timer 1's are, and the whole ROM runs on that model
  (tests/test_sim.py).
- The SCI talks to the external ADC. The model answers a channel byte written to TDR
  while P3-6 is low with the bit-reversed 8-bit reading for that channel, ``adc_delay``
  cycles later (default 320, the time the ROM itself allows [ROM:$F404]). The ADC's
  real conversion time is unknown (GUESS).

The model is instruction-granular: the FRC advances by each instruction's cycle count
after it executes, and a register read during an instruction sees the FRC as it was at
the start of that instruction. External edges are timestamped to the cycle, so input
captures are exact.
"""

from __future__ import annotations

import heapq
from collections.abc import Callable
from dataclasses import dataclass, field

from .cpu import VEC_ICF, VEC_OCF, VEC_SCI, VEC_TOF

ICF, OCF, TOF, EICI, EOCI, ETOI, IEDG, OLVL = 0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01
RDRF, ORFE, TDRE, RIE, RE, TIE, TE = 0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02
IS3F = 0x80

# Register addresses
DDR1, DDR2, PORT1, PORT2, DDR3, DDR4, PORT3, PORT4 = range(8)
TCSR1, FRC_H, FRC_L, OCR1_H, OCR1_L, ICR1_H, ICR1_L, P3CSR = range(8, 16)
RMCR, TRCSR, RDR, TDR, RAMC = range(0x10, 0x15)
TCSR2, OCR2_H, OCR2_L, ICR2_H, ICR2_L = 0x18, 0x1B, 0x1C, 0x1D, 0x1E

MODE_BITS = 0xE0  # P2-7..5 read the mode latched at reset: mode 7 (single chip)


def bitrev8(v: int) -> int:
    return int(f"{v & 0xFF:08b}"[::-1], 2)


@dataclass
class Channel:
    """One input-capture / output-compare pair and its TCSR."""

    tcsr: int = 0
    ocr: int = 0xFFFF
    icr: int = 0
    armed: int = 0  # flags seen set by a TCSR read; the second step of the clear sequence clears them
    pin_in: int = 0  # level on the input-capture pin
    pin_out: int = 1  # output-compare flip-flop

    def read_tcsr(self) -> int:
        self.armed = self.tcsr & (ICF | OCF | TOF)
        return self.tcsr

    def write_tcsr(self, v: int) -> None:
        self.tcsr = (self.tcsr & 0xE0) | (v & 0x1F)

    def pending(self) -> int:
        """Interrupt-enabled flags that are set."""
        t = self.tcsr
        return (ICF if t & ICF and t & EICI else 0) | (OCF if t & OCF and t & EOCI else 0)


@dataclass(order=True)
class _Event:
    t: int
    seq: int
    fn: Callable[[], None] = field(compare=False)


class Peripherals:
    """Memory bus with the on-chip peripherals. Pass it to ``HD6301`` as its bus.

    External signals are set with ``set_pin`` or scheduled with ``at(t, fn)``; ``t`` is in
    E-clock cycles (µs at 1 MHz), on the same scale as ``now``.
    """

    def __init__(self, rom: bytes, rom_base: int = 0xF000):
        self.mem = bytearray(0x10000)
        self.mem[rom_base : rom_base + len(rom)] = rom
        self.rom_base = rom_base
        self.now = 0  # cycles since power-up
        self.frc_offset = 0  # FRC = (now + frc_offset) & 0xFFFF
        self._frc_hi_written = 0
        self.t1 = Channel()
        self.t2 = Channel()
        self.tof = 0  # TOF lives in TCSR1 only
        self.ddr = [0, 0, 0, 0]
        self.latch = [0, 0, 0, 0]
        # External pin levels (inputs); index 0..3 = ports 1..4. Default: pulled high.
        self.pins = [0xFF, 0xFF, 0xFF, 0xFF]
        self.p3csr = 0
        self._is3_armed = False
        self.rmcr = 0
        self.trcsr = TDRE
        self.rdr = 0
        self._sci_armed = 0
        self.adc = [0] * 8  # 8-bit reading returned for each ADC channel
        self.adc_delay = 320
        self.adc_log: list[tuple[int, int]] = []  # (time, channel) requests
        self._events: list[_Event] = []
        self._seq = 0
        # Output-pin listeners: fn(name, level, time). Names: "P1-1", "P2-1", "P4-0", "P4-7", ...
        self.listeners: list[Callable[[str, int, int], None]] = []
        self._last_out = [self._out(i) for i in range(4)]

    # -- time ------------------------------------------------------------------------
    @property
    def frc(self) -> int:
        return (self.now + self.frc_offset) & 0xFFFF

    def frc_at(self, t: int) -> int:
        return (t + self.frc_offset) & 0xFFFF

    def at(self, t: int, fn: Callable[[], None]) -> None:
        """Schedule ``fn`` at absolute cycle time ``t``."""
        self._seq += 1
        heapq.heappush(self._events, _Event(t, self._seq, fn))

    def next_event_time(self) -> int | None:
        return self._events[0].t if self._events else None

    def advance(self, n: int) -> None:
        """Advance time by ``n`` cycles: run due external events and output compares in time order."""
        end = self.now + n
        f0 = self.frc
        while True:
            t_oc = self._next_compare(end)
            t_ev = self._events[0].t if self._events and self._events[0].t <= end else None
            if t_oc is None and t_ev is None:
                break
            if t_ev is not None and (t_oc is None or t_ev < t_oc):
                ev = heapq.heappop(self._events)
                self.now = max(self.now, ev.t)
                ev.fn()
            else:
                self.now = t_oc
                self._compare_match()
        self.now = end
        if self.frc < f0 or n >= 0x10000:  # wrapped through $0000
            self.tof = 1

    def _next_compare(self, end: int) -> int | None:
        best = None
        for ch in (self.t1, self.t2):
            d = (ch.ocr - self.frc) & 0xFFFF
            if d == 0:
                continue  # already matched at this count
            if self.now + d <= end and (best is None or self.now + d < best):
                best = self.now + d
        return best

    def _compare_match(self) -> None:
        for ch in (self.t1, self.t2):
            if ch.ocr == self.frc:
                ch.tcsr |= OCF
                ch.pin_out = ch.tcsr & OLVL
                self._outputs_changed()

    # -- interrupts --------------------------------------------------------------------
    def irq_vector(self) -> int | None:
        """Highest-priority pending maskable interrupt vector (handbook: ICF > OCF > TOF > SCI)."""
        p1, p2 = self.t1.pending(), self.t2.pending()
        if (p1 | p2) & ICF:
            return VEC_ICF
        if (p1 | p2) & OCF:
            return VEC_OCF
        if self.tof and self.t1.tcsr & ETOI:
            return VEC_TOF
        if self.trcsr & RIE and self.trcsr & (RDRF | ORFE):
            return VEC_SCI
        return None

    # -- external inputs -----------------------------------------------------------------
    def set_pin(self, port: int, bit: int, level: int) -> None:
        """Drive external input pin P<port>-<bit> (port 1..4) to ``level``; handles capture edges and IS3."""
        i = port - 1
        mask = 1 << bit
        old = 1 if self.pins[i] & mask else 0
        level = 1 if level else 0
        self.pins[i] = (self.pins[i] | mask) if level else (self.pins[i] & ~mask)
        if old == level:
            return
        if (port, bit) == (2, 0):
            self._edge(self.t1, level)
        elif (port, bit) == (1, 0):
            self._edge(self.t2, level)

    def _edge(self, ch: Channel, level: int) -> None:
        ch.pin_in = level
        if bool(ch.tcsr & IEDG) == bool(level):
            ch.icr = self.frc
            ch.tcsr |= ICF

    def is3_falling_edge(self) -> None:
        """A falling edge on /IS3 (the IGF input) sets the IS3 flag."""
        self.p3csr |= IS3F

    # -- ports -----------------------------------------------------------------------------
    def _out(self, i: int) -> int:
        """Pin levels of port ``i`` (0..3) as driven by the chip (outputs) or seen from outside."""
        v = (self.latch[i] & self.ddr[i]) | (self.pins[i] & ~self.ddr[i] & 0xFF)
        if i == 0 and self.ddr[0] & 0x02:  # P1-1 is OC2's output (GUESS, D151801)
            v = (v & ~0x02) | (0x02 if self.t2.pin_out else 0)
        if i == 1:
            if self.ddr[1] & 0x02:  # P2-1 is OC1's output
                v = (v & ~0x02) | (0x02 if self.t1.pin_out else 0)
            v = (v & 0x1F) | MODE_BITS
        return v & 0xFF

    def _outputs_changed(self) -> None:
        for i in range(4):
            new = self._out(i)
            diff = (new ^ self._last_out[i]) & self.ddr[i]
            if i == 1:
                diff &= 0x1F
            self._last_out[i] = new
            if diff and self.listeners:
                for bit in range(8):
                    if diff & (1 << bit):
                        name = f"P{i + 1}-{bit}"
                        for fn in self.listeners:
                            fn(name, (new >> bit) & 1, self.now)

    # -- bus interface ----------------------------------------------------------------------
    def read(self, addr: int) -> int:
        if addr >= 0x20:
            return self.mem[addr]
        return self._read_io(addr)

    def write(self, addr: int, value: int) -> None:
        if addr >= 0x20:
            if addr < self.rom_base:
                self.mem[addr] = value
            return
        self._write_io(addr, value)

    def _read_io(self, a: int) -> int:
        if a in (PORT1, PORT2, PORT3, PORT4):
            i = {PORT1: 0, PORT2: 1, PORT3: 2, PORT4: 3}[a]
            if a == PORT3 and self._is3_armed:
                self.p3csr &= ~IS3F
                self._is3_armed = False
            return self._out(i)
        if a in (DDR1, DDR2, DDR3, DDR4):
            return 0xFF  # DDRs are write-only
        if a == TCSR1:
            v = self.t1.read_tcsr() | (TOF if self.tof else 0)
            if self.tof:
                self.t1.armed |= TOF
            return v
        if a == FRC_H:
            if self.t1.armed & TOF:
                self.tof = 0
                self.t1.armed &= ~TOF
            return self.frc >> 8
        if a == FRC_L:
            return self.frc & 0xFF
        if a == OCR1_H:
            return self.t1.ocr >> 8
        if a == OCR1_L:
            return self.t1.ocr & 0xFF
        if a == ICR1_H:
            return self._read_icr(self.t1) >> 8
        if a == ICR1_L:
            return self.t1.icr & 0xFF
        if a == P3CSR:
            self._is3_armed = bool(self.p3csr & IS3F)
            return self.p3csr
        if a == RMCR:
            return self.rmcr
        if a == TRCSR:
            self._sci_armed = self.trcsr & (RDRF | ORFE)
            return self.trcsr
        if a == RDR:
            if self._sci_armed:
                self.trcsr &= ~self._sci_armed
                self._sci_armed = 0
            return self.rdr
        if a == TCSR2:
            return self.t2.read_tcsr()
        if a == OCR2_H:
            return self.t2.ocr >> 8
        if a == OCR2_L:
            return self.t2.ocr & 0xFF
        if a == ICR2_H:
            return self._read_icr(self.t2) >> 8
        if a == ICR2_L:
            return self.t2.icr & 0xFF
        return self.mem[a]

    def _read_icr(self, ch: Channel) -> int:
        if ch.armed & ICF:
            ch.tcsr &= ~ICF
            ch.armed &= ~ICF
        return ch.icr

    def _write_io(self, a: int, v: int) -> None:
        if a in (DDR1, DDR2, DDR3, DDR4):
            self.ddr[{DDR1: 0, DDR2: 1, DDR3: 2, DDR4: 3}[a]] = v
            self._outputs_changed()
        elif a in (PORT1, PORT2, PORT3, PORT4):
            self.latch[{PORT1: 0, PORT2: 1, PORT3: 2, PORT4: 3}[a]] = v
            self._outputs_changed()
        elif a == TCSR1:
            self.t1.write_tcsr(v)
        elif a == FRC_H:
            self._frc_hi_written = v
            self._set_frc(0xFFF8)
        elif a == FRC_L:
            self._set_frc((self._frc_hi_written << 8) | v)
        elif a in (OCR1_H, OCR1_L, OCR2_H, OCR2_L):
            ch = self.t1 if a in (OCR1_H, OCR1_L) else self.t2
            if a in (OCR1_H, OCR2_H):
                ch.ocr = (v << 8) | (ch.ocr & 0xFF)
            else:
                ch.ocr = (ch.ocr & 0xFF00) | v
            if ch.armed & OCF:
                ch.tcsr &= ~OCF
                ch.armed &= ~OCF
        elif a == P3CSR:
            self.p3csr = (self.p3csr & IS3F) | (v & 0x7F)
        elif a == RMCR:
            self.rmcr = v
        elif a == TRCSR:
            self.trcsr = (self.trcsr & (RDRF | ORFE | TDRE)) | (v & 0x1F)
        elif a == TDR:
            self._transmit(v)
        elif a == TCSR2:
            self.t2.write_tcsr(v)
        else:
            self.mem[a] = v

    def _set_frc(self, value: int) -> None:
        self.frc_offset = (value - self.now) & 0xFFFF

    # -- SCI / external ADC --------------------------------------------------------------------
    def _transmit(self, v: int) -> None:
        if not self.trcsr & TE:
            return
        self.trcsr &= ~TDRE
        adc_selected = not (self._out(2) & 0x40)  # P3-6 low selects the ADC
        t = self.now + self.adc_delay

        def done() -> None:
            self.trcsr |= TDRE
            if adc_selected and self.trcsr & RE:
                ch = v & 0x07
                self.adc_log.append((self.now, ch))
                if self.trcsr & RDRF:
                    self.trcsr |= ORFE
                self.rdr = bitrev8(self.adc[ch])
                self.trcsr |= RDRF

        self.at(t, done)
