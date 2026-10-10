; romdump.asm: HD6301V1 / D151801 internal-ROM dump over the SCI (P3)
;
; Runs in mode 0 (P22/P21/P20 strapped low). The RP2350 reader serves this program
; from page $C0xx and the reset vector $FFFE/$FFFF (= $C0C0) during the short window
; after RES rises in which the vectors are still external. Everything else the program
; touches is internal to the chip, and the reader only listens to it.
;
; Output on P24/TX, NRZ 8N1 at E/16 (15,625 baud with E = 250 kHz):
;   byte 0      Port 2 data register. Bits 7-5 are the latched mode (PC2-PC0) and
;               must read 000; the host rejects the run otherwise.
;   bytes 1..   every byte from START to $FFFF (4096 bytes for START = $F000)
; then the chip goes to sleep (SLP).
;
; Rules this program keeps (checked by tests/test_romdump.py in the emulator):
;   - no stack: no JSR/BSR/PSH/PUL, no RAM writes, interrupts stay masked from reset;
;   - only three writes, all to on-chip SCI registers (RMCR, TRCSR, TDR);
;   - TDR is written only after TRCSR has been read with TDRE set.
;
; Assemble:  asl -cpu 6301 romdump.asm   (python -m pcmre.romdump does this and writes
; the firmware header hardware/rp2350-reader/firmware/src/romdump.h)

        cpu     6301

        ifndef  START
START   equ     $F000           ; first byte sent after the mode byte
        endif

PORT2   equ     $03             ; port 2 data; bits 7-5 = latched mode
RMCR    equ     $10             ; rate and mode control
TRCSR   equ     $11             ; transmit/receive control and status
TDR     equ     $13             ; transmit data
TDRE    equ     $20             ; TRCSR: transmit data register empty
TE      equ     $02             ; TRCSR: transmit enable

        org     $C0C0           ; = the reset vector the reader serves

entry:  ldaa    #$04            ; CC1:CC0 = 01 (NRZ, internal clock, P22 unused), E/16
        staa    RMCR
        ldaa    #TE
        staa    TRCSR
        ldab    PORT2           ; mode byte first
        ldx     #START
send:   ldaa    TRCSR           ; wait for TDRE (this read is also half of its clear)
        bita    #TDRE
        beq     send
        stab    TDR
        ldab    0,x             ; internal ROM read: the reader only listens
        inx
        bne     send            ; X wraps to $0000 after $FFFF
last:   ldaa    TRCSR           ; send the byte from $FFFF
        bita    #TDRE
        beq     last
        stab    TDR
        ldx     #$0400          ; > 2 character times (4 E cycles per pass) so the
drain:  dex                     ; shift register empties before SLP
        bne     drain
done:   slp                     ; nothing is enabled to wake it; loop if it does
        bra     done

        if      * > $C100
        error   "program must fit in page $C0xx above $C0C0"
        endif
