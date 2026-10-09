# Bill of materials (UK)

> **Fundamental rule: Arduino-first, minimal purchases** (see [`../docs/RE_PLAN.md`](../docs/RE_PLAN.md) §1).
> The owner's **Arduino Zero** does every job it physically can. This list holds only the parts it cannot replace, and each one gives its reason.

**Stock last checked:** 2026-10-09, via web search. Prices and stock change, so check the live pages before ordering.

Farnell order codes are the same across its regional sites. On **uk.farnell.com** search by the order code. **CPC** (cpc.farnell.com) is Farnell's UK hobby arm and sells the same parts with low or no minimum order.

---

## A. Buy now: Arduino Zero ROM reader (phase P3) — about £10–15

Do **not** order until the two feasibility checks in [`RE_PLAN.md` §6a](../docs/RE_PLAN.md#6a-arduino-zero-rom-reader-p3-buy-now-about-1015) are signed off in [`STATUS.md`](../docs/STATUS.md): the mode-pin strapping and the MCU's minimum clock frequency. They could change the IC counts below.

| # | Item | Part | Qty | Why the Zero can't do this | UK source / order code | Approx. |
|---|---|---|---|---|---|---|
| R1 | Arduino Zero | — | 1 | — | **already owned** | £0 |
| R2 | Octal bus transceiver: 5 V → 3.3 V inputs and the bidirectional AD0–7 bus | TI **SN74LVC245AN**, DIP-20 | 3 | The Zero's pins are **not 5 V tolerant**. The LVC245 runs at 3.3 V but accepts 5 V inputs | Farnell **3119635** ([listing](https://fr.farnell.com/en-FR/texas-instruments/sn74lvc245an/logic-bus-transcvr-octal-20dip/dp/3119635), ships from the UK warehouse); RS UK **145-0186** ([listing](https://uk.rs-online.com/web/p/bus-transceivers/1450186)) | ~£2–3 |
| R3 | Quad buffer: 3.3 V → 5 V for EXTAL and /RES | TI **SN74AHCT125N**, DIP-14 | 1 (+1 spare) | The MCU's clock and reset inputs may need true 5 V CMOS levels. AHCT has TTL inputs and 5 V outputs | Farnell **3119387**; CPC **SC20501** ([listing, CPC Ireland](https://cpcireland.farnell.com/texas-instruments/sn74ahct125n/logic-bus-buffer-tri-st-qd-14dip/dp/SC20501)) | ~£0.50 |
| R4 | Breadboard + jumpers *(skip if already owned)* | full-size solderless breadboard, M-M and M-F jumper wires | 1 | Physical prototyping | CPC, The Pi Hut, Pimoroni | ~£8 |
| R5 | Passives | 100 nF ceramic ×6 (decoupling), 10 k resistors ×8 (pull-ups, mode straps) | — | Decoupling and strapping | CPC | ~£2 |
| R6 | MCU removal | desoldering braid + flux; IPA or acetone to remove conformal coat | — | Taking the MCU off the spare ECU | CPC, Rapid, or a hardware store | ~£5 |
| opt | DIP-40 ZIF socket | any 40-pin ZIF | 1 | Protects the MCU's legs during repeated insertion | CPC, eBay UK | ~£4 |

If P3 finds a **64-pin Toshiba 8X** instead of a 40-pin HD6301-type, add an SDIP-64 socket or adapter and recheck the shifter count.

---

## B. Buy later: bench simulator (phase P8) — about £3

| # | Item | Part | Qty | Why | UK source / order code | Approx. |
|---|---|---|---|---|---|---|
| B1 | Digital potentiometer for simulating the THW/THA NTC sensors | Microchip **MCP41010-I/P** (10 kΩ, SPI, DIP-8) | 2 | The Zero has only one DAC, and the ECU reads the NTC sensors as a resistance, not a voltage | RS UK **770-7761** ([listing](https://uk.rs-online.com/web/p/digital-potentiometers/7707761), £1.49 each ex VAT); Farnell **1292242** | ~£3 |
| B2 | *(only if NE/G need a VR-style bipolar waveform)* | LM358 dual op-amp, DIP-8 | 1 | The Zero cannot output negative voltages | CPC | ~£0.50 |

The R2/R3 shifters and R4 breadboard are reused here. The Zero also acts as the timing meter and the in-car logger. Those roles need only divider resistors and TVS diodes; the exact values are set in the P8 design.

---

## C. Deferred: in-car modified-ROM daughterboard (phase P7) — DO NOT ORDER

**Status: provisional.** Nothing here is ordered until three things are done: the CPU is identified (P3), the port-usage audit is complete (P7), and a design review has frozen the pin budget and memory map. The final order codes are added then.

| Item | Indicative part | Why the Zero can't do this |
|---|---|---|
| Glue logic: address latch, decode, emulation of the lost ports, cycle-steal writes | Microchip **ATF1508ASL**, PLCC-84, + through-hole socket | The bus must answer in about 100s of ns, which firmware cannot do. It also has to emulate the ports lost in expanded mode |
| ROM image memory | Alliance **AS6C62256-55PCN** (32 K×8, 5 V, DIP-28) + socket. Datasheet: [`../ram AS6C62256.pdf`](../ram%20AS6C62256.pdf) | Bus-speed memory |
| ECU interface | DIP-40 turned-pin socket (fitted to the ECU) + 2×20 machined-pin header plug | Physical connection |
| In-car power | 12 V → 5 V switching regulator (e.g. Traco TSR 1-2450), SMBJ24A TVS, polyfuse | Automotive supply protection |
| PCB | 2-layer, KiCad; JLCPCB / PCBWay / Aisler | — |
| ~~CPLD programmer (ATDH1150USB)~~ | — | **Not needed.** The Zero acts as the JTAG/SVF player. Buying one is an exception that needs the owner's approval |
| ~~EPROM programmer, EPROMs, Moates Ostrich~~ | — | **Not needed.** The Zero loads the image into SRAM and handles live tuning |

---

## Exceptions log

Any purchase beyond this list is recorded here, with the reason and the owner's approval, as required by the Arduino-first rule.

| Date | Item | Reason the Zero can't do it | Approved by owner? |
|---|---|---|---|
| — | — | — | — |
