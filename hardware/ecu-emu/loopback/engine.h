// The loopback's engine model in plain C: the same behaviour as src/pcmre/emu/engine17140.py,
// driven through the board's event hooks. Used by the RP2350 firmware (main.c, in real time)
// and by tests/hardware/test_loopback_engine.py (on the host, as fast as it runs), which must both
// reproduce the simulator's checksums in expected.h. Include once, after board.h and expected.h.
//
// Schedule: one REF row per 6 s phase (emu.loopback_ref.SCHEDULE): rpm, MAP, TPS and the switch
// inputs (idle contact P16, T terminal P30, IGF present), changing at exactly k x 6 s.
// Crank: NE rises every 30 deg (T = round(5e6 / rpm) us), falls half a tooth later; G is high
// for the first half of every 6th tooth. Producer: eng_crank_fill() queues these edges, and the
// phase changes, in time order into a single-producer / single-consumer ring.
// Reactions: the ADC hybrid (P20 rises REF_ADC_START_DELAY us after the hold line P15 rises, and
// falls REF_ADC_OFFSET + 200 us/V after P15 drops, for the channel on P12-P14, unless the hold line came
// back first) and, when the phase has IGF, the echo REF_IGF_DELAY us after each spark (P11 falling).

#ifndef LOOPBACK_ENGINE_H
#define LOOPBACK_ENGINE_H

#include <math.h>
#include <stdint.h>

#ifndef ENG_DMB
#define ENG_DMB()
#endif

static int eng_scenario_at(int64_t t) {
    int64_t k = t / REF_PHASE_US;
    return (int)(k < REF_PHASES ? k : REF_PHASES - 1);
}

static uint32_t eng_crc32(uint32_t crc, const uint8_t *p, unsigned n) {
    crc = ~crc;
    while (n--) {
        crc ^= *p++;
        for (int k = 0; k < 8; k++) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}

typedef struct {
    int64_t t;
    uint8_t kind, g;
} eng_ev_t;
enum { EV_TOOTH, EV_GLOW, EV_NELOW, EV_PHASE };
enum { LEV_ADC_END, LEV_IS3, LEV_ADC_START };
#define ENG_RING 1024u

typedef struct {
    uint32_t edges, edge_crc, ram_crc, inj_n, inj_sum;
    int rpm_word;
} eng_result_t;

typedef struct {
    board_t *b;
    // crank producer state (core 0) and ring
    eng_ev_t ring[ENG_RING];
    volatile uint32_t head, tail;
    volatile int64_t queued_until;  // every crank edge up to this time is in the ring
    int64_t tooth, pend_glow, pend_nelow, next_phase;
    int edge;
    // consumer side (core 1)
    struct { int64_t t; uint8_t kind; } local[16];
    int n_local, adc_hold;
    int64_t inj_on;
    uint32_t w_edges, w_crc, w_inj_n, w_inj_sum;
    void (*pin_out)(int port, int bit, int level, int64_t t);  // optional: drive real pins
} eng_t;

static void eng_init(eng_t *e, board_t *b) {
    *e = (eng_t){0};
    e->b = b;
    e->tooth = 1000;
    e->pend_glow = e->pend_nelow = -1;
    e->next_phase = REF_PHASES > 1 ? REF_PHASE_US : -1;
    e->adc_hold = 1;
    e->inj_on = -1;
}

// Queue crank edges with times up to `until`, in time order (Engine17140._tooth).
static void eng_crank_fill(eng_t *e, int64_t until) {
    while (e->head - e->tail < ENG_RING - 4) {
        int64_t t = e->tooth;
        if (e->pend_glow >= 0 && e->pend_glow < t) t = e->pend_glow;
        if (e->pend_nelow >= 0 && e->pend_nelow < t) t = e->pend_nelow;
        if (e->next_phase >= 0 && e->next_phase <= t) t = e->next_phase;  // ties: the phase change first
        if (t > until) break;
        eng_ev_t ev;
        if (e->next_phase >= 0 && e->next_phase == t) {
            ev = (eng_ev_t){t, EV_PHASE, 0};
            e->next_phase = t + REF_PHASE_US < (int64_t)REF_PHASES * REF_PHASE_US ? t + REF_PHASE_US : -1;
        } else if (e->pend_glow >= 0 && e->pend_glow == t) {
            ev = (eng_ev_t){t, EV_GLOW, 0};
            e->pend_glow = -1;
        } else if (e->pend_nelow >= 0 && e->pend_nelow == t) {
            ev = (eng_ev_t){t, EV_NELOW, 0};
            e->pend_nelow = -1;
        } else {
            int64_t T = (int64_t)llround(5e6 / REF[eng_scenario_at(e->tooth)].rpm);
            e->edge++;
            int g = e->edge % 6 == 0;
            ev = (eng_ev_t){e->tooth, EV_TOOTH, (uint8_t)g};
            if (g) e->pend_glow = e->tooth + T / 2;
            e->pend_nelow = e->tooth + (int64_t)llround(T * 0.5);
            e->tooth += T;
        }
        e->ring[e->head % ENG_RING] = ev;
        ENG_DMB();
        e->head = e->head + 1;
        e->queued_until = ev.t;
    }
    // Every edge up to `until` is queued (the next one is later), so the emulator may run to
    // `until` even when the last queued edge is much earlier (slow rpm, long gaps).
    if (e->head - e->tail < ENG_RING - 4 && until > e->queued_until) {
        ENG_DMB();
        e->queued_until = until;
    }
}

static void eng_local_push(eng_t *e, int64_t t, int kind) {
    int i = e->n_local++;
    while (i > 0 && e->local[i - 1].t > t) {
        e->local[i] = e->local[i - 1];
        i--;
    }
    e->local[i].t = t;
    e->local[i].kind = (uint8_t)kind;
}

static int64_t eng_next_ev(void *ctx) {
    eng_t *e = ctx;
    int64_t tr = (e->tail != e->head) ? e->ring[e->tail % ENG_RING].t : -1;
    int64_t tl = e->n_local ? e->local[0].t : -1;
    if (tr < 0) return tl;
    if (tl < 0) return tr;
    return tl < tr ? tl : tr;  // ties: the crank edge first
}

static void eng_run_ev(void *ctx) {
    eng_t *e = ctx;
    d151801_t *io = &e->b->io;
    int64_t tr = (e->tail != e->head) ? e->ring[e->tail % ENG_RING].t : -1;
    if (e->n_local && (tr < 0 || e->local[0].t < tr)) {
        int kind = e->local[0].kind;
        for (int i = 1; i < e->n_local; i++) e->local[i - 1] = e->local[i];
        e->n_local--;
        if (kind == LEV_ADC_END) {
            if (!e->adc_hold) d_set_pin(io, 2, 0, 0);
        } else if (kind == LEV_ADC_START) {
            d_set_pin(io, 2, 0, 1);
        } else {
            d_is3_edge(io);
        }
        return;
    }
    ENG_DMB();
    eng_ev_t ev = e->ring[e->tail % ENG_RING];
    e->tail = e->tail + 1;
    if (ev.kind == EV_TOOTH) {
        if (ev.g) d_set_pin(io, 3, 5, 1);
        d_set_pin(io, 1, 0, 1);
    } else if (ev.kind == EV_GLOW) {
        d_set_pin(io, 3, 5, 0);
    } else if (ev.kind == EV_PHASE) {
        const ref_t *r = &REF[eng_scenario_at(ev.t)];
        d_set_pin(io, 3, 0, r->tterm ? 0 : 1);  // T terminal
        d_set_pin(io, 1, 6, r->idl ? 0 : 1);    // idle contact
    } else {
        d_set_pin(io, 1, 0, 0);
    }
}

static double eng_channel_volts(int ch, int64_t t) {
    const ref_t *r = &REF[eng_scenario_at(t)];
    switch (ch) {
    case 1: return fmax(0.0, fmin(5.0, 0.6 + 0.03 * r->kpa));  // PIM (emu.sensors.pim_volts)
    case 2: return r->tps;
    case 3: return 2.5;
    case 4: return 3.5;
    case 5: return 0.5;
    case 6: return 2.5;
    case 7: return 5.0;
    default: return 0.0;
    }
}

static void eng_on_output(void *ctx, int port, int bit, int level, int64_t t) {
    eng_t *e = ctx;
    if (t % REF_PHASE_US >= REF_MEASURE_FROM_US) {  // packed as emu.loopback_ref does ("<BBBq")
        uint8_t rec[11] = {(uint8_t)port, (uint8_t)bit, (uint8_t)level};
        for (int i = 0; i < 8; i++) rec[3 + i] = (uint8_t)((uint64_t)t >> (8 * i));
        e->w_crc = eng_crc32(e->w_crc, rec, sizeof rec);
        e->w_edges++;
    }
    if (e->pin_out) e->pin_out(port, bit, level, t);
    if (port == 1 && bit == 5) {
        if (level) {
            e->adc_hold = 1;
            eng_local_push(e, t + REF_ADC_START_DELAY, LEV_ADC_START);
        } else if (e->adc_hold) {
            e->adc_hold = 0;
            int ch = (d_port_out(&e->b->io, 0) >> 2) & 7;
            double dt = rint(REF_ADC_OFFSET + 200.0 * eng_channel_volts(ch, t));
            eng_local_push(e, t + (dt > 1 ? (int64_t)dt : 1), LEV_ADC_END);
        }
    } else if (port == 1 && bit == 1 && !level) {
        if (REF[eng_scenario_at(t)].igf) eng_local_push(e, t + REF_IGF_DELAY, LEV_IS3);
    } else if (port == 2 && bit == 1) {
        if (!level) {
            e->inj_on = t;
        } else if (e->inj_on >= 0 && e->inj_on % REF_PHASE_US >= REF_MEASURE_FROM_US) {
            e->w_inj_n++;
            e->w_inj_sum += (uint32_t)(t - e->inj_on);
        }
    }
}

// Wire the engine into a board (call before board_init; board_init keeps these hooks), and
// set the switch inputs as Engine17140.update_sensors does (call after board_init).
static void eng_attach(eng_t *e, board_t *b) {
    eng_init(e, b);
    b->io.on_output = eng_on_output;
    b->io.ctx = e;
    b->next_ev = eng_next_ev;
    b->run_ev = eng_run_ev;
    b->ev_ctx = e;
}

static void eng_set_switches(eng_t *e) {
    d151801_t *io = &e->b->io;
    d_set_pin(io, 3, 0, REF[0].tterm ? 0 : 1);  // T terminal
    d_set_pin(io, 1, 6, REF[0].idl ? 0 : 1);    // idle contact
    d_set_pin(io, 3, 4, 1);  // J8: P34 = 1
    d_set_pin(io, 3, 6, 0);
    d_set_pin(io, 3, 5, 0);  // G low
}

// End of a phase (the first step at or after its boundary): take the results and reset.
static void eng_phase_end(eng_t *e, eng_result_t *r) {
    r->edges = e->w_edges;
    r->edge_crc = e->w_crc;
    r->ram_crc = eng_crc32(0, &e->b->mem[0x40], 0xC0);
    r->rpm_word = (e->b->mem[0x77] << 8) | e->b->mem[0x78];
    r->inj_n = e->w_inj_n;
    r->inj_sum = e->w_inj_sum;
    e->w_edges = e->w_crc = e->w_inj_n = e->w_inj_sum = 0;
}

static int eng_result_ok(const eng_result_t *r, const ref_t *x) {
    return r->edges == x->edges && r->edge_crc == x->edge_crc && r->ram_crc == x->ram_crc && r->inj_n == x->inj_n &&
           r->inj_sum == x->inj_sum && r->rpm_word == x->rpm_word;
}

#endif
