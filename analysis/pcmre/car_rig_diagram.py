# ruff: noqa: E501  (a drawing: long literal label lists)
"""Pictures and wire table of the proposed in-car test rig (docs/mr2/cpu_replacement.md, "In-car test rig").

    PYTHONPATH=analysis uv run python -m pcmre.car_rig_diagram            # both pictures
    PYTHONPATH=analysis uv run python -m pcmre.car_rig_diagram --table    # the wire table

No breadboard: one female-to-male jumper per signal from the Pico 2 W's header straight to a spare
turned-pin DIP-40 socket pressed into the spare ECU's CPU socket. The pin map is the car firmware's
hardware/ecu-emu/car/pins.h; tests/test_car_rig.py checks it against the ROM's port directions and the
5 V rule. Writes docs/hardware/photos/car_rig/car_rig.png (overview) and wiring_car.png (pin by pin).
"""

from __future__ import annotations

import re

from PIL import Image, ImageDraw, ImageFont

from . import wiring as BB
from .roundtrip import ROOT

PINS_H = ROOT / "hardware/ecu-emu/car/pins.h"
OUT = ROOT / "docs/hardware/photos/car_rig/car_rig.png"
WIRING = ROOT / "docs/hardware/photos/car_rig/wiring_car.png"
W, H = 1900, 1140
BG, INK = (250, 250, 247), (30, 30, 30)
RED, BLUE, GREY, ORANGE, GREEN, PURPLE = (
    (200, 30, 30),
    (30, 90, 200),
    (120, 120, 120),
    (220, 120, 0),
    (20, 140, 70),
    (120, 60, 160),
)
NOT_5V = (26, 27, 28)  # the Pico 2 W's ADC pins: not 5 V tolerant


def pins() -> dict[int, tuple[int, str, str]]:
    """GPIO -> (CPU pin, signal, CPU direction IN/OUT/IO), from pins.h, plus /RES and E."""
    text = PINS_H.read_text()
    out = {}
    for m in re.finditer(r"X\((\d+), \d, \d, (IN|OUT|IO)\)\s*/\*\s*(.+?)\s+pin (\d+)", text):
        out[int(m[1])] = (int(m[4]), " ".join(m[3].split()), m[2])
    out[int(re.search(r"CAR_GPIO_RES (\d+)u", text)[1])] = (6, "/RES", "IN")
    out[int(re.search(r"CAR_GPIO_E (\d+)u", text)[1])] = (40, "E", "OUT")
    return out


def gnd_pico_pin() -> int:
    return int(re.search(r"CAR_GND_PICO_PIN (\d+)", PINS_H.read_text())[1])


def car_wires() -> list[tuple[int, str, str, str]]:
    """(ECU socket pin, signal, CPU direction, Pico end): one jumper each, sorted by socket pin."""
    rows = [(1, "GND", "", f"GND (Pico pin {gnd_pico_pin()})")]
    rows += [(pin, name, d, f"GP{g} (Pico pin {BB.PICO_PIN[f'GP{g}']})") for g, (pin, name, d) in pins().items()]
    return sorted(rows)


def table() -> str:
    word = {"IN": "in", "OUT": "out", "IO": "in/out", "": ""}
    rows = ["| ECU socket pin | Signal | CPU direction | Pico end |", "|---|---|---|---|"]
    rows += [f"| {p} | {n} | {word[d]} | {g} |" for p, n, d, g in car_wires()]
    return "\n".join(rows)


def draw_wiring(out=WIRING) -> None:
    """The Pico's header (top view, USB up) and the CPU socket (top view, notch up), each pin tagged."""
    img = Image.new("RGB", (1900, 1230), "white")
    d = ImageDraw.Draw(img)
    purple, orange, grey = (130, 50, 170), (220, 110, 0), (150, 150, 150)
    f9b, f13, f15, f15b = font(9, True), font(13), font(15), font(15, True)
    lines = [
        ("In-car test rig: wiring (Pico 2 W straight to the ECU's CPU socket, no breadboard)", font(22, True), "black"),
        ("Generated from hardware/ecu-emu/car/pins.h (python -m pcmre.car_rig_diagram). Wire it unpowered: USB out, ECU out of the car.",
         f15, "black"),
        ("PURPLE E# = one female-to-male jumper: female end on that Pico pin, male end into pin # of the spare socket.",
         f15b, purple),
        ("ORANGE = GP26-28, not 5 V tolerant: they carry only P12-P14, which the ROM always drives as outputs.", f15b, orange),
        ("Before the first power-up: continuity of every jumper, and the meter check of socket pins 15-17 (see the doc).",
         f15b, (190, 0, 0)),
    ]  # fmt: skip
    for i, (t, f, c) in enumerate(lines):
        d.text((20, 15 + i * 30), t, fill=c, font=f)

    by_gpio = pins()
    gnd = gnd_pico_pin()
    pitch, top = 44, 230
    # Pico 2 W, top view, USB at the top: pins 1-20 down the left, 21-40 up the right
    px0, px1 = 380, 640
    d.rectangle([px0, top - 30, px1, top + 19 * pitch + 30], fill=(30, 110, 60), outline="black", width=2)
    d.rectangle(
        [(px0 + px1) // 2 - 28, top - 52, (px0 + px1) // 2 + 28, top - 22], fill=(190, 190, 190), outline="black"
    )
    d.text(((px0 + px1) // 2, top - 37), "USB", fill="black", font=f13, anchor="mm")
    d.text(((px0 + px1) // 2, top + 9.5 * pitch), "Pico 2 W\n(top view)", fill="white", font=f15b, anchor="mm",
           align="center")  # fmt: skip
    for pin, label in BB.PICO.items():
        left = pin <= 20
        x, y = (px0, top + (pin - 1) * pitch) if left else (px1, top + (40 - pin) * pitch)
        g = int(label[2:]) if label.startswith("GP") else None
        wired = (g in by_gpio) or pin == gnd
        d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(230, 190, 60), outline="black")
        short = {"3V3(OUT)": "3V3", "ADC_VREF": "VREF", "3V3_EN": "EN"}.get(label, label)
        d.text(
            (x + 12, y) if left else (x - 12, y),
            f"{pin} {short}",
            fill="white",
            font=f13,
            anchor="lm" if left else "rm",
        )
        if not wired:
            continue
        cpu, name, _ = by_gpio[g] if g is not None else (1, "GND", "")
        colour = orange if g in NOT_5V else purple
        tx = x - 22 if left else x + 22
        d.ellipse([tx - 15, y - 15, tx + 15, y + 15], fill=colour, outline="black")
        d.text((tx, y), f"E{cpu}", fill="white", font=f9b, anchor="mm")
        d.text((tx - 20, y) if left else (tx + 20, y), name, fill="black", font=f13, anchor="rm" if left else "lm")
        d.line([x - 7 if left else x + 7, y, tx + 15 if left else tx - 15, y], fill=colour, width=3)

    # the spare socket in the ECU's CPU socket, top view, notch up
    sx0, sx1 = 1300, 1450
    d.rectangle([sx0, top - 30, sx1, top + 19 * pitch + 30], fill=(60, 60, 60), outline="black", width=2)
    d.pieslice([(sx0 + sx1) // 2 - 22, top - 52, (sx0 + sx1) // 2 + 22, top - 8], 0, 180, fill="white")
    d.text(((sx0 + sx1) // 2, top + 9.5 * pitch), "ECU CPU\nsocket\n(spare socket\npressed in,\nnotch up)",
           fill="white", font=f13, anchor="mm", align="center")  # fmt: skip
    ends = {p: (n, g) for p, n, _, g in car_wires()}
    to_5v = {pin: g for g, (pin, _, _) in by_gpio.items()}
    for i in range(20):
        for cpu, x, side in ((i + 1, sx0, -1), (40 - i, sx1, 1)):
            y = top + i * pitch
            on = cpu in ends
            colour = (orange if to_5v.get(cpu) in NOT_5V else purple) if on else (205, 205, 205)
            d.ellipse([x - 15, y - 15, x + 15, y + 15], fill=colour, outline="black")
            d.text((x, y), f"E{cpu}" if on else str(cpu), fill="white" if on else "black", font=f9b, anchor="mm")
            label = f"{ends[cpu][0]}  ←  {ends[cpu][1]}" if on else "no wire (the ECU board's)"
            if on and side > 0:
                label = f"{ends[cpu][1]}  →  {ends[cpu][0]}"
            d.text((x + side * 22, y), label, fill="black" if on else grey, font=f13, anchor="rm" if side < 0 else "lm")
    d.text((20, top + 19 * pitch + 60), "The Pico is drawn from the top (USB up, pin 1 top left). Its header pins stick out underneath: turned over, "
           "pin 1 is top RIGHT. Count pins from the USB end, or check the GP numbers printed on the underside.\n"
           "Arrows read 'jumper from the Pico pin to the socket pin'. GP9 is free in the car "
           "(EXTAL has no wire). P36 and P42-P47 have no wire either: the car firmware uses the spare ECU's strap values (Q12).",
           fill="black", font=f13)  # fmt: skip
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, optimize=True)


def font(size: int, bold: bool = False):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def box(d, xy, fill, title, lines=(), tsize=24, outline=INK, width=3):
    d.rounded_rectangle(xy, radius=14, fill=fill, outline=outline, width=width)
    x0, y0 = xy[0], xy[1]
    d.text((x0 + 14, y0 + 10), title, font=font(tsize, True), fill=INK)
    for i, s in enumerate(lines):
        d.text((x0 + 14, y0 + 18 + tsize + i * 25), s, font=font(18), fill=INK)


def arrow(d, a, b, colour, label="", width=5, off=(0, -26)):
    d.line([a, b], fill=colour, width=width)
    (x0, y0), (x1, y1) = a, b
    d.polygon([(x1, y1), (x1 - 14, y1 - 8), (x1 - 14, y1 + 8)] if x1 > x0 else [(x1, y1), (x1 + 14, y1 - 8), (x1 + 14, y1 + 8)],
              fill=colour)  # fmt: skip
    if label:
        d.text(
            ((x0 + x1) / 2 + off[0] - 6 * len(label) / 2, (y0 + y1) / 2 + off[1]),
            label,
            font=font(17, True),
            fill=colour,
        )


def draw() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text(
        (40, 22), "In-car test rig (proposed): a Pico wired straight into the CPU socket", font=font(34, True), fill=INK
    )
    d.text((40, 70), "Only after the strict bench gate passes. Stationary tests only (key-on, idle with a timing light). "
           "The car's own ECU stays untouched as the spare.", font=font(19), fill=INK)  # fmt: skip

    # car harness + spare ECU
    box(
        d,
        (40, 150, 360, 330),
        (255, 235, 235),
        "Car harness",
        ["12 V, sensors, NE/G, IGF", "igniter, injectors, lamp", "(as stock)"],
    )
    ex0, ey0, ex1, ey1 = 440, 150, 980, 700
    d.rounded_rectangle((ex0, ey0, ex1, ey1), radius=18, fill=(214, 236, 214), outline=INK, width=4)
    d.text((ex0 + 18, ey0 + 12), "Spare 17140 ECU (lid off)", font=font(26, True), fill=INK)
    for i, s in enumerate(["its own 5 V regulator, crystal, reset,", "input conditioners, ADC hybrid,",
                           "igniter and injector drivers: unchanged"]):  # fmt: skip
        d.text((ex0 + 18, ey0 + 52 + i * 24), s, font=font(18), fill=INK)
    arrow(d, (360, 300), (ex0, 300), RED)
    d.text((368, 312), "edge\nconnector", font=font(16, True), fill=RED)
    # CPU socket with plug
    sx0, sy0 = 700, 300
    d.rectangle((sx0, sy0, sx0 + 200, sy0 + 300), fill=(60, 60, 60), outline=INK, width=3)
    for i in range(20):
        y = sy0 + 10 + i * 14.5
        d.rectangle((sx0 - 10, y, sx0, y + 7), fill=(200, 200, 200))
        d.rectangle((sx0 + 200, y, sx0 + 210, y + 7), fill=(200, 200, 200))
    d.text((sx0 + 100, sy0 + 120), "CPU socket\n(chip out)\n\nspare turned-pin\nDIP-40 socket\npressed in", font=font(18, True), fill="white",
           anchor="mm", align="center")  # fmt: skip

    # jumper wires
    for k in range(6):
        d.line([(sx0 + 210, sy0 + 60 + 14 * k), (1220, 290 + 14 * k)], fill=(150, 150, 150), width=4)
    d.text((990, 420), "26 female-to-\nmale jumpers\n(25 signals +\nGND), ~20 cm,\nPico pin to\nsocket pin",
           font=font(16, True), fill=(90, 90, 90))  # fmt: skip

    # Pico, no breadboard
    bx0, by0, bx1, by1 = 1180, 150, 1860, 760
    d.rounded_rectangle((bx0, by0, bx1, by1), radius=16, fill=(245, 243, 236), outline=GREY, width=3)
    d.text((bx0 + 16, by0 + 10), "Pico 2 W (no breadboard)", font=font(24, True), fill=INK)
    d.rectangle((bx0 + 40, by0 + 60, bx0 + 260, by0 + 480), fill=(30, 110, 60), outline=INK, width=2)
    d.text((bx0 + 150, by0 + 270), "Pico 2 W\nemulator\nfirmware\n(17140 ROM\n+ your tune)", font=font(18, True), fill="white",
           anchor="mm", align="center")  # fmt: skip
    notes = ["Jumpers straight from its header.", "Every pin the ECU drives is on", "GP0-22 (5 V tolerant while the",
             "Pico is powered); GP26-28 carry", "only P12-P14, always outputs.", "So no resistors are needed."]  # fmt: skip
    for i, s in enumerate(notes):
        d.text((bx0 + 300, by0 + 70 + i * 25), s, font=font(17), fill=INK)
    box(d, (bx0 + 300, by0 + 300, bx1 - 20, by0 + 470), (255, 244, 225), "Only if the chip is CMOS:",
        ["2x 74HCT541 on the 12 outputs (on", "a small breadboard), powered by one", "more wire from ECU pin 21",
         "(decided by the supply-current check)"], tsize=18, outline=ORANGE)  # fmt: skip

    # laptop + power order
    box(d, (1180, 820, 1860, 1010), (240, 232, 250), "Laptop (USB)", ["powers the Pico, flashes the tune, logs live values",
        "", "Power order: USB in  →  then key on", "               key off  →  then USB out"], outline=PURPLE)  # fmt: skip
    d.line([(1350, 820), (1350, by1)], fill=PURPLE, width=5)
    d.text((1362, 780), "USB", font=font(17, True), fill=PURPLE)

    # test steps
    box(d, (40, 780, 1120, 1110), (232, 242, 255), "Use, in order (each powered step: owner's OK on the day)", [
        "0. Strict bench gate passed first: every pin exact, replay passes, repeat runs identical,",
        "   plus a run covering idle contact, cranking, rev limit, missing IGF and the T terminal.",
        "1. Unpowered: meter check of socket pins 15-17; read the P36/P42-P47 straps (Q12);",
        "   fit the 26 jumpers by the wire table; check each by continuity.",
        "2. USB in. Key on, engine off: fault lamp, fuel-pump prime, live coolant/MAP/TPS",
        "   values over USB against the stock ECU's readings (serial link).",
        "3. Crank and idle: timing light shows 16° BTDC (T open) and 10° (T to E1 shorted).",
        "4. Key off, then USB out. Driving waits for the PCB (jumpers can shake loose).",
        "Still to write: the car firmware: emulator on real ECU pins (PIO-timed inputs,",
        "hardware-timed spark and injector, /RES from the ECU, E at 1 MHz on pin 40, USB logging).",
    ], tsize=21, outline=BLUE)  # fmt: skip
    return img


def main() -> int:
    import sys

    if "--table" in sys.argv:
        print(table())
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    draw().save(OUT, optimize=True)
    draw_wiring()
    print(f"wrote {OUT.relative_to(ROOT)}, {WIRING.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
