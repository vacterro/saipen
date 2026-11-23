"""Measure which CORE findings of audit/27.md still reproduce.

Read-only against this repository's engine; every reproduction uses a
throwaway temporary project.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))

from saipen_engine import campaign, saipal_adapter  # noqa: E402


def project() -> Path:
    root = Path(tempfile.mkdtemp(prefix="t1944-core-"))
    (root / ".saipen" / "campaign").mkdir(parents=True)
    (root / ".saipen" / "BOARD.md").write_text(
        "## DOING\n## TODO\n## BLOCKED\n## DONE\n- [x] T-200 [P1] unrelated\n",
        encoding="utf-8",
    )
    return root


def qualify(root: Path, receipt_id: str) -> dict:
    rel = f".saipen/campaign/qualifications/{receipt_id}.json"
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"receipt_id": receipt_id, "state": "QUALIFIED"}), encoding="utf-8"
    )
    return {
        "receipt_id": receipt_id,
        "artifact_path": rel,
        "qualification_digest": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def finding(root: Path, fid: str, **extra) -> dict:
    body = f"# Audit Finding {fid}\nprobe\n"
    return {
        "finding_id": fid,
        "state": "QUALIFIED",
        "qualification_receipt": qualify(root, f"QUAL-{fid}"),
        "audit_body": body,
        "artifact_digest": hashlib.sha256(body.encode()).hexdigest(),
        **extra,
    }


def core_001() -> str:
    """Forged authenticated:true receipt published?"""
    root = project()
    forged = {
        "finding_id": "PAL-ABC",
        "state": "QUALIFIED",
        "qualification_receipt": {"authenticated": True, "signature": "obviously-forged"},
        "audit_body": "# forged\n",
        "artifact_digest": hashlib.sha256(b"# forged\n").hexdigest(),
    }
    res = saipal_adapter.SaipalAdapter().deliver_finding_to_audit_inbox(
        root, forged, publication_authorized=True
    )
    layers = list((root / "audit").glob("*.md")) if (root / "audit").is_dir() else []
    return f"ok={res.get('ok')} status={res.get('status')} layers={len(layers)}"


def core_002() -> str:
    """Delete state_digest from a valid terminal state; does inspection accept it?"""
    root = project()
    state = {
        "schema_version": campaign.CAMPAIGN_SCHEMA_VERSION,
        "campaign_id": "CAMP-PROBE",
        "campaign_state": campaign.COMPLETE,
        "worker_generation": 1,
        "cycle_count": 1,
    }
    campaign.save_campaign_state(root, state)
    valid = campaign.inspect_campaign_state(root)
    path = campaign.campaign_state_path(root)
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("state_digest")
    data["updated_at"] = data["updated_at"]  # keep writer's other field
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    after = campaign.inspect_campaign_state(root)
    ctrl = campaign.CampaignController(root)
    step = ctrl.step(worker_func=lambda r, g: {"progress_verified": True})
    return (
        f"valid={valid.get('status')} digestless={after.get('status')} "
        f"step_ok={step.get('ok')} step_status={step.get('status')}"
    )


def core_003() -> str:
    """Does the registry admit a continuous_maintenance grant?"""
    from saipen_engine import goal_authority

    reg = json.loads((REPO / "saipen" / "REGISTRY.json").read_text(encoding="utf-8-sig"))
    declared = reg["goal_authority"]["until"]
    # `grant_fields` takes the source and the scope only: it derives the valve
    # from the scope. Passing a `valve` keyword (as an earlier revision of this
    # probe did) raised TypeError in BOTH directions, so the line measured
    # nothing and the finding looked unrepaired regardless of the real state.
    grant = goal_authority.grant_fields("SRC-304", until="continuous_maintenance")
    fields = {
        "execution_intent": "goal",
        "continuation_authority": "operator_persistent",
        "authority_source": "SRC-304",
        "authority_until": "continuous_maintenance",
        "safety_valve_mode": "checkpoint",
        "goal_ingress": "goal-0123456789abcdef",
    }
    errors = goal_authority.shape_errors(fields)
    return f"registry_until={declared} grant={grant} shape_errors={errors}"


def core_004() -> str:
    """Does T-20 match a DONE T-200, and is BOARD.md accepted as evidence?"""
    root = project()
    adapter = saipal_adapter.SaipalAdapter()
    a = adapter.record_maintainer_disposition(
        root,
        "PAL-not-fixed",
        disposition="VERIFIED",
        task_id="T-20",
        verification_evidence=".saipen/BOARD.md",
    )
    b = adapter.record_maintainer_disposition(
        root,
        "PAL-not-fixed-2",
        disposition="VERIFIED",
        task_id="T-200",
        verification_evidence={"authenticated": True, "signature": "made-up"},
    )
    return f"T20_ok={a.get('ok')} T20={a.get('status')} fakeauth_ok={b.get('ok')} fakeauth={b.get('status')}"


def core_005() -> str:
    """Corrupt campaign state through the CLI status route."""
    root = project()
    path = campaign.campaign_state_path(root)
    path.write_text("{invalid", encoding="utf-8")
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "saipen.py"), "campaign", "status",
         "--project-root", str(root), "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return f"rc={proc.returncode} out={proc.stdout.strip()[:200]}"


if __name__ == "__main__":
    for name in ("core_001", "core_002", "core_003", "core_004", "core_005"):
        try:
            print(f"{name}: {globals()[name]()}")
        except Exception as exc:  # noqa: BLE001 - a probe reports, never crashes
            print(f"{name}: EXCEPTION {type(exc).__name__}: {exc}")
