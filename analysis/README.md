# analysis/

Python tooling (`pcmre`) for the reverse-engineering playbook in [`../docs/RE_PLAN.md`](../docs/RE_PLAN.md).

## Quick start

```sh
tools/setup_assemblers.sh            # builds asl/p2bin (primary) and dasm (cross-check) into .tools/
uv sync                              # Python env (pytest, ruff)
uv run pytest                        # all tests, including the P0 round-trip gate
PYTHONPATH=analysis uv run python -m pcmre.roundtrip           # report
PYTHONPATH=analysis uv run python -m pcmre.roundtrip --write   # regenerate analysis/bluetop/cap.s
```

## Modules

| Module | Purpose |
|---|---|
| `pcmre/hd6301.py` | HD6301/6303 opcode table (230 opcodes: the 6801 set plus XGDX, SLP and AIM/OIM/EIM/TIM) and a single-instruction decoder. Verified against `asl` for every opcode. |
| `pcmre/idalisting.py` | Imports labels, comments and the code/data split from a legacy IDA 4.9 `.asm` listing. The listing has no addresses, so they are rebuilt by walking it alongside the ROM bytes. Any disagreement raises `ListingMismatch`. |
| `pcmre/emit.py` | Generates re-assemblable source for `asl` (primary) or `dasm` (legacy cross-check). Every byte comes from the ROM; the listing contributes only names and comments. |
| `pcmre/roundtrip.py` | The P0 gate. It regenerates the source, assembles it with both assemblers and requires byte-identical output. |

## Generated files

- [`bluetop/cap.s`](bluetop/cap.s): the AE86 Bluetop ROM (`cap.bin`, D151801-0642) as `asl` source, with all of IDA's labels and comments.
  - **Don't edit it by hand.** Regenerate it with `--write`. A test fails if the committed copy is out of date.
  - New annotations go in the analysis docs and, later, in `defs/*.yaml`.

## Notes and findings

- **Branches into the middle of an instruction.** The Bluetop code jumps into the middle of instructions in 6 places, a classic Denso size trick. For example, `cpx #$8DDE` hides a `bsr` in its operand bytes, and other code branches to `IC2low2+1` to execute that hidden `bsr`. The generator writes these targets as `label+offset`.
- **IDA comment quirk.** IDA adds one-character ASCII hints to byte values (`; O`, `; '?'`). These are dropped. One of them, `; \`, would otherwise be read by `asl` as a line continuation and silently swallow the next line.
- **`dasm` limitation.** The bundled `dasm` 6303 table mis-encodes AIM/OIM/EIM/TIM (it drops the immediate byte). The Bluetop ROM doesn't use them, so the cross-check works here; for a ROM that does, only `asl` is authoritative.
- **Ghidra is not set up yet.** This container's network policy blocks GitHub release downloads, so it can't fetch Ghidra. The labelled `cap.s` plus this tooling covers the gate for now. Ghidra will be added via CI (GitHub Actions can download it) or on the owner's PC; see `docs/STATUS.md`.
