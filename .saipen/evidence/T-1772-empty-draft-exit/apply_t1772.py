"""Apply the T-1772 change to tools/improve.py under a given root.

    python -B apply_t1772.py <root> [--check]

`reconcile_cycle` stops planning or attempting a retire that `retire_seat`
must refuse: when every seat that could still report is an EMPTY_DRAFT, the
cycle holds no audit evidence and reconcile answers a refusal whose canonical
next command is the sanctioned exit, `saipen improve abort <cycle>`. The plan
(`--dry-run`) answers the same verdict. Additive only; refuses unless the
anchor is found exactly once. Keeps line endings.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
SUBJECT = ROOT / "tools/improve.py"

ANCHOR = (
    '    empty = [record for record in records if record["class"] == "EMPTY_DRAFT"]\n'
    '    stale = [record for record in records if record["class"] == "STALE_COMPLETE"]\n'
)
ADD = (
    "    # T-1772 (SRC-248 R006): `retire_seat` may not empty the roster, so when\n"
    "    # every seat that could still report is an EMPTY_DRAFT there is no\n"
    "    # reconcile route, and planning one recommends an impossible transition.\n"
    "    # Such a cycle holds no audit evidence; its sanctioned exit is abort\n"
    "    # (manifest marker only, drafts byte-preserved), so that is the route\n"
    "    # named -- for the plan and the real call alike.\n"
    "    survivors = [\n"
    "        record\n"
    "        for record in records\n"
    '        if record["availability"] != "unavailable" and record["class"] != "EMPTY_DRAFT"\n'
    "    ]\n"
    "    if empty and not survivors:\n"
    "        return {\n"
    '            "ok": False,\n'
    '            "code": "VALIDATION_FAILED",\n'
    "            **base,\n"
    '            "detail": (\n'
    '                "reconcile cannot retire "\n'
    "                + \", \".join(record[\"seat_id\"] for record in empty)\n"
    '                + ": every seat that could still report is an EMPTY_DRAFT, so the "\n'
    '                "cycle holds no audit evidence and retire may not empty its roster; "\n'
    '                "the sanctioned exit is abort (manifest marker only; drafts preserved)"\n'
    "            ),\n"
    '            "canonical_next_command": f"saipen improve abort {cycle_dir.name}",\n'
    "        }\n"
)


def main() -> int:
    raw = SUBJECT.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if "T-1772 (SRC-248 R006)" in text:
        print("ALREADY_APPLIED")
        return 0
    if text.count(ANCHOR) != 1:
        print(f"ABORT: anchor found {text.count(ANCHOR)} times")
        return 1
    text = text.replace(ANCHOR, ANCHOR + ADD)
    if "--check" in sys.argv:
        print("CHECK OK: anchor matches once; nothing written")
        return 0
    SUBJECT.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print(f"patched {SUBJECT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
