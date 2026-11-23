"""T-1891 red control: the same receipt against the pre-fix age arithmetic.

The regression module proves a padded stamp now ages by its real elapsed time.
A control that has only ever been green proves nothing, so this runs the SAME
test methods twice in one process:

  1. on the current tree -- must pass;
  2. with `conformance_status` replaced by a copy whose freshness arithmetic is
     the pre-fix one (raw `fromisoformat` inside `except Exception: pass`) --
     the padded-stamp test must FAIL, and the clean-stamp test must still pass,
     so the control measures the parse, not the harness.

Nothing is written outside temp projects. The original function is restored
before the script exits.

    python .saipen/evidence/T-1891-freshness/red-control.py
"""

from __future__ import annotations

import datetime
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))

from saipen_engine import conformance as C  # noqa: E402
import test_t1412_conformance_truth as fixtures  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def prefix_status(project_root, gate="core", now=None, source_identity=None):
    """`conformance_status` with ONLY the freshness arithmetic reverted.

    Everything else -- receipt discovery, strict validation, binding, the
    future-skew check, the decision branches -- is the current implementation.
    The single difference is that the age comes from parsing the RAW stamp
    inside `except Exception: pass`, which is what left a padded stamp at
    `age_seconds = 0`.
    """
    ref = now or datetime.datetime.now(datetime.timezone.utc)
    info = C.validator_version_info(project_root, gate=gate, source_identity=source_identity)
    receipt = C.latest_receipt(project_root, gate)
    if receipt is None:
        return {"status": C.STATUS_NOT_RUN, "gate": gate, "validator": info.as_dict()}
    strict_err = C._strict_validate_receipt(receipt, gate, Path(project_root))
    if strict_err:
        return {
            "status": C.STATUS_INVALID,
            "gate": gate,
            "reason": f"receipt is invalid: {strict_err}",
            "receipt": receipt,
            "validator": info.as_dict(),
        }
    if C._future_beyond_skew(receipt.get("timestamp_utc", ""), ref):
        return {
            "status": C.STATUS_STALE_FAIL,
            "gate": gate,
            "stale_reason": C.STALE_REASON_FUTURE_TIMESTAMP,
            "receipt": receipt,
            "validator": info.as_dict(),
        }
    current_head = info.source_head
    current_fp = info.source_tree_fingerprint
    bound = (
        receipt.get("source_head") == current_head
        and receipt.get("source_tree_fingerprint") == current_fp
    )
    is_pass = receipt.get("verdict") == "PASS"
    # ---- the pre-fix arithmetic, verbatim ----
    age_seconds = 0
    try:
        rdt = datetime.datetime.fromisoformat(receipt["timestamp_utc"].replace("Z", "+00:00"))
        age_seconds = (ref - rdt).total_seconds()
    except Exception:
        pass
    # ------------------------------------------
    if not bound:
        return {
            "status": C.STATUS_STALE_PASS if is_pass else C.STATUS_STALE_FAIL,
            "stale_reason": C.STALE_REASON_SOURCE_BINDING_STALE,
            "gate": gate,
            "receipt": receipt,
            "validator": info.as_dict(),
        }
    if age_seconds > C.FRESHNESS_WINDOW_SECONDS:
        return {
            "status": C.STATUS_STALE_PASS if is_pass else C.STATUS_STALE_FAIL,
            "stale_reason": C.STALE_REASON_AGED_BEYOND_WINDOW,
            "gate": gate,
            "receipt": receipt,
            "validator": info.as_dict(),
        }
    cp_err = C._checkpoint_hash_mismatch(receipt, Path(project_root))
    if cp_err:
        return {
            "status": C.STATUS_STALE_PASS,
            "stale_reason": C.STALE_REASON_CHECKPOINT_HASHES_STALE,
            "gate": gate,
            "receipt": receipt,
            "validator": info.as_dict(),
        }
    return {
        "status": C.STATUS_CURRENT_PASS if is_pass else C.STATUS_CURRENT_FAIL,
        "gate": gate,
        "receipt": receipt,
        "validator": info.as_dict(),
    }


def run(names: list[str]) -> unittest.result.TestResult:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in names:
        suite.addTests(loader.loadTestsFromName(name))
    return unittest.TextTestRunner(verbosity=2).run(suite)


PADDED = "test_t1891_freshness_parser.PaddedStampTests." \
    "test_a_padded_stamp_reads_as_aged_beyond_the_window"
CLEAN = "test_t1891_freshness_parser.PaddedStampTests." \
    "test_the_same_receipt_with_a_clean_stamp_keeps_its_verdict"
SAME = "test_t1891_freshness_parser.PaddedStampTests." \
    "test_padding_no_longer_changes_the_classification"


def main() -> int:
    isolate_host_session()

    print("=" * 70)
    print("1. CURRENT TREE -- the three assertions must pass")
    print("=" * 70)
    current = run([PADDED, CLEAN, SAME])
    current_green = current.wasSuccessful()

    original = C.conformance_status
    C.conformance_status = prefix_status
    # The module imports the function by module reference, so patching the
    # module attribute is what its fixtures actually call.
    try:
        print()
        print("=" * 70)
        print("2. PRE-FIX freshness arithmetic -- the padded test must FAIL")
        print("=" * 70)
        prefix = run([PADDED, CLEAN, SAME])
        prefix_green = prefix.wasSuccessful()
        print()
        print("=" * 70)
        print("3. CLEAN-STAMP CONTROL -- must still pass pre-fix")
        print("=" * 70)
        clean_only = run([CLEAN])
    finally:
        C.conformance_status = original

    print()
    print("=" * 70)
    print("VERDICT")
    print("=" * 70)
    print(f"current tree green         : {current_green}")
    print(f"pre-fix tree green         : {prefix_green}")
    print(f"pre-fix clean-stamp green  : {clean_only.wasSuccessful()}")
    ok = current_green and not prefix_green and clean_only.wasSuccessful()
    print()
    if ok:
        print("CONTROL OK -- the age arithmetic is the fix, not the harness.")
        return 0
    print("CONTROL INVALID -- the assertions do not discriminate the two trees.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
