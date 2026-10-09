"""P1: Ross figure data (docs/ross/figures/) is well-formed and self-consistent."""

import csv
from pathlib import Path

import pytest

from pcmre.roundtrip import ROOT

FIG = ROOT / "docs/ross/figures"
PIL = pytest.importorskip("PIL.Image")


def read(name: str) -> list[dict]:
    lines = [ln for ln in (FIG / name).read_text().splitlines() if not ln.startswith("#")]
    return list(csv.DictReader(lines))


def test_all_csvs_parse_with_provenance():
    files = sorted(FIG.glob("*.csv"))
    assert len(files) >= 9
    for f in files:
        head = f.read_text().splitlines()[0]
        assert head.startswith("# ") and "Ross PDF p" in head, f.name
        rows = read(f.name)
        assert rows, f.name


def test_ignition_table_shape():
    rows = read("p12_ignition_table_17030_raw.csv")
    assert [int(r["rpm"]) for r in rows] == list(range(800, 7201, 400))  # 17 rpm sites
    assert all(0 <= int(r[f"map{i}"]) <= 255 for r in rows for i in range(1, 9))


def test_ignition_table_matches_p13_chart():
    """The hand transcription of p12 agrees with Ross's own p13 line chart of the same table."""
    from ross.digitise import Axis, column_y, magenta, navy

    im = PIL.open(Path(FIG / "img10.png")).convert("RGB")
    px = im.load()
    x_axis, y_axis = Axis(108, 0, 698, 8000), Axis(450, 0, 134, 200)
    rows = read("p12_ignition_table_17030_raw.csv")
    for r in rows:
        rpm = int(r["rpm"])
        xp = round(x_axis.pixel(rpm))
        checks = [("map2", magenta, 100, 460)]
        if rpm != 6000:  # MAP 1 and MAP 8 share the navy colour and cross at 6000 rpm
            checks.append(("map1", navy, round(y_axis.pixel(250)), round(y_axis.pixel(185))))
        if int(r["map8"]) < 110:  # MAP 8 in the low band, away from MAP 1
            checks.append(("map8", navy, round(y_axis.pixel(110)), round(y_axis.pixel(5))))
        for col, test, y0, y1 in checks:
            y = column_y(px, xp, im.size[1], test, y0, y1)
            assert y is not None, (rpm, col)
            assert abs(y_axis.value(y) - int(r[col])) <= 1.5, (rpm, col, y_axis.value(y), r[col])


def test_mixture_correction_matches_ross_text():
    rows = {float(r["rpm"]): float(r["mx2"]) for r in read("p17_mixture_rpm_corr.csv")}
    assert abs(rows[1000] - 128) <= 1.5 and abs(rows[3600] - 64) <= 1.5
