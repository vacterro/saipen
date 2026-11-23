"""Read-only next-slice reconnaissance on an owned disposable ledger fixture."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "preflight.json"
if OUTPUT.exists():
    raise SystemExit("existing evidence is immutable")
sys.path.insert(0, str(ROOT / "tools"))
from test_regression_gate import RegressionGateFixture

fixture = RegressionGateFixture(methodName="runTest")
commands = [["status"], ["recover", "--dry-run"], ["next"]]
root_before = {name: hashlib.sha256((ROOT / (".saipen/" + name)).read_bytes()).hexdigest()
               for name in ("STATE.md", "BOARD.md", "LOG.md")}

def run(words):
    command = [str(ROOT / "bin/saipen.cmd"), "--project-root", str(fixture.project),
               "--agent", "tester", *words, "--json"]
    result = subprocess.run(command, cwd=ROOT, env={**os.environ, "SAIPEN_CAPABILITY": "no-publish"},
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        value = None
    return {"command": words, "exit_code": result.returncode, "value": value,
            "stdout": result.stdout if value is None else None, "stderr": result.stderr}

try:
    fixture.setUp()
    good_before = fixture.canonical_digest()
    good = [run(words) for words in commands]
    good_unchanged = fixture.canonical_digest() == good_before
    log = fixture.project / ".saipen/LOG.md"
    log.write_text(log.read_text(encoding="utf-8") +
                   "- 11.10.26 00:00 [E-004] [parent: E-3133] [T-7] [agent: tester] "
                   "RUN: unsupported continuation across a missing parent\n", encoding="utf-8")
    bad_before = fixture.canonical_digest()
    bad = [run(words) for words in commands]
    bad_unchanged = fixture.canonical_digest() == bad_before
    root_after = {name: hashlib.sha256((ROOT / (".saipen/" + name)).read_bytes()).hexdigest()
                  for name in root_before}
    if root_before != root_after:
        raise RuntimeError("live canonical metadata moved during fixture-only reconnaissance")
    record = {"stage": "prepared while T-1711 owns VERIFY; T-1702 A05 is not claimed or completed",
              "good": good, "bad_missing_parent": bad, "good_canonical_unchanged": good_unchanged,
              "bad_canonical_unchanged": bad_unchanged, "live_canonical_unchanged": root_before,
              "limits": "Missing-parent failure class in a disposable repository-owned fixture; not the actual AUDAPACK ledger, recovery or authorization. Native status/recover-preview/next results retained without converting refusal into success."}
    OUTPUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"good": [{"command": x["command"], "exit_code": x["exit_code"]} for x in good],
                      "bad": [{"command": x["command"], "exit_code": x["exit_code"],
                               "code": (x["value"] or {}).get("code"),
                               "action": (x["value"] or {}).get("action")} for x in bad],
                      "good_canonical_unchanged": good_unchanged, "bad_canonical_unchanged": bad_unchanged,
                      "record": str(OUTPUT)}))
finally:
    fixture.doCleanups()
