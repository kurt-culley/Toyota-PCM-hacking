# Test ECU: Toyota 89661-17140 (UK mk1b MR2, 4A-GE)

This record comes from the owner's photos (2026-10-09, two sets) in [`photos/89661-17140/`](photos/89661-17140/), and from the factory wiring diagram summarised in [`ewd_aw11_1984.md`](ewd_aw11_1984.md). Each claim carries a confidence tag, as set out in [`../RE_PLAN.md`](../RE_PLAN.md).

## Identification

| Item | Value | Confidence | Evidence |
|---|---|---|---|
| Toyota part number | **89661-17140** | CONFIRMED | Case label ([01](photos/89661-17140/01-case-label.jpg)) |
| Denso part number | **175700-1043**, 12 V, "4A-G" | CONFIRMED | Case label |
| Connectors | 10P + 18P + 14P | CONFIRMED | Case label |
| PCB number | **175731-0460**, revision **A2** | CONFIRMED | [21](photos/89661-17140/21-pcb-number-175731-0460.jpg) |
| Build date stamp | **S63.11.30** = Showa 63 = **30 Nov 1988** | LIKELY | Sticker top right ([02](photos/89661-17140/02-board-overview.jpg)) |

## Main microcontroller: answers open question Q1

| Item | Value | Confidence |
|---|---|---|
| Reference | **IC7**, silkscreen **"6356/6801"** | CONFIRMED |
| Marking | **D151801-7110**, F356-1400, 8L1802 | CONFIRMED ([07](photos/89661-17140/07-ic7-mcu-jumpers.jpg)) |
| Package | **40-pin DIP**, 20 pins per side counted from a crop of photo 07. Soldered directly to the board, not socketed | CONFIRMED |
| Family | **HD6301/6801-type, the same D151801 family as the AE86 Bluetop** (D151801-0642). The silkscreen names the 6801/6356 footprint, and the package matches | LIKELY. Becomes CONFIRMED when the reader runs code on it |
| Crystal | "400IDK8Z": **4.00 MHz**, giving E = 1 MHz. This fits Ross's "1 µs timer = injector µs" (claim R-F23) | LIKELY |

**What this means for the plan:** P3 follows the **HD6301 path**. The [§6a RP2350 reader](../RE_PLAN.md#6a-rp2350-rom-reader-p3) and the Bluetop reader method both apply. The Toshiba 8X branch (Redtop/1UZ tooling) is not needed. The ROM size is still to be confirmed: the Bluetop's is 4 KB at `$F000`, and the D151801 variants may differ.

## Other ICs

| Ref | Marking | Likely function | Confidence |
|---|---|---|---|
| IC1 | **D151831-0430** (Denso hybrid SIP, "8-51") | Custom Denso module next to the MCU and crystal. Possibly the reset/watchdog/power-supervisor hybrid; the Bluetop code toggles a watchdog pin | GUESS |
| IC2 | **HC151 12H20** (Denso hybrid SIP) | Near the injector/ignition pins. Possibly the input conditioning or output driver hybrid | GUESS |
| IC5 | **HC120 1J07** (Denso hybrid SIP) | Near +B/BATT and the regulator area. Possibly the 5 V regulator/power hybrid | GUESS |
| IC6 | **ND MF176 12H15A** (Denso DIP-24) | Very likely the **serial ADC**. The Blacktop uses a Denso "MP499" 24-pin DIP ADC, and the Bluetop code reads its ADC over a serial link (`ADCcontrol`, `ADCRxData`) | LIKELY |
| IC3 | NEC **µPC177C** (silkscreen alternative: HA17901P) | Quad comparator (LM339/2901 class): conditioning for the NE/G/speed inputs | LIKELY |
| IC4 | Toshiba **TC4069UBP** | Hex inverter | CONFIRMED (marking) |
| T07 | Toshiba **2SD1678** power transistor, bolted to the case | A single high-current driver. Ross's claim R-F22 says **one transistor drives all four injectors**, with the #10 and #20 pins strapped together. This part is a strong candidate for that driver | GUESS. Trace #10/#20 to confirm |

## Connector-edge pin labels (silkscreen)

These were read from close-ups [09–18](photos/89661-17140/09-connector-labels-a.jpg). The order below follows the board, from the E01/E02 end:

`E02 E01 · #20 #10 · IGT STA · E1 ACT · FPU NSW · STH VISC · VF OX · E21 G− · NE G1 · IGF · IDL T · VCC THA · VTA PIM · E2 THW · L2 L1 · L3 · SPD ECT · A/C FC · EGW CCO · W BATT · +B +B1`

The table maps each label to the factory wiring diagram ([`ewd_aw11_1984.md`](ewd_aw11_1984.md), the 1984 edition). The 1984 pin numbers are shown for reference only; the 17140's own connector numbering is not confirmed yet.

| Board label | Meaning | 1984 EWD pin | Confidence (for the 17140) |
|---|---|---|---|
| E01, E02, E1, E2, E21 | Power, ECU and sensor grounds | N-5, N-10, N-7, M-10, M-16 | LIKELY |
| #10, #20 | Injector groups No.1+3 and No.2+4 | N-4, N-9 | LIKELY |
| IGT, IGF | Igniter trigger (output), spark confirmation (input) | M-8, M-5 | LIKELY |
| STA | Starter signal (input). The ECU's **only** cranking input | N-3 | LIKELY |
| **STH** | **S/TH: T-VIS VSV driver (output)**, switched above 4350 rpm on the mk1a. **Not** a cold-start terminal (earlier misread as "?TH/STJ") | M-18 | LIKELY |
| **VISC** | **V-ISC**: the ECU's idle-up VSV output, on during cranking and for 10 s after start, on the 1988 US car ([repair manual FI-119](repair_manual_aw11_1988.md)). The older reading, an I/UP-style sense input, is less likely | 1988 `V-ISC` (1984 M-9 I/UP?) | LIKELY (design); UK use open |
| VF | Feedback/CO check output to the service connector | M-17 | LIKELY |
| **OX** | The O2 input on other markets. The UK car has no O2 sensor, and the 1984 mixture-screw pin **VAF** is missing from this board, so OX **may carry the CO control resistor** on the 17140 (Ross R-M08) | (L-14 VAF) | GUESS |
| NE, G1, G− | Distributor pickups (G1 ≈ 1984 "G+") | M-15, M-6, M-7 | LIKELY |
| IDL, VTA, VCC | Throttle idle contact, throttle position, 5 V sensor supply | M-13, M-11, M-12 | LIKELY |
| T | Diagnostic test terminal (input) | M-4 | LIKELY |
| THA, THW, PIM | Air and coolant thermistors, vacuum (MAP) sensor | M-3, M-1, M-2 | LIKELY |
| SPD | Vehicle speed | L-12 | LIKELY |
| A/C | A/C switch signal from the A/C amplifier (input) | L-11 | LIKELY |
| FC | Fuel pump control (circuit opening relay) | L-4 | LIKELY |
| W | Check-engine (warning) lamp; 1988 RM spec 9–14 V with no fault, engine running | 1988 `W` (1984 L-9 DG) | LIKELY |
| BATT, +B, +B1 | Memory supply; main supply via the EFI main relay | L-2, L-8, L-1 | LIKELY |
| FPU | Low-side output for the fuel-pressure-up VSV (1988 hot-restart system, from STA/THW/THA) | 1988 `FPU` | LIKELY (design); probably unused on UK cars |
| ACT, NSW, L1–L3, ECT, EGW, CCO | A/C cut, neutral start, automatic-gearbox lines, EGR warning, ? Probably unused on the UK manual car | not in 1984 | GUESS |

**What this means for goal 1:** the factory wiring diagram shows the **cold start injector is wired to the start injector time switch, not the ECU**. The **idle-up VSV is switched by the electrical loads**, with the ECU only sensing it. The aux air valve is mechanical. So the framing hypothesis in `RE_PLAN.md` is supported for the 1984 car (STATUS Q2). **But** the [1988 repair manual](repair_manual_aw11_1988.md) shows a US-spec ECU that drives the idle-up VSV from `V-ISC` during cranking and for 10 s after start. Test B below decides which the 17140 does: an output transistor behind `VISC` means the ECU can command start-up idle air.

## Configuration jumpers next to the MCU: candidate for the "secret map" logic level

There is a row of jumper positions **J1–J10** between IC1 and IC7, labelled near the MCU's port pins ([07](photos/89661-17140/07-ic7-mcu-jumpers.jpg)):

| Jumper | State |
|---|---|
| **Two of J3 / J4 / J8** | **fitted** (wire links) |
| The other one of J3/J4/J8, and J5, J6, J7, J9, J10 | empty |
| J1, J2 (by the crystal) | empty |

**Correction (second photo set):** the first record said "J3 and J4 fitted". Each label sits *between* two rows of pads, so which label owns which link depends on how the photo is read. The straight-on photo [20](photos/89661-17140/20-ic7-jumpers-top-side.jpg) suggests **J4 and J8**; the earlier rotated photo was read as J3 and J4. **Test A below settles it.**

There are also test points **RT**, **RD**, **RS** and a resistor array **RA1**.

Ross says the secret fuel and ignition maps are selected by "a logic level inside the ECU" ([claims](../ross/claims.md) R-F12 and R-I15). Jumpers wired to MCU port pins are the obvious way Denso would set that level at the factory. **Hypothesis (GUESS):** one of J1–J10 sets the port bit that the code tests to choose the secret maps.

To check it:
1. Trace each jumper pad to its IC7 pin, using a continuity meter with the board unpowered.
2. In the ROM (P6), find which port bits are read once at start-up and switch table pointers.

Unpopulated positions **T20–T23** and **R536–R546** suggest more options for other markets, such as grouped injection or extra outputs.

## Board construction notes for P3 (MCU removal)

- IC7 is **soldered through-hole**, so 40 joints have to be desoldered. Use plenty of flux and braid or a desoldering pump, and don't overheat the pads. Afterwards, fit a turned-pin DIP-40 socket so the MCU can go back in.
- On the component side the board looks coated (glossy). Test a small area with IPA or acetone before probing, as the upstream notes advise.
- The solder side ([03](photos/89661-17140/03-board-solder-side.jpg)) is clean single-sided through-hole work, which makes tracing easy.

## Continuity test guide (owner: multimeter only, ECU unpowered)

This resolves STATUS **Q6** (what the jumpers connect to) and finishes **Q2/Q8** (whether `VISC` and `OX` are inputs, and where they go). No purchases are needed. The solder-side reference photo is [19](photos/89661-17140/19-solder-side-under-ic7-jumpers.jpg).

### Safety
- The ECU must be **unplugged from the car with no power applied**. Never use continuity or resistance mode on a powered circuit.
- Use ESD care: touch the metal case before handling the board, and don't touch IC7's pins with your fingers.
- Use the meter's **continuity (beep)** mode, and press the probes on solder joints from the **solder side**. Don't scratch the conformal coating off on the component side.

### IC7 pin numbering

IC7 is the D151801-7110, assumed to have the standard **HD6301V1 DIP-40 pinout**. Source: `TOYOTA Bluetop PCM/HD6301v1 datasheet.pdf`, page 3 (scanned), "Pin arrangement, HD6301V1P, top view".

Pin 1 is next to the notch or dot. From the **component side**, pins 1–20 run down one side and 21–40 come back up the other. **From the solder side the picture is mirrored**, so find pin 1 first: it is the joint at the notch end that beeps to ground (Vss, pin 1). Pin 21 (Vcc, +5 V) is diagonally opposite.

```
            ┌──── notch ────┐
  Vss   1 ──┤               ├── 40  E (bus clock, 1 MHz)
  XTAL  2 ──┤               ├── 39  SC1 (AS)
  EXTAL 3 ──┤               ├── 38  SC2 (R/W)
  /NMI  4 ──┤               ├── 37  P30  ┐
  /IRQ1 5 ──┤               ├── 36  P31  │
  /RES  6 ──┤               ├── 35  P32  │ Port 3
  /STBY 7 ──┤   HD6301V1    ├── 34  P33  │ (data bus AD0-7
  P20   8 ──┤  (component   ├── 33  P34  │  in expanded mode)
  P21   9 ──┤   side, top   ├── 32  P35  │
  P22  10 ──┤    view)      ├── 31  P36  │
  P23  11 ──┤               ├── 30  P37  ┘
  P24  12 ──┤               ├── 29  P40  ┐
  P10  13 ──┤               ├── 28  P41  │
  P11  14 ──┤               ├── 27  P42  │ Port 4
  P12  15 ──┤               ├── 26  P43  │ (address A8-15
  P13  16 ──┤               ├── 25  P44  │  in expanded mode)
  P14  17 ──┤               ├── 24  P45  │
  P15  18 ──┤               ├── 23  P46  │
  P16  19 ──┤               ├── 22  P47  ┘
  P17  20 ──┤               ├── 21  Vcc (+5 V)
            └───────────────┘
```

- **P20–P22 (pins 8–10) are the HD6301 mode-select pins**, latched at reset. A jumper that lands on one of these sets the chip's operating mode, which matters for the P3 reader. A jumper on any **other** port pin is a candidate for a calibration or "secret map" select.
- The repo README notes the D151801 uses P10/P11 for its extra input-capture/output-compare timer.
- The D151801 is a Denso custom part. The pinout above is the standard HD6301V1, assumed because the board's silkscreen names the "6356/6801" footprint. Test A also checks this: Vss and Vcc must land where expected.

### Results so far (owner, 2026-10-09) [BENCH: owner continuity tests]

- **The ECU case is not bonded to board ground.** No IC7 corner beeps to any point on the case. The board is grounded only through the connector's E pins. Use IC7 pin 1 as the ground reference. CONFIRMED.
- **IC7 orientation, three ways:**
  - the half-moon notch is at the X-TAL end;
  - the crystal leads beep to the 2nd and 3rd joints from solder-side corner B;
  - so **pin 1 is corner B** in [`guide/step1-ic7-corners.jpg`](photos/89661-17140/guide/step1-ic7-corners.jpg).

  This matches the standard HD6301V1 pinout, where XTAL and EXTAL are pins 2 and 3. CONFIRMED.
- **Fitted links:** J4 and J8 (top-side photo 20, wire stubs visible on the solder side). J3 is empty. This corrects the earlier "two links among J3/J4/J8". The solder-side pad map is [`guide/step2-jumper-pads.jpg`](photos/89661-17140/guide/step2-jumper-pads.jpg). CONFIRMED.

- **The jumper map** [BENCH: owner, 2026-10-09]. Results were taken one probe position at a time, and pin numbers come from [`guide/step2c-ic7-pin-numbers.jpg`](photos/89661-17140/guide/step2c-ic7-pin-numbers.jpg). **The jumpers come in pairs:** each option pin has one position to **ground** and one to a shared node **N**, and the factory fits one of each pair. CONFIRMED.

  | Jumper | Fitted | Inner pad (right) | Outer pad (left) | Role |
  |---|---|---|---|---|
  | **J4** | ✅ | ground | **P32** (IC7 pin 35) | P32 → ground = **0** |
  | J9 | — | node N | **P32** (pin 35) | alternative: P32 → N |
  | **J8** | ✅ | node N | **P34** (pin 33) | P34 → N |
  | J3 | — | ground | **P34** (pin 33) | alternative: P34 → ground = 0 |
  | J10 | — | node N | not on any IC7 pin | goes elsewhere on the board |
  | J5 | — | not N, not ground, not on IC7 | P32 or ground (the meter can't tell them apart while J4 is fitted) | unclear |
  | J6, J7, J1, J2 | — | not tested | not tested | — |

  - **Node N** reads about **750 Ω to ground**, the same in both probe directions, so it is a resistive path, not a diode. N is **not** connected to the main +5 V (pin 21). It may be a logic-high source such as a standby or battery-backed 5 V rail, which would read as a load to ground when unpowered. GUESS; settled by a powered check (STATUS Q10).
  - **Factory setting:** **P32 = 0**, and **P34 = N** (LIKELY 1).
  - **Correction:** many of the "0.757" readings on the beep setting were this 750 Ω path, not chip protection diodes. These conclusions still stand: J4 and J8 are separate nets, and pins 4, 5, 7 and 40 are not grounded (earlier beeps there were miscounts or capacitor-charging chirps).
  - **Meaning:** P32 and P34 sit on **Port 3**, which is only a general-purpose port in **single-chip mode**. So these are **factory option bits** the program reads. They are the prime candidates for Ross's secret-map "logic level" (R-F12, R-I15, STATUS Q6). LIKELY. The ROM search for reads of Port 3 bits 2 and 4 settles which bit selects what (P4/P6).
- **Mode pins P20–P22 (pins 8–10)** [BENCH], unpowered, 200k range:

  | Pin | To ground | To +5 V |
  |---|---|---|
  | 8 (P20) | 9.9k | 30.4k |
  | 9 (P21) | 17.1k | 37.5k |
  | 10 (P22) | 8.9k | 29.4k |

  The board's +5 V to ground reads 20.5k, and every "to +5 V" figure is the "to ground" figure plus about 20.5k. So each pin has a **resistor to ground or to a driving circuit**, not a pull-up. Unpowered, that reads as mode 0 (multiplexed test). It **does not show the reset level**: P20, P21 and P22 double as the timer input, timer output and serial clock, which other circuits drive when powered.
  - **Mode 7 (single chip) is LIKELY**, because the Bluetop ROM's `CPUModeTst` feeds the watchdog only when the mode bits read 111 [ROM:Bluetop $FC6E], and J4/J8 ground Port 3 pins.
  - **Settling it** needs a powered measurement at reset. That is a bench test and needs the owner's confirmation (CLAUDE.md hardware safety). It feeds the P3 ROM-reader design.

### Test A: where do the jumpers go?
1. Find IC7 **pin 1 (Vss)**: it beeps to the case or ground. Then find **pin 21 (Vcc)**.
2. For **each pad** of J1–J10 (two pads per jumper, 20 pads in total):
   - beep it against **every IC7 pin** (1–40), and note any pin that beeps;
   - beep it against **GND (pin 1)** and **+5 V (pin 21)**.
3. For the **two fitted links**, note which label each link sits under, and which IC7 pin(s) and rail it joins.

| Jumper | Fitted? | Pad A → IC7 pin / GND / +5 V | Pad B → IC7 pin / GND / +5 V |
|---|---|---|---|
| J1 | no | not tested | not tested |
| J2 | no | not tested | not tested |
| J3 | no | ground | P34 (pin 33) |
| J4 | **yes** | ground | P32 (pin 35) |
| J5 | no | not N / GND / IC7 | P32 or GND (ambiguous while J4 fitted) |
| J6 | no | not tested | not tested |
| J7 | no | not tested | not tested |
| J8 | **yes** | node N | P34 (pin 33) |
| J9 | no | node N | P32 (pin 35) |
| J10 | no | node N | not on IC7 |

### Test B: are `STH`, `VISC`, `FPU` and `OX` inputs or outputs?
For each of the connector pins `STH`, `VISC`, `FPU` and `OX` (plus `STA` as a known-good reference input):
1. Beep from the connector pin to the **first component** its track reaches. Note the reference (Rxxx, Cxxx, Txx, Dxxx or a hybrid ICx pin).
2. Follow it one step further, if you can, to an **IC7 pin**, an **IC3 (µPC177C) pin** or an **IC6 (MF176) pin**.
3. How to read the result:
   - **Output:** the pin reaches the **collector or drain of a transistor** (Txx), or a hybrid output.
   - **Input:** the pin goes through a **series resistor or RC filter** to IC3, IC6 or IC7. IC6 means an analogue input, which is what to expect for `OX` if it carries the mixture screw.
   - **`VISC` hint:** on the 1988 US car the idle-up VSV sits between `V-ISC` and ground, so the ECU *sources* battery voltage. Expect a **high-side (PNP) transistor** whose emitter goes to +B, rather than the low-side NPN drivers used for the injectors and `FPU`. An empty transistor footprint behind `VISC` would mean the board supports it but the UK build does not fit it.

| Connector pin | First component | Next IC / pin | Input or output? |
|---|---|---|---|
| STA (reference) | | | |
| STH | | | |
| VISC | | | |
| FPU | | | |
| OX | | | |

Send the filled-in tables, or photos of your notes, and they will be recorded here and in `STATUS.md`.
