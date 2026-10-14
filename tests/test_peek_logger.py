"""The Pico 2 W logger's link logic (hardware/peek-logger/firmware/src/link.h) against the
simulated ECU (analysis/emu/peek17140.py), plus the host decoder (pcmre.peeklog).

link.h is compiled for the host and called through ctypes, so the code under test is the
code that runs on the Pico. The simulated ECU's P23 follows the logger's TX line: low while
it holds the break, high otherwise.
"""

from __future__ import annotations

import ctypes
import shutil
import subprocess

import pytest

from emu.engine17140 import ROM_17140, Engine17140, Inputs17140
from emu.peek17140 import PeekHost
from emu.sim import Simulation
from pcmre.peeklog import parse
from pcmre.roundtrip import ROOT

CC = shutil.which("cc") or shutil.which("gcc")
pytestmark = pytest.mark.skipif(CC is None, reason="no host C compiler")
SRC = ROOT / "hardware/peek-logger/firmware/src"
TX_BREAK, TX_UART, TX_HIZ = range(3)
OFF, HOLD, POLL, LOST = range(4)
REC_NONE, REC_DATA, REC_MISS, REC_STATE = range(4)

SHIM = r"""
#include <stddef.h>
#include "link.h"
size_t link_size(void) { return sizeof(link_t); }
void shim_init(link_t *l) { link_init(l); }
void shim_step(link_t *l, uint32_t now, int vcc, int rx, link_out_t *o) { link_step(l, now, vcc != 0, rx, o); }
unsigned shim_set(link_t *l, const uint8_t *a, unsigned n) { return link_set_vars(l, a, n); }
"""


class Out(ctypes.Structure):
    _fields_ = [
        ("tx", ctypes.c_int),
        ("send", ctypes.c_int),
        ("rec", ctypes.c_int),
        ("addr", ctypes.c_uint8),
        ("word", ctypes.c_uint16),
        ("state", ctypes.c_int),
    ]


@pytest.fixture(scope="module")
def lib(tmp_path_factory):
    d = tmp_path_factory.mktemp("link")
    (d / "shim.c").write_text(SHIM)
    so = d / "link.so"
    subprocess.run([CC, "-shared", "-fPIC", "-O1", "-Wall", "-Wextra", "-Werror", f"-I{SRC}", "-o", str(so),
                    str(d / "shim.c")], check=True)  # fmt: skip
    return ctypes.CDLL(str(so))


class Logger:
    def __init__(self, lib, vars_: list[int] | None = None):
        self.lib = lib
        self.l = ctypes.create_string_buffer(lib.link_size())
        lib.shim_init(self.l)
        if vars_:
            arr = (ctypes.c_uint8 * len(vars_))(*vars_)
            self.kept = lib.shim_set(self.l, arr, len(vars_))
        self.o = Out()
        self.lines: list[str] = []
        self.states: list[int] = []

    def step(self, now: int, vcc: bool, rx: int = -1) -> Out:
        self.lib.shim_step(self.l, ctypes.c_uint32(now), int(vcc), rx, ctypes.byref(self.o))
        o = self.o
        if o.rec == REC_DATA:
            self.lines.append(f"D,{now // 1000},{o.addr:02X},{o.word:04X}")
        elif o.rec == REC_STATE:
            self.states.append(o.state)
        return o


def run(lib, seconds: float, rpm: int = 2000, kpa: float = 50, p23_pulled_high: bool = False, vars_=None):
    """Power the ECU and the logger together and run for ``seconds``; 100 us steps."""
    sim = Simulation(ROM_17140.read_bytes(), inputs=Inputs17140(rpm=rpm, map_kpa=kpa), engine=Engine17140)
    host = PeekHost(sim)
    lg = Logger(lib, vars_)
    seen = 0
    end = round(seconds * 1e6)
    while sim.periph.now < end:
        now = sim.periph.now
        rx = -1
        if seen < len(host.tx) and host.tx[seen][0] + 1280 <= now:  # byte fully on the wire
            rx = host.tx[seen][1]
            seen += 1
        o = lg.step(now, True, rx)
        low = o.tx == TX_BREAK and not p23_pulled_high
        if low:
            sim.periph.pins[1] &= ~0x08
        else:
            sim.periph.pins[1] |= 0x08
        if o.send >= 0:
            host.send(o.send)
        sim.run_until(now + 100)
    return sim, host, lg


def test_logger_brings_the_link_up_and_keeps_it(lib):
    sim, host, lg = run(lib, 3.0)
    assert lg.states[:2] == [HOLD, POLL]
    assert LOST not in lg.states
    assert host.enabled
    rows = parse(lg.lines)
    assert len(rows) > 10
    last = rows[-1]
    assert last["rpm [rpm]"] == pytest.approx(2000, abs=10)
    assert last["map_kpa [kPa, GUESS]"] == pytest.approx(50, abs=1)
    assert last["inj_pulse_us [us]"] == pytest.approx(sim.ram(0x88, 2), abs=50)


def test_logger_lets_go_of_the_line_when_the_ecu_never_answers(lib):
    # The board holds P23 high at reset (no break reaches the CPU): the link never starts.
    _, host, lg = run(lib, 0.6, p23_pulled_high=True)
    assert not host.enabled
    assert lg.states[-1] == LOST
    assert lg.o.tx == TX_HIZ


def test_unsafe_addresses_are_dropped(lib):
    lg = Logger(lib, [0x77, 0x0F, 0x12, 0xFF, 0x46, 0x02])
    assert lg.kept == 3  # $77, $46, $02


def test_ecu_power_off_returns_to_break(lib):
    lg = Logger(lib)
    lg.step(0, True)
    assert lg.step(300_000, True).tx == TX_UART
    assert lg.step(300_100, False).tx == TX_BREAK
