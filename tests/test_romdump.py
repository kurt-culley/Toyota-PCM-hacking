"""P3: the 6301 dump program and the reader's decode rule, run together in the emulator.

The bus model below plays the D151801 in mode 0: on-chip registers, RAM and the
Bluetop ROM (cap.bin) at $F000-$FFFF are internal; everything else, and the reset
vector during the window after RES rises, goes out to the reader. Each access is also
shown to ``ReaderDecode``, and an internal access the reader would drive is a bus
contention: the test fails on it.
"""

from __future__ import annotations

import pytest

from emu.cpu import HD6301
from pcmre.readerdecode import VECTOR_WINDOW, ReaderDecode
from pcmre.romdump import HEADER, PROGRAMS, assemble, header, parse_stream
from pcmre.roundtrip import ASL, ROOT

pytestmark = pytest.mark.skipif(not ASL.exists(), reason="asl not built (tools/setup_assemblers.sh)")

CAP = (ROOT / "TOYOTA Bluetop PCM/cap.bin").read_bytes()
CHAR_CYCLES = 16 * 10  # E/16 bit clock, 10 bits per NRZ character
MODE0_PORT2 = 0x10  # PC2-PC0 = 000, P24 (TX) idle high, straps P20-P22 low
RMCR, TRCSR, TDR = 0x10, 0x11, 0x13
TDRE, TE = 0x20, 0x02


class Mode0Chip:
    """The bus as the CPU core sees it, with the reader on the external side."""

    def __init__(self, rom: bytes, reader: ReaderDecode):
        self.rom = rom
        self.base = 0x10000 - len(rom)
        self.reader = reader
        self.cpu: HD6301 | None = None
        self.vector_window = True
        self.rmcr = 0
        self.trcsr = TDRE
        self.tdr_full = False
        self.shift_done = 0  # cycle the shift register empties
        self.tdre_seen = False
        self.sent: list[int] = []
        self.other_writes: list[tuple[int, int]] = []
        self.floating: list[int] = []
        self.contention: list[int] = []

    def internal(self, addr: int) -> bool:
        if self.vector_window and addr >= 0xFFFE:
            return False
        return addr < 0x100 or addr >= self.base

    def _sci(self) -> None:
        now = self.cpu.cycles
        if self.tdr_full and now >= self.shift_done:
            self.tdr_full = False
            self.shift_done = now + CHAR_CYCLES
        if not self.tdr_full:
            self.trcsr |= TDRE

    def read(self, addr: int) -> int:
        drive = self.reader.cycle(addr, read=True)
        if self.internal(addr):
            if drive is not None:
                self.contention.append(addr)
            if addr == 0x03:
                return MODE0_PORT2
            if addr == TRCSR:
                self._sci()
                self.tdre_seen = bool(self.trcsr & TDRE)
                return self.trcsr
            if addr >= self.base:
                return self.rom[addr - self.base]
            return 0
        if drive is None:
            self.floating.append(addr)
            return addr & 0xFF  # the address low byte left on the multiplexed bus
        return drive

    def write(self, addr: int, value: int) -> None:
        assert self.reader.cycle(addr, read=False) is None
        if addr == RMCR:
            self.rmcr = value
        elif addr == TRCSR:
            self.trcsr = (self.trcsr & 0xE0) | (value & 0x1F)
        elif addr == TDR:
            assert self.tdre_seen, "TDR written without first reading TDRE set"
            assert self.trcsr & TE, "TDR written before the transmitter was enabled"
            self.tdre_seen = False
            self.sent.append(value)
            self._sci()
            if self.cpu.cycles >= self.shift_done:  # shift register free: straight in
                self.shift_done = self.cpu.cycles + CHAR_CYCLES
            else:
                self.tdr_full = True
                self.trcsr &= ~TDRE
        else:
            self.other_writes.append((addr, value))


def run_dump(name: str, rom: bytes = CAP, max_steps: int = 2_000_000) -> Mode0Chip:
    reader = ReaderDecode(assemble(name))
    chip = Mode0Chip(rom, reader)
    cpu = HD6301(chip)
    chip.cpu = cpu
    reader.cycle(0xFFFF, read=True)  # cycles while RES is low: never driven
    reader.release_reset()
    reader.cycle(0xFFFF, read=True)  # the dummy cycle before the vector fetch
    cpu.reset()  # reads $FFFE, $FFFF
    chip.vector_window = False
    cpu.s = 0x0000  # never set by the program: a push would land outside RAM
    for _ in range(max_steps):
        if cpu.sleeping:
            break
        cpu.step()
    else:
        pytest.fail("program never reached SLP")
    return chip


@pytest.fixture(scope="module")
def dump() -> Mode0Chip:
    return run_dump("romdump")


def test_stream_is_mode_byte_then_rom(dump):
    cap = parse_stream(bytes(dump.sent))
    assert cap.mode == 0
    assert cap.rom == CAP


def test_no_contention_no_floating_reads(dump):
    assert dump.contention == []
    assert dump.floating == []


def test_only_sci_writes_no_stack(dump):
    assert dump.other_writes == []
    assert dump.rmcr == 0x04  # NRZ, internal clock, E/16
    assert dump.trcsr & TE


def test_ends_asleep_at_done(dump):
    page = assemble("romdump")
    pc = dump.cpu.pc
    assert dump.cpu.sleeping and page[(pc - 1) & 0xFF] == 0x1A  # just past an SLP


def test_run_time_at_250khz():
    """4097 characters at 15,625 baud: about 2.6 s, so a triple dump is under 10 s."""
    chip = run_dump("romdump")
    seconds = chip.cpu.cycles / 250_000
    assert 4097 * 640e-6 <= seconds < 3.0


def test_romsize_is_listen_only_above_c0xx():
    """$E000-$EFFF is external on a 4 KB chip: the reader must leave it floating."""
    chip = run_dump("romsize")
    assert chip.contention == []
    assert chip.floating == list(range(0xE000, 0xF000))
    cap = parse_stream(bytes(chip.sent), start=0xE000)
    assert cap.rom[0x1000:] == CAP
    assert cap.rom[:0x1000] == bytes(a & 0xFF for a in range(0xE000, 0xF000))


def test_bad_mode_rejected():
    with pytest.raises(ValueError, match="mode 2"):
        parse_stream(bytes([0x40]) + CAP)
    with pytest.raises(ValueError, match="expected 4097"):
        parse_stream(bytes([0x00]) + CAP[:-1])


# -- the decode rule on its own ------------------------------------------------------


def fresh() -> ReaderDecode:
    r = ReaderDecode(assemble("romdump"))
    r.release_reset()
    return r


def test_reset_sequence_serves_vector_once():
    r = fresh()
    assert r.cycle(0xFFFF, True) is None  # dummy
    assert r.cycle(0xFFFE, True) == 0xC0
    assert r.cycle(0xFFFF, True) == 0xC0
    assert r.cycle(0xC0C0, True) == 0x86  # first opcode
    # later vector-space reads are internal (dummy cycles, SLP): never driven
    assert r.cycle(0xFFFE, True) is None
    assert r.cycle(0xFFFF, True) is None


def test_window_closes_after_three_cycles():
    r = fresh()
    for _ in range(VECTOR_WINDOW):
        r.cycle(0xC0C0, True)
    assert r.cycle(0xFFFE, True) is None
    assert r.cycle(0xFFFF, True) is None


def test_ffff_alone_never_driven():
    r = fresh()
    assert r.cycle(0xFFFF, True) is None
    assert r.cycle(0xFFFF, True) is None


def test_never_drives_in_reset_on_writes_or_internal_space():
    r = ReaderDecode(assemble("romdump"))
    assert all(r.cycle(a, True) is None for a in (0xC0C0, 0xFFFE, 0xFFFF))  # RES low
    r.release_reset()
    assert r.cycle(0xC0C0, False) is None  # write
    for a in list(range(0x0000, 0x0100)) + list(range(0xF000, 0x10000)):
        assert r.cycle(a, True) is None, f"${a:04X}"
    r.assert_reset()
    assert r.cycle(0xC0C0, True) is None


def test_drives_whole_c0_page_only():
    r = fresh()
    for _ in range(VECTOR_WINDOW):
        r.cycle(0x0000, True)
    page = assemble("romdump")
    assert [r.cycle(0xC000 + i, True) for i in range(256)] == list(page)
    assert r.cycle(0xBFFF, True) is None and r.cycle(0xC100, True) is None


# -- generated firmware header -------------------------------------------------------


def test_header_is_current():
    assert HEADER.exists(), "run: PYTHONPATH=analysis uv run python -m pcmre.romdump --write"
    assert HEADER.read_text() == header(), "romdump.h is stale: run python -m pcmre.romdump --write"


def test_programs_listed():
    assert set(PROGRAMS) == {"romdump", "romsize"}
