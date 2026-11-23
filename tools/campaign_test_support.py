"""Simulated scoped issuer for campaign behavior contracts, never production use.

The independent campaign-authority kernel suite exercises real broker verification.
This fixture replaces that boundary only while testing unrelated campaign behavior.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
import uuid

from saipen_engine import campaign_authority as authority
from saipen_engine.operator_origin import context
from saipen_engine.pending_ingress import ingress_digest

_ISSUED = {}


def write_qualification_artifact(root, receipt_id):
    """Write a real qualification receipt file and return its digest-bound proof.

    Publication now requires the qualification receipt to resolve to an artifact
    whose bytes hash to the digest carried in the receipt. Fixtures that only
    need a passing finding therefore have to produce that artifact rather than
    name a receipt id, which is what CORE-006 proved was being accepted.
    """
    rel = f".saipen/campaign/qualifications/{receipt_id}.json"
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(
        {
            "receipt_id": receipt_id,
            "qualified_at": "2026-01-01T00:00:00Z",
            "state": "QUALIFIED",
        },
        indent=2,
        sort_keys=True,
    )
    path.write_text(body + "\n", encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "receipt_id": receipt_id,
        "artifact_path": rel,
        "qualification_digest": digest,
    }


def write_verification_receipt(root, name, payload=None):
    """Write a durable execution receipt under .saipen/ and return its path.

    VERIFIED dispositions now require evidence that resolves to a real file
    under .saipen/; a phrase like "unit_tests:PASS" was accepted as evidence
    before CORE-011 proved the phrase alone proves nothing.
    """
    rel = f".saipen/evidence/{name}.json"
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload or {"tests_run": 1, "result": "pass"}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return rel


def write_scoped_fixture_grant(root):
    scope = context(root)
    authorization = {
        "kind": authority.CAPSULE_KIND,
        "schema_version": 1,
        "campaign_limit": 1,
        "project_lineage": scope["lineage"],
        "target_project": str(root),
        "host": "claude",
        "session": "contract-session",
        "goal_binding": {"goal_ingress": scope["goal"], "authority_source": scope["budget"]},
        "authorized_scopes": sorted(authority.ALL_SCOPES),
        "resource_budget": {
            "max_generations": 1000,
            "max_cycles": 1000,
            "max_wall_seconds": 200000,
        },
        "expires_at": time.time() + 200000,
    }
    text = json.dumps(authorization)
    proof = {
        "kind": "operator-origin",
        "nonce": uuid.uuid4().hex,
        "request_digest": ingress_digest(text),
    }
    carrier = {
        "kind": authority.CARRIER_KIND,
        "schema_version": 1,
        "request_text": text,
        "operator_origin": proof,
    }
    body = json.dumps(carrier, indent=2).encode("utf-8")
    path = root / ".saipen/authority/grant.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    _ISSUED[proof["nonce"]] = {
        "project": root.resolve(),
        "proof": proof,
        "text": text,
        "authorization": authorization,
        "digest": hashlib.sha256(body).hexdigest(),
        "admission": None,
    }
    return path


def inspect_fixture_campaign(
    proof,
    *,
    project,
    request_text,
    requested_scope,
    admission,
    consume=False,
    carrier_digest,
    receipt=None,
):
    issued = _ISSUED.get(proof.get("nonce"))
    if (
        not issued
        or issued["project"] != project.resolve()
        or issued["proof"] != proof
        or issued["text"] != request_text
        or issued["digest"] != carrier_digest
        or requested_scope not in (None, *issued["authorization"]["authorized_scopes"])
        or not authority.validate_admission(admission, issued["authorization"])
    ):
        return {"ok": False, "detail": "simulated issuer did not issue that scope"}
    if issued["admission"] is None and consume:
        issued["admission"] = copy.deepcopy(admission)
    if issued["admission"] != admission:
        return {"ok": False, "detail": "simulated issuer reservation differs"}
    return {
        "ok": True,
        "kind": "operator-campaign-verdict",
        "authorization": copy.deepcopy(issued["authorization"]),
        "admission": copy.deepcopy(admission),
        "carrier_digest": carrier_digest,
    }
