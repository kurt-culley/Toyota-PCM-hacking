// D151801 on-chip peripherals in C: timer 1, the Denso second timer, SCI, ports 1-4 and the
// IS3 (IGF) flag. A line-for-line port of analysis/emu/periph.py, so the C board can be checked
// against the Python simulator (tests/test_d151801_c.py). Times are E-clock cycles (us at
// E = 1 MHz) since power-up.
//
// External inputs come in through d_set_pin() / d_is3_edge(); output pin changes go out
// through the output callback. In the host test the "events" are the Python engine model's;
// in the RP2350 firmware they will be PIO edge timestamps.

#ifndef D151801_H
#define D151801_H

#include <stdint.h>

typedef struct {
    uint8_t tcsr, armed, pin_in, pin_out;
    uint16_t ocr, icr;
} d_channel_t;

// Output pin change: port 1..4, bit 0..7, level 0/1, time.
typedef void (*d_output_fn)(void *ctx, int port, int bit, int level, int64_t t);
// A byte written to TDR while the transmitter is enabled.
typedef void (*d_tx_fn)(void *ctx, uint8_t byte, int64_t t);
// External events (host side): time of the next one (or -1), and run it.
typedef int64_t (*d_next_event_fn)(void *ctx);
typedef void (*d_run_event_fn)(void *ctx);

typedef struct {
    int64_t now;
    uint16_t frc_offset;
    uint8_t frc_hi_written;
    d_channel_t t1, t2;
    uint8_t tof;
    uint8_t ddr[4], latch[4], pins[4], last_out[4];
    uint8_t p3csr, is3_armed;
    uint8_t rmcr, trcsr, rdr, sci_armed;
    uint8_t regs[0x20];  // registers without a model (RAMCR $14, unused ones)
    d_output_fn on_output;
    d_tx_fn on_tx;
    void *ctx;
} d151801_t;

void d_init(d151801_t *d);
uint8_t d_read(d151801_t *d, uint16_t a);   // a in $00-$1F
void d_write(d151801_t *d, uint16_t a, uint8_t v);
uint16_t d_frc(const d151801_t *d);
uint8_t d_port_out(const d151801_t *d, int i);  // port index 0..3: pin levels
// Advance time by n cycles: run due external events and output compares in time order.
void d_advance(d151801_t *d, int64_t n, d_next_event_fn next_ev, d_run_event_fn run_ev, void *ev_ctx);
void d_set_pin(d151801_t *d, int port, int bit, int level);
void d_is3_edge(d151801_t *d);
// Highest-priority pending maskable interrupt vector, or 0 (ICF > OCF > TOF > SCI).
uint16_t d_irq_vector(const d151801_t *d);
// SCI line side: the transmitted byte has left (TDRE set again); a byte arrives in RDR.
void d_sci_tx_done(d151801_t *d);
void d_sci_rx(d151801_t *d, uint8_t byte);

#endif
