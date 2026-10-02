"""Same-oracle red/green pair for T-1575 (VERIFY-ORACLE-01).

The oracle (the T-1575 tests plus the inflight owner they exercise) is held
fixed; only the wiring owners change: pre-fix admission/core_unit/saipen.py
versus the current ones. Red must be behavioral -- the module alone enforces
nothing; the guard, the turn-entry projection and the runner wiring do.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.oracle import oracle_digest, verifier_identity  # noqa: E402

SUBJECTS = {
    "tools/saipen_engine/admission.py": "admission.py",
    "tools/saipen_engine/core_unit.py": "core_unit.py",
    "tools/saipen.py": "saipen.py",
}
COMMAND = "python -B -m unittest -v test_t1575_parallel_lane"
ORACLE = [
    "tools/test_t1575_parallel_lane.py",
    "tools/saipen_engine/inflight.py",
    "tools/test_guard_hostile_matrix.py",
    "tools/test_hermetic_env.py",
]
label_prefix = sys.argv[1] if len(sys.argv) > 1 else "pair"

with tempfile.TemporaryDirectory(prefix="saipen-t1575-oracle-") as directory:
    snapshot = Path(directory).resolve()
    for name in ("tools", "saipen", "extensions", "bootstrap", "bin", "tests"):
        shutil.copytree(ROOT / name, snapshot / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for file in ROOT.iterdir():
        if file.is_file():
            shutil.copy2(file, snapshot / file.name)
    environment = {k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")}
    environment["PYTHONPATH"] = str(snapshot / "tools")
    environment["PYTHONUTF8"] = "1"
    verifier = verifier_identity(COMMAND, ORACLE, snapshot)
    manifest = {"verifier": verifier, "command": COMMAND, "oracle": ORACLE, "runs": []}
    for label in ("red", "green"):
        for relative, original in SUBJECTS.items():
            source = EVIDENCE / "pre-fix" / original if label == "red" else ROOT / relative
            shutil.copy2(source, snapshot / relative)
        assert verifier_identity(COMMAND, ORACLE, snapshot) == verifier, "oracle drifted"
        subject = oracle_digest(snapshot, list(SUBJECTS))
        out = EVIDENCE / f"{label_prefix}-{label}.txt"
        with out.open("w", encoding="utf-8") as output:
            result = subprocess.run(
                [sys.executable, "-B", "-m", "unittest", "-v", "test_t1575_parallel_lane"],
                cwd=snapshot / "tools", env=environment, stdout=output,
                stderr=subprocess.STDOUT, timeout=900)
        tail = out.read_text(encoding="utf-8").strip().splitlines()[-1]
        errors = sum(1 for line in out.read_text(encoding="utf-8").splitlines()
                     if line.startswith("ERROR:"))
        manifest["runs"].append({"label": label, "subject": subject,
                                 "returncode": result.returncode, "verdict": tail,
                                 "errors": errors})
        print(label, result.returncode, subject, tail, "errors:", errors, flush=True)
    (EVIDENCE / f"{label_prefix}-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    assert manifest["runs"][0]["returncode"] != 0
    assert manifest["runs"][1]["returncode"] == 0
    print("verifier", verifier)
