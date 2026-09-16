"""T-1372 red control: the FINAL oracle against the PRE-FIX subject.

VERIFY-ORACLE-01 in one sentence: an old version's FAIL plus a new version's
PASS is not a pair. The controls in `tools/test_pending_ingress.py` grew after
the first red run, so this script re-establishes the red half against the
oracle as it stands now.

The subject is the engine's own decision point, reverted. `tools/` is copied to
a scratch directory and ONE thing is changed there: `pending_ingress.enforce`
returns None for every input -- exactly the pre-T-1372 behaviour, where a
transport refusal named a command and nothing compared the bytes that arrived
with the bytes that were refused. Everything else, the test file included, is
byte-identical to the tree under test.

Run:  python .saipen/evidence/T-1372-ingress-authority-20260917/red_subject.py
Exit: 0 when the pre-fix subject FAILS the oracle (the gate can fail), 1 when
      it passes (the oracle proves nothing and must not be believed).
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

# --- T-1372 RED SUBJECT: the engine before this ticket -------------------
# A transport refusal named the next command and owed nothing. Restoring only
# this decision keeps every other byte of the subject identical to the tree
# under test, so a red here is attributable to the enforcement and to nothing
# else.
def enforce(root, text, *, supersede=False):  # noqa: ARG001
    return None
'''

#: The controls that measure the enforcement. A subject that reverts the
#: decision must fail at least these; the recording and digest controls are
#: expected to stay green, because recording is not the thing being reverted.
ENFORCEMENT_CONTROLS = (
    "ParaphraseIsRefusedTests",
    "OperatorSupersedeTests",
    "MalformedRecordFailsClosedTests",
    "BothIngressDoorsTests",
    "OriginalBytesClearTheObligationTests",
)


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="t1372-red-"))
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
        target = subject / "tools" / "saipen_engine" / "pending_ingress.py"
        before = hashlib.sha256(target.read_bytes()).hexdigest()
        with target.open("a", encoding="utf-8") as handle:
            handle.write(MUTATION)
        after = hashlib.sha256(target.read_bytes()).hexdigest()

        oracle = REPO / "tools" / "test_pending_ingress.py"
        copied = subject / "tools" / "test_pending_ingress.py"
        print(f"oracle   sha256 {hashlib.sha256(oracle.read_bytes()).hexdigest()[:16]}")
        print(f"         copied {hashlib.sha256(copied.read_bytes()).hexdigest()[:16]} "
              f"(identical: {oracle.read_bytes() == copied.read_bytes()})")
        print(f"subject  {before[:16]} -> {after[:16]} (enforce() reverted)")

        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "tools.test_pending_ingress", "-v"],
            cwd=subject,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
        )
        output = proc.stdout + proc.stderr
        print("--- pre-fix subject run ---")
        print(output[-4000:])
        failed = {
            line.split("(", 1)[1].split(".")[-2]
            for line in output.splitlines()
            if line.startswith(("FAIL: ", "ERROR: ")) and "(" in line
        }
        missing = [name for name in ENFORCEMENT_CONTROLS if name not in failed]
        print(f"classes red against the pre-fix subject: {sorted(failed)}")
        if missing:
            print(f"NOT RED, so the oracle proves nothing here: {missing}")
            return 1
        print("RED CONTROL OK: every enforcement control fails against the reverted decision")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
