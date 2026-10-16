"""Host side of the 17140's serial RAM-peek link, for the whole-ROM simulator.

The ROM's protocol [ROM:$F33B-$F343, $F403-$F41E, $F62E-$F641] (docs/mr2/serial_link.md):

- **Enable:** at reset the SCI is switched on (TRCSR = RE + TE, no interrupts) only if P23,
  the SCI receive pin (chip pin 11), is **low**. RMCR = $05: NRZ, internal clock, E/128,
  so 7812.5 baud at E = 1 MHz. A tool holds its TX line low (a break) through power-up.
- **Request:** one byte, the address. **Reply:** the word at that address, high byte first.
  X is 0 when SerialPeek runs, so only $00-$FF can be read; nothing can be written.
- **Keep-alive:** about once a second the ROM checks DiagFlags ($CC) bit 0, which a reply
  sets, and switches the SCI off if no request was answered since the last check. It is
  only switched on again by a reset.

``PeekHost`` replaces the simulator's SCI transmit hook (which models the Bluetop's serial
ADC) with a UART line model: characters take 10 bits x 128 E cycles.
"""

from __future__ import annotations

from . import periph as P
from .engine17140 import ROM_17140, Engine17140, Inputs17140
from .sim import Simulation

CHAR_US = 10 * 128  # one 8N1 character at E/128, E = 1 MHz


class PeekHost:
    def __init__(self, sim: Simulation):
        self.sim = sim
        p = self.p = sim.periph
        self.tx: list[tuple[int, int]] = []  # (time, byte) sent by the ECU
        self.trcsr_writes: list[tuple[int, int]] = []
        p._transmit = self._ecu_transmit
        write_io = p._write_io

        def _write_io(a: int, v: int) -> None:
            if a == P.TRCSR:
                self.trcsr_writes.append((p.now, v))
            write_io(a, v)

        p._write_io = _write_io

    @property
    def enabled(self) -> bool:
        return bool(self.p.trcsr & P.RE)

    def _ecu_transmit(self, v: int) -> None:
        p = self.p
        if not p.trcsr & P.TE:
            return
        p.trcsr &= ~P.TDRE
        self.tx.append((p.now, v))
        p.at(p.now + CHAR_US, lambda: setattr(p, "trcsr", p.trcsr | P.TDRE))

    def send(self, byte: int) -> None:
        """Start sending one byte to the ECU; it lands in RDR one character time later."""
        p = self.p

        def arrive() -> None:
            if p.trcsr & P.RE:
                if p.trcsr & P.RDRF:
                    p.trcsr |= P.ORFE
                p.rdr = byte & 0xFF
                p.trcsr |= P.RDRF

        p.at(p.now + CHAR_US, arrive)

    def peek(self, addr: int, timeout_us: int = 50_000) -> tuple[int, int] | None:
        """Request ``addr`` and wait for the 2-byte reply: (word, latency in us), or None."""
        s, n0, t0 = self.sim, len(self.tx), self.p.now
        self.send(addr)
        while len(self.tx) < n0 + 2 and self.p.now < t0 + timeout_us:
            s.step()
        if len(self.tx) < n0 + 2:
            return None
        s.run_until(self.tx[n0 + 1][0] + CHAR_US)  # the second byte has left the ECU
        return self.tx[n0][1] << 8 | self.tx[n0 + 1][1], self.p.now - t0


def boot(inputs: Inputs17140 | None = None, p23_low: bool = True, hold_ms: float = 5) -> tuple[Simulation, PeekHost]:
    """Power up the 17140 with P23 held low (``p23_low``) for ``hold_ms``, then release it to idle."""
    sim = Simulation(rom=ROM_17140.read_bytes(), inputs=inputs or Inputs17140(), engine=Engine17140)
    host = PeekHost(sim)
    if p23_low:
        sim.periph.pins[1] &= ~0x08
    sim.cpu.reset()
    sim.run_ms(hold_ms)
    sim.periph.pins[1] |= 0x08
    return sim, host
