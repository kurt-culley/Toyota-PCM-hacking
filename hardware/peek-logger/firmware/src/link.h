// Serial-link state machine for the 17140's RAM-peek link (docs/mr2/serial_link.md).
//
// Pure logic, no hardware access: main.c feeds it the time, the ECU-power sense and each
// received byte, and applies what it asks for (TX line mode, a byte to send, a record to
// print). tests/test_peek_logger.py compiles this same header for the host and drives it
// against the whole-ROM simulator.
//
// The ECU's protocol:
//   - At reset the SCI is enabled only if P23 (its RX, chip pin 11) reads low, so the
//     logger holds its TX low (a break) whenever the ECU is off and for HOLD_US after it
//     powers up, then releases it to the UART's idle high.
//   - One address byte in, the word at that address out, high byte first.
//   - About 1 s without a request switches the link off until the next power-up, so the
//     logger polls continuously.
// Safety: when the ECU stops answering, its pin 11 may be an output again (the fault-code
// line), so the logger stops driving it (TX_HIZ) until the ECU is powered down.

#ifndef PEEK_LINK_H
#define PEEK_LINK_H

#include <stdbool.h>
#include <stdint.h>

#define LINK_HOLD_US 250000u    // break held after the ECU's 5 V appears
#define LINK_TIMEOUT_US 30000u  // a reply takes 4-10 ms in the simulator
#define LINK_MAX_MISSES 3u
#define LINK_MAX_VARS 32u

typedef enum { TX_BREAK, TX_UART, TX_HIZ } tx_mode_t;
typedef enum { ST_OFF, ST_HOLD, ST_POLL, ST_LOST } link_state_t;
typedef enum { REC_NONE, REC_DATA, REC_MISS, REC_STATE } rec_kind_t;

typedef struct {
    tx_mode_t tx;      // line mode to apply now
    int send;          // byte to send, or -1
    rec_kind_t rec;    // record to print, or REC_NONE
    uint8_t addr;      // REC_DATA / REC_MISS
    uint16_t word;     // REC_DATA
    link_state_t state;
} link_out_t;

typedef struct {
    link_state_t state;
    uint32_t t_mark;   // power-up time (HOLD) or request time (POLL)
    uint8_t vars[LINK_MAX_VARS];
    uint8_t nvars, idx, nrx, misses;
    bool waiting;
    uint8_t rx[2];
} link_t;

// Addresses polled by default: RpmWord, Load, MapRaw, TpsOpen, Coolant, Tha, Mixture, InjPulse,
// InjDeadTime, IgnBase, $A9, NEsum, PORT3/PORT4, FuelCut, fault bits. All in $02-$07 or
// $40-$FE, the safe range (docs/mr2/serial_link.md).
static const uint8_t LINK_DEFAULT_VARS[] = {0x77, 0x46, 0x4A, 0x44, 0x53, 0x5F, 0x8C, 0x88,
                                            0x8A, 0xA8, 0xA9, 0x82, 0x06, 0x95, 0x40, 0x42};

static inline bool link_addr_safe(uint8_t a) {
    return (a >= 0x02 && a <= 0x07) || (a >= 0x40 && a <= 0xFE);
}

static inline void link_init(link_t *l) {
    l->state = ST_OFF;
    l->t_mark = 0;
    l->nvars = (uint8_t)sizeof LINK_DEFAULT_VARS;
    for (unsigned i = 0; i < l->nvars; i++) l->vars[i] = LINK_DEFAULT_VARS[i];
    l->idx = l->nrx = l->misses = 0;
    l->waiting = false;
}

// Replace the polled list; unsafe addresses are dropped. Returns the number kept.
static inline unsigned link_set_vars(link_t *l, const uint8_t *a, unsigned n) {
    unsigned k = 0;
    for (unsigned i = 0; i < n && k < LINK_MAX_VARS; i++)
        if (link_addr_safe(a[i])) l->vars[k++] = a[i];
    if (k) {
        l->nvars = (uint8_t)k;
        l->idx = 0;
    }
    return k;
}

static inline tx_mode_t link_tx(link_state_t s) {
    return s == ST_POLL ? TX_UART : s == ST_LOST ? TX_HIZ : TX_BREAK;
}

static inline void link_goto(link_t *l, link_state_t s, uint32_t now, link_out_t *o) {
    l->state = s;
    l->t_mark = now;
    l->waiting = false;
    l->nrx = l->misses = 0;
    l->idx = 0;
    o->rec = REC_STATE;
}

// One step. vcc: the ECU's 5 V is present. rx: a received byte, or -1.
static inline void link_step(link_t *l, uint32_t now, bool vcc, int rx, link_out_t *o) {
    o->send = -1;
    o->rec = REC_NONE;
    if (!vcc) {
        if (l->state != ST_OFF) link_goto(l, ST_OFF, now, o);
    } else {
        switch (l->state) {
        case ST_OFF:
            link_goto(l, ST_HOLD, now, o);
            break;
        case ST_HOLD:
            if (now - l->t_mark >= LINK_HOLD_US) link_goto(l, ST_POLL, now, o);
            break;
        case ST_POLL:
            if (!l->waiting) {
                o->send = l->vars[l->idx];
                l->waiting = true;
                l->nrx = 0;
                l->t_mark = now;
            } else if (rx >= 0) {
                l->rx[l->nrx++] = (uint8_t)rx;
                if (l->nrx == 2) {
                    o->rec = REC_DATA;
                    o->addr = l->vars[l->idx];
                    o->word = (uint16_t)(l->rx[0] << 8 | l->rx[1]);
                    l->waiting = false;
                    l->misses = 0;
                    if (++l->idx >= l->nvars) l->idx = 0;
                }
            } else if (now - l->t_mark > LINK_TIMEOUT_US) {
                o->rec = REC_MISS;
                o->addr = l->vars[l->idx];
                l->waiting = false;
                if (++l->misses >= LINK_MAX_MISSES) link_goto(l, ST_LOST, now, o);
            }
            break;
        case ST_LOST:
            break;
        }
    }
    o->tx = link_tx(l->state);
    o->state = l->state;
}

#endif
