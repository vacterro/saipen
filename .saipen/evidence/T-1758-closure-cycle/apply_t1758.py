"""Apply the T-1758 change set: exact replacements, counts asserted, endings kept.

Run from the repository root:
    python -B .saipen/evidence/T-1758-closure-cycle/apply_t1758.py [--check]
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
HERE = Path(__file__).resolve().parent
EDITS: list[tuple[str, str, str]] = []


def edit(path: str, old: str, new: str) -> None:
    EDITS.append((path, old, new))


LOG = "tools/saipen_engine/log.py"

edit(
    LOG,
    "def verification_evidence(ticket_id: str, events: list[dict]) -> tuple[bool, str]:\n",
    "def _closes_the_cycle(ev: dict, ticket_id: str) -> bool:\n"
    '    """Is this the canonical finish of `ticket_id`, the end of its cycle? (T-1758)\n'
    "\n"
    "    A note logged after a ticket finished -- a continuation boundary, a later\n"
    "    diagnosis that names it -- is history about the closure, never evidence\n"
    "    for or against it. Read as part of the cycle, the post-finish checkpoint\n"
    "    E-14046 outranked T-1695's review PASS and turned this repository's own\n"
    "    validation red. A ticket re-verified after a reopen opens a new cycle at\n"
    "    its new VERIFY boundary, which this never reaches past.\n"
    '    """\n'
    "    return (\n"
    '        ev.get("ticket") == ticket_id\n'
    '        and ev.get("taxonomy") == "DEC"\n'
    '        and str(ev.get("op_id") or "").startswith("finish-")\n'
    '        and str(ev.get("text") or "").startswith("ticket finished via SAIOPS")\n'
    "        and not _hand_authored(ev)\n"
    "    )\n"
    "\n"
    "\n"
    "def verification_evidence(ticket_id: str, events: list[dict]) -> tuple[bool, str]:\n",
)
edit(
    LOG,
    "    - no boundary or no evidence after it -> unproven/failed.\n"
    '    """\n'
    "    if not ticket_id:\n"
    '        return False, "no ticket id provided"\n',
    "    - no boundary or no evidence after it -> unproven/failed;\n"
    "    - the cycle ends with the ticket's canonical finish: what was logged\n"
    "      after it is not evidence (`_closes_the_cycle`, T-1758).\n"
    '    """\n'
    "    if not ticket_id:\n"
    '        return False, "no ticket id provided"\n',
)
edit(
    LOG,
    "    if verify_start_idx is None:\n"
    "        return False, NO_VERIFY_BOUNDARY\n"
    "\n"
    "    for i in range(len(events) - 1, verify_start_idx - 1, -1):\n",
    "    if verify_start_idx is None:\n"
    "        return False, NO_VERIFY_BOUNDARY\n"
    "\n"
    "    cycle_end = len(events) - 1\n"
    "    for i in range(verify_start_idx, len(events)):\n"
    "        if _closes_the_cycle(events[i], ticket_id):\n"
    "            cycle_end = i\n"
    "            break\n"
    "    for i in range(cycle_end, verify_start_idx - 1, -1):\n",
)
edit(
    LOG,
    "    wanted = set(ticket_ids)\n"
    "    verdicts: dict[str, tuple[bool, str]] = {}\n"
    "    boundary_seen: set[str] = set()\n"
    "    pending: dict[str, tuple[bool, str]] = {}\n"
    "    for ev in reversed(events):\n"
    '        if ev.get("taxonomy") != "RUN":\n'
    "            continue\n"
    '        tid = ev.get("ticket")\n'
    "        if tid not in wanted or tid in verdicts:\n"
    "            continue\n",
    "    wanted = set(ticket_ids)\n"
    "    verdicts: dict[str, tuple[bool, str]] = {}\n"
    "    boundary_seen: set[str] = set()\n"
    "    pending: dict[str, tuple[bool, str]] = {}\n"
    "    for ev in reversed(events):\n"
    '        tid = ev.get("ticket")\n'
    "        if tid in wanted and tid not in verdicts and tid not in boundary_seen:\n"
    "            if _closes_the_cycle(ev, tid):\n"
    "                # T-1758: everything newer was logged after the ticket\n"
    "                # finished; the cycle is judged from here back.\n"
    "                pending.pop(tid, None)\n"
    "                continue\n"
    '        if ev.get("taxonomy") != "RUN":\n'
    "            continue\n"
    "        if tid not in wanted or tid in verdicts:\n"
    "            continue\n",
)


def main() -> int:
    planned: dict[str, bytes] = {}
    for rel, old, new in EDITS:
        data = planned.get(rel) or (ROOT / rel).read_bytes()
        crlf = b"\r\n" in data
        old_b, new_b = old.encode("utf-8"), new.encode("utf-8")
        if crlf:
            old_b, new_b = old_b.replace(b"\n", b"\r\n"), new_b.replace(b"\n", b"\r\n")
        count = data.count(old_b)
        if count != 1:
            print(f"ABORT: {rel}: expected exactly one match, found {count}:\n{old[:200]}")
            return 1
        planned[rel] = data.replace(old_b, new_b, 1)
    if "--check" in sys.argv:
        print(f"CHECK OK: {len(EDITS)} edits in {len(planned)} files match exactly once")
        return 0
    for rel, data in planned.items():
        (ROOT / rel).write_bytes(data)
        print(f"patched {rel}")
    target = ROOT / "tools" / "test_t1758_closure_cycle.py"
    shutil.copyfile(HERE / "draft" / "test_t1758_closure_cycle.py", target)
    print(f"wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
