"""Acceptance reconciliation: what was promised, what proves it, what does not.

A `verify:` clause is one prose blob, so completion evidence binds to a TICKET
rather than to a CRITERION. A later reader cannot tell which promise a green
gate actually covered, and a producer sentence saying the work is done reads
the same as a test result. This module gives criteria stable identity and binds
evidence to them, so the honest answer to "is this complete?" can be per
promise instead of per ticket.

Nothing here is stored. Criteria are parsed out of the existing `verify:` field
on the existing BOARD line; evidence is read out of the existing LOG. The
projection rebuilds from those two canonical files on every call and writes
nothing, so it can be wrong but it can never be stale in its own right.

Three rules carry the weight:

* **A producer claim is not evidence.** There is no evidence class for "the
  agent said so". Prose cannot enter this model at all -- an evidence record is
  a structurally anchored event or it does not exist.
* **Absence is not PASS.** A criterion with nothing behind it reports
  UNVERIFIED, which is a different answer from "checked and fine".
* **Disagreement is not resolved here.** Conflicting or stale evidence reports
  CONTESTED. Picking whichever record sounded more confident is exactly the
  failure this exists to expose.
"""

from __future__ import annotations

import re

from .log import structural_marker_events

# A criterion inside the existing verify clause: `AC-01 <observable outcome>`,
# segments separated by `;`. A legacy clause has no such segment and yields no
# criteria, which is why this is additive rather than a grammar change.
CRITERION_RE = re.compile(r"^(AC-\d{2,})\s+(.+)$", re.DOTALL)

# An evidence record is a RUN event whose text BEGINS with this token. Anchoring
# is the whole anti-leak property (see `structural_marker_events`): a checkpoint
# that DISCUSSES evidence must never become evidence, and this file's own prose
# is the first thing that would.
EVIDENCE_MARKER = "AC-EVIDENCE "
EVIDENCE_RE = re.compile(
    r"^(?P<ac>AC-\d{2,})\s+(?P<result>PASS|FAIL|UNKNOWN)\s+(?P<kind>[a-z]+)(?:\s+--\s+(?P<detail>.*))?$",
    re.DOTALL,
)

# Provenance, not truth rank. A test can prove the wrong behaviour and an
# inspection can be decisive; these say HOW a claim was produced so a later
# reader can weigh it, and deliberately carry no score.
EVIDENCE_CLASSES = ("inspection", "static", "behavioral", "manual")

SATISFIED = "SATISFIED"
FAILED = "FAILED"
UNVERIFIED = "UNVERIFIED"
CONTESTED = "CONTESTED"

# The boundary that decides whether evidence still describes what is built.
# Re-entering BUILD means the implementation moved, so anything proven before
# it is about a different tree. Same machine-owned marker the transition writer
# already emits, read the same anchored way.
BUILD_BOUNDARY = "transition to BUILD"


def parse_criteria(verify_text: str) -> dict:
    """`{ac_id: text}` declared in a verify clause, in declaration order.

    A clause with no `AC-NN` segment returns `{}` -- legacy tickets stay
    readable and are simply reported as declaring no criteria, never as an
    error. A duplicate id keeps the FIRST declaration: an id that silently
    changed meaning halfway down a clause is worse than one that is stable.
    """
    criteria: dict[str, str] = {}
    if not verify_text:
        return criteria
    for raw in verify_text.split(";"):
        match = CRITERION_RE.match(raw.strip())
        if not match:
            continue
        ac_id, text = match.group(1), match.group(2).strip()
        criteria.setdefault(ac_id, text)
    return criteria


def parse_evidence_payload(text: str) -> dict | None:
    """One evidence record's fields, or None when the payload is malformed.

    Malformed is reported as absent rather than guessed. A record whose class
    is not in `EVIDENCE_CLASSES` is malformed on purpose: an open vocabulary is
    how a producer invents `verified-by-agent` and re-enters through the door
    this module closed.
    """
    match = EVIDENCE_RE.match((text or "").strip())
    if not match:
        return None
    if match.group("kind") not in EVIDENCE_CLASSES:
        return None
    return {
        "ac": match.group("ac"),
        "result": match.group("result"),
        "kind": match.group("kind"),
        "detail": (match.group("detail") or "").strip(),
    }


def build_boundary(ticket_id: str, events) -> int:
    """Newest event id where this ticket entered BUILD, or 0."""
    own = [ev for ev in events if ev.get("ticket") == ticket_id]
    return max(structural_marker_events(own, BUILD_BOUNDARY, ("RUN",)), default=0)


def collect_evidence(ticket_id: str, events) -> list[dict]:
    """Every structurally valid evidence record for one ticket, oldest first.

    Records carry `stale` rather than being dropped: a projection that hides
    stale evidence cannot report CONTESTED, and silently ignoring the only
    evidence a criterion has is indistinguishable from having none.
    """
    boundary = build_boundary(ticket_id, events)
    records: list[dict] = []
    for ev in events:
        if ev.get("ticket") != ticket_id or ev.get("taxonomy") != "RUN":
            continue
        text = ev.get("text") or ""
        if not text.startswith(EVIDENCE_MARKER):
            continue
        payload = parse_evidence_payload(text[len(EVIDENCE_MARKER) :])
        if payload is None:
            continue
        event_id = ev.get("event")
        payload["event"] = event_id
        payload["stale"] = isinstance(event_id, int) and event_id < boundary
        records.append(payload)
    return records


def classify(records: list[dict]) -> str:
    """One criterion's state from the records that name it."""
    if not records:
        return UNVERIFIED
    current = [r for r in records if not r["stale"]]
    if not current:
        # Only stale evidence: it proved something, about a tree that moved.
        return CONTESTED
    results = {r["result"] for r in current}
    if "PASS" in results and "FAIL" in results:
        return CONTESTED
    if "FAIL" in results:
        return FAILED
    if "PASS" in results:
        return SATISFIED
    return UNVERIFIED


def reconcile(ticket_id: str, verify_text: str, events) -> dict:
    """Read-only acceptance projection for one Work. Writes nothing.

    Returns criteria in declaration order with their state and the records that
    decided it, plus any evidence naming a criterion the ticket never declared
    -- which is its own finding: evidence for `AC-07` on a ticket that promises
    six criteria is either a typo or a promise nobody wrote down.
    """
    criteria = parse_criteria(verify_text)
    records = collect_evidence(ticket_id, events)
    by_ac: dict[str, list[dict]] = {}
    for record in records:
        by_ac.setdefault(record["ac"], []).append(record)

    rows = []
    for ac_id, text in criteria.items():
        own = by_ac.get(ac_id, [])
        rows.append(
            {
                "ac": ac_id,
                "text": text,
                "state": classify(own),
                "evidence": own,
            }
        )

    undeclared = sorted(set(by_ac) - set(criteria))
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1

    return {
        "ticket": ticket_id,
        "criteria": rows,
        "undeclared_evidence": undeclared,
        "build_boundary": build_boundary(ticket_id, events),
        "counts": counts,
        "declared": len(rows),
    }


def render(projection: dict) -> str:
    """Plain text for a human. Absence and proof must not look alike."""
    lines = [f"acceptance {projection['ticket']}"]
    if not projection["criteria"]:
        lines.append("  no acceptance criteria declared in this ticket's verify clause")
        lines.append("  (a legacy ticket is readable; it simply promises nothing by id)")
        return "\n".join(lines)

    for row in projection["criteria"]:
        lines.append("  %-8s %-10s %s" % (row["ac"], row["state"], row["text"][:88]))
        for record in row["evidence"]:
            mark = " (stale)" if record["stale"] else ""
            detail = f" -- {record['detail']}" if record["detail"] else ""
            lines.append(
                "             E-%s %s %s%s%s"
                % (record["event"], record["result"], record["kind"], detail, mark)
            )
    summary = ", ".join(f"{state} {n}" for state, n in sorted(projection["counts"].items()))
    lines.append(f"  {projection['declared']} criteria: {summary}")
    if projection["undeclared_evidence"]:
        lines.append(
            "  evidence names criteria this ticket never declared: "
            + ", ".join(projection["undeclared_evidence"])
        )
    return "\n".join(lines)
