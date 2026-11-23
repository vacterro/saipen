"""T-1651 / SRC-189: an executor is admitted for what the current step needs.

The incident: a continuation task for a SAIPEN-managed C# project reached an
executor that exposed only `read_tabular` and `system_todo_write`. It reasoned
correctly for about fourteen seconds and then reported it could do nothing.
T-1619 already answers that executor `EXECUTOR_CAPABILITY_MISMATCH`.

SRC-189 asks for more than the rejection, and these cases bind the part this
ticket delivers:

* the admission is a CONTRACT a host reads (R011, R022): what the step
  requires, what the executor was granted from the tools it actually
  advertised, the result, what is missing and what follows;
* the requirement is the PHASE's (R003, R016, R017): SCOUT reads, VERIFY and
  REVIEW run the project's checks, and only a phase that edits the tree is
  charged for editing it -- no executor is rejected for a capability the
  current step does not require;
* control-plane access is a capability of its own (R005);
* an executor that advertises the filesystem and a shell is a full one (R015);
* an exhausted pool is ONE blocker that names what was required and what each
  executor lacked (R008).

Every case is read-only against the project: the verdict writes nothing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import host_iteration as HI  # noqa: E402
from saipen_engine import iteration  # noqa: E402
from saipen_engine import iteration_verdict as IV  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1614_future_gate import CURRENT_STYLE_CONTRACT, ROOT  # noqa: E402

ENGINE = TOOLS / "saipen.py"

#: What the incident executor advertised.
SAIOPP = {"read_tabular": True, "system_todo_write": True}
#: A full coding executor, in the words STATE `requires` uses.
FULL = {"filesystem": True, "shell": True, "git": True, "python": True}
#: Reads the repository and runs processes; cannot edit a file.
RUNS_AND_READS = {"filesystem_read": True, "shell": True, "git": True, "python": True}
#: Reads the repository and reaches the control plane; no shell at all.
READS_ONLY = {"filesystem_read": True, "saipen_control": True, "git": True, "python": True}

_SOURCE = {"SCOUT": "DONE", "BUILD": "SCOUT", "VERIFY": "BUILD", "REVIEW": "VERIFY",
           "SHIP": "REVIEW"}


def setUpModule() -> None:
    isolate_host_session()


def _memory(project: Path) -> dict[str, bytes]:
    base = project / ".saipen"
    return {p.name: p.read_bytes() for p in sorted(base.iterdir()) if p.is_file()}


class _Project(unittest.TestCase):
    """A managed C# project with one active ticket, in a chosen phase."""

    requires = ("filesystem", "git", "python")

    def project(self, phase: str = "BUILD", *, requires: tuple[str, ...] | None = None) -> Path:
        base = Path(tempfile.mkdtemp(prefix="saipen-t1651-"))
        self.addCleanup(shutil.rmtree, base, True)
        root = base / "project"
        (root / ".saipen").mkdir(parents=True)
        (root / "src").mkdir()
        (root / "src" / "Service.cs").write_text("class Service {}\n", encoding="utf-8")
        wanted = self.requires if requires is None else requires
        (root / ".saipen" / "STATE.md").write_text(
            "---\n"
            f"phase: {phase}\n"
            "task: T-7\n"
            f'next_action: "PHASE {phase} T-7"\n'
            'blocker: ""\n'
            f"transition_from: {_SOURCE[phase]}\n"
            "saipen_version: 8\n"
            "schema_version: 3\n"
            "last_event: 1\n"
            "style_contract: " + CURRENT_STYLE_CONTRACT + "\n"
            f'saipen_home: "{str(ROOT).replace(chr(92), chr(92) * 2)}"\n'
            "agent: tester\n"
            "requires:\n" + "".join(f"  - {name}\n" for name in wanted) +
            "mode: full\n"
            "execution_intent: goal\n"
            "goal_waves: 0\n"
            "goal_tickets: 1\n"
            'updated: "2026-10-07T00:00:00Z"\n'
            "---\n",
            encoding="utf-8",
        )
        (root / ".saipen" / "BOARD.md").write_text(
            "## DOING\n"
            "- [/] T-7 [P1] Change the C# service | verify: dotnet build and dotnet test pass"
            " | owner: tester | claim_time: 2026-10-07T00:00:00Z\n"
            "## TODO\n## DONE\n## BLOCKED\n",
            encoding="utf-8",
        )
        (root / ".saipen" / "LOG.md").write_text(
            "- 07.10.26 00:00 [E-001] [T-7] [agent: tester] RUN: fixture -> PASS\n",
            encoding="utf-8",
        )
        return root

    def verdict(self, phase: str, caps: dict | None, **kwargs) -> dict:
        root = self.project(phase)
        before = _memory(root)
        found = IV.project_iteration_verdict(root, executor_caps=caps, **kwargs)
        self.assertEqual(_memory(root), before, "the verdict writes nothing")
        self.assertTrue(found["state_readable"], found)
        return found


class ContractTests(_Project):
    """R011 / R022: required, granted, result, missing, next -- as data."""

    def test_an_assessed_executor_gets_the_whole_contract(self):
        found = self.verdict("BUILD", SAIOPP, executor_id="SAIRoute/SAIOPP")
        self.assertEqual(found["executor_id"], "SAIRoute/SAIOPP")
        self.assertEqual((found["phase"], found["canonical_task"]), ("BUILD", "T-7"))
        self.assertEqual(found["required_capabilities"], sorted(found["required_capabilities"]))
        self.assertEqual(
            found["executor_capabilities"], ["read_tabular", "system_todo_write"],
            "what the executor actually has is shown; none of it is required",
        )
        self.assertEqual(
            found["admission"],
            {
                "result": IV.ADMISSION_REJECT,
                "missing": found["required_capabilities"],
                "next": IV.NEXT_FAILOVER,
            },
        )
        self.assertEqual(found["missing_capabilities"], found["admission"]["missing"])

    def test_an_unassessed_executor_is_named_unassessed_not_admitted(self):
        found = self.verdict("BUILD", None)
        self.assertIsNone(found["executor_capabilities"])
        self.assertEqual(
            found["admission"],
            {"result": IV.ADMISSION_UNASSESSED, "missing": [], "next": IV.NEXT_NONE},
        )
        self.assertTrue(found["required_capabilities"], "what the step needs is still stated")

    def test_an_unreadable_checkpoint_keeps_the_shape(self):
        found = IV.project_iteration_verdict(Path(tempfile.gettempdir()) / "saipen-none-t1651")
        self.assertEqual(found["decision"], iteration.RUNTIME_PAUSED)
        self.assertEqual(found["required_capabilities"], [])
        self.assertEqual(found["admission"]["result"], IV.ADMISSION_UNASSESSED)

    def test_identity_grants_nothing(self):
        """R012: a brand, a provider or a harness name is not a tool."""
        named = {"model": "a-coding-model", "provider": "p", "harness": "full-coding",
                 "executor": "x", "route": "r"}
        found = self.verdict("SCOUT", named)
        self.assertEqual(found["executor_capabilities"], [])
        self.assertEqual(found["admission"]["result"], IV.ADMISSION_REJECT)


class DeadOnArrivalTests(_Project):
    """R014 / R026: the incident, in BUILD, with compilation and tests owed."""

    def test_the_incident_executor_is_rejected_and_nothing_is_written(self):
        found = self.verdict("BUILD", SAIOPP, executor_id="SAIRoute/SAIOPP")
        self.assertEqual(found["decision"], iteration.EXECUTOR_CAPABILITY_MISMATCH)
        self.assertFalse(found["executor_compatible"])
        self.assertFalse(found["requires_human"], "the operator receives no question")
        self.assertEqual(found["execution_intent"], "goal", "the intent stays intact")
        self.assertEqual(found["next_action"], "PHASE BUILD T-7", "the Work stays unchanged")
        for needed in (IV.FILESYSTEM_WRITE, IV.PATCH_APPLICATION, IV.PROCESS_EXECUTION,
                       IV.SAIPEN_CONTROL, IV.FILESYSTEM_READ):
            self.assertIn(needed, found["admission"]["missing"])

    def test_failover_reaches_a_compatible_executor_without_the_operator(self):
        root = self.project("BUILD")
        state = IV.parse_state_or_error((root / ".saipen" / "STATE.md").read_text("utf-8"))[0]
        controller = HI.HostIterationController(()).required_from_state(
            state["requires"], state["phase"]
        )
        selected, pause = controller.admit_candidates(
            [("SAIRoute/SAIOPP", SAIOPP), ("full", FULL)]
        )
        self.assertEqual((selected, pause), ("full", None))
        rejected = [t for t in controller.telemetry if t["event"] == "candidate_rejected"]
        self.assertEqual([t["candidate"] for t in rejected], ["SAIRoute/SAIOPP"])
        self.assertFalse(rejected[0]["requires_human"])
        self.assertFalse(rejected[0]["ticket_blocked"])
        refused = IV.project_iteration_verdict(root, executor_caps=SAIOPP)
        self.assertEqual(controller.on_model_turn_finished(refused), HI.REROUTE_EXECUTOR)

    def test_the_public_command_answers_the_same_and_writes_nothing(self):
        root = self.project("BUILD")
        before = _memory(root)
        proc = subprocess.run(
            [sys.executable, "-B", str(ENGINE), "--project-root", str(root), "iteration",
             "--json", "--cap", "read_tabular=true", "--cap", "system_todo_write=true",
             "--executor", "SAIRoute/SAIOPP"],
            stdin=subprocess.DEVNULL, capture_output=True, cwd=str(root), timeout=120,
            check=False,
        )
        answer = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual((proc.returncode, answer["ok"]), (0, True), answer)
        self.assertEqual(answer["decision"], iteration.EXECUTOR_CAPABILITY_MISMATCH)
        self.assertEqual(answer["admission"]["result"], IV.ADMISSION_REJECT)
        self.assertEqual(answer["admission"]["next"], IV.NEXT_FAILOVER)
        self.assertEqual(answer["executor_capabilities"], ["read_tabular", "system_todo_write"])
        self.assertEqual(_memory(root), before)


class InverseControlTests(_Project):
    """R015: an executor that can do the Work is admitted to it."""

    def test_filesystem_and_a_shell_are_a_full_executor_in_every_phase(self):
        for phase in _SOURCE:
            with self.subTest(phase):
                found = self.verdict(phase, FULL)
                self.assertEqual(found["admission"]["result"], IV.ADMISSION_ADMIT, found)
                self.assertEqual(found["admission"]["missing"], [])
                self.assertNotEqual(found["decision"], iteration.EXECUTOR_CAPABILITY_MISMATCH)

    def test_the_whole_filesystem_grants_what_its_write_half_grants(self):
        whole = IV.normalize_capabilities({"filesystem": True})
        write = IV.normalize_capabilities({"filesystem_write": True})
        self.assertTrue(write <= whole)
        self.assertIn(IV.PATCH_APPLICATION, whole)

    def test_a_named_patch_tool_still_counts(self):
        found = self.verdict("BUILD", {"filesystem_read": True, "file_write": True,
                                       "bash": True, "git": True, "python3": True})
        self.assertEqual(found["admission"]["result"], IV.ADMISSION_ADMIT, found)


class PhaseRequirementTests(_Project):
    """R003 / R016 / R017: only what the current step requires."""

    def required(self, phase: str | None) -> set[str]:
        return set(IV.required_for_state(list(self.requires), phase))

    def test_each_phase_is_charged_for_what_it_executes(self):
        reads = {IV.FILESYSTEM_READ, IV.GIT, IV.PYTHON, IV.SAIPEN_CONTROL}
        runs = reads | {IV.PROCESS_EXECUTION}
        whole = runs | {IV.FILESYSTEM_WRITE, IV.PATCH_APPLICATION}
        self.assertEqual(self.required("SCOUT"), reads)
        self.assertEqual(self.required("VERIFY"), runs)
        self.assertEqual(self.required("REVIEW"), runs)
        for phase in ("BUILD", "SHIP", "DONE", "PLAN", "CLEAN", "SOMETHING-NEW", "", None):
            with self.subTest(phase=phase):
                self.assertEqual(self.required(phase), whole, "edits or unknown: the whole set")
        self.assertEqual(self.required("scout"), reads, "a phase is a name, not a spelling")

    def test_an_executor_that_reads_and_runs_is_admitted_until_the_tree_is_edited(self):
        for phase, result in (("SCOUT", IV.ADMISSION_ADMIT), ("VERIFY", IV.ADMISSION_ADMIT),
                              ("REVIEW", IV.ADMISSION_ADMIT), ("BUILD", IV.ADMISSION_REJECT),
                              ("SHIP", IV.ADMISSION_REJECT)):
            with self.subTest(phase):
                found = self.verdict(phase, RUNS_AND_READS)
                self.assertEqual(found["admission"]["result"], result, found)
        rejected = self.verdict("BUILD", RUNS_AND_READS)
        self.assertEqual(
            rejected["admission"]["missing"], sorted([IV.FILESYSTEM_WRITE, IV.PATCH_APPLICATION])
        )

    def test_a_read_only_executor_scouts_and_goes_no_further(self):
        self.assertEqual(self.verdict("SCOUT", READS_ONLY)["admission"]["result"],
                         IV.ADMISSION_ADMIT)
        found = self.verdict("VERIFY", READS_ONLY)
        self.assertEqual(found["admission"]["missing"], [IV.PROCESS_EXECUTION])
        self.assertEqual(found["admission"]["next"], IV.NEXT_FAILOVER)

    def test_a_capability_nothing_requires_never_rejects(self):
        """A coding executor without a GUI is admitted to implementation and
        automated tests; a GUI is asked of it only where something requires one."""
        for phase in ("BUILD", "VERIFY"):
            self.assertEqual(self.verdict(phase, FULL)["admission"]["result"],
                             IV.ADMISSION_ADMIT)
        root = self.project("VERIFY", requires=(*self.requires, "gui"))
        found = IV.project_iteration_verdict(root, executor_caps=FULL)
        self.assertEqual(found["admission"]["missing"], ["gui"])

    def test_a_requirement_with_no_word_here_is_met_by_the_same_name_only(self):
        """A project may require what this module has no word for (`gui`,
        `dotnet`). It stayed required under its own name and nothing could
        grant it, so such a project admitted no executor at all."""
        root = self.project("VERIFY", requires=(*self.requires, "gui", "dotnet"))
        for caps, missing in (
            (FULL, ["dotnet", "gui"]),
            ({**FULL, "gui": True}, ["dotnet"]),
            ({**FULL, "GUI": "yes", "DotNet": True}, []),
            ({**FULL, "gui": False, "dotnet": None}, ["dotnet", "gui"]),
            ({**FULL, "computer_use": True, "csharp": True}, ["dotnet", "gui"]),
        ):
            with self.subTest(caps=sorted(caps)):
                found = IV.project_iteration_verdict(root, executor_caps=caps)
                self.assertEqual(found["admission"]["missing"], missing)
        shown = IV.project_iteration_verdict(root, executor_caps={**FULL, "gui": True})
        self.assertIn("gui", shown["executor_capabilities"])

    def test_an_advertised_name_cannot_pose_as_identity_or_grow_without_bound(self):
        self.assertEqual(IV.explicit_grants({"model": True, "provider": "yes", "x" * 65: True}),
                         frozenset())
        many = {f"tool_{n:03d}": True for n in range(200)}
        self.assertEqual(len(IV.explicit_grants(many)), 64)
        self.assertEqual(IV.explicit_grants({"shell": True, "saipen_control": True}), frozenset(),
                         "a name this module translates is not also an own name")
        self.assertEqual(IV.explicit_grants(None), frozenset())


class ControlPlaneTests(_Project):
    """R005: a route to the control plane is required and is not a shell."""

    def test_no_route_to_the_control_plane_is_incompatible_even_to_read(self):
        found = self.verdict("SCOUT", {"filesystem": True, "git": True, "python": True})
        self.assertEqual(found["admission"]["missing"], [IV.SAIPEN_CONTROL])

    def test_a_trusted_transport_that_is_not_a_shell_is_a_route(self):
        for name in ("saipen_control", "saipen", "saipen_cli", "control_plane"):
            with self.subTest(name):
                caps = {"filesystem_read": True, "git": True, "python": True, name: True}
                self.assertEqual(self.verdict("SCOUT", caps)["admission"]["result"],
                                 IV.ADMISSION_ADMIT)
        self.assertNotIn(IV.PROCESS_EXECUTION, IV.normalize_capabilities({"saipen": True}))

    def test_a_shell_is_a_route(self):
        self.assertIn(IV.SAIPEN_CONTROL, IV.normalize_capabilities({"shell": True}))


class ExhaustionTests(_Project):
    """R008: one blocker that says what was needed and what the pool lacked."""

    def test_an_exhausted_pool_names_the_required_set_and_each_executor(self):
        required = IV.required_for_state(list(self.requires), "BUILD")
        controller = HI.HostIterationController(required)
        selected, pause = controller.admit_candidates(
            [("SAIRoute/SAIOPP", SAIOPP), ("reader", RUNS_AND_READS)]
        )
        self.assertIsNone(selected)
        self.assertEqual(
            (pause["code"], pause["blocker"]),
            (iteration.RUNTIME_PAUSED, iteration.NO_COMPATIBLE_EXECUTOR),
        )
        self.assertEqual(pause["required"], sorted(required))
        self.assertEqual(sorted(pause["pool"]), ["SAIRoute/SAIOPP", "reader"])
        self.assertEqual(pause["pool"]["reader"],
                         sorted([IV.FILESYSTEM_WRITE, IV.PATCH_APPLICATION]))
        self.assertEqual(pause["pool"]["SAIRoute/SAIOPP"], sorted(required))
        self.assertFalse(pause["requires_human"])
        self.assertFalse(pause["project_blocked"])

    def test_the_verdict_names_exhaustion_as_the_next_step(self):
        found = self.verdict("BUILD", SAIOPP, all_candidates_exhausted=True)
        self.assertEqual(found["decision"], iteration.RUNTIME_PAUSED)
        self.assertEqual(found["admission"]["next"], IV.NEXT_NO_COMPATIBLE_EXECUTOR)
        self.assertTrue(found["admission"]["missing"])
        self.assertTrue(found["required_capabilities"])

    def test_a_second_pass_in_one_epoch_tries_nobody_twice(self):
        controller = HI.HostIterationController(
            IV.required_for_state(list(self.requires), "BUILD")
        )
        pool = [("SAIRoute/SAIOPP", SAIOPP), ("reader", RUNS_AND_READS)]
        controller.admit_candidates(pool)
        _selected, pause = controller.admit_candidates(pool)
        self.assertEqual(sorted(pause["pool"]), ["SAIRoute/SAIOPP", "reader"])
        rejected = [t for t in controller.telemetry if t["event"] == "candidate_rejected"]
        self.assertEqual(len(rejected), 2, "each executor was rejected once, not once per pass")


if __name__ == "__main__":
    unittest.main()
