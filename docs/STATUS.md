# Project status

The Lead agent updates this file at the end of every session. The plan is in [`RE_PLAN.md`](RE_PLAN.md).

**Last updated:** 2026-10-09 (later):
- **P2 work complete, gate review pending.**
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
| P2 | Bluetop analysis + Tier-A verification | ◐ all tasks done; gate review fixes awaiting Verifier re-check | ☐ |
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
  - Re-check pending.
- [x] Every table the code reads is now defined: 19 maps in the YAML.
  - New: `$FE9C` max airflow delay vs rpm, `$FEA7` acceleration enrichment, `$FF11` over-temperature retard, and the PWRr staircases `$FF94`/`$FF9C`.
  - **Correction:** the injector dead time is `$FEE9` (8·v + 464 µs); `$FF12` is the dwell term.
  - `Load` scaling documented (air-temperature-corrected airflow delay, µs).
  - Advance degrees: see Q3.
- [x] TunerPro RT XDF generated from the YAML ([`../analysis/bluetop/bluetop.xdf`](../analysis/bluetop/bluetop.xdf)) with display equations for advance, dead time, dwell and max airflow. **Not yet opened in TunerPro: owner check.**
  - Checksum helper [`../analysis/pcmre/checksum.py`](../analysis/pcmre/checksum.py): the word sum must be $AA55, balanced at $FFEE [ROM:$FE50].
  - A TunerStudio INI needs a comms protocol, so it moves to P7.

### P1 tasks
- [x] Claim register skeleton: [`ross/claims.md`](ross/claims.md).
- [x] Extract the 16 figures (`pdfimages`, flipped upright) and confirm the page mapping ([`ross/figures/`](ross/figures/README.md)).
- [x] Digitise the graphs to CSV ([`../analysis/ross/digitise.py`](../analysis/ross/digitise.py)) and transcribe the 17×8 ignition table. The transcription matches Ross's own p13 chart to within 1 count.
- [x] Mermaid diagrams of Ross's fuel chain, ignition chain, injection modes, T-VIS, idle stability, mixture screw and cold start ([`ross/diagrams.md`](ross/diagrams.md)). All render with mermaid-cli 11.4.

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
| Q2 | Does the ECU drive the cold start injector or any idle-air device? **CSI: no (LIKELY for the 17140).** Both factory manuals wire it starter → CSI → time switch, and the board label is `STH` = S/TH (T-VIS), not STJ. **Idle air: open.** The IACV is a mechanical wax valve in both manuals. The idle-up VSV is load-switched and only *sensed* (I/UP) in the 1984 EWD, but the 1988 US ECU **drives** it from `V-ISC` during cranking and for 10 s after start, and the 17140 board has a `VISC` pad. **Bluetop evidence (P2) [EMU:sim]:** the Bluetop ROM drives P1-5 from key-on until about 10 s after start (same at 0 °C and 80 °C in simulation), matching the 1988 RM's V-ISC timing, and also at idle while its learned trim `word_42` is below $42. So this ECU family drives an idle-up output, but not on a coolant warm-up schedule. See [`hardware/ewd_aw11_1984.md`](hardware/ewd_aw11_1984.md) and [`hardware/repair_manual_aw11_1988.md`](hardware/repair_manual_aw11_1988.md) | Continuity **Test B** (is there a driver transistor behind `VISC`?), then the P4 port audit ([`hardware/aw11_ecu.md`](hardware/aw11_ecu.md)) |
| Q3 | What converts raw ignition-table values to degrees BTDC, and does VR offset matter? **Bluetop answered in simulation [EMU:sim]:** BTDC = (map + ThW_tADV + idle term) × 90/256 − 10.74° plus a fixed 256 µs lead (T terminal → 10.3°, consistent with the factory 10° but not independent of it). For the Bluetop that makes a map cell v ≈ v × 90/256 − 0.9°. Open: whether the 256 µs lead offsets a real delay, and the 17140's conversion | Bench IGT vs crank capture (P8); 17140 ROM (P4) |
| Q4 | Can a 17030 or 17070 dump be found, to check Ross's 17030 numbers directly? | Community search (P3) |
| Q5 | Do NE/G inputs need a VR-style bipolar waveform from the bench simulator? | ECU input-circuit inspection (P8). IC3 (µPC177C comparator) is the likely conditioner |
| Q6 | ~~Do the factory jumpers set a logic level or the mode pins?~~ **Answered 2026-10-09 [BENCH] for P32/P34:**<br>• **The jumpers come in pairs** per option pin: one to ground, one to node N.<br>• **P32 (pin 35):** J4 to ground (fitted), J9 to N.<br>• **P34 (pin 33):** J8 to N (fitted), J3 to ground.<br>• **Factory setting:** P32 = 0, P34 = N (LIKELY 1).<br>• These are Port 3 option bits, the prime candidates for the secret-map select (R-F12, R-I15). They are not the mode pins.<br>See [`hardware/aw11_ecu.md`](hardware/aw11_ecu.md) | Search the 17140 ROM for reads of Port 3 bits 2 and 4 (P4/P6). J6, J7, J1 and J2 are not tested yet |
| Q7 | What does the 17140 ROM do with the `OX`/`VF` pins on a UK car with no O2 sensor? | ROM analysis (P4) |
| Q8 | Does the 17140's `OX` pin carry the mixture-screw CO resistor? The 1984 VAF pin is missing from the board (Ross R-M08) | Continuity **Test B**, then the ROM ADC channel map (P4) |
| Q9 | Is there a **1986–89 UK mk1b wiring diagram** to confirm the 17140 pinout (VISC, OX, W, ACT, FPU ...)? The 1988 repair manual is mk1b-era but **US spec** (air flow meter, O2 sensor), so it defines `V-ISC`, `FPU` and `W` but cannot say what the UK car uses | Owner: a UK/European 1986–89 EWD or repair manual supplement |
| Q10 | What is jumper **node N**? About 750 Ω to ground, the same both ways, not connected to the main +5 V. Is it a logic-high source, such as a standby 5 V rail? This decides what P34 reads (0 or 1) with the factory J8 fitted | **Powered** bench measurement of N and P20–P22 at reset. Needs the owner's confirmation (CLAUDE.md hardware safety) |

## Conflicts log

| Date | Topic | Source A says | Source B says | Resolution |
|---|---|---|---|---|
| 2026-10-09 | Idle-up VSV control | 1984 EWD (Europe, mk1a era): load-switched, ECU senses on I/UP | 1988 RM (US, mk1b era): ECU drives on `V-ISC`, cranking + 10 s | Era/market difference; the manuals do not contradict each other for their own cars. **Open for the 17140** (Q2): Test B + port audit |
| 2026-10-09 | Injector harness grouping and impedance | 1984 EWD: #10 = No.1+3, #20 = No.2+4; injectors 1.5–3.0 Ω | 1988 RM: No.10 = No.3+4, No.20 = No.1+2; injectors about 13.8 Ω | Era/market difference. The grouping matters only if the ECU does not join #10/#20 (R-F22). Measure the UK car's injectors before P8 |
| 2026-10-09 | HD6301 DAA V flag | Handbook table 3-2-1 (PDF p.190): V affected | Handbook instruction details (PDF p.89): V not affected | Open. The core clears V, as MAME does. The Bluetop never executes DAA; check the 17140 ROM for DAA before relying on it |
| 2026-10-09 | Bluetop IDL input polarity | cap.asm comment: P4-2 IDL "active low" (throttle closed = 0) | ROM behaviour: idle state (`byte_95` negative) builds while P4-2 is **high**, and three idle-only uses agree (idle advance, 800 µs airflow fallback, tip-in pulse below 2500 rpm); a second cap.asm comment at $F7F1 also says P4-2 is high when IDL is closed [ROM:$F9F7–$FA39, $F814, $F1E0, $FA19] | ROM wins (truth order): P4-2 high = throttle closed at the CPU pin, LIKELY (the input buffer presumably inverts). The simulation uses the ROM's polarity |
| 2026-10-09 | Bluetop cranking spark | Assumption that the CPU makes every spark | ROM: in start mode (`byte_C6` > 0) /IGT is held high, yet missing IGF still cuts fuel [ROM:$F24A, $F370, $F92D, $F420] | The cranking spark must come from outside the CPU (LIKELY the SE056 from NE). Modelled as such; confirm on the bench (P8) and in the 17140 ROM (P4) |
| 2026-10-09 | Max ignition advance | Ross p16 graph: about 50° BTDC | Upstream #6: implausible, may include a VR offset | Open. Settle with a bench measurement (R-I06) |

## Exceptions to the Arduino-first rule

| Date | Item | Reason | Owner approved? |
|---|---|---|---|
| 2026-10-09 | Level shifters (74LVC245, 74AHCT125) | The Zero is not 5 V tolerant | Accepted in the plan |
| 2026-10-09 | Bus-speed CPLD + SRAM (in-car daughterboard, deferred) | Firmware cannot answer a 1 MHz bus in hundreds of ns | Accepted in the plan; nothing ordered yet |
