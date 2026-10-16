# Hardware

## Summary

This folder holds the firmware for the Raspberry Pi Pico 2 W and the C emulator of the CPU. Each firmware project builds with pico-sdk 2.1.1 and makes one UF2 file. All projects use [`cmake/pico_sdk_import.cmake`](cmake/pico_sdk_import.cmake).

| Folder | Firmware (UF2) | Purpose | Documentation |
|---|---|---|---|
| [`rp2350-reader/`](rp2350-reader/) | `rp2350_reader_<board>.uf2` | Reads the ROM out of the CPU | [ROM dump](../docs/procedures/rom_dump.md) |
| [`peek-logger/`](peek-logger/) | `peek_logger_pico2_w.uf2` | Records RAM values from the ECU over the serial link | [serial link](../docs/mr2/serial_link.md) |
| [`ecu-emu/core/`](ecu-emu/core/) | — | The C emulator: CPU core and D151801 peripherals | [emulator design](../docs/emulator/design.md) |
| [`ecu-emu/bench/`](ecu-emu/bench/) | `ecu_emu_bench_pico2_w.uf2` | Measures the speed of the emulator on the Pico 2 W | [validation](../docs/emulator/validation.md) |
| [`ecu-emu/loopback/`](ecu-emu/loopback/) | `ecu_emu_loopback_pico2_w.uf2` | Runs the emulator in real time against an engine model, with no wires | [validation](../docs/emulator/validation.md) |
| [`ecu-emu/chipdiff/`](ecu-emu/chipdiff/) | `ecu_chipdiff_pico2_w.uf2` | Runs the real CPU against the engine model, for comparison with the emulator | [chip test](../docs/procedures/chip_test.md) |
| [`ecu-emu/car/`](ecu-emu/car/) | `ecu_emu_car_pico2_w.uf2` | Runs the emulator on the pins of the ECU board, in place of the CPU | [car test](../docs/procedures/car_test.md) |

## Build

1. Set `PICO_SDK_PATH` to a pico-sdk 2.1.1 folder.
2. Run `cmake -S hardware/<folder> -B build -DPICO_BOARD=pico2_w`.
3. Run `cmake --build build`.

Warnings stop the build. The CI workflow builds all projects on each push.

**CAUTION:** read the hardware safety rules in [`CLAUDE.md`](../CLAUDE.md) before you connect a Pico 2 W to a CPU or an ECU.
