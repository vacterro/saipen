"""T-38: `continue --json` names the assigned cycle's liveness.

Measured live on this repository (vacterro-saiwebsite, 2026-10-14): the
fallthrough answered `CONTINUE_IDLE_SOURCE_UNCHANGED` and named the marker's
cycle id, while `imp-vacterro-saiwebsite-20261007-1` -- archived with
`cycle_aborted: draft-preserved`, its seat report a seven-day-old header-only
draft with no RUN block -- was invisible in the payload. Days of unfinished
audit work read as a clean idle verdict.

The answer now carries `improve_cycle` on every outcome this branch emits:
status, report_status, run count, age in days, the `stale` verdict and the
exact submit route. Read-only: an unknown cycle leaves the payload unchanged.

Implementation: `saipen_engine.continue_fallback.cycle_liveness` +
`with_cycle_liveness`, wired into the CLI's `_emit_result`.

Run standalone:
    python tools/test_t38_improve_cycle_liveness.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import continue_fallback as cf  # noqa: E402

#: Resolved by name so the same file is a red control on the unpatched engine
#: (the symbol is absent there) instead of failing to import the module.
cycle_liveness = getattr(cf, "cycle_liveness", None)
with_cycle_liveness = getattr(cf, "with_cycle_liveness", None)

CYCLE = "imp-vacterro-saiwebsite-20261007-1"
SEAT = "saipen-01"
REPORT = "saipen_improve_SAIPEN.md"
PROJECT = "vacterro-saiwebsite"

MANIFEST = """# IMPROVE CYCLE ROSTER

manifest_schema: strict
cycle_id: {cycle}
created_at: {created}
project_identity: {project}
cycle_status: archived
seat_id: {seat}
role: core
report_path: {report}
availability: expected
cycle_aborted: draft-preserved
"""

DRAFT_REPORT = """agent: {seat}
role: core
model_or_runtime: unknown
project: {project}
saipen_version: 8.1.0
protocol_fingerprint: sha256:78a5433deacc5aab4ab7a3ac767cc79481e9699e5567cea76ec28fbea3b5c3f8
source_head: cbded0519deab0d1ffbf51c7ce38c6817382ecc3
source_tree_fingerprint: {tree}
discovery_model: git-delta-v1
context_scope: SAIPEN audit, phase DONE
context_available: partial
report_status: draft
""".replace(
    "{tree}",
    "git-delta-v1:45369bcac4c52c56015fe376444b70c432805f7c26aa464c66f8ec6e7e69fd8c",
)

COMPLETE_REPORT = (
    DRAFT_REPORT.replace("report_status: draft", "report_status: complete")
    + "\n## RUN 1\nIMP-001 the audit was submitted\n"
)

ASSIGNED = "imp-vacterro-saiwebsite-20261013-1"


def _iso(days_ago: int) -> str:
    moment = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _cycle(
    root: Path,
    cycle: str = CYCLE,
    *,
    days_ago: int | None = 7,
    status: str = "archived",
    report: str | None = DRAFT_REPORT,
) -> Path:
    """A cycle directory shaped like the measured one."""
    manifest = root / ".saipen" / "improve" / cycle / "MANIFEST.md"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        MANIFEST.format(
            cycle=cycle,
            created=_iso(days_ago) if days_ago is not None else "2026-10-07T20:44:02Z",
            project=PROJECT,
            seat=SEAT,
            report=REPORT,
        ).replace("cycle_status: archived", f"cycle_status: {status}"),
        encoding="utf-8",
    )
    if report is not None:
        seat_dir = manifest.parent / SEAT
        seat_dir.mkdir(parents=True, exist_ok=True)
        (seat_dir / REPORT).write_text(report.format(seat=SEAT, project=PROJECT), encoding="utf-8")
    return root


class _NeedsThePatch(unittest.TestCase):
    def setUp(self) -> None:
        if cycle_liveness is None or with_cycle_liveness is None:
            self.fail("saipen_engine.continue_fallback exposes no cycle liveness")


class CycleLiveness(_NeedsThePatch):
    def test_archived_empty_draft_is_preserved_without_pending_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _cycle(Path(tmp))
            live = cycle_liveness(root, CYCLE)
            assert live is not None
            self.assertEqual(live["cycle_id"], CYCLE)
            self.assertEqual(live["status"], "archived")
            self.assertEqual(live["report_status"], "draft")
            self.assertTrue(live["has_report"])
            self.assertEqual(live["runs"], 0)
            self.assertTrue(live["draft"])
            self.assertTrue(live["no_run"])
            self.assertGreaterEqual(live["age_days"], 6)
            self.assertFalse(live["stale"])
            self.assertEqual(live["pending_findings"], [])
            self.assertEqual(live["submit_route"], "")

    def test_a_complete_report_with_a_run_block_is_not_stale(self) -> None:
        report = DRAFT_REPORT.replace("report_status: draft", "report_status: complete")
        report += "\n## RUN 1\nNO_FINDINGS\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = _cycle(Path(tmp), days_ago=30, status="complete", report=report)
            live = cycle_liveness(root, CYCLE)
            assert live is not None
            self.assertEqual(live["runs"], 1)
            self.assertFalse(live["draft"])
            self.assertFalse(live["no_run"])
            self.assertFalse(live["stale"])
            self.assertEqual(live["submit_route"], "")

    def test_a_young_draft_is_reported_but_not_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _cycle(Path(tmp), days_ago=1, status="active")
            live = cycle_liveness(root, CYCLE)
            assert live is not None
            self.assertEqual(live["age_days"], 1)
            self.assertTrue(live["draft"])
            self.assertFalse(live["stale"])

    def test_an_unfinished_report_on_a_cycle_that_left_flight_is_stale(self) -> None:
        """Stale by state: an archived draft cannot resume on its own."""
        with tempfile.TemporaryDirectory() as tmp:
            pending = DRAFT_REPORT + (
                "\n## RUN 1\nIMP-001 [P2] [OTHER] [observed] [note]\n"
                "expected: synthetic archived finding remains visible\n"
                "actual: no historical disposition exists\n"
                "evidence: T-38 disposable liveness control\n"
            )
            root = _cycle(Path(tmp), days_ago=1, status="archived", report=pending)
            live = cycle_liveness(root, CYCLE)
            assert live is not None
            self.assertTrue(live["stale"])

    def test_an_unknown_cycle_says_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(cycle_liveness(Path(tmp), "imp-nowhere-1"))


class PayloadMerge(_NeedsThePatch):
    def _payload(self, cycle: str | None = CYCLE) -> dict:
        payload = {"ok": True, "code": "CONTINUE_IDLE_SOURCE_UNCHANGED"}
        if cycle is not None:
            payload["cycle_id"] = cycle
        return payload

    def test_the_answer_carries_the_assigned_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _cycle(Path(tmp))
            merged = with_cycle_liveness(self._payload(), root)
            self.assertFalse(merged["improve_cycle"]["stale"])
            self.assertEqual(merged["ok"], True)

    def test_the_marker_names_the_cycle_when_the_answer_does_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _cycle(Path(tmp))
            marker = root / cf.FALLBACK_MARKER_REL
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text('{"schema_version": 1, "cycle_id": "%s"}' % CYCLE, encoding="utf-8")
            merged = with_cycle_liveness(self._payload(cycle=None), root)
            self.assertEqual(merged["improve_cycle"]["cycle_id"], CYCLE)

    def test_an_unknown_cycle_leaves_the_answer_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = self._payload()
            self.assertEqual(with_cycle_liveness(payload, Path(tmp)), payload)

    def test_a_different_stale_cycle_rides_along(self) -> None:
        """The measured shape: the marker names a complete cycle, the work is elsewhere."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _cycle(
                Path(tmp), ASSIGNED, days_ago=0, status="complete", report=COMPLETE_REPORT
            )
            pending = DRAFT_REPORT + (
                "\n## RUN 1\nIMP-001 [P2] [OTHER] [observed] [note]\n"
                "expected: synthetic archived finding remains visible\n"
                "actual: no historical disposition exists\n"
                "evidence: T-38 disposable liveness control\n"
            )
            _cycle(root, CYCLE, days_ago=7, status="archived", report=pending)
            merged = with_cycle_liveness(self._payload(cycle=ASSIGNED), root)
            self.assertEqual(merged["improve_cycle"]["cycle_id"], ASSIGNED)
            self.assertFalse(merged["improve_cycle"]["stale"])
            stale = merged["improve_stale_cycles"]
            self.assertEqual(len(stale), 1)
            self.assertEqual(stale[0]["cycle_id"], CYCLE)
            self.assertGreaterEqual(stale[0]["age_days"], 6)
            self.assertFalse(stale[0]["no_run"])
            self.assertEqual(stale[0]["submit_route"], "")
            self.assertIn(f"saipen improve sweep-queue {CYCLE}", stale[0]["canonical_next_command"])

    def test_a_stale_cycle_is_visible_with_no_assigned_cycle_at_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pending = DRAFT_REPORT + (
                "\n## RUN 1\nIMP-001 [P2] [OTHER] [observed] [note]\n"
                "expected: synthetic archived finding remains visible\n"
                "actual: no historical disposition exists\n"
                "evidence: T-38 disposable liveness control\n"
            )
            root = _cycle(Path(tmp), report=pending)
            marker = root / cf.FALLBACK_MARKER_REL
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text('{"schema_version": 1}', encoding="utf-8")
            merged = with_cycle_liveness(self._payload(cycle=None), root)
            self.assertNotIn("improve_cycle", merged)
            self.assertEqual(merged["improve_stale_cycles"][0]["cycle_id"], CYCLE)


class CliWiring(unittest.TestCase):
    def test_the_continue_fallthrough_wires_the_liveness_in(self) -> None:
        text = (TOOLS / "saipen.py").read_text(encoding="utf-8")
        self.assertIn("from saipen_engine.continue_fallback import with_cycle_liveness", text)
        self.assertIn("payload = with_cycle_liveness(payload, project_root)", text)


if __name__ == "__main__":
    unittest.main()
