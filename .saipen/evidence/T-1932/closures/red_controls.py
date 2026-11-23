"""Independent red controls for the four still-open SRC-338 counterexamples.

Each control builds an isolated temporary project, exercises the public engine
surface, and prints the observed verdict. A printed value that reads like
success is the counterexample: the repair must flip it to a typed refusal.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import campaign, host_dispatch, saipal_adapter  # noqa: E402
from saipen_engine import saipal_adapter as SA  # noqa: E402


def fresh_project(tmp: Path) -> Path:
    proj = tmp / "proj"
    (proj / ".saipen" / "campaign").mkdir(parents=True)
    (proj / ".saipen" / "STATE.md").write_text("---\nphase: BUILD\ntask: T-1\n---\n", encoding="utf-8")
    (proj / ".saipen" / "BOARD.md").write_text("# BOARD\n\n## DONE\n- [x] T-900 claimed\n", encoding="utf-8")
    (proj / ".saipen" / "LOG.md").write_text("- e1\n", encoding="utf-8")
    return proj


def core_004_acc(tmp: Path) -> dict:
    """A receipt that omits lineage and the accepted request digest."""
    proj = fresh_project(tmp)
    payload = host_dispatch.build_dispatch_payload(proj, campaign_id="C-1", iteration_id=2, worker_generation=3)
    receipt = {
        "schema_version": 1,
        "status": host_dispatch.HOST_ACCEPTED,
        "campaign_id": "C-1",
        "iteration_id": 2,
        "worker_generation": 3,
        "idempotency_key": payload["idempotency_key"],
        "accepting_host": "zaicode-host",
    }
    res = host_dispatch.dispatch_next_turn(proj, dict(payload), host_hook=lambda p: receipt)
    return {
        "callback_returned_receipt_without_lineage_or_digest": True,
        "status": res.get("status"),
        "dispatched": res.get("dispatched"),
        "detail": res.get("detail") or res.get("error"),
    }


def core_009_progress(tmp: Path) -> dict:
    proj = fresh_project(tmp)
    ctl = campaign.CampaignController(proj)
    observed = ctl._verify_progress_evidence(
        {
            "progress_verified": True,
            "before_event": "same",
            "after_event": "same",
            "before_state": "a",
            "after_state": "a",
        }
    )
    return {"self_asserted_progress_verified": observed["made_progress"], **observed}


def core_006_publication(tmp: Path) -> dict:
    proj = fresh_project(tmp)
    adapter = SA.SaipalAdapter(saipal_home=proj)
    body = "# finding\nclaim\n"
    import hashlib

    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    calls = []
    original = SA.audit_enqueue.enqueue
    SA.audit_enqueue.enqueue = lambda *a, **k: (calls.append(k) or {"ok": True, "layer": 7, "digest": "d", "idempotent": False})
    try:
        res = adapter.deliver_finding_to_audit_inbox(
            proj,
            {
                "finding_id": "PAL-FORGED",
                "state": "QUALIFIED",
                "qualification_receipt": {"receipt_id": "invented-by-caller"},
                "audit_body": body,
                "artifact_digest": digest,
            },
            publication_authorized=True,
        )
    finally:
        SA.audit_enqueue.enqueue = original
    return {
        "caller_named_qualification_receipt_accepted": bool(res.get("ok")),
        "status": res.get("status"),
        "enqueue_call_count": len(calls),
    }


def core_011_disposition(tmp: Path) -> dict:
    proj = fresh_project(tmp)
    adapter = SA.SaipalAdapter(saipal_home=proj)
    res = adapter.record_maintainer_disposition(
        proj,
        "PAL-1",
        disposition="VERIFIED",
        task_id="T-900",
        verification_evidence="ran 12 tests, all green",
    )
    return {
        "free_text_verification_accepted": bool(res.get("ok")),
        "status": res.get("status"),
        "error": res.get("error"),
    }


def main() -> int:
    out = {}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for name, fn in (
            ("CORE-004", core_004_acc),
            ("CORE-009", core_009_progress),
            ("CORE-006", core_006_publication),
            ("CORE-011", core_011_disposition),
        ):
            sub = tmp / name
            sub.mkdir()
            try:
                out[name] = fn(sub)
            except Exception as exc:  # noqa: BLE001
                out[name] = {"raised": type(exc).__name__, "detail": str(exc)}
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
