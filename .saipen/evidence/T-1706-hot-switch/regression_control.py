"""Repeat the unchanged prevention oracle against disposable old/new subjects."""

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
OLD = ROOT / ".saipen/evidence/AUDAPACK-prevention"
SUBJECTS = {
    "tools/saipen_engine/guard_events.py": "original-guard_events.py",
    "tools/saipen_engine/admission.py": "original-admission.py",
    "extensions/adapters/opencode/saipen-guard.js": "original-opencode-saipen-guard.js",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    destination = HERE / "regression-control-v2.json"
    if destination.exists():
        raise SystemExit("existing evidence is immutable")
    temporary_root = Path(tempfile.gettempdir()).resolve()
    scratch = Path(tempfile.mkdtemp(prefix="saipen-t1706-oracle-")).resolve()
    if not scratch.is_relative_to(temporary_root) or scratch == temporary_root:
        raise SystemExit("scratch path is outside the expected temporary directory")
    sandbox = scratch / "project"
    command = [sys.executable, "-B", "-m", "unittest",
               "tools.test_t1705_lifecycle_write_preflight", "-q"]
    runs = []
    current = {name: (ROOT / name).read_bytes() for name in SUBJECTS}
    live_before = {name: digest(ROOT / name) for name in SUBJECTS}
    try:
        def ignore(directory: str, names: list[str]) -> set[str]:
            skipped = {name for name in names if name == "__pycache__" or name.endswith(".pyc")}
            if Path(directory) == ROOT:
                skipped.update({".git", ".saipen", ".ruff_cache", ".pytest_cache"} & set(names))
            return skipped

        shutil.copytree(ROOT, sandbox, symlinks=True, ignore=ignore)
        verifier = sandbox / "tools/test_t1705_lifecycle_write_preflight.py"
        verifier_hash = digest(verifier)
        for kind, repeat in (("good", 1), ("bad", 1), ("bad", 2), ("restored", 1),
                             ("restored", 2)):
            for name, backup in SUBJECTS.items():
                (sandbox / name).write_bytes(
                    (OLD / backup).read_bytes() if kind == "bad" else current[name]
                )
            result = subprocess.run(
                command, cwd=sandbox, capture_output=True, text=True,
                encoding="utf-8", errors="replace", check=False, timeout=300,
            )
            output = result.stdout + result.stderr
            label = f"regression-v2-{kind}-{repeat}"
            (HERE / f"{label}.txt").write_text(output, encoding="utf-8")
            count = re.search(r"Ran (\d+) tests?", output)
            failures = sorted(re.findall(r"^FAIL: (.*)$", output, re.MULTILINE))
            errors = sorted(re.findall(r"^ERROR: (.*)$", output, re.MULTILINE))
            runs.append({
                "subject": kind, "repeat": repeat, "command": command,
                "exit_code": result.returncode,
                "ran": int(count.group(1)) if count else 0,
                "failures": failures, "errors": errors,
                "verifier_sha256": digest(verifier),
                "implementation": {name: digest(sandbox / name) for name in SUBJECTS},
                "output": str((HERE / f"{label}.txt").relative_to(ROOT)).replace("\\", "/"),
                "output_sha256": digest(HERE / f"{label}.txt"),
            })
            print(json.dumps({key: runs[-1][key] for key in (
                "subject", "repeat", "exit_code", "ran", "failures", "errors",
            )}), flush=True)
            if not count or (kind != "bad" and result.returncode != 0):
                break  # an unavailable known-good instrument proves no subject failure
        bad = [run for run in runs if run["subject"] == "bad"]
        good = [run for run in runs if run["subject"] != "bad"]
        valid = (
            len(runs) == 5 and len(bad) == 2
            and all(run["ran"] > 0 and run["verifier_sha256"] == verifier_hash for run in runs)
            and all(run["exit_code"] == 0 and not run["failures"] and not run["errors"]
                    for run in good)
            and all(run["exit_code"] == 1 and run["failures"] and not run["errors"]
                    for run in bad)
            and bad[0]["failures"] == bad[1]["failures"]
            and live_before == {name: digest(ROOT / name) for name in SUBJECTS}
        )
        destination.write_text(json.dumps({
            "verdict": "PASS" if valid else "FAIL",
            "live_subject_unchanged": live_before == {
                name: digest(ROOT / name) for name in SUBJECTS
            },
            "unchanged_verifier": verifier_hash,
            "red_names_repeat_identically": len(bad) == 2 and bad[0]["failures"] == bad[1]["failures"],
            "runs": runs,
        }, indent=2) + "\n", encoding="utf-8")
        return 0 if valid else 1
    finally:
        # Revalidate the resolved absolute target before recursive cleanup.
        target = scratch.resolve()
        if target.is_relative_to(temporary_root) and target != temporary_root:
            def make_writable(func, path, _exc):
                os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                func(path)

            shutil.rmtree(target, onerror=make_writable)


if __name__ == "__main__":
    sys.exit(main())
