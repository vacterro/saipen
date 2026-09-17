"""T-1380 slice 6 red control: the FINAL polygon oracle against the PRE-FIX harness.

`tools/` is copied to a scratch directory and the polygon is reverted there to
the instrument the field measured:

* `windows_path_task` is a healthy project handed the missing-path task
  (`V:\\_TEMP_\\fastprompter_drag\\SAIPENVIEW_main.py`), so the positive case can
  only measure a model declining to invent notes;
* a provider error before any tool is never classified -- the session reads as
  MEASURED with `protocol_commands_before_productive: 0`;
* a condition is driven exactly once, whatever happened to the provider.

Exit: 0 when the pre-fix harness FAILS both new control classes.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]

MUTATION = '''

# --- T-1380 RED SUBJECT: the polygon before slice 6 --------------------------
def _windows_notes_project(case):
    import test_t1363_zero_manual_entry as fixtures

    return fixtures.healthy(case)


def windows_path_task(project):  # noqa: ARG001
    return FIELD_TASK


def infrastructure_failure(returncode, tools, events, stderr):  # noqa: ARG001
    return None


def drive_with_retries(run_once, retries, unchanged):  # noqa: ARG001
    record = run_once()
    record["attempts"] = [{"attempt": 1, "measurement": record.get("measurement")}]
    return record
'''

CONTROLS = ("WindowsPathAuthorityTests", "InfrastructureFailureTests")


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="t1380-red-polygon-"))
    try:
        subject = work / "subject"
        for name in ("tools", "saipen", "extensions"):
            source = REPO / name
            if source.is_dir():
                shutil.copytree(
                    source,
                    subject / name,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
        target = subject / "tools" / "t1363_field_polygon.py"
        before = hashlib.sha256(target.read_bytes()).hexdigest()
        with target.open("a", encoding="utf-8") as handle:
            handle.write(MUTATION)
        after = hashlib.sha256(target.read_bytes()).hexdigest()
        oracle = REPO / "tools" / "test_field_fixture_isolation.py"
        copied = subject / "tools" / "test_field_fixture_isolation.py"
        print(
            f"oracle  sha256 {hashlib.sha256(oracle.read_bytes()).hexdigest()[:16]} "
            f"(identical copy: {oracle.read_bytes() == copied.read_bytes()})"
        )
        print(f"subject {before[:16]} -> {after[:16]} (polygon reverted)")
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "tools.test_field_fixture_isolation", "-v"],
            cwd=subject,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
        )
        output = proc.stdout + proc.stderr
        failed = {
            line.split("(", 1)[1].split(".")[-2]
            for line in output.splitlines()
            if line.startswith(("FAIL: ", "ERROR: ")) and "(" in line
        }
        for line in output.splitlines():
            if line.startswith(("FAIL: ", "ERROR: ", "Ran ", "FAILED", "OK")):
                print(line)
        print(f"classes red against the pre-fix harness: {sorted(failed)}")
        missing = [name for name in CONTROLS if name not in failed]
        if missing:
            print(f"NOT RED, so the oracle proves nothing here: {missing}")
            return 1
        print("RED CONTROL OK: the reverted harness fails both new control classes")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
