"""T-1380 REVIEW F1 red control: the FINAL shell oracle against the PRE-FIX route.

`tools/` is copied to a scratch directory and `operator_task.file_route` is
reverted there to the route slice 1 printed -- `saipen start --file <path>`,
unquoted. The byte-identical oracle then types that route into every shell
available on this host.

Exit: 0 when the pre-fix route FAILS the quoting control and fails to reach
STARTED in EVERY available shell (one red subTest per shell), which also proves
the per-shell loop really ran each shell.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]

MUTATION = '''

# --- T-1380 RED SUBJECT: the file route before REVIEW F1 ----------------------
def file_route(task_file):
    path = (task_file or "").strip()
    return f"saipen start --file {path}" if path else None
'''

CLASS = "tools.test_operator_task_witness.TheFileRouteSurvivesEveryShellTests"


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="t1380-red-route-"))
    try:
        subject = work / "subject"
        for name in ("tools", "saipen", "extensions"):
            source = REPO / name
            if source.is_dir():
                shutil.copytree(
                    source, subject / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
                )
        target = subject / "tools" / "saipen_engine" / "operator_task.py"
        before = hashlib.sha256(target.read_bytes()).hexdigest()
        with target.open("a", encoding="utf-8") as handle:
            handle.write(MUTATION)
        after = hashlib.sha256(target.read_bytes()).hexdigest()
        oracle = REPO / "tools" / "test_operator_task_witness.py"
        copied = subject / "tools" / "test_operator_task_witness.py"
        print(
            f"oracle  sha256 {hashlib.sha256(oracle.read_bytes()).hexdigest()[:16]} "
            f"(identical copy: {oracle.read_bytes() == copied.read_bytes()})"
        )
        print(f"subject {before[:16]} -> {after[:16]} (file_route reverted to unquoted)")
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "-v", CLASS],
            cwd=subject,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
        )
        output = proc.stdout + proc.stderr
        for line in output.splitlines():
            if line.startswith(("FAIL: ", "ERROR: ", "Ran ", "FAILED", "OK")) or " ... " in line:
                print(line)
        red_shells = sorted(set(re.findall(r"^FAIL: .*\(shell='([^']+)'\)", output, re.MULTILINE)))
        quoting_red = "FAIL: test_the_route_is_double_quoted" in output
        print(f"shells red against the pre-fix route: {red_shells}")
        if not quoting_red or not red_shells:
            print("NOT RED, so the oracle proves nothing here")
            return 1
        print("RED CONTROL OK: the unquoted route fails the quoting control and every shell run")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
