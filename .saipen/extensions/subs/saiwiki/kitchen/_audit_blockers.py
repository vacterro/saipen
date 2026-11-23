"""Read-only audit: categorize BLOCKED BOARD rows by blocker class.

Nothing is written. Reads .saipen/BOARD.md and prints a class histogram plus the
rows whose blocker names no external/human class (candidates for an engine-side
unblock). Kept as a file, not a heredoc, because the PATH `git` wrapper
intercepts stdin on this host.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
text = (ROOT / ".saipen" / "BOARD.md").read_text(encoding="utf-8", errors="replace")

sec = None
blocked: list[str] = []
for line in text.splitlines():
    m = re.match(r"^##\s+(DOING|TODO|DONE|BLOCKED)", line)
    if m:
        sec = m.group(1)
        continue
    if sec == "BLOCKED" and re.match(r"^- \[ \] (T-\d+)", line):
        blocked.append(line)

counts: Counter[str] = Counter()
for line in blocked:
    mm = re.search(r"blocker:\s*([A-Z_]+)", line)
    counts[mm.group(1) if mm else "NO_CLASS"] += 1

print("BLOCKED rows:", len(blocked))
for k, v in counts.most_common():
    print(f"{v:4d}  {k}")

print("\n-- rows whose class is NOT an external/human class --")
external = {
    "BLOCKED_EXTERNAL",
    "ACTIVE_DEPENDENCY",
    "SEQUENCED_AFTER",
    "DUPLICATE_CONTINUATION",
}
for line in blocked:
    tid = re.match(r"^- \[ \] (T-\d+)", line).group(1)
    mm = re.search(r"blocker:\s*([A-Z_]+)", line)
    cls = mm.group(1) if mm else "NO_CLASS"
    if cls not in external:
        print(f"  {tid}  {cls}  {line[:180]}")
