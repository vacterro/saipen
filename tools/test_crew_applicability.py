"""T-1279 regression tests: a capability with nothing to apply to.

The roster was static. `CrewRole.ensure_instance` was a bool, `crew.py`
iterated it, and no code path could express that a project has no UI -- so a
mandatory UI stage ran against a surface that does not exist, eleven times,
and each honest empty package became a Core review ticket.

Proven here:
- the applicability decision is a pure function of deterministic project facts;
- every undecidable input -- no facts, an unreadable tree, an unknown probe
  name -- resolves APPLICABLE, so the model fails toward doing the work;
- a NOT_APPLICABLE role satisfies its crew stage through a receipt that NAMES
  the deciding fact and carries no action;
- the probe is NOT vacuous: on a tree that does contain a visual file the same
  role is APPLICABLE again and its stage goes back to demanding evidence;
- the desktop-UI case is covered by import, not only by extension, so a Tk or
  Qt application is not invisible because its files end in `.py`.

Run standalone:
    python tools/test_crew_applicability.py

Exit code 0 when every test passes.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import applicability as A  # noqa: E402
from saipen_engine import crew as C  # noqa: E402
from saipen_engine import subs as S  # noqa: E402

REPO = TOOLS.parent

STATE = (
    '---\nphase: DONE\ntask: none\nnext_action: "saipen continue"\n'
    'blocker: ""\ntransition_from: SHIP\nsaipen_version: 7\n'
    'schema_version: 3\nstyle_contract: ded-probe\nsaipen_home: "{home}"\n'
    'agent: probe\nmode: full\nupdated: "2026-09-03T00:00:00Z"\n---\n'
)
BOARD = "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n\n## BLOCKED\n"


FULL_ROSTER = ("saihunt", "saitest", "saipython", "saiui", "saiwiki")


def _seed(root: Path, roles=FULL_ROSTER) -> None:
    """The same minimal crew-capable project the scenario harness seeds."""
    saipen = root / ".saipen"
    (saipen / "extensions").mkdir(parents=True, exist_ok=True)
    (saipen / "STATE.md").write_text(STATE.format(home=REPO.as_posix()), encoding="utf-8")
    (saipen / "LOG.md").write_text("# Log\n", encoding="utf-8")
    (saipen / "BOARD.md").write_text(BOARD, encoding="utf-8")
    for name in roles:
        result = S.sub_spawn(root, name, REPO.as_posix())
        if not result.ok:
            raise AssertionError(f"fixture spawn {name} failed: {result.to_json()}")


def _stage(plan: dict, stage_id: str) -> dict:
    for stage in plan.get("stages", ()):
        if stage.get("stage") == stage_id:
            return stage
    present = [s.get("stage") for s in plan.get("stages", ())]
    raise AssertionError(f"{stage_id} absent from plan stages {present}")


# ---------------------------------------------------------------------------
# The pure decision. No filesystem below this point.
# ---------------------------------------------------------------------------


class VerdictTests(unittest.TestCase):
    def test_always_probe_is_applicable_and_says_why(self):
        state, reason = A.verdict(A.ALWAYS, A.ProjectFacts(scanned=10))
        self.assertEqual(state, A.APPLICABLE)
        self.assertTrue(reason)

    def test_empty_visual_surface_is_not_applicable_and_names_the_count(self):
        state, reason = A.verdict(A.VISUAL_SURFACE, A.ProjectFacts(scanned=4953))
        self.assertEqual(state, A.NOT_APPLICABLE)
        self.assertIn("4953", reason)
        self.assertIn("no visual implementation file", reason)

    def test_one_visual_file_flips_the_verdict_and_names_it(self):
        facts = A.ProjectFacts(visual_paths=("web/app.css",), scanned=4954)
        state, reason = A.verdict(A.VISUAL_SURFACE, facts)
        self.assertEqual(state, A.APPLICABLE)
        self.assertIn("web/app.css", reason)

    def test_a_desktop_toolkit_import_alone_is_a_visual_surface(self):
        facts = A.ProjectFacts(gui_module_paths=("app/window.py",), scanned=12)
        self.assertEqual(A.verdict(A.VISUAL_SURFACE, facts)[0], A.APPLICABLE)

    def test_every_reason_is_non_empty_for_every_probe_and_both_answers(self):
        for probe in (*A.PROBES, "a-probe-nobody-registered"):
            for facts in (A.ProjectFacts(scanned=1), A.ProjectFacts(visual_paths=("a.css",))):
                _state, reason = A.verdict(probe, facts)
                self.assertTrue(reason.strip(), f"empty reason for {probe}")

    def test_evidence_sample_is_bounded(self):
        facts = A.ProjectFacts(visual_paths=tuple(f"p{i}.css" for i in range(50)))
        self.assertEqual(len(facts.visual_evidence()), 3)


class FailClosedTests(unittest.TestCase):
    """Undecidable is APPLICABLE. A capability is never retired by silence."""

    def test_absent_facts_are_applicable(self):
        state, reason = A.verdict(A.VISUAL_SURFACE, None)
        self.assertEqual(state, A.APPLICABLE)
        self.assertIn("fails closed", reason)

    def test_unreadable_tree_is_applicable_and_carries_the_reason(self):
        facts = A.ProjectFacts(readable=False, unreadable_reason="tree walk failed: boom")
        state, reason = A.verdict(A.VISUAL_SURFACE, facts)
        self.assertEqual(state, A.APPLICABLE)
        self.assertIn("boom", reason)

    def test_unknown_probe_name_is_applicable_and_names_itself(self):
        state, reason = A.verdict("visual-surfaec", A.ProjectFacts(scanned=3))
        self.assertEqual(state, A.APPLICABLE)
        self.assertIn("visual-surfaec", reason)

    def test_no_constant_answer_satisfies_the_suite(self):
        """Red control: neither verdict can be hardcoded and still pass.

        A probe that always answered APPLICABLE would never skip anything and
        the empty-surface case fails; one that always answered NOT_APPLICABLE
        would retire a real capability and every fail-closed case fails.
        """
        empty = A.verdict(A.VISUAL_SURFACE, A.ProjectFacts(scanned=9))[0]
        present = A.verdict(A.VISUAL_SURFACE, A.ProjectFacts(visual_paths=("x.vue",)))[0]
        unknown = A.verdict(A.VISUAL_SURFACE, None)[0]
        self.assertEqual(empty, A.NOT_APPLICABLE)
        self.assertEqual(present, A.APPLICABLE)
        self.assertEqual(unknown, A.APPLICABLE)
        self.assertNotEqual(empty, present)


# ---------------------------------------------------------------------------
# Fact collection against a real tree.
# ---------------------------------------------------------------------------


class CollectFactsTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_a_tree_with_no_visual_file_reports_none(self):
        (self.root / "tool.py").write_text("import json\n", encoding="utf-8")
        facts = A.collect_facts(self.root)
        self.assertTrue(facts.readable)
        self.assertFalse(facts.visual_surface)

    def test_a_stylesheet_is_found_by_extension(self):
        (self.root / "site").mkdir()
        (self.root / "site" / "main.css").write_text("body{}\n", encoding="utf-8")
        self.assertTrue(A.collect_facts(self.root).visual_surface)

    def test_a_tk_application_is_found_by_import(self):
        (self.root / "gui.py").write_text("import tkinter as tk\n", encoding="utf-8")
        facts = A.collect_facts(self.root)
        self.assertTrue(facts.visual_surface)
        self.assertIn("gui.py", facts.gui_module_paths)

    def test_saipen_memory_never_counts_as_the_project_gaining_a_ui(self):
        """A producer's staged page under `.saipen/` is not a project surface.

        Same reason PROTOCOL.md section 6 excludes `.saipen/` from the source
        fingerprint: a worker's own kitchen is not the project.
        """
        staged = self.root / ".saipen" / "extensions" / "subs" / "saiwiki" / "kitchen"
        staged.mkdir(parents=True)
        (staged / "Home.html").write_text("<p>x</p>\n", encoding="utf-8")
        self.assertFalse(A.collect_facts(self.root).visual_surface)

    def test_this_repository_has_no_visual_surface(self):
        facts = A.collect_facts(REPO)
        self.assertTrue(facts.readable)
        self.assertGreater(facts.scanned, 100)
        self.assertFalse(
            facts.visual_surface,
            f"unexpected visual surface: {facts.visual_evidence()}",
        )


# ---------------------------------------------------------------------------
# The crew stage receipt.
# ---------------------------------------------------------------------------


class CrewStageTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "proj"
        self.root.mkdir()
        _seed(self.root)

    def test_a_non_applicable_role_is_dropped_from_the_applicable_set(self):
        snapshot = C.crew_snapshot(self.root)
        names = {role.name for role in C.applicable_roles(snapshot)}
        self.assertNotIn("saiui", names)
        for still_here in ("saihunt", "saitest", "saipython", "saiwiki", "saitranslate"):
            self.assertIn(still_here, names)

    def test_the_stage_is_satisfied_by_a_receipt_naming_the_deciding_fact(self):
        stage = _stage(C.crew_plan(self.root), "SC-5")
        self.assertTrue(stage["satisfied"], stage)
        self.assertIsNone(stage["action"], stage)
        self.assertTrue(stage["reason"].startswith("NOT_APPLICABLE -- "), stage["reason"])
        self.assertIn("no visual implementation file", stage["reason"])

    def test_a_visual_file_puts_the_stage_back_to_demanding_evidence(self):
        """Positive control: the skip cannot go vacuous.

        Without this, a probe that had silently broken into always answering
        NOT_APPLICABLE would pass every other test in this file. Note what is
        asserted: the stage stops carrying the receipt and saiui rejoins the
        applicable set. It is NOT asserted to be actionable here, because in
        this fixture SC-2 is still unsatisfied and an ordinary evidence-bearing
        stage behind a blocker correctly reports WAITING -- which is the very
        distinction the receipt exists to make.
        """
        (self.root / "app").mkdir()
        (self.root / "app" / "main.css").write_text("body{color:#000}\n", encoding="utf-8")
        snapshot = C.crew_snapshot(self.root)
        self.assertIn("saiui", {role.name for role in C.applicable_roles(snapshot)})
        stage = _stage(C.crew_plan(self.root), "SC-5")
        self.assertNotIn("NOT_APPLICABLE", stage["reason"] or "")
        self.assertFalse(stage["satisfied"], stage)

    def test_the_other_sensor_stages_are_untouched(self):
        plan = C.crew_plan(self.root)
        for stage_id in ("SC-2", "SC-3", "SC-4"):
            stage = _stage(plan, stage_id)
            self.assertNotIn("NOT_APPLICABLE", stage["reason"] or "")

    def test_a_role_with_no_applicability_declared_defaults_to_always(self):
        for role in S.CREW_ROLES:
            if role.name == "saiui":
                self.assertEqual(role.applicability, A.VISUAL_SURFACE)
            else:
                self.assertEqual(role.applicability, A.ALWAYS)

    def test_every_declared_probe_is_a_registered_one(self):
        for role in S.CREW_ROLES:
            self.assertIn(role.applicability, A.PROBES, role.name)


class HotPathCostTests(unittest.TestCase):
    """`crew_snapshot` is on the cc/sc/status path; the walk is not free.

    A Git subprocess plus a bounded read of every module, spent to answer a
    question no role asked, is the cost T-1019 counts. Skipping it changes
    timing and never a verdict: None resolves APPLICABLE for every probe,
    which is what an all-`always` roster would have answered anyway.
    """

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_an_all_always_roster_collects_nothing(self):
        plain = tuple(
            replace(role, applicability=A.ALWAYS) for role in S.CREW_ROLES
        )
        with mock.patch.object(C, "CREW_ROLES", plain):
            self.assertIsNone(C._project_facts(self.root))

    def test_one_conditional_role_is_enough_to_collect(self):
        self.assertTrue(
            any(role.applicability != A.ALWAYS for role in S.CREW_ROLES),
            "fixture assumption: the live registry has a conditional role",
        )
        facts = C._project_facts(self.root)
        self.assertIsNotNone(facts)
        self.assertTrue(facts.readable)

    def test_skipping_collection_does_not_change_any_verdict(self):
        """The optimisation is verdict-preserving, which is the whole licence."""
        plain = tuple(replace(role, applicability=A.ALWAYS) for role in S.CREW_ROLES)
        collected = A.collect_facts(self.root)
        for role in plain:
            self.assertEqual(
                A.verdict(role.applicability, None)[0],
                A.verdict(role.applicability, collected)[0],
                role.name,
            )


class RosterStageTests(unittest.TestCase):
    """SC-1: an instance is machinery for producing evidence.

    A role with nothing to produce evidence ABOUT does not need one spawned,
    registered in the manifest or re-adopted on every charter revision. Without
    this the applicability model would still save the model run and then demand
    the instance anyway, which is the ceremony half of the same cost.
    """

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "proj"
        self.root.mkdir()

    def test_a_missing_non_applicable_instance_is_not_demanded(self):
        _seed(self.root, roles=("saihunt", "saitest", "saipython", "saiwiki"))
        stage = _stage(C.crew_plan(self.root), "SC-1")
        self.assertNotIn("saiui", stage["reason"] or "")
        action = stage["action"] or {}
        self.assertNotEqual(action.get("role"), "saiui", stage)

    def test_the_same_missing_instance_IS_demanded_once_a_ui_exists(self):
        """Positive control for SC-1: the roster skip is conditional, not gone."""
        _seed(self.root, roles=("saihunt", "saitest", "saipython", "saiwiki"))
        (self.root / "ui").mkdir()
        (self.root / "ui" / "panel.svelte").write_text("<div/>\n", encoding="utf-8")
        stage = _stage(C.crew_plan(self.root), "SC-1")
        self.assertFalse(stage["satisfied"], stage)
        self.assertIn("saiui", stage["reason"] or "")
        self.assertEqual((stage["action"] or {}).get("role"), "saiui", stage)

    def test_a_missing_applicable_instance_is_still_demanded(self):
        _seed(self.root, roles=("saitest", "saipython", "saiui", "saiwiki"))
        stage = _stage(C.crew_plan(self.root), "SC-1")
        self.assertFalse(stage["satisfied"], stage)
        self.assertIn("saihunt", stage["reason"] or "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
