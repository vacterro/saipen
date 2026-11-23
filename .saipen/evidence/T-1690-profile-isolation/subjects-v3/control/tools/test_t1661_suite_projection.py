"""T-1661: a declared suite is named where the next act is chosen.

T-1658 gave a project one declared suite, an engine run and a typed record --
and no answer of the engine named the run command. Whether the checkpoint
could state suite totals then depended on an agent remembering one row of
COMMANDS.md.

The turn-entry answers (`continue`, `status`) and the `transition` answer now
carry a `suite` field with the exact run command, and only when there is a run
to do: a suite is declared, the phase is one that proves the tree (VERIFY,
REVIEW, SHIP) and this tree has no record. A project that declares no suite
gets no field, and neither does a tree that already has its record.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import phases  # noqa: E402
from saipen_engine import suite_record as SR  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_orchestration_repair import OrchestrationFixture  # noqa: E402

ENGINE = TOOLS / "saipen.py"
RUN = "saipen test suite run T-7"
SUMMARY = "=== 3 passed in 0.10s ==="


def setUpModule() -> None:
    isolate_host_session()


def _git(project: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=project, stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=120,
    )


class _Suite(OrchestrationFixture):
    """An active ticket T-7 in BUILD, a git tree and a scripted green suite."""

    def setUp(self) -> None:
        self.project = self.make_project(active=True)
        (self.project / "suite.py").write_text(f"print({SUMMARY!r})\n", encoding="utf-8")
        (self.project / "main.py").write_text("value = 1\n", encoding="utf-8")
        _git(self.project, "init", "-q")
        _git(self.project, "add", "-A")
        _git(self.project, "commit", "-q", "-m", "fixture")
        self.command = [sys.executable, "-B", "suite.py"]

    def phase(self, name: str) -> None:
        """Rewrite STATE to a VALID state in `name`; a malformed one would make
        every "no field" assertion pass for the wrong reason."""
        bearing = name in phases.TICKET_BEARING_PHASES
        # A phase enterable from anywhere names no source in the table.
        source = next(
            (tf for tf, allowed in sorted(phases.VALID_TRANSITIONS.items()) if name in allowed),
            "DONE",
        )
        fields = {
            "phase": name,
            "task": "T-7" if bearing else "none",
            "next_action": f'"PHASE {name} T-7"' if bearing else '"saipen continue"',
            "transition_from": source,
        }
        path = self.project / ".saipen" / "STATE.md"
        lines = [
            f"{line.split(':', 1)[0]}: {fields[line.split(':', 1)[0]]}"
            if line.split(":", 1)[0] in fields
            else line
            for line in path.read_text(encoding="utf-8").splitlines()
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assertEqual(self.state(self.project)["phase"], name)

    def record(self) -> None:
        SR.write_record(self.project, SR.run(self.project))

    def cli(self, *args: str):
        """One engine call bound to the fixture twice over.

        The root goes FIRST: appended after the words, it lands behind the
        `--` of `declare -- <command>`, becomes part of the suite command, and
        the call binds whatever project the working directory is in. That
        directory is therefore the fixture too, never the repository the tests
        run from -- measured on 2026-10-07: five `suite declared` lines in this
        repository's own LOG before the first assertion failed.
        """
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
        env["PWD"] = str(self.project)
        proc = subprocess.run(
            [sys.executable, "-B", str(ENGINE), "--project-root", str(self.project), *args],
            stdin=subprocess.DEVNULL, capture_output=True, env=env, cwd=str(self.project),
            timeout=300, check=False,
        )
        return proc.returncode, proc.stdout.decode("utf-8")


class ProjectionTests(_Suite):
    def test_a_project_that_declares_no_suite_gets_no_field(self):
        for phase in ("VERIFY", "REVIEW", "SHIP", "BUILD"):
            with self.subTest(phase):
                self.phase(phase)
                self.assertIsNone(SR.projection(self.project))

    def test_the_run_command_is_named_while_the_tree_has_no_record(self):
        SR.declare(self.project, self.command)
        for phase in ("VERIFY", "REVIEW", "SHIP"):
            with self.subTest(phase):
                self.phase(phase)
                found = SR.projection(self.project)
                self.assertEqual(found["command"], RUN)
                self.assertIn("no record of the current tree", found["reason"])

    def test_nothing_is_named_once_the_tree_has_its_record(self):
        SR.declare(self.project, self.command)
        self.phase("VERIFY")
        self.record()
        self.assertIsNone(SR.projection(self.project))
        (self.project / "main.py").write_text("value = 2\n", encoding="utf-8")
        self.assertEqual(SR.projection(self.project)["command"], RUN, "the tree moved on")
        self.record()
        self.assertIsNone(SR.projection(self.project))

    def test_a_red_record_of_this_tree_is_still_its_record(self):
        """The field means "this tree was not run", never "run it until green"."""
        (self.project / "suite.py").write_text(
            "import sys\nprint('=== 1 failed, 2 passed in 0.10s ===')\nsys.exit(1)\n",
            encoding="utf-8",
        )
        SR.declare(self.project, self.command)
        self.phase("VERIFY")
        self.record()
        self.assertIsNone(SR.projection(self.project))

    def test_the_phases_that_do_not_prove_the_tree_carry_no_field(self):
        SR.declare(self.project, self.command)
        for phase in ("SCOUT", "BUILD", "DONE", "BLOCKED", "PLAN", "CLEAN"):
            with self.subTest(phase):
                self.phase(phase)
                self.assertIsNone(SR.projection(self.project))

    def test_a_damaged_declaration_or_state_is_silence_not_a_crash(self):
        SR.declare(self.project, self.command)
        self.phase("VERIFY")
        declaration = self.project / SR.DECLARATION_REL
        kept = declaration.read_bytes()
        declaration.write_text("{", encoding="utf-8")
        self.assertIsNone(SR.projection(self.project))
        declaration.write_bytes(kept)
        (self.project / ".saipen" / "STATE.md").unlink()
        self.assertIsNone(SR.projection(self.project))

    def test_the_named_command_is_one_the_guard_admits(self):
        from saipen_engine import guard_events

        SR.declare(self.project, self.command)
        self.phase("VERIFY")
        command = SR.projection(self.project)["command"]
        self.assertIsNotNone(guard_events._saipen_cli_verb(command), command)


class AnswerTests(_Suite):
    def test_transition_to_verify_and_continue_name_the_run_then_fall_silent(self):
        rc, out = self.cli("continue", "--json")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("suite", json.loads(out), "nothing declared, nothing named")

        rc, out = self.cli("test", "suite", "declare", "--json", "--", *self.command)
        self.assertEqual((rc, json.loads(out)["code"]), (0, "SUITE_DECLARED"), out)
        rc, out = self.cli("continue", "--json")
        self.assertNotIn("suite", json.loads(out), "BUILD does not prove the tree")

        rc, out = self.cli("transition", "VERIFY", "T-7", "build recorded", "--json")
        moved = json.loads(out)
        self.assertEqual((rc, moved["code"]), (0, "TRANSITIONED"), out)
        self.assertEqual(moved["suite"]["command"], RUN)

        rc, out = self.cli("continue", "--json")
        self.assertEqual(json.loads(out)["suite"]["command"], RUN, out)
        rc, out = self.cli("status", "--json")
        self.assertEqual(json.loads(out)["suite"]["command"], RUN, out)
        rc, out = self.cli("continue")
        self.assertIn("suite: " + RUN, out.splitlines(), "the plain answer names it too")

        rc, out = self.cli("test", "suite", "run", "T-7", "--json")
        ran = json.loads(out)
        self.assertEqual((rc, ran["code"], ran["verdict"]), (0, "SUITE_RECORDED", "PASS"), out)
        rc, out = self.cli("continue", "--json")
        self.assertNotIn("suite", json.loads(out), "this tree has its record")
        rc, out = self.cli("status", "--json")
        self.assertNotIn("suite", json.loads(out))

    def test_the_harness_binds_the_fixture_and_never_the_repository_it_runs_from(self):
        """The leak this module once had, asked directly: an engine call whose
        words end in `-- <command>` must still land in the fixture."""
        rc, out = self.cli("test", "suite", "declare", "--json", "--", *self.command)
        self.assertEqual((rc, json.loads(out)["command"]), (0, self.command), out)
        declared, error = SR.load_declaration(self.project)
        self.assertIsNone(error)
        self.assertEqual(declared["command"], self.command)
        log = (self.project / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("suite declared -- command:" + declared["command_sha256"][:16], log)

    def test_a_refused_transition_and_other_commands_carry_no_field(self):
        self.cli("test", "suite", "declare", "--json", "--", *self.command)
        self.phase("VERIFY")
        rc, out = self.cli("transition", "SHIP", "T-7", "skipping review", "--json")
        refused = json.loads(out)
        self.assertFalse(refused["ok"], out)
        self.assertNotIn("suite", refused)
        rc, out = self.cli("checkpoint", "RUN", "T-7", "a note", "--json")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("suite", json.loads(out), "only the answers that choose the next act")


class WithdrawTests(_Suite):
    """A declaration has an inverse the engine owns: without one, undoing a
    declaration meant writing into the namespace a file tool is refused in."""

    def test_withdraw_removes_the_declaration_and_keeps_the_records(self):
        with self.assertRaises(LookupError):
            SR.withdraw(self.project)
        SR.declare(self.project, self.command)
        self.phase("VERIFY")
        self.record()
        result = SR.withdraw(self.project)
        self.assertEqual(result["previous_sha256"], SR.command_digest(self.command))
        self.assertIsNone(result["was_invalid"])
        self.assertEqual(SR.load_declaration(self.project), (None, None))
        self.assertEqual(len(list((self.project / SR.RECORD_DIR_REL).glob("*-*.json"))), 1)
        self.assertIsNone(SR.newest_record(self.project), "no declaration, no suite claim")
        self.assertIsNone(SR.projection(self.project))
        with self.assertRaises(LookupError):
            SR.withdraw(self.project)

    def test_the_command_withdraws_once_and_says_what_it_removed(self):
        rc, out = self.cli("test", "suite", "withdraw", "--json")
        refused = json.loads(out)
        self.assertEqual((rc, refused["code"], refused["suite"]),
                         (1, "VALIDATION_FAILED", "NOT_DECLARED"), out)
        self.cli("test", "suite", "declare", "--json", "--", *self.command)
        digest = SR.command_digest(self.command)
        rc, out = self.cli("test", "suite", "withdraw", "--dry-run", "--json")
        self.assertEqual((rc, json.loads(out)["code"]), (0, "SUITE_WITHDRAW_PLAN"), out)
        self.assertIsNotNone(SR.load_declaration(self.project)[0], "a preview removes nothing")
        rc, out = self.cli("test", "suite", "withdraw", "--json")
        gone = json.loads(out)
        self.assertEqual((rc, gone["code"], gone["previous_sha256"]),
                         (0, "SUITE_WITHDRAWN", digest), out)
        log = (self.project / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("suite withdrawn -- command:" + digest[:16], log)
        rc, out = self.cli("test", "suite", "--json")
        self.assertEqual((rc, json.loads(out)["declared"]), (0, False), out)

    def test_a_damaged_declaration_can_be_withdrawn(self):
        SR.declare(self.project, self.command)
        (self.project / SR.DECLARATION_REL).write_text("{", encoding="utf-8")
        rc, out = self.cli("test", "suite", "withdraw", "--json")
        gone = json.loads(out)
        self.assertEqual((rc, gone["code"], gone["previous_sha256"]),
                         (0, "SUITE_WITHDRAWN", None), out)
        self.assertIn("unreadable", gone["was_invalid"])
        self.assertEqual(SR.load_declaration(self.project), (None, None))
        log = (self.project / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("suite withdrawn -- an unreadable declaration", log)

    def test_withdraw_writes_and_is_refused_in_a_read_only_session(self):
        from saipen_engine.command_effects import classify_tokens

        self.assertEqual(classify_tokens("saipen test suite withdraw".split()), "EXECUTION")
        SR.declare(self.project, self.command)
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
        env.update(PWD=str(self.project), SAIPEN_CAPABILITY="read-only")
        proc = subprocess.run(
            [sys.executable, "-B", str(ENGINE), "--project-root", str(self.project),
             "test", "suite", "withdraw", "--json"],
            stdin=subprocess.DEVNULL, capture_output=True, env=env, cwd=str(self.project),
            timeout=300, check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIsNotNone(SR.load_declaration(self.project)[0])


if __name__ == "__main__":
    unittest.main()
