#!/usr/bin/env bash
# Build the MAME HD6301 reference used to check the Python emulator (tests/test_emu_cpu.py).
#
# MAME's m6800-family core (BSD-3-Clause) is downloaded at a pinned release tag
# into .tools/mame-ref/ (git-ignored); nothing from MAME is committed. Its
# instruction handlers are compiled unchanged inside a small shim
# (tools/mame_ref/harness.cpp) that runs random single-instruction cases.
# Usage: tools/setup_mame_ref.sh   (idempotent)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/.tools/mame-ref"
TAG="mame0275"
URL="https://raw.githubusercontent.com/mamedev/mame/$TAG/src/devices/cpu/m6800"
declare -A SHA=(
  [m6800.cpp]=974d0c205992d81bfa5c60bb4e2bccf03b7102c047b272c60285bf30180e4485
  [6800ops.hxx]=f4c692a1c51435a9c0b76a36c66dc8060fc6e6963da7cba84d75ac65fcc5dec1
  [m6801.cpp]=2fcca3ff628448fe7612ea1b3679a357158baa7a075b4ad3453adb7863a27735
)

if [[ -x "$OUT/hd6301ref" ]]; then
  echo "hd6301ref: $OUT/hd6301ref"
  exit 0
fi
mkdir -p "$OUT"
for f in "${!SHA[@]}"; do
  curl -fsSL -o "$OUT/$f" "$URL/$f"
  echo "${SHA[$f]}  $OUT/$f" | sha256sum -c --quiet -
done

# Fragments used by the shim:
#  macros.inc  register/flag macros and flag tables (m6800.cpp, "#define pPPC" up to the ops include)
#  ops_decl.inc  a member declaration for every OP_HANDLER in 6800ops.hxx
#  insn.inc / cycles.inc  the HD6301 (hd63701) dispatch and cycle tables from m6801.cpp
sed -n '/^#define pPPC/,/^\/\* include the opcode functions \*\//p' "$OUT/m6800.cpp" > "$OUT/macros.inc"
grep -o 'OP_HANDLER( *[a-z0-9_]* *)' "$OUT/6800ops.hxx" | sed -E 's/OP_HANDLER\( *([a-z0-9_]+) *\)/void \1();/' \
  | sort -u > "$OUT/ops_decl.inc"
sed -n '/m6801_cpu_device::hd63701_insn\[0x100\] = {/,/^};/p' "$OUT/m6801.cpp" \
  | sed 's/const m6800_cpu_device::op_func m6801_cpu_device::hd63701_insn/const m6800_cpu_device::op_func hd63701_insn_tbl/' \
  > "$OUT/insn.inc"
sed -n '/m6801_cpu_device::cycles_63701\[256\] =/,/^};/p' "$OUT/m6801.cpp" \
  | sed 's/const u8 m6801_cpu_device::cycles_63701/const u8 cycles_tbl/' > "$OUT/cycles.inc"
for f in macros.inc ops_decl.inc insn.inc cycles.inc; do
  [[ -s "$OUT/$f" ]] || { echo "extraction of $f failed" >&2; exit 1; }
done

c++ -O2 -std=c++17 -w -I"$OUT" -o "$OUT/hd6301ref" "$ROOT/tools/mame_ref/harness.cpp"
echo "hd6301ref: $OUT/hd6301ref"
