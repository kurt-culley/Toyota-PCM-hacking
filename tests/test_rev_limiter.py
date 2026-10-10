"""Bluetop rev limiter: what its two constants do, run on the whole ROM in the simulator.

[ROM:$F42A] ldd #$7B79   -> A = $7B reloads SatCount_98 on each IGF echo, B = $79 reloads SatCount_97
[ROM:$F431] ldx deltaNE; [ROM:$F433] cpx #$0FD6 (operand at $F434);
            bcs (above the limit: skip the reload); stab SatCount_97
[ROM:$F43A] the $FFE1 helper then increments both counters (saturating at $FF), every NE pass.
[ROM:$F1F0] any counter >= $80 (or byte_4C bit 7) stops injection.

So below the limit SatCount_97 sits at reload + 1, and fuel stops once it reaches $80.
"""

from __future__ import annotations

import pytest

from emu.engine import BLUETOP_ROM
from emu.sim import Simulation
from pcmre.checksum import TARGET, fix_checksum, rom_sum

LIMIT_ADDR = 0xF434  # cpx #$0FD6 operand: deltaNE (µs per 180°) at the limit; rpm = 30e6 / value
RELOAD_ADDR = 0xF42C  # ldd #$7B79 low byte: SatCount_97 reload


def patched(reload: int | None = None, limit: int | None = None) -> bytes:
    rom = bytearray(BLUETOP_ROM.read_bytes())
    assert rom[RELOAD_ADDR - 0xF000] == 0x79 and rom[LIMIT_ADDR - 0xF000 : LIMIT_ADDR - 0xF000 + 2] == b"\x0f\xd6"
    if reload is not None:
        rom[RELOAD_ADDR - 0xF000] = reload
    if limit is not None:
        rom[LIMIT_ADDR - 0xF000 : LIMIT_ADDR - 0xF000 + 2] = limit.to_bytes(2, "big")
    out = fix_checksum(bytes(rom))
    assert rom_sum(out) == TARGET
    return out


def running(rom: bytes, rpm: int, ms: int = 800) -> Simulation:
    s = Simulation(rom)
    s.inputs.rpm, s.inputs.idl, s.inputs.airflow_us = rpm, False, 900
    s.engine.update_sensors()
    s.run_ms(ms)
    return s


def fuel_pulses(s: Simulation, since: int) -> int:
    return len(s.injector_pulses("#10", since)) + len(s.injector_pulses("#20", since))


def counter_per_pass(s: Simulation, rpm: int, passes: int = 10) -> list[int]:
    s.inputs.rpm = rpm
    s.engine.update_sensors()
    seen, n = [], len(s.engine.falls)
    while len(s.engine.falls) < n + passes:
        s.step()
        if len(s.engine.falls) > n + len(seen):
            seen.append(s.ram("SatCount_97"))
    return seen


@pytest.mark.parametrize(("reload", "passes"), [(0x79, 6), (0x7C, 3), (0x7E, 1)])
def test_reload_sets_passes_above_limit_before_cut(reload, passes):
    """Passes above the limit before the cut = $80 - (reload + 1)."""
    seen = counter_per_pass(running(patched(reload), 7000, 500), 7600, 12)
    # Sampled at each NE edge, which is not aligned with the ROM's update, so a value can
    # appear twice; the counter itself steps by exactly one per pass above the limit.
    start = max(i for i, v in enumerate(seen) if v == reload + 1)  # the last below-limit value
    run = seen[start:]
    assert all(0 <= b - a <= 1 for a, b in zip(run, run[1:], strict=False)), [hex(v) for v in seen]
    assert set(range(reload + 1, 0x81)) <= set(run)
    assert 0x80 - (reload + 1) == passes


def test_reload_7f_cuts_fuel_at_every_rpm():
    """$7F + 1 = $80 on every pass, even below the limit: the engine would not run."""
    s = running(patched(0x7F), 3000)
    assert fuel_pulses(s, s.periph.now - 200_000) == 0
    s = running(patched(0x7E), 3000)
    assert fuel_pulses(s, s.periph.now - 200_000) > 0


def test_limit_constant_moves_the_limit():
    """$0EA6 = 3750 µs per 180° = 8000 rpm: 7600 rpm then runs uncut, 8200 rpm is cut."""
    rom = patched(limit=0x0EA6)
    s = running(rom, 7600)
    assert fuel_pulses(s, s.periph.now - 200_000) > 0
    s = running(rom, 8200)
    assert fuel_pulses(s, s.periph.now - 200_000) == 0
