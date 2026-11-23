"""Independent REVIEW of the frozen AUDAPACK recovery, with bounded live controls."""
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
HOME = HERE.parents[2]
ROOT = Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK_RECOVERY_20261010")
ENGINEERING = ROOT / ".saipen/evidence/T-2-engineering-20261012"
sys.path.insert(0, str(HOME / "tools"))
from saipen_engine import operations, regression_execution
from saipen_engine.process_tree import run


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


output = HERE / "independent-review.json"
assert not output.exists(), "preserve immutable independent review"
docs, state, board, _ = operations._read(ROOT)
assert state["task"] == "T-2" and state["phase"] == "REVIEW", state
assert board["tickets"]["T-2"]["fields"]["owner"] == "audapack-recovery-engineer"
gate_paths = [ROOT / ".saipen/evidence/T-2-20261012" / name for name in
              ("recovery-full-pytest-current.json", "recovery-full-node-current.json")]
gates = [json.loads(path.read_text(encoding="utf-8")) for path in gate_paths]
assert all(gate["exit_code"] == 0 and gate["source_unchanged"] for gate in gates)
assert "2911 passed, 17 skipped" in gates[0]["stdout"]
assert "pass 936" in gates[1]["stdout"] and "fail 0" in gates[1]["stdout"]
inputs = gates[0]["source_inputs"]
assert all(sha(ROOT / relative) == digest for relative, digest in inputs.items())
frozen = ROOT / ".saipen/evidence/T-2-20261012/current-control.py"
assert frozen.read_bytes() == (ROOT / "tests/test_packing_disposable_trees.py").read_bytes()
assert sha(frozen) == "a929d13a6a2ad2ee4f8d2871fa985355383f74a34ce12eb5e47a593789d67b22"

contract_path = ENGINEERING / "regression-pinned-host.json"
contract = json.loads(contract_path.read_text(encoding="utf-8"))
pair_path = ROOT / ".saipen/evidence/regression/regression-execution-f5b8ce3fc3e34b9581078b6e7f6fad62.json"
pair = json.loads(pair_path.read_text(encoding="utf-8"))
assert pair["contract_sha256"] == sha(contract_path)
assert [(item["ran"], item["failed"], item["skipped"], item["exit_code"])
        for item in pair["runs"]] == [(48, 21, 0, 1), (48, 0, 0, 0)]
assert len(contract["subject_files"]) == 9 and len(contract["oracle_files"]) == 12
controls_path = ENGINEERING / "instrument-controls.json"
controls = json.loads(controls_path.read_text(encoding="utf-8"))
assert len(controls) == 6 and all(item["good_exit"] == 0 and item["bad_exit"] == 1 for item in controls)

environment = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
environment.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
                   GIT_OPTIONAL_LOCKS="0", QT_QPA_PLATFORM="offscreen", SAIPEN_CAPABILITY="no-publish")
done = run(contract["command"], cwd=ROOT, env=environment, capture_output=True,
           timeout=contract["timeout"])
stdout = done.stdout.decode("utf-8", errors="replace")
stderr = done.stderr.decode("utf-8", errors="replace")
(HERE / "current-oracle-stdout.txt").write_text(stdout, encoding="utf-8")
(HERE / "current-oracle-stderr.txt").write_text(stderr, encoding="utf-8")
summary = regression_execution.parse_summary(stdout, "pytest")
assert done.returncode == 0 and summary == {"ran": 48, "failed": 0, "skipped": 0}, summary
assert all(sha(ROOT / relative) == digest for relative, digest in inputs.items())
print(json.dumps({"independent_same_oracle": summary, "product_unchanged": True}), flush=True)

# The engineer's verifier writes its fixed output name. Override only its
# evidence directory in this process so the original carrier stays immutable.
service_carrier = ENGINEERING / "return-to-service-control-final.json"
service_digest = sha(service_carrier)
staging = module("audapack_service_review", ENGINEERING / "stage_return_to_service.py")
staging.HERE = HERE
staging.verify_fixture()
assert sha(service_carrier) == service_digest
service = json.loads((HERE / "return-to-service-control-final.json").read_text(encoding="utf-8"))
assert service["verdict"] == "PASS" and service["source_runtime_unchanged"] and service["source_project_unchanged"]

readback = module("audapack_authority_review", ENGINEERING / "readback.py")
readback.HERE = HERE
saved_argv = sys.argv
try:
    sys.argv = [str(ENGINEERING / "readback.py"), "review"]
    readback.main()
finally:
    sys.argv = saved_argv
authority = json.loads((HERE / "review-readback.json").read_text(encoding="utf-8"))
assert authority["state"]["phase"] == "REVIEW" and authority["product_matches_current_full_gate"]
assert authority["original_protected_files"] == 8260 and authority["original_changed"] == []

value = {"work": "T-2", "phase": "REVIEW", "owner": "audapack-recovery-engineer",
         "current_input_count": len(inputs), "full_gate_sha256": {path.name: sha(path) for path in gate_paths},
         "full_python": "2911 passed/17 inherited platform or environment skips",
         "full_node": "936 passed/0 skipped/0 cancelled",
         "native_pair_sha256": sha(pair_path), "native_pair": "48/21 before; 48/0 after; zero skips; same oracle",
         "frozen_15_oracle_sha256": sha(frozen), "independent_same_oracle": summary,
         "independent_service_canary": service, "protected_original_files": authority["original_protected_files"],
         "original_unchanged": True, "negative_controls_unchanged": True,
         "instrument_controls_sha256": sha(controls_path),
         "instrument_controls": [{key: item[key] for key in ("label", "good_exit", "bad_exit")} for item in controls],
         "source_inspection": ["service-bound settings directory; first-save registry preservation",
                               "launcher refill keeps signals blocked through final selection",
                               "absent plane clears shared provenance; installed outage preserves last known good",
                               "exact launch argv and worker held-probe/closed-pool controls",
                               "new child detection uses PID and creation time; GUI API errors stay unavailable",
                               "data-I/O gate uses AST call/import inspection; this is not runtime I/O instrumentation"],
         "verdict": "PASS", "implementation_change_by_reviewer": False,
         "limits": "Windows controlled/offscreen application and native CLI proof; no original runtime cutover, real AG3, live IDE guard, user desktop/model acceptance or publication."}
assert all(sha(ROOT / relative) == digest for relative, digest in inputs.items())
output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"verdict": value["verdict"], "phase": value["phase"],
                  "current_inputs": len(inputs), "original_unchanged": True,
                  "independent_oracle": summary, "isolated_service_canary": service["verdict"]}))
