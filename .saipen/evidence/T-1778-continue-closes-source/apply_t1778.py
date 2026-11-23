"""Apply the T-1778 change to tools/saipen.py under a given root.

    python -B apply_t1778.py <root> [--check]

continue's finish-at-ship step runs the receipt closure `ticket done` runs
(T-1666) and reports it on its trace step. Every anchor must match exactly
once; line endings are kept.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
SUBJECT = ROOT / "tools/saipen.py"

PAIRS = [
    (
        "            before_event = state.get(\"last_event\")\n"
        "            if kind == continue_loop.APPLY_APPEND:\n",
        "            before_event = state.get(\"last_event\")\n"
        "            closure: dict = {}\n"
        "            if kind == continue_loop.APPLY_APPEND:\n",
    ),
    (
        "                    result = finish_ticket(project_root, ticket, agent)\n"
        "                    operation_name = \"ticket_done\"\n",
        "                    result = finish_ticket(project_root, ticket, agent)\n"
        "                    operation_name = \"ticket_done\"\n"
        "                    if result.ok:\n"
        "                        # T-1778: the receipt closure `ticket done` runs\n"
        "                        # (T-1666), so a Work finished here does not leave\n"
        "                        # its fully covered Source ACTIVE.\n"
        "                        _close_finished_receipts(project_root, closure, works=[ticket])\n",
    ),
    (
        "            if not step_ok:\n"
        "                payload = dict(failure_payload)\n",
        "            if closure.get(\"source_closed\"):\n"
        "                trace[-1][\"source_closed\"] = closure[\"source_closed\"]\n"
        "            if not step_ok:\n"
        "                payload = dict(failure_payload)\n",
    ),
]


def main() -> int:
    raw = SUBJECT.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if "T-1778: the receipt closure" in text:
        print("ALREADY_APPLIED")
        return 0
    for old, _new in PAIRS:
        if text.count(old) != 1:
            print(f"ABORT: anchor found {text.count(old)} times: {old.strip()[:70]!r}")
            return 1
    for old, new in PAIRS:
        text = text.replace(old, new)
    if "--check" in sys.argv:
        print("CHECK OK: every anchor matches once; nothing written")
        return 0
    SUBJECT.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print(f"patched {SUBJECT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
