"""Same-oracle red/green pair for T-1578 (VERIFY-ORACLE-01).

The oracle (the T-1578 carrier plus the T-1572 fixture it reuses) is held
fixed; only the subject changes: the preserved pre-fix `reconcile.py` versus
the repaired one. RED is behavioral -- the proposal refuses with
VALIDATION_FAILED because `STATE.agent` keeps the recovery actor while the
reopened BOARD row keeps its own owner. No import/collection error.
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

SUBJECTS = {"tools/saipen_engine/reconcile.py": "reconcile.py"}
COMMAND = "python -B -m unittest -v test_t1578_restore_owner"
ORACLE = [
    "tools/test_t1578_restore_owner.py",
    "tools/test_t1572_ticket_scoped_recovery.py",
    "tools/saipen_engine/ownership.py",
    "tools/saipen_engine/fast_check.py",
]
label_prefix = sys.argv[1] if len(sys.argv) > 1 else "pair"

with tempfile.TemporaryDirectory(prefix="saipen-t1578-oracle-") as directory:
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
                [sys.executable, "-B", "-m", "unittest", "-v", "test_t1578_restore_owner"],
                cwd=snapshot / "tools", env=environment, stdout=output,
                stderr=subprocess.STDOUT, timeout=900)
        text = out.read_text(encoding="utf-8")
        tail = text.strip().splitlines()[-1]
        errors = sum(1 for line in text.splitlines() if line.startswith("ERROR:"))
        manifest["runs"].append({"label": label, "subject": subject,
                                 "returncode": result.returncode, "verdict": tail,
                                 "errors": errors})
        print(label, result.returncode, subject, tail, "errors:", errors, flush=True)
    (EVIDENCE / f"{label_prefix}-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    assert manifest["runs"][0]["returncode"] != 0
    assert manifest["runs"][1]["returncode"] == 0
    print("verifier", verifier)
