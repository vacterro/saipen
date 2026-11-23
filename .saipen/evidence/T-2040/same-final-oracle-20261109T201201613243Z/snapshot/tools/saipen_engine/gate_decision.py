"""SRC-228: a source-backed decision consumes one exact checkpoint gate.

The existing source provenance verifier owns operator origin. This owner
adds only gate scope and a journaled state projection; LOG prose and a
canonical ticket_move never become operator witnesses.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path

from . import goal_authority, intake, operations
from .journal import hash_bytes, hash_file_dependency, semantic_receipts_for_operation_safe
from .operations import REPAIR_OBSERVABLE
from .paths import project_lineage_identity
from .plan import TargetPlan, apply_plan
from .result import Result
from .state import parse_wait, patch_state

KIND = "saipen-gate-decision"
FIELDS = frozenset({
    "kind", "schema", "project_lineage", "gate_id", "gate", "resolve",
    "decision", "statement", "expires_at",
})
OPTIONAL_FIELDS = frozenset({"next_action"})
GATE_FIELDS = ("phase", "task", "last_event", "blocker", "next_action")
RESOLVABLE = frozenset({"blocker", "next_action"})
METADATA = "operator_gate_decision"


def gate_id(lineage, gate):
    raw = json.dumps(
        {"project_lineage": lineage, "gate": gate},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _instant(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("gate expiry must be a UTC timestamp ending in Z")
    instant = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    if instant.tzinfo is None or instant.utcoffset() != dt.timedelta(0):
        raise ValueError("gate expiry must be UTC")
    return instant


def parse_capsule(text):
    value = goal_authority.parse_capsule(text)
    if (not set(value) >= FIELDS or set(value) - FIELDS - OPTIONAL_FIELDS
            or value["kind"] != KIND or type(value["schema"]) is not int):
        raise ValueError("unsupported or incomplete gate decision capsule")
    gate = value["gate"]
    fields = value["resolve"]
    if (
        value["schema"] != 1 or not isinstance(gate, dict)
        or set(gate) != set(GATE_FIELDS) or type(gate["last_event"]) is not int
        or any(not isinstance(gate[key], str) for key in GATE_FIELDS if key != "last_event")
        or not isinstance(value["project_lineage"], str)
        or not value["project_lineage"]
        or not isinstance(fields, list) or not fields
        or any(not isinstance(key, str) or key not in RESOLVABLE for key in fields)
        or len(set(fields)) != len(fields)
        or value["decision"] != "ACCEPT_LIMITATION"
        or not isinstance(value["statement"], str) or not value["statement"].strip()
        or len(value["statement"]) > 65536
        or not re.fullmatch(r"[0-9a-f]{64}", str(value["gate_id"]))
        or value["gate_id"] != gate_id(value["project_lineage"], gate)
    ):
        raise ValueError("invalid gate decision scope, fields or digest")
    _instant(value["expires_at"])
    if "next_action" in value:
        from .reconcile import _legacy_next_action
        proposed = value["next_action"]
        if ("next_action" not in fields or not isinstance(proposed, str)
                or not proposed.strip() or _legacy_next_action(proposed)):
            raise ValueError("the scoped replacement next_action must be executable")
    return value


def capsule_problem(text):
    try:
        parse_capsule(text)
    except (ValueError, TypeError, KeyError) as exc:
        return str(exc)
    return None


def _scope(root, state, dependencies):
    identity = root / ".saipen/IDENTITY.md"
    before = hash_file_dependency(identity)
    lineage = project_lineage_identity(root)
    if not lineage or before != hash_file_dependency(identity):
        raise ValueError("canonical project lineage is required")
    dependencies[".saipen/IDENTITY.md"] = before
    return lineage, {key: state[key] for key in GATE_FIELDS}


def _refuse(code, detail, *, cause=None):
    result = {"ok": False, "code": code, "detail": detail}
    if cause:
        result["cause"] = cause
    return result


def _committed(root, receipt, binding, source, dependencies, history):
    records, errors = semantic_receipts_for_operation_safe(root, "reconcile")
    if errors:
        raise ValueError("gate decision journal is unavailable: " + "; ".join(errors[:2]))
    for record in records:
        proof = (record.get("receipt_metadata") or {}).get(METADATA) or {}
        if proof.get("authorization_receipt") != receipt or record.get("status") != "COMMITTED":
            continue
        if (
            record.get("project_lineage") != binding["project_lineage"]
            or proof.get("gate_id") != binding["gate_id"]
            or proof.get("authorization_sha256") != source["source_sha256"]
            or proof.get("request_provenance") != source["request_provenance"]
            or proof.get("resolve") != binding["resolve"]
            or _instant(proof.get("accepted_at")) >= _instant(binding["expires_at"])
        ):
            raise ValueError("committed gate decision does not match its original authority")
        events = [event for event in history.events
                  if event.get("op_id") == record["op_id"]
                  and event.get("event") == proof.get("transition_event")
                  and event.get("taxonomy") == "DEC"
                  and str(event.get("text") or "").startswith("operator gate decision -- ")]
        if len(events) != 1:
            raise ValueError("committed gate decision has no matching transition event")
        goal_authority._pin_record(root, record, dependencies)
        return record
    return None


def resolve(root, agent, receipt, *, dry_run=False, only_next_action=False):
    """Consume a captured decision; never authenticate a model's current text."""
    root = Path(root)
    try:
        snapshot = operations._read(root, observe=REPAIR_OBSERVABLE)
        docs, state, board, _tail = snapshot
        if board["errors"]:
            return _refuse("VALIDATION_FAILED", "; ".join(board["errors"][:3]))
        guard = operations._active_claim_refusal(state, docs["board"].text_norm, agent)
        if guard is not None:
            return guard.to_dict()
        dependencies = {}
        lineage, gate = _scope(root, state, dependencies)
        if receipt == "preview" and dry_run:
            return {
                "ok": True, "code": "REPAIR_REQUIRED", "dry_run": True,
                "capsule": {
                    "kind": KIND, "schema": 1, "project_lineage": lineage,
                    "gate_id": gate_id(lineage, gate), "gate": gate,
                    "resolve": [key for key in ("blocker", "next_action")
                                if (key == "blocker" and str(state.get(key) or "").lower()
                                    not in ("", "none"))
                                or (key == "next_action" and parse_wait(str(state.get(key) or ""))
                                    == "blocked")],
                    "decision": "ACCEPT_LIMITATION", "statement": "", "expires_at": "",
                },
                "detail": "Complete the capsule and capture its original operator witness; "
                          "a preview grants no authority.",
                "canonical_next_command": "saipen authority capture --file <UTF8_FILE>",
                "apply_command": "saipen recover resolve-blocker <SRC-###>",
            }
        # A BLOCKED phase is owned by the lifecycle, never by this transition,
        # so its refusal is structural: it answers before the competing-repair
        # diagnosis, which can only report "unrepairable" for that surface.
        if state["phase"] == "BLOCKED":
            return _refuse("RECONCILE_REAUTH_REQUIRED", "phase BLOCKED retains its phase owner")
        # The mask runs before the carrier grammar on purpose: a prose or
        # unknown receipt on a surface that still owes a phase, Work or closure
        # repair must name THAT repair, never a capture route that would
        # leave the real defect in place.
        from .reconcile import reconcile_protocol_state

        diagnosis = reconcile_protocol_state(root, agent, dry_run=True)
        changed = diagnosis.get("changed") or {}
        if (
            diagnosis.get("code") not in {"CLEAN", "REPAIR_REQUIRED", "RECONCILE_REAUTH_REQUIRED"}
            or changed.get("lifecycle")
            or any(repair.get("field") in {"phase", "task"}
                   for repair in changed.get("state", []))
        ):
            return diagnosis
        if not re.fullmatch(r"SRC-[0-9]+", str(receipt or "")):
            return {
                **_refuse(
                "RECONCILE_REAUTH_REQUIRED",
                "an authority-only Source with its original operator carrier is required; "
                "decision text and canonical operation provenance grant no gate authority",
                cause="GATE_AUTHORITY_REQUIRED",
                ),
                "canonical_next_command": "saipen recover resolve-blocker preview --dry-run",
                "capture_command": "saipen authority capture --file <UTF8_FILE>",
            }
        found = intake.read_body(root, receipt)
        if not found.get("ok"):
            return _refuse("RECONCILE_REAUTH_REQUIRED", "authority Source is missing or invalid",
                           cause="GATE_AUTHORITY_UNVERIFIED")
        binding = parse_capsule(found.get("body") or "")
        source = goal_authority.source_proof(
            root, receipt, binding, dependencies, capability="gate_decision",
        )
        if binding["project_lineage"] != lineage:
            return _refuse("RECONCILE_REAUTH_REQUIRED", "the approval names another project",
                           cause="GATE_SCOPE_MISMATCH")
        committed = _committed(root, receipt, binding, source, dependencies, docs["_history"])
        if committed is not None:
            return {
                "ok": True, "code": "ALREADY_APPLIED",
                "op_id": committed["op_id"], "authorization_receipt": receipt,
                "gate_id": binding["gate_id"], "next_action": state["next_action"],
                "dry_run": dry_run,
            }
        if binding["gate"] != gate:
            return _refuse("RECONCILE_REAUTH_REQUIRED", "the approval names another gate version",
                           cause="GATE_SCOPE_MISMATCH")
        if _instant(binding["expires_at"]) <= dt.datetime.now(dt.timezone.utc):
            return _refuse("RECONCILE_REAUTH_REQUIRED", "the scoped approval has expired",
                           cause="GATE_AUTHORITY_EXPIRED")
        fields = set(binding["resolve"])
        if only_next_action and fields != {"next_action"}:
            return _refuse("RECONCILE_REAUTH_REQUIRED", "this recovery verb owns only next_action",
                           cause="GATE_SCOPE_MISMATCH")
        patch = {}
        remaining_wait = None
        if "blocker" in fields:
            if str(state.get("blocker") or "").strip().lower() in ("", "none"):
                return _refuse("RECONCILE_REAUTH_REQUIRED", "the named STATE.blocker is not active",
                               cause="GATE_NOT_ACTIVE")
            patch["blocker"] = "none"
        if "next_action" in fields:
            from .reconcile import _legacy_next_action, _tripped_valve_repairs
            old_action = str(state.get("next_action") or "")
            if parse_wait(old_action) != "blocked" and not _legacy_next_action(old_action):
                return _refuse(
                    "RECONCILE_REAUTH_REQUIRED",
                    "this decision cannot waive a user brake, manual verification, "
                    "destructive operation, budget or publication gate",
                    cause="GATE_OWNER_MISMATCH",
                )
            # FINISH routing precedes the counter-only budget check. Seed
            # its existing owner's derived WAIT so a limitation decision
            # cannot turn that independent stop into a runnable phase.
            remaining_wait = next(
                (repair["to"] for repair in _tripped_valve_repairs(state)
                 if repair.get("refuse") and isinstance(repair.get("to"), str)), None,
            )
            provisional = patch_state(docs["state"].text_norm, {
                **patch, "next_action": remaining_wait or "saipen continue",
            })
            from .router import route_next
            route = route_next(
                provisional, docs["board"].text_norm, current_agent=agent,
                pending_ops=[], conflict_ops=[],
            )
            if not route.get("ok") or not isinstance(route.get("action"), str):
                return _refuse(
                    "VALIDATION_FAILED", "the shared router cannot project a next action",
                    cause="GATE_ROUTE_UNAVAILABLE",
                )
            if (remaining_wait and "next_action" in binding
                    and binding["next_action"] != route["action"]):
                return _refuse(
                    "RECONCILE_REAUTH_REQUIRED",
                    "the requested replacement cannot waive the independent goal budget stop",
                    cause="GATE_OWNER_MISMATCH",
                )
            # A legacy unprojectable action may have an explicit replacement
            # in the witnessed capsule. It receives the same complete-surface
            # validation as the router's default, never authority from argv.
            patch["next_action"] = binding.get("next_action", route["action"])
        now, utc = operations._now(), operations._utc_iso()
        proof = {
            "schema": 1, "authorization_receipt": receipt,
            "authorization_sha256": source["source_sha256"],
            "request_provenance": source["request_provenance"],
            "gate_id": binding["gate_id"], "resolve": binding["resolve"],
            "accepted_at": utc, "expires_at": binding["expires_at"],
        }
        if remaining_wait:
            proof["remaining_wait"] = remaining_wait
        op_id = "reconcile-" + operations.uuid4_hex()
        original = (root / ".saipen/STATE.md").read_bytes()
        if hash_bytes(original) != docs["state"].raw_hash:
            return _refuse("STALE_STATE", "the approved checkpoint changed before planning")
        preserved = f".saipen/recovery/state-legacy-output/{op_id}.STATE.md"
        expected = {
            "ok": True, "code": "REPAIRED", "authorization_receipt": receipt,
            "gate_id": binding["gate_id"], "next_action": patch.get(
                "next_action", state["next_action"]
            ),
        }

        def mutate(raw, event):
            proof["transition_event"] = event
            return patch_state(raw, {**patch, "last_event": event, "updated": utc})

        plan = operations._state_only_plan(
            root, "reconcile", agent, mutate,
            f"operator gate decision -- {receipt} gate:{binding['gate_id'][:16]} "
            f"ACCEPT_LIMITATION fields:{','.join(sorted(fields))}",
            expected, now, utc, fields,
            ticket_id=(state.get("task")
                       if re.fullmatch(r"T-[0-9]+", str(state.get("task"))) else None),
            read_once=snapshot, op_id=op_id, evidence_preconditions=dependencies,
            receipt_metadata={METADATA: proof}, repair=True,
            extra_targets=[TargetPlan(preserved, "generic", original, "", hash_bytes(original))],
        )
        if isinstance(plan, Result):
            return plan.to_dict()
        if dry_run:
            return {**plan.expected, "code": "REPAIR_REQUIRED", "dry_run": True,
                    "targets": plan.changed_files}
        return apply_plan(root, plan).to_dict()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return _refuse(getattr(exc, "code", "RECONCILE_REAUTH_REQUIRED"), str(exc),
                       cause="GATE_AUTHORITY_UNVERIFIED")
