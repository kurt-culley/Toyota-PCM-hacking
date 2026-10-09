# CLAUDE.md: standing rules for agents in this repo

This repo is used to reverse-engineer Denso/Toyota ECUs. The active project is the **mk1 MR2 (AW11) ECU 89661-17140**. The owner knows aftermarket tuning well but is new to reverse engineering, so **agents take the lead**: explain your reasoning, propose the next step, and ask only when a decision belongs to the owner.

- **Playbook:** [`docs/RE_PLAN.md`](docs/RE_PLAN.md). Read it before starting any work.
- **Progress, gates, open questions and conflicts:** [`docs/STATUS.md`](docs/STATUS.md). Update it at the end of every session.

## Fundamental rules

1. **Arduino-first, minimal purchases.** Design every hardware task around the owner's **Arduino Zero** (SAMD21, 3.3 V, native USB). Buy a part only when the Zero physically cannot do the job, and write the reason in [`hardware/BOM.md`](hardware/BOM.md). Two exceptions are already accepted: level shifters, and bus-speed memory/glue for the in-car board. Any new exception needs the owner's approval, logged in `STATUS.md`. **The Zero is not 5 V tolerant, so always level-shift.**
2. **Modernise.** Use the current toolchain:
   - Python disassembly tooling (`analysis/pcmre`): verified decoder, generated source, cross-references and call graphs
   - the `asl` assembler
   - a Python HD6301 emulator
   - Python with `uv`, `pytest` and `ruff`
   - sigrok/PulseView
   - KiCad
   - TunerStudio, or TunerPro RT for raw ROM files

   Ghidra is **optional**: an interactive browser for the owner, never a dependency or a gate.

   Legacy tools (IDA 4.9, TASM, dasm, ExpressPCB, WinCUPL, RS232) are for cross-checking only. When you touch a legacy file, convert it to an open format, and never delete the original.
3. **Verify Ross first.** Cold-start work (P5) starts only after the "Ross verified" gate (P4). See [`docs/ross/claims.md`](docs/ross/claims.md).

## Evidence and truth

- **Source-of-truth order:**
  1. ROM bytes
  2. Bench or car measurement
  3. Ross PDF (17030/17140)
  4. Existing `cap.asm` annotations
  5. Upstream issues ([`docs/upstream_issues.md`](docs/upstream_issues.md)) and forums

  Log every conflict in `STATUS.md`. Never resolve one silently.
- **Tag every claim** with its evidence (`[ROM:$F863]`, `[PDF:p12]`, `[EMU:test]` or `[BENCH:file]`) and a confidence level (CONFIRMED, LIKELY or GUESS).
- **Verifier sign-off** is required at every gate. A session must not verify its own work.

## Conventions

- **Docs** are Markdown, with **Mermaid** for flows, signal chains and state machines.
- **Map write-ups** give the axes in physical units, the raw → physical scaling with its derivation, and an "In tuning terms" paragraph.
- **One definition file per ROM**, `analysis/defs/<rom>.yaml`. Generate XDF, TunerStudio INI, CSV and Markdown from it. Never hand-maintain two copies.
- **Never modify the original dumps** (`*.bin`, `*.idb`, `cap*.asm`). New work goes in `analysis/`, `docs/` and `hardware/`.
- **PDFs** may not render on github.com. Read them locally with `pdftotext` / `pdfimages`.

## Hardware safety (needs the owner's confirmation every time)

- Bring the D151801 supply up **before** releasing /RES.
- Use ESD precautions. Keep a known-good ECU aside.
- Never run the engine on untested code. Bench outputs must match the stock ECU first.
- Agents may draft posts for the upstream repo, but must never post without the owner's approval.

## Repo map

| Path | Contents |
|---|---|
| `TOYOTA Bluetop PCM/` | AE86 Bluetop, D151801 (HD6301-type). `cap.bin` + `cap.asm` is the main reference ROM. Also the reader and patch notes |
| `Toyota Redtop 4A-GE/`, `Toyota Blacktop 4a-ge/`, `Toyota 1UZ PCM/` | Toshiba 8X ECUs and dumps |
| `Toshiba 8x info/`, `Toshiba 8x daughtercard/` | T8X documentation, the CPLD port-emulator daughtercard |
| `BISON loader-debugger/` | 6301 RAM loader and monitor |
| `Lifting The Lid on the mk1 MR2 ECU (Jeremy Ross).pdf` | UK MR2 ECU articles. Claims are tracked in `docs/ross/claims.md` |
| `docs/` | Playbook, status, Ross verification, write-ups |
| `hardware/` | BOM, Zero firmware, KiCad (as it is created) |
| `analysis/` | `pcmre` Python tooling, generated source, emulator, map definitions, generated outputs (as they are created) |
