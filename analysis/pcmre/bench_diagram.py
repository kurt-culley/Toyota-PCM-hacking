"""Picture of the ECU bench setup (docs/hardware/ecu_bench_setup.md).

    PYTHONPATH=analysis uv run python -m pcmre.bench_diagram

Writes docs/hardware/photos/ecu_bench/bench_setup.png: a top-down sketch of the bench, with the
spare ECU in the middle, the engine Pico (old Pico WH) on the connector side, the emulator Pico
2 W on the CPU-socket side (stage 1), the sensor stand-ins, the dummy loads and the 12 V supply.
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from .roundtrip import ROOT

OUT = ROOT / "docs/hardware/photos/ecu_bench/bench_setup.png"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

W, H = 1900, 1250
BG = (250, 250, 247)
INK = (30, 30, 30)
C = {
    "12v": (200, 30, 30), "gnd": (40, 40, 40), "sig": (30, 90, 200), "out": (220, 120, 0),
    "sens": (20, 140, 70), "usb": (120, 60, 160), "ribbon": (130, 130, 130),
}  # fmt: skip


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(BOLD if bold else FONT, size)


def box(d: ImageDraw.ImageDraw, xy, fill, title: str, lines: list[str] = (), outline=INK, tsize=24) -> None:
    d.rounded_rectangle(xy, radius=14, fill=fill, outline=outline, width=3)
    x0, y0, x1, _ = xy
    d.text((x0 + 14, y0 + 10), title, font=font(tsize, True), fill=INK)
    for i, s in enumerate(lines):
        d.text((x0 + 14, y0 + 16 + tsize + i * 24), s, font=font(18), fill=INK)


def wire(d: ImageDraw.ImageDraw, pts, colour, label: str = "", width=5, at: int = 0, dy: int = -24) -> None:
    d.line(pts, fill=colour, width=width, joint="curve")
    if label:
        (x0, y0), (x1, y1) = pts[at], pts[at + 1]
        d.text(((x0 + x1) / 2 - 8 * len(label) / 2, (y0 + y1) / 2 + dy), label, font=font(17, True), fill=colour)


def draw() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 24), "ECU bench setup (draft): spare 17140 ECU with a simulated engine", font=font(34, True), fill=INK)
    sub = (
        "Stage 0: the real D151801 in its socket.   Stage 1: the D151801 out, the emulator Pico 2 W plugged in "
        "through a ribbon.   Every powered step needs the owner's OK."
    )
    d.text((40, 70), sub, font=font(19), fill=INK)

    # 12 V supply
    box(
        d,
        (60, 130, 380, 300),
        (255, 235, 235),
        "Bench 12 V supply",
        ["fused 3 A", "+ to +B, +B1, BATT", "- to E01/E02/E1"],
    )
    # laptop
    box(
        d,
        (1500, 130, 1840, 300),
        (240, 232, 250),
        "Laptop",
        ["USB to both Picos", "logging, comparison,", "flashing tunes"],
    )

    # ECU board
    ex0, ey0, ex1, ey1 = 560, 360, 1340, 900
    d.rounded_rectangle((ex0, ey0, ex1, ey1), radius=18, fill=(214, 236, 214), outline=INK, width=4)
    d.text((ex0 + 18, ey0 + 12), "Spare 17140 ECU (case open)", font=font(26, True), fill=INK)
    d.text((ex0 + 18, ey0 + 48), "5 V regulator, NE/G conditioner, ADC hybrid,", font=font(18), fill=INK)
    d.text((ex0 + 18, ey0 + 72), "igniter and injector drivers: all unchanged", font=font(18), fill=INK)
    # edge connector (left side of the ECU)
    d.rectangle((ex0 - 30, ey0 + 110, ex0 + 10, ey1 - 40), fill=(60, 60, 60))
    d.text((ex0 + 50, ey1 - 34), "edge connector", font=font(16), fill=INK)
    # CPU socket
    sx0, sy0 = 1010, 470
    d.rectangle((sx0, sy0, sx0 + 230, sy0 + 330), fill=(40, 40, 40), outline=INK, width=3)
    for i in range(20):
        y = sy0 + 12 + i * 16
        d.rectangle((sx0 - 12, y, sx0, y + 8), fill=(200, 200, 200))
        d.rectangle((sx0 + 230, y, sx0 + 242, y + 8), fill=(200, 200, 200))
    d.ellipse((sx0 + 100, sy0 - 8, sx0 + 130, sy0 + 12), fill=(214, 236, 214))
    d.text((sx0 + 22, sy0 + 120), "CPU socket", font=font(22, True), fill=(255, 255, 255))
    d.text((sx0 + 22, sy0 + 150), "(DIP-40)", font=font(18), fill=(255, 255, 255))
    d.text((sx0 + 22, sy0 + 190), "stage 0: D151801", font=font(17), fill=(255, 255, 255))
    d.text((sx0 + 22, sy0 + 214), "stage 1: ribbon plug", font=font(17), fill=(255, 255, 255))

    # engine Pico breadboard (left)
    box(d, (40, 470, 430, 900), (230, 240, 255), "Engine Pico", [
        "old Pico WH (RP2040, 3.3 V only)", "", "makes NE every 30 deg, G every 180",
        "echoes IGF 20 us after each spark",
        "timestamps IGT and injector edges", "", "interface parts on the breadboard:", "  series resistors on NE, G",
        "  NPN transistor on IGF", "  dividers + 3.3 V Zeners on", "  IGT, #10, #20",
    ])  # fmt: skip

    # emulator breadboard (right)
    box(d, (1440, 430, 1860, 900), (255, 244, 225), "Emulator (stage 1)", [
        "Pico 2 W running the D151801", "emulation + the 17140 ROM", "", "2x 74HCT541: Pico outputs", "to 5 V levels",
        "", "26 signals to the socket", "reads J8 and the trim jumpers", "(answers Q10 / Q12)",
    ])  # fmt: skip

    # sensor stand-ins (bottom left)
    box(d, (40, 960, 520, 1200), (230, 250, 236), "Sensor stand-ins", [
        "pot: PIM (manifold pressure)", "pot: VTA (throttle) + switch: IDL", "resistor: THW ~300 ohm (hot)",
        "resistor: THA ~2.2 kohm (20 C)", "pot: OX (mixture screw, GUESS)",
    ])  # fmt: skip
    # loads (bottom right)
    box(d, (1060, 960, 1560, 1200), (255, 240, 225), "Dummy loads to 12 V", [
        "#10, #20: 47 ohm 5 W (or 12 V bulbs)", "STH (T-VIS), FC (pump), VISC, W:", "12 V bulbs or LEDs + resistors",
        "so every output can be seen",
    ])  # fmt: skip

    # wires: 12 V
    wire(d, [(380, 200), (470, 200), (470, 380), (ex0 - 30, 380), (ex0 - 30, ey0 + 110)], C["12v"], "+12 V", at=0)
    wire(d, [(380, 260), (450, 260), (450, 930), (ex0 - 10, 930), (ex0 - 10, ey1 - 40)], C["gnd"])
    d.text((395, 266), "ground", font=font(17, True), fill=C["gnd"])
    # engine Pico <-> connector
    for y, col, label in ((560, "sig", "NE, G  ->"), (620, "sig", "IGF  ->"), (690, "out", "<- IGT"),
                          (750, "out", "<- #10, #20")):  # fmt: skip
        wire(d, [(430, y), (ex0 - 30, y)], C[col])
        d.text((458, y - 24), label, font=font(16, True), fill=C[col])
    # sensors -> connector
    wire(d, [(520, 1040), (610, 1040), (610, ey1 - 60), (ex0 - 30, ey1 - 60)], C["sens"])
    d.text((626, 1010), "VCC, PIM, VTA, IDL,", font=font(17, True), fill=C["sens"])
    d.text((626, 1032), "THW, THA, OX, E2", font=font(17, True), fill=C["sens"])
    # loads <- connector
    wire(d, [(1060, 1110), (820, 1110), (820, ey1)], C["out"])
    d.text((836, 1120), "#10, #20, STH, FC, VISC, W", font=font(17, True), fill=C["out"])
    # ribbon emulator -> socket
    for k in range(5):
        d.line([(1440, 600 + 12 * k), (1300, 600 + 12 * k), (1252, 560 + 12 * k)], fill=C["ribbon"], width=4)
    d.text((1290, 690), "40-way ribbon", font=font(16, True), fill=(90, 90, 90))
    d.text((1290, 710), "+ DIP-40 plug", font=font(16, True), fill=(90, 90, 90))
    # USB
    wire(d, [(1600, 300), (1600, 430)], C["usb"], "USB", dy=-10)
    wire(d, [(1700, 300), (1700, 330), (235, 330), (235, 470)], C["usb"], "USB", at=1, dy=-26)

    # legend
    lx, ly = 1600, 960
    d.text((lx, ly), "Wires", font=font(20, True), fill=INK)
    for i, (name, col) in enumerate([("12 V supply", "12v"), ("ground", "gnd"), ("engine signals in", "sig"),
                                     ("ECU outputs", "out"), ("sensor stand-ins", "sens"), ("USB", "usb"),
                                     ("ribbon (stage 1)", "ribbon")]):  # fmt: skip
        y = ly + 34 + i * 28
        d.line([(lx, y + 10), (lx + 50, y + 10)], fill=C[col], width=6)
        d.text((lx + 62, y), name, font=font(17), fill=INK)
    return img


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    draw().save(OUT)
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
