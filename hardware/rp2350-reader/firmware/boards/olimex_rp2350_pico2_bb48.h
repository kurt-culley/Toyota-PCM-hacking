// Olimex RP2350-PICO2-BB48 / BB48R (RP2350B, 16 MB flash; BB48R adds 8 MB PSRAM + microSD).
// From the Olimex Rev A schematic (github.com/OLIMEX/RP2350-PICO2-BB48, MIT licence).
//
// Board use of GPIOs (the reader avoids all of them):
//   GP0/1 UEXT UART, GP2/3 I2C with 2.2k pull-ups to 3.3 V, GP4-7 UEXT SPI,
//   GP8 PSRAM chip select (QMI_CS1n), GP9-11 + GP24 microSD, GP25 user LED.

// -----------------------------------------------------
// NOTE: THIS HEADER IS ALSO INCLUDED BY ASSEMBLER SO
//       SHOULD ONLY CONSIST OF PREPROCESSOR DIRECTIVES
// -----------------------------------------------------

// pico_cmake_set PICO_PLATFORM=rp2350

#ifndef _BOARDS_OLIMEX_RP2350_PICO2_BB48_H
#define _BOARDS_OLIMEX_RP2350_PICO2_BB48_H

#define OLIMEX_RP2350_PICO2_BB48

#define PICO_RP2350A 0

#ifndef PICO_DEFAULT_LED_PIN
#define PICO_DEFAULT_LED_PIN 25
#endif

#define OLIMEX_BB48_PSRAM_CS_PIN 8

#define PICO_BOOT_STAGE2_CHOOSE_W25Q080 1
#ifndef PICO_FLASH_SPI_CLKDIV
#define PICO_FLASH_SPI_CLKDIV 2
#endif

// pico_cmake_set_default PICO_FLASH_SIZE_BYTES = (16 * 1024 * 1024)
#ifndef PICO_FLASH_SIZE_BYTES
#define PICO_FLASH_SIZE_BYTES (16 * 1024 * 1024)
#endif

// pico_cmake_set_default PICO_RP2350_A2_SUPPORTED = 1
#ifndef PICO_RP2350_A2_SUPPORTED
#define PICO_RP2350_A2_SUPPORTED 1
#endif

#endif
