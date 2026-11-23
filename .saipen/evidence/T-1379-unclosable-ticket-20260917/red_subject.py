"""T-1379 red control: the FINAL oracle against the PRE-FIX subject.

`tools/` is copied to a scratch directory and ONE thing is reverted there:
`intake.discharge_request_clauses` returns nothing, which is exactly the engine
before this ticket -- a receipt captured by `saipen start` keeps its empty
contract, `coverage_complete` requires `actionable > 0`, and `ticket done`
answers SOURCE_UNRESOLVED forever. The oracle file itself is copied byte for
byte, so the only variable between red and green is the implementation.

Run:  python .saipen/evidence/T-1379-unclosable-ticket-20260917/red_subject.py
Exit: 0 when the pre-fix subject FAILS the closure controls (the gate can
      fail), 1 when it passes and the oracle proves nothing.
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

# --- T-1379 RED SUBJECT: the engine before this ticket ---------------------
# The request's own clause was never discharged, so a receipt with an empty
# contract could not reach coverage_complete and the ticket the canonical
# entry command created could not be finished by any CLI command.
def discharge_request_clauses(root, work, *, evidence, verification):  # noqa: ARG001
    return []
'''

#: The controls that measure the discharge. A subject that reverts it must fail
#: these; the identity and no-proof controls stay green, because neither is
#: about the discharge itself.
CLOSURE_CONTROLS = ("TheEntryCommandsTicketClosesTests",)


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="t1379-red-"))
    try:
        subject = work / "subject"
        shutil.copytree(
            REPO / "tools",
            subject / "tools",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        for name in ("saipen", "extensions"):
            source = REPO / name
            if source.is_dir():
                shutil.copytree(
                    source,
                    subject / name,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
        target = subject / "tools" / "saipen_engine" / "intake.py"
        before = hashlib.sha256(target.read_bytes()).hexdigest()
        with target.open("a", encoding="utf-8") as handle:
            handle.write(MUTATION)
        after = hashlib.sha256(target.read_bytes()).hexdigest()

        oracle = REPO / "tools" / "test_request_clause_closure.py"
        copied = subject / "tools" / "test_request_clause_closure.py"
        print(f"oracle   sha256 {hashlib.sha256(oracle.read_bytes()).hexdigest()[:16]} "
              f"(identical copy: {oracle.read_bytes() == copied.read_bytes()})")
        print(f"subject  {before[:16]} -> {after[:16]} (discharge_request_clauses reverted)")

        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "tools.test_request_clause_closure", "-v"],
            cwd=subject,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
        )
        output = proc.stdout + proc.stderr
        print("--- pre-fix subject run ---")
        print(output[-3000:])
        failed = {
            line.split("(", 1)[1].split(".")[-2]
            for line in output.splitlines()
            if line.startswith(("FAIL: ", "ERROR: ")) and "(" in line
        }
        print(f"classes red against the pre-fix subject: {sorted(failed)}")
        missing = [name for name in CLOSURE_CONTROLS if name not in failed]
        if missing:
            print(f"NOT RED, so the oracle proves nothing here: {missing}")
            return 1
        print("RED CONTROL OK: the closure controls fail against the reverted discharge")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
