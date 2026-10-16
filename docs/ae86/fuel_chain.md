# Bluetop fuel and ignition chains

## Summary

The Bluetop calculates the injector pulse as the airflow pulse time multiplied by a ratio, `FuelRatioH`. All fuel corrections act on that ratio. The spark advance comes from a 3D map (rpm × load) off idle, and from a fixed value plus an idle-stability term at idle. The figures use the layout of the Ross 17030 diagrams ([Ross diagrams](../ross/diagrams.md)), so that you can compare them box by box with the 17140.

<details>
<summary>Confidence</summary>

- The structure (which variable goes into which) comes from the code [ROM].
- The simulator proves the table lookups and the helper arithmetic [EMU].
- Physical meanings are LIKELY or GUESS, as each item shows.
- The Bluetop is **L-type** (airflow meter). Thus its base fuel is an airflow pulse time, not a value from MAP.

</details>

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
  OFF --> INJ["#10 on P47 (software)<br/>#20 on OC2 / P11<br/>grouped, not simultaneous<br/>[ROM:$F138, $F154, $F196]"]
  CUT["decel cut: lilRPM ≥ DecelCutRPM (table $FEE2 vs ThW)<br/>→ enrichment halved / cut<br/>[ROM:$F666–$F671]"] -.-> MIX
```

- **`Calc72` arithmetic** [ROM:$F6FC–$F709]: it stores the input in `word_72` and returns `(2·x·ThAcorr/256 + 3x) / 4`. This is a blend, not a pure multiplication: three quarters of the value goes through with no change. CONFIRMED [EMU:tests/ae86/test_fuel_chain.py::test_calc72_matches_emulator, ::test_calc72_is_a_blend_not_a_pure_multiply].
- **The multiplier loop** [ROM:$F6A8–$F6B1] adds `word_72` to itself `word_D3` times. `word_D3` is 1 plus the sum of the enrichments. Thus the enrichments are a **multiplier on the base ratio**. This agrees with Ross R-F02: each value after the base is a correction factor. CONFIRMED.
- **The coolant floor:** `FuelRatioH` is the larger of the corrected ratio and the coolant floor `word_70` [ROM:$F6D8–$F6DE]. Thus a cold engine never gets less fuel than the warm-up floor. CONFIRMED.

### Warm-up values

These values come from the whole-ROM simulator at 1000 rpm, after the after-start enrichment decays [EMU:tests/ae86/test_sim.py::test_warm_up_fuel_and_cold_advance]. CONFIRMED in the simulator.

- **Steady warm-up fuel:** 1.7 × the warm ratio at 0 °C. At 60 °C no warm-up fuel is left.
- **After-start enrichment:** an addition on top of the warm-up fuel. It decreases on each pass and is zero after 40 s at 0 °C.
- **Cold advance:** `ThW_tADV` is 56 at 0 °C and 28 warm. The difference of 28 raw is about +10°.

## 2. Ignition chain

```mermaid
flowchart TD
  TEST{"T terminal shorted (P45 low)<br/>or forced?"} -->|yes| FIX["fixed advance $1C = 10° BTDC<br/>[ROM:$F814–$F826]"]
  TEST -->|no| IDL{"throttle closed?<br/>byte_95 bit 7"}
  IDL -->|yes| IDLE["idle advance: $2D (+$0E with A/C, +$0E at low load)<br/>+ IDLcompADV = idle-stability term<br/>(IdleRPMfilt − IdleRPMs) × $88<br/>[ROM:$F82C–$F857]"]
  IDL -->|no| MAP3["3D map $FF40: 6 load rows × 14 rpm columns<br/>[EMU:test_3d_ignition_lookup]"]
  MAP3 --> TVIS{"TVIScounter ≥ 0?<br/>(T-VIS open, above 4350 rpm)"}
  TVIS -->|yes| TV8["+8 (≈3°)"] --> PWR
  TVIS -->|"no (T-VIS shut)"| PWR["PWRr trim (table $FF94)<br/>[ROM:$F8A5]"]
  PWR --> SUM
  IDLE --> SUM
  WU["ThW_tADV: warm-up advance from coolant<br/>(min 28; 15 when overheating)<br/>[ROM:$FC1E]"] --> SUM
  SUM["BaseAdvance + ThW_tADV + IDLcompADV<br/>clamped to $1F–$B8 (≈0.2°–54° BTDC), then −$1C<br/>[ROM:$F8CD–$F8EE]"] --> US["convert to µs from the NE period<br/>(deltaNE, referenced to the NE edge at 10° BTDC)<br/>→ AdvanceinUS, Dwell<br/>[ROM:$F8F0–$F92B]"]
  US --> IGT["OC1 → IGT"]
```

**Raw → degrees:** the clamp comments and the T-terminal value give **degrees ≈ raw × 90/256** before the −$1C offset. The T-terminal value is $1C = 10° BTDC, the factory value "10° BTDC with T–E1 shorted". LIKELY. The [simulation](simulation.md) gives the full formula. A bench capture of IGT against the crank must confirm it (R-I06, [open items](../project/open_items.md) Q3).

### In tuning terms

- **Fuel:** the Bluetop calculates fuel as an airflow measurement multiplied by a ratio. The ratio contains all the corrections: air temperature, the coolant warm-up floor, after-start, acceleration and O2 trim. There is no rpm × load VE table, because the airflow meter does that work. The 17140 is speed-density, so it uses density and speed maps instead ([17140 program](../mr2/program.md)).
- **Ignition:** a conventional rpm × load map that applies only off idle. At idle the spark is a fixed value plus an idle-stability term. This term adds advance when the rpm decreases. The warm-up advance and a T-VIS step are added to the result. The idle-stability loop is the only active idle control of the ECU. Thus it is important for a cold idle with less idle air.
