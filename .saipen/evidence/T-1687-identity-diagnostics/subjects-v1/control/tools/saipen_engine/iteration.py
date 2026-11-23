"""Outer-iteration terminality and executor capability admission (T-1619).

Two facts the protocol already owns but an ADVISORY host could ignore:

* a model turn ending is not goal completion -- canonical state owns
  terminality (MAINTENANCE GOAL-01);
* a model/provider is not an executor -- capability belongs to the current
  harness incarnation and is admitted per switch (MODEL != EXECUTOR).

This module is the canonical decision owner the outer iteration controller
queries after every model turn. It takes canonical facts only -- it accepts
no prose, so no sentence ("bigger than one sitting", "timebox complete",
"I'll continue later") can move it. Pure functions: no BOARD/STATE writes;
a mismatch is routing telemetry, never a project blocker.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping

#: Closed turn-decision vocabulary for the outer iteration controller.
AUTO_KICK = "AUTO_KICK"
VALID_TERMINAL = "VALID_TERMINAL"
OPERATOR_WAIT = "OPERATOR_WAIT"
EXECUTOR_CAPABILITY_MISMATCH = "EXECUTOR_CAPABILITY_MISMATCH"
RUNTIME_PAUSED = "RUNTIME_PAUSED"
#: Why a run is paused when the whole pool was tried: a blocker of the
#: runtime, never of the project or the ticket.
NO_COMPATIBLE_EXECUTOR = "NO_COMPATIBLE_EXECUTOR"
TURN_DECISIONS = frozenset(
    {
        AUTO_KICK,
        VALID_TERMINAL,
        OPERATOR_WAIT,
        EXECUTOR_CAPABILITY_MISMATCH,
        RUNTIME_PAUSED,
    }
)

#: What operational continuation needs. STATE `requires` carries the
#: repository half (filesystem/git/python); running `saipen continue --json`
#: and mutating the tree additionally needs a shell and patch/write.
EXECUTION_CAPABILITIES = frozenset({"shell", "patch"})
REQUIRED_OPERATIONAL = frozenset({"filesystem", "git", "python"}) | EXECUTION_CAPABILITIES


def required_for(state_requires: Collection[str]) -> frozenset:
    """The capability set operational continuation needs on this project."""
    return frozenset(state_requires) | EXECUTION_CAPABILITIES


def admit(
    candidate: Mapping[str, object],
    required: Collection[str],
) -> tuple[bool, frozenset]:
    """Admit one executor candidate against the required set.

    Only explicit advertised truth counts: an absent, unknown or falsy
    capability is missing (fail closed). The candidate's identity -- model,
    provider, route name -- is never read: MODEL != EXECUTOR CAPABILITY.
    Pure: reads nothing but its arguments, writes nothing.
    """
    missing = frozenset(
        name for name in required if not _truthy(candidate.get(name, False))
    )
    return (not missing, missing)


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1", "available", "granted")
    return bool(value)


def mismatch_verdict(candidate_id: str, missing: frozenset) -> dict:
    """The SAIOPP incident, classified: routing telemetry, not a blocker."""
    return {
        "code": EXECUTOR_CAPABILITY_MISMATCH,
        "candidate": candidate_id,
        "missing": sorted(missing),
        "project_blocked": False,
        "ticket_blocked": False,
        "requires_human": False,
        "retryable": True,
        "reroute_required": True,
    }


class Failover:
    """Bounded automatic failover with epoch-scoped negative observations.

    A rejected candidate is remembered for the capability epoch so the
    router never loops SAIOPP -> no shell -> SAIOPP. A new epoch (provider
    or tool-profile change) clears the memory and the candidate may be
    reconsidered. Session-local: no BOARD/STATE writes.
    """

    def __init__(self, epoch: str) -> None:
        self.epoch = epoch
        self.observations: dict[str, frozenset] = {}

    def observe(self, candidate_id: str, missing: frozenset) -> None:
        self.observations[candidate_id] = frozenset(missing)

    def new_epoch(self, epoch: str) -> None:
        self.epoch = epoch
        self.observations = {}

    def select(
        self,
        candidates: list[tuple[str, Mapping[str, object]]],
        required: Collection[str],
    ) -> tuple[str | None, dict | None]:
        """First compatible candidate never observed bad; else (None, pause).

        Rejections are observed as they happen, so a second call in the
        same epoch cannot return the same bad executor twice.
        """
        for candidate_id, caps in candidates:
            if candidate_id in self.observations:
                continue
            compatible, missing = admit(caps, required)
            if compatible:
                return candidate_id, None
            self.observe(candidate_id, missing)
        return None, {
            "code": RUNTIME_PAUSED,
            # SRC-189 R008: ONE canonical blocker that says what was needed
            # and what each executor of the pool lacked, never "the agent
            # cannot do this".
            "blocker": NO_COMPATIBLE_EXECUTOR,
            "required": sorted(required),
            "pool": {
                candidate_id: sorted(self.observations.get(candidate_id, frozenset()))
                for candidate_id, _caps in candidates
            },
            "reason": "every authorized executor route is incompatible "
            "with the mandatory task capabilities",
            "project_blocked": False,
            "requires_human": False,
        }


def decide_turn(
    *,
    executor_compatible: bool,
    goal_complete: bool,
    executable_action_remains: bool,
    operator_due: bool,
    valve_tripped: bool,
    all_candidates_exhausted: bool = False,
) -> str:
    """MODEL_TURN_FINISHED vs SAIPEN_GOAL_FINISHED, from canonical facts.

    Precedence is deliberate: executor fitness first (an unfit executor
    decides nothing else), then human boundaries (operator due, safety
    valve -- both stop, never weakened), then proven terminality, then
    remaining work. An unproven end-of-work pauses truthfully instead of
    reporting completion.
    """
    if not executor_compatible:
        if all_candidates_exhausted:
            return RUNTIME_PAUSED
        return EXECUTOR_CAPABILITY_MISMATCH
    if operator_due or valve_tripped:
        return OPERATOR_WAIT
    if goal_complete and not executable_action_remains:
        return VALID_TERMINAL
    if executable_action_remains:
        return AUTO_KICK
    return OPERATOR_WAIT


def may_report_goal_complete(decision: str) -> bool:
    """The UI gate: "goal complete" is permitted on one decision only."""
    return decision == VALID_TERMINAL
