"""Engine and sensor stimulus for the Bluetop full-ROM simulation.

Every signal here is a model of what the ECU's input circuits deliver to the CPU pins.
The ROM fixes most of it; the rest is marked GUESS.

- **NE on IC2 (P1-0).** The ECU's SE056 interface chip turns the distributor's NE pickup
  into one falling edge per 180° of crank. The falling edge is the reference for the
  spark: with the T terminal shorted the ROM fires on it, and the factory spec for that
  state is 10° BTDC [ROM:$F2B1, $F814] [repair manual]. The period between falling edges
  is ``deltaNE = 30e6 / rpm`` µs. That relation fits the ROM's 7400 rpm rev-limit
  constant ($0FD6) [ROM:$F432], and tests/test_sim.py checks it against the ROM's own
  rpm variables. The high part of each period is ``ne_duty`` (default 50 %, GUESS).
- **G+ on P3-7.** Low around every fourth NE falling edge. The ROM resets its
  cylinder counter ``IC2LowCnt`` there and uses bit 1 of it to pick the injector group
  [ROM:$F320-$F330, $F239]. G+ phase relative to a real cylinder is GUESS.
- **Airflow on IC1 (P2-0).** The ROM measures ``SE056plstime = IC1 rising time - NE
  falling time`` [ROM:$F1C1]. So the airflow meter reaches the CPU as a delay after each
  NE falling edge, made by the SE056. The model sets P2-0 low at each NE rising edge and
  high ``airflow_us`` after the falling edge. How the SE056 turns airflow-meter volts into
  that delay is unknown, so scenarios set the delay directly (GUESS physical meaning).
- **IGF on /IS3.** The igniter confirms each spark. The model gives one falling /IS3
  edge per rising edge of /IGT (P2-1), which is the spark [ROM:$F370-$F3AE].
  ``igf=False`` simulates a dead igniter.
- **Analogue sensors** are read through the serial ADC: channel 0 TPS, 1 battery (+B ÷ 5),
  2 ThA, 3 ThW, 4 PWRr, 5 O2 [ROM:$FAB9 ldx #$0054 / abx]. The coolant reading is made
  by inverting the ROM's own linearisation table $FEF0, so the ROM sees the requested
  °F. Air temperature uses the same inverse: the factory curves for the two NTC sensors
  agree within their tolerances (analysis/sensors/), but the ECU's pull-up for ThA is
  GUESS.
- **Digital inputs** (Port 4): P4-2 IDL (**high** = throttle closed at the CPU pin, LIKELY;
  cap.asm says active low, see below), P4-3 A/C (high = on),
  P4-4 STA (high while cranking), P4-5 T terminal (low = shorted), P4-6 SPD. Port 3
  bit 4 is an SE056 status line that the ROM expects high [ROM:$FC85].

IDL polarity: the ROM's idle state is ``byte_95`` negative. It counts up while P4-2 is
high [ROM:$F9F7-$FA39]. Three uses agree that negative means *throttle closed*: the idle
advance branch and its idle-stability term [ROM:$F834], the airflow fallback of 800 µs
(against 1600 µs off idle) when the airflow signal fails [ROM:$F1E8], and the
async "tip-in" injection when the throttle opens from that state above 2500 rpm
[ROM:$FA19]. So at the CPU pin P4-2 is high with the throttle closed; the ECU's input
buffer presumably inverts the IDL contact (closed to E2). LIKELY.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

from pcmre.tables import lookup_1d

from .periph import Peripherals

ROOT = Path(__file__).resolve().parents[2]
BLUETOP_ROM = ROOT / "TOYOTA Bluetop PCM/cap.bin"


@dataclass
class EngineInputs:
    """What the engine and its sensors present to the ECU. Change fields at any time."""

    rpm: float = 0.0  # 0 = not turning
    airflow_us: float = 800.0  # SE056 delay after each NE falling edge (µs)
    ne_duty: float = 0.5
    coolant_f: float = 176.0  # °F, as the ROM sees it after $FEF0
    intake_f: float = 68.0
    battery_v: float = 14.0
    tps_raw: int = 0x1A
    pwr_raw: int = 0x00
    o2_v: float = 0.45
    idl: bool = True  # throttle closed
    ac: bool = False
    starter: bool = False
    t_shorted: bool = False
    igf: bool = True


@cache
def _thw_inverse(rom: bytes) -> tuple[int, ...]:
    """For each °F 0..255, the raw ADC value whose $FEF0 linearisation is closest."""
    table = rom[0xFEF0 - 0xF000 : 0xFEF0 - 0xF000 + 17]
    out = []
    lin = [lookup_1d(table, raw, entry=0xFF28) for raw in range(256)]
    for f in range(256):
        out.append(min(range(256), key=lambda r: (abs(lin[r] - f), r)))
    return tuple(out)


def thw_raw(rom: bytes, degf: float) -> int:
    return _thw_inverse(rom)[max(0, min(255, round(degf)))]


def volts_raw(v: float, full_scale: float = 5.0) -> int:
    return max(0, min(255, round(v * 255 / full_scale)))


class Engine:
    """Drives the ECU's input pins from ``inputs`` and listens to its outputs."""

    def __init__(self, periph: Peripherals, rom: bytes, inputs: EngineInputs | None = None):
        self.p = periph
        self.rom = rom
        self.inputs = inputs or EngineInputs()
        self.edge = 0  # NE falling-edge count
        self.falls: list[int] = []  # NE falling-edge times
        self.sparks: list[int] = []  # /IGT rising edges
        self.dwell_starts: list[int] = []  # /IGT falling edges
        self.inj: dict[str, list[tuple[int, int]]] = {"#10": [], "#20": []}  # (on, off) times
        self._inj_on: dict[str, int | None] = {"#10": None, "#20": None}
        self._running = False
        periph.listeners.append(self._on_output)
        self.update_sensors()

    # -- sensors ---------------------------------------------------------------------------
    def update_sensors(self) -> None:
        i = self.inputs
        p = self.p
        p.adc[0] = i.tps_raw & 0xFF
        p.adc[1] = volts_raw(i.battery_v, 25.0)
        p.adc[2] = thw_raw(self.rom, i.intake_f)
        p.adc[3] = thw_raw(self.rom, i.coolant_f)
        p.adc[4] = i.pwr_raw & 0xFF
        p.adc[5] = volts_raw(i.o2_v)
        p.set_pin(4, 2, 1 if i.idl else 0)  # high = closed at the CPU pin (see module notes)
        p.set_pin(4, 3, 1 if i.ac else 0)
        p.set_pin(4, 4, 1 if i.starter else 0)
        p.set_pin(4, 5, 0 if i.t_shorted else 1)
        p.set_pin(3, 4, 1)
        if i.rpm > 0 and not self._running:
            self._running = True
            self.p.at(self.p.now + 1000, self._fall)

    # -- crank signals ----------------------------------------------------------------------
    def period(self) -> int:
        return round(30e6 / self.inputs.rpm)

    def _fall(self) -> None:
        if self.inputs.rpm <= 0:
            self._running = False
            return
        p, t, T = self.p, self.p.now, self.period()
        self.edge += 1
        self.falls.append(t)
        p.set_pin(1, 0, 0)  # NE falling edge -> IC2
        if self.edge % 4 == 0:
            p.at(t + T // 4, lambda: p.set_pin(3, 7, 1))  # G+ back high
        af = round(self.inputs.airflow_us)
        p.at(t + af, lambda: p.set_pin(2, 0, 1))  # SE056 airflow edge -> IC1
        p.at(t + round(T * (1 - self.inputs.ne_duty)), self._rise)
        p.at(t + T, self._fall)

    def _rise(self) -> None:
        p = self.p
        p.set_pin(2, 0, 0)  # airflow line back low, ready for the next measurement
        p.set_pin(1, 0, 1)  # NE rising edge -> IC2
        if (self.edge + 1) % 4 == 0:
            p.set_pin(3, 7, 0)  # G+ low across the next falling edge

    # -- outputs ------------------------------------------------------------------------------
    def _on_output(self, name: str, level: int, t: int) -> None:
        if name == "P2-1":  # /IGT
            if level:
                self.sparks.append(t)
                if self.inputs.igf:
                    self.p.at(t + 20, self.p.is3_falling_edge)
            else:
                self.dwell_starts.append(t)
        elif name in ("P4-7", "P1-1"):  # injector #10 (software), #20 (OC2); low = open
            g = "#10" if name == "P4-7" else "#20"
            if level == 0:
                self._inj_on[g] = t
            elif self._inj_on[g] is not None:
                self.inj[g].append((self._inj_on[g], t))
                self._inj_on[g] = None
