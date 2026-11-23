"""Read-only current acceptance for SRC-070's historical local commit."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.board import parse_board
from saipen_engine.core_unit import baseline_digest, tree_fingerprint

EXPECTED_PATHS = {"saipen/IMPROVE.md", "saipen/REGISTRY.json", "tools/improve.py",
                  "tools/run_scenarios.py", "tools/saipen.py"}
PRESERVED_COMMIT = "2eecc65c00ed9667b7c5f70259c05f97b062ee2d"


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", check=True, timeout=30).stdout.strip()


def main():
    label, commit = sys.argv[1:3]
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    source = ROOT / ".saipen/intake/active/SRC-070.md"
    meta = json.loads(source.with_suffix(".meta.json").read_text(encoding="utf-8"))
    contract = json.loads((ROOT / ".saipen/intake/contracts/SRC-070.json").read_text(encoding="utf-8"))
    board = parse_board((ROOT / ".saipen/BOARD.md").read_text(encoding="utf-8"))
    paths = set(git("diff-tree", "--no-commit-id", "--name-only", "-r", commit).splitlines())
    current = tree_fingerprint(ROOT)
    unit = json.loads((ROOT / ".saipen/evidence/core-unit/54ad859af386ae71-20261003T135812Z.json").read_text(encoding="utf-8"))
    scenario_dir = ROOT / ".saipen/evidence/scenario-review/full-current"
    scenario = json.loads((scenario_dir / "result.json").read_text(encoding="utf-8"))
    binding = json.loads((scenario_dir / "binding.json").read_text(encoding="utf-8"))
    checks = {
        "exact_source_integrity": sha(source) == meta["source_sha256"] == contract["source_sha256"],
        "exact_five_reviewed_paths": paths == EXPECTED_PATHS,
        "requested_commit_ancestral": subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT).returncode == 0,
        "later_preserved_scope_ancestral": subprocess.run(["git", "merge-base", "--is-ancestor", PRESERVED_COMMIT, "HEAD"], cwd=ROOT).returncode == 0,
        "separate_preserved_commit": git("rev-parse", PRESERVED_COMMIT + "^") == commit,
        "implementation_work_done": all(board["tickets"][ticket]["section"] == "## DONE"
                                        for ticket in ("T-1406", "T-1400", "T-1603")),
        "current_complete_unit_family": (unit["fingerprint"] == current and unit["baseline_sha256"] == baseline_digest(ROOT)
            and unit["exit_code"] == 0 and unit["verdict"] == "PASS" and unit["ran"] == unit["discovered"] == 4855
            and not unit["red"] and not unit["new_red"] and not unit.get("partition_error")),
        "current_complete_scenario_gate": (scenario["fingerprint"] == current == binding["fingerprint"]
            and scenario["exit_code"] == 0 and scenario["completed_groups"] == scenario["declared_groups"] == 44
            and scenario["checks"] == 1354 and scenario["output_sha256"] == sha(scenario_dir / "verify-scenarios.txt")
            and binding["scenario_sha256"] == sha(ROOT / "tools/run_scenarios.py")
            and scenario["snapshot_unchanged"] and scenario["live_source_unchanged"]),
    }
    record = {"label": label, "commit": commit, "paths": sorted(paths),
              "head": git("rev-parse", "HEAD"), "fingerprint": current,
              "verifier_sha256": sha(Path(__file__)), "checks": checks,
              "failures": sum(not passed for passed in checks.values()),
              "limits": ["Local ancestry is not remote publication evidence.",
                         "Historical model_supplied provenance is not upgraded.",
                         "Native scenario proof and failed collector finalization are separate; T-1604 owns the latter."]}
    (HERE / (label + ".json")).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record))
    return int(record["failures"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
