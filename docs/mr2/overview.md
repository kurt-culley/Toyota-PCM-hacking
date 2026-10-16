# MR2 17140: overview

## Summary

The 17140 is the Denso ECU 89661-17140 of the UK mk1b Toyota MR2 (AW11, 4A-GE). Its CPU is a Denso D151801-7110 with an HD6301 core and a 4 KB internal ROM. The ROM is dumped, labelled and runs in the simulator and in the emulator. The ROM has speed-density fuel, two ignition maps selected by a jumper, a fuel-only rpm limiter and a read-only serial link. The emulator agrees with the real CPU on spark and fuel at steady operating points. The ECU has not run on the emulator in the car.

## The ECU

| Item | Value | Page |
|---|---|---|
| ECU | Toyota 89661-17140, Denso 175700-1043, PCB 175731-0460 rev A2, build date 30 Nov 1988 | [hardware](hardware.md) |
| CPU | IC7, Denso **D151801-7110**, 40-pin DIP, HD6301 core, MC6801 instruction timing (LIKELY), 4.00 MHz crystal, E = 1 MHz | [hardware](hardware.md#cpu-ic7) |
| Memory | ROM 4 KB at `$F000`–`$FFFF` (word sum `$AA55`); RAM 192 bytes at `$40`–`$FF` | [program](program.md#memory-map) |
| Second timer | Registers `$18`, `$1B`, `$1D`; P10 (NE input capture), P11 (IGT output compare) | [hardware](hardware.md#cpu-ic7) |
| Mode | Mode 7 (single chip) in the car. The ROM also accepts mode 2 | [program](program.md#differences-from-the-bluetop) |
| ROM file | [`roms/mr2_17140/89661-17140.bin`](../../roms/mr2_17140/89661-17140.bin), SHA-256 `0cfc1fdd…6f271f6e`. Three identical reads [BENCH:data/captures/89661-17140_dump_2026-10-13.txt] | [ROM dump](../procedures/rom_dump.md) |

## What is known

| Area | Result | Confidence | Page |
|---|---|---|---|
| Program structure | Tables at `$F000`–`$F2BD`, code from `$F2BE`. The crank interrupt sets event flags; the main loop does the arithmetic. No hidden code | CONFIRMED (code) | [program](program.md) |
| Ports | P34 (jumper J8) selects the ignition map; P30 = test terminal T; P16 = IDL; P37 = A/C; P41 = T-VIS VSV; P31 = idle-up output (GUESS) | LIKELY | [program](program.md#port-3-and-port-4) |
| Sensors | ADC on input capture 1, 8 channels: zero, MAP, throttle, mixture screw, battery, coolant, intake air, reference. No O2 sensor | LIKELY | [maps](maps.md#sensor-channels) |
| Engine speed | `RpmWord` `$77` = rpm × 0.32 | CONFIRMED [EMU] | [maps](maps.md#engine-speed) |
| Ignition | Map A `$F1EF` (13 × 8) or map B `$F25D` (13 × 7), 800–5600 rpm. 15/64° per count; a warm cell is approximately its own advance in degrees BTDC | scale CONFIRMED [EMU]; absolute LIKELY | [maps](maps.md#ignition), [ignition maps](ignition_maps.md) |
| Fuel | Speed-density chain: density, speed correction, staircases, THA, global factor, mixture term, dead time | LIKELY | [maps](maps.md#fuel-speed-density-chain) |
| Load scale | Load `$46` ≈ 6.14 × kPa + 123 | LIKELY | [maps](maps.md#load-scale) |
| Rpm limit | Fuel only, 7600 rpm (7400 rpm after a fast climb), no hysteresis | CONFIRMED (code) | [program](program.md#speed-limit) |
| Serial link | RAM peek, `$00`–`$FF`, 7812.5 baud, read-only. Switched on by RX low at reset | CONFIRMED (code) | [serial link](serial_link.md) |
| Ross articles | 43 claims tested on the 17140 ROM: 30 CONFIRMED, 8 DIFFERS-BY-ECU, 4 PARTIAL, 1 CONTRADICTED (rpm axis of R-M02) | — | [Ross claims](../ross/claims.md) |

## Simulator, emulator and car

| Item | Result | Evidence | Page |
|---|---|---|---|
| Simulator (Python) | Runs the ROM from reset with its own I/O model ([`engine17140.py`](../../src/pcmre/emu/engine17140.py)): NE/G sync, 8 ADC channels, two sparks and one injection per revolution | [EMU:tests/mr2/test_sim17140.py] | [emulator design](../emulator/design.md) |
| Emulator (C) | The same result as the Python CPU on all 256 opcodes and 200,000 steps of the 17140 ROM. The D151801 peripherals agree with the simulator at 8 operating points | [EMU:tests/emu/test_hd6301_c.py, tests/emu/test_d151801_c.py] | [emulator design](../emulator/design.md) |
| Speed on the Pico 2 W | 4.6 × the real CPU at 150 MHz, 7.7 × at 250 MHz | [BENCH] | [emulator design](../emulator/design.md) |
| Chip test | Closed loop at 800, 2000 and 5000 rpm: every spark edge (6 238) and injector edge (3 130) of the real CPU, at a constant 2-cycle offset. ADC sequence 99.3–99.6 %. Replay does not agree yet | [BENCH:data/captures/chipdiff_17140_run5_6phase_2026-10-15.log] [EMU:tests/hardware/test_chip_vs_emulator.py] | [emulator validation](../emulator/validation.md), [chip test](../procedures/chip_test.md) |
| Car rig | Firmware for key on, engine off: the emulated CPU in the CPU socket of the spare ECU, with IGT and the injector held at their engine-stopped level. Not run in the car | [EMU:tests/hardware/test_car_fw.py] | [car test](../procedures/car_test.md) |

The engine must not run on the emulator before the chip test passes in full ([`CLAUDE.md`](../../CLAUDE.md)).

## Open items

These items are open ([open items](../project/open_items.md)):

- the stock level of P34 (which map the car uses)
- the kPa scale
- the absolute advance
- the board tracks of `VISC`, `FPU`, `OX`, `FC` and CPU pins 11/12
- the full chip-test pass.

## Read next

1. [Hardware](hardware.md): board, CPU, connector labels, jumpers, continuity results.
2. [Program](program.md): memory map, ports, interrupts, main loop, option behaviours, rpm limit.
3. [Maps](maps.md): ADC channels, ignition maps, fuel chain, scales.
4. [Ignition maps](ignition_maps.md): the two maps in degrees (generated).
5. [Serial link](serial_link.md): the RAM-peek protocol and the logger.
6. [Factory data](factory_data.md): the 1984 wiring diagram and the 1988 repair manual.
7. [Ross claims](../ross/claims.md): the claims of the Ross articles and their status.
