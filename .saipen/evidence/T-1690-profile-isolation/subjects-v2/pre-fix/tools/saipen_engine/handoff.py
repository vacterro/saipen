"""Voluntary mid-work claim handoff: who may move a LIVE claim (T-1487).

A live foreign claim is never taken by a plain `claim` -- that fail-closed rule
stays. What was missing is the deliberate case: the operator switches agents
while Work is in flight, or the owner hands its own Work on. Both collapsed
into "wait for the 15-minute lease to lapse", and a field session had to call
`operations.handover_agent(explicit=True)` through the Python API because no
command reached it (SAI-DEFECT-20260922-silent-actor-inheritance-
misattribution, future_gate/FUTURE GATE -- VOLUNTARY MID-WORK CLAIM HANDOFF).

Authority is exactly one of:

* the CURRENT owner of the claim hands its own Work on (voluntary); or
* an ACTIVE operator receipt carries a closed capsule granting this exact
  ticket to this exact agent:

      This message supplies operator authority for a claim handoff:
      T-108 -> opus
      only.

A new session that merely appeared has neither, and is refused.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import intake
from .supersession import AUTHORITY_SOURCE_KINDS

GRANT_HEADER = "This message supplies operator authority for a claim handoff:"
GRANT_TERMINATOR = "only."

_GRANT_ITEM_RE = re.compile(
    r"^[ \t]*(T-\d+)[ \t]+->[ \t]+([A-Za-z0-9][A-Za-z0-9._:-]{0,63})[ \t]*$"
)
_FENCE_RE = re.compile(r"^[ \t]{0,3}(```|~~~)")


@dataclass(frozen=True)
class HandoffGrants:
    grants: dict[str, str]
    lines: dict[str, str]
    problems: tuple[str, ...]


def handoff_grants(text: str) -> HandoffGrants:
    """Parse only closed, unfenced `T-### -> agent` capsules."""
    lines = text.splitlines()
    grants: dict[str, str] = {}
    grant_lines: dict[str, str] = {}
    conflicted: set[str] = set()
    problems: list[str] = []
    fence: str | None = None
    index = 0
    while index < len(lines):
        line = lines[index]
        fenced = _FENCE_RE.match(line)
        if fence is not None:
            if fenced and fenced.group(1) == fence:
                fence = None
            index += 1
            continue
        if fenced:
            fence = fenced.group(1)
            index += 1
            continue
        if line.rstrip() != GRANT_HEADER:
            index += 1
            continue
        header_line = index + 1
        items: list[tuple[str, str, str]] = []
        cursor = index + 1
        closed = False
        malformed: str | None = None
        while cursor < len(lines):
            candidate = lines[cursor]
            if not candidate.strip():
                cursor += 1
                continue
            if candidate.rstrip() == GRANT_TERMINATOR:
                closed = True
                break
            item = _GRANT_ITEM_RE.fullmatch(candidate)
            if not item:
                malformed = f"line {cursor + 1} is neither T-### -> agent nor the terminator"
                break
            items.append((item.group(1), item.group(2), candidate.strip()))
            cursor += 1
        if malformed is None and not closed:
            malformed = "it is never closed"
        if malformed is None and not items:
            malformed = "it grants no handoff"
        if malformed is not None:
            problems.append(
                f"claim-handoff capsule at line {header_line} is malformed ({malformed}) "
                "and grants nothing"
            )
            index = cursor + 1 if closed else max(cursor, index + 1)
            continue
        for ticket, agent, raw in items:
            if ticket in grants and grants[ticket] != agent:
                conflicted.add(ticket)
            grants.setdefault(ticket, agent)
            grant_lines.setdefault(ticket, raw)
        index = cursor + 1
    for ticket in sorted(conflicted):
        problems.append(f"{ticket} is handed to conflicting agents and so is not granted")
        grants.pop(ticket, None)
        grant_lines.pop(ticket, None)
    return HandoffGrants(grants, grant_lines, tuple(problems))


def grammar_hint() -> str:
    return (
        f"a capsule is a line `{GRANT_HEADER}`, one `T-### -> agent` line per grant, "
        f"then a line `{GRANT_TERMINATOR}`; capture it with `saipen authority capture`"
    )


def authority_error(root: Path, receipt: str, *, ticket: str, agent: str) -> str | None:
    """Why stored operator authority does not hand `ticket` to `agent`, or None."""
    if not intake._valid_receipt_id(receipt):
        return f"authority {receipt!r} is not a receipt id"
    meta = intake._read_meta(root, receipt)
    if not meta:
        return f"authority receipt {receipt} has no active metadata"
    if meta.get("status") != intake.ACTIVE_STATUS:
        return (
            f"authority receipt {receipt} is {meta.get('status')!r}; a handoff needs an "
            "ACTIVE operator decision"
        )
    if meta.get("source_kind") not in AUTHORITY_SOURCE_KINDS:
        return (
            f"authority receipt {receipt} is a {meta.get('source_kind')!r} source; a "
            "handoff needs the operator's own ingress"
        )
    provenance = meta.get("request_provenance") or {}
    if provenance.get("witness") != "operator_carrier":
        return (
            f"authority receipt {receipt} has no operator carrier; "
            "model-supplied text cannot grant a live claim handoff. Reachable "
            "routes: the owner runs the handoff, or `saipen claim` once the "
            "owner's lease lapses"
        )
    integrity = intake.verify_integrity(root, receipt)
    if not integrity["ok"]:
        return f"authority receipt {receipt}: {integrity['code']}"
    body = intake.read_body(root, receipt)
    if not body.get("ok"):
        return f"authority receipt {receipt} body unreadable"
    parsed = handoff_grants(str(body.get("body") or ""))
    if parsed.grants.get(ticket) != agent:
        detail = f"authority receipt {receipt} grants no handoff {ticket} -> {agent}"
        if parsed.problems:
            detail += " (" + "; ".join(parsed.problems[:3]) + ")"
        return detail + " -- " + grammar_hint()
    return None
