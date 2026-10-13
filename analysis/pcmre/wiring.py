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


# --- Physical layout on an 830-point breadboard (Pico 2 WH) -------------------------------------------
#
# Holes a-e | centre gap | f-j across, rows 1-63 along; a +/- rail pair runs beside column a and beside j.
# Both parts sit face up across the gap. The Pico uses columns c and h (0.7" header rows), USB off the
# row-1 end, so its pin 1 is c1 and a-b and i-j stay free. The 6301 (0.6") uses columns d and h, rows
# 25-44, NOTCH TOWARDS ROW 44, so its bus pins (21-40, column d) face the Pico's GP0-15 side: pin 1 is h44.
COLS = "abcdefghij"
CHIP_ROW0 = 25
RAIL_LINK_ROWS = {"+": 50, "-": 52}
EXTAL_JOIN_ROW = 47  # free f-j strip joining the two EXTAL pull-up resistors


def pico_hole(pin: int) -> tuple[str, int]:
    return ("c", pin) if pin <= 20 else ("h", 41 - pin)


def chip_hole(pin: int) -> tuple[str, int]:
    return ("h", CHIP_ROW0 + 20 - pin) if pin <= 20 else ("d", CHIP_ROW0 + pin - 21)


def _free(hole: tuple[str, int], k: int = 0) -> str:
    """The k-th free hole in a pin's row, counted outwards from the part."""
    col, row = hole
    side = {"c": "ba", "d": "cba", "h": "ij"}[col]
    return f"{side[k]}{row}"


def _rail(name: str, row: int) -> str:
    return f"{name}@{row}"


def is_rail(h: str) -> bool:
    return "@" in h


def _row(hole: str) -> int:
    return int(hole.split("@")[1]) if is_rail(hole) else int(hole[1:])


def breadboard() -> tuple[list[tuple[str, str, str, str]], list[tuple[str, str, str]]]:
    """(wires, parts) for the Pico 2 WH layout.

    wires: (tag, from, to, what); parts: (part, from, to). Holes are like "b26"; rail holes are like
    "j+@42": the + strip beside column j, level with row 42.
    """
    sig = board_pins("pico2w")
    dip = {name: pin for pin, name in DIP.items()}

    def to_rail(hole: str, rail: str) -> tuple[str, str]:
        return hole, _rail(rail, _row(hole))

    wires: list[tuple[str, str, str, str]] = []
    for pin in sorted((p for p in DIP if DIP[p] in sig), key=lambda p: (p <= 20, chip_hole(p)[1])):
        name, g = DIP[pin], sig[DIP[pin]]
        pp = PICO_PIN[f"GP{g}"]
        chip = _free(chip_hole(pin), 1 if pin > 20 else 0)
        wires.append((str(len(wires) + 1), chip, _free(pico_hole(pp)), f"{name} (pin {pin}) → GP{g} (Pico pin {pp})"))
    wires += [
        ("5V", *to_rail(_free(pico_hole(40)), "j+"), "THE 5 V JUMPER: Pico VBUS → + rail beside j. Last in, first out"),
        ("G1", *to_rail(_free(pico_hole(3)), "a-"), "Pico GND → − rail beside a"),
        ("G2", *to_rail(_free(pico_hole(38)), "j-"), "Pico GND → − rail beside j"),
        ("L+", _rail("a+", RAIL_LINK_ROWS["+"]), _rail("j+", RAIL_LINK_ROWS["+"]), "link the two + rails"),
        ("L−", _rail("a-", RAIL_LINK_ROWS["-"]), _rail("j-", RAIL_LINK_ROWS["-"]), "link the two − rails"),
        ("Vcc", *to_rail(_free(chip_hole(21), 1), "a+"), "6301 pin 21 Vcc → + rail beside a"),
        ("Vss", *to_rail(_free(chip_hole(1), 1), "j-"), "6301 pin 1 Vss → − rail beside j"),
    ]
    wires += [(DIP[p], *to_rail(_free(chip_hole(p), 1), "j+"), f"6301 pin {p} {DIP[p]} → + rail beside j")
              for p in (4, 5, 7)]  # fmt: skip
    beside_vcc = chip_hole(21)[1] - 1
    parts = [
        # both decoupling capacitors plug straight across the two rail strips beside column a,
        # either side of the Vcc wire (b25), so neither has to cross a strip
        ("100 nF (or 47 nF '473'), either way round", _rail("a+", beside_vcc + 2), _rail("a-", beside_vcc + 2)),
        ("10 µF, + leg on the + rail", _rail("a+", beside_vcc), _rail("a-", beside_vcc)),
        # EXTAL pull-up: 470 Ω, here built as 330 Ω + 220 Ω in series (550 Ω, within 470 Ω-2.2 kΩ),
        # joined in the free row EXTAL_JOIN_ROW. A single 470 Ω straight from j42 to the rail also works.
        ("330 Ω, EXTAL pull-up part 1", _free(chip_hole(dip["EXTAL"]), 1), f"j{EXTAL_JOIN_ROW}"),
        ("220 Ω, EXTAL pull-up part 2", f"i{EXTAL_JOIN_ROW}", _rail("j+", EXTAL_JOIN_ROW)),
        ("10 kΩ", *to_rail(_free(chip_hole(dip["/RES"]), 1), "j+")),
        ("10 kΩ", *to_rail(_free(chip_hole(dip["P24/TX"]), 1), "j+")),
        *[("10 kΩ", *to_rail(_free(chip_hole(dip[s]), 1), "j-")) for s in ("P20", "P21", "P22")],
    ]
    return wires, parts


def hole_name(h: str) -> str:
    if not is_rail(h):
        return h
    return f"{'+' if '+' in h else '−'} rail beside {h[0]} (row {_row(h)})"


def breadboard_table() -> str:
    wires, parts = breadboard()
    rows = ["| Wire | From | To | What |", "|---|---|---|---|"]
    rows += [f"| {t} | {hole_name(a)} | {hole_name(b)} | {w} |" for t, a, b, w in wires]
    rows += ["", "| Part | From | To |", "|---|---|---|"]
    rows += [f"| {part} | {hole_name(a)} | {hole_name(b)} |" for part, a, b in parts]
    return "\n".join(rows)


def draw_breadboard(out: Path) -> None:
    """A top view, row 1 on the left: on a real board that puts column j at the top and a at the bottom."""
    from PIL import Image, ImageDraw, ImageFont

    def font(size: int, bold: bool = False):
        try:
            return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)
        except OSError:
            return ImageFont.load_default()

    wires, parts = breadboard()
    p, x0, top = 26, 70, 150  # pitch and origin, px
    # lane (y) of each hole column and rail, in pitches; the centre gap is 3 pitches (e to f = 0.3")
    lane = {"j-": 0, "j+": 1, **{c: 3 + i for i, c in enumerate("jihgf")}, **{c: 10 + i for i, c in enumerate("edcba")},
            "a+": 16, "a-": 17}  # fmt: skip
    f10, f13b, f15, f15b, f24b = font(10), font(13, True), font(15), font(15, True), font(24, True)
    img = Image.new("RGB", (x0 + 64 * p + 40, 1200), "white")
    d = ImageDraw.Draw(img)

    def xy(hole: str) -> tuple[int, int]:
        key = hole.split("@")[0] if is_rail(hole) else hole[0]
        return x0 + _row(hole) * p, top + lane[key] * p

    def vlabel(text: str, cx: int, cy: int, colour) -> None:
        t = Image.new("RGBA", (int(d.textlength(text, font=f10)) + 4, 16), (0, 0, 0, 0))
        ImageDraw.Draw(t).text((2, 0), text, fill=colour, font=f10)
        t = t.rotate(90, expand=True)
        img.paste(t, (cx - t.width // 2, cy - t.height // 2), t)

    head = [
        ("HD6301 / D151801 ROM reader: breadboard layout (Raspberry Pi Pico 2 WH, 830-point board)", f24b, "black"),
        ("Top view, row 1 on the left. Generated from pins.h (python -m pcmre.wiring --png). Same number = one wire.",
         f15, "black"),
        ("Chip NOTCH points to row 44, away from the Pico. Pink wire = the 5 V jumper: last in, first out.",
         f15b, (190, 0, 0)),
    ]  # fmt: skip
    for i, (t, fnt, c) in enumerate(head):
        d.text((30, 20 + i * 30), t, fill=c, font=fnt)
    # the board, its holes and rails
    d.rounded_rectangle([x0 - 25, top - 30, x0 + 64 * p, top + 18 * p + 15], 10, fill=(245, 243, 236), outline="grey")
    d.rectangle([x0, top + 7 * p + 6, x0 + 63 * p, top + 10 * p - 6], fill=(225, 222, 212))
    for name in ("j-", "j+", "a+", "a-"):
        y = top + lane[name] * p
        c = (200, 0, 0) if "+" in name else (0, 90, 200)
        dy = -12 if name in ("j-", "a+") else 12
        d.line([x0 + p // 2, y + dy, x0 + 63 * p, y + dy], fill=c, width=2)
        d.text((x0 - 15, y), "+" if "+" in name else "−", fill=c, font=f13b, anchor="mm")
    for key, y_lane in lane.items():
        y = top + y_lane * p
        if len(key) == 1:
            d.text((x0 - 15, y), key, fill="black", font=f13b, anchor="mm")
        for r in range(1, 64):
            d.rectangle([x0 + r * p - 3, y - 3, x0 + r * p + 3, y + 3], fill=(150, 150, 150))
    for r in [1, *range(5, 64, 5)]:
        d.text((x0 + r * p, top - 20), str(r), fill="black", font=f10, anchor="mm")
        d.text((x0 + r * p, top + 18 * p + 2), str(r), fill="black", font=f10, anchor="mm")
    # Pico 2 WH, face up, USB off the row-1 end
    yh, yc = top + lane["h"] * p, top + lane["c"] * p
    d.rectangle([x0 + p // 2 - 4, yh - 12, x0 + 20 * p + p // 2, yc + 12], fill=(30, 110, 60), outline="black")
    d.rectangle([x0 - 22, (yc + yh) // 2 - 22, x0 + 8, (yc + yh) // 2 + 22], fill=(190, 190, 190), outline="black")
    d.text((x0 - 7, (yc + yh) // 2), "USB", fill="black", font=f10, anchor="mm")
    d.text((x0 + 10 * p + p // 2, (yc + yh) // 2), "Pico 2 WH (face up)", fill="white", font=f15, anchor="mm")
    for pin, label in PICO.items():
        col, r = pico_hole(pin)
        x, y = x0 + r * p, top + lane[col] * p
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(230, 190, 60), outline="black")
        short = {"3V3(OUT)": "3V3", "ADC_VREF": "VREF", "3V3_EN": "EN"}.get(label, label)
        vlabel(f"{pin} {short}", x, y + (34 if col == "h" else -34), "white")
    # 6301, face up, notch towards row 44
    yd = top + lane["d"] * p
    xa, xb = x0 + CHIP_ROW0 * p - p // 2, x0 + (CHIP_ROW0 + 19) * p + p // 2
    d.rectangle([xa, yh - 12, xb, yd + 12], fill=(40, 40, 40), outline="black")
    d.pieslice([xb - 18, (yd + yh) // 2 - 18, xb + 18, (yd + yh) // 2 + 18], 90, 270, fill=(245, 243, 236))
    d.text(((xa + xb) // 2, (yd + yh) // 2), "D151801 (face up)   notch →", fill="white", font=f15, anchor="mm")
    for pin, name in DIP.items():
        col, r = chip_hole(pin)
        x, y = x0 + r * p, top + lane[col] * p
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(200, 200, 200), outline="black")
        vlabel(f"{pin} {name}", x, y + (36 if col == "h" else -36), "white")
    # parts: drawn from the hole to the rail, label turned along the part
    for part, a, b in parts:
        (xa_, ya), (xb_, yb) = xy(a), xy(b)
        d.line([xa_, ya, xb_, yb], fill=(90, 90, 90), width=2)
        mx, my = (xa_ + xb_) // 2, (ya + yb) // 2
        if "F" in part:  # capacitor across the two rail strips: legs marked, label beside
            for x, y in ((xa_, ya), (xb_, yb)):
                d.ellipse([x - 4, y - 4, x + 4, y + 4], fill="black")
            d.rectangle([mx - 6, my - 6, mx + 6, my + 6], fill=(60, 120, 220) if "µ" in part else (230, 160, 40),
                        outline="black")  # fmt: skip
            label = "10 µF (+ leg on +)" if "µ" in part else "47–100 nF"
            dx = -10 if "µ" in part else 10  # labels either side, so the two neighbours do not overlap
            ty = top + 18 * p + 26
            d.text((mx + dx, ty), label, fill="black", font=f10, anchor="rm" if dx < 0 else "lm")
            d.line([mx, my + 7, mx + dx // 2, ty], fill=(120, 120, 120), width=1)
            continue
        elif ya == yb:  # resistor lying along a row strip
            d.rectangle([mx - 9, my - 4, mx + 9, my + 4], fill=(225, 200, 150), outline="black")
            d.text((mx, my - 12), part.split(",")[0], fill="black", font=f10, anchor="mb")
            continue
        else:
            d.rectangle([mx - 4, my - 9, mx + 4, my + 9], fill=(225, 200, 150), outline="black")
        vlabel(part.split(",")[0], mx + 12, my, "black")
    # wires: short ones to a rail drawn in full, signal ones as numbered tags at both ends
    sig_colour = {"AD": (0, 110, 200), "A": (0, 140, 70), "ctl": (200, 90, 0)}
    for tag, a, b, what in wires:
        (xa_, ya), (xb_, yb) = xy(a), xy(b)
        if is_rail(b):
            colour = (230, 0, 160) if tag == "5V" else (200, 0, 0) if "+" in b else (0, 90, 200)
            d.line([xa_, ya, xb_, yb], fill=colour, width=4)
            continue
        kind = "AD" if what.startswith("AD") else "A" if re.match(r"A\d", what) else "ctl"
        for x, y in ((xa_, ya), (xb_, yb)):
            d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=sig_colour[kind], outline="black")
            d.text((x, y), tag, fill="white", font=f10, anchor="mm")
    # key
    ky = top + 18 * p + 40
    d.text((30, ky), "Signal wires", fill="black", font=f15b)
    sig = [w for w in wires if not is_rail(w[2])]
    for i, (tag, a, b, what) in enumerate(sig):
        col, row = divmod(i, 8)
        d.text((30 + col * 560, ky + 28 + row * 22), f"{tag:>2}: {a} ↔ {b}   {what}", fill="black", font=f15)
    ky2 = ky + 28 + 8 * 22 + 20
    d.text((30, ky2), "Power, ground and parts", fill="black", font=f15b)
    lines = [f"{w}: {hole_name(a)} ↔ {hole_name(b)}" for _, a, b, w in wires if is_rail(b)]
    lines += [f"{part}: {hole_name(a)} ↔ {hole_name(b)}" for part, a, b in parts]
    for i, t in enumerate(lines):
        col, row = divmod(i, 10)
        d.text((30 + col * 860, ky2 + 28 + row * 22), t, fill="black", font=f15)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, optimize=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--png", action="store_true")
    a = ap.parse_args()
    for b in BOARDS:
        print(f"## {b}\n\n{table(b)}\n")
    print(f"## local\n\n{local_table()}\n")
    print(f"## breadboard (pico2w)\n\n{breadboard_table()}")
    if a.png:
        for b in BOARDS:
            draw(b, PNG_DIR / f"wiring_{b}.png")
        draw_breadboard(PNG_DIR / "breadboard_pico2w.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
