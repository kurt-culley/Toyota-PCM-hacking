"""The C emulator (hardware/ecu-emu/core) driven from Python, for checking it against the simulator.

``CSimulation`` has the same interface as ``emu.sim.Simulation`` for the 17140, but the CPU,
the peripherals and the memory run in the C code the RP2350 firmware uses. The engine model
(``Engine17140``) is unchanged: it talks to ``CPeripherals``, which forwards pin changes and
reads into the C peripherals and keeps the engine's scheduled events. tests/test_d151801_c.py
runs both side by side and requires identical outputs.

The shared library is built with the host C compiler on first use (cached by source hash).
"""

from __future__ import annotations

import ctypes
import hashlib
import heapq
import shutil
import subprocess
from collections.abc import Callable
from functools import cache
from pathlib import Path

from .engine import ROOT
from .engine17140 import ROM_17140, Engine17140, Inputs17140

CORE = ROOT / "hardware/ecu-emu/core"
SOURCES = ("hd6301.c", "d151801.c", "board.c")
CACHE = ROOT / ".tools/ecu-emu"

SHIM = r"""
#include <stdlib.h>
#include "board.h"
board_t *cb_new(void) { return calloc(1, sizeof(board_t)); }
void cb_free(board_t *b) { free(b); }
void cb_setup(board_t *b, d_output_fn out, d_next_event_fn nxt, d_run_event_fn run) {
    b->io.on_output = out; b->io.ctx = b; b->next_ev = nxt; b->run_ev = run; b->ev_ctx = b;
}
void cb_init(board_t *b, const uint8_t *rom, int len) { board_init(b, rom, len); }
int cb_step(board_t *b) { return board_step(b); }
int64_t cb_now(board_t *b) { return b->io.now; }
uint64_t cb_cycles(board_t *b) { return b->cpu.cycles; }
uint16_t cb_pc(board_t *b) { return b->cpu.pc; }
uint8_t *cb_mem(board_t *b) { return b->mem; }
int cb_waiting(board_t *b) { return b->cpu.waiting || b->cpu.sleeping; }
uint32_t cb_irq_count(board_t *b, int i) { return b->irq_counts[i]; }
void cb_set_pin(board_t *b, int port, int bit, int level) { d_set_pin(&b->io, port, bit, level); }
void cb_is3(board_t *b) { d_is3_edge(&b->io); }
uint8_t cb_port_out(board_t *b, int i) { return d_port_out(&b->io, i); }
"""

OUTPUT_FN = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int64)
NEXT_FN = ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.c_void_p)
RUN_FN = ctypes.CFUNCTYPE(None, ctypes.c_void_p)


@cache
def library() -> ctypes.CDLL:
    cc = shutil.which("cc") or shutil.which("gcc")
    if cc is None:
        raise RuntimeError("no host C compiler")
    h = hashlib.sha256(SHIM.encode())
    for name in (*SOURCES, "hd6301.h", "d151801.h", "board.h", "hd6301_ops.inc"):
        h.update((CORE / name).read_bytes())
    so = CACHE / f"board-{h.hexdigest()[:16]}.so"
    if not so.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        shim = CACHE / "shim.c"
        shim.write_text(SHIM)
        tmp = so.with_suffix(".tmp")
        subprocess.run([cc, "-shared", "-fPIC", "-O2", "-Wall", "-Wextra", "-Werror", f"-I{CORE}", "-o", str(tmp),
                        str(shim), *(str(CORE / s) for s in SOURCES)], check=True)  # fmt: skip
        tmp.replace(so)
    lib = ctypes.CDLL(str(so))
    lib.cb_new.restype = ctypes.c_void_p
    for f in ("cb_free", "cb_setup", "cb_init", "cb_step", "cb_now", "cb_cycles", "cb_pc", "cb_mem", "cb_waiting",
              "cb_irq_count", "cb_set_pin", "cb_is3", "cb_port_out"):  # fmt: skip
        getattr(lib, f).argtypes = [ctypes.c_void_p] + {
            "cb_setup": [OUTPUT_FN, NEXT_FN, RUN_FN], "cb_init": [ctypes.c_char_p, ctypes.c_int],
            "cb_irq_count": [ctypes.c_int], "cb_set_pin": [ctypes.c_int] * 3, "cb_port_out": [ctypes.c_int],
        }.get(f, [])  # fmt: skip
    lib.cb_now.restype = ctypes.c_int64
    lib.cb_cycles.restype = ctypes.c_uint64
    lib.cb_pc.restype = ctypes.c_uint16
    lib.cb_mem.restype = ctypes.POINTER(ctypes.c_uint8 * 0x10000)
    lib.cb_irq_count.restype = ctypes.c_uint32
    lib.cb_port_out.restype = ctypes.c_uint8
    return lib


class CPeripherals:
    """The subset of ``emu.periph.Peripherals`` that Engine17140 and the simulation helpers use."""

    def __init__(self, lib: ctypes.CDLL, board: int):
        self.lib, self.b = lib, board
        self._events: list[tuple[int, int, Callable[[], None]]] = []
        self._seq = 0
        self.listeners: list[Callable[[str, int, int], None]] = []
        self.mem = lib.cb_mem(board).contents

    @property
    def now(self) -> int:
        return self.lib.cb_now(self.b)

    def at(self, t: int, fn: Callable[[], None]) -> None:
        self._seq += 1
        heapq.heappush(self._events, (t, self._seq, fn))

    def next_event_time(self) -> int | None:
        return self._events[0][0] if self._events else None

    def set_pin(self, port: int, bit: int, level: int) -> None:
        self.lib.cb_set_pin(self.b, port, bit, 1 if level else 0)

    def is3_falling_edge(self) -> None:
        self.lib.cb_is3(self.b)

    def _out(self, i: int) -> int:
        return self.lib.cb_port_out(self.b, i)

    # -- callbacks from C ---------------------------------------------------------------
    def _on_output(self, _ctx, port: int, bit: int, level: int, t: int) -> None:
        name = f"P{port}-{bit}"
        for fn in self.listeners:
            fn(name, level, t)

    def _next(self, _ctx) -> int:
        return self._events[0][0] if self._events else -1

    def _run(self, _ctx) -> None:
        _, _, fn = heapq.heappop(self._events)
        fn()


class CSimulation:
    """``emu.sim.Simulation`` for the 17140, running on the C emulator."""

    def __init__(self, rom: bytes | None = None, inputs: Inputs17140 | None = None, engine: type = Engine17140):
        self.lib = lib = library()
        self.rom = rom if rom is not None else ROM_17140.read_bytes()
        self.b = lib.cb_new()
        self.periph = CPeripherals(lib, self.b)
        # keep the C callbacks alive as long as the simulation
        self._cbs = (OUTPUT_FN(self.periph._on_output), NEXT_FN(self.periph._next), RUN_FN(self.periph._run))
        lib.cb_setup(self.b, *self._cbs)
        lib.cb_init(self.b, self.rom, len(self.rom))
        self.engine = engine(self.periph, self.rom, inputs, None)
        self.inputs = self.engine.inputs

    def __del__(self):
        if getattr(self, "b", None):
            self.lib.cb_free(self.b)
            self.b = None

    @property
    def cycles(self) -> int:
        return self.lib.cb_cycles(self.b)

    def irq_counts(self) -> dict[int, int]:
        return {0xFFF0 + 2 * i: n for i in range(8) if (n := self.lib.cb_irq_count(self.b, i))}

    def step(self) -> None:
        if self.lib.cb_step(self.b) < 0:
            raise RuntimeError(f"TRAP taken (undefined opcode) at cycle {self.periph.now}")

    def run_until(self, t: int) -> None:
        while self.periph.now < t:
            self.step()

    def run_ms(self, ms: float) -> None:
        self.run_until(self.periph.now + round(ms * 1000))

    def ram(self, addr: int, width: int = 1) -> int:
        v = 0
        for k in range(width):
            v = (v << 8) | self.periph.mem[addr + k]
        return v

    def injector_pulses(self, group: str, since: int = 0) -> list[int]:
        return [off - on for on, off in self.engine.inj[group] if on >= since]
