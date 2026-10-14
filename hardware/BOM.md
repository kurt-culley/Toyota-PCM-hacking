# Bill of materials (UK)

> **Fundamental rule: RP2350-first, minimal purchases** (see [`../docs/RE_PLAN.md`](../docs/RE_PLAN.md) §1 and §6).
> The project's RP2350 board, a Raspberry Pi Pico 2 W, does every job it physically can. This list holds only what they need, and each line gives its reason.

**Stock last checked:** 2026-10-10, via web search. Prices and stock change, so check the live pages before ordering.

---

## A. Buy now: ROM dump (phase P3)

| # | Item | Qty | Why | Where | Approx. |
|---|---|---|---|---|---|
| A1 | **Raspberry Pi Pico 2 W with headers** (RP2350A, Wi-Fi/BLE, pre-soldered headers). This repo calls it the "Pico 2 WH", but shops list it as "Pico 2 W with headers" or "pre-soldered". Do **not** buy the "Pico WH" or "Pico W": those are the older RP2040 boards, and their pins are not 5 V tolerant. Check: the chip is marked **RP2350**, and BOOTSEL mode shows a drive called **`RP2350`** (an RP2040 shows `RPI-RP2`) | 1 (+1 optional spare) | The project board: ROM reader, serial-link logger and Wi-Fi dashboard, real-CPU harness, bench stimulus and timing | Amazon UK, The Pi Hut, Pimoroni | ~£7–8 |
| A3 | Micro-USB **data** cable (skip if owned) | 1 | Pico 2 W power and USB serial | — | ~£3 |
| A4 | Resistors: **470 Ω ×1, 10 kΩ ×5** (an assortment kit is fine). Acceptable: EXTAL pull-up 470 Ω–2.2 kΩ, never below 390 Ω (e.g. 330 Ω + 220 Ω in series); RES 4.7–10 kΩ; TX 4.7–22 kΩ; mode straps 4.7–47 kΩ | — | EXTAL pull-up; RES, SCI TX and 3× mode-strap pull-downs | Amazon UK, CPC, or salvaged through-hole parts (measure each) | ~£5 |
| A5 | Capacitors: **100 nF ceramic ×1, 10 µF ≥16 V electrolytic ×1**. Acceptable: 47–470 nF ceramic or film (marked 473–474); 4.7–100 µF ≥10 V, not bulging | — | Decoupling across the 6301's Vcc/GND (pins 21/1) | Amazon UK, CPC, or salvaged | ~£3 |
| A6 | **Turned-pin DIP-40 socket, 600 mil (15.24 mm)** | 2 (1 spare) | Fitted in the spare ECU when the chip comes out | Amazon UK, CPC | ~£3 |
| A7 | Desoldering pump, desoldering braid (2–2.5 mm), no-clean flux | — | Removing the D151801 | Amazon UK | ~£10 |
| A8 | **Chip Quik SMD1** low-melt removal alloy (leaded) | 1 kit | Backup removal method | RS UK, Amazon UK | ~£17 |
| A9 | Isopropyl alcohol 99% | 1 | Conformal-coat removal and flux clean-up | Amazon UK | ~£5 |
| A10 | **Full-size breadboard, 830 points** (or two half-size joined) | 1 | The Pico and the DIP-40 need 20 rows each | Amazon UK | ~£5 |
| opt | ESD wrist strap | 1 | Protects the only D151801 | Amazon UK | ~£5 |

Already owned: male-to-male jumpers, multimeter, and an older **Raspberry Pi Pico WH (RP2040)**: not 5 V tolerant, so not used. No scope or logic analyser is needed: the reader firmware measures the chip's E clock itself.

**Chip-in-isolation test** ([`../docs/hardware/chip_diff_test.md`](../docs/hardware/chip_diff_test.md)) on the same breadboard: only **1 kΩ ×3 and 10 kΩ ×8** more (A4 assortment).


---

## B. Deferred: measurement and logging (phase P8)

Bought as each measurement is needed: resistors, clamps (TVS/Zener) and, for any powered ECU-board measurement, a fused 12 V supply. The Pico 2 W provides stimulus, timing and logging.

---

## C. In-car modified-ROM board (phase P7)

### C1. In-car test rig (prototype): proposed, awaiting the owner's approval to order

Plugs into the spare ECU's CPU socket in place of the D151801 ([`../docs/mr2/cpu_replacement.md`](../docs/mr2/cpu_replacement.md#in-car-test-rig)). Only after the emulator passes the chip-in-isolation test.

| # | Item | Qty | Why | Where | Approx. |
|---|---|---|---|---|---|
| C1 | **Raspberry Pi Pico 2 W with headers** (as A1) | 1 | The emulated CPU. The owner's existing one can be used; a second keeps the reader/logger breadboard intact | The Pi Hut, Pimoroni | ~£7–8 |
| C2 | **40-way IDC DIP plug** (DIL "transition" plug, 600 mil) | 2 (1 spare) | Plugs into the ECU's turned-pin CPU socket | CPC / Farnell, eBay | ~£2 each |
| C3 | **40-way grey ribbon** (1.27 mm pitch, about 0.5 m) + **40-way IDC socket** (2×20, 2.54 mm) + **2×20 boxed header** | 1 each | Socket to rig, about 15 cm, so the rig sits beside the ECU whatever the clearance | CPC, Amazon UK | ~£6 |
| C4 | **74HCT541N** (DIP-20) + DIP-20 sockets | 2 + 2 (+1 spare chip) | The 12 outputs at true 5 V CMOS levels; the Pico's 3.3 V cannot meet 5 V-CMOS inputs | CPC, Farnell | ~£3 |
| C5 | **5 V buck module**, 6–36 V in, at least 500 mA, reverse-polarity protected (e.g. Pololu D24V5F5 or D24V10F5) | 1 | Powers the Pico from the ECU's switched +B; the ECU's 5 V regulator also feeds the sensors and its spare capacity is unknown | The Pi Hut, Pimoroni | ~£6 |
| C6 | **1N5819** Schottky diode | 2 | Buck to VSYS, so USB and the car supply can both be connected | CPC, Amazon UK | <£1 |
| C7 | Resistors **1 kΩ ×15, 10 kΩ ×4**; capacitors **100 nF ×3, 10 µF ×2** | — | Series protection on the inputs; decoupling for the buffers and the Pico | A4/A5 assortment | (owned) |
| C8 | **Stripboard**, about 100 × 160 mm, + 2× 1×20 female headers | 1 | Carries the Pico (removable), buffers and header | CPC, Amazon UK | ~£5 |
| C9 | **Micro-USB extension lead**, about 1 m, data | 1 | Flash the tune with the ECU closed | Amazon UK | ~£4 |
| — | Flying lead + inline fuse holder with 1 A fuse | 1 | +B to the buck | Car accessory shop | ~£3 |

**Total about £30** with a second Pico 2 W.

### C2. Final board: DO NOT ORDER

| Item | Indicative part | Why |
|---|---|---|
| Final board | an RP2350 (or a castellated Pico 2 W) + SMD 74HCT541s + 5 V buck + USB-C on a PCB with turned-pin DIP-40 legs (KiCad, JLCPCB PCBA) | In-car use; outline waits for the clearance photo above the CPU socket |
| Fallback | external-memory designs: dual-port SRAM run by the Pico, or flash + CPLD | Only if emulation fails validation |

---

## Exceptions log

Any purchase beyond this list is recorded here, with the reason and the owner's approval, as required by the RP2350-first rule.

| Date | Item | Reason | Approved by owner? |
|---|---|---|---|
| — | — | — | — |
