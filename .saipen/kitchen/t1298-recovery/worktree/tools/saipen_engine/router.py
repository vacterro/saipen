"""Shared deterministic next-action router (NITRO dogfood II, T-590).

One pure function implements the deterministic parts of CORE section 1.11's
action priority -- RECOVER > UNBLOCK > FINISH > START > MAINTAIN -- from a
parsed STATE + BOARD + recovery state. `saipen status`, `saipen next` and the
context compiler all consume THIS router, never separate routing logic.

It deliberately does NOT decide semantic architecture questions (whether a
transition deserves REVIEW, whether a goal is satisfied); it computes the
exact next EXECUTABLE mechanical action the state demands.
"""

from __future__ import annotations

from pathlib import Path

from . import phases
from .board import parse_board, ticket_is_workable, claim_status, board_graph_errors
from .result import Result
from .state import binding_wait


def _top_workable(board: dict, agent: str | None = None) -> str | None:
    """Deterministic Pick Rule: topmost TODO ticket whose needs are all DONE
    and which no other agent holds under a live claim."""
    tickets = board["tickets"]
    for ticket in tickets.values():
        if ticket_is_workable(ticket, tickets, agent=agent):
            return ticket["id"]
    return None


def route_next(
    state_text: str,
    board_text: str,
    pending_ops: list | None = None,
    conflict_ops: list | None = None,
    now: datetime.datetime | None = None,  # noqa: F821
    current_capability: str | None = None,
    current_agent: str | None = None,
    snap=None,
    audit_inbox: dict | None = None,
    # PERF-004: optional pre-parsed objects from the caller to avoid
    # redundant STATE/BOARD parsing. When provided, these take precedence
    # over parsing state_text/board_text.
    _state: dict | None = None,
    _board: dict | None = None,
    _state_error: str | None = None,
) -> dict:
    """Compute the exact next executable action.

    Returns a dict with `action` (an executable mechanical action), `reason`
    (which priority rule fired), and optional `ticket`/`detail`. Never echoes
    STATE.next_action -- it is a projection, not a mirror (NITRO dogfood II).
    `now` (UTC) drives § 1.4 claim-liveness for the active-ticket binding; tests
    inject a fixed instant (P0 claim-ownership truth).

    `current_capability` is the FRESHLY NEGOTIATED session capability
    ("full"/"read-only"/...), supplied by the caller. CORE § 1.3: a persisted
    `STATE.mode` is only the LAST handshake outcome and MUST NOT prove current
    authority, so routing never infers write authority from STATE.mode -- it
    gates only on an explicit current-capability value when one is supplied.

    `current_agent` is the canonical acting identity (T-1006): the ONE
    resolver in tools/saipen.py INHERITS persisted STATE.agent for a bare CLI
    and journals an explicit old -> new DEC for a genuine `--agent` handover.
    Claim truth and workability are judged relative to THAT value, never by
    reading STATE.agent a second time here -- a genuinely different actor B
    entering state last written by A must see A's live claim as FOREIGN_LIVE
    and refuse takeover, not impersonate A. When `current_agent` is None (a
    caller that does not know its own identity), routing falls back to the
    historical value for backward compatibility of pure-semantic callers,
    but the CLI/adapters always supply the resolved identity.

    `audit_inbox` is the Audit Inbox's READ-ONLY structural projection
    (`audit_inbox.projection`), supplied by the caller because this function
    stays pure -- it never touches the filesystem. `SOURCE-AUDIT-INBOX-01`
    places it AFTER recovery / WAIT / active continuation and BEFORE the
    ordinary BOARD Pick Rule: a fresh external audit usually corrects current
    project truth and must not sit unseen behind a stale backlog, but it never
    preempts a legitimately active ticket mid-transaction.
    """
    pending = list(pending_ops or [])
    conflicts = list(conflict_ops or [])
    # PERF-004: parse STATE/BOARD ONCE and reuse the result for both the
    # checkpoint-surface validation and the routing logic below. When the
    # caller provides pre-parsed objects, skip parsing entirely.
    from .state import parse_state_or_error

    if _state is not None and _board is not None:
        # PERF-004: the pre-parsed seam. `_state_error` may be None -- the
        # NORMAL "no parse error" case -- so it is NOT part of the guard; a
        # clean pre-parsed call must not silently fall through to re-parsing.
        state, state_error, board = _state, _state_error, _board
    else:
        state, state_error = parse_state_or_error(state_text)
        board = parse_board(board_text)
    if snap is not None:
        from .fast_check import validate_checkpoint_surface

        errors = validate_checkpoint_surface(
            state_text,
            board_text,
            snap,
            current_agent=current_agent,
            _state=state,
            _board=board,
            _state_error=state_error,
        )
        if errors:
            return {
                "ok": False,
                "action": "saipen status",
                "reason": "checkpoint-invalid",
                "detail": "checkpoint invalid: " + "; ".join(errors[:3]),
            }
    # A STATE the shared parser cannot read whole is not a routing surface:
    # duplicate keys or a broken fence must never project an executable next
    # action from a partial parse (T-1003 hostile findings). Fail closed.
    if state_error:
        return {
            "ok": False,
            "action": "saipen status",
            "reason": "state-malformed",
            "detail": f"STATE parse error: {state_error}",
        }
    # Empty STATE is bootstrap-only (hostile-regression, P1): a file with no
    # frontmatter reads as {} for status display, but it is NOT a routing
    # surface -- there is no phase, no agent, no continuation to project.
    # Only a fresh bootstrap may sit here, and the routed action for a
    # bootstrap is the INIT entry, never an ordinary maintenance/start
    # projection.
    if not state:
        return {
            "ok": True,
            "action": "saipen status",
            "reason": "bootstrap",
            "executable_behavior": "RESTATE_AND_STOP",
            "detail": "empty STATE is bootstrap-only; no continuation "
            "exists yet -- bootstrap via INIT before routing",
        }
    phase = state.get("phase")
    task = state.get("task")
    na = state.get("next_action") or ""

    # Second-wave P0: the CURRENT-SESSION actor, never STATE.agent. STATE.agent
    # is historical last-writer evidence; claim truth and workability are judged
    # relative to the identity the caller actually IS.
    session_agent = current_agent if current_agent is not None else state.get("agent")

    # CURRENT-SESSION CAPABILITY gate (CORE § 1.3): only an explicitly supplied,
    # freshly negotiated capability may grant/revoke write authority. A persisted
    # STATE.mode is the LAST handshake outcome and is NEVER used to infer current
    # authority (a stale read-only must not suppress a newly writable session,
    # nor a stale full route mutation into a newly read-only one). Callers that
    # do not pass current_capability get pure state-semantic routing.
    #
    # A capability that was supplied but is not one of the four closed values is
    # a broken handshake, never permission: fail closed rather than route as if
    # the session were writable.
    if current_capability is not None:
        from .capability import capability_error

        _cap_problem = capability_error(current_capability)
        if _cap_problem is not None:
            return {
                "ok": False,
                "action": "saipen status",
                "reason": "capability-invalid",
                "detail": _cap_problem,
            }
    if current_capability == "read-only":
        return {
            "ok": True,
            "action": "saipen status",
            "reason": "read-only-mode",
            "executable_behavior": "RESTATE_AND_STOP",
            "detail": "current session capability is read-only; no mutating "
            "next action may be routed -- inspect only",
        }

    # RECOVER outranks everything (after the read-only brake): an unresolved
    # op or conflict must be resolved before any canonical work.
    if conflicts:
        return {
            "ok": False,
            "action": "saipen recover",
            "reason": "recovery-conflict",
            "detail": f"unresolved conflict: {', '.join(conflicts)}",
        }
    if pending:
        return {
            "ok": False,
            "action": "saipen recover",
            "reason": "recovery-pending",
            "detail": f"unresolved operation: {', '.join(pending)}",
        }

    # A board the shared parser cannot read whole (an unrecognized ticket
    # field, a malformed ticket line, a missing heading) is not a work
    # surface: a typo'd `| blockr:` is exactly how a blocker-bearing ticket
    # launders itself into workable, so malformed input must FAIL the route
    # (ok: false, VALIDATION_FAILED) -- never a successful projection from
    # corrupt input. status/next/context propagate the failure; the parser
    # diagnostics stay in `detail` and recovery flags stay truthful.
    if board["errors"]:
        return {
            "ok": False,
            "action": "saipen status",
            "reason": "board-malformed",
            "detail": "BOARD parse error(s): " + "; ".join(board["errors"][:3]),
        }

    doing = [t for t in board["tickets"].values() if t["section"] == "## DOING"]
    active = doing[0]["id"] if doing else None

    # BINDING (hostile-regression, P0): STATE.task binds BOARD.DOING only where
    # this agent actually OWNS or ADOPTS the active ticket. The ONE
    # claim_status classifier decides: a runtime-fresh FOREIGN_LIVE or INVALID
    # claim changes the rule.
    #   - INVALID (half owner/claim_time pair, non-UTC stamp): fail closed.
    #   - FOREIGN_LIVE: another agent is actively working it; a foreign-owned
    #     DOING with observer STATE.task:none is VALID multi-agent state and
    #     routes NON-MUTATING (observe, do not take over).
    #   - SELF (this agent owns it): binding is mandatory; task:none fails.
    #   - UNCLAIMED / FOREIGN_STALE: adoptable orphan/stale DOING; task:none is
    #     fine and routes to ADOPT it.
    if active:
        cs = claim_status(board["tickets"][active], session_agent, now)
        if cs == "INVALID":
            return {
                "ok": False,
                "action": "saipen status",
                "reason": "binding-mismatch",
                "detail": f"BOARD.DOING {active} carries an INVALID claim "
                f"(half owner/claim_time pair or non-UTC stamp); "
                f"repair the claim before routing",
            }
        if cs == "FOREIGN_LIVE":
            if task and task != "none":
                return {
                    "ok": False,
                    "action": "saipen status",
                    "reason": "binding-mismatch",
                    "detail": f"STATE.task={task} but BOARD.DOING={active} "
                    f"is FOREIGN_LIVE (owned by another agent)",
                }
            return {
                "ok": True,
                "action": "saipen status",
                "reason": "foreign-live",
                "executable_behavior": "RESTATE_AND_STOP",
                "detail": f"BOARD.DOING {active} is actively owned by "
                f"another agent; observe, do not take over",
            }
        if task and task != "none" and task != active:
            return {
                "ok": False,
                "action": "saipen status",
                "reason": "binding-mismatch",
                "detail": f"STATE.task={task} but BOARD.DOING={active}; "
                "repair the split before routing",
            }
        if cs == "SELF" and (not task or task == "none"):
            return {
                "ok": False,
                "action": "saipen status",
                "reason": "binding-mismatch",
                "detail": f"STATE.task is none but BOARD.DOING={active} is "
                f"this agent's own SELF claim; bind STATE.task",
            }
        if cs in ("UNCLAIMED", "FOREIGN_STALE") and (not task or task == "none"):
            # Adoptable orphan/stale DOING: route to claim it in place.
            return {
                "ok": True,
                "action": f"PHASE SCOUT {active}",
                "reason": "adopt",
                "ticket": active,
                "detail": "DOING ticket carries no live own claim; adopt it",
                "load": load_for_action(f"PHASE SCOUT {active}"),
            }
    elif task and task != "none":
        return {
            "ok": False,
            "action": "saipen status",
            "reason": "binding-mismatch",
            "detail": f"STATE.task={task} but no BOARD.DOING ticket; "
            "repair the split before routing",
        }

    # WAIT: a legitimate persisted WAIT is a HARD STOP (CORE 1.11 OBEY/UNBLOCK
    # priority). It must never be walked through merely because TODO has
    # workable tickets. The narrow exception is exactly CORE's: DONE + empty
    # TODO + a WAIT that is not one of the explicitly legal DONE brakes may
    # route onward -- a genuine user brake remains a stop with 100 workable
    # tickets.
    if na.startswith("WAIT:"):
        # THE contextual brake classifier (hostile-regression, P1#5). A WAIT
        # that `binding_wait` recognizes is a HARD STOP (RESTATE_AND_STOP); one
        # it does not bind in this exact context may route onward. Outside
        # DONE+empty-TODO every legal WAIT binds (a user brake is a stop with
        # one hundred workable tickets). At DONE+empty-TODO only the three
        # fixed § 1.2 brakes bind; any other legal WAIT there is a question
        # about work in flight that does not exist, so CORE's UNBLOCK exception
        # routes it to documented repair rather than a stop. A malformed WAIT
        # never reaches here: parse_state_or_error already refused it.
        _empty_todo = not any(t["section"] == "## TODO" for t in board["tickets"].values())
        _brake = binding_wait(
            na, phase=phase, empty_todo=_empty_todo, intent=state.get("execution_intent")
        )
        if _brake:
            # CORE-004: the safety valve is an AUTHORIZATION boundary, not a
            # resumable yield. Once the 3-wave / 20-ticket budget is exhausted,
            # the persisted WAIT is a HARD STOP (RESTATE_AND_STOP) until the
            # documented re-authorization operation durably resets the counters.
            # A resumed automated run MUST NOT continue merely because TODO/DOING
            # work remains -- the prior 'valve-yield' branch let it, defeating
            # the runaway-work protection on long-running goal loops.
            return {
                "ok": True,
                "action": na,
                "reason": "wait",
                "executable_behavior": "RESTATE_AND_STOP",
                "detail": "persisted WAIT is a hard stop; do not route past it",
            }

    # BLOCKED phase: a hard stop, whatever the board holds. UNBLOCK is a
    # routing-priority NAME (CORE 1.11), not necessarily a `ticket unblock`
    # command -- the router must not emit a mutation the executor refuses.
    if phase == "BLOCKED":
        return {
            "ok": True,
            "action": "saipen status",
            "reason": "unblock",
            "executable_behavior": "RESTATE_AND_STOP",
            "detail": "phase BLOCKED; resolve the blocker before any "
            "further work (saipen sub list / status to inspect)",
        }

    # FINISH: phase in a ticket-bearing phase with an active ticket -> the
    # persisted next_action names the exact phase work; fall back to the
    # persisted value only when it is still a legal PHASE action for the
    # active ticket.
    if active and phase in phases.TICKET_BEARING_PHASES:
        if na.startswith("PHASE ") and task and task == active:
            return {
                "ok": True,
                "action": na,
                "reason": "finish",
                "ticket": active,
                "load": load_for_action(na),
            }
        if na.startswith(("RUN:", "RESUME:")) and task == active:
            return {
                "ok": True,
                "action": na,
                "reason": "finish",
                "ticket": active,
                "load": load_for_action(na),
            }
        return {
            "ok": True,
            "action": f"PHASE {phase} {active}",
            "reason": "finish",
            "ticket": active,
            "load": load_for_action(f"PHASE {phase} {active}"),
        }

    # Phase-owned partial continuation (T-1011): an UNFINISHED MARKHUNT pass
    # owns the next action even under an outer converge/crew target.
    # `phases/markhunt.md` makes `next_action: "saipen markhunt"` the resume
    # marker of a partial pass (manifest cursor: partial) -- routing must
    # continue THAT sweep until its manifest closes, never exit the audit
    # campaign to crew while findings are still being recorded. The persisted
    # crew intent is left untouched and resumes after MARKHUNT legitimately
    # closes (the crew branch below then owns continuation again).
    if phase == "MARKHUNT" and na.startswith("saipen markhunt"):
        return {
            "ok": True,
            "action": na,
            "reason": "markhunt-continue",
            "load": load_for_action(na),
            "detail": "partial MARKHUNT pass owns continuation until its manifest closes",
        }

    # Crew is an outer convergence target. Once local ticket execution has no
    # immediate continuation, ordinary `cc` returns to crew orchestration from
    # persisted semantics rather than relying on a lucky next_action string.
    if state.get("execution_intent") == "converge" and state.get("converge_target") == "crew":
        return {
            "ok": True,
            "action": "saipen crew",
            "reason": "crew-converge",
            "detail": "active crew target owns continuation",
        }

    # AUDIT INBOX (SOURCE-AUDIT-INBOX-01): an unconsumed external audit layer
    # outranks SELECTION of unrelated queued TODO. It sits here on purpose --
    # every active-continuation branch above has already returned, so a fresh
    # file can never steal ownership from a live BUILD/VERIFY/REVIEW
    # transaction; it only wins the START decision that has not been made yet.
    # `invalid_only` and `residue_only` are NOT routed here: an unreadable
    # layer and an uncaptured leftover are diagnostics that must not outrank
    # real workable BOARD Work (both are surfaced below, before the project
    # can call itself idle).
    if not active and audit_inbox and audit_inbox.get("action"):
        # BOARD policy stays HERE, not in the inbox module: the inbox answers
        # structurally ("this layer's Work owns continuation"), and the router
        # is the only place that knows whether that ticket is workable. An
        # audit whose Work is blocked or claimed elsewhere must fall through to
        # the ordinary Pick Rule instead of routing to a ticket the executor
        # would refuse.
        _audit_work = audit_inbox.get("work")
        _audit_blocked = bool(
            _audit_work
            and str(audit_inbox.get("action", "")).startswith("PHASE ")
            and not ticket_is_workable(
                board["tickets"].get(_audit_work, {}), board["tickets"], agent=session_agent
            )
        )
        if (
            not audit_inbox.get("invalid_only")
            and not audit_inbox.get("residue_only")
            and not _audit_blocked
        ):
            routed_audit = {
                "ok": True,
                "action": audit_inbox["action"],
                "reason": "audit-inbox",
                "detail": audit_inbox.get("detail", "audit inbox owns continuation"),
                "audit_layer": audit_inbox.get("layer"),
                "audit_path": audit_inbox.get("path"),
                "load": load_for_action(audit_inbox["action"]),
            }
            if audit_inbox.get("work"):
                routed_audit["ticket"] = audit_inbox["work"]
            return routed_audit

    # START: no DOING + a workable TODO -> Pick Rule claims the top ticket.
    if not active:
        top = _top_workable(board, agent=session_agent)
        if top is not None:
            return {
                "ok": True,
                "action": f"PHASE SCOUT {top}",
                "reason": "start",
                "ticket": top,
                "detail": "topmost workable ticket",
                "load": load_for_action(f"PHASE SCOUT {top}"),
            }
        # A cyclic or dangling `needs:` graph with NOTHING workable is corrupt
        # work state, not "no work left" (4th-wave P1#4): routing to
        # maintenance / `saipen continue` there hides the damage behind a
        # healthy-looking action. The gate sits HERE, after the Pick Rule, on
        # purpose: CORE § 1.2's remedy for a cycle or a dangling reference is to
        # block that ticket and KEEP WORKING the other tickets, so a broken edge
        # must never suppress a genuinely workable one.
        _graph_errors = board_graph_errors(board["tickets"])
        if _graph_errors:
            return {
                "ok": False,
                "action": "saipen status",
                "reason": "board-graph-invalid",
                "detail": "BOARD needs: graph invalid with no workable "
                "ticket: " + "; ".join(_graph_errors[:3]),
            }

    # A deliberately unreadable audit layer is NOT an idle project. Nothing
    # workable remains at this point, so surfacing the invalid inbox here --
    # before any maintenance/Improve verdict -- is the difference between
    # "your audit file is broken" and a silent "nothing to do".
    if audit_inbox and audit_inbox.get("invalid_only"):
        return {
            "ok": True,
            "action": audit_inbox.get("action", "saipen audit status"),
            "reason": "audit-inbox-invalid",
            "executable_behavior": "RESTATE_AND_STOP",
            "detail": audit_inbox.get(
                "detail", "audit inbox holds only invalid layer(s); it is not idle"
            ),
        }

    # Every layer settled, but `audit/` still holds bytes SAIPEN never
    # captured. The work is genuinely finished, so this is not a failure and
    # never a refusal -- it is the difference between "the audit is closed"
    # and "the audit directory is clean", which are not the same claim.
    if audit_inbox and audit_inbox.get("residue_only"):
        return {
            "ok": True,
            "action": audit_inbox.get("action", "saipen audit status"),
            "reason": "audit-inbox-residue",
            "executable_behavior": "RESTATE_AND_STOP",
            "detail": audit_inbox.get(
                "detail", "audit inbox is settled but the directory is not clean"
            ),
        }

    # MAINTAIN: fall through to the persisted next_action only when it is a
    # legal non-ticket action (saipen continue / saipen <verb>), never a stale
    # PHASE echo and never a WAIT -- a WAIT reaching here already failed the
    # hard-stop gate above (the narrow DONE+empty-TODO exception), so it is a
    # stale WAIT to route past, not a brake to restate.
    if na.startswith("saipen ") or na.startswith("RUN:"):
        return {"ok": True, "action": na, "reason": "maintain"}
    return {
        "ok": True,
        "action": "saipen continue",
        "reason": "maintain",
        "detail": "no pending recovery, no active ticket, no workable "
        "TODO; continue ordinary maintenance",
    }


ROUTING_FAILURE_CODES = {
    # Recovery conflicts/pending are recovery work: the project holds an
    # unresolved journal.
    "recovery-conflict": "RECOVERY_CONFLICT",
    "recovery-pending": "RECOVERY_REQUIRED",
    # Everything else is a malformed/binding failure: there is NO journal to
    # recover, so recovery_pending must be false and the refusal must be a
    # validation failure -- telling the agent to recover a non-existent op
    # would send it chasing ghosts (T-1003 hostile findings).
    "state-malformed": "VALIDATION_FAILED",
    "binding-mismatch": "VALIDATION_FAILED",
    "board-malformed": "VALIDATION_FAILED",
    "board-graph-invalid": "VALIDATION_FAILED",
    "checkpoint-invalid": "VALIDATION_FAILED",
    "capability-invalid": "VALIDATION_FAILED",
}


def routing_failure_code(out: dict) -> str:
    """The stable failure code for one route_next result."""
    return ROUTING_FAILURE_CODES.get(out.get("reason"), "VALIDATION_FAILED")


def audit_inbox_projection(project_root) -> dict | None:
    """The Audit Inbox's read-only routing projection, or None.

    The ONE seam between the pure router and the filesystem-backed inbox.
    Writes nothing. An unexpected failure does NOT fail open into "the project
    is idle": it degrades to an `invalid_only` projection so routing surfaces
    the inbox condition instead of letting Improve run over a live audit.
    """
    if project_root is None:
        return None
    try:
        from .audit_inbox import projection

        return projection(project_root)
    except Exception as exc:  # transport failure is a diagnostic, never idle
        return {
            "action": "saipen audit status",
            "invalid_only": True,
            "detail": f"audit inbox could not be classified ({type(exc).__name__}: {exc})",
            "pending": [],
            "closed_pending_delete": [],
            "invalid": [],
        }


def route_next_result(
    project_root,
    state_text: str,
    board_text: str,
    pending_ops_list: list | None = None,
    conflict_ops_list: list | None = None,
    snap=None,
) -> Result:
    """route_next wrapped in the stable Result shape for status/next/context."""
    out = route_next(
        state_text,
        board_text,
        pending_ops_list,
        conflict_ops_list,
        snap=snap,
        audit_inbox=audit_inbox_projection(project_root),
    )
    data = {k: v for k, v in out.items() if k != "ok"}
    # Capability surface (hostile-regression, P0#5): a PHASE action names the
    # phase doc it will load (saipen/phases/<phase>.md). A missing or empty
    # phase doc is a bogus checkpoint -- surface it as a routing failure so the
    # agent never boots from a phase that has no contract to execute.
    action = out.get("action")
    if out.get("ok") and isinstance(action, str) and action.startswith("PHASE "):
        load = load_for_action(action)
        if load:
            load_path = Path(project_root) / load
            if not load_path.is_file() or load_path.stat().st_size == 0:
                return Result(
                    ok=False,
                    code="VALIDATION_FAILED",
                    data={
                        "action": action,
                        "load": load,
                        "reason": "phase-doc-missing",
                        "detail": f"phase doc {load} is missing or empty",
                    },
                )
    # CORE-004: conformance health gate -- when routing to crew convergence,
    # verify that the canonical conformance evidence is healthy. Structural
    # corruption or failing conformance must route to VALIDATE/RECOVER
    # instead of normal crew work.
    if (
        out.get("ok")
        and out.get("action") == "saipen crew"
        and out.get("reason") == "crew-converge"
        and project_root is not None
    ):
        try:
            from .conformance import conformance_status, STATUS_CURRENT_PASS

            _cs = conformance_status(project_root, gate="core")
            if _cs.get("status") not in (STATUS_CURRENT_PASS, "NOT_RUN"):
                return Result(
                    ok=False,
                    code="CONFORMANCE_UNHEALTHY",
                    data={
                        "action": "saipen status",
                        "reason": "conformance-unhealthy",
                        "detail": (
                            f"crew convergence requires current conformance evidence, "
                            f"got {_cs['status']}: {_cs.get('reason', '')} -- "
                            "run 'saipen validate' before crew work"
                        ),
                        "conformance_status": _cs["status"],
                    },
                )
        except Exception as exc:
            # W2-007: fail closed when conformance cannot be positively
            # established. An import/read/decode or unexpected runtime
            # failure at the gate disables the gate and masks its root cause
            # if it falls through to ROUTED. Route toward validate/recover
            # instead of crew execution.
            return Result(
                ok=False,
                code="CONFORMANCE_UNKNOWN",
                data={
                    "action": "saipen status",
                    "reason": "conformance-unknown",
                    "detail": (
                        f"crew convergence could not establish conformance "
                        f"evidence ({type(exc).__name__}: {exc}); "
                        "run 'saipen validate' before crew work"
                    ),
                },
            )
    return Result(
        ok=bool(out.get("ok")),
        code=("ROUTED" if out.get("ok") else routing_failure_code(out)),
        data=data,
    )


def load_for_action(action: str) -> str | None:
    """The phase doc the ROUTED action needs, derived from the action itself
    (NITRO dogfood III, T-591): `next.action` and `next.load` can never
    disagree. For a PHASE <X> [T-###] action the doc is phases/<x>.md; a
    recovery/command/WAIT action carries no phase doc (the command/routing
    owner governs instead).
    """
    if not action or not action.startswith("PHASE "):
        return None
    parts = action.split()
    if len(parts) < 2:
        return None
    phase = parts[1].lower()
    return f"saipen/phases/{phase}.md"
