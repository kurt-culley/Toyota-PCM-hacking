# Upstream notes

## Summary

This page keeps the technical points from the issues of the upstream repository, [sparkiedk/Toyota-PCM-hacking](https://github.com/sparkiedk/Toyota-PCM-hacking/issues?q=is%3Aissue). It keeps only the points that apply to the D151801 (HD6301 type) ECUs: the 17140 and the Bluetop. Each point has a link to its issue. These points are level 6 in the source-of-truth order (upstream issues and forums). Use them as leads, and make sure of each one with the ROM or a bench test. Agents can write a draft for the upstream repository, but only the owner can post it.

## Mask ROM and custom code ([#4](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/4))

- The Denso CPUs have a mask ROM. They cannot get a new program.
- To run custom code with the factory CPU, the CPU must run in an external memory mode. The external memory is on a board that replaces the CPU. That mode takes port pins, so the board must make the lost ports again. This project replaces the CPU with an emulator instead ([emulator design](../emulator/design.md)).
- **Lesson for a board design:** connect each strobe and port pin that the ECU uses. On an upstream board, one strobe pin had no connection, and the idle input needed an extra wire.

## Dump method and lessons ([#4](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/4))

The upstream method runs a small reader program on the CPU in an external mode. The program sends the internal ROM over the SCI of the CPU to a 5 V USB-UART adapter.

- **The baud rate is unusual.** The upstream author measured it with a scope. The [reader](../procedures/rom_dump.md) of this project also reads the bus, so the dump does not depend on the baud rate.
- **Three dumps.** The upstream author did three dumps and compared the files. The link had no error check, and about 1 capture in 10 was bad. The reader keeps this rule, with SHA-256.
- **ROM size and base address.** Find the internal ROM size before a dump. The 17140 has 4 KB at `$F000`, the same as the Bluetop.
- **A data stream that does not stop** (or much more data than the ROM size) shows that the CPU runs its own internal program. The mode pins or the external memory are not correct. Prove external execution first, with a loop test and a probe of the bus.
- **One incorrect wire** can let a part of the program run and stop other parts. The `rigcheck` command of the reader tests each address and data line before the CPU goes in.
- **Prove the link before the dump.** The upstream author sent a known text again and again. The reader does this with its `clock` and `probe` commands, and the first byte of the dump is the mode byte.
- **Power and reset.** Apply power before the release of reset. Use a crystal of 4 MHz or less. Put 0.1 µF decoupling on each logic IC.
- **Contention.** A logic level that is more than 10 % away from 0 V or 5 V shows two drivers on one line.
- **Conformal coat.** Remove it from the pins before the CPU is removed.
- **Disassembly.** Start from the interrupt vectors at the end of the ROM. Mark jump tables as code by hand (index, add to the table base, read a 16-bit pointer, jump). `pcmre.xref` follows jump tables of this type (for example `procJmpTable` in the Bluetop).
- The upstream author offered help with the disassembly of a new dump. Agents do not contact him without the approval of the owner.

## Mode pins ([#1](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/1))

- The mode pins of a Denso CPU possibly do not operate as the data sheet shows. On a later CPU, external execution was difficult.
- **For the D151801:** prove external execution before a dump. The 17140 dump used mode 0, with the reset vector external for 3–4 cycles after the release of /RES ([ROM dump](../procedures/rom_dump.md)).
- The 17140 reset code accepts mode 2 as well as mode 7 [ROM:$F2BE] LIKELY.

## The part number does not identify the CPU ([#4](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/4), [#1](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/1))

- Denso part numbers of the form D1518xx-xxxx are used for different CPU families. Some of them are not HD6301 types.
- Identify the CPU by its package and pinout. The 17140 CPU is a 40-pin D151801-7110 with an HD6301 core ([board](../mr2/hardware.md)).

## D151801 extras ([#7](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/7))

- Special-order Denso parts can have extra ports, so a published pinout can be partly incorrect.
- The D151801 has a second timer and more RAM than the HD6301 ([glossary](../glossary.md): second timer).
- The address and data pins have the labels `A_nn_` and `DA_nn_` in the data sheet of the external (ROM-less) mode.

## Ignition units ([#6](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/6))

- To change table values to degrees, follow how the program makes IGT from the NE edges.
- It is not known whether the VR zero-crossing offset is in the tables. The 50° BTDC maximum of Ross was questioned. A bench rig that records NE against IGT settles it.
- In this project: the timing light and the Pico 2 W capture (Q3 and the advance conflict in [open items](open_items.md)), and Ross claim R-I06.
- WinOLS can find tables, but it does not show their format.

## Mazda D151801 ([#1](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/1))

A contributor worked on a Mazda PCM with a Denso D151801-2002 (and a D151801-0490 knock CPU):

- the board design is similar to the Toyota boards;
- WinOLS found the maps, and TunerPro with a Moates Ostrich confirmed them;
- the early Mazda CPUs appear to run only in mode 7.

Thus other D151801 ROMs exist outside Toyota. They are possible reference ROMs.

## Practical ([#8](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/8))

github.com cannot show some PDF files. Use a local copy with `pdftotext` and `pdfimages`.
