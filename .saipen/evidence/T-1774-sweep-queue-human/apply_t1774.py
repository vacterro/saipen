"""Apply the T-1774 change to tools/saipen.py under a given root.

    python -B apply_t1774.py <root> [--check]

The sweep-queue branch keeps its JSON payload and its shared `_emit` call, and
then prints, on the human surface only, the cycle, every queued finding with
its severity, class, expected, actual and evidence, and every precheck error.
Additive only; refuses unless the anchor is found exactly once. Keeps the
file's line endings.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
SUBJECT = ROOT / "tools/saipen.py"

ANCHOR = (
    '                "note": "semantic adjudication (reproduce/classify/dedupe/"\n'
    '                "decide) is Core-owned; commit each decision via "\n'
    '                "saipen improve sweep",\n'
    "            },\n"
    "            as_json,\n"
    "        )\n"
    "        return 0\n"
)
REPLACEMENT = (
    '                "note": "semantic adjudication (reproduce/classify/dedupe/"\n'
    '                "decide) is Core-owned; commit each decision via "\n'
    '                "saipen improve sweep",\n'
    "            },\n"
    "            as_json,\n"
    "        )\n"
    "        if not as_json:\n"
    "            # T-1774 (SRC-248 R008): the human surface of an enumeration shows\n"
    "            # what it enumerated. `_emit` prints an allow-list of scalars and\n"
    "            # this verb's content lives in two lists, so its whole human answer\n"
    "            # was `code: IMPROVE_SWEEP_QUEUE`. The JSON payload is unchanged.\n"
    '            print(f"cycle: {args[1]}")\n'
    '            print(f"queue: {len(queue)} unswept finding(s)")\n'
    "            for item in queue:\n"
    "                print(f\"  {item['finding_ref']} [{item['severity']}] [{item['class']}]\")\n"
    '                for key in ("expected", "actual", "evidence"):\n'
    '                    print(f"    {key}: {item[key]}")\n'
    '            print(f"precheck_errors: {len(precheck)}")\n'
    "            for error in precheck:\n"
    '                print(f"  - {error}")\n'
    "        return 0\n"
)


def main() -> int:
    raw = SUBJECT.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if "T-1774 (SRC-248 R008)" in text:
        print("ALREADY_APPLIED")
        return 0
    if text.count(ANCHOR) != 1:
        print(f"ABORT: anchor found {text.count(ANCHOR)} times")
        return 1
    text = text.replace(ANCHOR, REPLACEMENT)
    if "--check" in sys.argv:
        print("CHECK OK: anchor matches once; nothing written")
        return 0
    SUBJECT.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print(f"patched {SUBJECT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
