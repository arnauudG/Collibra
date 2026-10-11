"""Every relative link in the Markdown files points at a file that exists."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]


def test_relative_markdown_links_resolve():
    broken = []
    for md in FILES:
        for target in re.findall(r"\]\(([^)\s]+)\)", md.read_text()):
            if re.match(r"(https?:|mailto:|#)", target):
                continue
            path = target.split("#")[0]
            if path and not (md.parent / path).exists():
                broken.append(f"{md.relative_to(ROOT)} -> {target}")
    assert len(FILES) >= 9
    assert not broken, "\n".join(broken)
