"""Chip-in-isolation test: compare the real D151801 with the emulator (docs/hardware/chip_diff_test.md).

    # run the test on the Pico (chip on the breadboard) and save the log
    PYTHONPATH=analysis uv run --with pyserial python -m emu.chipdiff capture /dev/ttyACM0 run.log
    # compare the log with the emulator
    PYTHONPATH=analysis uv run python -m emu.chipdiff analyse run.log

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

from .cboard import CSimulation
from .engine import ROOT
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
    c.add_argument("--phases", type=int, default=6)
    a = sub.add_parser("analyse")
    a.add_argument("log", type=Path)
    a.add_argument("--offset", type=int)
    a.add_argument("--until", type=int, help="compare only the first N cycles")
    args = ap.parse_args()
    if args.cmd == "capture":
        capture(args.port, args.phases, args.out)
        return 0
    log = parse_log(args.log.read_text())
    if log.summary:
        print(log.summary)
    offset, res = analyse(log, args.offset, args.until)
    print(report(offset, res))
    return 0 if all(r.ok for r in res) else 1


if __name__ == "__main__":
    sys.exit(main())
