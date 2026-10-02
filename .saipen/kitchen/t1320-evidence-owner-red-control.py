"""Run the unchanged ownership regression against the former literal owner."""

import sys
import unittest
from pathlib import Path
from unittest import mock

tools = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(tools))

import test_opencode_host_smoke as smoke  # noqa: E402


def former_owner(_build_id, *, evidence_root=None, run_id=None):
    del run_id
    return smoke.EvidenceRun(
        "opencode-native-smoke", "T-1317",
        durable_dir=Path(evidence_root) / "T-1317-opencode-native-smoke",
    )


case = smoke.OpenCodeSmokeEvidenceOwnership(
    "test_later_ticket_smoke_preserves_earlier_durable_proof"
)
with mock.patch.object(smoke, "new_smoke_evidence_run", former_owner):
    result = unittest.TextTestRunner(verbosity=2).run(case)

if result.testsRun != 1 or len(result.failures) != 1 or result.errors:
    raise SystemExit("red control failed to detect the former evidence owner")
print("EXPECTED_RED: former literal T-1317 owner rejected by unchanged test")
