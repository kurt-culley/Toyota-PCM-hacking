"""Every relative link and image in the Markdown files resolves."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pcmre.paths import ROOT

LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
SKIP_DIRS = {".git", ".venv", "node_modules", ".tools", "build"}


def markdown_files() -> list[Path]:
    return sorted(
        p
        for p in ROOT.rglob("*.md")
        if not any(part in SKIP_DIRS or part.startswith("build") for part in p.relative_to(ROOT).parts)
        and "vendor" not in p.relative_to(ROOT).parts
    )


def strip_code(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


@pytest.mark.parametrize("md", markdown_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_resolve(md: Path) -> None:
    bad = []
    for target in LINK.findall(strip_code(md.read_text())):
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue
        path = target.split("#", 1)[0]
        if not path:
            continue
        if not (md.parent / path).exists():
            bad.append(target)
    assert not bad, f"{md.relative_to(ROOT)}: broken links {bad}"
