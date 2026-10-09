# analysis/

Python tooling (`pcmre`) for the reverse-engineering playbook in [`../docs/RE_PLAN.md`](../docs/RE_PLAN.md).

## Quick start

```sh
tools/setup_assemblers.sh            # builds asl/p2bin (primary) and dasm (cross-check) into .tools/
uv sync                              # Python env (pytest, ruff)
uv run pytest                        # all tests, including the P0 round-trip gate
PYTHONPATH=analysis uv run python -m pcmre.roundtrip           # report
PYTHONPATH=analysis uv run python -m pcmre.roundtrip --write   # regenerate analysis/bluetop/cap.s
PYTHONPATH=analysis uv run python -m pcmre.xref --write        # regenerate analysis/bluetop/xref.md
tools/setup_mame_ref.sh              # builds the MAME HD6301 reference for the emulator tests
```

## Modules

| Module | Purpose |
|---|---|
| `pcmre/hd6301.py` | HD6301/6303 opcode table (230 opcodes: the 6801 set plus XGDX, SLP and AIM/OIM/EIM/TIM) and a single-instruction decoder. Verified against `asl` for every opcode. |
| `pcmre/idalisting.py` | Imports labels, comments and the code/data split from a legacy IDA 4.9 `.asm` listing. The listing has no addresses, so they are rebuilt by walking it alongside the ROM bytes. Any disagreement raises `ListingMismatch`. |
| `pcmre/emit.py` | Generates re-assemblable source for `asl` (primary) or `dasm` (legacy cross-check). Every byte comes from the ROM; the listing contributes only names and comments. |
| `pcmre/xref.py` | Cross-references and Mermaid call graphs. It walks the code from the vectors with a small abstract state (X and B as value sets, and a stack whose return address is a symbol), so it follows Denso's indexed calls, RAM-wrapping indexed accesses, jump tables, inline-parameter routines and stack-argument routines. Checked against all 514 of IDA's own XREF comments in `cap.asm`. |
| `emu/cpu.py` | HD6301V1 CPU core: all documented opcodes, cycle counts, TRAP on undefined opcodes, WAI/SLP, IRQ/NMI entry. Peripherals sit behind a `Bus` and call `irq()`/`nmi()`. Written from the Hitachi handbook tables 3-2-1 to 3-2-4, and checked against MAME (below). |
| `emu/harness.py` | Runs one ROM routine (`call`) or a stretch of straight-line code (`run`) in the emulator, with preset registers, RAM, inline parameters and stacked arguments. Used to characterise lookups and maths helpers. |
| `emu/periph.py` | HD6301V1 on-chip peripherals plus the D151801's second timer channel: FRC, input capture/output compare with the handbook flag-clear sequences, the serial ADC on the SCI, ports with external pins, the IS3 flag and an event queue. See [`../docs/bluetop/simulation.md`](../docs/bluetop/simulation.md). |
| `emu/engine.py` | Engine and sensor stimulus: NE/G edges from rpm, the SE056 airflow delay, IGF after each spark, ADC readings from °F/volts, digital inputs. |
| `emu/sim.py` | `Simulation`: boots a ROM from reset and runs it against `engine.py`. Probes give RAM by name, injector pulses and spark angle. |
| `emu/scenarios.py` | Warm-up experiments (cold start, after-start decay, steady values vs coolant) → `bluetop/sim/*.csv`, written up in [`../docs/bluetop/warmup_sim.md`](../docs/bluetop/warmup_sim.md). |
| `pcmre/tables.py` | Python model of the Bluetop interpolating lookups: the six entry points of the 1D helper at `$FF1B`–`$FF3F` and the 3D ignition-map lookup. `find_1d_uses()` lists every table the code reads. Proven equal to the emulator by `tests/test_tables.py`. |
| `pcmre/defs.py` | Generates `<rom>/maps.md` and `<rom>/maps/*.csv` from the single definition file `defs/<rom>.yaml`. |
| `pcmre/roundtrip.py` | The P0 gate. It regenerates the source, assembles it with both assemblers and requires byte-identical output. |

## Generated files

- [`bluetop/cap.s`](bluetop/cap.s): the AE86 Bluetop ROM (`cap.bin`, D151801-0642) as `asl` source, with all of IDA's labels and comments.
  - **Don't edit it by hand.** Regenerate it with `--write`. A test fails if the committed copy is out of date.
  - New annotations go in the analysis docs and, later, in `defs/*.yaml`.

- [`bluetop/xref.md`](bluetop/xref.md): readers and writers of every RAM variable and I/O register, ROM table users, routine callers and callees, routines with non-standard returns, and one Mermaid call graph per interrupt vector. Same rule: regenerate, don't edit; a test fails if it is stale.

- [`bluetop/maps.md`](bluetop/maps.md) and [`bluetop/maps/`](bluetop/maps/): the Bluetop map definitions, generated from [`defs/bluetop.yaml`](defs/bluetop.yaml).

## Notes and findings

- **Branches into the middle of an instruction.** The Bluetop code jumps into the middle of instructions in 6 places, a classic Denso size trick. For example, `cpx #$8DDE` hides a `bsr` in its operand bytes, and other code branches to `IC2low2+1` to execute that hidden `bsr`. The generator writes these targets as `label+offset`.
- **IDA comment quirk.** IDA adds one-character ASCII hints to byte values (`; O`, `; '?'`). These are dropped. One of them, `; \`, would otherwise be read by `asl` as a line continuation and silently swallow the next line.
- **`dasm` limitation.** The bundled `dasm` 6303 table mis-encodes AIM/OIM/EIM/TIM (it drops the immediate byte). The Bluetop ROM doesn't use them, so the cross-check works here; for a ROM that does, only `asl` is authoritative.
- **Ghidra is optional.** It is not used for the gates. This text-based tooling is the primary disassembly path; Ghidra is only for the owner to browse ROMs interactively. See `docs/RE_PLAN.md` §2.
- **Inline-parameter and stack-argument routines.** `boundData` / `boundDataneg` read two bound bytes placed after the call and return with `pulx` / `jmp $02,x`. `mulDbyStack` takes a byte the caller pushed and removes it on return (`ins` / `pulx` / `ins` / `jmp $00,x`). `xref.py` models both, so the code after each call is followed correctly.
- **IDA error at `$F4C9`.** IDA disassembled the two inline bytes after `jsr boundData` at `$F4C6` as `suba $14,x`. They are data (bounds `$A0`/`$14`). This is the only listing code line the analyser never reaches.
- **Analyser limits.** Loops are not enumerated: when a back edge changes X or B, it becomes unknown. 24 indexed data sites are reached with X unknown, either wholly or after a loop's first pass; `xref.md` counts and lists them, and its RAM table header states that the lists are therefore not complete. Among them is the ADC result store at `$54` + channel, so `ADC_*` variables show no writer. One indirect call stays open: `$F45F` `jsr $00,x`, a computed entry into the `lsrd` run in `DivDby16`.

## Emulator reference (MAME)

`tests/test_emu_cpu.py` runs 64 random single-instruction cases per opcode through MAME's hd6301 instruction handlers and through `emu/cpu.py`, and requires identical registers, flags, memory writes and cycle counts.
- The MAME source (BSD-3-Clause) is downloaded at tag `mame0275` and SHA-256-checked by `tools/setup_mame_ref.sh`. Its handlers are compiled unchanged inside `tools/mame_ref/harness.cpp`, and nothing from MAME is committed.
- The cycle table in `emu/cpu.py` was transcribed from the handbook rather than copied from MAME, so the cycle comparison is a check between two independent sources.

Deliberate differences, all from the handbook:
- CCR bits 7–6 always read as 1, so only bits 5–0 are compared.
- `$12`/`$13` trap on the HD6301; MAME runs undocumented 6801 behaviour for them.
- MAME's TRAP cycle count is a placeholder, so it is not compared.
- DAA's V flag: the handbook contradicts itself. Table 3-2-1 (PDF p.190) marks V as affected; the instruction details (PDF p.89) say "not affected". The core clears V, as MAME does. The conflict is logged in `docs/STATUS.md`; the Bluetop never executes DAA.
- Not modelled: the address trap for fetching from non-memory space (handbook §2.13). It belongs in the memory map behind the `Bus`.
- Memory *reads* are not compared, only writes (in order). Reads only matter for clear-on-read I/O registers, which the peripheral models will handle.
