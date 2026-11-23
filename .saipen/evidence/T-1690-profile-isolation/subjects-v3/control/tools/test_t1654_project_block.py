"""T-1654 / SRC-188: a project's own SAIPEN block must not steer an agent off the runtime.

An older generation told the agent that created a project to write a block
between `<!-- SAIPEN:BEGIN -->` and `<!-- SAIPEN:END -->` into the project's
`AGENTS.md`. The block measured in a managed project on 2026-10-07 (the
fixture here, byte for byte) names the operator's per-user skill directory as
required reading and says `Path missing (new machine)? clone
github.com/vacterro/saipen`. No command wrote, refreshed, reported or removed
a block inside a project, so an account that cannot read the named path was
told to clone the public repository, and the machine runtime was never tried.

Pinned here:

- one command reports a block of another generation and names one repair;
- the repair replaces the bytes from the opening marker to the closing marker
  and nothing else: every byte outside them is identical afterwards, whatever
  its encoding or line ending;
- the current block is relocatable: it names no absolute path, only the
  launcher order (PATH, the home `STATE.md` records, the machine runtime), and
  it never tells the agent to clone;
- a file whose markers do not form exactly one pair is refused and left alone;
- text outside the markers is the operator's: reported, never rewritten.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_t1614_future_gate as H  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

ENGINE = TOOLS / "saipen.py"
FIXTURE = ROOT / "tests" / "fixtures" / "t1654-legacy-block" / "AGENTS.md.measured"
BEGIN = b"<!-- SAIPEN:BEGIN -->"
END = b"<!-- SAIPEN:END -->"
REPAIR = "saipen host instructions repair"

#: Bytes no decoder agrees on: a UTF-8 BOM, a cp1251 letter that is not valid
#: UTF-8, CRLF and bare LF mixed, and no final newline.
PREFIX = b"\xef\xbb\xbf# Rules of this project\r\n\r\nKeep the \xe4 byte.\nSecond line.\r\n\r\n"
SUFFIX = b"\r\n\r\n## After the block\nlast line without a newline \xe4"


def setUpModule() -> None:
    isolate_host_session()


def block_owner():
    from saipen_engine import project_block

    return project_block


def legacy_block() -> bytes:
    raw = FIXTURE.read_bytes()
    return raw[raw.index(BEGIN) : raw.index(END) + len(END)]


class _Project(unittest.TestCase):
    def setUp(self) -> None:
        base, self.project = H._project()
        self.addCleanup(shutil.rmtree, base, True)
        self.base = base

    def put(self, name: str, data: bytes) -> Path:
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def measured(self) -> Path:
        return self.put("AGENTS.md", FIXTURE.read_bytes())

    def row(self, report: dict, name: str = "AGENTS.md") -> dict:
        rows = [item for item in report.get("files") or [] if item.get("file") == name]
        self.assertEqual(len(rows), 1, report)
        return rows[0]


# ------------------------------------------------------------ the fixture itself


class MeasuredBlockTests(unittest.TestCase):
    """The fixture is the block as it was measured, not a paraphrase of it."""

    def test_the_fixture_is_the_measured_bytes(self):
        raw = FIXTURE.read_bytes()
        self.assertEqual(len(raw), 386)
        self.assertNotIn(b"\r", raw)
        block = legacy_block()
        self.assertEqual(len(block), 385)
        self.assertIn(b"## saipen protocol (any agent)", block)
        self.assertIn(b"clone github.com/vacterro/saipen", block)
        self.assertIn(b"\\.agents\\skills\\saipen\\BOOT.md", block)


# ------------------------------------------------------------------ the report


class ReportTests(_Project):
    def test_the_measured_block_is_reported_as_another_generation(self):
        self.measured()
        report = block_owner().status(self.project)
        self.assertFalse(report["ok"])
        self.assertEqual(report["code"], "PROJECT_BLOCK_STALE")
        self.assertEqual(report["action"], REPAIR)
        row = self.row(report)
        self.assertEqual(row["status"], "STALE")
        reasons = " | ".join(row["reasons"])
        self.assertIn("clone", reasons)
        self.assertIn("absolute path", reasons)

    def test_a_project_without_a_block_has_nothing_to_repair(self):
        report = block_owner().status(self.project)
        self.assertTrue(report["ok"])
        self.assertEqual(report["code"], "PROJECT_BLOCK_ABSENT")
        self.assertIsNone(report["action"])
        self.put("AGENTS.md", b"# Rules\n\nNo protocol text here.\n")
        report = block_owner().status(self.project)
        self.assertTrue(report["ok"])
        self.assertEqual(report["code"], "PROJECT_BLOCK_ABSENT")
        self.assertEqual(self.row(report)["status"], "ABSENT")

    def test_the_current_block_reads_current_in_either_line_ending(self):
        owner = block_owner()
        for newline in (b"\n", b"\r\n"):
            self.put("AGENTS.md", b"# Rules" + newline + owner.current_block(newline) + newline)
            report = owner.status(self.project)
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["code"], "PROJECT_BLOCK_CURRENT")
            self.assertIsNone(report["action"])

    def newer(self, extra: bytes = b"") -> bytes:
        owner = block_owner()
        mine = f"(project block {owner.BLOCK_REVISION})".encode()
        theirs = f"(project block {owner.BLOCK_REVISION + 1})".encode()
        block = owner.current_block(b"\n")
        self.assertEqual(block.count(mine), 1)
        closing = b"\n" + END
        return block.replace(mine, theirs).replace(
            closing, b"\nA sentence only the next revision has." + extra + closing
        )

    def test_a_block_of_a_newer_revision_is_left_alone(self):
        """Two installs of different generations reach one project. The older
        one must not rewrite what the newer one wrote, or each run of either
        undoes the other."""
        body = b"intro\n" + self.newer() + b"\n"
        path = self.put("AGENTS.md", body)
        owner = block_owner()
        report = owner.status(self.project)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["code"], "PROJECT_BLOCK_NEWER")
        self.assertIsNone(report["action"])
        self.assertEqual(self.row(report)["status"], "NEWER")
        fixed = owner.repair(self.project)
        self.assertEqual(fixed["written"], [])
        self.assertEqual(path.read_bytes(), body)

    def test_a_higher_number_does_not_excuse_a_clone_or_a_private_path(self):
        owner = block_owner()
        for extra in (
            b"\nPath missing? clone github.com/vacterro/saipen.",
            b"\nNever clone twice; clone github.com/vacterro/saipen once.",
            b"\nRead C:\\Users\\somebody\\tools\\BOOT.md first.",
        ):
            with self.subTest(extra):
                path = self.put("AGENTS.md", self.newer(extra) + b"\n")
                report = owner.status(self.project)
                self.assertEqual(report["code"], "PROJECT_BLOCK_STALE", report)
                fixed = owner.repair(self.project)
                self.assertEqual(fixed["code"], "PROJECT_BLOCK_REPAIRED", fixed)
                self.assertEqual(path.read_bytes(), owner.current_block(b"\n") + b"\n")

    def test_the_same_revision_with_other_text_is_another_generation(self):
        owner = block_owner()
        edited = owner.current_block(b"\n").replace(b"LAUNCHER ORDER", b"LAUNCHER  ORDER")
        self.put("AGENTS.md", edited + b"\n")
        self.assertEqual(owner.status(self.project)["code"], "PROJECT_BLOCK_STALE")

    def test_a_directory_without_project_memory_is_not_judged(self):
        bare = self.base / "not-a-project"
        bare.mkdir()
        (bare / "AGENTS.md").write_bytes(FIXTURE.read_bytes())
        report = block_owner().status(bare)
        self.assertFalse(report["ok"])
        self.assertEqual(report["code"], "NOT_SAIPEN_PROJECT")
        fixed = block_owner().repair(bare)
        self.assertEqual(fixed["code"], "NOT_SAIPEN_PROJECT")
        self.assertEqual((bare / "AGENTS.md").read_bytes(), FIXTURE.read_bytes())

    def test_every_project_instruction_file_is_read(self):
        self.put("AGENTS.md", b"# Rules\n")
        self.put(".github/copilot-instructions.md", b"intro\n" + legacy_block() + b"\n")
        report = block_owner().status(self.project)
        self.assertEqual(report["code"], "PROJECT_BLOCK_STALE")
        self.assertEqual(self.row(report, ".github/copilot-instructions.md")["status"], "STALE")
        self.assertEqual(self.row(report, "AGENTS.md")["status"], "ABSENT")

    def test_a_clone_is_an_instruction_unless_the_same_clause_forbids_it(self):
        told = {
            b"Path missing (new machine)? clone github.com/vacterro/saipen.": True,
            b"No install? clone github.com/vacterro/saipen": True,
            b"Never guess. Then clone github.com/vacterro/saipen": True,
            b"never clone it by hand; clone github.com/vacterro/saipen instead": True,
            b"never clone or copy it, never clone saipen at all": False,
            b"never clone or download a copy of saipen": False,
            b"do not search for SAIPEN or clone it": False,
            b"nothing about copies here, saipen": False,
        }
        for line, expected in told.items():
            with self.subTest(line):
                self.put("AGENTS.md", b"# Rules\n" + line + b"\n")
                report = block_owner().status(self.project)
                kinds = [item["kind"] for item in report["outside_block"]]
                self.assertEqual("clone-instruction" in kinds, expected, report)

    def test_a_host_level_instruction_file_belongs_to_the_installer(self):
        """The same markers delimit the host-level block in a host's own
        configuration directory. When that directory is also a project, the
        block there is not this command's to judge or to replace."""
        home = self.base / "isolated-home"
        project = home / ".zcode"
        home.mkdir()
        shutil.move(str(self.project), str(project))
        body = b"intro\n" + legacy_block() + b"\n"
        (project / "AGENTS.md").write_bytes(body)
        owner = block_owner()
        with mock.patch.dict(os.environ, {"ZAICODE_HOME": str(home)}):
            report = owner.status(project)
            fixed = owner.repair(project)
        rows = [item for item in report["files"] if item["file"] == "AGENTS.md"]
        self.assertEqual(rows[0]["status"], "HOST_SURFACE", report)
        self.assertTrue(report["ok"])
        self.assertEqual(fixed["written"], [])
        self.assertEqual((project / "AGENTS.md").read_bytes(), body)
        with mock.patch.dict(os.environ, {"ZAICODE_HOME": str(self.base / "elsewhere")}):
            self.assertEqual(owner.status(project)["code"], "PROJECT_BLOCK_STALE")

    def test_an_unreadable_instruction_file_names_one_action(self):
        owner = block_owner()
        self.put("AGENTS.md", b"x" * 64)
        with mock.patch.object(owner, "MAX_BYTES", 16):
            report = owner.status(self.project)
        self.assertFalse(report["ok"])
        self.assertEqual(report["code"], "PROJECT_BLOCK_UNREADABLE")
        self.assertIn("AGENTS.md", report["action"])
        self.assertIn("saipen host instructions", report["action"])

    def test_text_outside_the_markers_is_reported_and_is_the_operators(self):
        body = (
            b"# Hand-written\n\n"
            b"- Skill home: `C:\\Users\\somebody\\.agents\\skills\\saipen\\` -- read BOOT.md\n"
            b"- Path missing? clone github.com/vacterro/saipen\n"
        )
        path = self.put("AGENTS.md", body)
        report = block_owner().status(self.project)
        self.assertEqual(report["code"], "PROJECT_BLOCK_ABSENT")
        kinds = {(item["file"], item["line"], item["kind"]) for item in report["outside_block"]}
        self.assertIn(("AGENTS.md", 3, "per-user-skill-home"), kinds)
        self.assertIn(("AGENTS.md", 4, "clone-instruction"), kinds)
        fixed = block_owner().repair(self.project)
        self.assertEqual(fixed["written"], [])
        self.assertEqual(path.read_bytes(), body)


# ------------------------------------------------------------------ the repair


class RepairTests(_Project):
    def test_red_then_green_on_the_measured_block(self):
        path = self.measured()
        owner = block_owner()
        fixed = owner.repair(self.project)
        self.assertTrue(fixed["ok"], fixed)
        self.assertEqual(fixed["code"], "PROJECT_BLOCK_REPAIRED")
        self.assertEqual([item["file"] for item in fixed["written"]], ["AGENTS.md"])
        self.assertEqual(path.read_bytes(), owner.current_block(b"\n") + b"\n")
        after = owner.status(self.project)
        self.assertTrue(after["ok"])
        self.assertEqual(after["code"], "PROJECT_BLOCK_CURRENT")
        self.assertEqual(after["outside_block"], [])

    def test_only_the_bytes_between_the_markers_change(self):
        owner = block_owner()
        for old in (legacy_block(), legacy_block().replace(b"\n", b"\r\n")):
            path = self.put("AGENTS.md", PREFIX + old + SUFFIX)
            fixed = owner.repair(self.project)
            self.assertEqual(fixed["code"], "PROJECT_BLOCK_REPAIRED", fixed)
            data = path.read_bytes()
            self.assertTrue(data.startswith(PREFIX))
            self.assertTrue(data.endswith(SUFFIX))
            middle = data[len(PREFIX) : len(data) - len(SUFFIX)]
            newline = b"\r\n" if b"\r\n" in old else b"\n"
            self.assertEqual(middle, owner.current_block(newline))
            self.assertTrue(fixed["written"][0]["outside_bytes_identical"])

    def test_the_repaired_file_keeps_the_access_it_had(self):
        """The replacement is a new file the writer creates owner-only. The
        instruction file is read by other accounts, so it gets back the mode
        the replaced file had."""
        path = self.measured()
        owner = block_owner()
        if os.name == "posix":
            os.chmod(path, 0o644)
        before = stat.S_IMODE(path.stat().st_mode)
        with mock.patch.object(owner.os, "chmod", wraps=os.chmod) as restored:
            fixed = owner.repair(self.project)
        self.assertEqual(fixed["code"], "PROJECT_BLOCK_REPAIRED", fixed)
        restored.assert_called_once_with(path, before)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), before)

    def test_a_second_repair_writes_nothing(self):
        path = self.measured()
        owner = block_owner()
        owner.repair(self.project)
        first = path.read_bytes()
        stamp = path.stat().st_mtime_ns
        again = owner.repair(self.project)
        self.assertTrue(again["ok"])
        self.assertEqual(again["code"], "PROJECT_BLOCK_CURRENT")
        self.assertEqual(again["written"], [])
        self.assertEqual(path.read_bytes(), first)
        self.assertEqual(path.stat().st_mtime_ns, stamp)

    def test_a_dry_run_names_the_write_and_makes_none(self):
        path = self.measured()
        planned = block_owner().repair(self.project, dry_run=True)
        self.assertTrue(planned["dry_run"])
        self.assertEqual([item["file"] for item in planned["written"]], ["AGENTS.md"])
        self.assertEqual(path.read_bytes(), FIXTURE.read_bytes())

    def test_markers_that_are_not_one_pair_are_refused_and_left_alone(self):
        owner = block_owner()
        shapes = {
            "open only": b"intro\n" + BEGIN + b"\nold text\n",
            "close only": b"intro\nold text\n" + END + b"\n",
            "close first": END + b"\nold text\n" + BEGIN + b"\n",
            "two blocks": legacy_block() + b"\n\n" + legacy_block() + b"\n",
        }
        for name, body in shapes.items():
            with self.subTest(name):
                path = self.put("AGENTS.md", body)
                report = owner.status(self.project)
                self.assertFalse(report["ok"])
                self.assertEqual(report["code"], "PROJECT_BLOCK_MALFORMED")
                self.assertIn("AGENTS.md", str(report["action"]))
                fixed = owner.repair(self.project)
                self.assertFalse(fixed["ok"])
                self.assertEqual(fixed["written"], [])
                self.assertEqual(path.read_bytes(), body)

    def test_a_stale_file_is_repaired_beside_a_malformed_one(self):
        owner = block_owner()
        good = self.measured()
        bad_body = b"x\n" + BEGIN + b"\n"
        bad = self.put("GEMINI.md", bad_body)
        fixed = owner.repair(self.project)
        self.assertFalse(fixed["ok"])
        self.assertEqual(fixed["code"], "PROJECT_BLOCK_MALFORMED")
        self.assertEqual([item["file"] for item in fixed["written"]], ["AGENTS.md"])
        self.assertEqual(good.read_bytes(), owner.current_block(b"\n") + b"\n")
        self.assertEqual(bad.read_bytes(), bad_body)

    def test_a_refused_write_leaves_the_file_and_names_what_must_change(self):
        path = self.measured()
        owner = block_owner()
        refusal = ValueError("project instruction file is not a regular owned file")
        with mock.patch.object(owner, "safe_atomic_write_bytes", side_effect=refusal):
            fixed = owner.repair(self.project)
        self.assertFalse(fixed["ok"])
        self.assertEqual(fixed["code"], "PROJECT_BLOCK_REPAIR_FAILED")
        self.assertEqual(fixed["written"], [])
        self.assertIn("not a regular owned file", fixed["detail"])
        self.assertTrue(fixed["action"].startswith("make AGENTS.md a regular file"))
        self.assertNotEqual(fixed["action"], REPAIR, "the same command again is not an action")
        self.assertEqual(path.read_bytes(), FIXTURE.read_bytes())

    def test_a_linked_instruction_file_is_never_written_through(self):
        outside = self.base / "outside.md"
        outside.write_bytes(FIXTURE.read_bytes())
        link = self.project / "AGENTS.md"
        try:
            os.symlink(outside, link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"this account may not create a symbolic link: {exc}")
        owner = block_owner()
        report = owner.status(self.project)
        self.assertEqual(self.row(report)["status"], "LINKED")
        fixed = owner.repair(self.project)
        self.assertEqual(fixed["written"], [])
        self.assertEqual(outside.read_bytes(), FIXTURE.read_bytes())

    def test_a_node_the_system_answers_as_a_link_is_left_alone(self):
        """The same rule where this account may not create a link: the answer
        is replaced at the one place the system is asked what the node is."""
        path = self.measured()
        real = Path.lstat
        link = os.stat_result((stat.S_IFLNK | 0o777, 0, 0, 1, 0, 0, 386, 0, 0, 0))

        def answer(node):
            return link if Path(node).name == "AGENTS.md" else real(node)

        owner = block_owner()
        with mock.patch.object(Path, "lstat", answer):
            report = owner.status(self.project)
            fixed = owner.repair(self.project)
        self.assertEqual(self.row(report)["status"], "LINKED")
        self.assertEqual(report["code"], "PROJECT_BLOCK_ABSENT")
        self.assertEqual(fixed["written"], [])
        self.assertEqual(path.read_bytes(), FIXTURE.read_bytes())


# ------------------------------------------------------------- the block itself


class CurrentBlockTests(unittest.TestCase):
    def text(self) -> str:
        return block_owner().current_block(b"\n").decode("ascii")

    def test_it_is_one_marker_pair(self):
        block = block_owner().current_block(b"\n")
        self.assertTrue(block.startswith(BEGIN + b"\n"))
        self.assertTrue(block.endswith(b"\n" + END))
        self.assertEqual(block.count(BEGIN), 1)
        self.assertEqual(block.count(END), 1)

    def test_the_revision_moves_with_the_text(self):
        """Change the text, raise the revision, then pin the new pair here. A
        new text under an old number is undone by every install still writing
        the old one, and undoes theirs."""
        import hashlib

        owner = block_owner()
        pinned = {1: "1f7d5cc9cc7f9c029da4a4e859a802b091322a467ea600b5b3a7d0e576181c6d"}
        digest = hashlib.sha256(owner.current_block(b"\n")).hexdigest()
        self.assertEqual(pinned.get(owner.BLOCK_REVISION), digest)
        self.assertIn(
            f"## saipen protocol (project block {owner.BLOCK_REVISION})", self.text()
        )

    def test_it_is_relocatable(self):
        text = self.text()
        self.assertIsNone(re.search(r"[A-Za-z]:[\\/]", text), "a drive path")
        self.assertIsNone(re.search(r"(?<![\w<>.])/(?:home|Users|root)/", text), "a home path")
        self.assertNotIn("{{", text)
        self.assertNotIn("github.com", text)
        for home in (".agents", ".claude", ".codex", ".gemini"):
            self.assertNotIn(home, text)

    def test_it_never_tells_the_agent_to_clone(self):
        mentions = [
            sentence
            for sentence in re.split(r"(?<=[.;])\s+", " ".join(self.text().split()))
            if "clone" in sentence.lower()
        ]
        self.assertTrue(mentions, "the prohibition is stated")
        for sentence in mentions:
            self.assertIn("never", sentence.lower(), sentence)

    def test_it_names_the_launcher_order(self):
        text = " ".join(self.text().split())
        on_path = text.index("`saipen` on PATH")
        recorded = text.index("`saipen_home:` value in `.saipen/STATE.md`")
        machine_step = text.index("%ProgramData%\\SAI\\SAIPEN\\bin\\saipen.cmd")
        self.assertLess(on_path, recorded)
        self.assertLess(recorded, machine_step)

    def test_it_names_the_first_command_and_where_the_kernel_is(self):
        """A host with no block of its own has only this one: it must say what
        to run for each kind of turn, and reach the kernel through the answer."""
        text = " ".join(self.text().split())
        self.assertIn("New task: run `saipen start '<the task, one line>'`", text)
        self.assertIn("No new task (`cc`, bare `saipen`): run `saipen continue --json`", text)
        self.assertIn("the `boot` document named under `cold_route` in that answer", text)
        self.assertIn("(`saipen status --json` always names it)", text)

    def test_the_machine_launcher_it_names_is_the_one_the_runtime_installs(self):
        from saipen_engine import machine_runtime

        if os.name != "nt":
            self.skipTest("the machine runtime root is declared for Windows only")
        root = machine_runtime.default_root({"ProgramData": "%ProgramData%"})
        launcher = str(root / machine_runtime.BIN_DIR / machine_runtime.WINDOWS_LAUNCHER)
        self.assertIn(launcher, self.text())

    def test_it_is_ascii_so_no_file_encoding_can_break_it(self):
        block_owner().current_block(b"\r\n").decode("ascii")


# ---------------------------------------------------------------- the surfaces


class CommandSurfaceTests(_Project):
    def cli(self, *args: str, **declared: str) -> tuple[int, dict]:
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith("SAIPEN")
        }
        env["SAIPEN_MACHINE_ROOT"] = str(self.base / "no-machine-runtime")
        env.update(declared)
        proc = subprocess.run(
            [sys.executable, "-B", str(ENGINE), *args, "--json"],
            capture_output=True,
            env=env,
            cwd=str(self.base),
            timeout=240,
            check=False,
        )
        try:
            return proc.returncode, json.loads(proc.stdout.decode("utf-8", "replace"))
        except ValueError:
            return proc.returncode, {
                "code": f"UNPARSED rc={proc.returncode}",
                "detail": (proc.stderr or proc.stdout).decode("utf-8", "replace")[-600:],
            }

    def test_one_command_reports_and_one_repairs(self):
        path = self.measured()
        root = str(self.project)
        rc, report = self.cli("host", "instructions", "--project-root", root)
        self.assertEqual(report["code"], "PROJECT_BLOCK_STALE", report)
        self.assertEqual(rc, 1)
        self.assertEqual(report["action"], REPAIR)
        rc, same = self.cli("host", "instructions", "status", "--project-root", root)
        self.assertEqual((rc, same["code"]), (1, "PROJECT_BLOCK_STALE"))
        self.assertEqual(path.read_bytes(), FIXTURE.read_bytes())
        rc, fixed = self.cli("host", "instructions", "repair", "--project-root", root)
        self.assertEqual((rc, fixed["code"]), (0, "PROJECT_BLOCK_REPAIRED"), fixed)
        rc, after = self.cli("host", "instructions", "--project-root", root)
        self.assertEqual((rc, after["code"]), (0, "PROJECT_BLOCK_CURRENT"))
        self.assertNotIn(b"github.com", path.read_bytes())

    def test_the_global_dry_run_flag_writes_nothing(self):
        path = self.measured()
        rc, planned = self.cli(
            "host", "instructions", "repair", "--project-root", str(self.project), "--dry-run"
        )
        self.assertEqual(rc, 1, "the block is still of another generation")
        self.assertTrue(planned.get("dry_run"), planned)
        self.assertEqual(path.read_bytes(), FIXTURE.read_bytes())

    def test_a_read_only_session_reports_and_may_not_repair(self):
        path = self.measured()
        root = str(self.project)
        told = {"SAIPEN_CAPABILITY": "read-only"}
        rc, report = self.cli("host", "instructions", "--project-root", root, **told)
        self.assertEqual((rc, report["code"]), (1, "PROJECT_BLOCK_STALE"))
        rc, refused = self.cli("host", "instructions", "repair", "--project-root", root, **told)
        self.assertEqual((rc, refused["code"]), (1, "CAPABILITY_DENIED"), refused)
        self.assertEqual(path.read_bytes(), FIXTURE.read_bytes())
        rc, planned = self.cli(
            "host", "instructions", "repair", "--dry-run", "--project-root", root, **told
        )
        self.assertTrue(planned.get("dry_run"), planned)
        self.assertEqual(path.read_bytes(), FIXTURE.read_bytes())

    def test_an_unknown_action_or_option_is_refused(self):
        self.measured()
        root = str(self.project)
        owned = "host instructions accepts status|repair"
        rc, answer = self.cli("host", "instructions", "rewrite", "--project-root", root)
        self.assertEqual((rc, answer["code"]), (2, "VALIDATION_FAILED"))
        self.assertIn(owned, answer["detail"])
        rc, answer = self.cli("host", "instructions", "repair", "--force", "--project-root", root)
        self.assertEqual((rc, answer["code"]), (2, "VALIDATION_FAILED"))
        self.assertIn(owned, answer["detail"])
        self.assertEqual((self.project / "AGENTS.md").read_bytes(), FIXTURE.read_bytes())

    def test_the_command_every_session_runs_names_the_stale_block(self):
        """`status` and `continue` carry the cold route; a block of another
        generation is named there, and nothing is added once it is current."""
        self.measured()
        root = str(self.project)
        _rc, before = self.cli("status", "--project-root", root)
        boot = before["cold_route"]["boot"]
        self.assertTrue(boot and Path(boot).is_file(), "what the block says of `status`")
        hint = before["cold_route"]["instructions"]
        self.assertEqual(hint["code"], "PROJECT_BLOCK_STALE")
        self.assertEqual(hint["action"], REPAIR)
        self.assertEqual(hint["files"], [{"file": "AGENTS.md", "status": "STALE"}])
        self.cli("host", "instructions", "repair", "--project-root", root)
        _rc, after = self.cli("status", "--project-root", root)
        self.assertNotIn("instructions", after["cold_route"])

    def test_the_embedded_verdict_cannot_stop_the_command_that_carries_it(self):
        """The cold route rides `continue` and `start`. Whatever goes wrong
        while a project file is read, the route is still returned."""
        import saipen as engine

        owner = block_owner()
        self.measured()
        with mock.patch.object(owner, "status", side_effect=RuntimeError("unexpected")):
            embedded = owner.projection(self.project)
            route = engine._cold_route(self.project, None)
        self.assertEqual(embedded["code"], "PROJECT_BLOCK_UNREADABLE")
        self.assertIsNone(embedded["action"])
        self.assertEqual(route["project_root"], str(self.project.resolve()))
        self.assertNotIn("instructions", route)
        self.assertEqual(engine._cold_route(self.project, None)["instructions"]["action"], REPAIR)

    def test_the_first_command_of_a_new_task_names_the_kernel(self):
        """What the block promises of `saipen start`: its answer carries the
        cold route, so the kernel is found without a path written anywhere."""
        rc, started = self.cli(
            "start", "write the release note", "--project-root", str(self.project)
        )
        self.assertEqual((rc, started.get("code")), (0, "STARTED"), started)
        boot = started["cold_route"]["boot"]
        self.assertTrue(boot and Path(boot).is_file(), started["cold_route"])
        self.assertEqual(Path(boot).name, "BOOT.md")

    def test_the_project_diagnostic_carries_the_same_verdict(self):
        self.measured()
        root = str(self.project)
        rc, bound = self.cli("host", "bootstrap", "--project-root", root)
        self.assertEqual(bound["code"], "HOST_BOOTSTRAP_BOUND", bound)
        self.assertEqual(rc, 0, "a stale block does not unbind a reachable runtime")
        self.assertEqual(bound["instructions"]["code"], "PROJECT_BLOCK_STALE")
        self.assertEqual(bound["instructions"]["action"], REPAIR)
        self.cli("host", "instructions", "repair", "--project-root", root)
        _rc, bound = self.cli("host", "bootstrap", "--project-root", root)
        self.assertEqual(bound["instructions"]["code"], "PROJECT_BLOCK_CURRENT")
        self.assertIsNone(bound["instructions"]["action"])

    def test_the_effect_table_knows_which_action_writes(self):
        from saipen_engine import command_effects as CE

        self.assertEqual(CE.classify_invocation("host", ["instructions"]), CE.DIAGNOSTIC)
        self.assertEqual(CE.classify_invocation("host", ["instructions", "status"]), CE.DIAGNOSTIC)
        self.assertEqual(CE.classify_invocation("host", ["instructions", "repair"]), CE.RECOVERY)


class LawTextTests(unittest.TestCase):
    def test_the_command_row_states_the_command_and_its_two_limits(self):
        rows = [
            line
            for line in (ROOT / "saipen" / "COMMANDS.md").read_text(encoding="utf-8").splitlines()
            if "saipen host instructions [status\\|repair]" in line
        ]
        self.assertEqual(len(rows), 1, "one row owns the command")
        for phrase in ("RECOVERY marker-to-marker rewrite", "creates none"):
            self.assertIn(phrase, rows[0])


if __name__ == "__main__":
    unittest.main()
