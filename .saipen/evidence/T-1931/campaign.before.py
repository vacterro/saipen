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
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
import uuid
from collections.abc import Mapping
from pathlib import Path

from . import continuation_assessment as ca
from . import goal_authority, host_dispatch, lock, paths, saipal_adapter, supervisor, watchdog
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

# Independent scoped permissions
CAMPAIGN_EXECUTION = "CAMPAIGN_EXECUTION"
FORENSIC_ANALYSIS_SCOPE = "FORENSIC_ANALYSIS"
AUDIT_STAGING = "AUDIT_STAGING"
EXTERNAL_AUDIT_PUBLICATION = "EXTERNAL_AUDIT_PUBLICATION"
SAIPEN_AUDIT_INGESTION = "SAIPEN_AUDIT_INGESTION"
PROTOCOL_REPAIR = "PROTOCOL_REPAIR"
CONTINUOUS_MAINTENANCE_SCOPE = "continuous_maintenance"

ALL_SCOPES = frozenset(
    {
        CAMPAIGN_EXECUTION,
        FORENSIC_ANALYSIS_SCOPE,
        AUDIT_STAGING,
        EXTERNAL_AUDIT_PUBLICATION,
        SAIPEN_AUDIT_INGESTION,
        PROTOCOL_REPAIR,
        CONTINUOUS_MAINTENANCE_SCOPE,
    }
)

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
    if not path.is_file():
        return {"status": STATE_ABSENT}
    try:
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            return {"status": STATE_CORRUPT, "error": "Empty campaign state file", "path": str(path)}
        data = json.loads(content)
        if not isinstance(data, dict):
            return {"status": STATE_CORRUPT, "error": "Campaign state is not a dictionary", "path": str(path)}
        if data.get("schema_version") != CAMPAIGN_SCHEMA_VERSION:
            return {"status": STATE_INCOMPATIBLE, "version": data.get("schema_version"), "state": data}
        if "campaign_id" not in data or "campaign_state" not in data:
            return {"status": STATE_CORRUPT, "error": "Missing mandatory campaign fields", "state": data}
        stored_digest = data.get("state_digest")
        if stored_digest:
            state_copy = {k: v for k, v in data.items() if k not in ("state_digest", "updated_at")}
            expected_digest = hashlib.sha256(json.dumps(state_copy, sort_keys=True).encode("utf-8")).hexdigest()
            if stored_digest != expected_digest:
                return {
                    "status": STATE_UNTRUSTED,
                    "error": "Campaign state provenance digest mismatch; untrusted modification",
                    "path": str(path),
                    "state": data,
                }
        return {"status": STATE_VALID, "state": data}
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
    state["state_digest"] = hashlib.sha256(json.dumps(state_copy, sort_keys=True).encode("utf-8")).hexdigest()
    body = (json.dumps(state, indent=2, sort_keys=True) + "\n").encode("utf-8")
    safe_atomic_write_bytes(
        path,
        body,
        kind="campaign state",
        ownership_root=root,
    )


def verify_operator_grant(
    root: Path | str,
    grant_reference: str | None,
    requested_scope: str | None = None,
) -> dict:
    """Validate operator grant against canonical SAIPEN authority mechanism."""
    root = Path(root).resolve()
    if not grant_reference:
        return {
            "valid": False,
            "status": "GRANT_ABSENT",
            "error": "No operator grant reference provided",
            "authorized_scopes": set(),
        }

    # 1. Ingress receipt reference: SRC-###
    if re.fullmatch(r"SRC-[0-9]+", str(grant_reference)):
        from . import operator_task

        auth = operator_task.authority_for_receipt(root, grant_reference)
        if not auth.get("user_explicit"):
            return {
                "valid": False,
                "status": "GRANT_NOT_USER_EXPLICIT",
                "error": f"Receipt {grant_reference} carries no explicit operator authority (witness: {auth.get('witness')})",
                "authorized_scopes": set(),
            }
        scopes = set()
        if auth.get("local_work") or auth.get("user_explicit"):
            scopes.add(CAMPAIGN_EXECUTION)
            scopes.add(AUDIT_STAGING)
            scopes.add(SAIPEN_AUDIT_INGESTION)
            scopes.add(PROTOCOL_REPAIR)
        if auth.get("goal_pivot"):
            scopes.add(FORENSIC_ANALYSIS_SCOPE)
            scopes.add(EXTERNAL_AUDIT_PUBLICATION)
        from .codec import read_doc
        from .state import parse_state

        try:
            st = parse_state(read_doc(root / ".saipen" / "STATE.md"))
            if goal_authority.continuous_maintenance_proven(root, st):
                scopes.add(CONTINUOUS_MAINTENANCE_SCOPE)
        except Exception:
            pass

        if requested_scope and requested_scope not in scopes:
            return {
                "valid": False,
                "status": "SCOPE_UNAUTHORIZED",
                "error": f"Requested scope '{requested_scope}' not authorized by receipt {grant_reference}",
                "authorized_scopes": scopes,
            }
        return {
            "valid": True,
            "status": "VALID_GRANT",
            "grant": {
                "reference": grant_reference,
                "kind": "ingress_receipt",
                "authority": auth,
            },
            "authorized_scopes": scopes,
        }

    # 2. Journal event reference: E-###
    if re.fullmatch(r"E-[0-9]+", str(grant_reference)):
        from .journal import Journal
        from .log import parse_log_line

        log_path = root / ".saipen" / "LOG.md"
        if not log_path.is_file():
            return {
                "valid": False,
                "status": "LOG_MISSING",
                "error": f"LOG.md not found in project: {log_path}",
                "authorized_scopes": set(),
            }

        target_ev_num = int(grant_reference[2:])
        found_ev = None
        try:
            for line in log_path.read_text(encoding="utf-8").splitlines():
                parsed = parse_log_line(line)
                if parsed and parsed.get("event") == target_ev_num:
                    found_ev = parsed
                    break
        except Exception as exc:
            return {
                "valid": False,
                "status": "JOURNAL_ERROR",
                "error": f"Error reading LOG.md: {exc}",
                "authorized_scopes": set(),
            }

        if not found_ev:
            return {
                "valid": False,
                "status": "EVENT_NOT_FOUND",
                "error": f"Journal event {grant_reference} not found in LOG.md",
                "authorized_scopes": set(),
            }

        op_id = found_ev.get("op_id")
        if not op_id:
            return {
                "valid": False,
                "status": "EVENT_NOT_OPERATOR_AUTHORITY",
                "error": f"Journal event {grant_reference} has no operation record",
                "authorized_scopes": set(),
            }

        try:
            j = Journal(root, op_id)
            if not j.exists():
                return {
                    "valid": False,
                    "status": "JOURNAL_MANIFEST_MISSING",
                    "error": f"Journal manifest for {grant_reference} ({op_id}) not found",
                    "authorized_scopes": set(),
                }
            rec = j.read()
        except Exception as exc:
            return {
                "valid": False,
                "status": "JOURNAL_ERROR",
                "error": f"Journal manifest decode error: {exc}",
                "authorized_scopes": set(),
            }

        if rec.get("status") != "COMMITTED":
            return {
                "valid": False,
                "status": "JOURNAL_NOT_COMMITTED",
                "error": f"Journal event {grant_reference} is not committed (status: {rec.get('status')})",
                "authorized_scopes": set(),
            }

        op_name = rec.get("operation")
        meta = rec.get("receipt_metadata") or {}
        has_goal_auth = bool(meta.get("goal_authority"))
        has_op_origin = bool(meta.get("operator_origin"))
        is_operator_op = op_name in {"goal", "goal_entry", "operator_grant", "continuous_maintenance"}

        if not (has_goal_auth or has_op_origin or is_operator_op):
            return {
                "valid": False,
                "status": "EVENT_NOT_OPERATOR_AUTHORITY",
                "error": f"Journal event {grant_reference} is an operation receipt, not an eligible operator campaign authority grant",
                "authorized_scopes": set(),
            }

        lineage = host_dispatch.resolve_project_lineage(root)
        if rec.get("project_lineage") and rec.get("project_lineage") != lineage:
            return {
                "valid": False,
                "status": "GRANT_FOREIGN_LINEAGE",
                "error": f"Event lineage {rec.get('project_lineage')} does not match project lineage {lineage}",
                "authorized_scopes": set(),
            }

        scopes = {CAMPAIGN_EXECUTION, AUDIT_STAGING, SAIPEN_AUDIT_INGESTION, PROTOCOL_REPAIR}
        from .codec import read_doc
        from .state import parse_state
        try:
            st = parse_state(read_doc(root / ".saipen" / "STATE.md"))
            if goal_authority.continuous_maintenance_proven(root, st):
                scopes.update({CONTINUOUS_MAINTENANCE_SCOPE, FORENSIC_ANALYSIS_SCOPE, EXTERNAL_AUDIT_PUBLICATION})
        except Exception:
            pass

        if requested_scope and requested_scope not in scopes:
            return {
                "valid": False,
                "status": "SCOPE_UNAUTHORIZED",
                "error": f"Requested scope '{requested_scope}' not authorized by event {grant_reference}",
                "authorized_scopes": scopes,
            }
        return {
            "valid": True,
            "status": "VALID_GRANT",
            "grant": {
                "reference": grant_reference,
                "kind": "journal_event",
                "record": rec,
            },
            "authorized_scopes": scopes,
        }

    # 3. File grant reference (absolute or relative to project root)
    grant_file = root / grant_reference if not Path(grant_reference).is_absolute() else Path(grant_reference)
    if not grant_file.is_file():
        return {
            "valid": False,
            "status": "GRANT_FILE_MISSING",
            "error": f"Operator grant proof file not found: {grant_reference}",
            "authorized_scopes": set(),
        }

    try:
        raw_bytes = grant_file.read_bytes()
        file_digest = hashlib.sha256(raw_bytes).hexdigest()
        data = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(data, dict):
            return {
                "valid": False,
                "status": "GRANT_FILE_MALFORMED",
                "error": "Grant file is not a JSON object",
                "authorized_scopes": set(),
            }

        issuer = data.get("issuer")
        if not issuer or str(issuer).lower() in ("self", "local", "self-claimed", "self-asserted", "untrusted", "caller", "model_supplied", "anonymous"):
            return {
                "valid": False,
                "status": "GRANT_ISSUER_UNTRUSTED",
                "error": f"Grant issuer '{issuer}' is untrusted or self-authored",
                "authorized_scopes": set(),
            }

        proof = data.get("operator_origin") or data.get("proof")
        if not proof or not isinstance(proof, dict) or proof.get("kind") != "operator-origin":
            return {
                "valid": False,
                "status": "GRANT_PROOF_MISSING",
                "error": "Grant file carries no verifiable operator-origin proof",
                "authorized_scopes": set(),
            }

        lineage = host_dispatch.resolve_project_lineage(root)
        grant_lineage = data.get("project_lineage") or proof.get("lineage")
        if not grant_lineage or grant_lineage != lineage:
            return {
                "valid": False,
                "status": "GRANT_FOREIGN_LINEAGE",
                "error": f"Grant lineage '{grant_lineage}' does not match project lineage '{lineage}'",
                "authorized_scopes": set(),
            }

        grant_project = data.get("project") or proof.get("project")
        current_project = paths.project_identity(root)
        if grant_project and current_project:
            norm_grant = os.path.normcase(os.path.normpath(str(grant_project)))
            norm_current = os.path.normcase(os.path.normpath(str(current_project)))
            if norm_grant != norm_current and grant_project not in (lineage, str(root)):
                return {
                    "valid": False,
                    "status": "GRANT_FOREIGN_PROJECT",
                    "error": f"Grant project '{grant_project}' does not match current project '{current_project}'",
                    "authorized_scopes": set(),
                }

        expires_at = data.get("expires_at") or proof.get("expires")
        if expires_at:
            if isinstance(expires_at, (int, float)):
                import time
                if time.time() > expires_at:
                    return {
                        "valid": False,
                        "status": "GRANT_EXPIRED",
                        "error": f"Grant expired at {expires_at}",
                        "authorized_scopes": set(),
                    }
            elif isinstance(expires_at, str):
                try:
                    exp_dt = _dt.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    if _dt.datetime.now(_dt.timezone.utc) > exp_dt:
                        return {
                            "valid": False,
                            "status": "GRANT_EXPIRED",
                            "error": f"Grant expired at {expires_at}",
                            "authorized_scopes": set(),
                        }
                except Exception:
                    return {
                        "valid": False,
                        "status": "GRANT_EXPIRED",
                        "error": f"Grant expiry format invalid: {expires_at}",
                        "authorized_scopes": set(),
                    }

        if data.get("consumed") is True or proof.get("consumed") is True or data.get("revoked") is True:
            return {
                "valid": False,
                "status": "GRANT_CONSUMED",
                "error": "Operator grant has already been consumed or revoked",
                "authorized_scopes": set(),
            }

        if data.get("consumed_by_campaign"):
            return {
                "valid": False,
                "status": "GRANT_REPLAYED",
                "error": f"Grant already consumed by campaign {data.get('consumed_by_campaign')}",
                "authorized_scopes": set(),
            }

        from . import host_authority_client
        req_digest = proof.get("request_digest") or data.get("request_digest") or data.get("proof_digest") or ""
        session = proof.get("session") or data.get("session_id")
        try:
            is_valid_origin = host_authority_client.verify_operator_origin(
                proof,
                project=root,
                request_digest=req_digest,
                session=session,
            )
        except Exception:
            is_valid_origin = False

        if not is_valid_origin:
            return {
                "valid": False,
                "status": "GRANT_PROOF_UNVERIFIED",
                "error": "Operator-origin proof could not be verified by operator broker",
                "authorized_scopes": set(),
            }

        scopes = set(data.get("authorized_scopes") or proof.get("authorized_scopes") or [])
        if requested_scope and requested_scope not in scopes:
            return {
                "valid": False,
                "status": "SCOPE_UNAUTHORIZED",
                "error": f"Requested scope '{requested_scope}' not in grant scopes: {scopes}",
                "authorized_scopes": scopes,
            }
        return {
            "valid": True,
            "status": "VALID_GRANT",
            "grant": data,
            "authorized_scopes": scopes,
            "grant_digest": file_digest,
        }
    except Exception as exc:
        return {
            "valid": False,
            "status": "GRANT_FILE_ERROR",
            "error": str(exc),
            "authorized_scopes": set(),
        }


class CampaignController:
    """Supervises campaign lifecycle and successive bounded worker generations."""

    def __init__(self, project_root: Path | str) -> None:
        self.root = Path(project_root).resolve()
        self.saipal = saipal_adapter.SaipalAdapter()

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
            return {"ok": False, "code": "CAMPAIGN_LOCKED", "detail": "Another controller owns the campaign lock"}

        try:
            # 1. Horizon validation
            if horizon not in HORIZONS:
                return {
                    "ok": False,
                    "code": "INVALID_HORIZON",
                    "status": "INVALID_HORIZON",
                    "detail": f"Unknown horizon '{horizon}'; must be one of {sorted(HORIZONS.keys())}",
                }

            # 2. Resource budget validation
            if resource_budget:
                for k, v in resource_budget.items():
                    if k in ("max_generations", "max_wall_seconds"):
                        try:
                            num = float(v)
                            if num <= 0:
                                return {
                                    "ok": False,
                                    "code": "INVALID_RESOURCE_BUDGET",
                                    "status": "INVALID_RESOURCE_BUDGET",
                                    "detail": f"Budget field {k} must be positive, got {v}",
                                }
                        except (ValueError, TypeError):
                            return {
                                "ok": False,
                                "code": "INVALID_RESOURCE_BUDGET",
                                "status": "INVALID_RESOURCE_BUDGET",
                                "detail": f"Budget field {k} must be numeric, got {v}",
                            }

            inspect = inspect_campaign_state(self.root)
            if inspect["status"] in (STATE_CORRUPT, STATE_UNTRUSTED):
                return {
                    "ok": False,
                    "code": inspect["status"],
                    "status": inspect["status"],
                    "detail": f"Campaign state has invalid integrity ({inspect['status']}); overwrite refused without explicit recovery",
                    "inspection": inspect,
                }

            cid = str(campaign_id or f"CAMPAIGN-{uuid.uuid4()}")
            if inspect["status"] == STATE_VALID:
                existing = inspect["state"]
                if existing:
                    existing_state = existing.get("campaign_state")
                    if not force_new and existing_state not in (COMPLETE, CANCELLED):
                        return {"ok": True, "admitted": False, "state": existing, "status": "RESUMED_EXISTING"}

                    if force_new and existing_state in (RUNNING, REPAIRING, VERIFYING, AUDIT_DELIVERY, DISCOVERING):
                        return {
                            "ok": False,
                            "code": "LIVE_CAMPAIGN_SUPERSEDED_REFUSED",
                            "status": "LIVE_CAMPAIGN_SUPERSEDED_REFUSED",
                            "detail": f"Active campaign {existing.get('campaign_id')} is currently in live state '{existing_state}'. Cancel or stop it first.",
                        }
                    elif force_new and existing_state not in (COMPLETE, CANCELLED):
                        # Gracefully supersede prior non-live campaign
                        existing["campaign_state"] = CANCELLED
                        existing["superseded_by"] = cid
                        existing["next_action"] = f"campaign_superseded: replaced by {cid}"
                        save_campaign_state(self.root, existing)
            lineage = host_dispatch.resolve_project_lineage(self.root)
            budget = dict(HORIZONS.get(horizon, HORIZONS["SHORT"]))
            if resource_budget:
                budget.update(resource_budget)

            if goal_binding is None:
                state_file = self.root / ".saipen" / "STATE.md"
                goal_binding = {
                    "path": str(state_file),
                    "fingerprint": f"lineage-{lineage[:8]}",
                }

            # Authority grant verification
            grant_res = None
            if authority_proof_reference:
                grant_res = verify_operator_grant(self.root, authority_proof_reference, authority_scope)
                if not grant_res["valid"]:
                    return {
                        "ok": False,
                        "code": "INVALID_AUTHORITY_GRANT",
                        "status": grant_res.get("status", "INVALID_GRANT"),
                        "detail": grant_res.get("error", "Invalid operator grant proof"),
                    }
                valid_scopes = grant_res["authorized_scopes"]
                scope = authority_scope or (
                    CONTINUOUS_MAINTENANCE_SCOPE if CONTINUOUS_MAINTENANCE_SCOPE in valid_scopes else CAMPAIGN_EXECUTION
                )
                camp_state = ADMITTED
                executable = True
                grant_data = grant_res["grant"]
            else:
                # Without an authenticated operator grant, created only in non-executable PROPOSED state
                scope = "none"
                camp_state = PROPOSED
                executable = False
                grant_data = None

            now_str = _utc_now()
            state = {
                "schema_version": CAMPAIGN_SCHEMA_VERSION,
                "campaign_id": cid,
                "project_lineage": lineage,
                "goal_binding": goal_binding,
                "authority_proof_reference": authority_proof_reference,
                "authority_scope": scope,
                "authority_grant": grant_data,
                "campaign_state": camp_state,
                "current_work": None,
                "worker_generation": 0,
                "last_journal_event": "none",
                "last_source_generation": 0,
                "last_audit_generation": 0,
                "last_saipal_generation": 0,
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
            save_campaign_state(self.root, state)
            return {"ok": True, "admitted": executable, "state": state, "status": camp_state}
        finally:
            lk.release()

    def cancel(self, *, reason: str = "user_cancelled") -> dict:
        try:
            lk = self._acquire_lock()
        except lock.FileLockBusy:
            return {"ok": False, "code": "CAMPAIGN_LOCKED", "detail": "Another controller owns the campaign lock"}

        try:
            inspect = inspect_campaign_state(self.root)
            if inspect["status"] != STATE_VALID:
                return {"ok": False, "error": inspect["status"], "detail": inspect.get("error")}
            state = inspect["state"]
            state["campaign_state"] = CANCELLED
            state["next_action"] = f"campaign_cancelled: {reason}"
            save_campaign_state(self.root, state)
            return {"ok": True, "state": state, "status": CANCELLED}
        finally:
            lk.release()

    def step(self, *, worker_func: callable | None = None) -> dict:
        """Advance one lifecycle step under exclusive campaign lock."""
        try:
            lk = self._acquire_lock()
        except lock.FileLockBusy:
            return {"ok": False, "code": "CAMPAIGN_LOCKED", "detail": "Another controller owns the campaign lock"}

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
                    "detail": "Campaign in proposal state; valid operator grant required for execution",
                    "state": state,
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

            grant_chk = verify_operator_grant(
                self.root, proof_ref, state.get("authority_scope")
            )
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
            max_gen = int(budget.get("max_generations", 999999))
            if int(state.get("worker_generation", 0)) >= max_gen:
                state["campaign_state"] = CHECKPOINTING
                state["next_action"] = "budget_exhausted: max_generations reached"
                save_campaign_state(self.root, state)
                return {"ok": True, "event": "BUDGET_EXHAUSTED", "reason": "max_generations", "state": state}

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
                        return {"ok": True, "event": "BUDGET_EXHAUSTED", "reason": "max_wall_seconds", "state": state}
                except Exception:
                    pass

            # Continuation Assessment
            assessment = ca.assess_continuation(self.root)
            classification = assessment["classification"]
            state["next_action"] = assessment.get("next_action", "")

            # 1. Quiescent
            if classification == ca.QUIESCENT:
                state["campaign_state"] = QUIESCENT_WAIT
                state["wake_condition"] = {"event": "new_source_or_audit"}
                save_campaign_state(self.root, state)
                return {"ok": True, "event": "QUIESCENT_WAIT", "classification": classification, "state": state}

            # 2. Wait / Boundary Classifications
            if classification == ca.WAIT_OPERATOR:
                state["campaign_state"] = OPERATOR_BLOCKED
                save_campaign_state(self.root, state)
                return {"ok": True, "event": "OPERATOR_BLOCKED", "classification": classification, "state": state}

            if classification == ca.WAIT_AUTHORITY:
                state["campaign_state"] = AUTHORITY_BLOCKED
                save_campaign_state(self.root, state)
                return {"ok": True, "event": "AUTHORITY_BLOCKED", "classification": classification, "state": state}

            if classification == ca.WAIT_EXTERNAL:
                state["campaign_state"] = EXTERNAL_BLOCKED
                save_campaign_state(self.root, state)
                return {"ok": True, "event": "EXTERNAL_BLOCKED", "classification": classification, "state": state}

            if classification in (ca.SAFETY_STOP, ca.CONFORMANCE_STOP):
                state["campaign_state"] = SAFETY_STOP
                save_campaign_state(self.root, state)
                return {"ok": True, "event": "SAFETY_STOP", "classification": classification, "state": state}

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
                auth_scope = state.get("authority_scope")
                if auth_scope not in (CONTINUOUS_MAINTENANCE_SCOPE, FORENSIC_ANALYSIS_SCOPE):
                    state["campaign_state"] = AUTHORITY_BLOCKED
                    save_campaign_state(self.root, state)
                    return {
                        "ok": True,
                        "event": "AUTHORITY_BLOCKED",
                        "detail": "Forensic discovery requires continuous_maintenance or forensic_analysis authority",
                        "state": state,
                    }

                state["campaign_state"] = DISCOVERING
                disc_res = self.saipal.discover(self.root)
                if disc_res.get("status") in (saipal_adapter.NEW_QUALIFIED_FINDINGS, "ANALYSIS_PROGRESS"):
                    state["last_saipal_generation"] = int(state.get("last_saipal_generation", 0)) + 1

                pub_auth = auth_scope in (CONTINUOUS_MAINTENANCE_SCOPE, EXTERNAL_AUDIT_PUBLICATION)
                if disc_res.get("status") == saipal_adapter.NEW_QUALIFIED_FINDINGS:
                    state["campaign_state"] = FORENSIC_ANALYSIS
                    findings = disc_res.get("findings", [])
                    delivered = []
                    for f in findings:
                        d_res = self.saipal.deliver_finding_to_audit_inbox(
                            self.root, f, publication_authorized=pub_auth
                        )
                        delivered.append(d_res)
                    state["campaign_state"] = AUDIT_DELIVERY
                    save_campaign_state(self.root, state)
                    return {
                        "ok": True,
                        "event": "DISCOVERY_DELIVERED",
                        "delivered": delivered,
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

                if callable(worker_func):
                    try:
                        w_res = worker_func(self.root, generation=w_gen)
                    except TypeError:
                        try:
                            w_res = worker_func(self.root, w_gen)
                        except TypeError:
                            w_res = worker_func(self.root)
                else:
                    w_res = self._execute_canonical_worker(generation=w_gen, state=state)

                if not isinstance(w_res, dict) or w_res.get("ok") is False:
                    save_campaign_state(self.root, state)
                    return {
                        "ok": False,
                        "event": "WORKER_GENERATION_FAILED",
                        "code": "WORKER_GENERATION_FAILED",
                        "worker_generation": w_gen,
                        "worker_result": w_res,
                        "state": state,
                    }

                state["worker_generation"] = w_gen
                progress = self._verify_progress_evidence(w_res)
                if progress["made_progress"]:
                    state["last_productive_progress"] = _utc_now()
                    state["no_progress_count"] = 0
                else:
                    state["no_progress_count"] = int(state.get("no_progress_count", 0)) + 1

                save_campaign_state(self.root, state)
                return {
                    "ok": True,
                    "event": "WORKER_GENERATION_EXECUTED",
                    "worker_generation": w_gen,
                    "worker_result": w_res,
                    "progress": progress,
                    "state": state,
                }

            return {
                "ok": False,
                "code": "UNHANDLED_CLASSIFICATION",
                "classification": classification,
                "detail": f"Unrecognized continuation classification: {classification}",
                "state": state,
            }
        finally:
            lk.release()

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
                        check=False,
                        timeout=60.0,
                        cwd=str(self.root),
                    )
                    out_json = None
                    try:
                        out_json = json.loads(res.stdout)
                    except Exception:
                        pass
                    ok = (res.returncode == 0)
                    return {
                        "ok": ok,
                        "executed": True,
                        "decision": dec.get("verdict"),
                        "command": next_cmd,
                        "returncode": res.returncode,
                        "output": out_json or res.stdout[:500],
                        "error": None if ok else f"Process exited with code {res.returncode}: {res.stderr[:300]}",
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

    def _read_tail_event(self) -> str:
        log_file = self.root / ".saipen" / "LOG.md"
        if log_file.is_file():
            try:
                lines = [l for l in log_file.read_text(encoding="utf-8").splitlines() if l.strip()]
                if lines:
                    return lines[-1][:80]
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

    def _verify_progress_evidence(self, worker_result: dict) -> dict:
        b_ev = worker_result.get("before_event")
        a_ev = worker_result.get("after_event")
        b_st = worker_result.get("before_state")
        a_st = worker_result.get("after_state")
        made_progress = (b_ev != a_ev and a_ev != "none") or (b_st != a_st and a_st != "none")
        if worker_result.get("progress_verified") is True:
            made_progress = True
        return {
            "made_progress": made_progress,
            "journal_advanced": b_ev != a_ev,
            "state_mutated": b_st != a_st,
        }
