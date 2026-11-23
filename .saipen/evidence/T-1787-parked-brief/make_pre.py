"""Rebuild the pre-fix tools/saipen.py for T-1787 by reverting its three hunks.

Line endings are preserved byte for byte (the working copy is CRLF).
"""

import sys
from pathlib import Path

root = Path(sys.argv[1])
source = root / "tools" / "saipen.py"
with open(source, encoding="utf-8", newline="") as handle:
    text = handle.read()
nl = "\r\n" if "\r\n" in text else "\n"

start = text.index(nl + nl + "#: T-1787: a routing answer is read by a model")
marker = "    return brief" + nl
end = text.index(marker, start) + len(marker)
text = text[:start] + nl + text[end:]

pairs = [
    (
        '        "parked_work": _parked_brief(route["parked"]),' + nl
        + '        "parked_detail": PARKED_DETAIL if route["parked"] else None,' + nl,
        '        "parked_work": route["parked"] or None,' + nl,
    ),
    (
        '                        "parked_work": _parked_brief(route["parked"]),' + nl,
        '                        "parked_work": route["parked"] or None,' + nl,
    ),
]
for new, old in pairs:
    if text.count(new) != 1:
        raise SystemExit(f"hunk not unique: {new!r}")
    text = text.replace(new, old)

out = root / ".saipen" / "evidence" / "T-1787-parked-brief" / "pre" / "saipen.py"
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w", encoding="utf-8", newline="") as handle:
    handle.write(text)
print(out)
