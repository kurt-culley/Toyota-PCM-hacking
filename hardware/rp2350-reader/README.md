# RP2350 ROM reader

## Summary

This firmware reads the internal ROM of an HD6301V1 or D151801 CPU in mode 0. The procedure is in [ROM dump](../../docs/procedures/rom_dump.md).

| Path | Contents |
|---|---|
| `6301/romdump.asm`, `6301/romsize.asm` | The program that the reader gives to the CPU at `$C0C0` (asl). `uv run pcmre romdump --write` makes `firmware/src/romdump.h` from them |
| `firmware/` | C, pico-sdk 2.1.1, PIO. `pins.h` is the pin map for both boards. `decode.h` is the drive/listen rule |
| `../../src/pcmre/readerdecode.py` | The Python model of `decode.h` |
| `../../src/pcmre/romcapture.py` | The PC side: runs `dump`, then saves and examines the ROM |
| `../../src/pcmre/wiring.py` | Makes the wiring tables and pictures from `pins.h` |

Tests (in `tests/hardware/`):
- `test_romdump.py` runs the program in the simulator with a mode-0 bus model.
- `test_reader_decode_c.py` compares `decode.h` with the Python model.
- `test_wiring.py` keeps the procedure tables the same as `pins.h`.
- `test_romcapture.py` tests the PC-side parser.
