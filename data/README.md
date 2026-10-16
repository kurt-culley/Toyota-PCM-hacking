# Data

## Summary

This folder holds measured and transcribed data. The simulator and the tests read it.

| Folder | Contents | Source |
|---|---|---|
| [`sensors/`](sensors/) | Coolant (THW), intake-air (THA) and MAP (PIM) sensor curves | The 1984 wiring diagram of the mk1 MR2 ([factory data](../docs/mr2/factory_data.md)) |
| [`captures/`](captures/) | Bench records: the ROM dump log and the chip test logs | The reader and the chip test firmware on the Pico 2 W |

The file names of the captures include the date of the measurement. The documentation refers to a capture by its file name, as `[BENCH:data/captures/<file>]`.
