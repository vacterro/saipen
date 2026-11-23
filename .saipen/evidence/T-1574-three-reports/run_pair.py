"""Run identical regression oracles against preserved and repaired owners."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
SUBJECTS = {
    "tools/saipen_engine/reconcile.py": "reconcile.py",
    "tools/saipen_engine/hush.py": "hush.py",
    "tools/improve.py": "improve.py",
    "tools/nitro_integrity_repro.py": "nitro_integrity_repro.py",
}
TESTS = [
    "test_t1572_ticket_scoped_recovery",
    "test_t1574_followups.ImproveFollowupTests",
    "test_t1574_followups.ReproductionTests.test_real_producer_rejects_exit_status_as_defect_predicate",
    "test_t1574_followups.ReproductionTests.test_real_path_probe_distinguishes_guard_and_broken_harness",
    "test_t1574_followups.SilentExecutionTests.test_existing_policy_consumer_defaults_to_silent",
]


def digest(paths):
    h = hashlib.sha256()
    for path in sorted(paths):
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


with tempfile.TemporaryDirectory(prefix="saipen-t1574-oracle-") as directory:
    snapshot = Path(directory).resolve()
    assert snapshot.is_relative_to(Path(tempfile.gettempdir()).resolve())
    for name in ("tools", "saipen", "extensions", "bootstrap", "bin", "tests"):
        shutil.copytree(ROOT / name, snapshot / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for file in ROOT.iterdir():
        if file.is_file():
            shutil.copy2(file, snapshot / file.name)
    environment = os.environ.copy()
    for key in list(environment):
        if key.startswith("SAIPEN_") or key.startswith("NITRO_CRASH_"):
            environment.pop(key)
    environment["PYTHONPATH"] = str(snapshot / "tools")
    environment["PYTHONUTF8"] = "1"
    oracle_paths = [snapshot / "tools" / name for name in (
        "test_t1572_ticket_scoped_recovery.py", "test_t1574_followups.py",
        "test_fixture_support.py", "test_hermetic_env.py", "test_improve_reconcile.py")]
    oracle = digest(oracle_paths)
    manifest = {"verifier": oracle, "command": TESTS, "runs": []}
    for label in ("red", "green"):
        for relative, original in SUBJECTS.items():
            source = EVIDENCE / "pre-fix" / original if label == "red" else ROOT / relative
            shutil.copy2(source, snapshot / relative)
        assert digest(oracle_paths) == oracle
        subject = digest([snapshot / relative for relative in SUBJECTS])
        with (EVIDENCE / ("pair-" + label + ".txt")).open("w", encoding="utf-8") as output:
            result = subprocess.run([sys.executable, "-B", "-m", "unittest", "-v", *TESTS],
                                    cwd=snapshot, env=environment, stdout=output,
                                    stderr=subprocess.STDOUT, timeout=300)
        manifest["runs"].append({"label": label, "subject": subject,
                                  "returncode": result.returncode})
        print(label, result.returncode, subject, flush=True)
    (EVIDENCE / "pair-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                               encoding="utf-8")
    assert manifest["runs"][0]["returncode"] != 0
    assert manifest["runs"][1]["returncode"] == 0
