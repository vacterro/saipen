"""Reference outer-iteration controller (T-1619 finishing repair).

The mechanical HOST FLOW the real ZAICODE/SAIRoute iteration controller
ports natively::

    MODEL TURN RETURNS
        |
        v
    QUERY CANONICAL SAIPEN ITERATION VERDICT (``iteration_verdict``)
        |
        +--> VALID_TERMINAL --> allow goal-complete UI (once) + terminate goal
        +--> AUTO_KICK --> start next iteration automatically, Work preserved
        +--> OPERATOR_WAIT --> stop truthfully, no auto-kick
        +--> EXECUTOR_CAPABILITY_MISMATCH --> reroute, never a project blocker
        +--> RUNTIME_PAUSED --> preserve Work, report runtime unavailability,
                               never claim goal complete

A provider returning final text is only MODEL_TURN_FINISHED. It is never
sufficient evidence of SAIPEN_GOAL_FINISHED.

Pre-handoff admission runs on EVERY executor/tool-profile switch with no
capability inheritance: the current candidate's advertised tools are
normalized and admitted fresh, a mismatch is routing telemetry (rejected
candidate, missing set, next candidate), and exhaustion pauses at the
runtime level with canonical Work untouched.

Negative observations live for one capability/routing epoch. An epoch is a
stable routing/tool-configuration generation: advancing from candidate A to
candidate B inside the same attempt must NOT clear the negative set (that
loop would make SAIOPP eligible again immediately). ``reseat_epoch`` clears
only when the epoch fingerprint actually changes.

Session-local and pure of canonical writes: this controller never touches
STATE.md/BOARD.md/LOG.md. It records routing telemetry in memory for the
host to report.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping

from . import iteration
from .autonomy import ProgressTracker
from .iteration_verdict import (
    ITERATION_VERDICT_SCHEMA,
    admit_normalized,
    granted_capabilities,
    required_for_state,
    verdict_allows_goal_complete_ui,
)

#: Closed controller-action vocabulary returned by ``on_model_turn_finished``.
KICK_NEXT_ITERATION = "kick_next_iteration"
EMIT_GOAL_COMPLETE_UI = "emit_goal_complete_ui"
STOP_TRUTHFULLY = "stop_truthfully"
REROUTE_EXECUTOR = "reroute_executor"
REPORT_RUNTIME_PAUSED = "report_runtime_paused"
#: AUTO_KICK with a dispatch that never reached a host. Reconcile, do not
#: report that a turn was scheduled (CORE-012).
RECONCILE_DISPATCH = "reconcile_dispatch"

#: CORE-012 disposition vocabulary: the dispatch outcome decides the action.
DISPATCH_CONFIRMED = "DISPATCH_CONFIRMED"
REQUEST_PERSISTED = "REQUEST_PERSISTED"
DISPATCH_UNCONFIRMED = "DISPATCH_UNCONFIRMED"
DISPATCH_REFUSED = "DISPATCH_REFUSED"
DISPATCH_RECOVERY_REQUIRED = "DISPATCH_RECOVERY_REQUIRED"


def _dispatch_disposition(result: Mapping[str, object] | None) -> str:
    """Map one dispatch result onto the CORE-012 disposition vocabulary.

    The distinction that matters is *what the host has actually done*.
    `ok` alone cannot answer that: the file-advisory fallback returns
    ``ok: True, dispatched: False`` because the request was written durably,
    and the old controller reported that as a scheduled turn. Reading
    ``dispatched``/status here keeps "persisted" separate from "accepted".
    """
    if not isinstance(result, Mapping):
        return DISPATCH_UNCONFIRMED
    status = str(result.get("status") or "")
    if status in ("RECOVERY_REQUIRED", "CLAIM_IN_PROGRESS", "LEDGER_CORRUPT",
                  "LOCK_BUSY", "DISPATCH_TIMEOUT"):
        # LOCK_BUSY preserves the pending request; the caller must retry under
        # the same identity rather than claim a turn started. DISPATCH_TIMEOUT
        # is an UNCERTAIN outcome (W2-010), so it needs reconciliation rather
        # than a retry that could double-dispatch.
        return DISPATCH_RECOVERY_REQUIRED
    if status in ("HOOK_FAILED", "REFUSED", "REJECTED", "ERROR", "CAMPAIGN_CANCELLED"):
        return DISPATCH_REFUSED
    if status == "ALREADY_DISPATCHED":
        return DISPATCH_CONFIRMED
    if status == "ALREADY_PERSISTED":
        return REQUEST_PERSISTED
    if result.get("dispatched") is True:
        return DISPATCH_CONFIRMED if result.get("ok") else DISPATCH_REFUSED
    if result.get("ok") and result.get("disposition") == "DISPATCH_REQUEST_PERSISTED":
        return REQUEST_PERSISTED
    if result.get("ok"):
        return REQUEST_PERSISTED if status == "HOST_DISPATCH_UNAVAILABLE" else DISPATCH_UNCONFIRMED
    return DISPATCH_UNCONFIRMED


class HostIterationController:
    """The executable reference wiring between verdict, routing and UI gate."""

    #: Diagnostic history retention (PERF-007). Detection needs only the
    #: recent window; older observations are folded into aggregate counters so
    #: a long-lived controller has a fixed memory budget.
    HISTORY_RETENTION = 64
    TELEMETRY_RETENTION = 128

    def __init__(
        self,
        required,
        *,
        epoch: str = "cap-epoch-1",
        project_root: object | None = None,
        host_hook: object | None = None,
    ) -> None:
        self.required = frozenset(required)
        self._failover = iteration.Failover(epoch=str(epoch))
        #: Routing telemetry: mismatch/pause observations, newest last. A
        #: mismatch is never a project blocker and never asks the operator.
        self.telemetry: list[dict] = []
        #: Controller actions taken, as (decision, action) pairs.
        self.history: list[tuple[str, str]] = []
        #: Aggregate counters for observations dropped from the bounded
        #: windows above, so totals stay accurate without retaining records.
        self.telemetry_dropped = 0
        self.history_dropped = 0
        self.action_counts: Counter = Counter()
        self.event_counts: Counter = Counter()
        self._completion_ui_emitted: set[tuple[str, str]] = set()
        self.progress_tracker = ProgressTracker(max_iterations=50)
        from pathlib import Path
        self.project_root = Path(project_root).resolve() if project_root else None
        self.host_hook = host_hook
        self._dispatched_idempotency_keys: set[str] = set()
        #: The most recent AUTO_KICK dispatch disposition (CORE-012): the
        #: controller action now depends on this, not on the verdict alone.
        self.telemetry_dispatch: str | None = None

    def _note_telemetry(self, event: Mapping[str, object]) -> None:
        """Append one telemetry record inside the retention budget.

        The newest records are what diagnosis reads, so the oldest are dropped
        first and counted. Nothing here discards idempotency identity: the
        ``_dispatched_idempotency_keys`` set is not telemetry and is unbounded
        on purpose (PERF-007 GUARDRAIL).
        """
        self.telemetry.append(dict(event))
        self.event_counts[str(event.get("event") or "unknown")] += 1
        overflow = len(self.telemetry) - self.TELEMETRY_RETENTION
        if overflow > 0:
            del self.telemetry[:overflow]
            self.telemetry_dropped += overflow

    def _note_action(self, decision: str, action: str) -> None:
        self.history.append((decision, action))
        self.action_counts[action] += 1
        overflow = len(self.history) - self.HISTORY_RETENTION
        if overflow > 0:
            del self.history[:overflow]
            self.history_dropped += overflow

    @property
    def epoch(self) -> str:
        return self._failover.epoch

    def reseat_epoch(self, epoch: str) -> bool:
        """Move to a new capability epoch only when it actually changed.

        Returns True when the negative set was cleared. The same fingerprint
        is a no-op: reconsidering a rejected candidate needs a real tool-
        configuration change, not another lap through the route list.
        """
        if str(epoch) == self._failover.epoch:
            return False
        self._failover.new_epoch(str(epoch))
        self._note_telemetry({"event": "epoch_reseat", "epoch": str(epoch)})
        return True

    def required_from_state(
        self, state_requires: object, phase: object = None
    ) -> "HostIterationController":
        """Return a controller with required capabilities derived from STATE.

        Convenience for hosts that read STATE ``requires`` instead of
        carrying their own required set. ``phase`` narrows the set to what
        that phase executes (SRC-189 R003); without it the whole set stands.
        """
        return HostIterationController(
            required_for_state(state_requires, phase), epoch=self._failover.epoch
        )

    def admit_candidates(
        self,
        candidates: list[tuple[str, Mapping[str, object]]],
    ) -> tuple[str | None, dict | None]:
        """Pre-handoff admission over one route list, fresh per candidate.

        Every candidate is normalized and admitted independently -- no
        inheritance from the previous worker. A rejection is recorded as
        routing telemetry (``iteration.mismatch_verdict``); exhaustion
        returns the runtime-pause record with Work preserved. Writes
        nothing to STATE/BOARD.
        """
        normalized = [
            (candidate_id, {name: True for name in granted_capabilities(caps)})
            for candidate_id, caps in candidates
        ]
        known_bad = set(self._failover.observations)
        selected, pause = self._failover.select(normalized, self.required)
        for candidate_id in self._failover.observations:
            if candidate_id not in known_bad:
                missing = self._failover.observations[candidate_id]
                self._note_telemetry(
                    {
                        "event": "candidate_rejected",
                        "candidate": candidate_id,
                        **iteration.mismatch_verdict(candidate_id, missing),
                    }
                )
        if selected is None and pause is not None:
            self._note_telemetry({"event": "routes_exhausted", **pause})
        else:
            self._note_telemetry(
                {"event": "candidate_selected", "candidate": selected}
            )
        return selected, pause

    def admit_one(
        self, candidate_id: str, caps: Mapping[str, object] | None
    ) -> tuple[bool, frozenset]:
        """Admit a single switched-to executor. Fresh read, every switch."""
        return admit_normalized(caps, self.required)

    def on_model_turn_finished(
        self,
        verdict: Mapping[str, object] | None,
        *,
        turn_context: Mapping[str, object] | None = None,
    ) -> str:
        """Map one canonical verdict onto one controller action.

        Unknown, versioned-away or missing verdicts fail safe to
        ``REPORT_RUNTIME_PAUSED``: protocol-unavailable is never goal
        completion. Goal-complete UI is emitted at most once per
        (canonical task, phase).
        """
        decision = verdict.get("decision") if isinstance(verdict, Mapping) else None
        if decision not in iteration.TURN_DECISIONS:
            self._note_action("UNKNOWN", REPORT_RUNTIME_PAUSED)
            return REPORT_RUNTIME_PAUSED
        if decision == iteration.VALID_TERMINAL:
            if not verdict_allows_goal_complete_ui(verdict):
                self._note_action(decision, REPORT_RUNTIME_PAUSED)
                return REPORT_RUNTIME_PAUSED
            task = str(verdict.get("canonical_task") or "none")
            phase = str(verdict.get("phase") or "UNKNOWN")
            if (task, phase) in self._completion_ui_emitted:
                self._note_action(decision, STOP_TRUTHFULLY)
                return STOP_TRUTHFULLY
            self._completion_ui_emitted.add((task, phase))
            self._note_action(decision, EMIT_GOAL_COMPLETE_UI)
            return EMIT_GOAL_COMPLETE_UI
        if decision == iteration.AUTO_KICK:
            if turn_context:
                task = str(verdict.get("canonical_task") or "none")
                phase = str(verdict.get("phase") or "none")
                action = str(verdict.get("next_action") or "none")
                state_key = str(turn_context.get("state_hash") or turn_context.get("fingerprint") or f"{task}:{phase}")
                action_key = str(turn_context.get("action") or action)
                reason_key = str(turn_context.get("reason") or verdict.get("route_reason") or "")
                code_key = str(turn_context.get("result_code") or decision)
                if not self.progress_tracker.record(state_key, action_key, reason_key, code_key):
                    self._note_telemetry(
                        {
                            "event": "turn_stalled",
                            "reason": self.progress_tracker.stalled_reason(),
                            "task": task,
                            "phase": phase,
                        }
                    )
                    self._note_action(decision, REPORT_RUNTIME_PAUSED)
                    return REPORT_RUNTIME_PAUSED

            root = None
            if turn_context and turn_context.get("project_root"):
                from pathlib import Path
                root = Path(turn_context["project_root"]).resolve()
            elif self.project_root:
                root = self.project_root

            # With no project root there is nowhere to dispatch, so this
            # controller emits the routing decision alone and claims no
            # dispatch disposition. Only an ATTEMPTED dispatch can be
            # confirmed, persisted, refused or left unconfirmed.
            action = KICK_NEXT_ITERATION
            disposition = DISPATCH_UNCONFIRMED
            dispatch_res: dict | None = None
            if root:
                from . import host_dispatch
                cid = turn_context.get("campaign_id") if turn_context else None
                w_gen = int(turn_context.get("worker_generation", 1)) if turn_context else 1
                it_id = int(turn_context.get("iteration_id", len(self.history) + 1)) if turn_context else len(self.history) + 1
                hook = self.host_hook
                if turn_context and "host_hook" in turn_context:
                    hook = turn_context["host_hook"]
                payload = host_dispatch.build_dispatch_payload(
                    root,
                    campaign_id=cid,
                    goal_binding=turn_context.get("goal_binding") if turn_context else None,
                    worker_generation=w_gen,
                    iteration_id=it_id,
                    authority_proof_reference=turn_context.get("authority_proof_reference") if turn_context else None,
                    checkpoint_reference=turn_context.get("checkpoint_reference") if turn_context else None,
                    action=KICK_NEXT_ITERATION,
                    decision=decision,
                )
                idem_key = payload["idempotency_key"]
                if idem_key in self._dispatched_idempotency_keys:
                    disposition = DISPATCH_CONFIRMED
                else:
                    dispatch_res = host_dispatch.dispatch_next_turn(root, payload, host_hook=hook)
                    disposition = _dispatch_disposition(dispatch_res)
                    if disposition == DISPATCH_CONFIRMED:
                        self._dispatched_idempotency_keys.add(idem_key)
                        self._note_telemetry({"event": "turn_dispatched", **dispatch_res})
                    elif disposition == REQUEST_PERSISTED:
                        # Durable but not accepted: the next turn is intended,
                        # not started. Never record it as a dispatched turn.
                        self._dispatched_idempotency_keys.add(idem_key)
                        self._note_telemetry({"event": "turn_dispatch_pending", **dispatch_res})
                    else:
                        self._note_telemetry(
                            {
                                "event": "turn_dispatch_unconfirmed",
                                "disposition": disposition,
                                **dispatch_res,
                            }
                        )

                self.last_dispatch = {
                    "disposition": disposition,
                    "status": (dispatch_res or {}).get("status"),
                }
                self.telemetry_dispatch = disposition

            if root:
                action = {
                    DISPATCH_CONFIRMED: KICK_NEXT_ITERATION,
                    # The request is durable and will be replayed by the
                    # canonical protocol, but nothing has started yet (W2-004).
                    REQUEST_PERSISTED: KICK_NEXT_ITERATION,
                    DISPATCH_RECOVERY_REQUIRED: RECONCILE_DISPATCH,
                    DISPATCH_REFUSED: REPORT_RUNTIME_PAUSED,
                    DISPATCH_UNCONFIRMED: RECONCILE_DISPATCH,
                }[disposition]
            self._note_action(decision, action)
            return action
        if decision == iteration.OPERATOR_WAIT:
            self._note_action(decision, STOP_TRUTHFULLY)
            return STOP_TRUTHFULLY
        if decision == iteration.EXECUTOR_CAPABILITY_MISMATCH:
            self._note_action(decision, REROUTE_EXECUTOR)
            return REROUTE_EXECUTOR
        self._note_action(decision, REPORT_RUNTIME_PAUSED)
        return REPORT_RUNTIME_PAUSED

    def goal_complete_ui_allowed(self, verdict: Mapping[str, object] | None) -> bool:
        """The UI gate: goal-complete text requires the canonical verdict."""
        if not isinstance(verdict, Mapping):
            return False
        if verdict.get("schema_version") != ITERATION_VERDICT_SCHEMA:
            return False
        return verdict_allows_goal_complete_ui(verdict)
