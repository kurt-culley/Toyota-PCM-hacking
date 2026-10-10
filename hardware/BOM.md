# Bill of materials (UK)

> **Fundamental rule: RP2350-first, minimal purchases** (see [`../docs/RE_PLAN.md`](../docs/RE_PLAN.md) §1 and §6).
> The project's two RP2350 boards do every job they physically can. This list holds only what they need, and each line gives its reason.

**Stock last checked:** 2026-10-10, via web search. Prices and stock change, so check the live pages before ordering.

---

## A. Buy now: ROM dump (phase P3)

| # | Item | Qty | Why | Where | Approx. |
|---|---|---|---|---|---|
| A1 | **Raspberry Pi Pico 2 WH** (RP2350A, Wi-Fi/BLE, pre-soldered headers; order code SC1634). Must be a **Pico 2** model; the older Pico/Pico W (RP2040) is not 5 V tolerant | 1 (+1 optional spare) | Runs the ROM reader on its own; later the wireless link | Amazon UK, The Pi Hut, Pimoroni | ~£7–8 |
| A2 | **Olimex RP2350-PICO2-BB48R** (RP2350B, all 48 GPIOs pre-soldered, PSRAM, microSD). The BB48 (no PSRAM/microSD) also works | 1 | Main wired board: reader, real-CPU harness, bench, logger, P7 prototype. Not needed for the first dump | Olimex, The Pi Hut (BB48) | ~£11–13 |
| A3 | Micro-USB **data** cable (skip if owned) | 1 | Pico 2 WH power and USB serial | — | ~£3 |
| A4 | Resistors: **470 Ω ×1, 10 kΩ ×5** (an assortment kit is fine). Acceptable: EXTAL pull-up 470 Ω–2.2 kΩ, never below 390 Ω (e.g. 330 Ω + 220 Ω in series); RES 4.7–10 kΩ; TX 4.7–22 kΩ; mode straps 4.7–47 kΩ | — | EXTAL pull-up; RES, SCI TX and 3× mode-strap pull-downs | Amazon UK, CPC, or salvaged through-hole parts (measure each) | ~£5 |
| A5 | Capacitors: **100 nF ceramic ×1, 10 µF ≥16 V electrolytic ×1**. Acceptable: 47–470 nF ceramic or film (marked 473–474); 4.7–100 µF ≥10 V, not bulging | — | Decoupling across the 6301's Vcc/GND (pins 21/1) | Amazon UK, CPC, or salvaged | ~£3 |
| A6 | **Turned-pin DIP-40 socket, 600 mil (15.24 mm)** | 2 (1 spare) | Fitted in the spare ECU when the chip comes out | Amazon UK, CPC | ~£3 |
| A7 | Desoldering pump, desoldering braid (2–2.5 mm), no-clean flux | — | Removing the D151801 | Amazon UK | ~£10 |
| A8 | **Chip Quik SMD1** low-melt removal alloy (leaded) | 1 kit | Backup removal method | RS UK, Amazon UK | ~£17 |
| A9 | Isopropyl alcohol 99% | 1 | Conformal-coat removal and flux clean-up | Amazon UK | ~£5 |
| A10 | **Full-size breadboard, 830 points** (or two half-size joined) | 1 | The Pico and the DIP-40 need 20 rows each | Amazon UK | ~£5 |
| opt | ESD wrist strap | 1 | Protects the only D151801 | Amazon UK | ~£5 |

Already owned: male-to-male jumpers, multimeter. No scope or logic analyser is needed: the reader firmware measures the chip's E clock itself.

**Carrier PCB (P3, ordered once the design is reviewed):** DIP-40 ZIF socket, BB48R headers, the A4/A5 parts and a 5 V load switch, factory-assembled by JLCPCB. Price quoted before ordering.

---

## B. Deferred: bench rig and logger (phase P8)

Designed after P4. Expected to need only resistors, clamps (TVS/Zener) and a fused 12 V bench supply; the BB48R provides stimulus, timing and logging.

---

## C. Deferred: in-car modified-ROM board (phase P7) — DO NOT ORDER

**Status: provisional.** Nothing is ordered until the P4 port audit is complete and a design review has frozen the pin budget.

| Item | Indicative part | Why |
|---|---|---|
| Prototype | the BB48R (A2) + an HCT buffer if some ECU inputs need 5 V CMOS levels | Proves the RP2350 route on the bench |
| Final board | RP2350B + wireless module, 12 V → 5 V supply, TVS, polyfuse; factory-assembled (KiCad, JLCPCB PCBA) | In-car use |
| ECU interface | the DIP-40 socket (A6) + 2×20 machined-pin plug | Physical connection |
| Fallback | ATF1508ASL CPLD + AS6C62256 SRAM | Only if the RP2350 route fails the port audit |

---

## Exceptions log

Any purchase beyond this list is recorded here, with the reason and the owner's approval, as required by the RP2350-first rule.

| Date | Item | Reason | Approved by owner? |
|---|---|---|---|
| — | — | — | — |
