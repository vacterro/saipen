"""T-1376 red control: the FINAL oracle against the PRE-FIX subject.

`tools/` is copied to a scratch directory and one thing is reverted there:
`operator_task.witness` always answers `model_supplied`, which is the engine
before this ticket -- a receipt that says nothing about who compared its text
with the operator's, and an ingress that cannot contradict a declared task.
The oracle file is copied byte for byte, so the only variable is the engine.

Run:  python .saipen/evidence/T-1376-operator-words-20260917/red_subject.py
Exit: 0 when the pre-fix subject FAILS the witness controls, 1 when it passes
      and the oracle proves nothing.
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

# --- T-1376 RED SUBJECT: the engine before this ticket ---------------------
# Every request was recorded as the session's own words with nothing compared,
# and a declared operator task could not contradict the text that arrived.
def witness(text, *, obligation_met=False, env=None):  # noqa: ARG001
    from .pending_ingress import ingress_digest

    return {"witness": WITNESS_MODEL, "compared_digest": ingress_digest(text)}
'''

WITNESS_CONTROLS = (
    "NobodyComparedItAndTheReceiptSaysSoTests",
    "AnOperatorCarrierIsComparedTests",
    "TheTransportObligationIsAlsoAWitnessTests",
)


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="t1376-red-"))
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
        target = subject / "tools" / "saipen_engine" / "operator_task.py"
        before = hashlib.sha256(target.read_bytes()).hexdigest()
        with target.open("a", encoding="utf-8") as handle:
            handle.write(MUTATION)
        after = hashlib.sha256(target.read_bytes()).hexdigest()

        oracle = REPO / "tools" / "test_operator_task_witness.py"
        copied = subject / "tools" / "test_operator_task_witness.py"
        print(f"oracle  sha256 {hashlib.sha256(oracle.read_bytes()).hexdigest()[:16]} "
              f"(identical copy: {oracle.read_bytes() == copied.read_bytes()})")
        print(f"subject {before[:16]} -> {after[:16]} (witness() reverted)")

        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "tools.test_operator_task_witness", "-v"],
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
        missing = [name for name in WITNESS_CONTROLS if name not in failed]
        if missing:
            print(f"NOT RED, so the oracle proves nothing here: {missing}")
            return 1
        print("RED CONTROL OK: the witness controls fail when every receipt claims nothing")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
