"""P3: the host side parses the reader's console output and refuses bad captures."""

from __future__ import annotations

import pytest

from pcmre.romcapture import check_dump_image, console_section, parse_intel_hex, report, save
from pcmre.roundtrip import ROOT

CAP = (ROOT / "TOYOTA Bluetop PCM/cap.bin").read_bytes()


def intel_hex(data: bytes, base: int) -> list[str]:
    """Same records as print_hex() in the firmware's main.c."""
    out = []
    for o in range(0, len(data), 16):
        chunk, a = data[o : o + 16], base + o
        rec = bytes([len(chunk), a >> 8 & 0xFF, a & 0xFF, 0]) + chunk
        out.append(":" + rec.hex().upper() + f"{-sum(rec) & 0xFF:02X}")
    return out + [":00000001FF"]


def console(done: str = "DONE OK") -> str:
    return "\n".join(
        ["> dump", "run 1: 4097/4097 bytes, mode byte $10, late cycles 0", "mode 0 (want 0), runs identical: yes"]
        + intel_hex(CAP, 0xF000)
        + [done, "> "]
    )


def test_roundtrip_cap():
    start, rom = parse_intel_hex(console_section(console()))
    assert (start, rom) == (0xF000, CAP)
    r = report(start, rom)
    assert "word sum $AA55 (matches" in r
    assert "$FFFE RES" in r


def test_failed_run_rejected():
    with pytest.raises(ValueError, match="runs differ"):
        console_section(console("DONE FAIL runs differ"))
    with pytest.raises(ValueError, match="no DONE"):
        console_section("> dump\nrun 1: 12/4097 bytes")


def test_bad_record_rejected():
    lines = intel_hex(CAP, 0xF000)
    lines[3] = lines[3][:-2] + "00"
    with pytest.raises(ValueError, match="checksum"):
        parse_intel_hex(lines)


def test_never_overwrites_different_dump(tmp_path):
    out = tmp_path / "x.bin"
    save(CAP, out)
    save(CAP, out)  # same bytes: fine
    assert (tmp_path / "x.bin.sha256").read_text().endswith("  x.bin\n")
    with pytest.raises(SystemExit, match="not overwriting"):
        save(CAP[:-1] + bytes([CAP[-1] ^ 1]), out)


def test_size_image_not_saved_as_rom():
    check_dump_image(0xF000, CAP)
    with pytest.raises(SystemExit, match="not saved"):
        check_dump_image(0xE000, bytes(0x1000) + CAP)
