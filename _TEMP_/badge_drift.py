"""Bring the 32 locale kitchen README badges to the canonical VERSION badge.

They sit at **v8.2.0** from the skipped-publish cycle while VERSION (and the
root mirrors) read 8.1.0 -- drift the validator fails on.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine.release_contract import locale_readme_paths  # noqa: E402

VERSION = (ROOT / "VERSION").read_text(encoding="utf-8-sig").strip()
BADGE_NEW = f"**v{VERSION}**"
BADGE_RE = re.compile(r"\*\*v[^*]+\*\*")

changed = 0
for readme in locale_readme_paths(ROOT / ".saipen" / "saitranslate" / "kitchen"):
    if not readme.is_file():
        continue
    text = readme.read_text(encoding="utf-8-sig")
    found = BADGE_RE.findall(text)
    if found == [BADGE_NEW]:
        continue
    if not found:
        print("no badge in", readme.as_posix())
        continue
    new_text = BADGE_RE.sub(BADGE_NEW, text, count=1)
    readme.write_text(new_text, encoding="utf-8-sig", newline="")
    changed += 1
print("rewritten:", changed, "badges ->", BADGE_NEW)