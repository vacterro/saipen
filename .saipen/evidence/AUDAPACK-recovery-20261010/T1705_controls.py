"""Repeat the unchanged current T-1705 oracle against its preserved old owners."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = ROOT / ".saipen/evidence/AUDAPACK-prevention"
SUBJECTS = {"tools/saipen_engine/guard_events.py": "original-guard_events.py",
            "tools/saipen_engine/admission.py": "original-admission.py"}
VERIFIER = "tools/test_t1705_lifecycle_write_preflight.py"
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import oracle


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    sandbox = HERE / "T1705-oracle-subject"
    assert not sandbox.exists()
    before = {name: sha(ROOT / name) for name in (*SUBJECTS, VERIFIER)}
    for part in ("tools", "saipen", "tests", "extensions", "bin", "bootstrap"):
        shutil.copytree(ROOT / part, sandbox / part, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(ROOT / "VERSION", sandbox / "VERSION")
    command_text = "python -B -m unittest tools.test_t1705_lifecycle_write_preflight -q"
    command = [sys.executable, "-B", "-m", "unittest", "tools.test_t1705_lifecycle_write_preflight", "-q"]
    verifier = oracle.verifier_identity(command_text, (VERIFIER,), ROOT)
    current = {name: (ROOT / name).read_bytes() for name in SUBJECTS}
    runs = []
    for kind, repeat in (("current", 1), ("old", 1), ("old", 2), ("restored", 1)):
        for name, backup in SUBJECTS.items():
            (sandbox / name).write_bytes((OLD / backup).read_bytes() if kind == "old" else current[name])
        assert sha(sandbox / VERIFIER) == before[VERIFIER]
        env = os.environ.copy()
        for key in list(env):
            if key.upper().startswith("SAIPEN"):
                env.pop(key)
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", GIT_OPTIONAL_LOCKS="0")
        run = subprocess.run(command, cwd=sandbox, env=env, capture_output=True, timeout=240, check=False)
        raw = run.stdout + run.stderr
        path = HERE / f"T1705-control-{kind}-{repeat}.txt"
        with path.open("xb") as handle:
            handle.write(raw)
        text = raw.decode("utf-8", errors="replace")
        count = re.search(r"Ran (\d+) tests?", text)
        row = {"subject": kind, "repeat": repeat, "argv": command, "exit_code": run.returncode,
               "ran": int(count[1]) if count else 0,
               "failures": sorted(re.findall(r"^FAIL: (.*)$", text, re.M)),
               "errors": sorted(re.findall(r"^ERROR: (.*)$", text, re.M)),
               "verifier": verifier, "verifier_file_sha256": sha(sandbox / VERIFIER),
               "implementation": {name: sha(sandbox / name) for name in SUBJECTS},
               "subject_digest": oracle.oracle_digest(sandbox, SUBJECTS),
               "output": path.relative_to(ROOT).as_posix(), "output_sha256": sha(path)}
        runs.append(row)
        print(json.dumps({key: row[key] for key in ("subject", "repeat", "exit_code", "ran", "failures", "errors")}), flush=True)
        if not count or row["errors"] or (kind != "old" and run.returncode != 0):
            break
    old = [row for row in runs if row["subject"] == "old"]
    good = [row for row in runs if row["subject"] != "old"]
    unchanged = before == {name: sha(ROOT / name) for name in before}
    passed = (len(runs) == 4 and unchanged and len(old) == 2
              and all(row["ran"] > 0 and row["verifier_file_sha256"] == before[VERIFIER] for row in runs)
              and len({row["ran"] for row in runs}) == 1
              and all(row["exit_code"] == 1 and row["failures"] and not row["errors"] for row in old)
              and old[0]["failures"] == old[1]["failures"]
              and all(row["exit_code"] == 0 and not row["errors"] and not row["failures"] for row in good))
    record = {"pass": bool(passed), "live_subject_unchanged": unchanged,
              "verifier": verifier, "command": command_text, "before": before,
              "runs": runs, "scratch_preserved": str(sandbox)}
    with (HERE / "T1705-current-controls.json").open("x", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)
        handle.write("\n")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
