; romsize.asm: the same dump program, starting at $E000 (P3 `size` mode)
;
; The D151801 variants may hold more than the HD6301V1's 4 KB. This run sends
; $E000-$FFFF and the reader stays listen-only for the whole range (it never uses
; pull-ups on lines the 6301 drives to 5 V). The reader runs it three times and judges
; each 4 KB block:
;   - Internal ROM: the chip drives the bus, so all runs agree, and only a few bytes
;     happen to equal their address low byte.
;   - Not internal: nothing drives the bus, so the byte read either changes between
;     runs or echoes the address low byte left on the multiplexed bus.

START   equ     $E000
        include "romdump.asm"
