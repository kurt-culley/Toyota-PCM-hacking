"""Digitise the graphs in Jeremy Ross's "Lifting the Lid" PDF (P1).

The PDF stores each figure as an upside-down JPEG. This script extracts them
with ``pdfimages``, flips them upright into ``docs/ross/figures/`` and reads
values off the Excel charts by pixel:

* the y axis is calibrated from two gridlines, and the x axis from the axis
  tick marks (both found by eye once and checked against the tick labels);
* a series is the set of pixels of its colour, and its value at x is the
  median y of those pixels in a 3-pixel column around x.

Readings are good to about +/-1 pixel; the ``resolution`` column gives that
step in data units. This is evidence level [PDF] (Ross's own plots), not ROM
data.

    PYTHONPATH=analysis uv run python -m ross.digitise     # needs poppler-utils (pdfimages)
"""

from __future__ import annotations

import csv
import statistics
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "Lifting The Lid on the mk1 MR2 ECU (Jeremy Ross).pdf"
OUT = ROOT / "docs/ross/figures"

Pixel = tuple[int, int, int]


def navy(p: Pixel) -> bool:
    return p[2] > 40 and p[0] < 60 and p[1] < 60 and p[2] - p[0] > 30


def magenta(p: Pixel) -> bool:
    return p[0] > 200 and p[2] > 200 and p[1] < 140


def lavender(p: Pixel) -> bool:  # the MX-correction chart's series colour, about (100, 93, 157)
    return 70 < p[0] < 140 and 60 < p[1] < 130 and p[2] - p[0] > 35


@dataclass
class Axis:
    """Linear pixel -> value map through two reference points."""

    p0: float
    v0: float
    p1: float
    v1: float

    def value(self, p: float) -> float:
        return self.v0 + (p - self.p0) * (self.v1 - self.v0) / (self.p1 - self.p0)

    def pixel(self, v: float) -> float:
        return self.p0 + (v - self.v0) * (self.p1 - self.p0) / (self.v1 - self.v0)

    @property
    def per_pixel(self) -> float:
        return abs((self.v1 - self.v0) / (self.p1 - self.p0))


@dataclass
class Figure:
    image: int  # pdfimages index
    page: int
    slug: str
    title: str
    x: Axis
    y: Axis
    x_label: str
    y_label: str
    series: dict[str, Callable[[Pixel], bool]]
    xs: list[float] = field(default_factory=list)  # sample points (data units); empty = trace every pixel
    trace_step: float = 0.0  # when tracing, report one point per this many x units
    claims: str = ""
    notes: str = ""
    mask: list[tuple[int, int, int, int]] = field(default_factory=list)  # pixel boxes to ignore (legends)


# Calibration notes: y from two labelled gridlines; x from the tick marks under the plot area.
FIGURES = [
    Figure(0, 4, "p04_density_map", "17030 density map (fuel vs MAP site)",
           Axis(89, 0, 527, 12), Axis(350, 0, 130, 200), "map_site", "efi",
           {"below_3200rpm": navy, "above_3200rpm": magenta}, xs=list(range(1, 12)), claims="R-F03, R-F05",
           notes="Site 1 of the <3200 rpm series is hidden under the >3200 marker (both read about 18-20)."),
    Figure(1, 5, "p05_speed_corr_above_3200", "17030 rpm speed map >3200 rpm",
           Axis(84, 3000, 661.5, 7200), Axis(80, 8, 356, -12), "rpm", "corr_pct",
           {"corr_pct": navy}, xs=list(range(3200, 7201, 400)), claims="R-F07"),
    Figure(2, 5, "p05_speed_corr_below_3200", "17030 rpm speed map <3200 rpm",
           Axis(92, 400, 653, 3200), Axis(106, 10, 372, -20), "rpm", "corr_pct",
           {"corr_pct": navy}, xs=[533.3, 800, 1066.7, 1333.3, 1600, 2000, 2400, 2800, 3200], claims="R-F08"),
    Figure(3, 6, "p06_hard_driving_corr", "17030 hard-driving fuel correction map",
           Axis(86, 1000, 620, 7000), Axis(107, 8, 356, -10), "rpm", "corr_pct",
           {"corr_pct": navy}, trace_step=100, claims="R-F09, R-F10",
           notes="Step function; the step edges are only as sharp as the 100 rpm sampling."),
    Figure(4, 6, "p06_air_temp_corr", "17030 air temperature correction map",
           Axis(86, -20, 638, 80), Axis(95, 10, 327, -15), "tha_degC", "corr_pct",
           {"corr_pct": navy}, xs=[-15, 15, 45, 75], claims="R-F11"),
    Figure(5, 7, "p07_injector_dead_time", "mk1 MR2 injector response (dead-time) correction, 17030 mk1a",
           Axis(87, 5, 530, 18), Axis(277, 0, 74, 1400), "volts", "extra_us",
           {"extra_us": navy}, trace_step=0.5, claims="R-F17", mask=[(330, 95, 470, 175)],
           notes="Legend box masked out; the plotted line runs from about 6.5 V to 16.5 V."),
    Figure(12, 14, "p14_idle_overrun_ignition", "17030 idle/overrun ignition map (raw 8-bit)",
           Axis(69, 400, 358, 2400), Axis(274, 0, 46, 180), "rpm", "raw_advance",
           {"raw_advance": navy}, trace_step=100, claims="R-I07"),
    Figure(14, 17, "p17_mixture_rpm_corr", "rpm correction for the mixture screw (17030 and 17140)",
           Axis(52, 0, 410, 4000), Axis(266, 0, 49, 140), "rpm", "mx2",
           {"mx2": lavender}, trace_step=100, claims="R-M02",
           notes="Gaps where Ross's yellow annotation arrows cover the line. "
                 "Ross's text: 128 at 1000 rpm, 64 at 3600."),
]  # fmt: skip


def extract_images() -> dict[int, Image.Image]:
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdfimages", "-png", str(PDF), f"{td}/img"], check=True)
        return {
            int(p.stem.split("-")[1]): Image.open(p).transpose(Image.Transpose.FLIP_TOP_BOTTOM).convert("RGB")
            for p in sorted(Path(td).glob("img-*.png"))
        }


def column_y(px, x: int, height: int, test: Callable[[Pixel], bool], y0: int, y1: int, mask=()) -> float | None:
    def masked(xx: int, yy: int) -> bool:
        return any(a <= xx <= c and b <= yy <= d for a, b, c, d in mask)

    ys = [
        y
        for dx in (-1, 0, 1)
        for y in range(max(y0, 0), min(y1, height))
        if test(px[x + dx, y]) and not masked(x + dx, y)
    ]
    return statistics.median(ys) if ys else None


def digitise(fig: Figure, im: Image.Image) -> list[dict]:
    px, (w, h) = im.load(), im.size
    y_lo, y_hi = int(min(fig.y.p0, fig.y.p1)) - 60, int(max(fig.y.p0, fig.y.p1)) + 60
    rows = []
    if fig.xs:
        points = [(x, round(fig.x.pixel(x))) for x in fig.xs]
    else:
        x_start, x_end = sorted((fig.x.p0, fig.x.p1))
        points = []
        v = fig.x.value(x_start)
        v = fig.trace_step * round(v / fig.trace_step)
        while fig.x.pixel(v) <= x_end + 40:
            points.append((v, round(fig.x.pixel(v))))
            v += fig.trace_step
    for xv, xp in points:
        if not 1 <= xp < w - 1:
            continue
        row = {fig.x_label: round(xv, 1)}
        for name, test in fig.series.items():
            y = column_y(px, xp, h, test, y_lo, y_hi, fig.mask)
            row[name] = None if y is None else round(fig.y.value(y), 1)
        if any(row[n] is not None for n in fig.series):
            rows.append(row)
    return rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    images = extract_images()
    for i, im in images.items():
        im.save(OUT / f"img{i:02d}.png", optimize=True)
    for fig in FIGURES:
        rows = digitise(fig, images[fig.image])
        path = OUT / f"{fig.slug}.csv"
        with path.open("w", newline="") as f:
            f.write(f"# {fig.title}. Ross PDF p{fig.page}, image img{fig.image:02d}.png. Claims: {fig.claims}.\n")
            f.write(f"# Digitised by analysis/ross/digitise.py; resolution about +/-{fig.y.per_pixel:.2g} "
                    f"{fig.y_label} per pixel. Evidence level [PDF]; not ROM data.\n")  # fmt: skip
            if fig.notes:
                f.write(f"# Note: {fig.notes}\n")
            wr = csv.DictWriter(f, fieldnames=[fig.x_label, *fig.series])
            wr.writeheader()
            wr.writerows(rows)
        print(f"{path.relative_to(ROOT)}: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
