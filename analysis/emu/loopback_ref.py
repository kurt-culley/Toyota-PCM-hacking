"""Reference checksums for the real-time loopback test (hardware/ecu-emu/loopback).

    PYTHONPATH=analysis uv run python -m emu.loopback_ref --write

Runs the C emulator (``emu.cboard``) with the Python engine model through the fixed schedule
(``SCHEDULE``: cranking, idle with the throttle closed and open, 2000 and 5000 rpm, above the rev
limit, IGF missing, T terminal shorted; 6 s each), which the chip-in-isolation test also uses. For each 6 s phase it
records, over the measuring window (seconds 3-6 of the phase): the number of output-pin edges
and a CRC32 over every edge (port, bit, level, time), the injector pulses, and at the end of the
phase a CRC32 of RAM $40-$FF and RpmWord. The firmware computes the same numbers on the Pico
in real time and prints PASS when they are identical: the real-time emulator is then bit-exact
to the simulator. Writes ``hardware/ecu-emu/loopback/expected.h``.
"""

from __future__ import annotations

import argparse
import struct
import sys
import zlib
from typing import NamedTuple

from .cboard import CSimulation
from .engine import ROOT
from .engine17140 import Inputs17140

OUT = ROOT / "hardware/ecu-emu/loopback/expected.h"


class Phase(NamedTuple):
    rpm: int
    kpa: float
    tps: float
    idl: int = 0  # throttle idle contact closed (P1-6 low)
    igf: int = 1  # IGF echo after each spark
    tterm: int = 0  # T terminal shorted to E1 (P3-0 low)


# The schedule (v2): every operating condition the strict bench gate asks for, 6 s each.
SCHEDULE = (
    Phase(200, 100.0, 0.6, idl=1),  # cranking
    Phase(800, 35.0, 0.6, idl=1),  # warm idle, throttle closed
    Phase(800, 35.0, 0.6),  # idle speed, idle contact open
    Phase(2000, 50.0, 1.5),
    Phase(5000, 95.0, 4.0),
    Phase(7700, 95.0, 4.0),  # above the rev limit
    Phase(2000, 50.0, 1.5, igf=0),  # IGF missing: the ROM's safety cut
    Phase(800, 35.0, 0.6, idl=1, tterm=1),  # T terminal shorted (fixed timing, self-test)
)
ADC_START_DELAY = 20  # µs from the hold line rising to P20 rising (Engine17140.adc_start_delay)
# The ADC's fixed conversion time and the IGF delay for this schedule (Engine17140 defaults: 20 µs):
# 30 µs leaves the Pico room to react on time on the real chip.
ADC_OFFSET = 30
IGF_DELAY = 30
# The first schedule (chip runs 3-5, "chipdiff v1" logs): three points twice, P20 rising at once.
SCHEDULE_V1 = tuple(Phase(*p) for p in ((800, 35.0, 0.6), (2000, 50.0, 1.5), (5000, 95.0, 4.0)) * 2)
PHASE_US = 6_000_000
MEASURE_FROM_US = 3_000_000
PHASES = len(SCHEDULE)
SCENARIOS = tuple((p.rpm, p.kpa, p.tps) for p in SCHEDULE)  # (rpm, kPa, TPS volts) per phase


def simulate(schedule=SCHEDULE, adc_start_delay=ADC_START_DELAY, listener=None, until=None) -> CSimulation:
    """The emulator through ``schedule`` with the loopback's engine model, switching at exactly k x 6 s."""
    p0 = schedule[0]
    # p37=1 (A/C on) is the P3-7 level engine.h leaves the pin at. It only matters with the throttle
    # closed or T shorted.
    sim = CSimulation(inputs=Inputs17140(rpm=p0.rpm, map_kpa=p0.kpa, tps_v=p0.tps, p37=1, idl_closed=bool(p0.idl),
                                         test_terminal=bool(p0.tterm), igf=bool(p0.igf)))  # fmt: skip
    sim.engine.adc_start_delay = adc_start_delay
    if schedule is not SCHEDULE_V1:
        sim.engine.adc_offset, sim.engine.igf_delay = ADC_OFFSET, IGF_DELAY
    sim.engine.update_sensors()
    if listener:
        sim.periph.listeners.append(listener)

    def switch(k: int) -> None:
        ph = schedule[k]
        i = sim.inputs
        i.rpm, i.map_kpa, i.tps_v, i.igf = ph.rpm, ph.kpa, ph.tps, bool(ph.igf)
        i.idl_closed, i.test_terminal = bool(ph.idl), bool(ph.tterm)
        sim.periph.set_pin(3, 0, 0 if ph.tterm else 1)  # only the switch pins: G and NE keep their state
        sim.periph.set_pin(1, 6, 0 if ph.idl else 1)

    for k in range(1, len(schedule)):
        sim.periph.at(k * PHASE_US, lambda k=k: switch(k))
    if until is not None:
        sim.run_until(until)
    return sim


def run() -> list[dict]:
    edges: list[tuple[int, int, int, int]] = []
    sim = simulate(listener=lambda name, level, t: edges.append((int(name[1]), int(name[3]), level, t)))
    out = []
    for k, ph in enumerate(SCHEDULE):
        start = k * PHASE_US
        sim.run_until(start + PHASE_US)
        w0, w1 = start + MEASURE_FROM_US, start + PHASE_US
        win = [e for e in edges if w0 <= e[3] < w1]
        crc = 0
        for port, bit, level, t in win:
            crc = zlib.crc32(struct.pack("<BBBq", port, bit, level, t), crc)
        inj = [off - on for on, off in sim.engine.inj["Tout1"] if w0 <= on < w1]
        out.append({
            "phase": ph, "edges": len(win), "edge_crc": crc,
            "ram_crc": zlib.crc32(bytes(sim.periph.mem[0x40:0x100])), "rpm_word": sim.ram(0x77, 2),
            "inj_n": len(inj), "inj_sum": sum(inj),
        })  # fmt: skip
        edges = [e for e in edges if e[3] >= w1]
    return out


def header(rows: list[dict]) -> str:
    lines = [
        "/* Generated by `python -m emu.loopback_ref --write` from the C emulator and the Python",
        " * engine model. Do not edit. One row per 6 s phase (the schedule, emu.loopback_ref.SCHEDULE);",
        " * the measuring window is seconds 3-6. */",
        f"#define REF_PHASE_US {PHASE_US}",
        f"#define REF_MEASURE_FROM_US {MEASURE_FROM_US}",
        f"#define REF_PHASES {len(rows)}",
        f"#define REF_ADC_START_DELAY {ADC_START_DELAY}",
        f"#define REF_ADC_OFFSET {ADC_OFFSET}",
        f"#define REF_IGF_DELAY {IGF_DELAY}",
        "typedef struct { int rpm; double kpa, tps; int idl, igf, tterm; uint32_t edges, edge_crc, ram_crc;",
        "                 int rpm_word; uint32_t inj_n, inj_sum; } ref_t;",
        "static const ref_t REF[REF_PHASES] = {",
    ]
    for r in rows:
        ph = r["phase"]
        lines.append(
            f"    {{{ph.rpm}, {ph.kpa!r}, {ph.tps!r}, {ph.idl}, {ph.igf}, {ph.tterm}, {r['edges']}u, "
            f"0x{r['edge_crc']:08X}u, 0x{r['ram_crc']:08X}u, {r['rpm_word']}, {r['inj_n']}u, {r['inj_sum']}u}},"
        )
    lines.append("};")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    src = header(run())
    if a.write:
        OUT.write_text(src)
        print(f"wrote {OUT.relative_to(ROOT)}")
    else:
        print(src)
    return 0


if __name__ == "__main__":
    sys.exit(main())
