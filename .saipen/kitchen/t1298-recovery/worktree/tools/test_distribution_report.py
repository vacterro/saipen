"""Distribution freshness regressions (T-1271).

Every installed home already carried a stamp naming the source head it was
built from, and the scheduled runner already logged why a run published
nothing. Neither was readable from the project: `saipen status` said nothing
about injection, so "does an installed agent home run current SAIPEN" could be
answered only by opening a log under LOCALAPPDATA. Measured when the ticket
was written: all four homes held 7.241.1 while HEAD was two releases ahead,
and every scheduled run since 18:31 had skipped with SKIP DIRTY_SOURCE.

The guard that stalls distribution on a dirty source is correct. The defect was
that one uncommitted edit could stall it indefinitely and only a log file knew.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import autoinject as A  # noqa: E402

HEAD = "a" * 40
OLD = "b" * 40

RUN = "=== saipen scheduled inject run=deadbeef ==="


class DistributionFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-distribution-")
        self.base = Path(self.tmp.name)
        self.appdata = self.base / "appdata"
        (self.appdata / "saipen").mkdir(parents=True)
        self.env = patch.dict(os.environ, {"LOCALAPPDATA": str(self.appdata)})
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    # helpers -------------------------------------------------------------

    def home(self, name: str, head: str | None, at: str = "2026-09-03T00:00:00Z") -> Path:
        target = self.base / name / "skills" / "saipen"
        target.mkdir(parents=True, exist_ok=True)
        record: dict = {"digest": "d" * 16}
        if head:
            record["source_head"] = head
        if at:
            record["installed_at"] = at
        (target / A.STAMP).write_text(json.dumps(record), encoding="utf-8")
        return target

    def absent(self, name: str) -> Path:
        return self.base / name / "skills" / "saipen"

    def log(self, *lines: str) -> Path:
        path = self.appdata / "saipen" / "inject.log"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def report(self, targets: list[Path], head: str | None = HEAD) -> dict:
        with patch.object(A, "TARGETS", targets):
            return A.distribution_report(source_head=head)

    def tree(self) -> dict[str, str]:
        out = {}
        for path in sorted(self.base.rglob("*")):
            if path.is_file():
                out[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        return out


# ---------------------------------------------------------------------------
# AC-01 -- how many homes are stale, and the newest head they carry
# ---------------------------------------------------------------------------


class StaleCountTests(DistributionFixture):
    def test_a_stale_home_is_counted_and_named(self) -> None:
        targets = [self.home(".claude", OLD), self.home(".codex", HEAD)]
        report = self.report(targets)
        self.assertEqual(report["installed"], 2)
        self.assertEqual(report["stale"], 1)
        self.assertEqual(report["stale_homes"], [".claude"])

    def test_the_newest_installed_head_is_the_most_recently_stamped(self) -> None:
        targets = [
            self.home(".claude", OLD, at="2026-09-01T00:00:00Z"),
            self.home(".codex", HEAD, at="2026-09-03T00:00:00Z"),
        ]
        self.assertEqual(self.report(targets)["newest_installed_head"], HEAD)

    def test_all_stale_still_reports_the_newest_head_they_carry(self) -> None:
        targets = [
            self.home(".claude", OLD, at="2026-09-01T00:00:00Z"),
            self.home(".codex", OLD, at="2026-09-02T00:00:00Z"),
        ]
        report = self.report(targets)
        self.assertEqual(report["stale"], 2)
        self.assertEqual(report["newest_installed_head"], OLD)
        self.assertNotEqual(report["newest_installed_head"], report["source_head"])

    def test_an_absent_home_is_not_stale_it_is_simply_not_installed(self) -> None:
        targets = [self.home(".claude", HEAD), self.absent(".codex")]
        report = self.report(targets)
        self.assertEqual(report["installed"], 1)
        self.assertEqual(report["stale"], 0)

    def test_a_home_with_no_head_is_unknown_and_never_counted_fresh(self) -> None:
        # A copy that cannot say what it was built from is the case the stamp
        # exists to expose; counting it current would hide exactly that.
        report = self.report([self.home(".claude", None)])
        self.assertEqual(report["unknown"], 1)
        self.assertEqual(report["stale"], 1)
        self.assertFalse(report["fresh"])

    def test_the_summary_names_both_numbers(self) -> None:
        targets = [self.home(".claude", OLD), self.home(".codex", HEAD)]
        line = A.distribution_line(self.report(targets))
        self.assertIn("1 of 2 home(s) stale", line)
        self.assertIn(HEAD[:12], line)


# ---------------------------------------------------------------------------
# AC-02 -- a blocked injection names the blocking condition
# ---------------------------------------------------------------------------


class BlockedInjectionTests(DistributionFixture):
    def test_a_skipped_run_names_its_reason_and_the_dirty_paths(self) -> None:
        self.log(
            f"2026-09-03 09:46:00 {RUN}",
            "2026-09-03 09:46:00 dirty:  M saipen/CORE.md",
            "2026-09-03 09:46:00 dirty:  M tools/saipen.py",
            "2026-09-03 09:46:00 SKIP: DIRTY_SOURCE",
            "2026-09-03 09:46:00 === end rc=2 ===",
        )
        report = self.report([self.home(".claude", OLD)])
        self.assertEqual(report["blocked"], "DIRTY_SOURCE")
        self.assertEqual(report["blocking_paths"], ["M saipen/CORE.md", "M tools/saipen.py"])
        self.assertIn("injection blocked: DIRTY_SOURCE", A.distribution_line(report))
        self.assertIn("M saipen/CORE.md", A.distribution_line(report))

    def test_a_nonzero_run_with_no_skip_line_still_reports_blocked(self) -> None:
        self.log(f"2026-09-03 09:46:00 {RUN}", "2026-09-03 09:46:00 === end rc=9 ===")
        self.assertEqual(self.report([self.home(".claude", OLD)])["blocked"], "rc=9")

    def test_a_successful_run_is_not_blocked(self) -> None:
        self.log(
            f"2026-09-03 12:46:00 {RUN}",
            f"2026-09-03 12:46:12 inject: head={HEAD} exit=0",
            "2026-09-03 12:46:12 === end rc=0 ===",
        )
        report = self.report([self.home(".claude", HEAD)])
        self.assertIsNone(report["blocked"])
        self.assertTrue(report["fresh"])

    def test_only_the_newest_run_decides(self) -> None:
        self.log(
            f"2026-09-03 09:00:00 {RUN}",
            "2026-09-03 09:00:00 SKIP: DIRTY_SOURCE",
            "2026-09-03 09:00:00 === end rc=2 ===",
            f"2026-09-03 12:00:00 {RUN}",
            "2026-09-03 12:00:00 === end rc=0 ===",
        )
        self.assertIsNone(self.report([self.home(".claude", HEAD)])["blocked"])

    def test_a_run_still_in_flight_is_unknown_not_a_success(self) -> None:
        self.log(f"2026-09-03 12:00:00 {RUN}", "2026-09-03 12:00:00 inject: working")
        run = A.last_inject_run()
        self.assertIsNotNone(run)
        self.assertIsNone(run["rc"])

    def test_no_scheduler_log_is_a_normal_answer(self) -> None:
        self.assertIsNone(A.scheduler_log())
        self.assertIsNone(A.last_inject_run())
        report = self.report([self.home(".claude", HEAD)])
        self.assertIsNone(report["blocked"])
        self.assertTrue(report["fresh"])

    def test_a_blocked_run_makes_a_current_looking_set_not_fresh(self) -> None:
        # Homes can read current while publication is stalled: the stall is
        # about what happens NEXT, and reporting fresh would hide it.
        self.log(
            f"2026-09-03 09:46:00 {RUN}",
            "2026-09-03 09:46:00 SKIP: DIRTY_SOURCE",
            "2026-09-03 09:46:00 === end rc=2 ===",
        )
        report = self.report([self.home(".claude", HEAD)])
        self.assertEqual(report["stale"], 0)
        self.assertFalse(report["fresh"])
        self.assertIn("DIRTY_SOURCE", A.distribution_line(report))


# ---------------------------------------------------------------------------
# AC-03 -- it reads, and stores nothing
# ---------------------------------------------------------------------------


class ReadOnlyTests(DistributionFixture):
    def test_the_report_writes_nothing(self) -> None:
        targets = [self.home(".claude", OLD), self.home(".codex", HEAD)]
        self.log(f"2026-09-03 09:46:00 {RUN}", "2026-09-03 09:46:00 === end rc=0 ===")
        before = self.tree()
        report = self.report(targets)
        A.distribution_line(report)
        self.assertEqual(before, self.tree())

    def test_it_never_creates_an_absent_home(self) -> None:
        target = self.absent(".codex")
        self.report([self.home(".claude", HEAD), target])
        self.assertFalse(target.exists())

    def test_it_never_writes_a_stamp_into_an_unstamped_home(self) -> None:
        target = self.base / ".codex" / "skills" / "saipen"
        target.mkdir(parents=True)
        report = self.report([target])
        self.assertEqual(report["unknown"], 1)
        self.assertFalse((target / A.STAMP).exists())


# ---------------------------------------------------------------------------
# AC-04 -- a current set answers, it does not go quiet
# ---------------------------------------------------------------------------


class FreshIsAnAnswerTests(DistributionFixture):
    def test_a_fully_current_set_reports_fresh_with_a_sentence(self) -> None:
        targets = [self.home(".claude", HEAD), self.home(".codex", HEAD)]
        report = self.report(targets)
        self.assertTrue(report["fresh"])
        line = A.distribution_line(report)
        self.assertTrue(line.strip())
        self.assertIn("2 home(s) current", line)
        self.assertIn(HEAD[:12], line)

    def test_no_installed_home_says_so_rather_than_printing_nothing(self) -> None:
        report = self.report([self.absent(".claude")])
        self.assertEqual(report["installed"], 0)
        self.assertFalse(report["fresh"])
        self.assertIn("no installed agent home", A.distribution_line(report))

    def test_fresh_and_stale_produce_different_sentences(self) -> None:
        fresh = A.distribution_line(self.report([self.home(".claude", HEAD)]))
        stale = A.distribution_line(self.report([self.home(".codex", OLD)]))
        self.assertNotEqual(fresh, stale)
        self.assertIn("current", fresh)
        self.assertIn("stale", stale)


if __name__ == "__main__":
    unittest.main()
