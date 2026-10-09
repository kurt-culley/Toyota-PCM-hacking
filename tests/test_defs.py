"""P2: the Bluetop map definitions are consistent with the ROM code, and the outputs are current."""

from pcmre.defs import ROOT, generate, load
from pcmre.idalisting import parse
from pcmre.roundtrip import TARGETS
from pcmre.tables import ENTRIES_1D, entries_needed, find_1d_uses
from pcmre.xref import analyse


def test_generated_files_are_current():
    spec, rom = load("bluetop")
    gen = generate(spec, rom)
    base = ROOT / "analysis/bluetop"
    assert (base / "maps.md").read_text() == gen.markdown, (
        "run: PYTHONPATH=analysis uv run python -m pcmre.defs --write"
    )
    for mid, text in gen.csvs.items():
        assert (base / "maps" / f"{mid}.csv").read_text() == text, mid


def test_1d_defs_match_the_code():
    """Every 1D def is a table the ROM actually reads through the stated helper entry."""
    spec, rom = load("bluetop")
    t = TARGETS["bluetop"]
    uses = {(u.base, u.entry) for u in find_1d_uses(analyse(rom, parse(t["listing"], rom)), rom)}
    for m in spec["maps"]:
        if m["kind"] != "1d":
            continue
        assert m["entry"] in ENTRIES_1D, m["id"]
        assert (m["addr"], m["entry"]) in uses, f"{m['id']}: no ROM call reads ${m['addr']:04X} via ${m['entry']:04X}"
        assert m["axis"]["shift"] == ENTRIES_1D[m["entry"]][0], m["id"]
        need = entries_needed(m["entry"])
        if need is not None:
            assert m["length"] == need, m["id"]


def test_every_1d_table_in_the_code_is_defined():
    spec, rom = load("bluetop")
    t = TARGETS["bluetop"]
    defined = {m["addr"] for m in spec["maps"]}
    found = {u.base for u in find_1d_uses(analyse(rom, parse(t["listing"], rom)), rom)}
    missing = sorted(found - defined)
    assert not missing, [f"${a:04X}" for a in missing]


def test_ignition_map_def_matches_lookup_code():
    spec, _ = load("bluetop")
    ign = next(m for m in spec["maps"] if m["id"] == "ign_base")
    assert (ign["addr"], ign["rows"], ign["cols"]) == (0xFF40, 6, 14)  # ldx #$FF40, ldab #$0E, Load rows 0..5
