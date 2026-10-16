// HD6301 CPU core in C, for the RP2350 CPU-replacement firmware (docs/emulator/design.md).
//
// A port of the MAME-verified Python core (src/pcmre/emu/cpu.py); the instruction switch is
// generated from the same opcode table (hd6301_ops.inc, pcmre.gen_hd6301_c), and
// tests/emu/test_hd6301_c.py checks this core against the Python one instruction by instruction.
// Peripherals are not part of the core: they sit behind the read/write callbacks and call
// hd6301_irq() / hd6301_nmi().

#ifndef HD6301_H
#define HD6301_H

#include <stdint.h>

#define HD6301_VEC_TRAP 0xFFEE
#define HD6301_VEC_SCI 0xFFF0
#define HD6301_VEC_TOF 0xFFF2
#define HD6301_VEC_OCF 0xFFF4
#define HD6301_VEC_ICF 0xFFF6
#define HD6301_VEC_IRQ1 0xFFF8
#define HD6301_VEC_SWI 0xFFFA
#define HD6301_VEC_NMI 0xFFFC
#define HD6301_VEC_RES 0xFFFE

typedef uint8_t (*hd6301_read_fn)(void *ctx, uint16_t addr);
typedef void (*hd6301_write_fn)(void *ctx, uint16_t addr, uint8_t value);

typedef struct {
    uint8_t a, b, cc;
    uint16_t x, s, pc;
    uint8_t waiting, sleeping, irq_inhibit;
    uint64_t cycles;  // E-clock cycles executed
    hd6301_read_fn read;
    hd6301_write_fn write;
    void *ctx;
    // Optional fast path: if set, addresses >= $20 are read straight from mem[], and writes
    // below rom_base go straight to mem[] (writes at or above rom_base are dropped). Only the
    // I/O registers $00-$1F go through the callbacks. NULL: every access uses the callbacks.
    uint8_t *mem;
    uint16_t rom_base;
    // Cycle counts per opcode and the cycle of each instruction's 1st/2nd data access
    // (hd6301_timing.inc). hd6301_init selects the HD6301 timing; the D151801 board uses MC6801.
    const uint8_t *cyc;
    const uint8_t (*acc)[2];
} hd6301_t;

void hd6301_init(hd6301_t *c, hd6301_read_fn rd, hd6301_write_fn wr, void *ctx);
void hd6301_reset(hd6301_t *c);
// 0: HD6301 handbook counts (default); 1: MC6801 counts (the D151801, emu.cpu.CYCLES_6801).
void hd6301_set_timing(hd6301_t *c, int mc6801);
// Execute one instruction; returns its E-clock cycles (0 while waiting or asleep).
int hd6301_step(hd6301_t *c);
// Request a maskable interrupt; returns 1 if taken. A masked request still ends SLP.
int hd6301_irq(hd6301_t *c, uint16_t vector);
void hd6301_nmi(hd6301_t *c);

#endif
