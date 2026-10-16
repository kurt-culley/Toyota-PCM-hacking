# Glossary

## Summary

This page gives the technical names that the documentation uses. Each name has one meaning. Use these names, and no synonyms (see the [writing rules](style.md)).

## The ECUs

| Name | Meaning |
|---|---|
| **ECU** | Engine control unit. In this repository: the Denso ECU of the car, not a part of it |
| **17140** | The ECU 89661-17140 of the mk1 Toyota MR2 (AW11, 4A-GE engine, UK market). The main subject of this repository |
| **17030**, **17070** | Other ECUs of the mk1 MR2. They are not dumped |
| **Bluetop** | The ECU of the Toyota AE86 (4A-GE). It has the same CPU type. Its ROM is the reference ROM of this repository |
| **0642**, **2860** | The two Bluetop software versions (CPU D151801-0642 and D151801-2860) |
| **spare ECU** | A second 17140. Its CPU is removed and a socket is installed. It is the ECU for tests in the car |
| **stock ECU** | The ECU of the car, without changes. It is the reference for the tests in the car |

## The CPU

| Name | Meaning |
|---|---|
| **CPU** | The Denso D151801 microcontroller of the ECU (D151801-7110 in the 17140). It has an HD6301 core |
| **HD6301** | The Hitachi microcontroller family of the CPU. The data book is in `reference/` |
| **MC6801** | The Motorola microcontroller family. The CPU uses the MC6801 instruction timing |
| **ROM** | The 4 KB program memory inside the CPU, `$F000`–`$FFFF` |
| **RAM** | The data memory inside the CPU, `$40`–`$FF` |
| **second timer** | A timer of the D151801 that the HD6301 does not have: registers `$18`, `$1B`, `$1D`. It uses pins P10 (input capture) and P11 (output compare) |
| **mode 7** | The single-chip mode of the CPU. The ECU uses it |
| **E clock**, **E** | The bus clock of the CPU, on pin 40. 1 MHz in the ECU (4 MHz crystal) |
| **/RES** | The reset input of the CPU, pin 6. Low = reset |
| **word sum** | The 16-bit sum of all ROM words. It is `$AA55`. The word at `$FFEE` balances it |
| **Pxy** | Port *x*, bit *y* of the CPU (for example P11 = port 1, bit 1) |
| **IC1**, **IC2** | Input capture 1 (pin P20) and input capture 2 (pin P10) |
| **OC1**, **OC2** | Output compare 1 (pin P21) and output compare 2 (pin P11) |
| **IS3** | The input strobe flag on pin SC1. The ECU uses it for IGF |
| **SCI** | The serial interface of the CPU |

## Engine signals (as the CPU pins get them)

| Name | Pin | Meaning |
|---|---|---|
| **NE** | P10 | Crank position pulses, one edge each 30° of the crank |
| **G** | P35 | Cam reference |
| **IGT** | P11 | Ignition trigger to the igniter |
| **IGF** | SC1 | Ignition confirmation from the igniter |
| **injector** | P21 | Injector drive. Low = injector open |
| **IDL** | P16 | Throttle idle contact. Low = throttle closed |
| **T** | P30 | Test terminal. Low = T connected to E1 |
| **J8** | P34 | A jumper on the ECU board. It selects the ignition map and a fuel correction |
| **A/C** | P37 | Air-conditioning switch. High = on |
| **ADC** | P12–P15, P20 | The analogue-to-digital converter of the ECU board (outside the CPU). P12–P14 select the channel, P15 is the hold line, P20 is the end-of-conversion signal |
| **MAP** | ADC channel 1 | Manifold pressure (PIM sensor) |
| **THW**, **THA** | ADC channels 5, 6 | Coolant temperature, intake-air temperature |
| **Load** | RAM `$46` | The ROM's engine-load value, from MAP |
| **RpmWord** | RAM `$77` | Engine speed × 0.32 |

## Tools and tests

| Name | Meaning |
|---|---|
| **simulator** | The Python model of the CPU, its peripherals and an engine (`pcmre.emu`). It runs a ROM without hardware |
| **emulator** | The C model of the CPU (`hardware/ecu-emu/core`). It runs on the Pico 2 W and on a PC |
| **Pico 2 W** | The Raspberry Pi Pico 2 W board (RP2350 microcontroller). It is the only project board |
| **PIO** | The programmable I/O blocks of the RP2350 |
| **UF2** | The firmware file format for the Pico 2 W |
| **reader** | The Pico 2 W firmware and breadboard that read the ROM out of the CPU |
| **serial link** | The diagnostic link of the 17140. It sends RAM values on request (RAM peek) |
| **chip test** | The test of the real CPU against the emulator, on the reader breadboard (chip-in-isolation test) |
| **loopback test** | The test of the real-time emulator on one Pico 2 W, with no wires |
| **car rig** | The Pico 2 W connected by jumper wires to the CPU socket of the spare ECU |
| **gate** | A set of conditions that a phase must meet before the next phase starts ([roadmap](project/roadmap.md)) |
| **Verifier** | An independent agent that examines the work of a phase. A gate needs its approval |
| **owner** | The person who owns the project and the car |
| **Ross** | Jeremy Ross, author of the articles "Lifting the Lid on the mk1 MR2 ECU" (`reference/`) |
| **defs file** | `roms/<name>/defs.yaml`: the map definitions of one ROM. Map pages, CSV files and the XDF come from it |
| **symbols file** | `roms/<name>/symbols.yaml`: the names and notes for the 17140 source |
| **XDF** | A map definition file for TunerPro |
