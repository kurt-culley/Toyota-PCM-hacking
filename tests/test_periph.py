"""P2: HD6301V1 / D151801 peripheral model (analysis/emu/periph.py) register semantics."""

import pytest

from emu.cpu import VEC_ICF, VEC_OCF, VEC_SCI
from emu.periph import (
    EICI,
    EOCI,
    FRC_H,
    FRC_L,
    ICF,
    ICR1_H,
    ICR1_L,
    ICR2_H,
    IEDG,
    OCF,
    OCR1_H,
    OCR1_L,
    OCR2_H,
    OCR2_L,
    OLVL,
    P3CSR,
    PORT1,
    PORT2,
    PORT3,
    RDR,
    RDRF,
    RE,
    RIE,
    TCSR1,
    TCSR2,
    TDR,
    TE,
    TRCSR,
    Peripherals,
    bitrev8,
)

ROM = bytes(0x1000)


@pytest.fixture
def p():
    return Peripherals(ROM)


def wr16(p, addr, v):
    p.write(addr, v >> 8)
    p.write(addr + 1, v & 0xFF)


def test_frc_counts_cycles_and_high_byte_write_presets_fff8(p):
    p.advance(0x1234)
    assert (p.read(FRC_H) << 8 | p.read(FRC_L)) == 0x1234
    p.write(FRC_H, 0x55)
    assert p.frc == 0xFFF8
    wr16(p, FRC_H, 0x5AF3)  # double store loads the word (handbook fig. 2-5-2)
    assert p.frc == 0x5AF3
    p.advance(10)
    assert p.frc == 0x5AFD


def test_input_capture_on_selected_edge_only(p):
    p.write(TCSR1, IEDG)  # rising edge
    p.advance(100)
    p.set_pin(2, 0, 0)
    assert not p.read(TCSR1) & ICF
    p.advance(50)
    p.set_pin(2, 0, 1)
    assert p.read(TCSR1) & ICF
    assert (p.read(ICR1_H) << 8 | p.read(ICR1_L)) == 150


def test_icf_clears_only_after_tcsr_read_then_icr_read(p):
    p.write(TCSR1, IEDG)
    p.set_pin(2, 0, 0)
    p.set_pin(2, 0, 1)
    p.read(ICR1_H)  # ICR read without a TCSR read first: flag stays
    assert p.t1.tcsr & ICF
    p.read(TCSR1)
    p.read(ICR1_H)
    assert not p.t1.tcsr & ICF


def test_output_compare_sets_flag_and_drives_olvl_at_the_exact_cycle(p):
    seen = []
    p.listeners.append(lambda name, level, t: seen.append((name, level, t)))
    p.write(0x01, 0x02)  # DDR2 bit 1: P2-1 is the OC1 output
    p.write(TCSR1, 0)  # OLVL = 0: next match drives P2-1 low
    wr16(p, OCR1_H, 500)
    p.advance(499)
    assert not p.t1.tcsr & OCF
    p.advance(10)
    assert p.t1.tcsr & OCF
    assert not p.read(PORT2) & 0x02
    assert ("P2-1", 0, 500) in seen
    p.read(TCSR1)
    wr16(p, OCR1_H, 900)  # TCSR read then OCR write clears OCF
    assert not p.t1.tcsr & OCF


def test_timer2_mirrors_timer1_on_port1(p):
    """D151801 extra channel (GUESS layout, mirrored from timer 1): IC2 on P1-0, OC2 on P1-1."""
    p.write(0x00, 0x02)  # DDR1 bit 1
    p.write(TCSR2, IEDG | OLVL)
    p.advance(40)
    p.set_pin(1, 0, 0)
    p.set_pin(1, 0, 1)
    assert p.read(TCSR2) & ICF
    assert (p.read(ICR2_H) << 8 | p.read(ICR2_H + 1)) == 40
    assert not p.t2.tcsr & ICF
    p.write(TCSR2, 0)
    wr16(p, OCR2_H, 60)
    p.advance(30)
    assert p.t2.tcsr & OCF and not p.read(PORT1) & 0x02
    p.read(TCSR2)
    p.write(OCR2_L, 0x80)
    assert not p.t2.tcsr & OCF


def test_interrupt_priority_and_enables(p):
    p.write(TCSR1, IEDG)
    p.write(TCSR2, 0)
    p.set_pin(2, 0, 0)
    p.set_pin(2, 0, 1)  # ICF1 set, interrupt not enabled
    wr16(p, OCR2_H, 5)
    p.advance(10)  # OCF2 set, not enabled
    assert p.irq_vector() is None
    p.write(TCSR2, EOCI)
    assert p.irq_vector() == VEC_OCF
    p.write(TCSR1, IEDG | EICI)
    assert p.irq_vector() == VEC_ICF  # ICF outranks OCF


def test_sci_adc_answers_selected_channel_bit_reversed(p):
    p.write(0x04, 0x40)  # DDR3 bit 6 output
    p.write(PORT3, 0x00)  # P3-6 low: ADC selected
    p.adc[3] = 0x9C
    p.write(TRCSR, RIE | RE | TE)
    p.write(TDR, 3)
    p.advance(p.adc_delay - 1)
    assert not p.read(TRCSR) & RDRF
    p.advance(1)
    assert p.irq_vector() == VEC_SCI
    p.read(TRCSR)
    assert p.read(RDR) == bitrev8(0x9C)
    assert not p.trcsr & RDRF and p.irq_vector() is None


def test_sci_ignores_writes_while_adc_deselected(p):
    p.write(0x04, 0x40)
    p.write(PORT3, 0x40)  # P3-6 high
    p.write(TRCSR, RIE | RE | TE)
    p.write(TDR, 1)
    p.advance(1000)
    assert not p.trcsr & RDRF


def test_is3_flag_set_by_falling_edge_cleared_by_csr_then_port3_read(p):
    p.is3_falling_edge()
    assert p.read(P3CSR) & 0x80
    p.read(PORT3)
    assert not p.read(P3CSR) & 0x80


def test_mode_pins_read_mode_7(p):
    assert p.read(PORT2) & 0xE0 == 0xE0


def test_events_run_in_time_order_between_compares(p):
    order = []
    p.write(TCSR1, OLVL)
    wr16(p, OCR1_H, 100)
    p.listeners.append(lambda name, level, t: order.append(("oc", t)))
    p.write(0x01, 0x02)
    p.write(TCSR1, 0)
    p.at(50, lambda: order.append(("ev", p.now)))
    p.at(150, lambda: order.append(("ev", p.now)))
    p.advance(200)
    assert order == [("ev", 50), ("oc", 100), ("ev", 150)]


def test_ocr_low_byte_write_also_clears(p):
    wr16(p, OCR1_H, 3)
    p.advance(5)
    p.read(TCSR1)
    p.write(OCR1_L, 9)
    assert not p.t1.tcsr & OCF
    assert p.read(OCR1_H) == 0 and p.read(OCR1_L) == 9
    assert p.read(OCR2_H) == 0xFF and p.read(OCR2_L) == 0xFF  # reset value


def test_tof_set_on_wrap_and_cleared_by_tcsr_then_frc_read(p):
    from emu.periph import TOF

    p.advance(0x10000 + 5)
    assert p.read(TCSR1) & TOF
    p.read(FRC_H)
    assert not p.read(TCSR1) & TOF


def test_port3_read_without_csr_read_leaves_is3_set(p):
    p.is3_falling_edge()
    p.read(PORT3)
    assert p.read(P3CSR) & 0x80


def test_overrun_sets_orfe(p):
    from emu.periph import ORFE

    p.write(0x04, 0x40)
    p.write(PORT3, 0x00)
    p.write(TRCSR, RE | TE)
    p.write(TDR, 1)
    p.advance(p.adc_delay)
    p.write(TDR, 2)
    p.advance(p.adc_delay)
    assert p.read(TRCSR) & ORFE
