# CLAUDE.md: standing rules for agents in this repo

This repo reverse-engineers the Denso ECU **89661-17140** of the mk1 Toyota MR2 (AW11). The AE86 Bluetop ECU (same CPU type) is kept as a reference. The owner knows aftermarket tuning well but is new to reverse engineering, so **agents take the lead**: explain your reasoning, propose the next step, and ask only when a decision belongs to the owner.

- **Plan and gates:** [`docs/project/roadmap.md`](docs/project/roadmap.md). Read it before starting any work.
- **Open questions and conflicts:** [`docs/project/open_items.md`](docs/project/open_items.md). Update it, and the roadmap, at the end of every session.
- **All pages:** [`docs/index.md`](docs/index.md). Add each new page there (a test checks it).

## Fundamental rules

1. **RP2350-first, minimal purchases.** Design every hardware task around the project's RP2350 board, the **Raspberry Pi Pico 2 W** (with headers): ROM reader, serial-link logger, real-CPU harness, bench stimulus and timing, and the in-car board that replaces the CPU and emulates it ([`docs/emulator/design.md`](docs/emulator/design.md)). Buy a part only when the Pico 2 W cannot do the job, and write the reason in [`docs/project/hardware_bom.md`](docs/project/hardware_bom.md). Any new exception needs the owner's approval, logged in `open_items.md`. **The RP2350's digital pads take 5 V only while the board is powered:** power the 5 V side last and remove it first; drive 5 V-CMOS inputs (RES, STBY, EXTAL) open-drain with a pull-up; use dividers or clamps for 12 V, flyback, VR and ADC-pin signals; never enable internal pull-downs (erratum E9).
2. **Modern toolchain.**
   - The installable Python package `pcmre` (`src/pcmre/`), run with `uv run pcmre <command>`. No `PYTHONPATH`.
   - `uv`, `pytest` and `ruff`; the `asl` assembler; the Python HD6301 simulator and the C emulator.
   - sigrok/PulseView; pico-sdk 2.1.1 with PIO; KiCad; TunerStudio, or TunerPro RT for raw ROM files.

   Ghidra is **optional**: an interactive browser for the owner, never a dependency or a gate. IDA listings (`cap.asm`, `*.idb`) are for cross-checking only.
3. **Verify Ross first.** Cold-start work (P5) starts only after the "Ross verified" gate (P4). See [`docs/ross/claims.md`](docs/ross/claims.md).

## Evidence and truth

- **Source-of-truth order:**
  1. ROM bytes
  2. Bench or car measurement
  3. Factory service documentation ([`docs/mr2/factory_data.md`](docs/mr2/factory_data.md); the original PDFs are Toyota copyright and are not committed)
  4. Ross PDF (`reference/ross_lifting_the_lid_mk1_mr2_ecu.pdf`)
  5. Existing `cap.asm` annotations
  6. Upstream notes ([`docs/project/upstream_notes.md`](docs/project/upstream_notes.md)) and forums

  Log every conflict in `open_items.md`. Never resolve one silently.
- **Tag every claim** with its evidence (`[ROM:$F863]`, `[PDF:p12]`, `[EMU:test]` or `[BENCH:data/captures/file]`) and a confidence level (CONFIRMED, LIKELY or GUESS).
- **Verifier sign-off** is required at every gate. A session must not verify its own work.

## Documentation

- Write all documentation in **ASD-STE100 Simplified Technical English** to [`docs/style.md`](docs/style.md), with the names in [`docs/glossary.md`](docs/glossary.md).
- Each page starts with `## Summary`. Put detail in sub-sections or `<details>` blocks.
- Write facts only: no session history, dates of work, decision logs or Verifier rounds. Measurements cite their capture file in `data/captures/`.
- Use **Mermaid** for flows, signal chains and state machines.
- **Map write-ups** give the axes in physical units, the raw → physical scaling with its derivation, and an "In tuning terms" paragraph.
- Generated pages and tables name their generator. Change the generator and run it again; never edit generated text by hand.

## Conventions

- **One definition file per ROM**, `roms/<rom>/defs.yaml`. Generate XDF, CSV and Markdown from it. Never hand-maintain two copies.
- **Never modify a ROM dump in `roms/`** (`*.bin`, `*.idb`, `cap.asm`). New work goes in `src/`, `docs/`, `hardware/` and `data/`.
- **Every repo path** comes from `src/pcmre/paths.py`. Do not write a path again in a module or a test.
- **PDFs** are in `reference/`. Read them locally with `pdftotext` / `pdfimages`.

## Hardware safety (needs the owner's confirmation every time)

- Bring the D151801 supply up **before** releasing /RES.
- Use ESD precautions. Keep a known-good ECU aside.
- Never run the engine on untested code. The emulator must first match the stock CPU (the chip test, [`docs/procedures/chip_test.md`](docs/procedures/chip_test.md)).
- Agents may draft posts for the upstream repo, but must never post without the owner's approval.

## Repo map

| Path | Contents |
|---|---|
| `roms/mr2_17140/` | The 17140 dump, `symbols.yaml`, `defs.yaml`, generated source and cross-references |
| `roms/bluetop/`, `roms/bluetop_2860/` | The AE86 Bluetop ROMs (0642 and 2860), the IDA listing, defs and generated files |
| `src/pcmre/` | The Python tools: disassembler, map generator, simulator (`emu/`), Ross figure tools (`ross/`) |
| `hardware/` | Pico 2 W firmware: `rp2350-reader/`, `peek-logger/`, `ecu-emu/{core,bench,loopback,chipdiff,car}`, shared `cmake/` |
| `tests/` | `tooling/`, `emu/`, `mr2/`, `ae86/`, `hardware/`, `docs/` |
| `docs/` | The documentation ([`docs/index.md`](docs/index.md)) |
| `data/` | Sensor curves and bench captures |
| `reference/` | Data books, the Ross PDF, the AE86 board schematic |
| `tools/` | Assembler and MAME setup scripts, vendored dasm |
