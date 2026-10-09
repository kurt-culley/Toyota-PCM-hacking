# Ross's ECU logic as diagrams (P1)

These diagrams show **what Ross says** the 89661-17030 (mk1a) ECU does, in the order he describes it ([PDF] *Lifting the Lid*, parts 2–4). Every box carries the claim IDs from [`claims.md`](claims.md).
- **Nothing here is verified yet.** P2 (Bluetop) and P4 (17140 ROM) check each box against the code. A box is redrawn when the ROM disagrees, and the difference is logged in [`../STATUS.md`](../STATUS.md).
- Digitised data for the maps is in [`figures/`](figures/README.md).
- **Bench finding (17140):** Ross's secret-map "logic level" is most likely the factory jumper pair on **P32/P34** ([`../hardware/aw11_ecu.md`](../hardware/aw11_ecu.md)).

## 1. Fuel chain (warm engine) [PDF p2–p10]

Every map after the density map is a correction to its 16-bit base value (R-F02). The final number is the injector pulse width in µs (R-F23).

```mermaid
flowchart TD
  MAP["MAP sensor (PIM)"] --> DSEL{"rpm < 3200?<br/>R-F04"}
  NE["rpm (NE)"] --> DSEL
  DSEL -->|yes| D1["Density map &lt;3200<br/>11 sites, 16-bit<br/>R-F03 R-F05"]
  DSEL -->|no| D2["Density map &gt;3200<br/>11 sites, 16-bit<br/>R-F03 R-F05"]
  D1 --> S1["× speed correction &lt;3200<br/>(−15 % … +11 %)<br/>R-F06 R-F08"]
  D2 --> S2["× speed correction &gt;3200<br/>(−10 % … +8 %)<br/>R-F06 R-F07"]
  S1 --> HD
  S2 --> HD{"high load AND<br/>rpm well above idle?"}
  HD -->|yes| HDM["× hard-driving map<br/>staircase, no interpolation<br/>R-F09 R-F10"]
  HD -->|no| THA
  HDM --> THA["× air-temperature (THA) correction<br/>straight line<br/>R-F11"]
  THA --> SEC{"secret logic level set?<br/>(17140: P32/P34 jumpers?)"}
  SEC -->|"no (stock: always skipped)"| GCF
  SEC -->|yes| SECM["× secret rpm fuel map<br/>R-F12"] --> GCF
  GCF["× global correction factor (RAM)<br/>coolant warm-up + transient + 6300 rpm lift<br/>R-F13 R-F14 R-F15 R-F19"] --> MX{"rpm < 3600 AND<br/>light/medium load?<br/>R-F16 R-M04"}
  MX -->|yes| MXC["+ mixture screw:<br/>(screw − 128) × MX2(rpm) / 32000 ms<br/>R-M01 R-M02 R-M03"] --> VB
  MX -->|no| VB["+ injector dead time from battery voltage<br/>R-F17"]
  VB --> OUT["final 16-bit value = pulse width in µs<br/>R-F23"]
```

### Fuel cut and injection mode [PDF p9–p10]

```mermaid
stateDiagram-v2
  [*] --> Normal
  Normal: every revolution, all 4 injectors at once,<br/>half the fuel each (R-F21, R-F22)
  Doubled: every OTHER revolution, duration doubled,<br/>dead time not doubled (R-F24)
  Cut: injectors held off
  Normal --> Doubled: rpm ≥ 6000
  Doubled --> Normal: rpm < 6000
  Normal --> Cut: closed throttle on overrun from high rpm (R-F25)
  Normal --> Cut: rev limiter (R-F26)
  Normal --> Cut: several missed IGF confirmations (R-I16)
  Doubled --> Cut: rev limiter / IGF failure
  Cut --> Normal: throttle opened, rpm falls, or sparks confirmed
```

Factory return thresholds for the overrun cut on the 1988 US car: 1600 rpm cut, 1200 rpm return (A/C off). See [`../hardware/repair_manual_aw11_1988.md`](../hardware/repair_manual_aw11_1988.md).

## 2. Ignition chain [PDF p12–p16]

```mermaid
flowchart TD
  IDL{"throttle closed (IDL)?<br/>R-I07"} -->|"no: 'driven'"| SECI{"secret logic level set?"}
  SECI -->|"no (stock)"| BASE["Base 3D map 17 rpm × 8 MAP<br/>800–7200 rpm every 400, 8-bit, interpolated<br/>R-I02 R-I03 R-I04 R-I05"]
  SECI -->|yes| SECM["Secret 17×8 map<br/>R-I15"]
  IDL -->|yes| IDLE["Idle/overrun map<br/>3 sites: 1200/1600/2000 rpm<br/>above 2000 uses the 2000 site<br/>R-I07"]
  BASE --> WU
  SECM --> WU
  IDLE --> STAB["+ idle-stability step<br/>(closed throttle only)<br/>R-I13"] --> WU
  WU["+ warm-up advance (coolant only)<br/>R-I11"] --> HOT{"coolant over-temperature?<br/>R-I12"}
  HOT -->|yes| HOTM["over-temperature correction"] --> TV
  HOT -->|no| TV{"T-VIS open?<br/>R-I09 R-I10"}
  TV -->|"yes, after a short delay"| TVA["+ T-VIS advance step"] --> RAW
  TV -->|no| RAW["raw 8-bit advance<br/>(not degrees: R-I06)"]
  RAW --> IGT["IGT timing → igniter; IGF echo checked<br/>R-I16"]
```

### T-VIS switching [PDF p15]

Ross's figures, mk1a first, then mk1b. The 1984 EWD and the 1988 repair manual both give 4350 rpm.

```mermaid
stateDiagram-v2
  [*] --> Closed
  Closed --> Open: rpm > 4350 (mk1a) / 4650 (mk1b)
  Open --> Closed: rpm < 3950 (mk1a) / 4250 (mk1b)
  Open: VSV energised via S/TH,<br/>ignition step after a short delay (R-I09)
```

### Idle stability [PDF p15]

```mermaid
stateDiagram-v2
  [*] --> Steady
  Steady --> Kick: closed throttle AND rpm dips
  Kick: sudden extra advance<br/>(maximum amount is a map value)
  Kick --> Decay: rpm recovered
  Decay: extra advance decays<br/>at the mapped rate
  Decay --> Steady: back to the map value
  Decay --> Kick: rpm dips again
```

**In tuning terms:** this is the ECU's only closed-loop idle control on a UK car (no ISC valve, no O2 sensor). Idle speed is held by snapping the spark forward when rpm drops, then easing it back. It matters for goal 1: with the IACV removed there is less idle air, so this loop works harder on a cold engine. P5 measures how far it can compensate.

## 3. Mixture screw [PDF p17–p18]

```mermaid
flowchart LR
  ADC["screw resistor → 8-bit reading<br/>(17140: different ECU pin, R-M08)"] --> END{"within one slot-width<br/>of either end stop?<br/>R-M06"}
  END -->|yes| ZERO["MX1 = 0<br/>('get you home')"]
  END -->|no| MX1["MX1 = reading − 128<br/>R-M01"]
  RPM["rpm"] --> MX2["MX2 map: 128 @ 1000 rpm → 64 @ 3600<br/>17070: flat 128<br/>R-M02 R-M09"]
  MX1 --> MUL["Δ pulse width (ms) = MX1 × MX2 / 32000<br/>R-M03"]
  ZERO --> MUL
  MX2 --> MUL
  MUL --> GATE{"rpm < 3600 AND<br/>light/medium load?<br/>R-M04"}
  GATE -->|yes| ADD["added to the fuel pulse"]
  GATE -->|no| IGN["ignored"]
```

## 4. Cold start and warm-up as Ross describes it [PDF p14–p15]

Ross says little about cold start; goal 1 (P5) fills this in from the ROM. This is the starting picture, with the factory-manual evidence added.

```mermaid
flowchart LR
  subgraph Mechanical["Not ECU-controlled"]
    WAX["wax air-bleed valve (IACV)<br/>~2000 rpm cold → 1000 warm<br/>R-I08"]
    CSI["cold start injector<br/>via start-injector time switch<br/>(1984 EWD, 1988 RM)"]
  end
  subgraph ECU["ECU-side (to be traced in the ROM)"]
    GCFW["warm-up fuel in the global correction<br/>R-F13"]
    WUA["warm-up ignition advance<br/>R-I11"]
    STABE["idle-stability spark<br/>R-I13"]
    VISC["start-up idle-up via VISC?<br/>(1988 US: cranking + 10 s; 17140 open, STATUS Q2)"]
  end
  THW["coolant temp (THW)"] --> GCFW
  THW --> WUA
  STA["starter (STA)"] --> VISC
```
