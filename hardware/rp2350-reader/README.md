# RP2350 ROM reader (P3)

Reads the internal ROM of the HD6301V1 / D151801 in mode 0. Build and use: [`../../docs/hardware/rp2350_reader_guide.md`](../../docs/hardware/rp2350_reader_guide.md). Design: [RE_PLAN §6a](../../docs/RE_PLAN.md#6a-rp2350-rom-reader-p3).

| Path | Contents |
|---|---|
| `6301/romdump.asm`, `romsize.asm` | The 43-byte program the reader serves at `$C0C0` (asl). `python -m pcmre.romdump --write` regenerates `firmware/src/romdump.h` from them |
| `firmware/` | C, pico-sdk ≥ 2.1, PIO. `pins.h` is the single pin map for both boards; `decode.h` is the drive/listen rule |
| `../../analysis/pcmre/readerdecode.py` | Python model of `decode.h` |
| `../../analysis/pcmre/romcapture.py` | Host side: runs `dump`, saves and checks the ROM |
| `../../analysis/pcmre/wiring.py` | Generates the guide's wiring tables and pictures from `pins.h` |

Tests: `tests/test_romdump.py` runs the program in the emulator against `cap.bin` with a mode-0 bus model, `tests/test_reader_decode_c.py` compares `decode.h` with the Python model, `tests/test_wiring.py` keeps the guide in step with `pins.h`, and `tests/test_romcapture.py` covers the host parser.
