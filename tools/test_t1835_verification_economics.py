"""Economics must preserve missing data, sharing, failures and measurement units."""

import io
import json
import math
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import saipen_metrics
import verification_metrics as metrics
from saipen_engine import core_unit, verification_cache as cache
from test_core_unit_gate import CoreUnitFixture, _run
from test_hermetic_env import isolate_host_session

STAMP = int(datetime(2026, 10, 20, 10, tzinfo=timezone.utc).timestamp() * 1e9)


def setUpModule():
    isolate_host_session()


class VerificationEconomics(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="t1835-economics-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.write(".saipen/BOARD.md", "## DOING\n## TODO\n## DONE\n"
                   "- [x] T-1 [P2] Complete | verify: checked\n## BLOCKED\n", text=True)

    def write(self, path, data, *, text=False):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data if text else json.dumps(data), encoding="utf-8")
        return target

    def record(self, name="run", *, family="unit", **fields):
        folder = "core-unit" if family == "unit" else "focused-unit"
        return self.write(f".saipen/evidence/{folder}/{name}.json", {
            "family": family, "finished_utc": "2026-10-20T10:00:00Z",
            "fingerprint": "source", "verdict": "PASS", "duration_s": 4,
            "red": [], **fields,
        })

    def request(self, name, **fields):
        return self.write(f".saipen/cache/verification-observations/{name}.json", {
            "kind": "single-flight-request", "requested_ns": STAMP,
            "status": "COMPLETE", "elapsed_wall_s": 4, **fields,
        })

    def collect(self):
        return metrics.collect(self.root, "2026-10-01")

    def test_absent_observations_are_unknown_not_zero_measurements(self):
        data = self.collect()
        self.assertIsNone(data["implementation_wall_s"])
        self.assertIsNone(data["verification_share"])
        self.assertIsNone(data["full"]["summed_record_wall_s"])
        self.assertIsNone(data["requests"]["cache_hit_rate"])
        self.assertIsNone(data["requests"]["median_feedback_wall_s"])
        self.assertIsNone(data["regressions_escaping_earlier_tiers"])
        self.assertIsNone(data["impact"]["measured_wall_s"])
        self.assertTrue(data["advisory"])

    def test_shared_execution_is_not_counted_once_per_consumer(self):
        record = self.record(duration_s=8, module_durations_s={"a": 5, "b": 7})
        relative = record.relative_to(self.root).as_posix()
        self.request("first", ticket="T-1", record=relative, reused=False,
                     elapsed_wall_s=10, coordination_wait_wall_s=.25)
        self.request("second", ticket="T-2", record=relative, reused=True,
                     elapsed_wall_s=6, coordination_wait_wall_s=2)
        data = self.collect()
        self.assertEqual(data["full"]["records"], 1)
        self.assertEqual(data["full"]["summed_record_wall_s"], 8)
        self.assertEqual(data["full"]["summed_module_process_s"], 12)
        self.assertEqual(data["requests"]["summed_request_wall_s"], 16)
        self.assertEqual(data["requests"]["summed_coordination_wall_s"], 2.25)
        self.assertEqual(data["requests"]["cache_hit_rate"], .5)
        self.assertIsNone(data["operator_elapsed_wall_s"])
        self.assertTrue(data["per_ticket"]["T-1"]["completed"])
        self.assertFalse(data["per_ticket"]["T-2"]["completed"])

    def test_feedback_uses_nearest_rank_p95_and_not_record_duration(self):
        self.record(duration_s=1000)
        for value in range(1, 21):
            self.request(str(value), reused=value % 2 == 0, elapsed_wall_s=value)
        data = self.collect()
        self.assertEqual(data["requests"]["median_feedback_wall_s"], 10.5)
        self.assertEqual(data["requests"]["p95_feedback_wall_s"], 19)

    def test_interrupted_and_pending_requests_do_not_invent_cache_outcomes(self):
        self.request("interrupted", status="INTERRUPTED", elapsed_wall_s=2)
        self.request("pending", status="REQUESTED", elapsed_wall_s=None)
        data = self.collect()
        self.assertEqual(data["requests"]["completed"], 0)
        self.assertIsNone(data["requests"]["cache_hit_rate"])
        self.assertEqual(data["requests"]["feedback_samples"], 0)
        self.assertEqual(data["requests"]["summed_request_wall_s"], 2)

    def test_same_source_different_environment_is_not_compatible_repetition(self):
        self.record("a", verification_identity={"environment": "first"})
        self.record("b", verification_identity={"environment": "second"})
        data = self.collect()
        self.assertEqual(data["same_fingerprint_repeat_candidates"], 1)
        self.assertEqual(data["compatible_repeat_candidates"], 0)
        self.assertIsNone(data["redundant_verification_rate"])

    def test_legacy_identity_and_explicit_fresh_do_not_prove_redundancy(self):
        self.record("a")
        self.record("b")
        self.request("fresh", fresh=True, reused=False)
        data = self.collect()
        self.assertEqual(data["records_with_compatibility"], 0)
        self.assertEqual(data["same_fingerprint_repeat_candidates"], 1)
        self.assertEqual(data["compatible_repeat_candidates"], 0)
        self.assertIsNone(data["redundant_verification_rate"])

    def test_compatible_repeat_stays_a_candidate_not_an_automatic_defect(self):
        for name in ("a", "b"):
            self.record(name, verification_identity={"environment": "same"})
        data = self.collect()
        self.assertEqual(data["compatible_repeat_candidates"], 1)
        self.assertIsNone(data["redundant_verification_rate"])

    def test_failure_ids_and_recorded_verdicts_remain_visible(self):
        self.record("red", verdict="FAIL", red=["test_x.red"])
        self.record("focus", family="focused-unit", verdict="FAIL", red=None,
                    runs=[{"red": ["test_y.red"]}])
        data = self.collect()
        self.assertEqual(data["full"]["recorded_red_ids"], ["test_x.red"])
        self.assertEqual(data["focused"]["recorded_red_ids"], ["test_y.red"])
        self.assertEqual(data["full"]["recorded_verdicts"], {"FAIL": 1})
        self.assertNotIn("ok", data)

    def test_incomplete_failure_inventory_is_unknown_and_preserves_known_ids(self):
        self.record("missing", verdict="FAIL", red=None)
        unknown = self.collect()
        self.assertIsNone(unknown["full"]["recorded_red_ids"])
        self.assertEqual(unknown["full"]["red_inventory_unknown_records"], 1)
        self.assertTrue(unknown["diagnostics"])
        self.record("known", verdict="FAIL", red=["test_known.red"])
        mixed = self.collect()
        self.assertEqual(mixed["full"]["recorded_red_ids"], ["test_known.red"])
        self.assertEqual(mixed["full"]["red_inventory_records"], 1)
        self.assertEqual(mixed["full"]["red_inventory_unknown_records"], 1)

    def test_nonfinite_negative_and_boolean_times_are_not_measurements(self):
        self.record("bad", duration_s=math.nan, module_durations_s={"x": True},
                    timings_s={"copy_wall_s": -1})
        self.request("bad", elapsed_wall_s=math.inf, coordination_wait_wall_s=True)
        data = self.collect()
        self.assertIsNone(data["full"]["summed_record_wall_s"])
        self.assertIsNone(data["full"]["summed_module_process_s"])
        self.assertIsNone(data["full"]["stage_totals_s"]["copy_wall_s"])
        self.assertEqual(data["full"]["stage_samples"]["copy_wall_s"], 0)
        self.assertIsNone(data["requests"]["summed_request_wall_s"])

    def test_missing_stage_samples_do_not_become_measured_zero(self):
        self.record("a", timings_s={"copy_wall_s": 0})
        self.record("b")
        data = self.collect()
        self.assertEqual(data["full"]["stage_totals_s"]["copy_wall_s"], 0)
        self.assertEqual(data["full"]["stage_samples"]["copy_wall_s"], 1)

    def test_date_window_covers_records_and_requests_and_excludes_undated(self):
        self.record("old", finished_utc="2026-09-01T00:00:00Z")
        self.record("new")
        self.record("unknown", finished_utc=None)
        self.request("old", requested_ns=0)
        self.request("new")
        data = self.collect()
        self.assertEqual(data["full"]["records"], 1)
        self.assertEqual(data["requests"]["observed"], 1)
        self.assertTrue(data["diagnostics"])

    def test_corrupt_records_remain_diagnostics_and_never_run_anything(self):
        self.record("valid")
        self.write(".saipen/evidence/core-unit/broken.json", "{broken", text=True)
        self.write(".saipen/evidence/core-unit/array.json", [], text=False)
        data = self.collect()
        self.assertEqual(data["full"]["records"], 1)
        self.assertEqual(len(data["diagnostics"]), 2)

    def test_cli_reuses_existing_reporter_without_git_scan_or_writes(self):
        self.record()
        before = {str(path): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        output = io.StringIO()
        legacy = mock.patch.object(saipen_metrics, "collect",
                                   side_effect=AssertionError("git scan"))
        with mock.patch.object(saipen_metrics, "REPO", self.root), \
                legacy, redirect_stdout(output):
            self.assertEqual(saipen_metrics.main(["--verification", "--json"]), 0)
        self.assertTrue(json.loads(output.getvalue())["advisory"])
        after = {str(path): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_invalid_window_and_unrelated_project_root_fail_clearly(self):
        with self.assertRaises(ValueError):
            metrics.collect(self.root, "invalid")
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as result:
            saipen_metrics.main(["--project-root", str(self.root)])
        self.assertEqual(result.exception.code, 2)

    def test_render_names_required_categories_and_does_not_claim_a_share(self):
        text = metrics.render(self.collect())
        for heading in ("IMPLEMENTATION", "FOCUSED TESTS", "IMPACT TESTS", "FULL TESTS",
                        "WAIT/RECOVERY", "OTHER"):
            self.assertIn(heading, text)
        self.assertIn("UNKNOWN", text)
        self.assertNotIn("98%", text)
        self.assertNotIn("PASS", text)


class ObservationAttribution(CoreUnitFixture):
    def test_real_focused_producer_attributes_its_consumer(self):
        from saipen_engine import focused_unit

        self.assertTrue(self.to("VERIFY").ok)
        (self.project / "tools/verification_policy.json").write_text(
            json.dumps({"schema": 1, "ticket": "focused", "publication": "full"}))
        (self.project / "tools/test_probe.py").write_text(
            "import unittest\nclass Probe(unittest.TestCase):\n"
            "    def test_ok(self):\n        self.assertEqual(2+2,4)\n")
        args = Namespace(ticket="T-7", agent="tester", pattern=["test_probe.py"],
                         timeout=30, fresh=False)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(focused_unit.evidence(self.project, args), 0)
        data = metrics.collect(self.project)
        self.assertEqual(data["per_ticket"]["T-7"]["requests"], 1)
        self.assertEqual(data["requests"]["coordination_samples"], 1)
        self.assertEqual(data["focused"]["records"], 1)

    def test_request_ticket_and_real_lock_wait_are_advisory_not_identity(self):
        identity = {"family": "unit", "fingerprint": core_unit.tree_fingerprint(self.project),
                    "verification_identity": cache.capture(
                        self.project, core_unit.verification_configuration())}
        with cache.single_flight(self.project, identity, consumer="T-7") as first:
            with self.assertRaises(TimeoutError), cache.single_flight(
                self.project, identity, timeout=.05, consumer="T-8"
            ):
                self.fail("waiter became an executor")
            written = core_unit.write_record(self.project, _run([]), identity["fingerprint"])
            first.publish(written)
        directory = self.project / ".saipen/cache/verification-observations"
        observations = [json.loads(path.read_text()) for path in directory.glob("*.json")]
        self.assertEqual({row["ticket"] for row in observations}, {"T-7", "T-8"})
        self.assertEqual(len({row["key"] for row in observations}), 1)
        waiting = next(row for row in observations if row["ticket"] == "T-8")
        self.assertGreaterEqual(waiting["coordination_wait_wall_s"], .04)
        self.assertLessEqual(waiting["coordination_wait_wall_s"], waiting["elapsed_wall_s"] + .001)
        self.assertNotIn("ticket", identity)
