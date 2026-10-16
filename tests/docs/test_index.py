"""Every documentation page is listed in docs/index.md."""

from __future__ import annotations

import re

from pcmre.paths import DOCS


def test_every_page_in_index() -> None:
    index = DOCS / "index.md"
    listed = {(DOCS / t.split("#")[0]).resolve() for t in re.findall(r"\]\(([^)]+\.md)[^)]*\)", index.read_text())}
    pages = {p.resolve() for p in DOCS.rglob("*.md") if p != index}
    missing = sorted(str(p.relative_to(DOCS.resolve())) for p in pages - listed)
    assert not missing, f"not in docs/index.md: {missing}"
