# Bluetop software versions: D151801-0642 and D151801-2860

**ROMs:**
- `cap.bin` (= `cap1-151801-0642.bin`): the reference, with the annotated IDA listing.
- `cap2-151801-2860.bin`: provenance unknown.
- `cap4.bin` is **consistent with** a capture of the same ROM. It holds 2 bytes of `$00`, then the first 100 bytes of 2860, then one corrupted byte (`$EE` where 2860 has `$8E`, at the position of `$F064`), then a complete copy of 2860. That fits a capture that restarted once with a read error. `cap2` may simply be `cap4` with the prefix trimmed, so it is not proof of two fully independent reads.

**Method:** [`analysis/pcmre/crossver.py`](../../analysis/pcmre/crossver.py) does the following:
- traces both ROMs from their vectors;
- aligns the instruction streams and learns which RAM addresses moved;
- ports each map by following the 0642 code that reads it;
- checks every differing 16-bit operand and every data byte, in both directions.

**Outputs:**
- Generated report (every difference, with addresses): [`analysis/bluetop/crossver_2860.md`](../../analysis/bluetop/crossver_2860.md).
- Ported definition file: [`analysis/defs/bluetop_2860.yaml`](../../analysis/defs/bluetop_2860.yaml), with maps, CSVs and a TunerPro XDF in [`analysis/bluetop_2860/`](../../analysis/bluetop_2860/).
- Tests: [`tests/test_crossver.py`](../../tests/test_crossver.py), including hand-written byte checks of the known differences.

**Review:** an independent Verifier first returned FAIL on 2026-10-10: two changes were missed, one was wrong, and one was misread. This page is the corrected version.

## Summary

| | Finding | Evidence |
|---|---|---|
| **Program** | Same program, revised. 1989 against 1993 instructions reached, the same 68 routines; 1964 of 0642's instructions align | [EMU:test_crossver] CONFIRMED |
| **Calibration** | All 19 defined maps port automatically (confirmed through their reading code) and are **byte-for-byte identical**. The ignition map moved from `$FF40` to `$FF5A` | [EMU:test_every_map_ports_and_is_identical] CONFIRMED |
| **Load sensing** | The airflow-delay chain (SE056 pulse handling, `se056_max`, `tha_corr`, fuel formula) is identical in code and tables. That is consistent with the same load sensor type. The sensor front end (SE056) is hardware, so this is not proof | [EMU:test_crossver] LIKELY |
| **Data outside maps** | Every differing byte is explained: 7 code pointers that follow their moved targets (`$FD39` jump table, vectors), the checksum-balance word `$FFEE`, and two RAM start-up values. No 2860 data is unaccounted for | [EMU:test_every_data_difference_is_explained, test_no_2860_data_unaccounted] CONFIRMED |
| **16-bit constants** | 5 aligned instructions load a changed 16-bit constant (rows 1 and 2 below). Every other differing 16-bit operand is a moved code, map, RAM or data pointer | [EMU:test_wide_operand_changes_are_found] CONFIRMED |

## Behaviour changes in 2860

Addresses are 2860's unless marked. The code is CONFIRMED in each row; the stated purpose carries its own confidence.

| # | Change | 2860 address | 0642 | 2860 | Purpose |
|---|---|---|---|---|---|
| 1 | **Port direction registers at reset** | `$F01B`, `$F020`, `$F067`, `$F06C` | `ldx #$6081 / stx $04` and `ldx #$EE12 / stx $00`: Port 1 direction `$EE`, Port 3 direction `$60` | `#$6F81` and `#$FE12`: Port 1 direction **`$FE`** (P1-4 becomes an output), Port 3 direction **`$6F`** (P3-0 to P3-3 become outputs) | No code writes those bits afterwards, so they hold their reset values: P1-4 high (Port 1 = `$9F`), P3-0 to P3-3 high (Port 3 = `$BF`). The exception is the T-terminal self-test, which drives P1-4 low. P3-4 stays an input (read at `$FC82`). GUESS: unused pins made outputs so they don't float. **For the 17140:** its option jumpers ground P3-2 and load P3-4 (J4, J8), so those pins must stay inputs there. Check this in the P4 port audit. **Caution:** the 2860 image drives P3-2 high as an output, so it must not run on a board where J4 grounds P3-2 (the output would fight the ground link) |
| 2 | **Stall flag** (`byte_4C` bits 0–1) | `$FA39`; `$FA6D`–`$FA95`; RAM init | Engine-stopped detection sets bit 0 unconditionally | Bit 1 is set at power-up (RAM init `byte_4C = $02`), **cleared while STA (P4-4, cranking) is high** (`ldd #$10FC`, was `#$10FE`), and set again in run mode (`byte_C6` < 0) once `lilRPM` ≥ `$14` (500 rpm). Bit 0 (engine stopped) is set only while bit 1 is set | GUESS: "stalled" now means stopped after having run, not merely not yet started |
| 3 | **A/C idle advance gated by coolant** | `$F841`–`$F849` | Idle, A/C on (P4-3 high): **BaseAdvance** (`$A3`) gets +14 raw (≈ 5°) unconditionally; A/C off: +0 | +14 only when `ADC_ThW` ≥ `$DA` (218 °F, 103 °C); otherwise +0. The carry from `cmpb #$DA` survives `ldab #$0E` (LDAB does not change C) | 218 °F is the ROM's own over-temperature boundary, the same split as between `thw_FF0A` and `overheat_adv`. So **in normal running 2860 has removed the A/C idle advance**, and keeps it only when overheating. **In tuning terms:** at idle with the A/C on, 2860 runs about 5° less advance than 0642 at normal temperatures. Purpose GUESS. Depends on the `thw_linearise` °F scaling (LIKELY). `IDLcompADV` (`$A6`, the idle-speed-error term) is clamped to ≤ 14 with the A/C on in both versions |
| 4 | **Fault-flag `$10` rpm condition** | `$FCF8` | `cmpa #40` (`lilRPM` 40 = 1000 rpm) | `cmpa #60` (1500 rpm) | Flag `$10` (via `flagbadstuf3`) is raised by this path when the `jsr $11,x` count (in A) is ≥ `$25` and `lilRPM` ≥ the threshold. Other paths (`SatCount_D1` ≥ 9, the `$F3` branch) raise it regardless of rpm. 2860 needs ≥ 1500 rpm on this path, so the fault is harder to set. The sensor it covers is not yet identified |
| 5 | **P1-5 in the T-terminal self-test paths** (entry, checksum fail, RAM-test fail) | `$FE47`, `$FE5F`, `$FE8D` | Port 1 written `$C0` / `$C8` / `$48` (bit 5 low) | `$E0` / `$E8` / `$68` (bit 5 high) | The three writes are the T-terminal **self-test entry**, the **checksum-fail** path and the **RAM-test-fail** path, not normal reset (which sets Port 1 = `$9F` in both versions). P1-5 is LIKELY the idle-up VSV / V-ISC output (architecture.md, STATUS Q2) |
| 6 | Start-up TPS value | RAM init | `ADC_TPS = $73` | `$99` | CONFIRMED: the value assumed before the first conversion |
| 7 | `unk_D8` no longer written | 0642 `$F8EE` | The final advance is copied to `unk_D8` | Removed | No ROM code reads `unk_D8` by any addressing mode. Only the serial RAM-peek (`$F40D`) could have shown it |
| 8 | `SatCount_C7` cleared earlier | `$F81C` | Cleared in the idle path only | Cleared before the T-terminal test, so also when the test terminal is grounded | Minor |
| 9 | Fuel/feedback inhibit test (`Calc76`) | `$F7C7`–`$F7CB` | Two tests (`byte_4C`, `SatCount_97`) | One `oraa` of both; both branch targets map exactly (0642 `$F7B0` = 2860 `$F7AB`), and A is dead afterwards | Same logic, fewer bytes |

## Structural changes (no behaviour change)

- **RAM layout:** eight direct-page variables rotated. `SatCount_97`–`byte_9D` each moved down one byte, and `byte_96` moved to `$9D`. The full table is in the report.
- **Reset-loop rewrite:** 0642 loads `byte_95`/`byte_96` with `ldd`. 2860 instead does:
  - `ldd $9C` (the rotated pair), a sign test with `ldx $95`, and `deca` instead of `suba #1`;
  - `ldab #$8A` falling through to `decb` before `std $9C`, which stores `$89`, the same as 0642's `ldab #$89`.

  It is equivalent: `deca` leaves the carry alone, and the `$FB4B` clamp entry does not read it.
- **Helpers relocated:**
  - The 1D table helper moved by +`$1A`, with an identical body, changing every `jsr N,x` offset (18 call sites, each verified to reach the matching entry).
  - The PWRr step-table helper moved from `$FFA4` to `$FEB4`, together with its two tables (`$FF94` → `$FEA4`, `$FF9C` → `$FEAC`).
- **Table order:** the 1D tables were re-packed; for example `thw_FECB` → `$FEA0` (now first).
- **Same in both:** the rev limiter (`cpx #$0FD6`, reload `#$79`), the checksum convention (`$AA55` at `$FFEE`), the vector layout, and all 18 inline bound parameters.

## For the 17140

The port method works on a revised program with relocated helpers and rotated RAM: all 19 maps were found and confirmed with no manual help. The review showed that changed 16-bit constants need their own check, which the tool now does. A map whose reading code changed shape is reported as not ported rather than guessed.
