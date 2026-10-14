// Loopback test of the real-time D151801 emulator on one Pico 2 W. No wiring.
//
// Core 1 runs the emulated chip (hd6301 + d151801 + the 17140 ROM) locked to real time: it
// never runs ahead of the 1 us clock, nor past the last crank edge core 0 has queued. The
// engine model (engine.h: the same behaviour as analysis/emu/engine17140.py) runs inside it at
// exact emulated times, and the emulator drives its output pins as they change (IGT GP6, ADC
// select GP7-9, hold GP10, injector GP11).
// Core 0 queues the crank edges ahead of time and reads the spark pin back through its pad to
// measure how late it is.
//
// The schedule (800 rpm / 35 kPa, 2000 / 50, 5000 / 95, 6 s each) is the one emu.loopback_ref
// runs on the host. At the end of each phase core 1 checksums every output edge of seconds 3-6
// and the RAM; core 0 prints PASS if they equal the host's (expected.h): the real-time emulator
// is then bit-exact to the simulator. tests/test_loopback_engine.py runs engine.h on the host
// against the same expected.h.

#include <stdio.h>

#include "board.h"
#include "expected.h"
#include "hardware/clocks.h"
#include "hardware/gpio.h"
#include "hardware/sync.h"
#include "pico/multicore.h"
#include "pico/stdlib.h"
#include "rom17140.h"
#define ENG_DMB() __dmb()
#include "engine.h"

#define PIN_IGT 6   // P11 (OC2); P12-P15 follow on GP7-GP10
#define PIN_INJ 11  // P21 (OC1)
#define AHEAD_US 2000

static uint64_t t0;
static board_t b;
static eng_t eng;

typedef struct {
    eng_result_t r;
    int64_t max_lag, busy_us;
} phase_t;
static phase_t res[REF_PHASES];
static volatile int done_phases;
static volatile int64_t igt_fall_emu;

static void pin_out(int port, int bit, int level, int64_t t) {
    if (port == 1 && bit >= 1 && bit <= 5) {
        if (bit == 1 && !level) igt_fall_emu = t;
        gpio_put((uint)(PIN_IGT + bit - 1), level);
    } else if (port == 2 && bit == 1) {
        gpio_put(PIN_INJ, level);
    }
}

static void core1_main(void) {
    int phase = 0;
    int64_t boundary = REF_PHASE_US, lag_max = 0, busy = 0;
    for (;;) {
        int64_t rt = (int64_t)(time_us_64() - t0);
        int64_t q = eng.queued_until;
        int64_t lim = rt < q ? rt : q;
        if (rt - b.io.now > lag_max) lag_max = rt - b.io.now;
        if (b.io.now >= lim) continue;
        uint64_t s = time_us_64();
        while (b.io.now < lim) {
            board_step(&b);
            if (b.io.now >= boundary && phase < REF_PHASES) {  // = Simulation.run_until(boundary)
                eng_phase_end(&eng, &res[phase].r);
                uint64_t s2 = time_us_64();
                res[phase].max_lag = lag_max;
                res[phase].busy_us = busy + (int64_t)(s2 - s);
                busy = -(int64_t)(s2 - s);
                lag_max = 0;
                __dmb();
                done_phases = ++phase;
                boundary += REF_PHASE_US;
            }
        }
        busy += (int64_t)(time_us_64() - s);
    }
}

int main(void) {
    stdio_init_all();
    gpio_init_mask(0x3Fu << PIN_IGT);
    gpio_set_dir_out_masked(0x3Fu << PIN_IGT);
    eng_attach(&eng, &b);
    eng.pin_out = pin_out;
    board_init(&b, ROM17140, 4096);
    eng_set_switches(&eng);
    sleep_ms(2500);  // time to open the serial port
    printf("ecu_emu_loopback v2: emulator locked to real time on core 1, crank on core 0, CPU %lu MHz\n"
           "Each phase must match the simulator bit for bit (expected.h).\n",
           (unsigned long)(clock_get_hz(clk_sys) / 1000000));

    int printed = 0;
    int64_t late_max = 0;
    uint32_t last = gpio_get_all();
    t0 = time_us_64();
    eng_crank_fill(&eng, AHEAD_US);
    multicore_launch_core1(core1_main);

    for (;;) {
        int64_t now = (int64_t)(time_us_64() - t0);
        eng_crank_fill(&eng, now + AHEAD_US);
        uint32_t pins = gpio_get_all();  // the spark pin, read back through its pad
        if (((pins ^ last) & (1u << PIN_IGT)) && !(pins & (1u << PIN_IGT))) {
            int64_t late = now - igt_fall_emu;
            if (late > late_max) late_max = late;
        }
        last = pins;
        if (printed < done_phases) {
            __dmb();
            const phase_t *p = &res[printed];
            const eng_result_t *r = &p->r;
            const ref_t *x = &REF[printed];
            printf("\nphase %d: %d rpm, %.0f kPa: %s\n", printed + 1, x->rpm, x->kpa,
                   eng_result_ok(r, x) ? "PASS (bit-exact with the simulator)" : "FAIL");
            printf("  output edges %lu, CRC %08lX [%lu, %08lX]; RAM CRC %08lX [%08lX]; RpmWord %d [%d]\n",
                   (unsigned long)r->edges, (unsigned long)r->edge_crc, (unsigned long)x->edges,
                   (unsigned long)x->edge_crc, (unsigned long)r->ram_crc, (unsigned long)x->ram_crc, r->rpm_word,
                   x->rpm_word);
            printf("  injector %lu pulses, mean %lu us [%lu, %lu us]\n", (unsigned long)r->inj_n,
                   (unsigned long)(r->inj_n ? r->inj_sum / r->inj_n : 0), (unsigned long)x->inj_n,
                   (unsigned long)(x->inj_n ? x->inj_sum / x->inj_n : 0));
            printf("  emulator busy %.0f %%, max lag %lld us; spark pin late by up to %lld us\n",
                   100.0 * (double)p->busy_us / REF_PHASE_US, (long long)p->max_lag, (long long)late_max);
            late_max = 0;
            if (++printed == REF_PHASES) printf("\nall %d phases done\n", REF_PHASES);
        }
    }
}
