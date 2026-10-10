// Reader pin map. The bus block has the same layout on both boards, relative to BUS_BASE,
// so one PIO program serves both:
//
//   +0..+7    AD0-AD7   (6301 pins 37..30)  bidirectional
//   +10..+17  A8-A15    (6301 pins 29..22)
//   +18       AS        (6301 pin 39)
//   +19       E         (6301 pin 40)
//   +20       R/W       (6301 pin 38)
//
// +8/+9 are either reader pins (Pico 2 WH) or board pins (BB48R: microSD DAT0, LED); the
// bus program reads them but ignores them. RES, EXTAL and the SCI line sit wherever each
// board has free 5 V-tolerant pins. GPIO40-47 on the RP2350B are ADC pins and NOT 5 V
// tolerant: never wire the 6301 to them.
#pragma once

#if defined(OLIMEX_RP2350_PICO2_BB48)
#define READER_BOARD_NAME "Olimex RP2350-PICO2-BB48(R)"
#define BUS_BASE 16u  // GP16-23 AD, GP26-33 A8-A15, GP34 AS, GP35 E, GP36 R/W
#define PIN_RES 37u
#define PIN_EXTAL 38u
#define PIN_SCI 39u  // 6301 P24/TX (pin 12)
#define PIO_GPIO_BASE 16u
#define PIN_LED 25u
#elif defined(RASPBERRYPI_PICO2_W)
#define READER_BOARD_NAME "Raspberry Pi Pico 2 W(H)"
#define BUS_BASE 0u  // GP0-7 AD, GP10-17 A8-A15, GP18 AS, GP19 E, GP20 R/W
#define PIN_RES 8u
#define PIN_EXTAL 9u
#define PIN_SCI 21u
#define PIO_GPIO_BASE 0u
// the Pico 2 W LED hangs off the wireless chip; the reader does not use it
#else
#error "unsupported board: build with PICO_BOARD=olimex_rp2350_pico2_bb48 or pico2_w"
#endif

#define BUS_AD_OFF 0u
#define BUS_AHI_OFF 10u
#define BUS_AS_OFF 18u
#define BUS_E_OFF 19u
#define BUS_RW_OFF 20u
#define BUS_WIDTH 21u  // bits captured per address sample

#define PIN_AD0 (BUS_BASE + BUS_AD_OFF)
#define PIN_A8 (BUS_BASE + BUS_AHI_OFF)
#define PIN_AS (BUS_BASE + BUS_AS_OFF)
#define PIN_E (BUS_BASE + BUS_E_OFF)
#define PIN_RW (BUS_BASE + BUS_RW_OFF)
