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


def list_goals_report(root: Path | str | None) -> dict[str, Any]:
    """Read local goal identities without hiding unavailable inventory evidence.

    A missing optional goals directory is empty only under a readable project.
    Discovery of a goal is not authentication of its maintenance grant.
    """
    from .paths import prove_owned_dir_chain, prove_owned_regular, read_bound_regular_bytes

    report: dict[str, Any] = {
        "goals": [], "unreadable": [], "errors": [],
        "root_available": False, "complete": False,
    }
    try:
        if root is None:
            raise ValueError("project root not supplied")
        project = Path(root)
        if not project.is_dir():
            raise OSError(f"project root is not a directory: {project}")
        # Enumeration proves availability; is_dir alone hides access errors.
        next(project.iterdir(), None)
        report["root_available"] = True
        gdir = goals_dir(project)
        prove_owned_dir_chain(gdir, ownership_root=project, kind="goal inventory")
        try:
            paths = sorted(gdir.iterdir())
        except FileNotFoundError:
            report["complete"] = True
            return report
    except (OSError, ValueError) as exc:
        report["errors"].append(f"goal inventory: {type(exc).__name__}: {exc}")
        return report
    for path in paths:
        if path.name.startswith(".") or path.suffix != ".json":
            continue
        try:
            info = prove_owned_regular(path, kind="goal")
            raw = json.loads(read_bound_regular_bytes(path, info, max_bytes=1024 * 1024))
            if not isinstance(raw, dict):
                raise ValueError("goal must be an object")
            identity = validate_safe_id(raw.get("goal_id"), kind="goal_id")
            if identity != path.stem or raw.get("goal_id") != identity:
                raise ValueError("goal identity does not match its filename")
            if raw.get("current_status", STATUS_ACTIVE) not in GOAL_STATUSES:
                raise ValueError("unrecognized goal status")
            if not isinstance(raw.get("paused", False), bool):
                raise ValueError("paused must be a boolean")
            report["goals"].append(PersistentGoal.from_dict(raw))
        except (OSError, ValueError, TypeError) as exc:
            report["unreadable"].append(str(path))
            report["errors"].append(f"{path}: {type(exc).__name__}: {exc}")
    report["complete"] = not report["errors"]
    return report


def goal_inventory(evidence: Any) -> dict[str, Any]:
    """Normalize explicit goal evidence; absence is not a checked empty set."""
    result: dict[str, Any] = {
        "goals": [], "unreadable": [], "errors": [],
        "supplied": evidence is not None, "complete": False,
    }
    if evidence is None:
        return result
    if isinstance(evidence, dict) and "goals" in evidence:
        if not isinstance(evidence["goals"], (list, tuple)):
            result["errors"].append("goal inventory must contain a goal list")
            return result
        result["goals"] = list(evidence["goals"])
        for key in ("unreadable", "errors"):
            entries = evidence.get(key, [])
            if not isinstance(entries, (list, tuple)):
                result["errors"].append(f"goal inventory {key} must be a list")
            else:
                result[key].extend(str(entry) for entry in entries)
        result["complete"] = evidence.get("complete") is True
        if evidence.get("root_available") is False:
            result["complete"] = False
    elif isinstance(evidence, (list, tuple)):
        result["goals"] = list(evidence)
        result["complete"] = True
    elif isinstance(evidence, PersistentGoal) or isinstance(evidence, dict) and "goal_id" in evidence:
        result["goals"] = [evidence]
        result["complete"] = True
    else:
        result["errors"].append(f"unsupported goal evidence {type(evidence).__name__}")
    valid = []
    for goal in result["goals"]:
        if not isinstance(goal, (dict, PersistentGoal)):
            result["errors"].append("invalid goal inventory member")
            continue
        status = goal.get("current_status", STATUS_ACTIVE) if isinstance(goal, dict) else goal.current_status
        if status not in GOAL_STATUSES:
            result["errors"].append(f"unrecognized goal status: {status!r}")
            continue
        paused = goal.get("paused", False) if isinstance(goal, dict) else goal.paused
        if type(paused) is not bool:
            result["errors"].append("goal paused must be a boolean")
            continue
        valid.append(goal)
    result["goals"] = valid
    result["complete"] = result["complete"] and not result["unreadable"] and not result["errors"]
    return result


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
        if isinstance(raw, dict) and raw.get("goal_id") == goal_id:
            return PersistentGoal.from_dict(raw)
    except (OSError, ValueError, TypeError):
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
