"""T-1663 / SRC-189 R002, R004, R016, R017, R018: a ticket says what its steps need.

Before this ticket the required set of `saipen iteration` was STATE `requires`
plus what the PHASE executes. Work that needs a GUI, a browser, a C# toolchain
or Windows-native execution had no field to say so, a read-only audit ticket
was charged for editing as soon as it left SCOUT, and new evidence could raise
the requirement of one ticket only by raising it for the whole project.

A `requires:` field on the BOARD ticket now carries it, in the closed grammar
`name[@PHASE[+PHASE...]]` separated by commas, plus the one word `read_only`:

* a GUI acceptance ticket (`gui@VERIFY`) is built and tested by an executor
  without a GUI, and only its acceptance step asks for one (R016);
* a read-only audit ticket is admitted on an executor that reads and reaches
  the control plane in every phase its lifecycle uses (R017);
* SCOUT that finds a Windows-native step escalates the ticket through the
  canonical verb: the current step keeps its executor, BUILD asks for the
  capability, and nothing but the field moves (R018);
* every inventory class R002 lists has one shared name, met by the executor
  that advertises it (R002, R004).

The fixtures run red on the engine before T-1663 and green after it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import continuity_probes as probes  # noqa: E402
from saipen_engine import iteration  # noqa: E402
from saipen_engine import iteration_verdict as IV  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1651_executor_admission import FULL, _memory, _Project  # noqa: E402

AGENT = "buffy"
ENGINE = TOOLS / "saipen.py"
#: Reads the repository and reaches the control plane. Nothing else.
READER = {"filesystem_read": True, "saipen_control": True}
LIFECYCLE = ("SCOUT", "BUILD", "VERIFY", "REVIEW", "SHIP")

#: The classes SRC-189 R002 lists, each with the name this engine uses.
R002_CLASSES = {
    "shell or process execution": IV.PROCESS_EXECUTION,
    "filesystem read": IV.FILESYSTEM_READ,
    "filesystem write": IV.FILESYSTEM_WRITE,
    "code editing or patch application": IV.PATCH_APPLICATION,
    "recursive repository inspection": "repository_inspection",
    "Git read": "git_read",
    "Git write": "git_write",
    "compiler or build execution": "build_execution",
    "test execution": "test_execution",
    "Windows-native process execution": "windows_native",
    "GUI or computer use": "gui",
    "browser or web": "browser",
    "SAIPEN control-plane invocation": IV.SAIPEN_CONTROL,
    "file upload, download or materialization": "file_transfer",
    "image or visual inspection": "visual_inspection",
}


def setUpModule() -> None:
    isolate_host_session()


class _TicketProject(_Project):
    """The T-1651 C# project whose active ticket carries a `requires:` field."""

    def ticket_project(self, phase: str, requires: str) -> Path:
        root = self.project(phase)
        board = root / ".saipen" / "BOARD.md"
        text = board.read_text(encoding="utf-8")
        marker = " | owner: tester"
        self.assertEqual(text.count(marker), 1)
        board.write_text(text.replace(marker, f" | requires: {requires}{marker}"), encoding="utf-8")
        return root

    def ticket_verdict(self, phase: str, requires: str, caps: dict) -> dict:
        root = self.ticket_project(phase, requires)
        before = _memory(root)
        found = IV.project_iteration_verdict(root, executor_caps=caps)
        self.assertEqual(_memory(root), before, "the verdict writes nothing")
        self.assertTrue(found["state_readable"], found)
        return found


class GuiAcceptanceTicketTests(_TicketProject):
    """R016: a step is never charged for a capability another step needs."""

    def test_the_build_and_test_steps_admit_an_executor_without_a_gui(self):
        for phase in ("SCOUT", "BUILD", "REVIEW"):
            found = self.ticket_verdict(phase, "gui@VERIFY", FULL)
            self.assertEqual(found["admission"]["result"], IV.ADMISSION_ADMIT, (phase, found))
            self.assertNotIn("gui", found["required_capabilities"], phase)

    def test_the_acceptance_step_asks_for_the_gui_and_routes_to_a_capable_executor(self):
        found = self.ticket_verdict("VERIFY", "gui@VERIFY", FULL)
        self.assertEqual(found["decision"], iteration.EXECUTOR_CAPABILITY_MISMATCH, found)
        self.assertEqual(found["missing_capabilities"], ["gui"])
        self.assertIn("gui", found["required_capabilities"])
        self.assertEqual(found["admission"]["next"], IV.NEXT_FAILOVER)
        capable = self.ticket_verdict("VERIFY", "gui@VERIFY", {**FULL, "gui": True})
        self.assertEqual(capable["admission"]["result"], IV.ADMISSION_ADMIT, capable)

    def test_an_unscoped_requirement_holds_in_every_phase(self):
        for phase in LIFECYCLE:
            found = self.ticket_verdict(phase, "dotnet", FULL)
            self.assertEqual(found["missing_capabilities"], ["dotnet"], phase)
            capable = self.ticket_verdict(phase, "dotnet", {**FULL, "dotnet": True})
            self.assertEqual(capable["admission"]["result"], IV.ADMISSION_ADMIT, phase)

    def test_a_host_tool_name_translates_as_state_requires_does(self):
        found = self.ticket_verdict("SCOUT", "shell@SCOUT", READER)
        self.assertIn(IV.PROCESS_EXECUTION, found["missing_capabilities"])
        self.assertNotIn("shell", found["required_capabilities"])


class ReadOnlyTicketTests(_TicketProject):
    """R017: a read-only task stays runnable on a read-only executor."""

    def test_the_reader_is_admitted_in_every_phase_the_lifecycle_uses(self):
        for phase in LIFECYCLE:
            found = self.ticket_verdict(phase, "read_only", READER)
            self.assertEqual(found["admission"]["result"], IV.ADMISSION_ADMIT, (phase, found))
            self.assertEqual(
                found["required_capabilities"],
                sorted({IV.FILESYSTEM_READ, IV.SAIPEN_CONTROL}),
                phase,
            )

    def test_without_the_declaration_the_same_reader_stops_at_build(self):
        root = self.project("BUILD")
        found = IV.project_iteration_verdict(root, executor_caps=READER)
        self.assertEqual(found["admission"]["result"], IV.ADMISSION_REJECT, found)

    def test_a_read_only_ticket_still_needs_the_control_plane(self):
        found = self.ticket_verdict("SCOUT", "read_only", {"filesystem_read": True})
        self.assertEqual(found["missing_capabilities"], [IV.SAIPEN_CONTROL])

    def test_a_read_only_ticket_keeps_what_else_it_names(self):
        found = self.ticket_verdict("REVIEW", "read_only, visual_inspection", READER)
        self.assertEqual(found["missing_capabilities"], ["visual_inspection"])


class MalformedFieldTests(_TicketProject):
    """A field the grammar cannot read is never read as no requirement."""

    def test_an_unreadable_field_fails_closed_and_names_itself(self):
        for raw in ("gui@NOWHERE", "@VERIFY", "two words", "read_only@BUILD"):
            found = self.ticket_verdict("BUILD", raw, {**FULL, "gui": True})
            self.assertEqual(found["admission"]["result"], IV.ADMISSION_REJECT, (raw, found))
            self.assertIn(IV.TICKET_REQUIRES_INVALID, found["missing_capabilities"], raw)

    def test_the_grammar_is_one_function(self):
        self.assertEqual(
            IV.parse_ticket_requires("gui@VERIFY+REVIEW, windows_native@build, dotnet"),
            ({"gui": ("VERIFY", "REVIEW"), "windows_native": ("BUILD",), "dotnet": ()}, False),
        )
        self.assertEqual(IV.parse_ticket_requires("read_only"), ({}, True))
        self.assertEqual(IV.parse_ticket_requires(""), ({}, False))
        for raw in ("gui@", "gui@@VERIFY", "Gui!", "a" * 65, "gui@VERIFY+NOWHERE"):
            with self.assertRaises(ValueError, msg=raw):
                IV.parse_ticket_requires(raw)


class InventoryTests(_TicketProject):
    """R002: one shared word per inventory class, met by the executor that says it."""

    def test_every_class_the_source_lists_has_a_distinct_name(self):
        names = list(R002_CLASSES.values())
        self.assertEqual(len(set(names)), len(names))
        self.assertLessEqual(set(names), set(IV.CAPABILITY_INVENTORY))

    def test_an_inventory_requirement_is_met_by_the_executor_that_advertises_it(self):
        for name in ("git_write", "build_execution", "browser", "file_transfer"):
            found = self.ticket_verdict("BUILD", name, FULL)
            self.assertEqual(found["missing_capabilities"], [name], name)
            capable = self.ticket_verdict("BUILD", name, {**FULL, name: True})
            self.assertEqual(capable["admission"]["result"], IV.ADMISSION_ADMIT, name)


class EscalationTests(unittest.TestCase):
    """R018: SCOUT finds a Windows-native step; the canonical verb escalates.

    A real project and the real engine CLI: the field changes through
    `saipen ticket requires`, never through an edit of BOARD.md.
    """

    def setUp(self):
        self.root = probes.fresh_project("t1663")
        self.addCleanup(shutil.rmtree, self.root, True)
        subprocess.run(["git", "init", "-q", "."], cwd=self.root, check=True)
        for args in (("continue",), ("claim", "T-001")):
            answer = probes.cli(self.root, AGENT, *args)
            self.assertTrue(answer.get("ok"), (args, answer))

    def cli(self, *args):
        return probes.cli(self.root, AGENT, *args)

    def verdict(self, caps: dict) -> dict:
        found = IV.project_iteration_verdict(self.root, executor_caps=caps)
        self.assertTrue(found["state_readable"], found)
        return found

    def state(self) -> dict:
        text = (self.root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        return {
            key: value.strip()
            for key, _, value in (line.partition(":") for line in text.splitlines())
            if key in ("phase", "task", "next_action", "blocker", "transition_from")
        }

    def row(self) -> dict:
        board = parse_board((self.root / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))
        return board["tickets"]["T-001"]

    def test_scout_escalates_build_and_nothing_else_moves(self):
        self.assertEqual(self.state()["phase"], "SCOUT")
        self.assertEqual(self.verdict(FULL)["admission"]["result"], IV.ADMISSION_ADMIT)
        state_before, row_before = self.state(), self.row()

        answer = self.cli("ticket", "requires", "T-001", "windows_native@BUILD")
        self.assertTrue(answer.get("ok"), answer)
        self.assertEqual(answer.get("code"), "TICKET_REQUIRES_SET", answer)
        self.assertEqual(answer.get("unlisted"), [], answer)

        # The current safe step finishes on the executor it has.
        self.assertEqual(self.verdict(FULL)["admission"]["result"], IV.ADMISSION_ADMIT)
        self.assertEqual(self.state(), state_before)
        row_after = self.row()
        self.assertEqual(row_after["section"], row_before["section"])
        moved = {
            key
            for key in set(row_before["fields"]) | set(row_after["fields"])
            if row_before["fields"].get(key) != row_after["fields"].get(key)
        }
        self.assertEqual(moved, {"requires"})
        self.assertEqual(row_after["fields"]["requires"], "windows_native@BUILD")

        # Failover happens at the phase boundary, with the evidence kept.
        moved = self.cli("transition", "BUILD", "T-001", "scout done: a Windows-native step")
        self.assertTrue(moved.get("ok"), moved)
        at_build = self.verdict(FULL)
        self.assertEqual(at_build["decision"], iteration.EXECUTOR_CAPABILITY_MISMATCH)
        self.assertEqual(at_build["missing_capabilities"], ["windows_native"])
        capable = self.verdict({**FULL, "windows_native": True})
        self.assertEqual(capable["admission"]["result"], IV.ADMISSION_ADMIT, capable)
        status = self.cli("status")
        self.assertTrue(status.get("ok"), status)

    def test_the_public_verdict_reads_the_field(self):
        self.assertTrue(self.cli("ticket", "requires", "T-001", "gui@SCOUT").get("ok"))
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ENGINE),
                "--project-root",
                str(self.root),
                "iteration",
                "--json",
                "--cap",
                "filesystem=true",
                "--cap",
                "shell=true",
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            cwd=str(self.root),
            timeout=120,
            check=False,
        )
        answer = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual(answer["missing_capabilities"], ["gui"], answer)

    def test_a_repeat_is_idempotent_and_none_clears_the_field(self):
        self.assertTrue(self.cli("ticket", "requires", "T-001", "gui@VERIFY").get("ok"))
        log = (self.root / ".saipen" / "LOG.md").read_bytes()
        again = self.cli("ticket", "requires", "T-001", "gui@verify")
        self.assertEqual(again.get("code"), "ALREADY_SET", again)
        self.assertEqual((self.root / ".saipen" / "LOG.md").read_bytes(), log)
        unlisted = self.cli("ticket", "requires", "T-001", "gui@VERIFY, dotnet")
        self.assertEqual(unlisted.get("unlisted"), ["dotnet"], unlisted)
        cleared = self.cli("ticket", "requires", "T-001", "none")
        self.assertTrue(cleared.get("ok"), cleared)
        self.assertNotIn("requires", self.row()["fields"])

    def test_a_malformed_value_is_refused_with_zero_writes(self):
        before = _memory(self.root)
        for raw in ("gui@NOWHERE", "read_only@BUILD", "two words"):
            answer = self.cli("ticket", "requires", "T-001", raw)
            self.assertFalse(answer.get("ok"), (raw, answer))
            self.assertEqual(answer.get("code"), "VALIDATION_FAILED", (raw, answer))
        missing = self.cli("ticket", "requires", "T-999", "gui")
        self.assertEqual(missing.get("code"), "TICKET_NOT_FOUND", missing)
        self.assertEqual(_memory(self.root), before)


if __name__ == "__main__":
    unittest.main()
