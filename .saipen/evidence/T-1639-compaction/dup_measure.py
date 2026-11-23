"""Measure the protocol markdown: sizes, verbatim duplicates, history in law."""
import re
import sys
from collections import defaultdict
from pathlib import Path

base = Path(sys.argv[1])
files = sorted(base.rglob("*.md"))
total = 0
sizes = {}
for path in files:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    sizes[path.relative_to(base).as_posix()] = len(data)
    total += len(data)
print("total", total, "files", len(files))
for name, size in sorted(sizes.items(), key=lambda kv: -kv[1])[:16]:
    print(f"  {size:7d} {name}")

# Verbatim duplicate lines (long enough to be content, not markup).
seen = defaultdict(list)
for path in files:
    rel = path.relative_to(base).as_posix()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        text = line.strip()
        if len(text) >= 90 and not text.startswith(("|--", "<!--")):
            seen[text].append((rel, number))
dupes = {text: where for text, where in seen.items() if len(where) > 1}
waste = sum(len(text.encode("utf-8")) * (len(where) - 1) for text, where in dupes.items())
print("verbatim duplicate long lines:", len(dupes), "bytes repeated:", waste)
for text, where in sorted(dupes.items(), key=lambda kv: -len(kv[0]) * (len(kv[1]) - 1))[:14]:
    places = ", ".join(f"{rel}:{n}" for rel, n in where[:4])
    print(f"  {len(text.encode('utf-8')):5d} x{len(where)} {places} :: {text[:90]}")

# Incident history inside law: dated or ticket-numbered narration per file.
history = re.compile(r"\b(?:20\d\d-\d\d-\d\d|\d\d\.\d\d\.\d\d)\b|\bT-\d{3,4}\b|\bSRC-\d{2,3}\b|\bE-\d{3,5}\b")
print("history markers (dates, T-, SRC-, E- ids) per file:")
for path in files:
    rel = path.relative_to(base).as_posix()
    text = path.read_text(encoding="utf-8")
    hits = history.findall(text)
    if len(hits) >= 12:
        lines = [l for l in text.splitlines() if history.search(l)]
        print(f"  {len(hits):4d} markers on {len(lines):4d} lines, {sum(len(l.encode('utf-8')) + 1 for l in lines):6d} bytes  {rel}")
