"""T-1658: the operator checkpoint states the suite totals of ANY project.

Measured on 2026-10-07: for a project without SAIPEN's own unit family the
VALIDATION line showed the conformance verdict only, and the suite result
(4999 passed, 23 skipped, 0 red) existed as model-written LOG prose, which the
digest rightly never parses.

A project now declares ONE suite command; the engine executes it and writes a
typed record (command digest, exit code, totals, tree identity); the digest
reads totals from a record of the declared command whose tree is the current
tree. A number written in LOG text never reaches VALIDATION, and neither does
the record of a narrower command or of another tree.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_t1614_future_gate as H  # noqa: E402
from saipen_engine import response_surface as RS  # noqa: E402
from saipen_engine import suite_record as SR  # noqa: E402
from saipen_engine.command_effects import classify_tokens  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

ENGINE = TOOLS / "saipen.py"
MEASURED = "4999 passed, 23 skipped in 512.34s (0:08:32)"


def setUpModule() -> None:
    isolate_host_session()


def _git(project: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=project, stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=120,
    )


class _Project(unittest.TestCase):
    """A project that does NOT carry the unit family, with a scripted suite."""

    git = True

    def setUp(self) -> None:
        base, self.project = H._project()
        self.addCleanup(shutil.rmtree, base, True)
        self.command = [sys.executable, "-B", "suite.py"]
        self.suite(MEASURED)
        if self.git:
            _git(self.project, "init", "-q")
            _git(self.project, "add", "-A")
            _git(self.project, "commit", "-q", "-m", "fixture")

    def suite(self, summary: str, *, code: int = 0, stream: str = "stdout") -> None:
        (self.project / "suite.py").write_text(
            "import sys\n"
            f"print({('=' * 12 + ' ' + summary + ' ' + '=' * 12)!r}, file=sys.{stream})\n"
            f"sys.exit({code})\n",
            encoding="utf-8",
        )

    def record(self) -> dict:
        return SR.write_record(self.project, SR.run(self.project))

    def validation(self) -> str:
        facts = RS.canonical_facts(self.project)
        text = RS.digest_from_facts({**facts, "phase": "DONE"}, reason="status", language="en")
        return RS.parse_surface(text)[0]["VALIDATION"]

    def log(self, text: str) -> None:
        path = self.project / ".saipen" / "LOG.md"
        path.write_text(
            path.read_text(encoding="utf-8")
            + f"- 01.09.26 00:01 [E-002] [parent: E-001] [agent: tester] RUN: {text}\n",
            encoding="utf-8",
        )


class TotalsGrammarTests(unittest.TestCase):
    def test_pytest_summaries(self):
        for text, want in (
            (MEASURED, (5022, 4999, 0, 23)),
            ("=========== 3 passed in 0.12s ===========", (3, 3, 0, 0)),
            ("1 failed, 2 passed, 1 skipped, 4 warnings in 1.00s", (4, 2, 1, 1)),
            ("\x1b[31m==== 2 failed, 1 error in 0.50s ====\x1b[0m", (3, 0, 3, 0)),
            ("5 passed, 1 xfailed, 1 xpassed, 9 deselected in 2.5s", (7, 5, 0, 0)),
        ):
            with self.subTest(text):
                found = SR.parse_totals("collected\n" + text + "\n", "")
                self.assertEqual(found["runner"], "pytest")
                self.assertEqual(
                    (found["ran"], found["passed"], found["red"], found["skipped"]), want
                )

    def test_unittest_summaries(self):
        ok = "...\n" + "-" * 70 + "\nRan 12 tests in 0.5s\n\nOK (skipped=2)\n"
        red = "Ran 9 tests in 0.5s\n\nFAILED (failures=1, errors=2, skipped=1)\n"
        self.assertEqual(
            {k: SR.parse_totals("", ok)[k] for k in ("runner", "ran", "passed", "red", "skipped")},
            {"runner": "unittest", "ran": 12, "passed": 10, "red": 0, "skipped": 2},
        )
        found = SR.parse_totals("", red)
        self.assertEqual((found["ran"], found["passed"], found["red"]), (9, 5, 3))

    def test_prose_about_a_run_is_not_a_summary(self):
        for text in (
            "the suite: 4999 passed, 23 skipped, 0 red",
            "we saw 4999 passed, 23 skipped in 512.34s yesterday",
            "4999 green, 23 lazy in 5.0s",
            "no tests ran in 0.01s",
            "",
        ):
            with self.subTest(text):
                self.assertIsNone(SR.parse_totals(text, text))

    def test_two_grammars_in_one_run_give_no_totals(self):
        """A unittest run in which a test printed a pytest-looking line (or the
        reverse): one of the two is not the runner, and nothing tells which."""
        unittest_end = "Ran 12 tests in 0.5s\n\nOK\n"
        self.assertIsNone(SR.parse_totals(MEASURED + "\n", unittest_end))
        self.assertIsNone(SR.parse_totals(unittest_end + MEASURED + "\n", ""))
        self.assertEqual(SR.parse_totals("", unittest_end)["ran"], 12)


class DeclarationTests(_Project):
    git = False

    def test_a_declaration_round_trips_and_names_what_it_replaced(self):
        self.assertEqual(SR.load_declaration(self.project), (None, None))
        first = SR.declare(self.project, self.command)
        self.assertIsNone(first["previous_sha256"])
        self.assertIn("first declaration", SR.declaration_line(first))
        loaded, error = SR.load_declaration(self.project)
        self.assertIsNone(error)
        self.assertEqual(loaded["command"], self.command)
        self.assertEqual(loaded["command_sha256"], SR.command_digest(self.command))
        second = SR.declare(self.project, [*self.command, "-k", "one"], timeout=30)
        self.assertEqual(second["previous_sha256"], loaded["command_sha256"])
        self.assertIn("replaces command:" + loaded["command_sha256"][:16],
                      SR.declaration_line(second))

    def test_a_damaged_declaration_is_an_error_not_an_absence(self):
        SR.declare(self.project, self.command)
        path = self.project / SR.DECLARATION_REL
        data = json.loads(path.read_text(encoding="utf-8"))
        data["command"] = [*self.command, "tests/one"]
        path.write_text(json.dumps(data), encoding="utf-8")
        declaration, error = SR.load_declaration(self.project)
        self.assertIsNone(declaration)
        self.assertIn("command_sha256 does not match", error)
        with self.assertRaises(LookupError):
            SR.run(self.project)

    def test_an_unusable_command_or_timeout_is_refused(self):
        for command in ([], [""], ["ok", 3], "python -m pytest"):
            with self.subTest(command=command), self.assertRaises(ValueError):
                SR.declare(self.project, command)
        for timeout in (0, -1, SR.MAX_TIMEOUT_S + 1, True):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                SR.declare(self.project, self.command, timeout=timeout)

    def test_nothing_declared_or_no_program_is_not_a_run(self):
        with self.assertRaises(LookupError):
            SR.run(self.project)
        SR.declare(self.project, ["saipen-no-such-program-t1658", "x"])
        with self.assertRaises(LookupError):
            SR.run(self.project)
        self.assertEqual(list((self.project / SR.RECORD_DIR_REL).glob("*-*.json")), [])


class RecordTests(_Project):
    def test_the_engine_run_leaves_a_typed_record(self):
        SR.declare(self.project, self.command)
        written = self.record()
        record = json.loads((self.project / written["path"]).read_text(encoding="utf-8"))
        self.assertEqual(record, written["record"])
        self.assertTrue(written["path"].startswith(SR.RECORD_DIR_REL + "/"))
        self.assertEqual(record["command"], self.command)
        self.assertEqual(record["command_sha256"], SR.command_digest(self.command))
        self.assertEqual((record["status"], record["exit_code"], record["verdict"]),
                         ("PASS", 0, "PASS"))
        totals = record["totals"]
        self.assertEqual((totals["ran"], totals["passed"], totals["red"], totals["skipped"]),
                         (5022, 4999, 0, 23))
        self.assertEqual(record["subject"], SR.subject(self.project))
        self.assertFalse(record["tree_changed_during_run"])
        self.assertNotIn(b"\r\n", (self.project / written["path"]).read_bytes())
        cited = SR.parse_evidence(SR.evidence_line(written))
        self.assertEqual((cited["record"], cited["sha"]), (written["path"], written["sha256"]))

    def test_a_red_run_is_a_fail_record(self):
        self.suite("2 failed, 3 passed in 0.10s", code=1)
        SR.declare(self.project, self.command)
        record = self.record()["record"]
        self.assertEqual((record["verdict"], record["exit_code"], record["totals"]["red"]),
                         ("FAIL", 1, 2))
        self.assertIn("suite 5 (red 2)", self.validation())

    def test_a_green_exit_cannot_cover_a_red_summary(self):
        self.suite("1 failed, 3 passed in 0.10s", code=0)
        SR.declare(self.project, self.command)
        record = self.record()["record"]
        self.assertEqual(record["verdict"], "FAIL")
        self.assertIn("exit code 0 contradicts the red in the summary", record["problems"])

    def test_an_unknown_runner_gets_its_exit_code_and_no_invented_totals(self):
        self.suite("all 17 specs fine", code=0)
        SR.declare(self.project, self.command)
        record = self.record()["record"]
        self.assertEqual((record["verdict"], record["totals"]), ("PASS", None))
        validation = self.validation()
        self.assertIn("suite exit 0", validation)
        self.assertNotIn("17", validation)

    def test_a_suite_that_does_not_finish_is_a_timeout(self):
        (self.project / "suite.py").write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
        SR.declare(self.project, self.command, timeout=2)
        record = self.record()["record"]
        self.assertEqual((record["status"], record["verdict"], record["exit_code"]),
                         ("TIMEOUT", "FAIL", None))
        self.assertIn("suite TIMEOUT", self.validation())


class DigestTests(_Project):
    def test_validation_carries_the_totals_without_the_unit_family(self):
        self.assertFalse((self.project / "tools" / "saipen_engine" / "test_runner.py").exists())
        self.assertNotIn("suite", self.validation(), "nothing declared, nothing claimed")
        SR.declare(self.project, self.command)
        written = self.record()
        facts = RS.canonical_facts(self.project)
        self.assertEqual(facts["test_groups"], [], "the unit family is not this project's")
        self.assertEqual(
            facts["suite_groups"],
            [{"status": "PASS", "verdict": "PASS", "exit_code": 0,
              "ran": 5022, "red": 0, "skipped": 23}],
        )
        self.assertIn(written["path"], facts["evidence"])
        validation = self.validation()
        self.assertIn("suite 5022 (red 0, skipped 23)", validation)
        text = RS.digest_from_facts({**facts, "phase": "DONE"}, reason="status", language="en")
        self.assertEqual(RS.response_errors(text, response_class=RS.COMPACT_FINAL), [])

    def test_a_number_written_in_the_log_never_reaches_validation(self):
        SR.declare(self.project, self.command)
        digest = SR.command_digest(self.command)[:16]
        self.log("verify -> PASS -- full suite 4999 passed, 23 skipped, 0 failed")
        self.log(
            f"{SR.MARKER} PASS runner:pytest ran:9999 red:0 skipped:0 exit:0 command:{digest} "
            f"record:{SR.RECORD_DIR_REL}/{digest}-20261007T000000000000Z.json sha256:{'a' * 64}"
        )
        self.assertEqual(RS.canonical_facts(self.project)["suite_groups"], [])
        validation = self.validation()
        for number in ("4999", "9999", "suite"):
            self.assertNotIn(number, validation)

    def test_the_record_of_a_narrower_command_is_not_the_suite(self):
        SR.declare(self.project, [*self.command, "tests/one"])
        self.record()
        SR.declare(self.project, self.command)
        self.assertIsNone(SR.newest_record(self.project))
        self.assertNotIn("suite", self.validation())

    def test_a_record_that_is_not_the_engines_shape_is_ignored(self):
        SR.declare(self.project, self.command)
        written = self.record()
        path = self.project / written["path"]
        good = json.loads(path.read_text(encoding="utf-8"))
        for damage in (
            {"kind": "notes"},
            {"schema": 99},
            {"status": "GREEN"},
            {"totals": {"ran": "5022", "red": 0, "skipped": 0}},
            {"totals": {"ran": -1, "red": 0, "skipped": 0}},
            {"totals": {"ran": True, "red": 0, "skipped": 0}},
            {"exit_code": "0"},
            {"subject": None},
            {"command": [*self.command, "x"]},
        ):
            with self.subTest(damage=damage):
                path.write_text(json.dumps({**good, **damage}), encoding="utf-8")
                self.assertIsNone(SR.newest_record(self.project))
                self.assertNotIn("suite", self.validation())
        path.write_text("{not json", encoding="utf-8")
        self.assertIsNone(SR.newest_record(self.project))

    def test_a_malformed_facts_carrier_renders_no_number(self):
        for groups in (None, "suite 9 (red 0)", [], ["x"], [{"ran": "9", "red": "0"}],
                       [{"ran": True, "red": False}], [{"ran": -3, "red": 0}],
                       [{"exit_code": "0"}], [{"exit_code": True}]):
            with self.subTest(groups=groups):
                self.assertEqual(RS._suite_validation(groups), "")
        self.assertEqual(RS._suite_validation([{"ran": 4, "red": 0, "skipped": 0}]),
                         " | suite 4 (red 0)")


class SubjectTests(_Project):
    def current(self) -> bool:
        return SR.current_record(self.project) is not None

    def test_the_record_follows_the_tree_it_tested(self):
        SR.declare(self.project, self.command)
        self.record()
        self.assertTrue(self.current())
        (self.project / ".saipen" / "LOG.md").write_text("- rewritten\n", encoding="utf-8")
        self.assertTrue(self.current(), "canonical state is outside the subject")
        _git(self.project, "add", "-A")
        self.assertTrue(self.current(), "staging the same bytes changes nothing")
        _git(self.project, "commit", "-q", "-m", "ship")
        self.assertTrue(self.current(), "committing the same bytes changes nothing")
        for name, edit in (
            ("a tracked file is edited", lambda p: p.write_text("x = 2\n", encoding="utf-8")),
            ("a tracked file is deleted", lambda p: p.unlink()),
        ):
            with self.subTest(name):
                target = self.project / "evidence.md"
                before = target.read_bytes()
                edit(target)
                self.assertFalse(self.current())
                self.assertNotIn("suite", self.validation())
                target.write_bytes(before)
                self.assertTrue(self.current(), "the same bytes are the same tree again")
        (self.project / "new_module.py").write_text("y = 1\n", encoding="utf-8")
        self.assertFalse(self.current(), "an untracked file is part of the tree")
        (self.project / "new_module.py").write_text("y = 2\n", encoding="utf-8")
        first = SR.subject(self.project)
        (self.project / "new_module.py").write_text("y = 3\n", encoding="utf-8")
        self.assertNotEqual(first, SR.subject(self.project), "by content, not by name")

    def test_a_git_record_is_never_answered_by_hashing_the_whole_tree(self):
        from saipen_engine import core_unit

        SR.declare(self.project, self.command)
        self.record()
        with mock.patch.object(SR, "_git_subject", return_value=None), mock.patch.object(
            core_unit, "tree_fingerprint", side_effect=AssertionError("hashed")
        ):
            self.assertIsNone(SR.current_record(self.project))
            self.assertEqual(RS.canonical_facts(self.project)["suite_groups"], [])

    def test_a_name_outside_ascii_is_hashed_like_any_other(self):
        target = self.project / "тест файл.py"
        target.write_text("a = 1\n", encoding="utf-8")
        first = SR.subject(self.project)
        self.assertTrue(first.startswith("git:"), first)
        target.write_text("a = 2\n", encoding="utf-8")
        second = SR.subject(self.project)
        self.assertTrue(second.startswith("git:"), second)
        self.assertNotEqual(first, second)
        _git(self.project, "add", "-A")
        _git(self.project, "commit", "-q", "-m", "name")
        self.assertEqual(second, SR.subject(self.project))

    def test_an_ignored_file_is_outside_the_subject(self):
        (self.project / ".gitignore").write_text("cache/\n", encoding="utf-8")
        _git(self.project, "add", "-A")
        _git(self.project, "commit", "-q", "-m", "ignore")
        before = SR.subject(self.project)
        (self.project / "cache").mkdir()
        (self.project / "cache" / "junk.bin").write_bytes(b"\x00" * 16)
        self.assertEqual(before, SR.subject(self.project))

    def test_what_the_suite_itself_leaves_does_not_stale_its_own_record(self):
        (self.project / "suite.py").write_text(
            "import pathlib\npathlib.Path('report.xml').write_text('<r/>')\n"
            f"print({MEASURED!r})\n",
            encoding="utf-8",
        )
        SR.declare(self.project, self.command)
        record = self.record()["record"]
        self.assertTrue(record["tree_changed_during_run"])
        self.assertTrue(self.current())


class SubjectWithoutGitTests(_Project):
    git = False

    def test_a_tree_without_git_is_still_identified_by_content(self):
        if SR._git_subject(self.project) is not None:
            self.skipTest("the temporary directory sits inside a git work tree")
        first = SR.subject(self.project)
        self.assertTrue(first.startswith("tree:"), first)
        SR.declare(self.project, self.command)
        self.record()
        self.assertIsNotNone(SR.current_record(self.project))
        (self.project / "evidence.md").write_text("changed\n", encoding="utf-8")
        self.assertIsNone(SR.current_record(self.project))


class CommandTests(_Project):
    def cli(self, *args: str, **declared: str):
        # The working directory is the fixture, never the repository the tests
        # run from: a call whose explicit root is lost (T-1661 measured one
        # behind the `--` of `declare`) then still cannot write here.
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
        env["PWD"] = str(self.project)
        env.update(declared)
        proc = subprocess.run(
            [sys.executable, "-B", str(ENGINE), *args],
            stdin=subprocess.DEVNULL, capture_output=True, env=env, cwd=str(self.project),
            timeout=300, check=False,
        )
        return proc.returncode, proc.stdout.decode("utf-8")

    def test_the_writing_actions_are_execution_and_the_rest_read(self):
        for line, want in (
            ("saipen test", "DIAGNOSTIC"),
            ("saipen test suite", "DIAGNOSTIC"),
            ("saipen test suite status", "DIAGNOSTIC"),
            ("saipen test suite declare -- python -m pytest -q", "EXECUTION"),
            ("saipen test suite run T-12", "EXECUTION"),
            ("saipen tt suite run", "EXECUTION"),
        ):
            with self.subTest(line):
                self.assertEqual(classify_tokens(line.split()), want)

    def test_declare_then_run_then_the_digest_states_the_totals(self):
        root = ["--project-root", str(self.project), "--json"]
        rc, out = self.cli("test", "suite", "run", *root)
        refused = json.loads(out)
        self.assertEqual((rc, refused["code"], refused["suite"]),
                         (1, "VALIDATION_FAILED", "NOT_DECLARED"), out)
        self.assertEqual(refused["canonical_next_command"],
                         "saipen test suite declare -- <command>")
        rc, out = self.cli("test", "suite", "declare", *root)
        usage = json.loads(out)
        self.assertEqual((rc, usage["code"]), (2, "VALIDATION_FAILED"), out)
        self.assertEqual(usage["usage"], list(SR.USAGE))
        rc, out = self.cli("test", "suite", "declare", *root, "--", *self.command)
        declared = json.loads(out)
        self.assertEqual((rc, declared["code"]), (0, "SUITE_DECLARED"), out)
        rc, out = self.cli("test", "suite", "run", *root)
        ran = json.loads(out)
        self.assertEqual((rc, ran["code"], ran["verdict"]), (0, "SUITE_RECORDED", "PASS"), out)
        self.assertEqual(ran["totals"]["ran"], 5022)
        log = (self.project / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("suite declared -- command:" + declared["command_sha256"][:16], log)
        self.assertIn(f"{SR.MARKER} PASS runner:pytest ran:5022 red:0 skipped:23 exit:0", log)
        self.assertIn(f"record:{ran['record']} sha256:{ran['sha256']}", log)
        rc, out = self.cli("test", "suite", *root)
        status = json.loads(out)
        self.assertEqual((rc, status["declared"], status["current"]), (0, True, True), out)
        rc, out = self.cli(
            "response", "digest", "--project-root", str(self.project), "--reason", "status"
        )
        self.assertEqual(rc, 0, out)
        self.assertIn("suite 5022 (red 0, skipped 23)", out)

    def test_a_red_suite_answers_nonzero_and_shows_its_summary(self):
        self.suite("2 failed, 3 passed in 0.10s", code=1)
        root = ["--project-root", str(self.project), "--json"]
        self.cli("test", "suite", "declare", *root, "--", *self.command)
        rc, out = self.cli("test", "suite", "run", *root)
        ran = json.loads(out)
        self.assertEqual((rc, ran["ok"], ran["verdict"]), (1, False, "FAIL"), out)
        self.assertIn("2 failed, 3 passed", ran["stdout_tail"])

    def test_a_record_that_cannot_be_written_is_a_refusal_not_a_traceback(self):
        SR.declare(self.project, self.command)
        with mock.patch.object(SR, "write_record", side_effect=ValueError("unsafe topology")):
            payload, code = SR.cli(self.project, ["run"], agent="tester")
        self.assertEqual((code, payload["code"], payload["suite"], payload["detail"]),
                         (1, "IO_FAILED", "NOT_RECORDED", "unsafe topology"))
        log = (self.project / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertNotIn(SR.MARKER, log)

    def test_every_refusal_carries_a_registered_code_and_a_runnable_usage(self):
        """The two contracts the declared family holds every engine module to,
        asked of this one directly: a refusal code outside REGISTRY error_codes
        is a traceback waiting in `Result`, and a usage line that opens with
        the command word and is no command is an instruction nobody can run."""
        from saipen_engine import guard_events
        from saipen_engine.errors import CODES

        SR.declare(self.project, ["saipen-no-such-program-t1658"])
        answers = [
            SR.cli(self.project, ["bogus"], agent="tester"),
            SR.cli(self.project, ["declare"], agent="tester"),
            SR.cli(self.project, ["run", "not-a-ticket"], agent="tester"),
            SR.cli(self.project, ["run"], agent="tester"),
        ]
        (self.project / SR.DECLARATION_REL).write_text("{", encoding="utf-8")
        answers += [
            SR.cli(self.project, [], agent="tester"),
            SR.cli(self.project, ["run"], agent="tester"),
        ]
        for payload, code in answers:
            with self.subTest(payload=payload):
                self.assertFalse(payload["ok"])
                self.assertNotEqual(code, 0)
                self.assertIn(payload["code"], CODES)
        self.assertEqual([p.get("suite") for p, _c in answers[3:]],
                         ["NOT_RUN", "DECLARATION_INVALID", "DECLARATION_INVALID"])
        for form in SR.USAGE:
            typed = form.replace("<command>", "T-1").replace("<T-###>", "T-1")
            self.assertIsNotNone(guard_events._saipen_cli_verb(typed), form)

    def test_a_dry_run_and_a_read_only_session_write_nothing(self):
        root = ["--project-root", str(self.project), "--json"]
        rc, out = self.cli("test", "suite", "declare", "--dry-run", *root, "--", *self.command)
        self.assertEqual((rc, json.loads(out)["code"]), (0, "SUITE_DECLARE_PLAN"), out)
        rc, _out = self.cli(
            "test", "suite", "declare", *root, "--", *self.command, SAIPEN_CAPABILITY="read-only"
        )
        self.assertNotEqual(rc, 0)
        self.assertFalse((self.project / SR.RECORD_DIR_REL).exists())


if __name__ == "__main__":
    unittest.main()
