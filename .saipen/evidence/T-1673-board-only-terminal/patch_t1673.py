"""T-1673: a BOARD row moved into DONE with no LOG event is no longer invisible.

Usage: patch_t1673.py <tree-root>   (asserts every anchor occurs exactly once)
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


patch("tools/saipen_engine/lifecycle_authority.py", [
(
'''Not covered, and named so nobody reads it as covered: a BOARD row flipped to
DONE with no LOG event and no STATE change leaves no trace this module reads.
Closing that needs the journal to record the terminal set it wrote.
"""
''',
'''A hand may also leave the LOG and STATE alone and move a row under `## DONE`
in BOARD.md only (T-1673). Nothing above the floor names it, so the two rules
above cannot see it. Every committed plan that writes BOARD.md therefore leaves
a baseline (`record_terminal`): the BOARD bytes' digest and the `## DONE` set
they held. When the live BOARD no longer matches that digest, a ticket in the
live `## DONE` set and not in the baseline is `terminal-without-operation`
unless a closure operation stands behind it -- which is also what keeps a
writer that commits outside `plan.apply_plan` (a release closure, a recovery
replay) from ever reading as a hand. An edit that moves no ticket into
`## DONE` is not judged. With no baseline (a fresh clone, history older than
this contract) the rule is unavailable, never a finding.
"""
'''),
(
'''CLASS = "UNAUTHORIZED_LIFECYCLE_WRITE"
''',
'''CLASS = "UNAUTHORIZED_LIFECYCLE_WRITE"

#: The terminal baseline of the newest committed BOARD write (T-1673).
#: Machine-local like the journal it summarizes; rewritten under the writer lock.
TERMINAL_BASELINE = ".saipen/recovery/board-terminal.json"
'''),
(
'''def refusal_detail(verdict: dict) -> str:
''',
'''def _board_digest(raw: bytes) -> str:
    import hashlib

    return hashlib.sha256(raw).hexdigest()[:16]


def _done_set(board: dict | None) -> set[str]:
    return {
        tid
        for tid, row in ((board or {}).get("tickets") or {}).items()
        if isinstance(row, dict) and row.get("section") == "## DONE"
    }


def record_terminal(root: Path | str) -> None:
    """Write the terminal baseline for the BOARD.md that is live right now.

    Called by `plan.apply_plan` under the writer lock after a commit that wrote
    BOARD.md. Best effort: a baseline that cannot be written leaves the older
    one, and the rule falls back to the closure operations it already checks.
    """
    import json

    from .board import parse_board

    root = Path(root)
    try:
        raw = (root / ".saipen" / "BOARD.md").read_bytes()
        done = sorted(_done_set(parse_board(raw.decode("utf-8-sig"))))
        target = root / TERMINAL_BASELINE
        target.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(
            {"schema": 1, "board_sha256_16": _board_digest(raw), "done": done},
            sort_keys=True,
        )
        temporary = target.with_name(f".{target.name}.{os.getpid()}")
        temporary.write_text(body + chr(10), encoding="utf-8")
        os.replace(temporary, target)
    except (OSError, ValueError, UnicodeDecodeError):
        return


def _terminal_baseline(root: Path) -> dict | None:
    import json

    try:
        payload = json.loads((root / TERMINAL_BASELINE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("board_sha256_16"), str)
        or not isinstance(payload.get("done"), list)
    ):
        return None
    return payload


def _board_only_moves(root: Path, board: dict | None) -> list[str]:
    """Tickets moved into `## DONE` by a BOARD.md edit no baseline covers."""
    baseline = _terminal_baseline(root)
    if baseline is None or board is None:
        return []
    try:
        raw = (root / ".saipen" / "BOARD.md").read_bytes()
    except OSError:
        return []
    if _board_digest(raw) == baseline["board_sha256_16"]:
        return []
    return sorted(_done_set(board) - {str(item) for item in baseline["done"]})


def refusal_detail(verdict: dict) -> str:
'''),
(
'''    for ticket, ticket_events in sorted(named.items()):
        row = ((board or {}).get("tickets") or {}).get(ticket)
        if not isinstance(row, dict) or row.get("section") != "## DONE":
            continue
        if _closed_by_operation(numbered, ticket, floor):
            continue
        shown = ", ".join(f"E-{number}" for number in sorted(ticket_events)[:4])
''',
'''    for ticket in _board_only_moves(root, board):
        if ticket in named or ticket in quarantined:
            continue
        if _closed_by_operation(numbered, ticket, floor):
            continue
        findings.append(
            {
                "rule": TERMINAL_UNBACKED,
                "ticket": ticket,
                "events": [],
                "floor": floor,
                "origin": "board-only",
                "detail": (
                    f"{ticket} sits under ## DONE after an edit of BOARD.md that no "
                    "LOG event records, and no closure operation stands behind it -- "
                    "the completion was typed, not run"
                ),
            }
        )
    for ticket, ticket_events in sorted(named.items()):
        row = ((board or {}).get("tickets") or {}).get(ticket)
        if not isinstance(row, dict) or row.get("section") != "## DONE":
            continue
        if _closed_by_operation(numbered, ticket, floor):
            continue
        shown = ", ".join(f"E-{number}" for number in sorted(ticket_events)[:4])
'''),
])

patch("tools/saipen_engine/plan.py", [(
'''                receipt_metadata=plan.receipt_metadata,
            )
''',
'''                receipt_metadata=plan.receipt_metadata,
            )
            if commit.get("ok") and any(t.role == "board" for t in plan.targets):
                # T-1673: still under the writer lock, the terminal baseline a
                # later BOARD-only edit is judged by.
                from . import lifecycle_authority

                lifecycle_authority.record_terminal(root)
'''),
])

patch("tools/saipen_engine/reconcile.py", [(
'''    else:
        # T-1679: the typed lines were quarantined; their event named the rows.
        plan["trace"] = (
            "lifecycle authority: rows closed by a quarantined typed head have no "
            "operation behind them"
        )
''',
'''    elif any(f.get("origin") == "board-only" for f in findings):
        # T-1673: BOARD.md alone was edited; no LOG line names the move.
        plan["trace"] = (
            "lifecycle authority: rows moved under ## DONE by an edit of BOARD.md "
            "that no LOG event records have no operation behind them"
        )
    else:
        # T-1679: the typed lines were quarantined; their event named the rows.
        plan["trace"] = (
            "lifecycle authority: rows closed by a quarantined typed head have no "
            "operation behind them"
        )
'''),
])

patch("tools/saipen_engine/runtime_namespace.py", [
(
'''      .saipen/recovery/settled-index/**, .saipen/snapshots/**
''',
'''      .saipen/recovery/settled-index/**, .saipen/recovery/board-terminal.json,
      .saipen/snapshots/**
'''),
(
'''    (".saipen/recovery/settled-index/", "rebuildable-projection"),
''',
'''    (".saipen/recovery/settled-index/", "rebuildable-projection"),
    # T-1673: the terminal baseline of the newest committed BOARD write. Every
    # such commit rewrites it, so a tracked copy is churn; a checkout without
    # it only leaves the BOARD-only rule unavailable until the next operation.
    (".saipen/recovery/board-terminal.json", "terminal-baseline"),
'''),
])

patch("tools/test_t1674_typed_closure_mode.py", [(
'''    board.write_text(text.replace("## DONE''' + chr(92) + '''n", "## DONE''' + chr(92) + '''n" + done + "''' + chr(92) + '''n"),
                     encoding="utf-8", newline="''' + chr(92) + '''n")


def _bytes(root: Path) -> dict:''',
'''    board.write_text(text.replace("## DONE''' + chr(92) + '''n", "## DONE''' + chr(92) + '''n" + done + "''' + chr(92) + '''n"),
                     encoding="utf-8", newline="''' + chr(92) + '''n")
    # The row models AUDAPACK's T-282, typed before any operation left a
    # terminal baseline (T-1673). With one present the lifecycle authority
    # names the same row first as a BOARD-only move -- test_t1673 owns that.
    (root / ".saipen" / "recovery" / "board-terminal.json").unlink(missing_ok=True)


def _bytes(root: Path) -> dict:'''),
])

# Collateral found by core-unit bcc2b5af89963dd2 (E-13387): HostileControlTests
# control 2 hand-types a DONE row and now meets the BOARD-only rule first.
patch("tools/test_ticket_retirement.py", [(
r'''        board_path.write_text(text, encoding="utf-8")

        authority = self.capture(project, authority_text(ticket, None))
''',
r'''        board_path.write_text(text, encoding="utf-8")
        # The row stands for Work an operation closed: leave the terminal
        # baseline that operation would have written (T-1673), or the edit
        # above reads as a typed completion and status refuses first.
        from saipen_engine import lifecycle_authority

        lifecycle_authority.record_terminal(project)

        authority = self.capture(project, authority_text(ticket, None))
'''),
])
