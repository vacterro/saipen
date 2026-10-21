"""Which closed BOARD records a CLEAN scrub may prune (T-1640).

`phases/clean.md` step 1 told an agent to prune old `## DONE` entries, and the
validator repeated it on every run as `board-soft-cap`. No agent could: the
BOARD is a protected canonical file and no engine verb pruned a record. The
last scrub that did happen (18.09.26, by hand, before the guard) restored five
validator FAILs on the way, because its retention rule looked one hop off the
live sections and a kept row went on naming a pruned one.

This module is the retention rule, stated once and read by both the operation
that prunes (`operations.scrub_board`) and the validator finding that asks for
it. A closed record is KEPT while any of these holds:

  reference  a record that stays names it in `needs:`, `blocked_on:`,
             `superseded_by:` or `implementation_source:` -- every edge a
             validator resolves on the BOARD, followed transitively, because a
             kept record's own references must keep resolving;
  receipt    an ACTIVE source receipt names it (primary or member Work, or a
             coverage clause bound to it), or its own `source_receipts:` names
             an ACTIVE receipt: the row is that Work's existence record and
             the receipt's later verbs look it up. An unconsumed captured audit
             binding also holds its Work row after Source closure, because
             journaled consumption still checks that the Work is DONE;
  unproven   the complete LOG history holds no closing event for it, so the
             BOARD row is the only record that it closed at all.

Everything else in `## DONE` is closed-ticket text nothing reads from the
BOARD any more. It is moved, never dropped: the operation writes the pruned
rows verbatim under `SCRUB_EVIDENCE_ROOT` in the plan that removes them.

The cap this replaces measured the whole file against ~16 KB. No route could
ever meet that on a project whose open work alone is larger -- this
repository's live rows were 55 KB when it was measured -- so the number is
restated against what a scrub can actually clear: the prunable text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Where a scrub keeps the rows it pruned, one directory per operation.
SCRUB_EVIDENCE_ROOT = ".saipen/recovery/board-scrub"

#: Prunable closed-ticket text past this is due for a scrub, and under it is
#: left alone: recent closed rows are cheap context on a small board.
SCRUB_DUE_BYTES = 16 * 1024

#: Operations that move a record to `## DONE`. An event of one of these
#: classes bearing the ticket's id is the permanent LOG evidence
#: `phases/clean.md` requires before the row may leave the BOARD.
CLOSING_OP_CLASSES = (
    "finish-",
    "supersede-",
    "resolve-external-",
    "crew-defer-",
    "clear-wait-role-",
)

_TICKET_RE = re.compile(r"\bT-\d+\b")
_RECEIPT_RE = re.compile(r"\bSRC-\d+\b")
#: Scalar fields of a kept record whose ids a validator resolves on the BOARD.
_REFERENCE_FIELDS = ("blocked_on", "superseded_by", "implementation_source")


@dataclass(frozen=True)
class Selection:
    """What one scrub of one BOARD would prune and what it would keep."""

    #: Closed records to prune, in BOARD order.
    pruned: tuple[str, ...]
    #: Their size in the BOARD, counting one line terminator per record.
    pruned_bytes: int
    #: Every closed record that stays -> the guard that keeps it.
    kept: dict[str, str]

    @property
    def due(self) -> bool:
        return self.pruned_bytes > SCRUB_DUE_BYTES

    def kept_by(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for guard in self.kept.values():
            counts[guard] = counts.get(guard, 0) + 1
        return dict(sorted(counts.items()))


def closed_in_history(events, ticket_ids) -> set[str]:
    """The ids among `ticket_ids` that a closing operation wrote an event for."""
    wanted = set(ticket_ids)
    proven: set[str] = set()
    for event in events:
        ticket = event.get("ticket")
        if ticket in wanted and str(event.get("op_id") or "").startswith(CLOSING_OP_CLASSES):
            proven.add(ticket)
    return proven


def _receipts_named(ticket: dict) -> set[str]:
    return set(_RECEIPT_RE.findall(str((ticket.get("fields") or {}).get("source_receipts") or "")))


def _references(ticket: dict, by_receipt: dict[str, set[str]]) -> set[str]:
    """Every record this one names through an edge a validator resolves."""
    fields = ticket.get("fields") or {}
    named = set(ticket.get("needs") or [])
    for key in _REFERENCE_FIELDS:
        value = str(fields.get(key) or "")
        named.update(_TICKET_RE.findall(value))
        if key == "implementation_source":
            # A Source is provenance, not publication: the resolver follows it
            # to the Work it produced, so that Work is named here too.
            for receipt in _RECEIPT_RE.findall(value):
                named.update(by_receipt.get(receipt, ()))
    return named


def select(tickets: dict, events, active_receipts: set[str], receipt_works: set[str]) -> Selection:
    """Apply the retention rule to one parsed BOARD.

    Pure: `tickets` is `parse_board(...)["tickets"]`, `events` the complete
    history, and the two sets are `intake.active_receipt_works`. Nothing is read from
    disk here, so the operation plans on exactly the documents it will bind.
    """
    done = [tid for tid, ticket in tickets.items() if ticket.get("section") == "## DONE"]
    proven = closed_in_history(events, done)
    by_receipt: dict[str, set[str]] = {}
    for tid, ticket in tickets.items():
        for receipt in _receipts_named(ticket):
            by_receipt.setdefault(receipt, set()).add(tid)

    kept: dict[str, str] = {}
    frontier = [tid for tid, ticket in tickets.items() if ticket.get("section") != "## DONE"]
    for tid in done:
        if tid in receipt_works or _receipts_named(tickets[tid]) & active_receipts:
            kept[tid] = "receipt"
        elif tid not in proven:
            kept[tid] = "unproven"
    frontier.extend(kept)
    while frontier:
        for named in _references(tickets[frontier.pop()], by_receipt):
            if named in kept or tickets.get(named, {}).get("section") != "## DONE":
                continue
            kept[named] = "reference"
            frontier.append(named)

    pruned = sorted(
        (tid for tid in done if tid not in kept), key=lambda tid: tickets[tid].get("line_no") or 0
    )
    size = sum(len(str(tickets[tid].get("raw") or "").encode("utf-8")) + 1 for tid in pruned)
    return Selection(tuple(pruned), size, kept)
