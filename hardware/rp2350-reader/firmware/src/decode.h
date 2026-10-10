// The reader's drive/listen rule. Mirrors analysis/pcmre/readerdecode.py line for line;
// tests/test_romdump.py runs that model against the dump program in the emulator.
#pragma once

#include <stdbool.h>
#include <stdint.h>

// Bus cycles after RES rises: $FFFF (dummy), $FFFE, $FFFF. The handbook allows "3 or 4";
// 3 is the safe reading. Never raise it: outside the window the vector is internal.
#define VECTOR_WINDOW 3u
#define PROGRAM_PAGE 0xC0u
#define DECODE_LISTEN (-1)

typedef struct {
    const uint8_t *page;  // 256 bytes served at $C000-$C0FF
    uint16_t vector;
    bool in_reset;
    uint32_t cycle_no;
    bool locked;
    bool last_drove_fffe;
} decode_t;

static inline void decode_init(decode_t *d, const uint8_t *page, uint16_t vector) {
    d->page = page;
    d->vector = vector;
    d->in_reset = true;
    d->cycle_no = 0;
    d->locked = true;
    d->last_drove_fffe = false;
}

static inline void decode_assert_reset(decode_t *d) {
    d->in_reset = true;
    d->locked = true;
    d->last_drove_fffe = false;
}

static inline void decode_release_reset(decode_t *d) {
    d->in_reset = false;
    d->cycle_no = 0;
    d->locked = false;
    d->last_drove_fffe = false;
}

// One bus cycle. Returns the byte to drive, or DECODE_LISTEN.
static inline int decode_cycle(decode_t *d, uint16_t addr, bool read) {
    if (d->in_reset)
        return DECODE_LISTEN;
    uint32_t n = d->cycle_no++;
    bool follows_fffe = d->last_drove_fffe;
    d->last_drove_fffe = false;
    if (!read)
        return DECODE_LISTEN;
    if (!d->locked) {
        if (addr == 0xFFFE && n < VECTOR_WINDOW) {
            d->last_drove_fffe = true;
            return d->vector >> 8;
        }
        if (addr == 0xFFFF && follows_fffe && n < VECTOR_WINDOW) {
            d->locked = true;
            return d->vector & 0xFF;
        }
        if (n >= VECTOR_WINDOW)
            d->locked = true;
    }
    if ((addr >> 8) == PROGRAM_PAGE && d->page)
        return d->page[addr & 0xFF];
    return DECODE_LISTEN;
}
