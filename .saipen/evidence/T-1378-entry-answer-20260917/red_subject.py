"""T-1378 red control: the FINAL oracle against the PRE-FIX subject.

`tools/` is copied to a scratch directory and one thing is reverted there:
`operator_task.unstarted` always answers None, so the diagnostics stop naming
the entry command -- the runtime the field measured, where `status` answered
`next_action: saipen continue` and `continue` answered an improvement audit to
a session that had just been handed a user task.

Exit: 0 when the pre-fix subject FAILS the entry-answer controls.
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

# --- T-1378 RED SUBJECT: the engine before this ticket ---------------------
# The diagnostics answered without ever naming the entry command.
def unstarted(root, env=None):  # noqa: ARG001
    return None
'''

CONTROLS = ("BothDiagnosticsNameTheEntryCommandTests",)


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="t1378-red-"))
    try:
        subject = work / "subject"
        shutil.copytree(REPO / "tools", subject / "tools",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for name in ("saipen", "extensions"):
            source = REPO / name
            if source.is_dir():
                shutil.copytree(source, subject / name,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        target = subject / "tools" / "saipen_engine" / "operator_task.py"
        before = hashlib.sha256(target.read_bytes()).hexdigest()
        with target.open("a", encoding="utf-8") as handle:
            handle.write(MUTATION)
        after = hashlib.sha256(target.read_bytes()).hexdigest()
        oracle = REPO / "tools" / "test_entry_answer_agrees.py"
        copied = subject / "tools" / "test_entry_answer_agrees.py"
        print(f"oracle  sha256 {hashlib.sha256(oracle.read_bytes()).hexdigest()[:16]} "
              f"(identical copy: {oracle.read_bytes() == copied.read_bytes()})")
        print(f"subject {before[:16]} -> {after[:16]} (unstarted() reverted)")
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "tools.test_entry_answer_agrees", "-v"],
            cwd=subject, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=1800,
        )
        output = proc.stdout + proc.stderr
        print("--- pre-fix subject run ---")
        print(output[-2500:])
        failed = {
            line.split("(", 1)[1].split(".")[-2]
            for line in output.splitlines()
            if line.startswith(("FAIL: ", "ERROR: ")) and "(" in line
        }
        print(f"classes red against the pre-fix subject: {sorted(failed)}")
        missing = [name for name in CONTROLS if name not in failed]
        if missing:
            print(f"NOT RED, so the oracle proves nothing here: {missing}")
            return 1
        print("RED CONTROL OK: the diagnostics stop naming the entry command")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
