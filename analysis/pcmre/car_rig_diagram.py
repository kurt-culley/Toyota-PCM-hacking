# ruff: noqa: E501  (a drawing: long literal label lists)
"""Pictures of the proposed in-car test rig (docs/mr2/cpu_replacement.md, "In-car test rig").

    PYTHONPATH=analysis uv run python -m pcmre.car_rig_diagram            # both pictures
    PYTHONPATH=analysis uv run python -m pcmre.car_rig_diagram --table    # the wire table

The Pico on a half-size breadboard, with one jumper wire per used CPU pin from the Pico's own strip
to a spare turned-pin DIP-40 socket pressed into the spare ECU's CPU socket; the Pico runs the
emulator. The pin map is the chip test's (chipdiff.h), so the same firmware pins serve both, and
the chip-test board stays as it is. Writes docs/hardware/photos/car_rig/car_rig.png (overview) and
breadboard_car.png (hole by hole); --table prints the wire table for docs/mr2/cpu_replacement.md.
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from . import chipdiff_wiring as C
from . import wiring as BB
from .roundtrip import ROOT

OUT = ROOT / "docs/hardware/photos/car_rig/car_rig.png"
BREADBOARD = ROOT / "docs/hardware/photos/car_rig/breadboard_car.png"
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

ROWS = 30  # a half-size (400-point) breadboard: the Pico takes rows 1-20
UNUSED = {3: "EXTAL: the ECU's crystal drives it; the car firmware makes its own clock"}
GND_PICO_PIN = 3


def car_wires() -> list[tuple[int, str, str, str]]:
    """(ECU socket pin, signal, Pico end, breadboard hole): one jumper each, from a free hole in the
    Pico pin's strip (or, for GP26-28, the far side of its 1 kΩ) to the same pin of the socket. Every
    GPIO the chip test wires, except EXTAL, plus ground."""
    rows = [(1, "GND", f"GND (Pico pin {GND_PICO_PIN})", BB._free(BB.pico_hole(GND_PICO_PIN)))]
    for g, (pin, name) in C.gpio_pins().items():
        if pin in UNUSED:
            continue
        if g in C.SERIES_ROWS:
            rows.append((pin, name, f"GP{g} via 1 kΩ", f"j{C.SERIES_ROWS[g]}"))
        else:
            pp = BB.PICO_PIN[f"GP{g}"]
            rows.append((pin, name, f"GP{g} (Pico pin {pp})", BB._free(BB.pico_hole(pp))))
    return sorted(rows)


def table() -> str:
    rows = ["| ECU socket pin | Signal | Pico end | Breadboard hole |", "|---|---|---|---|"]
    rows += [f"| {p} | {n} | {g} | {h} |" for p, n, g, h in car_wires()]
    return "\n".join(rows)


def car_layout() -> tuple[list[tuple[str, str, str, str]], list[tuple[str, str, str]]]:
    """What sits on the small board besides the Pico: GP26-28 (ADC pins, not 5 V tolerant) each run
    to a row below the Pico, through a 1 kΩ across the centre gap, as on the chip-test board. No
    rails, no 5 V."""
    wires, parts = [], []
    for g, r in C.SERIES_ROWS.items():
        pp = BB.PICO_PIN[f"GP{g}"]
        pin, name = C.gpio_pins()[g]
        wires.append(
            (f"R{g - 25}", BB._free(BB.pico_hole(pp)), f"b{r}", f"GP{g} (Pico pin {pp}) → 1 kΩ in row {r} → {name}")
        )
        parts.append((f"1 kΩ (GP{g})", f"e{r}", f"f{r}"))
    return wires, parts


def draw_breadboard_car(out=BREADBOARD) -> None:
    wires, parts = car_layout()
    jumpers = car_wires()
    purple = (130, 50, 170)
    head = [
        ("In-car test rig: breadboard layout (Pico 2 W on a half-size breadboard)", font(22, True), "black"),
        ("Generated from chipdiff.h (python -m pcmre.car_rig_diagram). Unpowered work only: USB out, ECU out of the car.",
         font(15), "black"),
        ("The chip-test board stays as it is. Nothing on the rails: this board carries no 5 V.", font(15, True), "black"),
        ("PURPLE E# = a jumper from this hole to pin # of the spare socket in the ECU.", font(15, True), purple),
        ("Check each purple jumper by continuity (breadboard hole to ECU socket pin) before anything is powered.",
         font(15, True), (190, 0, 0)),
        ("Power order in the car: USB in, then key on; key off, then USB out.", font(15, True), (190, 0, 0)),
    ]  # fmt: skip

    def extra(d, xy, kx, ky):
        f12, f15, f15b = font(12), font(15), font(15, True)
        for pin, _, _, hole in jumpers:
            x, y = xy(hole)
            d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=purple, outline="black")
            d.text((x, y), f"E{pin}", fill="white", font=font(9, True), anchor="mm")
        ky += 30
        d.text((kx, ky), "Jumpers to the ECU (26, male-to-male, ~20 cm)", fill=purple, font=f15b)
        d.text((kx, ky + 24), "into the spare turned-pin DIP-40 socket pressed into the ECU's CPU socket,",
               fill="black", font=f15)  # fmt: skip
        d.text((kx, ky + 46), "never straight into the ECU's own socket. Socket top view, notch up:",
               fill="black", font=f15)  # fmt: skip
        used = {pin: (name, hole) for pin, name, _, hole in jumpers}
        sx, sy, pitch = kx + 300, ky + 90, 24
        d.rectangle([sx, sy - 14, sx + 150, sy + 19 * pitch + 14], fill=(60, 60, 60), outline="black")
        d.pieslice([sx + 57, sy - 32, sx + 93, sy + 4], 0, 180, fill="white")
        d.text((sx + 75, sy + 9.5 * pitch), "ECU CPU\nsocket\n(spare\nsocket in)", fill="white", font=f12, anchor="mm",
               align="center")  # fmt: skip
        for i in range(20):
            for pin, x, side in ((i + 1, sx, -1), (40 - i, sx + 150, 1)):
                y = sy + i * pitch
                on = pin in used
                d.ellipse([x - 11, y - 11, x + 11, y + 11], fill=purple if on else (200, 200, 200), outline="black")
                d.text((x, y), f"E{pin}" if on else str(pin), fill="white" if on else "black", font=font(9, True),
                       anchor="mm")  # fmt: skip
                label = f"{used[pin][0]}  ← {used[pin][1]}" if on else "no wire (the ECU board's)"
                if on and side > 0:
                    label = f"{used[pin][1]} →  {used[pin][0]}"
                d.text((x + side * 18, y), label, fill="black" if on else (140, 140, 140), font=f12,
                       anchor="rm" if side < 0 else "lm")  # fmt: skip

    BB.draw_breadboard(out, layout=(wires, parts), head=head, wire_colour=lambda t, w: (110, 110, 110),
                       part_colour=lambda pt: (60, 190, 90), chip=False, extra=extra, rows=ROWS,
                       height=1180)  # fmt: skip


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
        (40, 22), "In-car test rig (proposed): a Pico on a small breadboard as the CPU", font=font(34, True), fill=INK
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
    d.text((990, 420), "26 jumper wires\n(25 signals +\nGND), ~20 cm,\nPico strip to\nsocket pin:\nno new parts",
           font=font(16, True), fill=(90, 90, 90))  # fmt: skip

    # breadboard
    bx0, by0, bx1, by1 = 1180, 150, 1860, 760
    d.rounded_rectangle((bx0, by0, bx1, by1), radius=16, fill=(245, 243, 236), outline=GREY, width=3)
    d.text((bx0 + 16, by0 + 10), "Half-size breadboard", font=font(24, True), fill=INK)
    d.rectangle((bx0 + 40, by0 + 60, bx0 + 260, by0 + 400), fill=(30, 110, 60), outline=INK, width=2)
    d.text((bx0 + 150, by0 + 230), "Pico 2 W\nemulator\nfirmware\n(17140 ROM\n+ your tune)", font=font(18, True), fill="white",
           anchor="mm", align="center")  # fmt: skip
    for i in range(3):  # the three 1 kΩ below the Pico
        y = by0 + 440 + i * 34
        d.line([(bx0 + 60, y), (bx0 + 240, y)], fill=(90, 90, 90), width=3)
        d.rectangle((bx0 + 125, y - 8, bx0 + 175, y + 8), fill=(60, 190, 90), outline=INK)
    d.text((bx0 + 150, by0 + 555), "1 kΩ on GP26-28", font=font(16, True), fill=INK, anchor="mm")
    notes = ["On this board: the Pico and three", "1 kΩ (GP26-28 are ADC pins, not 5 V", "tolerant). Nothing on the rails:",
             "no 5 V here. Each jumper starts", "in its Pico pin's own strip.", "",
             "The chip-test board stays as it is,", "ready to re-run the bench gate."]  # fmt: skip
    for i, s in enumerate(notes):
        d.text((bx0 + 300, by0 + 70 + i * 25), s, font=font(17), fill=INK)
    box(d, (bx0 + 300, by0 + 300, bx1 - 20, by0 + 470), (255, 244, 225), "Only if the chip is CMOS:",
        ["2x 74HCT541 on the 12 outputs,", "powered by one more wire", "from ECU pin 21",
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
        "1. Unpowered: Pico + 3x 1 kΩ on the small board, 26 jumpers by the wire table, check by continuity.",
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
    import sys

    if "--table" in sys.argv:
        print(table())
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    draw().save(OUT, optimize=True)
    draw_breadboard_car()
    print(f"wrote {OUT.relative_to(ROOT)}, {BREADBOARD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
