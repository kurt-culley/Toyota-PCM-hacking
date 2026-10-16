"""Chip-in-isolation test: compare the real D151801 with the emulator (docs/procedures/chip_test.md).

    # run the test on the Pico (chip on the breadboard) and save the log
    uv run --extra serial python -m pcmre.emu.chipdiff capture /dev/ttyACM0 run.log
    # compare the log with the emulator
    uv run python -m pcmre.emu.chipdiff analyse run.log

The firmware (hardware/ecu-emu/chipdiff) logs every change of the chip's pins, one line per
change: ``<cycle hex> <pin word hex>``, where the cycle counts E cycles from the release of
/RES and the pin word holds both the inputs as the Pico applied them and the outputs as the
chip drove them (GPIO bit numbers, ``CD_PINS`` in chipdiff.h).

``analyse`` replays exactly the logged inputs into the C emulator (``emu.cboard``) and compares
every output edge, pin by pin. The emulator's time zero may differ from the chip's by a few
cycles (reset latency), so the input offset is found first by searching a short prefix. Each
pin may also show a constant sampling latency. PASS means: on every output pin the same edges,
in the same order, each a constant number of cycles from the emulator's.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pcmre.paths import ROOT

from .cboard import CSimulation
from .engine17140 import Inputs17140

HEADER = ROOT / "hardware/ecu-emu/chipdiff/chipdiff.h"


@dataclass(frozen=True)
class Pin:
    gpio: int
    port: int  # 0 = the IS3 strobe (SC1)
    bit: int
    is_input: bool  # chip input (driven by the Pico)
    name: str


def pins() -> list[Pin]:
    out = []
    for m in re.finditer(r"X\((\d+), (\d), (\d), (IN|OUT)\)\s*/\*\s*(\S+)", HEADER.read_text()):
        g, port, bit = int(m[1]), int(m[2]), int(m[3])
        out.append(Pin(g, port, bit, m[4] == "IN", m[5]))
    return out


PINS = pins()
IN_MASK = sum(1 << p.gpio for p in PINS if p.is_input)
OUT_MASK = sum(1 << p.gpio for p in PINS if not p.is_input)
BY_PORTBIT = {(p.port, p.bit): p for p in PINS if not p.is_input}


@dataclass
class Log:
    changes: list[tuple[int, int]]  # (cycle, pin word), first at cycle 0
    end: int  # cycles run
    summary: str = ""
    meta: list[str] = field(default_factory=list)


def parse_log(text: str) -> Log:
    changes: list[tuple[int, int]] = []
    end, summary, meta = 0, "", []
    for line in text.splitlines():
        line = line.strip()
        if m := re.fullmatch(r"([0-9a-f]+) ([0-9a-f]+)", line):
            changes.append((int(m[1], 16), int(m[2], 16)))
        elif line.startswith("END"):
            summary = line
            if m := re.search(r"cycles=(\d+)", line):
                end = int(m[1])
        elif line.startswith("#"):
            meta.append(line)
    if not changes:
        raise ValueError("no pin-change lines in the log")
    return Log(changes, end or changes[-1][0] + 1, summary, meta)


def chip_edges(log: Log, until: int) -> dict[int, list[tuple[int, int]]]:
    """Output edges of the chip as (cycle, level), per GPIO; outputs start high (pull-ups)."""
    edges: dict[int, list[tuple[int, int]]] = {p.gpio: [] for p in PINS if not p.is_input}
    prev = OUT_MASK
    for k, w in log.changes:
        if k >= until:
            break
        ch = (w ^ prev) & OUT_MASK
        for g in edges:
            if ch >> g & 1:
                edges[g].append((k, w >> g & 1))
        prev = w
    return edges


class ReplayEngine:
    """Feeds the logged inputs to the emulator at (cycle - offset); nothing else."""

    def __init__(self, periph, changes: list[tuple[int, int]], offset: int, until: int):
        self.inputs = Inputs17140()
        self.p = periph
        periph.set_pin(3, 6, 0)  # the P36 strap to GND on the breadboard
        prev = IN_MASK  # the emulator's pins start high
        for k, w in changes:
            if k >= until:
                break
            w &= IN_MASK
            if w != prev:
                if k == 0:
                    self._apply(prev, w)
                else:
                    periph.at(max(0, k - offset), lambda a=prev, b=w: self._apply(a, b))
            prev = w

    def _apply(self, old: int, new: int) -> None:
        ch = old ^ new
        for p in PINS:  # ascending GPIO, as the C harness applies them
            if p.is_input and ch >> p.gpio & 1:
                level = new >> p.gpio & 1
                if p.port == 0:
                    if not level:
                        self.p.is3_falling_edge()
                else:
                    self.p.set_pin(p.port, p.bit, level)


def emulator_edges(log: Log, offset: int, until: int) -> dict[int, list[tuple[int, int]]]:
    edges: dict[int, list[tuple[int, int]]] = {p.gpio: [] for p in PINS if not p.is_input}
    level = {g: 1 for g in edges}

    def on_out(name: str, lv: int, t: int) -> None:
        p = BY_PORTBIT.get((int(name[1]), int(name[3])))
        if p and lv != level[p.gpio]:
            level[p.gpio] = lv
            edges[p.gpio].append((t, lv))

    sim = CSimulation(engine=lambda periph, rom, inputs, profile: ReplayEngine(periph, log.changes, offset, until))
    sim.periph.listeners.append(on_out)
    if sim.lib.cb_run_until(sim.b, until - offset) < 0:
        raise RuntimeError("emulator took the TRAP vector")
    return edges


@dataclass
class PinResult:
    pin: Pin
    chip_n: int
    emu_n: int
    latency: Counter
    matched: int  # edges matching (same level, the pin's first latency) before the first divergence
    first_bad: tuple[int, int] | None  # (chip cycle, emulator time) of the first divergence

    @property
    def ok(self) -> bool:
        return self.first_bad is None and self.chip_n == self.emu_n and len(self.latency) <= 1


def compare(chip: dict, emu: dict, margin_end: int) -> list[PinResult]:
    res = []
    for p in PINS:
        if p.is_input:
            continue
        a = [e for e in chip[p.gpio] if e[0] < margin_end]
        b = [e for e in emu[p.gpio] if e[0] < margin_end]
        lat: Counter = Counter()
        matched, bad, first = 0, None, None
        for (ka, la), (tb, lb) in zip(a, b, strict=False):
            d = ka - tb
            lat[d] += 1
            if first is None:
                first = d
            if bad is None:
                if la == lb and d == first:
                    matched += 1
                else:
                    bad = (ka, tb)
        if bad is None and len(a) != len(b):
            n = min(len(a), len(b))
            bad = (a[n][0] if n < len(a) else -1, b[n][0] if n < len(b) else -1)
        res.append(PinResult(p, len(a), len(b), lat, matched, bad))
    return res


def score(res: list[PinResult]) -> int:
    return sum(r.matched for r in res)


def find_offset(log: Log, span: int = 300_000, search: range = range(-16, 17)) -> tuple[int, int]:
    until = min(span, log.end)
    chip = chip_edges(log, until)
    best = max(search, key=lambda o: (score(compare(chip, emulator_edges(log, o, until), until - 2000)), -abs(o)))
    return best, until


def analyse(log: Log, offset: int | None = None, until: int | None = None) -> tuple[int, list[PinResult]]:
    if offset is None:
        offset, _ = find_offset(log)
    end = min(until or log.end, log.end)
    margin = end - 2000  # edges near the end may be cut off on one side
    return offset, compare(chip_edges(log, end), emulator_edges(log, offset, end), margin)


def report(offset: int, res: list[PinResult]) -> str:
    lines = [f"input offset: {offset} E cycles (emulator time = chip cycle - offset)", ""]
    lines.append(f"{'pin':6} {'chip':>7} {'emu':>7}  latency (cycles: count)      first divergence")
    for r in res:
        lat = ", ".join(f"{d}: {n}" for d, n in sorted(r.latency.items())[:4]) or "-"
        bad = "" if r.first_bad is None else f"chip {r.first_bad[0]}, emu {r.first_bad[1]}"
        lines.append(f"{r.pin.name:6} {r.chip_n:7} {r.emu_n:7}  {lat:28} {bad}")
    bads = [r.first_bad[0] for r in res if r.first_bad and r.first_bad[0] >= 0]
    verdict = all(r.ok for r in res)
    lines.append("")
    if verdict:
        lines.append("PASS: every output edge matches the emulator (constant latency per pin)")
    else:
        where = f" (first at chip cycle {min(bads)})" if bads else ""
        lines.append(f"FAIL: the emulator differs from the chip{where}")
    return "\n".join(lines)


# -- closed loop: per-phase behaviour of the chip and of the emulator running free --------------
def phase_stats(ne: list[int], sparks: list[int], inj: list[tuple[int, int]], ph: int) -> dict:
    """Sparks, spark offset after the NE edge, and injector pulses in the measuring window of phase ``ph``."""
    from .loopback_ref import MEASURE_FROM_US, PHASE_US

    a, b = ph * PHASE_US + MEASURE_FROM_US, (ph + 1) * PHASE_US
    sp = [t for t in sparks if a <= t < b]
    offs = []
    for t in sp:
        prev = max((n for n in ne if n <= t), default=None)
        if prev is not None:
            offs.append(t - prev)
    pulses, on = [], None
    for t, lv in inj:
        if a <= t < b:
            if lv == 0:
                on = t
            elif on is not None:
                pulses.append(t - on)
                on = None
    return {"sparks": len(sp), "offset": (min(offs), max(offs)) if offs else None, "pulses": len(pulses),
            "pulse": (min(pulses), round(sum(pulses) / len(pulses)), max(pulses)) if pulses else None}  # fmt: skip


def schedule_of(log: Log):
    """The schedule a log ran: v1 (runs 3-5: three points twice, P20 rising at once) or the current one."""
    from . import loopback_ref as L

    v1 = any(m.startswith("# chipdiff v1") for m in log.meta)
    return (L.SCHEDULE_V1, 0) if v1 else (L.SCHEDULE, L.ADC_START_DELAY)


def schedule_sim(log: Log, listener, until: int) -> CSimulation:
    """The emulator running closed loop through the log's schedule (emu.loopback_ref.simulate)."""
    from .loopback_ref import simulate

    sched, delay = schedule_of(log)
    return simulate(sched, delay, listener, until)


def closed_loop(log: Log) -> dict[str, tuple[int, int, Counter]]:
    """Every output edge of the chip against the emulator running closed loop through the same schedule.

    The emulator gets on-time engine reactions from its own outputs; with ``late=0`` the chip got
    the same, so the two should agree edge for edge (at each pin's constant sampling offset).
    Returns pin -> (chip edges, emulator edges, Counter of chip - emulator offsets).
    """
    em: dict[int, list[tuple[int, int]]] = {p.gpio: [] for p in PINS if not p.is_input}
    lvl = {g: 1 for g in em}

    def on(name: str, lv: int, t: int) -> None:
        p = BY_PORTBIT.get((int(name[1]), int(name[3])))
        if p and lv != lvl[p.gpio]:
            lvl[p.gpio] = lv
            em[p.gpio].append((t, lv))

    schedule_sim(log, on, log.end)
    chip = chip_edges(log, log.end)
    out = {}
    for p in PINS:
        if not p.is_input:
            a, b = chip[p.gpio], em[p.gpio]
            out[p.name] = (len(a), len(b), Counter(x[0] - y[0] for x, y in zip(a, b, strict=False) if x[1] == y[1]))
    return out


def summary(log: Log) -> str:
    """The chip's log against the emulator running closed loop with the same engine model (as in the car).

    Unlike ``analyse``, the emulator gets its own on-time engine reactions, so this shows whether the two
    behave alike (spark timing, injector pulses) rather than whether they match edge for edge.
    """
    from .loopback_ref import PHASE_US

    g = {p.name: p.gpio for p in PINS}
    ne, sp, inj, prev = [], [], [], None
    for k, w in log.changes:
        if prev is not None:
            ch = w ^ prev
            if ch >> g["P10"] & 1 and w >> g["P10"] & 1:
                ne.append(k)
            if ch >> g["P11"] & 1 and not w >> g["P11"] & 1:
                sp.append(k)
            if ch >> g["P21"] & 1:
                inj.append((k, w >> g["P21"] & 1))
        prev = w
    phases = log.end // PHASE_US
    sched, _ = schedule_of(log)
    esp, einj = [], []

    def on(n: str, lv: int, t: int) -> None:
        if n == "P1-1" and not lv:
            esp.append(t)
        if n == "P2-1":
            einj.append((t, lv))

    sim = schedule_sim(log, on, phases * PHASE_US)
    lines = ["phase  rpm    sparks chip/emu  spark offset chip/emu  pulses chip/emu  pulse min/mean/max chip | emu"]
    for ph in range(phases):
        c, e = phase_stats(ne, sp, inj, ph), phase_stats(sim.engine.teeth, esp, einj, ph)
        off = f"{c['offset']}/{e['offset']}"
        lines.append(f"{ph + 1:5}  {sched[ph].rpm:4}   {c['sparks']:6}/{e['sparks']:<6}   {off:>24}"
                     f"   {c['pulses']:5}/{e['pulses']:<5}   {c['pulse']} | {e['pulse']}")  # fmt: skip
    lines += ["", "closed loop, edge for edge (chip - emulator offset: count; a pin is exact if it has one offset):"]
    for name, (nc, ne_, lat) in closed_loop(log).items():
        top = ", ".join(f"{d}: {n}" for d, n in lat.most_common(3))
        exact = (
            "EXACT"
            if nc == ne_ and len(lat) == 1
            else f"{lat.most_common(1)[0][1] if lat else 0}/{nc} at the main offset"
        )
        lines.append(f"  {name:4} {nc:6}/{ne_:<6} {exact:28} {top}")
    return "\n".join(lines)


def capture(port: str, phases: int, out: Path) -> None:
    import serial  # pyserial, only needed for a live capture

    with serial.Serial(port, 115200, timeout=30) as s, out.open("w") as f:
        s.write(f"run {phases}\r".encode())
        n = 0
        while True:
            line = s.readline().decode(errors="replace")
            if not line:
                raise TimeoutError("no output from the Pico for 30 s")
            f.write(line)
            n += 1
            if n % 20000 == 0:
                print(f"{n} lines", file=sys.stderr)
            if line.startswith(("END", "ABORT")):
                print(line.strip())
                return


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture")
    c.add_argument("port")
    c.add_argument("out", type=Path)
    from . import loopback_ref as L

    c.add_argument("--phases", type=int, default=len(L.SCHEDULE))
    a = sub.add_parser("analyse")
    a.add_argument("log", type=Path)
    a.add_argument("--offset", type=int)
    a.add_argument("--until", type=int, help="compare only the first N cycles")
    sm = sub.add_parser("summary", help="per-phase behaviour: the chip vs the emulator running closed loop")
    sm.add_argument("log", type=Path)
    args = ap.parse_args()
    if args.cmd == "capture":
        capture(args.port, args.phases, args.out)
        return 0
    log = parse_log(args.log.read_text())
    if log.summary:
        print(log.summary)
    if args.cmd == "summary":
        print(summary(log))
        return 0
    offset, res = analyse(log, args.offset, args.until)
    print(report(offset, res))
    return 0 if all(r.ok for r in res) else 1


if __name__ == "__main__":
    sys.exit(main())
