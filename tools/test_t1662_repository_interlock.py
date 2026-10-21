"""T-1662: no test may bind the repository it runs from for a write.

A test that shells the engine and loses its explicit root binds the working
directory's project. From inside this repository that project is this
repository, and the write SUCCEEDS against the wrong ledger, so nothing fails.
Measured twice: receipts and tickets minted here by host fixtures on
2026-09-16, and five `suite declared` LOG events written here on 2026-10-07 by
a module whose `--project-root` landed behind the `--` of `declare`. Each
repair was made in the one test that leaked.

One interlock closes the class: `isolate_host_session` names the repository
root in `FORBID_SAIPEN_PROJECT_WRITE`, and the engine refuses a mutating
command that resolves to that root, before dispatch and with zero writes. A
diagnostic command, a dry run and a fixture root still work.

The engine cases use a fixture AS the held repository: a test of this
interlock that pointed it at the real one would be the leak it describes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_hermetic_env as HE  # noqa: E402
from saipen_engine import paths  # noqa: E402
from saipen_engine.errors import CODES  # noqa: E402
from test_orchestration_repair import OrchestrationFixture  # noqa: E402

ENGINE = TOOLS / "saipen.py"


def setUpModule() -> None:
    HE.isolate_host_session()


def _memory(project: Path) -> dict[str, bytes]:
    """Every byte of a project's memory, by relative path."""
    base = project / ".saipen"
    return {
        path.relative_to(base).as_posix(): path.read_bytes()
        for path in sorted(base.rglob("*"))
        if path.is_file()
    }


class ArmingTests(unittest.TestCase):
    def test_the_session_names_the_repository_it_runs_from(self):
        self.assertEqual(HE.FORBID_PROJECT_WRITE, paths.ENV_FORBID_PROJECT_WRITE)
        self.assertTrue(os.path.samefile(HE.REPOSITORY_ROOT, TOOLS.parent))
        self.assertEqual(os.environ.get(HE.FORBID_PROJECT_WRITE), HE.REPOSITORY_ROOT)

    def test_a_child_environment_carries_it_unless_a_test_says_otherwise(self):
        self.assertEqual(HE.hermetic_env()[HE.FORBID_PROJECT_WRITE], HE.REPOSITORY_ROOT)
        self.assertEqual(HE.hermetic_env({})[HE.FORBID_PROJECT_WRITE], HE.REPOSITORY_ROOT)
        self.assertNotIn(
            HE.FORBID_PROJECT_WRITE, HE.hermetic_env(FORBID_SAIPEN_PROJECT_WRITE=None)
        )

    def test_the_name_survives_every_way_a_test_strips_the_session(self):
        """Many modules build a child environment by dropping every variable
        whose name opens with `SAIPEN`; the engine drops its binding carriers
        by name. A child stripped that way is exactly the child that falls
        back to the working directory, so the interlock must outlive each."""
        name = HE.FORBID_PROJECT_WRITE
        base = {name: "held", "SAIPEN_AGENT": "seat", "SAIPEN_PROJECT_ROOT": "p", "PATH": "x"}
        survivors = {
            "prefix with an underscore": {
                k: v for k, v in base.items() if not k.startswith("SAIPEN_")
            },
            "prefix in any case": {
                k: v for k, v in base.items() if not k.upper().startswith("SAIPEN")
            },
            "the engine's binding carriers": paths.unbound_environment(base),
            "the host-session variables": {
                k: v for k, v in base.items() if k not in HE.HOST_SESSION_VARIABLES
            },
        }
        for idiom, env in survivors.items():
            with self.subTest(idiom):
                self.assertEqual(env.get(name), "held")
                self.assertNotIn("SAIPEN_PROJECT_ROOT", env, "the idiom did strip something")
        self.assertNotIn(name, paths.PROJECT_BINDING_ENV)
        self.assertNotIn(name, HE.HOST_SESSION_VARIABLES)

    def test_no_test_module_names_the_interlock_to_take_it_off_by_hand(self):
        """Disarming is `hermetic_env(FORBID_SAIPEN_PROJECT_WRITE=None)` in the
        one module that tests the interlock, so the intent is one reviewable
        line and not a pattern to copy."""
        named = [
            path.name
            for path in sorted(TOOLS.glob("test_*.py"))
            if path.name not in (Path(__file__).name, "test_hermetic_env.py")
            and re.search(r"FORBID_(?:SAIPEN_)?PROJECT_WRITE", path.read_text(encoding="utf-8"))
        ]
        self.assertEqual(named, [])


class HeldRootTests(unittest.TestCase):
    def setUp(self) -> None:
        self.addCleanup(os.environ.__setitem__, HE.FORBID_PROJECT_WRITE, HE.REPOSITORY_ROOT)

    def test_the_held_root_is_recognised_however_it_is_spelled(self):
        here = Path(__file__).resolve().parent
        os.environ[HE.FORBID_PROJECT_WRITE] = str(here)
        for spelling in (str(here), str(here) + os.sep, str(here / "x" / ".."), here):
            with self.subTest(spelling=str(spelling)):
                self.assertEqual(paths.write_forbidden_root(spelling), str(here))
        if os.name == "nt":
            self.assertEqual(paths.write_forbidden_root(str(here).swapcase()), str(here))
        self.assertIsNone(paths.write_forbidden_root(here.parent))
        self.assertIsNone(paths.write_forbidden_root(here / "saipen_engine"))

    def test_an_unarmed_or_empty_interlock_holds_nothing(self):
        here = Path(__file__).resolve().parent
        for value in ("", "   "):
            os.environ[HE.FORBID_PROJECT_WRITE] = value
            self.assertIsNone(paths.write_forbidden_root(here))
        del os.environ[HE.FORBID_PROJECT_WRITE]
        self.assertIsNone(paths.write_forbidden_root(here))

    def test_a_held_path_that_does_not_exist_matches_only_itself(self):
        gone = Path(__file__).resolve().parent / "no-such-directory-t1662"
        os.environ[HE.FORBID_PROJECT_WRITE] = str(gone)
        self.assertEqual(paths.write_forbidden_root(gone), str(gone))
        self.assertIsNone(paths.write_forbidden_root(gone.parent))


class EngineTests(OrchestrationFixture):
    """`self.held` plays the repository a test session runs from."""

    def setUp(self) -> None:
        self.held = self.make_project(active=True)
        self.other = self.make_project(active=True)

    def engine(self, *args: str, cwd: Path | None = None, held: str | None = "held"):
        env = HE.hermetic_env(
            FORBID_SAIPEN_PROJECT_WRITE=str(self.held) if held == "held" else held,
            PWD=str(cwd or self.held),
        )
        # `--json` goes first for the reason the root does: behind a `--` it
        # would be payload.
        proc = subprocess.run(
            [sys.executable, "-B", str(ENGINE), "--json", *args],
            stdin=subprocess.DEVNULL, capture_output=True, env=env,
            cwd=str(cwd or self.held), timeout=300, check=False,
        )
        return proc.returncode, json.loads(proc.stdout.decode("utf-8"))

    def assert_refused(self, rc: int, answer: dict, before: dict[str, bytes]) -> None:
        self.assertEqual(
            (rc, answer["ok"], answer["code"]), (1, False, "CAPABILITY_DENIED"), answer
        )
        self.assertEqual(answer["interlock"], HE.FORBID_PROJECT_WRITE)
        self.assertIn(answer["code"], CODES)
        self.assertIn("--project-root", answer["detail"])
        self.assertEqual(_memory(self.held), before, "a refusal writes nothing")

    def test_a_write_with_no_explicit_root_from_inside_the_repository_is_refused(self):
        """The measured leak: the child binds its working directory's project."""
        before = _memory(self.held)
        for words in (
            ("checkpoint", "DEC", "a line that must not land"),
            ("transition", "VERIFY", "T-7", "build recorded"),
            ("ticket", "add", "P3", "a ticket that must not land", "--verify", "none"),
            ("test", "suite", "declare", "--", sys.executable, "-B", "suite.py"),
            ("continue",),
        ):
            with self.subTest(words=words):
                self.assert_refused(*self.engine(*words), before)

    def test_naming_the_repository_explicitly_is_refused_too(self):
        before = _memory(self.held)
        rc, answer = self.engine(
            "--project-root", str(self.held), "checkpoint", "DEC", "explicit", cwd=self.other
        )
        self.assert_refused(rc, answer, before)

    def test_a_root_lost_behind_the_double_dash_lands_nowhere(self):
        """The shape of 2026-10-07: the fixture root rides in the payload."""
        before, other_before = _memory(self.held), _memory(self.other)
        rc, answer = self.engine(
            "test", "suite", "declare", "--", sys.executable, "-B", "suite.py",
            "--project-root", str(self.other),
        )
        self.assert_refused(rc, answer, before)
        self.assertEqual(_memory(self.other), other_before)

    def test_reading_the_repository_still_works(self):
        before = _memory(self.held)
        for words in (("status",), ("next",), ("test", "suite"), ("knowledge", "status")):
            with self.subTest(words=words):
                rc, answer = self.engine(*words)
                self.assertEqual((rc, answer["ok"]), (0, True), answer)
        rc, answer = self.engine("checkpoint", "DEC", "a preview", "--dry-run")
        self.assertEqual((rc, answer["ok"]), (0, True), answer)
        self.assertEqual(_memory(self.held), before, "a dry run writes nothing")

    def test_a_fixture_root_is_written_as_before(self):
        before = _memory(self.held)
        rc, answer = self.engine(
            "--project-root", str(self.other), "checkpoint", "DEC", "lands in the fixture"
        )
        self.assertEqual((rc, answer["code"]), (0, "CHECKPOINTED"), answer)
        self.assertIn(b"lands in the fixture", _memory(self.other)["LOG.md"])
        rc, answer = self.engine("checkpoint", "DEC", "from the fixture itself", cwd=self.other)
        self.assertEqual((rc, answer["code"]), (0, "CHECKPOINTED"), answer)
        self.assertEqual(_memory(self.held), before)

    def test_without_the_interlock_the_same_command_writes(self):
        """The control: what refuses above is the interlock and nothing else."""
        rc, answer = self.engine("checkpoint", "DEC", "no interlock", held=None)
        self.assertEqual((rc, answer["code"]), (0, "CHECKPOINTED"), answer)
        self.assertIn(b"no interlock", _memory(self.held)["LOG.md"])


if __name__ == "__main__":
    unittest.main()
