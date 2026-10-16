// D151801 peripherals: see d151801.h. Semantics follow src/pcmre/emu/periph.py.

#include "d151801.h"

#include "hd6301.h"

enum { ICF = 0x80, OCF = 0x40, TOF = 0x20, EICI = 0x10, EOCI = 0x08, ETOI = 0x04, IEDG = 0x02, OLVL = 0x01 };
enum { RDRF = 0x80, ORFE = 0x40, TDRE = 0x20, RIE = 0x10, RE = 0x08, TIE = 0x04, TE = 0x02 };
enum { IS3F = 0x80 };
enum {
    DDR1 = 0x00, DDR2, PORT1, PORT2, DDR3, DDR4, PORT3, PORT4,
    TCSR1, FRC_H, FRC_L, OCR1_H, OCR1_L, ICR1_H, ICR1_L, P3CSR,
    RMCR, TRCSR, RDR, TDR,
    TCSR2 = 0x18, OCR2_H = 0x1B, OCR2_L, ICR2_H, ICR2_L,
};
#define MODE_BITS 0xE0  // P2-7..5 read the mode latched at reset: mode 7 (single chip)

static uint8_t ch_read_tcsr(d_channel_t *ch) {
    ch->armed = ch->tcsr & (ICF | OCF | TOF);
    return ch->tcsr;
}

static void ch_write_tcsr(d_channel_t *ch, uint8_t v) { ch->tcsr = (uint8_t)((ch->tcsr & 0xE0) | (v & 0x1F)); }

static uint8_t ch_pending(const d_channel_t *ch) {
    uint8_t t = ch->tcsr;
    return (uint8_t)(((t & ICF) && (t & EICI) ? ICF : 0) | ((t & OCF) && (t & EOCI) ? OCF : 0));
}

uint16_t d_frc(const d151801_t *d) { return (uint16_t)(d->now + d->frc_offset); }

// Next match of a channel from now: when the counter next equals OCR. A match at this very
// count is not counted (it already happened or was just written), as in periph._next_compare.
static void recalc_match(d151801_t *d, d_channel_t *ch) {
    uint16_t dist = (uint16_t)(ch->ocr - d_frc(d));
    ch->next_match = d->now + (dist ? dist : 0x10000);
    d->oc_dirty = 1;
}

static void set_frc(d151801_t *d, uint16_t value) {
    d->frc_offset = (uint16_t)(value - (uint16_t)d->now);
    recalc_match(d, &d->t1);
    recalc_match(d, &d->t2);
}

uint8_t d_port_out(const d151801_t *d, int i) {
    unsigned v = (unsigned)(d->latch[i] & d->ddr[i]) | (d->pins[i] & ~d->ddr[i] & 0xFF);
    if (i == 0 && (d->ddr[0] & 0x02)) v = (v & ~0x02u) | (d->t2.pin_out ? 0x02 : 0);  // P1-1 = OC2 (GUESS)
    if (i == 1) {
        if (d->ddr[1] & 0x02) v = (v & ~0x02u) | (d->t1.pin_out ? 0x02 : 0);  // P2-1 = OC1
        v = (v & 0x1F) | MODE_BITS;
    }
    return (uint8_t)v;
}

static void outputs_changed(d151801_t *d) {
    for (int i = 0; i < 4; i++) {
        uint8_t nv = d_port_out(d, i);
        uint8_t diff = (uint8_t)((nv ^ d->last_out[i]) & d->ddr[i]);
        if (i == 1) diff &= 0x1F;
        d->last_out[i] = nv;
        if (diff && d->on_output)
            for (int bit = 0; bit < 8; bit++)
                if (diff & (1 << bit)) d->on_output(d->ctx, i + 1, bit, (nv >> bit) & 1, d->now);
    }
}

void d_init(d151801_t *d) {
    *d = (d151801_t){0};
    d->t1.ocr = d->t2.ocr = 0xFFFF;
    d->t1.pin_out = d->t2.pin_out = 1;
    for (int i = 0; i < 4; i++) d->pins[i] = 0xFF;  // external pins default high
    d->latch[3] = 0xFF;  // port 4 data latch reads back high at reset (owner chip run 2; emu.periph)
    d->trcsr = TDRE;
    for (int i = 0; i < 4; i++) d->last_out[i] = d_port_out(d, i);
    recalc_match(d, &d->t1);
    recalc_match(d, &d->t2);
}

static uint16_t read_icr(d_channel_t *ch) {
    if (ch->armed & ICF) {
        ch->tcsr &= (uint8_t)~ICF;
        ch->armed &= (uint8_t)~ICF;
    }
    return ch->icr;
}

uint8_t d_read(d151801_t *d, uint16_t a) {
    switch (a) {
    case PORT1: case PORT2: case PORT3: case PORT4: {
        int i = a == PORT1 ? 0 : a == PORT2 ? 1 : a == PORT3 ? 2 : 3;
        if (a == PORT3 && d->is3_armed) {
            d->p3csr &= (uint8_t)~IS3F;
            d->is3_armed = 0;
        }
        return d_port_out(d, i);
    }
    case DDR1: case DDR2: case DDR3: case DDR4: return 0xFF;  // write-only
    case TCSR1: {
        uint8_t v = (uint8_t)(ch_read_tcsr(&d->t1) | (d->tof ? TOF : 0));
        if (d->tof) d->t1.armed |= TOF;
        return v;
    }
    case FRC_H:
        if (d->t1.armed & TOF) {
            d->tof = 0;
            d->t1.armed &= (uint8_t)~TOF;
        }
        d->frc_lo_latch = (uint16_t)(0x100 | (d_frc(d) & 0xFF));  // the LSB is latched on an MSB read
        return (uint8_t)(d_frc(d) >> 8);
    case FRC_L: {
        uint16_t l = d->frc_lo_latch;
        d->frc_lo_latch = 0;
        return (uint8_t)(l ? l : d_frc(d));
    }
    case OCR1_H: return (uint8_t)(d->t1.ocr >> 8);
    case OCR1_L: return (uint8_t)d->t1.ocr;
    case ICR1_H: return (uint8_t)(read_icr(&d->t1) >> 8);
    case ICR1_L: return (uint8_t)d->t1.icr;
    case P3CSR: d->is3_armed = (d->p3csr & IS3F) != 0; return d->p3csr;
    case RMCR: return d->rmcr;
    case TRCSR: d->sci_armed = d->trcsr & (RDRF | ORFE); return d->trcsr;
    case RDR:
        if (d->sci_armed) {
            d->trcsr &= (uint8_t)~d->sci_armed;
            d->sci_armed = 0;
        }
        return d->rdr;
    case TCSR2: return ch_read_tcsr(&d->t2);
    case OCR2_H: return (uint8_t)(d->t2.ocr >> 8);
    case OCR2_L: return (uint8_t)d->t2.ocr;
    case ICR2_H: return (uint8_t)(read_icr(&d->t2) >> 8);
    case ICR2_L: return (uint8_t)d->t2.icr;
    default: return d->regs[a & 0x1F];
    }
}

static void write_ocr(d151801_t *d, d_channel_t *ch, int hi, uint8_t v) {
    ch->ocr = hi ? (uint16_t)((v << 8) | (ch->ocr & 0xFF)) : (uint16_t)((ch->ocr & 0xFF00) | v);
    if (ch->armed & OCF) {
        ch->tcsr &= (uint8_t)~OCF;
        ch->armed &= (uint8_t)~OCF;
    }
    recalc_match(d, ch);
}

void d_write(d151801_t *d, uint16_t a, uint8_t v) {
    switch (a) {
    case DDR1: case DDR2: case DDR3: case DDR4: {
        int i = a == DDR1 ? 0 : a == DDR2 ? 1 : a == DDR3 ? 2 : 3;
        d->ddr[i] = v;
        outputs_changed(d);
        if (d->on_ddr) d->on_ddr(d->ctx, i + 1, v, d->now);
        break;
    }
    case PORT1: d->latch[0] = v; outputs_changed(d); break;
    case PORT2: d->latch[1] = v; outputs_changed(d); break;
    case PORT3: d->latch[2] = v; outputs_changed(d); break;
    case PORT4: d->latch[3] = v; outputs_changed(d); break;
    case TCSR1: ch_write_tcsr(&d->t1, v); d->oc_dirty = 1; break;
    case FRC_H: d->frc_hi_written = v; set_frc(d, 0xFFF8); break;
    case FRC_L: break;  // MC6801: a counter write only presets $FFF8 (FRC_H); the low byte is not loaded
    case OCR1_H: write_ocr(d, &d->t1, 1, v); break;
    case OCR1_L: write_ocr(d, &d->t1, 0, v); break;
    case OCR2_H: write_ocr(d, &d->t2, 1, v); break;
    case OCR2_L: write_ocr(d, &d->t2, 0, v); break;
    case P3CSR: d->p3csr = (uint8_t)((d->p3csr & IS3F) | (v & 0x7F)); break;
    case RMCR: d->rmcr = v; break;
    case TRCSR: d->trcsr = (uint8_t)((d->trcsr & (RDRF | ORFE | TDRE)) | (v & 0x1F)); break;
    case TDR:
        if (d->trcsr & TE) {
            d->trcsr &= (uint8_t)~TDRE;
            if (d->on_tx) d->on_tx(d->ctx, v, d->now);
        }
        break;
    case TCSR2: ch_write_tcsr(&d->t2, v); d->oc_dirty = 1; break;
    default: d->regs[a & 0x1F] = v; break;
    }
}

static int64_t next_compare(const d151801_t *d, int64_t end) {
    int64_t t = d->t1.next_match < d->t2.next_match ? d->t1.next_match : d->t2.next_match;
    return t <= end ? t : -1;
}

static void compare_match(d151801_t *d) {
    d_channel_t *chs[2] = {&d->t1, &d->t2};
    for (int k = 0; k < 2; k++)
        if (chs[k]->ocr == d_frc(d)) {
            if (!(chs[k]->tcsr & OCF)) chs[k]->ocf_t = d->now + 1;  // counts for interrupts a cycle after the match
            chs[k]->tcsr |= OCF;
            chs[k]->pin_out = (chs[k]->tcsr & OLVL) ? 1 : 0;
            chs[k]->next_match = d->now + 0x10000;
            d->oc_dirty = 1;
            outputs_changed(d);
        }
}

void d_advance(d151801_t *d, int64_t n, d_next_event_fn next_ev, d_run_event_fn run_ev, void *ev_ctx) {
    int64_t end = d->now + n;
    uint16_t f0 = d_frc(d);
    for (;;) {
        int64_t t_oc = next_compare(d, end);
        int64_t t_ev = next_ev ? next_ev(ev_ctx) : -1;
        if (t_ev > end) t_ev = -1;
        if (t_oc < 0 && t_ev < 0) break;
        if (t_ev >= 0 && (t_oc < 0 || t_ev < t_oc)) {
            if (t_ev > d->now) d->now = t_ev;
            run_ev(ev_ctx);
        } else {
            d->now = t_oc;
            compare_match(d);
        }
    }
    d->now = end;
    if (d_frc(d) < f0 || n >= 0x10000) {  // wrapped through $0000
        if (!d->tof) d->tof_t = d->now - d_frc(d);
        d->tof = 1;
    }
}

static void set_pin_frc(d151801_t *d, int port, int bit, int level, uint16_t frc, int64_t t) {
    int i = port - 1;
    uint8_t mask = (uint8_t)(1 << bit);
    int old = (d->pins[i] & mask) ? 1 : 0;
    level = level ? 1 : 0;
    d->pins[i] = level ? (uint8_t)(d->pins[i] | mask) : (uint8_t)(d->pins[i] & ~mask);
    if (old == level) return;
    d_channel_t *ch = (port == 2 && bit == 0) ? &d->t1 : (port == 1 && bit == 0) ? &d->t2 : 0;
    if (ch) {
        ch->pin_in = (uint8_t)level;
        if (((ch->tcsr & IEDG) != 0) == (level != 0)) {
            ch->icr = frc;
            if (!(ch->tcsr & ICF)) ch->icf_t = t - 1;  // counts for interrupts from the cycle before the edge
            ch->tcsr |= ICF;
        }
    }
}

void d_set_pin(d151801_t *d, int port, int bit, int level) { set_pin_frc(d, port, bit, level, d_frc(d), d->now); }

void d_set_pin_at(d151801_t *d, int port, int bit, int level, int64_t t) {
    set_pin_frc(d, port, bit, level, (uint16_t)(t + d->frc_offset), t);
}

void d_is3_edge(d151801_t *d) { d->p3csr |= IS3F; }

uint16_t d_irq_vector_at(const d151801_t *d, int64_t t) {
    const d_channel_t *chs[2] = {&d->t1, &d->t2};
    uint8_t p = 0;
    for (int k = 0; k < 2; k++) {
        uint8_t q = ch_pending(chs[k]);
        if ((q & ICF) && chs[k]->icf_t <= t) p |= ICF;
        if ((q & OCF) && chs[k]->ocf_t <= t) p |= OCF;
    }
    if (p & ICF) return HD6301_VEC_ICF;
    if (p & OCF) return HD6301_VEC_OCF;
    if (d->tof && (d->t1.tcsr & ETOI) && d->tof_t <= t) return HD6301_VEC_TOF;
    if ((d->trcsr & RIE) && (d->trcsr & (RDRF | ORFE)) && d->sci_t <= t) return HD6301_VEC_SCI;
    return 0;
}

uint16_t d_irq_vector(const d151801_t *d) {
    uint8_t p = ch_pending(&d->t1) | ch_pending(&d->t2);
    if (p & ICF) return HD6301_VEC_ICF;
    if (p & OCF) return HD6301_VEC_OCF;
    if (d->tof && (d->t1.tcsr & ETOI)) return HD6301_VEC_TOF;
    if ((d->trcsr & RIE) && (d->trcsr & (RDRF | ORFE))) return HD6301_VEC_SCI;
    return 0;
}

void d_sci_tx_done(d151801_t *d) { d->trcsr |= TDRE; }

void d_sci_rx(d151801_t *d, uint8_t byte) {
    if (!(d->trcsr & RE)) return;
    if (d->trcsr & RDRF) d->trcsr |= ORFE;
    else if (!(d->trcsr & ORFE)) d->sci_t = d->now;
    d->rdr = byte;
    d->trcsr |= RDRF;
}

void d_next_match(const d151801_t *d, int ch, int64_t *t, int *level) {
    const d_channel_t *c = ch == 1 ? &d->t1 : &d->t2;
    *t = c->next_match;
    *level = (c->tcsr & OLVL) ? 1 : 0;
}
