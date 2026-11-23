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


def write_qualification_artifact(root, receipt_id, finding_id=None):
    """Write a qualification artifact and record it as a producer qualification.

    Publication requires the qualification receipt to resolve to an artifact
    whose bytes hash to the digest in the receipt (CORE-006). T-1967 adds the
    other half: the digest match alone is self-consistency, because both values
    came from whoever built the finding, so a caller with write access could mint
    its own qualification. A fixture therefore has to register the qualification
    through `record_qualification`, the product's only writer of that log. When
    `finding_id` is omitted the file is written but nothing is recorded, which
    keeps the "unbound proof is refused" fixtures able to build exactly that.
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
    if finding_id:
        from producer_backends import saipal_adapter

        recorded = saipal_adapter.SaipalAdapter(saipal_home=root).record_qualification(
            root,
            finding_id,
            artifact_digest=digest,
            publication_scope=saipal_adapter.PUBLICATION_SCOPE_DEFAULT,
        )
        if not recorded.get("ok"):
            raise AssertionError(f"fixture qualification failed: {recorded}")
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


def write_canonical_worker_mutation(
    root: Path,
    attempt: dict,
    *,
    rel_path: str = "src/work.txt",
    content: str = "work\n",
    op_id: str | None = None,
    advance_log: bool = True,
) -> dict:
    """Simulate a current-attempt-bound mutation and COMMITTED receipt.

    Writes fixture bytes directly, not through the canonical journal lifecycle.
    Binds campaign attempt, generation, lineage and on-disk target hash.
    """
    import datetime
    from saipen_engine.journal import _hash_file, validate_op_id
    from saipen_engine.paths import project_lineage_identity

    target_path = root / rel_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")

    generation = int(attempt.get("generation", 1))
    if not op_id:
        op_id = f"op-{uuid.uuid4().hex[:12]}"
    validate_op_id(op_id)

    op_dir = root / ".saipen" / "recovery" / "ops" / op_id
    op_dir.mkdir(parents=True, exist_ok=True)

    lineage = project_lineage_identity(root) or "lineage-0123456789abcdef0123456789abcdef"
    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if attempt.get("started_at") and str(attempt["started_at"]) > now_utc:
        now_utc = str(attempt["started_at"])

    rec = {
        "op_id": op_id,
        "status": "COMMITTED",
        "operation": "worker_mutation",
        "semantic_payload_hash": f"sha256:{hashlib.sha256(content.encode()).hexdigest()}",
        "created_at": now_utc,
        "agent": "worker",
        "project_identity": "test-project",
        "project_lineage": lineage,
        "progress_index": 0,
        "targets": [
            {
                "path": rel_path,
                "role": "generic",
                "action": "write",
                "applied": True,
                "before_hash": "",
                "after_hash": _hash_file(target_path),
            }
        ],
        "receipt_metadata": {
            "attempt_id": attempt.get("attempt_id"),
            "campaign_id": attempt.get("campaign_id"),
            "worker_generation": generation,
        },
    }
    (op_dir / "operation.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")

    if advance_log:
        log_file = root / ".saipen" / "LOG.md"
        log_entry = f"- 25.10.26 20:01 [E-{100 + generation}] [agent: worker] RUN: WORK GEN {generation}\n"
        if log_file.exists():
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        else:
            log_file.write_text(f"# LOG\n{log_entry}", encoding="utf-8")

    return {
        "ok": True,
        "op_id": op_id,
        "wrote": True,
        "progress_class": "SOURCE_CHANGED",
    }
