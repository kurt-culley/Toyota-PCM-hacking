"""The documentation gives facts, not the history of the work (docs/style.md).

History markers, a missing summary and sentences over the STE length limit fail the test.
Table rows, headings and code are not counted.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pcmre.paths import DOCS, ROOT

PAGES = sorted([*DOCS.rglob("*.md"), ROOT / "README.md"])

# A date is permitted only inside an evidence tag or a capture-file name.
DATE = re.compile(r"20\d\d-\d\d-\d\d")
ALLOWED_DATE = re.compile(r"\[(?:BENCH|EMU|ROM|PDF):[^\]]*\]|[\w./-]*20\d\d-\d\d-\d\d[\w.-]*\.\w+")
HISTORY = [
    re.compile(p, re.I)
    for p in (
        r"\bowner decision\b",
        r"\bthis session\b",
        r"\bprevious session\b",
        r"\bin a session\b",
        r"\bverifier said\b",
        r"\bverifier round\b",
        r"\btonight\b",
        r"\byesterday\b",
    )
]
LIMIT = 25


def strip(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


@pytest.mark.parametrize("md", PAGES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_history(md: Path) -> None:
    text = strip(md.read_text())
    bad = [m.group() for m in DATE.finditer(ALLOWED_DATE.sub("", text))]
    bad += [m.group() for rx in HISTORY for m in rx.finditer(text)]
    assert not bad, f"{md.relative_to(ROOT)}: history markers {sorted(set(bad))}"


@pytest.mark.parametrize("md", PAGES, ids=lambda p: str(p.relative_to(ROOT)))
def test_has_summary(md: Path) -> None:
    head = [line for line in md.read_text().splitlines() if line.startswith("## ")]
    if md.name == "README.md" and md.parent.name == "figures":
        return
    assert head and head[0].strip() == "## Summary", f"{md.relative_to(ROOT)}: first section is not '## Summary'"


@pytest.mark.parametrize("md", PAGES, ids=lambda p: str(p.relative_to(ROOT)))
def test_sentence_length(md: Path) -> None:
    long = []
    for line in strip(md.read_text()).splitlines():
        s = line.strip()
        if not s or s.startswith(("|", "#", "<", "!", "[")):
            continue
        s = re.sub(r"\[[^\]]*\]\([^)]*\)", "link", s)
        s = re.sub(r"\[[A-Z]+:[^\]]*\]", "", s)
        for sentence in re.split(r"(?<=[.!?])\s+", s.lstrip("-*0123456789. ")):
            if len(sentence.split()) > LIMIT:
                long.append(sentence[:80])
    assert not long, f"{md.relative_to(ROOT)}: sentences over {LIMIT} words: {long}"
