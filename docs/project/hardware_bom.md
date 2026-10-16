# Parts list

## Summary

The Pico 2 W does every hardware task that it can (rule 1 in [`CLAUDE.md`](../../CLAUDE.md)). This page gives the parts that each task needs, with the reason for each part. The parts for the reader and the chip test are owned. The car rig needs nothing more, or two buffers (about £2) if the CPU is CMOS (Q14). Do not order the final board yet.

Prices are approximate (UK). Examine the shop page before an order.

## Owned

| Item | Quantity | Reason |
|---|---|---|
| Raspberry Pi Pico 2 W with headers (RP2350A) | 1 | The project board: reader, chip test, serial-link logger, car rig |
| Micro-USB data cable | 1 | Power and USB serial for the Pico 2 W |
| Breadboard, 830 points | 1 | The Pico 2 W and the DIP-40 CPU need 20 rows each |
| Turned-pin DIP-40 socket, 600 mil (15.24 mm) | 2 | One is installed in the spare ECU. The second is the plug of the car rig |
| Resistors and capacitors (below) | — | Reader and chip test |
| Desoldering pump, braid (2–2.5 mm), no-clean flux, isopropyl alcohol 99 % | — | Removal of the CPU and of the conformal coat |
| Chip Quik SMD1 low-melt alloy | 1 kit | Second method to remove the CPU |
| Jumper wires, male-to-male and female-to-male | — | Breadboard and car rig |
| Multimeter | 1 | Continuity checks and voltages. No scope or logic analyser is necessary: the Pico 2 W measures the E clock itself |
| ESD wrist strap (optional) | 1 | Protects the CPU |

**CAUTION:** a spare board must be the Pico 2 W (RP2350). Do not buy a "Pico W" or "Pico WH": these have the RP2040, and its pins do not accept 5 V. In BOOTSEL mode, a Pico 2 W shows a drive with the name `RP2350`.

## Reader

The reader ([ROM dump](../procedures/rom_dump.md)) needs these parts on the breadboard:

| Item | Quantity | Reason | Range that is permitted |
|---|---|---|---|
| 470 Ω resistor | 1 | Pull-up of EXTAL (open-drain) | 470 Ω–2.2 kΩ, never below 390 Ω |
| 10 kΩ resistor | 5 | Pull-ups of /RES and SCI TX; pull-downs of the three mode pins | /RES 4.7–10 kΩ; TX 4.7–22 kΩ; mode pins 4.7–47 kΩ |
| 100 nF ceramic capacitor | 1 | Decoupling across CPU pins 21 and 1 | 47–470 nF |
| 10 µF electrolytic capacitor, 16 V or more | 1 | Decoupling across CPU pins 21 and 1 | 4.7–100 µF, 10 V or more |

Approximate cost: Pico 2 W about £7–8; resistor and capacitor kits about £8; sockets about £3; removal tools about £30.

## Chip test

The [chip test](../procedures/chip_test.md) uses the reader breadboard. It needs only 3 more 1 kΩ resistors and 8 more 10 kΩ resistors (from the same kit).

## Car rig

The [car rig](../procedures/car_test.md) is the Pico 2 W with 26 female-to-male jumpers into the second turned-pin socket. The socket goes into the CPU socket of the spare ECU. The Pico 2 W gets its power from the laptop USB. The pin map keeps each pin that the ECU board can drive on a GPIO that accepts 5 V, so the rig needs no resistors.

| Item | Quantity | Reason | Approx. |
|---|---|---|---|
| 74HCT541N | 2 | Only if the CPU is CMOS (Q14): 5 V CMOS levels on the 12 outputs | £2 |

## Measurements (P8)

Buy each part only when a measurement needs it:

- resistors
- clamps (TVS or Zener)
- a 12 V supply with a fuse for a powered ECU board.

The Pico 2 W gives the stimulus, the timing and the log.

## Final board: do not order

| Item | Possible parts | Reason |
|---|---|---|
| Final board | An RP2350 (or a castellated Pico 2 W), SMD 74HCT541 buffers, a 5 V buck regulator and USB-C, on a PCB with turned-pin DIP-40 legs (KiCad, factory-assembled) | The emulator in the car ([design](../emulator/design.md)). The outline needs a photo of the clearance above the CPU socket. Order only after the strict bench gate ([open items](open_items.md)) |
| Fallback | External-memory designs: a dual-port SRAM that the Pico 2 W controls, or flash with a CPLD | Only if the emulator fails its validation |

## Exceptions

A part that the Pico 2 W can replace needs the approval of the owner, written in [open items](open_items.md). There are no exceptions.
