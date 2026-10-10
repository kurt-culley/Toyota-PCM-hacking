"""Reference model of the RP2350 reader's bus decode rule (P3).

The firmware (``hardware/rp2350-reader/firmware``) decides once per 6301 bus cycle
whether to drive a byte onto AD0-AD7 or only listen. This module is the same rule in
Python, so it can be tested against the documented reset sequence and run under the
emulator with the real dump program. The C code mirrors it line for line.

The rule keeps the reader off the bus whenever the chip itself might be driving it
(HD6301V1 handbook: internal and external spaces must never overlap, "to avoid driving
the data bus with more than one device"):

- Never while RES is low, and never on a write.
- Never in $0000-$00FF (on-chip registers and RAM; in modes 0/2 the port registers
  $04-$07 and $0F are external, but the dump program never touches them).
- Never in $F000-$FFFF, except for the reset vector: $FFFE, then $FFFF straight after
  it, within the first ``VECTOR_WINDOW`` bus cycles after RES rises. In mode 0 the
  vectors are external only for those few cycles. After that the window locks shut
  until the next reset.
- Drive only reads of page $C0xx, from the program image.

Everything else is listened to (the snoop channel).
"""

from __future__ import annotations

VECTOR_WINDOW = 3  # bus cycles after RES rises: $FFFF (dummy), $FFFE, $FFFF
PROGRAM_PAGE = 0xC0


class ReaderDecode:
    def __init__(self, page: bytes, vector: int = 0xC0C0):
        if len(page) != 256:
            raise ValueError("program image must be one 256-byte page ($C000-$C0FF)")
        self.page = page
        self.vector = vector
        self.in_reset = True
        self.cycle_no = 0
        self.locked = True
        self.last_drove_fffe = False

    def assert_reset(self) -> None:
        self.in_reset = True
        self.locked = True
        self.last_drove_fffe = False

    def release_reset(self) -> None:
        self.in_reset = False
        self.cycle_no = 0
        self.locked = False
        self.last_drove_fffe = False

    def cycle(self, addr: int, read: bool) -> int | None:
        """One bus cycle. Return the byte to drive, or None to listen."""
        if self.in_reset:
            return None
        n = self.cycle_no
        self.cycle_no += 1
        follows_fffe = self.last_drove_fffe
        self.last_drove_fffe = False
        if not read:
            return None
        if not self.locked:
            if addr == 0xFFFE and n < VECTOR_WINDOW:
                self.last_drove_fffe = True
                return self.vector >> 8
            if addr == 0xFFFF and follows_fffe:
                self.locked = True
                return self.vector & 0xFF
            if n >= VECTOR_WINDOW:
                self.locked = True
        if addr >> 8 == PROGRAM_PAGE:
            return self.page[addr & 0xFF]
        return None
