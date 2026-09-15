"""Protocol-state reconciliation (CORE-002).

CORE.md section 1.2 / OPS.md section 357-370 make BOARD checkbox presentation
*and* the deterministic STATE metadata -- `last_event`, the goal counters,
`schema_version` and `style_contract` -- reconciliation-owned. Recovery and
continuation share this reconciliation before validation, and `CLEAN` is a
statement about that WHOLE owned surface: OPS forbids reporting CLEAN while
repairable drift remains.

The first implementation of this module repaired BOARD checkboxes only, under a
direct `_atomic_write`, and returned `CLEAN` the moment no checkbox differed. A
STATE whose `last_event` disagreed with the LOG tail was therefore certified
clean and the very next `continue` failed validation. This module now:

  * derives the complete repair set from the authoritative BOARD/LOG/current
    intent, covering every reconciliation-owned field;
  * computes all target bytes first and runs the SAME complete-surface fast
    invariants the post-write gate uses against the *proposal*;
  * commits LOG + BOARD + STATE through one journaled OperationPlan/CAS
    transaction under the writer lock, with a DEC trace for the repair;
  * renders the identical plan under `dry_run` with zero writes.

There is deliberately no BOARD-only write path left: a partial repair that
reports CLEAN is the exact failure this module exists to prevent.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from .board import parse_board

_SECTION_BOX = {
    "## TODO": " ",
    "## BLOCKED": " ",
    "## DOING": "/",
    "## DONE": "x",
}
_TICKET_BOX_RE = re.compile(r"^(\s*- \[)([ x/])(\])")

# CORE section 1.5: two LOG lines are goal MARKERS -- the `DEC: goal pivot`
# line a new objective writes, and the `DEC: goal reauthorized` line section
# 2.4 requires from a re-authorizing `cc`.
_GOAL_MARKER_RE = re.compile(r"^goal (?:pivot|reauthorized)\b")
# CORE section 1.5: "Only increments are completion events -- a marker's own
# `N->0` records the reset, it is not a wave or a ticket."
_GOAL_INCREMENT_RE = re.compile(r"^goal_(waves|tickets) (\d+)->(\d+)$")

# The STATE keys reconciliation owns, in the order they are reported.
_OWNED_COUNTERS = ("goal_waves", "goal_tickets")


def _checkbox_drifts(board_text: str) -> list[dict]:
    drifts: list[dict] = []
    section = ""
    parsed = parse_board(board_text)
    ticket_section = {
        ticket_id: ticket.get("section", "")
        for ticket_id, ticket in parsed.get("tickets", {}).items()
    }
    for offset, line in enumerate(board_text.splitlines(), 1):
        if line.startswith("## "):
            section = line.strip()
            continue
        match = _TICKET_BOX_RE.match(line)
        if not match or section not in _SECTION_BOX:
            continue
        want = _SECTION_BOX[section]
        if match.group(2) != want:
            tid = re.match(rf"^\s*- \[{re.escape(match.group(2))}\] (T-\d+)", line)
            drifts.append(
                {
                    "line": offset,
                    "section": section,
                    "checkbox": match.group(2),
                    "expected": want,
                    "ticket": tid.group(1) if tid else None,
                    "from_board": ticket_section.get(tid.group(1) if tid else "") == section,
                }
            )
    return drifts


def _apply_checkbox_repairs(board_text: str, drifts: list[dict]) -> str:
    targets = {drift["line"]: drift["expected"] for drift in drifts}
    lines = board_text.splitlines(keepends=True)
    for lineno, box in targets.items():
        lines[lineno - 1] = _TICKET_BOX_RE.sub(rf"\g<1>{box}\g<3>", lines[lineno - 1], count=1)
    return "".join(lines)


def _derived_goal_counters(events) -> dict[str, int]:
    """Rebuild the goal counters exactly as CORE section 1.5 Recovery requires.

    The rebuilt count is the NUMBER OF INCREMENT EVENTS SINCE THE NEWEST GOAL
    MARKER -- not the `to` value of the last bump line. Both halves matter:

      * Two lines are markers, not one: the `DEC: goal pivot` line and the
        `DEC: goal reauthorized` line. Counting from the pivot alone rebuilds
        every bump a later re-authorization already cancelled, handing the run
        back a tripped valve the human cleared.
      * Only increments count. A marker's own `N->0` records the reset; it is
        not a wave or a ticket.

    The pivot line may have been sealed away if enough LOG activity happened
    since, so this walks the COMPLETE history the caller supplies (sealed
    segments plus the active LOG) -- the same walk section 1.5 mandates rather
    than the active file alone.
    """
    counts = {"goal_waves": 0, "goal_tickets": 0}
    for event in events:
        if event.get("taxonomy") != "DEC":
            continue
        text = (event.get("text") or "").strip()
        if _GOAL_MARKER_RE.match(text):
            counts = {"goal_waves": 0, "goal_tickets": 0}
            continue
        match = _GOAL_INCREMENT_RE.match(text)
        if match and int(match.group(3)) > int(match.group(2)):
            counts["goal_" + match.group(1)] += 1
    return counts


def _state_marker_repairs(state: dict, tail: int | None) -> list[dict]:
    """Repairs for the reconciliation-owned STATE freshness/schema markers."""
    from .state import running_schema_version, running_style_token

    repairs: list[dict] = []
    have = state.get("last_event")
    if tail is not None and have != tail:
        repairs.append(
            {
                "field": "last_event",
                "from": have,
                "to": tail,
                "surface": "state",
                "reason": "STATE freshness marker must equal the LOG tail (CORE section 1.2)",
            }
        )
    current_schema = running_schema_version()
    token = running_style_token()
    have_schema = state.get("schema_version")
    have_schema_int = (
        have_schema
        if isinstance(have_schema, int) and not isinstance(have_schema, bool)
        else None
    )
    if current_schema is not None and (
        have_schema_int is None or have_schema_int < current_schema
    ):
        repairs.append(
            {
                "field": "schema_version",
                "from": have_schema,
                "to": current_schema,
                "surface": "state",
                "reason": "readable legacy revision must upgrade to the current schema",
            }
        )
    # The style marker is enforced whenever it is present OR whenever the
    # schema moves: a token that disagrees with STYLE.md means the checkpoint
    # was written against a contract that is not the installed one.
    if token and state.get("style_contract") != token and (
        have_schema_int is None or have_schema_int <= (current_schema or have_schema_int)
    ):
        repairs.append(
            {
                "field": "style_contract",
                "from": state.get("style_contract"),
                "to": token,
                "surface": "state",
                "reason": "voice marker must equal the installed STYLE.md boot marker",
            }
        )
    return repairs


def _state_output_field_repairs(state: dict) -> list[dict]:
    """Migration repairs for PROVEN output-only fields persisted as input.

    The allowlist is CLOSED (`state.STATE_OUTPUT_ONLY_FIELDS`) and carries only
    fields whose historical semantics are already proven to be engine-computed
    OUTPUT, never canonical STATE input (today: `parked_work`). Such a field is
    removed by EXACT key -- never "unknown fields are ignored" -- because the
    defect is the engine's own projection vocabulary pasted back into the input
    document (W2-003).

    Any unknown field OUTSIDE the allowlist is deliberately untouched here: it
    produces no repair, so the strict-state error survives and reconciliation
    refuses (RECOVERY_BLOCKED). This function can therefore never widen into a
    generic unknown-field stripper.
    """
    from .state import STATE_KNOWN_FIELDS, STATE_OUTPUT_ONLY_FIELDS

    repairs: list[dict] = []
    for field in sorted(STATE_OUTPUT_ONLY_FIELDS):
        if field in state and field not in STATE_KNOWN_FIELDS:
            repairs.append(
                {
                    "field": field,
                    "from": state.get(field),
                    "to": None,
                    "surface": "state",
                    "remove": True,
                    "reason": (
                        f"{field!r} is engine OUTPUT-only (computed by the status/next "
                        "projections), not canonical STATE input; the exact key is "
                        "removed by the canonical legacy-state migration (T-1322)"
                    ),
                }
            )
    return repairs


def _state_blocker_repairs(
    state: dict, board: dict | None, resolve_blocker: str | None = None
) -> list[dict]:
    """Repairs for a non-empty `STATE.blocker` outside `phase: BLOCKED` (T-1324).

    The AUDAPACK deadlock class: CORE keeps `STATE.blocker` non-empty ONLY in
    `phase: BLOCKED`, but a legacy or aborted run can persist a non-empty
    blocker while the phase is an ordinary ACTIVE phase (SCOUT/BUILD/...).
    `binding_brake` -- the ONE hard-stop truth shared by the router and the
    admission guard -- then refuses every consequential tool as `WAIT_BLOCKED`,
    and NO canonical verb owned clearing that field: `recover` reconciled
    everything except the blocker and certified CLEAN, so known-root became a
    HARD BRAKE with no legal repair action.

    Classification is CLOSED and lifecycle-based, never prose matching:

      * `phase: BLOCKED` -- the blocker is the phase's own field; no repair.
      * a live `## BLOCKED` board ticket exists, OR the blocker opens with a
        recognised BLOCKED-class token from the closed `board` vocabulary
        (`HELD`, `WAIT_USER_CONFIRMATION`, `BLOCKED_EXTERNAL`, ...) -- real
        gate authority the engine cannot infer away. By default returned as a
        `refuse` repair: OPERATOR_DECISION_REQUIRED, zero bytes written.
      * no board block authority and no class token -- PROVEN stale in an
        active phase. Reset to `none` (never dropped: CORE requires the key),
        with the original STATE bytes archived as recovery evidence.

    Target C operator gate: when `resolve_blocker` carries an explicit operator
    DECISION, the gate is no longer ambiguous -- the engine is TOLD the gate is
    resolved. The blocker it owns (and only it) is cleared to `none`, the old
    value is preserved as recovery evidence, and the DEC records the authority.
    A live `## BLOCKED` board ticket is NOT owned here and is named in the
    reason for the follow-up `saipen ticket unblock`. Empty decision text never
    resolves a gate -- there is no generic unblock-anything path.
    """
    from .board import blocker_class
    from . import phases as _phases

    blocker = state.get("blocker")
    if not isinstance(blocker, str) or not blocker.strip() or blocker.strip().lower() == "none":
        return []
    phase = str(state.get("phase") or "")
    if phase.upper() == "BLOCKED" or phase not in _phases.ALL_PHASES:
        # BLOCKED: the blocker is consistent. Out-of-enum: `_state_phase_repairs`
        # owns the refusal -- never clear a blocker over an unproven phase.
        return []

    tickets = (board or {}).get("tickets") or {}
    live_blocked = sorted(
        tid
        for tid, ticket in tickets.items()
        if isinstance(ticket, dict) and ticket.get("section") == "## BLOCKED"
    )
    cls = blocker_class(blocker)
    if live_blocked or cls is not None:
        authority = (
            f"live ## BLOCKED board ticket(s) {', '.join(live_blocked)}"
            if live_blocked
            else f"recognised gate class {cls!r}"
        )
        if isinstance(resolve_blocker, str) and resolve_blocker.strip():
            decision = resolve_blocker.strip()
            board_note = (
                f"; {', '.join(live_blocked)} remain ## BLOCKED -- lift each with "
                '`saipen ticket unblock <T-###> "<decision>"`'
                if live_blocked
                else ""
            )
            return [
                {
                    "field": "blocker",
                    "from": blocker,
                    "to": "none",
                    "surface": "state",
                    "operator_authorized": True,
                    "follow_up": (
                        f'saipen ticket unblock {live_blocked[0]} "<decision>"'
                        if live_blocked
                        else None
                    ),
                    "reason": (
                        f"phase {phase!r} carries blocker {blocker!r} with "
                        f"{authority}; cleared by EXPLICIT operator authority "
                        f"{decision!r}. Only STATE.blocker is owned here, the "
                        "original bytes are archived as recovery evidence, and "
                        "the surface is revalidated immediately "
                        f"(OPERATOR_AUTHORIZED){board_note}"
                    ),
                }
            ]
        return [
            {
                "field": "blocker",
                "from": blocker,
                "to": None,
                "surface": "state",
                "refuse": True,
                "operator_decision_available": True,
                "canonical_next_command": 'saipen recover resolve-blocker "<decision>"',
                "reason": (
                    f"phase {phase!r} carries blocker {blocker!r} with {authority}; "
                    "the engine cannot infer whether that gate still applies, so "
                    "clearing it requires an explicit operator decision "
                    '(OPERATOR_DECISION_REQUIRED): run `saipen recover '
                    'resolve-blocker "<decision>"`'
                    + (
                        f' or `saipen ticket unblock {live_blocked[0]} "<decision>"`'
                        if live_blocked
                        else ""
                    )
                    + " -- zero bytes written"
                ),
            }
        ]

    return [
        {
            "field": "blocker",
            "from": blocker,
            "to": "none",
            "surface": "state",
            "reason": (
                f"phase {phase!r} is an ACTIVE phase and neither a ## BLOCKED board "
                "ticket nor a recognised gate class carries this blocker; CORE keeps "
                "STATE.blocker non-empty only in BLOCKED, so this is a proven stale "
                "blocker (SAFE_CANONICAL_REPAIR)"
            ),
        }
    ]


_GOAL_WAVES_CAP = 3
_GOAL_TICKETS_CAP = 20


_LEGAL_NEXT_PREFIXES = ("WAIT:", "saipen ", "RUN:", "RESUME:")


def _legacy_next_action(na: str) -> bool:
    """True when `next_action` violates the executable grammar (CORE / T-1324).

    Mirrors the exact predicate `fast_check` refuses on: a `PHASE` action must
    pass `phases.phase_next_action_error`, anything else must open with one of
    the four legal prefixes. Everything else is legacy/freeform prose.
    """
    from . import phases

    if na.startswith("PHASE "):
        return phases.phase_next_action_error(na) is not None
    return not na.startswith(_LEGAL_NEXT_PREFIXES)


def _state_next_action_repairs(
    state: dict, state_text: str, board_text: str, agent: str, project_root: Path
) -> list[dict]:
    """Target D: repair a legacy `next_action` ONLY when the router proves it.

    The SAITULS deadlock: `phase`/`task` are provable, but a freeform
    `next_action` fails the executable grammar, so every strict reader refuses
    the checkpoint and the mutating verbs that could rewrite it are unreachable
    behind the same brake. Clearing it needs no invention -- the SHARED router
    already projects `PHASE <phase> <task>` from state alone (router.py FINISH
    branch). This repair fires only when `route_next` returns EXACTLY that
    projection with reason `finish`; any other legacy value (unprovable phase,
    no active binding, ambiguous route) refuses as an operator decision.

    The original prose is preserved: the whole pre-repair STATE is archived by
    the shared evidence path, and the DEC names both sides.
    """
    from . import phases

    na = state.get("next_action")
    if not isinstance(na, str):
        return []
    na = na.strip()
    if not _legacy_next_action(na):
        return []

    def refuse(reason: str) -> list[dict]:
        return [
            {
                "field": "next_action",
                "from": na,
                "to": None,
                "surface": "state",
                "refuse": True,
                "terminal_disposition": "RECOVERY_BLOCKED",
                "reason": reason + " (OPERATOR_DECISION_REQUIRED)",
            }
        ]

    phase = str(state.get("phase") or "")
    task = str(state.get("task") or "")
    if phase not in phases.TICKET_BEARING_PHASES or not re.fullmatch(r"T-\d+", task):
        return refuse(
            f"legacy next_action {na!r} cannot be projected: phase {phase!r} is "
            "not ticket-bearing or task is not a work ticket"
        )

    # The blocker is owned by `_state_blocker_repairs`; neutralize it in a
    # PROVISIONAL copy so the router reaches its FINISH projection instead of
    # the brake branch. Nothing here is committed -- only the parsed action is.
    from .state import patch_state

    provisional = state_text
    if str(state.get("blocker") or "").strip().lower() not in ("", "none"):
        try:
            provisional = patch_state(state_text, {"blocker": "none"})
        except ValueError as exc:
            return refuse(f"cannot stage routing over malformed STATE: {exc}")

    from .router import audit_inbox_projection, route_next

    routed = route_next(
        provisional,
        board_text,
        current_agent=agent,
        audit_inbox=audit_inbox_projection(Path(project_root)),
    )
    canonical = f"PHASE {phase} {task}"
    if (
        routed.get("ok")
        and routed.get("action") == canonical
        and routed.get("reason") == "finish"
    ):
        return [
            {
                "field": "next_action",
                "from": na,
                "to": canonical,
                "surface": "state",
                "reason": (
                    f"legacy next_action {na!r} has no executable form; the shared "
                    f"router projects {canonical!r} (reason 'finish') from the "
                    "provable phase/task, so this is a deterministic "
                    "SAFE_CANONICAL_REPAIR (Target D)"
                ),
            }
        ]
    return refuse(
        f"legacy next_action {na!r} is ambiguous: the shared router does not "
        f"uniquely project {canonical!r} (routed "
        f"{routed.get('action')!r} / {routed.get('reason')!r})"
    )


def _board_adoption_repairs(
    board: dict | None, history, adopt_legacy: tuple | list
) -> list[dict]:
    """Target E: truthful legacy BOARD adoption, never a fabricated allocation.

    The SAITULS class: BOARD carries T-### records in a workable section whose
    canonical allocation event does not exist in the complete history. The
    allocation-identity gate (`fast_check` / `validate`) then refuses them, and
    the mutating verbs that could allocate are unreachable behind the same
    brake. Repairing by inventing a historical allocation event is a STOP gate;
    deleting the records is destructive.

    The truthful contract already available is the LOG itself: an adoption is an
    explicit, NOW-dated `DEC` that names the ticket in the structured slot. It
    claims no past allocation, preserves the original id/title/bytes, and only
    the ids the OPERATOR names are adopted. Every other unattested record
    refuses as an operator decision, so an unknown suspicious record can never
    be laundered into authority by a silent automatic pass.

    Returns a list of repairs; each is either `kind: adopt` (writes one NOW DEC)
    or `kind: attest` with `refuse: True` (operator must name it).
    """
    from .board import detached_ticket_id_known_ids

    if history is None:
        return []
    frontier = getattr(history, "max_ticket_id", 0) or 0
    if not frontier:
        # No allocation authority has ever existed: hand-authored fixtures stay
        # legal, exactly as the pre-write gate arms only past the frontier.
        return []
    known = detached_ticket_id_known_ids(history)
    requested = {str(t) for t in (adopt_legacy or ())}
    repairs: list[dict] = []
    for tid, ticket in sorted((board or {}).get("tickets", {}).items()):
        if not isinstance(ticket, dict):
            continue
        section = ticket.get("section")
        # VALIDATOR PARITY, not a section preference. The allocation-identity
        # gate (`validate.py`, CORE-003 / SRC-026:R003) arms over EVERY BOARD
        # record in EVERY section. This repair used to scan only `## TODO` and
        # `## DOING`, so a record in any other section produced a red gate with
        # no canonical operation able to see it: `recover` answered CLEAN,
        # `--adopt-legacy` could not name it, and the pre-commit gate refused
        # every commit -- `needs_local_mutation` true while all local repair
        # operations refuse, the combination T-1324 closed as forbidden.
        # Reproduced here by nine `## BLOCKED` records (T-1313, T-1309, T-1306,
        # T-1257, T-1099, T-407, T-406, T-442, T-575), which in turn pinned the
        # distribution guard at DIRTY_SOURCE and left all six installed agent
        # homes stale. The two surfaces judge one record set or the stop has no
        # exit.
        if section is None or tid in known:
            continue
        if tid in requested:
            repairs.append(
                {
                    "field": "board",
                    "kind": "adopt",
                    "ticket": tid,
                    "surface": "log",
                    "reason": (
                        f"{tid} has no [T-###] allocation event in the complete "
                        "history; explicitly adopted by the operator. A NOW-dated "
                        "DEC records the adoption and no historical allocation or "
                        "actor is fabricated (Target E LEGACY_ADOPTED)"
                    ),
                }
            )
        else:
            repairs.append(
                {
                    "field": "board",
                    "kind": "attest",
                    "ticket": tid,
                    "surface": "log",
                    "refuse": True,
                    "operator_decision_available": True,
                    "canonical_next_command": f"saipen recover --adopt-legacy {tid}",
                    "reason": (
                        f"{tid} sits in {section} with no [T-###] allocation event "
                        "in the complete history; adoption needs an explicit "
                        "operator decision -- run `saipen recover --adopt-legacy "
                        f"{tid}` (OPERATOR_DECISION_REQUIRED)"
                    ),
                }
            )
    return repairs


#: BOARD sections whose records are TERMINAL: the Work is over, so an `owner`
#: on them is historical attribution, never a live execution lease.
_TERMINAL_SECTIONS = ("## DONE",)


def _closure_contract_frontier(board: dict | None) -> int | None:
    """Lowest ticket id at which THIS project observes the closure contract.

    The modern closure contract is observable in exactly one immutable place:
    a BOARD record carrying `closure_mode`, the field the canonical finish
    operation writes. The lowest id carrying it is the project's own first
    observation of that generation, so every lower id was allocated before the
    contract existed here.

    Ticket ids are allocated monotonically, so this is a durable ordering fact
    of the record itself -- not a wall-clock guess, not an mtime, and not a
    property of the machine the recovery happens to run on. `None` means the
    contract has never been observed in this project at all, and the caller
    then falls back to historical event grammar.
    """
    observed: list[int] = []
    for tid, ticket in ((board or {}).get("tickets", {}) or {}).items():
        if not isinstance(ticket, dict):
            continue
        if not (tid.startswith("T-") and tid[2:].isdigit()):
            continue
        if str((ticket.get("fields") or {}).get("closure_mode", "") or "").strip():
            observed.append(int(tid[2:]))
    return min(observed) if observed else None


def _mechanized_ticket_ids(events) -> set[str]:
    """Ticket ids that ever appear on a MECHANIZED (`[op: ...]`) event.

    The `[op: <verb>-<id>]` slot is written only by the canonical operation
    layer. A record that never appears on one was never touched by the
    generation that owns closure_mode, so its grammar is the fallback
    compatibility marker when the BOARD carries no closure_mode at all.
    """
    return {
        ev.get("ticket") for ev in (events or ()) if ev.get("ticket") and ev.get("op_id")
    }


def _is_legacy_generation(tid: str, frontier: int | None, mechanized: set[str]) -> bool:
    """Is this record older than the closure contract that would judge it?

    Frontier known -> pure allocation order decides. Frontier unknown (no
    record in the project has ever carried closure_mode) -> the historical
    event grammar decides: a record the operation layer never touched predates
    it. Anything undecidable resolves to LEGACY, because the destructive
    mistake is the one this boundary exists to prevent.
    """
    if not (tid.startswith("T-") and tid[2:].isdigit()):
        return True
    if frontier is not None:
        return int(tid[2:]) < frontier
    return tid not in mechanized


def _board_lifecycle_repairs(
    board: dict | None, events, state: dict | None = None, history=None
) -> list[dict]:
    """Deterministic BOARD lifecycle repairs (SRC-043 / SAIPENDEFECT).

    Three defect classes, each the mechanical consequence of an already-closed
    rule -- never a guess, never fabricated evidence:

      * INCOMPLETE CLAIM PAIR -- CORE's both-or-neither rule makes a half
        ``owner``/``claim_time`` pair INVALID *on claimable Work*. The
        deterministic repair removes BOTH halves, so the record keeps no claim
        rather than a fabricated one. It is scoped to claimable sections on
        purpose: a claim is a LIVE LEASE, and a terminal record has no lease to
        be half of (see ``_TERMINAL_SECTIONS``).
      * DOING WITH NO CLAIM -- a ``## DOING`` Work is by definition claimed
        (``saipen claim`` writes the pair). An unclaimed DOING record was never
        started and belongs in ``## TODO``.
      * PHANTOM DONE -- a ``## DONE`` record of the CURRENT generation carrying
        no ``closure_mode``, no ``owner``, no ``claim_time`` AND no verification
        evidence in history was never completed by a canonical operation, so it
        is reopened into ``## TODO``. This class carries ``requires_approval``:
        a hand-authored DONE could be a real completion awaiting
        reconstruction, so bare recovery never reopens it silently -- ONE
        operator approval of the whole repair plan authorizes it.

    LEGACY COMPATIBILITY BOUNDARY. Both destructive classes above are written
    in terms of fields (`closure_mode`, `claim_time`) and an evidence grammar
    (VERIFY boundary + `conf: high`) that are YOUNGER than the records they are
    now asked to judge. Applying them to a record created before they existed
    reads "this field did not exist yet" as "this completion was fabricated",
    and proposes to rewrite valid history. So:

      * ``_closure_contract_frontier`` / ``_is_legacy_generation`` split the
        DONE set into records the modern contract governs and records that
        predate it;
      * a legacy DONE proven by the grammar of ITS generation
        (``bulk_legacy_completion_evidence``) keeps DONE and produces NO atom;
      * a legacy DONE with no evidence in EITHER grammar is genuinely
        ambiguous: it reports ``OPERATOR_DECISION_REQUIRED`` with an exact
        command, and is never proposed as a deterministic reopen;
      * a legacy terminal ``owner`` with no ``claim_time`` keeps its historical
        attribution: it is not a live lease and nothing may erase it to satisfy
        a lease schema that postdates it.

    Returns mutation atoms and -- distinguished by ``refuse: True`` -- refusal
    atoms the caller must surface rather than apply.
    """
    if not board:
        return []
    tickets = board.get("tickets", {})
    repairs: list[dict] = []
    cleared: set[str] = set()
    frontier = _closure_contract_frontier(board)
    mechanized = _mechanized_ticket_ids(events)
    for tid, ticket in sorted(tickets.items()):
        if not isinstance(ticket, dict):
            continue
        fields = ticket.get("fields", {})
        section = ticket.get("section")
        owner = str(fields.get("owner", "") or "").strip()
        claim_time = str(fields.get("claim_time", "") or "").strip()
        if bool(owner) == bool(claim_time):
            continue
        if section in _TERMINAL_SECTIONS and owner and not claim_time:
            # Terminal Work has no live lease. `owner` here is the historical
            # record of WHO did it, and the both-or-neither rule governs the
            # lease, not the attribution. Clearing it would discard provenance
            # to satisfy a schema that did not exist when the record was
            # written -- a lossy rewrite of history, not a repair.
            continue
        repairs.append(
            {
                "field": "board",
                "kind": "claim-clear",
                "ticket": tid,
                "surface": "board",
                "section": section,
                "fields": ["owner", "claim_time"],
                "reason": (
                    f"{tid} carries a half claim pair (owner={owner!r}, "
                    f"claim_time={claim_time!r}) on claimable Work; CORE's "
                    "both-or-neither rule makes the LEASE INVALID, so the "
                    "deterministic repair removes BOTH halves and fabricates "
                    "no owner or time (SRC-043)"
                ),
            }
        )
        cleared.add(tid)
    for tid, ticket in sorted(tickets.items()):
        if ticket.get("section") != "## DOING":
            continue
        fields = ticket.get("fields", {})
        owner = str(fields.get("owner", "") or "").strip()
        claim_time = str(fields.get("claim_time", "") or "").strip()
        if tid == (state or {}).get("task"):
            # The ticket STATE names as the active Work is NOT "unstarted" even
            # when a legacy hand-authored record carries no claim pair; moving
            # it would commit a STATE.task/BOARD split the floor rejects.
            continue
        if tid in cleared or (not owner and not claim_time):
            repairs.append(
                {
                    "field": "board",
                    "kind": "section-move",
                    "ticket": tid,
                    "surface": "board",
                    "from_section": "## DOING",
                    "to_section": "## TODO",
                    "reason": (
                        f"{tid} sits under ## DOING with no owner/claim_time pair; "
                        "an unclaimed DOING Work was never started, so it returns "
                        "to ## TODO (SRC-043)"
                    ),
                }
            )
    if events is not None:
        # A ticket record BELOW the allocation frontier is a real allocated
        # Work whose completion can be judged; a hand-authored record ABOVE it
        # (or in a project that never allocated) is a different class entirely
        # and is never reopened by this rule. This is what keeps minimal
        # fixtures and never-allocated scaffolds out of scope.
        alloc_frontier = getattr(history, "max_ticket_id", 0) or 0
        done_ids = [
            tid
            for tid, ticket in tickets.items()
            if ticket.get("section") == "## DONE"
            and alloc_frontier
            and tid.startswith("T-")
            and tid[2:].isdigit()
            and int(tid[2:]) <= alloc_frontier
        ]
        evidence_ok: dict = {}
        legacy_ok: dict = {}
        if done_ids:
            try:
                from .log import (
                    bulk_legacy_completion_evidence,
                    bulk_verification_evidence,
                )

                evidence_ok = bulk_verification_evidence(events, done_ids)
                legacy_ok = bulk_legacy_completion_evidence(events, done_ids)
            except Exception:
                evidence_ok = {}
                legacy_ok = {}
        for tid in sorted(done_ids):
            fields = tickets[tid].get("fields", {})
            has_closure = bool(str(fields.get("closure_mode", "") or "").strip())
            owner = str(fields.get("owner", "") or "").strip()
            claim_time = str(fields.get("claim_time", "") or "").strip()
            if has_closure or owner or claim_time:
                continue
            ok, _reason = evidence_ok.get(tid, (False, "unproven"))
            if ok:
                continue
            if not _is_legacy_generation(tid, frontier, mechanized):
                repairs.append(
                    {
                        "field": "board",
                        "kind": "section-move",
                        "ticket": tid,
                        "surface": "board",
                        "from_section": "## DONE",
                        "to_section": "## TODO",
                        "requires_approval": True,
                        "generation": "current",
                        "reason": (
                            f"{tid} sits under ## DONE with no closure_mode, no "
                            "owner, no claim_time and no verification evidence in "
                            "history, and was allocated AFTER this project's "
                            "closure contract became observable"
                            + (f" (frontier T-{frontier})" if frontier else "")
                            + "; the completion was never established by a "
                            "canonical operation, so reopening it into ## TODO "
                            "requires ONE operator approval of the repair plan "
                            "(SRC-043)"
                        ),
                    }
                )
                continue
            legacy_proven, legacy_reason = legacy_ok.get(tid, (False, "unproven"))
            if legacy_proven:
                # Valid under the rules that existed for its generation. The
                # record stands exactly as written: no atom, no fabricated
                # closure_mode, no rewritten LOG.
                continue
            repairs.append(
                {
                    "field": "board",
                    "kind": "legacy-done-review",
                    "ticket": tid,
                    "surface": "board",
                    "section": "## DONE",
                    "refuse": True,
                    "operator_decision_available": True,
                    "generation": "legacy",
                    "canonical_next_command": (
                        f"saipen recover --attest-legacy-done {tid}"
                    ),
                    "reason": (
                        f"{tid} predates this project's closure contract"
                        + (f" (frontier T-{frontier})" if frontier else "")
                        + " and carries no execution evidence in EITHER the "
                        f"current or its own generation's grammar ({legacy_reason}); "
                        "a missing field that did not exist yet is not proof the "
                        "completion was fabricated, so this is an operator "
                        "decision, never an automatic reopen -- run `saipen "
                        f"recover --attest-legacy-done {tid}` to let the "
                        "historical completion stand (OPERATOR_DECISION_REQUIRED)"
                    ),
                }
            )
    return repairs


def _apply_lifecycle_repairs(board_text: str, repairs: list[dict]) -> str:
    """Apply claim-clear and section-move repairs by bounded line surgery."""
    from .board import remove_ticket_field

    if not repairs:
        return board_text
    tickets = parse_board(board_text).get("tickets", {})
    lines: list[str | None] = board_text.splitlines(keepends=True)

    removals: dict[str, list[str]] = {}
    moves: dict[str, str] = {}
    for repair in repairs:
        tid = repair.get("ticket")
        if tid not in tickets:
            continue
        if repair.get("kind") == "claim-clear":
            removals.setdefault(tid, []).extend(repair.get("fields", []))
        elif repair.get("kind") == "section-move":
            moves[tid] = repair["to_section"]

    for tid, fields in removals.items():
        line_no = tickets[tid]["line_no"]
        raw = lines[line_no - 1].rstrip("\n")
        for field in dict.fromkeys(fields):
            raw = remove_ticket_field(raw, field)
        lines[line_no - 1] = raw + "\n"

    moved: dict[str, list[str]] = {}
    for tid, target in sorted(moves.items()):
        line_no = tickets[tid]["line_no"]
        raw = lines[line_no - 1].rstrip("\n")
        raw = _TICKET_BOX_RE.sub(r"\g<1> \g<3>", raw, count=1)
        lines[line_no - 1] = None
        moved.setdefault(target, []).append(raw + "\n")

    out: list[str] = []
    for line in lines:
        if line is None:
            continue
        out.append(line)
        stripped = line.strip()
        if stripped.startswith("## ") and stripped in moved:
            out.extend(moved[stripped])
    return "".join(out)


def _plan_repair_id(
    board_drifts: list[dict],
    state_repairs: list[dict],
    lifecycle_repairs: list[dict],
    attest_ids: list[str],
) -> str:
    """Content identity of the COMPLETE bounded repair set (SRC-043).

    Approval binds to this digest, so the exact set the operator saw is the
    exact set that is applied; a changed surface recomputes a different id and
    the approved repair is refused as stale.
    """
    import hashlib
    import json

    payload = {
        "schema": 1,
        "board_drifts": [
            {"line": d.get("line"), "ticket": d.get("ticket"), "to": d.get("expected")}
            for d in board_drifts
        ],
        "state_repairs": [
            {
                "field": r.get("field"),
                "from": r.get("from"),
                "to": r.get("to"),
                "remove": bool(r.get("remove")),
                "blocked": bool(r.get("blocked")),
            }
            for r in state_repairs
            if not r.get("refuse") and not r.get("blocked")
        ],
        "lifecycle_repairs": [
            {
                "ticket": r.get("ticket"),
                "kind": r.get("kind"),
                "from": r.get("from_section"),
                "to": r.get("to_section"),
                "fields": r.get("fields"),
            }
            for r in lifecycle_repairs
        ],
        "adoptions": sorted(attest_ids),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _state_counter_repairs(state: dict, events) -> list[dict]:
    """Repairs for the goal counters, owned only while the intent is `goal`.

    CORE-001 (audit-all3): the representation is the truth, and any non-equal
    counter must produce a repair or an explicit refusal the validator cannot
    silently ignore.

      * BELOW the rebuilt count -- the section 1.5 crash signature (a bump
        reached the LOG and never STATE). Repaired upward. Doing so can only
        trip the safety valve EARLIER, which section 2.4 calls deliberate
        and conservative.
      * ABOVE the rebuilt count but still BELOW the safety cap -- an ordinary
        ahead mismatch (e.g. derived=0/state=1). Repaired DOWNWARD to the
        canonical evidence.
      * AT or OVER the safety cap while canonical history is lower -- the
        tripped safety valve. NEVER repaired downward (that would silently
        clear a valve the human has not re-authorized) and never certified
        CLEAN: returned as a `refuse` repair the caller turns into an explicit
        non-CLEAN classification requiring the reauthorization path.
      * ABSENT -- initialized from the evidence (including to 0).
    """
    if state.get("execution_intent") != "goal":
        return []
    rebuilt = _derived_goal_counters(events)
    cap = {
        "goal_waves": _GOAL_WAVES_CAP,
        "goal_tickets": _GOAL_TICKETS_CAP,
    }
    repairs: list[dict] = []
    for field in _OWNED_COUNTERS:
        have = state.get(field)
        want = rebuilt.get(field, 0)
        if isinstance(have, bool) or not isinstance(have, int):
            if have is None:
                repairs.append(
                    {
                        "field": field,
                        "from": None,
                        "to": want,
                        "surface": "state",
                        "reason": "goal counter absent under goal intent; initialized from "
                        "the section 1.5 rebuild (CORE section 1.2)",
                    }
                )
            elif have is not None:
                repairs.append(
                    {
                        "field": field,
                        "from": have,
                        "to": want,
                        "surface": "state",
                        "reason": "goal counter is malformed (non-integer); rebuilt from "
                        "the section 1.5 evidence (CORE section 1.2)",
                    }
                )
            continue
        if have == want:
            continue
        if want > have:
            repairs.append(
                {
                    "field": field,
                    "from": have,
                    "to": want,
                    "surface": "state",
                    "reason": "goal counter behind the section 1.5 rebuild -- a bump reached "
                    "the LOG and never reached STATE (CORE section 1.5)",
                }
            )
            continue
        if have >= cap[field]:
            repairs.append(
                {
                    "field": field,
                    "from": have,
                    "to": want,
                    "surface": "state",
                    "reason": "goal counter is at/over the safety cap while canonical "
                    "history is lower -- never silently cleared without "
                    "re-authorization (CORE section 2.4)",
                    "refuse": True,
                    "operator_decision_available": True,
                    "canonical_next_command": "saipen continue",
                }
            )
            continue
        repairs.append(
            {
                "field": field,
                "from": have,
                "to": want,
                "surface": "state",
                "reason": "goal counter ahead of the section 1.5 rebuild but under the "
                "safety cap -- reconciled down to canonical evidence (CORE-001)",
            }
        )
    return repairs


def _tripped_valve_repairs(state: dict) -> list[dict]:
    """The tripped valve is an invariant, not a side effect of counter drift.

    `_state_counter_repairs` only notices a valve while the counter DISAGREES
    with canonical history. The ordinary way a valve trips is by honest
    counting -- `have == want == 20` -- and that path hits the equality
    `continue`, emits nothing, and lets the whole reconciliation certify CLEAN
    over a run that MAINTENANCE section 2.4 says must be paused.

    Witnessed (T-1181): `validate.py` reported `execution_intent: goal with
    goal_waves=0/goal_tickets=20 is the tripped safety valve (caps 3/20), but
    next_action='PHASE SHIP T-1242'` while `saipen continue`'s reconciliation
    returned CLEAN on the same STATE in the same minute. Two gates, one
    condition, opposite answers.

    So the counters are read directly against the caps, and the field checked
    is `next_action` -- reconciliation-owned, and the one field section 2.4
    requires the trip to be visible in. The grammar is not respelled here:
    `state._SAFETY_VALVE_RE` already owns it, and a second spelling of a
    verbatim protocol string is a second thing to drift.

    Never repaired silently. A tripped valve is the human's to clear through
    `cc`, so this returns a `refuse` repair -- the same shape the at-cap
    counter case uses -- which the caller turns into RECONCILE_REAUTH_REQUIRED.
    """
    from .state import _SAFETY_VALVE_RE

    if state.get("execution_intent") != "goal":
        return []

    caps = {"goal_waves": _GOAL_WAVES_CAP, "goal_tickets": _GOAL_TICKETS_CAP}
    tripped = {
        field: value
        for field, cap in caps.items()
        if isinstance((value := state.get(field)), int)
        and not isinstance(value, bool)
        and value >= cap
    }
    if not tripped:
        return []

    waves = state.get("goal_waves") or 0
    tickets = state.get("goal_tickets") or 0
    want = f"WAIT: safety valve reached ({waves} waves / {tickets} tickets) -- run 'cc' to continue"

    have = state.get("next_action")
    if isinstance(have, str) and _SAFETY_VALVE_RE.match(have.removeprefix("WAIT: ").strip()):
        # Already stating the pause. The counters stay at the cap on purpose --
        # they ARE the tripped condition, and tidying them walks past the valve.
        return []

    named = ", ".join(f"{field}={value}" for field, value in sorted(tripped.items()))
    return [
        {
            "field": "next_action",
            "from": have,
            "to": want,
            "surface": "state",
            "reason": (
                f"safety valve tripped ({named}) but next_action does not state the pause -- "
                "MAINTENANCE section 2.4 requires the section 1.2 WAIT form, and `cc` is the "
                "only re-authorization; reconciliation must not certify CLEAN over it"
            ),
            "refuse": True,
            "operator_decision_available": True,
            "canonical_next_command": "saipen continue",
        }
    ]


# The one LOG shape that PROVES which phase the state is in: the canonical
# `transition` operation journals `RUN: transition to <PHASE>`. `claim-`,
# `finish-` and `goal-entry-` events do not name a destination phase, so they
# are not evidence about the phase and are deliberately not matched here.
_PHASE_EVENT_RE = re.compile(r"^transition to ([A-Z][A-Z_]*)\b")


def _transition_chain(events, budget: int | None) -> list[tuple[int, str]]:
    """Every phase a phase-changing event PROVES, oldest first, to `budget`.

    Each `transition to <PHASE>` event proves a DESTINATION; the phase a
    transition came FROM is the previous destination in the same ordered chain.
    That is the whole proof: the LOG records destinations, and the chain is what
    makes a source knowable at all -- which is why a lone transition event can
    prove a destination but never a pair.

    Evidence only: an event whose destination is outside the enum proves
    nothing, and an event after `STATE.last_event` describes a phase this STATE
    has not summarised yet.
    """
    from . import phases as _phases

    chain: list[tuple[int, str]] = []
    for event in events:
        number = event.get("event")
        if not isinstance(number, int) or isinstance(number, bool):
            continue
        if budget is not None and number > budget:
            continue
        if not str(event.get("op_id") or "").startswith("transition-"):
            continue
        match = _PHASE_EVENT_RE.match((event.get("text") or "").strip())
        if not match:
            continue
        candidate = match.group(1)
        if candidate not in _phases.ALL_PHASES:
            continue
        chain.append((number, candidate))
    chain.sort(key=lambda item: item[0])
    return chain


def _state_phase_repairs(state: dict, events, board: dict | None = None) -> list[dict]:
    """Repairs for an out-of-enum `phase` / `transition_from` (T-1318).

    Defect class this closes -- KNOWN ROOT collapsing into NO LEGAL ACTION.
    Reconciliation owned BOARD checkboxes, `last_event`, the goal counters, the
    schema/style markers and the safety valve, but NOT the phase. A STATE whose
    `phase` sat outside the enum therefore had no owner anywhere: every strict
    reader refused it (`state-malformed`), the guard refused generic shell
    (`PROTOCOL_STATE_INVALID`), and the canonical namespace -- the only surface
    permitted to write STATE.md -- refused the very operation that could repair
    it. The project stayed bound and became unworkable (FastPrompter, 13.09.26,
    `phase: IMPL`).

    The replacement is NEVER a guess. It is the phase named by the NEWEST legal
    phase-changing event at or before `STATE.last_event` -- the same history the
    STATE claims to summarise -- and the resulting `(transition_from, phase)`
    pair must be DFA-reachable (`ANY_FROM` or the table's own edge). With no such
    event, or with an unreachable pair, the repair is `blocked`: it refuses with
    ZERO bytes written rather than inventing a phase, because a phase with no
    history behind it is exactly the fabrication this ticket exists to prevent.
    """
    from . import phases as _phases

    phase = state.get("phase")
    transition_from = state.get("transition_from")
    phase_bad = phase not in _phases.ALL_PHASES
    # A legal phase is not automatically a legal PAIR: `phase: BUILD` with
    # `transition_from: DONE` is refused by the DFA (allowed from DONE:
    # SCOUT/PLAN/HUNT/BLOCKED), so the transaction gate would reject a state
    # this repair had certified. Both fields are therefore in scope together.
    pair_bad = bool(
        not phase_bad
        and phase != "INIT"
        and transition_from
        and transition_from != phase
        and not (
            phase in _phases.ANY_FROM
            or (
                transition_from in _phases.ALL_PHASES
                and _phases.transition_legal(transition_from, phase)
            )
        )
    )
    if not (phase_bad or pair_bad):
        return []

    # The one deliberate non-DFA pair is the canonical active-ticket park:
    # BUILD/VERIFY/REVIEW/SHIP -> DONE after `ticket block`.  Fast validation
    # binds that shape to the newest journal event and the exact ticket still
    # in BOARD.BLOCKED.  Reconciliation must consume the same authority;
    # treating a valid parked parent as malformed made crash recovery report a
    # second, contradictory failure after it had already converged the journal.
    #
    # SRC-043: `block_parked_evidence_error` returns None BOTH for the legal
    # park shape AND for every pair it does not own (any destination other than
    # DONE). Using it as a blanket `return []` therefore left every non-DONE
    # illegal pair -- e.g. `DONE -> BUILD` -- with NO phase repair, so recovery
    # exposed no canonical fix and the operator was told to edit STATE.md by
    # hand. The carve-out is scoped to the destination it actually owns.
    if board is not None and not phase_bad and phase == "DONE":
        from .fast_check import block_parked_evidence_error

        if block_parked_evidence_error(state, board, events) is None:
            return []

    def blocked(reason: str) -> list[dict]:
        return [
            {
                "field": "phase",
                "from": phase,
                "to": None,
                "surface": "state",
                "blocked": True,
                "terminal_disposition": "RECOVERY_BLOCKED",
                "reason": reason,
            }
        ]

    last_event = state.get("last_event")
    budget = (
        last_event
        if isinstance(last_event, int) and not isinstance(last_event, bool)
        else None
    )
    chain = _transition_chain(events, budget)
    if not chain:
        return blocked(
            f"phase {phase!r} with transition_from {transition_from!r} cannot be "
            "reconciled: no legal `transition to <PHASE>` event at or before "
            "STATE.last_event proves a replacement, and an unprovable phase "
            "repair refuses with zero bytes written (T-1318)"
        )
    number, target = chain[-1]
    source = chain[-2][1] if len(chain) > 1 else transition_from
    if not (
        target in _phases.ANY_FROM
        or (source in _phases.ALL_PHASES and _phases.transition_legal(source, target))
    ):
        return blocked(
            f"phase {phase!r} with transition_from {transition_from!r} cannot be "
            f"reconciled: E-{number} proves the destination {target}, but no "
            f"provable source reaches it ({source!r} -> {target!r} is outside the "
            "DFA), so committing the pair would write a state the release gate "
            "rejects (T-1318)"
        )

    repairs: list[dict] = []
    if phase != target:
        repairs.append(
            {
                "field": "phase",
                "from": phase,
                "to": target,
                "surface": "state",
                "reason": (
                    f"phase {phase!r} disagrees with the newest provable "
                    f"phase-changing event E-{number}, which names {target} (T-1318)"
                ),
            }
        )
    if source is not None and transition_from != source:
        repairs.append(
            {
                "field": "transition_from",
                "from": transition_from,
                "to": source,
                "surface": "state",
                "reason": (
                    f"transition_from {transition_from!r} does not reach {target}; "
                    f"the transition chain proves the pair {source} -> {target} "
                    "(T-1318)"
                ),
            }
        )
    return repairs


def _repair_summary(board_drifts: list[dict], state_repairs: list[dict]) -> str:
    parts: list[str] = []
    if board_drifts:
        parts.append(f"{len(board_drifts)} board checkbox drift(s)")
    for repair in state_repairs:
        if repair.get("blocked"):
            parts.append(f"{repair['field']} {repair['from']!r}->BLOCKED")
            continue
        if repair.get("remove"):
            parts.append(f"{repair['field']} {repair['from']!r}->REMOVED")
            continue
        parts.append(f"{repair['field']} {repair['from']!r}->{repair['to']!r}")
    return "; ".join(parts)


def _blocked_recovery_fields(
    repairs: tuple | list = (),
    *,
    command: str | None = None,
    terminal_disposition: str | None = None,
    evidence_reference: str | None = None,
    reason_code: str | None = None,
) -> dict:
    """One T-1324 remediation vocabulary for every non-repairing result.

    A refusal may either expose one exact operator command or terminate as a
    truthful read-only diagnosis. It may never advertise bare ``recover`` when
    that same invocation can only return the same refusal again.
    """
    repairs = list(repairs or ())
    terminals = {
        str(item.get("terminal_disposition"))
        for item in repairs
        if item.get("terminal_disposition")
    }
    commands = {
        str(item.get("canonical_next_command"))
        for item in repairs
        if item.get("canonical_next_command")
    }
    surfaces = {str(item.get("surface")) for item in repairs if item.get("surface")}
    fields = {str(item.get("field")) for item in repairs if item.get("field")}
    if terminal_disposition is None and terminals:
        terminal_disposition = min(terminals)
    if command is None and terminal_disposition is None and len(commands) == 1:
        command = next(iter(commands))
    if command is None and terminal_disposition is None:
        terminal_disposition = "RECOVERY_BLOCKED"
    if terminal_disposition is not None:
        command = None

    instruction = "READ_ONLY_DIAGNOSIS_ONLY -- do not probe mutating verbs"
    if command:
        instruction += f"; the only sanctioned mutation is `{command}`"
    else:
        instruction += "; no local mutation can reconstruct the missing truth"
    if len(surfaces) == 1:
        blocking_surface = next(iter(surfaces))
    elif evidence_reference == ".saipen/LOG.md":
        blocking_surface = "log"
    elif evidence_reference == ".saipen/STATE.md":
        blocking_surface = "state"
    else:
        blocking_surface = None
    result = {
        "needs_local_mutation": False,
        "safe_auto_repair_available": False,
        "operator_decision_available": command is not None,
        "canonical_next_command": command,
        "read_only": True,
        "terminal_disposition": terminal_disposition,
        "blocking_surface": blocking_surface,
        "blocking_field": next(iter(fields)) if len(fields) == 1 else None,
        "evidence_reference": evidence_reference,
        "diagnosis": "READ_ONLY_DIAGNOSIS_ONLY",
        "read_only_diagnosis_only": True,
        "instruction": instruction,
        "forbidden_probes": [
            "saipen stop",
            "saipen transition",
            "saipen goal",
            "saipen ticket",
            "Bash",
            "Edit",
            "Write",
        ],
    }
    if reason_code:
        result["reason_code"] = reason_code
    return result


def _ensure_audit_contract(result: dict, project_root: Path) -> dict:
    """Enroll this project in the protocol's own audit-evidence contract.

    WHY THE RECONCILIATION BOUNDARY IS THE LIFECYCLE POINT
    -----------------------------------------------------
    `reconcile_protocol_state` is the protocol's ONE self-healing entry: an
    ordinary `continue`/`cc`, a `recover`, and fleet admission all pass through
    it before anything is routed. By the time it returns success, "this is a
    real SAIPEN project whose canonical checkpoint is readable" is not a
    guess -- it is the thing that just happened. That is exactly the
    precondition under which the export contract may legally be minted, so no
    new setup flow is introduced and no operator has to remember a flag.

    A packager cannot know which of `.saipen/` is load-bearing, so a project
    that never declared its evidence packages as PROTOCOL_MANIFEST_ABSENT and
    is read downstream as a project with no lifecycle at all. Enrollment must
    therefore be a property of USING the protocol.

    Deliberately narrow:
      * a dry-run reconciliation writes nothing (that is what dry_run means);
      * a refused enrollment NEVER fails the reconciliation -- the canonical
        mutation is already committed when this runs, and a derived
        declaration may not un-commit real work -- but it IS reported, because
        a refusal that says nothing is the silent no-op this exists to
        prevent;
      * `audit_manifest.ensure` owns every legality rule (no protocol memory,
        unloadable checkpoint, declaration that is not this contract, a NEWER
        contract), so there is exactly one implementation of the contract's
        own rules, and the CLI surface cannot drift from the lifecycle hook.

    The result key is added only when the enrollment CHANGED something or was
    refused: a steady-state reconciliation output stays exactly what it was.
    """
    if result.get("dry_run"):
        return result
    try:
        from . import audit_manifest
    except ImportError as exc:  # pragma: no cover - import graph is static
        return {
            **result,
            "audit_manifest": {
                "ok": False,
                "code": "AUDIT_MANIFEST_REFUSED",
                "detail": f"audit manifest module unavailable: {exc}",
            },
        }
    try:
        outcome = audit_manifest.ensure(project_root)
    except OSError as exc:
        return {
            **result,
            "audit_manifest": {
                "ok": False,
                "code": "AUDIT_MANIFEST_REFUSED",
                "reason_code": "AUDIT_MANIFEST_UNWRITABLE",
                "detail": str(exc),
            },
        }
    if outcome.get("changed") or not outcome.get("ok"):
        return {**result, "audit_manifest": outcome}
    return result


def reconcile_protocol_state(
    root: Path | str,
    agent: str,
    *,
    dry_run: bool = False,
    adopt_legacy: tuple | list = (),
    resolve_blocker: str | None = None,
    approved_repair_id: str | None = None,
    attest_legacy_done: tuple | list = (),
) -> dict:
    """Derive, validate and (unless dry_run) commit the complete repair set.

    `adopt_legacy` names legacy BOARD ticket ids the OPERATOR explicitly adopts
    (Target E). Adoption appends a NOW-dated LOG DEC and never fabricates a
    historical allocation event; an unattested ticket NOT named here refuses as
    OPERATOR_DECISION_REQUIRED.

    `attest_legacy_done` names LEGACY-generation `## DONE` ticket ids whose
    completion the OPERATOR confirms. It appends one NOW-dated DEC per ticket
    recording that decision; it fabricates no `closure_mode` for a generation
    that had none and rewrites no historical LOG line. It is the explicit
    answer to a `legacy-done-review` refusal.

    `resolve_blocker` carries an explicit operator decision (Target C) that
    clears a gated `STATE.blocker`. It is not a generic unblock: empty text is
    ignored, a live `## BLOCKED` board ticket is never owned here, and the
    decision is recorded in the LOG DEC with the original STATE archived.
    """
    project_root = Path(root)
    try:
        from .operations import (
            _docs_preconditions,
            _event_line,
            _identity,
            _log_targets,
            _read,
            _target,
        )
        from .fast_check import validate_texts
        from .log import legacy_done_attestation_text
        from .plan import apply_plan, build_plan
    except ImportError as exc:  # pragma: no cover - import graph is static
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}

    try:
        docs, state, _board, log_tail = _read(project_root, allow_malformed_state=True)
    except Exception as exc:
        # CheckpointError / HomeDeadError / OSError all mean the surface cannot
        # be reconciled mechanically. Refuse loudly -- none of them is the
        # absence of drift. A CheckpointError that already names its own class
        # (e.g. HISTORY_LEDGER_CORRUPT for immutable-ledger corruption) keeps
        # that precise code so the outer Fleet/continue surface reports a
        # machine-readable blocked classification, never a generic dead end.
        result = {
            "ok": False,
            "code": getattr(exc, "code", "VALIDATION_FAILED"),
            "detail": str(exc),
        }
        if result["code"] == "HISTORY_LEDGER_CORRUPT":
            result.update(
                _blocked_recovery_fields(
                    terminal_disposition="FORENSICALLY_UNRECOVERABLE",
                    evidence_reference=".saipen/LOG.md",
                    reason_code="HISTORY_LEDGER_CORRUPT",
                )
            )
        return result

    events = docs["_history"].events if docs.get("_history") is not None else ()
    state_text = docs["state"].text_norm
    board_text = docs["board"].text_norm
    # Present only when the strict contract refused its own STATE -- i.e. the
    # drift is severe enough that the repair set is the last chance before the
    # surface is declared unreconcileable. Reported, never silently healed.
    strict_state_error = docs.get("_state_error", "")

    board_drifts = _checkbox_drifts(board_text)
    state_repairs = (
        _state_output_field_repairs(state)
        + _state_marker_repairs(state, log_tail)
        + _state_counter_repairs(state, events)
        + _tripped_valve_repairs(state)
        + _state_phase_repairs(state, events, _board)
        + _state_blocker_repairs(state, _board, resolve_blocker)
        + _state_next_action_repairs(state, state_text, board_text, agent, project_root)
    )
    adoption_repairs = _board_adoption_repairs(_board, docs.get("_history"), adopt_legacy)
    lifecycle_all = _board_lifecycle_repairs(
        _board, events, state, docs.get("_history")
    )
    # A refusal atom is an OPERATOR DECISION, never a mutation. It is reported
    # with its exact command and is excluded from the applicable plan, so
    # approving the plan can never silently apply it.
    attested = {str(t) for t in (attest_legacy_done or ())}
    lifecycle_refusals = [
        repair
        for repair in lifecycle_all
        if repair.get("refuse") and repair.get("ticket") not in attested
    ]
    lifecycle_attestations = [
        repair
        for repair in lifecycle_all
        if repair.get("refuse")
        and repair.get("kind") == "legacy-done-review"
        and repair.get("ticket") in attested
    ]
    lifecycle_candidates = [
        repair for repair in lifecycle_all if not repair.get("refuse")
    ]
    # SRC-043: the whole BOARD lifecycle repair set is approval-gated as ONE
    # plan. Bare recovery DETECTS it (so the operator sees the complete set and
    # its content-addressed id) but never half-commits: applying the phase or
    # adoption repairs alone would expose the next defect on the next run, the
    # exact repair-one-field-then-rerun loop this contract removes.
    lifecycle_repairs = lifecycle_candidates if approved_repair_id is not None else []
    attest_ids = sorted(r["ticket"] for r in adoption_repairs if r.get("refuse"))
    approval_needed = lifecycle_candidates if approved_repair_id is None else []
    repair_id = _plan_repair_id(
        board_drifts, state_repairs, lifecycle_all, attest_ids
    )
    if approved_repair_id is not None:
        # SRC-043: approval binds to the WHOLE plan. A recomputed surface that no
        # longer matches the approved digest is a stale plan -- refused, never
        # applied against bytes the operator never saw.
        if approved_repair_id != repair_id:
            return {
                "ok": False,
                "code": "STALE_APPROVED_REPAIR",
                "detail": (
                    "the approved repair id does not match the current bounded "
                    f"repair set (approved {approved_repair_id!r}, current "
                    f"{repair_id!r}); re-run `saipen recover` and approve the new plan"
                ),
                "repair_id": repair_id,
                "changed": {"board": board_drifts, "state": state_repairs},
                "strict_state_error": strict_state_error or None,
                "dry_run": dry_run,
            }
        if attest_ids:
            # Approval authorizes the PLAN, so every legacy record the plan
            # named is adopted in the SAME bounded set -- no second round trip.
            adoption_repairs = _board_adoption_repairs(
                _board, docs.get("_history"), tuple(attest_ids)
            )
    operator_authorized = [r for r in state_repairs if r.get("operator_authorized")]
    if resolve_blocker and not operator_authorized:
        # The verb owns ONLY an ACTIVE-phase gated STATE.blocker. A phase BLOCKED
        # or out-of-enum phase is not this verb's business -- refuse rather than
        # certify CLEAN over a field the operator asked to clear and did not.
        blocker_text = state.get("blocker")
        blocker_present = (
            isinstance(blocker_text, str)
            and blocker_text.strip()
            and blocker_text.strip().lower() != "none"
        )
        if blocker_present:
            return {
                "ok": False,
                "code": "RECONCILE_REAUTH_REQUIRED",
                "detail": (
                    f"recover resolve-blocker owns only an ACTIVE-phase gated "
                    f"STATE.blocker; phase {state.get('phase')!r} carries "
                    f"{blocker_text!r} which this verb does not own -- transition "
                    "out of BLOCKED / repair the phase first (OPERATOR_DECISION_REQUIRED)"
                ),
                "changed": {"board": [], "state": state_repairs},
                "refused": [{"field": "blocker", "refuse": True, "reason": "phase-not-active"}],
                "strict_state_error": strict_state_error or None,
                "dry_run": dry_run,
                **_blocked_recovery_fields(
                    terminal_disposition="RECOVERY_BLOCKED",
                    evidence_reference=".saipen/STATE.md",
                    reason_code="RECONCILE_REAUTH_REQUIRED",
                ),
            }
    # T-1318: a phase repair with no provable replacement is NOT drift and NOT a
    # valve. It refuses as its own class, before any plan is built, so the run
    # cannot fall through to CLEAN over a state it cannot legally write.
    blocked_repairs = [r for r in state_repairs if r.get("blocked")]
    if blocked_repairs:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": "; ".join(f"{r['field']}: {r['reason']}" for r in blocked_repairs),
            "changed": {"board": [], "state": state_repairs},
            "blocked": blocked_repairs,
            "strict_state_error": strict_state_error or None,
            "dry_run": dry_run,
            **_blocked_recovery_fields(
                blocked_repairs,
                evidence_reference=".saipen/STATE.md",
                reason_code="RECOVERY_BLOCKED",
            ),
        }
    refused_repairs = [r for r in state_repairs if r.get("refuse")]
    if refused_repairs:
        # CORE-001: an at/over-cap counter while canonical history is lower
        # cannot be CLEANed and cannot be auto-repaired. Surface the refusal
        # explicitly so the run cannot pretend the valve was never tripped.
        return {
            "ok": False,
            "code": "RECONCILE_REAUTH_REQUIRED",
            "detail": "; ".join(
                f"{r['field']} {r['from']!r}->{r['to']!r} ({r['reason']})"
                for r in refused_repairs
            ),
            "changed": {"board": [], "state": state_repairs},
            "refused": refused_repairs,
            "strict_state_error": strict_state_error or None,
            "dry_run": dry_run,
            **_blocked_recovery_fields(
                refused_repairs,
                evidence_reference=".saipen/STATE.md",
                reason_code="RECONCILE_REAUTH_REQUIRED",
            ),
        }
    if approval_needed and approved_repair_id is None:
        # One approval authorizes the whole plan. Bare recover never reopens a
        # phantom DONE silently; it names the exact trusted command instead.
        return {
            "ok": False,
            "code": "RECONCILE_REAUTH_REQUIRED",
            "detail": "; ".join(r["reason"] for r in approval_needed),
            "changed": {
                "board": board_drifts,
                "state": state_repairs,
                "lifecycle": lifecycle_candidates,
                "lifecycle_refused": lifecycle_refusals,
            },
            "refused": approval_needed + lifecycle_refusals,
            "repair_id": repair_id,
            "strict_state_error": strict_state_error or None,
            "dry_run": dry_run,
            **_blocked_recovery_fields(
                approval_needed,
                command=f"saipen recover --apply-approved-repair {repair_id}",
                evidence_reference=".saipen/BOARD.md",
                reason_code="RECONCILE_REAUTH_REQUIRED",
            ),
        }
    if lifecycle_refusals:
        # LEGACY COMPATIBILITY BOUNDARY. A `## DONE` record older than this
        # project's closure contract, with no execution evidence in either
        # generation's grammar, is genuinely ambiguous. Reopening it would
        # destroy history on the strength of a field that did not exist when it
        # was written, so it stops here as an operator decision with an exact
        # command -- never as a deterministic repair atom.
        review_ids = sorted(r["ticket"] for r in lifecycle_refusals)
        return {
            "ok": False,
            "code": "RECONCILE_REAUTH_REQUIRED",
            "detail": "; ".join(r["reason"] for r in lifecycle_refusals),
            "changed": {
                "board": [],
                "state": state_repairs,
                "lifecycle_refused": lifecycle_refusals,
            },
            "refused": lifecycle_refusals,
            "repair_id": repair_id,
            "strict_state_error": strict_state_error or None,
            "dry_run": dry_run,
            **_blocked_recovery_fields(
                lifecycle_refusals,
                command=(
                    "saipen recover --attest-legacy-done " + ",".join(review_ids)
                ),
                evidence_reference=".saipen/BOARD.md",
                reason_code="RECONCILE_REAUTH_REQUIRED",
            ),
        }
    adoption_refusals = [r for r in adoption_repairs if r.get("refuse")]
    if adoption_refusals:
        # Target E: an unattested workable BOARD record whose provenance the
        # engine cannot prove refuses as an explicit operator decision -- never
        # silently auto-adopted, never auto-deleted, never laundered.
        adoption_ids = sorted(r["ticket"] for r in adoption_refusals)
        return {
            "ok": False,
            "code": "RECONCILE_REAUTH_REQUIRED",
            "detail": "; ".join(r["reason"] for r in adoption_refusals),
            "changed": {"board": [], "state": state_repairs, "adoption": adoption_repairs},
            "refused": adoption_refusals,
            "repair_id": repair_id,
            "strict_state_error": strict_state_error or None,
            "dry_run": dry_run,
            **_blocked_recovery_fields(
                adoption_refusals,
                command=(
                    "saipen recover --adopt-legacy " + ",".join(adoption_ids)
                ),
                evidence_reference=".saipen/LOG.md",
                reason_code="RECONCILE_REAUTH_REQUIRED",
            ),
        }
    adoptions = [r for r in adoption_repairs if r.get("kind") == "adopt"]
    if not (
        board_drifts
        or state_repairs
        or adoptions
        or lifecycle_repairs
        or lifecycle_attestations
    ):
        # Nothing the reconciliation owns differs. A STATE that is still red by
        # the strict contract is then NOT drift -- it is damage this operation
        # does not own, and certifying CLEAN over it would be the exact lie
        # CORE-002 exists to kill.
        if strict_state_error:
            return {
                "ok": False,
                "code": "VALIDATION_FAILED",
                "detail": f"state-malformed: {strict_state_error}",
                "changed": {"board": [], "state": []},
                "strict_state_error": strict_state_error or None,
                "dry_run": dry_run,
                **_blocked_recovery_fields(
                    terminal_disposition="RECOVERY_BLOCKED",
                    evidence_reference=".saipen/STATE.md",
                    reason_code="PROTOCOL_STATE_INVALID",
                ),
            }
        return _ensure_audit_contract(
            {
                "ok": True,
                "code": "CLEAN",
                "changed": [],
                "strict_state_error": None,
                "dry_run": dry_run,
            },
            project_root,
        )

    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%d.%m.%y %H:%M")
    utc = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    op_id = "reconcile-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S%f")
    # The DEC names the DRIFT that was detected -- `last_event 2->1` means
    # "STATE claimed 2, the LOG tail is 1". The value actually persisted is the
    # tail AFTER this trace is appended, because the repair's own DEC is then
    # the newest event; the drift it reports is the one it was asked to fix.
    description = "reconcile protocol state -- " + _repair_summary(board_drifts, state_repairs)
    if operator_authorized:
        description += (
            f"; operator-authorized STATE.blocker clear: {resolve_blocker.strip()!r}"
        )
        for _repair in operator_authorized:
            if _repair.get("follow_up"):
                description += f"; follow-up: {_repair['follow_up']}"
    if adoptions:
        description += "; adopt legacy " + ", ".join(r["ticket"] for r in adoptions)
    if lifecycle_attestations:
        description += "; attest legacy completion " + ", ".join(
            r["ticket"] for r in lifecycle_attestations
        )
    if lifecycle_repairs:
        description += "; board lifecycle " + ", ".join(
            f"{r['ticket']}:{r.get('kind')}"
            + (f"->{r['to_section']}" if r.get("to_section") else "")
            for r in lifecycle_repairs
        )
    new_log = docs["log"].text_norm.rstrip("\n") + "\n"
    tail = log_tail
    for adoption in adoptions:
        _adopt_tid = adoption["ticket"]
        tail, adoption_line = _event_line(
            docs,
            tail,
            "DEC",
            _adopt_tid,
            agent,
            f"LEGACY_ADOPTED {_adopt_tid} -- no canonical allocation event is "
            "available in the complete history; adopted now by explicit operator "
            "decision, original ticket id/title/bytes preserved, no historical "
            "allocation or actor fabricated (Target E)",
            stamp,
            op_id,
            # T-1326 P0: a variable-length DEC (the operator decision, the drift
            # summary, an adoption rationale) must go through the canonical
            # lossless path. Without `root` the raw `build_event` raises
            # `LOG_EVENT_OVERSIZE`, so the ONLY sanctioned recovery verb would
            # crash on the very brake it exists to clear.
            root=project_root,
        )
        new_log += adoption_line + "\n"
    for attestation in lifecycle_attestations:
        _att_tid = attestation["ticket"]
        tail, attest_line = _event_line(
            docs,
            tail,
            "DEC",
            _att_tid,
            agent,
            legacy_done_attestation_text(_att_tid),
            stamp,
            op_id,
            root=project_root,
        )
        new_log += attest_line + "\n"
    event, line = _event_line(
        docs, tail, "DEC", None, agent, description, stamp, op_id, root=project_root
    )
    new_log += line + "\n"
    new_board = _apply_checkbox_repairs(board_text, board_drifts) if board_drifts else board_text
    if lifecycle_repairs:
        new_board = _apply_lifecycle_repairs(new_board, lifecycle_repairs)

    from .state import patch_state, remove_state_fields

    remove_fields = [repair["field"] for repair in state_repairs if repair.get("remove")]
    owned = {
        repair["field"]: repair["to"]
        for repair in state_repairs
        if not repair.get("remove")
    }
    owned["last_event"] = event
    owned["updated"] = utc
    owned["agent"] = agent
    try:
        new_state = patch_state(state_text, owned)
        if remove_fields:
            new_state = remove_state_fields(new_state, remove_fields)
    except ValueError as exc:
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": str(exc)}

    # ONE complete-surface validation of the PROPOSAL -- the same invariants the
    # post-write gate runs. A proposal that cannot pass is never committed, and
    # a surface that cannot be made clean is reported rather than certified.
    errors = validate_texts(
        new_state,
        new_board,
        new_log,
        current_agent=agent,
        sealed_events=docs.get("_history"),
    )
    if errors:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": "proposed reconciliation fails fast validation: " + "; ".join(errors[:5]),
            "changed": {"board": board_drifts, "state": state_repairs},
            "strict_state_error": strict_state_error or None,
            "dry_run": dry_run,
        }

    # T-1326 P0: the ONE canonical LOG target set. Every artifact `prepare_event`
    # produced for an oversized DEC -- here, the operator's resolve-blocker
    # decision and each legacy-adoption rationale -- joins the SAME journaled
    # commit as LOG/STATE/BOARD/evidence. Omitting them would commit a
    # `detail_ref` that names bytes the transaction never wrote: a lossless
    # claim over an absent authority.
    targets = [
        *_log_targets(docs, new_log),
    ]
    if board_drifts or lifecycle_repairs:
        targets.append(_target(docs["board"], ".saipen/BOARD.md", "board", new_board))
    targets.append(_target(docs["state"], ".saipen/STATE.md", "state", new_state))

    preconditions = _docs_preconditions(docs, "state", "board", "log")
    # T-1318 A6: an EXCEPTIONAL repair of the phase is the one mutation whose
    # subject may not exist in any predictable earlier form, so the exact
    # pre-repair bytes are preserved before they are replaced. T-1322 extends the
    # same guarantee to a legacy output-field MIGRATION (the original STATE bytes
    # are archived before the exact field is removed). The artifact path is
    # deterministic (op_id carries microseconds) and the plan declares it
    # MISSING, so a replay of the same operation can never overwrite a copy, and
    # nothing ever edits the copy afterwards.
    phase_field_repairs = [
        repair for repair in state_repairs if repair["field"] in ("phase", "transition_from")
    ]
    blocker_repairs = [repair for repair in state_repairs if repair["field"] == "blocker"]
    next_action_repairs = [
        repair for repair in state_repairs if repair["field"] == "next_action"
    ]
    removal_repairs = [repair for repair in state_repairs if repair.get("remove")]
    preserved_path = None
    if phase_field_repairs or removal_repairs or blocker_repairs or next_action_repairs:
        from .journal import hash_bytes, owned_target_path
        from .plan import TargetPlan

        original = (project_root / ".saipen" / "STATE.md").read_bytes()
        subdir = "state-phase" if phase_field_repairs else "state-legacy-output"
        preserved_rel = f".saipen/recovery/{subdir}/{op_id}.STATE.md"
        owned_target_path(project_root, preserved_rel, kind="state recovery evidence")
        # The journal's OWN convention for a file that must not exist yet: the
        # empty before-hash. `_target_bytes` in controls.py uses exactly this
        # for created artifacts, and the dependency channel is for READ-ONLY
        # dependencies -- a created target declares its own precondition.
        targets.append(
            TargetPlan(preserved_rel, "generic", original, "", hash_bytes(original))
        )
        preserved_path = preserved_rel

    plan = build_plan(
        "reconcile",
        agent,
        _identity(project_root),
        {
            "operation": "reconcile",
            "board_drifts": len(board_drifts),
            "state_repairs": [repair["field"] for repair in state_repairs],
            "adopted": [repair["ticket"] for repair in adoptions],
            "lifecycle": [repair["ticket"] for repair in lifecycle_repairs],
            "repair_id": repair_id,
            "event": event,
            "preserved_state": preserved_path,
        },
        preconditions,
        targets,
        {"ok": True, "code": "REPAIRED", "event_id": f"E-{event}"},
        op_id=op_id,
    )

    if dry_run:
        return {
            "ok": True,
            "code": "REPAIR_REQUIRED",
            "changed": {"board": board_drifts, "state": state_repairs},
            "adopted": [repair["ticket"] for repair in adoptions],
            "lifecycle": lifecycle_repairs,
            "repair_id": repair_id,
            "targets": [target.path for target in targets],
            "planned_event": f"E-{event}",
            "detail": description,
            "strict_state_error": strict_state_error or None,
            "dry_run": True,
        }

    applied = apply_plan(project_root, plan)
    if not applied.get("ok"):
        return {
            "ok": False,
            "code": applied.get("code", "VALIDATION_FAILED"),
            "detail": applied.get("message", ""),
            "changed": {"board": board_drifts, "state": state_repairs},
            "dry_run": False,
        }
    return _ensure_audit_contract(
        {
            "ok": True,
            "code": "REPAIRED",
            "changed": {"board": board_drifts, "state": state_repairs},
            "adopted": [repair["ticket"] for repair in adoptions],
            "lifecycle": lifecycle_repairs,
            "repair_id": repair_id,
            "targets": [target.path for target in targets],
            "event": f"E-{event}",
            "agent": agent,
            "strict_state_error": strict_state_error or None,
            "dry_run": False,
        },
        project_root,
    )
