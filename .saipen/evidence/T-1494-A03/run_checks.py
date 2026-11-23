"""A03 execution receipts; delegates isolation and process ownership to project tools."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import core_unit, inflight
from saipen_engine.test_runner import TestFamily, _ignore_copy, _run_family


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def save(name, value):
    (OUT / (name + ".json")).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def subject(root, paths):
    hashes = {path: sha(root / path) for path in paths}
    return hashes, hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()


def run(name, root, args, *, cwd="tools", timeout=1800):
    started = datetime.now(timezone.utc).isoformat()
    clock = time.monotonic()
    before = core_unit.tree_fingerprint(root)
    spool = OUT / (name + "-spool")
    spool.mkdir(exist_ok=False)
    command = (sys.executable, "-B", *args)
    report = _run_family(root / cwd, TestFamily(name, command, timeout), spool=spool)
    stdout = (spool / "stdout").read_text(encoding="utf-8", errors="replace")
    stderr = (spool / "stderr").read_text(encoding="utf-8", errors="replace")
    parsed = core_unit.parse_output(stderr)
    skip = re.search(r"(?:OK|FAILED)\s*\([^\n]*skipped=(\d+)", stderr)
    result = {"name": name, "command": list(command), "cwd": str(root / cwd),
              "started_utc": started, "source_fingerprint_before": before,
              "source_fingerprint_after": core_unit.tree_fingerprint(root),
              "exit_code": report.get("exit_code"), "status": report.get("status"),
              "duration_s": time.monotonic() - clock, "tests": parsed,
              "skipped": int(skip.group(1)) if skip else 0,
              "stdout_sha256": sha(spool / "stdout"), "stderr_sha256": sha(spool / "stderr"),
              "processes_leaked": report.get("processes_leaked", []),
              "oracle_hashes": {str(p.relative_to(root)): sha(p)
                                for p in (root / "tools").glob("test*.py")}}
    if args[:2] == ("-m", "unittest"):
        result["accepted"] = (result["exit_code"] == 0 and bool(parsed["ran"])
                              and not parsed["red"] and parsed["tallied"] == 0)
    else:
        result["accepted"] = result["exit_code"] == 0
    result["passed"] = (parsed["ran"] - parsed["tallied"] - result["skipped"]
                        if parsed["ran"] is not None and parsed["tallied"] is not None else None)
    save(name, result)
    print(json.dumps({k: result[k] for k in ("name", "exit_code", "accepted", "tests", "skipped", "duration_s")}), flush=True)
    return result, stdout, stderr


def units(name, root, *targets):
    return run(name, root, ("-m", "unittest", *targets, "-v"))[0]


def focused():
    commands = [("a01-inventory", ("tools/fail_site_inventory.py",), "."),
                ("a01-unit", ("-m", "unittest", "test_check_inventory", "-v"), "tools"),
                ("a02-routing", ("-m", "unittest", "test_command_routing", "-v"), "tools"),
                ("a02-hostile", ("-m", "unittest", "test_hostile_wave_regressions", "-v"), "tools"),
                ("authority", ("-m", "unittest", "test_t1494_continuation_authority", "-v"), "tools")]
    for name, command, cwd in commands:
        result, _, _ = run(name, ROOT, command, cwd=cwd)
        if not result["accepted"]:
            return 1
    return 0


def neighbors():
    for target in ("test_t1293_valve_resume_audit_route", "test_intent_audit_fixes",
                   "test_t1474_start_goal_entry", "test_t1619_goal_terminality",
                   "test_t1619_iteration_boundary"):
        if not units("neighbor-" + target, ROOT, target)["accepted"]:
            return 1
    return 0


def oracle(stage):
    historical = ROOT / ".saipen/evidence/T-1494-continuation-authority"
    pair = json.loads((historical / "pair.json").read_text())
    paths = [path for path in pair["subject_paths"] if not path.startswith("tools/test_")]
    pre = json.loads((historical / "pre-hashes.json").read_text())
    post = json.loads((historical / "post-hashes.json").read_text())
    for path in pair["subject_paths"]:
        assert sha(historical / "pre" / path) == pre[path], path
        assert sha(ROOT / path) == post[path], path
    assert sha(ROOT / "tools/test_t1494_continuation_authority.py") == pair["verifier_sha256"]
    owner = core_unit.new_sandbox_root()
    disposable = owner / "project"
    control = {"temporary_root": str(owner), "copy_api": "core_unit.copy_tree_consistent",
               "pre_authentication": "E-13952 subject + exact pre-hashes.json bytes",
               "subject_paths": paths, "fixtures_policy": "all current test files identical in both halves"}
    try:
        assert not owner.is_relative_to(ROOT)
        core_unit.copy_tree_consistent(ROOT, disposable, _ignore_copy)
        fixture_paths = [p.relative_to(disposable).as_posix()
                         for p in (disposable / "tools").glob("test*.py")]
        fixture_paths += [p.relative_to(disposable).as_posix()
                          for p in (disposable / "tests").rglob("*") if p.is_file()]
        fixtures, fixtures_digest = subject(disposable, fixture_paths)
        backups = {path: (disposable / path).read_bytes() if (disposable / path).is_file() else None
                   for path in paths}
        for path in paths:
            target = disposable / path
            if pre[path] is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes((historical / "pre" / path).read_bytes())
        pre_map, pre_digest = subject(disposable, paths)
        assert pre_map == {path: pre[path] for path in paths}
        red = units(stage + "-oracle-red", disposable, "test_t1494_continuation_authority")
        controls = ("test_command_routing.CommandSemanticsTests.test_bare_continue_cc_identical_on_tripped_goal_valve",
                    "test_command_routing.CommandSemanticsTests.test_tripped_goal_valve_cc_reauthorizes_keeps_objective",
                    "test_hostile_wave_regressions.Wave2ObeyTests.test_safety_valve_cc_reauthorizes")
        red_a02 = units(stage + "-a02-red", disposable, *controls)
        original_controls = (
            "test_automation_block.WaitOwnership.test_bounded_safety_valve_requires_operator_cc",
            "test_automation_block.ClosureGate.test_bounded_wait_preserves_route_outside_rtc",
        )
        original_red = (units(stage + "-original-checks-red", disposable, *original_controls)
                        if stage == "review-oracle" else None)
        assert subject(disposable, fixture_paths)[1] == fixtures_digest
        for path, data in backups.items():
            if data is None:
                (disposable / path).unlink(missing_ok=True)
            else:
                (disposable / path).write_bytes(data)
        post_map, post_digest = subject(disposable, paths)
        assert post_map == {path: post[path] for path in paths}
        green = units(stage + "-oracle-green", disposable, "test_t1494_continuation_authority")
        green_a02 = units(stage + "-a02-green", disposable, *controls)
        original_green = (units(stage + "-original-checks-green", disposable, *original_controls)
                          if stage == "review-oracle" else None)
        assert subject(disposable, fixture_paths)[1] == fixtures_digest
        control.update({"pre_hashes": pre_map, "pre_subject_sha256": pre_digest,
                        "post_hashes": post_map, "post_subject_sha256": post_digest,
                        "fixture_sha256": fixtures_digest, "fixture_hashes": fixtures,
                        "verifier_sha256": pair["verifier_sha256"],
                        "historical_pre_digest": pair["pre_subject_sha256"],
                        "historical_post_digest": pair["post_subject_sha256"],
                        "red": red["tests"], "green": green["tests"],
                        "a02_red": red_a02["tests"], "a02_green": green_a02["tests"]})
        control["accepted"] = (red["exit_code"] == 1 and red["tests"]["ran"] == 18
                               and bool(red["tests"]["red"]) and green["accepted"]
                               and red_a02["exit_code"] == 1 and red_a02["tests"]["ran"] == 3
                               and len(red_a02["tests"]["red"]) == 3 and green_a02["accepted"])
        if original_red is not None:
            control["original_modified_checks_red"] = original_red["tests"]
            control["original_modified_checks_green"] = original_green["tests"]
            control["accepted"] = (control["accepted"] and original_red["tests"]["ran"] == 2
                                   and len(original_red["tests"]["red"]) == 2
                                   and original_green["accepted"])
    finally:
        control["cleanup_complete"] = core_unit.reclaim(owner)
        save(stage + "-pair", control)
    return 0 if control.get("accepted") and control["cleanup_complete"] else 1


def core():
    assert inflight.current(ROOT) is None, "foreign in-flight family"
    result, stdout, _ = run("core-unit", ROOT,
        ("tools/core_unit.py", "evidence", "T-1494", "--project-root", ".", "--jobs", "1", "--fresh"),
        cwd=".", timeout=9000)
    payload = json.loads(stdout)
    save("core-unit-response", payload)
    print(json.dumps(payload), flush=True)
    return 0 if result["accepted"] and payload.get("ok") else 1


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "focused":
        code = focused()
    elif mode == "neighbors":
        code = neighbors()
    elif mode in ("verify-oracle", "review-oracle"):
        code = oracle(mode)
    elif mode == "core":
        code = core()
    elif mode == "review":
        code = 0 if units("review-authority", ROOT, "test_t1494_continuation_authority")["accepted"] else 1
    else:
        raise ValueError(mode)
    sys.exit(code)
