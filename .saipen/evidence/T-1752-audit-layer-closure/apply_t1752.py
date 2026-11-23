"""Apply the T-1752 change set: exact replacements, counts asserted, endings kept.

Run from the repository root:
    python -B .saipen/evidence/T-1752-audit-layer-closure/apply_t1752.py [--check]
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


INTAKE = "tools/saipen_engine/intake.py"
INBOX = "tools/saipen_engine/audit_inbox.py"

edit(
    INTAKE,
    '    """ACTIVE receipts whose last closing gate is met (T-1666).\n'
    "\n"
    "    Full terminal coverage, and every linked Work the BOARD holds is DONE --\n"
    "    with at least one such Work, so a receipt that never produced Work is not\n"
    "    swept up here. A receipt an audit inbox layer is bound to is left to\n"
    "    `saipen audit ingest`, which closes it and settles the layer together: a\n"
    "    close here would let the next BOARD scrub prune the Work row that ingest\n"
    "    still reads. `works` narrows to receipts linking one of them, `receipts`\n"
    "    to the named ones. Read-only; `close_receipt` re-proves every gate.\n"
    '    """\n',
    '    """ACTIVE receipts whose last closing gate is met (T-1666).\n'
    "\n"
    "    Full terminal coverage, and every linked Work the BOARD holds is DONE --\n"
    "    with at least one such Work, so a receipt that never produced Work is not\n"
    "    swept up here. A receipt an audit inbox layer is bound to closes like any\n"
    "    other (T-1752); its layer then reads CLOSED_PENDING_DELETE and the next\n"
    "    `saipen audit ingest` consumes it, even after a CLEAN scrub has pruned the\n"
    "    Work row (`audit_inbox.delete_gate`). An unreadable inbox closes nothing.\n"
    "    `works` narrows to receipts linking one of them, `receipts` to the named\n"
    "    ones. Read-only; `close_receipt` re-proves every gate.\n"
    '    """\n',
)
edit(
    INTAKE,
    "    if inbox.get(\"ok\") is False:\n"
    "        return []\n"
    '    audited = {str(layer.get("receipt_id")) for layer in inbox.get("layers") or []}\n'
    "    wanted_works = set(works) if works is not None else None\n",
    "    if inbox.get(\"ok\") is False:\n"
    "        return []\n"
    "    wanted_works = set(works) if works is not None else None\n",
)
edit(
    INTAKE,
    "        if (wanted is not None and receipt_id not in wanted) or receipt_id in audited:\n"
    "            continue\n",
    "        if wanted is not None and receipt_id not in wanted:\n"
    "            continue\n",
)
edit(
    INTAKE,
    "    ticket = board.get(\"tickets\", {}).get(work)\n"
    "    return bool(ticket and ticket.get(\"section\") == \"## DONE\")\n",
    "    ticket = board.get(\"tickets\", {}).get(work)\n"
    "    return bool(ticket and ticket.get(\"section\") == \"## DONE\")\n"
    "\n"
    "\n"
    "def _work_is_settled(root: Path, work: str | None, *, receipt_closed: bool) -> bool:\n"
    '    """Is the Work a CLOSED receipt answered finished, row or no row? (T-1752)\n'
    "\n"
    "    DONE on the BOARD, or no longer on it at all once its receipt CLOSED:\n"
    "    `close_receipt` proved every linked Work DONE under the writer lock before\n"
    "    it closed, and a CLEAN scrub prunes a row only once its closing event is in\n"
    "    the LOG. Reading DONE from the row alone left a closed audit layer that a\n"
    "    scrub had reached undeletable. A row that is present and not DONE refuses,\n"
    "    and so does a missing row behind a receipt that is not CLOSED.\n"
    '    """\n'
    "    if not work:\n"
    "        return True\n"
    "    try:\n"
    "        from .board import parse_board\n"
    "\n"
    "        raw = _read_owned_file(\n"
    '            root, ".saipen/BOARD.md", kind="source BOARD authority", max_bytes=_BOARD_MAX\n'
    "        )\n"
    '        board = parse_board(raw.decode("utf-8-sig"))\n'
    "    except (OSError, ValueError):\n"
    "        return False\n"
    "    ticket = board.get(\"tickets\", {}).get(work)\n"
    "    if ticket is None:\n"
    "        return receipt_closed\n"
    "    return ticket.get(\"section\") == \"## DONE\"\n",
)
edit(
    INBOX,
    "    linked_work = status_out.get(\"linked_work\") or record.get(\"linked_work\")\n"
    "    if linked_work and not intake._work_is_done(root, linked_work):\n",
    "    linked_work = status_out.get(\"linked_work\") or record.get(\"linked_work\")\n"
    "    # T-1752: a CLOSED receipt already proved its Work DONE; a scrub may have\n"
    "    # pruned the row since. A tombstone proves no such thing, so it still reads\n"
    "    # the row.\n"
    "    if linked_work and not intake._work_is_settled(\n"
    "        root, linked_work, receipt_closed=not _tombstoned\n"
    "    ):\n",
)

# The T-1666 control pinned the defect: it asked that an audit-bound receipt
# be left to an ingest that never closes one.
edit(
    "tools/test_t1666_receipt_close.py",
    "* a receipt whose Work is still open, or that never produced Work, stays\n"
    "  ACTIVE, and one an audit inbox layer is bound to is left to\n"
    "  `saipen audit ingest`, which settles the layer with it;\n",
    "* a receipt whose Work is still open, or that never produced Work, stays\n"
    "  ACTIVE; one an audit inbox layer is bound to closes like any other and the\n"
    "  next `saipen audit ingest` consumes its layer (T-1752);\n",
)
edit(
    "tools/test_t1666_receipt_close.py",
    "    def test_a_receipt_an_audit_layer_is_bound_to_is_left_to_audit_ingest(self):\n"
    "        project = self.make_project()\n"
    "        work = self.finished_work(project)\n"
    "        receipt = self.receipt(project, work)\n"
    "        self.assertEqual(intake.closable_receipts(project), [receipt])\n"
    '        layer = {"layer": 1, "rel": "audit/1.md", "receipt_id": receipt, "state": "ACTIVE"}\n'
    "        with mock.patch.object(\n"
    '            audit_inbox, "classify", return_value={"layers": [layer], "orphans": []}\n'
    "        ):\n"
    "            self.assertEqual(intake.closable_receipts(project), [])\n",
    "    def test_a_receipt_an_audit_layer_is_bound_to_closes_like_any_other(self):\n"
    "        # T-1752: ingest consumes only a layer whose receipt is CLOSED, so the\n"
    "        # receipt that waited for ingest to close it waited forever.\n"
    "        project = self.make_project()\n"
    "        work = self.finished_work(project)\n"
    "        receipt = self.receipt(project, work)\n"
    "        self.assertEqual(intake.closable_receipts(project), [receipt])\n"
    '        layer = {"layer": 1, "rel": "audit/1.md", "receipt_id": receipt, "state": "ACTIVE"}\n'
    "        with mock.patch.object(\n"
    '            audit_inbox, "classify", return_value={"layers": [layer], "orphans": []}\n'
    "        ):\n"
    "            self.assertEqual(intake.closable_receipts(project), [receipt])\n",
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
    target = ROOT / "tools" / "test_t1752_audit_layer_closure.py"
    shutil.copyfile(HERE / "draft" / "test_t1752_audit_layer_closure.py", target)
    print(f"wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
