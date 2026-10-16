# Emulator validation

## Summary

| Step | Method | Result | Status |
|---|---|---|---|
| 1. Python CPU core against MAME | Each opcode against MAME, random and targeted cases | 0 differences in 256 000 random and 1.08 million targeted cases | CONFIRMED |
| 2. C core against the Python core | Each opcode, and 200 000 steps of the 17140 ROM; then CPU, peripherals and memory at 8 operating points | Identical | CONFIRMED |
| 3. Loopback test (real time, one Pico 2 W) | Edge and RAM checksums against the simulator | All phases bit-exact, with the old model. Not run with the current model | OPEN |
| 4. Chip test (real CPU) | Every pin of the real CPU against the emulator | Every spark and injector edge identical at 3 steady points (closed loop). The strict bench gate is not met | LIKELY |
| 5. Car test, key on, engine off | The emulated CPU on the pins of the spare ECU, IGT and injector held | Host test passes. No car log yet | OPEN |

Open questions: [open items](../project/open_items.md).

## Step 1: Python CPU core against MAME

- **Method:** the Python core (`pcmre.emu.cpu`) runs each opcode with random registers and memory, and with interrupts. MAME runs the same cases.
- **Result:** 0 differences in 256 000 random cases and 1.08 million targeted cases. The tests also compare the order of the memory writes, the SLP wake on a masked IRQ, and the 4-cycle wake from WAI [EMU:tests/emu/test_emu_cpu.py] CONFIRMED.
- **Note:** after the chip test, the cycle counts are the MC6801 counts (`pcmre.emu.cpu.CYCLES_6801`), not the HD6301 counts ([design](design.md#what-is-emulated)).

## Step 2: C emulator against the simulator

- **CPU:** the C core gives the same result as the Python core on all 256 opcodes (random cases, interrupts included). It also gives the same result on 200 000 steps of the 17140 ROM [EMU:tests/emu/test_hd6301_c.py] CONFIRMED.
- **Peripherals:** `board.c` (CPU, peripherals and memory) runs with the engine model of the simulator through `pcmre.emu.cboard`. At 8 operating points, every spark, injector edge, ADC conversion, interrupt count and RAM byte is identical [EMU:tests/emu/test_d151801_c.py] CONFIRMED.
  - The 8 points: idle, cruise, full load, rev limit, cranking, cold with map B, no IGF, test terminal.
  - A one-bit fault in the C output-compare logic makes all 8 points fail.

## Step 3: loopback test

- **Method:** one Pico 2 W runs the emulator locked to real time, with the engine model ([`engine.h`](../../hardware/ecu-emu/loopback/engine.h), the same behaviour as `pcmre.emu.engine17140`). Core 0 puts each crank edge in a queue before its time. Core 1 runs the emulator, never ahead of the 1 µs clock and never past the queue look-ahead. At the end of each phase, core 1 calculates CRC32 values of all output edges in seconds 3–6 and of the RAM. Core 0 prints PASS if they are equal to [`expected.h`](../../hardware/ecu-emu/loopback/expected.h) (`uv run pcmre loopback-ref`). No wires.
- **Host result:** `engine.h` gives the same result as the simulator, bit for bit, on all 8 phases of the current schedule [EMU:tests/hardware/test_loopback_engine.py] CONFIRMED.
- **Pico result, old model** [BENCH: `ecu_emu_loopback` v2, console output, no capture file]. The run used HD6301 timing and 150 MHz. It ran two times on 3 points: 800 rpm / 35 kPa, 2000 rpm / 50 kPa and 5000 rpm / 95 kPa. Results:
  - all 6 phases PASS, bit-exact (output edges, RAM, injector pulses);
  - emulator busy 73–77 %;
  - worst lag 1128 µs at 800 rpm, because the emulator stopped at the last queued crank edge (3 ms apart at 800 rpm). The current firmware runs to the end of its look-ahead (`AHEAD_US` = 2000 µs).
- **Pico result, first free-running version** [BENCH: `ecu_emu_loopback` v1, console output]:
  - RpmWord exact at all 3 points;
  - 2.00 sparks and 1.00 injections per revolution;
  - spark angle within 0.13° of the simulator;
  - emulator busy about 72 %;
  - worst lag 14 µs;
  - spark pin up to 9 µs late.
- **Status:** OPEN. `expected.h` now uses the MC6801 model and the 8-phase schedule. The current loopback firmware (250 MHz, hardware alarms for IGT and the injector) has no result on the Pico yet.

## Step 4: chip test

- **Method:** the real CPU runs its own ROM in mode 7 on the reader breadboard. The Pico 2 W plays the engine. The PC replays the inputs of the CPU into the emulator and compares each output edge ([chip test](../procedures/chip_test.md)).
- **Closed-loop result** (all 6 phases of the 3-point schedule, `late=0`, 36 s at 800, 2000 and 5000 rpm) [BENCH:data/captures/chipdiff_17140_run5_6phase_2026-10-15.log] [EMU:tests/hardware/test_chip_vs_emulator.py]:
  - every spark edge (6 238) and every injector edge (3 130) of the real CPU, at a constant offset of 2 cycles;
  - injector pulse widths equal to the cycle in each phase;
  - the ADC channel sequence on 99.3–99.6 % of the edges. The other edges are a few conversions moved by one slot.
- **Status:** LIKELY for spark and fuel at steady points. The strict bench gate is not met ([roadmap](../project/roadmap.md)). The gate needs:
  - every pin exact;
  - the replay passing;
  - two identical runs with `late=0`;
  - a run that covers idle contact, cranking, the rev limit, missing IGF and the T terminal (the 8-phase schedule).

<details>
<summary>Chip test: results of each capture</summary>

**One phase at 800 rpm, 6 M E cycles** [BENCH:data/captures/chipdiff_17140_run3_2026-10-15.log] [EMU:tests/hardware/test_chip_vs_emulator.py]:

- The Pico sampled all 6 000 000 cycles in 47 999 ms (48 000 ms expected). No sample was lost.
- With the inputs of the CPU replayed into the emulator, every output pin has the same number of edges.
- All 318 spark edges (P11) and 162 injector edges (P21) are at a constant 2 cycles.
- All ADC-select and port edges are at a constant 3 cycles.
- The ADC hold line (P15) is at 3 cycles on 2994 of 3001 edges.
- The constant offsets come from the start-up time of the CPU after /RES and from the sample point of the Pico in the cycle.
- The interrupt rule of [design](design.md#what-is-emulated) item 6 is fitted to this capture.

**All 6 phases, 36 M cycles, look-ahead 16** [BENCH:data/captures/chipdiff_17140_run4_6phase_2026-10-15.log]:

- 287 999 ms against 288 000 ms expected. No sample was lost.
- The CPU is deterministic: its phase-1 output is identical, edge for edge, to the one-phase capture.
- Replay: identical through phase 1. Soon after the change to 2000 rpm, the replay moves apart, with no interrupt near the first difference. Possibly the 7 ADC-start differences of phase 1 changed the program state (GUESS).
- Closed loop (`uv run pcmre chipdiff summary`): each phase has the same number of sparks and injector pulses. The spark is at the 2-cycle offset at 800 and 2000 rpm, and 8 cycles early at 5000 rpm. The injector pulse is 0.3–0.8 % shorter on the CPU.
- The Pico applied 3420 engine reactions late (`late=3420`), mostly fast ADC conversions. Late ADC-end edges change the readings of the CPU. Thus this capture is not a fair closed-loop comparison.

**All 6 phases, look-ahead 8, `late=0`** [BENCH:data/captures/chipdiff_17140_run5_6phase_2026-10-15.log] [EMU:tests/hardware/test_chip_vs_emulator.py]:

- Closed loop: the result in the table above.
- Most of the ADC residual comes from the rig. The Pico applies ADC-start 12–15 cycles after the edge that it sees. It applies ADC-end and IGF 3 and 2 cycles later than the model. With these latencies in the model, P15 agrees on 17 978 of 18 002 edges (17 921 without them). No spark or injector edge changes.
- Spark timing is a weak test of the CPU model: it stays correct with all interrupt rules off. The injector is a strong test: an interrupt window of 0, 1 or 3 cycles makes it agree on only about 74 % of edges.
- The interrupt rules came from the one-phase capture only. Phases 2–6 are new operating points, so this is an out-of-sample test.
- Replay: spark and injector agree through phases 1 and 2, but P15 differs on 41 edges there. In phase 3, each spark is 8 cycles off from the change to 5000 rpm.
- Replay program state: AdcZero (RAM `$50`) is 27 in replay and 24 in closed loop. This agrees with replayed ADC-end edges 3 cycles late (GUESS). The cause is not known ([open items](../project/open_items.md)).
- 7 ADC-hold edges differ by 3–5 cycles in the output-compare routine. The first, at cycle 322 048, is an interrupt that the CPU took one instruction before the emulator. Another, at cycle 661 883, comes later on the CPU, with an interrupt margin of 6 cycles. Thus a second effect is present (GUESS).

**Scope of these captures:**

- 3 steady points with constant sensor voltages. Thus the ADC sample time cannot change a reading (the ROM also subtracts AdcZero).
- Not tested: idle contact closed, cranking, rev limit, cold start, missing IGF, T terminal, serial traffic.
- The CPU ran at E = 125 kHz, not 1 MHz.
- The C core ran on a PC, not on the RP2350 with its I/O.

</details>

## Step 5: car test, key on, engine off

- **Method:** the car firmware runs the 17140 ROM on the emulated CPU, on the pins of the spare ECU in the car. It holds IGT and the injector at their engine-stopped level ([car test](../procedures/car_test.md)).
- **Host result:** the firmware logic (`car.h`) runs on the PC against the engine model of the chip test [EMU:tests/hardware/test_car_fw.py] CONFIRMED:
  - with the hold off, every output edge agrees with the emulator at one constant delay of 100 µs;
  - with the hold on, IGT and the injector never change. The missing-IGF fail-safe of the ROM stops injection after 2 pulses, as in the stock ECU;
  - a /RES pulse starts the emulated CPU again correctly;
  - the ADC conversion times at the pins are correct.
- **Status:** OPEN. No log from the car yet.
- **Not covered:** spark, fuel and the timing of IGT and the injector. A build that drives them needs hardware-timed compares (as in the loopback firmware) and the strict bench gate. The IGT polarity for that build is open. In the chip test, P11 is low for about 6 ms of each 37 ms ignition period at 800 rpm. The model takes the falling edge as the spark (LIKELY).
