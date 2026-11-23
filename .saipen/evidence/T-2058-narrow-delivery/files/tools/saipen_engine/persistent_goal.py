"""SAIPEN Core Persistent Goal Engine (SRC-367 / T-1993).

Differentiates:
A. The current ticket queue is empty.
B. The current execution wave has completed.
C. Project conformance checks pass.
D. A persistent user-authorized project goal has actually been fulfilled.
E. There are still actionable research, development, verification or maintenance gaps.
F. No further authorized work can currently proceed.

Formalizes persistent project goals with durable identity, evidence providers,
satisfaction criteria, admission policies, and progress tracking.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .safeid import InvalidIdError, prove_inside, validate_safe_id

# Goal Status Vocabulary (SRC-367 Section 4)
STATUS_ACTIVE = "ACTIVE"
STATUS_SATISFIED = "SATISFIED"
STATUS_ACTIONABLE_GAPS = "ACTIONABLE_GAPS"
STATUS_DISCOVERY_REQUIRED = "DISCOVERY_REQUIRED"
STATUS_WAITING_DEPENDENCY = "WAITING_DEPENDENCY"
STATUS_WAITING_AUTHORITY = "WAITING_AUTHORITY"
STATUS_BLOCKED_BY_EVIDENCE = "BLOCKED_BY_EVIDENCE"
STATUS_NO_ADMISSIBLE_WORK = "NO_ADMISSIBLE_WORK"
STATUS_VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"

GOAL_STATUSES = frozenset({
    STATUS_ACTIVE,
    STATUS_SATISFIED,
    STATUS_ACTIONABLE_GAPS,
    STATUS_DISCOVERY_REQUIRED,
    STATUS_WAITING_DEPENDENCY,
    STATUS_WAITING_AUTHORITY,
    STATUS_BLOCKED_BY_EVIDENCE,
    STATUS_NO_ADMISSIBLE_WORK,
    STATUS_VERIFICATION_REQUIRED,
})

# Goal Verification / Scope classifications
SCOPE_RESEARCH = "RESEARCH"
SCOPE_IMPLEMENTATION = "IMPLEMENTATION"
SCOPE_RELEASE = "RELEASE"
SCOPE_MAINTENANCE = "MAINTENANCE"
SCOPE_TEST_CAMPAIGN = "TEST_CAMPAIGN"
SCOPE_DESTRUCTIVE = "DESTRUCTIVE"


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class PersistentGoal:
    goal_id: str
    project_id: str
    title: str
    objective: str
    authorization_scope: str = SCOPE_RESEARCH
    success_criteria: dict[str, Any] = field(default_factory=dict)
    evidence_provider: str = "evidence_gap_ledger"
    current_progress: dict[str, Any] = field(default_factory=dict)
    target_progress: dict[str, Any] = field(default_factory=dict)
    research_or_work_backlog_source: str = ""
    admission_policy: dict[str, Any] = field(default_factory=dict)
    current_status: str = STATUS_ACTIVE
    last_evaluation: str = ""
    last_successful_work: str | None = None
    last_discovery: str | None = None
    blockers: list[str] = field(default_factory=list)
    completion_evidence: dict[str, Any] | None = None
    resume_metadata: dict[str, Any] = field(default_factory=dict)
    paused: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PersistentGoal:
        status = data.get("current_status", STATUS_ACTIVE)
        if status not in GOAL_STATUSES:
            status = STATUS_ACTIVE
        return cls(
            goal_id=str(data.get("goal_id", "")),
            project_id=str(data.get("project_id", "")),
            title=str(data.get("title", "")),
            objective=str(data.get("objective", "")),
            authorization_scope=str(data.get("authorization_scope", SCOPE_RESEARCH)),
            success_criteria=dict(data.get("success_criteria") or {}),
            evidence_provider=str(data.get("evidence_provider", "evidence_gap_ledger")),
            current_progress=dict(data.get("current_progress") or {}),
            target_progress=dict(data.get("target_progress") or {}),
            research_or_work_backlog_source=str(data.get("research_or_work_backlog_source", "")),
            admission_policy=dict(data.get("admission_policy") or {}),
            current_status=status,
            last_evaluation=str(data.get("last_evaluation", "")),
            last_successful_work=data.get("last_successful_work"),
            last_discovery=data.get("last_discovery"),
            blockers=list(data.get("blockers") or []),
            completion_evidence=data.get("completion_evidence"),
            resume_metadata=dict(data.get("resume_metadata") or {}),
            paused=bool(data.get("paused", False)),
        )


def goals_dir(root: Path | str) -> Path:
    return Path(root) / ".saipen" / "goals"


def list_goals(root: Path | str | None) -> list[PersistentGoal]:
    if not root:
        return []
    gdir = goals_dir(root)
    if not gdir.is_dir():
        return []
    goals: list[PersistentGoal] = []
    for path in sorted(gdir.glob("*.json")):
        if path.name.startswith("."):
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "goal_id" in raw:
                goals.append(PersistentGoal.from_dict(raw))
        except (OSError, ValueError):
            continue
    return goals


def get_goal(root: Path | str, goal_id: str) -> PersistentGoal | None:
    try:
        validate_safe_id(goal_id, kind="goal_id")
    except InvalidIdError:
        return None
    gdir = goals_dir(root)
    path = gdir / f"{goal_id}.json"
    try:
        path = prove_inside(path, gdir, kind="goal_path")
    except InvalidIdError:
        return None
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "goal_id" in raw:
            return PersistentGoal.from_dict(raw)
    except (OSError, ValueError):
        return None
    return None


class DuplicateGoalError(ValueError):
    """Raised when registering a goal with an ID that already exists."""
    pass


def register_goal(root: Path | str, goal: PersistentGoal) -> Path:
    """Register a new persistent goal. Refuses duplicate registrations."""
    existing = get_goal(root, goal.goal_id)
    if existing is not None:
        raise DuplicateGoalError(f"goal '{goal.goal_id}' already exists")
    return save_goal(root, goal)


def save_goal(root: Path | str, goal: PersistentGoal) -> Path:
    validate_safe_id(goal.goal_id, kind="goal_id")
    gdir = goals_dir(root)
    gdir.mkdir(parents=True, exist_ok=True)
    path = gdir / f"{goal.goal_id}.json"
    path = prove_inside(path, gdir, kind="goal_path")
    tmp = path.with_suffix(".tmp")
    tmp = prove_inside(tmp, gdir, kind="goal_tmp_path")
    tmp.write_text(json.dumps(goal.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path


def delete_goal(root: Path | str, goal_id: str) -> bool:
    try:
        validate_safe_id(goal_id, kind="goal_id")
    except InvalidIdError:
        return False
    gdir = goals_dir(root)
    path = gdir / f"{goal_id}.json"
    try:
        path = prove_inside(path, gdir, kind="goal_path")
    except InvalidIdError:
        return False
    if path.is_file():
        try:
            path.unlink()
            return True
        except OSError:
            return False
    return False
