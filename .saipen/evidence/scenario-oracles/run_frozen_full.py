"""Run the unchanged complete scenario gate on one settled source snapshot."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import core_unit
from saipen_engine.evidence import EvidenceRun
from saipen_engine.test_runner import _ignore_copy
from test_hermetic_env import hermetic_env


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    evidence = EvidenceRun("t1603-full-scenarios", "T-1603", durable_dir=HERE / "full-current")
    subject = evidence.temp_root / "home"
    evidence.register_ephemeral(subject)
    fingerprint = core_unit.tree_fingerprint(ROOT)
    core_unit.copy_tree_consistent(ROOT, subject, _ignore_copy)
    assert core_unit.tree_fingerprint(subject) == fingerprint
    assert core_unit.tree_fingerprint(ROOT) == fingerprint
    command = [sys.executable, str(subject / "tools/run_scenarios.py")]
    env = hermetic_env()
    assert not any(key.startswith("SAIPEN_") and key.endswith("_PROBES_ONLY")
                   and value == "1" for key, value in env.items())
    binding = {"command": command, "source_root": str(ROOT), "snapshot": str(subject),
               "fingerprint": fingerprint, "baseline_sha256": core_unit.baseline_digest(subject),
               "scenario_sha256": sha(subject / "tools/run_scenarios.py"),
               "snapshot_state_sha256": sha(subject / ".saipen/STATE.md"),
               "snapshot_board_sha256": sha(subject / ".saipen/BOARD.md"),
               "snapshot_log_sha256": sha(subject / ".saipen/LOG.md"),
               "mode": "complete native scenario gate; no selector or new timeout",
               "wrapper_sha256": sha(Path(__file__))}
    (evidence.durable_dir / "binding.json").write_text(json.dumps(binding, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(binding), flush=True)
    output = evidence.temp_root / "scenario-output.txt"
    started = time.monotonic()
    with output.open("wb") as handle:
        result = subprocess.run(command, cwd=subject, env=env, stdout=handle,
                                stderr=subprocess.STDOUT)
    raw = output.read_text(encoding="utf-8", errors="replace")
    footer = re.search(r"(\d+) of (\d+) probe group\(s\) reached a verdict; "
                       r"(\d+) grouped check\(s\) executed", raw)
    counts = tuple(map(int, footer.groups())) if footer else (0, 0, 0)
    unchanged_snapshot = core_unit.tree_fingerprint(subject) == fingerprint
    unchanged_live = core_unit.tree_fingerprint(ROOT) == fingerprint
    passed = (result.returncode == 0 and counts[0] == counts[1] and counts[0] > 0
              and counts[2] > 0 and unchanged_snapshot and unchanged_live)
    retained = evidence.retain(output, name="verify-scenarios.txt",
                               large_evidence_required="Complete native gate output preserves every declared group's verdict and all failures.")
    report = {"verdict": "PASS" if passed else "FAIL", "exit_code": result.returncode,
              "completed_groups": counts[0], "declared_groups": counts[1], "checks": counts[2],
              "fingerprint": fingerprint, "snapshot_unchanged": unchanged_snapshot,
              "live_source_unchanged": unchanged_live, "output_sha256": sha(retained),
              "seconds": round(time.monotonic() - started, 3)}
    (evidence.durable_dir / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)
    evidence.finalize(verdict=report["verdict"], extra={"scenario_gate": report})
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
