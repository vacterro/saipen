"""The phase DFA and the `next_action` grammar, in one place.

These were hand-kept constants inside `tools/validate.py`. They are mechanical
facts — which phase may follow which, which phases carry a ticket, what shape a
`next_action` takes — so under NITRO they belong to the engine and the validator
imports them.

That does NOT make this file the source of truth. CORE section 1.6 is, and the
validator's cross-doc drift check still compares these sets against CORE's own
sentences: the constants exist in code because a DFA cannot be executed from
prose, and the drift check exists because a constant cannot be trusted to still
match the prose it came from.
"""

from __future__ import annotations

import re

# CORE section 1.6's transition table.
VALID_TRANSITIONS: dict[str, list[str]] = {
    "INIT": ["PLAN", "BLOCKED"],
    "PLAN": ["SCOUT", "BUILD", "DONE", "BLOCKED"],
    "SCOUT": ["BUILD", "BLOCKED"],
    "BUILD": ["VERIFY", "BLOCKED"],
    "VERIFY": ["REVIEW", "SCOUT", "BUILD", "BLOCKED"],
    "REVIEW": ["SHIP", "BUILD", "SCOUT", "BLOCKED"],
    "SHIP": ["DONE", "BUILD", "BLOCKED"],
    "DONE": ["SCOUT", "PLAN", "HUNT", "BLOCKED"],
    "VALIDATE": ["SCOUT", "PLAN", "DONE", "BLOCKED"],
    "HUNT": ["ADD", "PLAN", "SCOUT", "BLOCKED"],
    "MARKHUNT": ["DONE", "BLOCKED"],
    "ADD": ["BUILD", "PLAN", "SCOUT", "DONE", "BLOCKED"],
    "CLEAN": ["DONE", "BLOCKED"],
    "TRANSLATE": ["DONE", "BLOCKED"],
    "PREPARE": ["DONE", "BLOCKED"],
    "BLOCKED": ["PLAN", "SCOUT", "DONE"],
}

# The COMPLETE canonical phase enum: every source node of the DFA (T-1008).
# The Nitro frontmatter probe and every other phase-whitelist consumer derive
# accepted phases from THIS set -- never a hand-kept local tuple that drifts
# when the DFA grows (MARKHUNT/VALIDATE/HUNT/CLEAN/TRANSLATE/PREPARE were
# once excluded by exactly such a copy).
ALL_PHASES = frozenset(VALID_TRANSITIONS)


# These seven phases are entered by explicit user command from ANY phase
# (CORE section 1.6/1.10) -- the transition table's FROM row doesn't restrict
# them. PLAN joined in v7.92.0: section 2.4's goal-mode Entry mandates a PLAN
# for the new objective from wherever the pivot happens, so `saipen goal` out of
# REVIEW (whose row allows only SHIP/BUILD/SCOUT/BLOCKED) was an invalid state
# produced by following the protocol exactly. Caught on a live pivot.
# NOTE: SHIP is deliberately absent. `saipen ship` is recognized from any phase
# as a COMMAND (CORE section 1.10), but `phase: SHIP` is reachable only from
# REVIEW -- section 1.10 says so in as many words while this set said otherwise
# from v7.83.0 to v7.94.0. A command is not a transition.
ANY_FROM = frozenset({"VALIDATE", "MARKHUNT", "CLEAN", "TRANSLATE", "PREPARE",
                      "PLAN", "HUNT"})

# The five phases whose `next_action` MUST name a ticket.
TICKET_BEARING_PHASES = frozenset({"SCOUT", "BUILD", "VERIFY", "REVIEW",
                                   "SHIP"})

PHASE_NA_RE = re.compile(
    r"^PHASE\s+([A-Za-z_-]+)(?:\s+(T-\d+))?(?:\s+\[[^\]]*\])?\s*$")


def phase_next_action_error(value: str) -> str | None:
    """CORE section 1.2's `PHASE` pairing rule, or None when the value obeys it.

    Shared by Core and subSaipen states on purpose: the protocol has twice
    shipped a rule enforced on only one of the two, in both directions.
    """
    m = PHASE_NA_RE.match(value.strip())
    if not m:
        return (f"{value!r} is not a legal `PHASE <phase-enum> [T-###]` -- "
                f"the argument is one uppercase phase plus at most a ticket "
                f"ref, and nothing but the optional [...] progress tag may "
                f"follow it")
    ph, ref = m.group(1), m.group(2)
    if ph != ph.upper():
        return (f"{value!r} writes the phase in lower case -- RFC § 1.2 takes "
                f"the uppercase § 1.6 enum value, and the phase doc is loaded "
                f"from its lowercased name, not from what the state says")
    _five = "/".join(sorted(TICKET_BEARING_PHASES))
    if ph in TICKET_BEARING_PHASES and not ref:
        return (f"{value!r} enters ticket-bearing phase {ph} with no T-### -- "
                f"RFC § 1.2 REQUIRES the ref for {_five}, and a cold agent "
                f"cannot act on a phase with no subject")
    if ph not in TICKET_BEARING_PHASES and ref:
        return (f"{value!r} attaches {ref} to {ph}, which is not one of the "
                f"five ticket-bearing phases ({_five}) -- RFC § 1.2 omits the "
                f"ref for every other phase; name the ticket in `task:`")
    return None


def transition_legal(source: str, destination: str) -> bool:
    """Is `source -> destination` an edge of the DFA?

    A phase in `ANY_FROM` is reachable from anywhere by explicit command, so it
    is legal regardless of the source row. A self-transition is legal for any
    known phase — re-entering BUILD after a failed VERIFY is ordinary work, not
    a state machine violation.
    """
    if destination in ANY_FROM:
        return True
    if source == destination:
        return source in VALID_TRANSITIONS or source in ANY_FROM
    return destination in VALID_TRANSITIONS.get(source, [])


def phase_document(phase: str) -> str:
    """The phase doc a given phase requires, relative to `protocol_dir`.

    The document is named from the LOWERCASED enum value, never from whatever
    casing the state happens to carry — which is why `phase_next_action_error`
    rejects a lowercase phase rather than helpfully accepting it.
    """
    return f"phases/{phase.lower()}.md"
