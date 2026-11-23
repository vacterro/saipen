"""Lossless publication of a reviewed cumulative generation, never hash refresh."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import closure, operations  # noqa: E402
from test_closure_provenance import _tree_digest  # noqa: E402
from test_hermetic_env import hermetic_env, isolate_host_session  # noqa: E402
from test_orchestration_repair import OrchestrationFixture  # noqa: E402


def setUpModule():
    isolate_host_session()


class ReconciliationTests(OrchestrationFixture):
    def batches(self, *, cover_old=True):
        project = self.make_project(active=True)
        (project / "main.py").write_text("value = 1\n", encoding="utf-8")
        (project / "extra.py").write_text("other = True\n", encoding="utf-8")
        self.to_ship(project, "T-7")
        result = operations.finish_ticket(
            project,
            "T-7",
            "tester",
            closure_mode="cohort",
            closure_cohort="C-001",
            closure_paths=("main.py",),
        )
        self.assertTrue(result.ok, result.to_dict())
        review = self.add(project, "Review integrated cumulative behavior")
        self.assertTrue(operations.apply_claim(project, review, "tester", explicit=True).ok)
        (project / "main.py").write_text("value = 2\n", encoding="utf-8")
        self.to_ship(project, review)
        paths = ("main.py", "extra.py") if cover_old else ("extra.py",)
        result = operations.finish_ticket(
            project,
            review,
            "tester",
            closure_mode="cohort",
            closure_cohort="C-002",
            closure_paths=paths,
        )
        self.assertTrue(result.ok, result.to_dict())
        return project, review

    def reconcile(self, project, review, **changes):
        method = getattr(operations, "cohort_reconcile", None)
        self.assertTrue(callable(method), "canonical cumulative-batch reconciliation is missing")
        return method(
            project,
            changes.pop("target", "C-002"),
            changes.pop("agent", "tester"),
            sources=changes.pop("sources", ["C-001"]),
            review_work=review,
            **changes,
        )

    def registry(self, project, mutate):
        registry = closure.read_registry(project)
        mutate(registry["cohorts"])
        closure.registry_path(project).write_text(
            closure.render_registry(registry), encoding="utf-8"
        )

    def published_fixture(self, project):
        self.registry(
            project,
            lambda cohorts: cohorts["C-002"].update(
                publication_status="shipped", release_op_id="release-fixture", version="1.2.3"
            ),
        )
        (project / ".saipen/kitchen/release_receipt.json").write_text(
            json.dumps(
                {
                    "operation": "release_receipt",
                    "op_id": "release-fixture",
                    "version": "1.2.3",
                    "cohort_id": "C-002",
                    "commit": "fixture-commit",
                }
            ),
            encoding="utf-8",
        )

    def refused_unchanged(self, project, review, **kwargs):
        before = _tree_digest(project)
        result = self.reconcile(project, review, **kwargs)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(_tree_digest(project), before)
        return result

    def test_real_reconciliation_preserves_history_and_owes_publication(self):
        project, review = self.batches()
        before = closure.read_registry(project)
        board = (project / ".saipen/BOARD.md").read_bytes()
        log = (project / ".saipen/LOG.md").read_bytes()
        self.assertTrue(closure.cohort_member_mismatches(project, before["cohorts"]["C-001"]))
        result = self.reconcile(project, review)
        self.assertTrue(result.ok, result.to_dict())
        after = closure.read_registry(project)
        for cid in ("C-001", "C-002"):
            self.assertEqual(after["cohorts"][cid]["members"], before["cohorts"][cid]["members"])
            self.assertEqual(after["cohorts"][cid]["publication_status"], "pending")
        self.assertEqual((project / ".saipen/BOARD.md").read_bytes(), board)
        self.assertTrue((project / ".saipen/LOG.md").read_bytes().startswith(log))
        self.assertTrue((project / result.data["evidence_path"]).is_file())
        self.assertFalse(closure.resolve_implementation_source(project, "T-7").ok)
        self.assertFalse(operations.cohort_ship(project, "C-001", "tester", dry_run=True).ok)
        self.assertTrue(closure.cohort_readiness(project, after["cohorts"]["C-002"])["ready"])

    def test_only_actual_successor_publication_resolves_old_work(self):
        project, review = self.batches()
        result = self.reconcile(project, review)
        self.assertTrue(result.ok, result.to_dict())
        self.registry(
            project,
            lambda cohorts: cohorts["C-002"].update(
                publication_status="shipped", release_op_id="release-fixture", version="1.2.3"
            ),
        )
        self.assertFalse(closure.resolve_implementation_source(project, "T-7").ok)
        self.published_fixture(project)
        verdict = closure.resolve_implementation_source(project, "T-7")
        self.assertTrue(verdict.ok, verdict.to_dict())
        self.assertIn("C-002", verdict.detail)
        receipt = project / ".saipen/kitchen/release_receipt.json"
        original = json.loads(receipt.read_text(encoding="utf-8"))
        for cohort in (None, "C-999"):
            with self.subTest(publication_cohort=cohort):
                changed = dict(original)
                if cohort is None:
                    changed.pop("cohort_id")
                else:
                    changed["cohort_id"] = cohort
                receipt.write_text(json.dumps(changed), encoding="utf-8")
                self.assertFalse(closure.resolve_implementation_source(project, "T-7").ok)
        receipt.write_text(json.dumps(original), encoding="utf-8")
        self.assertTrue(closure.resolve_implementation_source(project, "T-7").ok)
        # Later development cannot revoke an already published historical result.
        (project / "main.py").write_text("value = 3\n", encoding="utf-8")
        self.assertTrue(closure.resolve_implementation_source(project, "T-7").ok)

    def test_dry_run_and_exact_retry_are_byte_noops(self):
        project, review = self.batches()
        before = _tree_digest(project)
        preview = self.reconcile(project, review, dry_run=True)
        self.assertTrue(preview.ok, preview.to_dict())
        self.assertEqual(_tree_digest(project), before)
        result = self.reconcile(project, review)
        self.assertTrue(result.ok, result.to_dict())
        before = _tree_digest(project)
        repeated = self.reconcile(project, review)
        self.assertTrue(repeated.ok, repeated.to_dict())
        self.assertEqual(repeated.code, "ALREADY_APPLIED")
        self.assertEqual(_tree_digest(project), before)

    def test_uncovered_old_path_refuses(self):
        project, review = self.batches(cover_old=False)
        self.refused_unchanged(project, review)

    def test_changed_reviewed_generation_refuses(self):
        project, review = self.batches()
        (project / "main.py").write_text("unreviewed = True\n", encoding="utf-8")
        self.refused_unchanged(project, review)

    def test_foreign_owner_or_missing_review_refuses(self):
        project, review = self.batches()
        self.refused_unchanged(project, review, agent="other")
        self.refused_unchanged(project, "T-999")
        self.registry(
            project, lambda cohorts: cohorts["C-001"]["members"]["T-7"].update(closed_by="other")
        )
        self.refused_unchanged(project, review)

    def test_shipped_missing_self_and_duplicate_sources_refuse(self):
        project, review = self.batches()
        for sources in (["C-999"], ["C-002"], ["C-001", "C-001"], []):
            self.refused_unchanged(project, review, sources=sources)
        self.registry(
            project, lambda cohorts: cohorts["C-001"].update(publication_status="shipped")
        )
        self.refused_unchanged(project, review)

    def test_pending_source_clause_and_failed_current_review_refuse(self):
        project, review = self.batches()
        with mock.patch(
            "saipen_engine.intake.work_closure_gate",
            return_value={"ok": False, "code": "SOURCE_UNRESOLVED"},
        ):
            self.refused_unchanged(project, review)
        with mock.patch("saipen_engine.core_unit.ship_gate", return_value="stale current evidence"):
            self.refused_unchanged(project, review)

    def test_forged_successor_without_journal_authority_never_resolves(self):
        for invalid in ({}, None, "", []):
            with self.subTest(invalid=invalid):
                project, review = self.batches()
                self.registry(
                    project, lambda cohorts: cohorts["C-001"].update(publication_successor=invalid)
                )
                self.refused_unchanged(project, review)
        project, review = self.batches()
        self.registry(
            project,
            lambda cohorts: (
                cohorts["C-001"].update(
                    publication_successor={
                        "cohort": "C-002",
                        "op_id": "cohort-reconcile-" + "a" * 32,
                    }
                ),
                cohorts["C-002"].update(
                    publication_status="shipped", release_op_id="forged", version="1.0.0"
                ),
            ),
        )
        self.assertFalse(closure.resolve_implementation_source(project, "T-7").ok)
        self.refused_unchanged(project, review)

    def test_tampered_receipt_or_original_member_never_resolves(self):
        for tamper in ("receipt", "member"):
            with self.subTest(tamper=tamper):
                project, review = self.batches()
                result = self.reconcile(project, review)
                self.assertTrue(result.ok, result.to_dict())
                if tamper == "receipt":
                    path = project / result.data["evidence_path"]
                    data = json.loads(path.read_text(encoding="utf-8"))
                    data["review_work"] = "T-999"
                    path.write_text(json.dumps(data), encoding="utf-8")
                else:
                    self.registry(
                        project,
                        lambda cohorts: cohorts["C-001"]["members"]["T-7"]["paths"].update(
                            {"main.py": "f" * 16}
                        ),
                    )
                self.published_fixture(project)
                self.assertFalse(closure.resolve_implementation_source(project, "T-7").ok)

    def test_reconciled_cohorts_cannot_gain_unreviewed_members_or_cycles(self):
        project, review = self.batches()
        result = self.reconcile(project, review)
        self.assertTrue(result.ok, result.to_dict())
        registry = closure.read_registry(project)
        for cid in ("C-001", "C-002"):
            with self.assertRaises(ValueError):
                closure.upsert_member(
                    registry,
                    cid,
                    "T-999",
                    paths={"main.py": "a" * 16},
                    verification="unreviewed",
                    closed_at="2026-10-20T00:00:00Z",
                    agent="tester",
                )
        self.refused_unchanged(project, review, target="C-001", sources=["C-002"])

    def test_public_finish_cannot_add_a_member_to_a_frozen_batch(self):
        project, review = self.batches()
        self.assertTrue(self.reconcile(project, review).ok)
        work = self.add(project, "Later independent work")
        self.assertTrue(operations.apply_claim(project, work, "tester", explicit=True).ok)
        self.to_ship(project, work)
        before = _tree_digest(project)
        refused = operations.finish_ticket(
            project,
            work,
            "tester",
            closure_mode="cohort",
            closure_cohort="C-002",
            closure_paths=("main.py",),
        )
        self.assertFalse(refused.ok, refused.to_dict())
        self.assertEqual(_tree_digest(project), before)

    def test_active_work_and_goal_counters_are_preserved(self):
        project, review = self.batches()
        work = self.add(project, "Independent active work")
        self.assertTrue(operations.apply_claim(project, work, "tester", explicit=True).ok)
        self.assertTrue(operations.set_goal_intent(project, "tester", "fixture goal").ok)
        before = self.state(project)
        result = self.reconcile(project, review)
        self.assertTrue(result.ok, result.to_dict())
        after = self.state(project)
        for key in (
            "phase",
            "task",
            "next_action",
            "transition_from",
            "agent",
            "execution_intent",
            "goal_waves",
            "goal_tickets",
        ):
            self.assertEqual(after.get(key), before.get(key), key)

    def test_postfinish_prose_cannot_add_an_evidence_read_dependency(self):
        project, review = self.batches()
        before = tuple((project / ".saipen" / name).read_bytes()
                       for name in ("STATE.md", "BOARD.md", "LOG.md"))
        result = operations.checkpoint(
            project,
            "tester",
            "RUN",
            review,
            "CORE-UNIT-EVIDENCE PASS record:../../unrelated.json sha256:" + "a" * 64,
        )
        # The canonical context guard now refuses a ticket-bearing lifecycle
        # checkpoint after finish. Keep the hostile payload and require the
        # stronger zero-write boundary instead of inventing an active seat.
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "STALE_WORK_CONTEXT")
        self.assertEqual(before, tuple((project / ".saipen" / name).read_bytes()
                                      for name in ("STATE.md", "BOARD.md", "LOG.md")))
        reconciled = self.reconcile(project, review)
        self.assertTrue(reconciled.ok, reconciled.to_dict())

    def test_malformed_membership_and_review_path_disagreement_refuse(self):
        for malformed in (None, [], {"T-7": {"paths": None}}):
            with self.subTest(malformed=malformed):
                project, review = self.batches()
                self.registry(project, lambda cohorts: cohorts["C-001"].update(members=malformed))
                self.refused_unchanged(project, review)
        project, review = self.batches()
        self.registry(
            project, lambda cohorts: cohorts["C-002"]["members"][review]["paths"].pop("extra.py")
        )
        self.refused_unchanged(project, review)

    def test_invalid_api_types_paths_and_receipt_corruption_refuse(self):
        project, review = self.batches()
        for values in ({"target": 7}, {"sources": None}, {"agent": None}):
            self.refused_unchanged(project, review, **values)
        self.refused_unchanged(project, None)
        self.registry(project, lambda cohorts: cohorts["C-002"].update(scope=["../escape"]))
        self.refused_unchanged(project, review)

    def test_stale_apply_cannot_authorize_changed_source(self):
        project, review = self.batches()
        from saipen_engine.cohort_reconcile import plan

        intended = plan(project, "C-002", "tester", ["C-001"], review)
        (project / "main.py").write_text("racing_writer = True\n", encoding="utf-8")
        before = _tree_digest(project)
        applied = operations.apply_plan(project, intended)
        self.assertFalse(applied.ok, applied.to_dict())
        self.assertEqual(applied.code, "STALE_STATE")
        self.assertEqual(_tree_digest(project), before)

    def test_cli_uses_the_same_operation(self):
        project, review = self.batches()
        command = [
            sys.executable,
            "-B",
            str(TOOLS / "saipen.py"),
            "--project-root",
            str(project),
            "cohort",
            "reconcile",
            "C-002",
            "--from",
            "C-001",
            "--review-work",
            review,
            "--json",
        ]
        # The direct public route is the acceptance oracle. Existing capability
        # negotiation remains independently covered by its repository tests.
        executed = subprocess.run(
            command,
            cwd=project,
            env=hermetic_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
        )
        self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
        self.assertEqual(json.loads(executed.stdout)["code"], "COHORT_RECONCILED")

    def test_readonly_cli_refuses_before_mutation(self):
        import saipen

        project, review = self.batches()
        before = _tree_digest(project)
        with mock.patch.object(
            saipen, "_negotiate_capability", return_value="read-only"
        ), mock.patch.object(saipen, "_emit"), mock.patch.object(
            operations, "cohort_reconcile", create=True
        ) as mutate:
            result = saipen._cohort(
                project,
                ["reconcile", "C-002", "--from", "C-001", "--review-work", review],
                True,
                False,
            )
        self.assertNotEqual(result, 0)
        mutate.assert_not_called()
        self.assertEqual(_tree_digest(project), before)


if __name__ == "__main__":
    unittest.main()
