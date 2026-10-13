; bluetop_overrun.asm: overrun fuel and retard ("pops and bangs") for the Bluetop D151801 ROM (cap.bin)
;
; Prototype for the simulator and the P7 external-memory board, built and tested like
; bluetop_sparkcut.asm (tests/test_overrun.py, via pcmre.patch). New code at $E000.
;
; Stock, throttle closed (byte_95 bit 7, the ROM's idle state):
;   - fuel is cut while lilRPM >= DecelCutRPM (+16 to enter, i.e. 400 rpm of hysteresis)
;     [ROM:$F50A-$F51C];
;   - the spark uses the fixed idle advance (45 raw, plus A/C and idle-speed terms)
;     instead of the map [ROM:$F82C-$F857].
; This patch, throttle closed AND lilRPM >= OB_RPM (the overrun window):
;   - no decel fuel cut: the injectors keep firing the normal airflow-based pulse;
;   - BaseAdvance = OB_ADV and the idle-speed term IDLcompADV = 0.
; Below OB_RPM, and whenever the throttle is open, everything is stock.
;
;   A  $F512  decel-cut decision: was cmpb lilRPM / bhi / ldab byte_95 / bpl
;   B  $F8AD  temploadADV: was staa BaseAdvance / ldaa ADC_ThW (reached from both the
;             idle and the map paths)

        cpu     6301

lilRPM          equ     $65             ; rpm / 25
byte_95         equ     $95             ; bit 7 = throttle closed (idle state)
ADC_ThW         equ     $57
BaseAdvance     equ     $A3
IDLcompADV      equ     $A6

; ---- calibration ---------------------------------------------------------------------
OB_RPM          equ     160             ; overrun window starts at 160 x 25 = 4000 rpm
OB_ADV          equ     38              ; raw advance; warm: 38 x 90/256 - 0.9 = 12.5 deg BTDC
                                        ; (before the 256 us lead, open question Q3)

; ---- hooks in the 4 KB ROM -----------------------------------------------------------

        org     $F512                   ; B = decel-cut rpm (+16 when not already cutting)
        jsr     ob_cut                  ; N = 1: cut fuel
        bpl     $F51E                   ; stock "no cut" path
        nop
        nop
        nop                             ; falls into the stock ora #$C0 / bra (cut)

        org     $F8AD
        jsr     ob_adv
        nop

; ---- new code, external memory -------------------------------------------------------

        org     $E000

; Decel-cut decision. A (byte_4C being built) must survive; B is free.
ob_cut: cmpb    lilRPM
        bhi     ob_fuel                 ; stock: below the cut rpm
        ldab    byte_95
        bpl     ob_fuel                 ; stock: throttle open
        ldab    lilRPM
        cmpb    #OB_RPM
        bcc     ob_fuel                 ; overrun window: keep fuelling
        ldab    #$80                    ; N = 1: stock cut
        rts
ob_fuel:
        clrb                            ; N = 0: no cut
        rts

; Advance store. A = BaseAdvance from the idle or map path; B is free.
ob_adv: ldab    byte_95
        bpl     ob_store                ; throttle open: stock
        ldab    lilRPM
        cmpb    #OB_RPM
        bcs     ob_store                ; below the window: stock idle advance
        clr     IDLcompADV
        ldaa    #OB_ADV
ob_store:
        staa    BaseAdvance
        ldaa    ADC_ThW
        rts
