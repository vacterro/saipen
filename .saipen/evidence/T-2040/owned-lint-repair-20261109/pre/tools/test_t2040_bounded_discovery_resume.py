"""T-2040 bounded discovery resume: unchanged red/green oracle, stdlib only.

Run: python -B tools/test_t2040_bounded_discovery_resume.py -v
All Git/history/report writes below belong to disposable test projects.
"""
from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

import freshness
import improve
import saipen as CLI
from saipen_engine import (
    conformance, continue_fallback as CF, discovery_providers as DP,
    goal_authority, intake, persistent_goal, replenishment, source_append,
    work_exhaustion as W,
)
from test_hermetic_env import hermetic_env, isolate_host_session


def setUpModule():
    isolate_host_session()


def incomplete_certificate(source=W.HUNT_FINDINGS, action="saipen hunt"):
    generation = "head+git-delta-v1:tree"
    rows = [
        {"source_name": name, "source_generation": generation,
         "last_checked_generation": generation, "checked": True,
         "eligibility_result": W.CLEAN_VERIFIED, "authorized_actions": []}
        for name in W.ALL_WORK_SOURCES
    ]
    row = next(row for row in rows if row["source_name"] == source)
    row.update(checked=False, last_checked_generation=None,
               eligibility_result=W.NOT_CHECKED, authorized_actions=[action])
    return {
        "schema_version": 2, "status": W.INCOMPLETE_DISCOVERY,
        "source_generation": generation, "sources": rows,
        "all_checked": False, "exhausted": False, "verified_exhausted": False,
        "no_work_available": True, "certificate_errors": [],
        "discovery_dispatch": {"source_name": source, "source_generation": generation,
                               "action": action, "bounded": True},
    }


class CertificateDispatchTests(unittest.TestCase):
    def test_same_bounded_hint_not_work_or_exhaustion(self):
        cert = incomplete_certificate()
        before = copy.deepcopy(cert)
        self.assertEqual(W.certificate_diagnostics(cert), [])
        self.assertIs(W.discovery_dispatch_for(cert), cert["discovery_dispatch"])
        self.assertFalse(W.verified_quiescence(cert))
        self.assertEqual(cert, before)

    def test_exact_native_allowlist(self):
        for source, action in (
            (W.HUNT_FINDINGS, "saipen hunt"),
            (W.IMPROVE_CANDIDATES, "saipen improve"),
            (W.IMPROVE_CANDIDATES, "saipen improve --session tester-01"),
        ):
            with self.subTest(action=action):
                cert = incomplete_certificate(source, action)
                self.assertIs(W.discovery_dispatch_for(cert), cert["discovery_dispatch"])
        for source, action in (
            (W.HUNT_FINDINGS, "saipen improve"),
            (W.IMPROVE_CANDIDATES, "saipen improve sweep-queue cycle"),
            (W.IMPROVE_CANDIDATES, "saipen improve --session ../foreign"),
            (W.IMPROVE_CANDIDATES, "saipen improve; git push"),
            (W.EXTERNAL_FORENSICS, "saipen sub"),
            (W.CANONICAL_RECOVERY, "saipen recover"),
        ):
            with self.subTest(source=source, action=action):
                self.assertIsNone(W.discovery_dispatch_for(incomplete_certificate(source, action)))

    def test_duplicate_missing_stale_and_malformed_rows_refused(self):
        for change in (
            lambda cert: cert["sources"].pop(),
            lambda cert: cert["sources"].__setitem__(1, copy.deepcopy(cert["sources"][0])),
            lambda cert: cert["sources"][1].update(source_generation="old"),
            lambda cert: cert["sources"][1].update(last_checked_generation="old"),
            lambda cert: cert["sources"][1].update(source_name=[]),
            lambda cert: cert["sources"][1].update(eligibility_result={}),
            lambda cert: cert["sources"][1].update(checked="true"),
            lambda cert: cert["sources"][1].update(authorized_actions={}),
        ):
            cert = incomplete_certificate()
            change(cert)
            self.assertTrue(W.certificate_diagnostics(cert), cert)
            self.assertIsNone(W.discovery_dispatch_for(cert), cert)

    def test_hint_must_name_exact_unchecked_row_and_generation(self):
        for change in (
            lambda cert: cert["discovery_dispatch"].update(source_generation="old"),
            lambda cert: cert["discovery_dispatch"].update(bounded=1),
            lambda cert: cert["discovery_dispatch"].update(extra="unbounded"),
            lambda cert: cert["sources"][7].update(checked=True),
            lambda cert: cert["sources"][7].update(eligibility_result=W.BLOCKED_AUTHORITY),
            lambda cert: cert["sources"][7].update(authorized_actions=[]),
            lambda cert: cert.update(certificate_errors=["unreadable evidence"]),
            lambda cert: cert.update(status=W.WORK_ELIGIBLE),
            lambda cert: cert.update(all_checked=True),
            lambda cert: cert.update(exhausted=True),
            lambda cert: cert.update(schema_version=1),
        ):
            cert = incomplete_certificate()
            change(cert)
            self.assertIsNone(W.discovery_dispatch_for(cert), cert)

    def test_total_diagnostics_on_hostile_envelopes(self):
        for value in (None, 42, [], {"sources": 42}, {"schema_version": 2, "status": []}):
            with self.subTest(value=value):
                self.assertTrue(W.certificate_diagnostics(value))
                self.assertIsNone(W.discovery_dispatch_for(value))
                self.assertFalse(W.verified_quiescence(value))


class NativeObservationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="saipen-bounded-discovery-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / ".saipen").mkdir()
        (self.root / ".gitignore").write_text(".saipen/\n", encoding="utf-8")
        (self.root / "source.py").write_text("value = 1\n", encoding="utf-8")
        self.git("init", "-q")
        self.git("add", ".gitignore", "source.py")
        self.git("commit", "-qm", "disposable discovery fixture")
        self.identity = freshness.compute_source_identity(self.root)
        self.short = self.git("rev-parse", "--short", "HEAD").strip()
        self.log = self.root / ".saipen/LOG.md"
        self.clean_hunt()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)

    def git(self, *args):
        env = {**hermetic_env(), "GIT_OPTIONAL_LOCKS": "0",
               "GIT_AUTHOR_NAME": "fixture", "GIT_COMMITTER_NAME": "fixture",
               "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
               "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
        return subprocess.run(["git", "-C", str(self.root), *args], env=env,
                              check=True, capture_output=True, text=True).stdout

    def clean_hunt(self, *, taxonomy="RUN", text=None):
        text = text if text is not None else f"hunt -> clean @{self.short}"
        self.log.write_text(f"# LOG\n- [E-1] {taxonomy}: {text}\n", encoding="utf-8")

    def test_actual_canonical_hunt_clean_current_head(self):
        from saipen_engine.log import read_history_snapshot
        history = read_history_snapshot(self.root, lean=True)
        before = self.log.read_bytes()
        with mock.patch.object(freshness, "compute_source_identity", side_effect=AssertionError("recapture")):
            observed = CF.hunt_observation(self.root, source_identity=self.identity, history=history)
        self.assertEqual(observed["eligibility_result"], W.CLEAN_VERIFIED, observed)
        self.assertEqual(self.log.read_bytes(), before)

    def test_dirty_missing_unreadable_and_prose_hunt_never_clean(self):
        for taxonomy, text in (
            ("DEC", f"hunt -> clean @{self.short}"),
            ("RUN", f"notes about hunt -> clean @{self.short}"),
            ("RUN", "hunt -> clean @deadbee"),
        ):
            self.clean_hunt(taxonomy=taxonomy, text=text)
            self.assertEqual(CF.hunt_observation(self.root, source_identity=self.identity)["eligibility_result"],
                             W.NOT_CHECKED)
        self.clean_hunt()
        (self.root / "source.py").write_text("value = 2\n", encoding="utf-8")
        self.assertEqual(CF.hunt_observation(self.root, source_identity=self.identity)["eligibility_result"],
                         W.NOT_CHECKED)
        (self.root / "source.py").write_text("value = 1\n", encoding="utf-8")
        self.log.unlink()
        self.assertEqual(CF.hunt_observation(self.root, source_identity=self.identity)["eligibility_result"],
                         W.NOT_CHECKED)
        self.clean_hunt()
        with mock.patch("subprocess.run", side_effect=OSError("unreadable Git")):
            self.assertEqual(CF.hunt_observation(self.root, source_identity=self.identity)["eligibility_result"],
                             W.NOT_CHECKED)

    def improve_cycle(self):
        cycle = self.root / ".saipen/improve/imp-fixture-1"
        seat = "tester-01"
        report_name = "saipen_improve_FIXTURE.md"
        (cycle / seat).mkdir(parents=True)
        project = improve.portable_project_key(self.root)
        manifest = (
            "# IMPROVE CYCLE ROSTER\n\nmanifest_schema: strict\ncycle_id: imp-fixture-1\n"
            "created_at: 2026-11-08T09:00:00Z\n"
            f"project_identity: {project}\ncycle_status: complete\n\n"
            f"seat_id: {seat}\nrole: core\nreport_path: {report_name}\navailability: expected\n"
        )
        (cycle / "MANIFEST.md").write_text(manifest, encoding="utf-8")
        (cycle / "SWEEP.md").write_text("# SWEEP\n", encoding="utf-8")
        header = {
            "agent": seat, "role": "core", "model_or_runtime": "fixture",
            "project": project, "saipen_version": "fixture-version",
            "protocol_fingerprint": "sha256:" + "1" * 64,
            "source_head": self.identity.source_head,
            "source_tree_fingerprint": self.identity.source_tree_fingerprint,
            "discovery_model": self.identity.discovery_model,
            "context_scope": "entire project", "context_available": "complete",
            "report_status": "complete",
        }
        report = "# REPORT\n" + "".join(f"{key}: {value}\n" for key, value in header.items())
        report += (f"\n## RUN 1\nrun_source_head: {self.identity.source_head}\n"
                   f"run_source_tree_fingerprint: {self.identity.source_tree_fingerprint}\n\nNO_FINDINGS\n")
        path = cycle / seat / report_name
        path.write_text(report, encoding="utf-8")
        self.stack.enter_context(mock.patch.object(improve, "installed_protocol_fingerprint",
                                                   return_value=header["protocol_fingerprint"]))
        self.stack.enter_context(mock.patch.object(improve, "_saipen_install_version",
                                                   return_value=header["saipen_version"]))
        return cycle, path, report

    def test_current_complete_improve_uses_shared_bound_bar(self):
        cycle, path, report = self.improve_cycle()
        before = path.read_bytes()
        with mock.patch.object(improve, "validate_bound_report", wraps=improve.validate_bound_report) as validate:
            observed = CF.improve_observation(self.root, source_identity=self.identity)
        self.assertEqual(observed["eligibility_result"], W.CLEAN_VERIFIED, observed)
        self.assertTrue(validate.called)
        self.assertIs(validate.call_args.kwargs["current_source"], self.identity)
        self.assertTrue(validate.call_args.kwargs["require_runs"])
        self.assertTrue(validate.call_args.kwargs["require_fresh"])
        self.assertTrue(validate.call_args.kwargs["cycle_active"])
        self.assertEqual(path.read_bytes(), before)

    def test_complete_improve_cannot_restamp_any_identity_dimension(self):
        cycle, path, report = self.improve_cycle()
        for key, value in (
            ("agent", "other-01"), ("project", "other-project"),
            ("saipen_version", "old-version"), ("protocol_fingerprint", "sha256:" + "2" * 64),
            ("source_head", "f" * 40), ("source_tree_fingerprint", "git-delta-v1:" + "2" * 64),
            ("discovery_model", "no-git-tree-v1"), ("report_status", "draft"),
            ("run_source_head", "f" * 40),
            ("run_source_tree_fingerprint", "git-delta-v1:" + "2" * 64),
        ):
            import re
            changed = re.sub(rf"(?m)^{key}:.*$", f"{key}: {value}", report)
            path.write_text(changed, encoding="utf-8")
            with self.subTest(key=key):
                self.assertEqual(CF.improve_observation(self.root, source_identity=self.identity)["eligibility_result"],
                                 W.NOT_CHECKED)
        path.write_text(report.replace(f"run_source_head: {self.identity.source_head}\n", ""), encoding="utf-8")
        self.assertEqual(CF.improve_observation(self.root, source_identity=self.identity)["eligibility_result"],
                         W.NOT_CHECKED)

    def test_header_cannot_mix_head_and_tree_from_different_runs(self):
        text = ("source_head: first\nsource_tree_fingerprint: tree-second\n\n"
                "## RUN 1\nrun_source_head: first\nrun_source_tree_fingerprint: tree-first\n\nNO_FINDINGS\n"
                "## RUN 2\nrun_source_head: second\nrun_source_tree_fingerprint: tree-second\n\nNO_FINDINGS\n")
        self.assertTrue(improve._header_repair_errors(text))

    def test_source_change_marker_is_not_completed_analysis(self):
        CF.write_marker(self.root, "imp-absent", "tester")
        goal = persistent_goal.PersistentGoal("goal", self.root.name, "Source", "Inspect source")
        result = DP.SourceChangeProvider().evaluate(self.root, goal)
        self.assertEqual(result.satisfaction_status, persistent_goal.STATUS_DISCOVERY_REQUIRED)
        self.assertEqual(result.completeness_status, DP.COMPLETION_UNKNOWN)
        self.assertFalse(result.actionable_candidates)

    def collection_owners(self):
        for owner, name, value in (
            (goal_authority, "continuous_maintenance_proven", True),
            (intake, "active_receipts", []),
            (intake, "recover_orphans", {"ok": True, "orphans": []}),
            (source_append, "pending_appends", []), (source_append, "ledgers", []),
            (conformance, "conformance_status", {"status": conformance.STATUS_CURRENT_PASS}),
        ):
            self.stack.enter_context(mock.patch.object(owner, name, return_value=value))

    def test_discovery_keys_same_generation_no_publication_copy(self):
        self.collection_owners()
        publication = object()
        evidence = W.discovery_evidence(
            self.root, state={"agent": "tester", "last_event": "1"}, tickets={},
            pending_ops=[], conflict_ops=[], publication_evidence=publication,
            source_identity=self.identity,
        )
        self.assertEqual(set(evidence), {"persistent_goals", "source_evidence",
                                        "continuous_maintenance_authorized", "source_generation",
                                        "discovery_dispatch"})
        self.assertEqual(evidence["source_generation"],
                         self.identity.source_head + "+" + self.identity.source_tree_fingerprint)
        self.assertTrue(all(row["source_generation"] == evidence["source_generation"]
                            for row in evidence["source_evidence"].values()))
        self.assertEqual(evidence["source_evidence"][W.HUNT_FINDINGS]["eligibility_result"], W.CLEAN_VERIFIED)
        self.assertEqual(evidence["source_evidence"][W.EXTERNAL_FORENSICS]["eligibility_result"], W.NOT_CHECKED)
        self.assertEqual(evidence["discovery_dispatch"]["action"], "saipen improve")

    def test_grant_recovery_and_owned_work_gate_one_analysis_hint(self):
        self.collection_owners()
        self.log.write_text("# LOG\n", encoding="utf-8")
        args = {"state": {"agent": "tester", "last_event": "1"}, "tickets": {},
                "pending_ops": [], "conflict_ops": [], "source_identity": self.identity}
        evidence = W.discovery_evidence(self.root, **args)
        self.assertEqual(evidence["discovery_dispatch"]["action"], "saipen hunt")
        goal_authority.continuous_maintenance_proven.return_value = False
        self.assertIsNone(W.discovery_evidence(self.root, **args)["discovery_dispatch"])
        goal_authority.continuous_maintenance_proven.return_value = True
        for extra in (
            {"pending_ops": ["op-pending"]},
            {"pending_ops": [{"corrupt": True}]},
            {"tickets": {"T-1": {"section": "## DOING", "fields": {}}}},
            {"state": {"agent": "tester", "next_action": "WAIT: user brake"}},
        ):
            with self.subTest(extra=extra):
                self.assertIsNone(W.discovery_evidence(self.root, **{**args, **extra})["discovery_dispatch"])


class ContinuationAdmissionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="saipen-discovery-admission-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / ".saipen").mkdir()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        goal = persistent_goal.PersistentGoal("goal", self.root.name, "Goal", "Repair")
        for owner, name, value in (
            (persistent_goal, "list_goals_report", {"goals": [goal], "complete": True,
                                                    "root_available": True, "errors": []}),
            (CF, "read_marker", {}), (CF, "source_unchanged", (True, "unchanged")),
            (CLI, "_agent_for", "tester"),
        ):
            self.stack.enter_context(mock.patch.object(owner, name, return_value=value))
        self.stack.enter_context(mock.patch.object(CF, "with_cycle_liveness", side_effect=lambda value, _: value))
        self.improve = self.stack.enter_context(mock.patch.object(CLI, "_public_improve"))

    def fallthrough(self, result):
        emitted = []
        with mock.patch.object(replenishment, "replenish_from_goals", return_value=result), mock.patch.object(
            CLI, "_emit", side_effect=lambda payload, _: emitted.append(payload),
        ):
            rc = CLI._continue_improve_fallthrough(self.root, True, False, {}, [], [], None)
        self.assertEqual(len(emitted), 1)
        return rc, emitted[0]

    def test_reused_work_keeps_actual_ticket_and_receipt_fields(self):
        rc, payload = self.fallthrough({"ok": True, "replenished": True, "reused_work": True,
                                       "admitted_ticket": "T-7", "goal_id": "goal",
                                       "action": "PHASE SCOUT T-7"})
        self.assertEqual(rc, 0)
        self.assertEqual(payload["code"], "GOAL_TASK_REPLENISHED")
        self.assertTrue(payload["reused_work"])
        self.assertEqual(payload["admitted_ticket"], "T-7")
        self.assertEqual(payload["ticket"], "T-7")
        self.improve.assert_not_called()

    def test_structured_admission_failures_never_fall_through_improve(self):
        for status in ("BOARD_INVALID", "RECOVERY_BLOCKED", "ADMISSION_FAILED", "ADMISSION_POLICY_DRIFT"):
            with self.subTest(status=status):
                rc, payload = self.fallthrough({"ok": False, "replenished": False,
                                               "status": status, "detail": "current refusal"})
                self.assertEqual(rc, 1)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["status"], status)
                self.assertEqual(payload["code"], status)
                self.improve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
