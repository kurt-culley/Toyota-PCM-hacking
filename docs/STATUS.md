# Project status

The Lead agent updates this file at the end of every session. The plan is in [`RE_PLAN.md`](RE_PLAN.md).

**Last updated:** 2026-10-09 — P0 round-trip gate passed (asl + dasm byte-identical on the Bluetop ROM). Next: emulator, then Ghidra via CI.

## Phase checklist

| Phase | Description | State | Gate signed off by Verifier |
|---|---|---|---|
| P0 | Foundations: tooling, Ghidra/asl round-trip, emulator | ◐ round-trip gate passed; Ghidra + emulator outstanding | ☐ |
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
- [ ] Ghidra + pyghidra. **Blocked in the cloud container** (proxy denies GitHub release downloads). Options: run Ghidra headless in GitHub Actions, or on the owner's PC. Still to decide: whether an existing 6800/6801 module fits or a new HD6301 SLEIGH module is needed.
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
| Q1 | Is the 17140's CPU a 40-pin HD6301-type (like the Bluetop) or a 64-pin Toshiba 8X? | Owner opens the spare ECU and sends photos (P3) |
| Q2 | Does the ECU drive the cold start injector or any idle-air device at all? The hypothesis is no: they are driven by the time switch/STA and a wax valve | Port audit + wiring diagram (P5) |
| Q3 | What converts raw ignition-table values to degrees BTDC, and does VR offset matter? | IGT tracing + Zero timing meter (P2/P8) |
| Q4 | Can a 17030 or 17070 dump be found, to check Ross's 17030 numbers directly? | Community search (P3) |
| Q5 | Do NE/G inputs need a VR-style bipolar waveform from the bench simulator? | ECU input-circuit inspection (P8) |

## Conflicts log

| Date | Topic | Source A says | Source B says | Resolution |
|---|---|---|---|---|
| 2026-10-09 | Max ignition advance | Ross p16 graph: about 50° BTDC | Upstream #6: implausible, may include a VR offset | Open. Settle with a bench measurement (R-I06) |

## Exceptions to the Arduino-first rule

| Date | Item | Reason | Owner approved? |
|---|---|---|---|
| 2026-10-09 | Level shifters (74LVC245, 74AHCT125) | The Zero is not 5 V tolerant | Accepted in the plan |
| 2026-10-09 | Bus-speed CPLD + SRAM (in-car daughterboard, deferred) | Firmware cannot answer a 1 MHz bus in hundreds of ns | Accepted in the plan; nothing ordered yet |
