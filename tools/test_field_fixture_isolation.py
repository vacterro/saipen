"""Field-fixture ledger isolation (T-1370, SRC-049:R009).

WHAT THIS REPRODUCES
--------------------
The 16.09.26 harness defect, exactly as measured:

    main repository            the project the harness was launched from
    fixture worktree           the sandbox the session was supposed to use
    subprocess cwd = fixture   what `subprocess` sets
    PWD = main repository      what `subprocess` does NOT reset
    weak model                 resolved its work against PWD, not cwd
    saipen start               therefore ran against the WRONG project
    -> SRC-047/T-1368, SRC-048/T-1369 and src/app.py minted in the repository

The host binary is not what these tests drive -- they drive the measured
RESOLUTION RULE, in a stand-in host of four lines: chdir to `$PWD`, then run
`saipen start`. That is precisely what the session transcripts show the model's
shell doing, and it is the only part of the host this defect lives in.

WHY IT ASSERTS THE LEDGER, NOT THE FILE
---------------------------------------
"the docstring landed in the fixture" is a weak claim: a session can edit the
right file and still mint a receipt, a ticket and three canonical events in the
wrong project. The pass condition here is therefore CANONICAL LEDGER
ISOLATION -- `STATE.md`, `BOARD.md`, `LOG.md` and `intake/index.json` of the
project that was NOT targeted must be byte-identical afterwards.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import t1363_field_polygon as polygon  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.journal import ensure_project_lineage  # noqa: E402

#: Every canonical carrier a wrong-project session can damage. `intake/index.json`
#: is on the list because the incident's first durable trace was a RECEIPT, and a
#: check that watched only STATE/BOARD/LOG would have called that run clean.
CANONICAL = ("STATE.md", "BOARD.md", "LOG.md", "intake/index.json")

TASK = "add a one-line docstring to the top of src/app.py"

#: The stand-in host. It does the one thing the transcripts prove the real
#: session did: trust `PWD` over the working directory it was given.
STAND_IN_HOST = (
    "import os, subprocess, sys\n"
    "os.chdir(os.environ['PWD'])\n"
    "sys.exit(subprocess.run([sys.executable, sys.argv[1], 'start', sys.argv[2],\n"
    "                         '--json']).returncode)\n"
)


def canonical_hashes(root: Path) -> dict:
    out = {}
    for name in CANONICAL:
        path = root / ".saipen" / name
        out[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return out


class LedgerIsolationTests(unittest.TestCase):
    def make_project(self, label: str) -> Path:
        base = Path(tempfile.mkdtemp(prefix=f"saipen-{label}-"))
        self.addCleanup(lambda: shutil.rmtree(base, ignore_errors=True))
        project = base / label
        (project / ".saipen").mkdir(parents=True)
        (project / "src").mkdir(parents=True)
        (project / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
        (project / ".saipen" / "STATE.md").write_text(
            "---\nphase: DONE\ntask: none\n"
            'next_action: "saipen continue"\n'
            'blocker: ""\ntransition_from: DONE\n'
            "saipen_version: 8\nschema_version: 3\nlast_event: 1\n"
            "style_contract: ded-4ae736e4\n"
            f'saipen_home: "{str(ROOT).replace(chr(92), chr(92) * 2)}"\n'
            "agent: tester\nrequires:\n  - filesystem\n  - python\n"
            "mode: full\n"
            'updated: "2026-09-16T00:00:00Z"\n---\n',
            encoding="utf-8",
        )
        (project / ".saipen" / "BOARD.md").write_text(
            "## DOING\n## TODO\n## DONE\n## BLOCKED\n", encoding="utf-8"
        )
        (project / ".saipen" / "LOG.md").write_text(
            "- 16.09.26 00:00 [E-001] [agent: tester] RUN: fixture -> PASS\n",
            encoding="utf-8",
        )
        ensure_project_lineage(project)
        polygon._git_worktree(project)
        return project

    def run_stand_in_host(self, *, cwd: Path, pwd: Path) -> subprocess.CompletedProcess:
        script = Path(tempfile.mkdtemp(prefix="saipen-host-")) / "host.py"
        self.addCleanup(lambda: shutil.rmtree(script.parent, ignore_errors=True))
        script.write_text(STAND_IN_HOST, encoding="utf-8")
        env = {**os.environ, "PWD": str(pwd), "PYTHONDONTWRITEBYTECODE": "1"}
        for key in ("SAIPEN_PROJECT_ROOT", "SAIPEN_PROJECT_LINEAGE", "SAIPEN_SKILL_ROOT"):
            env.pop(key, None)
        return subprocess.run(
            [sys.executable, str(script), str(ROOT / "tools" / "saipen.py"), TASK],
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )

    def owning_ledger(self, project: Path) -> tuple[list[str], int]:
        board = parse_board((project / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))
        index = json.loads(
            (project / ".saipen" / "intake" / "index.json").read_text(encoding="utf-8-sig")
        ) if (project / ".saipen" / "intake" / "index.json").is_file() else {"active": {}}
        return sorted(board["tickets"]), len(index.get("active", {}))

    def test_red_inherited_pwd_mints_into_the_other_project(self):
        """The measured defect: cwd says fixture, PWD says repository."""
        repository = self.make_project("repository")
        fixture = self.make_project("fixture")
        repo_before = canonical_hashes(repository)
        fixture_before = canonical_hashes(fixture)

        self.run_stand_in_host(cwd=fixture, pwd=repository)

        self.assertNotEqual(
            canonical_hashes(repository),
            repo_before,
            "the RED control did not reproduce: the wrong project was untouched",
        )
        self.assertEqual(
            canonical_hashes(fixture),
            fixture_before,
            "the RED control is wrong: the fixture changed too",
        )
        tickets, receipts = self.owning_ledger(repository)
        self.assertTrue(tickets, "no ticket was minted in the wrong project")
        self.assertEqual(receipts, 1)
        self.assertEqual(self.owning_ledger(fixture), ([], 0))

    def test_green_bound_pwd_keeps_the_other_project_byte_identical(self):
        """The fix: the child's environment agrees with its directory."""
        repository = self.make_project("repository")
        fixture = self.make_project("fixture")
        repo_before = canonical_hashes(repository)
        fixture_before = canonical_hashes(fixture)

        self.run_stand_in_host(cwd=fixture, pwd=fixture)

        self.assertEqual(
            canonical_hashes(repository),
            repo_before,
            "canonical ledger isolation broken: the untargeted project changed",
        )
        self.assertNotEqual(
            canonical_hashes(fixture),
            fixture_before,
            "the fixture did no work, so this proves nothing",
        )
        tickets, receipts = self.owning_ledger(fixture)
        self.assertTrue(tickets, "the fixture minted no Work")
        self.assertEqual(receipts, 1)
        # And the claim a model makes is never the proof: the FIXTURE ledger is.
        self.assertEqual(self.owning_ledger(repository), ([], 0))

    def test_the_harness_environment_strips_every_stale_project_carrier(self):
        """`_host_env` is the fix's single point of truth -- pin its contract."""
        fixture = self.make_project("fixture")
        polluted = {
            "SAIPEN_PROJECT_ROOT": str(ROOT),
            "SAIPEN_PROJECT_LINEAGE": "stale",
            "SAIPEN_AGENT": "someone-else",
            "SAIPEN_SKILL_ROOT": str(ROOT),
            "OLDPWD": str(ROOT),
            "INIT_CWD": str(ROOT),
            "PWD": str(ROOT),
        }
        saved = {key: os.environ.get(key) for key in polluted}
        os.environ.update(polluted)
        try:
            env = polygon._host_env(fixture)
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        self.assertEqual(env["PWD"], str(fixture))
        for key in (
            "SAIPEN_PROJECT_ROOT",
            "SAIPEN_PROJECT_LINEAGE",
            "SAIPEN_AGENT",
            "SAIPEN_SKILL_ROOT",
            "OLDPWD",
            "INIT_CWD",
        ):
            self.assertNotIn(key, env, f"{key} survived into the child environment")

    def test_the_polygon_watches_every_canonical_carrier(self):
        """A watcher blind to `intake/index.json` would have called this clean."""
        fixture = self.make_project("fixture")
        watched = set(polygon._canonical_hashes(fixture))
        self.assertEqual(watched, set(CANONICAL), "the polygon stopped watching a carrier")


class MatrixCompletenessTests(unittest.TestCase):
    """The matrix must build every condition it claims (T-1367, SRC-051 §11).

    `conditions()` built eight while the matrix named nine, and its own
    docstring said "eight", so a run that printed a row per built condition
    looked complete while the `--file` transport -- the one BOOT offers for a
    request the shell cannot carry -- was never driven by a model at all. The
    defect class: a matrix whose coverage is whatever the builder happened to
    write, checked against nothing.
    """

    #: Verbatim from SRC-051 section 11, in its order.
    DECLARED = (
        "healthy",
        "operator_decision",
        "safety_valve",
        "repairable_debt",
        "captured_unprojected",
        "already_done",
        "foreign_owner",
        "windows_path_task",
        "long_file_task",
    )

    def test_the_declared_matrix_still_equals_the_source(self):
        self.assertEqual(polygon.CONDITION_NAMES, self.DECLARED)

    def test_every_declared_condition_has_a_builder(self):
        self.assertEqual(set(polygon.condition_builders()), set(self.DECLARED))

    def test_a_builder_the_matrix_does_not_name_is_refused(self):
        """The check runs inside the builder, so it cannot be skipped."""
        original = polygon.CONDITION_NAMES
        polygon.CONDITION_NAMES = original[:-1]
        try:
            with self.assertRaises(ValueError) as caught:
                polygon.condition_builders()
        finally:
            polygon.CONDITION_NAMES = original
        self.assertIn("long_file_task", str(caught.exception))

    def test_the_long_request_routes_to_the_file_transport(self):
        """Not merely long -- long enough that the guard names `--file`."""
        from saipen_engine import guard_events

        payload = polygon.LONG_TASK
        self.assertGreater(len(payload.encode("utf-8")), guard_events.MAX_INGRESS_HEX_PAYLOAD)
        self.assertEqual(
            guard_events.ingress_rewrite(f"saipen start '{payload}'"),
            "saipen start --file <path>",
        )

    def test_an_unreadable_transcript_is_not_a_perfect_run(self):
        """Measured on `long_file_task`: the session drove the whole chain and
        closed T-1 at E-13 -- its own fixture ledger proves it -- while the
        host's JSON stream gave the harness nothing. The old metrics answered
        `protocol_commands_before_productive: 0`, which IS the strong
        acceptance number, so an unreadable transcript scored perfect."""
        blind = polygon.measure([], measured=False)
        self.assertEqual(blind["measurement"], polygon.UNMEASURED)
        for field in (
            "tools",
            "first_saipen_command",
            "protocol_commands_before_productive",
            "productive_action",
            "refusal_sequence",
            "repeated_refusal",
        ):
            self.assertIsNone(blind[field], field)

    def test_a_readable_transcript_still_measures(self):
        """The known-good control: the same call with events present."""
        seen = polygon.measure(
            [{"tool": "bash", "status": "completed",
              "input": {"command": "saipen start 'x'"}, "output": "", "error": ""}],
            measured=True,
        )
        self.assertEqual(seen["measurement"], polygon.MEASURED)
        self.assertEqual(seen["first_saipen_command"], "saipen start 'x'")
        self.assertEqual(seen["protocol_commands_before_productive"], 1)

    def test_looking_at_the_project_is_not_doing_the_work(self):
        """SRC-051 §11: status/read/git-status/test-only shell is not
        productivity. The old rule counted every non-`saipen` shell line, so
        `git status` scored a session productive at command one."""
        for inert in (
            "git status --porcelain",
            "git log --oneline -5",
            "ls -la src",
            "cat src/app.py",
            "pwd",
            "grep -rn docstring src",
            "python -m unittest discover -s tools",
            "ruff check tools/",
            "Get-Content src/app.py",
            "saipen status --json",
        ):
            self.assertFalse(polygon.productive_shell(inert), inert)
        for real in (
            "python -c \"open('src/app.py','w').write('x')\"",
            "sed -i '1i \"\"\"doc.\"\"\"' src/app.py",
            "git commit -m 'doc'",
            "npm run build",
        ):
            self.assertTrue(polygon.productive_shell(real), real)

    def test_an_inert_shell_line_does_not_score_a_session_productive(self):
        """The known-bad input the rule exists for, through `measure`."""
        looked = polygon.measure(
            [{"tool": "bash", "status": "completed",
              "input": {"command": "git status"}, "output": "", "error": ""}],
            measured=True,
        )
        self.assertIsNone(looked["productive_action"])

    def test_a_console_codec_cannot_kill_the_run(self):
        """The known-bad input: a cp1251 stream and a u-umlaut.

        That pair ended a nine-session matrix at session five with
        UnicodeEncodeError and threw away four measured sessions.
        """
        import io

        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="cp1251", errors="strict")
        with self.assertRaises(UnicodeEncodeError):
            stream.write("für")
            stream.flush()

        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="cp1251", errors="strict")
        polygon.force_utf8_console(stream)
        stream.write("für")
        stream.flush()
        self.assertIn("f", raw.getvalue().decode("utf-8"))

    def test_the_report_is_on_disk_before_the_next_session_can_crash(self):
        """Live model time is the expensive part; a run that persists only at
        the end loses all of it to any crash in the loop."""
        out = Path(tempfile.mkdtemp(prefix="polygon-out-"))
        self.addCleanup(shutil.rmtree, out, True)
        report = {"sessions": [{"condition": "healthy", "note": "für"}]}
        self.assertTrue(polygon._write_report(str(out), report))
        written = json.loads((out / "polygon.json").read_text(encoding="utf-8"))
        self.assertEqual(written["sessions"][0]["note"], "für")
        self.assertFalse(polygon._write_report(None, report))

    def test_isolation_separates_contamination_from_a_concurrent_operator(self):
        """Measured 2026-09-16: an operator checkpointing in the main
        repository while the matrix ran scored a clean `healthy` session
        isolation=FAIL. "this repository moved" answers two questions."""
        repo = Path("V:/repo")
        clean = {
            "canonical_changed": ["BOARD.md"],
            "repository_canonical_changed": [],
            "owner_repository": {"T-1": ["V:/fixture"]},
        }
        self.assertEqual(polygon.isolation_verdict(clean, repo), polygon.ISOLATION_PASS)

        contaminated = {
            "canonical_changed": ["BOARD.md"],
            "repository_canonical_changed": ["BOARD.md", "LOG.md"],
            "owner_repository": {"T-1": ["V:/fixture", str(repo)]},
        }
        self.assertEqual(polygon.isolation_verdict(contaminated, repo), polygon.ISOLATION_FAIL)

        concurrent = {
            "canonical_changed": ["BOARD.md"],
            "repository_canonical_changed": ["LOG.md"],
            "owner_repository": {"T-1": ["V:/fixture"]},
        }
        self.assertEqual(
            polygon.isolation_verdict(concurrent, repo), polygon.ISOLATION_INCONCLUSIVE
        )

        nothing = {
            "canonical_changed": [],
            "repository_canonical_changed": [],
            "owner_repository": {},
        }
        self.assertEqual(polygon.isolation_verdict(nothing, repo), polygon.ISOLATION_FAIL)

    def test_each_condition_gets_the_task_its_name_promises(self):
        self.assertEqual(polygon.CONDITION_TASKS["long_file_task"], polygon.LONG_TASK)
        self.assertEqual(polygon.CONDITION_TASKS["windows_path_task"], polygon.FIELD_TASK)
        for name in self.DECLARED:
            if name not in polygon.CONDITION_TASKS:
                self.assertEqual(polygon.CONDITION_TASKS.get(name, polygon.SIMPLE_TASK),
                                 polygon.SIMPLE_TASK)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
