// In-car test firmware (docs/procedures/car_test.md): the Pico 2 W in place of
// the D151801 in the spare ECU, wired by jumpers to its CPU socket (pins.h).
//
//   PIO0 sm car_in:  every GPIO sampled once per us into the input ring (DMA, endless).
//   PIO0 sm car_out: one word per us from the output ring onto the output pins (DMA, endless).
//   PWM:             E (pin 40) at 1 MHz while the emulated chip runs.
//   Core 1:          car_poll (car.h): the 17140 ROM on the emulated chip, on the rings.
//   Core 0:          USB: a status line and the RAM variables every 0.5 s ("#", "S" and "D" lines;
//                    the D lines are the serial-link logger's format, decoded by pcmre.peeklog).
//
// THIS BUILD CANNOT RUN THE ENGINE: car.h's hold keeps IGT (P11) and the injector (P21) at the level
// the real chip drives while the engine is not turning. The emulator still computes both; their
// counts are in the status line.

#include <stdio.h>
#include <string.h>

#include "board.h"
#include "car.h"
#include "car.pio.h"
#include "hardware/clocks.h"
#include "hardware/dma.h"
#include "hardware/gpio.h"
#include "hardware/pio.h"
#include "hardware/pwm.h"
#include "hardware/sync.h"
#include "pico/multicore.h"
#include "pico/stdlib.h"
#include "rom17140.h"

#if !CAR_HOLD
#error "the car build keeps the IGT/injector hold until the strict bench gate has passed (CLAUDE.md)"
#endif

#define VERSION "ecu_emu_car v1"
#define SYS_KHZ 250000u
#define RES_DEBOUNCE_US 2000  // /RES must read high this long before the chip starts (a floating pin cannot start it)
#define STATUS_MS 500u

static uint32_t in_ring[CAR_IN_N];  // car.h's view: raw_ring with /RES debounced
static uint32_t out_ring[CAR_OUT_N] __attribute__((aligned(CAR_OUT_N * 4)));
static PIO pio = pio0;
static uint sm_in, sm_out;
static int dma_in, dma_out;
static car_t car;
static uint32_t raw_ring[CAR_IN_N] __attribute__((aligned(CAR_IN_N * 4)));  // the samples as taken (DMA)

// ---- snapshot core 1 -> core 0 (seqlock) --------------------------------------------------

typedef struct {
    volatile uint32_t seq;
    int64_t real_us, emu_us;
    int running;
    uint32_t runs, resets, late, qfull, oeqfull, lost, traps, tx_bytes, spark_n, inj_n, inj_last_us;
    int64_t lag_max;
    uint32_t adc_n[8], adc_us[8];
    uint32_t pins, drive;
    uint8_t ports[4], ddr[4], trcsr, ram[0x100];
} snap_t;
static snap_t snap;
static volatile bool selftest_req, force_e;
static volatile int selftest_done;
static volatile int selftest_delay, selftest_bad;
static volatile uint32_t selftest_badmask;

// ---- pins -----------------------------------------------------------------------------------

static void set_oe(car_t *c, uint32_t m) {
    for (uint g = 0; g < 29; g++)
        if (c->out_mask >> g & 1u) gpio_set_oeover(g, (m >> g & 1u) ? GPIO_OVERRIDE_NORMAL : GPIO_OVERRIDE_LOW);
}

static void pins_init(void) {
    // Every pin starts as a plain input with no pulls (RP2350-E9: never a pull-down).
    for (int i = 0; i < CAR_NPINS; i++) {
        uint g = CAR_TAB[i].g;
        gpio_init(g);
        gpio_disable_pulls(g);
        if (CAR_TAB[i].dir != CAR_D_IN) {
            pio_gpio_init(pio, g);  // (setting a function clears the pad's overrides, so this comes first)
            gpio_set_oeover(g, GPIO_OVERRIDE_LOW);  // hi-Z until the emulated chip's DDR drives it
        }
    }
    gpio_init(CAR_GPIO_RES);
    gpio_disable_pulls(CAR_GPIO_RES);
    // E: 1 MHz PWM, released (hi-Z) until the chip runs
    gpio_disable_pulls(CAR_GPIO_E);
    gpio_set_function(CAR_GPIO_E, GPIO_FUNC_PWM);
    gpio_set_oeover(CAR_GPIO_E, GPIO_OVERRIDE_LOW);
    uint slice = pwm_gpio_to_slice_num(CAR_GPIO_E);
    pwm_set_clkdiv_int_frac(slice, 1, 0);
    pwm_set_wrap(slice, SYS_KHZ / 1000u - 1u);
    pwm_set_chan_level(slice, pwm_gpio_to_channel(CAR_GPIO_E), SYS_KHZ / 2000u);
    pwm_set_enabled(slice, true);
}

static void dma_endless(int ch) {
    dma_channel_hw_addr((uint)ch)->transfer_count =
        (DMA_CH0_TRANS_COUNT_MODE_VALUE_ENDLESS << DMA_CH0_TRANS_COUNT_MODE_LSB) | 1u;
}

static void rings_init(void) {
    uint32_t div = clock_get_hz(clk_sys) / 1000000u;  // 250: exactly 1 MHz
    sm_in = pio_claim_unused_sm(pio, true);
    sm_out = pio_claim_unused_sm(pio, true);
    uint off_in = pio_add_program(pio, &car_in_program);
    uint off_out = pio_add_program(pio, &car_out_program);

    pio_sm_config ci = car_in_program_get_default_config(off_in);
    sm_config_set_in_pins(&ci, 0);
    sm_config_set_in_shift(&ci, false, true, 32);
    sm_config_set_fifo_join(&ci, PIO_FIFO_JOIN_RX);
    sm_config_set_clkdiv_int_frac(&ci, (uint16_t)div, 0);
    pio_sm_init(pio, sm_in, off_in, &ci);

    pio_sm_config co = car_out_program_get_default_config(off_out);
    sm_config_set_out_pins(&co, 0, 29);
    sm_config_set_out_shift(&co, true, true, 32);
    sm_config_set_fifo_join(&co, PIO_FIFO_JOIN_TX);
    sm_config_set_clkdiv_int_frac(&co, (uint16_t)div, 0);
    pio_sm_init(pio, sm_out, off_out, &co);
    pio_sm_set_pins_with_mask(pio, sm_out, car.out_mask, car.out_mask);
    pio_sm_set_pindirs_with_mask(pio, sm_out, car.out_mask, car.out_mask);  // drive is gated by the OE override

    dma_in = dma_claim_unused_channel(true);
    dma_channel_config c = dma_channel_get_default_config((uint)dma_in);
    channel_config_set_transfer_data_size(&c, DMA_SIZE_32);
    channel_config_set_read_increment(&c, false);
    channel_config_set_write_increment(&c, true);
    channel_config_set_ring(&c, true, 15);  // 32 KB
    channel_config_set_dreq(&c, pio_get_dreq(pio, sm_in, false));
    dma_channel_configure((uint)dma_in, &c, raw_ring, &pio->rxf[sm_in], 1, false);
    dma_endless(dma_in);

    dma_out = dma_claim_unused_channel(true);
    c = dma_channel_get_default_config((uint)dma_out);
    channel_config_set_transfer_data_size(&c, DMA_SIZE_32);
    channel_config_set_read_increment(&c, true);
    channel_config_set_write_increment(&c, false);
    channel_config_set_ring(&c, false, 15);
    channel_config_set_dreq(&c, pio_get_dreq(pio, sm_out, true));
    dma_channel_configure((uint)dma_out, &c, &pio->txf[sm_out], out_ring, 1, false);
    dma_endless(dma_out);

    dma_channel_start((uint)dma_out);  // fills the TX FIFO before the clocks start
    dma_channel_start((uint)dma_in);
    sleep_us(10);
    pio_enable_sm_mask_in_sync(pio, (1u << sm_in) | (1u << sm_out));
}

// Absolute ring positions (core 1 only: called often enough to see every wrap).
static int64_t in_abs(void) {
    static uint32_t last;
    static int64_t wraps;
    uint32_t p = ((uint32_t)dma_hw->ch[dma_in].write_addr - (uint32_t)(uintptr_t)raw_ring) / 4u % CAR_IN_N;
    if (p < last) wraps++;
    last = p;
    return wraps * CAR_IN_N + p;
}

static int64_t out_abs(void) {
    static uint32_t last;
    static int64_t wraps;
    uint32_t p = ((uint32_t)dma_hw->ch[dma_out].read_addr - (uint32_t)(uintptr_t)out_ring) / 4u % CAR_OUT_N;
    if (p < last) wraps++;
    last = p;
    return wraps * CAR_OUT_N + p;
}

// ---- core 1 ---------------------------------------------------------------------------------

// The raw samples land in raw_ring; car.h reads in_ring, a copy in which /RES only counts as high
// after RES_DEBOUNCE_US of continuous high samples (and low at once).
static void debounce(int64_t upto) {
    static int64_t done;
    static int64_t high_run;
    for (; done < upto; done++) {
        uint32_t w = raw_ring[(uint64_t)done % CAR_IN_N];
        high_run = (w & car.res_mask) ? high_run + 1 : 0;
        if (high_run < RES_DEBOUNCE_US) w &= ~car.res_mask;
        in_ring[(uint64_t)done % CAR_IN_N] = w;
    }
}

static void selftest(void) {
    // Nothing connected: drive every output pin with a pattern and read it back through its own pad.
    int64_t j0 = out_abs() + 256;
    const int n = 2048;
    for (int i = 0; i < n; i++) {
        uint32_t x = (uint32_t)i * 2654435761u;
        out_ring[(uint64_t)(j0 + i) % CAR_OUT_N] = (x ^ (x >> 13)) & car.out_mask;
    }
    set_oe(&car, car.out_mask);
    while (in_abs() < j0 + n + 64) tight_loop_contents();
    set_oe(&car, 0);
    int best = 99, best_bad = 1 << 30;
    uint32_t badmask = 0;
    for (int d = -8; d <= 8; d++) {
        int bad = 0;
        uint32_t m = 0;
        for (int i = 16; i < n - 16; i++) {
            uint32_t x = (uint32_t)i * 2654435761u;
            uint32_t want = (x ^ (x >> 13)) & car.out_mask;
            uint32_t got = raw_ring[(uint64_t)(j0 + i + d) % CAR_IN_N] & car.out_mask;
            if (want != got) {
                bad++;
                m |= want ^ got;
            }
        }
        if (bad < best_bad) {
            best_bad = bad;
            best = d;
            badmask = m;
        }
    }
    for (int i = 0; i < n + 64; i++) out_ring[(uint64_t)(j0 + i) % CAR_OUT_N] = car.out_mask;
    if (car.filled < j0 + n + 64) car.filled = j0 + n + 64;
    selftest_delay = best;
    selftest_bad = best_bad;
    selftest_badmask = badmask;
}

static void publish(int64_t avail) {
    snap.seq++;
    __dmb();
    snap.real_us = avail;
    snap.running = car.base >= 0;
    snap.emu_us = car.base >= 0 ? car.b.io.now : 0;
    snap.runs = car.runs;
    snap.resets = car.resets;
    snap.late = car.late;
    snap.qfull = car.qfull;
    snap.oeqfull = car.oeqfull;
    snap.lost = car.lost;
    snap.traps = car.traps;
    snap.tx_bytes = car.tx_bytes;
    snap.spark_n = car.spark_n;
    snap.inj_n = car.inj_n;
    snap.inj_last_us = car.inj_last_us;
    snap.lag_max = car.lag_max;
    car.lag_max = 0;
    for (int i = 0; i < 8; i++) {
        snap.adc_n[i] = car.adc_n[i];
        snap.adc_us[i] = car.adc_us[i];
    }
    snap.pins = raw_ring[(uint64_t)(avail - 1) % CAR_IN_N];
    snap.drive = car.oe_now;
    for (int i = 0; i < 4; i++) {
        snap.ports[i] = d_port_out(&car.b.io, i);
        snap.ddr[i] = car.b.io.ddr[i];
    }
    snap.trcsr = car.b.io.trcsr;
    memcpy(snap.ram, car.b.mem, sizeof snap.ram);
    __dmb();
    snap.seq++;
}

static void core1_main(void) {
    int e_on = 0;
    int64_t next_pub = 0;
    for (;;) {
        int64_t avail = in_abs();
        if (selftest_req) {
            if (car.base < 0 && !(raw_ring[(uint64_t)(avail - 1) % CAR_IN_N] & car.res_mask)) selftest();
            else selftest_bad = -1;  // refused: the board is powered
            selftest_req = false;
            selftest_done++;
            continue;
        }
        debounce(avail);
        car_poll(&car, avail, out_abs());
        int want_e = car.base >= 0 || force_e;
        if (want_e != e_on) {
            gpio_set_oeover(CAR_GPIO_E, want_e ? GPIO_OVERRIDE_NORMAL : GPIO_OVERRIDE_LOW);
            e_on = want_e;
        }
        if (avail >= next_pub) {
            publish(avail);
            next_pub = avail + 100000;
        }
    }
}

// ---- core 0: USB --------------------------------------------------------------------------

static bool read_snap(snap_t *s) {
    for (int tries = 0; tries < 100; tries++) {
        uint32_t a = snap.seq;
        if (a & 1u) continue;
        __dmb();
        memcpy(s, (const void *)&snap, sizeof *s);
        __dmb();
        if (snap.seq == a) return true;
    }
    return false;
}

static int bit(uint32_t w, int port, int b) {
    int g = car_gpio(port, b);
    return g >= 0 ? (int)(w >> g & 1u) : -1;
}

// The serial-link logger's variables (pcmre.peeklog.VARS), so its decoder reads this log as is.
static const uint8_t PEEK[] = {0x77, 0x82, 0x46, 0x4A, 0x44, 0x53, 0x5F, 0x8C, 0x88, 0x8A, 0xA8, 0xA9, 0x06, 0x95, 0x40, 0x42};

static void status(const snap_t *s, uint32_t ms) {
    if (!s->running) {
        printf("# %lu.%lu s  WAITING for /RES (key on)  runs=%lu resets=%lu | pins now: RES=%d T(P30)=%d IDL(P16)=%d "
               "NE(P10)=%d G(P35)=%d ADCend(P20)=%d IGF(SC1)=%d\n",
               (unsigned long)(ms / 1000), (unsigned long)(ms % 1000 / 100), (unsigned long)s->runs,
               (unsigned long)s->resets, (int)(s->pins >> CAR_GPIO_RES & 1u), bit(s->pins, 3, 0), bit(s->pins, 1, 6),
               bit(s->pins, 1, 0), bit(s->pins, 3, 5), bit(s->pins, 2, 0), bit(s->pins, 0, 0));
        return;
    }
    const uint8_t *r = s->ram;
    printf("# %lu.%lu s  RUNNING %lld ms  resets=%lu lag_max=%lld us late=%lu lost=%lu traps=%lu qfull=%lu sci=%d | "
           "lamp(P24)=%d P22=%d P23=%d P31=%d P40=%d P41=%d | T(P30)=%d IDL(P16)=%d P17=%d A/C(P37)=%d J8(P34)=%d | "
           "held: spark=%lu inj=%lu (%lu us) | rpm %u\n",
           (unsigned long)(ms / 1000), (unsigned long)(ms % 1000 / 100), (long long)(s->emu_us / 1000),
           (unsigned long)s->resets, (long long)s->lag_max, (unsigned long)s->late, (unsigned long)s->lost,
           (unsigned long)s->traps, (unsigned long)s->qfull, (s->trcsr & 0x02) ? 1 : 0, s->ports[1] >> 4 & 1,
           s->ports[1] >> 2 & 1, s->ports[1] >> 3 & 1, s->ports[2] >> 1 & 1, s->ports[3] & 1, s->ports[3] >> 1 & 1,
           bit(s->pins, 3, 0), bit(s->pins, 1, 6), bit(s->pins, 1, 7), bit(s->pins, 3, 7), bit(s->pins, 3, 4),
           (unsigned long)s->spark_n, (unsigned long)s->inj_n, (unsigned long)s->inj_last_us,
           (unsigned)(((r[0x77] << 8) | r[0x78]) * 100u / 32u));
    printf("# ADC conversion us (ch0..7, at the pins): %lu %lu %lu %lu %lu %lu %lu %lu  (counts %lu %lu %lu %lu %lu %lu %lu %lu)\n",
           (unsigned long)s->adc_us[0], (unsigned long)s->adc_us[1], (unsigned long)s->adc_us[2],
           (unsigned long)s->adc_us[3], (unsigned long)s->adc_us[4], (unsigned long)s->adc_us[5],
           (unsigned long)s->adc_us[6], (unsigned long)s->adc_us[7], (unsigned long)s->adc_n[0],
           (unsigned long)s->adc_n[1], (unsigned long)s->adc_n[2], (unsigned long)s->adc_n[3],
           (unsigned long)s->adc_n[4], (unsigned long)s->adc_n[5], (unsigned long)s->adc_n[6],
           (unsigned long)s->adc_n[7]);
    printf("S,%lu,run,%lld,%lu,%lld,%lu,%lu,%lu,%02X%02X%02X%02X,%08lX\n", (unsigned long)ms, (long long)s->emu_us,
           (unsigned long)s->resets, (long long)s->lag_max, (unsigned long)s->late, (unsigned long)s->spark_n,
           (unsigned long)s->inj_n, s->ports[0], s->ports[1], s->ports[2], s->ports[3], (unsigned long)s->pins);
    for (unsigned i = 0; i < sizeof PEEK; i++) {
        uint8_t a = PEEK[i];
        unsigned w = a == 0x06 ? (unsigned)(s->ports[2] << 8 | s->ports[3]) : (unsigned)(r[a] << 8 | r[(a + 1) & 0xFF]);
        printf("D,%lu,%02X,%04X\n", (unsigned long)ms, a, w);
    }
}

static void dump_ram(const snap_t *s) {
    printf("# RAM $00-$FF (registers $00-$1F as stored, not live):\n");
    for (int a = 0; a < 0x100; a += 16) {
        printf("R,%02X", a);
        for (int i = 0; i < 16; i++) printf(",%02X", s->ram[a + i]);
        printf("\n");
    }
}

static void help(void) {
    printf("# %s: the 17140 ROM on an emulated D151801, on the ECU board's pins (pins.h).\n"
           "# SAFETY: IGT (P11) and injector (P21) are HELD at their engine-stopped level: this build cannot run the engine.\n"
           "# Order: USB in -> check this says WAITING -> key on.  Key off -> USB out.\n"
           "# Keys: r = RAM dump, t = self-test (only with nothing connected), e = E clock on/off while waiting, h = help\n",
           VERSION);
}

int main(void) {
    set_sys_clock_khz(SYS_KHZ, true);
    car_init(&car, ROM17140, in_ring, out_ring, set_oe);
    pins_init();
    rings_init();
    stdio_init_all();
    multicore_launch_core1(core1_main);
    sleep_ms(2000);
    help();
    uint32_t last = 0;
    for (;;) {
        int ch = getchar_timeout_us(20000);
        snap_t s;
        if (ch == 'h' || ch == '?') help();
        if (ch == 'e') {
            force_e = !force_e;
            printf("# E clock forced %s\n", force_e ? "ON" : "off (on only while running)");
        }
        if (ch == 'r' && read_snap(&s)) dump_ram(&s);
        if (ch == 't') {
            int d0 = selftest_done;
            selftest_req = true;
            while (selftest_done == d0) tight_loop_contents();
            if (selftest_bad < 0) printf("# self-test REFUSED: /RES is high (board powered) or the chip is running\n");
            else
                printf("# self-test: %s, pad delay %d us, %d bad samples, bad pins mask %08lX\n",
                       selftest_bad == 0 ? "PASS" : "FAIL", selftest_delay, selftest_bad,
                       (unsigned long)selftest_badmask);
        }
        uint32_t ms = to_ms_since_boot(get_absolute_time());
        if (ms - last >= STATUS_MS && read_snap(&s)) {
            last = ms;
            status(&s, ms);
        }
    }
}
