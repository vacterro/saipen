"""T-1803: archived findings have a lossless, admitted retrospective exit.

All findings, authorities and Git repositories in this suite are disposable
unit controls. No test edits AUDAPACK or asserts real operator acceptance.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import improve  # noqa: E402
import saipen  # noqa: E402
import test_improve_reconcile as fixtures  # noqa: E402
from saipen_engine import continue_fallback as cf  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


class ArchivedImproveTests(unittest.TestCase):
    _cycle = fixtures.ReconcileTests._cycle
    _run_text = staticmethod(fixtures.ReconcileTests._run_text)
    _add_seat = fixtures.ReconcileTests._add_seat
    _add_idle_seat = fixtures.ReconcileTests._add_idle_seat
    _dispose = fixtures.ReconcileTests._dispose

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t1803-")
        assert Path(self._tmp.name).resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
        self.addCleanup(self._tmp.cleanup)

    def _project(self):
        root = fixtures.ReconcileTests._project(self)
        process = subprocess.run(
            [
                sys.executable,
                "-B",
                str(TOOLS / "saipen.py"),
                "--project-root",
                str(root),
                "--agent",
                "probe",
                "start",
                "Disposable T-1803 local retrospective engineering control",
                "--json",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        admitted = json.loads(process.stdout)
        self.assertTrue(admitted.get("work_claimed"), admitted)
        self._work_ticket = admitted["ticket"]
        return root

    def _archived(self, *, findings=2, empty_first=False, complete=False, partial=False):
        root = self._project()
        cycle = self._cycle(root, "imp-t1803-20261016-1")
        content_seat = "probe-02" if empty_first else "probe-01"
        empty_seat = "probe-01" if empty_first else "probe-02"
        if empty_first:
            self._add_idle_seat(root, cycle, empty_seat)
        if findings:
            self._add_seat(
                root, cycle, content_seat, findings=findings, complete=complete or partial
            )
        else:
            self._add_idle_seat(root, cycle, content_seat)
        if not empty_first:
            self._add_idle_seat(root, cycle, empty_seat)
        if partial:
            self._dispose(cycle, content_seat, 1)
        # Incoming historical fixture only: reproduce archives created by an
        # earlier engine. This is not a claimed canonical live transition.
        manifest = cycle / "MANIFEST.md"
        text = manifest.read_text(encoding="utf-8").replace(
            "cycle_status: active", "cycle_status: archived"
        )
        manifest.write_text(text.rstrip() + "\ncycle_aborted: draft-preserved\n", encoding="utf-8")
        (root / "proof.txt").write_text(
            "Synthetic T-1803 unit adjudication; no production finding or human approval.\n",
            encoding="utf-8",
        )
        return root, cycle, content_seat

    @staticmethod
    def _history(cycle):
        return {
            p.relative_to(cycle).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in cycle.rglob("*")
            if p.is_file()
        }

    @staticmethod
    def _successor(cycle):
        return cycle.parents[2] / ".saipen/improve-reconciliation" / (cycle.name + ".jsonl")

    @staticmethod
    def _entry(seat, finding=1, **changes):
        return {
            "run": "RUN-1",
            "imp_id": f"IMP-{finding:03d}",
            "disposition": "INVALID",
            "ticket": "-",
            "reproduced": "n",
            "report": seat + "/saipen_improve_PROBE.md",
            "verification": "proof.txt",
            "retrospective": True,
            **changes,
        }

    def _all_dispositions(self, cycle, seat, count=2):
        for number in range(1, count + 1):
            result = improve.write_sweep_entry(cycle, self._entry(seat, number))
            self.assertTrue(result.get("ok"), result)

    def test_malformed_successor_returns_blocked_without_writes(self):
        from saipen_engine.improve_retrospective import inspect_archive

        root, cycle, seat = self._archived(findings=1)
        history = self._history(cycle)
        improve.write_sweep_entry(
            cycle, self._entry(seat, disposition="NEEDS_EXTERNAL_EVIDENCE", verification="-")
        )
        successor = self._successor(cycle)
        valid = successor.read_bytes()
        self.assertTrue(inspect_archive(cycle)["pending_findings_known"])
        malformed = [
            (name, valid + (json.dumps(value) + "\n").encode("utf-8"))
            for name, value in (
                ("array", []), ("null", None), ("boolean", True),
                ("number", 1), ("string", "invalid-event"),
            )
        ]
        lines = valid.splitlines(keepends=True)
        event = json.loads(lines[-1])
        event["evidence"] = []
        event.pop("sha256")
        event["sha256"] = hashlib.sha256(
            json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()
        malformed.append(("evidence-array", b"".join(lines[:-1]) + (
            json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")))
        for name, raw in malformed:
            with self.subTest(shape=name):
                successor.write_bytes(raw)  # Corrupt incoming fixture only.
                live = cf.cycle_liveness(root, cycle.name)
                self.assertTrue(live["blocked"], live)
                self.assertFalse(live["stale"], live)
                self.assertFalse(live["pending_findings_known"], live)
                result = improve.reconcile_cycle(cycle, dry_run=True)
                self.assertFalse(result["ok"], result)
                self.assertTrue(result["blocked"], result)
                if name in ("array", "evidence-array"):
                    code, result = self._cli(root, "improve", "reconcile", cycle.name, "--dry-run")
                    self.assertNotEqual(code, 0, result)
                    self.assertTrue(result["blocked"], result)
                self.assertEqual(successor.read_bytes(), raw)
                self.assertEqual(self._history(cycle), history)

    def test_empty_archive_is_not_advertised_as_pending(self):
        root, cycle, _seat = self._archived(findings=0)
        before = self._history(cycle)
        live = cf.cycle_liveness(root, cycle.name)
        self.assertFalse(live["stale"], live)
        self.assertEqual(improve.reconcile_cycle(cycle)["code"], "ALREADY_TERMINAL")
        self.assertEqual(self._history(cycle), before)

    def test_secondary_seat_findings_are_visible(self):
        root, cycle, seat = self._archived(empty_first=True)
        live = cf.cycle_liveness(root, cycle.name)
        self.assertEqual(len(live.get("pending_findings", [])), 2, live)
        self.assertEqual({item["seat_id"] for item in live["pending_findings"]}, {seat})
        self.assertIn("sweep-queue", live.get("canonical_next_command", ""))
        self.assertNotIn("submit", live.get("submit_route", ""))

    def test_terminal_status_does_not_hide_unfinished_findings(self):
        _root, cycle, _seat = self._archived()
        before = self._history(cycle)
        result = improve.reconcile_cycle(cycle, dry_run=True)
        self.assertFalse(result["ok"], result)
        self.assertEqual(len(result.get("pending_findings", [])), 2, result)
        self.assertEqual(self._history(cycle), before)

    def test_first_historical_disposition_preserves_original_missing_sweep(self):
        _root, cycle, seat = self._archived()
        before = self._history(cycle)
        result = improve.write_sweep_entry(cycle, self._entry(seat))
        self.assertTrue(result.get("ok"), result)
        self.assertTrue(self._successor(cycle).is_file())
        self.assertFalse((cycle / "SWEEP.md").exists())
        self.assertEqual(self._history(cycle), before)

    def test_resolved_disposition_requires_owned_verification_evidence(self):
        _root, cycle, seat = self._archived()
        for verification in ("-", "missing-proof.txt", "../outside-proof.txt"):
            with self.subTest(verification=verification), self.assertRaisesRegex(
                improve.ImproveError, "evidence|verification|owned"
            ):
                improve.write_sweep_entry(
                    cycle,
                    self._entry(
                        seat,
                        disposition="ALREADY_FIXED",
                        verification=verification,
                        fixed_by="T-001",
                        reproduced="y",
                    ),
                )
        self.assertFalse(self._successor(cycle).exists())

    def test_partial_sweep_is_preserved_and_combined_with_successor(self):
        root, cycle, seat = self._archived(partial=True)
        before = self._history(cycle)
        result = improve.write_sweep_entry(cycle, self._entry(seat, 2))
        self.assertTrue(result.get("ok"), result)
        self.assertTrue(improve.reconcile_cycle(cycle)["ok"])
        self.assertFalse(cf.cycle_liveness(root, cycle.name)["stale"])
        self.assertEqual(self._history(cycle), before)

    def test_exact_disposition_retry_is_idempotent(self):
        _root, cycle, seat = self._archived()
        improve.write_sweep_entry(cycle, self._entry(seat))
        before = self._successor(cycle).read_bytes()
        result = improve.write_sweep_entry(cycle, self._entry(seat))
        self.assertTrue(result.get("ok"), result)
        self.assertEqual(self._successor(cycle).read_bytes(), before)

    def test_conflicting_duplicate_disposition_never_overwrites(self):
        _root, cycle, seat = self._archived()
        improve.write_sweep_entry(cycle, self._entry(seat))
        before = self._successor(cycle).read_bytes()
        with self.assertRaisesRegex(improve.ImproveError, "duplicate|already|conflict"):
            improve.write_sweep_entry(cycle, self._entry(seat, disposition="NOT_REPRODUCED"))
        self.assertEqual(self._successor(cycle).read_bytes(), before)

    def test_concurrent_dispositions_preserve_both_findings_after_bounded_retry(self):
        root, cycle, seat = self._archived()
        before = self._history(cycle)

        def write(number):
            try:
                return improve.write_sweep_entry(cycle, self._entry(seat, number))
            except (improve.ImproveError, PermissionError) as exc:
                return {"ok": False, "detail": str(exc)}

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, (1, 2)))
        self.assertTrue(any(result.get("ok") for result in results), results)
        # A fenced/busy writer retries from a fresh read, never a stale plan.
        self._all_dispositions(cycle, seat)
        self.assertTrue(improve.reconcile_cycle(cycle)["ok"])
        self.assertEqual(cf.cycle_liveness(root, cycle.name).get("pending_findings"), [])
        self.assertEqual(self._history(cycle), before)

    def test_original_history_change_invalidates_successor_binding(self):
        _root, cycle, seat = self._archived()
        improve.write_sweep_entry(cycle, self._entry(seat))
        before = self._successor(cycle).read_bytes()
        report = cycle / seat / "saipen_improve_PROBE.md"
        report.write_text(
            report.read_text(encoding="utf-8") + "\nchanged fixture history\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(improve.ImproveError, "changed|binding|stale"):
            improve.write_sweep_entry(cycle, self._entry(seat, 2))
        self.assertEqual(self._successor(cycle).read_bytes(), before)

    def test_wrong_lineage_cannot_reuse_successor(self):
        root, cycle, seat = self._archived()
        improve.write_sweep_entry(cycle, self._entry(seat))
        before = self._successor(cycle).read_bytes()
        from saipen_engine.paths import identity_file_content, new_project_lineage

        (root / ".saipen/IDENTITY.md").write_text(
            identity_file_content(new_project_lineage()), encoding="utf-8"
        )
        with self.assertRaisesRegex(improve.ImproveError, "lineage|identity|binding"):
            improve.write_sweep_entry(cycle, self._entry(seat, 2))
        self.assertEqual(self._successor(cycle).read_bytes(), before)

    def test_needs_external_evidence_stays_visible_without_endless_actionable_retry(self):
        root, cycle, seat = self._archived(findings=1)
        result = improve.write_sweep_entry(
            cycle, self._entry(seat, disposition="NEEDS_EXTERNAL_EVIDENCE", verification="-")
        )
        self.assertTrue(result.get("ok"), result)
        result = improve.reconcile_cycle(cycle)
        self.assertFalse(result["ok"], result)
        live = cf.cycle_liveness(root, cycle.name)
        self.assertTrue(live.get("blocked"), live)
        self.assertEqual(len(live.get("pending_findings", [])), 1)
        self.assertFalse(live["stale"], live)

    def test_reconciled_archive_stops_repeated_advertisement(self):
        root, cycle, seat = self._archived()
        before = self._history(cycle)
        self._all_dispositions(cycle, seat)
        self.assertTrue(improve.reconcile_cycle(cycle)["ok"])
        successor = self._successor(cycle).read_bytes()
        for _ in range(3):
            result = improve.reconcile_cycle(cycle)
            self.assertTrue(result["ok"], result)
            payload = cf.with_cycle_liveness({"cycle_id": cycle.name}, root)
            self.assertFalse(payload["improve_cycle"]["stale"])
            self.assertFalse(payload.get("improve_stale_cycles"))
            self.assertEqual(self._successor(cycle).read_bytes(), successor)
        self.assertEqual(self._history(cycle), before)

    def test_fresh_process_sees_persisted_reconciliation(self):
        root, cycle, seat = self._archived()
        self._all_dispositions(cycle, seat)
        self.assertTrue(improve.reconcile_cycle(cycle)["ok"])
        program = (
            "import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);"
            "from saipen_engine.continue_fallback import cycle_liveness;"
            "print(json.dumps(cycle_liveness(Path(sys.argv[2]),sys.argv[3])))"
        )
        process = subprocess.run(
            [sys.executable, "-B", "-c", program, str(TOOLS), str(root), cycle.name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        live = json.loads(process.stdout)
        self.assertFalse(live["stale"], live)
        self.assertEqual(live.get("pending_findings"), [])

    def test_ordinary_archived_mutators_remain_forbidden(self):
        _root, cycle, seat = self._archived()
        before = self._history(cycle)
        with self.assertRaises(improve.ImproveError):
            improve.write_sweep_entry(cycle, dict(self._entry(seat), retrospective=False))
        with self.assertRaises(improve.ImproveError):
            improve.retire_seat(cycle, "probe-02", "EMPTY_DRAFT")
        with self.assertRaises(improve.ImproveError):
            improve.complete_report(cycle / seat / "saipen_improve_PROBE.md")
        self.assertEqual(self._history(cycle), before)

    def test_missing_admission_refuses_at_existing_public_boundary(self):
        root, cycle, _seat = self._archived()
        before = self._history(cycle)
        with mock.patch.object(
            saipen, "_negotiate_capability", return_value="read-only"
        ), mock.patch.object(saipen, "_emit") as emitted:
            code = saipen._public_improve(root, ["reconcile", cycle.name], True, False)
        self.assertNotEqual(code, 0)
        self.assertTrue(emitted.called)
        self.assertEqual(self._history(cycle), before)
        self.assertFalse(self._successor(cycle).exists())

    def test_no_go_binding_brake_refuses_retrospective_mutation(self):
        root, cycle, seat = self._archived()
        state = root / ".saipen/STATE.md"
        state.write_text(
            re.sub(
                r"(?m)^next_action:.*$",
                'next_action: "WAIT: blocked -- NO_GO controlled unit safety boundary"',
                state.read_text(encoding="utf-8"),
            ),
            encoding="utf-8",
        )
        self.assertIn("NO_GO", state.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(improve.ImproveError, "WAIT|NO_GO|blocked"):
            improve.write_sweep_entry(cycle, self._entry(seat))
        self.assertFalse(self._successor(cycle).exists())

    def test_foreign_actor_cannot_mutate_claimed_project_history(self):
        _root, cycle, seat = self._archived()
        with self.assertRaisesRegex(improve.ImproveError, "OWNERSHIP|owner|actor"):
            improve.write_sweep_entry(cycle, self._entry(seat, actor="foreign-live-actor"))
        self.assertFalse(self._successor(cycle).exists())

    def test_interrupted_append_recovers_without_mutating_original_cycle(self):
        root, cycle, seat = self._archived()
        before = self._history(cycle)
        with mock.patch.dict(os.environ, {"NITRO_CRASH_AFTER_PREPARE": "1"}):
            try:
                result = improve.write_sweep_entry(cycle, self._entry(seat))
            except (improve.ImproveError, SystemExit) as exc:
                if isinstance(exc, SystemExit):
                    self.assertEqual(exc.code, 87)
                result = {"ok": False}
        self.assertFalse(result.get("ok"), result)
        from saipen_engine.journal import auto_recover_pending

        recovered = auto_recover_pending(root)
        self.assertTrue(recovered.get("ok"), recovered)
        # The canonical journal safely ABORTS an untouched PREPARED plan.
        # It must not invent a committed disposition. A fresh admitted retry
        # then commits against fresh inputs.
        self.assertFalse(self._successor(cycle).exists(), recovered)
        self.assertEqual(self._history(cycle), before)
        self.assertTrue(improve.write_sweep_entry(cycle, self._entry(seat)).get("ok"))
        self.assertTrue(self._successor(cycle).is_file())

    def test_recovery_refuses_changed_original_dependency(self):
        root, cycle, seat = self._archived()
        with mock.patch.dict(os.environ, {"NITRO_CRASH_AFTER_VERIFIED": "1"}):
            try:
                improve.write_sweep_entry(cycle, self._entry(seat))
            except (improve.ImproveError, SystemExit) as exc:
                if isinstance(exc, SystemExit):
                    self.assertEqual(exc.code, 87)
                pass
        report = cycle / seat / "saipen_improve_PROBE.md"
        report.write_text(
            report.read_text(encoding="utf-8") + "\nchanged after PREPARED\n", encoding="utf-8"
        )
        from saipen_engine.journal import auto_recover_pending

        recovered = auto_recover_pending(root)
        self.assertFalse(recovered.get("ok"), recovered)
        self.assertTrue(self._successor(cycle).is_file())
        self.assertTrue(cf.cycle_liveness(root, cycle.name).get("blocked"))

    def test_current_active_cycle_is_not_a_retrospective_target(self):
        _root, cycle, seat = self._archived()
        manifest = cycle / "MANIFEST.md"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace(
                "cycle_status: archived", "cycle_status: active"
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(improve.ImproveError, "terminal|archiv|retrospective"):
            improve.write_sweep_entry(cycle, self._entry(seat))
        self.assertFalse(self._successor(cycle).exists())

    def test_genuinely_complete_cycle_keeps_existing_terminal_behavior(self):
        root = self._project()
        cycle = self._cycle(root, "imp-t1803-20261016-complete")
        self._add_seat(root, cycle, "probe-01", findings=0, complete=True)
        self.assertTrue(improve.complete_cycle(cycle)["ok"])
        before = self._history(cycle)
        self.assertEqual(improve.reconcile_cycle(cycle)["code"], "ALREADY_TERMINAL")
        self.assertFalse(cf.cycle_liveness(root, cycle.name)["stale"])
        self.assertEqual(self._history(cycle), before)
        self.assertFalse(self._successor(cycle).exists())

    def test_missing_active_work_is_not_retrospective_admission(self):
        root, cycle, seat = self._archived()
        # A stopped canonical seat does not inherit retrospective permission.
        process = subprocess.run(
            [
                sys.executable,
                "-B",
                str(TOOLS / "saipen.py"),
                "--project-root",
                str(root),
                "--agent",
                "probe",
                "ticket",
                "block",
                self._work_ticket,
                "Disposable unit external boundary",
                "--json",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        with self.assertRaisesRegex(improve.ImproveError, "NO_ACTIVE_WORK|admission"):
            improve.write_sweep_entry(cycle, self._entry(seat))
        self.assertFalse(self._successor(cycle).exists())

    def test_successor_namespace_is_protected_from_direct_file_tools(self):
        root, cycle, _seat = self._archived()
        from saipen_engine.admission import evaluate_admission

        decision = evaluate_admission(root, self._successor(cycle), action="write", agent="probe")
        self.assertFalse(decision.get("admitted"), decision)
        self.assertEqual(decision.get("code"), "PROTECTED_CANONICAL_NAMESPACE", decision)

    def test_producer_cannot_write_successor_canonical_evidence(self):
        _root, cycle, _seat = self._archived()
        from saipen_engine.capability import guard_core_mutation

        blocked, reason = guard_core_mutation(self._successor(cycle))
        self.assertTrue(blocked, reason)

    def test_forged_valid_hash_chain_without_native_writer_receipt_is_blocked(self):
        root, cycle, seat = self._archived()
        improve.write_sweep_entry(cycle, self._entry(seat))
        successor = self._successor(cycle)
        lines = successor.read_text(encoding="utf-8").splitlines()
        previous = json.loads(lines[-1])
        forged = dict(previous)
        forged["sequence"] += 1
        forged["previous"] = previous["sha256"]
        forged["operation_id"] = "retrospective-forged-operation"
        forged["record"] = dict(previous["record"], finding_ref="RUN-1/IMP-002")
        forged.pop("sha256")
        forged["sha256"] = hashlib.sha256(
            json.dumps(forged, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()
        successor.write_text(
            "\n".join(lines) + "\n" + json.dumps(forged, sort_keys=True) + "\n", encoding="utf-8"
        )
        result = improve.reconcile_cycle(cycle, dry_run=True)
        self.assertFalse(result.get("ok"), result)
        self.assertTrue(cf.cycle_liveness(root, cycle.name).get("blocked"))

    def _cli(self, root, *words, env=None):
        process = subprocess.run(
            [
                sys.executable,
                "-B",
                str(TOOLS / "saipen.py"),
                "--project-root",
                str(root),
                "--agent",
                "probe",
                *words,
                "--json",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
            env=env,
        )
        self.assertTrue(process.stdout.strip(), process.stderr)
        return process.returncode, json.loads(process.stdout)

    def test_public_cli_sweep_reconcile_queue_and_repeated_continue(self):
        root, cycle, seat = self._archived()
        original = self._history(cycle)
        for number in (1, 2):
            code, result = self._cli(
                root,
                "improve",
                "sweep",
                cycle.name,
                f"RUN-1/IMP-{number:03d}",
                "INVALID",
                "--report",
                seat + "/saipen_improve_PROBE.md",
                "--reproduced",
                "n",
                "--verification",
                "proof.txt",
                "--retrospective",
            )
            self.assertEqual(code, 0, result)
            self.assertTrue(result.get("ok"), result)
        code, result = self._cli(root, "improve", "reconcile", cycle.name)
        self.assertEqual(code, 0, result)
        code, result = self._cli(root, "improve", "sweep-queue", cycle.name)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["queue"], [])
        self.assertEqual(result["precheck_errors"], [])
        successor = self._successor(cycle).read_bytes()
        for _ in range(2):
            code, result = self._cli(root, "continue", "--dry-run")
            self.assertEqual(code, 0, result)
            self.assertFalse(
                any(
                    item["cycle_id"] == cycle.name
                    for item in result.get("improve_stale_cycles", [])
                ),
                result,
            )
            self.assertEqual(self._successor(cycle).read_bytes(), successor)
        self.assertEqual(self._history(cycle), original)

    def test_retrospective_cli_dry_run_validates_without_creating_a_record(self):
        root, cycle, seat = self._archived()
        code, result = self._cli(
            root,
            "improve",
            "sweep",
            cycle.name,
            "RUN-1/IMP-001",
            "INVALID",
            "--report",
            seat + "/saipen_improve_PROBE.md",
            "--reproduced",
            "n",
            "--verification",
            "proof.txt",
            "--retrospective",
            "--dry-run",
        )
        self.assertEqual(code, 0, result)
        self.assertFalse(self._successor(cycle).exists())

    def test_fresh_process_crash_after_verified_rolls_forward(self):
        root, cycle, seat = self._archived()
        original = self._history(cycle)
        environment = dict(os.environ, NITRO_CRASH_AFTER_VERIFIED="1")
        process = subprocess.run(
            [
                sys.executable,
                "-B",
                str(TOOLS / "saipen.py"),
                "--project-root",
                str(root),
                "--agent",
                "probe",
                "improve",
                "sweep",
                cycle.name,
                "RUN-1/IMP-001",
                "INVALID",
                "--report",
                seat + "/saipen_improve_PROBE.md",
                "--reproduced",
                "n",
                "--verification",
                "proof.txt",
                "--retrospective",
                "--json",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
            env=environment,
        )
        self.assertEqual(process.returncode, 87, process.stdout + process.stderr)
        self.assertTrue(self._successor(cycle).exists())
        self.assertTrue(cf.cycle_liveness(root, cycle.name).get("blocked"))
        from saipen_engine.journal import auto_recover_pending

        self.assertTrue(auto_recover_pending(root).get("ok"))
        live = cf.cycle_liveness(root, cycle.name)
        self.assertFalse(live.get("blocked"), live)
        self.assertEqual(len(live["pending_findings"]), 1)
        self.assertEqual(self._history(cycle), original)

    def test_stale_disposition_plan_cannot_overwrite_an_intervening_commit(self):
        root, cycle, seat = self._archived()
        original_writer = improve._journaled_write
        interleaved = False

        def writer(*args, **kwargs):
            nonlocal interleaved
            if not interleaved and len(args) > 2 and args[2] == "retrospective":
                interleaved = True
                with mock.patch.object(improve, "_journaled_write", original_writer):
                    improve.write_sweep_entry(cycle, self._entry(seat, 2))
            return original_writer(*args, **kwargs)

        with mock.patch.object(
            improve, "_journaled_write", side_effect=writer
        ), self.assertRaisesRegex(improve.ImproveError, "STALE_STATE"):
            improve.write_sweep_entry(cycle, self._entry(seat, 1))
        live = cf.cycle_liveness(root, cycle.name)
        self.assertEqual(
            [item["finding_ref"] for item in live["pending_findings"]], ["RUN-1/IMP-001"]
        )
        self._all_dispositions(cycle, seat)

    def test_compacted_native_receipts_still_prove_the_successor(self):
        root, cycle, seat = self._archived()
        improve.write_sweep_entry(cycle, self._entry(seat))
        from saipen_engine.journal import compact_committed

        result = compact_committed(root)
        self.assertTrue(result.get("ok"), result)
        self.assertFalse(cf.cycle_liveness(root, cycle.name).get("blocked"))
        self.assertTrue(improve.write_sweep_entry(cycle, self._entry(seat, 2)).get("ok"))

    def test_pending_external_decision_can_advance_only_by_append_only_correction(self):
        root, cycle, seat = self._archived(findings=1)
        improve.write_sweep_entry(
            cycle, self._entry(seat, disposition="NEEDS_EXTERNAL_EVIDENCE", verification="-")
        )
        before = self._successor(cycle).read_bytes()
        with self.assertRaises(improve.ImproveError):
            improve.write_sweep_entry(cycle, self._entry(seat))
        self.assertTrue(improve.write_sweep_entry(cycle, self._entry(seat, amend=True)).get("ok"))
        self.assertTrue(self._successor(cycle).read_bytes().startswith(before))
        self.assertTrue(improve.reconcile_cycle(cycle).get("ok"))
        self.assertFalse(cf.cycle_liveness(root, cycle.name)["stale"])

    def test_archived_draft_cannot_mint_current_confirmed_authority(self):
        _root, cycle, seat = self._archived()
        with self.assertRaisesRegex(improve.ImproveError, "CONFIRMED|current"):
            improve.write_sweep_entry(
                cycle,
                self._entry(
                    seat, disposition="CONFIRMED", ticket=self._work_ticket, reproduced="y"
                ),
            )
        self.assertFalse(self._successor(cycle).exists())

    def test_older_kernel_policy_registry_refuses_new_successor_receipts(self):
        root, cycle, seat = self._archived()
        improve.write_sweep_entry(cycle, self._entry(seat))
        from saipen_engine import journal

        before = self._successor(cycle).read_bytes()
        old_policies = journal.VERIFICATION_POLICIES - {journal.RETROSPECTIVE_POLICY}
        with mock.patch.object(journal, "VERIFICATION_POLICIES", old_policies):
            live = cf.cycle_liveness(root, cycle.name)
            self.assertTrue(live.get("blocked"), live)
            self.assertFalse(live["stale"], live)
        self.assertEqual(self._successor(cycle).read_bytes(), before)

    def test_blocked_retirement_does_not_hide_findings_or_prevent_later_coverage(self):
        root, cycle, seat = self._archived()
        original = self._history(cycle)
        retired = improve.retire_seat(cycle, seat, "BLOCKED_EXTERNAL", retrospective=True)
        self.assertTrue(retired.get("ok"), retired)
        self.assertTrue(cf.cycle_liveness(root, cycle.name).get("blocked"))
        self._all_dispositions(cycle, seat)
        result = improve.reconcile_cycle(cycle)
        self.assertTrue(result.get("ok"), result)
        self.assertEqual(result["outcome"], "BLOCKED_EXTERNAL")
        self.assertEqual(cf.cycle_liveness(root, cycle.name)["pending_findings"], [])
        self.assertFalse(cf.cycle_liveness(root, cycle.name)["stale"])
        self.assertEqual(self._history(cycle), original)


if __name__ == "__main__":
    unittest.main()
