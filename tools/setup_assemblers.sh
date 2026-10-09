#!/usr/bin/env bash
# Build the assemblers used by the round-trip gate into .tools/ (git-ignored).
#   asl/p2bin : Macroassembler AS, built from the asl-releases "upstream" branch
#               (primary, modern assembler).
#   dasm      : built from the copy vendored in "TOYOTA Bluetop PCM/dasm/src"
#               (legacy, used only as a cross-check).
# Usage: tools/setup_assemblers.sh   (idempotent)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT/.tools"
ASL_REPO="https://github.com/Macroassembler-AS/asl-releases"
ASL_REF="c7155b4fd3d33110f0eb098dede4295a8c008772"   # asl-current-142-bld306
mkdir -p "$TOOLS"

if [[ ! -x "$TOOLS/asl/asl" || ! -x "$TOOLS/asl/p2bin" ]]; then
  rm -rf "$TOOLS/asl"
  git clone -q --depth 1 -b upstream "$ASL_REPO" "$TOOLS/asl"
  got="$(git -C "$TOOLS/asl" rev-parse HEAD)"
  [[ "$got" == "$ASL_REF" ]] || echo "warning: asl upstream is $got, pinned $ASL_REF" >&2
  cp "$TOOLS/asl/Makefile.def-samples/Makefile.def-x86_64-unknown-linux" "$TOOLS/asl/Makefile.def"
  # The sample targets athlon64; use generic x86-64 so a cached build runs on any CI runner.
  sed -i 's/-march=athlon64/-march=x86-64/' "$TOOLS/asl/Makefile.def"
  make -C "$TOOLS/asl" -j"$(nproc)" asl p2bin >"$TOOLS/asl/build.log" 2>&1
fi

if [[ ! -x "$TOOLS/dasm/dasm" ]]; then
  rm -rf "$TOOLS/dasm"
  mkdir -p "$TOOLS/dasm"
  cp -r "$ROOT/TOYOTA Bluetop PCM/dasm/src/." "$TOOLS/dasm/"
  make -C "$TOOLS/dasm" >"$TOOLS/dasm/build.log" 2>&1
fi

echo "asl:   $TOOLS/asl/asl"
echo "p2bin: $TOOLS/asl/p2bin"
echo "dasm:  $TOOLS/dasm/dasm"
