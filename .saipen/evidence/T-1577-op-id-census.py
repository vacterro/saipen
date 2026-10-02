"""T-1577 SCOUT: what op-id shapes actually exist, active log vs sealed segments.

Read-only census. The ticket asks the validator to name an unregistered class
or a non-32-hex id as hand-authored external mutation, so the first question is
what the canonical writers actually emit and where the non-canonical ones live.
"""
import collections
import pathlib
import re
import sys

PAT = re.compile(r"\[op: ([^\]]+)\]")


def shapes(lines):
    counter = collections.Counter()
    for line in lines:
        match = PAT.search(line)
        if not match:
            continue
        cls, _, hexpart = match.group(1).partition("-")
        counter[(cls, len(hexpart), bool(re.fullmatch(r"[0-9a-f]+", hexpart)))] += 1
    return counter


def read(path):
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
active = shapes(read(root / ".saipen" / "LOG.md"))
sealed = collections.Counter()
for path in sorted((root / ".saipen" / "logs").glob("LOG-*.md")):
    sealed += shapes(read(path))

print("ACTIVE LOG.md total", sum(active.values()), "shapes", len(active))
for key, value in sorted(active.items(), key=lambda kv: -kv[1]):
    print("   ", key, value)
print("SEALED total", sum(sealed.values()), "shapes", len(sealed))
for key, value in sorted(sealed.items(), key=lambda kv: -kv[1]):
    print("   ", key, value)
