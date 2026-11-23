"""T-1666: a source receipt closes when its last gate is met.

Usage: patch_t1666.py <tree-root>   (asserts every anchor occurs exactly once)
"""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])


def patch(rel: str, edits: list[tuple[str, str]]) -> None:
    path = ROOT / rel
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new in edits:
        assert text.count(old) == 1, (rel, text.count(old), old[:80])
        text = text.replace(old, new)
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print("patched", rel, "crlf" if crlf else "lf")


patch("tools/saipen_engine/intake.py", [(
'''def archive_receipt(root: Path | str, receipt_id: str) -> dict:
''',
'''def closable_receipts(
    root: Path | str,
    *,
    works: set[str] | list[str] | None = None,
    receipts: set[str] | list[str] | None = None,
) -> list[str]:
    """ACTIVE receipts whose last closing gate is met (T-1666).

    Full terminal coverage, and every linked Work the BOARD holds is DONE --
    with at least one such Work, so a receipt that never produced Work is not
    swept up here. A receipt an audit inbox layer is bound to is left to
    `saipen audit ingest`, which closes it and settles the layer together: a
    close here would let the next BOARD scrub prune the Work row that ingest
    still reads. `works` narrows to receipts linking one of them, `receipts`
    to the named ones. Read-only; `close_receipt` re-proves every gate.
    """
    from . import audit_inbox
    from .board import parse_board

    root = Path(root)
    try:
        index = _read_index(root)
        raw = _read_owned_file(
            root, ".saipen/BOARD.md", kind="source BOARD authority", max_bytes=_BOARD_MAX
        )
        tickets = parse_board(raw.decode("utf-8-sig")).get("tickets", {})
        inbox = audit_inbox.classify(root)
    except (OSError, ValueError):
        return []
    if inbox.get("ok") is False:
        return []
    audited = {str(layer.get("receipt_id")) for layer in inbox.get("layers") or []}
    wanted_works = set(works) if works is not None else None
    wanted = set(receipts) if receipts is not None else None
    found: list[str] = []
    for receipt_id in sorted(index.get("active", {})):
        if (wanted is not None and receipt_id not in wanted) or receipt_id in audited:
            continue
        meta = _read_meta(root, receipt_id)
        if not meta or meta.get("status", ACTIVE_STATUS) != ACTIVE_STATUS:
            continue
        members = linked_works(meta)
        if wanted_works is not None and not members & wanted_works:
            continue
        held = [tickets[m] for m in members if m in tickets]
        if not held or any(t.get("section") != "## DONE" for t in held):
            continue
        try:
            if not coverage_complete(root, receipt_id):
                continue
        except (OSError, ValueError):
            continue
        found.append(receipt_id)
    return found


def close_finished(
    root: Path | str,
    *,
    works: set[str] | list[str] | None = None,
    receipts: set[str] | list[str] | None = None,
) -> dict:
    """Close every receipt `closable_receipts` names (T-1666).

    Run when a gate can have just been met -- a Work reaching DONE, a clause
    reaching its disposition -- and on entering CLEAN for whatever an older
    engine left open. Each close is `close_receipt`, which re-proves
    integrity, contract, coverage and Work under the writer lock; a refusal
    closes nothing and is reported.
    """
    closed: list[str] = []
    refused: dict[str, str] = {}
    for receipt_id in closable_receipts(root, works=works, receipts=receipts):
        result = close_receipt(root, receipt_id)
        if result.get("ok"):
            closed.append(receipt_id)
        else:
            refused[receipt_id] = str(result.get("code") or "REFUSED")
    return {"ok": not refused, "closed": closed, "refused": refused}


def archive_receipt(root: Path | str, receipt_id: str) -> dict:
'''),
])

patch("tools/saipen.py", [
(
'''def _clean_entry_steps(project_root, answer: dict) -> None:''',
'''def _close_finished_receipts(project_root, answer: dict, **narrow) -> None:
    """Close the source receipts whose last gate this command met (T-1666).

    After the command's own write has committed: a receipt that is complete
    and whose Work is all DONE leaves the hot surface instead of being
    re-proved on every validation. Reported only when it did something.
    """
    from saipen_engine import intake as _intake

    outcome = _intake.close_finished(project_root, **narrow)
    if outcome["closed"] or outcome["refused"]:
        answer["source_closed"] = outcome


def _clean_entry_steps(project_root, answer: dict) -> None:'''),
(
'''    for key, step in (
        ("board_scrub", scrub_board),
        ("log_seal", seal_log),
        ("journal_compaction", compact_journal),
    ):''',
'''    # T-1666: first, so the scrub below can prune the rows a receipt this
    # closes was the last thing to hold.
    _close_finished_receipts(project_root, answer)
    for key, step in (
        ("board_scrub", scrub_board),
        ("log_seal", seal_log),
        ("journal_compaction", compact_journal),
    ):'''),
(
'''            environment=environment,
        )
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
''',
'''            environment=environment,
        )
        if result.get("ok"):
            _close_finished_receipts(project_root, result, receipts=[receipt_id])
        _emit(result, as_json)
        return 0 if result.get("ok") else 1
'''),
(
'''                invalidation_evidence=_opts.get("invalidation_evidence"),
            )
            _emit(result.to_dict(), as_json)
            return 0 if result.ok else 1''',
'''                invalidation_evidence=_opts.get("invalidation_evidence"),
            )
            answer = result.to_dict()
            if result.ok and not dry_run:
                _close_finished_receipts(project_root, answer, works=[rest[0].upper()])
            _emit(answer, as_json)
            return 0 if result.ok else 1'''),
(
'''        result = execute_release(project_root, plan)
        _emit(result, as_json)
        return 0 if result.get("ok") else 1''',
'''        result = execute_release(project_root, plan)
        if result.get("ok") and getattr(plan, "ticket_id", None):
            _close_finished_receipts(project_root, result, works=[plan.ticket_id])
        _emit(result, as_json)
        return 0 if result.get("ok") else 1'''),
])


# The two end-to-end cases read the receipt from the ACTIVE surface after
# `ticket done`; the receipt that Work answered now closes there (T-1666) and
# its contract and coverage move to the archive with it.
patch("tools/test_request_clause_closure.py", [
(
"""        self.assertEqual(payload["code"], "FINISHED", text)

        receipts = receipts_of(root)
        self.assertEqual(len(receipts), 1, receipts)
        summary = intake.coverage_summary(root, receipts[0])
        self.assertEqual(summary["actionable"], 1, summary)
        self.assertEqual(summary["unresolved"], [], summary)
        ledger = json.loads(
            (root / ".saipen" / "intake" / "coverage" / f"{receipts[0]}.json").read_text(
                encoding="utf-8"
            )
        )
        clause = ledger["requirements"][f"{receipts[0]}:R001"]
""",
"""        self.assertEqual(payload["code"], "FINISHED", text)

        # The clause the finish settled was the receipt's last gate: it closed.
        self.assertEqual(receipts_of(root), [])
        receipts = payload["source_closed"]["closed"]
        self.assertEqual(len(receipts), 1, payload)
        ledger = json.loads(
            (root / ".saipen" / "archive" / "source" / f"{receipts[0]}.coverage.json").read_text(
                encoding="utf-8"
            )
        )
        clause = ledger["requirements"][f"{receipts[0]}:R001"]
"""),
(
"""        cli(root, "ticket", "done", "T-1", "--closure-mode", "own_patch", "--json")
        receipt = receipts_of(root)[0]
        contract = json.loads(
            (root / ".saipen" / "intake" / "contracts" / f"{receipt}.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(contract["clauses"][f"{receipt}:R001"]["text"], TASK)
        self.assertTrue(intake.is_request_clause(root, receipt, f"{receipt}:R001"))
""",
"""        receipt = receipts_of(root)[0]
        self.assertTrue(intake.ensure_request_clause(root, receipt).get("ok"))
        self.assertTrue(intake.is_request_clause(root, receipt, f"{receipt}:R001"))
        cli(root, "ticket", "done", "T-1", "--closure-mode", "own_patch", "--json")
        contract = json.loads(
            (root / ".saipen" / "archive" / "source" / f"{receipt}.contract.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(contract["clauses"][f"{receipt}:R001"]["text"], TASK)
"""),
])
