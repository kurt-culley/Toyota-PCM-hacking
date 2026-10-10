; bluetop_sparkcut.asm: spark-cut rev limiter for the Bluetop D151801 ROM (cap.bin)
;
; Prototype for the simulator and the P7 external-memory board. Hooks overlay four
; places in the 4 KB ROM; the new code lives at $E000, outside the internal ROM (the
; 4 KB ROM has no free bytes). Build and test: tests/test_sparkcut.py, which uses
; pcmre.patch to overlay this onto cap.bin.
;
; Stock limiter: SatCount_97 >= $80 (6 passes above 7400 rpm) skips injection, spark runs.
; This patch:    SatCount_97 >= $80 skips the coil charge (dwell), injection runs.
;
;   A  $F387  IRQoutcmp: the dwell start after each spark also bails out while limiting.
;   B  $F252  NE handler: its catch-up dwell start is also skipped while limiting.
;   C  $F1F2  injection test: SatCount_97 no longer cuts fuel (byte_4C and the
;             IGF counter SatCount_98 still do).
;   D  $F42D  IGF reload: with no spark there is no IGF echo, so SatCount_98 is also
;             reloaded while limiting. Outside the limiter the IGF safety cut is unchanged.
;
; The limit (deltaNE word at $F434) and the engage delay (reload byte at $F42C) keep
; their stock meaning; see docs/bluetop/rev_limiter.md.

        cpu     6301

SatCount_97     equ     $97             ; rev-limit counter, bit 7 = limiting
SatCount_98     equ     $98             ; missing-IGF counter
byte_C6         equ     $C6             ; > 0 in start mode (the ROM makes no spark)

IRQoc_cont      equ     $F38B           ; IRQoutcmp after its start-mode test
OutCmpBombout   equ     $F3B0           ; IRQoutcmp exit: OC1 level high, no dwell
NEhi_cont       equ     $F256           ; NE handler: catch-up dwell start
IGTisON         equ     $F262           ; NE handler: skip the catch-up

; ---- hooks in the 4 KB ROM -----------------------------------------------------------

        org     $F387                   ; was: ldab byte_C6 / bgt OutCmpBombout
        jmp     sc_oc
        nop

        org     $F252                   ; was: ldaa byte_C6 / bgt IGTisON
        jmp     sc_ne
        nop

        org     $F1F2                   ; was: ldaa SatCount_97 (then ora byte_4C, SatCount_98)
        clra
        nop

        org     $F42D                   ; was: bcc RevLimiter / staa SatCount_98
        jsr     sc_igf                  ; carry = IGF echo seen (from rola), A = $7B
        nop

; ---- new code, external memory -------------------------------------------------------

        org     $E000

; IRQoutcmp: A holds TCSR1 and must survive; B is free.
sc_oc:  ldab    byte_C6                 ; stock: start mode, no dwell
        bgt     sc_oc_off
        ldab    SatCount_97             ; limiting: no dwell
        bmi     sc_oc_off
        jmp     IRQoc_cont
sc_oc_off:
        jmp     OutCmpBombout

; NE handler: A and B are reloaded straight after.
sc_ne:  ldaa    byte_C6                 ; stock: start mode, no catch-up dwell
        bgt     sc_ne_skip
        ldaa    SatCount_97             ; limiting: no catch-up dwell
        bmi     sc_ne_skip
        jmp     NEhi_cont
sc_ne_skip:
        jmp     IGTisON

; IGF reload: A = $7B and B = $79 must survive (B reloads SatCount_97 next).
sc_igf: bcs     sc_igf_set              ; stock: IGF echo seen
        tst     SatCount_97
        bpl     sc_igf_ret              ; not limiting: the safety counter keeps running
sc_igf_set:
        staa    SatCount_98
sc_igf_ret:
        rts
