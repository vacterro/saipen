"""T-1332 / T-1333: the reverify timeout and the improve-report route.

Both were measured on FastPrompter 27.09.26, from improve cycle
imp-vacterro-fastprompter-20260927-2 RUN-1/IMP-002 and IMP-001.

T-1332: `work reverify --run "python -m pytest tests/ -q"` is the remediation
the gate itself prints, and on this project the strict gate takes 604 s. The
default budget for a verification command was 300 s -- smaller than the
VALIDATOR_CAPTURE_TIMEOUT the same operation already spends capturing the
strict gate -- so the prescribed command recorded an honest `timed_out` FAIL
and the identical command with `--timeout 900` recorded exit_code 0. The
truncation appeared in neither the refusal nor the remediation string.

T-1333: a stale improve DRAFT report is a blocking conformance finding, and
the closed remediation table already registers `saipen improve reconcile
<cycle>` for it. Extraction reads the failure TEXT, and the validator's
failure only described the report, so the receipt carried no route at all:
the receipt's remediation_commands named two unrelated reverify tickets and
the operator had to derive `improve abort` by hand.

Run standalone:
    python -m unittest tools.test_reverify_timeout_and_route
"""

from __future__ import annotations

import inspect
import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _entry in (str(TOOLS), str(ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

import saipen  # noqa: E402
from saipen_engine import debt, remediation  # noqa: E402
from test_t1412_conformance_truth import T1412Base  # noqa: E402

CYCLE = "imp-fixture-20260927-1"

_MANIFEST = f"""# IMPROVE CYCLE ROSTER

manifest_schema: strict
cycle_id: {CYCLE}
created_at: 2026-09-27T03:05:56Z
project_identity: fixture
cycle_status: active
seat_id: buffy-01
role: core
report_path: saipen_improve_FIXTURE.md
availability: expected
"""

#: A DRAFT seat report whose protocol_fingerprint no longer matches the
#: installed engine -- exactly the shape that produced the red gate.
_STALE_DRAFT = """agent: buffy-01
role: core
model_or_runtime: unknown
project: fixture
saipen_version: 8.0.1
protocol_fingerprint: sha256:{"0" * 64}
source_head: 0000000000000000000000000000000000000000
source_tree_fingerprint: git-delta-v1:{"0" * 64}
discovery_model: git-delta-v1
context_scope: SAIPEN audit, phase DONE
context_available: partial
report_status: draft
"""


class VerifyTimeoutTests(unittest.TestCase):
    """T-1332: one budget, large enough for the gate the operation already runs."""

    def test_engine_default_is_the_capture_budget(self) -> None:
        default = inspect.signature(debt.reverify_work).parameters["timeout"].default
        self.assertEqual(default, debt.VALIDATOR_CAPTURE_TIMEOUT)
        self.assertGreater(default, 300, "the budget must exceed the 300 s defect")

    def test_cli_default_is_the_same_budget(self) -> None:
        self.assertEqual(saipen._reverify_default_timeout(), debt.VALIDATOR_CAPTURE_TIMEOUT)

    def test_a_timed_out_check_records_its_budget(self) -> None:
        entry = debt._run_verification_command(ROOT, "ping -n 3 127.0.0.1 -w 5000", 1)
        self.assertEqual(entry["result"], "FAIL")
        self.assertTrue(entry["timed_out"])
        # T-1332: an honest FAIL that does not say it was truncated sends the
        # operator to re-run the identical command forever.
        self.assertEqual(entry["timeout_seconds"], 1)


class ImproveReportRouteTests(T1412Base):
    """T-1333: the blocking finding names the door."""

    def _project_with_stale_draft(self, name: str) -> Path:
        root = self.make_project(name)
        cycle = root / ".saipen" / "improve" / CYCLE
        (cycle / "buffy-01").mkdir(parents=True)
        (cycle / "MANIFEST.md").write_text(_MANIFEST, encoding="utf-8")
        (cycle / "buffy-01" / "saipen_improve_FIXTURE.md").write_text(
            _STALE_DRAFT, encoding="utf-8"
        )
        return root

    def test_a_stale_draft_finding_yields_a_concrete_reconcile_route(self) -> None:
        root = self._project_with_stale_draft("improve-route")
        rc, payload, text = self.run_cli(root, "validate", timeout=900)
        status = payload.get("conformance_status") or {}
        receipt = status.get("receipt") or {}
        commands = receipt.get("remediation_commands") or []
        self.assertTrue(
            any(cmd == f"saipen improve reconcile {CYCLE}" for cmd in commands),
            f"no improve reconcile route in {commands} (rc={rc})\n{text[:2000]}",
        )
        # and the decision a consumer reads names the same route first
        self.assertEqual(
            payload.get("canonical_next_command"), f"saipen improve reconcile {CYCLE}"
        )
        self.assertTrue(
            any(
                "improve report" in str(pr.get("detail"))
                for pr in ((receipt.get("blocking_findings") or {}).get("problems") or [])
            ),
            "the stale draft itself must still be reported as a finding",
        )

    def test_the_closed_table_accepts_the_named_route(self) -> None:
        """The extractor is the only door, so the shape must be registered."""
        extracted = remediation.extract_commands(
            [f"improve report [improve-report] -- stale; run saipen improve reconcile {CYCLE}"]
        )
        self.assertIn(f"saipen improve reconcile {CYCLE}", extracted)


if __name__ == "__main__":
    unittest.main()
