# Upstream knowledge digest

Source: issues on the original repo, [sparkiedk/Toyota-PCM-hacking](https://github.com/sparkiedk/Toyota-PCM-hacking/issues?q=is%3Aissue). That repo has 8 issues, no Discussions, and an empty wiki. Only the technical points are kept here, each linked to its issue. Treat them as **source-of-truth level 5**: useful leads, to be confirmed against the ROM or bench.

> **TODO (phase P0):** 10 collapsed comments in [#4](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/4) (May–Jul 2021) and the end of [#1](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/1) could not be read when this digest was written. Fetch them from a session whose source is `sparkiedk/Toyota-PCM-hacking`, or have the owner paste them in. Then fold the findings in here.

## Hardware and dumping — [#4 "Hacking a USDM 4AGZE"](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/4) (the most useful thread)

- **Mask ROM.** These Denso MCUs cannot be reflashed. Running custom code means running the MCU in external (expanded) mode from external memory on a daughtercard that replaces the CPU.
- **Dumping method.** Run the repo's reader code with the MCU in external mode. It sends the internal ROM over the MCU UART to a **5 V USB-UART** (not RS232), captured with a terminal program.
  - The baud rate is odd: measure it on a scope and set the adapter to the nearest rate. For the HD6301, `reader6301v1.asm` sets 244.1 baud.
  - *Modernised in this project:* the Arduino Zero reader snoops the bus instead, so there is no baud-rate problem ([`RE_PLAN.md` §6a](RE_PLAN.md)).
- **Daughtercard design (1UZ, Toshiba 8X).** The parts are external flash plus an **ATF1504ASL CPLD** (CUPL source in [`Toshiba 8x daughtercard/1504 CUPL code/`](../Toshiba%208x%20daughtercard/1504%20CUPL%20code/)). The CPLD:
  - emulates port A and part of port B
  - emulates the port-B input strobe (IS), which the 1UZ uses to sense /IDL
  - latches the multiplexed address bus
  - decodes the flash, RAM and FTDI addresses
  - provides a 2-bit "port_hi" GPIO

  A "portaccess" signal gates port emulation.
- **Design bug to avoid.** The IS/OS pins were not routed to the CPLD, so /IDL sensing needed a bodge wire. **Route every strobe and port pin the ECU uses to the CPLD.**
- **Low power.** Use the ATF1504/1508 **ASL**. Its input-transition detection lets it sleep. Otherwise the CPLD draws tens of mA with the car off, unless an inverter drives its power-down input.
- **Bring-up checklist:**
  - A crystal of 4 MHz or less, with about 10 pF loading caps as a starting point.
  - Prefer DIP parts for prototypes: SST39SF040 flash or a 27C256 UV EPROM rather than SMT flash.
  - The first 32 KB of flash appears at the top 32 KB of the CPU address space, so offset the code. Tie unused high address lines to ground.
  - Fit 0.1 µF decoupling on every logic IC.
  - Ground I/E (T8X pin 12), especially at boot. Power up **before** releasing reset.
  - First run an **infinite-loop test** and probe the bus to confirm fetches from external memory (about three bus cycles).
  - Contention check: any level outside ±10 % of 0 V/5 V means two drivers are fighting. One mis-wired bit can let some code run while other parts crash.
  - Use **X1** probes. X10 probes are noisier for slow logic.
  - Remove the conformal coat from the pins with acetone and a toothbrush.
  - Check that the scope and the USB-serial adapter share a common ground. Use full solder fillets on 0.1" headers, and don't trust cheap SDIP-64 sockets.
- **The part number does not identify the CPU.** The 4AGZE's 64-pin "D151801-5890" is a **Toshiba 8X**, while the Bluetop's D151801-0642 is an HD6301-type. Identify the chip by package and pinout.
- **Ignition multiplexer.** The author also built a dsPIC30F3010 board that intercepted IGT and NE/G to drive coil-on-plug, and it was used on a Blacktop.

## Table formats and ignition units — [#6](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/6)

- To convert spark-table values into degrees, trace how **IGT** is generated. On the T8X, IGT is bit 0 of the DOUT port, driven from the timer CPR0 interrupt, which counts at 250 kHz (4 µs per count). The interrupt is scheduled at **TDC − advance − dwell**, converted into time and offset from a measured NE edge.
- It is disputed whether the **VR-sensor zero-crossing offset** is "baked into" the tables. Ross's roughly **50° BTDC** maximum was questioned. The suggested way to settle it is a bench rig that logs NE against the IGT pin (the author spun an old Blacktop distributor with a cordless drill).
  - *This project:* the Arduino Zero timing meter (P8) and Ross claim R-I06.
- WinOLS can locate tables but does not reveal their format.

## Other platforms — [#1](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/1)

- A 1993 GS300 (2JZ) PCM uses the same Toshiba 8X hardware as the 1UZ, Redtop and Blacktop units. Later units use the TLCS-900.
- SABBAi worked on a **Mazda PCM with a Denso D151801-2002** (board architecture similar to Toyota's; D151801-0490 knock CPU):
  - located maps with WinOLS
  - **verified them with TunerPro and a Moates Ostrich**
  - used the IDA Denso plugin
  - early Mazda CPUs appear to run only in "mode 7"
  - was still looking for load cut, the rev limiter and injector scaling

  This confirms the D151801 family is used beyond Toyota, which could provide extra reference ROMs.

## External-memory mode and pinouts — [#7](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/7)

- External (ROMless) mode is documented in the MCU datasheet. The address/data pins are labelled `A_nn_` / `DA_nn_`.
- Special-order Denso parts can have extra ports, so the published pinouts may be partly wrong. The D151801 has an extra timer and RAM; see the [README](../README).

## Practical — [#8](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/8)

- github.com fails to render some of the repo's PDFs. Use a local clone with `pdftotext` / `pdfimages`.

## Off-topic (no project content)

- [#2](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/2): Prius adaptive high beam.
- [#3](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/3): the dorikaze.net forum is closed to new registrations and is effectively an archive.
- [#5](https://github.com/sparkiedk/Toyota-PCM-hacking/issues/5): 1988 Cressida dash MCU.
