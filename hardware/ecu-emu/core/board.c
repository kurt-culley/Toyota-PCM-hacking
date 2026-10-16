// See board.h.

#include "board.h"

#define IRQ_WINDOW_DEFAULT 2


// I/O registers are read and written at their own bus cycle within the instruction (the
// MC6801 accesses data in its last cycles), so pins, the counter and flags change when the real
// chip's do: bring peripheral time up to that cycle first. As emu.periph._sync_access.
static void sync_access(board_t *b) {
    if (b->insn_start < 0) return;
    int64_t t = b->insn_start + b->insn_acc[b->insn_n_acc < 1 ? b->insn_n_acc : 1];
    b->insn_n_acc++;
    if (t > b->io.now) d_advance(&b->io, t - b->io.now, b->next_ev, b->run_ev, b->ev_ctx);
}

static uint8_t io_read(void *ctx, uint16_t a) {
    board_t *b = ctx;
    sync_access(b);
    return d_read(&b->io, a);
}

static void io_write(void *ctx, uint16_t a, uint8_t v) {
    board_t *b = ctx;
    sync_access(b);
    d_write(&b->io, a, v);
}

void board_init(board_t *b, const uint8_t *rom, int len) {
    d_output_fn on_output = b->io.on_output;  // keep callbacks set by the host
    d_tx_fn on_tx = b->io.on_tx;
    d_ddr_fn on_ddr = b->io.on_ddr;
    void *ctx = b->io.ctx;
    d_init(&b->io);
    b->io.on_output = on_output;
    b->io.on_tx = on_tx;
    b->io.on_ddr = on_ddr;
    b->io.ctx = ctx;
    for (int i = 0; i < 0x10000; i++) b->mem[i] = 0;
    b->rom_base = (uint16_t)(0x10000 - len);
    for (int i = 0; i < len; i++) b->mem[b->rom_base + i] = rom[i];
    for (int i = 0; i < 8; i++) b->irq_counts[i] = 0;
    hd6301_init(&b->cpu, io_read, io_write, b);
    hd6301_set_timing(&b->cpu, 1);  // the D151801 runs MC6801 timing
    b->insn_start = -1;
    for (int i = 0; i < 256; i++) b->irq_window[i] = IRQ_WINDOW_DEFAULT;
    b->cpu.mem = b->mem;
    b->cpu.rom_base = b->rom_base;
    hd6301_reset(&b->cpu);
}

int board_step(board_t *b) {
    hd6301_t *c = &b->cpu;
    uint64_t before = c->cycles;
    if (c->waiting || c->sleeping) {
        int64_t t = b->next_ev ? b->next_ev(b->ev_ctx) : -1;
        int64_t n = t >= 0 ? t - b->io.now : 1;
        c->cycles += (uint64_t)(n > 1 ? n : 1);
    } else {
        uint16_t trap = (uint16_t)((b->mem[HD6301_VEC_TRAP] << 8) | b->mem[HD6301_VEC_TRAP + 1]);
        if (c->pc == trap) return -1;
        int64_t start = b->io.now;
        uint8_t op = b->mem[c->pc];
        b->insn_start = start;
        b->insn_acc = c->acc[b->mem[c->pc]];
        b->insn_n_acc = 0;
        hd6301_step(c);
        b->insn_start = -1;
        // An interrupt is taken after this instruction only if its flag had risen IRQ_WINDOW
        // cycles before the instruction's end; one raised later waits for the next instruction,
        // as on the owner's chip (emu.sim.IRQ_WINDOW).
        int64_t end = start + (int64_t)(c->cycles - before);
        d_advance(&b->io, end - b->io.now, b->next_ev, b->run_ev, b->ev_ctx);
        uint16_t vec = d_irq_vector_at(&b->io, end - b->irq_window[op]);
        before = c->cycles;
        if (vec && hd6301_irq(c, vec)) {
            b->irq_counts[(vec - 0xFFF0) / 2]++;
            d_advance(&b->io, (int64_t)(c->cycles - before), b->next_ev, b->run_ev, b->ev_ctx);
        }
        return 0;
    }
    d_advance(&b->io, (int64_t)(c->cycles - before), b->next_ev, b->run_ev, b->ev_ctx);
    uint16_t vec = d_irq_vector(&b->io);
    if (vec) {
        before = c->cycles;
        if (hd6301_irq(c, vec)) {
            b->irq_counts[(vec - 0xFFF0) / 2]++;
            d_advance(&b->io, (int64_t)(c->cycles - before), b->next_ev, b->run_ev, b->ev_ctx);
        }
    }
    return 0;
}
