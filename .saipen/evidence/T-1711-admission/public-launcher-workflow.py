"""Documented Windows launcher end-to-end, only in disposable protocol fixtures."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "public-launcher-workflow.json"
if OUTPUT.exists():
    raise SystemExit("existing evidence is immutable")
sys.path.insert(0, str(ROOT / "tools"))
from test_t1711_regression_execution import ExecutionControls

root_before = {name: hashlib.sha256((ROOT / (".saipen/" + name)).read_bytes()).hexdigest()
               for name in ("STATE.md", "BOARD.md", "LOG.md")}
cases = []

def native(fixture, words):
    command = [str(ROOT / "bin/saipen.cmd"), "--project-root", str(fixture.project),
               "--agent", "tester", *words, "--json"]
    environment = {**os.environ, "SAIPEN_CAPABILITY": "no-publish"}
    result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=120)
    value = json.loads(result.stdout)
    return {"command": command, "exit_code": result.returncode,
            "result": value, "stderr": result.stderr}

for format_name in ("unittest", "tap"):
    fixture = ExecutionControls(methodName="test_actual_active_pair_is_admitted_and_typed")
    try:
        fixture.setUp()
        if format_name == "tap":
            node = shutil.which("node")
            if not node:
                raise RuntimeError("the consumer-compatible native Node verifier is unavailable")
            (fixture.project / "subject.cjs").write_text("exports.answer = () => 2;\n", encoding="utf-8")
            (fixture.project / ".saipen/evidence/before.cjs").write_text("exports.answer = () => 1;\n", encoding="utf-8")
            (fixture.project / "check.cjs").write_text(
                "const test = require('node:test'); const assert = require('node:assert/strict');\n"
                "const {answer} = require('./subject.cjs');\n"
                "test('clipboard result contract', () => assert.equal(answer(), 2));\n", encoding="utf-8")
            fixture.contract.update(command=[node, "--test", "--test-reporter=tap", "check.cjs"],
                                    format="tap", context=["subject.cjs", "check.cjs"],
                                    oracle_files=["check.cjs"], subject_files=["subject.cjs"],
                                    before={"subject.cjs": ".saipen/evidence/before.cjs"})
            fixture.write_contract()
        words = ["work", "regression", "T-7", "--file", str(fixture.contract_path)]
        admitted = native(fixture, words)
        if admitted["exit_code"] or not admitted["result"].get("ok"):
            raise RuntimeError("public active evidence admission failed: " + str(admitted))
        before_replay = fixture.canonical_digest()
        replay = native(fixture, words)
        if (replay["exit_code"] or replay["result"].get("code") != "ALREADY_APPLIED"
                or fixture.canonical_digest() != before_replay):
            raise RuntimeError("public exact replay added authority: " + str(replay))
        carrier = fixture.project / next(iter(fixture.contract["before"].values()))
        prior = carrier.read_bytes()
        carrier.write_bytes(prior + (b"\n// changed prior\n" if format_name == "tap" else b"\n# changed prior\n"))
        before_refusal = fixture.canonical_digest()
        refused = native(fixture, ["transition", "REVIEW"])
        if (refused["exit_code"] == 0 or refused["result"].get("ok")
                or fixture.canonical_digest() != before_refusal):
            raise RuntimeError("public prior-material negative control did not refuse safely: " + str(refused))
        carrier.write_bytes(prior)
        approved = native(fixture, ["transition", "REVIEW"])
        if approved["exit_code"] or not approved["result"].get("ok"):
            raise RuntimeError("public current evidence did not reach REVIEW: " + str(approved))
        cases.append({"format": format_name, "admission": admitted, "exact_replay": replay,
                      "changed_prior_refusal": refused, "restored_prior_review": approved})
    finally:
        fixture.doCleanups()
root_after = {name: hashlib.sha256((ROOT / (".saipen/" + name)).read_bytes()).hexdigest()
              for name in root_before}
if root_before != root_after:
    raise RuntimeError("live canonical metadata changed during the disposable public workflow")
OUTPUT.write_text(json.dumps({"ok": True, "cases": cases, "live_canonical_unchanged": root_before,
                              "scope": "actual documented bin/saipen.cmd; disposable Python/Node fixtures; no live consumer or product mutation"}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"ok": True, "formats": [case["format"] for case in cases],
                  "actual_native_operations": len(cases) * 4, "record": str(OUTPUT),
                  "live_canonical_unchanged": True}))
