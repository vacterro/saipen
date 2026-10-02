"""Three-report regressions: truthful recovery, reproduction and silent policy."""

import json
import contextlib
import io
import subprocess
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

import improve
from saipen_engine import hush
from saipen_engine.reproduction import run_reproduction
from test_hermetic_env import isolate_host_session
import test_improve_reconcile as fixtures
from test_improve_reconcile import _git

ROOT = Path(__file__).resolve().parents[1]


def setUpModule():
    isolate_host_session()


class ImproveFollowupTests(unittest.TestCase):
    setUp = fixtures.ReconcileTests.setUp
    _project = fixtures.ReconcileTests._project
    _cycle = fixtures.ReconcileTests._cycle
    _add_seat = fixtures.ReconcileTests._add_seat
    _run_text = staticmethod(fixtures.ReconcileTests._run_text)
    _dispose = fixtures.ReconcileTests._dispose
    _move_tree = fixtures.ReconcileTests._move_tree

    def test_disposed_stale_seats_get_an_executable_lossless_route(self):
        root = self._project()
        cycle = self._cycle(root)
        reports = []
        for i in range(6):
            seat = f"old-{i}"
            reports.append(self._add_seat(root, cycle, seat, findings=1))
            self._dispose(cycle, seat, 1, "SUPERSEDED")
        before = {p: p.read_bytes() for p in [*reports, cycle / "SWEEP.md"]}
        self._move_tree(root)
        self._add_seat(root, cycle, "replacement")
        with self.assertRaises(improve.ImproveError) as caught:
            improve.complete_cycle(cycle)
        message = str(caught.exception)
        command = f"saipen improve reconcile {cycle.name}"
        self.assertIn(command, message)
        self.assertNotIn("dispose every historical", message)
        result = subprocess.run([sys.executable, str(ROOT / "tools/saipen.py"),
                                 *command.split()[1:], "--json"], cwd=root,
                                capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["outcome"], "COMPLETE")
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_completion_reports_unpersisted_history_without_touching_git(self):
        root = self._project()
        cycle = self._cycle(root)
        (root / "unrelated.txt").write_text("user change", encoding="utf-8")
        _git(root, "add", "unrelated.txt")
        self._add_seat(root, cycle, "current")
        index = _git(root, "diff", "--cached", "--binary")
        head = _git(root, "rev-parse", "HEAD")
        result = improve.complete_cycle(cycle)
        self.assertIn("bookkeeping", result)
        bookkeeping = result["bookkeeping"]
        self.assertFalse(bookkeeping["persisted"])
        self.assertIn("git commit --only", bookkeeping["next_action"])
        self.assertTrue(any("MANIFEST.md" in p for p in bookkeeping["untracked_history"]))
        self.assertEqual(_git(root, "rev-parse", "HEAD"), head)
        self.assertEqual(_git(root, "diff", "--cached", "--binary"), index)
        # Explicit operator-scoped commit persists history; unrelated staging survives.
        paths = [".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md",
                 cycle.relative_to(root).as_posix()]
        _git(root, "add", "-f", "--", *paths)
        _git(root, "commit", "-qm", "protocol history", "--only", "--", *paths)
        self.assertTrue(improve.protocol_git_status(root, cycle)["persisted"])
        self.assertIn("unrelated.txt", _git(root, "diff", "--cached", "--name-only"))


class ReproductionTests(unittest.TestCase):
    def test_real_path_probe_distinguishes_guard_and_broken_harness(self):
        import nitro_integrity_repro

        for error, status in ((improve.ImproveError("unsafe path"), "NOT_REPRODUCED"),
                              (OSError("fixture unavailable"), "INVALID")):
            with patch.object(improve, "cycle_dir", side_effect=error), \
                    patch.object(nitro_integrity_repro, "fixture", return_value=Path("probe")):
                self.assertEqual(run_reproduction(nitro_integrity_repro.r9_cycle_path_traversal)
                                 ["status"], status)

    def test_real_producer_rejects_exit_status_as_defect_predicate(self):
        import nitro_integrity_repro

        output = io.StringIO()
        repros = [("guard", lambda: (1, "exit status"))]
        with patch.object(nitro_integrity_repro, "REPROS", repros), \
                contextlib.redirect_stdout(output):
            result = nitro_integrity_repro.main()
        self.assertIn("[INVALID]", output.getvalue())
        self.assertNotIn("[REPRODUCED]", output.getvalue())
        self.assertEqual(result, 1)

    def test_unsafe_effect_is_reproduced(self):
        self.assertEqual(run_reproduction(lambda: (True, "secret escaped sanitizer"))["status"],
                         "REPRODUCED")

    def test_protective_rejection_is_not_reproduced(self):
        effects = []

        def probe():
            try:
                raise ValueError("unsafe path rejected")
            except ValueError as exc:
                return bool(effects), str(exc) + "; no path escaped"

        self.assertEqual(run_reproduction(probe)["status"], "NOT_REPRODUCED")

    def test_harness_error_and_non_boolean_predicate_are_invalid(self):
        def broken():
            raise RuntimeError("fixture unavailable")
        for probe in (broken, lambda: (None, "unknown"), lambda: (1, "nonzero exit"),
                      lambda: (False, "")):
            self.assertEqual(run_reproduction(probe)["status"], "INVALID")


class SilentExecutionTests(unittest.TestCase):
    def test_existing_policy_consumer_defaults_to_silent(self):
        self.assertTrue(hush.activate("cc")["policy"].suppresses("progress"))

    def test_public_intermediate_transport_refuses_narration(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/saipen.py"), "response", "intermediate",
             "--stdin", "--request", "continue", "--json"], input="Reading files now.",
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(json.loads(result.stdout)["code"], "INTERMEDIATE_TEXT_SUPPRESSED")
        self.assertNotEqual(result.returncode, 0)

    def test_a_b_f_h_runnable_narration_is_suppressed(self):
        for request in ("", "continue", "finish it", "keep going", "work on this"):
            for prose in ("I am reading the board now.", "SCOUT complete. Starting BUILD.",
                          "The tests are still running."):
                result = hush.intermediate_verdict(prose, request=request)
                self.assertEqual(result["code"], "INTERMEDIATE_TEXT_SUPPRESSED")
                self.assertFalse(result["emit"])

    def test_c_d_g_i_machine_data_blockers_and_final_reports_survive(self):
        for kind in hush.MANDATORY | {"runtime_status", "heartbeat", "host_thought"}:
            self.assertFalse(hush.DEFAULT.suppresses(kind))
        self.assertTrue(hush.intermediate_verdict("")["ok"])

    def test_e_progress_is_explicit_bounded_and_turn_local(self):
        for request in ("keep me updated", "show progress", "tell me after every phase",
                        "explain what you're doing", "держи меня в курсе",
                        "hoia mind kursis"):
            self.assertTrue(hush.for_request(request).progress_authorized)
            self.assertTrue(hush.intermediate_verdict("Kontroll käib.", request=request)["ok"])
            self.assertEqual(hush.intermediate_verdict("rida\n" * 40, request=request)["code"],
                             "CHAT_STYLE_DRIFT")
        for request in ('"show progress"', "do not show progress", "continue",
                        "example: keep me updated"):
            self.assertFalse(hush.for_request(request).progress_authorized)
        self.assertTrue(hush.for_request("continue").suppresses("progress"))

    def test_j_details_and_final_gates_keep_their_owner(self):
        from saipen_engine.response_surface import detail_mode_for_request
        self.assertFalse(hush.DEFAULT.suppresses("details"))
        self.assertNotEqual(detail_mode_for_request("give me a detailed report"), "NONE")

    def test_k_adapter_capabilities_are_explicit_and_do_not_claim_stream_control(self):
        registry = json.loads((ROOT / "extensions/adapters/registry.json").read_text())
        for adapter in registry["adapters"]:
            capabilities = adapter["execution_capabilities"]
            self.assertEqual(capabilities["final_response_gate"], adapter["response_enforcement"])
            self.assertEqual(capabilities["host_thought_visibility_control"], "UNAVAILABLE")
            self.assertEqual(capabilities["intermediate_text_suppression"], "ADVISORY")
            self.assertIn("silent_tool_continuation", capabilities)
            self.assertIn("structured_progress", capabilities)


if __name__ == "__main__":
    unittest.main()
