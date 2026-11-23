"""Repeat the fixed native CLI and concurrent-writer controls on exact subjects."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from test_hermetic_env import hermetic_env

CASES = (
    "test_public_binding_preserves_original_finish_and_active_work",
    "test_intake_change_after_plan_refuses",
    "test_publication_after_plan_refuses",
    "test_registry_change_during_plan_is_not_overwritten",
)
PATHS = ("tools/saipen_engine/operations.py", "tools/saipen.py",
         "saipen/COMMANDS.md", "saipen/OPS.md")


def digest(parts):
    h = hashlib.sha256()
    for name, data in parts:
        h.update(name.encode("utf-8") + b"\0" + data + b"\0")
    return h.hexdigest()


def main():
    subject = sys.argv[1]
    if subject == "preserve-cas":
        for rel in PATHS:
            target = HERE / "pre-cas" / rel
            if target.exists():
                raise RuntimeError("pre-CAS subject already preserved")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / rel).read_bytes())
        print("pre-CAS bytes preserved")
        return 0
    if subject not in ("original", "pre-cas", "current"):
        raise ValueError(subject)
    verifier = digest([(name, (ROOT / name).read_bytes()) for name in (
        "tools/test_closure_provenance.py", "tools/test_orchestration_repair.py",
        "tools/test_hermetic_env.py")]
        + [("oracle.py", Path(__file__).read_bytes()),
           ("configuration", json.dumps({"cases": CASES, "timeout": 180}).encode())])
    with tempfile.TemporaryDirectory(prefix="saipen-T1605-oracle-") as temp:
        copied = Path(temp) / "subject"
        copied.mkdir()
        for name in ("tools", "saipen", "extensions", "bootstrap", "tests", "bin"):
            shutil.copytree(ROOT / name, copied / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for name in ("README.md", "VERSION"):
            shutil.copyfile(ROOT / name, copied / name)
        if subject != "current":
            source = HERE / ("before" if subject == "original" else "pre-cas")
            for rel in PATHS:
                shutil.copyfile(source / rel, copied / rel)
        subject_hash = digest([(rel, (copied / rel).read_bytes()) for rel in PATHS])
        cases = ["test_closure_provenance.ClosedCohortBindingTests." + case for case in CASES]
        result = subprocess.run([sys.executable, "-B", "-m", "unittest", *cases],
            cwd=copied / "tools", env=hermetic_env(), capture_output=True,
            text=True, encoding="utf-8", timeout=180)
        match = re.search(r"Ran (\d+) tests", result.stderr)
        count = int(match.group(1)) if match else 0
        receipt = {"subject_name": subject, "subject": subject_hash, "verifier": verifier,
                   "exit_code": result.returncode, "ran": count,
                   "verdict": "PASS" if result.returncode == 0 and count == len(CASES) else "FAIL",
                   "stdout": result.stdout, "stderr": result.stderr}
    destination = HERE / (subject + "-oracle.json")
    destination.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: receipt[key] for key in (
        "subject_name", "subject", "verifier", "verdict", "ran", "exit_code")}))
    return 0 if count == len(CASES) else 2


if __name__ == "__main__":
    raise SystemExit(main())
