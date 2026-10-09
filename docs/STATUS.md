# Project status

The Lead agent updates this file at the end of every session. The plan is in [`RE_PLAN.md`](RE_PLAN.md).

**Last updated:** 2026-10-09 — The factory wiring diagram (1984 EWD) and the second photo set are recorded: the CSI and idle air are not ECU-driven, `STH` = T-VIS output, PCB is 175731-0460-A2. A continuity-test guide for the owner is ready. P0 next: cross-reference/call-graph generator, then the emulator.

## Phase checklist

| Phase | Description | State | Gate signed off by Verifier |
|---|---|---|---|
| P0 | Foundations: tooling, asl round-trip, xref, emulator | ◐ round-trip gate passed; xref + emulator outstanding | ☐ |
| P1 | Ross claim register (skeleton done; figures and Mermaid diagrams outstanding) | ◐ started | — |
| P2 | Bluetop analysis + Tier-A verification | ☐ | ☐ |
| P3 | Dump the MR2 89661-17140 ROM (Arduino Zero reader) | ☐ | — |
| P4 | MR2 analysis + Tier-B verification → **Ross verified** | ☐ | ☐ |
| P5 | Warm-up / cold start (goal 1), blocked until the P4 gate | ☐ blocked | ☐ |
| P6 | Secret maps (goal 2) | ☐ | ☐ |
| P7 | Modified ROM + TunerStudio (goal 3) | ☐ | ☐ |
| P8 | Bench rig + validation (Arduino Zero) | ☐ | — |

### P0 tasks
- [x] Archive the missing upstream comments (#4 and #1, all read through the API on 2026-10-09). See [`upstream_issues.md`](upstream_issues.md).
- [x] Set up the Python project (`uv`, `pytest`, `ruff`) and GitHub Actions CI (`.github/workflows/ci.yml`).
- [x] Build `asl` 1.42 bld306 from source, plus `dasm` from the vendored copy: [`../tools/setup_assemblers.sh`](../tools/setup_assemblers.sh).
- [x] HD6301 opcode table and decoder: all 230 opcodes verified against `asl`.
- [x] `cap.asm` → label/comment/code-data importer. It rebuilds every address by walking the listing alongside `cap.bin`: 1,980 instructions, 331 data lines, 339 ROM labels and 141 RAM labels, with every mnemonic matching the ROM.
- [x] **Gate: [`analysis/bluetop/cap.s`](../analysis/bluetop/cap.s) reassembles byte-identical to `cap.bin` with `asl`, and the `dasm` cross-check agrees** (`uv run pytest`, 2026-10-09). The ROM's SHA-256 (`62b2a3f2…7f2`) is pinned in the tests.
- [ ] Cross-reference and call-graph generator: `analysis/bluetop/xref.md` lists the readers, writers and callers of every RAM variable and routine, with Mermaid call graphs.
- [~] ~~Ghidra + pyghidra~~ **Made optional (owner decision, 2026-10-09).** There is no HD6301 module, and a decompiler adds little on hand-written 8-bit code. It is not a dependency or a gate. A later optional task may write a setup guide so the owner can browse the ROMs in Ghidra on their own PC.
- [ ] Python HD6301 emulator passing the `suite6303` instruction tests (next P0 task).
### P1 tasks
- [x] Claim register skeleton: [`ross/claims.md`](ross/claims.md).
- [ ] Extract the 16 figures (`pdfimages`) and confirm the page mapping.
- [ ] Digitise the graphs to CSV, and transcribe the 17×8 ignition table.
- [ ] Mermaid diagrams of Ross's fuel chain, ignition chain and injection-mode state machine (`ross/diagrams.md`).

### P3 pre-purchase checks (from the HD6301 handbook and `bluetopreader.sch`)
- [ ] Mode-pin strapping for external vector fetch with the internal ROM still readable.
- [ ] MCU minimum clock frequency: static (single-step) or a slow continuous clock.
- [ ] Internal ROM size of the 17140's MCU (the reader assumes 4 KB at `$F000`), per upstream #4.
- [ ] Zero firmware self-test: walking-ones test on every address and data line, then a known-pattern program, then an infinite-loop external-execution test, all before the real dump (upstream #4: a mis-wired bit or wrong mode pins made the chip run its own code).
- [ ] Owner orders [`../hardware/BOM.md`](../hardware/BOM.md) section A.

## Open questions

| # | Question | Who / how |
|---|---|---|
| Q1 | ~~Is the 17140's CPU a 40-pin HD6301-type (like the Bluetop) or a 64-pin Toshiba 8X?~~ **Answered 2026-10-09:** a 40-pin **D151801-7110** with silkscreen "6356/6801" and a 4.00 MHz crystal. It is the same family as the Bluetop, so P3 follows the HD6301 path. See [`hardware/aw11_ecu.md`](hardware/aw11_ecu.md) | Done (photos) |
| Q2 | ~~Does the ECU drive the cold start injector or any idle-air device at all?~~ **Answered (LIKELY for the 17140):** no. The factory wiring diagram shows the CSI wired starter → CSI → time switch, and the idle-up VSV switched by the electrical loads (the ECU only senses it on I/UP). The board label is `STH` = S/TH, the T-VIS output, not STJ. See [`hardware/ewd_aw11_1984.md`](hardware/ewd_aw11_1984.md) | Becomes CONFIRMED when continuity Test B shows `VISC` is an input ([`hardware/aw11_ecu.md`](hardware/aw11_ecu.md)) |
| Q3 | What converts raw ignition-table values to degrees BTDC, and does VR offset matter? | IGT tracing + Zero timing meter (P2/P8) |
| Q4 | Can a 17030 or 17070 dump be found, to check Ross's 17030 numbers directly? | Community search (P3) |
| Q5 | Do NE/G inputs need a VR-style bipolar waveform from the bench simulator? | ECU input-circuit inspection (P8). IC3 (µPC177C comparator) is the likely conditioner |
| Q6 | Do the factory jumpers next to the MCU (**two links fitted among J3/J4/J8**; the rest empty) set Ross's secret-map "logic level", or the HD6301 mode pins (P20–P22)? | Owner runs continuity **Test A** ([`hardware/aw11_ecu.md`](hardware/aw11_ecu.md)), then the ROM is searched for port-bit tests (P6) |
| Q7 | What does the 17140 ROM do with the `OX`/`VF` pins on a UK car with no O2 sensor? | ROM analysis (P4) |
| Q8 | Does the 17140's `OX` pin carry the mixture-screw CO resistor? The 1984 VAF pin is missing from the board (Ross R-M08) | Continuity **Test B**, then the ROM ADC channel map (P4) |
| Q9 | Is there a **1986–89 mk1b wiring diagram** to confirm the 17140 pinout (VISC, OX, W, ACT, FPU ...)? | Owner (the second PDF may be it) |

## Conflicts log

| Date | Topic | Source A says | Source B says | Resolution |
|---|---|---|---|---|
| 2026-10-09 | Max ignition advance | Ross p16 graph: about 50° BTDC | Upstream #6: implausible, may include a VR offset | Open. Settle with a bench measurement (R-I06) |

## Exceptions to the Arduino-first rule

| Date | Item | Reason | Owner approved? |
|---|---|---|---|
| 2026-10-09 | Level shifters (74LVC245, 74AHCT125) | The Zero is not 5 V tolerant | Accepted in the plan |
| 2026-10-09 | Bus-speed CPLD + SRAM (in-car daughterboard, deferred) | Firmware cannot answer a 1 MHz bus in hundreds of ns | Accepted in the plan; nothing ordered yet |
