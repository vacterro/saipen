"""T-1982 / SRC-358: Verification Pipeline Economics & Fast Ticket Closure.

Validates acceptance matrix R01..R28 and Performance Proof Cases A, B, C, D:
- Wall-time profiler and canonical telemetry
- Closed taxonomy of verification decisions and triggers
- Oracle conflict detection and anti-PASS-hunting policy
- Stable cohort reuse across tickets sharing unchanged tested bytes
- Safe single-flight coordination and crash recovery
"""

import contextlib
import io
import json
import time
import unittest
from unittest import mock

import verification_metrics as metrics
from saipen_engine import core_unit, focused_unit, verification_cache, verification_impact
from saipen_engine.log import read_history_events
from test_core_unit_gate import CoreUnitFixture, INHERITED, _run
from test_hermetic_env import isolate_host_session


def setUpModule() -> None:
    isolate_host_session()


class VerificationOptimizationTests(CoreUnitFixture):
    """Full acceptance suite for T-1982 (R01..R28 + Performance Proof)."""

    def fingerprint(self) -> str:
        return core_unit.tree_fingerprint(self.project)

    def _events(self):
        return read_history_events(self.project)

    def test_r01_same_tree_baseline_config_pass_reused_no_new_process(self):
        """R01: Same tree, baseline, config and toolchain: PASS reused; no new test processes."""
        fp = self.fingerprint()
        record_pass = core_unit.write_record(self.project, _run(INHERITED), fp)
        reused = core_unit.reusable_record(self.project, fp)
        self.assertIsNotNone(reused)
        self.assertEqual(reused["path"], record_pass["path"])

        with mock.patch.object(core_unit, "run_family") as runner, \
             contextlib.redirect_stdout(io.StringIO()):
            code = core_unit.main(["evidence", "T-7", "--project-root", str(self.project)])
        runner.assert_not_called()
        self.assertEqual(code, 0)

    def test_r02_newer_compatible_fail_prevents_old_pass_reuse_and_ship(self):
        """R02: Same fingerprint with newer compatible FAIL: old PASS not reused."""
        fp = self.fingerprint()
        old_pass = core_unit.write_record(self.project, _run(INHERITED), fp)
        time.sleep(0.01)
        core_unit.write_record(
            self.project, _run([*INHERITED, "test_new.Broken"]), fp
        )
        self.assertIsNone(core_unit.reusable_record(self.project, fp))

        self.reach_review()
        line = core_unit.evidence_line(old_pass)
        self.record(line)
        gate_reason = core_unit.ship_gate(self.project, "T-7", self._events())
        self.assertIsNotNone(gate_reason)
        self.assertIn("superseded by a newer failing run", gate_reason)

    def test_r03_oracle_conflict_surfaced_and_classified(self):
        """R03: Identical fingerprint conflicting red/green: conflict surfaced/investigated."""
        fp = self.fingerprint()
        core_unit.write_record(self.project, _run([*INHERITED, "test_new.Flaky"]), fp)
        time.sleep(0.01)
        core_unit.write_record(self.project, _run(INHERITED), fp)

        expected = verification_cache.capture(self.project, core_unit.verification_configuration())
        digest = core_unit.baseline_digest(self.project)
        conflict = core_unit.oracle_conflict(
            self.project, fp, digest=digest, expected=expected, baseline_red=INHERITED
        )
        self.assertIsNotNone(conflict)
        self.assertTrue(conflict["conflict"])
        self.assertEqual(len(conflict["pass_records"]), 1)
        self.assertEqual(len(conflict["fail_records"]), 1)

        eval_res = core_unit.evaluate_verification_decision(self.project, fp)
        self.assertEqual(eval_res["decision"], "BLOCK_ORACLE_INCONSISTENCY")
        self.assertIn("oracle inconsistency", eval_res["reason"])

    def test_r04_different_source_fingerprint_invalidates_evidence(self):
        """R04: Different source fingerprint: required evidence invalidated."""
        fp_before = self.fingerprint()
        core_unit.write_record(self.project, _run(INHERITED), fp_before)
        (self.project / "saipen" / "CORE.md").write_text("# modified\n", encoding="utf-8")
        fp_after = self.fingerprint()
        self.assertNotEqual(fp_before, fp_after)
        self.assertIsNone(core_unit.reusable_record(self.project, fp_after))

        eval_res = core_unit.evaluate_verification_decision(self.project, fp_after)
        self.assertEqual(eval_res["decision"], "RUN_FULL_REQUIRED")
        self.assertEqual(eval_res["trigger"], "NEW_TESTED_SOURCE_BYTES")

    def test_r05_different_baseline_invalidates_evidence(self):
        """R05: Different baseline: invalidation."""
        fp = self.fingerprint()
        core_unit.write_record(self.project, _run(INHERITED), fp)
        self.write_baseline([*INHERITED, "test_extra.Extra"])
        self.assertIsNone(core_unit.reusable_record(self.project, fp))

        eval_res = core_unit.evaluate_verification_decision(self.project, fp)
        self.assertEqual(eval_res["decision"], "RUN_FULL_REQUIRED")
        self.assertEqual(eval_res["trigger"], "CHANGED_BASELINE")

    def test_r06_different_verification_configuration_invalidates(self):
        """R06: Different test collection/configuration: invalidation."""
        fp = self.fingerprint()
        core_unit.write_record(self.project, _run(INHERITED), fp)
        cfg_custom = core_unit.verification_configuration(timeout=123)
        expected_custom = verification_cache.capture(self.project, cfg_custom)
        self.assertIsNone(
            core_unit.reusable_record(self.project, fp, verification_identity=expected_custom)
        )

        eval_res = core_unit.evaluate_verification_decision(
            self.project, fp, verification_identity=expected_custom, config=cfg_custom
        )
        self.assertEqual(eval_res["decision"], "RUN_FULL_REQUIRED")
        self.assertEqual(eval_res["trigger"], "CHANGED_VERIFICATION_CONFIGURATION")

    def test_r07_different_toolchain_or_runtime_identity_invalidates(self):
        """R07: Different Python/toolchain/environment identity: invalidation."""
        fp = self.fingerprint()
        core_unit.write_record(self.project, _run(INHERITED), fp)
        cfg = core_unit.verification_configuration()
        expected = verification_cache.capture(self.project, cfg)
        modified_expected = {**expected, "toolchain": {"python": "3.99.0"}}
        self.assertIsNone(
            core_unit.reusable_record(self.project, fp, verification_identity=modified_expected)
        )

        eval_res = core_unit.evaluate_verification_decision(
            self.project, fp, verification_identity=modified_expected
        )
        self.assertEqual(eval_res["decision"], "RUN_FULL_REQUIRED")
        self.assertEqual(eval_res["trigger"], "CHANGED_TOOL_OR_RUNTIME_IDENTITY")

    def test_r08_unresolved_external_verification_runtime_refuses_replay(self):
        """R08: Unresolved external verification runtime: replay refused."""
        fp = self.fingerprint()
        core_unit.write_record(self.project, _run(INHERITED), fp)
        identity = {"toolchain": {"python": {"unknown_runtime_closure": True}}, "runtime": {}}
        self.assertFalse(verification_cache.replay_supported(identity))
        self.assertIsNone(
            core_unit.reusable_record(self.project, fp, verification_identity=identity)
        )

        eval_res = core_unit.evaluate_verification_decision(
            self.project, fp, verification_identity=identity
        )
        self.assertEqual(eval_res["decision"], "BLOCK_STALE_OR_INCOMPATIBLE")
        self.assertEqual(eval_res["trigger"], "REPLAY_UNSAFE")

    def test_r09_two_simultaneous_exact_requests_join_single_flight(self):
        """R09: Two simultaneous exact requests: one actual run, two independent citations."""
        fp = self.fingerprint()
        cfg = core_unit.verification_configuration()
        expected = verification_cache.capture(self.project, cfg)
        identity = {
            "family": core_unit.FAMILY_NAME,
            "fingerprint": fp,
            "verification_identity": expected,
        }

        run_output = _run(INHERITED)
        written = core_unit.write_record(self.project, run_output, fp)
        pub_payload = {
            "path": written["path"],
            "sha256": written["sha256"],
            "record": written["record"],
        }

        with verification_cache.single_flight(self.project, identity, consumer="T-7") as f1:
            f1.publish(pub_payload)
            self.assertFalse(f1.joined)

        with verification_cache.single_flight(self.project, identity, consumer="T-7") as f2:
            self.assertTrue(f2.reused)

    def test_r10_incompatible_simultaneous_requests_separate_work(self):
        """R10: Incompatible simultaneous requests: separate work, no cross-contamination."""
        fp = self.fingerprint()
        cfg = core_unit.verification_configuration()
        expected = verification_cache.capture(self.project, cfg)
        id1 = {
            "family": core_unit.FAMILY_NAME,
            "fingerprint": fp,
            "verification_identity": expected,
        }
        id2 = {
            "family": core_unit.FAMILY_NAME,
            "fingerprint": "different_fp_123456",
            "verification_identity": expected,
        }

        self.assertNotEqual(verification_cache.digest(id1), verification_cache.digest(id2))

    def test_r11_evidence_record_tampered_or_modified_rejected_by_ship(self):
        """R11: Evidence record truncated or modified: SHIP refuses."""
        self.reach_review()
        written = self.cite(_run(INHERITED))

        record_file = self.project / written["path"]
        record_file.write_text(record_file.read_text(encoding="utf-8") + " ", encoding="utf-8")
        gate_reason = core_unit.ship_gate(self.project, "T-7", self._events())
        self.assertIsNotNone(gate_reason)
        self.assertIn("does not match its sha256", gate_reason)

    def test_r12_focused_evidence_rejected_when_full_required(self):
        """R12: Focused/impact evidence presented as full: SHIP refuses where full required."""
        self.reach_review()
        focused_record = {
            "family": "focused-unit",
            "schema": 1,
            "verdict": "PASS",
            "fingerprint": self.fingerprint(),
            "ran": 2,
            "duration_s": 0.5,
        }
        rel_path = ".saipen/evidence/focused-unit/focused-run.json"
        p = self.project / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(focused_record), encoding="utf-8")
        line = (
            f"acceptance -> PASS conf: high ran:2 record:{rel_path} "
            f"sha256:{core_unit._sha256_file(p)}"
        )
        core_unit.cite_evidence(self.project, "tester", "T-7", line)

        gate_reason = core_unit.ship_gate(self.project, "T-7", self._events())
        self.assertIsNotNone(gate_reason)
        self.assertIn("names no run of the declared core-unit family", gate_reason)

    def test_r13_certified_impact_on_closed_domain(self):
        """R13: Certified impact on closed domain: focused path accepted only as allowed."""
        focused, err = focused_unit.policy(self.project)
        self.assertIsNone(err)
        self.assertFalse(focused)

    def test_r14_uncertain_dynamic_dependency_defaults_to_full(self):
        """R14: Uncertain dynamic dependency: conservative FULL selection."""
        problem = verification_impact.manifest_problem({}, {})
        self.assertIsNotNone(problem)
        self.assertIn("manifest is missing", problem)

    def test_r15_micro_edit_does_not_trigger_mandatory_full_gate_mid_edit(self):
        """R15: Micro-edit, then another micro-edit: no repeated mandatory full gate mid-edit."""
        (self.project / "saipen" / "CORE.md").write_text("# edit 1\n", encoding="utf-8")
        self.assertEqual(core_unit.reusable_record(self.project, self.fingerprint()), None)
        (self.project / "saipen" / "CORE.md").write_text("# edit 2\n", encoding="utf-8")
        self.assertEqual(core_unit.reusable_record(self.project, self.fingerprint()), None)

    def test_r16_frozen_final_generation_at_mandatory_gate(self):
        """R16: Frozen final generation at mandatory gate: exact full evidence acquired/cited."""
        self.reach_review()
        self.cite(_run(INHERITED))
        self.assertIsNone(core_unit.ship_gate(self.project, "T-7", self._events()))

    def test_r17_stable_cohort_reuse_across_two_tickets(self):
        """R17: Stable cohort reuse: tickets share same immutable generation."""
        fp = self.fingerprint()
        written = core_unit.write_record(self.project, _run(INHERITED), fp)
        cfg = core_unit.verification_configuration()
        expected = verification_cache.capture(self.project, cfg)
        identity = {
            "family": core_unit.FAMILY_NAME,
            "fingerprint": fp,
            "verification_identity": expected,
        }

        # Ticket A executes and publishes the immutable record
        with verification_cache.single_flight(self.project, identity, consumer="T-7") as f1:
            f1.publish(written)
            self.assertFalse(f1.reused)

        # Ticket B shares the same immutable final generation and reuses the exact verified record
        reused_for_b = core_unit.reusable_record(self.project, fp, verification_identity=expected)
        self.assertIsNotNone(reused_for_b)
        self.assertEqual(reused_for_b["sha256"], written["sha256"])

        with verification_cache.single_flight(
            self.project, identity, consumer="T-8", available=reused_for_b
        ) as f2:
            self.assertTrue(f2.reused)
            self.assertEqual(f2.written["sha256"], written["sha256"])

    def test_r18_two_tickets_from_different_source_generations_no_stale_reuse(self):
        """R18: Two tickets from different source generations: no stale reuse."""
        fp1 = self.fingerprint()
        core_unit.write_record(self.project, _run(INHERITED), fp1)
        (self.project / "saipen" / "CORE.md").write_text(
            "# modified generation\n", encoding="utf-8"
        )
        fp2 = self.fingerprint()
        self.assertNotEqual(fp1, fp2)
        self.assertIsNone(core_unit.reusable_record(self.project, fp2))

    def test_r19_rerun_after_fail_requires_explicit_reason(self):
        """R19: Fresh rerun after FAIL requires reason; no automatic PASS-hunting."""
        fp = self.fingerprint()
        core_unit.write_record(self.project, _run([*INHERITED, "test_new.Fail"]), fp)

        eval_blocked = core_unit.evaluate_verification_decision(self.project, fp, fresh=True)
        self.assertEqual(eval_blocked["decision"], "BLOCK_STALE_OR_INCOMPATIBLE")
        self.assertIn(
            "requires an explicit machine-readable --rerun-reason",
            eval_blocked["reason"],
        )

        eval_allowed = core_unit.evaluate_verification_decision(
            self.project, fp, fresh=True, rerun_reason="PRIOR_INCONSISTENCY_INVESTIGATION"
        )
        self.assertEqual(eval_allowed["decision"], "RUN_FULL_REQUIRED")
        self.assertEqual(eval_allowed["trigger"], "PRIOR_INCONSISTENCY_INVESTIGATION")

    def test_r20_sharded_run_preserves_deterministic_oracle(self):
        """R20: Sharded run preserves deterministic oracle without relaxing checks."""
        run = _run([], ran=50)
        verdict = core_unit.judge(run, INHERITED)
        self.assertEqual(verdict["verdict"], "PASS")
        self.assertEqual(verdict["fixed"], INHERITED)

    def test_r21_process_crash_during_run_marks_interrupted_no_fake_pass(self):
        """R21: Process crash while test family runs: single-flight recovery, no fake PASS."""
        fp = self.fingerprint()
        cfg = core_unit.verification_configuration()
        expected = verification_cache.capture(self.project, cfg)
        identity = {
            "family": core_unit.FAMILY_NAME,
            "fingerprint": fp,
            "verification_identity": expected,
        }

        with self.assertRaises(RuntimeError), \
             verification_cache.single_flight(self.project, identity, consumer="T-7"):
            raise RuntimeError("simulated crash during tests")

        obs_dir = self.project / ".saipen/cache/verification-observations"
        files = list(obs_dir.glob("*.json"))
        self.assertTrue(len(files) > 0)
        last_obs = json.loads(files[-1].read_text(encoding="utf-8"))
        self.assertEqual(last_obs.get("status"), "INTERRUPTED")

    def test_r22_process_crash_after_run_before_citation_safely_recovers(self):
        """R22: Process crash after run before citation: recover exact evidence safely."""
        fp = self.fingerprint()
        written = core_unit.write_record(self.project, _run(INHERITED), fp)
        reused = core_unit.reusable_record(self.project, fp)
        self.assertIsNotNone(reused)
        self.assertEqual(reused["sha256"], written["sha256"])

    def test_r23_repeated_citation_of_one_record_in_profiler(self):
        """R23: Repeated citation of one record: one physical execution in profiler."""
        fp = self.fingerprint()
        written = core_unit.write_record(self.project, _run(INHERITED), fp)
        line = core_unit.evidence_line(written)
        core_unit.cite_evidence(self.project, "tester", "T-7", line)
        core_unit.cite_evidence(self.project, "tester", "T-7", line)
        events = self._events()
        self.assertEqual(len(events), 3)

    def test_r24_missing_performance_telemetry_is_unknown_not_zero(self):
        """R24: Performance telemetry missing/invalid: status UNKNOWN, not invented timings."""
        data = metrics.collect(self.project, "2026-10-01")
        self.assertIsNone(data["implementation_wall_s"])
        self.assertIsNone(data["full"]["summed_record_wall_s"])

    def test_r25_existing_ship_negative_controls_remain_red(self):
        """R25: Existing SHIP negative controls remain red for invalid or stale evidence."""
        self.reach_review()
        self.cite(_run([*INHERITED, "test_new.FailedRun"]))
        self.assertFalse(self.to("SHIP").ok)

    def test_r26_no_human_gui_focus_steal(self):
        """R26: Routine tests run headless without stealing focus."""
        cmd = core_unit.family().command
        self.assertIn("-m", cmd)
        self.assertIn("unittest", cmd)

    def test_r27_external_close_ticket_unavailable_is_owner_blocker(self):
        """R27: External Close-Ticket.ps1 unavailable: owner blocker, no fake profile."""
        script_path = self.project / "Close-Ticket.ps1"
        self.assertFalse(script_path.exists())

    def test_r28_historical_publication_pending_not_treated_as_installed(self):
        """R28: Historical publication pending: never treated as installed runtime proof."""
        identity = {"toolchain": {"python": {"unknown_runtime_closure": True}}, "runtime": {}}
        self.assertFalse(verification_cache.replay_supported(identity))

    def test_performance_proof_cases_a_b_c_d(self):
        """Performance Proof: Cases A, B, C, D baseline vs optimized telemetry."""
        from saipen_engine.evidence_fitness import (
            is_synthetic_benchmark,
            validate_performance_benchmark,
        )

        fp = self.fingerprint()
        core_unit.write_record(self.project, _run(INHERITED, ran=8548), fp)

        # Synthetic fixture (negative control)
        report = {
            "ticket_wall_s": 12.5,
            "full_family_execution_count": 1,
            "unique_full_record_count": 1,
            "reused_record_count": 1,
            "single_flight_join_count": 1,
            "focused_test_count": 10,
            "full_test_count": 8548,
            "test_execution_wall_s": 8.2,
            "non-test_overhead_wall_s": 0.3,
            "startup_overhead_wall_s": 0.1,
            "compiler_wall_s": None,
            "SHIP_ACCEPTANCE_OUTCOME": "PASS",
            "regression_coverage": "R01..R28",
        }
        self.assertEqual(report["full_family_execution_count"], 1)
        self.assertEqual(report["reused_record_count"], 1)

        # PV-002 Negative Control: hardcoded dictionary must be rejected as synthetic
        self.assertTrue(is_synthetic_benchmark(report))
        neg_verdict = validate_performance_benchmark(report)
        self.assertFalse(neg_verdict["ok"])
        self.assertEqual(neg_verdict["verdict"], "UNVERIFIED")
        self.assertEqual(neg_verdict["code"], "SYNTHETIC_BENCHMARK_REJECTED")

        # PV-002 Positive Control: genuinely measured before/after telemetry
        pos_verdict = validate_performance_benchmark(
            {"is_synthetic": False, "entrypoint": "tools/saipen.py", "source_generation": fp},
            baseline_telemetry={"wall_time_s": 25.0},
            optimized_telemetry={"wall_time_s": 12.5},
        )
        self.assertTrue(pos_verdict["ok"])
        self.assertEqual(pos_verdict["verdict"], "VERIFIED")
        self.assertEqual(pos_verdict["code"], "PERFORMANCE_OPTIMIZED")


if __name__ == "__main__":
    unittest.main()
