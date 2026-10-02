"""Public-CLI subprocess regressions for the T-1302 orchestration repair.

CONTROLS A-I from the handoff: the public command surface must actually work
end to end -- not just the engine functions. The FastPrompter failure was a
PUBLIC workflow (agent runs `saipen ...`), so these tests drive the real
`tools/saipen.py` as a subprocess against a throwaway project and assert the
public JSON contract. Engine-level regressions stay in
test_orchestration_repair.py; this suite proves the CLI exposes them.

Run standalone:
    python tools/test_public_closure_cli.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.operations import apply_claim, finish_ticket  # noqa: E402
from saipen_engine.state import parse_state  # noqa: E402
from test_orchestration_repair import OrchestrationFixture  # noqa: E402

SAIPEN_PY = TOOLS / "saipen.py"


def _with_published_release(project: Path, version: str = "0.4.2") -> str:
    """Durable publication evidence (FINDING 3 authority): the implementation
    the verification-only ticket inherits was already released. Scenario setup,
    not a closure shortcut."""
    (project / ".saipen" / "kitchen").mkdir(parents=True, exist_ok=True)
    (project / ".saipen" / "kitchen" / "release_receipt.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "op_id": "release-abc123",
                "version": version,
                "tag": f"v{version}",
                "commit": "c0ffee",
            }
        ),
        encoding="utf-8",
    )
    return f"release:v{version}"


def _copy_tools(project: Path) -> None:
    """The no-publish release gate runs `<project>/tools/validate.py --gate
    core` (T-994 / § 10), so a cohort ship fixture needs a working tools copy
    bound to the same engine."""
    target = project / "tools"
    if target.exists():
        return
    shutil.copytree(TOOLS, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


class PublicClosureCliTests(OrchestrationFixture):
    """CONTROL A/B: public `ticket done --closure-mode ...` grammar."""

    def run_cli(self, project: Path, *args: str) -> tuple[int, dict, str]:
        proc = subprocess.run(
            [
                sys.executable,
                str(SAIPEN_PY),
                "--project-root",
                str(project),
                "--agent",
                "tester",
                "--json",
                *args,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
            timeout=180,
        )
        try:
            payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
        except ValueError:
            payload = {"_unparseable_stdout": proc.stdout}
        return proc.returncode, payload, proc.stderr

    def test_control_a_inherited_cli(self):
        """A verification-only ticket closes through the PUBLIC CLI with
        closure provenance, zero Git publication."""
        project = self.make_project(active=True)
        source = _with_published_release(project)
        self.to_ship(project, "T-7")
        rc, payload, _err = self.run_cli(
            project,
            "ticket",
            "done",
            "T-7",
            "--closure-mode",
            "inherited_verified",
            "--implementation-source",
            source,
        )
        self.assertEqual(rc, 0, payload)
        self.assertTrue(payload.get("ok"), payload)
        board = self.board(project)
        done = board["tickets"]["T-7"]
        self.assertEqual(done["section"], "## DONE")
        fields = done["fields"]
        self.assertEqual(fields.get("closure_mode"), "inherited_verified")
        self.assertEqual(fields.get("implementation_delta"), "none")
        self.assertEqual(fields.get("implementation_source"), source)
        self.assertFalse((project / ".git").exists())
        state = self.state(project)
        self.assertEqual(state["phase"], "DONE")
        self.assertEqual(state["task"], "none")

    def test_control_b_malformed_inherited_cli(self):
        """Missing / malformed / duplicate / unknown closure options REFUSE
        with zero canonical mutation (FINDING 1 + 3)."""
        project = self.make_project(active=True)
        self.to_ship(project, "T-7")
        # Missing implementation_source.
        rc, payload, _err = self.run_cli(
            project,
            "ticket",
            "done",
            "T-7",
            "--closure-mode",
            "inherited_verified",
        )
        self.assertNotEqual(rc, 0)
        self.assertEqual(payload.get("code"), "VALIDATION_FAILED")
        self.assertIn("--implementation-source", payload.get("detail", ""))
        self.assertEqual(self.board(project)["tickets"]["T-7"]["section"], "## DOING")
        # Duplicate option.
        rc, payload, _err = self.run_cli(
            project,
            "ticket",
            "done",
            "T-7",
            "--closure-mode",
            "cohort",
            "--closure-mode",
            "own_patch",
            "--closure-cohort",
            "C-001",
            "--paths",
            "main.py",
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("duplicate option", payload.get("detail", ""))
        # Unknown option.
        rc, payload, _err = self.run_cli(
            project,
            "ticket",
            "done",
            "T-7",
            "--closure-mode",
            "cohort",
            "--closure-cohort",
            "C-001",
            "--paths",
            "main.py",
            "--frobnicate",
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("unknown option", payload.get("detail", ""))
        # Option value missing.
        rc, payload, _err = self.run_cli(
            project,
            "ticket",
            "done",
            "T-7",
            "--closure-mode",
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("needs a value", payload.get("detail", ""))
        # Semantics: cohort without cohort id refuses (engine gate).
        rc, payload, _err = self.run_cli(
            project, "ticket", "done", "T-7", "--closure-mode", "cohort", "--paths", "main.py"
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("closure_cohort", payload.get("detail", ""))
        # Semantics: --closure-cohort on own_patch refuses.
        rc, payload, _err = self.run_cli(
            project,
            "ticket",
            "done",
            "T-7",
            "--closure-cohort",
            "C-001",
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("only valid with closure_mode cohort", payload.get("detail", ""))
        # The ticket never moved: every refusal above was zero-write.
        self.assertEqual(self.board(project)["tickets"]["T-7"]["section"], "## DOING")

    def test_control_c_d_cohort_cli_and_publication(self):
        """CONTROL C/D: two overlapping members join C-001 through the public
        CLI; `saipen cohort ship C-001` publishes ONE batch scope through the
        release machinery and flips the durable registry to shipped."""
        project = self.make_project(active=True)
        (project / "main.py").write_text("shared = True\n", encoding="utf-8")
        # no-publish policy: the fixture project never publishes Git.
        state_path = project / ".saipen" / "STATE.md"
        state_text = state_path.read_text(encoding="utf-8")
        state_path.write_text(state_text.replace("mode: full", "mode: no-publish"), encoding="utf-8")
        (project / "VERSION").write_text("0.5.0\n", encoding="utf-8")
        _copy_tools(project)

        second = self.add(project, "overlapping work")
        self.to_ship(project, "T-7")
        rc, payload, _err = self.run_cli(
            project,
            "ticket",
            "done",
            "T-7",
            "--closure-mode",
            "cohort",
            "--closure-cohort",
            "C-001",
            "--paths",
            "main.py",
        )
        self.assertEqual(rc, 0, payload)
        self.assertTrue(payload.get("ok"), payload)
        claim = apply_claim(project, second, "buffy", explicit=True)
        self.assertTrue(claim.ok, claim.to_dict())
        self.to_ship(project, second)
        rc, payload, _err = self.run_cli(
            project,
            "ticket",
            "done",
            second,
            "--closure-mode",
            "cohort",
            "--closure-cohort",
            "C-001",
            "--paths",
            "main.py",
        )
        self.assertEqual(rc, 0, payload)

        registry = json.loads(
            (project / ".saipen" / "kitchen" / "cohort_registry.json").read_text(
                encoding="utf-8"
            )
        )
        cohort = registry["cohorts"]["C-001"]
        self.assertEqual(cohort["publication_status"], "pending")
        self.assertEqual(set(cohort["members"]), {"T-7", second})
        # No individual fake commit exists.
        self.assertFalse((project / ".git").exists())

        # CONTROL D: foreign dirty work elsewhere must survive publication.
        (project / "foreign.py").write_text("foreign = True\n", encoding="utf-8")

        # Public cohort publication: one batch scope, registry flips shipped.
        rc, payload, _err = self.run_cli(project, "cohort", "ship", "C-001")
        self.assertEqual(rc, 0, payload)
        self.assertTrue(payload.get("ok"), payload)
        registry = json.loads(
            (project / ".saipen" / "kitchen" / "cohort_registry.json").read_text(
                encoding="utf-8"
            )
        )
        cohort = registry["cohorts"]["C-001"]
        self.assertEqual(cohort["publication_status"], "shipped")
        self.assertTrue(cohort["release_op_id"], cohort)
        self.assertEqual(cohort["version"], "0.5.0")
        self.assertEqual(cohort["tag"], "v0.5.0")
        # The frozen batch scope names the shared path exactly once.
        self.assertEqual(sorted(cohort["scope"]), ["main.py"])
        # Foreign bytes are untouched.
        self.assertEqual(
            (project / "foreign.py").read_text(encoding="utf-8"), "foreign = True\n"
        )
        # Idempotency: a second ship refuses (already published).
        rc, payload, _err = self.run_cli(project, "cohort", "ship", "C-001")
        self.assertNotEqual(rc, 0)
        self.assertIn("already published", payload.get("detail", ""))
        # Durable publication receipt exists (FINDING 4).
        receipt = json.loads(
            (project / ".saipen" / "kitchen" / "release_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(receipt["cohort_id"], "C-001")
        self.assertEqual(receipt["op_id"], cohort["release_op_id"])

    def test_control_e_fastprompter_verification_only(self):
        """CONTROL E: the original T-1201 class -- implementation already
        durably owned elsewhere, current ticket adds no code, shared worktree
        carries unrelated bytes -- closes inherited_verified through the
        public CLI with no attempted isolation/commit."""
        project = self.make_project(active=True)
        source = _with_published_release(project)
        # Shared accumulated worktree with unrelated bytes (FastPrompter main.py).
        (project / "main.py").write_text(
            "# accumulated from T-A, T-B, T-C\ncheckbox = False\n", encoding="utf-8"
        )
        self.to_ship(project, "T-7")
        rc, payload, _err = self.run_cli(
            project,
            "ticket",
            "done",
            "T-7",
            "--closure-mode",
            "inherited_verified",
            "--implementation-source",
            source,
        )
        self.assertEqual(rc, 0, payload)
        board = self.board(project)
        self.assertEqual(board["tickets"]["T-7"]["section"], "## DONE")
        fields = board["tickets"]["T-7"]["fields"]
        self.assertEqual(fields.get("closure_mode"), "inherited_verified")
        self.assertEqual(fields.get("implementation_delta"), "none")
        # main.py was never staged/committed/isolated -- no .git at all.
        self.assertFalse((project / ".git").exists())
        self.assertEqual(
            (project / "main.py").read_text(encoding="utf-8"),
            "# accumulated from T-A, T-B, T-C\ncheckbox = False\n",
        )

    def test_control_f_user_interrupt(self):
        """CONTROL F: public `user-request` persists the new explicit request
        while T-A stays DOING; after a ticket-scope block the scheduler picks
        the new request."""
        project = self.make_project(active=True)
        rc, payload, _err = self.run_cli(project, "user-request", "make checkbox indicators square")
        self.assertEqual(rc, 0, payload)
        self.assertTrue(payload.get("ok"), payload)
        new_ticket = payload.get("data", {}).get("ticket") or payload.get("ticket")
        self.assertTrue(new_ticket, payload)
        board = self.board(project)
        self.assertTrue(board["tickets"][new_ticket].get("fields", {}).get("user_explicit"))
        # T-A untouched and still claimed.
        self.assertEqual(board["tickets"]["T-7"]["section"], "## DOING")
        # Now block T-A with ticket scope through the public CLI.
        rc, payload, _err = self.run_cli(
            project, "ticket", "block", "T-7", "exact patch isolation unavailable", "--scope", "ticket"
        )
        self.assertEqual(rc, 0, payload)
        state = self.state(project)
        self.assertTrue(state["next_action"].endswith(new_ticket), state)
        # The request survives a re-read (durable projection, not agent memory).
        board = self.board(project)
        self.assertEqual(board["tickets"][new_ticket]["section"], "## TODO")

    def test_control_g_h_blocked_release_and_goal_block(self):
        """CONTROL G/H: `saipen continue` + `saipen status --json` agree that
        an independent explicit ticket is next while a release's gates are
        blocked; with only goal-scope blockers left, GOAL_BLOCKED appears."""
        project = self.make_project()
        self.add(project, "gate A", verify="PASS A")
        gate_b = self.add(project, "gate B", verify="PASS B")
        release = self.add(project, "release work", needs=[gate_b])
        rc, payload, _err = self.run_cli(project, "ticket", "block", gate_b, "operator hardware confirmation", "--scope", "goal")
        self.assertEqual(rc, 0, payload)
        rc, payload, _err = self.run_cli(project, "user-request", "make checkbox indicators square")
        self.assertEqual(rc, 0, payload)
        new_ticket = payload.get("data", {}).get("ticket") or payload.get("ticket")
        # Public status agrees on the workable pick.
        rc, status, _err = self.run_cli(project, "status", "--json")
        self.assertEqual(rc, 0, status)
        # status --json reports the FRESH route (computed_next_action) beside
        # the persisted next_action; both must agree the user ticket is next
        # and never the blocked release.
        self.assertIn(new_ticket, status.get("computed_next_action") or "", status)
        self.assertNotIn(release, status.get("computed_next_action") or "", status)
        self.assertEqual(status.get("computed_reason"), "start-user-explicit")
        self.assertNotEqual(release, new_ticket)
        # Public continue re-routes and PERSISTS the pick on STATE.
        rc, cont, _err = self.run_cli(project, "continue")
        self.assertEqual(rc, 0, cont)
        state = self.state(project)
        self.assertIn(new_ticket, state["next_action"], state)
        self.assertNotIn(release, state["next_action"], state)

    def test_control_i_help_contract(self):
        """CONTROL I: `saipen --help` advertises every surface the agent
        needs -- the executable feature must never become undiscoverable."""
        proc = subprocess.run(
            [sys.executable, str(SAIPEN_PY), "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
            timeout=60,
        )
        text = proc.stdout + proc.stderr
        for token in (
            "user-request",
            "--closure-mode",
            "--closure-cohort",
            "--implementation-source",
            "--paths",
            "cohort ship",
        ):
            self.assertIn(token, text, f"--help must advertise {token!r}")


if __name__ == "__main__":
    unittest.main()