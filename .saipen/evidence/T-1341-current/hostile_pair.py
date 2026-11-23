"""Actual foreign-engine execution distinguishes historical and current entry forms."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[2]
HISTORICAL = "17c61f732ce32bccee3dcc27905377433600a5d5"
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.evidence import EvidenceRun
from test_hermetic_env import hermetic_env

FIXTURE = ("import os\nfrom pathlib import Path\n"
           "Path(os.environ['T1341_SHADOW_SENTINEL']).write_text('executed')\n"
           "raise RuntimeError('foreign saipen_engine executed')\n")
COMMANDS = ([sys.executable, "-B", "tools/saipen.py", "--help"],
            [sys.executable, "-B", "-m", "tools.saipen", "--help"])


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def ignore(directory: str, names: list[str]) -> list[str]:
    excluded = {".git", "__pycache__", ".ruff_cache", ".pytest_cache"}
    if Path(directory).resolve() == ROOT:
        excluded.add(".saipen")
    return [name for name in names if name in excluded]


def run(label: str) -> int:
    durable = EVIDENCE / label
    assert not durable.exists(), "immutable evidence label already exists"
    live_init = sha(ROOT / "tools/__init__.py")
    historical = subprocess.check_output(
        ["git", "show", HISTORICAL + ":tools/__init__.py"], cwd=ROOT)
    allocation = EvidenceRun("t1341-" + label, "T-1341", durable_dir=durable)
    original, current, shadow = [allocation.temp_root / name
                                 for name in ("original", "current", "shadow")]
    allocation.register_ephemeral(original, current, shadow)
    shutil.copytree(ROOT, current, ignore=ignore)
    shutil.copytree(current, original)
    (original / "tools/__init__.py").write_bytes(historical)
    package = shadow / "saipen_engine"
    package.mkdir(parents=True)
    fixture_path = package / "__init__.py"
    fixture_path.write_text(FIXTURE, encoding="utf-8")
    sentinel = shadow / "foreign-executed.txt"
    env = hermetic_env()
    import os
    env["PYTHONPATH"] = str(shadow) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["T1341_SHADOW_SENTINEL"] = str(sentinel)
    verifier = {"commands": COMMANDS, "timeout": 90, "fixture_sha256": sha(fixture_path),
                "rules": "both exit0; usage:saipen stdout equal; foreign execution sentinel absent",
                "environment": "same owned shadow first on PYTHONPATH; same sentinel path"}
    records = []
    for name, subject in (("original", original), ("current", current)):
        cases = []
        for index, command in enumerate(COMMANDS):
            sentinel.unlink(missing_ok=True)
            result = subprocess.run(command, cwd=subject, env=env, capture_output=True,
                                    text=True, encoding="utf-8", timeout=90)
            output = result.stdout + result.stderr
            (durable / f"{name}-{index}.txt").write_text(output, encoding="utf-8")
            cases.append({"entry": "script" if index == 0 else "module",
                          "exit_code": result.returncode,
                          "foreign_executed": sentinel.exists(),
                          "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
                          "output_sha256": hashlib.sha256(output.encode()).hexdigest(),
                          "has_usage": "usage: saipen" in result.stdout,
                          "has_foreign_error": "foreign saipen_engine executed" in result.stderr})
        okay = (all(case["exit_code"] == 0 and case["has_usage"]
                    and not case["foreign_executed"] for case in cases)
                and cases[0]["stdout_sha256"] == cases[1]["stdout_sha256"])
        record = {"label": name, "result": "PASS" if okay else "FAIL",
                  "verifier": digest(verifier), "verifier_identity": verifier,
                  "subject": sha(subject / "tools/__init__.py"), "cases": cases}
        (durable / (name + ".json")).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        records.append(record)
        print(json.dumps(record), flush=True)
    actual_bug = (records[0]["cases"][0]["exit_code"] == 0
                  and not records[0]["cases"][0]["foreign_executed"]
                  and records[0]["cases"][1]["exit_code"] != 0
                  and records[0]["cases"][1]["foreign_executed"]
                  and records[0]["cases"][1]["has_foreign_error"])
    unchanged = live_init == sha(ROOT / "tools/__init__.py")
    okay = actual_bug and records[1]["result"] == "PASS" and unchanged
    summary = {"pair_ok": okay, "actual_bug_observed": actual_bug,
               "historical_commit": HISTORICAL, "historical_init_sha256": hashlib.sha256(historical).hexdigest(),
               "live_init_unchanged": unchanged, "temp_root": str(allocation.temp_root),
               "driver_sha256": sha(Path(__file__)), "records": records}
    (durable / "result.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    allocation.finalize(verdict="PASS" if okay else "FAIL", extra={"pair_ok": okay})
    assert not allocation.temp_root.exists()
    print(json.dumps({"pair_ok": okay, "actual_bug_observed": actual_bug,
                      "live_unchanged": unchanged, "temp_reclaimed": True}), flush=True)
    return 0 if okay else 1


if __name__ == "__main__":
    assert len(sys.argv) == 2 and re.fullmatch(r"[a-z][a-z0-9-]*", sys.argv[1])
    raise SystemExit(run(sys.argv[1]))
