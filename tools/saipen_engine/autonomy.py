"""SAIPEN Autonomous Command Closure engine.

Drives imperative commands (cc, sc, qq, ee, qqq, eee, ship) to
deterministic terminal states without repeatedly asking the human to
authorize inspection, repair, retry, validation, recovery, reprepare,
or prerequisite execution.

CORE RULE: NEVER escalate a deterministic protocol problem to the user.

Every refusal/blocker classifies as exactly one of:
- AUTO_REPAIRABLE: engine can restore canonical state without inventing evidence
- AUTO_RECOVERABLE: restart/reprepare/supersede/retry can progress deterministically
- EXTERNAL_WAIT: real external condition must change; SAIPEN cannot cause it
- HUMAN_DECISION_REQUIRED: two or more valid outcomes change user-owned behavior
- FATAL_CORRUPTION: insufficient evidence for safe recovery

Only HUMAN_DECISION_REQUIRED may ask the user a decision question.
"""

from __future__ import annotations

import enum
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


class BlockerClass(enum.Enum):
    AUTO_REPAIRABLE = "auto_repairable"
    AUTO_RECOVERABLE = "auto_recoverable"
    EXTERNAL_WAIT = "external_wait"
    HUMAN_DECISION_REQUIRED = "human_decision_required"
    FATAL_CORRUPTION = "fatal_corruption"


class TerminalState(enum.Enum):
    DONE = "done"
    SHIPPED = "shipped"
    LOOP_STALLED = "loop_stalled"
    EXTERNAL_WAIT = "external_wait"
    HUMAN_DECISION_REQUIRED = "human_decision_required"
    FATAL_CORRUPTION = "fatal_corruption"
    CREW_COMPLETE = "crew_complete"


@dataclass
class Blocker:
    classification: BlockerClass
    stage: str
    reason: str
    repair_action: str | None = None
    detail: dict = field(default_factory=dict)


@dataclass
class IterationRecord:
    state_hash: str
    action: str
    reason: str
    result_code: str


class ProgressTracker:
    """Detects loop stalls by tracking state transitions.

    Each iteration must prove progress through at least one of:
    - checkpoint identity changed
    - lifecycle stage advanced
    - blocker count decreased
    - stale object terminalized
    - package state advanced
    - validator failure set changed
    """

    def __init__(self, max_iterations: int = 50):
        self.max_iterations = max_iterations
        self.iterations = 0
        self.history: list[IterationRecord] = []

    def record(
        self, state_hash: str, action: str, reason: str, result_code: str
    ) -> bool:
        """Record an iteration. Returns False if loop is stalled."""
        self.iterations += 1
        self.history.append(
            IterationRecord(state_hash, action, reason, result_code)
        )

        if self.iterations >= self.max_iterations:
            return False

        # Check for stall: same state+action+reason tuple repeated 3+ times
        current = (state_hash, action, reason)
        count = sum(
            1
            for h in self.history
            if (h.state_hash, h.action, h.reason) == current
        )
        if count >= 3:
            return False

        # Check for regressions: result_code oscillates
        recent_codes = [h.result_code for h in self.history[-6:]]
        if len(recent_codes) >= 6:
            if (
                recent_codes[0] == recent_codes[2] == recent_codes[4]
                and recent_codes[1] == recent_codes[3] == recent_codes[5]
                and recent_codes[0] != recent_codes[1]
            ):
                return False

        return True

    def stalled_reason(self) -> str:
        if not self.history:
            return "no iterations recorded"
        last = self.history[-1]
        return (
            f"loop stalled after {self.iterations} iterations; "
            f"last action={last.action} reason={last.reason} "
            f"code={last.result_code}"
        )


def classify_blocker(result: dict) -> Blocker:
    """Classify a command result as a blocker type.

    The classification determines whether the autonomous loop can
    repair/recover automatically or must escalate.
    """
    code = result.get("code", "")
    ok = result.get("ok", True)

    if ok:
        return Blocker(
            classification=BlockerClass.AUTO_REPAIRABLE,
            stage="",
            reason="success",
        )

    # ── CREW states ──────────────────────────────────────────────
    if code == "CREW_NOT_READY":
        return Blocker(
            classification=BlockerClass.AUTO_RECOVERABLE,
            stage="crew",
            reason=result.get("detail", "active crew epoch missing"),
            repair_action="claim_epoch_or_resume_crew",
        )

    if code == "CREW_BLOCKED":
        plan = result.get("plan", {})
        first_unsat = plan.get("first_unsatisfied", "")
        roles = plan.get("roles", {})

        # Find the blocking role
        for role, health in roles.items():
            if health in ("STALE", "INVALID"):
                return Blocker(
                    classification=BlockerClass.AUTO_REPAIRABLE,
                    stage=first_unsat,
                    reason=f"role {role} is {health}",
                    repair_action=f"prepare_or_repair_{role}",
                    detail={"role": role, "health": health},
                )
            if health == "WORK_PENDING":
                return Blocker(
                    classification=BlockerClass.AUTO_REPAIRABLE,
                    stage=first_unsat,
                    reason=f"role {role} has pending work",
                    repair_action=f"clear_or_complete_{role}",
                    detail={"role": role, "health": health},
                )
            if health == "NOT_RUN":
                return Blocker(
                    classification=BlockerClass.AUTO_REPAIRABLE,
                    stage=first_unsat,
                    reason=f"role {role} not run",
                    repair_action=f"prepare_{role}",
                    detail={"role": role, "health": health},
                )

        # Check for convergence proof issues
        reason = plan.get("action", {}).get("reason", "") if plan.get("action") else ""
        if not reason:
            reason = result.get("message", "")
        if "convergence" in reason.lower() or "source" in reason.lower():
            return Blocker(
                classification=BlockerClass.AUTO_RECOVERABLE,
                stage=first_unsat,
                reason=reason,
                repair_action="run_convergence_chain",
            )

        # Ready packages need collection
        if "ready package" in result.get("reason", "").lower():
            return Blocker(
                classification=BlockerClass.AUTO_REPAIRABLE,
                stage=first_unsat,
                reason=result.get("reason", ""),
                repair_action="collect_ready_packages",
            )

        return Blocker(
            classification=BlockerClass.AUTO_REPAIRABLE,
            stage=first_unsat,
            reason=result.get("reason", result.get("message", "")),
            repair_action="diagnose_and_repair",
        )

    # ── Release/ship states ──────────────────────────────────────
    if code == "RELEASE_BLOCKED":
        detail = result.get("detail", "")
        return Blocker(
            classification=BlockerClass.AUTO_RECOVERABLE,
            stage="ship",
            reason=detail,
            repair_action="satisfy_ship_prerequisites",
        )

    # ── Validation ───────────────────────────────────────────────
    if code == "VALIDATION_FAILED":
        detail = result.get("detail", "")
        return Blocker(
            classification=BlockerClass.AUTO_REPAIRABLE,
            stage="validation",
            reason=detail,
            repair_action="repair_validation_failure",
        )

    # ── Recovery ─────────────────────────────────────────────────
    if code == "RECOVERY_REQUIRED":
        return Blocker(
            classification=BlockerClass.AUTO_RECOVERABLE,
            stage="recovery",
            reason=result.get("detail", "recovery required"),
            repair_action="run_recovery",
        )

    # ── Default: try auto-repair ─────────────────────────────────
    return Blocker(
        classification=BlockerClass.AUTO_REPAIRABLE,
        stage="unknown",
        reason=f"code={code}: {result.get('detail', result.get('message', ''))}",
        repair_action="diagnose_and_repair",
    )


def _state_hash(project_root: Path) -> str:
    """Compute a lightweight state fingerprint for progress detection."""
    import hashlib

    h = hashlib.sha256(b"saipen-state-v1\0")
    for rel in (
        ".saipen/STATE.md",
        ".saipen/BOARD.md",
        ".saipen/LOG.md",
    ):
        path = project_root / rel
        try:
            h.update(path.read_bytes())
        except OSError:
            h.update(b"missing")
    # Include sub outbox state
    subs_dir = project_root / ".saipen" / "extensions" / "subs"
    if subs_dir.is_dir():
        for sub_dir in sorted(subs_dir.iterdir()):
            outbox = sub_dir / "kitchen" / "OUTBOX.md"
            if outbox.is_file():
                try:
                    h.update(outbox.read_bytes())
                except OSError:
                    pass
    return h.hexdigest()[:16]


def autonomous_loop(
    project_root: Path,
    intent: str,
    step_fn: Callable[[Path], dict],
    repair_fn: Callable[[Path, Blocker], bool] | None = None,
    as_json: bool = False,
    dry_run: bool = False,
    max_iterations: int = 50,
) -> dict:
    """Run the autonomous loop for a goal-directed command.

    Args:
        project_root: SAIPEN project root
        intent: human-readable intent description
        step_fn: executes the current required action, returns result dict
        repair_fn: attempts auto-repair for a blocker, returns True if repaired
        as_json: emit JSON output
        dry_run: no mutations
        max_iterations: loop bound

    Returns:
        Terminal state dict with ok/code/message/detail.
    """
    tracker = ProgressTracker(max_iterations=max_iterations)
    last_result: dict = {}

    while True:
        # Execute current required action
        try:
            result = step_fn(project_root)
        except Exception as exc:
            return {
                "ok": False,
                "code": "FATAL_CORRUPTION",
                "message": f"unrecoverable exception in {intent}",
                "detail": str(exc),
                "terminal_state": TerminalState.FATAL_CORRUPTION.value,
            }

        last_result = result

        # Check success
        if result.get("ok", False):
            terminal = result.get("_terminal_state")
            if terminal:
                return {
                    **result,
                    "terminal_state": terminal,
                    "iterations": tracker.iterations,
                }
            # If not explicitly terminal, the step succeeded but more may be needed
            # Let the next iteration decide
            state_hash = _state_hash(project_root)
            if not tracker.record(state_hash, intent, "success", result.get("code", "")):
                return {
                    "ok": False,
                    "code": "LOOP_STALLED",
                    "message": tracker.stalled_reason(),
                    "terminal_state": TerminalState.LOOP_STALLED.value,
                    "last_result": last_result,
                    "iterations": tracker.iterations,
                }
            # Success with no terminal marker = done
            return {
                **result,
                "terminal_state": TerminalState.DONE.value,
                "iterations": tracker.iterations,
            }

        # Classify the blocker
        blocker = classify_blocker(result)

        # Track progress
        state_hash = _state_hash(project_root)
        if not tracker.record(
            state_hash,
            intent,
            blocker.reason,
            result.get("code", ""),
        ):
            return {
                "ok": False,
                "code": "LOOP_STALLED",
                "message": tracker.stalled_reason(),
                "terminal_state": TerminalState.LOOP_STALLED.value,
                "last_result": last_result,
                "iterations": tracker.iterations,
                "blocker": {
                    "classification": blocker.classification.value,
                    "stage": blocker.stage,
                    "reason": blocker.reason,
                },
            }

        # Handle terminal classifications
        if blocker.classification == BlockerClass.HUMAN_DECISION_REQUIRED:
            return {
                "ok": False,
                "code": "HUMAN_DECISION_REQUIRED",
                "message": blocker.reason,
                "terminal_state": TerminalState.HUMAN_DECISION_REQUIRED.value,
                "blocker": {
                    "classification": blocker.classification.value,
                    "stage": blocker.stage,
                    "reason": blocker.reason,
                    "detail": blocker.detail,
                },
                "iterations": tracker.iterations,
            }

        if blocker.classification == BlockerClass.EXTERNAL_WAIT:
            return {
                "ok": False,
                "code": "EXTERNAL_WAIT",
                "message": blocker.reason,
                "terminal_state": TerminalState.EXTERNAL_WAIT.value,
                "blocker": {
                    "classification": blocker.classification.value,
                    "stage": blocker.stage,
                    "reason": blocker.reason,
                },
                "iterations": tracker.iterations,
            }

        if blocker.classification == BlockerClass.FATAL_CORRUPTION:
            return {
                "ok": False,
                "code": "FATAL_CORRUPTION",
                "message": blocker.reason,
                "terminal_state": TerminalState.FATAL_CORRUPTION.value,
                "blocker": {
                    "classification": blocker.classification.value,
                    "stage": blocker.stage,
                    "reason": blocker.reason,
                },
                "iterations": tracker.iterations,
            }

        # AUTO_REPAIRABLE or AUTO_RECOVERABLE: attempt repair
        if repair_fn is not None:
            try:
                repaired = repair_fn(project_root, blocker)
                if repaired:
                    continue  # retry the step
            except Exception as exc:
                return {
                    "ok": False,
                    "code": "REPAIR_FAILED",
                    "message": f"repair failed for {blocker.stage}: {exc}",
                    "terminal_state": TerminalState.FATAL_CORRUPTION.value,
                    "blocker": {
                        "classification": blocker.classification.value,
                        "stage": blocker.stage,
                        "reason": blocker.reason,
                    },
                    "iterations": tracker.iterations,
                }

        # No repair function or repair didn't help
        return {
            "ok": False,
            "code": result.get("code", "BLOCKED"),
            "message": f"autonomous {intent} blocked: {blocker.reason}",
            "terminal_state": TerminalState.DONE.value,
            "blocker": {
                "classification": blocker.classification.value,
                "stage": blocker.stage,
                "reason": blocker.reason,
                "repair_action": blocker.repair_action,
            },
            "iterations": tracker.iterations,
        }
