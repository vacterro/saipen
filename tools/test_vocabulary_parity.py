"""Every closed vocabulary has ONE declared owner, and the copies must agree.

The defect class this ends, measured four times in one session on 2026-09-22:
a closed set of tokens gets copied into a second module, the two drift, and
the surfaces answer different questions with the same name.

* `deferred_state` asked `blocker_class`, so every recognized blocker became an
  operator due-time gate (T-1429).
* `cold_recovery.classify_blocker` kept its own copy of the same vocabulary and
  published every parked ticket as DUE.
* `status`'s `waiting_on_you` kept a THIRD copy, listing only the two
  WAIT_USER classes, so real BLOCKED_EXTERNAL operator work was invisible.
* `discharge_request_clauses` kept a fourth, `!= "user_instruction"`, and
  silently skipped every corrective_followup forever.

All four were found by reading, one at a time, after the damage. This suite
finds the next one mechanically. It does not refactor the copies away -- a
duplicate that is CHECKED is not the defect; a duplicate that drifts unnoticed
is -- so the cost is one assertion per vocabulary instead of a rewrite of every
module that reads it.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import board, cold_recovery, entry, intake, state, supervisor  # noqa: E402

REGISTRY = json.loads((ROOT / "saipen" / "REGISTRY.json").read_text(encoding="utf-8"))

#: One routing-table row: a backticked `saipen <verb> ...` command literal in
#: any column. The table is the surface an agent routes by, so a verb the
#: engine dispatches but no row names is a command that exists only in source.
_ROW_COMMAND = re.compile(r"\|\s*`saipen ([a-z][a-z0-9-]*)([^`]*)`")

class RoutingTableCoverageTests(unittest.TestCase):
    """T-407: every registered subcommand has a COMMANDS.md row naming it.

    Measured live on `Wintage` 2026-10-05: `COMMAND_EFFECTS.json` carried 15
    `source` subcommands and the routing table named 9, so `saipen source
    capture` and `saipen source close` -- the two verbs that bound the
    SOURCE-AUDIT-INBOX-01 lifecycle, capture being the ingress and close the
    ONLY writer of the tombstone the consume gate requires -- were discoverable
    only by reading `saipen.py`. Ten verbs were affected and 32 subcommands
    appeared nowhere in the document at all.

    The registry was already complete, so this is not a second registry: it is
    the check that the prose routing table keeps up with the machine facts it
    claims to own. Harvested, never restated -- a new subcommand fails here
    instead of in a session that greps for it.
    """

    def setUp(self):
        effects = json.loads(
            (ROOT / "saipen" / "COMMAND_EFFECTS.json").read_text(encoding="utf-8-sig")
        )
        document = (ROOT / "saipen" / "COMMANDS.md").read_text(encoding="utf-8-sig")
        rows: dict[str, list[str]] = {}
        for match in _ROW_COMMAND.finditer(document):
            rows.setdefault(match.group(1), []).append(match.group(2))
        self.rows = rows
        self.subcommands = {
            verb: spec["subcommands"]
            for verb, spec in effects["verbs"].items()
            if isinstance(spec, dict) and spec.get("subcommands")
        }

    def test_every_registered_verb_has_a_row(self):
        missing = sorted(verb for verb in self.subcommands if verb not in self.rows)
        self.assertEqual(missing, [], "a dispatching verb with no routing-table row")

    def test_every_registered_subcommand_is_named_by_a_row(self):
        gaps: dict[str, list[str]] = {}
        for verb, subcommands in self.subcommands.items():
            named = self.rows.get(verb, [])
            # A row may bundle its subcommands in brackets
            # (`saipen storage [status|...]`) or spread them over several rows,
            # so any word-boundary match in ANY row of that verb counts.
            unnamed = [
                sub
                for sub in subcommands
                if not any(
                    re.search(rf"(?<![a-z0-9-]){re.escape(sub)}(?![a-z0-9-])", row)
                    for row in named
                )
            ]
            if unnamed:
                gaps[verb] = unnamed
        self.assertEqual(
            gaps,
            {},
            "COMMANDS.md owns command semantics; a subcommand the engine "
            "dispatches but no row names is discoverable only by reading source",
        )


class PhaseVocabularyTests(unittest.TestCase):
    """`REGISTRY.phases.ticket_bearing` owns which phases carry a ticket."""

    def setUp(self):
        self.declared = set(REGISTRY["phases"]["ticket_bearing"])

    def test_the_declared_set_is_not_empty(self):
        self.assertTrue(self.declared)

    def test_entry_agrees_with_the_declaration(self):
        self.assertEqual(set(entry._WORK_PHASES), self.declared)

    def test_the_schema_enum_agrees_with_the_declaration(self):
        schema = json.loads(
            (ROOT / "extensions" / "schemas" / "board.schema.json").read_text(encoding="utf-8")
        )
        resume = schema["items"]["properties"]["resume_phase"]["enum"]
        self.assertEqual(set(resume), self.declared)

    def test_the_hardcoded_copies_in_the_engine_agree(self):
        # Read the literal tuples out of the modules that keep their own copy.
        # A drifted copy shows up here as a set difference, named by file.
        import re

        pattern = re.compile(
            r"\(\s*\"SCOUT\"\s*,\s*\"BUILD\"\s*,\s*\"VERIFY\"\s*,\s*\"REVIEW\"\s*,\s*\"SHIP\"\s*\)"
        )
        for relative in (
            "tools/saipen_engine/fast_check.py",
            "tools/saipen_engine/state.py",
            "tools/validate.py",
        ):
            with self.subTest(file=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertTrue(
                    pattern.search(text),
                    f"{relative} no longer carries the declared ticket-bearing "
                    "phase tuple -- either it now reads the owner (good: drop "
                    "this entry) or it drifted (bad: that is the defect)",
                )

    def test_phase_order_covers_every_ticket_bearing_phase(self):
        from saipen_metrics import PHASE_ORDER

        self.assertTrue(self.declared.issubset(set(PHASE_ORDER)))


class BlockerVocabularyTests(unittest.TestCase):
    """`board` owns blocker classification. Nothing else may widen it."""

    def test_the_operator_set_is_a_strict_subset_of_the_recognized_set(self):
        # The whole T-1429 defect in one assertion: these are different
        # questions, so the sets must not become the same set.
        recognized = set(board._NON_CLOSURE_BLOCKER_TOKENS)
        operator = set(board._DEFERRED_OPERATOR_BLOCKER_CLASSES)
        self.assertTrue(operator < recognized, "operator-owned is NARROWER than recognized")

    def test_the_operator_set_is_exactly_the_evidenced_three(self):
        # Expanding this needs live repository evidence of an explicit
        # operator-owned contract, recorded with the change.
        self.assertEqual(
            set(board._DEFERRED_OPERATOR_BLOCKER_CLASSES),
            {"WAIT_USER_CONFIRMATION", "WAIT_USER_DECISION", "BLOCKED_EXTERNAL"},
        )

    def test_cold_recovery_derives_its_gate_from_the_owner(self):
        for blocker in sorted(board._NON_CLOSURE_BLOCKER_TOKENS):
            with self.subTest(blocker=blocker):
                self.assertEqual(
                    cold_recovery.classify_blocker(blocker)["is_operator_gate"],
                    board.deferred_operator_class(blocker) is not None,
                )

    def test_the_only_extra_class_cold_recovery_names_is_the_dependency_hold(self):
        self.assertEqual(cold_recovery.DEPENDENCY_HOLD_PREFIX, "ACTIVE_DEPENDENCY")
        verdict = cold_recovery.classify_blocker("ACTIVE_DEPENDENCY:T-1 -- paused")
        self.assertTrue(verdict["is_parked_hold"])
        self.assertFalse(verdict["is_operator_gate"])


class SourceVocabularyTests(unittest.TestCase):
    def test_request_kinds_are_a_subset_of_the_declared_source_kinds(self):
        self.assertTrue(set(intake.REQUEST_KINDS) < set(intake.SOURCE_KINDS))

    def test_an_audit_is_never_a_request_kind(self):
        for kind in ("external_audit", "user_audit", "imported_spec"):
            with self.subTest(kind=kind):
                self.assertNotIn(kind, intake.REQUEST_KINDS)

    def test_every_coverage_refusal_code_is_registered(self):
        declared = set(REGISTRY["error_codes"])
        for code in intake._COVERAGE_NEXT_COMMAND:
            with self.subTest(code=code):
                self.assertIn(code, declared)


class SupervisorVocabularyTests(unittest.TestCase):
    def test_every_verdict_is_routable_and_classified(self):
        self.assertEqual(set(supervisor.NEXT_COMMAND), set(supervisor.VERDICTS))
        self.assertTrue(supervisor.MUTATING_VERDICTS.issubset(supervisor.VERDICTS))

    def test_supervisor_refusal_codes_are_registered(self):
        declared = set(REGISTRY["error_codes"])
        for code in ("AMBIGUOUS_AUTHORITY", "LIVE_LEASE_PRESENT", "FENCED_LEASE_GENERATION"):
            with self.subTest(code=code):
                self.assertIn(code, declared)

    def test_the_autonomy_verb_is_declared_where_the_surface_is_declared(self):
        effects = json.loads(
            (ROOT / "saipen" / "COMMAND_EFFECTS.json").read_text(encoding="utf-8")
        )
        self.assertIn("autonomy", REGISTRY["commands"]["saipen"])
        self.assertEqual(effects["verbs"]["autonomy"], "DIAGNOSTIC")

    def test_every_registered_verb_has_a_resolvable_effect_class(self):
        # `hush` is the one registered token that is NOT a verb: it is the
        # execution-policy MODIFIER, so it has no class of its own and must
        # resolve to the class of the task it modifies. Everything else needs
        # a declared entry, or it silently falls to `unknown_class`.
        from saipen_engine import command_effects, hush

        effects = json.loads(
            (ROOT / "saipen" / "COMMAND_EFFECTS.json").read_text(encoding="utf-8")
        )
        missing = [
            verb
            for verb in REGISTRY["commands"]["saipen"]
            if verb not in effects["verbs"] and verb != hush.MODIFIER
        ]
        self.assertEqual(missing, [], "a verb with no declared effect class")
        self.assertNotIn(hush.MODIFIER, effects["verbs"], "a modifier is not a verb")
        self.assertEqual(
            command_effects.classify_tokens(["saipen", hush.MODIFIER, "status"]),
            command_effects.classify_tokens(["saipen", "status"]),
            "hush <task> classifies as <task>, or a hushed read-only command is "
            "judged a write and refused in read-only capability",
        )

    def test_the_modifier_is_stripped_only_at_the_head(self):
        from saipen_engine import command_effects as ce
        from saipen_engine import hush

        self.assertEqual(ce.classify_tokens(["saipen", hush.MODIFIER, "ship"]), ce.EXECUTION)
        self.assertEqual(ce.classify_tokens(["saipen", hush.MODIFIER]), ce.DIAGNOSTIC)
        self.assertEqual(
            ce.classify_tokens(["saipen", hush.MODIFIER, hush.MODIFIER, "status"]),
            ce.UNKNOWN_CLASS,
            "a second hush is the TASK, not a second modifier",
        )

    def test_a_hushed_diagnostic_needs_no_fleet_preparation(self):
        # The measured consequence: EXECUTION demands fleet preparation, so a
        # hushed status probe was pre-empted by a preflight it never needed.
        from saipen_engine import command_effects as ce
        from saipen_engine import hush

        klass = ce.classify_tokens(["saipen", hush.MODIFIER, "status"])
        self.assertFalse(ce.fleet_preflight_required(klass))


class BoardSectionVocabularyTests(unittest.TestCase):
    def test_the_declared_sections_and_checkboxes_agree_with_the_parser(self):
        declared = REGISTRY["ticket_states"]
        parsed = board.parse_board(
            "## DOING\n"
            "- [/] T-1 [P1] doing | verify: x\n"
            "## TODO\n"
            "- [ ] T-2 [P1] todo | verify: x\n"
            "## DONE\n"
            "- [x] T-3 [P1] done | verify: x\n"
            "## BLOCKED\n"
            "- [ ] T-4 [P1] blocked | verify: x | blocker: HELD -- hold\n"
        )
        sections = {t["id"]: t["section"] for t in parsed["tickets"].values()}
        for ticket, name in (("T-1", "DOING"), ("T-2", "TODO"), ("T-3", "DONE"),
                             ("T-4", "BLOCKED")):
            with self.subTest(ticket=ticket):
                self.assertIn(name, declared["sections"])
                self.assertEqual(sections[ticket], f"## {name}")

    def test_the_state_module_knows_every_declared_phase(self):
        known = set(REGISTRY["phases"]["all"])
        self.assertTrue(known)
        self.assertEqual(set(state.STATE_PHASE_ENUM), known)


if __name__ == "__main__":
    unittest.main()
