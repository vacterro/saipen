"""Evidence-only SAME-FINAL-ORACLE replay; never admits native ledger evidence."""
from __future__ import annotations

import ast
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import traceback
from unittest.mock import patch

EVIDENCE = Path(__file__).resolve().parent
SNAPSHOT = EVIDENCE / "snapshot"
INVENTORY = json.loads((EVIDENCE / "complete-snapshot-inventory.json").read_text(encoding="utf-8"))
SOURCE = Path(INVENTORY["source_root"])
SUBJECT = INVENTORY["subject_path"]
TESTS = [
    "tools/test_response_delivery.py::RepeatedStateDigest::test_stop_delivery_matches_the_current_route_without_inventing_human_work",
    "tools/test_codex_stop_hook.py::CanonicalClassifierTests::test_a_valid_boundary_passes",
    "tools/test_codex_stop_hook.py::CodexStopHookTests::test_a_valid_boundary_passes_untouched",
]
COMMAND = ["{python}", "-B", "-m", "pytest", "-v", "--tb=short", "--color=no", "-p", "no:cacheprovider", *TESTS]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    for relative, row in INVENTORY["files"].items():
        assert sha((SNAPSHOT / relative).read_bytes()) == row["sha256"], relative
    context = sorted({Path(relative).parts[0] for relative in INVENTORY["files"]})
    contract = {
        "schema": 1,
        "command": COMMAND,
        "format": "pytest",
        "context": context,
        "oracle_files": list(INVENTORY["oracle_sha256"]),
        "subject_files": [SUBJECT],
        "before": {SUBJECT: (EVIDENCE / "preimages" / SUBJECT).relative_to(SOURCE).as_posix()},
        "timeout": 240,
    }
    source_manifest = EVIDENCE / "source-manifest.json"
    write_json(source_manifest, contract)
    frozen_evidence = SNAPSHOT / ".saipen/evidence"
    frozen_evidence.mkdir(parents=True, exist_ok=True)
    frozen_before = frozen_evidence / "operations-before.py"
    frozen_before.write_bytes((EVIDENCE / "preimages" / SUBJECT).read_bytes())
    frozen_contract = {**contract, "before": {SUBJECT: ".saipen/evidence/operations-before.py"}}
    frozen_manifest = frozen_evidence / "frozen-manifest.json"
    write_json(frozen_manifest, frozen_contract)

    sys.path.insert(0, str(SNAPSHOT / "tools"))
    from saipen_engine import regression_execution as runner

    assert Path(runner.__file__).resolve().is_relative_to(SNAPSHOT)
    material = runner._load(SNAPSHOT, frozen_manifest)
    assert set(material["context"]) == set(INVENTORY["files"])
    before_files = {**material["context"], **material["prior"]}
    after_files = {**material["context"], **material["current"]}
    changed = [p for p in before_files if before_files[p] != after_files[p]]
    assert changed == [SUBJECT], changed
    selected_hashes = {}
    for test_id in TESTS:
        relative, class_name, method_name = test_id.split("::")
        text = material["context"][relative].decode("utf-8-sig")
        tree = ast.parse(text)
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method_name)
        selected_hashes[test_id] = sha(ast.get_source_segment(text, method).encode("utf-8"))

    attempt = EVIDENCE / ("run-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    attempt.mkdir()
    record = {
        "task": "T-2040",
        "evidence_class": "measured-unadmitted",
        "same_final_oracle": True,
        "source_snapshot": str(SNAPSHOT),
        "snapshot_inventory": str(EVIDENCE / "complete-snapshot-inventory.json"),
        "source_manifest": str(source_manifest),
        "frozen_manifest": str(frozen_manifest),
        "command": COMMAND,
        "runtime": material["runtime"],
        "verifier": material["verifier"],
        "runner_owner": str(Path(runner.__file__).resolve()),
        "runner_sha256": sha(Path(runner.__file__).read_bytes()),
        "context_roots": context,
        "context_file_count": len(after_files),
        "context_only_difference": changed,
        "context_before_sha256": sha(runner._json(runner._manifest(before_files))),
        "context_after_sha256": sha(runner._json(runner._manifest(after_files))),
        "context_except_subject_sha256": sha(runner._json(runner._manifest({p: raw for p, raw in after_files.items() if p != SUBJECT}))),
        "oracle_file_sha256": INVENTORY["oracle_sha256"],
        "oracle_method_sha256": selected_hashes,
        "subject_before_sha256": sha(material["prior"][SUBJECT]),
        "subject_after_sha256": sha(material["current"][SUBJECT]),
        "environment_sha256": sha(runner._json(material["environment"])),
        "environment_rules": "Native execution_environment: strips SAIPEN/session diagnostic variables, no-publish, bytecode disabled. No PYTHONPATH override. Fixtures use unchanged isolate_host_session.",
        "isolation": "Each lane is a retained native _measure temporary directory outside shared checkout; all 1417 inputs materialized; only subject differs; native post-run byte verification enabled.",
        "old_pair_exclusion": "Earlier before/after logs used a stale manual-WAIT oracle, later corrected to set HUMAN_DECISION -- verification required. Old FAIL plus final-oracle-after PASS is not a same-oracle pair. Neither old run contributes to this pair.",
        "native_admission": "Not executed: active BUILD and evidence-only scope. Native VERIFY must run source-manifest.json through saipen work regression T-2040 --file before ledger admission. Later source edits require fresh native measurement, not reuse of this snapshot result.",
        "runs": [],
    }
    lanes = []
    actual_commands = []
    original_run = runner.run

    @contextmanager
    def retain_directory(*args, **kwargs):
        lane = Path(tempfile.mkdtemp(*args, **kwargs)).resolve()
        lanes.append(lane)
        yield str(lane)
        # ponytail: retain evidence lanes; no cleanup until an operator archives them.

    def observe_run(argv, **kwargs):
        command = {"argv": list(argv), "cwd": str(kwargs["cwd"]), "timeout_seconds": kwargs["timeout"]}
        actual_commands.append(command)
        result = original_run(argv, **kwargs)
        command["exit_code"] = result.returncode
        return result

    try:
        with patch.object(runner.tempfile, "TemporaryDirectory", retain_directory), patch.object(runner, "run", observe_run):
            for stage, subject in (("before", material["prior"]), ("after", material["current"])):
                observation = runner._measure(material, stage, subject)
                observation.update(actual_commands[-1])
                observation["lane_path"] = str(lanes[-1])
                observation["context_bytes_unchanged"] = True
                observation["oracle_sha256"] = {p: sha((lanes[-1] / p).read_bytes()) for p in contract["oracle_files"]}
                observation["subject_sha256"] = sha((lanes[-1] / SUBJECT).read_bytes())
                record["runs"].append(observation)
                for stream in ("stdout", "stderr"):
                    shutil.copyfile(lanes[-1] / ("." + stream), attempt / (stage + "." + stream + ".log"))
                write_json(attempt / (stage + ".json"), observation)
                write_json(attempt / "pair-result.json", record)
                print(json.dumps({k: v for k, v in observation.items() if k not in {"stdout", "stderr"}}, indent=2), flush=True)
        before, after = record["runs"]
        record["pair_result"] = "PASS" if before["exit_code"] == 1 and before["failed"] > 0 and after["exit_code"] == 0 and after["failed"] == 0 else "FAIL"
        record["oracle_unchanged_between_lanes"] = before["oracle_sha256"] == after["oracle_sha256"] == INVENTORY["oracle_sha256"]
        assert record["oracle_unchanged_between_lanes"]
        assert all("collected 3 items" in run["stdout"] for run in record["runs"])
        assert "3 passed, 3 subtests passed" in after["stdout"]
        record["selected_tests"] = 3
        record["summary_count_note"] = "pytest counts three failed subtests in before total (ran=6); both lanes collected the same three test methods. Green reports three methods plus three passing subtests."
        record["genuine_failure_checks"] = {
            "status_projection": "STATUS: DONE" in before["stdout"] and "STATUS: BLOCKED" in before["stdout"],
            "blocked_wait_operator_due": 'report["facts"]["operator_due"]' in before["stdout"] and "True != False" in before["stdout"],
            "codex_classifier_and_hook": all("FAILED " + test_id in before["stdout"] for test_id in TESTS[1:]),
            "not_isolation_errors": not any(token in before["stdout"] + before["stderr"] for token in ("ModuleNotFoundError", "ImportError", "FileNotFoundError", "SAIPEN_HOST_RUNTIME_UNAVAILABLE")),
        }
        assert all(record["genuine_failure_checks"].values())
    except BaseException:
        record["pair_result"] = "ERROR"
        record["error"] = traceback.format_exc()
        raise
    finally:
        record["lane_paths"] = [str(p) for p in lanes]
        record["actual_commands"] = actual_commands
        write_json(attempt / "pair-result.json", record)
        print("PAIR_RESULT_FILE", str(attempt / "pair-result.json"), flush=True)
    assert record["pair_result"] == "PASS", record["pair_result"]


if __name__ == "__main__":
    main()
