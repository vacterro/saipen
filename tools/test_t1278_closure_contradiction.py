"""T-1278: a closure commit never asserts a terminal state its bytes contradict.

Observed live: 058ab732 "closure v7.250.0: ticket T-1276 DONE" carries a BOARD
on which T-1276 is still ## DOING, and the history scan found the same at
794085e9 (T-1280). These controls hold:

* AC-01/02: the commit path refuses, and creates no commit, when the staged
  BOARD does not close the ticket its subject names;
* AC-03: the history scan goes red on a hand-built commit carrying a DONE
  subject over a DOING board, and stays green on a consistent one;
* AC-04: recorded divergences are excepted by commit, never rewritten.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import release  # noqa: E402


def board(section: str, ticket: str = "T-1") -> str:
    line = f"- [{'x' if section == 'DONE' else '/'}] {ticket} fixture work | verify: proof\n"
    parts = {"DOING": "", "TODO": "", "BLOCKED": "", "DONE": ""}
    parts[section] = line
    return "# BOARD\n\n" + "".join(f"## {name}\n{body}\n" for name, body in parts.items())


class Repo:
    def __init__(self, case: unittest.TestCase):
        self.root = Path(tempfile.mkdtemp(prefix="t1278-"))
        case.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env = env
        self.git("init", "-q")
        # The identity goes IN the repository, not only on this helper's command
        # line: the code under test runs its own `git commit` inside this repo
        # and inherits nothing from `-c`. Those commits picked up the
        # maintainer's global config here, and failed on a runner that has none.
        self.git("config", "user.name", "fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        (self.root / ".saipen").mkdir()

    def git(self, *args: str) -> str:
        proc = subprocess.run(
            ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
             "-c", "core.autocrlf=false", *args],
            cwd=self.root, env=self.env, capture_output=True, text=True, check=True,
        )
        return proc.stdout.strip()

    def commit_board(self, text: str, subject: str) -> str:
        (self.root / ".saipen" / "kitchen").mkdir(exist_ok=True)
        for name, body in (
            ("BOARD.md", text),
            ("LOG.md", "- log\n"),
            ("STATE.md", "---\n---\n"),
            ("kitchen/digest.md", "digest\n"),
        ):
            (self.root / ".saipen" / name).write_bytes(body.encode("utf-8"))
        self.git("add", "-A")
        self.git("commit", "-q", "-m", subject)
        return self.git("rev-parse", "HEAD")


class BoardContradictionTests(unittest.TestCase):
    def test_a_done_ticket_is_consistent(self):
        self.assertIsNone(release.closure_board_contradiction(board("DONE"), "T-1"))

    def test_a_doing_ticket_contradicts(self):
        problem = release.closure_board_contradiction(board("DOING"), "T-1")
        self.assertIn("## DOING", problem)

    def test_a_missing_ticket_contradicts(self):
        problem = release.closure_board_contradiction(board("DONE", "T-2"), "T-1")
        self.assertIn("not on its BOARD", problem)


class HistoryScanTests(unittest.TestCase):
    def test_a_done_subject_over_a_doing_board_is_reported(self):
        repo = Repo(self)
        repo.commit_board(board("DONE", "T-1"), "closure v1.0.0: ticket T-1 DONE")
        bad = repo.commit_board(board("DOING", "T-2"), "closure v1.0.1: ticket T-2 DONE")
        found = release.closure_history_contradictions(repo.root)
        self.assertEqual([(item["commit"], item["ticket"]) for item in found], [(bad, "T-2")])

    def test_a_recorded_divergence_is_excepted_not_rewritten(self):
        repo = Repo(self)
        bad = repo.commit_board(board("DOING"), "closure v1.0.0: ticket T-1 DONE")
        with mock.patch.dict(release.KNOWN_CLOSURE_DIVERGENCES, {bad[:8]: "fixture"}):
            self.assertEqual(release.closure_history_contradictions(repo.root), [])
        self.assertEqual(repo.git("rev-parse", "HEAD"), bad)

    def test_other_subjects_are_ignored(self):
        repo = Repo(self)
        repo.commit_board(board("DOING"), "ship v1.0.0")
        self.assertEqual(release.closure_history_contradictions(repo.root), [])

    def test_no_repository_reports_nothing(self):
        plain = Path(tempfile.mkdtemp(prefix="t1278-plain-"))
        self.addCleanup(shutil.rmtree, plain, ignore_errors=True)
        self.assertEqual(release.closure_history_contradictions(plain), [])

    def test_the_live_history_carries_only_recorded_divergences(self):
        self.assertEqual(release.closure_history_contradictions(TOOLS.parent), [])


class _Journal:
    manifest = "fixture-journal"

    def update(self, **_fields):
        return None


class _Plan:
    version = "1.0.0"
    ticket_id = "T-1"


class CommitGuardTests(unittest.TestCase):
    def stage(self, text: str) -> Repo:
        repo = Repo(self)
        repo.commit_board(board("DOING"), "base")
        (repo.root / ".saipen" / "BOARD.md").write_bytes(text.encode("utf-8"))
        return repo

    def test_no_closure_commit_over_a_board_that_leaves_the_ticket_open(self):
        repo = self.stage(board("DOING"))
        before = repo.git("rev-parse", "HEAD")
        with self.assertRaises(release.ReleaseRefusal) as caught:
            release._commit_closure(repo.root, _Plan(), _Journal())
        self.assertEqual(caught.exception.code, "CLOSURE_CONTRADICTION")
        self.assertEqual(repo.git("rev-parse", "HEAD"), before)

    def test_a_consistent_closure_is_committed(self):
        repo = self.stage(board("DONE"))
        before = repo.git("rev-parse", "HEAD")
        release._commit_closure(repo.root, _Plan(), _Journal())
        self.assertNotEqual(repo.git("rev-parse", "HEAD"), before)
        self.assertEqual(repo.git("log", "-1", "--format=%s"), "closure v1.0.0: ticket T-1 DONE")


if __name__ == "__main__":
    unittest.main()
