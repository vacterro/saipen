"""Current-engine adjudication of an old handoff; no LIMISAW writes."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

OUT = Path(__file__).resolve().parent
HOME = OUT.parents[2]
prefix = sys.argv[1] + "-" if len(sys.argv) > 1 else ""


def output(name):
    return OUT / (prefix + name)


sys.path.insert(0, str(HOME / "tools"))
from test_src085_improve_run_body import RunBodyContractTests
import improve

paths = ["tools/saipen.py", "tools/improve.py", "tools/saipen_engine/conformance.py",
         "tools/test_t1412_conformance_truth.py", "tools/test_src085_improve_run_body.py"]
before = {p: hashlib.sha256((HOME / p).read_bytes()).hexdigest() for p in paths}
env = dict(os.environ, PYTHONIOENCODING="utf-8", GIT_OPTIONAL_LOCKS="0")
result = subprocess.run([sys.executable, "-m", "unittest",
                         "tools.test_t1412_conformance_truth.StatusSurfaceTests",
                         "tools.test_t1412_conformance_truth.ValidateSurfaceTests", "-v"],
                        cwd=HOME, env=env, capture_output=True, timeout=180)
output("conformance-tests.txt").write_bytes(result.stdout + result.stderr)
assert result.returncode == 0, (result.stdout + result.stderr).decode("utf-8", "replace")

fixture = RunBodyContractTests()
fixture.setUp()
try:
    improve.append_run(fixture.report, "NO_FINDINGS -- synthetic recovery control\n")
    original = fixture.report.read_text(encoding="utf-8")
    stale = re.sub(r"(?m)^protocol_fingerprint:.*$",
                   "protocol_fingerprint: sha256:" + "0" * 64, original, count=1)
    assert stale != original
    fixture.report.write_text(stale, encoding="utf-8")
    try:
        improve.append_run(fixture.report, "NO_FINDINGS -- should refuse stale identity\n")
    except improve.ImproveError as exc:
        refusal = str(exc)
    else:
        raise AssertionError("stale draft was unexpectedly appendable")
    assert fixture.report.read_text(encoding="utf-8") == stale
    rebound = subprocess.run([str(HOME / "bin/saipen.cmd"), "--project-root", str(fixture.root),
                              "improve", "rebind", fixture.cycle.name, "seat-a", "PROBE", "--json"],
                             cwd=HOME, env=env, capture_output=True, timeout=60)
    payload = json.loads(rebound.stdout)
    output("rebind-cli.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    assert rebound.returncode == 0 and payload.get("code") == "REBIND_COMMITTED", payload
    corrected = fixture.report.read_text(encoding="utf-8")
    assert corrected == original, "rebind changed more than the stale identity scalar"
    improve.append_run(fixture.report, "NO_FINDINGS -- append succeeds after recovery\n")
    improve.complete_report(fixture.report)
    assert "report_status: complete" in fixture.report.read_text(encoding="utf-8")
    completed = fixture.report.read_bytes()
    rejected = subprocess.run([str(HOME / "bin/saipen.cmd"), "--project-root", str(fixture.root),
                               "improve", "rebind", fixture.cycle.name, "seat-a", "PROBE", "--json"],
                              cwd=HOME, env=env, capture_output=True, timeout=60)
    rejection = json.loads(rejected.stdout)
    assert rejected.returncode != 0 and not rejection.get("ok"), rejection
    assert "only a DRAFT report" in rejection.get("detail", ""), rejection
    assert fixture.report.read_bytes() == completed, "completed report was mutated"
    output("completed-rebind-refusal.json").write_text(json.dumps(rejection, indent=2), encoding="utf-8")
    record = {"stale_append_refused": refusal, "rebind": payload,
              "original_run_bytes_preserved": True, "append_and_completion_after_rebind": "PASS",
              "completed_rebind_refused_without_writes": True,
              "scope": "sacrificial fixture only; no foreign project repair claim"}
    output("rebind-control.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
finally:
    fixture.doCleanups()

after = {p: hashlib.sha256((HOME / p).read_bytes()).hexdigest() for p in paths}
assert before == after, "observed producer code moved during this bounded verification"
output("subject.json").write_text(json.dumps({"before": before, "after": after,
                                              "foreign_target_mutations": []}, indent=2), encoding="utf-8")
print(json.dumps({"conformance_tests": "PASS", "rebind_recovery": "PASS",
                  "reader_sources_stable": True, "foreign_target_mutations": []}))
