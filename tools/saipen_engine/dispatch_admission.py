"""SRC-274:R003 -- a fresh handoff is ADMITTED, QUEUED or REFUSED, never dropped.

F-02 measured the defect on the AUDAPACK session (2026-10-16 01:27 UTC). The
operator's message named a different objective, the executor SAIPEN root and an
end-to-end repair. The session ran `continue`, was handed `PHASE REVIEW T-1745`,
verified and closed T-1745, and then reported the newly requested mechanism as
already present. The new objective was never refused and never admitted -- it
was never SEEN, because `route_next` consults the queued operator Source only
under `if not active`:

    if not active and queued_source:

That single condition is the whole defect. While a ticket holds the seat, a
durable explicit user receipt is invisible to routing, so `continue` cannot
distinguish "the operator gave me nothing new" from "the operator gave me a new
mission and I did not look". Persisted Work then answers in its place, and a
DONE reached for the old ticket reads as an answer to the new request.

WHAT THIS MODULE IS: one read-only projection that makes the ordering decision
explicit and machine-readable. It never routes, never writes and never consumes
a receipt. The router keeps its precedence -- a live transaction is not
preempted mid-phase -- but the answer now carries WHICH fresh objective is
waiting, WHO holds the seat, and WHY the deferral is bounded, so no reader has
to infer that from silence.

The verdict is closed:

    ADMITTED  the receipt owns the START seat now (no live ticket holds it)
    QUEUED    a live ticket holds the seat; the receipt is deferred, not lost,
              and the reason names the holder and the bounded cure
    REFUSED   the receipt cannot be read as a request; never read as idle

An absent verdict means there is no fresh unprojected operator receipt. That is
the only case in which a project may call itself free of new input.

The clause's second half is a NEGATIVE property, so this module states it as a
fact rather than trusting prose: the receipt is unprojected precisely when no
Work membership names it, so `holder` can never be the Work that answers it.
A closure of `holder` therefore closes nothing about `receipt`, and the next
route re-derives that from the ledger instead of from this record.
"""

from __future__ import annotations

from pathlib import Path

SCHEMA = 1
FAMILY = "dispatch-admission"

ADMITTED = "ADMITTED"
QUEUED = "QUEUED"
REFUSED = "REFUSED"
VERDICTS = (ADMITTED, QUEUED, REFUSED)

#: Why a receipt is deferred. Closed vocabulary: a reader switches on these,
#: never on the prose in `detail`.
QUEUED_BEHIND_USER_WORK = "QUEUED_BEHIND_USER_WORK"
QUEUED_BEHIND_LIVE_WORK = "QUEUED_BEHIND_LIVE_WORK"
QUEUED_SEAT_RESERVED = "QUEUED_SEAT_RESERVED"

REFUSED_UNREADABLE = "REFUSED_UNREADABLE"
ADMITTED_FREE_SEAT = "ADMITTED_FREE_SEAT"


def _active_doing(board: dict | None) -> dict | None:
    """The one BOARD.DOING row, or None. Same shape the router reads."""
    tickets = (board or {}).get("tickets") or {}
    for ticket in tickets.values():
        if isinstance(ticket, dict) and ticket.get("section") == "## DOING":
            return ticket
    return None


def decision(
    project_root: Path | str,
    *,
    state: dict | None,
    board: dict | None,
    queued_source: dict | None,
) -> dict | None:
    """The fresh-handoff admission verdict, or None when no receipt is waiting.

    Read-only. `queued_source` is the router's own projection (the OLDEST
    unprojected explicit user receipt); passing it in keeps ONE walk of the
    intake index and guarantees this verdict and the START branch can never
    disagree about which receipt is next.
    """
    if queued_source is None:
        return None

    holder = _active_doing(board)
    holder_id = str((holder or {}).get("id") or "") or None

    base = {
        "schema": SCHEMA,
        "family": FAMILY,
        "receipt": queued_source.get("receipt"),
        "holder": holder_id,
        # The receipt is unprojected, so no Work membership names it: the
        # holder cannot be the Work that answers this request. Stated as a
        # field so a consumer never has to reason it out from absence.
        "holder_is_linked_work": False,
    }

    if queued_source.get("invalid"):
        return {
            **base,
            "verdict": REFUSED,
            "reason": REFUSED_UNREADABLE,
            "detail": str(
                queued_source.get("detail")
                or "the queued operator receipt cannot be read as a request"
            )[:600],
            "action": queued_source.get("action") or "saipen source status",
        }

    consume = f"saipen start --receipt {base['receipt']}"

    if holder is None:
        return {
            **base,
            "verdict": ADMITTED,
            "reason": ADMITTED_FREE_SEAT,
            "detail": (
                "no live ticket holds the seat, so this fresh operator request "
                "owns the next START"
            ),
            "action": consume,
        }

    from .board import is_user_explicit

    explicit = is_user_explicit(holder)
    if explicit:
        reason = QUEUED_BEHIND_USER_WORK
        detail = (
            f"ticket {holder_id} is earlier explicit operator Work already in "
            f"flight and holds the single DOING seat until it closes; receipt "
            f"{base['receipt']} is deferred behind it and outranks ordinary "
            "backlog when the seat frees"
        )
    else:
        reason = QUEUED_BEHIND_LIVE_WORK
        detail = (
            f"ticket {holder_id} is a live transaction in flight; a fresh "
            f"receipt never preempts a phase mid-write, so {base['receipt']} "
            "waits for the seat and is not lost"
        )
    return {
        **base,
        "verdict": QUEUED,
        "reason": reason,
        "detail": detail,
        "action": consume,
        "queued_behind": holder_id,
    }


def problem(view: object) -> str | None:
    """Why this admission record is not trustworthy, or None when it is.

    A record is only a verdict of this family when its schema, family and
    verdict all match the closed vocabulary; a foreign or partial shape must
    never read as "nothing was waiting".
    """
    if view is None:
        return None
    if not isinstance(view, dict):
        return "not a dispatch-admission record"
    if view.get("schema") != SCHEMA or view.get("family") != FAMILY:
        return "not a dispatch-admission record"
    if view.get("verdict") not in VERDICTS:
        return f"unknown dispatch-admission verdict {view.get('verdict')!r}"
    if view.get("verdict") in (ADMITTED, QUEUED) and not view.get("receipt"):
        return "a dispatch-admission record admits or queues no receipt"
    if view.get("verdict") == QUEUED and not view.get("queued_behind"):
        return "a queued receipt names no holder"
    return None


def summary(view: dict | None) -> str:
    """One line a route answer can carry without repeating the projection."""
    if not isinstance(view, dict):
        return "no fresh handoff"
    return (
        f"{view.get('verdict')} {view.get('receipt')} "
        f"({view.get('reason')}, holder={view.get('holder') or 'none'})"
    )
