// In-car firmware logic (docs/mr2/cpu_replacement.md, "In-car test rig"): the emulated D151801
// on the ECU board's real pins. Shared by the RP2350 firmware (main.c) and the host test
// (tests/test_car_fw.py), so everything here is plain C with no SDK calls.
//
// Time: two rings of pin words, one word per microsecond, run by PIO from the same clock:
//   input ring:  every pin sampled each us (DMA writes it); index = real us since sampling began.
//   output ring: the word driven onto the output pins each us (DMA reads it).
// Emulated time t is input-ring index base + t, where base is the sample at which /RES rose: the
// emulated chip sees every input edge at the microsecond it happened (input captures exact).
// The emulator runs CAR_LIN us behind the newest sample, so every edge is queued before it is
// due. Every output change at emulated time t is written into the output ring at index
// base + t + CAR_LOUT, so it reaches the pin a constant CAR_LOUT us later (the two PIO state
// machines start together, so output slot j is driven while input sample j is taken). A constant delay is harmless here: the ROM reads its ADC by timing the
// conversion from its own hold-line release to the ADC-end edge, and subtracts the zero channel
// (ch 0) from every reading, so a fixed offset cancels; jitter would not.
//
// Safety (CAR_HOLD, default on): the IGT (P11) and injector (P21) pins are held at the level the
// real chip drives when the engine is not turning, 1 for both [BENCH: chip test run 5: P11 high
// from the port set-up to the first crank-driven edge at cycle 64507, P21 to cycle 32417] (key-on,
// engine off, the ROM makes no IGT or injector edge [EMU:tests/test_car_fw.py::test_koeo_no_spark_or_fuel]).
// With the hold on, the emulator computes spark and injection as normal (counted in the
// statistics) but neither pin ever moves, so the engine cannot run on this build.

#ifndef CAR_H
#define CAR_H

#include <stdint.h>

#include "board.h"
#include "pins.h"

#define CAR_IN_N 8192u   // input ring, words (8.2 ms); a power of two (DMA ring)
#define CAR_OUT_N 8192u  // output ring, words
#ifndef CAR_LOUT
#define CAR_LOUT 100  // us from an output's emulated time to its output-ring slot
#endif
#define CAR_LIN 16  // the emulator stays this many us behind the newest sample (> longest instruction)
#define CAR_QN 1024u
#define CAR_OEQ 64u
#ifndef CAR_HOLD
#define CAR_HOLD 1
#endif

enum { CAR_D_IN, CAR_D_OUT, CAR_D_IO };
#define CAR_DV_IN CAR_D_IN
#define CAR_DV_OUT CAR_D_OUT
#define CAR_DV_IO CAR_D_IO
#define CAR_ROW_(g, port, bit, dir) {(g), (port), (bit), CAR_DV_##dir},
typedef struct {
    uint8_t g, port, bit, dir;
} car_pin_t;
static const car_pin_t CAR_TAB[] = {CAR_PINS(CAR_ROW_)};
#define CAR_NPINS ((int)(sizeof CAR_TAB / sizeof CAR_TAB[0]))

typedef struct car car_t;
typedef void (*car_oe_fn)(car_t *c, uint32_t drive_mask);  // drive these GPIOs, the rest hi-Z

struct car {
    board_t b;
    const uint8_t *rom;
    const volatile uint32_t *in;
    volatile uint32_t *out;
    car_oe_fn set_oe;
    uint32_t in_mask, out_mask, held_mask, res_mask;
    int g_igt, g_inj, g_hold, g_adc_end;
    int64_t base;      // input-ring index of emulated time 0; -1 while the chip is in reset
    int64_t scanned;   // next input-ring index to scan
    uint32_t prev;     // the word at scanned - 1
    int64_t res_fall;  // input-ring index where /RES fell during a run (-1: none)
    int64_t fetched;   // output-ring entries already taken by the DMA (set by car_poll's caller)
    struct {
        int64_t t;
        uint32_t w;
    } q[CAR_QN];  // input changes not yet applied, emulated time order
    unsigned qh, qt;
    uint32_t applied;  // input word the emulated chip has
    uint32_t oval;     // output word at the emulator's current time
    int64_t filled;    // next output-ring index to write
    struct {
        int64_t at;
        uint32_t oe;
    } oeq[CAR_OEQ];  // drive-mask changes, by output-ring index
    unsigned oh, ot;
    uint32_t oe_now, oe_queued;
    // statistics (cumulative over runs)
    uint32_t runs, resets, late, qfull, oeqfull, lost, traps, tx_bytes;
    int64_t lag_max;
    uint32_t spark_n, inj_n, inj_last_us;
    int64_t inj_t0;
    uint32_t adc_n[8], adc_us[8];
    int64_t adc_t0;
    int adc_ch;
    uint8_t igt_lvl, inj_lvl, trapped;
};

static int car_gpio(int port, int bit) {
    for (int i = 0; i < CAR_NPINS; i++)
        if (CAR_TAB[i].port == port && CAR_TAB[i].bit == bit) return CAR_TAB[i].g;
    return -1;
}

// The output word at the emulator's current time: every OUT/IO pin's level as the chip drives
// it (d_port_out: the latch, or the compare pin for P11/P21; 1 while the pin is an input).
static uint32_t car_out_word(car_t *c) {
    uint8_t po[4];
    for (int i = 0; i < 4; i++) po[i] = d_port_out(&c->b.io, i);
    uint32_t w = 0;
    for (int i = 0; i < CAR_NPINS; i++) {
        const car_pin_t *p = &CAR_TAB[i];
        if (p->dir != CAR_D_IN && p->port) w |= (uint32_t)((po[p->port - 1] >> p->bit) & 1u) << p->g;
    }
    if (CAR_HOLD) w |= c->held_mask;  // IGT and injector at their engine-stopped level
    return w;
}

static uint32_t car_drive_mask(const car_t *c) {
    uint32_t m = 0;
    for (int i = 0; i < CAR_NPINS; i++) {
        const car_pin_t *p = &CAR_TAB[i];
        if (p->dir != CAR_D_IN && p->port && (c->b.io.ddr[p->port - 1] >> p->bit & 1u)) m |= 1u << p->g;
    }
    return m;
}

static void car_fill(car_t *c, int64_t upto) {  // output-ring slots [filled, upto] get the current word
    for (int64_t j = c->filled; j <= upto; j++) {
        if (j < c->fetched) c->late++;  // the DMA already took this slot: the pin showed the old word
        c->out[(uint64_t)j % CAR_OUT_N] = c->oval;
    }
    if (upto + 1 > c->filled) c->filled = upto + 1;
}

static void car_on_output(void *ctx, int port, int bit, int level, int64_t t) {
    car_t *c = ctx;
    car_fill(c, c->base + t + CAR_LOUT - 1);  // the old word up to this change
    if (port == 1 && bit == 1) {              // IGT (OC2)
        if (!level && c->igt_lvl) c->spark_n++;
        c->igt_lvl = (uint8_t)level;
    } else if (port == 2 && bit == 1) {  // injector (OC1): low = open
        if (!level) c->inj_t0 = t;
        else if (c->inj_t0 >= 0) {
            c->inj_last_us = (uint32_t)(t - c->inj_t0);
            c->inj_n++;
            c->inj_t0 = -1;
        }
        c->inj_lvl = (uint8_t)level;
    } else if (port == 1 && bit == 5) {  // ADC hold: its fall starts a conversion
        if (!level) {
            c->adc_t0 = t;
            c->adc_ch = (d_port_out(&c->b.io, 0) >> 2) & 7;
        } else c->adc_t0 = -1;
    }
    c->oval = car_out_word(c);
}

static void car_on_tx(void *ctx, uint8_t byte, int64_t t) {
    car_t *c = ctx;
    (void)byte;
    (void)t;
    c->tx_bytes++;
    d_sci_tx_done(&c->b.io);  // no line model: the byte is gone at once
}

static int64_t car_next_ev(void *ctx) {
    car_t *c = ctx;
    return c->qt != c->qh ? c->q[c->qt % CAR_QN].t : -1;
}

static void car_run_ev(void *ctx) {
    car_t *c = ctx;
    int64_t t = c->q[c->qt % CAR_QN].t;
    uint32_t w = c->q[c->qt % CAR_QN].w;
    c->qt++;
    uint32_t ch = (w ^ c->applied) & c->in_mask;
    c->applied = w;
    for (int i = 0; i < CAR_NPINS && ch; i++) {
        const car_pin_t *p = &CAR_TAB[i];
        if (!(ch >> p->g & 1u)) continue;
        int lv = (int)(w >> p->g & 1u);
        if (p->port == 0) {
            if (!lv) d_is3_edge(&c->b.io);  // IS3 (IGF) strobe: falling edge
        } else {
            d_set_pin_at(&c->b.io, p->port, p->bit, lv, t);
        }
        if (p->g == c->g_adc_end && !lv && c->adc_t0 >= 0) {  // conversion time at the pins
            int64_t us = t - c->adc_t0 - CAR_LOUT;
            c->adc_us[c->adc_ch] = (uint32_t)(us > 0 ? us : 0);
            c->adc_n[c->adc_ch]++;
            c->adc_t0 = -1;
        }
    }
}

static void car_on_ddr(void *ctx, int port, uint8_t ddr, int64_t t);

// /RES rose at input-ring index idx: reset the emulated chip, its pins from that sample.
static void car_start(car_t *c, int64_t idx) {
    c->b.io.on_output = car_on_output;
    c->b.io.on_tx = car_on_tx;
    c->b.io.on_ddr = car_on_ddr;
    c->b.io.ctx = c;
    c->b.next_ev = car_next_ev;
    c->b.run_ev = car_run_ev;
    c->b.ev_ctx = c;
    board_init(&c->b, c->rom, 4096);
    uint32_t w = c->in[(uint64_t)idx % CAR_IN_N];
    for (int i = 0; i < CAR_NPINS; i++) {  // levels at reset: no edges, so no captures
        const car_pin_t *p = &CAR_TAB[i];
        if (p->dir == CAR_D_OUT || !p->port) continue;
        uint8_t m = (uint8_t)(1u << p->bit);
        if (w >> p->g & 1u) c->b.io.pins[p->port - 1] |= m;
        else c->b.io.pins[p->port - 1] &= (uint8_t)~m;
    }
    c->b.io.pins[2] &= (uint8_t)~0x40;  // P36 (pin 31, no wire): low, as on the chip test (gates only the T-shorted self-test)
    // P42-P47 (pins 22-27, no wire) stay high, as on the chip test (P42/P43: advance trim, Q12)
    c->applied = w;
    c->qh = c->qt = 0;
    c->base = idx;
    c->res_fall = -1;
    c->igt_lvl = c->inj_lvl = 1;
    c->inj_t0 = c->adc_t0 = -1;
    c->trapped = 0;
    c->oval = car_out_word(c);
    if (c->filled < idx + CAR_LOUT) c->filled = idx + CAR_LOUT;  // earlier slots play while every pin is hi-Z
    c->runs++;
}

// /RES fell: the chip's pins go hi-Z at once.
static void car_stop(car_t *c) {
    c->base = -1;
    c->oh = c->ot = 0;
    c->oe_now = c->oe_queued = 0;
    if (c->set_oe) c->set_oe(c, 0);
    c->resets++;
}

static void car_init(car_t *c, const uint8_t *rom, const volatile uint32_t *in, volatile uint32_t *out,
                     car_oe_fn set_oe) {
    *c = (car_t){0};
    c->rom = rom;
    c->in = in;
    c->out = out;
    c->set_oe = set_oe;
    for (int i = 0; i < CAR_NPINS; i++) {
        const car_pin_t *p = &CAR_TAB[i];
        if (p->dir != CAR_D_OUT) c->in_mask |= 1u << p->g;
        if (p->dir != CAR_D_IN) c->out_mask |= 1u << p->g;
    }
    c->res_mask = 1u << CAR_GPIO_RES;
    c->g_igt = car_gpio(1, 1);
    c->g_inj = car_gpio(2, 1);
    c->g_hold = car_gpio(1, 5);
    c->g_adc_end = car_gpio(2, 0);
    c->held_mask = (1u << c->g_igt) | (1u << c->g_inj);
    c->base = -1;
    c->res_fall = -1;
    for (unsigned j = 0; j < CAR_OUT_N; j++) out[j] = c->out_mask;  // idle high; nothing is driven yet
    if (set_oe) set_oe(c, 0);
}

// A DDR write at emulated time t: the drive mask follows it at the same output-ring slot as the
// values, so a pin starts or stops driving exactly CAR_LOUT after the chip's bus cycle.
static void car_on_ddr(void *ctx, int port, uint8_t ddr, int64_t t) {
    car_t *c = ctx;
    (void)port;
    (void)ddr;
    int64_t at = c->base + t + CAR_LOUT;
    car_fill(c, at - 1);
    c->oval = car_out_word(c);
    uint32_t m = car_drive_mask(c);
    if (m == c->oe_queued) return;  // the ROM rewrites its DDRs every main-loop pass: only changes count
    if (c->oh - c->ot >= CAR_OEQ) {
        c->oeqfull++;
        return;
    }
    c->oeq[c->oh % CAR_OEQ].at = at;
    c->oeq[c->oh % CAR_OEQ].oe = m;
    c->oe_queued = m;
    c->oh++;
}

// One pass, called continuously: avail = input samples written so far (= the output slot now
// being driven), fetched = output-ring entries the DMA has taken (slots below it are final).
static void car_poll(car_t *c, int64_t avail, int64_t fetched) {
    c->fetched = fetched;
    while (c->ot != c->oh && c->oeq[c->ot % CAR_OEQ].at <= avail) {  // drive-mask changes now playing
        c->oe_now = c->oeq[c->ot % CAR_OEQ].oe;
        if (c->set_oe) c->set_oe(c, c->oe_now);
        c->ot++;
    }
    if (avail - c->scanned > (int64_t)CAR_IN_N - 256) {  // fell a whole ring behind: samples lost
        c->lost++;
        c->scanned = avail - 1;
        c->prev = c->in[(uint64_t)c->scanned % CAR_IN_N];
        if (c->base >= 0) car_stop(c);
    }
    while (c->scanned < avail && c->res_fall < 0) {
        uint32_t w = c->in[(uint64_t)c->scanned % CAR_IN_N];
        if (c->base < 0) {
            if (w & c->res_mask) car_start(c, c->scanned);
        } else if (!(w & c->res_mask)) {
            c->res_fall = c->scanned;  // run the chip up to here, then reset it
            break;
        } else if ((w ^ c->prev) & c->in_mask) {
            if (c->qh - c->qt >= CAR_QN) c->qfull++;
            else {
                c->q[c->qh % CAR_QN].t = c->scanned - c->base;
                c->q[c->qh % CAR_QN].w = w;
                c->qh++;
            }
        }
        c->prev = w;
        c->scanned++;
    }
    if (c->base < 0) return;
    int64_t target = (c->res_fall >= 0 ? c->res_fall : avail - CAR_LIN) - c->base;
    while (c->b.io.now < target && !c->trapped) {
        if (board_step(&c->b) < 0) {
            c->traps++;
            c->trapped = 1;  // undefined opcode: the chip would run off into the weeds; release the pins, wait for /RES
            c->oh = c->ot = 0;
            c->oe_now = c->oe_queued = 0;
            if (c->set_oe) c->set_oe(c, 0);
        }
    }
    int64_t lag = (avail - c->base) - c->b.io.now;
    if (lag > c->lag_max) c->lag_max = lag;
    if (c->res_fall >= 0) {
        c->scanned = c->res_fall;
        c->prev = c->in[(uint64_t)c->scanned % CAR_IN_N];
        c->res_fall = -1;
        car_stop(c);
        return;
    }
    if (!c->trapped) car_fill(c, c->base + c->b.io.now + CAR_LOUT);
}

#endif
