"""Durable Campaign Lifecycle Controller for SAIPEN (Block 3, 7, 8).

Supervises successive bounded worker generations, maintenance discovery,
forensic audit delivery, and repair verification across long-running campaigns.

Closed States:
- PROPOSED
- ADMITTED
- RUNNING
- CHECKPOINTING
- DISCOVERING
- FORENSIC_ANALYSIS
- AUDIT_DELIVERY
- REPAIRING
- VERIFYING
- QUIESCENT_WAIT
- RETRY_WAIT
- OPERATOR_BLOCKED
- AUTHORITY_BLOCKED
- EXTERNAL_BLOCKED
- SAFETY_STOP
- CANCELLED
- COMPLETE
"""

from __future__ import annotations

import datetime as _dt
import contextlib
import hashlib
import inspect as _inspect
import json
import math
import os
import shlex
import subprocess
import sys
import uuid
from collections.abc import Mapping
from pathlib import Path

from . import continuation_assessment as ca
from . import backend_protocol, campaign_authority, host_dispatch, lock, supervisor
from .paths import safe_atomic_write_bytes

CAMPAIGN_SCHEMA_VERSION = 1
STATE_REL = Path(".saipen") / "campaign" / "state.json"
LOCK_REL = Path(".saipen") / "locks" / "campaign.lock"

# State inspection outcomes
STATE_ABSENT = "STATE_ABSENT"
STATE_VALID = "STATE_VALID"
STATE_CORRUPT = "STATE_CORRUPT"
STATE_INCOMPATIBLE = "STATE_INCOMPATIBLE"
STATE_UNTRUSTED = "STATE_UNTRUSTED"

# Closed states
PROPOSED = "PROPOSED"
ADMITTED = "ADMITTED"
RUNNING = "RUNNING"
CHECKPOINTING = "CHECKPOINTING"
DISCOVERING = "DISCOVERING"
FORENSIC_ANALYSIS = "FORENSIC_ANALYSIS"
AUDIT_DELIVERY = "AUDIT_DELIVERY"
REPAIRING = "REPAIRING"
VERIFYING = "VERIFYING"
QUIESCENT_WAIT = "QUIESCENT_WAIT"
RETRY_WAIT = "RETRY_WAIT"
OPERATOR_BLOCKED = "OPERATOR_BLOCKED"
AUTHORITY_BLOCKED = "AUTHORITY_BLOCKED"
EXTERNAL_BLOCKED = "EXTERNAL_BLOCKED"
SAFETY_STOP = "SAFETY_STOP"
CANCELLED = "CANCELLED"
COMPLETE = "COMPLETE"

CAMPAIGN_STATES = frozenset(
    {
        PROPOSED,
        ADMITTED,
        RUNNING,
        CHECKPOINTING,
        DISCOVERING,
        FORENSIC_ANALYSIS,
        AUDIT_DELIVERY,
        REPAIRING,
        VERIFYING,
        QUIESCENT_WAIT,
        RETRY_WAIT,
        OPERATOR_BLOCKED,
        AUTHORITY_BLOCKED,
        EXTERNAL_BLOCKED,
        SAFETY_STOP,
        CANCELLED,
        COMPLETE,
    }
)

# Public aliases; the scoped authorization owner defines this vocabulary.
CAMPAIGN_EXECUTION = campaign_authority.CAMPAIGN_EXECUTION
FORENSIC_ANALYSIS_SCOPE = campaign_authority.FORENSIC_ANALYSIS_SCOPE
AUDIT_STAGING = campaign_authority.AUDIT_STAGING
EXTERNAL_AUDIT_PUBLICATION = campaign_authority.EXTERNAL_AUDIT_PUBLICATION
SAIPEN_AUDIT_INGESTION = campaign_authority.SAIPEN_AUDIT_INGESTION
PROTOCOL_REPAIR = campaign_authority.PROTOCOL_REPAIR
CONTINUOUS_MAINTENANCE_SCOPE = campaign_authority.CONTINUOUS_MAINTENANCE_SCOPE
ALL_SCOPES = campaign_authority.ALL_SCOPES

# Campaign Horizons
HORIZONS = {
    "SHORT": {"max_wall_seconds": 3600.0, "max_cycles": 10, "max_generations": 5},
    "MULTI_HOUR": {"max_wall_seconds": 14400.0, "max_cycles": 30, "max_generations": 15},
    "OVERNIGHT": {"max_wall_seconds": 36000.0, "max_cycles": 100, "max_generations": 40},
    "MULTI_DAY": {"max_wall_seconds": 172800.0, "max_cycles": 500, "max_generations": 200},
}


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def campaign_state_path(root: Path | str) -> Path:
    return Path(root).resolve() / STATE_REL


def inspect_campaign_state(root: Path | str) -> dict:
    path = campaign_state_path(root)
    try:
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            return {
                "status": STATE_CORRUPT,
                "error": "Empty campaign state file",
                "path": str(path),
            }
        data = json.loads(content)
        if not isinstance(data, dict):
            return {
                "status": STATE_CORRUPT,
                "error": "Campaign state is not a dictionary",
                "path": str(path),
            }
        if (
            type(data.get("schema_version")) is not int
            or data["schema_version"] != CAMPAIGN_SCHEMA_VERSION
        ):
            return {
                "status": STATE_INCOMPATIBLE,
                "version": data.get("schema_version"),
                "state": data,
            }
        if "campaign_id" not in data or "campaign_state" not in data:
            return {
                "status": STATE_CORRUPT,
                "error": "Missing mandatory campaign fields",
                "state": data,
            }
        if (
            not isinstance(data["campaign_id"], str)
            or not data["campaign_id"].strip()
            or not isinstance(data["campaign_state"], str)
            or data["campaign_state"] not in CAMPAIGN_STATES
        ):
            return {
                "status": STATE_CORRUPT,
                "error": "Invalid campaign identity or lifecycle state",
                "state": data,
            }
        # CORE-002 (audit/27.md): `save_campaign_state` writes `state_digest`
        # unconditionally, so a reader that treats the field as optional lets
        # anyone fabricate a terminal lifecycle by deleting it. The digest is
        # mandatory under this schema: absence, emptiness and malformed shape are
        # refused as corrupt, and only a well-formed mismatch is STATE_UNTRUSTED.
        stored_digest = data.get("state_digest")
        if "state_digest" not in data:
            return {
                "status": STATE_CORRUPT,
                "error": (
                    "Campaign state carries no state_digest; every state written "
                    "under this schema is digest-bound, so an unsigned record is "
                    "not a state this engine produced"
                ),
                "path": str(path),
                "state": data,
            }
        if not isinstance(stored_digest, str) or not stored_digest.strip():
            return {
                "status": STATE_CORRUPT,
                "error": "Campaign state_digest is empty or not a string",
                "path": str(path),
                "state": data,
            }
        if len(stored_digest) != 64 or any(
            char not in "0123456789abcdef" for char in stored_digest
        ):
            return {
                "status": STATE_CORRUPT,
                "error": "Campaign state_digest is not a sha256 hex digest",
                "path": str(path),
                "state": data,
            }
        state_copy = {k: v for k, v in data.items() if k not in ("state_digest", "updated_at")}
        expected_digest = hashlib.sha256(
            json.dumps(state_copy, sort_keys=True).encode("utf-8")
        ).hexdigest()
        if stored_digest != expected_digest:
            return {
                "status": STATE_UNTRUSTED,
                "error": "Campaign state provenance digest mismatch; untrusted modification",
                "path": str(path),
                "state": data,
            }
        for key in (
            "worker_generation",
            "cycle_count",
            "cancellation_epoch",
            "retry_count",
            "no_progress_count",
        ):
            if key in data and (type(data[key]) is not int or data[key] < 0):
                return {
                    "status": STATE_CORRUPT,
                    "error": f"Invalid persisted counter: {key}",
                    "path": str(path),
                }
        if "resource_budget" in data and not _valid_budget(data["resource_budget"]):
            return {
                "status": STATE_CORRUPT,
                "error": "Invalid persisted resource budget",
                "path": str(path),
            }
        if "worker_attempt" in data:
            attempt = data["worker_attempt"]
            if (
                not isinstance(attempt, dict)
                or not {
                    "attempt_id",
                    "campaign_id",
                    "generation",
                    "cancellation_epoch",
                    "execution_intent",
                    "status",
                }
                <= attempt.keys()
                or attempt["campaign_id"] != data["campaign_id"]
                or type(attempt["generation"]) is not int
                or attempt["generation"] < 1
                or attempt["generation"] != data.get("worker_generation")
                or type(attempt["cancellation_epoch"]) is not int
                or attempt["cancellation_epoch"] < 0
                or not isinstance(attempt["execution_intent"], dict)
                or attempt["status"]
                not in (
                    "EXECUTOR_STARTED",
                    "UNKNOWN_OUTCOME",
                    "CANCEL_REQUESTED",
                    "EXECUTION_RESULT_OBSERVED",
                )
            ):
                return {
                    "status": STATE_CORRUPT,
                    "error": "Invalid worker attempt",
                    "path": str(path),
                }
        return {"status": STATE_VALID, "state": data}
    except FileNotFoundError:
        return {"status": STATE_ABSENT}
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"status": STATE_CORRUPT, "error": str(exc), "path": str(path)}


def load_campaign_state(root: Path | str) -> dict | None:
    inspect = inspect_campaign_state(root)
    if inspect.get("status") == STATE_VALID:
        return inspect.get("state")
    return None


def save_campaign_state(root: Path | str, state: dict) -> None:
    root = Path(root).resolve()
    path = campaign_state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _utc_now()
    state_copy = {k: v for k, v in state.items() if k not in ("state_digest", "updated_at")}
    state["state_digest"] = hashlib.sha256(
        json.dumps(state_copy, sort_keys=True).encode("utf-8")
    ).hexdigest()
    body = (json.dumps(state, indent=2, sort_keys=True) + "\n").encode("utf-8")
    safe_atomic_write_bytes(
        path,
        body,
        kind="campaign state",
        ownership_root=root,
    )


def _valid_budget(budget: object) -> bool:
    if not isinstance(budget, Mapping):
        return False
    for key, value in budget.items():
        if key not in ("max_generations", "max_cycles", "max_wall_seconds"):
            return False
        if type(value) not in (int, float):
            return False
        try:
            if not math.isfinite(value) or value <= 0:
                return False
        except OverflowError:
            return False
        if key != "max_wall_seconds" and type(value) is not int:
            return False
    return True


def _invoke_worker(worker_func: callable, root: Path, generation: int) -> dict:
    """Resolve the legacy call shapes before invocation; never retry a side effect."""
    signature = _inspect.signature(worker_func)
    for args, kwargs in (
        ((root,), {"generation": generation}),
        ((root, generation), {}),
        ((root,), {}),
    ):
        try:
            signature.bind(*args, **kwargs)
        except TypeError:
            continue
        return worker_func(*args, **kwargs)
    raise TypeError("Worker signature must accept project root and optional generation")


def _attempt_binding(attempt: dict) -> dict:
    return {
        key: attempt[key]
        for key in (
            "attempt_id",
            "campaign_id",
            "generation",
            "cancellation_epoch",
            "execution_intent",
        )
    }


def _outcome_digest(outcome: dict) -> str:
    payload = {key: value for key, value in outcome.items() if key != "receipt_digest"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()


def verify_operator_grant(
    root, grant_reference, requested_scope=None, *, admission=None, consume=False
):
    """Verify the exact operator capsule through its separated native issuer."""
    return campaign_authority.verify_grant(
        root,
        grant_reference,
        requested_scope,
        admission=admission,
        consume=consume,
    )


def _verify_state_grant(root, state, requested_scope=None):
    scope = state.get("authority_scope") if requested_scope is None else requested_scope
    result = verify_operator_grant(
        root,
        state.get("authority_proof_reference"),
        scope,
        admission=campaign_authority.admission_for_state(state),
    )
    if result.get("valid") and scope not in result.get("authorized_scopes", set()):
        return {
            "valid": False,
            "status": "SCOPE_UNAUTHORIZED",
            "authorized_scopes": set(),
            "error": "The original capsule does not grant this operation",
        }
    if result.get("valid") and (
        not state.get("authority_grant_digest")
        or state["authority_grant_digest"] != result.get("grant_digest")
    ):
        return {
            "valid": False,
            "status": "GRANT_MODIFIED_AFTER_ADMISSION",
            "authorized_scopes": set(),
            "error": "Original authority carrier changed",
        }
    return result


class CampaignController:
    """Supervises campaign lifecycle and successive bounded worker generations."""

    def __init__(self, project_root: Path | str, *, backend=None) -> None:
        """`backend` is injected; the engine may not name a producer (T-1947).

        A controller built without one still runs the whole campaign lifecycle
        -- admission, worker generations, checkpoints, cancellation. Only the
        discovery edge needs an analysis backend, and with none injected it
        answers with a typed refusal instead of resolving a producer itself:
        which backend this deployment drives is a caller fact, and a name the
        engine cannot spell is a name it cannot branch on.
        """
        self.root = Path(project_root).resolve()
        self.backend = backend

    def _acquire_lock(self) -> lock.FileWriterLock:
        lock_file = self.root / LOCK_REL
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lk = lock.FileWriterLock(lock_file, self.root, blocking=False)
        lk.acquire()
        return lk

    def admit_campaign(
        self,
        *,
        campaign_id: str | None = None,
        horizon: str = "SHORT",
        goal_binding: object | None = None,
        authority_scope: str | None = None,
        authority_proof_reference: str | None = None,
        resource_budget: Mapping[str, object] | None = None,
        force_new: bool = False,
    ) -> dict:
        """Admit a new campaign or resume existing admitted campaign."""
        try:
            lk = self._acquire_lock()
        except lock.FileLockBusy:
            return {
                "ok": False,
                "code": "CAMPAIGN_LOCKED",
                "detail": "Another controller owns the campaign lock",
            }

        try:
            # 1. Horizon validation
            if not isinstance(horizon, str) or horizon not in HORIZONS:
                return {
                    "ok": False,
                    "code": "INVALID_HORIZON",
                    "status": "INVALID_HORIZON",
                    "detail": (
                        f"Unknown horizon '{horizon}'; must be one of {sorted(HORIZONS.keys())}"
                    ),
                }

            # 2. Resource budget validation
            if resource_budget is not None and not _valid_budget(resource_budget):
                return {
                    "ok": False,
                    "code": "INVALID_RESOURCE_BUDGET",
                    "status": "INVALID_RESOURCE_BUDGET",
                    "detail": (
                        "Budget must use positive finite numeric limits; "
                        "cycle and generation counts must be integers"
                    ),
                }

            inspect = inspect_campaign_state(self.root)
            if inspect["status"] not in (STATE_ABSENT, STATE_VALID):
                return {
                    "ok": False,
                    "code": inspect["status"],
                    "status": inspect["status"],
                    "detail": (
                        f"Campaign state has invalid integrity ({inspect['status']}); "
                        "overwrite refused without explicit recovery"
                    ),
                    "inspection": inspect,
                }

            cid = str(campaign_id or f"CAMPAIGN-{uuid.uuid4()}")
            if inspect["status"] == STATE_VALID:
                existing = inspect["state"]
                if existing:
                    existing_state = existing.get("campaign_state")
                    if not force_new and existing_state not in (COMPLETE, CANCELLED):
                        return {
                            "ok": True,
                            "admitted": False,
                            "state": existing,
                            "status": "RESUMED_EXISTING",
                        }

                    if force_new and existing_state not in (COMPLETE, CANCELLED):
                        return {
                            "ok": False,
                            "code": "LIVE_CAMPAIGN_SUPERSEDED_REFUSED",
                            "status": "LIVE_CAMPAIGN_SUPERSEDED_REFUSED",
                            "detail": (
                                f"Active campaign {existing.get('campaign_id')} is "
                                f"currently in live state '{existing_state}'. "
                                "Cancel or stop it first."
                            ),
                        }
                    if existing_state in (COMPLETE, CANCELLED) and cid == existing["campaign_id"]:
                        return {
                            "ok": False,
                            "code": "CAMPAIGN_ID_REUSED",
                            "detail": "A new campaign must have a new identity",
                        }
            lineage = host_dispatch.resolve_project_lineage(self.root)
            budget = dict(HORIZONS.get(horizon, HORIZONS["SHORT"]))
            if resource_budget:
                budget.update(resource_budget)

            # Authority grant verification
            grant_res = None
            if authority_proof_reference:
                try:
                    candidate = campaign_authority.read_carrier(
                        self.root, authority_proof_reference
                    )
                    authorization = candidate["authorization"]
                except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
                    return {
                        "ok": False,
                        "code": "INVALID_AUTHORITY_GRANT",
                        "status": "GRANT_INVALID",
                        "detail": str(exc),
                    }
                if resource_budget and any(
                    value > authorization["resource_budget"][key]
                    for key, value in resource_budget.items()
                ):
                    return {
                        "ok": False,
                        "code": "INVALID_RESOURCE_BUDGET",
                        "detail": "Requested resources exceed the original operator capsule",
                    }
                budget = {
                    key: min(value, authorization["resource_budget"][key])
                    for key, value in budget.items()
                }
                if goal_binding is None:
                    goal_binding = authorization["goal_binding"]
                scopes = authorization["authorized_scopes"]
                scope = authority_scope or (
                    CONTINUOUS_MAINTENANCE_SCOPE
                    if CONTINUOUS_MAINTENANCE_SCOPE in scopes
                    else CAMPAIGN_EXECUTION
                    if CAMPAIGN_EXECUTION in scopes
                    else min(scopes)
                )
                admission = {
                    "campaign_id": cid,
                    "goal_binding": goal_binding,
                    "resource_budget": budget,
                }
                grant_res = verify_operator_grant(
                    self.root,
                    authority_proof_reference,
                    scope,
                    admission=admission,
                    consume=True,
                )
                if not grant_res["valid"]:
                    return {
                        "ok": False,
                        "code": "INVALID_AUTHORITY_GRANT",
                        "status": grant_res.get("status", "INVALID_GRANT"),
                        "detail": grant_res.get("error", "Invalid operator grant proof"),
                    }
                camp_state = ADMITTED
                executable = True
                grant_data = grant_res["grant"]
            else:
                # A campaign without an authenticated grant is a non-executable proposal.
                scope = "none"
                camp_state = PROPOSED
                executable = False
                grant_data = None
                if goal_binding is None:
                    goal_binding = {
                        "path": str(self.root / ".saipen/STATE.md"),
                        "fingerprint": lineage,
                    }

            now_str = _utc_now()
            state = {
                "schema_version": CAMPAIGN_SCHEMA_VERSION,
                "campaign_id": cid,
                "project_lineage": lineage,
                "goal_binding": goal_binding,
                "authority_proof_reference": authority_proof_reference,
                "authority_scope": scope,
                "authority_grant": grant_data,
                "authority_grant_digest": grant_res.get("grant_digest") if grant_res else None,
                "campaign_state": camp_state,
                "current_work": None,
                "worker_generation": 0,
                "cycle_count": 0,
                "cancellation_epoch": 0,
                "last_journal_event": "none",
                "last_source_generation": 0,
                "last_audit_generation": 0,
                "last_analysis_generation": 0,
                "last_productive_progress": now_str,
                "last_verified_result": None,
                "next_action": "start_campaign_worker" if executable else "operator_grant_required",
                "wake_condition": None,
                "retry_count": 0,
                "no_progress_count": 0,
                "resource_budget": budget,
                "created_at": now_str,
                "updated_at": now_str,
            }
            if inspect["status"] == STATE_VALID:
                # Archive first: interruption here leaves the original live state intact.
                # The successor references the exact original bytes, not a rewritten summary.
                previous_bytes = campaign_state_path(self.root).read_bytes()
                previous_digest = hashlib.sha256(previous_bytes).hexdigest()
                previous_rel = STATE_REL.parent / "history" / f"{previous_digest}.json"
                previous_path = self.root / previous_rel
                previous_path.parent.mkdir(parents=True, exist_ok=True)
                if previous_path.exists():
                    if previous_path.read_bytes() != previous_bytes:
                        return {"ok": False, "code": "CAMPAIGN_HISTORY_CONFLICT"}
                else:
                    safe_atomic_write_bytes(
                        previous_path,
                        previous_bytes,
                        kind="campaign predecessor",
                        ownership_root=self.root,
                    )
                state["predecessor_reference"] = previous_rel.as_posix()
            save_campaign_state(self.root, state)
            return {"ok": True, "admitted": executable, "state": state, "status": camp_state}
        finally:
            lk.release()

    def run(
        self,
        *,
        max_steps: int = 1,
        worker_func: callable | None = None,
    ) -> dict:
        """Drive successive bounded steps until a stopping condition.

        AUT-006 (SRC-344): `step()` executes exactly one generation, and the
        only caller was a single manual `saipen campaign step`. A campaign
        admitted for a multi-hour horizon therefore had no driver at all --
        nothing advanced it from one generation to the next, so every
        successive step was a human action.

        This is that driver, and it is deliberately bounded on every axis:

        * `max_steps` caps how many steps one invocation may take.
        * The persisted budget (`max_cycles`, `max_generations`, wall clock)
          still stops the loop from inside `step()`.
        * A step that reports no productive progress stops the loop, so an
          unproductive campaign cannot spin.
        * Any non-quiescent blocking state (operator, authority, external,
          safety stop, cancellation, completion) ends the loop.
        * An error or a refusal ends the loop rather than retrying blindly;
          reconciliation is a decision, not a spin.

        A driver is not authority: every step re-verifies the operator grant
        exactly as a manual step does, and this method adds no bypass.
        """
        if not isinstance(max_steps, int) or isinstance(max_steps, bool) or max_steps < 1:
            return {
                "ok": False,
                "code": "INVALID_STEP_BOUND",
                "detail": f"max_steps must be a positive integer, got {max_steps!r}",
            }

        # States in which another step cannot make progress on its own. The
        # loop stops BEFORE taking one of these as a step, so a driver never
        # turns "waiting for an operator" into a busy loop.
        terminal = {COMPLETE, CANCELLED}
        blocked = {
            OPERATOR_BLOCKED,
            AUTHORITY_BLOCKED,
            EXTERNAL_BLOCKED,
            SAFETY_STOP,
            CHECKPOINTING,
            PROPOSED,
        }

        steps: list[dict] = []
        for _ in range(max_steps):
            current = inspect_campaign_state(self.root)
            if current["status"] != STATE_VALID:
                return {
                    "ok": False,
                    "code": "CAMPAIGN_STATE_UNREADABLE",
                    "detail": current.get("error") or current["status"],
                    "steps": steps,
                }
            cur_state = (current.get("state") or {}).get("campaign_state")
            if cur_state in terminal:
                return {
                    "ok": True,
                    "status": "STOPPED",
                    "reason": f"campaign_{str(cur_state).lower()}",
                    "steps": steps,
                }
            if cur_state in blocked:
                return {
                    "ok": True,
                    "status": "STOPPED",
                    "reason": f"campaign_{str(cur_state).lower()}_requires_operator",
                    "steps": steps,
                }

            result = self.step(worker_func=worker_func)
            steps.append(result)
            if result.get("ok") is not True:
                return {
                    "ok": False,
                    "status": "STOPPED",
                    "reason": "step_failed",
                    "code": result.get("code"),
                    "detail": result.get("detail") or result.get("error"),
                    "steps": steps,
                }

            progress = result.get("progress") or {}
            if progress and progress.get("made_progress") is not True:
                return {
                    "ok": True,
                    "status": "STOPPED",
                    "reason": "no_productive_progress",
                    "steps": steps,
                }
            after = result.get("state") or {}
            if after.get("campaign_state") in (QUIESCENT_WAIT, *terminal, *blocked):
                return {
                    "ok": True,
                    "status": "STOPPED",
                    "reason": f"campaign_{str(after.get('campaign_state')).lower()}",
                    "steps": steps,
                }

        return {
            "ok": True,
            "status": "STEP_BOUND_REACHED",
            "detail": (
                "The declared step bound was reached; the campaign is still "
                "schedulable and another bounded run may continue it."
            ),
            "steps": steps,
        }

    def cancel(self, *, reason: str = "user_cancelled") -> dict:
        try:
            lk = self._acquire_lock()
        except lock.FileLockBusy:
            return {
                "ok": False,
                "code": "CAMPAIGN_LOCKED",
                "detail": "Another controller owns the campaign lock",
            }

        try:
            inspect = inspect_campaign_state(self.root)
            if inspect["status"] != STATE_VALID:
                return {"ok": False, "error": inspect["status"], "detail": inspect.get("error")}
            state = inspect["state"]
            if state["campaign_state"] in (COMPLETE, CANCELLED):
                return {"ok": True, "state": state, "status": state["campaign_state"]}
            state["cancellation_epoch"] = int(state.get("cancellation_epoch", 0)) + 1
            if state.get("worker_attempt", {}).get("status") in (
                "EXECUTOR_STARTED",
                "UNKNOWN_OUTCOME",
            ):
                state["worker_attempt"]["status"] = "CANCEL_REQUESTED"
            state["campaign_state"] = CANCELLED
            state["next_action"] = f"campaign_cancelled: {reason}"
            save_campaign_state(self.root, state)
            return {"ok": True, "state": state, "status": CANCELLED}
        finally:
            lk.release()

    def step(self, *, worker_func: callable | None = None) -> dict:
        """Claim a durable attempt, execute without the lifecycle lock, then reconcile."""
        try:
            lk = self._acquire_lock()
        except lock.FileLockBusy:
            return {
                "ok": False,
                "code": "CAMPAIGN_LOCKED",
                "detail": "Another controller owns the campaign lock",
            }

        try:
            inspect = inspect_campaign_state(self.root)
            if inspect["status"] != STATE_VALID:
                return {
                    "ok": False,
                    "code": inspect["status"],
                    "detail": inspect.get("error", "Campaign state is not valid"),
                }

            state = inspect["state"]
            cur_state = state.get("campaign_state")
            if cur_state in (CANCELLED, COMPLETE):
                return {"ok": True, "stopped": True, "state": state, "status": cur_state}

            if cur_state == PROPOSED:
                return {
                    "ok": False,
                    "code": "CAMPAIGN_NOT_ADMITTED",
                    "detail": (
                        "Campaign in proposal state; valid operator grant required for execution"
                    ),
                    "state": state,
                }

            attempt = state.get("worker_attempt")
            if isinstance(attempt, dict) and attempt.get("status") in (
                "EXECUTOR_STARTED",
                "UNKNOWN_OUTCOME",
            ):
                if attempt.get("status") == "EXECUTOR_STARTED" and attempt.get("result_reference"):
                    result = self._commit_worker_outcome(state, attempt)
                    if result.get("ok"):
                        result["event"] = "WORKER_ATTEMPT_RECONCILED"
                    return result
                return {
                    "ok": False,
                    "code": "ATTEMPT_RECOVERY_REQUIRED",
                    "state": state,
                    "detail": (
                        "Reconcile the original worker attempt before another generation; "
                        "elapsed time grants no retry"
                    ),
                }

            # Authority re-verification before protected side effects
            proof_ref = state.get("authority_proof_reference")
            if not proof_ref:
                state["campaign_state"] = AUTHORITY_BLOCKED
                state["next_action"] = "operator_grant_required"
                save_campaign_state(self.root, state)
                return {
                    "ok": True,
                    "event": "AUTHORITY_BLOCKED",
                    "code": "AUTHORITY_PROOF_MISSING",
                    "detail": "Admitted campaign missing authority proof reference",
                    "state": state,
                }

            grant_chk = _verify_state_grant(self.root, state)
            if not grant_chk["valid"]:
                state["campaign_state"] = AUTHORITY_BLOCKED
                state["next_action"] = "operator_grant_required"
                save_campaign_state(self.root, state)
                return {
                    "ok": True,
                    "event": "AUTHORITY_BLOCKED",
                    "code": "GRANT_INVALIDATED",
                    "status": grant_chk.get("status", "GRANT_INVALIDATED"),
                    "detail": grant_chk.get("error"),
                    "state": state,
                }

            # Enforce resource budgets
            budget = state.get("resource_budget", {})
            if not _valid_budget(budget):
                return {"ok": False, "code": "INVALID_RESOURCE_BUDGET", "state": state}
            if int(state.get("cycle_count", 0)) >= budget.get(
                "max_cycles", HORIZONS["SHORT"]["max_cycles"]
            ):
                state["campaign_state"] = CHECKPOINTING
                state["next_action"] = "budget_exhausted: max_cycles reached"
                save_campaign_state(self.root, state)
                return {
                    "ok": True,
                    "event": "BUDGET_EXHAUSTED",
                    "reason": "max_cycles",
                    "state": state,
                }
            max_gen = int(budget.get("max_generations", 999999))
            if int(state.get("worker_generation", 0)) >= max_gen:
                state["campaign_state"] = CHECKPOINTING
                state["next_action"] = "budget_exhausted: max_generations reached"
                save_campaign_state(self.root, state)
                return {
                    "ok": True,
                    "event": "BUDGET_EXHAUSTED",
                    "reason": "max_generations",
                    "state": state,
                }

            max_wall = float(budget.get("max_wall_seconds", 999999999.0))
            created_str = state.get("created_at")
            if created_str:
                try:
                    c_dt = _dt.datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                    elapsed = (_dt.datetime.now(_dt.timezone.utc) - c_dt).total_seconds()
                    if elapsed >= max_wall:
                        state["campaign_state"] = CHECKPOINTING
                        state["next_action"] = "budget_exhausted: max_wall_seconds reached"
                        save_campaign_state(self.root, state)
                        return {
                            "ok": True,
                            "event": "BUDGET_EXHAUSTED",
                            "reason": "max_wall_seconds",
                            "state": state,
                        }
                except Exception:
                    pass

            # Continuation Assessment
            assessment = ca.assess_continuation(self.root)
            state["cycle_count"] = int(state.get("cycle_count", 0)) + 1
            classification = assessment["classification"]
            state["next_action"] = assessment.get("next_action", "")

            # 1. Quiescent
            if classification == ca.QUIESCENT:
                state["campaign_state"] = QUIESCENT_WAIT
                state["wake_condition"] = {"event": "new_source_or_audit"}
                save_campaign_state(self.root, state)
                return {
                    "ok": True,
                    "event": "QUIESCENT_WAIT",
                    "classification": classification,
                    "state": state,
                }

            # 2. Wait / Boundary Classifications
            if classification == ca.WAIT_OPERATOR:
                state["campaign_state"] = OPERATOR_BLOCKED
                save_campaign_state(self.root, state)
                return {
                    "ok": True,
                    "event": "OPERATOR_BLOCKED",
                    "classification": classification,
                    "state": state,
                }

            if classification == ca.WAIT_AUTHORITY:
                state["campaign_state"] = AUTHORITY_BLOCKED
                save_campaign_state(self.root, state)
                return {
                    "ok": True,
                    "event": "AUTHORITY_BLOCKED",
                    "classification": classification,
                    "state": state,
                }

            if classification == ca.WAIT_EXTERNAL:
                state["campaign_state"] = EXTERNAL_BLOCKED
                save_campaign_state(self.root, state)
                return {
                    "ok": True,
                    "event": "EXTERNAL_BLOCKED",
                    "classification": classification,
                    "state": state,
                }

            if classification in (ca.SAFETY_STOP, ca.CONFORMANCE_STOP):
                state["campaign_state"] = SAFETY_STOP
                save_campaign_state(self.root, state)
                return {
                    "ok": True,
                    "event": "SAFETY_STOP",
                    "classification": classification,
                    "state": state,
                }

            if classification == ca.INVALID_RUNTIME:
                state["campaign_state"] = SAFETY_STOP
                save_campaign_state(self.root, state)
                return {
                    "ok": False,
                    "code": "INVALID_RUNTIME",
                    "event": "INVALID_RUNTIME",
                    "classification": classification,
                    "detail": assessment.get("detail"),
                    "state": state,
                }

            # 3. Future Gate Discovery (NOT SAIPAL!)
            if classification == ca.DISCOVERY_AVAILABLE:
                state["campaign_state"] = DISCOVERING
                state["next_action"] = assessment.get("next_action") or "saipen future refresh"
                save_campaign_state(self.root, state)
                return {
                    "ok": True,
                    "event": "DISCOVERY_AVAILABLE",
                    "type": "future_gate",
                    "classification": classification,
                    "state": state,
                }

            # 4. Forensic Discovery / SAIPAL Maintenance
            if classification == ca.MAINTENANCE_AVAILABLE:
                forensic_grant = _verify_state_grant(self.root, state, FORENSIC_ANALYSIS_SCOPE)
                if not forensic_grant.get("valid"):
                    state["campaign_state"] = AUTHORITY_BLOCKED
                    save_campaign_state(self.root, state)
                    return {
                        "ok": True,
                        "event": "AUTHORITY_BLOCKED",
                        "detail": (
                            "Forensic discovery requires continuous_maintenance "
                            "or forensic_analysis authority"
                        ),
                        "state": state,
                    }

                state["campaign_state"] = DISCOVERING
                if self.backend is None:
                    # No backend was injected, so there is nothing to ask. This
                    # is a deployment fact, not a discovery failure: the typed
                    # refusal keeps the campaign schedulable and names the one
                    # thing the caller has to supply.
                    state["campaign_state"] = EXTERNAL_BLOCKED
                    state["last_discovery_failure"] = {
                        "status": backend_protocol.RUNTIME_UNAVAILABLE,
                        "error": "No analysis backend is configured for this campaign",
                        "path": None,
                    }
                    state["next_action"] = "configure_analysis_backend"
                    save_campaign_state(self.root, state)
                    return {
                        "ok": False,
                        "event": "FORENSIC_DISCOVERY_FAILED",
                        "status": backend_protocol.RUNTIME_UNAVAILABLE,
                        "discovery": state["last_discovery_failure"],
                        "state": state,
                    }
                disc_res = self.backend.discover(self.root)
                if not isinstance(disc_res, dict) or disc_res.get("ok") is not True:
                    failure = (
                        disc_res
                        if isinstance(disc_res, dict)
                        else {
                            "status": backend_protocol.BACKEND_PROTOCOL_ERROR,
                            "error": "Forensic discovery returned an invalid envelope",
                        }
                    )
                    status = failure.get("status", backend_protocol.PERMANENT_FAILURE)
                    state["campaign_state"] = (
                        AUTHORITY_BLOCKED
                        if status == backend_protocol.AUTHORITY_REQUIRED
                        else RETRY_WAIT
                        if status == backend_protocol.RETRYABLE_FAILURE
                        else EXTERNAL_BLOCKED
                    )
                    state["last_discovery_failure"] = {
                        "status": status,
                        "error": failure.get("error") or failure.get("detail"),
                        "path": failure.get("path"),
                    }
                    state["next_action"] = "forensic_backend_recovery_required"
                    save_campaign_state(self.root, state)
                    return {
                        "ok": False,
                        "event": "FORENSIC_DISCOVERY_FAILED",
                        "status": status,
                        "discovery": failure,
                        "state": state,
                    }
                if disc_res.get("status") in (
                    backend_protocol.NEW_QUALIFIED_FINDINGS,
                    backend_protocol.ANALYSIS_PROGRESS,
                ):
                    state["last_analysis_generation"] = (
                        int(state.get("last_analysis_generation", 0)) + 1
                    )

                # AUT-007: one analysis slice is progress, not a finished
                # objective. This branch used to fall through to the `else`
                # below and report DISCOVERY_NO_NEW_FINDINGS into QUIESCENT_WAIT,
                # so an analysis objective with pending hot/cold sessions became
                # unschedulable after its first slice and the campaign slept
                # through its own remaining work. A slice keeps the campaign in
                # FORENSIC_ANALYSIS with an explicit next action.
                if disc_res.get("status") == backend_protocol.ANALYSIS_PROGRESS:
                    state["campaign_state"] = FORENSIC_ANALYSIS
                    state["last_analysis_slice"] = {
                        "at": _utc_now(),
                        "generation": state.get("last_analysis_generation"),
                        "slice": disc_res.get("slice"),
                    }
                    state["next_action"] = "forensic_analysis_slice"
                    save_campaign_state(self.root, state)
                    return {
                        "ok": True,
                        "event": "ANALYSIS_PROGRESS",
                        "detail": (
                            "One bounded forensic analysis slice executed; the "
                            "objective has further eligible slices, so the "
                            "campaign stays schedulable rather than quiescent."
                        ),
                        "slice": disc_res.get("slice"),
                        "state": state,
                    }

                if disc_res.get("status") == backend_protocol.NEW_QUALIFIED_FINDINGS:
                    state["campaign_state"] = FORENSIC_ANALYSIS
                    findings = disc_res.get("findings", [])
                    delivered = []
                    for f in findings:
                        pub_grant = _verify_state_grant(
                            self.root, state, EXTERNAL_AUDIT_PUBLICATION
                        )
                        pub_auth = pub_grant.get("valid") is True
                        d_res = self.backend.deliver_finding_to_audit_inbox(
                            self.root, f, publication_authorized=pub_auth
                        )
                        delivered.append(d_res)

                    # W2-004: discovery success is NOT publication success. The
                    # controller used to return `ok: true, event:
                    # DISCOVERY_DELIVERED` after every delivery had failed --
                    # reproduced with one finding and ARTIFACT_MISSING, zero
                    # published layers, and a persisted AUDIT_DELIVERY state.
                    # Each result is classified, the aggregate event names what
                    # actually happened, and only a genuinely published finding
                    # counts as delivered.
                    published = [
                        row for row in delivered if row.get("ok") is True
                    ]
                    staged = [
                        row
                        for row in delivered
                        if row.get("status") == backend_protocol.STAGED_PUBLICATION
                    ]
                    authority_required = [
                        row
                        for row in delivered
                        if row.get("status") == "AUTHORITY_REQUIRED"
                    ]
                    unknown = [
                        row
                        for row in delivered
                        if row.get("receipt_reconciliation_required") is True
                        or row.get("outcome_unknown") is True
                    ]
                    failed = [
                        row
                        for row in delivered
                        if row.get("ok") is not True
                        and row.get("status") != backend_protocol.STAGED_PUBLICATION
                        and row.get("receipt_reconciliation_required") is not True
                        and row.get("outcome_unknown") is not True
                    ]
                    if not delivered:
                        delivery_status = "NOTHING_TO_DELIVER"
                    elif len(published) == len(delivered):
                        delivery_status = "ALL_DELIVERED"
                    elif published:
                        delivery_status = "PARTIALLY_DELIVERED"
                    elif unknown:
                        delivery_status = "PUBLICATION_OUTCOME_UNKNOWN"
                    elif staged:
                        delivery_status = "PUBLICATION_STAGED"
                    elif authority_required:
                        delivery_status = "PUBLICATION_AUTHORITY_REQUIRED"
                    else:
                        delivery_status = "NONE_DELIVERED"

                    # A batch with nothing published is not a delivery. It is
                    # either a refusal (retryable or blocked) or an unknown
                    # outcome that must be reconciled before any replay.
                    if delivery_status in ("ALL_DELIVERED", "PARTIALLY_DELIVERED"):
                        event = "DISCOVERY_DELIVERED"
                        state["campaign_state"] = AUDIT_DELIVERY
                        state["last_delivery"] = {
                            "status": delivery_status,
                            "published_finding_ids": [
                                row.get("finding_id") for row in published
                            ],
                            "failed_finding_ids": [
                                row.get("finding_id") for row in failed
                            ],
                        }
                        save_campaign_state(self.root, state)
                        return {
                            "ok": True,
                            "event": event,
                            "delivery_status": delivery_status,
                            "delivered": delivered,
                            "published_finding_ids": [
                                row.get("finding_id") for row in published
                            ],
                            "failed_finding_ids": [
                                row.get("finding_id") for row in failed
                            ],
                            "state": state,
                        }

                    state["campaign_state"] = (
                        RETRY_WAIT
                        if delivery_status == "PUBLICATION_OUTCOME_UNKNOWN"
                        else EXTERNAL_BLOCKED
                        if delivery_status == "PUBLICATION_AUTHORITY_REQUIRED"
                        else RETRY_WAIT
                    )
                    state["last_delivery_failure"] = {
                        "status": delivery_status,
                        "failed_finding_ids": [
                            row.get("finding_id") for row in failed
                        ],
                        "diagnostics": [
                            {
                                "finding_id": row.get("finding_id"),
                                "status": row.get("status"),
                                "error": row.get("error") or row.get("detail"),
                            }
                            for row in delivered
                            if row not in published
                        ],
                    }
                    save_campaign_state(self.root, state)
                    return {
                        "ok": False,
                        "event": "DISCOVERY_DELIVERY_FAILED",
                        "delivery_status": delivery_status,
                        "delivered": delivered,
                        "failed_finding_ids": [
                            row.get("finding_id") for row in failed
                        ],
                        "state": state,
                    }
                else:
                    state["campaign_state"] = QUIESCENT_WAIT
                    save_campaign_state(self.root, state)
                    return {
                        "ok": True,
                        "event": "DISCOVERY_NO_NEW_FINDINGS",
                        "discovery": disc_res,
                        "state": state,
                    }

            # 5. Audit Intake & Repair
            if classification == ca.AUDIT_AVAILABLE:
                state["campaign_state"] = AUDIT_DELIVERY
                save_campaign_state(self.root, state)
                return {
                    "ok": True,
                    "event": "AUDIT_AVAILABLE",
                    "classification": classification,
                    "state": state,
                }

            # 6. Source Available
            if classification == ca.SOURCE_AVAILABLE:
                state["campaign_state"] = RUNNING
                state["next_action"] = assessment.get("next_action") or "saipen source project"
                save_campaign_state(self.root, state)
                return {
                    "ok": True,
                    "event": "SOURCE_AVAILABLE",
                    "classification": classification,
                    "state": state,
                }

            # 7. Executable Work (ACTIVE_WORK, QUEUED_WORK, RECOVERY_AVAILABLE)
            if classification in (ca.ACTIVE_WORK, ca.QUEUED_WORK, ca.RECOVERY_AVAILABLE):
                execution_grant = _verify_state_grant(self.root, state, CAMPAIGN_EXECUTION)
                if not execution_grant.get("valid"):
                    state["campaign_state"] = AUTHORITY_BLOCKED
                    state["next_action"] = "operator_grant_required"
                    save_campaign_state(self.root, state)
                    return {
                        "ok": False,
                        "event": "AUTHORITY_BLOCKED",
                        "status": "SCOPE_UNAUTHORIZED",
                        "state": state,
                    }
                if not callable(worker_func):
                    tool_py = self.root / "tools" / "saipen.py"
                    if not tool_py.is_file():
                        return {
                            "ok": False,
                            "code": "EXECUTOR_UNAVAILABLE",
                            "status": "EXECUTOR_UNAVAILABLE",
                            "detail": f"Canonical worker entry point not found: {tool_py}",
                            "state": state,
                        }

                state["campaign_state"] = RUNNING
                w_gen = int(state.get("worker_generation", 0)) + 1
                state["worker_generation"] = w_gen
                attempt = {
                    "attempt_id": str(uuid.uuid4()),
                    "campaign_id": state["campaign_id"],
                    "generation": w_gen,
                    "cancellation_epoch": state.get("cancellation_epoch", 0),
                    "status": "EXECUTOR_STARTED",
                    "started_at": _utc_now(),
                    "owner_pid": os.getpid(),
                    "execution_intent": assessment,
                    "recovery_eligibility": "reconcile_original_operation",
                    # Recorded durably so reconciliation can tell the explicit
                    # injected-executor test path from a real canonical worker.
                    "executor_kind": (
                        "injected_test_worker" if callable(worker_func) else "canonical"
                    ),
                }
                attempt["result_reference"] = (
                    STATE_REL.parent / "attempts" / f"{attempt['attempt_id']}.json"
                ).as_posix()
                state["worker_attempt"] = attempt
                save_campaign_state(self.root, state)
                lk.release()
                lk = None
                worker_error = None
                # The controller observes LOG/STATE itself, immediately around the
                # call. A worker's own before/after strings -- or a bare
                # `progress_verified: true` -- are caller assertions about itself,
                # not evidence that canonical Work advanced (CORE-009).
                before_event = self._read_tail_event()
                before_state = self._read_state_tuple()
                try:
                    w_res = (
                        _invoke_worker(worker_func, self.root, w_gen)
                        if callable(worker_func)
                        else self._execute_canonical_worker(generation=w_gen, state=state)
                    )
                    # Validate persistence before reacquiring ownership. Unserializable
                    # results also mean the external execution's outcome is uncertain.
                    json.dumps(w_res, allow_nan=False)
                except Exception as exc:
                    worker_error = f"{type(exc).__name__}: {exc}"
                    w_res = {"ok": False, "error": worker_error}
                observation = {
                    "before_event": before_event,
                    "after_event": self._read_tail_event(),
                    "before_state": before_state,
                    "after_state": self._read_state_tuple(),
                }
                # Preserve the original result even if lifecycle commit is contended,
                # cancelled, or interrupted. This receipt describes a local executor
                # outcome; it does not authenticate Work progress or host acceptance.
                outcome = {
                    "schema_version": 1,
                    "binding": _attempt_binding(attempt),
                    "result": w_res,
                    "error": worker_error,
                    "observation": observation,
                    "observed_at": _utc_now(),
                }
                outcome["receipt_digest"] = _outcome_digest(outcome)
                outcome_path = self.root / attempt["result_reference"]
                try:
                    outcome_path.parent.mkdir(parents=True, exist_ok=True)
                    body = (json.dumps(outcome, sort_keys=True, allow_nan=False) + "\n").encode()
                    if outcome_path.exists():
                        raise ValueError(
                            "Original attempt outcome already exists; refusing overwrite"
                        )
                    safe_atomic_write_bytes(
                        outcome_path, body, kind="campaign worker outcome", ownership_root=self.root
                    )
                except (OSError, ValueError) as exc:
                    return {
                        "ok": False,
                        "code": "ATTEMPT_RECOVERY_REQUIRED",
                        "attempt_id": attempt["attempt_id"],
                        "detail": str(exc),
                    }
                try:
                    lk = self._acquire_lock()
                except lock.FileLockBusy:
                    return {
                        "ok": False,
                        "code": "ATTEMPT_RECOVERY_REQUIRED",
                        "attempt_id": attempt["attempt_id"],
                        "detail": (
                            "Worker returned but lifecycle ownership is unavailable; "
                            "original intent is durable"
                        ),
                    }
                inspection = inspect_campaign_state(self.root)
                if inspection["status"] != STATE_VALID:
                    return {
                        "ok": False,
                        "code": inspection["status"],
                        "attempt_id": attempt["attempt_id"],
                    }
                current = inspection["state"]
                return self._commit_worker_outcome(current, attempt)

            return {
                "ok": False,
                "code": "UNHANDLED_CLASSIFICATION",
                "classification": classification,
                "detail": f"Unrecognized continuation classification: {classification}",
                "state": state,
            }
        finally:
            if lk is not None:
                lk.release()

    def _commit_worker_outcome(self, state: dict, expected: dict) -> dict:
        """Reconcile one original outcome while holding the lifecycle lock."""
        attempt = state.get("worker_attempt") or {}
        if (
            state["campaign_id"] != expected["campaign_id"]
            or state.get("cancellation_epoch", 0) != expected["cancellation_epoch"]
            or attempt.get("attempt_id") != expected["attempt_id"]
            or state["campaign_state"] in (COMPLETE, CANCELLED)
        ):
            return {
                "ok": False,
                "code": "WORKER_GENERATION_FENCED",
                "state": state,
                "attempt_id": expected["attempt_id"],
                "detail": "The worker no longer owns this campaign generation",
            }
        try:
            attempt_id = str(uuid.UUID(attempt["attempt_id"]))
            reference = (STATE_REL.parent / "attempts" / f"{attempt_id}.json").as_posix()
            if attempt.get("result_reference") != reference:
                raise ValueError("Attempt result reference mismatch")
            outcome = json.loads((self.root / reference).read_text(encoding="utf-8"))
            if (
                not isinstance(outcome, dict)
                or type(outcome.get("schema_version")) is not int
                or outcome["schema_version"] != 1
                or outcome.get("binding") != _attempt_binding(attempt)
                or outcome.get("receipt_digest") != _outcome_digest(outcome)
                or "result" not in outcome
                or "error" not in outcome
                or not isinstance(outcome.get("observed_at"), str)
                or not outcome["observed_at"]
                or (outcome["error"] is not None and not isinstance(outcome["error"], str))
            ):
                raise ValueError("Attempt result integrity or binding mismatch")
        except FileNotFoundError:
            return {
                "ok": False,
                "code": "ATTEMPT_RECOVERY_REQUIRED",
                "state": state,
                "detail": "Original worker outcome is not observed; no replay is authorized",
            }
        except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
            return {
                "ok": False,
                "code": "ATTEMPT_RESULT_CORRUPT",
                "state": state,
                "detail": str(exc),
            }

        w_res, worker_error = outcome["result"], outcome["error"]
        grant_chk = _verify_state_grant(self.root, state)
        if not grant_chk.get("valid"):
            worker_error = "Authority invalidated while the worker was running"
            state["campaign_state"] = AUTHORITY_BLOCKED
        failed = worker_error is not None or not isinstance(w_res, dict) or w_res.get("ok") is False
        attempt["status"] = "UNKNOWN_OUTCOME" if failed else "EXECUTION_RESULT_OBSERVED"
        attempt["finished_at"] = outcome["observed_at"]
        attempt["result"] = w_res
        if failed:
            attempt["error"] = (
                worker_error
                or "Worker reported failure; partial side effects require reconciliation"
            )
            state["retry_count"] = int(state.get("retry_count", 0)) + 1
            state["no_progress_count"] = int(state.get("no_progress_count", 0)) + 1
            state["next_action"] = "reconcile_worker_attempt"
            save_campaign_state(self.root, state)
            return {
                "ok": False,
                "event": "WORKER_GENERATION_FAILED",
                "code": "WORKER_GENERATION_FAILED",
                "worker_generation": attempt["generation"],
                "worker_result": w_res,
                "state": state,
            }

        if w_res.get("route_only") is True:
            state["no_progress_count"] = int(state.get("no_progress_count", 0)) + 1
            save_campaign_state(self.root, state)
            return {
                "ok": True,
                "event": "WORKER_ROUTE_ONLY",
                "worker_generation": attempt["generation"],
                "worker_result": w_res,
                "progress": {
                    "made_progress": False,
                    "journal_advanced": False,
                    "state_mutated": False,
                },
                "state": state,
            }

        progress = self._verify_progress_evidence(
            w_res,
            observation=outcome.get("observation"),
            injected_worker=attempt.get("executor_kind") == "injected_test_worker",
        )
        if progress["made_progress"]:
            state["last_productive_progress"] = _utc_now()
            state["no_progress_count"] = 0
        else:
            state["no_progress_count"] = int(state.get("no_progress_count", 0)) + 1
        save_campaign_state(self.root, state)
        return {
            "ok": True,
            "event": "WORKER_GENERATION_EXECUTED",
            "worker_generation": attempt["generation"],
            "worker_result": w_res,
            "progress": progress,
            "state": state,
        }

    def _execute_canonical_worker(self, *, generation: int, state: dict) -> dict:
        """Execute one bounded worker slice using canonical worker API."""
        dec = supervisor.decide(self.root)
        next_cmd = dec.get("next_command")

        before_event = self._read_tail_event()
        before_state = self._read_state_tuple()

        if dec.get("may_mutate") and next_cmd:
            cmd_parts = shlex.split(next_cmd)
            if cmd_parts and cmd_parts[0] == "saipen":
                tool_py = self.root / "tools" / "saipen.py"
                if not tool_py.is_file():
                    return {
                        "ok": False,
                        "executed": False,
                        "code": "EXECUTOR_UNAVAILABLE",
                        "error": f"Executor {tool_py} not found",
                        "before_event": before_event,
                        "after_event": before_event,
                    }
                argv = [sys.executable, str(tool_py), *cmd_parts[1:], "--json"]
                try:
                    res = subprocess.run(
                        argv,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        check=False,
                        timeout=60.0,
                        cwd=str(self.root),
                    )
                    out_json = None
                    with contextlib.suppress(json.JSONDecodeError):
                        out_json = json.loads(res.stdout)
                    ok = res.returncode == 0
                    return {
                        "ok": ok,
                        "executed": True,
                        "decision": dec.get("verdict"),
                        "command": next_cmd,
                        "returncode": res.returncode,
                        "output": out_json or res.stdout[:500],
                        "error": None
                        if ok
                        else f"Process exited with code {res.returncode}: {res.stderr[:300]}",
                        "before_event": before_event,
                        "after_event": self._read_tail_event(),
                        "before_state": before_state,
                        "after_state": self._read_state_tuple(),
                    }
                except Exception as exc:
                    return {
                        "ok": False,
                        "executed": False,
                        "decision": dec.get("verdict"),
                        "error": str(exc),
                        "before_event": before_event,
                        "after_event": before_event,
                    }
        # Non-mutating or no command: ROUTE_ONLY planning verdict, not executed mutation
        return {
            "ok": True,
            "executed": False,
            "route_only": True,
            "decision": dec.get("verdict"),
            "command": next_cmd,
            "decision_record": dec,
            "before_event": before_event,
            "after_event": before_event,
            "before_state": before_state,
            "after_state": before_state,
        }

    #: Reverse-tail reading bounds (PERF-006). The scan walks backwards in
    #: windows of this size, so memory stays bounded no matter how large the
    #: journal or its final record grows.
    TAIL_WINDOW_BYTES = 8192
    #: Bytes read from the located line to produce the reported value.
    TAIL_PREFIX_BYTES = 4096
    _TAIL_SPACE = frozenset(b" \t\r\n\v\f")

    def _tail_line_bounds(self, handle, size: int) -> tuple[int, int] | None:
        """Offsets of the last non-empty LOG line, or ``None`` when there is none.

        Walks backwards from EOF in bounded windows: first past trailing
        whitespace to the last content byte, then back to the newline that
        starts that record. Both scans allocate one window, so this never
        materialises the journal and never returns a mid-record fragment.
        """
        end = None
        cursor = size
        while cursor > 0:
            start = max(0, cursor - self.TAIL_WINDOW_BYTES)
            handle.seek(start)
            chunk = handle.read(cursor - start)
            for index in range(len(chunk) - 1, -1, -1):
                if chunk[index] not in self._TAIL_SPACE:
                    end = start + index + 1
                    break
            if end is not None:
                break
            cursor = start
        if end is None:
            return None

        line_start = 0
        cursor = end
        while cursor > 0:
            start = max(0, cursor - self.TAIL_WINDOW_BYTES)
            handle.seek(start)
            chunk = handle.read(cursor - start)
            found = chunk.rfind(b"\n")
            if found != -1:
                line_start = start + found + 1
                break
            cursor = start
        return line_start, end

    def _read_tail_event(self) -> str:
        """The last complete non-empty LOG line, read from the end backwards.

        Reading the whole file allocated memory proportional to the journal,
        and reading one fixed window from the end returned a mid-line fragment
        whenever the final record exceeded that window -- a different string
        than a full read produced. Locating the record's exact bounds first
        keeps the result identical to a full read: `strip()` then the first 80
        characters of the real last line.
        """
        log_file = self.root / ".saipen" / "LOG.md"
        if not log_file.is_file():
            return "none"
        try:
            size = log_file.stat().st_size
            if size == 0:
                return "none"
            with open(log_file, "rb") as handle:
                bounds = self._tail_line_bounds(handle, size)
                if bounds is None:
                    return "none"
                line_start, end = bounds
                handle.seek(line_start)
                prefix = handle.read(min(end - line_start, self.TAIL_PREFIX_BYTES))
            text = prefix.decode("utf-8", errors="replace").strip()
            if text:
                return text[:80]
        except Exception:
            pass
        return "none"

    def _read_state_tuple(self) -> str:
        st_file = self.root / ".saipen" / "STATE.md"
        if st_file.is_file():
            try:
                return st_file.read_text(encoding="utf-8")[:300]
            except Exception:
                pass
        return "none"

    def _verify_progress_evidence(
        self,
        worker_result: dict,
        *,
        observation: dict | None = None,
        injected_worker: bool = False,
    ) -> dict:
        """Testable progress, derived only from controller-observed evidence.

        `worker_result`'s own before/after strings and `progress_verified` /
        `mutated` booleans are what the worker says about itself. CORE-009
        reproduced a worker that answered `progress_verified: true` with an
        unchanged journal and unchanged STATE, and the controller reset
        `no_progress_count` on that assertion. The controller therefore passes
        its own `observation`; self-assertion is recorded but never counted,
        except through the explicit `worker_func` test interface, where the
        caller injected the executor deliberately.
        """
        source = observation if isinstance(observation, dict) else {}
        b_ev = source.get("before_event")
        a_ev = source.get("after_event")
        b_st = source.get("before_state")
        a_st = source.get("after_state")
        journal_advanced = b_ev != a_ev and a_ev not in (None, "none")
        state_mutated = b_st != a_st and a_st not in (None, "none")
        asserted = bool(
            worker_result.get("progress_verified") is True
            or worker_result.get("mutated") is True
        )
        return {
            "made_progress": bool(
                journal_advanced or state_mutated or (asserted and injected_worker)
            ),
            "journal_advanced": bool(journal_advanced),
            "state_mutated": bool(state_mutated),
            "evidence_source": "controller_observation" if source else "absent",
            "untrusted_worker_assertion": asserted,
            "injected_test_worker": bool(injected_worker),
        }
