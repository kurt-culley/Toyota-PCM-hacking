# ROMs

## Summary

Each folder holds one ROM. It contains the dump, the definition files that people write, and the files that the tools make from them. Do not change a dump. Do not edit a generated file by hand: change its definition file, then run the generator again.

| Folder | ROM | ECU |
|---|---|---|
| [`mr2_17140/`](mr2_17140/) | `89661-17140.bin` (CPU D151801-7110) | mk1 MR2, UK, 89661-17140 |
| [`bluetop/`](bluetop/) | `cap.bin` (CPU D151801-0642) | AE86 Bluetop, the reference ROM |
| [`bluetop_2860/`](bluetop_2860/) | `cap2-151801-2860.bin` (CPU D151801-2860) | AE86 Bluetop, a second software version |

## Files in each folder

| File | Type | Made by | Test that keeps it current |
|---|---|---|---|
| `*.bin` | dump | the ROM reader | the word sum and the SHA-256 file |
| `cap.asm`, `*.idb` | original IDA 4.9 listing and database (Bluetop) | — | — |
| `symbols.yaml` | names and notes for the 17140 source | people | — |
| `defs.yaml` | map definitions | people (`bluetop`, `mr2_17140`); `pcmre crossver` (`bluetop_2860`) | `tests/ae86/test_crossver.py` |
| `cap.s` | Bluetop source that assembles to the same bytes | `pcmre roundtrip --write` | `tests/tooling/test_roundtrip.py` |
| `mr2_17140.asm` | 17140 source that assembles to the same bytes | `pcmre symlisting mr2_17140 --write` | `tests/tooling/test_symlisting.py` |
| `xref.md` | cross-reference and call graph | `pcmre xref --write`, `pcmre symlisting` | `tests/tooling/test_xref.py`, `test_symlisting.py` |
| `maps.md`, `maps/*.csv`, `*.xdf` | map pages, CSV files, TunerPro definitions | `pcmre defs <name> --write` | `tests/ae86/test_defs.py`, `test_crossver.py` |
| `crossver_2860.md` | the differences between 0642 and 2860 | `pcmre crossver --write` | `tests/ae86/test_crossver.py` |
| `readable/*.csv` | the Bluetop ignition map in degrees | `pcmre readable --write` | `tests/ae86/test_readable.py` |
