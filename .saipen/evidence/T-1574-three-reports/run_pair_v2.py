"""Same-oracle red/green pair for T-1574 (VERIFY-ORACLE-01).

Identical oracle files and command run against the preserved pre-fix owners
(red) and the current owners (green) inside one disposable snapshot. Digests
come from the canonical `saipen_engine.oracle` functions, so the recorded
`verifier:`/`subject:` tokens are the ones `regression_pair_verdict` reads.
v2 adds the real AUDAPACK-shape recovery carrier (RealDownstreamShapeTests).
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
COMMAND = "python -B -m unittest -v " + " ".join(TESTS)
ORACLE = [
    "tools/test_t1572_ticket_scoped_recovery.py",
    "tools/test_t1574_followups.py",
    "tools/test_fixture_support.py",
    "tools/test_hermetic_env.py",
    "tools/test_improve_reconcile.py",
    "tools/saipen_engine/reproduction.py",
]

with tempfile.TemporaryDirectory(prefix="saipen-t1574-oracle-") as directory:
    snapshot = Path(directory).resolve()
    for name in ("tools", "saipen", "extensions", "bootstrap", "bin", "tests"):
        shutil.copytree(ROOT / name, snapshot / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for file in ROOT.iterdir():
        if file.is_file():
            shutil.copy2(file, snapshot / file.name)
    environment = {k: v for k, v in os.environ.items()
                   if not k.startswith(("SAIPEN_", "NITRO_CRASH_"))}
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
        out = EVIDENCE / f"pair-v2-{label}.txt"
        with out.open("w", encoding="utf-8") as output:
            result = subprocess.run([sys.executable, "-B", "-m", "unittest", "-v", *TESTS],
                                    cwd=snapshot / "tools", env=environment, stdout=output,
                                    stderr=subprocess.STDOUT, timeout=900)
        tail = out.read_text(encoding="utf-8").strip().splitlines()[-1]
        manifest["runs"].append({"label": label, "subject": subject,
                                 "returncode": result.returncode, "verdict": tail})
        print(label, result.returncode, subject, tail, flush=True)
    (EVIDENCE / "pair-v2-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                                  encoding="utf-8")
    assert manifest["runs"][0]["returncode"] != 0
    assert manifest["runs"][1]["returncode"] == 0
    print("verifier", verifier)
