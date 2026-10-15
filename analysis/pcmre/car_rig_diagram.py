# ruff: noqa: E501  (a drawing: long literal label lists)
"""Picture of the proposed in-car test rig (docs/mr2/cpu_replacement.md, "In-car test rig").

    PYTHONPATH=analysis uv run python -m pcmre.car_rig_diagram

The chip-in-isolation breadboard, with the D151801 replaced by a DIP-40 ribbon jumper to the spare
ECU's CPU socket and the Pico running the emulator. Writes docs/hardware/photos/car_rig/car_rig.png.
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from .roundtrip import ROOT

OUT = ROOT / "docs/hardware/photos/car_rig/car_rig.png"
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
    d.text((40, 22), "In-car test rig (proposed): the chip-test breadboard as the CPU", font=font(34, True), fill=INK)
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
    d.text((sx0 + 100, sy0 + 120), "CPU socket\n(chip out)\n\nDIP-40 plug\nof the ribbon", font=font(18, True), fill="white",
           anchor="mm", align="center")  # fmt: skip

    # ribbon
    for k in range(6):
        d.line([(sx0 + 210, sy0 + 60 + 14 * k), (1220, 560 + 14 * k)], fill=(150, 150, 150), width=5)
    d.text(
        (990, 250),
        "40-way ribbon\n~30 cm, DIP-40\nplug at both\nends: the one\nnew part",
        font=font(16, True),
        fill=(90, 90, 90),
    )

    # breadboard
    bx0, by0, bx1, by1 = 1180, 150, 1860, 760
    d.rounded_rectangle((bx0, by0, bx1, by1), radius=16, fill=(245, 243, 236), outline=GREY, width=3)
    d.text((bx0 + 16, by0 + 10), "Breadboard (from the chip test)", font=font(24, True), fill=INK)
    d.rectangle((bx0 + 40, by0 + 60, bx0 + 260, by0 + 330), fill=(30, 110, 60), outline=INK, width=2)
    d.text((bx0 + 150, by0 + 195), "Pico 2 W\nemulator\nfirmware\n(17140 ROM\n+ your tune)", font=font(18, True), fill="white",
           anchor="mm", align="center")  # fmt: skip
    d.rectangle((bx0 + 40, by0 + 360, bx0 + 260, by0 + 560), fill=(70, 70, 70), outline=INK, width=2)
    d.text((bx0 + 150, by0 + 460), "ribbon's DIP-40\nplug, where\nthe chip sat\n(notch down)", font=font(17, True),
           fill="white", anchor="mm", align="center")  # fmt: skip
    for i in range(7):  # the existing signal wires, Pico to the plug's holes
        d.line([(bx0 + 70 + i * 28, by0 + 330), (bx0 + 70 + i * 28, by0 + 360)], fill=GREY, width=4)
    keep = ["KEEP (grey): all 26 signal wires,", "ground, the three 1 kΩ on GP26-28", "", "REMOVE (red):"]
    rem = ["5 V jumper; pins 21, 4, 5, 7 to + rail", "EXTAL wire + pull-up; /RES pull-up", "3 mode straps; P42-P47 jumpers +",
           "resistor; P36 ground wire", "(the ECU board sets all of these)"]  # fmt: skip
    for i, s in enumerate(keep):
        d.text((bx0 + 320, by0 + 70 + i * 25), s, font=font(17, i == 3), fill=GREY if i < 2 else RED)
    for i, s in enumerate(rem):
        d.text((bx0 + 320, by0 + 170 + i * 25), "  " + s, font=font(17), fill=RED)
    box(d, (bx0 + 300, by0 + 330, bx1 - 20, by0 + 470), (255, 244, 225), "Only if the chip is CMOS:",
        ["2x 74HCT541 on the 12 outputs,", "powered from ECU pin 21", "(decided by the supply-current check)"], tsize=18,
        outline=ORANGE)  # fmt: skip

    # laptop + power order
    box(d, (1180, 820, 1860, 1010), (240, 232, 250), "Laptop (USB)", ["powers the Pico, flashes the tune, logs live values",
        "", "Power order: USB in  →  then key on", "               key off  →  then USB out"], outline=PURPLE)  # fmt: skip
    d.line([(1350, 820), (1350, by1)], fill=PURPLE, width=5)
    d.text((1362, 780), "USB", font=font(17, True), fill=PURPLE)

    # test steps
    box(d, (40, 780, 1120, 1110), (232, 242, 255), "Use, in order (each powered step: owner's OK on the day)", [
        "0. Strict bench gate passed first: every pin exact, replay passes, repeat runs identical,",
        "   plus a run covering idle contact, cranking, rev limit, missing IGF and the T terminal.",
        "1. Unpowered: rework the breadboard (red items), fit the ribbon, check by continuity.",
        "2. USB in. Key on, engine off: fault lamp, fuel-pump prime, live coolant/MAP/TPS",
        "   values over USB against the stock ECU's readings (serial link).",
        "3. Crank and idle: timing light shows 16° BTDC (T open) and 10° (T to E1 shorted).",
        "4. Key off, then USB out. Driving waits for the PCB (a breadboard can shake loose).",
        "",
        "Still to write: the car firmware: emulator on real ECU pins (PIO-timed inputs,",
        "hardware-timed spark and injector, /RES from the ECU, E at 1 MHz on pin 40, USB logging).",
    ], tsize=21, outline=BLUE)  # fmt: skip
    return img


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    draw().save(OUT, optimize=True)
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
