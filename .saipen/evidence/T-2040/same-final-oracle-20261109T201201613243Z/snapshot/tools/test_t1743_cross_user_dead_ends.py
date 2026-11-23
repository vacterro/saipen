"""T-1743: three dead ends a managed Windows account hit on a real project.

1. `recover --adopt-legacy` wrote a mechanized DEC that the next pass counted
   as closure-generation evidence, so adopted-and-attested rows were flipped
   to `current` and a reopen approval was demanded for them.
2. A BOARD row within the live cap that carries a field outside the closed
   grammar had no canonical repair: `ticket compact` refused and Fleet named
   nothing.
3. The audit-manifest writer proved owned directories all the way to the
   drive root, so an account granted only the project hit WinError 5 on an
   ancestor it was never meant to read.
4. A project recording an injector home of the SAIPEN checkout (not the
   checkout itself) was "another install" to the machine runtime, so a
   managed account could read it but every lifecycle write was refused with
   "This needs the operator".
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import audit_manifest, machine_runtime  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.board_compaction import (  # noqa: E402
    foreign_field_ticket_ids,
    oversized_ticket_ids,
    resolve_detail,
)
from saipen_engine.fleet import CLASS_SAFE, preflight  # noqa: E402
from saipen_engine.log import LEGACY_ADOPTION, LEGACY_DONE_ATTESTATION  # noqa: E402
from saipen_engine.operations import compact_board  # noqa: E402
from saipen_engine.paths import project_lineage_identity  # noqa: E402
from saipen_engine.state import persisted_home_access  # noqa: E402
from saipen_engine.reconcile import (  # noqa: E402
    _is_legacy_generation,
    _mechanized_ticket_ids,
    reconcile_protocol_state,
)
from test_guard_hostile_matrix import fresh_project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1647_machine_runtime import (  # noqa: E402
    DENIED,
    ENV_ROOT,
    WINDOWS,
    _Scratch,
    an_install,
    deny_this_account,
)


def setUpModule() -> None:
    isolate_host_session()


class AdoptionIsNotClosureEvidenceTests(unittest.TestCase):
    def _events(self, text: str) -> list[dict]:
        return [{"ticket": "T-171", "op_id": "reconcile-1", "text": text}]

    def test_an_adoption_dec_leaves_the_record_legacy(self):
        events = self._events(
            f"{LEGACY_ADOPTION} T-171 -- no canonical allocation event is available"
        )
        mechanized = _mechanized_ticket_ids(events)
        self.assertNotIn("T-171", mechanized)
        self.assertTrue(_is_legacy_generation("T-171", None, mechanized))

    def test_an_attestation_still_leaves_the_record_legacy(self):
        mechanized = _mechanized_ticket_ids(
            self._events(f"{LEGACY_DONE_ATTESTATION} for T-171 -- operator decision")
        )
        self.assertTrue(_is_legacy_generation("T-171", None, mechanized))

    def test_a_real_operation_still_marks_the_record_current(self):
        # Negative control: ordinary mechanized history keeps its meaning.
        mechanized = _mechanized_ticket_ids(self._events("RUN: transition to BUILD"))
        self.assertIn("T-171", mechanized)
        self.assertFalse(_is_legacy_generation("T-171", None, mechanized))


def _foreign_project(field: str = "source: saihunt HUNT-001", **state) -> Path:
    fields = {
        "phase": "DONE",
        "task": "none",
        "next_action": "saipen continue",
        "agent": "test-agent",
    }
    fields.update(state)
    root = fresh_project(**fields)
    row = f"- [ ] T-0001 [P1] Remediate hunt defects | verify: regression passes | {field}\n"
    board = "## DOING\n## TODO\n" + row + "## DONE\n## BLOCKED\n"
    (root / ".saipen" / "BOARD.md").write_text(board, encoding="utf-8")
    return root


class ForeignFieldRowRepairTests(unittest.TestCase):
    def test_the_row_is_recognised_as_losslessly_repairable(self):
        root = _foreign_project()
        text = (root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        self.assertEqual(foreign_field_ticket_ids(text), ["T-0001"])
        # The implicit oversized route is unchanged: nothing is oversized.
        self.assertEqual(oversized_ticket_ids(text), [])

    def test_explicit_compaction_repairs_it_and_keeps_the_original_bytes(self):
        root = _foreign_project()
        board_path = root / ".saipen" / "BOARD.md"
        before = board_path.read_text(encoding="utf-8")
        self.assertTrue(parse_board(before)["errors"])

        repaired = compact_board(root, "T-0001", "test-agent")
        self.assertTrue(repaired.ok, repaired.to_dict())

        after = parse_board(board_path.read_text(encoding="utf-8"))
        self.assertEqual(after["errors"], [])
        ticket = after["tickets"]["T-0001"]
        self.assertNotIn("saihunt", ticket["raw"])
        detail = resolve_detail(root, ticket["fields"]["detail_ref"])
        self.assertIn("source: saihunt HUNT-001", detail["original_record"].decode("utf-8"))
        log = (root / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("field outside the closed grammar compacted losslessly", log)

    def test_recovery_residue_names_the_repair_instead_of_nothing(self):
        root = _foreign_project()
        result = reconcile_protocol_state(root, "test-agent", dry_run=True)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["canonical_next_command"], "saipen ticket compact T-0001", result)

    def test_fleet_names_the_repair_instead_of_nothing(self):
        root = _foreign_project()
        result = preflight(
            explicit_root=root,
            host_root=root,
            host_lineage=project_lineage_identity(root),
        )
        self.assertEqual(result["classification"], CLASS_SAFE, result)
        self.assertEqual(result["reason_code"], "BOARD_FOREIGN_FIELD", result)
        self.assertEqual(result["canonical_next_command"], "saipen ticket compact T-0001")

    def test_a_project_newer_than_the_runtime_is_not_stripped(self):
        root = _foreign_project()
        state_path = root / ".saipen" / "STATE.md"
        text = state_path.read_text(encoding="utf-8")
        self.assertIn("saipen_version: 7", text)
        state_path.write_text(
            text.replace("saipen_version: 7", "saipen_version: 99", 1), encoding="utf-8"
        )
        board_path = root / ".saipen" / "BOARD.md"
        before = board_path.read_bytes()
        with patch("saipen_engine.state.running_protocol_major", return_value=8):
            refused = compact_board(root, "T-0001", "test-agent")
        self.assertFalse(refused.ok)
        self.assertEqual(board_path.read_bytes(), before)

    def test_another_parse_fault_keeps_the_board_fatal(self):
        root = _foreign_project()
        board_path = root / ".saipen" / "BOARD.md"
        text = board_path.read_text(encoding="utf-8").replace(
            "## DONE\n", "## DONE\n- [x] T-0001 duplicate id | verify: x\n", 1
        )
        board_path.write_text(text, encoding="utf-8")
        self.assertEqual(foreign_field_ticket_ids(text), [])
        refused = compact_board(root, "T-0001", "test-agent")
        self.assertFalse(refused.ok)
        self.assertEqual(board_path.read_text(encoding="utf-8"), text)


class ManifestStopsAtTheProjectRootTests(unittest.TestCase):
    """An ancestor ABOVE the project root may be unreadable to the account."""

    def _deny_above(self, root: Path):
        real_lstat = Path.lstat
        denied = {Path(os.path.abspath(p)) for p in root.parents}

        def lstat(self, *args, **kwargs):
            if Path(os.path.abspath(self)) in denied:
                raise PermissionError(5, "Access is denied", str(self))
            return real_lstat(self, *args, **kwargs)

        return patch.object(Path, "lstat", lstat)

    def test_write_succeeds_when_every_ancestor_above_root_is_denied(self):
        root = fresh_project(phase="DONE", task="none", next_action="saipen continue")
        with self._deny_above(root):
            result = audit_manifest.write(root, force=True)
        self.assertTrue(result["ok"], result)
        self.assertTrue((root / ".saipen" / "MANIFEST.json").is_file())

    def test_ensure_succeeds_when_every_ancestor_above_root_is_denied(self):
        root = fresh_project(phase="DONE", task="none", next_action="saipen continue")
        manifest = root / ".saipen" / "MANIFEST.json"
        if manifest.exists():
            manifest.unlink()
        with self._deny_above(root):
            result = audit_manifest.ensure(root)
        self.assertTrue(result["ok"], result)

    def test_a_denied_ancestor_inside_the_project_still_refuses(self):
        # Negative control: the proof itself is intact below the root.
        root = fresh_project(phase="DONE", task="none", next_action="saipen continue")
        real_lstat = Path.lstat
        target = Path(os.path.abspath(root / ".saipen"))

        def lstat(self, *args, **kwargs):
            if Path(os.path.abspath(self)) == target:
                raise PermissionError(5, "Access is denied", str(self))
            return real_lstat(self, *args, **kwargs)

        with patch.object(Path, "lstat", lstat):
            result = audit_manifest.write(root, force=True)
        self.assertFalse(result["ok"], result)
        self.assertIn(".saipen", str(result))


class ProjectedHomeTests(unittest.TestCase):
    """Which homes the machine runtime may stand in for (F5)."""

    def test_a_proven_projection_is_served_and_nothing_else(self):
        source = r"V:\Work\SAIPEN"
        injected = r"C:\Users\op\.agents\skills\saipen"
        registration = {"source_root": source, "projected_homes": [injected]}
        self.assertTrue(machine_runtime.projects(registration, source))
        self.assertTrue(machine_runtime.projects(registration, injected))
        if WINDOWS:
            self.assertTrue(
                machine_runtime.projects(registration, "c:/users/op/.agents/skills/saipen/")
            )
        for other in (r"C:\Users\op\.other\saipen", "", None):
            self.assertFalse(machine_runtime.projects(registration, other), other)
        # A malformed list is no list: it serves nothing beyond the source.
        malformed = {**registration, "projected_homes": injected}
        self.assertFalse(machine_runtime.projects(malformed, injected))
        self.assertFalse(machine_runtime.projects({"projected_homes": [r"X:\h"]}, r"X:\h"))

    def test_only_stamped_registry_surfaces_of_this_source_are_projected(self):
        tmp = Path(tempfile.mkdtemp(prefix="saipen-t1743-homes-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        source = tmp / "checkout"
        (source / "extensions" / "adapters").mkdir(parents=True)
        surfaces = [
            "$T1743_HOME/a/saipen",
            "$T1743_HOME/b/saipen",
            "$T1743_HOME/c/saipen",
            "$T1743_UNSET_VARIABLE/d/saipen",
            str(source),
        ]
        (source / "extensions" / "adapters" / "registry.json").write_text(
            json.dumps({"adapters": [{"id": "x", "skill_surfaces": surfaces}]}), encoding="utf-8"
        )
        for name, declared in (("a", source), ("b", tmp / "elsewhere")):
            home = tmp / name / "saipen"
            home.mkdir(parents=True)
            (home / ".saipen_runtime.json").write_text(
                json.dumps({"canonical_source_root": str(declared)}), encoding="utf-8"
            )
        (tmp / "c" / "saipen").mkdir(parents=True)  # installed, but no stamp
        (source / ".saipen_runtime.json").write_text(
            json.dumps({"canonical_source_root": str(source)}), encoding="utf-8"
        )
        with patch.dict(os.environ, {"T1743_HOME": str(tmp)}):
            found = machine_runtime.projected_homes(source)
        self.assertEqual(found, [os.path.abspath(tmp / "a" / "saipen")])


@unittest.skipUnless(WINDOWS, "an access list that denies the owner needs icacls")
class ProjectedHomeIsServedTests(_Scratch):
    """The SMART_VAC_CLEANER layout: the project records an injector home of
    the source; the account cannot read it; the machine runtime serves it."""

    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "ProgramData" / "SAI" / "SAIPEN"
        source = an_install(self.tmp / "operator" / "checkout")
        report = machine_runtime.install(source, self.root, python=sys.executable, env=self.env)
        self.assertTrue(report["saipen_runtime_ready"], report)
        self.injected = an_install(self.tmp / "operator" / ".agents" / "skills" / "saipen")
        registration_path = self.root / "registration.json"
        registration = json.loads(registration_path.read_text(encoding="utf-8"))
        registration["projected_homes"] = [str(self.injected)]
        registration_path.write_text(json.dumps(registration, indent=2), encoding="utf-8")
        deny_this_account(self.injected)
        deny_this_account(source)
        self.project, self.tid = self.project_recording(self.injected)
        self.launcher = [str(self.root / "bin" / "saipen.cmd")]

    def through_machine(self, *args: str) -> dict:
        return self.ask([*self.launcher, *args], self.project, **{ENV_ROOT: str(self.root)})

    def test_bootstrap_says_replaced_and_owes_the_operator_nothing(self):
        answer = self.through_machine("host", "bootstrap")
        self.assertEqual(answer.get("code"), "HOST_BOOTSTRAP_BOUND", answer)
        binding = answer["binding"]
        self.assertEqual(binding["legacy_saipen_home"], "INACCESSIBLE_BUT_REPLACED", binding)
        self.assertNotIn("needs the operator", str(binding.get("reason")))

    def test_a_lifecycle_write_lands_and_the_recorded_home_is_untouched(self):
        answer = self.through_machine("checkpoint", "DEC", "note through the projected home")
        self.assertTrue(answer.get("ok"), answer)
        self.assertEqual(answer.get("code"), "CHECKPOINTED")
        self.assertEqual(self.recorded_home(self.project), str(self.injected))
        with self.assertRaises(PermissionError):
            (self.injected / "BOOT.md").read_bytes()

    def test_an_unlisted_home_is_still_refused(self):
        stranger = self.private_home()
        project, _tid = self.project_recording(stranger)
        answer = self.ask(
            [*self.launcher, "checkpoint", "DEC", "note"], project, **{ENV_ROOT: str(self.root)}
        )
        self.assertEqual(answer.get("code"), DENIED, answer)

    def test_a_dry_run_write_meets_the_same_gate_and_writes_nothing(self):
        # The write-admission oracle a broker can run as the account: the same
        # gate answers, and nothing in the project changes either way.
        log = self.project / ".saipen" / "LOG.md"
        before = log.read_bytes()
        served = self.through_machine("checkpoint", "DEC", "admission probe", "--dry-run")
        self.assertTrue(served.get("ok"), served)
        self.assertEqual(log.read_bytes(), before)
        stranger = self.private_home()
        project, _tid = self.project_recording(stranger)
        refused = self.ask(
            [*self.launcher, "checkpoint", "DEC", "admission probe", "--dry-run"],
            project,
            **{ENV_ROOT: str(self.root)},
        )
        self.assertEqual(refused.get("code"), DENIED, refused)


@unittest.skipUnless(WINDOWS, "the machine launcher under test is the Windows one")
class PrunedGenerationPointerTests(_Scratch):
    """SUNO_DOWNLOADER: STATE recorded a machine-runtime generation directory
    that a later upgrade pruned (F6)."""

    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "ProgramData" / "SAI" / "SAIPEN"
        source = an_install(self.tmp / "operator" / "checkout")
        report = machine_runtime.install(source, self.root, python=sys.executable, env=self.env)
        self.assertTrue(report["saipen_runtime_ready"], report)
        self.pruned = self.root / "runtime" / "0123456789abcdef"
        self.assertFalse(self.pruned.exists())
        self.project, self.tid = self.project_recording(self.pruned)
        self.launcher = [str(self.root / "bin" / "saipen.cmd")]

    def through_machine(self, *args: str) -> dict:
        return self.ask([*self.launcher, *args], self.project, **{ENV_ROOT: str(self.root)})

    def test_the_pointer_follows_the_current_generation(self):
        with patch.dict(os.environ, {ENV_ROOT: str(self.root)}):
            current = machine_runtime.current_generation_for(str(self.pruned))
            status = persisted_home_access(str(self.pruned))
        self.assertIsNotNone(current)
        self.assertTrue(current.is_dir())
        self.assertEqual(status[0], "usable", status)

    def test_a_write_lands_instead_of_home_required(self):
        bound = self.through_machine("host", "bootstrap")
        self.assertEqual(bound.get("code"), "HOST_BOOTSTRAP_BOUND", bound)
        self.assertFalse(bound["binding"]["persisted_home_dead"], bound["binding"])
        answer = self.through_machine("checkpoint", "DEC", "note through a pruned generation")
        self.assertTrue(answer.get("ok"), answer)
        self.assertEqual(answer.get("code"), "CHECKPOINTED")
        self.assertEqual(self.recorded_home(self.project), str(self.pruned))

    def test_a_runtime_dir_elsewhere_is_still_dead(self):
        elsewhere = self.tmp / "not-the-machine" / "runtime" / "0123456789abcdef"
        with patch.dict(os.environ, {ENV_ROOT: str(self.root)}):
            self.assertIsNone(machine_runtime.current_generation_for(str(elsewhere)))
            status = persisted_home_access(str(elsewhere))
        self.assertEqual(status[0], "dead", status)


if __name__ == "__main__":
    unittest.main()
