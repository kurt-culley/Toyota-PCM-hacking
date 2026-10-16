# Document index

## Summary

This page lists each documentation page and its purpose. Start with the [README](../README.md) for the project overview. Each page starts with a summary. Open the detail sections for more information.

## Common pages

| Page | Purpose |
|---|---|
| [Writing rules](style.md) | The ASD-STE100 rules and the evidence tags for all documentation |
| [Glossary](glossary.md) | The technical names, with one meaning for each |

## MR2 ECU 89661-17140

| Page | Purpose |
|---|---|
| [Overview](mr2/overview.md) | What is known about the 17140, with links to the detail pages |
| [Hardware](mr2/hardware.md) | The ECU board, the CPU pins and the interface circuits |
| [Program](mr2/program.md) | The ROM program: memory map, interrupts, ports, the rpm limit |
| [Maps](mr2/maps.md) | The ignition and fuel maps, the ADC channels and the scaling |
| [Ignition maps in degrees](mr2/ignition_maps.md) | The ignition maps in degrees BTDC (generated) |
| [Serial link](mr2/serial_link.md) | The diagnostic RAM-peek link and its logger |
| [Factory data](mr2/factory_data.md) | The facts from the Toyota wiring diagram and repair manual |

## Ross articles

| Page | Purpose |
|---|---|
| [Claims](ross/claims.md) | Each claim of the Ross articles, with its status and evidence |
| [Diagrams](ross/diagrams.md) | The flow diagrams of the articles, as Mermaid |
| [Figures](ross/figures/README.md) | The figures taken from the PDF, and how they were made |

## Emulator

| Page | Purpose |
|---|---|
| [Design](emulator/design.md) | The CPU and peripheral model, the timing and the pins of the Pico 2 W |
| [Validation](emulator/validation.md) | The tests that compare the emulator with the real CPU, and their results |

## Procedures

| Page | Purpose |
|---|---|
| [ROM dump](procedures/rom_dump.md) | Read the ROM out of a CPU with the Pico 2 W reader |
| [Chip test](procedures/chip_test.md) | Compare the real CPU with the emulator on the reader breadboard |
| [Car test](procedures/car_test.md) | Connect the Pico 2 W to the spare ECU and do the key-on, engine-off test |

## AE86 Bluetop ECU

| Page | Purpose |
|---|---|
| [Architecture](ae86/architecture.md) | The Bluetop ROM program and its memory map |
| [Fuel chain](ae86/fuel_chain.md) | How the Bluetop ROM calculates the injection time |
| [Simulation](ae86/simulation.md) | The results of the Bluetop ROM in the simulator |
| [Versions](ae86/versions.md) | The differences between the 0642 and 2860 ROMs |
| [Ignition table](ae86/ignition_table.md) | The Bluetop ignition map in degrees BTDC (generated) |

## Project

| Page | Purpose |
|---|---|
| [Roadmap](project/roadmap.md) | The phases, the gates and the next steps |
| [Open items](project/open_items.md) | The open questions and the open conflicts between sources |
| [Hardware list](project/hardware_bom.md) | The parts that the project uses, and why each part is necessary |
| [Upstream notes](project/upstream_notes.md) | The facts about the D151801 from the upstream repository and forums |

## Other READMEs

| Page | Purpose |
|---|---|
| [ROMs](../roms/README.md) | The ROM folders and the files in each folder |
| [Tools](../src/pcmre/README.md) | The `pcmre` command and the Python package |
| [Hardware](../hardware/README.md) | The Pico 2 W firmware projects |
| [Data](../data/README.md) | Sensor curves and bench captures |
| [Reference](../reference/README.md) | The data books and articles |
