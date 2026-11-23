"""T-1892 red control: the same assertions against the pre-fix read().

The regression module proves `Journal.read()` refuses what the canonical
decoder refuses. A control that has only ever been green proves nothing, so
this runs the SAME test methods twice in one process:

  1. on the current tree -- must pass;
  2. with `Journal.read` and `Journal.fold_progress` restored to their exact
     HEAD bodies (the permissive projection inside `except Exception: pass`)
     -- the forged-terminal test must FAIL, and the legitimate-merge test must
     still pass, so the control is measuring the refusal and not the harness.

Nothing is written outside a temp project. The original methods are restored
before the script exits.

    python .saipen/evidence/T-1892-one-decoder/red-control.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))

from saipen_engine import journal as J  # noqa: E402


def head_read(self) -> dict:
    record = json.loads(self.manifest.read_text(encoding="utf-8"))
    progress_file = self.dir / "progress.json"
    if progress_file.is_file():
        try:
            prog = json.loads(progress_file.read_text(encoding="utf-8"))
            if "status" in prog:
                record["status"] = prog["status"]
            if "progress_index" in prog:
                record["progress_index"] = prog["progress_index"]
            frontier = prog.get("applied_frontier", -1)
            targets = record.get("targets", [])
            for i in range(min(frontier + 1, len(targets))):
                targets[i]["applied"] = True
        except Exception:
            pass
    return record


def head_fold_progress(self) -> None:
    progress_file = self.dir / "progress.json"
    if progress_file.is_file():
        try:
            record = self.read()
            J._atomic_json(self.manifest, record, ownership_root=self.project_root)
            progress_file.unlink()
        except OSError:
            pass


def run(names: list[str]) -> unittest.result.TestResult:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in names:
        suite.addTests(loader.loadTestsFromName(name))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result


FORGED = "test_t1892_one_decoder.RefusedSidecarTests." \
    "test_a_forged_terminal_status_is_not_visible_through_read"
MERGE = "test_t1892_one_decoder.LegitimateSidecarTests." \
    "test_a_legitimate_sidecar_still_merges"
REFUSALS = "test_t1892_one_decoder.RefusedSidecarTests." \
    "test_every_decoder_refusal_is_read_s_refusal"


def main() -> int:
    print("=" * 70)
    print("1. CURRENT TREE -- the three assertions must pass")
    print("=" * 70)
    current = run([FORGED, MERGE, REFUSALS])
    current_green = current.wasSuccessful()

    original_read, original_fold = J.Journal.read, J.Journal.fold_progress
    J.Journal.read, J.Journal.fold_progress = head_read, head_fold_progress
    try:
        print()
        print("=" * 70)
        print("2. PRE-FIX read()/fold_progress() -- the refusal tests must FAIL")
        print("=" * 70)
        prefix = run([FORGED, MERGE, REFUSALS])
        prefix_green = prefix.wasSuccessful()
        print()
        print("=" * 70)
        print("3. LEGITIMATE-MERGE CONTROL -- must still pass pre-fix")
        print("=" * 70)
        merge_only = run([MERGE])
    finally:
        J.Journal.read, J.Journal.fold_progress = original_read, original_fold

    print()
    print("=" * 70)
    print("VERDICT")
    print("=" * 70)
    print(f"current tree green            : {current_green}")
    print(f"pre-fix tree green            : {prefix_green}")
    print(f"pre-fix legitimate merge green: {merge_only.wasSuccessful()}")
    ok = current_green and not prefix_green and merge_only.wasSuccessful()
    print()
    if ok:
        print("CONTROL OK -- the refusals are the fix, not the harness.")
        return 0
    print("CONTROL INVALID -- the assertions do not discriminate the two trees.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
