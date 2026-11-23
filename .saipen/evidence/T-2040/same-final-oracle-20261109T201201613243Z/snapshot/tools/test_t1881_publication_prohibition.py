"""T-1881 / SRC-306:R004 (audit D-06): a ticket-scoped publication prohibition.

D-06 is the one finding in SRC-306 whose measured failure is an *attempt*, not
a publication: a session under an explicit `PUBLICATION: FORBIDDEN` instruction
ran `saipen ship`, and the engine reached the remote-classification step
because the only "no publication" authority it knew was the SESSION capability
-- and a goal session negotiates `full`. Nothing durable recorded that a
publication had even been tried: the DONE line answers "is this ticket done?",
which is a different question.

What this module pins, in both directions:

  * a live ticket carrying `| publication: forbidden` refuses the RELEASE PLAN
    with RELEASE_FORBIDDEN, and the refusal happens BEFORE the first remote
    query -- the D-06 requirement is preventive, not a post-hoc report;
  * the SAME project still closes locally in a no-publish session. Lifecycle
    closure and external publication are separate questions, and a
    prohibition must never take the first one away;
  * a prohibition written BETWEEN plan and apply refuses the apply, because a
    plan is not the last word and the board it was built against is not the
    board the push would run against;
  * a prohibition on ANY member of a cohort batch binds the whole batch. A
    batch published for several tickets and forbidden for one of them is
    forbidden;
  * absence of the field is not permission and not a prohibition: a project
    that never declares it behaves exactly as before;
  * a typo or a granting value is REFUSED rather than ignored, because a
    reader that treated `publication: frobidden` as absent would publish
    exactly what the operator forbade, and `allowed` would be a second,
    model-writable place to grant publication authority;
  * the attempt is recorded in its own ledger, one row per real attempt, and
    it is written at the invocation boundary rather than by the release
    executor -- so "a refusal writes nothing" stays true for direct engine
    callers, and one release verdict never depends on whether the audit trail
    could be appended.

The red control is `test_a_forbidden_ticket_refuses_the_plan_before_any_network_call`:
removing the planner gate turns it red, and the network spy records the call
that would have happened.

Run standalone:
    python tools/test_t1881_publication_prohibition.py
"""

from __future__ import annotations

import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_source_receipts as fixtures  # noqa: E402
import test_no_publish_source_scope as source_scope  # noqa: E402
from saipen_engine import board as board_mod  # noqa: E402
from saipen_engine import release, release_attempt  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

DOING_LINE = "- [/] T-001 current task | verify: current"
FORBIDDEN_DOING = DOING_LINE + " | publication: forbidden"


def setUpModule() -> None:
    isolate_host_session()


class _ReleaseFixture(unittest.TestCase):
    """The real source-receipt project the release fixtures share.

    The release engine is entirely real (preflight, source gate, journal); only
    `_check_parity` is supplied, because this minimal fixture has no versioned
    protocol install and parity is not what any test here measures.

    The project builder is borrowed by ATTRIBUTE from its owning module rather
    than by importing the class: `from ... import LocalSourceClosure` would put
    a TestCase subclass in this module's namespace, and the loader would then
    run that module's fifteen tests here a second time.
    """

    setUp = fixtures.SourceReceiptTests.setUp
    tearDown = fixtures.SourceReceiptTests.tearDown
    resolve = fixtures.SourceReceiptTests.resolve
    _scope_file = fixtures.SourceReceiptTests._scope_file
    _record_scope = fixtures.SourceReceiptTests._record_scope
    _complete_work = fixtures.SourceReceiptTests._complete_work
    _incomplete_work = fixtures.SourceReceiptTests._incomplete_work
    _project = source_scope.LocalSourceClosure._project
    _snapshot = source_scope.LocalSourceClosure._snapshot

    def _forbid(self, ticket_line: str = DOING_LINE) -> None:
        path = self.root / ".saipen/BOARD.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn(ticket_line, text)
        path.write_text(
            text.replace(ticket_line, ticket_line + " | publication: forbidden"),
            encoding="utf-8",
        )

    def _plan(self, capability: str = "no-publish"):
        with patch.object(release, "_check_parity", return_value=None):
            return release.plan_release(
                self.root, "ship", current_capability=capability
            )

    def _refusal(self, capability: str = "full", **kwargs) -> release.ReleaseRefusal:
        with self.assertRaises(release.ReleaseRefusal) as caught:
            self._plan_with(capability, **kwargs)
        return caught.exception

    def _plan_with(self, capability: str, **kwargs):
        with patch.object(release, "_check_parity", return_value=None):
            return release.plan_release(
                self.root, "ship", current_capability=capability, **kwargs
            )


class PlanTimeProhibitionTests(_ReleaseFixture):
    def test_a_forbidden_ticket_refuses_the_plan_before_any_network_call(self):
        """RED CONTROL: without the planner gate this reaches `_remote_snapshot`.

        D-06's exact shape is "the prohibition was never consulted". So the
        spy is the assertion: not merely that a refusal happened, but that no
        remote query was issued to produce it.
        """
        self._project()
        self._forbid()
        calls: list[str] = []

        def spy(root, endpoint):
            calls.append(endpoint)
            raise AssertionError(
                "a publication query was issued for a forbidden ticket -- "
                "this is the D-06 defect exactly"
            )

        with patch.object(release, "_remote_snapshot", side_effect=spy):
            refusal = self._refusal("full")

        self.assertEqual(refusal.code, "RELEASE_FORBIDDEN", refusal.detail)
        self.assertEqual(calls, [], "no remote classification may be attempted")
        self.assertIn("T-001", refusal.detail)
        self.assertIn("publication: forbidden", refusal.detail)
        # The sentence must say the two things an agent needs: that nothing
        # external happened, and that closing the Work is still available.
        self.assertIn("Nothing was pushed", refusal.detail)
        self.assertIn("Lifecycle closure stays available", refusal.detail)

    def test_the_prohibition_cannot_be_lifted_by_the_session_that_wrote_it(self):
        self._project()
        self._forbid()
        refusal = self._refusal("full")
        self.assertIn("never be lifted by the same session that wrote it", refusal.detail)

    def test_the_same_project_still_closes_locally(self):
        """A prohibition forbids PUBLICATION, never lifecycle closure."""
        self._project()
        self._forbid()
        plan = self._plan("no-publish")
        self.assertEqual(plan.mode, "no-publish")
        self.assertEqual(plan.ticket_id, "T-001")

    def test_absence_of_the_field_is_neither_permission_nor_prohibition(self):
        """A project that never declares it behaves exactly as before.

        The full-mode plan still fails here -- this fixture has no git branch
        -- but it must fail for its OWN reason, never with RELEASE_FORBIDDEN.
        """
        self._project()
        with self.assertRaises(release.ReleaseRefusal) as caught:
            self._plan_with("full")
        self.assertNotEqual(caught.exception.code, "RELEASE_FORBIDDEN")
        self.assertEqual(caught.exception.code, "STALE_PLAN", caught.exception.detail)


class ApplyTimeProhibitionTests(_ReleaseFixture):
    def test_a_prohibition_written_after_the_plan_refuses_the_apply(self):
        """The board the plan was built against is not the board a push runs against."""
        self._project()
        plan = self._plan("no-publish")
        publishing = replace(plan, mode="full")
        self._forbid()
        before = self._snapshot()

        result = release.execute_release(self.root, publishing)

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "RELEASE_FORBIDDEN", result)
        self.assertEqual(result["stage"], "RELEASE_FORBIDDEN", result)
        self.assertEqual(result["forbidden_ticket"], "T-001", result)
        self.assertEqual(self._snapshot(), before, "a refused apply wrote bytes")

    def test_the_apply_refusal_is_not_downgraded_to_a_stale_board_message(self):
        """Adding the prohibition IS a board edit, so the generic hash check
        would otherwise answer first and tell the caller to rebuild a plan the
        next planner call would refuse again."""
        self._project()
        plan = self._plan("no-publish")
        publishing = replace(plan, mode="full")
        self._forbid()
        result = release.execute_release(self.root, publishing)
        self.assertNotIn("BOARD.md changed since the plan was built", result["detail"])
        self.assertIn("publication: forbidden", result["detail"])

    def test_a_cohort_member_prohibition_binds_the_whole_batch(self):
        """A batch published for several tickets and forbidden for one is forbidden."""
        self._project()
        registry = {
            "schema_version": 1,
            "cohorts": {"C-001": {"members": {"T-001": {}, "T-002": {}}}},
        }
        kitchen = self.root / ".saipen" / "kitchen"
        kitchen.mkdir(parents=True, exist_ok=True)
        (kitchen / "cohort_registry.json").write_text(
            json.dumps(registry), encoding="utf-8"
        )
        # The prohibition sits on the NON-owning member: the carrier names the
        # lowest id (T-001), so checking only the owner would miss it. A ## TODO
        # row is the cheapest place to put it; the field is valid on any section
        # precisely because a prohibition governs a FUTURE action.
        path = self.root / ".saipen/BOARD.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            "## TODO\n",
            "## TODO\n- [ ] T-002 other batch work | verify: shared "
            "| publication: forbidden\n",
        )
        path.write_text(text, encoding="utf-8")

        refusal = self._refusal(
            "full",
            cohort_carrier={"cohort_id": "C-001", "ticket_id": "T-001", "scope": {}},
        )
        self.assertEqual(refusal.code, "RELEASE_FORBIDDEN", refusal.detail)
        self.assertIn("T-002", refusal.detail)
        self.assertIn("would publish for T-001, T-002", refusal.detail)


class BatchPlannerProhibitionTests(_ReleaseFixture):
    """The gate belongs to whoever RESOLVED the carrier, not only to its caller.

    `plan_release` derives a crew carrier from `crew_release_context` after its
    own prohibition check has already run, and hands it to `_plan_crew_release`.
    A gate that lived only in `plan_release` would therefore miss a prohibition
    on the epoch's owning ticket -- D-06's "the prohibition was never consulted"
    reached through the batch route. These tests call the batch planner
    DIRECTLY, which is the only way to see whether it refuses on its own.
    """

    def _batch_attempt(self, *, capability: str = "full"):
        """Run the batch planner directly. Returns (refusal, plan, remote_calls).

        Called directly on purpose: the prohibition must hold for a caller that
        never went through `plan_release` at all, and the only way to observe
        that is to invoke the batch planner the way `plan_release` does.
        """
        from saipen_engine.operations import release_scope_hash

        registry = {
            "schema_version": 1,
            "cohorts": {"C-001": {"members": {"T-001": {}, "T-002": {}}}},
        }
        kitchen = self.root / ".saipen" / "kitchen"
        kitchen.mkdir(parents=True, exist_ok=True)
        (kitchen / "cohort_registry.json").write_text(json.dumps(registry), encoding="utf-8")
        board_path = self.root / ".saipen/BOARD.md"
        text = board_path.read_text(encoding="utf-8").replace(
            "## TODO\n",
            "## TODO\n- [ ] T-002 other batch work | verify: shared "
            "| publication: forbidden\n",
        )
        board_path.write_text(text, encoding="utf-8")

        state_text, _state = release._read_state(self.root)
        board_text, board = release._read_board(self.root)
        # The batch planner requires local DONE / task none, which is the state
        # a terminal crew or cohort release runs in.
        state = {"phase": "DONE", "task": "none", "mode": "full", "agent": "saipen-cli"}
        scope = {"current.py": release_scope_hash((self.root / "current.py").read_bytes())}

        calls: list[str] = []

        def spy(root, endpoint):
            calls.append(endpoint)
            raise AssertionError(
                "the batch planner queried the remote for a forbidden ticket"
            )

        with patch.object(release, "_check_parity", return_value=None), patch.object(
            release, "_remote_snapshot", side_effect=spy
        ):
            try:
                plan = release._plan_crew_release(
                    self.root,
                    "ship",
                    "8.0.1",
                    state_text,
                    state,
                    board_text,
                    board,
                    release._log_hash(self.root),
                    "",
                    "",
                    "",
                    "",
                    "v8.0.1",
                    {
                        "crew_epoch": "",
                        "scope": scope,
                        "ticket_id": "T-001",
                    },
                    True,
                    current_capability=capability,
                    cohort_id="C-001",
                )
            except release.ReleaseRefusal as exc:
                return exc, None, calls
        return None, plan, calls

    def test_the_batch_planner_refuses_on_its_own(self):
        """RED CONTROL: before the gate moved here the planner never saw it."""
        self._project()
        refusal, plan, calls = self._batch_attempt()
        self.assertIsNone(plan, "the batch planner published a forbidden ticket")
        self.assertEqual(refusal.code, "RELEASE_FORBIDDEN", refusal.detail)
        self.assertEqual(calls, [], "no remote query may precede the prohibition check")
        self.assertIn("T-002", refusal.detail)
        self.assertIn("would publish for T-001, T-002", refusal.detail)

    def test_a_no_publish_batch_still_plans(self):
        """A prohibition forbids publication; a local batch closure still plans."""
        self._project()
        refusal, plan, _calls = self._batch_attempt(capability="no-publish")
        self.assertIsNone(refusal, refusal.detail if refusal else "")
        self.assertEqual(plan.mode, "no-publish")
        self.assertEqual(plan.cohort_id, "C-001")


class VocabularyTests(unittest.TestCase):
    """The directive is closed at ONE value, and a bad value fails closed."""

    def _ticket(self, value: str, section: str = "## DOING") -> dict:
        return {
            "id": "T-001",
            "section": section,
            "fields": {board_mod.PUBLICATION_PROHIBITION_FIELD: value},
        }

    def test_forbidden_is_valid_on_any_section(self):
        for section in ("## DOING", "## TODO", "## DONE", "## BLOCKED"):
            with self.subTest(section=section):
                self.assertEqual(board_mod.closure_metadata_errors(self._ticket("forbidden", section)), [])

    def test_a_typo_is_refused_rather_than_read_as_absence(self):
        errors = board_mod.closure_metadata_errors(self._ticket("frobidden"))
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("frobidden", errors[0])
        self.assertIn("can never GRANT publication", errors[0])

    def test_the_vocabulary_cannot_grant_publication(self):
        errors = board_mod.closure_metadata_errors(self._ticket("allowed"))
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("allowed", errors[0])

    def test_the_registry_declares_the_field_once(self):
        registry = json.loads(
            (TOOLS.parent / "saipen" / "REGISTRY.json").read_text(encoding="utf-8")
        )
        known = registry["ticket_states"]["known_fields"]
        self.assertEqual(known.count("publication"), 1)
        self.assertIn("publication_state", known)
        self.assertIn("RELEASE_FORBIDDEN", registry["error_codes"])

    def test_compaction_never_hides_the_prohibition(self):
        from saipen_engine import board_compaction

        self.assertEqual(
            board_compaction.COMPACTION_DISPOSITION["publication"], "inline"
        )


class AttemptLedgerTests(unittest.TestCase):
    """The attempt is recorded separately from ticket lifecycle closure."""

    def setUp(self) -> None:
        import tempfile

        self.root = Path(tempfile.mkdtemp(prefix="t1881-ledger-"))
        (self.root / ".saipen").mkdir()

    def test_the_ledger_is_append_only_and_reportable(self):
        first = release_attempt.record(
            self.root, invocation="ship", outcome="RELEASED", ticket="T-001",
            mode="full", op_id="release-x", code="RELEASED", detail="done",
        )
        second = release_attempt.record_result(
            self.root,
            invocation="ship",
            result={"ok": False, "code": "RELEASE_FORBIDDEN", "detail": "forbidden",
                    "forbidden_ticket": "T-009"},
        )
        self.assertTrue(first["ok"], first)
        self.assertTrue(second["ok"], second)
        rows = release_attempt.read(self.root)
        self.assertEqual([row["outcome"] for row in rows],
                         ["RELEASED", "REFUSED_FORBIDDEN"])
        self.assertEqual(rows[1]["forbidden_by"], "T-009")
        self.assertEqual(rows[1]["code"], "RELEASE_FORBIDDEN")

    def test_a_dry_run_is_not_an_attempt(self):
        """A preview is a plan shown and discarded; recording it would make
        every preview look like a publication event in the one ledger that
        exists to say whether one was tried."""
        self.assertEqual(
            release_attempt.outcome_token({"ok": True, "code": "PLAN"}), "RELEASED"
        )
        # The decision lives at the caller, and the CLI is that caller: a
        # `ship --dry-run` writes no ledger (measured in the CLI test below).
        self.assertFalse(release_attempt.ledger_path(self.root).exists())

    def test_the_outcome_vocabulary_is_total(self):
        self.assertEqual(release_attempt.outcome_token({"ok": True, "code": "NO_PUBLISH_MODE"}),
                         "NO_PUBLISH_MODE")
        self.assertEqual(release_attempt.outcome_token({"ok": True, "code": "RELEASED"}),
                         "RELEASED")
        self.assertEqual(release_attempt.outcome_token({"ok": False, "code": "SOURCE_COVERAGE"}),
                         "REFUSED_SOURCE_COVERAGE")
        # An unclassifiable shape still yields a row: a ledger that drops what
        # it cannot explain is worse than one that records a partial truth.
        self.assertEqual(release_attempt.outcome_token({}), "ATTEMPTED")

    def test_a_ledger_write_failure_is_reported_and_never_raises(self):
        with patch.object(release_attempt.os, "open", side_effect=OSError("denied")):
            outcome = release_attempt.record(
                self.root, invocation="ship", outcome="RELEASED"
            )
        self.assertFalse(outcome["ok"])
        self.assertIn("cannot append", outcome["error"])
        self.assertFalse(release_attempt.ledger_path(self.root).exists())

    def test_a_ledger_is_never_minted_into_a_directory_that_is_not_a_project(self):
        import tempfile

        scratch = Path(tempfile.mkdtemp(prefix="t1881-scratch-"))
        outcome = release_attempt.record(
            scratch, invocation="ship", outcome="RELEASED"
        )
        self.assertFalse(outcome["ok"], outcome)
        self.assertFalse((scratch / ".saipen").exists(), "a project was minted")

    def test_a_malformed_line_is_reported_not_skipped(self):
        path = release_attempt.ledger_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"kind": "release-attempt"}\nnot json\n', encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            release_attempt.read(self.root)
        self.assertIn("release_attempts.jsonl:2", str(caught.exception))


class CliAttemptBoundaryTests(unittest.TestCase):
    """The CLI is the caller that records: one row per real attempt, none for a preview."""

    def _project(self) -> Path:
        from test_t1363_zero_manual_entry import healthy

        return healthy(self)

    def test_a_refused_ship_records_an_attempt_and_changes_no_lifecycle_byte(self):
        from test_t1363_zero_manual_entry import cli

        root = self._project()
        canonical = {
            name: (root / ".saipen" / name).read_bytes()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        }
        code, payload, text = cli(root, "ship", "--json")
        self.assertNotEqual(code, 0, text)
        self.assertFalse(payload["ok"], payload)

        rows = release_attempt.read(root)
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["invocation"], "ship")
        self.assertEqual(rows[0]["outcome"], f"REFUSED_{payload['code']}", rows[0])
        self.assertEqual(rows[0]["code"], payload["code"])
        for name, before in canonical.items():
            self.assertEqual((root / ".saipen" / name).read_bytes(), before,
                             f"{name} changed during a refused publication attempt")

    def test_a_dry_run_records_nothing(self):
        from test_t1363_zero_manual_entry import cli

        root = self._project()
        code, _payload, text = cli(root, "ship", "--dry-run", "--json")
        self.assertNotEqual(code, 0, text)
        self.assertFalse(release_attempt.ledger_path(root).exists(),
                         "a preview was recorded as a publication attempt")

    def test_the_forbidden_attempt_itself_is_named_in_the_ledger(self):
        """D-06's own case must be the MOST informative row, not the least.

        A prohibition refusal is raised before any plan exists, so the caller
        has no plan identity to read. Recording `ticket: ""` there would make
        the one row the whole finding is about say nothing about which ticket
        forbade the publication.
        """
        from test_t1363_zero_manual_entry import _allocation_log, _doing, cli, project

        board = _doing("T-9100", "wire it", "test-agent", -1).replace(
            "| verify: it holds", "| verify: it holds | publication: forbidden"
        )
        root = project(
            self,
            phase="SHIP",
            task="T-9100",
            next_action="PHASE SHIP T-9100",
            transition_from="REVIEW",
            board=board,
            log=_allocation_log("T-9100"),
        )
        (root / "VERSION").write_text("8.0.1\n", encoding="utf-8")

        code, payload, text = cli(root, "ship", "--json")

        self.assertNotEqual(code, 0, text)
        self.assertEqual(payload["code"], "RELEASE_FORBIDDEN", payload)
        rows = release_attempt.read(root)
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["ticket"], "T-9100", rows[0])
        self.assertEqual(rows[0]["forbidden_by"], "T-9100", rows[0])
        self.assertEqual(rows[0]["outcome"], "REFUSED_FORBIDDEN", rows[0])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
