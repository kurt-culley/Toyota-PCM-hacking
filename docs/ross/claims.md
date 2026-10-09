# Ross "Lifting the Lid" claim register

Source: [`Lifting The Lid on the mk1 MR2 ECU (Jeremy Ross).pdf`](../../Lifting%20The%20Lid%20on%20the%20mk1%20MR2%20ECU%20%28Jeremy%20Ross%29.pdf). The PDF has 18 pages and contains Parts 2–4 of the series. Part 1 is not in the repo.

Every factual claim in the PDF is listed here so it can be checked against ROM code, the emulator, or bench measurements. The process is set out in [`../RE_PLAN.md`](../RE_PLAN.md) under phases P1, P2 and P4. Each claim cites the PDF page it comes from (`pN`, using the PDF viewer's page number).

## Legend

| Column | Meaning |
|---|---|
| **ECU** | The ECU the claim refers to. `17030` = UK mk1a, `17140` = UK mk1b, `17070` = other mk1, `UK` = UK mk1 in general. |
| **Tier** | `A` = how the ECU works (strategy or structure). Likely shared with the AE86 Bluetop, so it can be checked on `cap.bin` now. `B` = a calibration value or threshold specific to that ECU, which needs the MR2 ROM. `C` = only settled by a bench or car measurement. `X` = opinion or speculation with nothing to check. Ross's own view is noted for context. |
| **Test on** | Where the claim can be checked: `Bluetop`, `MR2 ROM`, `Bench`, `Car` or `—`. |
| **Status** | `PENDING` → `CONFIRMED` / `CONTRADICTED` / `PARTIAL` / `DIFFERS-BY-ECU` / `NOT-APPLICABLE` (for example the Bluetop is L-type, not D-type). Every change of status needs an evidence tag such as `[ROM:$xxxx]`, `[EMU:test]` or `[BENCH:file]`. |

## Fuel (Part 2)

| ID | Claim | Page | ECU | Tier | Test on | Status | Evidence / notes |
|---|---|---|---|---|---|---|---|
| R-F01 | The UK mk1 uses speed-density (D-type) EFI with a MAP sensor and no airflow meter | p2 | UK | A | MR2 ROM | PENDING | The Bluetop is L-type (`SE056` pulse), so this claim is NOT-APPLICABLE to the Bluetop. |
| R-F02 | Fuel comes from a chain of lookup tables. The density map gives a **16-bit base value**, and every later map is a correction factor applied to it | p4–p5 | 17030 | A | Bluetop, MR2 ROM | PENDING | |
| R-F03 | The density map is 2D (MAP → fuel), nearly linear, with **11 sites**. Site 11 is the smallest pressure drop (WOT) | p4 | 17030 | B | MR2 ROM | PENDING | Figure p4: digitise it. |
| R-F04 | There are two density maps, one used **below 3200 rpm** and one above | p4 | 17030 | B | MR2 ROM | PENDING | |
| R-F05 | Near maximum MAP the density map bumps upward, giving slight over-fuelling (Ross thinks this is engine protection) | p4 | 17030 | B | MR2 ROM | PENDING | |
| R-F06 | There are two rpm ("speed") correction maps, split at 3200 rpm and paired with the density maps | p5 | 17030 | B | MR2 ROM | PENDING | |
| R-F07 | The >3200 rpm speed correction ranges from **−10 % to +8 %** and passes through zero at about **5200 rpm**. It has a small peak near 4000 rpm and a dip after it | p5 | 17030 | B | MR2 ROM | PENDING | Figure p5: digitise it. |
| R-F08 | The <3200 rpm speed correction leans out markedly **below 900 rpm** | p5 | 17030 | B | MR2 ROM | PENDING | Figure p5. |
| R-F09 | A hard-driving rpm correction applies only at high load and rpm well above idle. Its sites are 1800/2600/3000/6200/6450/6650/>6650 rpm | p6 | 17030 | B | MR2 ROM | PENDING | |
| R-F10 | The hard-driving map **does not interpolate** (it is a staircase). It adds about +2 % at 2000 rpm and about −7.5 % above 6650 rpm | p6 | 17030 | A/B | Bluetop, MR2 ROM | PENDING | The lack of interpolation is checkable as table-lookup code (Tier A). The values need the MR2 ROM. |
| R-F11 | An air-temperature (THA) correction follows, and it is a straight line | p6 | 17030 | B | MR2 ROM | PENDING | Ross doubted his own THA sensor calibration. Cross-check with Zero sensor characterisation. |
| R-F12 | A **secret** rpm fuel correction map exists. Stock code always jumps over it. A "logic level inside the ECU" enables it, and the same level selects an alternative 3D ignition map | p6 | 17030 | A/B | Bluetop, MR2 ROM | PENDING | Goal 2. See also R-I15. Candidate hardware: the J1–J10 jumpers by IC7 (J3/J4 fitted), see [`aw11_ecu.md`](../hardware/aw11_ecu.md). Jumper correction: **two links among J3/J4/J8**; which label owns which is settled by the continuity test (Test A). **BENCH 2026-10-09:** the 17140 has factory jumper pairs on **P32** (J4 to ground, fitted; J9 to node N) and **P34** (J8 to node N, fitted; J3 to ground). These Port 3 option bits are the prime candidates for the 'logic level'. Next: find the ROM's reads of Port 3 bits 2 and 4. |
| R-F13 | Next a **global correction factor** from RAM is applied. It is computed elsewhere and combines coolant (warm-up), transient throttle and a high-rpm/high-load/high-throttle enrichment | p7 | 17030 | A | Bluetop, MR2 ROM | PENDING | |
| R-F14 | The high-rpm part of the global correction cuts in at **6300 rpm** and adds a fixed richening offset | p7 | 17030 | B | MR2 ROM | PENDING | |
| R-F15 | The global correction drops once throttle falls below about two-thirds | p8 | 17030 | B | MR2 ROM | PENDING | |
| R-F16 | Mixture-screw correction applies only **below 3600 rpm** and at light-to-medium load | p7, p17 | 17030, 17140 | B | MR2 ROM | PENDING | |
| R-F17 | Voltage (battery) correction for injector dead time is applied last. Dead time in µs rises as voltage falls | p7 | 17030 | A/B | Bluetop, MR2 ROM | PENDING | The Bluetop has `InjDeadTime` and `ADC_12V`. Figure p7: digitise it. EWD 1984: ECU pin **BF (N-6)** reads the injector supply after the INJ fuse, a LIKELY battery-voltage input for this correction. |
| R-F18 | Ross's 8086 port of the fuel code plus 2nd-gear WOT logs agree in shape: a peak at 4000 rpm and odd fuelling above 6000 rpm | p7–p8 | 17030 | C | Car | PENDING | Reproduce with our emulator, then a car log. |
| R-F19 | Snapping the throttle open gives a brief large rise in the global factor (an acceleration enrichment "spurt") | p9 | 17030 | A | Bluetop, MR2 ROM | PENDING | |
| R-F20 | Typical injector pulse width is 1.5–7 ms. It is about 1.6 ms at warm idle and about 3 ms at 3500 rpm, light to medium load | p9, p17 | UK | C | Bench, Car | PENDING | |
| R-F21 | UK mk1 injection is **simultaneous**: all four injectors fire every revolution, each with half the fuel | p9 | UK | A/C | MR2 ROM, Bench | PENDING | |
| R-F22 | The two injector output pins are **strapped together inside the ECU** (one driver transistor). Some JDM and US variants may use grouped injection | p9 | UK | C | Bench (PCB inspection) | PENDING | The 17140 board has separate `#10`/`#20` pins and a single large Toshiba 2SD1678 driver transistor (T07), consistent with the claim. Trace #10/#20 to confirm. Unpopulated T20–T23 may be the grouped-injection option. [`aw11_ecu.md`](../hardware/aw11_ecu.md) **EWD 1984** [p22–23]: the harness has two injector groups (No.1+3 on #10, No.2+4 on #20), consistent with internal strapping. [`ewd_aw11_1984.md`](../hardware/ewd_aw11_1984.md) |
| R-F23 | The final 16-bit fuel value **equals the injector pulse width in µs** (1 MHz timer) | p9 | UK | A/C | Bluetop, Bench | PENDING | Bluetop: E clock and timer prescale. Bench: Zero timing meter. |
| R-F24 | **Above 6000 rpm** injection switches to every other revolution with the duration doubled, but the dead-time correction is **not** doubled | p9–p10 | 17030, 17140 | A/B | Bluetop, MR2 ROM, Bench | PENDING | |
| R-F25 | Fuel is cut on closed-throttle overrun from high rpm (decel fuel cut) | p10 | UK | A | Bluetop, MR2 ROM | PENDING | The Bluetop has `DecelCutRPM`. **RM 1988** [FI-128]: factory fuel cut **1600 rpm** (A/C off) / 1900 (A/C on), return **1200** / 1500 rpm, warm engine with IDL shorted. US calibration, so it is a cross-check value for the 17140 ROM, not proof. |
| R-F26 | Fuel is also cut at the rev limiter | p10 | UK | A/B | Bluetop, MR2 ROM | PENDING | `TOYOTA Bluetop PCM/notes.txt` gives about 7400 rpm for the Bluetop. |
| R-F27 | Speed-density cannot compensate for cam or exhaust changes. Intake mods upstream of the throttle are mostly handled | p10 | — | X | — | PENDING | Engineering opinion. |

## Ignition (Part 3)

| ID | Claim | Page | ECU | Tier | Test on | Status | Evidence / notes |
|---|---|---|---|---|---|---|---|
| R-I01 | Engine speed comes from igniter/distributor pulses. Load for ignition comes from the MAP sensor | p12 | UK | A | MR2 ROM | PENDING | |
| R-I02 | The base ignition map is 3D, **17 rpm × 8 MAP** sites (136 bytes, 8-bit). A larger value means more advance | p12–p13 | 17030 | A/B | Bluetop, MR2 ROM | PENDING | Bluetop `lookup3dTable` uses a 14-byte stride ([`cap.asm`](../../TOYOTA%20Bluetop%20PCM/cap.asm) near `$F863`), so it has a different shape. |
| R-I03 | The rpm sites run every 400 rpm from **800 to 7200 rpm** | p12 | 17030 | B | MR2 ROM | PENDING | |
| R-I04 | Example value: MAP site 6, 4000 rpm → 128. At 4400 rpm → 132 | p13 | 17030 | B | MR2 ROM | PENDING | Figure p13: transcribe the full table. |
| R-I05 | The ignition map **interpolates** in both rpm and MAP | p14 | 17030 | A | Bluetop, MR2 ROM | PENDING | Bluetop: `sub_FF35` "finish 3d interpolation". |
| R-I06 | Stored values are raw 8-bit numbers, not degrees. The degrees graph on p16 assumes a conversion Ross does not give | p13, p16 | 17030 | C | Bench | PENDING | The ~50° maximum is disputed in upstream issue #6. Settle with a Zero timing meter capture of IGT vs NE/G. **RM 1988** [IG section]: base timing **10° BTDC at idle with T–E1 shorted**. This is a fixed reference that any raw → degrees conversion must reproduce. |
| R-I07 | The base map is used only when the throttle is open ("driven"). With the throttle closed a small **idle map** is used, with 3 rpm sites (1200/1600/2000) and no load axis. On overrun the 2000 rpm value is used | p14 | 17030 | A/B | Bluetop, MR2 ROM | PENDING | |
| R-I08 | Cold high idle (about 2000 rpm falling to 1000) comes from the **wax air-bleed valve** in the throttle body, not from the ECU | p14 | UK | A/C | MR2 ROM, Car | PENDING | **Key for goal 1** (IACV removal). The 17140 board has `VISC` and `?TH` (STJ?) pins, so ECU involvement in idle air or the CSI must be ruled out. See STATUS Q2. **EWD 1984** [p16–17, p28–29]: the CSI is wired starter → CSI → time switch with no ECU connection, and the idle-up VSV is switched by the loads (ECU senses it on I/UP). The board's `?TH` is actually **STH = S/TH (T-VIS)**. Supports the claim; LIKELY for the 17140 until Test B. **RM 1988** [FI-119]: on the US 4A-GE the ECU **drives** the idle-up VSV from `V-ISC` during cranking and for 10 s after start, and the 17140 board has a `VISC` pad. The wax valve part of the claim still holds (FI-108), but ECU start-up idle air is **open** for the 17140 (STATUS Q2). |
| R-I09 | When TVIS opens, ignition steps in advance after a short delay | p15 | 17030 | A | Bluetop, MR2 ROM | PENDING | Bluetop: `TVIScounter`, `PWRrAdv`. |
| R-I10 | TVIS opens at 4350 rpm and closes at 3950 rpm (mk1a). On the mk1b it opens at **4650** and closes at **4250** rpm | p15 | 17030, 17140 | B | MR2 ROM | PENDING | **EWD 1984** [p25]: S/TH (M-18) reads 0–2 V at idle and 10–14 V **above 4350 rpm**. Independent factory evidence for the mk1a opening point; the mk1b 4650/4250 figures still need the ROM. **RM 1988** repeats S/TH above 4350 rpm. |
| R-I11 | A coolant-only **warm-up advance** map adds to the base map: large when cold, decaying to a small constant when warm | p15 | 17030 | A/B | Bluetop, MR2 ROM | PENDING | Bluetop: `ThW_tADV`. Goal 1. |
| R-I12 | An **over-temperature** correction map switches in when coolant is hotter than normal | p15 | 17030 | A/B | Bluetop, MR2 ROM | PENDING | |
| R-I13 | Idle stability: with the throttle closed, an rpm dip triggers a step of extra advance that decays away. Attack, decay and maximum are stored as calibration values | p15 | 17030 | A/B | Bluetop, MR2 ROM | PENDING | Bluetop: `IdleADVcomp`, `IdleRPMs`, `IdleRPMfilt`. Goal 1. |
| R-I14 | There is no self-learning (no O2 sensor). Only fault codes are remembered in RAM | p15 | UK | A | MR2 ROM | PENDING | NOT-APPLICABLE to the Bluetop, which has `ADC_Oxy`. |
| R-I15 | Secret mode replaces the whole base map with a second **17×8** 3D ignition map | p15 | 17030 | A/B | MR2 ROM | PENDING | Pairs with R-F12. **BENCH 2026-10-09:** the 17140 has factory jumper pairs on **P32** (J4 to ground, fitted; J9 to node N) and **P34** (J8 to node N, fitted; J3 to ground). These Port 3 option bits are the prime candidates for the 'logic level'. Next: find the ROM's reads of Port 3 bits 2 and 4. |
| R-I16 | After each spark the ECU checks the IGF echo. After **several** failed sparks it cuts the injectors, even though the UK car has no catalytic converter | p15–p16 | UK | A/B | Bluetop, MR2 ROM, Bench | PENDING | |
| R-I17 | Toyota/Denso "softened" a dyno-optimal map for fuel quality and tolerances | p14 | — | X | — | PENDING | Opinion. |

## Mixture screw (Part 4)

| ID | Claim | Page | ECU | Tier | Test on | Status | Evidence / notes |
|---|---|---|---|---|---|---|---|
| R-M01 | The mixture screw is a variable resistor read as an 8-bit value. **MX1 = reading − 128** | p17 | 17030, 17140 | B | MR2 ROM | PENDING | |
| R-M02 | An rpm map gives **MX2**, which is about 128 at 1000 rpm and about 64 at 3500 rpm. It is identical on 17030 and 17140 | p17 | 17030, 17140 | B | MR2 ROM | PENDING | Figure p17: digitise it. |
| R-M03 | Change in injector time (ms) = **MX1 × MX2 / 32000** | p17 | 17030, 17140 | B | MR2 ROM | PENDING | Find the multiply/divide routine. "32000" is probably an approximation of a binary scaling such as 32768. |
| R-M04 | Not applied above about **3600 rpm** or at high load | p16–p17 | 17030, 17140 | B | MR2 ROM | PENDING | Same as R-F16. |
| R-M05 | Turning the screw clockwise richens the mixture on the 17140 | p16 | 17140 | C | Car | PENDING | |
| R-M06 | **"Get you home" behaviour:** within about one slot-width of either end stop, the ECU ignores the screw and uses a correction of exactly 0 | p18 | 17140 | B | MR2 ROM | PENDING | Look for range checks on the ADC value. |
| R-M07 | The zero position is "fully anticlockwise, then just over ¼ turn" (photo) | p18 | 17140 | C | Car | PENDING | |
| R-M08 | The 17140 reads the screw on a **different ECU pin** from the 17030/17070, so the ECUs are not fully interchangeable | p18 | 17030, 17070, 17140 | B/C | MR2 ROM, Bench | PENDING | Look for an ADC channel or port difference. A 17030 dump is needed for a full check. **EWD 1984** [p24]: the mixture screw is the 5 kΩ "CO control resistor" on **VAF (L-14)**. The 17140 board has **no VAF label** but does have `OX`, which supports the claim. Hypothesis: OX carries it on the 17140 (Test B, STATUS Q8). |
| R-M09 | The 17070's MX2 map is flat (128) up to about 3800 rpm | p18 | 17070 | B | 17070 ROM | PENDING | Needs a 17070 dump. Record in `docs/variants.md`. |

## Figures to digitise (P1)

These are the 16 embedded images, extracted with `pdfimages -list`. Digitised data goes in `docs/ross/figures/` as one CSV per figure, next to the extracted PNG.

| Page | Expected content | Linked claims |
|---|---|---|
| p4 | Density map (MAP vs fuel) | R-F03, R-F05 |
| p5 (×2) | Speed correction >3200 and <3200 rpm | R-F07, R-F08 |
| p6 (×2) | Hard-driving map and THA correction | R-F09, R-F10, R-F11 |
| p7 | Voltage / dead-time curve | R-F17 |
| p8 (×2) | Emulator output and datalog | R-F18 |
| p9 | Fuel value → pulse illustration | R-F23 |
| p12 | 17×8 ignition table (raw values) | R-I02–R-I04 |
| p13 | Ignition curves per MAP column | R-I02 |
| p14 (×2) | 3D surface and idle ignition map | R-I05, R-I07 |
| p16 | Ignition in degrees BTDC | R-I06 |
| p17 | MX2 vs rpm | R-M02 |
| p18 | Mixture-screw zero position photo | R-M07 |

The mapping is **confirmed** (2026-10-09), and the data is in [`figures/`](figures/README.md). One correction: p9 (img08) is a Toyota manual excerpt, not Ross's own figure.
