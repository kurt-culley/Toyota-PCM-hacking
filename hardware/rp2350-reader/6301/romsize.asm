; romsize.asm: the same dump program, starting at $E000 (P3 `size` mode)
;
; The D151801 variants may hold more than the HD6301V1's 4 KB. This run sends
; $E000-$FFFF and the reader stays listen-only for the whole range. The reader runs
; it twice: once with its weak pull-ups on AD0-AD7 off, once with them on.
;   - Internal ROM: the chip drives the bus, so both runs agree.
;   - Not internal: nothing drives the bus. Without pull-ups the byte read usually
;     echoes the address low byte left on the multiplexed bus; with them it reads $FF.
; A 4 KB block counts as ROM only if every byte agrees between the two runs.

START   equ     $E000
        include "romdump.asm"
