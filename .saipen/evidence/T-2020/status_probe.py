"""Disposable stub-mismatch replay and public suite-status field checks."""
import json
import sys
import tempfile
import time
from pathlib import Path

home = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(home / "tools"))
from saipen_engine import suite_record as suite

with tempfile.TemporaryDirectory(prefix="saipen-t2020-probe-") as directory:
    root = Path(directory)
    (root / "fixture.py").write_text(
        "import time\n"
        "print('SAIPEN-SCRIPT {\"script\":\"Test-Stub.ps1\",\"duration_s\":0.25}', flush=True)\n"
        "print('FAIL: NativeMissionRouterTests: DllBase.cpp stub lacks vrv::satmap', flush=True)\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    suite.declare(root, [sys.executable, "-B", "fixture.py"])
    began = time.monotonic()
    written = suite.write_record(root, suite.run(root, fail_fast=True))
    elapsed = time.monotonic() - began
    status, code = suite.cli(root, ["status"], agent="audit-probe")
    newest = status["newest"]
    assert code == 0 and newest["verdict"] == "FAIL", status
    assert elapsed < 120, elapsed
    assert newest["duration_s"] == written["record"]["duration_s"]
    assert "NativeMissionRouterTests" in newest["first_failure_line"]
    assert newest["scripts"] == [{"script": "Test-Stub.ps1", "duration_s": 0.25}]
    assert set(newest["overhead_s"]) == {"pre_hash", "post_hash", "parsing", "total"}
    assert suite.reusable_record(root)[0] is None
    proof = {
        "verdict": "PASS", "fixture_only": True, "bzdecomp_executed": False,
        "elapsed_s": elapsed, "status_code": status["code"], "newest": newest,
        "partial_fail": written["record"]["stopped_on_failure"],
    }
    path = Path(__file__).with_name("status_probe.json")
    path.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof))
