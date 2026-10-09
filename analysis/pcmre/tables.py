"""Bluetop table lookups, modelled in Python and checked against the ROM code.

The 1D lookup helper at ``$FF1B``–``$FF3F`` has several entry points that differ
only in how many times the 16-bit input D (= A:B) is shifted right first:

========  =========  ==============================================================
Entry     Shifts k   Notes
========  =========  ==============================================================
$FF1B     5          ``TableThW``: A = ``ADC_ThW``, B = 0; A > $C0 returns t[6]
$FF25     5          ``Table12V``: B = 0
$FF28     4          B = 0
$FF2A     3          A:B used as given (16-bit input)
$FF2B     2          A:B used as given
$FF2D     0          A:B used as given (A = segment, B = fraction)
========  =========  ==============================================================

After shifting, the high byte is the segment n and the low byte is the fraction f.
The result (in A) is linear interpolation between t[n] and t[n+1]::

    t[n] + ((t[n+1] - t[n]) * f) >> 8            if t[n+1] >= t[n]
    t[n+1] + ((t[n] - t[n+1]) * (256 - f)) >> 8   if falling (and f != 0)

so a falling segment rounds towards t[n+1], not t[n]. X points at t[0].
``tests/test_tables.py`` proves this model equals the emulator for every
table the ROM passes to these helpers.
"""

from __future__ import annotations

from dataclasses import dataclass

from .hd6301 import IDX

# entry point -> (shift count, B forced to 0, ThW clamp)
ENTRIES_1D: dict[int, tuple[int, bool, bool]] = {
    0xFF1B: (5, True, True),
    0xFF25: (5, True, False),
    0xFF28: (4, True, False),
    0xFF2A: (3, False, False),
    0xFF2B: (2, False, False),
    0xFF2D: (0, False, False),
}
THW_CLAMP = 0xC0


def lookup_1d(table: bytes, a: int, b: int = 0, *, entry: int = 0xFF2D) -> int:
    """Value the ROM's 1D lookup returns in A. ``table`` starts at t[0]."""
    shift, clear_b, thw = ENTRIES_1D[entry]
    if thw and a > THW_CLAMP:
        return table[6]
    if clear_b:
        b = 0
    d = ((a << 8) | b) >> shift
    n, f = d >> 8, d & 0xFF
    lo, hi = table[n], table[n + 1]
    if hi >= lo:
        return (lo + ((hi - lo) * f >> 8)) & 0xFF
    if f == 0:
        return lo
    return (hi + ((lo - hi) * (256 - f) >> 8)) & 0xFF


def entries_needed(entry: int) -> int | None:
    """Table length implied by the entry point for an 8-bit A input (None if A:B is 16-bit)."""
    shift, clear_b, thw = ENTRIES_1D[entry]
    if thw:
        return 7  # A <= $C0 -> segment 0..6
    if clear_b:
        return ((0xFF00 >> shift) >> 8) + 2
    return None


@dataclass(frozen=True)
class TableUse:
    site: int  # address of the jsr N,x
    caller: int  # routine containing the call
    entry: int  # helper entry point
    base: int  # table address (X at the call)


def find_1d_uses(xref, rom: bytes, org: int = 0xF000) -> list[TableUse]:
    """Every call into the 1D helper through a constant X, from a ``pcmre.xref.Xref``."""
    uses = []
    for c in xref.calls:
        if c.callee not in ENTRIES_1D or c.how != "jsr,x":
            continue
        ins = xref.instrs[c.site]
        assert ins.mode == IDX
        base = (c.callee - ins.operand) & 0xFFFF
        uses.append(TableUse(c.site, c.caller, c.callee, base))
    return sorted(set(uses), key=lambda u: (u.base, u.site))
