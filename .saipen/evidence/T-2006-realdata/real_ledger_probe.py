"""Real-data probe: run the fixed provider against the ACTUAL _BZ_REA coverage
ledger (12521 gaps, 14122 procedures) and the ACTUAL capture binary.

This is not a fixture. It reads the live producer output and the live 5.1 MB
capture, binds the computed sha256 as required_capture_sha256, places a copy of
the capture under the probe root so lineage VERIFIES, and reports what the fixed
provider answers. Read-only outside its own temp dir.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[3] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.discovery_providers import EvidenceGapLedgerProvider  # noqa: E402
from saipen_engine.persistent_goal import PersistentGoal  # noqa: E402

REAL_LEDGER = Path(r"V:\___VAC\__K\__CODE\_MISC\_BZ_REA\evidence\deep\coverage\coverage.json")
REAL_CAPTURE = Path(
    r"V:\___VAC\__K\__CODE\_MISC\_BZDECOMP\.freebuff\public-port-185\public-2.0.185-live.exe"
)


def main() -> int:
    report: dict = {"schema": 1, "kind": "real_ledger_probe"}
    ledger_bytes = REAL_LEDGER.read_bytes()
    ledger = json.loads(ledger_bytes)
    report["ledger_path"] = str(REAL_LEDGER)
    report["ledger_sha256"] = hashlib.sha256(ledger_bytes).hexdigest()
    report["capture_path"] = str(REAL_CAPTURE)
    report["capture_exists"] = REAL_CAPTURE.is_file()

    capture_sha = hashlib.sha256(REAL_CAPTURE.read_bytes()).hexdigest()
    report["capture_sha256"] = capture_sha
    counts = ledger.get("counts") or {}
    report["producer_counts"] = {
        "procedures": counts.get("procedures"),
        "described_procedures": counts.get("described_procedures"),
        "gap_procedures": counts.get("gap_procedures"),
        "independently_verified_procedures": counts.get("independently_verified_procedures"),
    }
    report["ledger_declared_capture_sha256"] = (
        (ledger.get("sources") or {}).get("capture") or {}
    ).get("sha256")

    root = Path(tempfile.mkdtemp(prefix="saipen_real_ledger_")).resolve()
    try:
        (root / ".saipen" / "goals").mkdir(parents=True, exist_ok=True)
        (root / ".saipen" / "evidence").mkdir(parents=True, exist_ok=True)
        (root / ".saipen" / "BOARD.md").write_text(
            "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n\n## BLOCKED\n", encoding="utf-8"
        )
        # Place the real capture under the probe root at the ledger's declared
        # relative path so the provider can derive and verify the digest.
        declared_rel = ((ledger.get("sources") or {}).get("capture") or {}).get("path") or "capture.exe"
        declared_rel = declared_rel.replace("/", os.sep)
        if declared_rel.startswith("_BZDECOMP"):
            declared_rel = declared_rel.replace("_BZDECOMP", "capture_root", 1)
        dest = root / declared_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REAL_CAPTURE, dest)

        rooted = json.loads(ledger_bytes)
        rooted["sources"]["capture"]["path"] = declared_rel
        led_path = root / ".saipen" / "evidence" / "coverage.json"
        led_path.write_text(json.dumps(rooted), encoding="utf-8")

        goal = PersistentGoal(
            goal_id="G-REAL-BZ",
            project_id="BZ_REA-REAL",
            title="Document all remaining BZ_REA procedures",
            objective="Document every remaining BZ_REA procedure with verified semantics",
            success_criteria={
                "capture_sha256": capture_sha,
                "coverage_percent": 100.0,
            },
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
            admission_policy={"max_candidates_per_evaluation": 5},
        )
        provider = EvidenceGapLedgerProvider()
        result = provider.evaluate(root, goal)
        report["evaluation"] = {
            "satisfaction_status": result.satisfaction_status,
            "completeness_status": result.completeness_status,
            "metrics": {k: v for k, v in (result.metrics or {}).items()},
            "blockers": list(result.blockers or []),
            "candidate_count": len(result.actionable_candidates or []),
            "summary": result.summary,
        }
        cands = result.actionable_candidates or []
        if cands:
            c0 = cands[0]
            report["first_candidate"] = {
                "candidate_id": c0.candidate_id,
                "evidence_fingerprint": c0.evidence_fingerprint,
                "target_locator": str(c0.target_locator),
            }
        # Per-item stability: changing one unrelated gap must not move the
        # fingerprint of an unchanged item (P1-04), while a real byte change of
        # the item itself must (genuine reanalysis).
        if cands:
            mut = json.loads(json.dumps(rooted))
            mut["gap"] = list(mut["gap"]) + [{"id": "unrelated-marker", "name": "x", "bytes": 1}]
            led_path.write_text(json.dumps(mut), encoding="utf-8")
            goal2 = PersistentGoal(
                goal_id="G-REAL-BZ",
                project_id="BZ_REA-REAL",
                title="Document all remaining BZ_REA procedures",
            objective="Document every remaining BZ_REA procedure with verified semantics",
                success_criteria={"capture_sha256": capture_sha, "coverage_percent": 100.0},
                research_or_work_backlog_source=".saipen/evidence/coverage.json",
                admission_policy={"max_candidates_per_evaluation": 5},
            )
            res2 = provider.evaluate(root, goal2)
            c2 = (res2.actionable_candidates or [])
            report["unrelated_change_candidate0_fingerprint"] = (
                c2[0].evidence_fingerprint if c2 else None
            )
            report["fingerprint_stable_under_unrelated_change"] = bool(
                c2 and c2[0].evidence_fingerprint == c0.evidence_fingerprint
            )
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
