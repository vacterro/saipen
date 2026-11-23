"""T-1377 red control: the FINAL oracle against the PRE-FIX subject.

`tools/` is copied to a scratch directory and exactly one thing is reverted
there: refusals stop carrying a route. `operations._refuse` drops the
`canonical_next_command` and `legal_destinations` fields, and `admission`'s
brake route table is emptied -- which is precisely the engine the field
measured, where every refusal named a rule and none named a move.

Run:  python .saipen/evidence/T-1377-refusal-routes-20260917/red_subject.py
Exit: 0 when the pre-fix subject FAILS the route controls, 1 when it passes and
      the oracle proves nothing.
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

OPERATIONS_MUTATION = '''

# --- T-1377 RED SUBJECT: refusals before this ticket -----------------------
# The payload named the rule and nothing else. Reverting only the carrying of
# the route keeps every other byte of the subject identical to the tree under
# test, so a red here is attributable to the route and to nothing else.
_T1377_ORIGINAL_REFUSE = _refuse


def _refuse(code: str, detail: str = "", **extra):  # noqa: F811
    extra.pop("canonical_next_command", None)
    extra.pop("legal_destinations", None)
    return _T1377_ORIGINAL_REFUSE(code, detail, **extra)
'''

ADMISSION_MUTATION = '''

# --- T-1377 RED SUBJECT: the guard's brake named no exit -------------------
_BRAKE_ROUTES = {}
'''

ROUTE_CONTROLS = (
    "IllegalTransitionNamesTheLegalEdgeTests",
    "VerificationEvidenceNamesItsShapeTests",
    "MalformedCommandsPrintTheCorrectedOneTests",
    "BlockedProjectNamesItsExitTests",
)


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="t1377-red-"))
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
        for rel, mutation in (
            ("tools/saipen_engine/operations.py", OPERATIONS_MUTATION),
            ("tools/saipen_engine/admission.py", ADMISSION_MUTATION),
        ):
            target = subject / rel
            before = hashlib.sha256(target.read_bytes()).hexdigest()
            with target.open("a", encoding="utf-8") as handle:
                handle.write(mutation)
            after = hashlib.sha256(target.read_bytes()).hexdigest()
            print(f"subject {rel}: {before[:16]} -> {after[:16]}")

        oracle = REPO / "tools" / "test_refusal_routes.py"
        copied = subject / "tools" / "test_refusal_routes.py"
        print(f"oracle  sha256 {hashlib.sha256(oracle.read_bytes()).hexdigest()[:16]} "
              f"(identical copy: {oracle.read_bytes() == copied.read_bytes()})")

        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "tools.test_refusal_routes", "-v"],
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
        missing = [name for name in ROUTE_CONTROLS if name not in failed]
        if missing:
            print(f"NOT RED, so the oracle proves nothing here: {missing}")
            return 1
        print("RED CONTROL OK: every route control fails when refusals carry no route")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
