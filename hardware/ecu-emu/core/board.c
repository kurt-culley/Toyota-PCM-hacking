// See board.h.

#include "board.h"

static uint8_t io_read(void *ctx, uint16_t a) { return d_read(&((board_t *)ctx)->io, a); }
static void io_write(void *ctx, uint16_t a, uint8_t v) { d_write(&((board_t *)ctx)->io, a, v); }

void board_init(board_t *b, const uint8_t *rom, int len) {
    d_output_fn on_output = b->io.on_output;  // keep callbacks set by the host
    d_tx_fn on_tx = b->io.on_tx;
    void *ctx = b->io.ctx;
    d_init(&b->io);
    b->io.on_output = on_output;
    b->io.on_tx = on_tx;
    b->io.ctx = ctx;
    for (int i = 0; i < 0x10000; i++) b->mem[i] = 0;
    b->rom_base = (uint16_t)(0x10000 - len);
    for (int i = 0; i < len; i++) b->mem[b->rom_base + i] = rom[i];
    for (int i = 0; i < 8; i++) b->irq_counts[i] = 0;
    hd6301_init(&b->cpu, io_read, io_write, b);
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
        hd6301_step(c);
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
