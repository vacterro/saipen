"""T-148: a non-CONFIRMED sweep disposal must not be bound to the CURRENT install.

RED CONTROL. `write_sweep_entry` called `validate_bound_report(..., cycle_active=True)`
for every disposition, so the bound bar compared the HISTORICAL report's
`saipen_version`/`protocol_fingerprint` against the install running today. IMPROVE.md
sec7 step 2 makes a non-CONFIRMED disposal the only route out of a seat whose report
was written by an older generation -- so that route was unreachable: the cycle could
never be closed. Confirmed against live install 8.0.2 where a stale report's sweep was
refused with "report saipen_version '8.0.1' != installed SAIPEN version '8.0.2'".

The fix narrows the INSTALLED-truth comparison to CONFIRMED, the only disposition
that claims current authority. These tests pin BOTH halves: the historical disposal
opens, and the two guarantees the bar was built for stay closed -- a malformed
report still cannot authorize any disposition (T-638, zero sweep writes), and
CONFIRMED on stale evidence still refuses (T-619).
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = str(Path(__file__).resolve().parent)
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import improve  # noqa: E402

ROSTER = """# IMPROVE CYCLE ROSTER

manifest_schema: strict
cycle_id: cyc
created_at: 2026-09-30T11:53:50Z
project_identity: p
cycle_status: active

## SEAT s1

seat_id: s1
role: core
report_path: r.md
availability: expected
"""


def report_text(version, fingerprint, imp="IMP-001"):
    return (
        "agent: s1\n"
        "role: core\n"
        "model_or_runtime: unknown\n"
        "project: p\n"
        f"saipen_version: {version}\n"
        f"protocol_fingerprint: {fingerprint}\n"
        "source_head: f94744501205ff00e0773a14e23c2f0231c65b31\n"
        "source_tree_fingerprint: git-delta-v1:aaaa\n"
        "discovery_model: git-delta-v1\n"
        "context_scope: SAIPEN audit, phase DONE\n"
        "context_available: partial\n"
        "report_status: complete\n"
        "\n"
        "## RUN 1\n"
        f"\n{imp} [P2] [OTHER] [observed] [note] a finding\n"
        "  expected: e\n"
        "  actual: a\n"
        "  evidence: v\n"
    )


class T148HistoricalDisposalBar(unittest.TestCase):
    """The sweep writer must bind installed truth to CONFIRMED only."""

    CURRENT_VERSION = improve._saipen_install_version()
    CURRENT_FINGERPRINT = improve.installed_protocol_fingerprint(
        improve._protocol_root_for()
    )
    STALE_VERSION = "8.0.1"
    STALE_FINGERPRINT = "sha256:deadbeef"

    def _sweep(self, disposition, *, version=None, fingerprint=None, imp="IMP-001"):
        """Run write_sweep_entry over a throwaway strict cycle; return None on accept."""
        version = version or self.CURRENT_VERSION
        fingerprint = fingerprint or self.CURRENT_FINGERPRINT
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "proj"
            cycle = project / ".saipen" / "improve" / "cyc"
            (cycle / "s1").mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            (cycle / "MANIFEST.md").write_text(ROSTER, encoding="utf-8")
            (cycle / "SWEEP.md").write_text("# SWEEP\n", encoding="utf-8")
            (cycle / "s1" / "r.md").write_text(
                report_text(version, fingerprint, imp), encoding="utf-8"
            )
            try:
                improve.write_sweep_entry(
                    cycle,
                    {
                        "disposition": disposition,
                        "report": "s1/r.md",
                        "run": "RUN-1",
                        "imp_id": "IMP-001",
                        "reproduced": "n",
                        "fixed_by": "-",
                        "verification": "cyc/s2/r.md#RUN-1/IMP-001",
                    },
                )
            except improve.ImproveError as exc:
                return str(exc)
            return None

    def test_stale_report_allows_a_historical_not_reproduced_disposal(self):
        """The defect: IMPROVE.md sec7 step 2 was unreachable on stale evidence."""
        self.assertIsNone(
            self._sweep(
                "NOT_REPRODUCED",
                version=self.STALE_VERSION,
                fingerprint=self.STALE_FINGERPRINT,
            ),
            "a non-CONFIRMED disposal of a prior-generation report must be writable",
        )

    def test_stale_report_allows_a_superseded_disposal(self):
        self.assertIsNone(
            self._sweep(
                "SUPERSEDED",
                version=self.STALE_VERSION,
                fingerprint=self.STALE_FINGERPRINT,
            )
        )

    def test_malformed_report_authorizes_no_disposition(self):
        """T-638 stays closed: structural validity is NOT relaxed by T-148."""
        for disposition in ("NOT_REPRODUCED", "SUPERSEDED", "INVALID", "DUPLICATE"):
            with self.subTest(disposition=disposition):
                error = self._sweep(disposition, imp="IMP-1")
                self.assertIsNotNone(error)
                self.assertIn("bound bar", error)

    def test_confirmed_on_stale_evidence_still_refuses(self):
        """T-619 stays closed: only CONFIRMED needs, and gets, the freshness gate."""
        self.assertIsNotNone(self._sweep("CONFIRMED"))

    def test_current_evidence_disposal_is_unaffected(self):
        self.assertIsNone(self._sweep("NOT_REPRODUCED"))


if __name__ == "__main__":
    unittest.main()