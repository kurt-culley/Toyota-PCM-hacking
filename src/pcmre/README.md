# pcmre tool guide

## Summary

`pcmre` is the Python package of this repository. It has the disassembly and source tools, the map generators, the support tools for the firmware, the simulator (`pcmre.emu`) and the Ross figure tool (`pcmre.ross`). The command `uv run pcmre <command>` starts each tool. A test makes sure that each generated file is current. The [roadmap](../../docs/project/roadmap.md) gives the phases that use the tools.

## Install

```sh
uv sync                     # Python environment: pyyaml, pytest, ruff, pillow
uv sync --extra serial      # also pyserial, for live captures from the Pico 2 W
tools/setup_assemblers.sh   # builds asl and p2bin (main) and dasm (cross-check) into .tools/
tools/setup_mame_ref.sh     # builds the MAME HD6301 reference for the CPU tests into .tools/
```

Both scripts can run again with no effect. `.tools/` is not in git. A test that needs `asl`, `dasm` or the MAME reference does not run if the tool is not built. GitHub Actions sets `REQUIRE_MAME_REF`, so there the MAME test must run.

## Commands

`uv run pcmre` lists the commands. `uv run pcmre <command> --help` gives the options of one command. Each command is the same as `uv run python -m <module>`. The list comes from `COMMANDS` in [`cli.py`](cli.py).

| Group | Command | Module | Purpose |
|---|---|---|---|
| Disassembly and source | `roundtrip` | `pcmre.roundtrip` | AE86 ROM: the generated source reassembles to the same bytes |
| | `xref` | `pcmre.xref` | Cross-reference and call graph of a ROM |
| | `symlisting` | `pcmre.symlisting` | MR2 ROM: labelled source and cross-reference from `symbols.yaml` |
| | `ingest` | `pcmre.ingest` | First report on a new ROM dump |
| | `crossver` | `pcmre.crossver` | AE86 ROM: compare two software versions and port the maps |
| Maps | `defs` | `pcmre.defs` | Map pages, CSV files and TunerPro XDF from `roms/<name>/defs.yaml` |
| | `readable` | `pcmre.readable` | AE86 ignition table in degrees |
| | `readable17140` | `pcmre.readable17140` | MR2 ignition maps in degrees |
| | `checksum` | `pcmre.checksum` | Examine or correct the ROM word sum |
| Hardware support | `romdump` | `pcmre.romdump` | Assemble the reader programs into the firmware header |
| | `romcapture` | `pcmre.romcapture` | Capture a ROM from the reader over USB |
| | `peeklog` | `pcmre.peeklog` | Decode a serial-link log into physical units |
| | `wiring` | `pcmre.wiring` | Reader wiring tables and pictures |
| | `chipdiff-wiring` | `pcmre.chipdiff_wiring` | Chip-test breadboard layout |
| | `car-rig` | `pcmre.car_rig_diagram` | Car rig wiring table and pictures |
| | `gen-hd6301-c` | `pcmre.gen_hd6301_c` | Generate the opcode and timing tables of the emulator (C) |
| Emulator | `chipdiff` | `pcmre.emu.chipdiff` | Capture the chip test and compare it with the emulator |
| | `loopback-ref` | `pcmre.emu.loopback_ref` | Reference checksums for the loopback firmware |
| Reference data | `digitise` | `pcmre.ross.digitise` | Digitise the figures of the Ross articles |

Examples:

```sh
uv run pcmre ingest roms/mr2_17140/89661-17140.bin --name mr2_17140
uv run pcmre checksum edited.bin --fix
uv run --extra serial pcmre romcapture /dev/ttyACM0
uv run --extra serial pcmre chipdiff capture /dev/ttyACM0 run.log
uv run pcmre chipdiff analyse run.log
```

## Package map

| Module | Purpose |
|---|---|
| `cli.py` | The `pcmre` command: one entry point for each tool |
| `paths.py` | Each repository path that the tools use |
| `hd6301.py` | HD6301 opcode table (the MC6801 set, plus XGDX, SLP and AIM/OIM/EIM/TIM) and a decoder for one instruction. `asl` agrees on each opcode |
| `idalisting.py` | Imports labels, comments and the code/data split from the IDA 4.9 listing (`cap.asm`). It finds the addresses from the ROM bytes and stops on a mismatch (`ListingMismatch`) |
| `emit.py` | Writes source for `asl` (main) or `dasm` (cross-check). Each byte comes from the ROM; the listing gives only names and comments |
| `roundtrip.py` | Writes the AE86 source again and assembles it with both assemblers. The result must be the same bytes as the ROM |
| `xref.py` | Cross-references and Mermaid call graphs. It follows the code from the vectors with a small model of X, B and the stack, so it follows Denso indexed calls, jump tables and inline parameters |
| `symlisting.py` | Labelled source and cross-reference of the 17140 from `roms/mr2_17140/symbols.yaml`, with a round trip through `asl` |
| `ingest.py` | First report on a new D151801 ROM: size, vectors, word sum, trace, alignment with the Bluetop, map port, candidate tables, Ross table search |
| `crossver.py` | Compares the two Bluetop versions (0642 and 2860), ports the maps and lists the behaviour changes |
| `tables.py` | Python model of the Bluetop table lookups (the 1D helper at `$FF1B`–`$FF3F` and the 3D ignition lookup). A test makes sure that it agrees with the simulator |
| `defs.py` | Map page, CSV files and XDF from `roms/<name>/defs.yaml` |
| `readable.py` | The Bluetop ignition table in degrees, with load as a percentage |
| `readable17140.py` | The 17140 ignition maps in degrees over rpm and kPa |
| `checksum.py` | The ROM word sum: the 16-bit sum of the words `$F000`–`$FFFF` must be `$AA55`. `--fix` balances it at `$FFEE` |
| `readerdecode.py` | Python model of the bus rule of the reader firmware: when the reader drives the bus, and when it only listens |
| `romdump.py` | Assembles the reader programs and writes the firmware header `romdump.h` |
| `romcapture.py` | Captures the ROM from the reader (Intel HEX over USB) and writes the `.bin` and `.sha256` files. It does not write over a file with different bytes |
| `peeklog.py` | Decodes a log of the serial-link logger into physical units (table or CSV) |
| `wiring.py` | Reader wiring tables and pictures, from the `pins.h` file of the firmware |
| `chipdiff_wiring.py` | Chip-test breadboard layout, as changes to the reader layout |
| `car_rig_diagram.py` | Car rig wire table and pictures, from `hardware/ecu-emu/car/pins.h` |
| `gen_hd6301_c.py` | Writes the instruction switch and the cycle tables of the C emulator from the Python opcode table |
| `emu/cpu.py` | HD6301 CPU core: each documented opcode, cycle counts (HD6301 or MC6801), TRAP, WAI, SLP, interrupts. The peripherals are behind a `Bus` |
| `emu/periph.py` | On-chip peripherals: timer 1, the second timer of the D151801, the serial ADC on the SCI, the ports, IS3 and an event queue |
| `emu/harness.py` | Runs one ROM routine, or a part of the code, with preset registers, RAM and inline parameters |
| `emu/engine.py` | Engine and sensor model of the Bluetop: NE, G, SE056 airflow, IGF, ADC readings, switches |
| `emu/engine17140.py` | Engine and sensor model of the 17140: NE on IC2 (30° each edge), G on P35, the ADC on IC1, IGT on P11, the injector on P21 |
| `emu/sensors.py` | Sensor models from `data/sensors` (PIM, coolant and intake-air NTC) |
| `emu/sim.py` | `Simulation`: starts a ROM from reset and runs it against the engine model. Probes give RAM values by name, injector pulses and the spark angle |
| `emu/peek17140.py` | Host side of the serial link of the 17140, for the simulator |
| `emu/cboard.py` | The C emulator, called from Python, with the same interface as `Simulation`. Tests run both together |
| `emu/chipdiff.py` | Chip test: capture the log of the Pico 2 W, replay the inputs into the emulator, compare each output edge |
| `emu/loopback_ref.py` | The schedule of the loopback test and chip test, and the reference checksums `expected.h` |
| `ross/digitise.py` | Extracts the figures of the Ross articles (`pdfimages`) and reads the curves by pixel into CSV |

## Where data is

[`paths.py`](paths.py) gives each path. In short:

| Path | Contents |
|---|---|
| `roms/<name>/` | One folder for each ROM (`mr2_17140`, `bluetop`, `bluetop_2860`): the dump, `defs.yaml`, `symbols.yaml`, and the files made from them |
| `data/sensors/` | Sensor curves from factory data |
| `data/captures/` | Bench captures (dump log, chip test logs) |
| `reference/` | Data books and the Ross articles (PDF) |
| `docs/` | Documentation. Some pages and pictures come from generators |
| `hardware/` | Firmware and the C emulator core |
| `.tools/` | `asl`, `dasm` and the MAME reference, made by `tools/setup_*.sh` |

## Generated files

Do not edit a generated file by hand. Change the source or the generator, then run the command again. The test in the table fails if the file is not current.

| File | Command | Test |
|---|---|---|
| `roms/bluetop/cap.s` | `pcmre roundtrip --write` | `tests/tooling/test_roundtrip.py` |
| `roms/bluetop/xref.md` | `pcmre xref --write` | `tests/tooling/test_xref.py` |
| `roms/mr2_17140/mr2_17140.asm`, `roms/mr2_17140/xref.md` | `pcmre symlisting mr2_17140 --write` | `tests/tooling/test_symlisting.py` |
| `roms/bluetop/maps.md`, `maps/*.csv`, `bluetop.xdf` | `pcmre defs bluetop --write` | `tests/ae86/test_defs.py` |
| `roms/bluetop/crossver_2860.md`, `roms/bluetop_2860/defs.yaml` and its maps and XDF | `pcmre crossver --write`, then `pcmre defs bluetop_2860 --write` | `tests/ae86/test_crossver.py` |
| `docs/ae86/ignition_table.md`, `roms/bluetop/readable/ign_base_degrees.csv` | `pcmre readable --write` | `tests/ae86/test_readable.py` |
| `docs/mr2/ignition_maps.md` | `pcmre readable17140 --write` | `tests/mr2/test_sim17140.py` |
| `hardware/rp2350-reader/firmware/src/romdump.h` | `pcmre romdump --write` | `tests/hardware/test_romdump.py` |
| Reader tables in `docs/procedures/rom_dump.md` | `pcmre wiring` (`--png` for the pictures) | `tests/hardware/test_wiring.py` |
| Chip-test table in `docs/procedures/chip_test.md` | `pcmre chipdiff-wiring` (`--png` for the picture) | `tests/hardware/test_chipdiff_wiring.py` |
| Car rig table in `docs/procedures/car_test.md` | `pcmre car-rig --table` | `tests/hardware/test_car_rig.py` |
| `hardware/ecu-emu/core/hd6301_ops.inc`, `hd6301_timing.inc` | `pcmre gen-hd6301-c --write` | `tests/emu/test_hd6301_c.py` |
| `hardware/ecu-emu/loopback/expected.h` | `pcmre loopback-ref --write` | `tests/hardware/test_loopback_engine.py` |

The `wiring`, `chipdiff-wiring` and `car-rig` commands print a table. Paste it into the page.

<details>
<summary>Notes on the disassembly of the Bluetop</summary>

- **Branches into an instruction.** The Bluetop code jumps into the middle of an instruction at 6 locations. For example, `cpx #$8DDE` has a `bsr` in its operand bytes. The generator writes these targets as `label+offset`.
- **IDA comment hints.** IDA adds ASCII hints of one character to byte values (`; O`). The importer removes them. One of them, `; \`, is a line continuation for `asl`.
- **`dasm` limit.** The `dasm` 6303 table encodes AIM/OIM/EIM/TIM incorrectly (it drops the immediate byte). The Bluetop ROM does not use them. For a ROM that uses them, only `asl` is the reference.
- **Inline parameters and stack arguments.** `boundData` reads two bound bytes after the call. `mulDbyStack` removes a byte that the caller pushed. `xref.py` models both.
- **IDA error at `$F4C9`.** IDA shows the two inline bytes after `jsr boundData` at `$F4C6` as code. They are data (bounds `$A0`/`$14`).
- **Limits of the analyser.** It does not follow each pass of a loop. If a loop changes X or B, the value becomes unknown. `xref.md` counts the indexed data sites with an unknown X, so its RAM lists are not complete.

</details>

## MAME reference and the differences of the simulator

`tests/emu/test_emu_cpu.py` runs 64 random cases of one instruction for each opcode through the MAME hd6301 handlers and through `emu/cpu.py`. The registers, flags, memory writes (in order) and cycle counts must agree.

- `tools/setup_mame_ref.sh` downloads the MAME source (BSD-3-Clause) at tag `mame0275` and examines its SHA-256. `tools/mame_ref/harness.cpp` compiles the MAME handlers without changes. No MAME code is in git.
- The HD6301 cycle table in `emu/cpu.py` comes from the handbook, not from MAME. Thus the cycle comparison is between two independent sources.
- The D151801 uses MC6801 instruction timing ([chip test](../../docs/procedures/chip_test.md)). The simulator uses `CYCLES_6801` (from the MAME `cycles_6803` table) for it: `HD6301(bus, timing="6801")`.

The deliberate differences, all from the handbook:

- CCR bits 7–6 always read as 1. The test compares only bits 5–0.
- `$12` and `$13` cause a TRAP on the HD6301. MAME does undocumented MC6801 operations for them.
- The TRAP cycle count of MAME is a placeholder. The test does not compare it.
- DAA V flag: the handbook gives two different answers (table 3-2-1, PDF p.190: V changes; instruction detail, PDF p.89: V does not change). The core clears V, as MAME does. The conflict is in [open items](../../docs/project/open_items.md). The Bluetop and 17140 ROMs do not use DAA.
- The address trap for an instruction fetch from a non-memory area (handbook §2.13) is not in the model.
- The test compares memory writes, not reads. Reads are important only for I/O registers that clear on a read, and the peripheral models handle them.

## Tests

```sh
uv run pytest                    # all tests
uv run pytest tests/mr2          # one folder
uv run ruff check                # lint
```

| Folder | Tests |
|---|---|
| `tests/tooling/` | Decoder, round trip, cross-reference, 17140 source, ingest |
| `tests/emu/` | CPU core against MAME, harness, peripherals, profiles, sensor tables, C core and C peripherals against Python |
| `tests/ae86/` | Bluetop tables, fuel chain, simulation, maps, versions, ignition table |
| `tests/mr2/` | 17140 simulation, serial link, rev limit, Ross claims, Ross figures |
| `tests/hardware/` | Reader rule and dump program, ROM capture, wiring, chip test, loopback, car firmware and car rig, serial-link logger |

GitHub Actions runs the tests and builds the firmware.
