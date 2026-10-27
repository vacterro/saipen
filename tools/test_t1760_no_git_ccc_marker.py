"""T-1760: the validator reads the ccc route the engine writes without Git.

`saipen ccc` logs `DEC: ccc converge target -> ship @<pre-SHIP-source_head>`
(CONVERGE.md). In a tree without Git that head is the literal `no-git`
(`freshness.compute_source_identity`), and `validate.py` admitted only a
commit id: a project failed `converge_target: ship has no ccc entry marker`
on the engine's own line (measured on a managed project, 2026-10-13), and a
session working there then widened the pattern in this tree for every project.

The owner of "no Git" decides in both places now. `@no-git` is a marker only
in a tree that owner calls no-Git, where SHIP's skipped publish is also the
boundary stages J-M must follow. A Git project owes a commit id as before.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import continuity_probes as probes  # noqa: E402
from test_control_primitives import ControlFixture  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

from saipen_engine.operations import checkpoint, enter_ship_convergence  # noqa: E402

AGENT = "tester"
NO_MARKER = "converge_target: ship has no ccc entry marker"
BEFORE_SHIP = "ccc prepared EE/QQ before SHIP"


def setUpModule() -> None:
    isolate_host_session()


def _commit_everything(project: Path) -> None:
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "audit@example.invalid"],
        ["git", "config", "user.name", "Audit Fixture"],
        ["git", "config", "core.autocrlf", "false"],
        ["git", "add", "."],
        ["git", "commit", "-qm", "fixture"],
    ):
        subprocess.run(command, cwd=project, check=True)


class ShipRouteFixture(ControlFixture):
    def enter(self) -> str:
        entered = enter_ship_convergence(self.project, AGENT)
        self.assertTrue(entered.ok, entered.to_dict())
        return entered.data["source_head"]

    def log(self, text: str) -> None:
        written = checkpoint(self.project, AGENT, "RUN", "T-7", text)
        self.assertTrue(written.ok, written.to_dict())

    def named(self, phrase: str) -> list:
        _code, out = probes.validate(self.project)
        return [line for line in out.splitlines() if line.startswith("FAIL") and phrase in line]


class NoGitShipRouteTests(ShipRouteFixture):
    def setUp(self):
        self.project = self.make_project(intent="goal", active=True)
        self.assertEqual(self.enter(), "no-git")

    def test_the_engines_own_marker_is_a_marker_without_git(self):
        log = (self.project / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("DEC: ccc converge target -> ship @no-git", log)
        self.assertEqual(self.named(NO_MARKER), [])

    def test_a_git_project_still_owes_a_commit_id(self):
        # The same LOG, now in a Git project of its own: `@no-git` names no
        # commit there, so the route has no entry evidence.
        _commit_everything(self.project)
        self.assertEqual(len(self.named(NO_MARKER)), 1)

    def test_a_skipped_publish_is_the_ship_boundary_without_git(self):
        self.log("ship v1.0.0 -> skipped publish (no-publish: no git)")
        self.log("prepare saitranslate -> done")
        self.assertEqual(self.named(BEFORE_SHIP), [])

    def test_a_package_prepared_before_any_ship_still_fails(self):
        self.log("prepare saitranslate -> done")
        self.assertEqual(len(self.named(BEFORE_SHIP)), 1)


class NestedShipRouteTests(ShipRouteFixture):
    def test_a_project_inside_another_repository_is_no_git_too(self):
        # Git answers "inside a work tree" here, and the identity owner still
        # says no-git: the project is not a Git project of its own. One owner
        # decides, so the validator reads the marker that owner made the
        # engine write.
        self.project = self.make_project(intent="goal", active=True)
        _commit_everything(self.project.parent)
        self.assertEqual(self.enter(), "no-git")
        self.assertEqual(self.named(NO_MARKER), [])


class GitShipRouteTests(ShipRouteFixture):
    def setUp(self):
        self.project = self.make_project(intent="goal", active=True)
        _commit_everything(self.project)
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.project, text=True
        ).strip()
        self.assertEqual(self.enter(), head)

    def test_a_commit_id_is_still_the_marker(self):
        self.assertEqual(self.named(NO_MARKER), [])

    def test_a_skipped_publish_is_no_boundary_where_a_push_can_exist(self):
        # A line anyone can write does not stand in for a pushed head.
        self.log("ship v1.0.0 -> skipped publish (no-publish: policy)")
        self.log("prepare saitranslate -> done")
        self.assertEqual(len(self.named(BEFORE_SHIP)), 1)


if __name__ == "__main__":
    unittest.main()
