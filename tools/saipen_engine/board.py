"""BOARD ticket parsing -- the shared primitive."""

from __future__ import annotations

import datetime
import re

REQUIRED_HEADINGS = ["## DOING", "## TODO", "## DONE", "## BLOCKED"]
TICKET_RE = re.compile(r"^- \[([ x/])\] (T-\d+)\s+(.*)$")
PIPE_SENTINEL = "\x00"
KNOWN_FIELDS = frozenset({"needs", "owner", "claim_time", "blocker", "verify",
                          "review_passes", "verify_attempts",
                          "source_reports", "recurrence", "weak_model"})


def parse_board(text: str) -> dict:
    """Walk the board into a ticket map.

    Returns {"tickets": {tid: {...}}, "headings": [...], "errors": [...]}.
    Mirrors the validator's walk exactly so the engine and validate.py cannot
    drift apart. A ticket line preserves its raw text for surgical mutation.
    """
    tickets = {}
    headings = []
    errors = []
    section = None
    for line_no, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            section = line.strip()
            headings.append(section)
            continue
        if not line.strip():
            continue
        if line.lstrip().startswith("- ["):
            m = TICKET_RE.match(line.strip().replace("\\|", PIPE_SENTINEL))
            if not m:
                errors.append(
                    f"BOARD.md:{line_no} ticket-ish line doesn't match "
                    f"RFC section 1.2 shape `- [ ] T-### description`")
                continue
            checkbox, tid, rest = m.groups()
            if section not in REQUIRED_HEADINGS:
                errors.append(
                    f"BOARD.md:{line_no} ticket {tid} sits under "
                    f"{section or 'no heading'} -- not one of the four RFC "
                    f"sections, so no operation may mutate a board built "
                    f"around it")
                continue
            parts = [unescape_ticket_part(p.strip())
                     for p in rest.split(" | ")]
            needs, fields = [], {}
            for part in parts[1:]:
                fm = re.match(r"^([a-z_]+):\s*(.*)$", part)
                if not fm or fm.group(1) not in KNOWN_FIELDS:
                    errors.append(
                        f"BOARD.md:{line_no} ticket {tid} has unrecognized "
                        f"field {part!r}")
                    continue
                fields[fm.group(1)] = fm.group(2)
                if fm.group(1) == "needs":
                    needs = re.findall(r"T-\d+", fm.group(2))
            if tid in tickets:
                errors.append(f"BOARD.md:{line_no} duplicate ticket ID {tid}")
                continue
            tickets[tid] = {
                "id": tid,
                "section": section,
                "line_no": line_no,
                "checkbox": checkbox,
                "needs": needs,
                "fields": fields,
                "raw": line,
                "description": parts[0] if parts else "",
            }
    for heading in REQUIRED_HEADINGS:
        if headings.count(heading) != 1:
            errors.append(
                f"BOARD.md required heading {heading} appears "
                f"{headings.count(heading)} time(s) -- the shared parser "
                f"refuses a board whose work surface is split or missing, so "
                f"no operation can mutate it into a crash")
    return {"tickets": tickets, "headings": headings, "errors": errors}


def ticket_has_blocker(ticket: dict) -> bool:
    """Whether a blocker field exists, including a malformed empty one."""
    return "blocker" in ticket.get("fields", {})


def ticket_status_error(ticket: dict) -> str | None:
    """Enforce blocker presence iff ticket status is BLOCKED."""
    fields = ticket.get("fields", {})
    blocked = ticket.get("section") == "## BLOCKED"
    if blocked and not str(fields.get("blocker", "")).strip():
        return "sits under ## BLOCKED without a non-empty | blocker: field"
    if not blocked and "blocker" in fields:
        return f"carries | blocker: outside ## BLOCKED ({ticket.get('section')})"
    return None


CLAIM_LIVENESS_WINDOW = datetime.timedelta(minutes=15)


def _claim_is_live(owner: str, claim_time: str, agent: str | None,
                   now: datetime.datetime | None) -> bool:
    """A ticket under ## TODO that still carries a live § 1.4 claim pair.

    Claims live in ## DOING, so a TODO ticket holding owner+claim_time is
    either stale (forfeited after 15 minutes) or someone else's live claim.
    A malformed or zone-less stamp is FAIL-CLOSED: it cannot be proven
    forfeited, so the ticket is excluded whatever the owner -- a bad stamp is
    anomalous either way and a self-owner exemption must not hide it.
    """
    if not owner or not claim_time:
        return False
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    try:
        stamp = datetime.datetime.fromisoformat(
            claim_time.replace("Z", "+00:00"))
    except ValueError:
        return True
    if stamp.tzinfo is None:
        return True
    if agent and owner == agent:
        return False
    return (now - stamp).total_seconds() < CLAIM_LIVENESS_WINDOW.total_seconds()


def ticket_is_workable(ticket: dict, tickets: dict, agent: str | None = None,
                       now: datetime.datetime | None = None) -> bool:
    """Defense-in-depth Pick Rule for possibly malformed BOARD input.

    Workable means: open ## TODO, no blocker (even malformed), every needs:
    DONE, and not under another agent's live § 1.4 claim.
    """
    fields = ticket.get("fields", {})
    return (
        ticket.get("section") == "## TODO"
        and ticket.get("checkbox") in (" ", "")
        and not ticket_has_blocker(ticket)
        and not _claim_is_live(fields.get("owner", ""),
                               fields.get("claim_time", ""), agent, now)
        and all(
            need in tickets and tickets[need].get("section") == "## DONE"
            for need in ticket.get("needs", [])
        )
    )


def escape_ticket_description(description: str) -> str:
    """Reversibly escape payload text so it renders as ONE ticket field.

    Backslash first, pipe second: a literal backslash becomes `\\\\` and a
    literal pipe becomes `\\|`, so a value that itself contains `\\|` cannot
    lose its backslash on the parse round-trip.
    """
    return (description.replace("\\", "\\\\").replace("|", "\\|"))


def unescape_ticket_part(part: str) -> str:
    """Reverse escape_ticket_description for one pipe-delimited part."""
    return (part.replace("\\\\", "\\").replace(PIPE_SENTINEL, "|"))


def _fields_split(raw: str) -> list[str]:
    """Split a ticket line into checkbox/prefix and pipe-delimited fields,
    honouring `\\|` escapes."""
    return raw.replace("\\|", PIPE_SENTINEL).split(" | ")


def _fields_join(parts: list[str]) -> str:
    return " | ".join(parts).replace(PIPE_SENTINEL, "\\|")


def set_ticket_field(raw: str, field: str, value: str) -> str:
    """Replace or append `field: value` on a ticket line, preserving every
    other field byte-for-byte."""
    parts = _fields_split(raw)
    out = []
    replaced = False
    pattern = re.compile(rf"^{re.escape(field)}:\s*")
    for part in parts:
        if part.startswith("- ") or pattern.match(part):
            if pattern.match(part):
                if not replaced:
                    out.append(f"{field}: {value}")
                    replaced = True
                    continue
            out.append(part)
            continue
        out.append(part)
    if not replaced:
        out.append(f"{field}: {value}")
    return _fields_join(out)


def remove_ticket_field(raw: str, field: str) -> str:
    """Remove exactly `| field: <value>` structurally. The leftover value
    cannot survive as free text."""
    parts = _fields_split(raw)
    pattern = re.compile(rf"^{re.escape(field)}:\s*")
    kept = [part for part in parts if not pattern.match(part)]
    return _fields_join(kept)
