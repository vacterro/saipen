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

from collections.abc import Mapping

from . import iteration
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


class HostIterationController:
    """The executable reference wiring between verdict, routing and UI gate."""

    def __init__(self, required, *, epoch: str = "cap-epoch-1") -> None:
        self.required = frozenset(required)
        self._failover = iteration.Failover(epoch=str(epoch))
        #: Routing telemetry: mismatch/pause observations, newest last. A
        #: mismatch is never a project blocker and never asks the operator.
        self.telemetry: list[dict] = []
        #: Controller actions taken, as (decision, action) pairs.
        self.history: list[tuple[str, str]] = []
        self._completion_ui_emitted: set[tuple[str, str]] = set()

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
        self.telemetry.append({"event": "epoch_reseat", "epoch": str(epoch)})
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
                self.telemetry.append(
                    {
                        "event": "candidate_rejected",
                        "candidate": candidate_id,
                        **iteration.mismatch_verdict(candidate_id, missing),
                    }
                )
        if selected is None and pause is not None:
            self.telemetry.append({"event": "routes_exhausted", **pause})
        else:
            self.telemetry.append(
                {"event": "candidate_selected", "candidate": selected}
            )
        return selected, pause

    def admit_one(
        self, candidate_id: str, caps: Mapping[str, object] | None
    ) -> tuple[bool, frozenset]:
        """Admit a single switched-to executor. Fresh read, every switch."""
        return admit_normalized(caps, self.required)

    def on_model_turn_finished(self, verdict: Mapping[str, object] | None) -> str:
        """Map one canonical verdict onto one controller action.

        Unknown, versioned-away or missing verdicts fail safe to
        ``REPORT_RUNTIME_PAUSED``: protocol-unavailable is never goal
        completion. Goal-complete UI is emitted at most once per
        (canonical task, phase).
        """
        decision = verdict.get("decision") if isinstance(verdict, Mapping) else None
        if decision not in iteration.TURN_DECISIONS:
            self.history.append(("UNKNOWN", REPORT_RUNTIME_PAUSED))
            return REPORT_RUNTIME_PAUSED
        if decision == iteration.VALID_TERMINAL:
            if not verdict_allows_goal_complete_ui(verdict):
                self.history.append((decision, REPORT_RUNTIME_PAUSED))
                return REPORT_RUNTIME_PAUSED
            task = str(verdict.get("canonical_task") or "none")
            phase = str(verdict.get("phase") or "UNKNOWN")
            if (task, phase) in self._completion_ui_emitted:
                self.history.append((decision, STOP_TRUTHFULLY))
                return STOP_TRUTHFULLY
            self._completion_ui_emitted.add((task, phase))
            self.history.append((decision, EMIT_GOAL_COMPLETE_UI))
            return EMIT_GOAL_COMPLETE_UI
        if decision == iteration.AUTO_KICK:
            self.history.append((decision, KICK_NEXT_ITERATION))
            return KICK_NEXT_ITERATION
        if decision == iteration.OPERATOR_WAIT:
            self.history.append((decision, STOP_TRUTHFULLY))
            return STOP_TRUTHFULLY
        if decision == iteration.EXECUTOR_CAPABILITY_MISMATCH:
            self.history.append((decision, REROUTE_EXECUTOR))
            return REROUTE_EXECUTOR
        self.history.append((decision, REPORT_RUNTIME_PAUSED))
        return REPORT_RUNTIME_PAUSED

    def goal_complete_ui_allowed(self, verdict: Mapping[str, object] | None) -> bool:
        """The UI gate: goal-complete text requires the canonical verdict."""
        if not isinstance(verdict, Mapping):
            return False
        if verdict.get("schema_version") != ITERATION_VERDICT_SCHEMA:
            return False
        return verdict_allows_goal_complete_ui(verdict)
