"""Apply the T-1761 change set: exact replacements, counts asserted, endings kept.

Run from the repository root (or from the root of a disposable copy):
    python -B <this file> [--check]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path.cwd()
EDITS: list[tuple[str, str, str, int]] = []


def edit(path: str, old: str, new: str, count: int = 1) -> None:
    EDITS.append((path, old, new, count))


AUTHORITY = "tools/saipen_engine/lifecycle_authority.py"
BOARD = "tools/saipen_engine/board.py"
RECONCILE = "tools/saipen_engine/reconcile.py"

edit(
    BOARD,
    "            if tid in tickets:\n"
    '                errors.append(f"BOARD.md:{line_no} duplicate ticket ID {tid}")\n'
    "                continue\n",
    "            if tid in tickets:\n"
    '                errors.append(f"BOARD.md:{line_no} duplicate ticket ID {tid}")\n'
    "                # T-1761: the dropped record has no name of its own, but the\n"
    "                # section it sits under is a fact: a typed `## DONE` record\n"
    "                # behind a live id was invisible to lifecycle authority.\n"
    '                tickets[tid].setdefault("shadowed", []).append(section)\n'
    "                continue\n",
)

edit(
    AUTHORITY,
    "def typed_rows(head_events, board: dict | None, events, floor: int) -> list[str]:\n",
    "def _under_done(board: dict | None, ticket: str) -> bool:\n"
    '    """Does any record of this id sit under `## DONE`?\n'
    "\n"
    "    The row the parser kept, or a record it dropped for the duplicated key\n"
    "    (T-1761): a hand that types a second record of a live id under `## DONE`\n"
    "    does not hide that closure behind the first.\n"
    '    """\n'
    '    row = ((board or {}).get("tickets") or {}).get(ticket)\n'
    "    if not isinstance(row, dict):\n"
    "        return False\n"
    '    return row.get("section") == "## DONE" or "## DONE" in (row.get("shadowed") or ())\n'
    "\n"
    "\n"
    "def typed_rows(head_events, board: dict | None, events, floor: int) -> list[str]:\n",
)

edit(
    AUTHORITY,
    '        row = ((board or {}).get("tickets") or {}).get(ticket)\n'
    '        if not isinstance(row, dict) or row.get("section") != "## DONE":\n'
    "            continue\n",
    "        if not _under_done(board, ticket):\n"
    "            continue\n",
    3,
)

edit(
    AUTHORITY,
    "    return {\n"
    "        tid\n"
    '        for tid, row in ((board or {}).get("tickets") or {}).items()\n'
    '        if isinstance(row, dict) and row.get("section") == "## DONE"\n'
    "    }\n",
    '    return {tid for tid in ((board or {}).get("tickets") or {}) if _under_done(board, tid)}\n',
)

edit(
    AUTHORITY,
    '_ROWS_RE = re.compile(re.escape(ROWS_PHRASE) + r"((?:T-\\d+)(?:, T-\\d+)*)")\n',
    '_ROWS_RE = re.compile(re.escape(ROWS_PHRASE) + r"((?:T-\\d+)(?:, T-\\d+)*)")\n'
    "\n"
    "#: The duplicate-id decision is the one repair every later repair waits for\n"
    "#: (`reconcile` refuses to aim a BOARD write through a duplicated id), so it\n"
    "#: must run on an unauthorized head too. Its own event would then become the\n"
    "#: floor and bury the typed closures above the old one, so it carries them:\n"
    "#: the rows that head had closed, in the quarantine's grammar, read back by\n"
    "#: `assess` until an operation closes or reopens each one (T-1761).\n"
    'CARRY_OP_CLASS = "duplicate-id-"\n'
    'CARRY_MARKER = "typed head carried"\n',
)

edit(
    AUTHORITY,
    "def assess(root: Path | str, state: dict | None, board: dict | None, events) -> dict:\n",
    "def carried_rows(verdict: dict | None, reassigned: str | None = None) -> list[str]:\n"
    '    """The rows an operation must carry when it commits over this verdict.\n'
    "\n"
    "    Every `## DONE` row the unauthorized head speaks for, and `reassigned`:\n"
    "    the new id of a record renamed while it sat under `## DONE`. No\n"
    "    operation ever closed that id, and the typed lines name the old one, so\n"
    "    without it a typed row would leave the verdict by changing its name.\n"
    "    Empty on any other verdict: an authorized head has nothing to carry.\n"
    '    """\n'
    '    if not isinstance(verdict, dict) or verdict.get("status") != UNAUTHORIZED:\n'
    "        return []\n"
    "    rows = {\n"
    '        finding["ticket"]\n'
    '        for finding in verdict.get("findings") or ()\n'
    '        if finding.get("rule") == TERMINAL_UNBACKED and finding.get("ticket")\n'
    "    }\n"
    "    if reassigned:\n"
    "        rows.add(reassigned)\n"
    '    return sorted(rows, key=lambda name: int(name.split("-")[1]))\n'
    "\n"
    "\n"
    "def carry_note(rows: list[str]) -> str:\n"
    '    """The clause a carrying operation appends to its DEC; `assess` parses it."""\n'
    '    return f"{CARRY_MARKER} past this decision; " + ROWS_PHRASE + ", ".join(rows)\n'
    "\n"
    "\n"
    "def assess(root: Path | str, state: dict | None, board: dict | None, events) -> dict:\n",
)

edit(
    AUTHORITY,
    "    quarantined: dict[str, int] = {}\n"
    "    for event in numbered:\n"
    '        text = str(event.get("text") or "")\n'
    "        if (\n"
    "            _event_number(event) <= floor\n"
    '            and str(event.get("op_id") or "").startswith(QUARANTINE_OP_CLASS)\n'
    "            and TYPED_HEAD_MARKER in text\n"
    "        ):\n",
    "    quarantined: dict[str, int] = {}\n"
    "    carried: set[int] = set()\n"
    "    for event in numbered:\n"
    '        text = str(event.get("text") or "")\n'
    '        op_id = str(event.get("op_id") or "")\n'
    "        carrying = op_id.startswith(CARRY_OP_CLASS) and CARRY_MARKER in text\n"
    "        if carrying:\n"
    "            carried.add(_event_number(event))\n"
    "        if _event_number(event) <= floor and (\n"
    "            carrying or (op_id.startswith(QUARANTINE_OP_CLASS) and TYPED_HEAD_MARKER in text)\n"
    "        ):\n",
)

edit(
    AUTHORITY,
    '                    f"{ticket} sits under ## DONE on the word of a typed head that "\n'
    '                    f"E-{number} quarantined, and no closure operation stands behind "\n'
    '                    "it -- the completion was typed, not run"\n',
    '                    f"{ticket} sits under ## DONE on the word of a typed head that "\n'
    '                    f"E-{number} {\'carried\' if number in carried else \'quarantined\'}, "\n'
    '                    "and no closure operation stands behind it -- the completion "\n'
    '                    "was typed, not run"\n',
)

edit(
    RECONCILE,
    "    try:\n"
    "        docs, state, _board, log_tail = _read(project_root, observe=REPAIR_OBSERVABLE)\n"
    "    except Exception as exc:  # CheckpointError / HomeDeadError / OSError\n",
    "    try:\n"
    "        # T-1761: every later repair waits for this decision, so it reads past\n"
    "        # an unauthorized head -- and carries the rows that head closed, so\n"
    "        # its own event is never the floor that buries them.\n"
    "        from . import lifecycle_authority as _authority\n"
    "\n"
    "        docs, state, _board, log_tail = _read(\n"
    "            project_root, observe=(*REPAIR_OBSERVABLE, _authority.OBSERVABLE)\n"
    "        )\n"
    "    except Exception as exc:  # CheckpointError / HomeDeadError / OSError\n",
)

edit(
    RECONCILE,
    '    op_id = "duplicate-id-" + uuid4_hex()\n'
    '    evidence = f"{DUPLICATE_ID_EVIDENCE_ROOT}/{op_id}/BOARD.md"\n',
    '    op_id = "duplicate-id-" + uuid4_hex()\n'
    '    evidence = f"{DUPLICATE_ID_EVIDENCE_ROOT}/{op_id}/BOARD.md"\n'
    "    carried = _authority.carried_rows(\n"
    '        docs.get("_lifecycle"), new_id if loser["section"] == "## DONE" else None\n'
    "    )\n",
)

edit(
    RECONCILE,
    '            f"{new_id}. Original BOARD bytes preserved at {evidence}"\n'
    "        ),\n",
    '            f"{new_id}. Original BOARD bytes preserved at {evidence}"\n'
    '            + (f". {_authority.carry_note(carried)}" if carried else "")\n'
    "        ),\n",
)


def main() -> int:
    planned: dict[str, bytes] = {}
    for rel, old, new, expected in EDITS:
        data = planned.get(rel) or (ROOT / rel).read_bytes()
        crlf = b"\r\n" in data
        old_b, new_b = old.encode("utf-8"), new.encode("utf-8")
        if crlf:
            old_b, new_b = old_b.replace(b"\n", b"\r\n"), new_b.replace(b"\n", b"\r\n")
        count = data.count(old_b)
        if count != expected:
            print(f"ABORT: {rel}: expected {expected} match(es), found {count}:\n{old[:200]}")
            return 1
        planned[rel] = data.replace(old_b, new_b)
    if "--check" in sys.argv:
        print(f"CHECK OK: {len(EDITS)} edits in {len(planned)} files match as counted")
        return 0
    for rel, data in planned.items():
        (ROOT / rel).write_bytes(data)
        print(f"patched {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
