// Serial-link logger for the MR2 89661-17140 ECU, Raspberry Pi Pico 2 W.
//
// Polls the ECU's factory RAM-peek link (docs/mr2/serial_link.md) and prints every reply on
// the USB serial port; src/pcmre/peeklog.py turns the log into physical units. The
// protocol logic is in link.h (tested against the simulator: tests/test_peek_logger.py).
//
// Wiring (docs/mr2/serial_link.md, "Hardware"):
//   GP0 (UART0 TX) -- 1 kOhm --> ECU chip pin 11 (P23, SCI RX)
//   GP1 (UART0 RX) <-- 1 kOhm -- ECU chip pin 12 (P24, SCI TX)
//   GP2 (ECU 5 V sense) <-- 10 kOhm --+-- 15 kOhm -- GND, top of the divider on the ECU's VCC
//   GND -- ECU ground
// The Pico must be powered before the ECU (its pins take 5 V only while powered). No
// internal pull-downs are used (RP2350 erratum E9).
//
// Console (USB serial, 115200 or any): lines out
//   S,<ms>,<state>            OFF / HOLD / POLL / LOST
//   D,<ms>,<addr>,<word>      a reply, hex
//   M,<ms>,<addr>             no reply within 30 ms
// commands in
//   v 77 46 53 ...            set the polled addresses (hex; unsafe ones are dropped)
//   ?                         print the list and the state

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "hardware/gpio.h"
#include "hardware/uart.h"
#include "link.h"
#include "pico/stdlib.h"

#define PIN_TX 0
#define PIN_RX 1
#define PIN_VCC 2
#define BAUD 7813  // E/128 at E = 1 MHz: 7812.5 baud

static const char *const STATE_NAME[] = {"OFF", "HOLD", "POLL", "LOST"};

static void apply_tx(tx_mode_t m) {
    static int cur = -1;
    if ((int)m == cur) return;
    cur = (int)m;
    if (m == TX_UART) {
        gpio_set_function(PIN_TX, GPIO_FUNC_UART);
    } else {
        gpio_set_function(PIN_TX, GPIO_FUNC_SIO);
        gpio_put(PIN_TX, 0);
        gpio_set_dir(PIN_TX, m == TX_BREAK ? GPIO_OUT : GPIO_IN);
    }
}

static void command(link_t *l, char *line) {
    if (line[0] == 'v') {
        uint8_t a[LINK_MAX_VARS];
        unsigned n = 0;
        for (char *t = strtok(line + 1, " ,"); t && n < LINK_MAX_VARS; t = strtok(NULL, " ,"))
            a[n++] = (uint8_t)strtoul(t, NULL, 16);
        printf("# %u addresses kept\n", link_set_vars(l, a, n));
    }
    printf("# state %s, vars", STATE_NAME[l->state]);
    for (unsigned i = 0; i < l->nvars; i++) printf(" %02X", l->vars[i]);
    printf("\n");
}

int main(void) {
    stdio_init_all();
    uart_init(uart0, BAUD);
    uart_set_format(uart0, 8, 1, UART_PARITY_NONE);
    uart_set_fifo_enabled(uart0, true);
    gpio_set_function(PIN_RX, GPIO_FUNC_UART);
    gpio_disable_pulls(PIN_RX);
    gpio_init(PIN_TX);
    gpio_disable_pulls(PIN_TX);
    gpio_init(PIN_VCC);
    gpio_set_dir(PIN_VCC, GPIO_IN);
    gpio_disable_pulls(PIN_VCC);

    link_t l;
    link_init(&l);
    link_out_t o = {.tx = TX_BREAK};
    apply_tx(TX_BREAK);
    printf("# peek_logger 1: 17140 serial link, 7812.5 baud\n");

    char line[128];
    unsigned nline = 0;
    for (;;) {
        int ch = getchar_timeout_us(0);
        if (ch >= 0) {
            if (ch == '\r' || ch == '\n') {
                line[nline] = 0;
                if (nline) command(&l, line);
                nline = 0;
            } else if (nline < sizeof line - 1) {
                line[nline++] = (char)ch;
            }
        }
        int rx = -1;
        if (uart_is_readable(uart0)) {
            uint8_t b = (uint8_t)uart_getc(uart0);
            rx = (l.state == ST_POLL) ? b : -1;  // ignore bytes during break / hold
        }
        uint32_t now = time_us_32();
        link_step(&l, now, gpio_get(PIN_VCC), rx, &o);
        apply_tx(o.tx);
        if (o.send >= 0) {
            while (uart_is_readable(uart0)) (void)uart_getc(uart0);  // drop stale bytes
            uart_putc_raw(uart0, (char)o.send);
        }
        uint32_t ms = now / 1000u;
        if (o.rec == REC_DATA) printf("D,%lu,%02X,%04X\n", (unsigned long)ms, o.addr, o.word);
        else if (o.rec == REC_MISS) printf("M,%lu,%02X\n", (unsigned long)ms, o.addr);
        else if (o.rec == REC_STATE) printf("S,%lu,%s\n", (unsigned long)ms, STATE_NAME[o.state]);
    }
}
