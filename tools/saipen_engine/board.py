"""BOARD ticket parsing -- the shared primitive."""

from __future__ import annotations

import datetime
import re

REQUIRED_HEADINGS = ["## DOING", "## TODO", "## DONE", "## BLOCKED"]
TICKET_RE = re.compile(r"^- \[([ x/])\] (T-\d+)\s+(.*)$")

# ONE canonical strict-UTC timestamp parser (hostile-regression, P1#5 / wave 3).
# The contract admits EXACTLY ``YYYY-MM-DDTHH:MM:SS[.fraction](Z|+00:00)``:
# a ``T`` separator (never a space), seconds mandatory, and a UTC suffix of
# ``Z`` or ``+00:00`` only. Forbidden spellings -- space separator, ``+0000``,
# ``+00``, or missing seconds -- are refused before any parse, so a 10:00+03:00
# (07:00Z) stamp can never enter chronological ordering (P1#3).
_STRICT_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$"
    r"|^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$")
_UTC_ZERO = datetime.timedelta(0)


def _strict_utc_stamp(text: str) -> datetime.datetime | None:
    """Parse a canonical strict-UTC string into a UTC-aware datetime, or None."""
    if not _STRICT_UTC_RE.match(text):
        return None
    try:
        stamp = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None or stamp.utcoffset() != _UTC_ZERO:
        return None
    return stamp.astimezone(datetime.timezone.utc)


def strict_iso_utc(value: object) -> str:
    """Strict ISO-8601 UTC (Z or +00:00, ``utcoffset() == 0``) -> canonical Z.

    Returns the canonical ``YYYY-MM-DDTHH:MM:SS[.fff]Z`` form, or ``""`` for any
    non-string, noncanonical-spelling, naive, or non-zero-offset stamp."""
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text:
        return ""
    stamp = _strict_utc_stamp(text)
    if stamp is None:
        return ""
    return stamp.replace(tzinfo=None).isoformat() + "Z"


def iso_utc_sort_key(value: object) -> datetime.datetime | None:
    """The actual UTC instant of ``value``, or None when not strict-UTC.

    Use as the sort key for pending-op and terminal-receipt ordering so two
    admissible instants tie by the real clock (op_id is only the equal-instant
    tiebreak) and never by their spelling -- ``00Z`` and ``00.900000Z`` order
    correctly regardless of lexical form (P1#3)."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return _strict_utc_stamp(text)
# A second canonical ticket-record opener anywhere AFTER the first on the same
# physical line. ONE PHYSICAL BOARD RECORD == ONE TICKET IDENTITY (T-1003): a
# merged record silently deletes the second ticket's identity (T-473/T-576 and
# T-407/T-406 both shipped merged once). A description may legitimately hold
# `- [ ]` prose; a `- [ ] T-###`/`- [/] T-###`/`- [x] T-###` marker is NEVER
# prose -- it is a second identity and a parse error.
EMBEDDED_TICKET_RE = re.compile(r"\[[ x/]\]\s+T-\d+")
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
            if EMBEDDED_TICKET_RE.search(rest):
                errors.append(
                    f"BOARD.md:{line_no} ticket {tid} embeds a second "
                    f"ticket-record opener -- ONE PHYSICAL BOARD RECORD == "
                    f"ONE TICKET IDENTITY; split the records onto separate "
                    f"lines or the embedded ticket silently loses its "
                    f"identity")
                continue
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
                if fm.group(1) in fields:
                    errors.append(
                        f"BOARD.md:{line_no} ticket {tid} duplicates the "
                        f"known field {fm.group(1)!r} -- a weak model must "
                        f"never read one value while Python uses another")
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


def board_semantic_errors(ticket: dict) -> list[str]:
    """Mechanically-decidable BOARD lifecycle invariants, ONE shared home.

    fast_check (transactional verifier: does this proposed board survive
    the release gate?) and validate.py (canonical validator) must reject the
    SAME checkbox/section/evidence mismatches -- an unrelated mutation may
    otherwise COMMIT an already-invalid board that the full release gate
    rejects, and the two gates would disagree (T-1003).

    Rules (RFC § 1.2): the section IS the status; the checkbox is how a
    human skims it.
      - [x] belongs only under ## DONE
      - [/] belongs only under ## DOING
      - open [ ] belongs only under ## TODO / ## BLOCKED
      - ## DONE requires non-empty | verify: evidence (a completion claim
        with no evidence attached is indistinguishable from one never tested)
      - ## BLOCKED requires a non-empty | blocker:
      - | blocker: outside ## BLOCKED is stale advisory data
    """
    errors = []
    section = ticket.get("section")
    checkbox = ticket.get("checkbox")
    fields = ticket.get("fields", {})
    tid = ticket.get("id", "?")
    if checkbox == "x" and section != "## DONE":
        errors.append(f"{tid} is checked [x] but sits under {section} -- "
                      "checkbox and section disagree; [x] belongs only "
                      "under ## DONE")
    if checkbox == "/" and section != "## DOING":
        errors.append(f"{tid} is [/] in-progress but sits under {section} -- "
                      "in-progress work belongs only under ## DOING")
    if checkbox in (" ", "") and section in ("## DONE", "## DOING"):
        errors.append(f"{tid} has an open [ ] checkbox under {section} -- "
                      "open boxes belong under ## TODO or ## BLOCKED")
    if section == "## DONE" and not str(fields.get("verify", "")).strip():
        errors.append(f"{tid} sits under ## DONE with no | verify: evidence "
                      "-- ## DONE is a claim that the ticket's own verify "
                      "condition was met")
    status_error = ticket_status_error(ticket)
    if status_error:
        errors.append(f"{tid} {status_error}")
    return errors


def ticket_has_blocker(ticket: dict) -> bool:
    """Whether a blocker field exists, including a malformed empty one."""
    return "blocker" in ticket.get("fields", {})


def board_graph_errors(tickets: dict) -> list[str]:
    """Dangling `needs:` references and `needs:` cycles -- ONE shared primitive
    (hostile-regression, 4th-wave P1#4) used by fast_check, validate.py and the
    router before Pick Rule evaluation. A cyclic all-TODO graph is corrupt work
    state, never merely 'no workable ticket' (which would otherwise route to
    maintenance / `saipen continue`).

    Self-edges (`T-1 needs T-1`) and two-node cycles are both caught.

    Cycle detection is EXPLICIT-STACK iterative three-color DFS (second-wave
    P1): recursive DFS over a valid acyclic chain deeper than Python's
    recursion limit would raise RecursionError, taking fast validation, routing
    and full validation down instead of returning a deterministic result. The
    explicit stack preserves the exact insertion-order traversal and the
    cycle-path diagnostic (`cyclic needs: T-a -> T-b -> T-a`) of the old
    recursion.
    """
    errors: list[str] = []
    ids = set(tickets.keys())
    for tid, ticket in tickets.items():
        for need in ticket.get("needs", []):
            if need not in ids:
                errors.append(
                    f"{tid} needs nonexistent {need} "
                    f"(line {ticket.get('line_no')})")
    # Cycle detection over the needs: dependency DAG (iterative three-color).
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {tid: WHITE for tid in tickets}
    seen_cycles: set[tuple[str, ...]] = set()

    for start in tickets:
        if color[start] != WHITE:
            continue
        # Explicit DFS stack of [node, next-need-index] frames -- mirrors the
        # recursion exactly (push on WHITE descent, pop on node completion)
        # without consuming the Python call stack.
        stack: list[str] = [start]
        color[start] = GRAY
        frames: list[list] = [[start, 0]]
        while frames:
            node, idx = frames[-1]
            needs = tickets[node].get("needs", [])
            descended = False
            while idx < len(needs):
                need = needs[idx]
                frames[-1][1] = idx + 1
                if need not in tickets:
                    idx += 1
                    continue
                if color.get(need) == GRAY:
                    cycle_start = stack.index(need)
                    cycle = tuple(stack[cycle_start:] + [need])
                    if cycle not in seen_cycles:
                        seen_cycles.add(cycle)
                        errors.append("cyclic needs: " + " -> ".join(cycle))
                elif color.get(need) == WHITE:
                    color[need] = GRAY
                    stack.append(need)
                    frames.append([need, 0])
                    descended = True
                    break
                idx += 1
            if descended:
                continue
            stack.pop()
            color[node] = BLACK
            frames.pop()
    return errors


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

# The ONE claim-ownership classifier (hostile-regression, P0): every consumer
# (validator, fast gate, router, workability, claim) decides claim truth through
# this, never a divergent half-check. CORE's both-or-neither rule is enforced
# here: a half pair (owner xor claim_time) or an unparsable/non-UTC stamp is
# INVALID, which fails closed and can never be picked.
CLAIM_STATUS = ("UNCLAIMED", "SELF", "FOREIGN_LIVE", "FOREIGN_STALE", "INVALID")


def claim_status(ticket: dict, agent: str | None = None,
                 now: datetime.datetime | None = None) -> str:
    """Classify a ticket's § 1.4 claim relative to ``agent`` at ``now``.

    Returns one of UNCLAIMED | SELF | FOREIGN_LIVE | FOREIGN_STALE | INVALID.
      - UNCLAIMED: no owner and no claim_time.
      - SELF:       owner == agent (this agent owns it).
      - FOREIGN_LIVE:   another agent owns it and the claim is still within the
                        15-minute liveness window.
      - FOREIGN_STALE:  another agent owns it but the claim has lapsed.
      - INVALID:    half pair (owner xor claim_time), or an unparsable /
                    non-UTC (utcoffset != 0) claim_time -- CORE's both-or-neither
                    rule, fail closed.
    """
    fields = ticket.get("fields", {})
    owner = (fields.get("owner") or "").strip()
    claim_time = (fields.get("claim_time") or "").strip()
    has_owner = bool(owner)
    has_time = bool(claim_time)
    if has_owner != has_time:
        return "INVALID"
    if not has_owner:
        return "UNCLAIMED"
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    stamp = iso_utc_sort_key(claim_time)
    if stamp is None:
        return "INVALID"
    if agent and owner == agent:
        return "SELF"
    expired = (now - stamp).total_seconds() >= CLAIM_LIVENESS_WINDOW.total_seconds()
    return "FOREIGN_STALE" if expired else "FOREIGN_LIVE"


def _claim_is_live(owner: str, claim_time: str, agent: str | None,
                   now: datetime.datetime | None) -> bool:
    """Backward-compatible live-foreign-claim probe (delegates to claim_status).

    True only for a present, well-formed, foreign-owned claim still inside the
    § 1.4 liveness window. A half pair or bad stamp is INVALID and therefore
    never "live" -- fail closed, never picked (P0 both-or-neither rule).
    """
    owner = (owner or "").strip()
    claim_time = (claim_time or "").strip()
    if not owner or not claim_time:
        return False
    if agent and owner == agent:
        return False
    return claim_status({"fields": {"owner": owner, "claim_time": claim_time}},
                        agent, now) == "FOREIGN_LIVE"


def ticket_is_workable(ticket: dict, tickets: dict, agent: str | None = None,
                        now: datetime.datetime | None = None) -> bool:
    """Defense-in-depth Pick Rule for possibly malformed BOARD input.

    Workable means: open ## TODO, no blocker (even malformed), every needs:
    DONE, and not under another agent's live § 1.4 claim. A half pair or
    non-UTC claim_time is INVALID and fails closed -- it can never be picked
    (CORE's both-or-neither rule, P0).
    """
    fields = ticket.get("fields", {})
    # A syntactically VALID claim (owner + claim_time) on a non-DOING ticket is
    # INACTIVE history -- CORE's claim truth lives in DOING, so a stale pair
    # left by a block/unblock cycle must not make a TODO non-workable
    # (hostile-regression, P1#5). A half/bad (INVALID) pair still fails closed,
    # and a live foreign claim on an ACTIVE DOING ticket still blocks.
    _cs = claim_status(ticket, agent, now)
    _claim_blocks = (
        _cs == "INVALID"
        or (ticket.get("section") == "## DOING" and _cs == "FOREIGN_LIVE"))
    return (
        ticket.get("section") == "## TODO"
        and ticket.get("checkbox") in (" ", "")
        and not ticket_has_blocker(ticket)
        and not _claim_blocks
        and all(
            need in tickets and tickets[need].get("section") == "## DONE"
            for need in ticket.get("needs", [])
        )
    )


# The closed blocker-class vocabulary. A ## BLOCKED ticket is closure-exempt
# ONLY when its blocker field opens with one of these EXACT class tokens
# (prose is never a class). HELD/FUTURE_GATE/PERMANENT_WARNING_OWNER/
# WAIT_USER_CONFIRMATION are exempt by design; ACTIVE is a recognized class
# that genuinely blocks closure. Any other blocker text fails closed and
# blocks closure (T-1003 sweep: prose never decides control flow).
_NON_CLOSURE_BLOCKER_TOKENS = frozenset({
    "HELD", "FUTURE_GATE", "PERMANENT_WARNING_OWNER",
    "WAIT_USER_CONFIRMATION", "WAIT_USER_DECISION", "ACTIVE", "WAIT_ROLE",
})
_CLOSURE_EXEMPT_BLOCKER_CLASSES = frozenset({
    "HELD", "FUTURE_GATE", "PERMANENT_WARNING_OWNER",
    "WAIT_USER_CONFIRMATION", "WAIT_USER_DECISION",
})


def blocker_class(blocker: str) -> str | None:
    """The exact class token a blocker field opens with, or None when it does
    not open with one of the closed tokens. Exact-match only -- a substring
    mention inside free prose is not a class. `WAIT_ROLE:<role>` is the
    structured crew-owned blocker: the CREW planner routes to that built-in
    role; it is NOT globally closure-exempt -- ordinary Core treats it as a
    genuine blocker."""
    head = blocker.strip().split(" -- ", 1)[0].strip().upper()
    if head in _NON_CLOSURE_BLOCKER_TOKENS:
        return head
    wait_role = re.match(r"^WAIT_ROLE:([A-Za-z0-9_-]+)$",
                         blocker.strip().split(" -- ", 1)[0].strip())
    return "WAIT_ROLE" if wait_role else None


def wait_role_target(blocker: str) -> str | None:
    """The role name a WAIT_ROLE:<role> blocker names, or None."""
    m = re.match(r"^WAIT_ROLE:([A-Za-z0-9_-]+)",
                 blocker.strip().split(" -- ", 1)[0].strip())
    return m.group(1) if m else None


def convergence_closure_problems(board: dict,
                                 agent: str | None = None,
                                 wait_role_roles: frozenset = frozenset()) \
        -> list[str]:
    """Canonical mechanically-decidable Core work-closure predicate.

    Closure means no active work, no currently workable TODO, and no blocker
    that claims to prevent present closure. A ## BLOCKED ticket is exempt
    ONLY when its blocker field opens with an exact closed-class token from
    the exempt set; the description is inert and arbitrary prose inside the
    blocker details is inert. Explicit held/future/historical blockers remain
    on BOARD without turning fixed point into "empty BOARD".

    WAIT_ROLE:<role> is NEVER exempt by itself (ordinary Core: blocked remains
    blocked). Only the CREW planner may pass `wait_role_roles` = the built-in
    crew registry; a WAIT_ROLE ticket whose role is in that set is work FOR
    the crew, so it does not block the crew's Core-convergence stage -- the
    planner routes to that role instead (T-1003 hostile finding 10).
    """
    errors = list(board.get("errors", []))
    tickets = board.get("tickets", {})
    doing = [ticket["id"] for ticket in tickets.values()
             if ticket.get("section") == "## DOING"]
    if doing:
        errors.append("active DOING: " + ", ".join(doing[:3]))
    workable = [ticket["id"] for ticket in tickets.values()
                if ticket_is_workable(ticket, tickets, agent=agent)]
    if workable:
        errors.append("workable TODO: " + ", ".join(workable[:3]))
    blocking = []
    for ticket in tickets.values():
        if ticket.get("section") != "## BLOCKED":
            continue
        blocker = ticket.get("fields", {}).get("blocker", "")
        cls = blocker_class(blocker)
        if cls is not None and cls in _CLOSURE_EXEMPT_BLOCKER_CLASSES:
            continue
        if cls == "WAIT_ROLE" and wait_role_roles:
            role = wait_role_target(blocker)
            if role in wait_role_roles:
                continue
        blocking.append(ticket["id"])
    if blocking:
        errors.append("closure-blocking ticket(s): " + ", ".join(blocking[:3]))
    return errors


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


def _reject_duplicate_fields(raw: str) -> None:
    """Refuse to MUTATE a ticket line that repeats a field name.

    A board with `| owner: a | owner: b` is already a parse error; a mutator
    must never rewrite only the first occurrence and leave the second -- the
    effective value would silently disagree with the mutation (T-1003).
    """
    seen: set[str] = set()
    for part in _fields_split(raw):
        if part.startswith("- "):
            continue
        fm = re.match(r"^([a-z_]+):\s*", part)
        if not fm:
            continue
        if fm.group(1) in seen:
            raise ValueError(
                f"ticket line repeats field {fm.group(1)!r}; parse the board "
                "before mutating -- refusing to edit a malformed record")
        seen.add(fm.group(1))


def set_ticket_field(raw: str, field: str, value: str) -> str:
    """Replace or append `field: value` on a ticket line, preserving every
    other field byte-for-byte."""
    _reject_duplicate_fields(raw)
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
    _reject_duplicate_fields(raw)
    parts = _fields_split(raw)
    pattern = re.compile(rf"^{re.escape(field)}:\s*")
    kept = [part for part in parts if not pattern.match(part)]
    return _fields_join(kept)
