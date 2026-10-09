"""P0: cross-reference generator (analysis/pcmre/xref.py) on the Bluetop ROM."""

import re
from collections import defaultdict

import pytest

from pcmre.idalisting import parse
from pcmre.roundtrip import ROOT, TARGETS
from pcmre.xref import analyse, report

BLUETOP = TARGETS["bluetop"]


@pytest.fixture(scope="module")
def rom():
    return BLUETOP["rom"].read_bytes()


@pytest.fixture(scope="module")
def listing(rom):
    return parse(BLUETOP["listing"], rom)


@pytest.fixture(scope="module")
def xr(rom, listing):
    return analyse(rom, listing)


def _addr(listing, name):
    for a, names in listing.labels.items():
        if name in names:
            return a
    for a, n in listing.ram_labels.items():
        if n == name:
            return a
    raise KeyError(name)


def test_committed_report_is_current(rom, listing):
    _, md = report(rom, listing, BLUETOP["title"])
    assert (ROOT / "analysis/bluetop/xref.md").read_text() == md, (
        "analysis/bluetop/xref.md is stale: run `PYTHONPATH=analysis uv run python -m pcmre.xref --write`"
    )


def test_vectors_are_roots(xr):
    assert xr.roots[0xF000] == ["TOF", "IRQ1", "SWI", "NMI", "RES"]
    assert {0xF3DB, 0xF370, 0xF1B1} <= set(xr.roots)


def test_constant_x_indexed_call_and_ram_wrap(xr):
    # ldx #$FFCF / jsr $14,x  ->  $FFE3; there, inc $FF,x wraps to RAM $00CE.
    assert any(c.site == 0xF0BE and c.callee == 0xFFE3 and c.how == "jsr,x" for c in xr.calls)
    assert any(a.addr == 0xCE and a.routine == 0xFFE3 and a.kind == "rw" and a.via_x for a in xr.accesses)


def test_exit_x_flows_back_into_shared_tail(xr):
    # loc_FFE1 (X=$FF98) does bsr loc_FFE3 (counter $97), which returns with X+1, then falls into
    # the same code itself (counter $98).
    rw = {(a.routine, a.addr) for a in xr.accesses if a.kind == "rw"}
    assert (0xFFE3, 0x97) in rw
    assert (0xFFE1, 0x98) in rw


def test_inline_parameter_routine(xr, listing):
    bound = _addr(listing, "boundData")
    assert {e.offset for e in xr.exits[bound]} == {2}
    # The two bytes after "jsr boundData" at $F4C6 are data (IDA disassembled them as code).
    assert 0xF4C9 not in xr.instrs


def test_stack_argument_routine(xr, listing):
    mul = _addr(listing, "mulDbyStack")
    assert {(e.offset, e.extra) for e in xr.exits[mul]} == {(0, 1)}


def test_jump_table_resolved(xr, listing):
    targets = {c.callee for c in xr.calls if c.caller == _addr(listing, "procJmpTable")}
    assert {_addr(listing, f"jmptable{i}") for i in range(1, 5)} <= targets


def test_nearly_all_listed_code_reached(xr, listing):
    code = {it.addr for it in listing.items if it.kind == "code"}
    assert code - set(xr.instrs) == {0xF4C9}


_XREF = re.compile(r"^(\w+):.*?(?:DATA|CODE) XREF: (.*)$")
# IDA puts an arrow byte (\x18 up, \x19 down) between the location and the kind letter.
_REF = re.compile(r"^(?:(\w+):)?(\w+?)(?:([+-])([0-9A-F]+))?[\x18\x19]?([rwopjPJ])$")


def _ida_xrefs(listing):
    """(source address, target address, kind) from IDA's XREF comments in cap.asm."""
    text = BLUETOP["listing"].read_bytes().decode("latin-1").splitlines()
    out = []
    for line in text:
        m = _XREF.match(line.strip())
        if not m:
            continue
        target = _addr(listing, m.group(1))
        for tok in m.group(2).split():
            r = _REF.match(tok)
            if not r:
                continue  # "..." and similar
            prefix, name, sign, off, kind = r.groups()
            if prefix == "ROM" and re.fullmatch(r"[0-9A-F]{4}", name):
                src = int(name, 16)
            else:
                src = _addr(listing, name)
            if off:
                src += int(off, 16) if sign == "+" else -int(off, 16)
            out.append((src, target, kind.lower()))
    return out


def test_ida_xrefs_agree(xr, listing, rom):
    """Every XREF IDA recorded is found by the analyser (IDA lists only the first few per label)."""
    refs = _ida_xrefs(listing)
    assert len(refs) > 500
    kinds = defaultdict(set)
    for a in xr.accesses:
        kinds[(a.site, a.addr)].add(a.kind)
    calls = {(c.site, c.callee) for c in xr.calls}
    flow = xr.jumps | calls
    items = listing.item_at()

    def lands_in(src, target, edges):
        # IDA files a jump into the middle of an instruction (Denso skip trick) under that instruction's label.
        size = items[target].size if target in items else 1
        return any((src, t) in edges for t in range(target, target + size))

    missing = []
    for src, target, kind in refs:
        if src in items and items[src].kind == "word":
            # A pointer table entry (e.g. JumpTable): the stored word is the target.
            ok = (rom[src - listing.org] << 8 | rom[src - listing.org + 1]) == target
        elif kind in "rw":
            ok = any(kind in k for k in kinds[(src, target)])
        elif kind == "o":
            ok = (src, target) in kinds
        elif kind == "p":
            ok = lands_in(src, target, calls)
        else:  # j
            ok = lands_in(src, target, flow)
        if not ok:
            missing.append(f"${src:04X} -> ${target:04X} ({kind})")
    assert not missing, missing
