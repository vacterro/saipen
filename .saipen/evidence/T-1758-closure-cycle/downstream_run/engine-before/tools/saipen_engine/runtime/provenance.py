"""Canonical, append-only runtime provenance for SAIPEN Attempt sessions.

Only the host-declared runtime-info environment carrier is eligible. Explicit
CLI metadata remains a read-only projection and cannot be promoted into a
canonical Attempt record.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from typing import Any, Mapping

from .base import RuntimeInfoError, load_runtime_info

SCHEMA_VERSION = 1
RUNTIME_FIELDS = ("runtime_provider", "runtime_model", "runtime_effort")
_FIELDS = frozenset(
    {
        "schema_version",
        "executor_identity",
        *RUNTIME_FIELDS,
        "provenance_source",
        "provenance_status",
        "benchmark_evidence",
        "reason_code",
        "missing_fields",
    }
)
_TOKEN_RE = re.compile(r"^([A-Za-z0-9_-]+)\.([0-9a-f]{64})$")
_MAX_IDENTITY_CHARS = 128


class RuntimeProvenanceError(ValueError):
    """Malformed or internally inconsistent canonical provenance."""


def _identity(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RuntimeProvenanceError(f"{field} must be a string or null")
    clean = value.strip()
    if not clean:
        raise RuntimeProvenanceError(f"{field} must not be empty")
    if len(clean) > _MAX_IDENTITY_CHARS:
        raise RuntimeProvenanceError(f"{field} exceeds {_MAX_IDENTITY_CHARS} characters")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in clean):
        raise RuntimeProvenanceError(f"{field} contains control characters")
    return clean


def _build_record(
    executor_identity: str,
    *,
    values: Mapping[str, str | None],
    source: str,
    reason_code: str,
) -> dict[str, Any]:
    seat = _identity(executor_identity, "executor_identity")
    assert seat is not None
    runtime_values = {field: _identity(values.get(field), field) for field in RUNTIME_FIELDS}
    missing = [field for field in RUNTIME_FIELDS if runtime_values[field] is None]

    if source == "unavailable":
        if not missing:
            raise RuntimeProvenanceError("unavailable source cannot carry runtime values")
        status = "unavailable"
        evidence = "incomplete"
        if len(missing) != len(RUNTIME_FIELDS):
            raise RuntimeProvenanceError("unavailable source must not carry partial runtime values")
        if reason_code not in ("host_context_missing", "host_context_invalid"):
            raise RuntimeProvenanceError("invalid unavailable reason code")
    elif source == "host_launch_context":
        status = "incomplete" if missing else "complete"
        evidence = "incomplete" if missing else "available"
        expected_reason = "runtime_fields_missing" if missing else "none"
        if reason_code != expected_reason:
            raise RuntimeProvenanceError("runtime provenance reason does not match its fields")
    else:
        raise RuntimeProvenanceError("unknown runtime provenance source")

    return {
        "schema_version": SCHEMA_VERSION,
        "executor_identity": seat,
        **runtime_values,
        "provenance_source": source,
        "provenance_status": status,
        "benchmark_evidence": evidence,
        "reason_code": reason_code,
        "missing_fields": missing,
    }


def capture_runtime_provenance(
    executor_identity: str, *, env: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """Snapshot host launch metadata; never accept an explicit CLI path here."""
    try:
        info = load_runtime_info(env=env)
    except RuntimeInfoError:
        return _build_record(
            executor_identity,
            values={},
            source="unavailable",
            reason_code="host_context_invalid",
        )

    if info["source"] != "environment" or not info["present"]:
        return _build_record(
            executor_identity,
            values={},
            source="unavailable",
            reason_code="host_context_missing",
        )

    values = {
        "runtime_provider": info["provider"],
        "runtime_model": info["model"],
        "runtime_effort": info["effort"],
    }
    missing = any(values[field] is None for field in RUNTIME_FIELDS)
    return _build_record(
        executor_identity,
        values=values,
        source="host_launch_context",
        reason_code="runtime_fields_missing" if missing else "none",
    )


def _canonical_json(record: Mapping[str, Any]) -> bytes:
    return json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def seal_runtime_provenance(record: Mapping[str, Any]) -> str:
    """Encode canonical JSON and its digest as one LOG-safe token."""
    if set(record) != _FIELDS:
        raise RuntimeProvenanceError("runtime provenance has unsupported or missing fields")
    rebuilt = _build_record(
        str(record.get("executor_identity") or ""),
        values={field: record.get(field) for field in RUNTIME_FIELDS},
        source=str(record.get("provenance_source") or ""),
        reason_code=str(record.get("reason_code") or ""),
    )
    if dict(record) != rebuilt:
        raise RuntimeProvenanceError("runtime provenance fields are inconsistent")
    body = _canonical_json(rebuilt)
    encoded = base64.urlsafe_b64encode(body).decode("ascii").rstrip("=")
    return f"{encoded}.{hashlib.sha256(body).hexdigest()}"


def parse_runtime_provenance(token: str) -> dict[str, Any]:
    """Verify digest, canonical serialization, schema, and derived statuses."""
    match = _TOKEN_RE.fullmatch(token)
    if match is None:
        raise RuntimeProvenanceError("token syntax is invalid")
    encoded, expected_digest = match.groups()
    try:
        body = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (ValueError, base64.binascii.Error):
        raise RuntimeProvenanceError("token body is not valid base64url") from None
    actual_digest = hashlib.sha256(body).hexdigest()
    if actual_digest != expected_digest:
        raise RuntimeProvenanceError("integrity digest mismatch")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise RuntimeProvenanceError(f"duplicate field {key!r}")
            result[key] = value
        return result

    try:
        record = json.loads(body.decode("utf-8", errors="strict"), object_pairs_hook=unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeProvenanceError("token body is not valid UTF-8 JSON") from None
    if not isinstance(record, dict) or set(record) != _FIELDS:
        raise RuntimeProvenanceError("record has unsupported or missing fields")
    if type(record.get("schema_version")) is not int or record["schema_version"] != SCHEMA_VERSION:
        raise RuntimeProvenanceError("unsupported schema version")
    if not isinstance(record.get("missing_fields"), list) or any(
        not isinstance(field, str) for field in record["missing_fields"]
    ):
        raise RuntimeProvenanceError("missing_fields must be a string array")
    try:
        rebuilt = _build_record(
            record["executor_identity"],
            values={field: record.get(field) for field in RUNTIME_FIELDS},
            source=record.get("provenance_source"),
            reason_code=record.get("reason_code"),
        )
    except (KeyError, RuntimeProvenanceError):
        raise RuntimeProvenanceError("record fields are invalid") from None
    if record != rebuilt or _canonical_json(record) != body:
        raise RuntimeProvenanceError("record is noncanonical or internally inconsistent")
    return {**record, "integrity_digest": actual_digest}
