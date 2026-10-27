"""Decision B scope and independent origin for accepted historical debt.

Source integrity, reference syntax and a model-writable journal are not operator
permission. The existing separated event owner reserves one exact registration;
consumers recheck that reservation, including after a lineage-preserving move.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import goal_authority, intake
from .gate_decision import _instant
from .journal import hash_file_dependency
from .paths import project_lineage_identity

KIND = "saipen-accepted-debt-decision"
FIELDS = frozenset({"kind", "schema", "project_lineage", "check_id", "check_version",
                    "events", "event_hashes", "decision", "statement", "expires_at"})


def parse(text):
    from . import accepted_debt as debt

    value = goal_authority.parse_capsule(text)
    events = value.get("events")
    hashes = value.get("event_hashes")
    if (set(value) - FIELDS - {"supersedes"} or not set(value) >= FIELDS
            or value["kind"] != KIND or type(value["schema"]) is not int or value["schema"] != 1
            or not re.fullmatch(r"lineage-[0-9a-f]{32}", str(value["project_lineage"]))
            or value["check_id"] != debt.RULE_ID
            or type(value["check_version"]) is not int
            or value["check_version"] != debt.CHECK_VERSION
            or value["decision"] != "ACCEPT_LEGACY_DEBT"
            or not isinstance(events, list) or not 1 <= len(events) <= 4096
            or any(not isinstance(e, str) or debt.canonical_event_id(e) != e for e in events)
            or len(set(events)) != len(events)
            or events != sorted(events, key=lambda e: int(e[2:]))
            or not isinstance(hashes, dict) or set(hashes) != set(events)
            or any(not re.fullmatch(r"[0-9a-f]{64}", str(h)) for h in hashes.values())
            or not isinstance(value["statement"], str) or not value["statement"].strip()
            or len(value["statement"]) > 65536):
        raise ValueError("invalid exact accepted-debt decision scope")
    _instant(value["expires_at"])
    if "supersedes" in value:
        prior = value["supersedes"]
        if (not isinstance(prior, dict) or set(prior) != {"record_id", "sha256"}
                or not debt.ACCEPTED_DEBT_ID_RE.fullmatch(str(prior["record_id"]))
                or not re.fullmatch(r"[0-9a-f]{64}", str(prior["sha256"]))):
            raise ValueError("invalid immutable accepted-debt predecessor")
    return value


def scope(record):
    if not isinstance(record, dict):
        raise ValueError("accepted-debt record is malformed")
    evidence = record.get("evidence")
    if not isinstance(evidence, list) or any(not isinstance(e, dict) for e in evidence):
        raise ValueError("accepted-debt line evidence is malformed")
    hashes = {e.get("event"): e.get("line_sha256") for e in evidence}
    if len(hashes) != len(evidence):
        raise ValueError("accepted-debt event evidence is ambiguous")
    return {"project_lineage": record.get("project_lineage"),
            "check_id": record.get("check_id"), "check_version": record.get("check_version"),
            "events": record.get("accepted_missing_events"), "event_hashes": hashes}


def source_shape(root, record, dependencies=None):
    """Read a matching original capsule; authentication stays with the broker."""
    if not isinstance(record, dict):
        raise ValueError("authority UNKNOWN: accepted-debt record is malformed")
    receipt = record.get("authority")
    if not re.fullmatch(r"SRC-\d+", str(receipt)):
        raise ValueError("authority UNKNOWN: an event or lineage is not an operator Source")
    def source_pins():
        from .distribution import distribution_record_rel, quarantine_body_rel

        paths = [f"{base}/{receipt}{suffix}"
                 for base in (".saipen/intake/active", ".saipen/archive/source")
                 for suffix in (".md", ".meta.json")]
        paths.extend((distribution_record_rel(receipt), quarantine_body_rel(receipt)))
        return {rel: hash_file_dependency(Path(root) / rel) for rel in paths}

    pins = source_pins()
    # Reuse the source owner's bounded integrity and distribution readers.
    found = intake.read_body(root, receipt)
    meta = found.get("meta") or {}
    if not isinstance(meta, dict):
        raise ValueError("authority UNKNOWN: original Source metadata is malformed")
    if (not found.get("ok") or found.get("location") not in {"active", "archive"}
            or meta.get("source_kind") != "user_instruction"
            or meta.get("status") not in {intake.ACTIVE_STATUS, intake.CLOSED_STATUS}
            or meta.get("projection_policy") != intake.PROJECTION_AUTHORITY_ONLY
            or (found.get("distribution") or {}).get("state") != intake.DISTRIBUTABLE):
        raise ValueError("authority UNKNOWN: original scoped operator Source is absent or invalid")
    binding = parse(found.get("body") or "")
    if (project_lineage_identity(root) != binding["project_lineage"]
            or any(binding[k] != v for k, v in scope(record).items())):
        raise ValueError("authority UNKNOWN: the approval names different history or project scope")
    provenance = meta.get("request_provenance") or {}
    if not isinstance(provenance, dict):
        raise ValueError("authority UNKNOWN: original Source provenance is malformed")
    proof = provenance.get("operator_origin")
    if (provenance.get("witness") != "operator_carrier" or not isinstance(proof, dict)
            or proof.get("action") != "resolve-gate"):
        raise ValueError("authority UNKNOWN: the Source has no native Decision B event")
    if pins != source_pins():
        raise ValueError("authority UNKNOWN: original Source changed while being read")
    auth = {"receipt": receipt, "source_sha256": meta["source_sha256"],
            "binding": binding, "operator_origin": proof}
    if dependencies is not None:
        dependencies.update(pins)
    return auth


def record_bytes(record):
    return json.dumps(record, indent=2, sort_keys=True).encode("utf-8")


def record_intent(record):
    operational = {"created_at", "integrity_digest", "registration_attempt", "retry_of",
                   "registration_op_id", "journal_op_id"}
    return {k: v for k, v in record.items() if k not in operational}


def operation(record):
    material = (f"{record['project_lineage']}|{record['record_id']}|"
                f"{record['accepted_missing_events']}")
    attempt = record.get("registration_attempt", 0)
    if type(attempt) is not int or attempt < 0:
        raise ValueError("registration attempt must be a nonnegative integer")
    if attempt:
        material += f"|attempt:{attempt}"
    return "accepted_debt.register-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]


def authorize(root, record, dependencies):
    from .host_authority_client import prepare_operator_debt

    auth = source_shape(root, record, dependencies)
    record["authorization"] = auth
    record["registration_op_id"] = operation(record)
    record["journal_op_id"] = record["registration_op_id"]
    from .accepted_debt import _integrity_digest

    record["integrity_digest"] = _integrity_digest(record)
    canonical = prepare_operator_debt(auth["operator_origin"], project=root, record=record)
    if (not isinstance(canonical, dict) or record_intent(canonical) != record_intent(record)
            or canonical.get("registration_op_id") != operation(canonical)
            or canonical.get("journal_op_id") != canonical["registration_op_id"]
            or canonical.get("integrity_digest") != _integrity_digest(
                {k: v for k, v in canonical.items() if k != "integrity_digest"})):
        raise ValueError("authority UNKNOWN: no independently verified native registration intent")
    record.update(canonical)
    return auth


def status(root, record, *, pending=False):
    from .host_authority_client import verify_operator_debt

    try:
        if not isinstance(record, dict):
            raise ValueError("authority UNKNOWN: accepted-debt record is malformed")
        auth = record.get("authorization")
        if not isinstance(auth, dict) or auth != source_shape(root, record):
            raise ValueError("authority UNKNOWN: historical origin is not independently bound")
        if record.get("registration_op_id") != operation(record):
            raise ValueError("authority UNKNOWN: registration identity changed")
        if not verify_operator_debt(auth["operator_origin"], project=root,
                                    record=record, pending=pending):
            raise ValueError("authority UNKNOWN: the original native reservation is unverified")
        return {"authority_status": "KNOWN",
                "authority_reason": "scoped native Decision B verified"}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {"authority_status": "UNKNOWN", "authority_reason": str(exc)}
