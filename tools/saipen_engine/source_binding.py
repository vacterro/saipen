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


def citation_map(
    root: Path | str, events: list[dict], done_ids: list[str]
) -> dict[str, str | None]:
    """Every DONE ticket's binding fingerprint from ONE reverse history pass.

    T-2089: the historical rule walked the whole history once per DONE ticket
    (O(DONE x LOG) -- ~144 tickets x ~21k events on _SAIPEN). One newest-first
    walk over the shared snapshot events reproduces it exactly: the first RUN
    line whose citation parses and whose record loads cleanly binds the ticket,
    and a cited record that fails to load makes that ticket UNBOUND and stops
    its scan (return None -- not "keep looking at older lines"). Tickets are
    matched only after they are asked for, so events between a ticket's
    unbound citation and an older good one keep the old skip-to-older order.
    """
    base = Path(root)
    wanted = set(done_ids)
    found: dict[str, str | None] = {}
    for event in reversed(events):
        ticket_id = event.get("ticket")
        if ticket_id not in wanted or event.get("taxonomy") != "RUN":
            continue
        cited = core_unit.parse_evidence(event.get("text", ""))
        if cited is None:
            continue
        try:
            record = json.loads((base / cited["record"]).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            found[ticket_id] = None
            wanted.discard(ticket_id)
            continue
        fingerprint = str(record.get("fingerprint") or "")[:16] or None
        found[ticket_id] = fingerprint
        wanted.discard(ticket_id)
    return {tid: found.get(tid) for tid in done_ids}


def advisory(root: Path | str, *, events: list[dict] | None = None) -> dict:
    """The read-only block, or {} when the project declares no family / no DONE.

    ``events``: the caller's already-parsed complete history (sealed + active)
    from one ``ProjectSnapshot`` pass. Absent -> this advisory reads history
    itself (direct callers keep working); unreadable -> the historical safe
    fallback {}. Passing events never re-reads a byte.
    """
    base = Path(root)
    if not core_unit.declared(base):
        return {}
    done = _done_ids(base)
    if not done:
        return {}
    if events is None:
        try:
            events = read_history_events(base)
        except Exception:
            return {}
    current = core_unit.tree_fingerprint(base)
    bound: list[dict] = []
    unbound: list[str] = []
    recorded_by_ticket = citation_map(base, events, done)
    for ticket_id in done:
        recorded = recorded_by_ticket[ticket_id]
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
