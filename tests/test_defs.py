"""P2: the Bluetop map definitions are consistent with the ROM code, and the outputs are current."""

from pcmre.defs import ROOT, generate, load, map_bytes
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


def test_xdf_is_current_and_matches_the_yaml():
    import xml.etree.ElementTree as ET

    spec, rom = load("bluetop")
    gen = generate(spec, rom)
    path = ROOT / "analysis/bluetop/bluetop.xdf"
    assert path.read_text() == gen.xdf, "run: PYTHONPATH=analysis uv run python -m pcmre.defs --write"
    tables = ET.fromstring(gen.xdf).findall("XDFTABLE")
    assert len(tables) == len(spec["maps"])
    for m, t in zip(spec["maps"], tables, strict=True):
        z = t.find("XDFAXIS[@id='z']/EMBEDDEDDATA")
        off = int(z.get("mmedaddress"), 16)
        rows, cols = int(z.get("mmedrowcount")), int(z.get("mmedcolcount"))
        assert off == m["addr"] - spec["base"], m["id"]
        assert rows * cols == (m["rows"] * m["cols"] if m["kind"] == "3d" else m["length"]), m["id"]
        assert off + rows * cols <= len(rom), m["id"]
        assert rom[off : off + rows * cols] == map_bytes(spec, rom, m)
        assert len(t.findall("XDFAXIS[@id='x']/LABEL")) == cols


def test_checksum_matches_rom_and_fix_rebalances_an_edit():
    from pcmre.checksum import TARGET, fix_checksum, rom_sum

    _, rom = load("bluetop")
    assert rom_sum(rom) == TARGET  # [ROM:$FE50] stock image is balanced
    edited = bytearray(rom)
    edited[0xFF40 - 0xF000] += 3  # change one ignition cell
    assert rom_sum(edited) != TARGET
    fixed = fix_checksum(bytes(edited))
    assert rom_sum(fixed) == TARGET
    assert sum(a != b for a, b in zip(fixed, edited, strict=True)) <= 2  # only the $FFEE word changed
    assert fixed[0xFF40 - 0xF000] == edited[0xFF40 - 0xF000]
