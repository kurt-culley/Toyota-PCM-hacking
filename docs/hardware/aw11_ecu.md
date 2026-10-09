# Test ECU: Toyota 89661-17140 (UK mk1b MR2, 4A-GE)

This record comes from the owner's photos (2026-10-09) in [`photos/89661-17140/`](photos/89661-17140/). Each claim carries a confidence tag, as set out in [`../RE_PLAN.md`](../RE_PLAN.md).

## Identification

| Item | Value | Confidence | Evidence |
|---|---|---|---|
| Toyota part number | **89661-17140** | CONFIRMED | Case label ([01](photos/89661-17140/01-case-label.jpg)) |
| Denso part number | **175700-1043**, 12 V, "4A-G" | CONFIRMED | Case label |
| Connectors | 10P + 18P + 14P | CONFIRMED | Case label |
| PCB number | 175731-1??0-A2 (middle digits hidden behind IC1) | PARTIAL | [06](photos/89661-17140/06-ic1-ic5-crystal.jpg). A clearer photo is needed |
| Build date stamp | **S63.11.30** = Showa 63 = **30 Nov 1988** | LIKELY | Sticker top right ([02](photos/89661-17140/02-board-overview.jpg)) |

## Main microcontroller: answers open question Q1

| Item | Value | Confidence |
|---|---|---|
| Reference | **IC7**, silkscreen **"6356/6801"** | CONFIRMED |
| Marking | **D151801-7110**, F356-1400, 8L1802 | CONFIRMED ([07](photos/89661-17140/07-ic7-mcu-jumpers.jpg)) |
| Package | **40-pin DIP**, 20 pins per side counted from a crop of photo 07. Soldered directly to the board, not socketed | CONFIRMED |
| Family | **HD6301/6801-type, the same D151801 family as the AE86 Bluetop** (D151801-0642). The silkscreen names the 6801/6356 footprint, and the package matches | LIKELY. Becomes CONFIRMED when the reader runs code on it |
| Crystal | "400IDK8Z": **4.00 MHz**, giving E = 1 MHz. This fits Ross's "1 µs timer = injector µs" (claim R-F23) | LIKELY |

**What this means for the plan:** P3 follows the **HD6301 path**. The [§6a Arduino Zero reader](../RE_PLAN.md#6a-arduino-zero-rom-reader-p3-buy-now-about-1015) and the Bluetop reader method both apply. The Toshiba 8X branch (Redtop/1UZ tooling) is not needed. The ROM size is still to be confirmed: the Bluetop's is 4 KB at `$F000`, and the D151801 variants may differ.

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

## Connector-edge pin labels (silkscreen, photos 04/05)

These were read from the photos. Some are partly hidden by components.

`E02 E01 #20 #10 · IGT STA · E1 ACT · FPU NSW · ?TH VISC · VF OX · E21 G− · NE G1 · IGF T · IDL · VCC THA · VTA PIM · E2 THW · L2 L1 L3 · SPD ECT · A/C FC · EGW CCO · W BATT · +B +B1`

Most are standard Toyota terminals:

- **Ignition, injection and crank/cam signals:** IGT and IGF are the ignition trigger and confirmation. #10 and #20 are the injector outputs. NE, G1 and G− are the crank/cam pickups.
- **Sensors and supplies:** VTA and IDL are the throttle position and idle switch. PIM is the MAP sensor. THA and THW are the air and coolant temperature sensors. VCC is the 5 V sensor supply, E1/E2/E21 are grounds, and BATT/+B/+B1 are the supplies.
- **Driver and gearbox inputs:** STA is the starter signal. NSW is the neutral start switch. L1–L3, ECT and SPD are automatic-gearbox and vehicle-speed lines.
- **Outputs and diagnostics:** FC is fuel pump control, W is the check-engine lamp, and T is the diagnostic test terminal.

Three of these labels change the plan:

1. **`?TH` and `VISC` bear directly on goal 1 (IACV and cold start injector removal).**
   - The first letter of `?TH` is hidden. If it reads **`STJ`**, that is Toyota's terminal for the **cold start injector / start injector time switch**. On some Toyota ECUs this means the ECU itself monitors or drives the CSI.
   - `VISC` may be a **VSV for idle-speed control** (an idle-up or air valve) driven by the ECU.

   Either would contradict the framing hypothesis in `RE_PLAN.md`, which assumes the ECU neither knows about nor drives the CSI and IACV. **Status: open, high priority.** A clear photo of these labels and then tracing them on the board will settle it (open question Q2).
2. **`OX` and `VF` exist on a UK car that has no O2 sensor.** The board is shared with O2-equipped markets. The 17140 ROM probably ignores OX or has it disabled by a jumper or calibration flag. Check this against Ross's R-I14 ("no self-learning").
3. **`FPU`** is the fuel-pressure-up VSV, used for hot restart. It is another temperature-dependent strategy, relevant to warm-up and start-up (P5).

## Configuration jumpers next to the MCU: candidate for the "secret map" logic level

There is a row of jumper positions **J1–J10** between IC1 and IC7, labelled near the MCU's port pins ([07](photos/89661-17140/07-ic7-mcu-jumpers.jpg)):

| Jumper | State |
|---|---|
| **J3** | **fitted** (wire link) |
| **J4** | **fitted** (wire link) |
| J5, J6, J7, J8, J9, J10 | empty |
| J1, J2 (by the crystal) | empty |

There are also test points **RT**, **RD**, **RS** and a resistor array **RA1**.

Ross says the secret fuel and ignition maps are selected by "a logic level inside the ECU" ([claims](../ross/claims.md) R-F12 and R-I15). Jumpers wired to MCU port pins are the obvious way Denso would set that level at the factory. **Hypothesis (GUESS):** one of J3–J10 sets the port bit that the code tests to choose the secret maps.

To check it:
1. Trace each jumper pad to its IC7 pin, using a continuity meter with the board unpowered.
2. In the ROM (P6), find which port bits are read once at start-up and switch table pointers.

Unpopulated positions **T20–T23** and **R536–R546** suggest more options for other markets, such as grouped injection or extra outputs.

## Board construction notes for P3 (MCU removal)

- IC7 is **soldered through-hole**, so 40 joints have to be desoldered. Use plenty of flux and braid or a desoldering pump, and don't overheat the pads. Afterwards, fit a turned-pin DIP-40 socket so the MCU can go back in.
- On the component side the board looks coated (glossy). Test a small area with IPA or acetone before probing, as the upstream notes advise.
- The solder side ([03](photos/89661-17140/03-board-solder-side.jpg)) is clean single-sided through-hole work, which makes tracing easy.

## Photos still wanted

1. **Straight-on close-up of the connector-edge labels**, especially `?TH` and `VISC`. If the labels are hidden, a photo of the case connector pin numbering also helps.
2. **Close-up of the PCB part number** next to the DENSO logo (175731-1??0).
3. **The solder side directly under IC7 and J1–J10**, lit at an angle, for tracing the jumpers to MCU pins.
