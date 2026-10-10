"""Wiring table and picture for the RP2350 ROM reader, generated from the firmware's pins.h.

    PYTHONPATH=analysis uv run python -m pcmre.wiring          # print the Markdown tables
    PYTHONPATH=analysis uv run python -m pcmre.wiring --png    # also redraw the pictures

pins.h is the single source of truth: the guide's tables are checked against this
output by tests/test_wiring.py, so the guide cannot drift from the firmware.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .roundtrip import ROOT

PINS_H = ROOT / "hardware/rp2350-reader/firmware/src/pins.h"
PNG_DIR = ROOT / "docs/hardware/photos/rp2350_reader"
BOARDS = {"pico2w": "RASPBERRYPI_PICO2_W", "bb48": "OLIMEX_RP2350_PICO2_BB48"}

# HD6301V1 DIP-40, component-side top view: pin -> name
DIP = {
    1: "Vss", 2: "XTAL", 3: "EXTAL", 4: "/NMI", 5: "/IRQ1", 6: "/RES", 7: "/STBY",
    8: "P20", 9: "P21", 10: "P22", 11: "P23", 12: "P24/TX",
    **{13 + i: f"P1{i}" for i in range(8)},
    21: "Vcc", **{22 + i: f"A{15 - i}" for i in range(8)},
    **{30 + i: f"AD{7 - i}" for i in range(8)},
    38: "R/W", 39: "AS", 40: "E",
}  # fmt: skip

# Raspberry Pi Pico 2 W header: physical pin -> label
PICO = {
    1: "GP0", 2: "GP1", 3: "GND", 4: "GP2", 5: "GP3", 6: "GP4", 7: "GP5", 8: "GND", 9: "GP6", 10: "GP7",
    11: "GP8", 12: "GP9", 13: "GND", 14: "GP10", 15: "GP11", 16: "GP12", 17: "GP13", 18: "GND", 19: "GP14",
    20: "GP15", 21: "GP16", 22: "GP17", 23: "GND", 24: "GP18", 25: "GP19", 26: "GP20", 27: "GP21", 28: "GND",
    29: "GP22", 30: "RUN", 31: "GP26", 32: "GP27", 33: "GND", 34: "GP28", 35: "ADC_VREF", 36: "3V3(OUT)",
    37: "3V3_EN", 38: "GND", 39: "VSYS", 40: "VBUS",
}  # fmt: skip
PICO_PIN = {v: k for k, v in PICO.items() if v.startswith("GP")}

# 6301 pins wired to something other than a GPIO
LOCAL = [
    (1, "GND (any GND pin on the board)"),
    (21, "switched 5 V rail; 100 nF and 10 µF from pin 21 to pin 1, at the chip"),
    (7, "switched 5 V rail (/STBY high: run)"),
    (4, "switched 5 V rail (/NMI inactive)"),
    (5, "switched 5 V rail (/IRQ1 inactive)"),
    (8, "10 kΩ to GND (mode bit 0)"),
    (9, "10 kΩ to GND (mode bit 1)"),
    (10, "10 kΩ to GND (mode bit 2)"),
    (2, "not connected (XTAL)"),
]
PULLUPS = {"/RES": "10 kΩ to the 5 V rail", "EXTAL": "470 Ω to the 5 V rail", "P24/TX": "10 kΩ to the 5 V rail"}


def board_pins(board: str) -> dict[str, int]:
    """6301 signal -> GPIO, from pins.h."""
    text = PINS_H.read_text()
    m = re.search(rf"defined\({BOARDS[board]}\)(.*?)#(?:elif|else)", text, re.S)
    if not m:
        raise ValueError(f"{board} not in pins.h")
    defs = dict(re.findall(r"#define (\w+) (\d+)u", text + m.group(1)))  # the board block wins
    base = int(defs["BUS_BASE"])
    sig = {f"AD{i}": base + int(defs["BUS_AD_OFF"]) + i for i in range(8)}
    sig |= {f"A{8 + i}": base + int(defs["BUS_AHI_OFF"]) + i for i in range(8)}
    sig |= {"AS": base + int(defs["BUS_AS_OFF"]), "E": base + int(defs["BUS_E_OFF"])}
    sig |= {"R/W": base + int(defs["BUS_RW_OFF"]), "/RES": int(defs["PIN_RES"])}
    sig |= {"EXTAL": int(defs["PIN_EXTAL"]), "P24/TX": int(defs["PIN_SCI"])}
    return sig


def table(board: str) -> str:
    sig = board_pins(board)
    pico = board == "pico2w"
    head = "| 6301 pin | Signal | GPIO | " + ("Pico pin | " if pico else "") + "Also |"
    rows = [head, "|" + "---|" * (head.count("|") - 1)]
    for pin in sorted(DIP, key=lambda p: (DIP[p] not in sig, p)):
        name = DIP[pin]
        if name not in sig:
            continue
        g = sig[name]
        cells = [str(pin), name, f"GP{g}"] + ([str(PICO_PIN[f"GP{g}"])] if pico else []) + [PULLUPS.get(name, "")]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def local_table() -> str:
    rows = ["| 6301 pin | Name | Connect to |", "|---|---|---|"]
    rows += [f"| {p} | {DIP[p]} | {what} |" for p, what in LOCAL]
    rows.append("| 11, 13–20 | P23, P10–P17 | not connected |")
    return "\n".join(rows)


def draw(board: str, out: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    def font(size: int, bold: bool = False):
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            return ImageFont.load_default()

    sig = board_pins(board)
    f, fb, ft = font(17), font(17, True), font(26, True)
    colour = {"AD": (0, 110, 200), "A": (0, 140, 70), "ctl": (200, 90, 0), "pwr": (190, 0, 0), "gnd": (60, 60, 60),
              "nc": (160, 160, 160)}  # fmt: skip

    def kind(name: str) -> str:
        if name.startswith("AD"):
            return "AD"
        if re.fullmatch(r"A\d+", name):
            return "A"
        if name in ("Vcc", "/STBY", "/NMI", "/IRQ1"):
            return "pwr"
        if name in ("Vss", "P20", "P21", "P22"):
            return "gnd"
        if name not in sig and name not in ("EXTAL", "/RES"):
            return "nc"
        return "ctl"

    local = {p: w for p, w in LOCAL}
    img = Image.new("RGB", (1560, 1190), "white")
    d = ImageDraw.Draw(img)
    title = {"pico2w": "Raspberry Pi Pico 2 WH", "bb48": "Olimex RP2350-PICO2-BB48R"}[board]
    d.text((30, 20), f"HD6301 / D151801 ROM reader: {title}", fill="black", font=ft)
    d.text((30, 58), "Chip drawn from the component side (top view). Notch at the top. 5 V rail: last in, first out.",
           fill="black", font=f)  # fmt: skip
    x0, y0, w, pitch = 560, 110, 400, 46
    d.rectangle([x0, y0, x0 + w, y0 + 20 * pitch + 10], outline="black", width=3)
    d.arc([x0 + w // 2 - 30, y0 - 30, x0 + w // 2 + 30, y0 + 30], 0, 180, fill="black", width=3)
    d.text((x0 + w // 2, y0 + 10 * pitch), "HD6301V1\nD151801", fill="black", font=ft, anchor="mm", align="center")
    for i in range(20):
        for pin, side in ((i + 1, "L"), (40 - i, "R")):
            name = DIP[pin]
            y = y0 + 10 + i * pitch + pitch // 2
            c = colour[kind(name)]
            if name in sig:
                g = sig[name]
                where = f"GP{g}" + (f" (pin {PICO_PIN[f'GP{g}']})" if board == "pico2w" else "")
                extra = f" + {PULLUPS[name]}" if name in PULLUPS else ""
                label = f"{where}{extra}"
            else:
                label = local.get(pin, "n/c").split(";")[0].split(" (")[0]
            if side == "L":
                d.line([x0 - 40, y, x0, y], fill=c, width=4)
                d.text((x0 + 8, y - 10), f"{pin} {name}", fill=c, font=fb)
                tw = d.textlength(label, font=f)
                d.text((x0 - 50 - tw, y - 10), label, fill=c, font=f)
            else:
                d.line([x0 + w, y, x0 + w + 40, y], fill=c, width=4)
                t = f"{name} {pin}"
                d.text((x0 + w - 8 - d.textlength(t, font=fb), y - 10), t, fill=c, font=fb)
                d.text((x0 + w + 50, y - 10), label, fill=c, font=f)
    vbus = "Pico pin 40" if board == "pico2w" else "the VBUS header pin"
    notes = [
        "Decoupling: 100 nF ceramic + 10 µF (+ to pin 21) right across pins 21 and 1.",
        f"Switched 5 V rail = one jumper from the board's VBUS ({vbus}) to the rail. Plug it in only",
        "after the reader's banner appears; unplug it before the USB cable.",
    ]
    for k, n in enumerate(notes):
        d.text((30, 1100 + k * 24), n, fill="black", font=f)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, optimize=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--png", action="store_true")
    a = ap.parse_args()
    for b in BOARDS:
        print(f"## {b}\n\n{table(b)}\n")
    print(f"## local\n\n{local_table()}")
    if a.png:
        for b in BOARDS:
            draw(b, PNG_DIR / f"wiring_{b}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
