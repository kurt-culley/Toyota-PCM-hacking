// The emulated D151801: HD6301 core + peripherals + 64 KB memory image, stepped the same way
// as analysis/emu/sim.py's Simulation.step (one instruction, then advance peripheral time by
// its cycles, then take the highest-priority pending interrupt).

#ifndef BOARD_H
#define BOARD_H

#include <stdint.h>

#include "d151801.h"
#include "hd6301.h"

typedef struct {
    hd6301_t cpu;
    d151801_t io;
    uint8_t mem[0x10000];
    uint16_t rom_base;
    d_next_event_fn next_ev;
    d_run_event_fn run_ev;
    void *ev_ctx;
    uint32_t irq_counts[8];  // per vector, index (vector - $FFF0) / 2
} board_t;

// Load the ROM image (ending at $FFFF) and reset the CPU.
void board_init(board_t *b, const uint8_t *rom, int len);
// One step; returns -1 if the CPU is about to take the TRAP vector (undefined opcode).
int board_step(board_t *b);

#endif
