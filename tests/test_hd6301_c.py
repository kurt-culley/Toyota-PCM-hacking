"""The C HD6301 core (hardware/ecu-emu/core) against the MAME-verified Python core.

Two checks, both through ctypes on a host build of the same C files the RP2350 firmware uses:
- every opcode (all 256, undefined ones trap) on random registers and memory: final
  registers, flags, cycles, wait/sleep state and every memory write must match;
- the 17140 ROM from reset for 200 000 instructions on the firmware's fast memory path, with
  deterministic pseudo-random port reads and periodic interrupt requests: the register state
  must match after every step.
Plus a staleness check on the generated instruction switch.
"""

from __future__ import annotations

import ctypes
import random
import shutil
import subprocess

import pytest

from emu.cpu import HD6301
from emu.engine17140 import ROM_17140
from pcmre.gen_hd6301_c import OUT, OUT_TIMING, build, build_timing
from pcmre.roundtrip import ROOT

CC = shutil.which("cc") or shutil.which("gcc")
pytestmark = pytest.mark.skipif(CC is None, reason="no host C compiler")
CORE = ROOT / "hardware/ecu-emu/core"
VECTORS = (0xFFF0, 0xFFF2, 0xFFF4, 0xFFF6, 0xFFF8)

SHIM = r"""
#include <stdint.h>
#include <string.h>
#include "hd6301.h"

static uint32_t mix(uint32_t seed, uint32_t addr) {
    uint32_t h = seed * 0x9E3779B1u + addr * 0x85EBCA77u;
    h ^= h >> 15; h *= 0x2C1B3C6Du; h ^= h >> 12; h *= 0x297A2D39u; h ^= h >> 15;
    return h;
}

/* ---- random single-instruction cases: memory = mix(seed, addr) unless written ---- */
static uint32_t g_seed; static uint16_t g_opaddr; static uint8_t g_op;
static uint16_t w_addr[64]; static uint8_t w_val[64]; static int w_n;
static uint8_t lazy_rd(void *ctx, uint16_t a) {
    (void)ctx;
    for (int i = w_n - 1; i >= 0; i--) if (w_addr[i] == a) return w_val[i];
    if (a == g_opaddr) return g_op;
    return (uint8_t)mix(g_seed, a);
}
static void lazy_wr(void *ctx, uint16_t a, uint8_t v) {
    (void)ctx;
    if (w_n < 64) { w_addr[w_n] = a; w_val[w_n] = v; }
    w_n++;
}

typedef struct { uint8_t a, b, cc; uint16_t x, s, pc; uint8_t waiting, sleeping; int cycles; } state_t;

int one(uint32_t seed, uint8_t op, state_t *st, int irq_vec, uint16_t *wa, uint8_t *wv) {
    hd6301_t c; hd6301_init(&c, lazy_rd, lazy_wr, 0);
    g_seed = seed; g_opaddr = st->pc; g_op = op; w_n = 0;
    c.a = st->a; c.b = st->b; c.cc = (uint8_t)(st->cc | 0xC0); c.x = st->x; c.s = st->s; c.pc = st->pc;
    int n = hd6301_step(&c);
    if (irq_vec) hd6301_irq(&c, (uint16_t)irq_vec);
    st->a = c.a; st->b = c.b; st->cc = c.cc; st->x = c.x; st->s = c.s; st->pc = c.pc;
    st->waiting = c.waiting; st->sleeping = c.sleeping; st->cycles = (int)c.cycles; (void)n;
    for (int i = 0; i < w_n && i < 64; i++) { wa[i] = w_addr[i]; wv[i] = w_val[i]; }
    return w_n;
}

/* ---- whole-ROM trace: flat memory, pseudo-random reads of $00-$1F ---- */
static uint8_t *g_mem; static uint32_t g_io;
static uint8_t flat_rd(void *ctx, uint16_t a) {
    (void)ctx;
    if (a >= 0x20) return g_mem[a];
    uint8_t v = (uint8_t)mix(g_io++, a);
    return a == 0x03 ? (uint8_t)(v | 0xE0) : v; /* PORT2 mode bits: mode 7 */
}
static void flat_wr(void *ctx, uint16_t a, uint8_t v) { (void)ctx; if (a < 0xF000) g_mem[a] = v; }

int trace(uint8_t *mem, int steps, int irq_every, uint32_t *out) {
    hd6301_t c; hd6301_init(&c, flat_rd, flat_wr, 0);
    static const uint16_t vecs[5] = {0xFFF0, 0xFFF2, 0xFFF4, 0xFFF6, 0xFFF8};
    g_mem = mem; g_io = 0;
    c.mem = mem; c.rom_base = 0xF000; /* the firmware's fast path: only $00-$1F via callbacks */
    hd6301_reset(&c);
    for (int i = 0; i < steps; i++) {
        if (c.waiting || c.sleeping) c.sleeping = 0, c.waiting = 0;
        hd6301_step(&c);
        if (irq_every && i % irq_every == irq_every - 1) hd6301_irq(&c, vecs[(i / irq_every) % 5]);
        out[2 * i] = (uint32_t)c.pc << 16 | c.x;
        out[2 * i + 1] = (uint32_t)c.a << 24 | (uint32_t)c.b << 16 | (uint32_t)c.cc << 8 | (c.s & 0xFF);
    }
    return 0;
}
"""


def mix(seed: int, addr: int) -> int:
    m = 0xFFFFFFFF
    h = (seed * 0x9E3779B1 + addr * 0x85EBCA77) & m
    h ^= h >> 15
    h = (h * 0x2C1B3C6D) & m
    h ^= h >> 12
    h = (h * 0x297A2D39) & m
    h ^= h >> 15
    return h


class State(ctypes.Structure):
    _fields_ = [("a", ctypes.c_uint8), ("b", ctypes.c_uint8), ("cc", ctypes.c_uint8), ("x", ctypes.c_uint16),
                ("s", ctypes.c_uint16), ("pc", ctypes.c_uint16), ("waiting", ctypes.c_uint8),
                ("sleeping", ctypes.c_uint8), ("cycles", ctypes.c_int)]  # fmt: skip


@pytest.fixture(scope="module")
def lib(tmp_path_factory):
    d = tmp_path_factory.mktemp("hd6301c")
    (d / "shim.c").write_text(SHIM)
    so = d / "core.so"
    subprocess.run([CC, "-shared", "-fPIC", "-O2", "-Wall", "-Wextra", "-Werror", f"-I{CORE}", "-o", str(so),
                    str(d / "shim.c"), str(CORE / "hd6301.c")], check=True)  # fmt: skip
    return ctypes.CDLL(str(so))


class LazyBus:
    def __init__(self, seed: int, op_addr: int, op: int):
        self.seed, self.mem, self.writes = seed, {op_addr: op}, []

    def read(self, addr: int) -> int:
        if addr not in self.mem:
            self.mem[addr] = mix(self.seed, addr) & 0xFF
        return self.mem[addr]

    def write(self, addr: int, value: int) -> None:
        self.mem[addr] = value
        self.writes.append((addr, value))


def test_generated_switch_is_current():
    assert OUT.read_text() == build(), "stale: rerun python -m pcmre.gen_hd6301_c --write"
    assert OUT_TIMING.read_text() == build_timing(), "stale: rerun python -m pcmre.gen_hd6301_c --write"


@pytest.mark.parametrize("op", range(256))
def test_every_opcode_matches_the_python_core(lib, op):
    rng = random.Random(0x6301 + op)
    for case in range(48):
        seed = rng.getrandbits(32)
        a, b, cc = rng.getrandbits(8), rng.getrandbits(8), rng.getrandbits(6)
        x, s, pc = rng.getrandbits(16), rng.getrandbits(16), rng.getrandbits(16)
        irq = VECTORS[case % 5] if case % 3 == 0 else 0
        bus = LazyBus(seed, pc, op)
        py = HD6301(bus)
        py.a, py.b, py.cc, py.x, py.s, py.pc = a, b, cc, x, s, pc
        py.step()
        if irq:
            py.irq(irq)
        st = State(a, b, cc, x, s, pc, 0, 0, 0)
        wa, wv = (ctypes.c_uint16 * 64)(), (ctypes.c_uint8 * 64)()
        n = lib.one(ctypes.c_uint32(seed), ctypes.c_uint8(op), ctypes.byref(st), irq, wa, wv)
        got = (st.a, st.b, st.cc & 0x3F, st.x, st.s, st.pc, st.waiting, st.sleeping, st.cycles)
        want = (py.a, py.b, py.cc & 0x3F, py.x, py.s, py.pc, py.waiting, py.sleeping, py.cycles)
        assert got == want, f"op ${op:02X} case {case}: C {got} != Python {want}"
        assert [(wa[i], wv[i]) for i in range(n)] == bus.writes, f"op ${op:02X} case {case}: writes differ"


def test_17140_rom_runs_identically_for_200k_instructions(lib):
    rom = ROM_17140.read_bytes()
    steps, irq_every = 200_000, 97
    mem = (ctypes.c_uint8 * 0x10000)()
    ctypes.memmove(ctypes.addressof(mem) + 0xF000, rom, len(rom))
    out = (ctypes.c_uint32 * (2 * steps))()
    lib.trace(mem, steps, irq_every, out)

    pymem = bytearray(0x10000)
    pymem[0xF000:] = rom
    io = [0]

    class Bus:
        def read(self, a: int) -> int:
            if a < 0x20:
                v = mix(io[0], a) & 0xFF
                io[0] += 1
                return v | 0xE0 if a == 0x03 else v  # PORT2 mode bits: mode 7
            return pymem[a]

        def write(self, a: int, v: int) -> None:
            if a < 0xF000:
                pymem[a] = v

    cpu = HD6301(Bus())
    cpu.reset()
    pcs = set()
    for i in range(steps):
        cpu.waiting = cpu.sleeping = False
        cpu.step()
        if i % irq_every == irq_every - 1:
            cpu.irq(VECTORS[(i // irq_every) % 5])
        want0 = cpu.pc << 16 | cpu.x
        want1 = cpu.a << 24 | cpu.b << 16 | cpu.cc << 8 | (cpu.s & 0xFF)
        assert (out[2 * i], out[2 * i + 1]) == (want0, want1), f"diverged at step {i}, PC ${cpu.pc:04X}"
        pcs.add(cpu.pc)
    assert len(pcs) > 400  # the trace covers a good part of the program (483 distinct PCs)
