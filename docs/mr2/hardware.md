# MR2 17140: ECU hardware

## Summary

| Item | Value |
|---|---|
| ECU | Toyota **89661-17140**, Denso **175700-1043**, 12 V, "4A-G" (UK mk1b MR2) |
| Board | PCB **175731-0460**, revision **A2**, single-sided through-hole |
| CPU | **IC7, Denso D151801-7110**, 40-pin DIP, HD6301 core, 4.00 MHz crystal (E = 1 MHz) |
| Option jumpers | **J4** (P32 to ground) and **J8** (P34 to node N) are fitted. P34 selects the ignition map ([program](program.md)) |
| Connectors | 10P + 18P + 14P. The pin labels are in [Connector pin labels](#connector-pin-labels) |

The photos are in [`../images/mr2_board/`](../images/mr2_board/). Each fact gives its evidence and a confidence level ([writing rules](../style.md)). The factory documents for the connector pins are in [factory data](factory_data.md).

## Identification

| Item | Value | Confidence | Evidence |
|---|---|---|---|
| Toyota part number | **89661-17140** | CONFIRMED | Case label ([01](../images/mr2_board/01-case-label.jpg)) |
| Denso part number | **175700-1043**, 12 V, "4A-G" | CONFIRMED | Case label |
| Connectors | 10P + 18P + 14P | CONFIRMED | Case label |
| PCB number | **175731-0460**, revision **A2** | CONFIRMED | [21](../images/mr2_board/21-pcb-number-175731-0460.jpg) |
| Build date stamp | **S63.11.30** = Showa 63 = **30 Nov 1988** | LIKELY | Sticker, top right ([02](../images/mr2_board/02-board-overview.jpg)) |

## CPU (IC7)

| Item | Value | Confidence |
|---|---|---|
| Reference | **IC7**, silkscreen **"6356/6801"** | CONFIRMED |
| Marking | **D151801-7110**, F356-1400, 8L1802 | CONFIRMED ([07](../images/mr2_board/07-ic7-mcu-jumpers.jpg)) |
| Package | **40-pin DIP**. Soldered into the board, no socket, on the stock ECU. On the spare ECU the CPU is removed and a turned-pin DIP-40 socket is installed | CONFIRMED |
| Family | **HD6301 core, the same D151801 family as the AE86 Bluetop** (D151801-0642). The reader dumped the ROM with HD6301 mode 0, and the ROM is HD6301 code [BENCH:data/captures/89661-17140_dump_2026-10-13.txt] | CONFIRMED |
| ROM | **4 KB internal, `$F000`–`$FFFF`**. `$E000`–`$EFFF` reads back the address (no memory). Word sum `$AA55` [BENCH:data/captures/89661-17140_dump_2026-10-13.txt] | CONFIRMED |
| RAM | **192 bytes from `$0040`** (`$40`–`$FF`). The ROM self-test writes all of it [ROM:$F310-$F336] | CONFIRMED (code) |
| Second timer | Input capture on **P10** and output compare on **P11**. Registers: `$18` (byte, TCSR2), `$1B` (word, OCR2), `$1D` (word, ICR2). It is a copy of the normal timer and uses the same free-running counter at `$0009`. The two timers share the timer interrupt vectors | Registers and pins CONFIRMED (code) [ROM:$FE36-$FE45, $FEB4-$FEC4]; the shared counter and vectors LIKELY ([upstream notes](../project/upstream_notes.md)) |
| Instruction timing | MC6801 cycle counts, not HD6301 counts. The chip test shows it ([emulator validation](../emulator/validation.md)) | LIKELY |
| Crystal | "400IDK8Z": **4.00 MHz**, so E = 1 MHz. This agrees with Ross's "1 µs timer = injector µs" (claim R-F23) | LIKELY |
| Operating mode | **Mode 7** (single chip) in the car. The reset code stops unless the mode is 7 or 2 [ROM:$F2BE-$F2C8] | LIKELY |

**CAUTION:** Apply the supply to the CPU **before** you release /RES (pin 6). This is a project safety rule ([`CLAUDE.md`](../../CLAUDE.md)).

<details>
<summary>IC7 pinout (HD6301V1 DIP-40)</summary>

The pinout is the standard HD6301V1 DIP-40 pinout. Source: [`reference/hd6301v1_datasheet.pdf`](../../reference/hd6301v1_datasheet.pdf), page 3, "Pin arrangement, HD6301V1P, top view". The continuity tests agree with it: pin 1 is ground, and the crystal is on pins 2 and 3 [BENCH].

Pin 1 is next to the notch. From the **component side**, pins 1–20 go down one side and pins 21–40 come back up the other side. **From the solder side the pinout is a mirror image.**

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

- **P20–P22 (pins 8–10) are the mode-select pins.** The CPU latches them at reset.
- **P10 and P11 (pins 13 and 14)** are the pins of the second timer.
- **P23 and P24 (pins 11 and 12)** are the SCI receive and transmit pins ([serial link](serial_link.md)).

</details>

## Other ICs

| Ref | Marking | Possible function | Confidence |
|---|---|---|---|
| IC1 | **D151831-0430** (Denso hybrid SIP, "8-51") | Custom Denso module next to the CPU and the crystal. Possibly the reset, watchdog or supply supervisor | GUESS |
| IC2 | **HC151 12H20** (Denso hybrid SIP) | Near the injector and ignition pins. Possibly input conditioning or output drivers | GUESS |
| IC5 | **HC120 1J07** (Denso hybrid SIP) | Near +B/BATT and the regulator area. Possibly the 5 V regulator | GUESS |
| IC6 | **ND MF176 12H15A** (Denso DIP-24) | The ADC. The ROM times each conversion with input capture 1 and selects the channel on P12–P14 ([maps](maps.md#sensor-channels)) | LIKELY |
| IC3 | NEC **µPC177C** (silkscreen alternative: HA17901P) | Quad comparator (LM339/2901 class): conditioning for the NE, G and speed inputs | LIKELY |
| IC4 | Toshiba **TC4069UBP** | Hex inverter | CONFIRMED (marking) |
| T07 | Toshiba **2SD1678** power transistor, bolted to the case | One high-current driver. Ross claim R-F22 says one transistor drives all four injectors, with #10 and #20 connected together. This part is the best candidate | GUESS |

## Connector pin labels

The silkscreen labels come from the close-up photos [09–18](../images/mr2_board/09-connector-labels-a.jpg). This is their order on the board, from the E01/E02 end:

`E02 E01 · #20 #10 · IGT STA · E1 ACT · FPU NSW · STH VISC · VF OX · E21 G− · NE G1 · IGF · IDL T · VCC THA · VTA PIM · E2 THW · L2 L1 · L3 · SPD ECT · A/C FC · EGW CCO · W BATT · +B +B1`

The table gives the meaning of each label from the factory documents ([factory data](factory_data.md)). The pin numbers are those of the 1984 wiring diagram (EWD), for reference only. The connector numbers of the 17140 are not known.

| Board label | Meaning | 1984 EWD pin | Confidence (for the 17140) |
|---|---|---|---|
| E01, E02, E1, E2, E21 | Power, ECU and sensor grounds | N-5, N-10, N-7, M-10, M-16 | LIKELY |
| #10, #20 | Injector groups No.1+3 and No.2+4 | N-4, N-9 | LIKELY |
| IGT, IGF | Igniter trigger (output), spark confirmation (input) | M-8, M-5 | LIKELY |
| STA | Starter signal (input). The only cranking input of the ECU | N-3 | LIKELY |
| **STH** | **S/TH: T-VIS VSV driver (output).** The 1984 EWD gives 4350 rpm (mk1a). The ROM switches P41 on at 4650 rpm and off at 4250 rpm, the mk1b values ([maps](maps.md#t-vis-advance-step)). It is not a cold-start terminal | M-18 | LIKELY |
| **VISC** | **V-ISC**: the idle-up VSV output of the ECU. On the 1988 US car it is on during cranking and for 10 s after start (1988 repair manual FI-119). The best ROM candidate is the P31 output ([program](program.md#port-3-and-port-4)) | 1988 `V-ISC` | LIKELY (board design); P31 = VISC is a GUESS |
| VF | Feedback / CO check output to the service connector | M-17 | LIKELY |
| **OX** | The O2 input on other markets. The UK car has no O2 sensor. The 1984 mixture-screw pin **VAF** is not on this board, so OX possibly carries the CO control resistor (Ross R-M08) | (L-14 VAF) | GUESS |
| NE, G1, G− | Distributor pickups (G1 = 1984 "G+") | M-15, M-6, M-7 | LIKELY |
| IDL, VTA, VCC | Throttle idle contact, throttle position, 5 V sensor supply | M-13, M-11, M-12 | LIKELY |
| T | Diagnostic test terminal (input) | M-4 | LIKELY |
| THA, THW, PIM | Air and coolant thermistors, vacuum (MAP) sensor | M-3, M-1, M-2 | LIKELY |
| SPD | Vehicle speed | L-12 | LIKELY |
| A/C | A/C switch signal from the A/C amplifier (input) | L-11 | LIKELY |
| FC | Fuel pump control (circuit opening relay). No ROM output behaves like a fuel-pump control | L-4 | LIKELY |
| W | Check-engine (warning) lamp. 1988 repair manual: 9–14 V with no fault and the engine on | 1988 `W` (1984 L-9 DG) | LIKELY |
| BATT, +B, +B1 | Memory supply; main supply through the EFI main relay | L-2, L-8, L-1 | LIKELY |
| FPU | Low-side output for the fuel-pressure-up VSV (1988 hot-restart system, from STA, THW and THA). The best ROM candidate is PORT2 bit 2 | 1988 `FPU` | LIKELY (board design); possibly not used on UK cars |
| ACT, NSW, L1–L3, ECT, EGW, CCO | A/C cut, neutral start, automatic-gearbox lines, EGR warning. Possibly not used on the UK manual car | not in 1984 | GUESS |

The cold start injector is not connected to the ECU in the factory documents. It is wired from the starter circuit through the start injector time switch ([factory data](factory_data.md)).

## Option jumpers

A row of jumper positions **J1–J10** is between IC1 and IC7 ([07](../images/mr2_board/07-ic7-mcu-jumpers.jpg), [20](../images/mr2_board/20-ic7-jumpers-top-side.jpg)). The solder-side pad map is [`guide/step2-jumper-pads.jpg`](../images/mr2_board/guide/step2-jumper-pads.jpg). The pin numbers come from [`guide/step2c-ic7-pin-numbers.jpg`](../images/mr2_board/guide/step2c-ic7-pin-numbers.jpg).

**The jumpers are in pairs** [BENCH] CONFIRMED. Each option pin has one position to **ground** and one to a shared node **N**. The factory installs one jumper of each pair.

| Jumper | Fitted | Inner pad (right) | Outer pad (left) | Result |
|---|---|---|---|---|
| **J4** | yes | ground | **P32** (IC7 pin 35) | P32 = 0 |
| J9 | no | node N | **P32** (pin 35) | alternative: P32 to N |
| **J8** | yes | node N | **P34** (pin 33) | P34 = node N |
| J3 | no | ground | **P34** (pin 33) | alternative: P34 = 0 |
| J10 | no | node N | not on an IC7 pin | goes to a different part of the board |
| J5 | no | not N, not ground, not on IC7 | P32 or ground (the meter cannot tell them apart while J4 is fitted) | not known |
| J1, J2, J6, J7 | no | not tested | not tested | — |

- **Node N** reads about **750 Ω to ground**, the same in the two probe directions. Thus it is a resistive path, not a diode. N is **not** connected to the main +5 V (pin 21) [BENCH] CONFIRMED.
- **Possible meaning of N:** a logic-high source, for example a standby 5 V supply. Unpowered, such a supply reads as a load to ground. GUESS.
- **Factory setting:** P32 = 0, and P34 = N (possibly 1).
- **ROM use:** the ROM reads **P34** to select the ignition map and an rpm fuel correction. No instruction reads P32 directly (LIKELY) ([program](program.md#option-behaviours)).
- **P32 and P34 are on Port 3.** Port 3 is a general-purpose port only in single-chip mode. Thus the jumpers are factory option bits, not mode pins.

The board also has test points **RT**, **RD** and **RS**, and a resistor array **RA1**. The positions **T20–T23** and **R536–R546** have no parts. They are possibly options for other markets, for example grouped injection or more outputs (GUESS).

## Continuity results

All results are unpowered, with a multimeter [BENCH].

| Test | Result | Confidence |
|---|---|---|
| ECU case to board ground | **Not connected.** No IC7 corner beeps to the case. The board ground is only through the E pins of the connector. Use IC7 pin 1 as the ground reference | CONFIRMED |
| IC7 orientation | The notch is at the crystal end. The crystal leads beep to the 2nd and 3rd joints from solder-side corner B. Thus **pin 1 is corner B** in [`guide/step1-ic7-corners.jpg`](../images/mr2_board/guide/step1-ic7-corners.jpg). This agrees with the HD6301V1 pinout (XTAL and EXTAL on pins 2 and 3) | CONFIRMED |
| Fitted jumpers | J4 and J8 (photo 20, wire ends on the solder side). J3 has no jumper | CONFIRMED |
| Pins 4, 5, 7 and 40 | Not connected to ground | CONFIRMED |
| Board +5 V to ground | 20.5 kΩ | CONFIRMED |

**Mode pins P20–P22 (pins 8–10)**, 200 kΩ range:

| Pin | To ground | To +5 V |
|---|---|---|
| 8 (P20) | 9.9 kΩ | 30.4 kΩ |
| 9 (P21) | 17.1 kΩ | 37.5 kΩ |
| 10 (P22) | 8.9 kΩ | 29.4 kΩ |

- Each "to +5 V" value is the "to ground" value plus approximately 20.5 kΩ. Thus each pin has a resistor to ground or to a drive circuit, not a pull-up.
- Unpowered, the pins read as mode 0. This does not show the level at reset. P20, P21 and P22 are also the timer input, the timer output and the serial clock. Other circuits drive them when the board has power.
- **Mode 7 is LIKELY.** The Bluetop ROM feeds its watchdog only when the mode bits read 111 [ROM:Bluetop $FC6E]. The 17140 ROM accepts mode 7 or mode 2 only [ROM:$F2BE-$F2C8]. J4 and J8 connect Port 3 pins, which are port pins only in single-chip mode.

## Board construction

- IC7 is **soldered through-hole**: 40 joints.
- The component side has a glossy coating. Before you probe through it, test a small area with IPA or acetone.
- The solder side ([03](../images/mr2_board/03-board-solder-side.jpg), [19](../images/mr2_board/19-solder-side-under-ic7-jumpers.jpg)) is single-sided through-hole work. The tracks are easy to follow.

<details>
<summary>Continuity procedure for the pins that are not traced</summary>

Use this procedure for `STH`, `VISC`, `FPU`, `OX` and `FC`, and for CPU pins 11, 12, 26 and 27. Use `STA` as a known input for reference.

**CAUTION:** Disconnect the ECU from the car. Never use the continuity or resistance range on a circuit that has power.

**CAUTION:** Touch the metal case before you touch the board. Do not touch the IC7 pins with your fingers.

1. Set the meter to the continuity (beep) range.
2. Put the probes on the solder joints, on the solder side. Do not remove the coating on the component side.
3. Find the first component that the track of the pin goes to. Record its reference (Rxxx, Cxxx, Txx, Dxxx, or a pin of a hybrid IC).
4. If possible, follow the track one more step to an IC7, IC3 or IC6 pin.
5. Use these rules to read the result:
   - **Output:** the pin goes to the collector or drain of a transistor (Txx), or to a hybrid output.
   - **Input:** the pin goes through a series resistor or an RC filter to IC3, IC6 or IC7. IC6 shows an analogue input.
   - **`VISC`:** on the 1988 US car the VSV is between `V-ISC` and ground. Thus the ECU supplies battery voltage. Expect a high-side (PNP) transistor with its emitter on +B. An empty transistor position behind `VISC` shows that the board has the circuit but the UK build does not.

</details>

## Open items

These items are open ([open items](../project/open_items.md)):

- the input or output function of `STH`, `VISC`, `FPU`, `OX` and `FC`
- the voltage of node N
- the destination of CPU pins 11 and 12
- the jumpers for P42/P43.
