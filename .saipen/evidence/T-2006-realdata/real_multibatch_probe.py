"""Real-data probe for R007: multi-batch research progress + durable recovery.

Uses the ACTUAL _BZ_REA coverage ledger (12521 gaps) and the ACTUAL capture.
Shows that successive evaluations of ONE goal advance a bounded cursor across
different gap items (multi-batch progress), that the cursor is durable across a
save/load cycle (recovery), and that no batch re-admits an already-emitted item.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[3] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.discovery_providers import EvidenceGapLedgerProvider  # noqa: E402
from saipen_engine.persistent_goal import PersistentGoal, save_goal, get_goal  # noqa: E402

REAL_LEDGER = Path(r"V:\___VAC\__K\__CODE\_MISC\_BZ_REA\evidence\deep\coverage\coverage.json")
REAL_CAPTURE = Path(
    r"V:\___VAC\__K\__CODE\_MISC\_BZDECOMP\.freebuff\public-port-185\public-2.0.185-live.exe"
)


def _goal(capture_sha: str) -> PersistentGoal:
    return PersistentGoal(
        goal_id="G-REAL-BATCH",
        project_id="BZ_REA-REAL",
        title="Document all remaining BZ_REA procedures",
        objective="Document every remaining BZ_REA procedure with verified semantics",
        success_criteria={"capture_sha256": capture_sha, "coverage_percent": 100.0},
        research_or_work_backlog_source=".saipen/evidence/coverage.json",
        admission_policy={"max_candidates_per_evaluation": 4},
    )


def main() -> int:
    report: dict = {"schema": 1, "kind": "real_multibatch_probe"}
    ledger_bytes = REAL_LEDGER.read_bytes()
    ledger = json.loads(ledger_bytes)
    capture_sha = hashlib.sha256(REAL_CAPTURE.read_bytes()).hexdigest()

    root = Path(tempfile.mkdtemp(prefix="saipen_real_batch_")).resolve()
    try:
        (root / ".saipen" / "goals").mkdir(parents=True, exist_ok=True)
        (root / ".saipen" / "evidence").mkdir(parents=True, exist_ok=True)
        (root / ".saipen" / "BOARD.md").write_text(
            "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n\n## BLOCKED\n", encoding="utf-8"
        )
        declared_rel = str(
            ((ledger.get("sources") or {}).get("capture") or {}).get("path") or "capture.exe"
        ).replace("/", "\\")
        declared_rel = declared_rel.replace("_BZDECOMP", "capture_root", 1)
        dest = root / declared_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REAL_CAPTURE, dest)
        rooted = json.loads(ledger_bytes)
        rooted["sources"]["capture"]["path"] = declared_rel.replace("\\", "/")
        (root / ".saipen" / "evidence" / "coverage.json").write_text(
            json.dumps(rooted), encoding="utf-8"
        )

        provider = EvidenceGapLedgerProvider()
        goal = _goal(capture_sha)
        batches = []
        seen: list[str] = []
        for i in range(3):
            res = provider.evaluate(root, goal)
            ids = [c.candidate_id for c in (res.actionable_candidates or [])]
            cursor = int((goal.resume_metadata or {}).get("cursor_index", -1))
            batches.append(
                {
                    "batch": i,
                    "cursor_after": cursor,
                    "candidate_ids": ids,
                    "repeats_prior_batch": [x for x in ids if x in seen],
                }
            )
            seen.extend(ids)

        # Durable recovery: save the goal, drop the in-memory copy, reload it,
        # and confirm the cursor survives and the next batch continues (does not
        # restart from zero).
        save_goal(root, goal)
        cursor_saved = int((goal.resume_metadata or {}).get("cursor_index", -1))
        reloaded = get_goal(root, "G-REAL-BATCH")
        cursor_reloaded = int((reloaded.resume_metadata or {}).get("cursor_index", -1))
        res_after = provider.evaluate(root, reloaded)
        ids_after = [c.candidate_id for c in (res_after.actionable_candidates or [])]

        report["capture_sha256"] = capture_sha
        report["producer_gap_count"] = (ledger.get("counts") or {}).get("gap_procedures")
        report["batches"] = batches
        report["cursor_advanced_across_batches"] = bool(
            batches[0]["cursor_after"] != batches[1]["cursor_after"] != batches[2]["cursor_after"]
        )
        report["no_batch_repeats_a_prior_item"] = all(
            not b["repeats_prior_batch"] for b in batches
        )
        report["cursor_saved"] = cursor_saved
        report["cursor_reloaded"] = cursor_reloaded
        report["durable_cursor_survived_save_load"] = cursor_saved == cursor_reloaded
        report["post_recovery_first_candidate"] = ids_after[0] if ids_after else None
        report["post_recovery_cursors_forward"] = bool(
            ids_after and ids_after[0] not in [b["candidate_ids"][0] for b in batches if b["candidate_ids"]]
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
