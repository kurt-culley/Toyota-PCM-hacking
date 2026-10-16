# Bluetop software versions 0642 and 2860

## Summary

| | Result | Evidence |
|---|---|---|
| **Program** | The same program, revised. 1989 against 1993 instructions reached, the same 68 routines. 1964 of the 0642 instructions align | [EMU:test_crossver] CONFIRMED |
| **Calibration** | The tool ports all 19 defined maps automatically (it confirms each through its reading code). They are **byte-for-byte identical**. The ignition map moved from `$FF40` to `$FF5A` | [EMU:test_every_map_ports_and_is_identical] CONFIRMED |
| **Load sensing** | The airflow-delay chain (SE056 pulse handling, `se056_max`, `tha_corr`, fuel formula) is identical in code and tables. This agrees with the same load sensor type. The SE056 front end is hardware, so this is not a proof | [EMU:test_crossver] LIKELY |
| **Data outside maps** | Each different byte has an explanation: 7 code pointers that follow their moved targets (`$FD39` jump table, vectors), the word-sum balance word `$FFEE`, and two RAM start values. No 2860 data is unexplained | [EMU:test_every_data_difference_is_explained, test_no_2860_data_unaccounted] CONFIRMED |
| **16-bit constants** | 5 aligned instructions load a changed 16-bit constant (rows 1 and 2 below). Each other different 16-bit operand is a moved code, map, RAM or data pointer | [EMU:test_wide_operand_changes_are_found] CONFIRMED |

## ROMs, method and outputs

**ROMs:**

- [`roms/bluetop/cap.bin`](../../roms/bluetop/cap.bin) (= `cap1-151801-0642.bin`): version 0642, the reference ROM, with the IDA listing.
- [`roms/bluetop_2860/cap2-151801-2860.bin`](../../roms/bluetop_2860/cap2-151801-2860.bin): version 2860. Its source is not known.

**Method:** [`src/pcmre/crossver.py`](../../src/pcmre/crossver.py) does these steps:

1. It traces the two ROMs from their vectors.
2. It aligns the instruction streams and finds which RAM addresses moved.
3. It ports each map through the 0642 code that reads it.
4. It examines each different 16-bit operand and each data byte, in the two directions.

A map whose reading code changed shape is reported as "not ported". The tool does not guess it.

**Outputs:**

- The generated report (each difference, with addresses): [`roms/bluetop/crossver_2860.md`](../../roms/bluetop/crossver_2860.md).
- The ported defs file: [`roms/bluetop_2860/defs.yaml`](../../roms/bluetop_2860/defs.yaml). The maps, CSV files and a TunerPro XDF are in [`roms/bluetop_2860/`](../../roms/bluetop_2860/).
- The tests: [`tests/ae86/test_crossver.py`](../../tests/ae86/test_crossver.py). They include hand-written byte checks of the known differences.

## Behaviour changes in 2860

The addresses are 2860 addresses, except where the table shows "0642". The code is CONFIRMED in each row. The purpose has its own confidence.

| # | Change | 2860 address | 0642 | 2860 | Purpose |
|---|---|---|---|---|---|
| 1 | **Port direction registers at reset** | `$F01B`, `$F020`, `$F067`, `$F06C` | `ldx #$6081 / stx $04` and `ldx #$EE12 / stx $00`: Port 1 direction `$EE`, Port 3 direction `$60` | `#$6F81` and `#$FE12`: Port 1 direction **`$FE`** (P14 becomes an output), Port 3 direction **`$6F`** (P30 to P33 become outputs) | No code writes those bits after reset, so they keep their reset values: P14 high (Port 1 = `$9F`), P30 to P33 high (Port 3 = `$BF`). The exception is the T-terminal self-test, which drives P14 low. P34 stays an input (read at `$FC82`). GUESS: unused pins become outputs so that they do not float. **For the 17140:** its option jumpers connect P32 and P34 (J4, J8), so those pins must stay inputs there ([17140 hardware](../mr2/hardware.md)). **CAUTION:** the 2860 image drives P32 high as an output. Do not run it on a board where J4 connects P32 to ground |
| 2 | **Stall flag** (`byte_4C` bits 0–1) | `$FA39`; `$FA6D`–`$FA95`; RAM init | The engine-stopped detection sets bit 0 always | The RAM init sets bit 1 at power-up (`byte_4C = $02`). The ROM **clears bit 1 while STA (P44, cranking) is high** (`ldd #$10FC`, 0642 `#$10FE`). It sets bit 1 again in run mode (`byte_C6` < 0) when `lilRPM` ≥ `$14` (500 rpm). Bit 0 (engine stopped) is set only while bit 1 is set | GUESS: "stalled" now means "stopped after it ran", not "not yet started" |
| 3 | **A/C idle advance controlled by coolant** | `$F841`–`$F849` | Idle, A/C on (P43 high): **BaseAdvance** (`$A3`) gets +14 raw (≈ 5°) always; A/C off: +0 | +14 only when `ADC_ThW` ≥ `$DA` (218 °F, 103 °C); else +0. The carry from `cmpb #$DA` stays after `ldab #$0E` (LDAB does not change C) | 218 °F is the over-temperature limit of the ROM, the same limit as between `thw_FF0A` and `overheat_adv`. Thus **in normal operation 2860 has no A/C idle advance**. It keeps it only when the engine is too hot. **In tuning terms:** at idle with the A/C on, 2860 has about 5° less advance than 0642 at normal temperatures. Purpose GUESS. It depends on the `thw_linearise` °F scale (LIKELY). `IDLcompADV` (`$A6`, the idle-speed-error term) has a maximum of 14 with the A/C on in the two versions |
| 4 | **Fault-flag `$10` rpm condition** | `$FCF8` | `cmpa #40` (`lilRPM` 40 = 1000 rpm) | `cmpa #60` (1500 rpm) | This path sets flag `$10` (through `flagbadstuf3`) when the `jsr $11,x` count (in A) is ≥ `$25` and `lilRPM` ≥ the limit. Other paths (`SatCount_D1` ≥ 9, the `$F3` branch) set it at all rpm. 2860 needs ≥ 1500 rpm on this path, so the fault is more difficult to set. The sensor that it monitors is not known |
| 5 | **P15 in the T-terminal self-test paths** (entry, word-sum fail, RAM-test fail) | `$FE47`, `$FE5F`, `$FE8D` | Port 1 written `$C0` / `$C8` / `$48` (bit 5 low) | `$E0` / `$E8` / `$68` (bit 5 high) | The three writes are the T-terminal **self-test entry**, the **word-sum fail** path and the **RAM-test fail** path. They are not the normal reset, which sets Port 1 = `$9F` in the two versions. P15 is LIKELY the idle-up VSV / V-ISC output ([architecture](architecture.md), [open items](../project/open_items.md) Q2) |
| 6 | Start TPS value | RAM init | `ADC_TPS = $73` | `$99` | CONFIRMED: the value before the first conversion |
| 7 | No write to `unk_D8` | 0642 `$F8EE` | The final advance is copied to `unk_D8` | Removed | No ROM code reads `unk_D8`, in any addressing mode. Only the serial RAM peek (`$F40D`) can show it |
| 8 | `SatCount_C7` cleared before | `$F81C` | Cleared only in the idle path | Cleared before the T-terminal test, thus also when the test terminal is connected to ground | Small change |
| 9 | Fuel and feedback inhibit test (`Calc76`) | `$F7C7`–`$F7CB` | Two tests (`byte_4C`, `SatCount_97`) | One `oraa` of the two. The two branch targets map exactly (0642 `$F7B0` = 2860 `$F7AB`), and A is not used after it | Same logic, fewer bytes |

## Structural changes (no behaviour change)

- **RAM layout:** eight direct-page variables rotated. `SatCount_97`–`byte_9D` each moved down one byte, and `byte_96` moved to `$9D`. The report has the full table.
- **Reset loop:** 0642 loads `byte_95`/`byte_96` with `ldd`. 2860 does this:
  - `ldd $9C` (the rotated pair), a sign test with `ldx $95`, and `deca` instead of `suba #1`;
  - `ldab #$8A`, then `decb` before `std $9C`. This stores `$89`, the same value as `ldab #$89` in 0642.

  The result is the same: `deca` does not change the carry, and the `$FB4B` clamp entry does not read it.
- **Moved helpers:**
  - The 1D table helper moved by +`$1A`, with an identical body. This changes each `jsr N,x` offset (18 call sites; each reaches the correct entry).
  - The PWRr step-table helper moved from `$FFA4` to `$FEB4`, with its two tables (`$FF94` → `$FEA4`, `$FF9C` → `$FEAC`).
- **Table order:** the 1D tables have a new order. For example `thw_FECB` → `$FEA0` (now first).
- **The same in the two versions:**
  - the rev limiter (`cpx #$0FD6`, reload `#$79`)
  - the word sum (`$AA55`, balanced at `$FFEE`)
  - the vector layout
  - all 18 inline bound parameters.

## For the 17140

The port method works on a revised program with moved helpers and rotated RAM. It found and confirmed all 19 maps with no manual help. It also examines changed 16-bit constants separately, because a map port does not find them.
