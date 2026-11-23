"""Repeat one unchanged declaration oracle against restored old/new subjects."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SUBJECTS = {
    "tools/saipen_engine/operations.py": "operations.py.before",
    "tools/saipen.py": "saipen.py.before",
}
VERIFIER = "tools/test_t1708_regression_declaration.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    label = sys.argv[1]
    if Path(label).name != label:
        raise SystemExit("invalid label")
    receipt = HERE / f"{label}.json"
    if receipt.exists():
        raise SystemExit("existing evidence is immutable")
    live = {name: sha(ROOT / name) for name in (*SUBJECTS, VERIFIER)}
    current = {name: (ROOT / name).read_bytes() for name in SUBJECTS}
    runs = []
    # No live subject is changed. TemporaryDirectory owns exactly this scratch.
    with tempfile.TemporaryDirectory(prefix="saipen-t1708-controls-") as tmp:
        sandbox = Path(tmp) / "subject"
        sandbox.mkdir()
        for name in ("tools", "saipen", "tests", "extensions", "bin"):
            shutil.copytree(ROOT / name, sandbox / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        command = [sys.executable, "-B", "-m", "unittest",
                   "tools.test_t1708_regression_declaration", "-q"]
        for kind, repeat in (("current", 1), ("old", 1), ("old", 2),
                             ("restored", 1), ("restored", 2)):
            for name, backup in SUBJECTS.items():
                (sandbox / name).write_bytes(
                    (HERE / backup).read_bytes() if kind == "old" else current[name])
            run = subprocess.run(command, cwd=sandbox, capture_output=True,
                                 text=True, encoding="utf-8", errors="replace",
                                 timeout=180, check=False)
            output = run.stdout + run.stderr
            path = HERE / f"{label}-{kind}-{repeat}.txt"
            if path.exists():
                raise SystemExit("output already exists")
            path.write_text(output, encoding="utf-8")
            count = re.search(r"Ran (\d+) tests?", output)
            record = {
                "subject": kind, "repeat": repeat, "command": command,
                "exit_code": run.returncode, "ran": int(count[1]) if count else 0,
                "failures": sorted(re.findall(r"^FAIL: (.*)$", output, re.M)),
                "errors": sorted(re.findall(r"^ERROR: (.*)$", output, re.M)),
                "verifier_sha256": sha(sandbox / VERIFIER),
                "implementation": {name: sha(sandbox / name) for name in SUBJECTS},
                "output": path.relative_to(ROOT).as_posix(), "output_sha256": sha(path),
            }
            runs.append(record)
            print(json.dumps({key: record[key] for key in
                              ("subject", "repeat", "exit_code", "ran", "failures", "errors")}),
                  flush=True)
            if not count or (kind != "old" and run.returncode != 0):
                break
    old = [run for run in runs if run["subject"] == "old"]
    good = [run for run in runs if run["subject"] != "old"]
    unchanged = live == {name: sha(ROOT / name) for name in live}
    valid = (
        len(runs) == 5 and len(old) == 2 and unchanged
        and all(run["ran"] == 13 and run["verifier_sha256"] == live[VERIFIER] for run in runs)
        and all(run["exit_code"] == 0 and not run["failures"] and not run["errors"] for run in good)
        and all(run["exit_code"] == 1 and len(run["failures"]) == 11 and not run["errors"] for run in old)
        and old[0]["failures"] == old[1]["failures"]
    )
    receipt.write_text(json.dumps({"verdict": "PASS" if valid else "FAIL",
                                  "live_subject_unchanged": unchanged, "live": live,
                                  "runs": runs}, indent=2) + "\n", encoding="utf-8")
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
