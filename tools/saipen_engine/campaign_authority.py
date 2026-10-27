"""One scoped campaign credential: exact human bytes plus live broker ownership.

Parsing is not authority. Only the separated native-event owner can accept the
capsule, bind its one campaign and verify later use of the original permission.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from . import paths
from .pending_ingress import ingress_digest

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
CAPSULE_KIND = "saipen-campaign-authorization"
CARRIER_KIND = "saipen-campaign-grant"
MAX_CARRIER_BYTES = 512 * 1024
BUDGET_FIELDS = frozenset({"max_generations", "max_cycles", "max_wall_seconds"})


def _object(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError(f"duplicate credential field: {key}")
        data[key] = value
    return data


def _constant(value):
    raise ValueError(f"non-finite credential value: {value}")


def strict_json(text):
    return json.loads(text, object_pairs_hook=_object, parse_constant=_constant)


def valid_budget(data, *, complete=True):
    if not isinstance(data, dict) or not set(data) <= BUDGET_FIELDS:
        return False
    if complete and set(data) != BUDGET_FIELDS:
        return False
    try:
        return all(
            type(value) in (int, float)
            and math.isfinite(value)
            and value > 0
            and (key == "max_wall_seconds" or type(value) is int)
            for key, value in data.items()
        )
    except OverflowError:
        return False


def parse_capsule(text: str) -> dict:
    if not isinstance(text, str) or not 0 < len(text.encode("utf-8")) <= 256 * 1024:
        raise ValueError("campaign authorization needs bounded original human text")
    data = strict_json(text)
    fields = {
        "schema_version",
        "kind",
        "campaign_limit",
        "project_lineage",
        "target_project",
        "host",
        "session",
        "goal_binding",
        "authorized_scopes",
        "resource_budget",
        "expires_at",
    }
    if not isinstance(data, dict) or set(data) != fields:
        raise ValueError("campaign authorization has an invalid field set")
    if (
        type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or data["kind"] != CAPSULE_KIND
        or type(data["campaign_limit"]) is not int
        or data["campaign_limit"] != 1
    ):
        raise ValueError("campaign authorization schema or campaign limit is invalid")
    if any(
        not isinstance(data[key], str) or not data[key].strip()
        for key in ("project_lineage", "target_project", "host", "session")
    ):
        raise ValueError("campaign authorization lacks its project/host/session identity")
    goal = data["goal_binding"]
    if (
        not isinstance(goal, dict)
        or set(goal) != {"goal_ingress", "authority_source"}
        or any(not isinstance(value, str) for value in goal.values())
    ):
        raise ValueError("campaign authorization lacks its exact goal epoch")
    scopes = data["authorized_scopes"]
    if (
        not isinstance(scopes, list)
        or not scopes
        or any(not isinstance(scope, str) or scope not in ALL_SCOPES for scope in scopes)
        or len(set(scopes)) != len(scopes)
    ):
        raise ValueError("campaign authorization has invalid or duplicate scopes")
    expires = data["expires_at"]
    try:
        finite_expiry = type(expires) in (int, float) and math.isfinite(expires) and expires > 0
    except OverflowError:
        finite_expiry = False
    if not finite_expiry or not valid_budget(data["resource_budget"]):
        raise ValueError("campaign authorization needs finite expiry and positive resource limits")
    return data


def validate_admission(admission: object, authorization: dict) -> bool:
    return bool(
        isinstance(admission, dict)
        and set(admission) == {"campaign_id", "goal_binding", "resource_budget"}
        and isinstance(admission["campaign_id"], str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}", admission["campaign_id"])
        and admission["goal_binding"] == authorization["goal_binding"]
        and valid_budget(admission["resource_budget"])
        and all(
            admission["resource_budget"][key] <= authorization["resource_budget"][key]
            for key in BUDGET_FIELDS
        )
    )


def admission_for_state(state: dict) -> dict:
    return {key: state.get(key) for key in ("campaign_id", "goal_binding", "resource_budget")}


def read_carrier(root: Path | str, reference: str) -> dict:
    """Read and validate bytes only; this function grants no capabilities."""
    root = Path(root).resolve()
    if not isinstance(reference, str) or not reference:
        raise ValueError("campaign authority reference is absent")
    receipt = None
    if re.fullmatch(r"E-\d+", reference):
        raise ValueError("ordinary journal events are not scoped campaign credentials")
    if re.fullmatch(r"SRC-\d+", reference):
        from . import intake

        found = intake.read_body(root, reference)
        if not found.get("ok"):
            raise ValueError("original campaign Source is unreadable or corrupt")
        body = found.get("body") or ""
        text = intake.request_clause_text(body) if body.startswith("# User request\n") else body
        meta = found.get("meta") or {}
        provenance = meta.get("request_provenance") or {}
        if not isinstance(provenance, dict):
            raise ValueError("campaign Source provenance is malformed")
        if provenance.get("witness") != "operator_carrier" or provenance.get(
            "compared_digest"
        ) != ingress_digest(text):
            raise ValueError("campaign Source has no exact original operator provenance")
        proof = provenance.get("operator_origin")
        raw = body.encode("utf-8")
        receipt = reference
    else:
        path = root / reference
        stat = paths.prove_owned_regular(path, kind="campaign authority carrier")
        if stat.st_size > MAX_CARRIER_BYTES:
            raise ValueError("campaign authority carrier exceeds its size bound")
        with path.open("rb") as stream:
            raw = stream.read(MAX_CARRIER_BYTES + 1)
        if len(raw) > MAX_CARRIER_BYTES:
            raise ValueError("campaign authority carrier exceeds its size bound")
        data = strict_json(raw.decode("utf-8"))
        if (
            not isinstance(data, dict)
            or set(data) != {"kind", "schema_version", "request_text", "operator_origin"}
            or data["kind"] != CARRIER_KIND
            or type(data["schema_version"]) is not int
            or data["schema_version"] != 1
        ):
            raise ValueError(
                "campaign grant file must carry the original scoped request and its proof"
            )
        text, proof = data["request_text"], data["operator_origin"]
    authorization = parse_capsule(text)
    if (
        not isinstance(proof, dict)
        or proof.get("kind") != "operator-origin"
        or proof.get("request_digest") != ingress_digest(text)
    ):
        raise ValueError("campaign authorization bytes do not match the original operator event")
    return {
        "request_text": text,
        "proof": proof,
        "authorization": authorization,
        "digest": hashlib.sha256(raw).hexdigest(),
        "receipt": receipt,
    }


def is_authorization_request(text: str) -> bool:
    try:
        if not text.lstrip().startswith("{") or len(text.encode("utf-8")) > 256 * 1024:
            return False
        data = strict_json(text)
    except (ValueError, TypeError, RecursionError):
        return False
    return isinstance(data, dict) and data.get("kind") == CAPSULE_KIND


def capture_authorization(root, text, provenance, authority, *, dry_run=False):
    """START captures authority data without projecting it as engineering Work."""
    from . import intake, operator_task

    try:
        parse_capsule(text)
    except (ValueError, TypeError, RecursionError) as exc:
        return {"ok": False, "code": "CAMPAIGN_AUTHORITY_INVALID", "detail": str(exc)}
    if not authority.get("user_explicit"):
        existing = intake.find_by_body(root, text, request_provenance=provenance)
        if (
            existing
            and existing.get("projection_policy") == intake.PROJECTION_AUTHORITY_ONLY
            and operator_task.received_source_origin(
                root,
                existing["receipt"],
                action=(provenance.get("operator_origin") or {}).get("action"),
            )
        ):
            return _received_route(existing["receipt"])
        return {
            "ok": False,
            "code": "CAMPAIGN_AUTHORITY_REQUIRED",
            "detail": "The exact capsule needs its original verified native operator event",
        }
    if dry_run:
        return {
            "ok": True,
            "code": "PLAN",
            "operation": "capture_campaign_authority",
            "dry_run": True,
            "projection_policy": intake.PROJECTION_AUTHORITY_ONLY,
            "detail": "Authority-only intake; no Work, grant reservation or campaign admission",
        }
    captured = intake.capture(
        root,
        text,
        source_kind="user_instruction",
        projection_policy=intake.PROJECTION_AUTHORITY_ONLY,
        request_provenance=provenance,
    )
    if not captured.get("ok"):
        return captured
    receipt = captured["receipt"]
    current = operator_task.authority_for_receipt(root, receipt, existing_only=False)
    if not current.get("user_explicit"):
        return {
            "ok": False,
            "code": "CAMPAIGN_AUTHORITY_REQUIRED",
            "receipt": receipt,
            "detail": "Captured bytes do not establish original native operator authority",
        }
    return _received_route(receipt)


def _received_route(receipt):
    from . import intake

    action = f"saipen campaign admit --authority {receipt}"
    return {
        "ok": True,
        "code": "CAMPAIGN_AUTHORITY_RECEIVED",
        "receipt": receipt,
        "projection_policy": intake.PROJECTION_AUTHORITY_ONLY,
        "action": action,
        "canonical_next_command": action,
        "detail": (
            "Authority carrier captured; campaign admission still verifies "
            "exact scope and resources"
        ),
    }


def verify_grant(root, reference, requested_scope=None, *, admission=None, consume=False):
    from . import host_authority_client

    invalid = {"valid": False, "authorized_scopes": set()}
    if isinstance(reference, str) and re.fullmatch(r"E-\d+", reference):
        return {
            **invalid,
            "status": "EVENT_NOT_OPERATOR_AUTHORITY",
            "error": "Ordinary journal events are not scoped campaign credentials",
        }
    try:
        carrier = read_carrier(root, reference)
        authorization = carrier["authorization"]
        if (
            requested_scope is not None
            and requested_scope not in authorization["authorized_scopes"]
        ):
            return {**invalid, "status": "SCOPE_UNAUTHORIZED", "error": "Requested scope is absent"}
        if not validate_admission(admission, authorization):
            return {
                **invalid,
                "status": "GRANT_ADMISSION_INVALID",
                "error": "Campaign identity, goal and resources require an exact scoped admission",
            }
        verdict = host_authority_client.inspect_operator_campaign(
            carrier["proof"],
            project=root,
            request_text=carrier["request_text"],
            requested_scope=requested_scope,
            admission=admission,
            consume=consume,
            carrier_digest=carrier["digest"],
            receipt=carrier["receipt"],
        )
        if (
            not isinstance(verdict, dict)
            or verdict.get("ok") is not True
            or verdict.get("kind") != "operator-campaign-verdict"
            or verdict.get("authorization") != authorization
            or verdict.get("admission") != admission
            or verdict.get("carrier_digest") != carrier["digest"]
        ):
            return {
                **invalid,
                "status": "GRANT_UNVERIFIED",
                "error": (verdict if isinstance(verdict, dict) else {}).get(
                    "detail", "Separated campaign issuer unavailable or unverified"
                ),
            }
        return {
            "valid": True,
            "status": "VALID_GRANT",
            "authorization": authorization,
            "authorized_scopes": set(authorization["authorized_scopes"]),
            "grant": {"authorization": authorization, "operator_origin": carrier["proof"]},
            "grant_digest": carrier["digest"],
        }
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        return {**invalid, "status": "GRANT_INVALID", "error": str(exc)}
