"""Detach ONE inverted `needs:` edge (T-1939 / SRC-274).

The measured defect: `saipen ticket add --needs` created SRC-274's three
projected children (T-1853/T-1854/T-1855) with `needs: T-1815`, while the
receipt's own coverage assigns the open clauses R003/R004/R005 to exactly
those three and T-1815 is the single row carrying `source_receipts: SRC-274`.
The receipt-owning parent therefore has to close LAST, and cannot: `ticket done`
refuses `SOURCE_UNRESOLVED` while a clause it does not own is still open, and
`claim` of every child refuses `unmet needs: T-1815`. Neither side can move, and
no canonical operation could detach a `needs` edge -- `repair-metadata` is
closed to `source_receipts`, and the handback path removes `needs` only for a
row that also carries `blocked_on`, which these children never had.

The repair is deliberately narrow. It detaches a named edge ONLY when the
inversion is mechanically PROVEN, and every proof input is project truth that
already exists:

  * the ticket that would lose the edge is `## TODO` (never a live or
    closed row, whose ordering is history);
  * the named need is `## BLOCKED` and its blocker head is exactly
    `ACTIVE_DEPENDENCY:<this ticket>`, so the park already points back here;
  * that need carries `source_receipts`, and one of its receipts has an open
    clause whose coverage `work` is THIS ticket.

That last condition is the whole point: the edge is inverted because the
receipt's own ledger says this ticket is the one that must still build the
clause. A genuine prerequisite fails it, because a real prerequisite is not
parked on the ticket that needs it and does not own a clause the ticket is
supposed to implement.

Nothing here trusts prose or an operator-supplied reason. The command takes only
two identities; the proof is read from BOARD and the coverage ledger.
"""

from __future__ import annotations

import re
from pathlib import Path

from .result import Result

#: The closed refusal vocabulary this module answers with. Registered in
#: `saipen/REGISTRY.json` under `error_codes`. Only codes a branch actually
#: returns live here: a registered code nothing can reach is a claim, not a
#: refusal, and a reader would wait for a verdict this module never gives.
NEEDS_EDGE_ABSENT = "NEEDS_EDGE_ABSENT"
NEEDS_DETACH_NOT_INVERTED = "NEEDS_DETACH_NOT_INVERTED"

_TICKET_RE = re.compile(r"\AT-\d+\Z")


def _refuse(code: str, detail: str, ticket: str) -> Result:
    return Result(ok=False, code=code, message=detail, data={"ticket": ticket})


def prove_inversion(
    root: Path | str,
    ticket_id: str,
    need_id: str,
    *,
    tickets: dict | None = None,
) -> dict:
    """Read-only: is `ticket_id needs need_id` a PROVEN inversion?

    Returns a mapping with `inverted` plus the exact facts the decision used.
    Every refusal carries a reason, so a caller can print why nothing moved
    instead of a bare boolean.
    """
    from .board import parse_board

    root = Path(root)
    ticket_id = str(ticket_id or "").strip().upper()
    need_id = str(need_id or "").strip().upper()

    if tickets is None:
        board_path = root / ".saipen" / "BOARD.md"
        try:
            text = board_path.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            return {"inverted": False, "reason": "BOARD is absent", "facts": {}}
        board = parse_board(text)
        if board.get("errors"):
            return {
                "inverted": False,
                "reason": "BOARD is malformed: " + "; ".join(board["errors"][:3]),
                "facts": {},
            }
        tickets = board["tickets"]

    facts: dict = {"ticket": ticket_id, "need": need_id}

    ticket = tickets.get(ticket_id)
    if ticket is None:
        return {"inverted": False, "reason": f"{ticket_id} is not on the board", "facts": facts}
    need = tickets.get(need_id)
    if need is None:
        return {"inverted": False, "reason": f"{need_id} is not on the board", "facts": facts}

    facts["ticket_section"] = ticket.get("section")
    facts["need_section"] = need.get("section")

    if need_id not in (ticket.get("needs") or []):
        return {
            "inverted": False,
            "reason": f"{ticket_id} does not declare needs: {need_id}",
            "facts": facts,
        }
    if str(ticket.get("section")) != "## TODO":
        return {
            "inverted": False,
            "reason": (
                f"{ticket_id} is under {ticket.get('section')}; only an unstarted TODO "
                "row may lose an edge -- a DOING or DONE ordering is history"
            ),
            "facts": facts,
        }
    if str(need.get("section")) != "## BLOCKED":
        return {
            "inverted": False,
            "reason": (
                f"{need_id} is under {need.get('section')}, not BLOCKED; an inversion has "
                "the dependency parked on the ticket it was made to wait for"
            ),
            "facts": facts,
        }

    need_fields = need.get("fields") or {}
    blocker_text = str(need_fields.get("blocker") or "")
    blocker_head = blocker_text.split(" -- ", 1)[0].strip().upper()
    facts["blocker_head"] = blocker_head

    receipts = [
        value.strip()
        for value in str(need_fields.get("source_receipts") or "").split(",")
        if value.strip()
    ]
    facts["need_receipts"] = receipts
    if not receipts:
        return {
            "inverted": False,
            "reason": (
                f"{need_id} carries no source_receipts; without a receipt there is no "
                "ledger that can prove which ticket owns the open clause"
            ),
            "facts": facts,
        }

    from .intake import TERMINAL_DISPOSITIONS, _read_coverage

    def _open_owners(receipt: str) -> dict:
        """Open clause -> the Work its coverage row names ('' when unrecorded)."""
        try:
            rows = (_read_coverage(root, receipt) or {}).get("requirements") or {}
        except (OSError, ValueError):
            return {}
        owners: dict = {}
        for rid, entry in rows.items():
            if not isinstance(entry, dict):
                continue
            if entry.get("disposition") in TERMINAL_DISPOSITIONS:
                continue
            owners[rid] = str(entry.get("work") or "").strip().upper()
        return owners

    ledger = {receipt: _open_owners(receipt) for receipt in receipts}

    # The park names ONE representative owner, not every owner: a receipt-wide
    # park reads `owner: T-1853 (+2 other owners)`. So a head that is not this
    # ticket is still an inversion when the park is scoped to a receipt this
    # need owns AND the named head is itself a co-owner of that receipt. A
    # genuine prerequisite fails that second half, because its blocker names no
    # receipt of ours and its head owns no clause we must build.
    if blocker_head == f"ACTIVE_DEPENDENCY:{ticket_id}":
        facts["park_pin"] = "direct"
    else:
        named = [receipt for receipt in receipts if receipt.upper() in blocker_text.upper()]
        peers = sorted(
            {
                owner
                for receipt in named
                for owner in ledger[receipt].values()
                if owner and owner != ticket_id
            }
        )
        facts["park_named_receipts"] = named
        facts["park_peer_owners"] = peers
        if not named:
            return {
                "inverted": False,
                "reason": (
                    f"{need_id}'s blocker head is {blocker_head!r}, not "
                    f"ACTIVE_DEPENDENCY:{ticket_id}; the park does not point back here "
                    f"and names none of {', '.join(receipts)}"
                ),
                "facts": facts,
            }
        head_ticket = blocker_head.split(":", 1)[-1].strip()
        if head_ticket not in peers:
            return {
                "inverted": False,
                "reason": (
                    f"{need_id}'s park names {', '.join(named)} but its head "
                    f"{blocker_head!r} owns no open clause of that receipt, so the park "
                    f"is not a receipt-wide dependency on a co-owner"
                ),
                "facts": facts,
            }
        facts["park_pin"] = "receipt-scoped"

    owned: list[dict] = []
    for receipt in receipts:
        for rid, owner in ledger[receipt].items():
            if owner == ticket_id:
                owned.append({"receipt": receipt, "clause": rid})

    facts["open_clauses_owned_by_ticket"] = owned
    if not owned:
        return {
            "inverted": False,
            "reason": (
                f"no open clause of {', '.join(receipts)} is assigned to {ticket_id}; "
                f"the edge is a real prerequisite ordering, not an inversion"
            ),
            "facts": facts,
        }

    return {
        "inverted": True,
        "reason": (
            f"{need_id} is parked on {ticket_id} while the receipt it owns assigns "
            f"{len(owned)} open clause(s) to {ticket_id}"
        ),
        "facts": facts,
    }
