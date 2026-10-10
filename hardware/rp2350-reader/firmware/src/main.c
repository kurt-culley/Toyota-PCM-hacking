// HD6301V1 / D151801 internal-ROM reader for the RP2350 (P3).
//
// The 6301 runs in mode 0 with its own internal ROM. This firmware clocks it (EXTAL),
// holds and releases its RES line, serves the tiny dump program from page $C0xx plus the
// reset vector, and receives the ROM over the 6301's SCI. It also snoops every internal
// read on the bus as a second, independent copy.
//
// Core 1 serves the bus (one PIO word in, one word out per 6301 cycle) and nothing else.
// Core 0 runs the USB console. See docs/hardware/rp2350_reader_guide.md for the wiring
// and the bring-up order: rigcheck, clock, listen, probe, dump.
//
// Safety rules kept here:
//   - RES is held low from power-up and is only released when E has been running at
//     EXTAL/4 for at least 100 ms (power-good). If E stops during a run, RES goes low.
//   - The reader drives AD0-AD7 only as decode.h allows (never internal space).
//   - EXTAL and RES are open-drain: the RP2350 never drives a 5 V input high.
//   - No internal pull-downs, ever (RP2350 erratum E9). Pull-ups only in rigcheck,
//     which refuses to run if the 5 V rail is on.

#include <stdio.h>
#include <string.h>

#include "decode.h"
#include "hardware/clocks.h"
#include "hardware/gpio.h"
#include "hardware/pio.h"
#include "hardware/sync.h"
#include "pico/multicore.h"
#include "pico/stdlib.h"
#include "pins.h"
#include "reader.pio.h"
#include "romdump.h"

#define EXTAL_HZ 1000000u
#define E_HZ (EXTAL_HZ / 4u)
#define SCI_BAUD (E_HZ / 16u)  // RMCR = $04: E/16
#define SNOOP_DELAY_NS 1200u   // sample AD 1.2 us into the ~2 us E-high phase
#define LOG_N 64u
#define RUNS 3u
#define MAX_STREAM (1u + 0x2000u)  // mode byte + $E000-$FFFF

// ---- shared with core 1 ---------------------------------------------------------------

typedef struct {
    uint16_t addr;
    uint8_t data;  // driven byte, or the snoop sample
    uint8_t flags;
} cycle_log_t;
#define LOG_READ 1u
#define LOG_DROVE 2u
#define LOG_LATE 4u

static decode_t dec;
static volatile bool listen_only = true;
static volatile uint32_t release_req, release_seen, assert_req, assert_seen;
static volatile uint32_t bus_cycles, late_cycles, drive_cycles;
static volatile uint32_t log_count;
static cycle_log_t cycle_log[LOG_N];
static uint8_t snoop_img[0x10000];
static uint32_t snoop_seen[0x10000 / 32];

static uint8_t serve_page[256];  // served from RAM: no flash-cache stalls on core 1

static PIO pio = pio0;      // bus server and EXTAL clock
static PIO pio_sci = pio1;  // SCI receiver (pio0 is full)
static uint sm_bus, sm_clk, sm_sci;

// Core 1: one address word per cycle, optionally followed by a snoop word (bit 31 set).
// It sends an answer only for a cycle it drives, and only if it is still in time: E has
// not risen yet and the PIO has queued nothing newer. Once it is late, it stops driving
// until the next reset (the dump then fails visibly instead of risking contention).
static void __not_in_flash_func(core1_bus)(void) {
    save_and_disable_interrupts();
    bool have_prev = false, prev_listened = false, given_up = false;
    uint16_t prev_addr = 0;
    uint32_t prev_log = LOG_N;
    for (;;) {
        uint32_t w = pio_sm_get_blocking(pio, sm_bus);
        if (w >> 31) {  // snoop sample (bit 8 set) or early-release marker for the previous cycle
            if (have_prev && prev_listened && (w & 0x100u)) {
                snoop_img[prev_addr] = (uint8_t)w;
                snoop_seen[prev_addr >> 5] |= 1u << (prev_addr & 31);
            }
            if (prev_log < LOG_N && !(cycle_log[prev_log].flags & LOG_DROVE) && (w & 0x100u))
                cycle_log[prev_log].data = (uint8_t)w;
            have_prev = false;
            continue;
        }
        if (assert_seen != assert_req) {
            assert_seen = assert_req;
            decode_assert_reset(&dec);
        }
        if (release_seen != release_req) {
            // arm the decoder and release RES together, so the vector window counts
            // from the moment RES rises
            decode_release_reset(&dec);
            log_count = 0;
            given_up = false;
            gpio_set_dir(PIN_RES, GPIO_IN);
            release_seen = release_req;
        }
        uint16_t addr = (uint16_t)((w & 0xFFu) | (((w >> BUS_AHI_OFF) & 0xFFu) << 8));
        bool read = (w >> BUS_RW_OFF) & 1u;
        int d = decode_cycle(&dec, addr, read);
        if (listen_only || given_up)
            d = DECODE_LISTEN;
        uint8_t flags = read ? LOG_READ : 0;
        if (d >= 0) {
            if (gpio_get(PIN_E) || !pio_sm_is_rx_fifo_empty(pio, sm_bus)) {
                given_up = true;  // too late for this cycle: never drive again this run
                late_cycles++;
                flags |= LOG_LATE;
                d = DECODE_LISTEN;
            } else {
                pio_sm_put(pio, sm_bus, 0xFF00u | (uint32_t)d);
                // Confirm the PIO took it at E rise. If it is still queued after E rose,
                // this cycle was not driven: count it late and stop driving this run.
                uint32_t spin = 0;
                while (!gpio_get(PIN_E) && ++spin < 4000u)
                    tight_loop_contents();
                for (int k = 0; k < 16; k++)  // > the PIO's input sync + pull latency
                    __asm volatile("nop");
                if (!pio_sm_is_tx_fifo_empty(pio, sm_bus)) {
                    given_up = true;
                    late_cycles++;
                    flags |= LOG_LATE;
                    d = DECODE_LISTEN;
                } else {
                    drive_cycles++;
                    flags |= LOG_DROVE;
                }
            }
        }
        bus_cycles++;
        have_prev = true;
        prev_addr = addr;
        prev_listened = d < 0 && read && !dec.in_reset;
        uint32_t n = log_count;
        prev_log = LOG_N;
        if (n < LOG_N) {
            cycle_log[n] = (cycle_log_t){addr, d >= 0 ? (uint8_t)d : 0u, flags};
            prev_log = n;
            log_count = n + 1;
        }
    }
}

// ---- pins -----------------------------------------------------------------------------

static const struct {
    uint gpio;
    const char *name;
} bus_pins[] = {
    {PIN_AD0 + 0, "AD0 (pin 37)"}, {PIN_AD0 + 1, "AD1 (pin 36)"}, {PIN_AD0 + 2, "AD2 (pin 35)"},
    {PIN_AD0 + 3, "AD3 (pin 34)"}, {PIN_AD0 + 4, "AD4 (pin 33)"}, {PIN_AD0 + 5, "AD5 (pin 32)"},
    {PIN_AD0 + 6, "AD6 (pin 31)"}, {PIN_AD0 + 7, "AD7 (pin 30)"}, {PIN_A8 + 0, "A8 (pin 29)"},
    {PIN_A8 + 1, "A9 (pin 28)"},   {PIN_A8 + 2, "A10 (pin 27)"},  {PIN_A8 + 3, "A11 (pin 26)"},
    {PIN_A8 + 4, "A12 (pin 25)"},  {PIN_A8 + 5, "A13 (pin 24)"},  {PIN_A8 + 6, "A14 (pin 23)"},
    {PIN_A8 + 7, "A15 (pin 22)"},  {PIN_AS, "AS (pin 39)"},       {PIN_E, "E (pin 40)"},
    {PIN_RW, "R/W (pin 38)"},
};
#define N_BUS_PINS (sizeof bus_pins / sizeof bus_pins[0])

static void res_assert(void) {
    gpio_put(PIN_RES, 0);
    gpio_set_dir(PIN_RES, GPIO_OUT);
#ifdef PIN_LED
    gpio_put(PIN_LED, 0);
#endif
}

static void res_release(void) {
    gpio_set_dir(PIN_RES, GPIO_IN);  // the 10k pull-up takes RES to 5 V
#ifdef PIN_LED
    gpio_put(PIN_LED, 1);
#endif
}

static void pins_init(void) {
    // RES first: low before anything else can happen
    gpio_init(PIN_RES);
    gpio_disable_pulls(PIN_RES);
    res_assert();
    for (uint i = 0; i < N_BUS_PINS; i++) {
        gpio_init(bus_pins[i].gpio);
        gpio_disable_pulls(bus_pins[i].gpio);
    }
    for (uint i = 0; i < 8; i++) {
        pio_gpio_init(pio, PIN_AD0 + i);  // PIO drives AD0-7 when decode.h allows
        gpio_disable_pulls(PIN_AD0 + i);
        gpio_set_drive_strength(PIN_AD0 + i, GPIO_DRIVE_STRENGTH_2MA);
    }
    gpio_init(PIN_SCI);
    gpio_disable_pulls(PIN_SCI);
    pio_gpio_init(pio, PIN_EXTAL);
    gpio_disable_pulls(PIN_EXTAL);
    gpio_set_drive_strength(PIN_EXTAL, GPIO_DRIVE_STRENGTH_12MA);
#ifdef PIN_LED
    gpio_init(PIN_LED);
    gpio_set_dir(PIN_LED, GPIO_OUT);
    gpio_put(PIN_LED, 0);
#endif
}

static void pio_init_all(void) {
#if PIO_GPIO_BASE
    pio_set_gpio_base(pio, PIO_GPIO_BASE);
#endif
    float sys = (float)clock_get_hz(clk_sys);

    // EXTAL: output value 0, direction toggled
    sm_clk = pio_claim_unused_sm(pio, true);
    uint off = pio_add_program(pio, &extal_od_program);
    pio_sm_config c = extal_od_program_get_default_config(off);
    sm_config_set_set_pins(&c, PIN_EXTAL, 1);
    sm_config_set_clkdiv(&c, sys / (2.0f * EXTAL_HZ));
    pio_sm_set_pins_with_mask64(pio, sm_clk, 0, 1ull << PIN_EXTAL);
    pio_sm_set_pindirs_with_mask64(pio, sm_clk, 0, 1ull << PIN_EXTAL);
    pio_sm_init(pio, sm_clk, off, &c);

    // SCI receiver, 8 PIO clocks per bit
#if PIO_GPIO_BASE
    pio_set_gpio_base(pio_sci, PIO_GPIO_BASE);
#endif
    sm_sci = pio_claim_unused_sm(pio_sci, true);
    off = pio_add_program(pio_sci, &sci_rx_program);
    c = sci_rx_program_get_default_config(off);
    sm_config_set_in_pins(&c, PIN_SCI);
    sm_config_set_jmp_pin(&c, PIN_SCI);
    sm_config_set_in_shift(&c, true, false, 32);
    sm_config_set_fifo_join(&c, PIO_FIFO_JOIN_RX);
    sm_config_set_clkdiv(&c, sys / (8.0f * SCI_BAUD));
    pio_sm_init(pio_sci, sm_sci, off, &c);

    // bus server: AD0-7 start as inputs
    sm_bus = pio_claim_unused_sm(pio, true);
    off = pio_add_program(pio, &bus6301_program);
    c = bus6301_program_get_default_config(off);
    sm_config_set_in_pins(&c, BUS_BASE);
    sm_config_set_out_pins(&c, PIN_AD0, 8);
    sm_config_set_jmp_pin(&c, PIN_E);
    sm_config_set_in_shift(&c, false, false, 32);
    sm_config_set_out_shift(&c, true, false, 32);
    pio_sm_set_pins_with_mask64(pio, sm_bus, 0, 0xFFull << PIN_AD0);
    pio_sm_set_pindirs_with_mask64(pio, sm_bus, 0, 0xFFull << PIN_AD0);
    pio_sm_init(pio, sm_bus, off, &c);
    pio_sm_put(pio, sm_bus, (uint32_t)(SNOOP_DELAY_NS * (sys / 1e9f) / 2.0f));  // 2 clocks per pass

    pio_sm_set_enabled(pio_sci, sm_sci, true);
    pio_sm_set_enabled(pio, sm_bus, true);
    pio_sm_set_enabled(pio, sm_clk, true);
}

// ---- measurements ---------------------------------------------------------------------

typedef struct {
    uint32_t hz;
    uint32_t duty_pct;
} emeas_t;

static emeas_t measure_e(uint32_t ms) {
    uint32_t t0 = time_us_32(), edges = 0, hi = 0, samples = 0;
    bool last = gpio_get(PIN_E);
    while (time_us_32() - t0 < ms * 1000u) {
        for (int k = 0; k < 256; k++) {
            bool v = gpio_get(PIN_E);
            edges += v && !last;
            hi += v;
            last = v;
        }
        samples += 256;
    }
    uint32_t us = time_us_32() - t0;
    return (emeas_t){(uint32_t)((uint64_t)edges * 1000000u / us), samples ? hi * 100u / samples : 0};
}

static bool power_good(bool verbose) {
    emeas_t m = measure_e(100);
    bool ok = m.hz > E_HZ * 95 / 100 && m.hz < E_HZ * 105 / 100;
    if (verbose || !ok)
        printf("E: %lu Hz (want %lu), high %lu%% -> %s\n", (unsigned long)m.hz, (unsigned long)E_HZ,
               (unsigned long)m.duty_pct, ok ? "OK" : "NOT RUNNING: is the 5 V jumper in? is EXTAL wired?");
    return ok;
}

// ---- runs -----------------------------------------------------------------------------

static void end_run(void) {
    listen_only = true;
    res_assert();
    assert_req++;
}

static bool start_run(const uint8_t *page, bool drive) {
    end_run();
    sleep_ms(50);  // RES low >= 20 ms with the clock running
    if (!power_good(false))
        return false;
    memset(snoop_seen, 0, sizeof snoop_seen);
    while (!pio_sm_is_rx_fifo_empty(pio_sci, sm_sci))
        (void)pio_sm_get(pio_sci, sm_sci);
    if (page)
        memcpy(serve_page, page, sizeof serve_page);
    dec.page = page ? serve_page : NULL;
    dec.vector = ROMDUMP_VECTOR;
    late_cycles = drive_cycles = 0;
    listen_only = !drive;
    __dmb();
    release_req++;  // core 1 releases RES on its next bus cycle
    uint32_t t0 = time_us_32();
    while (release_seen != release_req && time_us_32() - t0 < 1000u)
        tight_loop_contents();
    // No bus cycles while in reset: release RES here; core 1 arms the decoder on the
    // first cycle after, which is then cycle 0 of the window.
    res_release();
    return true;
}

// Receive up to want bytes from the SCI. Stops early if the bus stops (E lost).
static uint32_t receive(uint8_t *buf, uint32_t want, uint32_t timeout_ms) {
    uint32_t n = 0, t0 = time_us_32(), tick = t0, cyc = bus_cycles;
    while (n < want && time_us_32() - t0 < timeout_ms * 1000u) {
        if (!pio_sm_is_rx_fifo_empty(pio_sci, sm_sci))
            buf[n++] = (uint8_t)(pio_sm_get(pio_sci, sm_sci) >> 24);
        if (time_us_32() - tick > 5000u) {
            if (bus_cycles == cyc) {
                end_run();
                printf("ABORT: bus stopped (E lost) after %lu bytes; RES asserted\n", (unsigned long)n);
                return n;
            }
            cyc = bus_cycles;
            tick = time_us_32();
        }
    }
    return n;
}

static void print_log(void) {
    uint32_t n = log_count;
    printf("cycle  addr   r/w  data  note\n");
    for (uint32_t i = 0; i < n && i < LOG_N; i++) {
        cycle_log_t e = cycle_log[i];
        printf("%5lu  $%04X  %s    $%02X   %s%s\n", (unsigned long)i, e.addr, (e.flags & LOG_READ) ? "R" : "W",
               e.data, (e.flags & LOG_DROVE) ? "served" : "listened",
               (e.flags & LOG_LATE) ? " LATE (not driven)" : "");
    }
}

// ---- console commands -----------------------------------------------------------------

static void cmd_rigcheck(void) {
    printf("rigcheck: 6301 OUT of its socket, 5 V jumper OUT.\n");
    pio_sm_set_enabled(pio, sm_clk, false);
    pio_sm_set_pindirs_with_mask64(pio, sm_clk, 0, 1ull << PIN_EXTAL);
    gpio_set_dir(PIN_RES, GPIO_IN);
    sleep_ms(5);
    bool hot = gpio_get(PIN_RES) || gpio_get(PIN_EXTAL) || gpio_get(PIN_SCI);
    if (hot) {
        printf("FAIL: RES/EXTAL/SCI read high, so the 5 V rail is on. Unplug the 5 V jumper and retry.\n");
        goto out;
    }
    if (measure_e(20).hz) {
        printf("FAIL: E is toggling, so a chip is running. Remove the 6301 and retry.\n");
        goto out;
    }
    uint faults = 0;
    for (uint i = 0; i < N_BUS_PINS; i++)
        gpio_pull_up(bus_pins[i].gpio);  // pull-ups only: never pull-downs (erratum E9)
    sleep_ms(5);
    for (uint i = 0; i < N_BUS_PINS; i++)
        if (!gpio_get(bus_pins[i].gpio)) {
            printf("FAIL: %s (GP%u) stuck low: shorted to GND or a strap\n", bus_pins[i].name, bus_pins[i].gpio);
            faults++;
        }
    for (uint i = 0; i < N_BUS_PINS; i++) {
        uint g = bus_pins[i].gpio;
        if (!gpio_get(g))
            continue;
        gpio_set_drive_strength(g, GPIO_DRIVE_STRENGTH_2MA);
        gpio_set_function(g, GPIO_FUNC_SIO);
        gpio_put(g, 0);
        gpio_set_dir(g, GPIO_OUT);
        sleep_us(200);
        for (uint j = 0; j < N_BUS_PINS; j++)
            if (j != i && !gpio_get(bus_pins[j].gpio)) {
                printf("FAIL: %s (GP%u) is shorted to %s (GP%u)\n", bus_pins[i].name, g, bus_pins[j].name,
                       bus_pins[j].gpio);
                faults++;
            }
        gpio_set_dir(g, GPIO_IN);
        sleep_us(200);
    }
    for (uint i = 0; i < N_BUS_PINS; i++)
        gpio_disable_pulls(bus_pins[i].gpio);
    for (uint i = 0; i < 8; i++)
        pio_gpio_init(pio, PIN_AD0 + i);
    printf(faults ? "rigcheck: %u fault(s)\n" : "rigcheck: PASS (no stuck or shorted lines)\n", faults);
out:
    res_assert();
    pio_sm_set_enabled(pio, sm_clk, true);
}

static void cmd_clock(void) {
    emeas_t m = measure_e(200);
    printf("E: %lu Hz, high %lu%% of the time (want %lu Hz, about 50%%)\n", (unsigned long)m.hz,
           (unsigned long)m.duty_pct, (unsigned long)E_HZ);
    printf("%s\n", power_good(false) ? "clock: PASS" : "clock: FAIL (see the guide's troubleshooting table)");
}

static void cmd_listen(void) {
    if (!start_run(NULL, false))
        return;
    sleep_ms(5);
    end_run();
    printf("listen: RES released for 5 ms with nothing driven.\n");
    print_log();
    // With nothing driving, the vector reads float and echo the address low byte
    // ($FE, $FF). Real data there means the chip drove its vector internally, so the
    // reader must not serve it: probe and dump would collide with the chip.
    int fffe = -1, fffe_at = -1;
    for (uint32_t i = 0; i + 1 < log_count && i < LOG_N - 1; i++)
        if (cycle_log[i].addr == 0xFFFE && cycle_log[i + 1].addr == 0xFFFF) {
            fffe = cycle_log[i].data << 8 | cycle_log[i + 1].data;
            fffe_at = (int)i;
            break;
        }
    if (fffe < 0)
        printf("listen: no $FFFE/$FFFF fetch seen -> FAIL (check AS, E, R/W, RES and the straps)\n");
    else if (fffe_at >= (int)VECTOR_WINDOW)
        printf("listen: vector fetch at cycle %d, after the %u-cycle window -> STOP, send this log to the agent\n",
               fffe_at, VECTOR_WINDOW);
    else if (fffe == 0xFEFF)
        printf("listen: vector fetch at cycle %d reads $FEFF (floating bus, external as expected) -> PASS\n", fffe_at);
    else if (fffe >= 0xF000)
        printf("listen: vector fetch at cycle %d reads $%04X, a plausible internal vector -> STOP: do not run\n"
               "        probe; the chip may be driving its vector itself (wrong mode?). Send this log to the agent.\n",
               fffe_at, fffe);
    else
        printf("listen: vector fetch at cycle %d reads $%04X, not the floating $FEFF -> UNCLEAR: send this log\n"
               "        to the agent before running probe.\n",
               fffe_at, fffe);
}

static void cmd_res(void) {
    if (!start_run(NULL, false))
        return;
    printf("res: RES released for 15 s, nothing driven. Measure chip pin 6 to GND now (want >= 4.5 V).\n");
    sleep_ms(15000);
    end_run();
    printf("res: RES held low again.\n");
}

static uint8_t probe_page[256];

static void cmd_probe(void) {
    memset(probe_page, 0x1A, sizeof probe_page);  // SLP
    probe_page[0xC0] = 0x20;                      // $C0C0: BRA $C0C0
    probe_page[0xC1] = 0xFE;
    if (!start_run(probe_page, true))
        return;
    sleep_ms(5);
    end_run();
    print_log();
    bool vec = false, fetch = false;
    for (uint32_t i = 0; i + 1 < log_count && i < LOG_N; i++) {
        if (cycle_log[i].addr == 0xFFFE && (cycle_log[i].flags & LOG_DROVE) && cycle_log[i + 1].addr == 0xFFFF &&
            (cycle_log[i + 1].flags & LOG_DROVE))
            vec = true;
        if (vec && cycle_log[i].addr == 0xC0C0)
            fetch = true;
    }
    printf("probe: vector served %s, $C0C0 fetched %s, late cycles %lu -> %s\n", vec ? "yes" : "NO",
           fetch ? "yes" : "NO", (unsigned long)late_cycles, vec && fetch && !late_cycles ? "PASS" : "FAIL");
}

static uint8_t runs[RUNS][MAX_STREAM];

static void print_hex(const uint8_t *data, uint32_t base, uint32_t len) {
    for (uint32_t o = 0; o < len; o += 16) {
        uint32_t a = base + o, n = len - o < 16 ? len - o : 16;
        uint8_t sum = (uint8_t)(n + (a >> 8) + a);
        printf(":%02lX%04lX00", (unsigned long)n, (unsigned long)(a & 0xFFFF));
        for (uint32_t k = 0; k < n; k++) {
            printf("%02X", data[o + k]);
            sum += data[o + k];
        }
        printf("%02X\n", (uint8_t)(-sum));
    }
    printf(":00000001FF\n");
}

static bool capture(const uint8_t *page, uint32_t start, uint32_t *lens) {
    uint32_t want = 1u + 0x10000u - start;
    for (uint r = 0; r < RUNS; r++) {
        if (!start_run(page, true))
            return false;
        lens[r] = receive(runs[r], want, 2u * want * 1000u / (SCI_BAUD / 10u) + 500u);
        end_run();
        printf("run %u: %lu/%lu bytes, mode byte $%02X, late cycles %lu\n", r + 1, (unsigned long)lens[r],
               (unsigned long)want, lens[r] ? runs[r][0] : 0, (unsigned long)late_cycles);
        if (lens[r] != want)
            return false;
    }
    return true;
}

static void cmd_dump(void) {
    uint32_t lens[RUNS];
    if (!capture(romdump_page, ROMDUMP_START, lens)) {
        printf("DONE FAIL short run\n");
        return;
    }
    const uint32_t len = 0x10000u - ROMDUMP_START;
    const uint8_t *rom = runs[0] + 1;
    uint mode = runs[0][0] >> 5;
    bool same = !memcmp(runs[0], runs[1], len + 1) && !memcmp(runs[0], runs[2], len + 1);
    uint32_t seen = 0, agree = 0, sum = 0;
    for (uint32_t i = 0; i < len - 1; i++) {  // $FFFF: dummy cycles overwrite its snoop
        uint32_t a = ROMDUMP_START + i;
        if (snoop_seen[a >> 5] & (1u << (a & 31))) {
            seen++;
            agree += snoop_img[a] == rom[i];
        }
    }
    for (uint32_t i = 0; i < len; i += 2)
        sum += (uint32_t)(rom[i] << 8 | rom[i + 1]);
    printf("mode %u (want 0), runs identical: %s\n", mode, same ? "yes" : "NO");
    printf("snoop channel: %lu of %lu bytes seen, %lu agree with the SCI copy ($FFFF not compared)\n",
           (unsigned long)seen, (unsigned long)(len - 1), (unsigned long)agree);
    printf("word sum $%04lX (the Bluetop convention is $AA55)\n", (unsigned long)(sum & 0xFFFF));
    printf("vectors:");
    for (uint32_t a = 0xFFF0; a < 0x10000; a += 2)
        printf(" $%04lX=$%04X", (unsigned long)a, rom[a - ROMDUMP_START] << 8 | rom[a - ROMDUMP_START + 1]);
    printf("\n");
    if (mode != 0 || !same) {
        printf("DONE FAIL %s\n", mode ? "wrong mode: check the P20-P22 straps" : "runs differ");
        return;
    }
    print_hex(rom, ROMDUMP_START, len);
    printf("DONE OK\n");
}

static void cmd_size(void) {
    uint32_t lens[RUNS];
    if (!capture(romsize_page, ROMSIZE_START, lens)) {
        printf("DONE FAIL short run\n");
        return;
    }
    const uint32_t len = 0x10000u - ROMSIZE_START;
    for (uint32_t blk = 0; blk < len; blk += 0x1000) {
        uint32_t differ = 0, echo = 0;
        for (uint32_t i = blk; i < blk + 0x1000; i++) {
            uint8_t v = runs[0][1 + i];
            differ += v != runs[1][1 + i] || v != runs[2][1 + i];
            echo += v == (uint8_t)(ROMSIZE_START + i);
        }
        bool rom = !differ && echo < 0x1000 / 8;
        printf("$%04lX-$%04lX: %lu bytes differ between runs, %lu echo the address -> %s\n",
               (unsigned long)(ROMSIZE_START + blk), (unsigned long)(ROMSIZE_START + blk + 0xFFF),
               (unsigned long)differ, (unsigned long)echo, rom ? "internal ROM" : "not ROM (floating bus)");
    }
    print_hex(runs[0] + 1, ROMSIZE_START, len);
    printf("DONE OK\n");
}

static void help(void) {
    printf("\nHD6301 ROM reader on %s\n", READER_BOARD_NAME);
    printf("Wiring: AD0 GP%u, A8 GP%u, AS GP%u, E GP%u, R/W GP%u, RES GP%u, EXTAL GP%u, SCI GP%u\n", PIN_AD0, PIN_A8,
           PIN_AS, PIN_E, PIN_RW, PIN_RES, PIN_EXTAL, PIN_SCI);
    printf("RES is held low. Plug the 6301 5 V jumper in only now; unplug it before USB.\n");
    printf("Commands: rigcheck  clock  listen  res  probe  dump  size  help\n");
}

int main(void) {
    pins_init();  // RES low first
    stdio_init_all();
    decode_init(&dec, NULL, ROMDUMP_VECTOR);
    pio_init_all();
    multicore_launch_core1(core1_bus);
    while (!stdio_usb_connected())
        sleep_ms(50);
    help();
    char line[32];
    uint n = 0;
    printf("> ");
    for (;;) {
        int ch = getchar_timeout_us(100000);
        if (ch == PICO_ERROR_TIMEOUT)
            continue;
        if (ch != '\r' && ch != '\n') {
            if (n < sizeof line - 1)
                line[n++] = (char)ch;
            continue;
        }
        line[n] = 0;
        n = 0;
        printf("\n");
        if (!strcmp(line, "rigcheck"))
            cmd_rigcheck();
        else if (!strcmp(line, "clock"))
            cmd_clock();
        else if (!strcmp(line, "listen"))
            cmd_listen();
        else if (!strcmp(line, "res"))
            cmd_res();
        else if (!strcmp(line, "probe"))
            cmd_probe();
        else if (!strcmp(line, "dump"))
            cmd_dump();
        else if (!strcmp(line, "size"))
            cmd_size();
        else if (line[0])
            help();
        printf("> ");
    }
}
