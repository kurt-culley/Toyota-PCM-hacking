// Chip-in-isolation test (docs/hardware/chip_diff_test.md): the real D151801 runs its own 17140
// program in mode 7 on the reader breadboard; this Pico 2 W clocks it, plays the engine around
// it one E cycle at a time, and logs every pin change over USB.
//
//   PIO0: EXTAL, open-drain 500 kHz (E = 125 kHz, the reader's proven clock).
//   PIO1 (chipio.pio): holds /RES low, releases it, then once per E cycle drives the chip's
//         inputs from a DMA ring and samples every pin into a second DMA ring.
//   Core 0: walks the samples (cd_sample: the engine's reactions) and keeps the input ring
//         LOOKAHEAD cycles ahead (cd_word: crank schedule and reactions), both from chipdiff.h.
//   Core 1: prints the pin changes, one line each: "<cycle hex> <pin word hex>".
//
// analysis/emu/chipdiff.py captures the log and replays it into the emulator.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "board.h"
#include "chipdiff.pio.h"
#include "expected.h"
#include "hardware/clocks.h"
#include "hardware/dma.h"
#include "hardware/gpio.h"
#include "hardware/pio.h"
#include "hardware/sync.h"
#include "pico/multicore.h"
#include "pico/stdlib.h"
#define ENG_DMB() __dmb()
#include "engine.h"
#include "chipdiff.h"

#define EXTAL_HZ 500000u
#define E_HZ (EXTAL_HZ / 4u)
#define HOLD_CYCLES (E_HZ / 20u)  // /RES low for 50 ms of E cycles (>= 20 ms needed)
#define LOOKAHEAD 8               // input words computed ahead of the DMA
#define TX_N 1024u                // words; ring of 4 KB
#define RX_N 8192u                // words; ring of 32 KB (65 ms at E = 125 kHz)
#define LOG_N 16384u
#define DMA_COUNT 0x0FFFFFFFu     // longest plain transfer: 2147 s at E = 125 kHz
#define RAIL_PULLUPS ((1u << 12) | (1u << 13) | (1u << 20) | (1u << 21) | (1u << 22))  // 10k to the 5 V rail

static uint32_t tx_ring[TX_N] __attribute__((aligned(TX_N * 4)));
static uint32_t rx_ring[RX_N] __attribute__((aligned(RX_N * 4)));
static struct {
    uint32_t k, w;
} log_q[LOG_N];
static volatile uint32_t log_head, log_tail, log_dropped;

static PIO pio_clk = pio0, pio_io = pio1;
static uint sm_clk, sm_io, off_io;
static int dma_tx, dma_rx;
static cd_t cd;

// ---- core 1: the log printer ------------------------------------------------------------

static void core1_printer(void) {
    for (;;) {
        if (log_tail != log_head) {
            uint32_t i = log_tail % LOG_N;
            printf("%lx %lx\n", (unsigned long)log_q[i].k, (unsigned long)log_q[i].w);
            __dmb();
            log_tail = log_tail + 1;
        } else {
            tight_loop_contents();
        }
    }
}

static inline void log_push(uint32_t k, uint32_t w) {
    if (log_head - log_tail >= LOG_N) {
        log_dropped++;
        return;
    }
    log_q[log_head % LOG_N].k = k;
    log_q[log_head % LOG_N].w = w;
    __dmb();
    log_head = log_head + 1;
}

// ---- pins and PIO -----------------------------------------------------------------------

static void res_assert(void) {  // /RES low through SIO (between runs)
    gpio_put(CD_GPIO_RES, 0);
    gpio_set_dir(CD_GPIO_RES, GPIO_OUT);
    gpio_set_function(CD_GPIO_RES, GPIO_FUNC_SIO);
}

static void pins_init(void) {
    gpio_init(CD_GPIO_RES);
    gpio_disable_pulls(CD_GPIO_RES);
    res_assert();  // first: /RES low before anything else
    gpio_init(CD_GPIO_E);
    gpio_disable_pulls(CD_GPIO_E);
    for (uint g = 0; g < 29; g++) {
        if (CD_IN_MASK >> g & 1u) {
            gpio_init(g);  // stays an input until a run starts
            gpio_disable_pulls(g);
        } else if (CD_OUT_MASK >> g & 1u) {
            gpio_init(g);
            gpio_pull_up(g);  // undriven chip outputs read high, as in the emulator (no pull-downs: E9)
        }
    }
    pio_gpio_init(pio_clk, CD_GPIO_EXTAL);
    gpio_disable_pulls(CD_GPIO_EXTAL);
    gpio_set_drive_strength(CD_GPIO_EXTAL, GPIO_DRIVE_STRENGTH_12MA);
}

static void clock_init(void) {
    sm_clk = pio_claim_unused_sm(pio_clk, true);
    uint off = pio_add_program(pio_clk, &extal_od_program);
    pio_sm_config c = extal_od_program_get_default_config(off);
    sm_config_set_set_pins(&c, CD_GPIO_EXTAL, 1);
    sm_config_set_clkdiv(&c, (float)clock_get_hz(clk_sys) / (2.0f * EXTAL_HZ));
    pio_sm_set_pins_with_mask(pio_clk, sm_clk, 0, 1u << CD_GPIO_EXTAL);
    pio_sm_set_pindirs_with_mask(pio_clk, sm_clk, 0, 1u << CD_GPIO_EXTAL);
    pio_sm_init(pio_clk, sm_clk, off, &c);
    pio_sm_set_enabled(pio_clk, sm_clk, true);
}

static void chipio_init(void) {
    sm_io = pio_claim_unused_sm(pio_io, true);
    off_io = pio_add_program(pio_io, &chipio_program);
    dma_tx = dma_claim_unused_channel(true);
    dma_rx = dma_claim_unused_channel(true);
}

// ---- measurements -----------------------------------------------------------------------

static uint32_t measure_e_hz(uint32_t ms) {
    uint32_t t0 = time_us_32(), edges = 0;
    bool last = gpio_get(CD_GPIO_E);
    while (time_us_32() - t0 < ms * 1000u) {
        bool v = gpio_get(CD_GPIO_E);
        edges += v && !last;
        last = v;
    }
    return (uint32_t)((uint64_t)edges * 1000000u / (time_us_32() - t0));
}

static bool power_good(void) {
    uint32_t hz = measure_e_hz(100);
    bool ok = hz > E_HZ * 95 / 100 && hz < E_HZ * 105 / 100;
    printf("E: %lu Hz (want %lu) -> %s\n", (unsigned long)hz, (unsigned long)E_HZ,
           ok ? "OK" : "NOT RUNNING: is the 5 V jumper in? is EXTAL wired?");
    return ok;
}

// A mode-strap pin (P21, P22; the chip holds them as inputs while /RES is low) with its 10k pull-up
// to 5 V rises within microseconds after a brief pull low; without it the pin stays low. The
// Pico's own pull-up is switched off for the test, so it cannot hide a missing strap.
static bool strap_high(uint g) {
    gpio_init(g);
    gpio_disable_pulls(g);
    gpio_set_drive_strength(g, GPIO_DRIVE_STRENGTH_2MA);
    gpio_put(g, 0);
    gpio_set_dir(g, GPIO_OUT);
    sleep_us(10);
    gpio_set_dir(g, GPIO_IN);
    sleep_us(50);  // 10k x ~30 pF: under 1 us to rise
    bool high = gpio_get(g);
    gpio_pull_up(g);
    return high;
}

// ---- the run ----------------------------------------------------------------------------

static inline uint32_t dma_done(int ch) { return DMA_COUNT - (dma_hw->ch[ch].transfer_count & 0x0FFFFFFFu); }

static void __not_in_flash_func(run)(uint32_t phases) {
    uint64_t total = (uint64_t)phases * REF_PHASE_US;
    if (!power_good()) return;
    if (!strap_high(13) || !strap_high(20)) {
        printf("ABORT: P21 (GP13) or P22 (GP20) has no pull-up to 5 V: check the mode straps (pins 9, 10)\n");
        return;
    }
    cd_init(&cd);
    log_head = log_tail = log_dropped = 0;

    // chipio: inputs and /RES driven by PIO1, chip outputs sampled
    pio_sm_config c = chipio_program_get_default_config(off_io);
    sm_config_set_out_pins(&c, 0, 29);
    sm_config_set_in_pins(&c, 0);
    sm_config_set_sideset_pins(&c, CD_GPIO_RES);
    sm_config_set_out_shift(&c, true, true, 29);
    sm_config_set_in_shift(&c, true, true, 32);
    pio_sm_init(pio_io, sm_io, off_io, &c);
    pio_sm_set_pins_with_mask(pio_io, sm_io, CD_IN_INIT, CD_IN_MASK | (1u << CD_GPIO_RES));
    pio_sm_set_pindirs_with_mask(pio_io, sm_io, CD_IN_MASK | (1u << CD_GPIO_RES), CD_IN_MASK | (1u << CD_GPIO_RES));
    for (uint g = 0; g < 29; g++)
        if ((CD_IN_MASK | CD_OUT_MASK) >> g & 1u) pio_gpio_init(pio_io, g);
    pio_gpio_init(pio_io, CD_GPIO_RES);  // PIO now holds /RES low (direction out, value 0)

    for (int64_t k = 0; k < LOOKAHEAD; k++) tx_ring[k % TX_N] = cd_word(&cd, k);
    int64_t filled = LOOKAHEAD;

    pio_sm_put(pio_io, sm_io, HOLD_CYCLES - 1);
    uint32_t delay = clock_get_hz(clk_sys) / E_HZ / 4u;  // sample a quarter period after E rises
    pio_sm_put(pio_io, sm_io, delay > 8 ? delay - 8 : 1);

    dma_channel_config ct = dma_channel_get_default_config(dma_tx);
    channel_config_set_transfer_data_size(&ct, DMA_SIZE_32);
    channel_config_set_read_increment(&ct, true);
    channel_config_set_write_increment(&ct, false);
    channel_config_set_ring(&ct, false, 12);  // 4 KB read ring
    channel_config_set_dreq(&ct, pio_get_dreq(pio_io, sm_io, true));
    dma_channel_configure(dma_tx, &ct, &pio_io->txf[sm_io], tx_ring, DMA_COUNT, true);
    dma_channel_config cr = dma_channel_get_default_config(dma_rx);
    channel_config_set_transfer_data_size(&cr, DMA_SIZE_32);
    channel_config_set_read_increment(&cr, false);
    channel_config_set_write_increment(&cr, true);
    channel_config_set_ring(&cr, true, 15);  // 32 KB write ring
    channel_config_set_dreq(&cr, pio_get_dreq(pio_io, sm_io, false));
    dma_channel_configure(dma_rx, &cr, rx_ring, &pio_io->rxf[sm_io], DMA_COUNT, true);

    printf("# chipdiff v1 e_hz=%lu phases=%lu cycles=%llu lookahead=%d\n", (unsigned long)E_HZ,
           (unsigned long)phases, (unsigned long long)total, LOOKAHEAD);
    printf("BEGIN\n");
    sleep_ms(20);
    pio_sm_set_enabled(pio_io, sm_io, true);

    const char *abort = NULL;
    uint64_t k = 0;
    uint32_t last = 0xFFFFFFFFu;
    while (k < total && !abort) {
        uint32_t avail = dma_done(dma_rx);
        if (avail - (uint32_t)k > RX_N - 256) abort = "sample ring overflow (core 0 too slow)";
        while ((uint32_t)k != avail && k < total) {
            uint32_t pins = rx_ring[k % RX_N];
            uint32_t w = (pins & CD_OUT_MASK) | (tx_ring[k % TX_N] & CD_IN_MASK);
            cd_sample(&cd, (int64_t)k, pins);
            if (w != last) log_push((uint32_t)k, w);
            last = w;
            k++;
        }
        uint32_t reads = dma_done(dma_tx);
        if ((int64_t)reads >= filled) abort = "input ring underrun (core 0 too slow)";
        while (filled < (int64_t)reads + LOOKAHEAD) {
            tx_ring[filled % TX_N] = cd_word(&cd, filled);
            filled++;
        }
    }

    // stop: /RES low first, then the PIO and the DMA
    res_assert();
    pio_sm_set_enabled(pio_io, sm_io, false);
    dma_channel_abort(dma_tx);
    dma_channel_abort(dma_rx);
    pio_sm_clear_fifos(pio_io, sm_io);
    pio_sm_restart(pio_io, sm_io);
    while (log_tail != log_head) tight_loop_contents();
    sleep_ms(50);
    if (abort)
        printf("ABORT %s at cycle %llu\n", abort, (unsigned long long)k);
    else
        printf("END cycles=%llu late=%lu qfull=%lu dropped=%lu\n", (unsigned long long)k, (unsigned long)cd.late,
               (unsigned long)cd.qfull, (unsigned long)log_dropped);
}

// ---- console ----------------------------------------------------------------------------

static void cmd_rigcheck(void) {
    printf("rigcheck: chip OUT of its socket, 5 V jumper OUT.\n");
    if (measure_e_hz(20)) {
        printf("FAIL: E is toggling, so a chip is running. Remove it and retry.\n");
        return;
    }
    uint32_t pins = CD_IN_MASK | CD_OUT_MASK, faults = 0;
    for (uint g = 0; g < 29; g++)
        if (pins >> g & 1u) {
            gpio_init(g);  // back to SIO inputs (a run leaves them with PIO)
            gpio_pull_up(g);
        }
    sleep_ms(5);
    for (uint g = 0; g < 29; g++)
        if ((pins >> g & 1u) && !gpio_get(g)) {
            printf("FAIL: GP%u stuck low: shorted to GND, or a strap on the wrong rail\n", g);
            faults++;
        }
    for (uint g = 0; g < 29; g++) {
        if (!(pins >> g & 1u) || !gpio_get(g)) continue;
        gpio_set_drive_strength(g, GPIO_DRIVE_STRENGTH_2MA);
        gpio_put(g, 0);
        gpio_set_dir(g, GPIO_OUT);
        sleep_us(200);
        for (uint j = 0; j < 29; j++) {
            bool both_rail = (RAIL_PULLUPS >> g & 1u) && (RAIL_PULLUPS >> j & 1u);  // joined by the unpowered rail
            if (j != g && (pins >> j & 1u) && !both_rail && !gpio_get(j)) {
                printf("FAIL: GP%u is shorted to GP%u\n", g, j);
                faults++;
            }
        }
        gpio_set_dir(g, GPIO_IN);
        sleep_us(200);
    }
    for (uint g = 0; g < 29; g++)
        if (CD_IN_MASK >> g & 1u) gpio_disable_pulls(g);
    printf(faults ? "rigcheck: %lu fault(s)\n" : "rigcheck: PASS (no stuck or shorted lines)\n", (unsigned long)faults);
}

static void help(void) {
    printf("ecu_chipdiff: the real D151801 against the emulator (docs/hardware/chip_diff_test.md)\n");
    printf("/RES is held low. Plug the chip's 5 V jumper in only now; unplug it before USB.\n");
    printf("Commands: rigcheck  clock  run [phases, 1-6, default 6]  help\n");
}

int main(void) {
    pins_init();
    stdio_init_all();
    clock_init();
    chipio_init();
    multicore_launch_core1(core1_printer);
    while (!stdio_usb_connected()) sleep_ms(50);
    help();
    char line[32];
    uint n = 0;
    printf("> ");
    for (;;) {
        int ch = getchar_timeout_us(100000);
        if (ch == PICO_ERROR_TIMEOUT) continue;
        if (ch != '\r' && ch != '\n') {
            if (n < sizeof line - 1) line[n++] = (char)ch;
            continue;
        }
        line[n] = 0;
        n = 0;
        printf("\n");
        if (!strcmp(line, "rigcheck"))
            cmd_rigcheck();
        else if (!strcmp(line, "clock"))
            power_good();
        else if (!strncmp(line, "run", 3)) {
            long p = line[3] ? strtol(line + 3, NULL, 10) : REF_PHASES;
            run(p >= 1 && p <= REF_PHASES ? (uint32_t)p : REF_PHASES);
        } else if (line[0])
            help();
        printf("> ");
    }
}
