"""Restore the chronology defect in a disposable copy with a fixed verifier."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SUBJECT = "tools/saipen_engine/oracle.py"
VERIFIER = "tools/test_t1707_regression_chronology.py"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    destination = HERE / "chronology-control.json"
    if destination.exists():
        raise SystemExit("existing evidence is immutable")
    identities = json.loads((HERE / "chronology-identities-before.json").read_text())
    old = (HERE / "oracle-before-t1707.py").read_bytes()
    new = (ROOT / SUBJECT).read_bytes()
    verifier = (ROOT / VERIFIER).read_bytes()
    assert sha(old) == identities["subject_before_sha256"]
    assert sha(verifier) == identities["verifier_sha256"]
    temporary_root = Path(tempfile.gettempdir()).resolve()
    scratch = Path(tempfile.mkdtemp(prefix="saipen-t1707-control-")).resolve()
    assert scratch.is_relative_to(temporary_root) and scratch != temporary_root
    project = scratch / "project"
    command = [sys.executable, "-B", "-m", "unittest",
               "tools.test_t1707_regression_chronology", "-q"]
    runs = []
    try:
        def ignore(directory, names):
            skipped = {name for name in names if name == "__pycache__" or name.endswith(".pyc")}
            if Path(directory) == ROOT:
                skipped.update({".git", ".saipen", ".ruff_cache", ".pytest_cache"} & set(names))
            return skipped

        shutil.copytree(ROOT, project, symlinks=True, ignore=ignore)
        attempts = [("current", 0), *[(kind, repeat) for repeat in (1, 2, 3)
                                    for kind in ("old", "restored")]]
        for kind, repeat in attempts:
            (project / SUBJECT).write_bytes(old if kind == "old" else new)
            assert (project / VERIFIER).read_bytes() == verifier
            completed = subprocess.run(command, cwd=project, capture_output=True,
                                       check=False, timeout=120)
            output = completed.stdout + completed.stderr
            path = HERE / f"chronology-control-{kind}-{repeat}.txt"
            assert not path.exists()
            path.write_bytes(output)
            text = output.decode("utf-8", errors="replace")
            count = re.search(r"Ran (\d+) tests?", text)
            run = {"subject": kind, "repeat": repeat, "command": command,
                   "exit_code": completed.returncode,
                   "ran": int(count.group(1)) if count else 0,
                   "failures": sorted(re.findall(r"^FAIL: (.*)$", text, re.MULTILINE)),
                   "errors": sorted(re.findall(r"^ERROR: (.*)$", text, re.MULTILINE)),
                   "verifier_sha256": sha((project / VERIFIER).read_bytes()),
                   "subject_sha256": sha((project / SUBJECT).read_bytes()),
                   "output": str(path.relative_to(ROOT)).replace("\\", "/"),
                   "output_sha256": sha(output)}
            runs.append(run)
            print(json.dumps({key: run[key] for key in (
                "subject", "repeat", "exit_code", "ran", "failures", "errors",
            )}), flush=True)
            if run["ran"] != 8 or (kind != "old" and completed.returncode != 0):
                break
        bad = [run for run in runs if run["subject"] == "old"]
        good = [run for run in runs if run["subject"] != "old"]
        unchanged = (ROOT / SUBJECT).read_bytes() == new and (ROOT / VERIFIER).read_bytes() == verifier
        valid = (len(runs) == 7 and len(bad) == 3 and unchanged
                 and all(run["ran"] == 8 and run["verifier_sha256"] == sha(verifier)
                         for run in runs)
                 and all(run["exit_code"] == 0 and not run["failures"] and not run["errors"]
                         for run in good)
                 and all(run["exit_code"] == 1 and len(run["failures"]) == 4
                         and run["failures"] == bad[0]["failures"] and not run["errors"]
                         for run in bad))
        destination.write_text(json.dumps({"verdict": "PASS" if valid else "FAIL",
                                           "live_subject_unchanged": unchanged,
                                           "unchanged_verifier": sha(verifier),
                                           "runs": runs}, indent=2) + "\n", encoding="utf-8")
        return 0 if valid else 1
    finally:
        target = scratch.resolve()
        assert target.is_relative_to(temporary_root) and target != temporary_root

        def make_writable(func, path, _exc):
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            func(path)

        shutil.rmtree(target, onerror=make_writable)


if __name__ == "__main__":
    sys.exit(main())
