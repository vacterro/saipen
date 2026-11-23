"""Current bounded foreign-tail checks; the preserved pre-fix carrier is read-only."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OLD = ROOT / ".saipen/kitchen/t1565-goalresume-prefix-20260930"
PUBLIC = "test_log_tail_quarantine.QuarantineLogTailTests.test_public_recovery_same_damage_preserves_bytes_and_resumes"
MODULES = ["test_log_tail_quarantine", "test_log_stamp_guard",
           "test_foreign_observation_authority", "test_foreign_owner_terminal_route"]
SUBJECTS = ["tools/saipen_engine/log.py", "tools/saipen_engine/operations.py",
            "tools/saipen_engine/reconcile.py", "tools/_log_append.py",
            "tools/saipen_engine/runtime_namespace.py", ".gitattributes"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root: Path, targets: list[str], label: str) -> dict:
    command = [sys.executable, "-m", "unittest", "-v", *targets]
    before = {path: sha(root / path) for path in SUBJECTS}
    result = subprocess.run(command, cwd=root / "tools", capture_output=True,
                            timeout=600)
    output = result.stdout + result.stderr
    (HERE / (label + ".txt")).write_bytes(output)
    after = {path: sha(root / path) for path in SUBJECTS}
    return {"command": command, "cwd": str(root / "tools"),
            "exit_code": result.returncode, "subject_sha256": before,
            "subject_unchanged": before == after,
            "verifier_test_sha256": sha(root / "tools/test_log_tail_quarantine.py"),
            "output_sha256": hashlib.sha256(output).hexdigest(),
            "output": output.decode("utf-8", errors="replace")}


def main() -> int:
    label = sys.argv[1]
    red = run(OLD, [PUBLIC], label + "-known-bad")
    green = run(ROOT, [PUBLIC], label + "-public-green")
    focused = run(ROOT, MODULES, label + "-focused")
    checks = {
        "same_public_oracle": red["verifier_test_sha256"] == green["verifier_test_sha256"],
        "behavioral_prefixed_runtime_rejected": (red["exit_code"] == 1
            and "Ran 1 test" in red["output"] and "FAILED (failures=1)" in red["output"]
            and "FORENSICALLY_UNRECOVERABLE" in red["output"]
            and "None != 'saipen recover quarantine-log-tail'" in red["output"]),
        "current_public_control_passes": (green["exit_code"] == 0
            and "Ran 1 test" in green["output"] and "OK" in green["output"].splitlines()),
        "all_40_focused_controls_pass": (focused["exit_code"] == 0
            and "Ran 40 tests" in focused["output"] and "OK" in focused["output"].splitlines()),
        "subject_bytes_unchanged": all(run["subject_unchanged"] for run in (red, green, focused)),
    }
    record = {"label": label, "verifier_sha256": sha(Path(__file__)),
              "checks": checks, "failures": sum(not passed for passed in checks.values()),
              "red": red, "green": green, "focused": focused,
              "limits": ["Historical source provenance is not upgraded.",
                         "The pre-fix carrier is a preserved implementation control.",
                         "Admission and remote publication remain outside this repair closure."]}
    (HERE / (label + ".json")).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: record[key] for key in ("label", "verifier_sha256", "checks", "failures")}))
    return int(record["failures"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
