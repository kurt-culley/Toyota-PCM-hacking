# Bluetop fuel and ignition chains (P2)

This page traces how the AE86 Bluetop computes the injector pulse and the spark advance. The figures follow the layout of Ross's 17030 diagrams ([`../ross/diagrams.md`](../ross/diagrams.md)), so the two can be compared box by box. That comparison is what P4 will do with the 17140 ROM.

**Confidence:**
- The structure (which variable feeds which) is read from the code [ROM].
- The table lookups and the helper arithmetic are proven in the emulator [EMU].
- Physical meanings are LIKELY or GUESS as marked.
- The Bluetop is **L-type** (airflow meter), so its base fuel is an airflow pulse time, not a MAP-based density value.

## 1. Fuel chain

```mermaid
flowchart TD
  AF["SE056 airflow pulse<br/>IC1 capture, clamped to SE056Min/Max<br/>→ SE056plstime $6A<br/>[ROM:$F1C1]"] --> LOAD
  THA["ADC_ThA → table $FED9 → ThAcorr $8A<br/>[ROM:$FBF6] [EMU]"] --> CALC72
  LOAD["Calc72(SE056plstime)<br/>blend with ThAcorr<br/>→ Load $7F<br/>[ROM:$F550]"] --> FILT["Loadfilt1 / Loadfilt2<br/>(filtered load; filtering is lighter when cold)<br/>[ROM:$F61B–$F659]"]
  CALC72["Calc72($0800) → word_72<br/>air-temperature compensated base ratio<br/>[ROM:$F585]"] --> W70
  THW1["ADC_ThW (°F) → table $FED2<br/>[EMU]"] --> W70["word_70 = word_72 × 2 × FED2(ThW) / 256<br/>coolant-compensated floor<br/>[ROM:$F589–$F597]"]
  subgraph ENR["Additive enrichments, summed into a multiplier [ROM:$F673–$F6A6]"]
    E84["byte_84: table $FEB6 (ThW), decays per pass<br/>after-start enrichment [EMU:sim]"]
    E89["byte_89: load rising faster than its filter<br/>→ acceleration enrichment (only when warm)"]
    E8C["word_8C + byte_8B: table $FEC4 / $FEBD (ThW),<br/>decays −$10 per pass → after-start enrichment"]
    E86["byte_86, byte_88: throttle / rpm / load-dependent terms"]
    E87["byte_87: decaying term"]
  end
  W70 --> MIX
  ENR --> MIX["sum → repeat-add multiplier on word_72<br/>× byte_83 (table $FEAF, ThW)<br/>[ROM:$F67B–$F6B1]"]
  MIX --> O2["Calc76: O2 trim word_76<br/>(ADC_Oxy; default $8000)<br/>[ROM:$F7BE]"]
  O2 --> FR["FuelRatioH $74 = max(word_70, corrected word_72)<br/>'ratio to multiply SE056plstime by'<br/>[ROM:$F6D8–$F6E0]"]
  FR --> PW["pulse width InCp2TrEg $9F<br/>= airflow time × FuelRatioH<br/>[ROM:$F138–$F160]"]
  BAT["ADC_12V → table $FEE9 → InjDeadTime $81<br/>= 8·v + 464 µs [ROM:$FC8F–$FC9E] [EMU]"] --> OFF
  PW --> OFF["injector off time = Timer + pulse + dead time<br/>(µs on the 1 MHz timer)<br/>[ROM:$F168 CalcInjOffTime]"]
  OFF --> INJ["#10 on P4-7 (software)<br/>#20 on OC2 / P1-1<br/>grouped, not simultaneous<br/>[ROM:$F138, $F154, $F196]"]
  CUT["decel cut: lilRPM ≥ DecelCutRPM (table $FEE2 vs ThW)<br/>→ enrichment halved / cut<br/>[ROM:$F666–$F671]"] -.-> MIX
```

Notes:
- **`Calc72` arithmetic** [ROM:$F6FC–$F709]: it stores the input in `word_72`, then returns `(2·x·ThAcorr/256 + 3x) / 4`. That is a blend, not a pure multiplication: three quarters of the value passes through unchanged. The test `tests/test_fuel_chain.py` checks this formula in the emulator.
- **The multiplier loop** [ROM:$F6A8–$F6B1] adds `word_72` to itself `word_D3` times. `word_D3` is 1 plus the summed enrichments, so the enrichments act as a **multiplier on the base ratio**. That matches Ross's "everything after the base is a correction factor" (R-F02).
- `FuelRatioH` is the larger of the corrected ratio and the coolant floor `word_70` [ROM:$F6D8–$F6DE]. So a cold engine can never run leaner than the warm-up floor.

### Warm-up numbers

Realistic warm-up and after-start numbers come from the whole-ROM simulation: [`warmup_sim.md`](warmup_sim.md) [EMU:sim].
- **Steady warm-up fuel:** 2.0× warm at −10 °C, 1.7× at 0 °C, gone by about 60 °C.
- **After-start boost:** on top of that, bleeding off over a fixed number of revolutions (about 33 s at 1000 rpm from 0 °C).
- **Extra cold advance:** about +10° at idle.

An earlier routine-level experiment (running `loc_F534` alone) gave 2.5× at 0 °C. It is superseded, because the diagnostic routine that sets `byte_83`/`byte_8B` did not run.

## 2. Ignition chain

```mermaid
flowchart TD
  TEST{"T terminal shorted (P4-5 low)<br/>or forced?"} -->|yes| FIX["fixed advance $1C = 10° BTDC<br/>[ROM:$F814–$F826]"]
  TEST -->|no| IDL{"throttle closed?<br/>byte_95 bit 7"}
  IDL -->|yes| IDLE["idle advance: $2D (+$0E with A/C, +$0E at low load)<br/>+ IDLcompADV = idle-stability term<br/>(IdleRPMfilt − IdleRPMs) × $88<br/>[ROM:$F82C–$F857]"]
  IDL -->|no| MAP3["3D map $FF40: 6 load rows × 14 rpm columns<br/>[EMU:test_3d_ignition_lookup]"]
  MAP3 --> TVIS{"TVIScounter ≥ 0?<br/>(T-VIS off)"}
  TVIS -->|yes| TV8["+8 (≈3°)"] --> PWR
  TVIS -->|"no (T-VIS open)"| PWR["PWRr trim (table $FF94)<br/>[ROM:$F8A5]"]
  PWR --> SUM
  IDLE --> SUM
  WU["ThW_tADV: warm-up advance from coolant<br/>(min 28; 15 when overheating)<br/>[ROM:$FC1E]"] --> SUM
  SUM["BaseAdvance + ThW_tADV + IDLcompADV<br/>clamped to $1F–$B8 (≈11°–65°), then −$1C<br/>[ROM:$F8CD–$F8EE]"] --> US["convert to µs from the NE period<br/>(deltaNE, referenced to the NE edge at 10° BTDC)<br/>→ AdvanceinUS, Dwell<br/>[ROM:$F8F0–$F92B]"]
  US --> IGT["OC1 → IGT"]
```

**Raw → degrees:** the clamp comments and the T-terminal value ($1C = 10° BTDC, matching the factory "10° BTDC with T–E1 shorted") point to **degrees ≈ raw × 90/256** before the −$1C offset. LIKELY; this feeds R-I06 / STATUS Q3. It needs a bench check: Zero timing meter against IGT (P8).

### In tuning terms

- **Fuel:** the Bluetop builds fuel from an airflow measurement times a "ratio". The ratio carries all the corrections: air temperature, coolant warm-up floor, after-start, acceleration, O2 trim. There is no rpm × load VE table; the airflow meter does that job. The MR2's speed-density ROM will differ here (density and speed maps, per Ross).
- **Ignition:** a conventional rpm × load map that only applies off idle. At idle the spark is a fixed value plus an idle-stability term that adds advance when rpm drops. Warm-up advance and a T-VIS step are added on top. That idle-stability loop is the ECU's only active idle control, which matters for goal 1.
