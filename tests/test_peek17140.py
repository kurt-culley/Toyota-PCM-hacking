"""The 17140's serial RAM-peek link in the whole-ROM simulator (docs/mr2/serial_link.md).

Pins down the protocol a logger must follow: P23 low at reset enables it, one address byte
in gives the word there back (high byte first), and about 1 s without a request switches
it off until the next reset.
"""

from __future__ import annotations

from functools import cache

from emu.engine17140 import Inputs17140
from emu.peek17140 import PeekHost, boot
from emu.sim import Simulation


@cache
def running() -> tuple[Simulation, PeekHost]:
    s, h = boot(Inputs17140(rpm=2000, map_kpa=50))
    s.run_ms(300)
    return s, h


def test_link_off_unless_p23_low_at_reset():
    s, h = boot(p23_low=False)
    s.run_ms(20)
    assert not h.enabled
    assert all(v == 0 for _, v in h.trcsr_writes)
    assert h.peek(0x77, timeout_us=10_000) is None


def test_link_on_with_rx_and_tx_only():
    _, h = running()
    assert h.trcsr_writes[1][1] == 0x0A  # RE + TE; no receive or transmit interrupt


def test_reply_is_the_ram_word_high_byte_first():
    s, h = running()
    for addr in (0x77, 0x46, 0x88):
        word, latency = h.peek(addr)
        # RpmWord and Load are re-read the instant the reply was sent; allow one update
        assert abs(word - s.ram(addr, 2)) <= 4
        assert latency < 12_000
    assert abs(h.peek(0x46)[0] - (4.98 * 50 + 98.6)) < 2  # Load at 50 kPa (docs/mr2/maps.md)


def test_switches_off_after_a_second_without_requests():
    s, h = boot(Inputs17140(rpm=2000, map_kpa=50))
    assert h.peek(0x77) is not None
    s.run_ms(2500)
    off = [t for t, v in h.trcsr_writes[2:] if v == 0]
    assert off and 1_000_000 < off[0] < 2_200_000
    assert not h.enabled
    assert h.peek(0x77, timeout_us=20_000) is None


def test_polling_twice_a_second_keeps_it_on():
    s, h = boot(Inputs17140(rpm=2000, map_kpa=50))
    for _ in range(6):
        assert h.peek(0x77) is not None
        s.run_ms(500)
    assert h.enabled


def test_polling_flat_out_leaves_spark_and_injection_alone():
    quiet, _ = boot(Inputs17140(rpm=5000, map_kpa=50))
    busy, h = boot(Inputs17140(rpm=5000, map_kpa=50))
    quiet.run_ms(400)
    busy.run_ms(400)
    t0 = busy.periph.now
    n = 0
    while busy.periph.now < t0 + 300_000:
        n += h.peek((0x77, 0x46, 0x53, 0x88)[n % 4]) is not None
    quiet.run_until(busy.periph.now)
    assert n > 30  # over 100 words a second even at 5000 rpm
    assert set(busy.engine.spark_tooth_offsets(t0)) == set(quiet.engine.spark_tooth_offsets(t0))
    pulses = busy.injector_pulses("Tout1", t0), quiet.injector_pulses("Tout1", t0)
    assert abs(max(pulses[0]) - max(pulses[1])) <= 20 and abs(min(pulses[0]) - min(pulses[1])) <= 20
