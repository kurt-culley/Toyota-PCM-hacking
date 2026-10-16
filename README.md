# Toyota MR2 ECU reverse engineering

## Summary

This repository reverse-engineers the Denso ECU 89661-17140 of the mk1 Toyota MR2 (AW11, 4A-GE engine). The ECU uses a Denso D151801 CPU with an HD6301 core. The repository also holds the ROM of the AE86 "Bluetop" ECU, which has the same CPU type, as a reference. The end goal is a changed ROM that you can tune in TunerStudio. A Raspberry Pi Pico 2 W replaces the CPU and runs that ROM.

| Part | State |
|---|---|
| ROM | Read out of the CPU. 4 KB, word sum `$AA55` ([roms/mr2_17140](roms/mr2_17140/)) |
| Program | Labelled source, memory map, interrupts, ports ([program](docs/mr2/program.md)) |
| Maps | Ignition and fuel maps, ADC channels, scaling ([maps](docs/mr2/maps.md)) |
| Diagnostic link | The serial RAM-peek link, with a logger ([serial link](docs/mr2/serial_link.md)) |
| Ross articles | Each claim tested against the ROM ([claims](docs/ross/claims.md)) |
| Emulator | Runs the ROM in real time. It matches the real CPU for spark and injection ([validation](docs/emulator/validation.md)) |
| Car | Key-on, engine-off test with the Pico 2 W on the ECU board ([procedure](docs/procedures/car_test.md)) |

## Where to start

- [Document index](docs/index.md): every page, with its purpose.
- [MR2 ECU overview](docs/mr2/overview.md): what is known about the 17140.
- [Roadmap](docs/project/roadmap.md) and [open items](docs/project/open_items.md): the plan, and what is not known yet.
- [Tools](src/pcmre/README.md): the `pcmre` command and the Python package.

## Quick start

1. Install [uv](https://docs.astral.sh/uv/).
2. Run `uv sync` to install the tools.
3. Run `tools/setup_assemblers.sh` to build the assemblers (asl, dasm).
4. Run `tools/setup_mame_ref.sh` to build the CPU reference for the emulator tests.
5. Run `uv run pytest` to run all tests.
6. Run `uv run pcmre` to see the tool commands.

To build the firmware, install pico-sdk 2.1.1 and the ARM GCC toolchain. Then run `cmake -S hardware/<project> -B build -DPICO_BOARD=pico2_w` and `cmake --build build`. The CI workflow builds every firmware file (UF2) on each push.

## Folders

| Folder | Contents |
|---|---|
| [`docs/`](docs/index.md) | The documentation |
| [`roms/`](roms/README.md) | One folder for each ROM: the dump, its definition files and the files made from them |
| [`src/pcmre/`](src/pcmre/README.md) | The Python tools: disassembler, map generator, simulator, test analysis |
| [`hardware/`](hardware/README.md) | Pico 2 W firmware and the C emulator |
| [`data/`](data/README.md) | Sensor curves and bench captures |
| [`reference/`](reference/README.md) | Data books and articles (PDF) |
| [`tests/`](tests/) | The tests, in groups: tooling, emu, ae86, mr2, hardware |
| [`tools/`](tools/) | Setup scripts and the vendored dasm assembler |

## Rules for contributors

- Read [`CLAUDE.md`](CLAUDE.md) for the project rules, including the hardware safety rules.
- Write documentation to the [writing rules](docs/style.md) (ASD-STE100 Simplified Technical English).
- Do not change the ROM dumps in `roms/`.
