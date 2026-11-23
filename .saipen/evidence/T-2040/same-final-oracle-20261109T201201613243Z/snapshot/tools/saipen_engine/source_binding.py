"""Read-only source-drift advisory for historically-closed Work (T-1734).

A DONE Work's VERIFY cycle may cite a core-unit family record; that record's
``fingerprint`` is a content digest of the source tree the family tested. Once
the ticket closes nothing re-reads the binding, so a later change to the tree
drifts silently away from the bytes that were verified -- historical closure
and current product acceptance are not the same claim.

This module is the bounded, read-only observation of that gap. It names the
Work, the recorded fingerprint and the current one, and never mutates history,
never re-runs the family and never rewrites a LOG line. Closure stays intact;
the manual remedy is still ``saipen work reverify``.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import core_unit
from .board import parse_board
from .log import read_history_events

SCHEMA_VERSION = 1
#: Bounded like the other post-closure diagnostics: the newest DONE rows only.
MAX_WORKS = 8

CURRENT = "CURRENT"
DRIFTED = "DRIFTED"
UNBOUND = "UNBOUND"


def _done_ids(root: Path) -> list[str]:
    try:
        board = parse_board((root / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [
        tid
        for tid, ticket in board.get("tickets", {}).items()
        if ticket.get("section") == "## DONE"
    ]


def _citation(root: Path, events: list[dict], ticket_id: str) -> str | None:
    """The fingerprint the ticket's newest core-unit citation verified, or None."""
    for event in reversed(events):
        if event.get("ticket") != ticket_id or event.get("taxonomy") != "RUN":
            continue
        cited = core_unit.parse_evidence(event.get("text", ""))
        if cited is None:
            continue
        try:
            record = json.loads((root / cited["record"]).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return str(record.get("fingerprint") or "")[:16] or None
    return None


def advisory(root: Path | str) -> dict:
    """The read-only block, or {} when the project declares no family / no DONE."""
    base = Path(root)
    if not core_unit.declared(base):
        return {}
    done = _done_ids(base)
    if not done:
        return {}
    try:
        events = read_history_events(base)
    except Exception:
        return {}
    current = core_unit.tree_fingerprint(base)
    bound: list[dict] = []
    unbound: list[str] = []
    for ticket_id in done:
        recorded = _citation(base, events, ticket_id)
        if recorded is None:
            unbound.append(ticket_id)
            continue
        status = CURRENT if recorded == current[:16] or recorded == current else DRIFTED
        bound.append(
            {
                "ticket": ticket_id,
                "binding": status,
                "recorded_fingerprint": recorded,
                "current_fingerprint": current[:16],
                "detail": (
                    "the tree matches the verified bytes"
                    if status == CURRENT
                    else "the tree changed after this Work closed; the verified "
                    "bytes are no longer the live source (run `saipen work reverify`)"
                ),
            }
        )
    drifted = [work["ticket"] for work in bound if work["binding"] == DRIFTED]
    return {
        "schema": SCHEMA_VERSION,
        "advisory": True,
        "current_fingerprint": current[:16],
        "drifted": drifted[:MAX_WORKS],
        "drifted_count": len(drifted),
        "unbound": unbound[:MAX_WORKS],
        "unbound_count": len(unbound),
        "works": bound[-MAX_WORKS:],
    }
