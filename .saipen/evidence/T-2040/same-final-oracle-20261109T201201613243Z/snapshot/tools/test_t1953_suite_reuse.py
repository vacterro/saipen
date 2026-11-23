"""T-1953: reuse a suite record only when it still answers for this tree.

Measured on 2026-10-29 in the consumer project: 273 suite records, and on
twenty distinct tree identities the suite had been re-run 3..66 times each.
One subject (`86bb24cf8c38`) was executed 66 times for 4211 s where one run of
123.7 s answered every one of them; across the whole history the redundant
execution is 19 542 s. The skipping was not a missing feature -- `current_record`
already decided whether a record describes the tree in front of it -- but
`run` never asked, so every closure re-executed a suite whose answer was
already immutable in `.saipen/evidence/suite/`.

The repair adds one opt-in word (`--reuse`) rather than a second framework: the
engine keeps the eligibility decision, the caller can only ask. These tests pin
the four ways a record may NOT be reused, each of which would otherwise turn a
reuse into a false PASS.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_t1614_future_gate as H  # noqa: E402
from saipen_engine import suite_record as SR  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

MEASURED = "12 passed in 0.40s"


def setUpModule() -> None:
    isolate_host_session()


def _git(project: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=project, stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=120,
    )


class _Project(unittest.TestCase):
    """A git project with a declared suite that records what it was asked."""

    def setUp(self) -> None:
        base, self.project = H._project()
        self.addCleanup(shutil.rmtree, base, True)
        # The counter lives OUTSIDE the project on purpose. A suite that wrote
        # into the tree it is testing would move the subject while it ran, and
        # `tree_changed_during_run` would (rightly) withhold reuse for a reason
        # these tests are not about.
        self.marker = base / "suite-runs.txt"
        self.script(exit_code=0, summary=MEASURED)
        _git(self.project, "init", "-q")
        _git(self.project, "add", "-A")
        _git(self.project, "commit", "-q", "-m", "fixture")
        SR.declare(self.project, [sys.executable, "-B", "suite.py"])

    def script(self, *, exit_code: int, summary: str) -> None:
        """A suite that counts its own executions, so reuse is observable."""
        (self.project / "suite.py").write_text(
            "import pathlib, sys\n"
            f"log = pathlib.Path({str(self.marker)!r})\n"
            "log.write_text((log.read_text() if log.exists() else '') + 'run\\n')\n"
            f"print({('=' * 12 + ' ' + summary + ' ' + '=' * 12)!r}, file=sys.stdout)\n"
            f"sys.exit({exit_code})\n",
            encoding="utf-8",
        )

    def executions(self) -> int:
        if not self.marker.exists():
            return 0
        return len(self.marker.read_text(encoding="utf-8").splitlines())

    def run_cli(self, *words: str) -> dict:
        payload, _code = SR.cli(self.project, ["run", "T-1", *words], agent="tester")
        return payload

    def seed(self) -> dict:
        """One real run, so a record of the current tree exists."""
        return SR.write_record(self.project, SR.run(self.project))


class ReuseEligibilityTests(_Project):
    def test_a_current_pass_record_is_reused_without_executing(self):
        self.seed()
        before = self.executions()

        payload = self.run_cli("--reuse")

        self.assertEqual(payload["code"], "SUITE_REUSED")
        self.assertFalse(payload["executed"])
        self.assertEqual(self.executions(), before, "the suite must not have run again")
        self.assertEqual(payload["verdict"], "PASS")

    def test_the_reuse_cites_the_record_instead_of_restating_a_pass(self):
        written = self.seed()
        payload = self.run_cli("--reuse")

        self.assertEqual(payload["record"], written["path"])
        self.assertEqual(payload["sha256"], written["sha256"])

    def test_reuse_is_opt_in_so_the_default_always_executes(self):
        self.seed()
        before = self.executions()

        payload = self.run_cli()

        self.assertEqual(payload["code"], "SUITE_RECORDED")
        self.assertTrue(payload["executed"])
        self.assertEqual(self.executions(), before + 1)

    def test_a_fail_record_is_never_reused_as_a_pass(self):
        self.script(exit_code=1, summary="1 failed, 11 passed in 0.40s")
        self.seed()
        before = self.executions()

        payload = self.run_cli("--reuse")

        self.assertEqual(payload["code"], "SUITE_RECORDED")
        self.assertTrue(payload["executed"], "a red tree is re-measured, not reused")
        self.assertEqual(payload["verdict"], "FAIL")
        self.assertIn("not PASS", payload["reuse_withheld"])
        self.assertEqual(self.executions(), before + 1)

    def test_changed_bytes_withhold_reuse(self):
        self.seed()
        (self.project / "suite.py").write_text(
            (self.project / "suite.py").read_text(encoding="utf-8") + "\n# moved\n",
            encoding="utf-8",
        )
        before = self.executions()

        payload = self.run_cli("--reuse")

        self.assertEqual(payload["code"], "SUITE_RECORDED")
        self.assertTrue(payload["executed"])
        self.assertIn("describes the current tree", payload["reuse_withheld"])
        self.assertEqual(self.executions(), before + 1)

    def test_a_record_that_counted_no_test_proves_nothing(self):
        written = self.seed()
        path = self.project / written["path"]
        record = json.loads(path.read_text(encoding="utf-8"))
        record["totals"] = {"runner": "pytest", "ran": 0, "passed": 0, "red": 0, "skipped": 0}
        path.write_text(json.dumps(record), encoding="utf-8")

        found, reason = SR.reusable_record(self.project)

        self.assertIsNone(found)
        self.assertIn("counts no test", reason)

    def test_a_record_of_a_moved_tree_is_withheld(self):
        written = self.seed()
        path = self.project / written["path"]
        record = json.loads(path.read_text(encoding="utf-8"))
        record["tree_changed_during_run"] = True
        path.write_text(json.dumps(record), encoding="utf-8")

        found, reason = SR.reusable_record(self.project)

        self.assertIsNone(found)
        self.assertIn("changed while that record", reason)


class ReuseEvidenceTests(unittest.TestCase):
    def test_the_log_line_marks_itself_as_a_reuse_and_still_parses(self):
        line = SR.reuse_line(
            {
                "record": {
                    "verdict": "PASS",
                    "status": "PASS",
                    "totals": {"runner": "unittest", "ran": 12, "red": 0, "skipped": 0},
                    "exit_code": 0,
                    "command_sha256": "a" * 64,
                },
                "path": ".saipen/evidence/suite/x.json",
                "sha256": "b" * 64,
            }
        )
        parsed = SR.parse_evidence(line)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["verdict"], "PASS")
        self.assertEqual(parsed["reused"], "-REUSED", "a reuse must be legible as one")
        self.assertEqual(parsed["sha"], "b" * 64)

    def test_a_real_run_line_is_not_marked_as_reused(self):
        line = SR.evidence_line(
            {
                "record": {
                    "verdict": "PASS",
                    "totals": {"runner": "unittest", "ran": 3, "red": 0, "skipped": 0},
                    "exit_code": 0,
                    "command_sha256": "a" * 64,
                },
                "path": ".saipen/evidence/suite/y.json",
                "sha256": "c" * 64,
            }
        )
        self.assertIsNone(SR.parse_evidence(line)["reused"])


class GitPathCanonicalityTests(unittest.TestCase):
    """An untracked directory's trailing slash is a real entry, not a defect.

    Measured in the consumer project: `git ls-files -o` emits
    `contributions/.tooling/upstream-parser/` for a nested repository it does
    not enter. Rejecting that spelling raised FreshnessError, and the raise
    propagated out of `compute_source_identity` for the whole tree -- one
    nested untracked directory disabled every caller that needs an identity.
    The bounds that stop a path escaping the root must survive unchanged.
    """

    def test_a_directory_entry_is_accepted_and_the_slash_is_dropped(self):
        import tempfile

        import freshness

        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve()
            (root / "nested" / "sub").mkdir(parents=True)
            self.assertEqual(
                freshness._path_from_git(root, b"nested/"), root / "nested"
            )
            self.assertEqual(
                freshness._path_from_git(root, b"nested/sub/"), root / "nested" / "sub"
            )
            self.assertEqual(freshness._path_from_git(root, b"a.py"), root / "a.py")

    def test_the_bounds_that_stop_escape_still_hold(self):
        import tempfile

        import freshness

        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve()
            for raw in (b"../x", b"./x", b"a/../b", b"/x", b"", b"a\0b"):
                with self.subTest(raw=raw), self.assertRaises(freshness.FreshnessError):
                    freshness._path_from_git(root, raw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
