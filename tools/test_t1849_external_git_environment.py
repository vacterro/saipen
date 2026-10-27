"""External implementation evidence belongs to its declared Git repository."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import external, external_renewal  # noqa: E402

LINEAGE = "lineage-0123456789abcdef0123456789abcdef"


class ExternalGitEnvironment(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="saipen-external-git-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.upstream = self.base / "upstream"
        self.caller = self.base / "caller"
        self.fixture_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        for repo, content in ((self.upstream, "real implementation\n"),
                              (self.caller, "caller implementation\n")):
            repo.mkdir()
            self.git(repo, "init")
            (repo / "implementation.txt").write_text(content, encoding="utf-8")
            self.git(repo, "add", "--", "implementation.txt")
            self.git(repo, "-c", "user.name=T", "-c", "user.email=t@e",
                     "commit", "-m", content.strip())
        self.commit = self.git(self.upstream, "rev-parse", "HEAD").decode().strip()
        self.foreign = self.git(self.caller, "rev-parse", "HEAD").decode().strip()
        memory = self.upstream / ".saipen"
        memory.mkdir()
        (memory / "IDENTITY.md").write_text(
            f"---\nproject_lineage: {LINEAGE}\n---\n", encoding="utf-8",
        )
        (memory / "BOARD.md").write_text(
            "## DOING\n## TODO\n## DONE\n"
            "- [x] T-289 [P1] external implementation | verify: pass\n## BLOCKED\n",
            encoding="utf-8",
        )
        self.conflicting = {
            "GIT_DIR": str(self.caller / ".git"),
            "GIT_COMMON_DIR": str(self.caller / ".git"),
            "GIT_WORK_TREE": str(self.caller),
            "GIT_INDEX_FILE": str(self.caller / ".git/index"),
        }

    def git(self, repo, *arguments):
        return subprocess.run(
            ["git", "-C", str(repo), *arguments], env=self.fixture_env,
            check=True, capture_output=True, timeout=30,
        ).stdout

    def inspect(self, commit=None, lineage=LINEAGE):
        return external.inspect_external_dependency(
            self.base, lineage, f"T-289@{commit or self.commit}", project_root=self.upstream,
        )

    def test_real_external_commit_resolves_with_conflicting_hook_selectors(self):
        with mock.patch.dict(os.environ, self.conflicting):
            before = dict(os.environ)
            result = self.inspect()
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["external_head"], self.commit)
            self.assertEqual(dict(os.environ), before)

    def test_commit_only_present_in_caller_remains_missing_externally(self):
        with mock.patch.dict(os.environ, self.conflicting):
            result = self.inspect(self.foreign)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "EXTERNAL_COMMIT_MISSING")

    def test_external_blob_snapshot_uses_external_objects(self):
        with mock.patch.dict(os.environ, self.conflicting):
            snapshot = external_renewal.capture(
                self.base, LINEAGE, f"T-289@{self.commit}", ["implementation.txt"],
                external_root=self.upstream,
            )
            self.assertIsNone(external_renewal.snapshot_problem(self.base, snapshot))
        (self.upstream / "implementation.txt").write_text("changed\n", encoding="utf-8")
        with mock.patch.dict(os.environ, self.conflicting):
            self.assertIsNotNone(external_renewal.snapshot_problem(self.base, snapshot))

    def test_wrong_lineage_still_refuses_before_git(self):
        with mock.patch.dict(os.environ, self.conflicting):
            result = self.inspect(lineage="lineage-fedcba9876543210fedcba9876543210")
        self.assertEqual(result["code"], "EXTERNAL_LINEAGE_MISMATCH")

    def test_unrelated_external_commit_is_not_an_ancestor(self):
        branch = self.git(self.upstream, "symbolic-ref", "--short", "HEAD").decode().strip()
        self.git(self.upstream, "checkout", "-b", "side")
        (self.upstream / "implementation.txt").write_text("side branch\n", encoding="utf-8")
        self.git(self.upstream, "add", "--", "implementation.txt")
        self.git(self.upstream, "-c", "user.name=T", "-c", "user.email=t@e",
                 "commit", "-m", "side")
        side = self.git(self.upstream, "rev-parse", "HEAD").decode().strip()
        self.git(self.upstream, "checkout", branch)
        with mock.patch.dict(os.environ, self.conflicting):
            result = self.inspect(side)
        self.assertEqual(result["code"], "EXTERNAL_COMMIT_NOT_IN_HEAD")

    def test_ordinary_callers_keep_existing_result(self):
        with mock.patch.dict(os.environ, self.fixture_env, clear=True):
            self.assertTrue(self.inspect()["ok"])
            self.assertEqual(self.inspect(self.foreign)["code"], "EXTERNAL_COMMIT_MISSING")


if __name__ == "__main__":
    unittest.main()
