"""T-1511: field-soak evidence names the source it tested.

Every soak generation is a fresh agent process whose fixture points
`saipen_home` at this checkout, so it imports the engine from the working tree
as it is at that moment. Measured 2026-09-24: the T-1446 24H gate launched at
03:48Z against HEAD 86878249, `tools/saipen_engine/journal.py` became dirty at
10:11:32Z mid-run, and neither launch.json, interim.jsonl nor report.json could
say so -- the "source frozen" blockers on nineteen tickets rested on prose.

The regressions drive the REAL driver `main()` against a disposable Git source
fixture; only the agent host and the supervisor are replaced, and the fake
supervisor changes the source the way a concurrent actor does.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import t1446_field_soak as soak  # noqa: E402
from freshness import FreshnessError  # noqa: E402


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


class SoakSourceIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="saipen-t1511-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        self.source = base / "source"
        (self.source / "tools").mkdir(parents=True)
        (self.source / ".saipen").mkdir()
        (self.source / "tools" / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.source / ".saipen" / "LOG.md").write_text("- one\n", encoding="utf-8")
        _git(self.source, "init", "-q")
        _git(self.source, "config", "user.email", "t1511@example.invalid")
        _git(self.source, "config", "user.name", "t1511")
        _git(self.source, "config", "core.autocrlf", "false")
        _git(self.source, "add", "-A")
        _git(self.source, "commit", "-q", "-m", "fixture")
        self.head = _git(self.source, "rev-parse", "HEAD")
        self.project = base / "project"
        (self.project / ".saipen").mkdir(parents=True)
        (self.project / ".saipen" / "BOARD.md").write_text(
            "## DOING\n## TODO\n## DONE\n", encoding="utf-8"
        )
        self.out = base / "out"

    def drive(self, supervise, interim_every: float = 3600.0) -> dict:
        argv = ["t1446_field_soak.py", "--model", "m", "--wall-seconds", "5"]
        argv += ["--interim-every", str(interim_every), "--out", str(self.out)]
        for patcher in (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(soak, "OPENCODE", "opencode"),
            mock.patch.object(soak, "SOURCE_ROOT", self.source),
            mock.patch.object(soak, "build_project", return_value=self.project),
            mock.patch.object(soak.worker, "supervise", supervise),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.assertEqual(soak.main(), 0)
        return json.loads((self.out / "report.json").read_text(encoding="utf-8"))

    @staticmethod
    def quiet(*_args, **_kwargs) -> dict:
        return {"ok": True, "code": "SUPERVISE_STOPPED", "stop": "IDLE", "history": []}

    def test_a_quiet_run_binds_the_launch_source_and_reports_it_stable(self):
        report = self.drive(self.quiet)
        source = report["source"]
        self.assertEqual(source["integrity"], "STABLE")
        self.assertEqual(source["changed_paths"], [])
        self.assertEqual(source["at_launch"]["source_head"], self.head)
        self.assertTrue(source["at_launch"]["source_tree_fingerprint"].startswith("git-delta-v1:"))
        self.assertEqual(source["at_end"], source["at_launch"])
        written = json.loads((self.out / "source.json").read_text(encoding="utf-8"))
        self.assertEqual(written["at_launch"], source["at_launch"])

    def test_a_tracked_edit_during_the_run_is_drift_naming_the_path(self):
        def editing(*_args, **_kwargs):
            (self.source / "tools" / "engine.py").write_text("VALUE = 2\n", encoding="utf-8")
            return self.quiet()

        source = self.drive(editing)["source"]
        self.assertEqual(source["integrity"], "DRIFTED")
        self.assertEqual(source["changed_paths"], ["tools/engine.py"])
        self.assertNotEqual(
            source["at_end"]["source_tree_fingerprint"],
            source["at_launch"]["source_tree_fingerprint"],
        )

    def test_a_dirty_launch_tree_is_bound_as_is_and_further_edits_still_drift(self):
        (self.source / "tools" / "engine.py").write_text("VALUE = 7\n", encoding="utf-8")

        def editing_again(*_args, **_kwargs):
            (self.source / "tools" / "engine.py").write_text("VALUE = 8\n", encoding="utf-8")
            return self.quiet()

        source = self.drive(editing_again)["source"]
        self.assertEqual(list(source["at_launch"]["dirty"]), ["tools/engine.py"])
        self.assertEqual(source["integrity"], "DRIFTED")
        self.assertEqual(source["changed_paths"], ["tools/engine.py"])

    def test_a_commit_during_the_run_is_drift_naming_the_committed_path(self):
        def committing(*_args, **_kwargs):
            (self.source / "tools" / "new_module.py").write_text("X = 1\n", encoding="utf-8")
            _git(self.source, "add", "-A")
            _git(self.source, "commit", "-q", "-m", "concurrent")
            return self.quiet()

        source = self.drive(committing)["source"]
        self.assertEqual(source["integrity"], "DRIFTED")
        self.assertEqual(source["changed_paths"], ["tools/new_module.py"])
        self.assertNotEqual(source["at_end"]["source_head"], self.head)

    def test_project_memory_writes_are_not_source_drift(self):
        def journaling(*_args, **_kwargs):
            with (self.source / ".saipen" / "LOG.md").open("a", encoding="utf-8") as handle:
                handle.write("- two\n")
            (self.source / ".saipen" / "STATE.md").write_text("phase: DONE\n", encoding="utf-8")
            return self.quiet()

        source = self.drive(journaling)["source"]
        self.assertEqual(source["integrity"], "STABLE")
        self.assertEqual(source["changed_paths"], [])

    def test_an_edit_reverted_before_the_end_is_still_drift_when_a_sample_saw_it(self):
        engine = self.source / "tools" / "engine.py"
        interim = self.out / "interim.jsonl"

        def edit_then_revert(*_args, **_kwargs):
            engine.write_text("VALUE = 3\n", encoding="utf-8")
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if interim.exists() and '"DRIFTED"' in interim.read_text(encoding="utf-8"):
                    break
                time.sleep(0.05)
            engine.write_text("VALUE = 1\n", encoding="utf-8")
            return self.quiet()

        source = self.drive(edit_then_revert, interim_every=0.2)["source"]
        self.assertEqual(source["integrity"], "DRIFTED")
        self.assertEqual(source["changed_paths"], ["tools/engine.py"])
        self.assertIsNotNone(source["first_drift_elapsed_seconds"])
        self.assertEqual(source["at_end"], source["at_launch"])
        samples = [json.loads(line) for line in interim.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(any(s.get("source", {}).get("integrity") == "DRIFTED" for s in samples))

    def test_an_unmeasurable_source_is_named_never_reported_stable(self):
        with mock.patch.object(
            soak, "compute_source_identity", side_effect=FreshnessError("git unavailable")
        ):
            source = self.drive(self.quiet)["source"]
        self.assertEqual(source["integrity"], "UNMEASURED")
        self.assertFalse(source["at_launch"]["measured"])
        self.assertIn("git unavailable", source["at_launch"]["error"])


if __name__ == "__main__":
    unittest.main()
