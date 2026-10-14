// Speed test of the C HD6301 core on the RP2350: runs the 17140 ROM with pseudo-random reads
// of the I/O registers (as tests/test_hd6301_c.py does) and an interrupt every 97
// instructions, and prints the speed as a multiple of the real chip (E = 1 MHz).
// No wiring: plug in USB, open the serial port, read the numbers.

#include <stdio.h>

#include "hardware/clocks.h"
#include "hd6301.h"
#include "pico/stdlib.h"
#include "rom17140.h"

static uint8_t mem[0x10000];
static uint32_t io = 1;

static uint8_t rd(void *ctx, uint16_t a) {
    (void)ctx;
    if (a >= 0x20) return mem[a];
    io = io * 1103515245u + 12345u;
    uint8_t v = (uint8_t)(io >> 16);
    return a == 0x03 ? (uint8_t)(v | 0xE0) : v;  // PORT2 mode bits: mode 7
}

static void wr(void *ctx, uint16_t a, uint8_t v) {
    (void)ctx;
    if (a < 0xF000) mem[a] = v;
}

int main(void) {
    stdio_init_all();
    for (int i = 0; i < 4096; i++) mem[0xF000 + i] = ROM17140[i];
    hd6301_t c;
    for (;;) {
        sleep_ms(3000);
        hd6301_init(&c, rd, wr, 0);
        hd6301_reset(&c);
        uint64_t t0 = time_us_64();
        uint32_t n = 0;
        while (time_us_64() - t0 < 2000000) {
            for (int k = 0; k < 1000; k++, n++) {
                if (c.waiting || c.sleeping) c.waiting = c.sleeping = 0;
                hd6301_step(&c);
                if (n % 97 == 96) hd6301_irq(&c, HD6301_VEC_OCF);
            }
        }
        double s = (double)(time_us_64() - t0) / 1e6;
        double mhz = (double)c.cycles / s / 1e6;
        printf("ecu_emu_bench: %.2f M instructions/s, E-clock equivalent %.2f MHz = %.1fx the real chip "
               "(CPU clock %lu MHz)\n", n / s / 1e6, mhz, mhz / 1.0, (unsigned long)(clock_get_hz(clk_sys) / 1000000));
    }
}
