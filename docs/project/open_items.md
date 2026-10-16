# Open items

## Summary

This page gives only the items that are open now: questions, conflicts between sources, and the conditions of the open gates. Each question has a number (Q*n*) that other pages use. When an item is closed, its result goes into the topic page, and its row goes out of this page. The phases and gates are in the [roadmap](roadmap.md).

## Open questions

| # | Question | Why it is important | How to settle it | Who |
|---|---|---|---|---|
| Q2 | Does the 17140 drive an idle-air device, and which board pins do P31 and PORT2 bit 2 drive? The ROM sets P31 while P17 is low, for 20–21 s after P17 goes high, and in a decel fuel cut above the return rpm [ROM:$F3A2-$F3CC]. PORT2 bit 2 goes low for about 92 s after a hot crank [ROM:$F478-$F49F] [EMU:tests/mr2/test_ross17140.py::test_hot_crank_p31_timer_and_port2_bit2]. Best fit: P31 = `VISC`, PORT2 bit 2 = `FPU` (GUESS). The CSI is not driven by the ECU (LIKELY) | Goal 1: what the ECU adds to idle air at start, after IACV removal | Continuity Test B ([board](../mr2/hardware.md)): an output transistor behind `VISC` and `FPU`, and its CPU pin | Owner, ECU without power |
| Q3 | Does the 256 µs spark lead of the ROM cancel a real hardware delay? What is the absolute advance of the 17140? The T-terminal anchor gives v × 15/64° BTDC for a warm map cell without trim, and 16.0° BTDC at a warm idle with T open (LIKELY) [EMU:tests/mr2/test_ross17140.py::test_t_terminal_fixed_sum_only_with_the_throttle_closed] | The map pages give degrees; a tune needs the true crank angle | Timing light at a warm idle: expect about 16° BTDC with T open and 10° with T shorted. Also a Pico 2 W capture of IGT against NE (P8) | Car, bench |
| Q4 | Is a 17030 or 17070 dump available? | Ross's 17030 values (R-M02 rpm axis, R-M08) and the 17070 map (R-M09) cannot be examined without it | Find an ECU or a dump | Owner |
| Q5 | Does a bench stimulus of NE and G need a VR waveform? IC3 (µPC177C comparator) is possibly the input conditioner | A bench stimulus into the ECU board (P8). The chip test drives the CPU pins directly and does not need it | Examine the input circuit of the ECU board | Bench |
| Q7 | What do the `OX` and `VF` pins do on a UK car without an O2 sensor? The ROM reads the mixture screw on ADC channel 3 [ROM:$FC67-$FC96]. Pin 11 (P23) is a fault output, possibly to `VF` (GUESS) [ROM:$FC1C-$FC28] | The pin map of the final board, and the serial link connection | Continuity Test B and the trace of Q11 | Owner, ECU without power |
| Q8 | Does `OX` carry the mixture-screw CO resistor? The 1984 `VAF` pin is not on the 17140 board (R-M08) | Which ECU pin gives the mixture input | Continuity Test B | Owner, ECU without power |
| Q9 | Is a UK wiring diagram of 1986–89 (mk1b) available? The 1988 repair manual is US spec | It confirms the 17140 pins (`VISC`, `OX`, `W`, `ACT`, `FPU`) | A UK or European EWD, or a repair manual supplement | Owner |
| Q10 | What level does P34 read with the factory jumper J8 (node N)? P34 = 1 selects map `$F1EF` and fuel × 1.00. P34 = 0 selects map `$F25D` and the rpm correction `$F117` [ROM:$FDC9-$FDD5, $FAC2-$FACB] | Which ignition map and fuel correction the car uses as stock (goal 2) | The status line `J8(P34)` in the [car test](../procedures/car_test.md), or PORT3 bit 4 over the [serial link](../mr2/serial_link.md), or a powered measurement of node N | Car (owner approval) |
| Q11 | Where do CPU pins 11 (P23, SCI RX) and 12 (P24, SCI TX) go on the board? Pin 12 is the fault-code flasher [ROM:$F769-$F7E9], possibly the `W` lamp line (LIKELY) | How to connect the serial-link logger in the car | Continuity from socket pins 11 and 12 to the next resistor or transistor, and on to the `W`, `VF` and `T` pins | Owner, ECU without power |
| Q12 | Which jumpers or pins drive PORT4 bits 2–3 (CPU pins 27 and 26)? They select an advance trim of +9/−17/−9/0 counts [ROM:$FDE4-$FDFD]. Candidates: J1, J2, J6, J7. The same check gives the straps P36 and P44–P47 | The car firmware uses the strap values of the spare ECU | Continuity check | Owner, ECU without power |
| Q13 | What drives the `FC` pin (circuit opening relay)? No ROM output operates like a fuel-pump control [ROM:$F3A2-$F3CC, $FB98-$FBB6, $F478-$F49F, $FC1C-$FC28]. Possibly board hardware drives it from NE or STA (GUESS) | Whether the final board must drive `FC` | Continuity from `FC` to its driver transistor, and on to the CPU socket or the NE and STA circuits | Owner, ECU without power |
| Q14 | Is the CPU NMOS or CMOS? | A CMOS input needs 5 V CMOS levels, so the car rig then needs 74HCT541 buffers on its 12 outputs | Supply current of the CPU. In the car test: if the ADC channels read correctly and the lamp operates, the board accepts the 3.3 V outputs | Bench or car (owner approval) |
| Q15 | Which edge of IGT (P11) is the spark? In the chip test P11 is low for about 6 ms of each 37 ms period at 800 rpm; the model uses the fall (LIKELY) | The car firmware that drives IGT. The car test holds IGT and does not need it | Capture IGT and the igniter output, or a timing light with the car rig | Bench, car |
| Q16 | Is P17 the STA input? | The P31 timer starts when P17 goes high (Q2), and STA controls cranking fuel (goal 1) | P17 over the serial link (PORT1) while cranking, or continuity from the `STA` pin | Car or owner, ECU without power |

### Car checks of LIKELY facts

Make these checks over the serial link in the car. They need no new hardware.

- Load (RAM `$46`) at key on, engine off: expect about 745 at sea level (the kPa scale conflict below).
- P16 (IDL) with the throttle closed and open.
- P30 (T) reads 0 with T–E1 shorted.
- P37 (A/C) with the A/C switch on and off.

## Open conflicts

| Topic | Source A | Source B | How to settle |
|---|---|---|---|
| Idle-up VSV control | 1984 EWD (Europe, mk1a): the loads switch the VSV; the ECU senses it on I/UP | 1988 repair manual (US, mk1b): the ECU drives it on `V-ISC`, cranking and 10 s after start | Q2: continuity Test B and the port audit |
| Injector groups and resistance | 1984 EWD: #10 = No. 1 + 3, #20 = No. 2 + 4; 1.5–3.0 Ω | 1988 repair manual: No. 10 = No. 3 + 4, No. 20 = No. 1 + 2; about 13.8 Ω | Measure the injectors and the harness of the UK car |
| 17140 load scale (kPa) | Simulator default: Load ≈ 4.98 × kPa + 98.6, from the EWD PIM curve and ADC channel 7 = 5 V (GUESS) | ROM: the readings are ratiometric to channel 7 (table `$F044`). The staircase `$F1DA` and the top map rows then apply only above about 120 kPa, which needs boost [ROM:$FA81-$FA8D]. Proposed: Load ≈ 6.14 × kPa + 123 (LIKELY) | Load at key on, engine off (about 745 at sea level, against 603 on the default scale), or a measurement of channel 7. Then change the simulator default (`ref_v=3.0`) and generate `mr2/ignition_maps.md` again |
| Maximum ignition advance | Ross p16: about 50° BTDC [PDF:p16] | Upstream issue #6: not credible, possibly includes a VR offset. The 17140 anchor gives 49.9° BTDC for the map value 213 (LIKELY) | Timing light (R-I06, Q3) |
| Decel fuel cut, A/C off | 1988 repair manual (US, mk1b) FI-128: cut at 1600 rpm, return at 1200 rpm | 17140 ROM, warm, car stopped: cut at 1800 rpm, return at 1400 rpm ([maps](../mr2/maps.md#decel-fuel-cut)) | The manual is for a different ECU. Log the cut point in the car with the serial link (RpmWord at the cut) |
| HD6301 DAA V flag | Handbook table 3-2-1 [PDF:p190]: V changes | Handbook instruction detail [PDF:p89]: V does not change | The simulator clears V, as MAME does. The Bluetop and 17140 ROMs do not use DAA. Settle only if a ROM uses DAA |
| Chip test: replay against closed loop | Replay of the logged inputs of the chip into the emulator: AdcZero (`$50`) = 27; spark 8 cycles off after the change to 5000 rpm [BENCH:data/captures/chipdiff_17140_run5_6phase_2026-10-15.log] | Closed loop, emulator with the engine model: AdcZero = 24; each spark and injector edge at a constant 2-cycle offset | Possibly the replayed ADC-end edges arrive 3 cycles late (GUESS). Find the cause; the strict bench gate needs a replay that passes |

## Gate status

### P4: "Ross verified"

Each claim that the register tests on the 17140 has a status. The PARTIAL claims need bench work, but they are not PENDING. The gate needs:

1. **R-M09** (Tier B, the 17070 MX2 map) is PENDING and needs a 17070 dump (Q4). The owner decides: keep it as a gate item, or mark it out of scope for the 17140.
2. The verification report in `docs/ross/`: a status and evidence for each claim, and diagrams of the verified chains with each difference from Ross.
3. The approval of the gate by a Verifier.

P5 (warm-up and cold start) starts only after this gate.

### P7: strict bench gate

The engine does not run on the emulator before this gate. The [chip test](../procedures/chip_test.md) gives spark and fuel at steady points (LIKELY), but the gate needs all of these:

1. Two full runs on the 8-phase schedule (`emu.loopback_ref.SCHEDULE`):
   - cranking
   - idle with the throttle closed and open
   - 2000 rpm and 5000 rpm
   - the rev limit
   - no IGF
   - the T terminal shorted.
2. `late`, `qfull` and `dropped` are 0 in both runs, and the two logs are the same.
3. Each output pin has the same edges as the emulator at a constant offset, which includes the ADC lines P12–P15. Seven ADC-hold edges are different now (two different effects).
4. The replay passes (see the conflict above).
5. The approval of a Verifier.

Then, before the engine runs on the car rig:

- Run the loopback UF2 again against the current `expected.h`.
- Add hardware-timed compares for IGT and the injector to the car firmware, and settle Q15.

The chip test does not cover:

- a cold start
- serial-link traffic
- E = 1 MHz (the chip test uses 125 kHz)
- the I/O delay of the RP2350.

**Permitted before the gate:** the [car test](../procedures/car_test.md) with key on and engine off. The car firmware holds IGT and the injector, and it does not build without the hold. Do the check of socket pins 15–17 without power first. Cranking with the outputs held is a later step, with its own owner approval.

### P3 follow-ups (no gate)

- Add the firmware version to the banner of the reader, and record it with each capture.
- Make agreement of the bus channel with the SCI channel a condition of `DONE OK`. The firmware now prints the agreement but does not use it for `DONE OK`.
