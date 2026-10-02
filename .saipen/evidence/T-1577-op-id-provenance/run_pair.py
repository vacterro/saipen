"""Same-oracle red/green pair for T-1577 (VERIFY-ORACLE-01).

The oracle (the T-1577 carrier) is held fixed; only the subjects change: the
preserved pre-fix `journal.py`, `log.py` and `validate.py` against the live
ones. RED is behavioural -- 7 assertions fail because a hand-authored
`transition to VERIFY` opens a cycle, a hand-authored `PASS conf: high`
closes one, a hand-authored anchor settles a regression pair, and the
validator has no gate that names the id. No import or collection error.
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
    "tools/saipen_engine/journal.py": "journal.py",
    "tools/saipen_engine/log.py": "log.py",
    "tools/validate.py": "validate.py",
}
COMMAND = "python -B -m unittest -v test_t1577_op_id_provenance"
ORACLE = ["tools/test_t1577_op_id_provenance.py"]
label_prefix = sys.argv[1] if len(sys.argv) > 1 else "pair"

with tempfile.TemporaryDirectory(prefix="saipen-t1577-oracle-") as directory:
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
    # `reviewed` (make_reviewed.py) is the tree the independent review
    # returned to BUILD (E-11028): width-only grammar, no class registry.
    labels = ("red", "reviewed", "green") if (EVIDENCE / "reviewed").is_dir() else ("red", "green")
    for label in labels:
        for relative, original in SUBJECTS.items():
            if label == "red":
                source = EVIDENCE / "pre-fix" / original
            elif label == "reviewed" and (EVIDENCE / "reviewed" / original).is_file():
                source = EVIDENCE / "reviewed" / original
            else:
                source = ROOT / relative
            shutil.copy2(source, snapshot / relative)
        assert verifier_identity(COMMAND, ORACLE, snapshot) == verifier, "oracle drifted"
        subject = oracle_digest(snapshot, list(SUBJECTS))
        out = EVIDENCE / f"{label_prefix}-{label}.txt"
        with out.open("w", encoding="utf-8") as output:
            result = subprocess.run(
                [sys.executable, "-B", "-m", "unittest", "-v",
                 "test_t1577_op_id_provenance"],
                cwd=snapshot / "tools", env=environment, stdout=output,
                stderr=subprocess.STDOUT, timeout=900)
        text = out.read_text(encoding="utf-8")
        tail = text.strip().splitlines()[-1]
        errors = sum(1 for line in text.splitlines() if line.startswith("ERROR:"))
        failures = sum(1 for line in text.splitlines() if line.startswith("FAIL:"))
        manifest["runs"].append({"label": label, "subject": subject,
                                 "returncode": result.returncode, "verdict": tail,
                                 "errors": errors, "failures": failures})
        print(label, result.returncode, subject, tail,
              "errors:", errors, "failures:", failures, flush=True)
    (EVIDENCE / f"{label_prefix}-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    assert all(run["returncode"] != 0 for run in manifest["runs"][:-1])
    assert manifest["runs"][-1]["returncode"] == 0
    print("verifier", verifier)