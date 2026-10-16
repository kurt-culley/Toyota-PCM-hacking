// Chip-in-isolation test (docs/hardware/chip_diff_test.md): the engine around a real D151801,
// one E cycle at a time. Shared by the RP2350 firmware (main.c) and the host self-test
// (tests/test_chipdiff.py), which uses the C emulator as the "chip".
//
// Time is in E cycles from the release of /RES: cycle k starts when E rises. In each cycle the
// firmware drives the chip's inputs with cd_word(k), computed a few cycles ahead, and samples
// all pins; cd_sample(k, pins) turns output edges into the engine's reactions. The crank
// schedule and the reactions are engine.h's (the loopback's model of engine17140.py):
//   NE / G and the phase's switch inputs from eng_crank_fill; P20 up REF_ADC_START_DELAY after P15
//   rises and down REF_ADC_OFFSET + 200 x volts after it falls; IGF: SC1 pulled low REF_IGF_DELAY
//   after each spark (P11 falling), for IGF_LOW_CYCLES, in phases with IGF.
// The chip's reaction times are its own (observed), so the log records the inputs as actually
// applied; analysis/emu/chipdiff.py replays exactly those into the emulator and compares the
// outputs. Include once, after board.h, expected.h and engine.h.

#ifndef CHIPDIFF_H
#define CHIPDIFF_H

#include <math.h>
#include <stdint.h>

// GPIO, port, bit, direction as seen from the chip. Parsed by analysis/emu/chipdiff.py.
#define CD_PINS(X)                                                                                                     \
    X(0, 3, 0, IN)    /* P30  T terminal       pin 37 */                                                               \
    X(1, 3, 1, OUT)   /* P31                   pin 36 */                                                               \
    X(2, 3, 2, IN)    /* P32                   pin 35 */                                                               \
    X(3, 3, 3, IN)    /* P33                   pin 34 */                                                               \
    X(4, 3, 4, IN)    /* P34  J8               pin 33 */                                                               \
    X(5, 3, 5, IN)    /* P35  G                pin 32 */                                                               \
    X(6, 1, 5, OUT)   /* P15  ADC hold         pin 18 */                                                               \
    X(7, 3, 7, IN)    /* P37                   pin 30 */                                                               \
    X(10, 4, 0, OUT)  /* P40                   pin 29 */                                                               \
    X(11, 4, 1, OUT)  /* P41                   pin 28 */                                                               \
    X(12, 2, 0, IN)   /* P20  ADC end          pin 8  */                                                               \
    X(13, 2, 1, OUT)  /* P21  injector         pin 9  */                                                               \
    X(14, 1, 1, OUT)  /* P11  IGT              pin 14 */                                                               \
    X(15, 1, 2, OUT)  /* P12  ADC select       pin 15 */                                                               \
    X(16, 1, 3, OUT)  /* P13  ADC select       pin 16 */                                                               \
    X(17, 1, 4, OUT)  /* P14  ADC select       pin 17 */                                                               \
    X(18, 0, 0, IN)   /* SC1  IS3 / IGF        pin 39 (port 0 = the IS3 strobe) */                                     \
    X(20, 2, 2, OUT)  /* P22                   pin 10 */                                                               \
    X(21, 2, 4, OUT)  /* P24  TX / fault lamp  pin 12 */                                                               \
    X(22, 2, 3, OUT)  /* P23                   pin 11 */                                                               \
    X(26, 1, 0, IN)   /* P10  NE               pin 13, via 1k */                                                       \
    X(27, 1, 6, IN)   /* P16  IDL              pin 19, via 1k */                                                       \
    X(28, 1, 7, IN)   /* P17                   pin 20, via 1k */

#define CD_GPIO_RES 8u
#define CD_GPIO_EXTAL 9u
#define CD_GPIO_E 19u

#define CD_MASK_IN_(g, port, bit, dir) | (CD_DIR_##dir ? (1u << (g)) : 0u)
#define CD_MASK_OUT_(g, port, bit, dir) | (CD_DIR_##dir ? 0u : (1u << (g)))
#define CD_DIR_IN 1
#define CD_DIR_OUT 0
#define CD_IN_MASK (0u CD_PINS(CD_MASK_IN_))
#define CD_OUT_MASK (0u CD_PINS(CD_MASK_OUT_))

#define CD_G_P10 26
#define CD_G_P11 14
#define CD_G_P15 6
#define CD_G_P20 12
#define CD_G_P35 5
#define CD_G_IS3 18
#define CD_ADC_SEL_SHIFT 15  // P12-P14 on GP15-17: the channel number

#define CD_G_P30 0   // T terminal
#define CD_G_P16 27  // idle contact
// Input levels before and at reset, as the simulator starts: every pin high except G and the
// switches of the first phase (eng_set_switches). The P36 strap (pin 31) is a wire to GND, P42-P47
// a resistor to 5 V.
#define CD_IN_INIT                                                                                                     \
    (CD_IN_MASK & ~(1u << CD_G_P35) & ~(REF[0].tterm ? 1u << CD_G_P30 : 0u) & ~(REF[0].idl ? 1u << CD_G_P16 : 0u))

// The chip's output edges are sampled this many cycles after the emulator's time for them: port
// writes 3, compare outputs 2 (chip runs 3-5, constant over every edge). Reactions are timed from
// the corrected edge, so they reach the chip at the model's times (engine.h). The host self-test,
// whose "chip" is the emulator itself, sets both to 0.
#ifndef CD_LAT_PORT
#define CD_LAT_PORT 3
#endif
#ifndef CD_LAT_OC
#define CD_LAT_OC 2
#endif

#define IGF_LOW_CYCLES 8

enum { CD_ADC_START, CD_ADC_END, CD_IS3_LOW, CD_IS3_HIGH };
#define CD_QN 16

typedef struct {
    eng_t eng;  // crank generator only (ring + tooth state); no board attached
    uint32_t in;
    int64_t filled;  // the next cycle cd_word will compute
    struct {
        int64_t t;
        uint8_t kind;
    } q[CD_QN];
    int nq, adc_hold;
    uint32_t out_prev;
    uint32_t late, qfull;  // reactions applied after their time; reactions dropped
} cd_t;

static void cd_init(cd_t *c) {
    eng_init(&c->eng, 0);
    c->in = CD_IN_INIT;
    c->filled = 0;
    c->nq = 0;
    c->adc_hold = 1;
    c->out_prev = CD_OUT_MASK;  // undriven outputs read high (pull-ups), as the emulator's ports
    c->late = c->qfull = 0;
}

static void cd_push(cd_t *c, int64_t t, int kind) {
    if (c->nq == CD_QN) {
        c->qfull++;
        return;
    }
    if (t < c->filled) {
        c->late++;
        t = c->filled;
    }
    int i = c->nq++;
    while (i > 0 && c->q[i - 1].t > t) {
        c->q[i] = c->q[i - 1];
        i--;
    }
    c->q[i].t = t;
    c->q[i].kind = (uint8_t)kind;
}

static inline void cd_set(cd_t *c, int g, int level) {
    c->in = level ? (c->in | (1u << g)) : (c->in & ~(1u << g));
}

// The input word for cycle k; call with k = 0, 1, 2, ... in order.
static uint32_t cd_word(cd_t *c, int64_t k) {
    eng_t *e = &c->eng;
    eng_crank_fill(e, k + 64);
    while (e->tail != e->head && e->ring[e->tail % ENG_RING].t <= k) {
        eng_ev_t ev = e->ring[e->tail % ENG_RING];
        e->tail = e->tail + 1;
        if (ev.kind == EV_TOOTH) {
            if (ev.g) cd_set(c, CD_G_P35, 1);
            cd_set(c, CD_G_P10, 1);
        } else if (ev.kind == EV_GLOW) {
            cd_set(c, CD_G_P35, 0);
        } else if (ev.kind == EV_PHASE) {
            const ref_t *r = &REF[eng_scenario_at(ev.t)];
            cd_set(c, CD_G_P30, !r->tterm);
            cd_set(c, CD_G_P16, !r->idl);
        } else {
            cd_set(c, CD_G_P10, 0);
        }
    }
    while (c->nq && c->q[0].t <= k) {
        int kind = c->q[0].kind;
        for (int i = 1; i < c->nq; i++) c->q[i - 1] = c->q[i];
        c->nq--;
        if (kind == CD_ADC_START) cd_set(c, CD_G_P20, 1);
        else if (kind == CD_ADC_END) {
            if (!c->adc_hold) cd_set(c, CD_G_P20, 0);
        } else
            cd_set(c, CD_G_IS3, kind == CD_IS3_HIGH);
    }
    c->filled = k + 1;
    return c->in;
}

// The pins as sampled in cycle k (k = 0, 1, 2, ... in order).
static void cd_sample(cd_t *c, int64_t k, uint32_t pins) {
    uint32_t out = pins & CD_OUT_MASK, ch = out ^ c->out_prev;
    c->out_prev = out;
    if (!ch) return;
    if (ch & (1u << CD_G_P15)) {
        int64_t t = k - CD_LAT_PORT;  // the model's time of this edge
        if (out & (1u << CD_G_P15)) {
            c->adc_hold = 1;
            cd_push(c, t + REF_ADC_START_DELAY, CD_ADC_START);
        } else if (c->adc_hold) {
            c->adc_hold = 0;
            int chn = (int)((out >> CD_ADC_SEL_SHIFT) & 7u);
            double dt = rint(REF_ADC_OFFSET + 200.0 * eng_channel_volts(chn, t));
            cd_push(c, t + (dt > 1 ? (int64_t)dt : 1), CD_ADC_END);
        }
    }
    if ((ch & (1u << CD_G_P11)) && !(out & (1u << CD_G_P11))) {
        int64_t t = k - CD_LAT_OC;
        if (REF[eng_scenario_at(t)].igf) {
            cd_push(c, t + REF_IGF_DELAY, CD_IS3_LOW);
            cd_push(c, t + REF_IGF_DELAY + IGF_LOW_CYCLES, CD_IS3_HIGH);
        }
    }
}

#endif
