# Project status

The Lead agent updates this file at the end of every session. The plan is in [`RE_PLAN.md`](RE_PLAN.md).

**Last updated:** 2026-10-15 (Verifier fixes to the Ross Tier-B pass):
- **Every Ross claim tested on the MR2 ROM now has a 17140 status** (43 claims): 30 CONFIRMED, 8 DIFFERS-BY-ECU, 4 PARTIAL, 1 CONTRADICTED (rpm axis: R-M02). Summary under "P4 tasks"; evidence in [`ross/claims.md`](ross/claims.md); tests in `tests/test_ross17140.py`.
- **New 17140 facts:** P16 is the IDL contact; the closed-throttle state selects an idle ignition table identical to Ross's (68/98/162 at 1200/1600/2000 rpm) and arms the decel fuel cut. The T-terminal fixed spark sum belongs to that closed-throttle state, so the 10° anchor applies after all: a map cell is about its own advance, v × 15/64° BTDC (LIKELY). The ADC is ratiometric, and the evidence now favours Load ≈ 6.14 × kPa + 123 (LIKELY). P37 is the A/C switch (LIKELY, Toyota code 51). The anchor and the kPa scale are logged as conflict updates.
- **Verifier review of the Tier-B pass (independent agent, 2026-10-14): PASS WITH ISSUES**, no blockers. Fixes applied (P4 tasks). **Re-check of the fixes (a second independent agent, 2026-10-15): PASS WITH ISSUES**, no blockers: every finding confirmed fixed from ROM bytes and simulator runs; the p37 default change alters no documented result; `expected.h` unchanged; the `cboard` speed-up gives identical edges, RAM and cycle counts (old and new trees hashed, including tied and past-time events). Its follow-ups are applied: the P31 delay is 20–21 s (21 one-second ticks), not a fixed 20.5 s; the PORT3 table row and the `maps.md` scale note brought up to date; the `loopback_ref` p37 comment clarified.
- **Gate blockers:** R-M09 (Tier B, needs a 17070 dump), the verification report, the re-check of the Verifier fixes, and the gate sign-off.

Earlier, 2026-10-13:
- **P3 is done and signed off**: the 17140 ROM is dumped (4 KB, SHA-256 `0cfc1fdd…6f271f6e`).
- **P4 steps 1–3 first pass** are done: labelled source, channel map, ignition and fuel maps, simulator units.
- **Code sweep:** there is no hidden code, but the 17140 has a **serial diagnostic link** ([`mr2/serial_link.md`](mr2/serial_link.md)). It is a read-only live-data port that can answer Q10 and the kPa-scale doubt in the car.
- **Hardware (owner decision, 2026-10-14):** the Pico 2 W is the only project board, including the in-car modified-ROM board (P7). **P7 replaces the CPU** (owner decision): an RP2350 emulates the D151801 running the 17140 program in single-chip mode, because external-memory mode takes 18 of the pins the ECU uses (handbook §2.1) [`mr2/cpu_replacement.md`](mr2/cpu_replacement.md). Factory-chip fallback on the same board: owner idea, to revisit.
- **Next:**
  - owner: trace chip pins 11/12 (Q11) and the PORT4 jumpers (Q12), both unpowered;
  - agents: Verifier review of P4 steps 1–3, then the Ross Tier-B pass.

Earlier:
- **P2 is complete and signed off** (independent Verifier PASS, 2026-10-10).
  - Next is **P3, dumping the 17140 ROM**. It needs the owner to order [`../hardware/BOM.md`](../hardware/BOM.md) section A.
  - Owner checks outstanding: load `analysis/bluetop/bluetop.xdf` in TunerPro, continuity Test B, and Q10 (a powered check).
  - Whole-ROM simulation and warm-up results (PR #4).
  - All Tier-A claims have Bluetop evidence; every table is defined.
  - TunerPro XDF and checksum helper.
  - **Goal-1 note:** the Bluetop drives an idle-up output (P1-5, like the 1988 RM's V-ISC) for about 10 s after start, and at idle while the learned trim `word_42` is low; no direct coolant warm-up schedule for idle air.

Earlier on 2026-10-09:
- **Continuity Test A (jumpers) is done.** The links come in pairs, setting two **Port 3 option bits**: **P32 = 0** (J4) and **P34 = node N** (J8). These are the likely secret-map select bits.
- The case floats. IC7 pin 1 is confirmed. Mode 7 is LIKELY.
- P0 is signed off. P1's figures and data are done.
- **P1 is complete,** including the Ross logic diagrams.
- Next: P2, the Bluetop analysis with the emulator's peripheral models.
- Test B (VISC/FPU/OX/STH) is deferred by the owner. Q10 is a powered check that needs owner approval.

Earlier: the 1988 repair manual is recorded ([`hardware/repair_manual_aw11_1988.md`](hardware/repair_manual_aw11_1988.md); the PDF is not committed). Its US ECU drives the idle-up VSV from `V-ISC` (cranking + 10 s), so Q2 is partly reopened for the 17140; continuity Test B now also covers `FPU`. Earlier today: the 1984 EWD, the second photo set and the continuity-test guide. P0 next: cross-reference/call-graph generator, then the emulator.

## Phase checklist

| Phase | Description | State | Gate signed off by Verifier |
|---|---|---|---|
| P0 | Foundations: tooling, asl round-trip, xref, emulator | ✅ done | ☑ 2026-10-09 (independent Verifier agents: xref and emulator, both after fixes) |
| P1 | Ross claim register, figures, digitised data, diagrams | ✅ done | — |
| P2 | Bluetop analysis + Tier-A verification | ✅ done | ☑ 2026-10-10 (independent Verifier agents: simulation, then P2 gate; PASS after fixes) |
| P3 | Dump the MR2 89661-17140 ROM (RP2350 reader) | ✅ done 2026-10-13 | ☑ 2026-10-13 (independent Verifier agent: PASS WITH ISSUES; minor follow-ups listed under P3) |
| P4 | MR2 analysis + Tier-B verification → **Ross verified** | ☐ | ☐ |
| P5 | Warm-up / cold start (goal 1), blocked until the P4 gate | ☐ blocked | ☐ |
| P6 | Secret maps (goal 2) | ☐ | ☐ |
| P7 | Modified ROM + TunerStudio (goal 3) | ☐ | ☐ |
| P8 | Measurement + logging (RP2350) | ☐ | — |

### P0 tasks
- [x] Archive the missing upstream comments (#4 and #1, all read through the API on 2026-10-09). See [`upstream_issues.md`](upstream_issues.md).
- [x] Set up the Python project (`uv`, `pytest`, `ruff`) and GitHub Actions CI (`.github/workflows/ci.yml`).
- [x] Build `asl` 1.42 bld306 from source, plus `dasm` from the vendored copy: [`../tools/setup_assemblers.sh`](../tools/setup_assemblers.sh).
- [x] HD6301 opcode table and decoder: all 230 opcodes verified against `asl`.
- [x] `cap.asm` → label/comment/code-data importer. It rebuilds every address by walking the listing alongside `cap.bin`: 1,980 instructions, 331 data lines, 339 ROM labels and 141 RAM labels, with every mnemonic matching the ROM.
- [x] **Gate: [`analysis/bluetop/cap.s`](../analysis/bluetop/cap.s) reassembles byte-identical to `cap.bin` with `asl`, and the `dasm` cross-check agrees** (`uv run pytest`, 2026-10-09). The ROM's SHA-256 (`62b2a3f2…7f2`) is pinned in the tests.
- [x] Cross-reference and call-graph generator ([`../analysis/pcmre/xref.py`](../analysis/pcmre/xref.py) → [`../analysis/bluetop/xref.md`](../analysis/bluetop/xref.md)). It covers 68 routines and 1,989 instructions, with readers/writers of every RAM variable and Mermaid call graphs per vector. It follows Denso's indexed calls, jump tables and inline-parameter returns, and agrees with all 514 of IDA's XREF comments (`tests/test_xref.py`). It also found one IDA error: `$F4C9` is inline data, not code. **Verifier (independent agent, 2026-10-09): PASS WITH ISSUES.** It hand-traced 10 X-resolved calls, swept 28 variables by name and checked the stack model, and all of these were correct. Its two should-fix items are now fixed: 16-bit accesses are credited to both bytes, and loop sites are counted and disclosed. Five latent nits were fixed as well.
- [~] ~~Ghidra + pyghidra~~ **Made optional (owner decision, 2026-10-09).** There is no HD6301 module, and a decompiler adds little on hand-written 8-bit code. It is not a dependency or a gate. A later optional task may write a setup guide so the owner can browse the ROMs in Ghidra on their own PC.
- [x] Python HD6301 CPU core ([`../analysis/emu/cpu.py`](../analysis/emu/cpu.py)), written from the Hitachi handbook tables.
  - It matches MAME's hd6301 handlers on 16,384 random single-instruction cases (64 per opcode): registers, flags, memory writes and cycles.
  - Every `suite6303` instruction steps with the right length.
  - The Bluetop ROM runs from reset into `Main_Loop`.
  - The reference is built by [`../tools/setup_mame_ref.sh`](../tools/setup_mame_ref.sh), with MAME pinned at `mame0275` and SHA-256-checked; no MAME code is committed.
  - **Verifier (independent agent): PASS WITH ISSUES.** It found 0 mismatches over 256,000 random and 1.08 million targeted cases. All 4 should-fix items are fixed, with regression tests: write order is now compared, SLP wakes on a masked IRQ, waking from WAI costs 4 cycles not 12, and the DAA V-flag conflict is logged. The Verifier re-checked the fixes: **signed off**.
- [x] P0 gate signed off by the Verifier (2026-10-09). The emulator re-check passed after the fixes.
### P2 tasks (Bluetop analysis)
- [x] Emulator routine-call harness ([`../analysis/emu/harness.py`](../analysis/emu/harness.py)).
- [x] Table lookups modelled and proven equal to the emulator:
  - the 1D helper (six entry points);
  - the 3D ignition map at `$FF40`: 6 load rows × 14 rpm columns at 800–4800 every 400, then 5600, 6400, 7200 rpm.
  - [EMU:tests/test_tables.py]
- [x] `analysis/defs/bluetop.yaml` with its generator:
  - 13 maps, including coolant linearisation, THA correction, injector dead time and decel-cut rpm;
  - output in [`../analysis/bluetop/maps.md`](../analysis/bluetop/maps.md).
- [x] Architecture write-up ([`bluetop/architecture.md`](bluetop/architecture.md)): reset, the event-driven main loop, ISR roles, ADC sequencer, RAM map.
- [x] Fuel and ignition chains ([`bluetop/fuel_chain.md`](bluetop/fuel_chain.md)). `Calc72` is proven in the emulator [EMU:tests/test_fuel_chain.py]. The ratio-vs-coolant shape (≈2.5× at 0 °C) comes from a routine-level experiment.
- [x] **Peripheral model + whole-ROM simulation** ([`bluetop/simulation.md`](bluetop/simulation.md)): timers 1 and 2, the serial ADC, ports and IS3, plus NE/G, airflow, IGF and sensor stimulus. `cap.bin` runs unmodified from reset at about real time. Checked against the ROM's own arithmetic [EMU:tests/test_sim.py]:
  - rpm variables;
  - injector pulses in both injection modes (cold simultaneous, warm grouped);
  - 3D-map advance and the µs conversion, to 0.15°;
  - T terminal → 10.3° BTDC;
  - rev-limit and missing-IGF fuel cuts.
  - **Verifier (independent agent, 2026-10-09): PASS WITH ISSUES.** It agreed with the handbook semantics, the timer-2 mirror, the IDL polarity and the cranking-spark inference. Fixed: pass counts (6 above the limit, 4 without IGF), no rev-limit hysteresis, the $FA19 tip-in reading, the circular NE-reference confidence, the cranking-spark model limited to cranking, the formula clamps, and the missing tests.
- [x] Warm-up experiments ([`bluetop/warmup_sim.md`](bluetop/warmup_sim.md), CSVs in `analysis/bluetop/sim/`). Steady warm-up fuel is 2.0× warm at −10 °C and 1.7× at 0 °C, gone by 60 °C. The after-start boost (`byte_84`) is +1.1× at 0 °C and bleeds off over about 550 revolutions. Extra cold advance is about +10° at idle. The injection mode switches simultaneous → grouped at 22–27 °C.
- [x] Tier-A claim statuses: all 24 have Bluetop evidence.
  - Latest: R-F10 DIFFERS (only PWRr staircases), R-F12/R-I15 no alternative map on the Bluetop (17140 question), R-I08 PARTIAL, R-I12 CONFIRMED, R-I14 DIFFERS.
  - **R-I08 / P1-5:** the Bluetop drives an idle-up output for about 10 s after start (= 1988 RM V-ISC timing), plus at idle while the learned `word_42` is below $42; no direct coolant schedule.
  - **R-I14:** the Bluetop keeps learned O2 trims and fault codes in standby RAM $40–$4A.
  - CONFIRMED (Bluetop): R-F17, R-F23, R-F25, R-I05.
  - PARTIAL: R-F11, R-I01.
  - DIFFERS-BY-ECU: R-F21, R-F22 (the Bluetop uses grouped injection), R-I02 (14×6 map).
  - NOT-APPLICABLE: R-F01 (the Bluetop has no MAP channel).
  - The rest need the fuel-chain trace.
- **P2 gate Verifier (independent agent, 2026-10-10): PASS WITH ISSUES.**
  - Confirmed against the ROM: the table maths, the $FEE9/$FF12 correction, the Port 1/3 audit, the standby RAM and the checksum.
  - Fixed: the second P1-5 path (idle while learned `word_42` < $42) and the toned-down coolant wording; `se056_max` is 11 entries (FullRPM is capped at $09FF); `thw_FF0A` named as the warm-up advance; `pwr_o2_trim` marked signed; the R-I14 and R-F10 wording; extra overheat and P1-5 tests; overlap warnings in the table titles.
  - **Re-check (independent agent, 2026-10-10): PASS.** All items are fixed; it confirmed the second P1-5 path, the $F84F/$F9BF/$F461 citations and the XDF/CSV outputs. Its wording nits (Load ≥ $190 plus the T-terminal condition in R-I14, the extra test citation for P1-5) are applied.
- [x] Every table the code reads is now defined: 19 maps in the YAML.
  - New: `$FE9C` max airflow delay vs rpm, `$FEA7` acceleration enrichment, `$FF11` over-temperature retard, and the PWRr staircases `$FF94`/`$FF9C`.
  - **Correction:** the injector dead time is `$FEE9` (8·v + 464 µs); `$FF12` is the dwell term.
  - `Load` scaling documented (air-temperature-corrected airflow delay, µs).
  - Advance degrees: see Q3.
- [x] TunerPro RT XDF generated from the YAML ([`../analysis/bluetop/bluetop.xdf`](../analysis/bluetop/bluetop.xdf)) with display equations for advance, dead time, dwell and max airflow. **Not yet opened in TunerPro: owner check.**
  - Checksum helper [`../analysis/pcmre/checksum.py`](../analysis/pcmre/checksum.py): the word sum must be $AA55, balanced at $FFEE [ROM:$FE50].
  - A TunerStudio INI needs a comms protocol, so it moves to P7.
- [x] **P4 prep: day-one toolkit** `pcmre.ingest`. It handles any ROM size, traces and ports the Bluetop maps (all 19 CONFIRMED on 2860), lists candidate tables, searches for Ross's tables, and finds the ADC array, mixture-screw candidates and rpm constants [EMU:tests/test_ingest.py, including a synthetic 8 KB ROM with Ross's table planted]. `crossver` now works with any ROM origin.
- [x] **P4 prep: MAP-sensor simulator.** `EcuProfile` sets the ADC channel map, the coolant table and whether the SE056 airflow edge exists. `mr2_dtype()` is for the 17140; the PIM sensor model comes from the EWD curve. The Bluetop wiring is unchanged [EMU:tests/test_profiles.py].
- [x] Readable ignition table ([`bluetop/ignition_table.md`](bluetop/ignition_table.md), `pcmre.readable`): the base map in degrees BTDC with load as a percentage of the map's top row, the full-load line per rpm, the T-VIS step and the 256 µs lead shown separately [EMU:test_readable].
- [x] Cross-version analysis 0642 against 2860 ([`bluetop/versions.md`](bluetop/versions.md), `pcmre.crossver`). The same program, revised: all 19 maps ported automatically and **identical**; a load-sensing chain consistent with the same sensor type (LIKELY). 9 behaviour changes:
  - port direction registers (P1-4, P3-0 to P3-3 become outputs);
  - stall-flag logic;
  - the A/C idle advance kept only above 218 °F, i.e. removed in normal running;
  - fault-flag `$10` rpm path 1000 → 1500 rpm;
  - P1-5 high in the T-terminal self-test paths;
  - …

  8 RAM variables moved. Generated 2860 defs, CSVs and XDF [EMU:test_crossver]. **Verifier (independent agent, 2026-10-10): FAIL.** It found the missed direction-register and STA-clear changes, a false "counter reload" change, and a misread A/C change. All are fixed: the tool now checks every differing 16-bit operand and 2860-only data, and hand-written byte tests were added. **Re-check: PASS WITH ISSUES**, all fixed: helper-pointer, code-pointer-table and data-block rules tightened, wording corrected.
- [x] Rev limiter mapped ([`bluetop/rev_limiter.md`](bluetop/rev_limiter.md)): a fuel-only cut after 6 passes above 7400 rpm, with no hysteresis. Constants: the limit word `$F434` and the reload byte `$F42C` (`$7E` is the maximum; `$7F` cuts fuel at every rpm) [EMU:test_rev_limiter].
- [x] Spark-cut limiter prototype ([`../analysis/patches/bluetop_sparkcut.asm`](../analysis/patches/bluetop_sparkcut.asm), `pcmre.patch`): no dwell while limiting, fuel kept, IGF safety cut held off only while limiting, 38 bytes of code at `$E000` [EMU:test_sparkcut]. **Open:** whether hardware outside the CPU fires the coil when dwell is withheld at speed (bench, P8). Not yet reviewed by a Verifier.
- [x] Overrun fuel and retard prototype ([`bluetop/overrun.md`](bluetop/overrun.md), [`../analysis/patches/bluetop_overrun.asm`](../analysis/patches/bluetop_overrun.asm)): throttle closed above `OB_RPM` (4000 rpm) keeps fuel (no decel cut) and fires at `OB_ADV` (12.5° warm, before the 256 µs lead); stock everywhere else; 39 bytes at `$E000` [EMU:test_overrun]. **Open:** real overrun mixture and response (car), Q3 lead. Not yet reviewed by a Verifier.

### P1 tasks
- [x] Claim register skeleton: [`ross/claims.md`](ross/claims.md).
- [x] Extract the 16 figures (`pdfimages`, flipped upright) and confirm the page mapping ([`ross/figures/`](ross/figures/README.md)).
- [x] Digitise the graphs to CSV ([`../analysis/ross/digitise.py`](../analysis/ross/digitise.py)) and transcribe the 17×8 ignition table. The transcription matches Ross's own p13 chart to within 1 count.
- [x] Mermaid diagrams of Ross's fuel chain, ignition chain, injection modes, T-VIS, idle stability, mixture screw and cold start ([`ross/diagrams.md`](ross/diagrams.md)). All render with mermaid-cli 11.4.

### P3 tasks (ROM dump, RP2350 reader)
- [x] Mode for the dump: **mode 0** (P22/P21/P20 = L/L/L, pins 10/9/8), "Multiplexed Test": internal ROM on, reset vector external for 3–4 cycles after RES rises [handbook Table 2-1-1].
- [x] Clock: E = 0.1–1.0 MHz, so EXTAL 0.4–4 MHz; not static. The reader runs EXTAL at 0.5 MHz (E = 125 kHz); it started at 1 MHz, but `probe` showed core 1 too slow for back-to-back vector cycles there [handbook p.128, p.188] [BENCH:probe 2026-10-13].
- [x] ROM size method: the reader's `size` run sends `$E000`–`$FFFF`; a 4 KB block counts as ROM only if three runs agree and it does not echo the address bus. 4 KB at `$F000` is expected, as on the D151801 Bluetops.
- [x] Self-test plan: multimeter checklist, `rigcheck`, `clock`, `listen`, `probe`, then `dump` ([`hardware/rp2350_reader_guide.md`](hardware/rp2350_reader_guide.md)).
- [x] Owner orders [`../hardware/BOM.md`](../hardware/BOM.md) section A. (A first "Pico WH" turned out to be the RP2040 board: not 5 V tolerant, not used; replaced by a Pico 2 W with headers.)
- [x] 6301 dump program ([`../hardware/rp2350-reader/6301/`](../hardware/rp2350-reader/6301/)): in the emulator against `cap.bin` it sends the mode byte then the ROM exactly, with no stack use, no contention and no TDRE violation [EMU:tests/test_romdump.py].
- [x] RP2350 reader firmware ([`../hardware/rp2350-reader/firmware/`](../hardware/rp2350-reader/firmware/)): builds warning-free for the BB48R and the Pico 2 W(H) (pico-sdk 2.1.1); CI uploads both UF2s. Its decode rule matches the Python model [EMU:tests/test_reader_decode_c.py]. Not yet run on hardware.
- [x] Host capture tool `analysis/pcmre/romcapture.py` [EMU:tests/test_romcapture.py].
- **Firmware Verifier (independent agent, 2026-10-10): FAIL, then PASS WITH ISSUES on re-review.** It confirmed the blocker fixed and found no remaining contention path while the clock is in spec. Its four minor follow-ups are fixed: the early-release path pushes a marker, so lateness is always detected (the SCI receiver moved to PIO1 to make room); a missed drive is detected after each put; `listen` reports PASS/UNCLEAR/STOP; and a new `res` command lets the owner measure the RES level. **Final check of the follow-ups: PASS** (same independent agent, 2026-10-10). The firmware is cleared for the guided hardware bring-up; the P3 gate itself still needs the dump and its Verifier sign-off.
  - **Blocker:** a late core-1 answer could be driven past E falling, or into a later cycle. Fixed in the PIO and core 1:
    - the answer must be queued before E rises, or the cycle is listen-only;
    - stale answers are discarded at the start of each cycle;
    - the bus is released early if E falls during the snoop delay;
    - FIFO words are tagged, so core 1 cannot lose its place;
    - core 1 stops driving for the rest of a run once it is late;
    - the served pages are in RAM.
  - **Major:** `$FFFF` was served after `$FFFE` without a window bound. Now bounded (tested). `listen` now checks that the vector reads float (external) and says STOP otherwise. The guide no longer invites changing the window.
  - **Minor:**
    - `romcapture` refuses non-`$F000` images;
    - `$FFFF` is excluded from the snoop comparison (6301 dummy cycles);
    - the guide stresses "chip out" for `rigcheck`, adds a RES-level and rail check, and makes pull-ups for the unused port pins optional;
    - "43-byte" program.
  - **Accepted:** the release lags E falling by about 3 PIO clocks (~20 ns at 2 mA drive). Input-sync bypass is not used, because the RP2350 register's mapping under a GPIO base of 16 is not documented. The emulator does not model the 6301's dummy `$FFFF` cycles. No test covers PIO or core-1 timing; the hardware `listen`/`probe` steps cover it.
- [x] Reader guide with wiring pictures, multimeter checklist, bring-up and troubleshooting ([`hardware/rp2350_reader_guide.md`](hardware/rp2350_reader_guide.md)); its tables are generated from `pins.h` and checked by `tests/test_wiring.py`.
- [ ] Carrier PCB (KiCad, factory-assembled): deferred; the breadboard rig stays as the P4 real-CPU harness.
- [x] Chip removed from the spare ECU, socket fitted (owner, 2026-10-12).
- [x] Reader firmware flashed to the Pico 2 W; banner correct on macOS [BENCH:owner report 2026-10-13].
- [x] Breadboard wired (Pico 2 W layout), multimeter checklist all six checks OK, `rigcheck` PASS [BENCH:owner report 2026-10-13]. The first `rigcheck` correctly refused to run with the 5 V jumper only half removed.
- [x] Chip fitted (rail strips found split mid-board and bridged); `clock` PASS: E = 249,981 Hz, 49 % duty [BENCH:owner report 2026-10-13].
- [x] `listen` PASS: cycles 0-1 read the vector from the floating bus ($FE, $FF), cycle 4 reads $FFFF internally ($BE), so the vector is external only in the window [BENCH:owner listen.txt 2026-10-13]. The firmware check that first reported STOP had matched a later stack pull (RTS from $FFFE/$FFFF); it now only looks at the first cycles.
- [x] **Fault found and cleared (owner, 2026-10-13):** a sliver of copper or solder left from the desoldering bridged chip pins 28/29. Found by beeping GP10–GP11 with the chip in and out. Re-check with `listen` pending. Original symptom: A8 and A9 read as wired-AND whenever they differ ($FE→$FC at cycle 2, $01→$00 at cycles 40-41, $F2→$F0 after the RTS). Every other bit agrees with the instruction flow. Likely chip pins 28/29 (rows d32/d33) bent together or sharing a hole, since the unpowered checks passed before the chip went in.
- [x] Second `listen` after the fix: all high address bytes correct; reset vector **`$F2BE`** confirmed. Cycle 0 logged `$FFFF` for the `$FFFE` vector fetch (echo `$FE`), so AD0 was still settling at the AS edge on the first cycle after reset [BENCH:owner listen.txt 2026-10-13].
- [x] Firmware: the address is now sampled 16 PIO clocks (~107 ns) after AS falls. **Verifier (independent agent, 2026-10-13): PASS WITH ISSUES**:
  - no new contention path, and write data cannot be caught;
  - the first proposal of 32 clocks risked core 1's answer deadline, so it was cut to 16 as the Verifier advised;
  - the AS-to-E time is an estimate until measured; check `late cycles` = 0 in `probe`;
  - confirm the first-cycle settling across several `listen` runs.
- [x] `res`: RES (pin 6) reads ≥ 4.5 V while released [BENCH:owner report 2026-10-13].
- [x] New firmware (address sampled ~107 ns after AS): two `listen` runs, both PASS and identical cycle for cycle; cycle 0 reads `$FFFE`; all 64 addresses agree with the instruction flow [BENCH:owner logs 2026-10-13].
- [x] At E = 125 kHz: `clock` PASS (124,993 Hz, 50 %), `listen` PASS, **`probe` PASS** (vector served, `$C0C0` fetched, late cycles 0) [BENCH:owner report 2026-10-13]. At E = 250 kHz the first `probe` failed safe: core 1 was late on the back-to-back `$FFFF` cycle, so it stopped driving; no contention.
- [x] **17140 ROM dumped** (2026-10-13): three runs identical (4096 ROM bytes, 0 differ), mode bits 000 in every run, snoop channel agrees on 4095/4095 bytes, word sum `$AA55`, vectors RES/SWI/NMI/IRQ1/TOF/SCI `$F2BE`, OCF `$FE36`, ICF `$FEB4` [BENCH:analysis/captures/89661-17140_dump_2026-10-13.txt]. SHA-256 `0cfc1fdd36fc4514cf0693e18ef7e4b47594a4b78f72beadd30766a36f271f6e`. Saved as `AW11 MR2 PCM/89661-17140.bin`. The first dump attempt failed only because the run comparison included the Port 2 pin byte (P22 read 0 in one run and 1 in two); fixed in firmware v4.
- [x] `size`: `$E000`–`$EFFF` echoes the address on all 4096 bytes (floating bus, not ROM); `$F000`–`$FFFF` is identical across runs (internal ROM). **The 17140 ROM is 4 KB** [BENCH:owner report 2026-10-13].
- [x] **Dump Verifier (independent agent, 2026-10-13): PASS WITH ISSUES.**
  - **Image:** the .bin equals the captured HEX, re-parsed with two parsers; SHA-256 matches.
  - **Self-check:** the ROM's own reset code verifies the word sum against `$AA55` [ROM:$F2FE], and the image passes it.
  - **Code:** the reset handler (mode 7 or mode 2 check, then `LDS #$00FF` and register setup) and both timer handlers (ending in RTI) decode cleanly.
  - **Data:** no stuck bits, no floating-bus patterns.
  - **Follow-ups:**
    - `size` run still to do;
    - print the firmware version in the banner, and record it with each capture;
    - make snoop agreement a condition of `DONE OK`;
    - `$FFEE` is the balance word, not a vector (fixed in ingest and romcapture).

## Open questions

| # | Question | Who / how |
|---|---|---|
| Q1 | ~~Is the 17140's CPU a 40-pin HD6301-type (like the Bluetop) or a 64-pin Toshiba 8X?~~ **Answered 2026-10-09:** a 40-pin **D151801-7110** with silkscreen "6356/6801" and a 4.00 MHz crystal. It is the same family as the Bluetop, so P3 follows the HD6301 path. See [`hardware/aw11_ecu.md`](hardware/aw11_ecu.md) | Done (photos) |
| Q2 | Does the ECU drive the cold start injector or any idle-air device? **CSI: no (LIKELY for the 17140).** Both factory manuals wire it starter → CSI → time switch, and the board label is `STH` = S/TH (T-VIS), not STJ. **Idle air: open.** The IACV is a mechanical wax valve in both manuals. The idle-up VSV is load-switched and only *sensed* (I/UP) in the 1984 EWD, but the 1988 US ECU **drives** it from `V-ISC` during cranking and for 10 s after start, and the 17140 board has a `VISC` pad. **Bluetop evidence (P2) [EMU:sim]:** the Bluetop ROM drives P1-5 from key-on until about 10 s after start (same at 0 °C and 80 °C in simulation), matching the 1988 RM's V-ISC timing, and also at idle while its learned trim `word_42` is below $42. So this ECU family drives an idle-up output, but not on a coolant warm-up schedule. See [`hardware/ewd_aw11_1984.md`](hardware/ewd_aw11_1984.md) and [`hardware/repair_manual_aw11_1988.md`](hardware/repair_manual_aw11_1988.md) | Continuity **Test B** (is there a driver transistor behind `VISC`?), then the P4 port audit ([`hardware/aw11_ecu.md`](hardware/aw11_ecu.md)). **17140 ROM (Ross pass, 2026-10-14):** no output follows coolant temperature. **P31** is on while P17 is low and for 20–21 s after it rises, and during a decel cut above the return rpm [ROM:$F3A2-$F3CC]. **PORT2 bit 2** goes low after a hot crank (coolant and intake air both hot) from about 0.18 s to about 92 s [ROM:$F478-$F49F, $F654-$F672] [EMU:tests/test_ross17140.py::test_hot_crank_p31_timer_and_port2_bit2, ::test_warmer_crank_keeps_port2_bit2_high]. Best fits: P31 = `VISC` idle-up, PORT2 bit 2 = `FPU` (GUESS). Test B decides |
| Q3 | What converts raw ignition-table values to degrees BTDC, and does VR offset matter? **Bluetop answered in simulation [EMU:sim]:** BTDC = (map + ThW_tADV + idle term) × 90/256 − 10.74° plus a fixed 256 µs lead (T terminal → 10.3°, consistent with the factory 10° but not independent of it). For the Bluetop that makes a map cell v ≈ v × 90/256 − 0.9°. Open: whether the 256 µs lead offsets a real delay, and the 17140's conversion | Bench IGT vs crank capture (P8); 17140 ROM (P4). **17140 (Ross pass, LIKELY):** the fixed sum 170 is the closed-throttle T-terminal check, so advance ≈ 10° + (sum − 170) × 15/128°; a warm untrimmed map cell v ≈ v × 15/64° BTDC, and the warm idle with T open is 16.0° (conflicts log) |
| Q4 | Can a 17030 or 17070 dump be found, to check Ross's 17030 numbers directly? No public 17030/17070/17140 dump found (web search 2026-10-10) | Open |
| Q5 | Do NE/G inputs need a VR-style bipolar waveform from the bench simulator? | ECU input-circuit inspection (P8). IC3 (µPC177C comparator) is the likely conditioner |
| Q6 | ~~Do the factory jumpers set a logic level or the mode pins?~~ **Answered 2026-10-09 [BENCH] for P32/P34:**<br>• **The jumpers come in pairs** per option pin: one to ground, one to node N.<br>• **P32 (pin 35):** J4 to ground (fitted), J9 to N.<br>• **P34 (pin 33):** J8 to N (fitted), J3 to ground.<br>• **Factory setting:** P32 = 0, P34 = N (LIKELY 1).<br>• These are Port 3 option bits, the prime candidates for the secret-map select (R-F12, R-I15). They are not the mode pins.<br>See [`hardware/aw11_ecu.md`](hardware/aw11_ecu.md) | **P4 (2026-10-13):** the ROM reads **P34** at `$FDCF` (ignition map `$F1EF` if 1, `$F25D` if 0) and `$FAC2` (fuel: x1.00 if 1, secret rpm correction `$F117` if 0). **P32 is not read** by any instruction found (LIKELY). PORT4 bits 2–3 select an advance trim; J6, J7, J1 and J2 are candidates for those, not tested yet |
| Q7 | What does the 17140 ROM do with the `OX`/`VF` pins on a UK car with no O2 sensor? | ROM analysis (P4) |
| Q8 | Does the 17140's `OX` pin carry the mixture-screw CO resistor? The 1984 VAF pin is missing from the board (Ross R-M08) | Continuity **Test B**, then the ROM ADC channel map (P4) |
| Q9 | Is there a **1986–89 UK mk1b wiring diagram** to confirm the 17140 pinout (VISC, OX, W, ACT, FPU ...)? The 1988 repair manual is mk1b-era but **US spec** (air flow meter, O2 sensor), so it defines `V-ISC`, `FPU` and `W` but cannot say what the UK car uses | Owner: a UK/European 1986–89 EWD or repair manual supplement |
| Q11 | Where do chip **pins 11 (P23, SCI RX) and 12 (P24, SCI TX)** go on the 17140 board? This decides how the serial link ([`mr2/serial_link.md`](mr2/serial_link.md)) is reached in the car. With the link off, both are Port 2 outputs: **pin 12 is the fault-code flasher** [ROM:$F769-$F7E9], almost certainly the `W`/`DG` lamp line that also reaches the engine-bay check connector (LIKELY); **pin 11** is another fault-dependent output [ROM:$FC1C-$FC28], perhaps `VF` (GUESS). If so, the check connector can carry the ECU's replies (through the lamp driver) but probably cannot send requests | Owner: unpowered continuity from socket pins 11/12 to the nearest resistor or transistor, and on to the `W`, `VF` and `T` connector pins |
| Q12 | Which jumpers or pins drive **PORT4 bits 2–3** (P42/P43, chip pins 27 and 26)? They select the advance trim +9/−17/−9/0 counts [ROM:$FDE4-$FDFD]. Candidates: J1/J2/J6/J7 | Owner: unpowered continuity |
| Q10 | What is jumper **node N**? About 750 Ω to ground, the same both ways, not connected to the main +5 V. Is it a logic-high source, such as a standby 5 V rail? This decides what P34 reads (0 or 1) with the factory J8 fitted, and so **which ignition map and fuel correction the car runs stock** (P4: `$F1EF` + x1.00 if P34 = 1; secret `$F25D` + `$F117` if 0) | **Powered** measurement of N and P20–P22 in the socketed ECU with the chip out (P3). Needs the owner's confirmation at the time (CLAUDE.md hardware safety). Alternative: read PORT3 over the serial link in the car (bit 4 = P34) |
| Q13 | What drives the ECU's **`FC`** pin (fuel pump control, circuit opening relay, EWD L-4)? No 17140 ROM output behaves like a fuel-pump control: P31 is an idle-up-like timer (Q2), P40/P41 follow rpm compares, PORT2 bits 2–4 are the hot-start output, a fault timer and the flasher [ROM:$F3A2-$F3CC, $FB98-$FBB6, $F478-$F49F, $FC1C-$FC28, $F7DF-$F7E9]. So `FC` may be driven from NE or STA by board hardware outside the CPU (GUESS). This decides whether the P7 board must drive it | Owner: unpowered continuity from `FC` back to its driver transistor and on to the CPU socket or the NE/STA circuitry (with Test B) |

### P4 tasks (MR2 17140 analysis)
- [x] Step 1, first pass: labelled source `analysis/mr2_17140/mr2_17140.asm` (generated from `symbols.yaml` by `pcmre.symlisting`; asl round trip IDENTICAL), xref and call graph, architecture map [`mr2/architecture.md`](mr2/architecture.md). Findings:
  - NE on input capture 2 (6 edges, G on PORT3 bit 5);
  - ignition on output compare 2;
  - a timed ADC on input capture 1 with channel select on PORT1 bits 2–4;
  - SCI used only for a RAM-peek link;
  - test-terminal-gated self-test.
  Most items LIKELY or GUESS; not yet reviewed by a Verifier.
- [x] Step 2, first pass ([`mr2/maps.md`](mr2/maps.md)); all LIKELY, not yet Verifier-reviewed:
  - **ADC channel map:** 0 zero, 1 MAP, 2 throttle, 3 mixture (VAF), 4 battery, 5 coolant, 6 intake air, 7 reference.
  - **Engine speed:** RpmWord `$77` = rpm × 0.32.
  - **Ignition base maps** `$F1EF` (13 rpm × 8 load) and `$F25D` (13 × 7), **selected by P34 (jumper J8)**.
  - **PORT4 bits 2–3 trim** the advance (table `$F01A`).
  - **Fuel chain:**
    - density maps `$F0FF`/`$F10B` (split at 3200 rpm) and high-MAP bump `$F196`/`$F1A2`;
    - speed maps `$F1AE`/`$F1BA`;
    - staircases `$F1C5`/`$F1D7`;
    - THA correction `$F083`;
    - the secret rpm correction `$F117`, used only when P34 = 0.
  - Units (kPa, degrees, µs) still to calibrate.
  - **Verifier (independent agent, 2026-10-13): PASS WITH ISSUES.**
    - **Confirmed:** the ADC dispatch (no off-by-one), the ignition table format, P34 selection and trim, "larger = more advance", the staircase walk, and the factor scaling.
    - **Fixed:**
      - `$F1BA` has 11 sites (ends at `$F1C7`);
      - `$F196`/`$F1A2` is a fine-resolution extension, not a high-MAP bump (R-F05 link dropped);
      - map A counts twice in the spark sum;
      - the other ignition paths are now documented (`$F0FA` table, fixed `$00AA`, +13);
      - the `FuelPulse` terms are listed;
      - the `#$4D` fault value is distinguished from the `$4D` RAM variable;
      - code at `$F01E`–`$F03A` is noted;
      - "secret" map B is conditional on Q10.
- [x] Step 3, first pass: the 17140 runs in the whole-ROM simulator. Its own I/O model is [`../analysis/emu/engine17140.py`](../analysis/emu/engine17140.py): NE on IC2 at 30°/edge, G on P3-5, a timed ADC on IC1, spark on P1-1, injector on Tout1. Units [EMU:tests/test_sim17140.py]:
  - **RpmWord = rpm × 0.32** CONFIRMED;
  - **15/64° per ignition-map count** CONFIRMED;
  - **injector pulse = InjPulse + dead time** in µs, CONFIRMED;
  - **Load ≈ 4.98 × kPa + 98.6** LIKELY, resting on the PIM curve and ADC ch7 = 5 V (GUESS);
  - **absolute advance: LIKELY v × 15/64° BTDC** for a warm untrimmed map cell, anchored at the T-terminal check (conflicts log, 2026-10-14).

  Readable maps: [`mr2/ignition_maps.md`](mr2/ignition_maps.md).
- [x] Code and table sweep, first pass ([`mr2/architecture.md`](mr2/architecture.md) "Coverage and option behaviours"); not yet Verifier-reviewed:
  - **coverage:** every code byte is reached except the padding byte `$F9D2`, so there is no hidden code;
  - **table bytes the simulator never reads**, notably the high-load staircase `$F1DA` (see the kPa conflict below);
  - **option behaviours:** P34 map select, test-terminal fixed timing, PORT4 trims, the self-test gate, mode 2 accepted, P32 unused.
- [x] **Serial diagnostic link** ([`mr2/serial_link.md`](mr2/serial_link.md)) [ROM:$F33B, $F403, $F62E] [EMU:tests/test_peek17140.py]:
  - enabled only if P23 (pin 11, SCI RX) is low at reset;
  - 7812.5 baud;
  - one address byte in, the word at `$00`–`$FF` out, high byte first;
  - read-only;
  - switched off after about 1 s without a request;
  - about 130–200 words/s in the simulator, with no effect on spark or injection.
  
  Simulator host model: [`../analysis/emu/peek17140.py`](../analysis/emu/peek17140.py).
- [x] **17140 rev limiter** ([`mr2/rev_limiter.md`](mr2/rev_limiter.md)) [ROM:$FA03-$FA3E, $FFB7] [EMU:tests/test_rev_limiter17140.py]:
  - fuel only, after 3 calculations over the limit, no hysteresis;
  - **7600 rpm** (`$07B6` at `$FA1F`), or **7400 rpm** (`$07EB` at `$FA27`) after a fast climb through 6000 rpm;
  - two missing IGF echoes also stop injection;
  - `RpmWord` saturates at about 7325 rpm, so the limiter uses the crank period `$82`.
  
  Not yet Verifier-reviewed.
- **Verifier (independent agent, 2026-10-14) on P4 so far (architecture, maps, units, serial link, rev limiter, symbols, simulator): PASS WITH ISSUES**, no blockers.
  - **Confirmed against the ROM and in its own simulator runs:**
    - the serial link (X = 0 at both entries, P23 enable, E/128, keep-alive, pin 12 flasher);
    - the rev limiter (threshold rule, 3-pass counter, SchedInj skips, 7600/7400 rpm);
    - P34 map selection and both map tables byte for byte;
    - the staircase thresholds;
    - RpmWord/RpmIndex saturation;
    - coverage (independent byte check);
    - the advance arithmetic.
  - **Fixed:**
    - P30 polarity: the fixed spark sum, the self-test and the flasher pattern all act on P30 = 0, and the simulator now models T open as P3-0 high;
    - the fixed-sum path is a start/stall path, so the 10° anchor does not apply to the maps (readable maps are now relative; conflicts log);
    - the undocumented P30 spark-skip at `$FF7C` added to the option table;
    - the origin of DiagFlags bit 7 recorded;
    - `pcmre.symlisting` now warns about labels inside an instruction (`IgnFixedTest` moved to `$F7F2`, test added);
    - rpm figures marked as resting on E = 1 MHz and 30°/edge;
    - nits: StartCount, `$FA27`, the P23 description, the instruction count, P32 → LIKELY, overrun and keep-alive wording, the map footer, the 4A-GZE alternative, citation ranges, stronger missing-IGF and slow-climb tests.
  - **Re-check of the fixes (same independent agent, 2026-10-14): PASS.** Its cosmetic follow-ups are applied (citation `$FDC9-$FDD5`, evidence tag on the `ModeFlags` bit 7 statement, a car check of the P30 polarity).
- [x] **P7 early exploration: the C HD6301 core** (`hardware/ecu-emu/core/`, switch generated from the opcode table by `pcmre.gen_hd6301_c`). It matches the MAME-verified Python core on all 256 opcodes (random cases, interrupts included) and on 200 000 steps of the 17140 ROM [EMU:tests/test_hd6301_c.py]. On a PC it runs the ROM about 270× faster than the real chip. **On the owner's Pico 2 W: 4.6× the real chip at 150 MHz, 7.7× at 250 MHz** [BENCH: owner, bench v2, 2026-10-14]. **D151801 peripherals in C done** (`d151801.c`, `board.c`): identical to the Python simulator at 8 operating points, every spark, injector edge, ADC conversion and RAM byte [EMU:tests/test_d151801_c.py]. Loopback on the Pico (v1, owner 2026-10-14): RpmWord exact, spark within 0.13°, 72 % busy, lag ≤ 14 µs. **v2 on the Pico: all 6 phases PASS, bit-exact with the simulator** (every output edge, RAM, injector pulse) [BENCH: owner 2026-10-14]. A low-rpm lag spike (1.1 ms at 800 rpm, a crank-queue horizon bug) is fixed in v2.1.
- [ ] **Chip-in-isolation test (next P7 step):** [`hardware/chip_diff_test.md`](hardware/chip_diff_test.md). The real D151801 runs its own ROM in mode 7 on the reader breadboard while the Pico plays the engine with the loopback's model and schedule; its edge checksums must equal `expected.h`, which the emulator already matches. Owner decision 2026-10-14: this replaces the ECU bench as the emulator's validation; then the car on the in-car test rig (spare ECU, car's own ECU kept as the known-good spare). Firmware `hardware/ecu-emu/chipdiff/` (UF2 builds clean, CI artefact) and the PC tool `analysis/emu/chipdiff.py` (replays the logged inputs into the emulator, compares every output edge) are done; the pipeline passes with the emulator standing in for the chip, and catches a spark moved by one cycle [EMU:tests/test_chipdiff.py]. Not yet run on hardware. Next: the owner rewires the breadboard (unpowered) and runs it.
- [ ] **In-car test rig: parts list proposed** ([`../hardware/BOM.md`](../hardware/BOM.md) section C1; about £30). Awaiting owner approval to order. The final PCB outline waits for a photo of the clearance above the CPU socket.
- [x] **Ross Tier-B pass on the 17140** (2026-10-14; Verifier PASS WITH ISSUES, fixes applied, re-check pending). Every claim whose "Test on" includes `MR2 ROM` (43) has a 17140 status, evidence and a "P4 17140" note in [`ross/claims.md`](ross/claims.md). Simulator results are pinned in [`../tests/test_ross17140.py`](../tests/test_ross17140.py) (44 tests, about 3 s, on the C-backed simulator). The simulator has two inputs for them, `idl_closed` (P1-6, default throttle open) and `p37` (P3-7, default 0 = A/C off). `emu.loopback_ref` pins `p37=1`, the level `expected.h` and `engine.h` use, so the loopback reference is unchanged.

  | Status (17140) | Count | Claims |
  |---|---|---|
  | CONFIRMED | 30 | R-F01, F02, F04, F05, F06, F08, F11, F13, F14, F16, F17, F19, F21, F24, F25, F26; R-I01, I05, I07, I09, I10, I11, I12, I13, I14, I16; R-M01, M03, M04, M06 |
  | DIFFERS-BY-ECU | 8 | R-F03 (9 density sites, not 11), F07 (speed map −4.5..+4.1 %, zero at 3600), F09/F10 (staircase at 3500–6500 rpm), I02/I03 (13 × 8 map, 800–5600 rpm), I04, I15 (secret map 13 × 7) |
  | PARTIAL | 4 | R-F12 (stock P34 level: Q10), F15 (throttle fraction: VTA travel on the bench), I08 (which pins P31 and PORT2 bit 2 drive: Test B), M08 (pin: Test B; 17030 channel: dump) |
  | CONTRADICTED (rpm axis) | 1 | R-M02: same five MX2 bytes and the same 1000 rpm point, different rpm sites (78 at 3500 rpm, not 64) |

  - **Exact matches with Ross:** T-VIS 4650/4250 rpm (mk1b), the idle ignition table, the mixture term (Mixture − 128) × MX2 / 32 µs (his ÷ 32000 in ms) with its 3600 rpm cut-off, the 6300 rpm global-factor step, double pulses above 6000 rpm (back below 5600), and the THA correction values to within 0.2 %.
  - **New mechanisms found:**
    - `ModeFlags` bits: 7 = throttle closed or cranking, 6 = closed-throttle idle, 1 = decel cut, 0 = cranking;
    - the global factor `$F8DA`: (transient + `$5D` + `$5C` + `$60`) × (1 + `$58`/128), capped by `$56`;
    - region state `$62` and its enrichment `$60`;
    - decel cut and return rpm vs coolant, with the P37 floor matching the 1988 RM's A/C-on figures (P37 = A/C, LIKELY, from the code-51 check);
    - T-VIS advance delay 0.21 s;
    - idle-stability gain;
    - P31 and the PORT2 bit 2 hot-start output (Q2).

    All are named in `analysis/mr2_17140/symbols.yaml` (asl round trip IDENTICAL).
  - **Blocking the "Ross verified" gate:**
    1. **R-M09** (Tier B, 17070 MX2 map) is still PENDING and needs a 17070 dump. Owner decision: keep it as a gate item, or move it to `docs/variants.md` as out of scope for the 17140.
    2. `docs/ross/verification_report.md` (the P4 deliverable) is not written yet.
    3. The gate sign-off by an independent Verifier (the fixes' re-check is done: PASS WITH ISSUES, follow-ups applied).

    The PARTIAL items carry bench work but are not PENDING.
  - **Verifier (independent agent, 2026-10-14): PASS WITH ISSUES**, no blockers. Fixes applied:
    - **P37 = A/C switch, LIKELY:** the T-shorted check at `$F769`–`$F797` ORs P37 with P16 into one fault bit, Toyota's code 51 ("IDL off or A/C on with T–E1 shorted"); with the 1500/1900 rpm decel floor (the 1988 RM's A/C-on figures). New test `test_code_51_check_ors_idl_open_with_p37`; `architecture.md`, `claims.md`, `symbols.yaml` (`Code51Check`) and the simulator docstring updated. The simulator default is now `p37=0` (A/C off): the full suite passes unchanged; `expected.h` is byte-identical.
    - **Stale docs:** `ignition_maps.md` (absolute degrees LIKELY v × 15/64° BTDC; rows on both kPa scales), `serial_link.md` (Load → kPa on both scales), the max-advance conflict row, "the fuel pump" in `cpu_replacement.md` and `RE_PLAN.md` §6b (new Q13 on `FC`), "idle" → `RegionState` in `architecture.md`.
    - **R-I08 / Q2:** real tests for the P31 timer (off 20–21 s after P17 rises: 21 one-second ticks) and the PORT2 bit 2 hot-start output (low 0.18–92 s after a hot crank; stays high with Coolant above `$18`).
    - **Nits:** R-M02 status "CONTRADICTED (rpm axis)" plus the 17030 multiplier-10 hypothesis; the mixture high-load case at 115 kPa; R-I06 points to the 17140 conversion; R-F25 says P16 = IDL is LIKELY; the `DecelCutTbl` note gives the 42 used below the first site (asm and xref regenerated, asl round trip IDENTICAL); R-F26 test citation.
    - **Also:** `emu.cboard` now runs the step loop in C (`cb_run_until`) and keeps the next engine-event time on the C side, about 30× faster with identical results [EMU:tests/test_d151801_c.py, tests/test_loopback_engine.py].
    - **Re-check (second independent agent, 2026-10-15): PASS WITH ISSUES**, no blockers; follow-ups applied (see the summary at the top).
- [ ] Bench and car anchors: Load at key-on, engine off, over the serial link (kPa scale); what ADC ch7 measures; timing-light readings with T open at idle and at a steady 2500–3000 rpm; PORT3 over the link (Q10), and with T–E1 shorted confirm P3-0 reads 0 (P30 polarity).
- [x] Pico 2 W serial-link logger ([`../hardware/peek-logger/firmware/`](../hardware/peek-logger/firmware/)) and host decoder (`pcmre.peeklog`): the firmware's link logic runs against the simulated ECU [EMU:tests/test_peek_logger.py]; the UF2 builds warning-free. Not yet run on hardware; not Verifier-reviewed.
- [ ] Logger on the spare ECU on the bench (after Q11; owner confirmation), then the Wi-Fi dashboard.

### Bench observations to follow up (P4)
- **Day-one ingest** ([`../analysis/mr2_17140/ingest.md`](../analysis/mr2_17140/ingest.md)):
  - Only 4 % of the Bluetop's instructions align, so this is a different program, and **none of the 19 Bluetop maps port automatically**.
  - The data tables sit at the **start** of the ROM (`$F000`–`$F2BD`), not the end.
  - Ross's 17030 ignition table is not present byte for byte (mean difference 44 counts).
  - The candidate tables `$F1AE`/`$F1BA`/`$F1EF` correlate with his density and speed curves (shape only).
- **The 17140 reset code accepts mode 2 as well as mode 7** (LIKELY): `$F2BE LDAB $03 / ANDB #$E0 / CMPB #$E0 / BEQ +4 / CMPB #$40 / BNE *` hangs unless the latched mode is 7 (single chip) or 2 (expanded multiplexed). It looks like a built-in development mode, and is directly relevant to the P7 external-memory plan (no mode-test patch needed).
- **17140 reset vector is probably `$F2BE`** (LIKELY): an RTS with the stack on ROM pulled `$F2`/`$BE` from `$FFFE`/`$FFFF`; the logged jump to `$F0BE` is the A8/A9 fault. Mode check at `$F2BE`: `LDAB $03 / ANDB #$E0 / CMPB #$E0 / BEQ`, read Port 2 = `$18` (mode 0) [BENCH:listen].
- **Bus-cycle counts look 6801-like, not HD6301:** LSRB, CLRA show 2 bus cycles and ABX, LSRD 3, where the HD6301V1 handbook gives 1 (GUESS until checked against the handbook and more logs). If confirmed, the emulator's cycle counts for the D151801 need a 6801 timing table; it affects main-loop pacing, not the ROM arithmetic.

## Conflicts log

| Date | Topic | Source A says | Source B says | Resolution |
|---|---|---|---|---|
| 2026-10-14 | MX2 mixture-screw rpm map (R-M02) | Ross p17: MX2 about 128 at 1000 rpm and **64 at 3500/3600 rpm**, identical on the 17030 and 17140 | 17140 ROM: `$F0BD` holds the same five values (128/113/96/81/64), but the code reads them at 1000/1800/2600/3400/4200 rpm and clamps at 3600 rpm, so MX2 is **78 at 3500 and 76 at 3600**; the 64 is never used [ROM:$F0BD-$F0C3, $FAEC-$FAF1] [EMU:tests/test_ross17140.py::test_mixture_tables] | **ROM wins for the 17140** (truth order). The bytes and the 1000 rpm point agree; Ross's curve fits the bytes at about 650 rpm spacing (1000/1650/2300/2950/3600 rpm). **17030 hypothesis (GUESS):** the same lookup with multiplier 10 instead of 8 puts the sites at 1000/1640/2280/2920/3560 rpm, reproducing his curve. Otherwise his rpm axis is off. A 17030 dump settles which (Q4) |
| 2026-10-14 | Meaning of `ModeFlags` bit 7 (affects the absolute-advance conflict below) | Earlier P4 docs and the Verifier: a start/stall state, set only at low rpm, so the T-terminal fixed sum is not reached at a warm idle | ROM + EMU: P16 low for about 150 ms (throttle closed) sets it while running; it selects the idle ignition table `$F0FA` (Ross R-I07's values) and arms the decel cut. In the simulator P16 had been left high (throttle open), so bit 7 only appeared while cranking [ROM:$F4C9-$F51E] [EMU:tests/test_ross17140.py] | **Resolved (LIKELY: P16 = IDL, from the code-51 check at $F769, which ORs P16 with P37 (A/C) [EMU:tests/test_ross17140.py::test_code_51_check_ors_idl_open_with_p37], and the EWD's IDL levels):** bit 7 = throttle closed or cranking. `maps.md`, `architecture.md` and `symbols.yaml` corrected. Car check: P16 level over the serial link (PORT1) with the throttle shut and open |
| 2026-10-09 | Idle-up VSV control | 1984 EWD (Europe, mk1a era): load-switched, ECU senses on I/UP | 1988 RM (US, mk1b era): ECU drives on `V-ISC`, cranking + 10 s | Era/market difference; the manuals do not contradict each other for their own cars. **Open for the 17140** (Q2): Test B + port audit |
| 2026-10-09 | Injector harness grouping and impedance | 1984 EWD: #10 = No.1+3, #20 = No.2+4; injectors 1.5–3.0 Ω | 1988 RM: No.10 = No.3+4, No.20 = No.1+2; injectors about 13.8 Ω | Era/market difference. The grouping matters only if the ECU does not join #10/#20 (R-F22). Measure the UK car's injectors before P8 |
| 2026-10-10 | T-VIS ignition step direction (R-I09) | Earlier P2 note: +8 raw "while T-VIS is shut/off", so less advance with T-VIS open, opposite to Ross | ROM: +8 when `TVIScounter` ≥ 0, the state above 4350 rpm [ROM:$FC47–$FC6D] [EMU:test_readable]. EWD p25: S/TH switches at 4350 rpm, where T-VIS opens | **Resolved:** the old note confused the VSV output being off with the valves being shut. +2.8° applies with T-VIS **open**, agreeing with Ross. Fixed in claims.md, bluetop.yaml, simulation.md, and (2026-10-13) the fuel_chain.md ignition diagram |
| 2026-10-13 | Ignition clamp in degrees | ignition_table.md said "about 10° to 64°", fuel_chain.md "≈11°–65°": the raw sum × 90/256 without the conversion offset | ROM: sum clamped to `$1F`–`$B8` [ROM:$F8E6]; the ROM's own conversion gives 0.2°–54° BTDC warm, before the 256 µs lead [EMU:pcmre.readable.degrees, simulation.md formula] | **Resolved:** the two docs left out the −10.74° offset. Both corrected |
| 2026-10-13 | 17140 load (kPa) scale | Simulator scale Load ≈ 4.98 × kPa + 98.6, resting on the EWD PIM curve and ADC ch7 = 5 V (GUESS) | ROM: the high-load staircase `$F1DA` is used only above Load `$2B8` [ROM:$FA81-$FA8D], about 120 kPa on that scale, unreachable without boost; the top ignition-map rows likewise [EMU:sweep] | **Open.** Probably the scale is about 20–25 % low (ch7 not 5 V). Settle with Load at key-on, engine off, over the serial link, or a ch7 measurement. Until then the kPa labels in `mr2/ignition_maps.md` are GUESS. **Update (Ross pass, 2026-10-14):** the ROM's readings are exactly ratiometric to ch7 (153.7 × V / V_ch7, table `$F044`), and the simulator's AdcRef is pinned at the end of that table, so the default scale rests on `adc_k` (GUESS). With 256 counts per 5 V, 101.3 kPa gives Load 745, the top row of both ignition maps and of the density map; mixture mid travel reads 128 and both end stops are reachable [EMU:tests/test_ross17140.py]. **Proposed (LIKELY): Load ≈ 6.14 × kPa + 123.** Still open until the key-on reading (expect about 745 at sea level, against 603 on the old scale); then switch the simulator default (`ref_v=3.0`) and regenerate `ignition_maps.md` |
| 2026-10-14 | 17140 absolute ignition advance | Assumption (P4 step 3): the ROM's fixed spark sum `$00AA` is the factory base timing, 10° BTDC with T–E1 shorted | ROM: the fixed sum needs `ModeFlags` bit 7 (a start/stall state) and P30 = 0 [ROM:$F7F2-$F800], so it is not used at a warm idle; anchoring it at 10° puts a warm idle (map value 192) at 45° BTDC, not credible [Verifier, EMU] | **Open.** The maps are shown relative (v × 15/64°). Settle the offset with a timing light at a warm idle with T open, read next to the map value from the serial link. **Update (Ross pass, 2026-10-14):** `ModeFlags` bit 7 is the closed-throttle state (row above), so the fixed sum is the factory T-terminal check after all. The anchor gives a warm idle with T open of **16.0° BTDC** (idle table 68, not the map's 192), and warm untrimmed map cells read **v × 15/64° BTDC** (+0.04°), light load up to 50°, close to Ross's p16 chart [EMU:tests/test_ross17140.py::test_t_terminal_fixed_sum_only_with_the_throttle_closed]. **LIKELY**; confirm with a timing light: about 16° with T open, 10° with T shorted |
| 2026-10-14 | P30 (test terminal) polarity | Earlier docs and the simulator: fixed timing with P3-0 high | ROM: the self-test, the flasher pattern and the fixed sum all act on P30 = 0 [ROM:$F2F0, $F774, $F7F2] | **Resolved (LIKELY):** T shorted reads P30 = 0. Docs and simulator corrected |
| 2026-10-09 | HD6301 DAA V flag | Handbook table 3-2-1 (PDF p.190): V affected | Handbook instruction details (PDF p.89): V not affected | Open. The core clears V, as MAME does. The Bluetop never executes DAA; check the 17140 ROM for DAA before relying on it |
| 2026-10-09 | Bluetop IDL input polarity | cap.asm comment: P4-2 IDL "active low" (throttle closed = 0) | ROM behaviour: idle state (`byte_95` negative) builds while P4-2 is **high**, and three idle-only uses agree (idle advance, 800 µs airflow fallback, tip-in pulse below 2500 rpm); a second cap.asm comment at $F7F1 also says P4-2 is high when IDL is closed [ROM:$F9F7–$FA39, $F814, $F1E0, $FA19] | ROM wins (truth order): P4-2 high = throttle closed at the CPU pin, LIKELY (the input buffer presumably inverts). The simulation uses the ROM's polarity |
| 2026-10-09 | Bluetop cranking spark | Assumption that the CPU makes every spark | ROM: in start mode (`byte_C6` > 0) /IGT is held high, yet missing IGF still cuts fuel [ROM:$F24A, $F370, $F92D, $F420] | The cranking spark must come from outside the CPU (LIKELY the SE056 from NE). Modelled as such; confirm on the bench (P8) and in the 17140 ROM (P4) |
| 2026-10-09 | Max ignition advance | Ross p16 graph: about 50° BTDC | Upstream #6: implausible, may include a VR offset | Open. Settle with a timing light (R-I06). **Update (Ross pass, 2026-10-14):** the 17140's T-terminal anchor (the 2026-10-14 absolute-advance row) puts map A's largest value, 213, at **49.9° BTDC** (LIKELY), which supports Ross's ~50° for light-load cells. Stays open until the timing-light check |

## Exceptions to the RP2350-first rule

| Date | Item | Reason | Owner approved? |
|---|---|---|---|
