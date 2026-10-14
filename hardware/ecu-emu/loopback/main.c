// Loopback test of the real-time D151801 emulator on one Pico 2 W. No wiring.
//
// Core 1: the emulated chip (hd6301 + d151801 + the 17140 ROM) locked to real time: it runs
//         instructions only while its time is behind the real 1 us clock. Input edges reach it
//         as timestamped events; its output pins are driven the moment they change.
// Core 0: the engine, as analysis/emu/engine17140.py models it: NE (30 deg per edge), G every
//         6th edge, the ADC hybrid (P20 falls 20 us + 200 us/V after the hold line drops, for
//         the channel on P12-P14) and the IGF echo 20 us after each spark. It reads the
//         emulator's outputs back through the same pads and measures them.
//
// Each signal is one GPIO: one core drives it, the other reads the pad. Every few seconds the
// operating point changes and core 0 prints what it measured next to what the Python simulator
// predicts for the same inputs (docs/mr2/cpu_replacement.md, "Loopback test").

#include <math.h>
#include <stdio.h>

#include "board.h"
#include "hardware/clocks.h"
#include "hardware/gpio.h"
#include "hardware/sync.h"
#include "pico/multicore.h"
#include "pico/stdlib.h"
#include "rom17140.h"

// Engine side -> emulator inputs
#define PIN_NE 2    // P10, input capture 2
#define PIN_G 3     // P35
#define PIN_ADC 4   // P20, input capture 1 (ADC end)
#define PIN_IGF 5   // IS3
// Emulator outputs -> engine side
#define PIN_IGT 6   // P11, output compare 2
#define PIN_SEL0 7  // P12-P14: ADC channel
#define PIN_HOLD 10 // P15: ADC hold / start
#define PIN_INJ 11  // P21, output compare 1 (injector, active low)

// ---- events from core 0 to core 1 (single producer, single consumer) ----------------------
typedef struct {
    int64_t t;
    uint8_t kind, level;
} ev_t;
enum { EV_NE, EV_G, EV_ADC, EV_IS3 };
#define RING 1024u
static ev_t ring[RING];
static volatile uint32_t r_head, r_tail;
static uint64_t t0;

static void push(int64_t t, int kind, int level) {
    uint32_t h = r_head;
    ring[h % RING] = (ev_t){t, (uint8_t)kind, (uint8_t)level};
    __dmb();
    r_head = h + 1;
}

// ---- core 1: the emulated chip -------------------------------------------------------------
static board_t b;
static volatile int64_t max_lag, busy_us;
static volatile int64_t last_igt_fall_emu;

static int64_t next_ev(void *ctx) {
    (void)ctx;
    if (r_tail == r_head) return -1;
    __dmb();
    return ring[r_tail % RING].t;
}

static void run_ev(void *ctx) {
    (void)ctx;
    ev_t e = ring[r_tail % RING];
    __dmb();
    r_tail = r_tail + 1;
    switch (e.kind) {
    case EV_NE: d_set_pin_at(&b.io, 1, 0, e.level, e.t); break;
    case EV_ADC: d_set_pin_at(&b.io, 2, 0, e.level, e.t); break;
    case EV_G: d_set_pin(&b.io, 3, 5, e.level); break;
    case EV_IS3: d_is3_edge(&b.io); break;
    }
}

static void on_output(void *ctx, int port, int bit, int level, int64_t t) {
    (void)ctx;
    int pin = -1;
    if (port == 1 && bit >= 1 && bit <= 5) pin = PIN_IGT + bit - 1;  // P11..P15 -> GP6..GP10
    if (port == 2 && bit == 1) pin = PIN_INJ;
    if (pin < 0) return;
    gpio_put((uint)pin, level);
    if (pin == PIN_IGT && !level) last_igt_fall_emu = t;
}

static void core1_main(void) {
    for (;;) {
        int64_t rt = (int64_t)(time_us_64() - t0);
        int64_t lag = rt - b.io.now;
        if (lag > max_lag) max_lag = lag;
        if (lag > 0) {
            uint64_t s = time_us_64();
            while (b.io.now < rt) board_step(&b);
            busy_us += (int64_t)(time_us_64() - s);
        }
    }
}

// ---- core 0: the engine and the measurements ----------------------------------------------
typedef struct {
    int rpm;
    float kpa, tps;
    // Python simulator, same inputs, 3 s after power-up (tests/test_d151801_c.py setup)
    int rpm_word;
    float spark_deg;
    int inj_us;
} scen_t;
static const scen_t SCEN[] = {
    {800, 35, 0.6f, 256, 118.71f, 1988},
    {2000, 50, 1.5f, 639, 122.69f, 2633},
    {5000, 95, 4.0f, 1600, 123.63f, 5536},
};
static volatile float volts[8];

static void set_scenario(const scen_t *s) {
    float v[8] = {0.0f, 0.6f + 0.03f * s->kpa, s->tps, 2.5f, 3.5f, 0.5f, 2.5f, 5.0f};
    for (int i = 0; i < 8; i++) volts[i] = v[i];
}

typedef struct {
    int sparks, injs, adcs;
    double deg_sum, deg_min, deg_max;
    int64_t inj_sum, inj_min, inj_max, out_err_max, stim_late_max;
} stats_t;

static void stats_reset(stats_t *s) {
    *s = (stats_t){0};
    s->deg_min = 1e9;
    s->inj_min = INT64_MAX;
}

int main(void) {
    stdio_init_all();
    const uint32_t ins = (1u << PIN_NE) | (1u << PIN_G) | (1u << PIN_ADC) | (1u << PIN_IGF);
    const uint32_t outs = (0x3Fu << PIN_IGT);
    gpio_init_mask(ins | outs);
    gpio_set_dir_out_masked(ins | outs);
    gpio_put(PIN_NE, 1);  // the model's pins start high (emu.periph: pins = 0xFF)
    gpio_put(PIN_ADC, 1);
    gpio_put(PIN_IGF, 1);
    gpio_put(PIN_G, 0);

    b.io.on_output = on_output;
    b.next_ev = next_ev;
    b.run_ev = run_ev;
    board_init(&b, ROM17140, 4096);
    d_set_pin(&b.io, 3, 0, 1);  // T open (Engine17140.update_sensors)
    d_set_pin(&b.io, 3, 4, 1);  // J8: P34 = 1
    d_set_pin(&b.io, 3, 6, 0);
    d_set_pin(&b.io, 3, 5, 0);  // G low
    sleep_ms(2500);  // time to open the serial port
    printf("ecu_emu_loopback: emulated D151801 + 17140 ROM on core 1, engine on core 0, CPU %lu MHz\n",
           (unsigned long)(clock_get_hz(clk_sys) / 1000000));

    unsigned si = 0;
    const scen_t *sc = &SCEN[0];
    set_scenario(sc);
    t0 = time_us_64();
    multicore_launch_core1(core1_main);

    int64_t next_tooth = 1000, g_low = -1, ne_low = -1, adc_low = -1, igf_low = -1, igf_high = -1;
    int64_t tooth_t = 0, tooth_T = 0, inj_fall = -1, phase_start = 0;
    int edge = 0, tooth_edge = 0, measuring = 0;
    uint32_t last = gpio_get_all();
    stats_t st;
    stats_reset(&st);

    for (;;) {
        int64_t now = (int64_t)(time_us_64() - t0);
        int64_t T = (int64_t)llround(60e6 / sc->rpm / 12.0);
        // -- stimulus: drive the pin, then hand the edge to the emulator with its drive time
        if (now >= next_tooth) {
            int64_t late = now - next_tooth;
            if (measuring && late > st.stim_late_max) st.stim_late_max = late;
            edge++;
            if (edge % 6 == 0) {
                gpio_put(PIN_G, 1);
                push(now, EV_G, 1);
                g_low = next_tooth + T / 2;
            }
            gpio_put(PIN_NE, 1);
            push(now, EV_NE, 1);
            tooth_T = next_tooth - tooth_t;
            tooth_t = next_tooth;
            tooth_edge = edge;
            ne_low = next_tooth + T / 2;
            next_tooth += T;
        }
        if (g_low >= 0 && now >= g_low) { gpio_put(PIN_G, 0); push(now, EV_G, 0); g_low = -1; }
        if (ne_low >= 0 && now >= ne_low) { gpio_put(PIN_NE, 0); push(now, EV_NE, 0); ne_low = -1; }
        if (adc_low >= 0 && now >= adc_low) { gpio_put(PIN_ADC, 0); push(now, EV_ADC, 0); adc_low = -1; }
        if (igf_low >= 0 && now >= igf_low) { gpio_put(PIN_IGF, 0); push(now, EV_IS3, 0); igf_low = -1; }
        if (igf_high >= 0 && now >= igf_high) { gpio_put(PIN_IGF, 1); igf_high = -1; }

        // -- the emulator's outputs, read back through the pads
        uint32_t pins = gpio_get_all();
        uint32_t chg = (pins ^ last) & outs;
        last = pins;
        if (chg & (1u << PIN_HOLD)) {
            if (pins & (1u << PIN_HOLD)) {  // hold: ADC end line back high
                adc_low = -1;
                gpio_put(PIN_ADC, 1);
                push(now, EV_ADC, 1);
            } else {  // conversion starts: end after 20 us + 200 us/V of the selected channel
                int ch = (int)((pins >> PIN_SEL0) & 7);
                adc_low = now + (int64_t)lroundf(20.0f + 200.0f * volts[ch]);
                if (measuring) st.adcs++;
            }
        }
        if ((chg & (1u << PIN_IGT)) && !(pins & (1u << PIN_IGT))) {  // spark
            igf_low = now + 20;
            igf_high = now + 40;
            if (measuring && tooth_T > 0) {
                double deg = (tooth_edge % 6) * 30.0 + (double)(now - tooth_t) * 30.0 / (double)tooth_T;
                st.sparks++;
                st.deg_sum += deg;
                if (deg < st.deg_min) st.deg_min = deg;
                if (deg > st.deg_max) st.deg_max = deg;
                int64_t err = now - last_igt_fall_emu;
                if (err > st.out_err_max) st.out_err_max = err;
            }
        }
        if (chg & (1u << PIN_INJ)) {
            if (!(pins & (1u << PIN_INJ))) {
                inj_fall = now;
            } else if (inj_fall >= 0 && measuring) {
                int64_t w = now - inj_fall;
                st.injs++;
                st.inj_sum += w;
                if (w < st.inj_min) st.inj_min = w;
                if (w > st.inj_max) st.inj_max = w;
            }
        }

        // -- phases: 3 s to settle, 3 s to measure, then report and move on
        if (!measuring && now - phase_start >= 3000000) {
            measuring = 1;
            stats_reset(&st);
            max_lag = 0;
            busy_us = 0;
            phase_start = now;
        } else if (measuring && now - phase_start >= 3000000) {
            double secs = (double)(now - phase_start) / 1e6, revs = sc->rpm / 60.0 * secs;
            int rpm_word = (b.mem[0x77] << 8) | b.mem[0x78];
            printf("\n%d rpm, %.0f kPa (simulator in brackets)\n", sc->rpm, (double)sc->kpa);
            printf("  RpmWord %d [%d]\n", rpm_word, sc->rpm_word);
            if (st.sparks)
                printf("  spark %.2f deg after the G edge, range %.2f..%.2f [%.2f]; %.2f per rev [2.00]\n",
                       st.deg_sum / st.sparks, st.deg_min, st.deg_max, (double)sc->spark_deg, st.sparks / revs);
            if (st.injs)
                printf("  injector %lld us, range %lld..%lld [%d]; %.2f per rev [about 1]\n",
                       (long long)(st.inj_sum / st.injs), (long long)st.inj_min, (long long)st.inj_max, sc->inj_us,
                       st.injs / revs);
            printf("  ADC conversions %d; emulator busy %.0f %%, max lag %lld us; spark pin late by up to %lld us; "
                   "stimulus late by up to %lld us\n",
                   st.adcs, 100.0 * (double)busy_us / ((double)(now - phase_start)), (long long)max_lag,
                   (long long)st.out_err_max, (long long)st.stim_late_max);
            si = (si + 1) % (sizeof SCEN / sizeof SCEN[0]);
            sc = &SCEN[si];
            set_scenario(sc);
            measuring = 0;
            phase_start = now;
        }
    }
}
