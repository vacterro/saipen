"""Route a blocked finding to the Work that already owns it (SRC-276 R002).

The measured defect (SRC-276 F-01/F-02): a `cc all` continuation hit
`CONFORMANCE_UNHEALTHY` with `ENGINEERING_REQUIRED, action: null`, and the agent
then ran `saipen start "<the blocked finding>"` -- minting a second receipt and
a second ticket (T-62) for a subject T-57 already tracked. No repair was
produced; the project gained a duplicate record instead.

The engine could already deduplicate an identical request BODY
(`entry.existing_work_for_request`, T-1446 and T-1363). What it could not do was
route a *finding* -- a rule id plus its subject -- to the Work that already owns
that subject. That is this module: a READ-ONLY resolver, so a continuation can
name the existing owner instead of opening a new one.

Resolution order, most authoritative first:

1. **subject work** -- the finding's own subject is a live Work id (`work` rules).
2. **linked source work** -- the subject is a Source that a Work links, through
   the index projection or the archived metadata.
3. **declared receipt work** -- a Work's `source_receipts` field names the
   subject's Source.
4. **rule family** -- an OPEN Work already carries the same `rule_id` in a
   recorded finding reference.

Only a live (non-`## DONE`) Work is an owner. A DONE Work keeps its history and
is NOT reopened: an operator repeating a request after DONE is a new action
(entry.existing_work_for_request / T-1363), and silently reopening closed Work
would rewrite the meaning of its closure. When every candidate is DONE the
answer is `DONE_ONLY` with no owner, so the caller must justify new Work rather
than inherit a closed one.

This module never writes. It answers a routing question; opening or linking Work
stays the caller's explicit, journaled act.
"""

from __future__ import annotations

import re
from pathlib import Path

DONE = "## DONE"

#: How an owner was found, most authoritative first. Reported beside the owner
#: so a caller can say WHY this Work is the owner without re-deriving it.
LINKAGE_SUBJECT = "subject-work"
LINKAGE_SOURCE = "linked-source-work"
LINKAGE_DECLARED = "declared-receipt-work"
LINKAGE_FAMILY = "rule-family-work"

_SRC_RE = re.compile(r"^SRC-\d+$")
_WORK_RE = re.compile(r"^T-\d+$")


def resolve(root: Path | str, finding: dict, tickets: dict) -> dict:
    """The existing live Work that owns `finding`, or an honest refusal.

    Returns ``{"ok", "code", "owner", "linkage", "candidates"}``:

    * ``ROUTED_TO_OWNER`` -- one live Work owns it; use it, do not start.
    * ``DONE_ONLY`` -- the subject was tracked, but only by DONE Work. No owner
      is returned: a closed Work is history, not a queue slot.
    * ``NO_OWNER`` -- nothing on the BOARD owns this subject.
    * ``AMBIGUOUS`` -- more than one live Work claims it. The caller must pick,
      because guessing would reproduce the duplicate-ownership defect.
    """
    root = Path(root)
    subject = str(finding.get("subject_id") or "").strip()
    rule_id = str(finding.get("rule_id") or "").strip()
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(work: str | None, linkage: str) -> None:
        if not work or not _WORK_RE.match(str(work)):
            return
        work = str(work)
        if work in seen or work not in tickets:
            return
        seen.add(work)
        candidates.append((work, linkage))

    if _WORK_RE.match(subject):
        add(subject, LINKAGE_SUBJECT)
    if _SRC_RE.match(subject):
        for work, linkage in _source_owners(root, subject, tickets):
            add(work, linkage)
    for work, linkage in _family_owners(tickets, rule_id, subject):
        add(work, linkage)

    live = [(w, why) for w, why in candidates if tickets[w].get("section") != DONE]
    done = [w for w, _why in candidates if tickets[w].get("section") == DONE]
    base = {
        "subject": subject or None,
        "rule_id": rule_id or None,
        "candidates": [
            {"work": w, "linkage": why} for w, why in sorted(candidates, key=_work_order)
        ],
    }
    if len(live) == 1:
        work, why = live[0]
        return {"ok": True, "code": "ROUTED_TO_OWNER", "owner": work,
                "linkage": why, **base}
    if len(live) > 1:
        return {"ok": False, "code": "AMBIGUOUS", "owner": None, "linkage": None,
                "live": [w for w, _why in sorted(live, key=_work_order)], **base}
    if done:
        return {"ok": True, "code": "DONE_ONLY", "owner": None, "linkage": None,
                "done": sorted(done, key=_work_order), **base}
    return {"ok": True, "code": "NO_OWNER", "owner": None, "linkage": None, **base}


def _work_order(item) -> tuple[int, str]:
    """Numeric ticket order, so T-9 precedes T-10 for a human reader."""
    work = item[0] if isinstance(item, tuple) else item
    digits = re.sub(r"\D", "", str(work))
    return (int(digits) if digits else 0, str(work))


def _source_owners(root: Path, source: str, tickets: dict) -> list[tuple[str, str]]:
    """Work linked to `source` through the intake projection or BOARD fields."""
    found: list[tuple[str, str]] = []
    try:
        from . import intake

        index = intake._read_index(root)
        projection = index.get("tombstones", {}).get(source) or index.get("active", {}).get(source)
        if isinstance(projection, dict):
            linked = projection.get("linked_work")
            if isinstance(linked, str) and linked:
                found.append((linked, LINKAGE_SOURCE))
        for tid, ticket in tickets.items():
            raw = str((ticket.get("fields") or {}).get("source_receipts") or "")
            declared = {part.strip() for part in raw.split(",") if part.strip()}
            if source in declared:
                found.append((tid, LINKAGE_DECLARED))
    except Exception:  # a resolver never blocks a continuation
        return found
    return found


def _family_owners(tickets: dict, rule_id: str, subject: str) -> list[tuple[str, str]]:
    """OPEN Work whose recorded finding reference names this rule and subject.

    The reference grammar is the one the engine already writes into a blocked
    ticket (`rule_id` plus subject appear in the blocker text). Matching is
    lexical on whole tokens so `SRC-003` never matches `SRC-0030`.
    """
    if not rule_id:
        return []
    found: list[tuple[str, str]] = []
    for tid, ticket in sorted(tickets.items()):
        fields = ticket.get("fields") or {}
        blocked = str(fields.get("blocker") or "")
        if not blocked:
            continue
        if rule_id not in blocked:
            continue
        if subject and not _mentions(blocked, subject):
            continue
        found.append((tid, LINKAGE_FAMILY))
    return found


def _mentions(haystack: str, needle: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(needle)}(?![\w-])", haystack) is not None


def route_command(result: dict) -> str | None:
    """The one executable move for a resolution, or None when none exists.

    A routed finding yields the existing Work's claim, never a `saipen start`:
    that is the loop SRC-276 F-01 measured. An unowned or ambiguous subject
    yields None so the caller must state its justification.
    """
    if result.get("code") == "ROUTED_TO_OWNER" and result.get("owner"):
        return f"saipen ticket claim {result['owner']}"
    return None
