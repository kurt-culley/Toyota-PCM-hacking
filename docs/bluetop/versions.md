# Bluetop software versions: D151801-0642 and D151801-2860

**ROMs:**
- `cap.bin` (= `cap1-151801-0642.bin`): the reference, with the annotated IDA listing.
- `cap2-151801-2860.bin`: provenance unknown. `cap4.bin` is a second, independent capture of the same ROM: 103 bytes of a restarted capture, then every byte identical to `cap2`. So the 2860 image is confirmed by two captures.

**Method:** [`analysis/pcmre/crossver.py`](../../analysis/pcmre/crossver.py) traces both ROMs from their vectors, aligns the instruction streams, learns the RAM addresses that moved, and ports each map by following the 0642 code that reads it. The generated report (every difference, with addresses) is [`analysis/bluetop/crossver_2860.md`](../../analysis/bluetop/crossver_2860.md). The ported definition file is [`analysis/defs/bluetop_2860.yaml`](../../analysis/defs/bluetop_2860.yaml), with maps, CSVs and a TunerPro XDF in [`analysis/bluetop_2860/`](../../analysis/bluetop_2860/). Tests: [`tests/test_crossver.py`](../../tests/test_crossver.py).

## Summary

| | Finding | Evidence |
|---|---|---|
| **Program** | Same program, revised. 1989 against 1993 instructions reached, the same 68 routines; 1964 of 0642's instructions align | [EMU:test_crossver] CONFIRMED |
| **Calibration** | All 19 defined maps port automatically (CONFIRMED by their reading code) and are **byte-for-byte identical**. The ignition map moved from `$FF40` to `$FF5A` | [EMU:test_every_map_ports_and_is_identical] CONFIRMED |
| **Load sensing** | The airflow-delay chain (SE056 pulse, `se056_max`, `tha_corr`, fuel formula) is identical, so 2860 uses the same load sensor type as 0642 | CONFIRMED (code and tables) |
| **Data outside maps** | The only differing bytes are 7 code pointers that follow their moved targets (`$FD39` jump table, vectors), the checksum-balance word `$FFEE`, and two RAM start-up values | [EMU:test_every_data_difference_is_explained] CONFIRMED |

## Behaviour changes in 2860

Addresses are 2860's unless marked. The code is CONFIRMED in each case; the stated purpose carries its own confidence.

| # | Change | 2860 address | 0642 | 2860 | Purpose |
|---|---|---|---|---|---|
| 1 | **A/C idle advance gated by coolant** | `$F841`–`$F849` | With the A/C on at idle, `IDLcompADV` gets +14 raw (≈5°) | +14 only when `ADC_ThW` ≥ `$DA` (218 °F, 103 °C); otherwise +0 | LIKELY: extra idle advance (idle speed and charging) only when the engine is hot under A/C load |
| 2 | **Stall-flag logic** (`byte_4C` bits 0–1) | `$FA6D`–`$FA95`; init table | Engine-stopped detection sets `byte_4C` bit 0 unconditionally | Sets bit 0 only if bit 1 is set. Bit 1 is set at power-up (RAM init `byte_4C = $02`) and whenever the engine runs above the start threshold | GUESS: a refined stall/restart flag |
| 3 | **Diagnostic rpm threshold** | `$FCF8` | `cmpa #40` (`lilRPM` 40 = 1000 rpm) | `cmpa #60` (1500 rpm) | CONFIRMED: the check that raises fault flag `$10` via `flagbadstuf3` passes above this rpm. Which sensor it covers is not yet identified |
| 4 | **P1-5 in safe states** | `$FE47`, `$FE5F`, `$FE8D` | Port 1 written `$C0` / `$C8` / `$48` (bit 5 low) in the reset, checksum-fail and test-mode paths | `$E0` / `$E8` / `$68` (bit 5 high) | CONFIRMED: P1-5 (the idle-up VSV / V-ISC output, STATUS Q2) is driven high in these paths |
| 5 | Reset-loop counter reload | `$F0E3` | `byte_96 = $89` | `= $8A` (one count shorter) | GUESS: a main-loop timing counter |
| 6 | Start-up TPS value | RAM init | `ADC_TPS = $73` | `$99` | CONFIRMED: the value assumed before the first conversion |
| 7 | `unk_D8` no longer written | 0642 `$F8EE` | The final advance is copied to `unk_D8` | Removed | CONFIRMED: no ROM code reads `unk_D8`. Only the serial RAM-peek could have shown it |
| 8 | `SatCount_C7` cleared earlier | `$F81C` | Cleared in the idle path only | Cleared before the T-terminal test | CONFIRMED; minor |
| 9 | Fuel/feedback inhibit test (`Calc76`) | `$F7C7`–`$F7CB` | Two tests (`byte_4C`, `SatCount_97`) | One `oraa` of both | CONFIRMED: same logic, fewer bytes |

## Structural changes (no behaviour change)

- **RAM layout:** eight direct-page variables rotated. `SatCount_97`–`byte_9D` each moved down one byte, and `byte_96` moved to `$9D`, so that `ldd $9C` loads two related bytes at once. Full table in the report.
- **Helpers relocated:** the 1D table helper's entry points moved, changing every `jsr N,x` offset (18 call sites). The PWRr step-table helper moved from `$FFA4` to `$FEB4`, together with its two tables (`$FF94` → `$FEA4`, `$FF9C` → `$FEAC`).
- **Table order:** the 1D tables were re-packed, for example `thw_FECB` → `$FEA0` (now first).
- **Same in both:** rev limiter (`$0FD6`, reload `$79`), checksum convention (`$AA55` at `$FFEE`), interrupt structure.

## For the 17140

The port method works on a revised program with relocated helpers and rotated RAM: all 19 maps were found and confirmed with no manual help. The 17140 is expected to be a further revision of this program. Running `pcmre.crossver` against it should therefore:
- port most map definitions automatically;
- list the RAM moves;
- flag every behaviour change for review.

A map whose reading code changed shape is reported as not ported rather than guessed.
