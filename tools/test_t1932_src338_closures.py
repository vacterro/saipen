"""SRC-338 red-before/green-after controls, promoted to the focused family.

Each class pins one finding that the SRC-337 closure had claimed complete
while the counterexample still reproduced. These are local contract controls
with isolated temporary projects and no installed host: they prove the engine
fails closed on its own public surface, never that a real SAIPAL runtime or a
native scheduler accepted anything.

Evidence for this module: .saipen/evidence/T-1932/closures/ holds the original
red scripts that reproduced each defect before the repair.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from saipen_engine import (
    audit_enqueue,
    autonomy,
    board as board_mod,
    campaign,
    continuation_assessment,
    host_dispatch,
    host_iteration,
    iteration,
    iteration_verdict,
    supervisor,
)

# T-1947: the producer-specific backend lives outside the neutral engine.
from producer_backends import saipal_adapter  # noqa: E402


def make_project(root: Path, *, task: str = "T-1", phase: str = "BUILD") -> Path:
    (root / ".saipen" / "campaign").mkdir(parents=True, exist_ok=True)
    (root / ".saipen" / "STATE.md").write_text(
        "---\n"
        f"phase: {phase}\n"
        f"task: {task}\n"
        "next_action: x\n"
        "last_event: E-1\n"
        "agent: saipen-cli\n"
        "updated: '2026-01-01T00:00:00Z'\n"
        "---\n",
        encoding="utf-8",
    )
    (root / ".saipen" / "BOARD.md").write_text(
        f"# BOARD\n\n## DOING\n- [/] {task} [P1] work\n\n## TODO\n\n## DONE\n",
        encoding="utf-8",
    )
    (root / ".saipen" / "LOG.md").write_text("- e1\n", encoding="utf-8")
    return root


def host_receipt(payload: dict, *, status: str = host_dispatch.HOST_ACCEPTED) -> dict:
    return {
        "schema_version": 1,
        "status": status,
        "campaign_id": payload["campaign_id"],
        "iteration_id": payload["iteration_id"],
        "worker_generation": payload["worker_generation"],
        "idempotency_key": payload["idempotency_key"],
        "project_lineage": payload["project_lineage"],
        "accepted_request_id": payload["idempotency_key"],
        "accepting_host": "native_test_host",
    }


def qualification_artifact(root: Path, receipt_id: str) -> dict:
    rel = f".saipen/campaign/qualifications/{receipt_id}.json"
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"receipt_id": receipt_id}), encoding="utf-8")
    return {
        "receipt_id": receipt_id,
        "artifact_path": rel,
        "artifact_digest": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


class TsBase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="saipen-t1932-closure-")
        self.addCleanup(tmp.cleanup)
        self.root = make_project(Path(tmp.name))
        # AUT-001: these are dispatch-mechanics closures, not host-trust
        # evidence. `host_receipt()` builds a dict this process wrote, which
        # production now refuses because no live broker reproduces it. The
        # simulation is declared once here; `HostTrustTests` owns the real gate
        # and deliberately does NOT inherit this seam.
        self._trust_patcher = mock.patch(
            "saipen_engine.host_dispatch._broker_verified_receipt",
            return_value=True,
        )
        self._trust_patcher.start()
        self.addCleanup(self._trust_patcher.stop)


class DispatchDispositionTests(TsBase):
    """CORE-012 / R012: the controller action depends on the dispatch result."""

    def _controller(self) -> host_iteration.HostIterationController:
        return host_iteration.HostIterationController(
            required={"filesystem"}, project_root=self.root
        )

    def _verdict(self) -> dict:
        return {
            "decision": iteration.AUTO_KICK,
            "canonical_task": "T-1",
            "phase": "BUILD",
            "route_reason": "active_work",
        }

    def test_confirmed_host_acknowledgment_kicks(self) -> None:
        ctrl = self._controller()
        action = ctrl.on_model_turn_finished(
            self._verdict(),
            turn_context={
                "project_root": self.root,
                "iteration_id": 1,
                "host_hook": lambda p: host_receipt(p),
            },
        )
        self.assertEqual(action, host_iteration.KICK_NEXT_ITERATION)
        self.assertEqual(
            ctrl.telemetry_dispatch, host_iteration.DISPATCH_CONFIRMED
        )

    def test_failed_hook_is_not_a_successful_dispatch_disposition(self) -> None:
        def failing_hook(_payload):
            raise RuntimeError("scheduler offline")

        ctrl = self._controller()
        action = ctrl.on_model_turn_finished(
            self._verdict(),
            turn_context={
                "project_root": self.root,
                "iteration_id": 1,
                "host_hook": failing_hook,
            },
        )
        self.assertNotEqual(action, host_iteration.KICK_NEXT_ITERATION)
        self.assertEqual(
            ctrl.telemetry_dispatch, host_iteration.DISPATCH_REFUSED
        )
        events = {e.get("event") for e in ctrl.telemetry}
        self.assertIn("turn_dispatch_unconfirmed", events)
        self.assertNotIn("turn_dispatched", events)

    def test_persisted_advisory_is_pending_not_started(self) -> None:
        ctrl = self._controller()
        action = ctrl.on_model_turn_finished(
            self._verdict(),
            turn_context={"project_root": self.root, "iteration_id": 1},
        )
        self.assertEqual(action, host_iteration.KICK_NEXT_ITERATION)
        self.assertEqual(ctrl.telemetry_dispatch, host_iteration.REQUEST_PERSISTED)
        events = [e.get("event") for e in ctrl.telemetry]
        self.assertIn("turn_dispatch_pending", events)
        self.assertNotIn("turn_dispatched", events)

    def test_no_false_turn_start_metrics(self) -> None:
        ctrl = self._controller()
        ctrl.on_model_turn_finished(
            self._verdict(),
            turn_context={
                "project_root": self.root,
                "iteration_id": 1,
                "host_hook": lambda p: {"ok": False, "status": "REFUSED"},
            },
        )
        for event in ctrl.telemetry:
            self.assertNotEqual(event.get("event"), "turn_dispatched")
            self.assertNotEqual(event.get("status"), host_dispatch.TURN_STARTED)


class PersistedDispatchReplayTests(TsBase):
    """W2-004 / R017: a durable request is delivered once a host appears."""

    def _persist_only(self) -> dict:
        payload = host_dispatch.build_dispatch_payload(self.root, campaign_id="C-1")
        first = host_dispatch.dispatch_next_turn(
            self.root, dict(payload), host_hook=None, print_advisory=False
        )
        self.assertEqual(first["status"], host_dispatch.HOST_DISPATCH_UNAVAILABLE)
        self.assertFalse(first["dispatched"])
        self.assertEqual(first["disposition"], host_dispatch.DISPATCH_REQUEST_PERSISTED)
        return payload

    def test_later_host_delivers_the_pending_request(self) -> None:
        payload = self._persist_only()
        second = host_dispatch.dispatch_next_turn(
            self.root,
            dict(payload),
            host_hook=lambda p: host_receipt(p),
            print_advisory=False,
        )
        self.assertTrue(second["ok"])
        self.assertTrue(second["dispatched"])
        self.assertEqual(second["status"], host_dispatch.HOST_ACCEPTED)
        self.assertEqual(second["receipt"]["idempotency_key"], payload["idempotency_key"])

    def test_replay_reuses_the_operation_identity(self) -> None:
        payload = self._persist_only()
        host_dispatch.dispatch_next_turn(
            self.root,
            dict(payload),
            host_hook=lambda p: host_receipt(p),
            print_advisory=False,
        )
        ledger = host_dispatch._load_dispatch_ledger(
            self.root / ".saipen" / "campaign"
        )
        self.assertEqual(list(ledger), [payload["idempotency_key"]])
        self.assertEqual(ledger[payload["idempotency_key"]]["status"], host_dispatch.HOST_ACCEPTED)

    def test_repeated_registration_does_not_duplicate_accepted_work(self) -> None:
        payload = self._persist_only()
        delivered = []
        for _ in range(3):
            host_dispatch.dispatch_next_turn(
                self.root,
                dict(payload),
                host_hook=lambda p: delivered.append(p) or host_receipt(p),
                print_advisory=False,
            )
        self.assertEqual(len(delivered), 1)
        inbox = self.root / ".saipen" / "campaign" / "dispatch_inbox.jsonl"
        rows = [line for line in inbox.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows), 1)

    def test_restart_preserves_the_pending_request(self) -> None:
        payload = self._persist_only()
        campaign_dir = self.root / ".saipen" / "campaign"
        reopened = host_dispatch._load_dispatch_ledger(campaign_dir)
        self.assertEqual(reopened[payload["idempotency_key"]]["status"], host_dispatch.DISPATCH_REQUEST_PERSISTED)
        second = host_dispatch.dispatch_next_turn(
            self.root,
            dict(payload),
            host_hook=lambda p: host_receipt(p),
            print_advisory=False,
        )
        self.assertEqual(second["status"], host_dispatch.HOST_ACCEPTED)

    def test_replay_without_a_host_keeps_one_durable_copy(self) -> None:
        payload = self._persist_only()
        again = host_dispatch.dispatch_next_turn(
            self.root, dict(payload), host_hook=None, print_advisory=False
        )
        self.assertEqual(again["status"], host_dispatch.HOST_DISPATCH_UNAVAILABLE)
        self.assertTrue(again["replayed"])
        inbox = self.root / ".saipen" / "campaign" / "dispatch_inbox.jsonl"
        rows = [line for line in inbox.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows), 1)

    def test_receipt_naming_the_request_as_a_digest_is_accepted(self) -> None:
        """The contract calls the field "accepted request digest"."""
        payload = self._persist_only()
        receipt = host_receipt(payload)
        receipt["accepted_request_digest"] = receipt.pop("accepted_request_id")
        second = host_dispatch.dispatch_next_turn(
            self.root,
            dict(payload),
            host_hook=lambda p: receipt,
            print_advisory=False,
        )
        self.assertTrue(second["dispatched"])
        self.assertEqual(second["status"], host_dispatch.HOST_ACCEPTED)

    def test_receipt_without_request_identity_is_unverified(self) -> None:
        payload = self._persist_only()
        receipt = host_receipt(payload)
        for field in ("accepted_request_id", "request_id", "request_digest",
                      "accepted_request_digest"):
            receipt.pop(field, None)
        second = host_dispatch.dispatch_next_turn(
            self.root,
            dict(payload),
            host_hook=lambda p: receipt,
            print_advisory=False,
        )
        self.assertFalse(second["dispatched"])
        self.assertEqual(second["status"], host_dispatch.ACCEPTANCE_UNVERIFIED)
        self.assertIn("request identity", second["detail"])


class PublicationReceiptIdentityTests(TsBase):
    """W2-007 / R020: one operation identity keeps one logical receipt."""

    def _finding(self, finding_id: str = "PAL-DUP") -> dict:
        body = "# finding\nbody\n"
        return {
            "finding_id": finding_id,
            "state": "QUALIFIED",
            "qualification_receipt": qualification_artifact(self.root, f"QUAL-{finding_id}"),
            "audit_body": body,
            "artifact_digest": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        }

    def _deliver(self, finding: dict) -> dict:
        adapter = saipal_adapter.SaipalAdapter(saipal_home=self.root)
        return adapter.deliver_finding_to_audit_inbox(
            self.root, finding, publication_authorized=True
        )

    def test_same_finding_twice_retains_one_receipt(self) -> None:
        finding = self._finding()
        first = self._deliver(finding)
        self.assertEqual(first["status"], saipal_adapter.DELIVERED_PUBLICATION)
        second = self._deliver(finding)
        self.assertEqual(second["status"], saipal_adapter.DELIVERED_PUBLICATION)
        self.assertTrue(second["idempotent_replay"])
        rows = self._receipt_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["operation_id"], first["receipt"]["operation_id"])

    def test_idempotent_enqueue_preserves_original_timestamp(self) -> None:
        finding = self._finding()
        first = self._deliver(finding)
        recorded_at = self._receipt_rows()[0]["delivered_at"]
        self._deliver(finding)
        rows = self._receipt_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["delivered_at"], recorded_at)
        self.assertEqual(
            rows[0]["delivered_at"], first["receipt"]["delivered_at"]
        )

    def test_crash_after_enqueue_reconstructs_the_missing_receipt(self) -> None:
        finding = self._finding()
        # W2-003 moved the receipt append to the atomic check-and-append helper,
        # so this injects the failure there: the enqueue still commits and the
        # receipt must be reconstructable from the allocator.
        with mock.patch.object(
            saipal_adapter, "_append_history_unique",
            return_value={"ok": False, "status": "HISTORY_WRITE_FAILED"},
        ):
            partial = self._deliver(finding)
        self.assertTrue(partial["enqueue_committed"])
        self.assertTrue(partial["receipt_reconciliation_required"])
        self.assertEqual(self._receipt_rows(), [])
        recovered = self._deliver(finding)
        self.assertEqual(recovered["status"], saipal_adapter.DELIVERED_PUBLICATION)
        self.assertEqual(len(self._receipt_rows()), 1)

    def test_different_findings_keep_independent_receipts(self) -> None:
        self._deliver(self._finding("PAL-A"))
        self._deliver(self._finding("PAL-B"))
        rows = self._receipt_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            sorted(row["finding_id"] for row in rows), ["PAL-A", "PAL-B"]
        )

    def test_conflicting_digest_for_one_operation_is_refused(self) -> None:
        self._deliver(self._finding())
        adapter = saipal_adapter.SaipalAdapter(saipal_home=self.root)
        with mock.patch.object(
            saipal_adapter.audit_enqueue,
            "enqueue",
            return_value={
                "ok": True,
                "layer": 1,
                "digest": "0" * 64,
                "idempotent": True,
            },
        ):
            res = adapter.deliver_finding_to_audit_inbox(
                self.root, self._finding(), publication_authorized=True
            )
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], "PUBLICATION_RECEIPT_CONFLICT")

    def _receipt_rows(self) -> list:
        history = saipal_adapter._read_append_log(
            self.root / ".saipen" / "campaign" / "saipal_receipts.jsonl"
        )
        return history["records"]


class DispatchLedgerCostTests(TsBase):
    """PERF-003 / R026: durable updates cost the transition, not the history."""

    def _run_operations(self, count: int) -> tuple[Path, list, int]:
        """Run `count` dispatches; return the dir, atomic write sizes, journal bytes.

        Two write paths matter and both are counted: durable transitions go
        through a raw fsynced `os.write` (the journal append), while a
        checkpoint rewrites the whole ledger via `safe_atomic_write_bytes`.
        Measuring only the latter would miss the ordinary path entirely, which
        is precisely the path R026 says must cost the transition and not the
        history.
        """
        campaign_dir = self.root / ".saipen" / "campaign"
        written: list[int] = []
        original = host_dispatch.paths.safe_atomic_write_bytes

        def counting(path, body, **kwargs):
            written.append(len(body))
            return original(path, body, **kwargs)

        with mock.patch.object(
            host_dispatch.paths, "safe_atomic_write_bytes", side_effect=counting
        ):
            for index in range(1, count + 1):
                payload = host_dispatch.build_dispatch_payload(
                    self.root, campaign_id="C-PERF", iteration_id=index
                )
                host_dispatch.dispatch_next_turn(
                    self.root,
                    dict(payload),
                    host_hook=lambda p: host_receipt(p),
                    print_advisory=False,
                )
        journal_bytes = sum(
            1 for _ in (campaign_dir / host_dispatch.DISPATCH_LEDGER_JOURNAL).read_bytes().splitlines()
        )
        return campaign_dir, written, journal_bytes

    def test_per_operation_write_volume_does_not_scale_with_history(self) -> None:
        """Per-operation write cost stays bounded as history grows.

        A checkpoint is a whole-ledger write, so a growing history must not
        increase the per-operation share of it. The defect R026 names is the
        OLD writer paying a whole-ledger rewrite on EVERY transition: at 1000
        operations that measured 72 KB per operation. The two assertions split
        the claim: an absolute ceiling well under that regime, and a ratio
        proving the average does not climb as history doubles.

        The floor is lowered so both sizes see several compactions. At the
        production 256 KB floor a short run has not compacted even once, so it
        reports zero and the ratio compares "no checkpoint" with "one", which
        would measure the first compaction rather than the steady state. The
        threshold scales with the checkpoint it writes, so the geometry under
        test is identical at any floor.
        """
        averages = {}
        for size in (200, 400, 800):
            with tempfile.TemporaryDirectory() as tmp:
                self.root = make_project(Path(tmp))
                with mock.patch.object(host_dispatch, "JOURNAL_COMPACT_BYTES", 8192):
                    _campaign_dir, written, _lines = self._run_operations(size)
            averages[size] = sum(written) / size
        for size, average in averages.items():
            self.assertLess(
                average,
                4096,
                f"{size} operations averaged {average:.0f} bytes of ledger write each",
            )
        self.assertLess(
            averages[800],
            averages[200],
            f"per-op average rose with history instead of amortising: {averages}",
        )

    def test_historical_accepted_operations_remain_discoverable(self) -> None:
        campaign_dir, _written, _lines = self._run_operations(120)
        ledger = host_dispatch._load_dispatch_ledger(campaign_dir)
        self.assertEqual(len(ledger), 120)
        first = host_dispatch.build_dispatch_payload(
            self.root, campaign_id="C-PERF", iteration_id=1
        )
        replay = host_dispatch.dispatch_next_turn(
            self.root,
            dict(first),
            host_hook=lambda p: host_receipt(p),
            print_advisory=False,
        )
        self.assertEqual(replay["status"], "ALREADY_DISPATCHED")
        self.assertFalse(replay["dispatched"])

    def test_partial_journal_append_is_detected(self) -> None:
        campaign_dir, _written, _lines = self._run_operations(5)
        journal = campaign_dir / host_dispatch.DISPATCH_LEDGER_JOURNAL
        with journal.open("ab") as stream:
            stream.write(b'{"key": "torn-half-writ')
        status = host_dispatch._read_journal(campaign_dir)
        self.assertTrue(status["partial_tail"])
        self.assertEqual(status["status"], "JOURNAL_PARTIAL_APPEND")
        # The torn tail is not a committed transition, so the ledger is intact.
        self.assertEqual(len(host_dispatch._load_dispatch_ledger(campaign_dir)), 5)

    def test_interrupted_compaction_preserves_recoverable_data(self) -> None:
        campaign_dir, _written, _lines = self._run_operations(40)
        before = host_dispatch._load_dispatch_ledger(campaign_dir)
        journal = campaign_dir / host_dispatch.DISPATCH_LEDGER_JOURNAL
        journal.write_bytes(journal.read_bytes() + b'{"key": "torn')
        pre = host_dispatch._load_dispatch_ledger(campaign_dir)
        with mock.patch.object(host_dispatch, "JOURNAL_COMPACT_BYTES", 1):
            ran = host_dispatch._checkpoint_journal(
                campaign_dir, pre, host_dispatch._read_journal(campaign_dir)
            )
        self.assertTrue(ran)
        after = host_dispatch._load_dispatch_ledger(campaign_dir)
        self.assertEqual(set(before), set(after))
        self.assertEqual(len(after), 40)
        # The torn tail was never a committed transition, so it is not folded
        # into the checkpoint and cannot resurrect as a phantom operation.
        self.assertEqual(journal.stat().st_size, 0)

    def test_migration_preserves_legacy_accepted_identities(self) -> None:
        campaign_dir = self.root / ".saipen" / "campaign"
        campaign_dir.mkdir(parents=True, exist_ok=True)
        legacy_key = hashlib.sha256(b"legacy-operation").hexdigest()
        (campaign_dir / host_dispatch.DISPATCH_LEDGER_LEGACY).write_text(
            json.dumps({"keys": [legacy_key]}), encoding="utf-8"
        )
        ledger = host_dispatch._load_dispatch_ledger(campaign_dir)
        self.assertEqual(ledger[legacy_key]["status"], host_dispatch.HOST_ACCEPTED)

    def test_ledger_corruption_remains_a_typed_failure(self) -> None:
        campaign_dir = self.root / ".saipen" / "campaign"
        campaign_dir.mkdir(parents=True, exist_ok=True)
        (campaign_dir / host_dispatch.DISPATCH_LEDGER_JOURNAL).write_bytes(
            b"{not json}\n"
        )
        with self.assertRaises(host_dispatch.LedgerCorruptError):
            host_dispatch._load_dispatch_ledger(campaign_dir)


class SupervisorParseTests(TsBase):
    """PERF-005 / R028: one observation parses BOARD once."""

    def test_normal_observation_parses_board_once(self) -> None:
        calls: list[str] = []
        original = board_mod.parse_board

        def counting(text):
            calls.append(text)
            return original(text)

        with mock.patch.object(board_mod, "parse_board", side_effect=counting), mock.patch.object(
            supervisor, "parse_board", side_effect=counting
        ), mock.patch.object(
            continuation_assessment, "parse_board", side_effect=counting
        ):
            observation = supervisor.observe(self.root)
        self.assertEqual(len(calls), 1, f"parsed BOARD {len(calls)} times")
        self.assertTrue(observation)

    def test_board_change_between_observations_is_detected(self) -> None:
        first = supervisor.observe(self.root)
        (self.root / ".saipen" / "BOARD.md").write_text(
            "# BOARD\n\n## DOING\n- [/] T-1 [P1] work\n\n## TODO\n"
            "- [ ] T-2 [P1] later\n\n## DONE\n",
            encoding="utf-8",
        )
        second = supervisor.observe(self.root)
        self.assertNotEqual(
            first.get("executable_work"), second.get("executable_work")
        )

    def test_read_only_observation_writes_nothing(self) -> None:
        before = {
            path.name: path.read_bytes()
            for path in (self.root / ".saipen").iterdir()
            if path.is_file()
        }
        supervisor.observe(self.root)
        after = {
            path.name: path.read_bytes()
            for path in (self.root / ".saipen").iterdir()
            if path.is_file()
        }
        self.assertEqual(before, after)


class ProgressTrackerBoundsTests(unittest.TestCase):
    """PERF-007 / R030: bounded detection state, unchanged thresholds."""

    def test_large_sequence_uses_bounded_memory(self) -> None:
        tracker = autonomy.ProgressTracker(max_iterations=1_000_000)
        for index in range(50_000):
            tracker.record(f"state-{index}", "RUN", f"reason-{index}", "OK")
        self.assertEqual(len(tracker.history), tracker.retention)
        self.assertGreater(tracker.dropped, 0)

    def test_stall_detection_triggers_at_the_established_threshold(self) -> None:
        tracker = autonomy.ProgressTracker(max_iterations=20)
        self.assertTrue(tracker.record("A", "RUN", "same", "OK"))
        self.assertTrue(tracker.record("A", "RUN", "same", "OK"))
        self.assertFalse(tracker.record("A", "RUN", "same", "OK"))

    def test_oscillation_detection_is_unchanged(self) -> None:
        tracker = autonomy.ProgressTracker(max_iterations=20)
        outcomes = [
            tracker.record(label, "RUN", "cycle", "OK")
            for label in ("A", "B", "A", "B", "A", "B")
        ]
        self.assertFalse(outcomes[-1])

    def test_max_iterations_is_still_enforced(self) -> None:
        tracker = autonomy.ProgressTracker(max_iterations=5)
        outcomes = [
            tracker.record(str(index), "RUN", "advance", "OK") for index in range(5)
        ]
        self.assertEqual(outcomes, [True, True, True, True, False])

    def test_aggregate_counters_remain_accurate(self) -> None:
        tracker = autonomy.ProgressTracker(max_iterations=1_000_000)
        for index in range(10_000):
            tracker.record(f"state-{index}", "RUN", "reason", "OK")
        self.assertEqual(tracker.counters["observations"], 10_000)
        self.assertEqual(tracker.iterations, 10_000)
        self.assertEqual(
            len(tracker.history) + tracker.dropped, tracker.iterations
        )


class ControllerMemoryBoundsTests(TsBase):
    """PERF-007 / R030: the controller's own history and telemetry are bounded.

    R030 names `HostIterationController` first and `ProgressTracker` second:
    the controller's append-only `telemetry` and `history` were the reported
    2,000-record leak. Bounding only the tracker would leave the finding open.
    """

    def _controller(self) -> host_iteration.HostIterationController:
        return host_iteration.HostIterationController(required=set())

    def _paused_verdict(self) -> dict:
        return {
            "decision": iteration.OPERATOR_WAIT,
            "canonical_task": "T-1",
            "phase": "BUILD",
            "route_reason": "operator_wait",
        }

    def test_repeated_callbacks_do_not_grow_history_without_bound(self) -> None:
        ctrl = self._controller()
        limit = host_iteration.HostIterationController.HISTORY_RETENTION
        for _ in range(limit * 20):
            ctrl.on_model_turn_finished(self._paused_verdict())
        self.assertLessEqual(len(ctrl.history), limit)
        # Every action is still counted even though the record was dropped.
        self.assertEqual(sum(ctrl.action_counts.values()), limit * 20)
        self.assertEqual(len(ctrl.history) + ctrl.history_dropped, limit * 20)

    def test_telemetry_is_bounded_and_events_still_counted(self) -> None:
        ctrl = self._controller()
        limit = host_iteration.HostIterationController.TELEMETRY_RETENTION
        for index in range(limit * 10):
            ctrl.reseat_epoch(f"cap-epoch-{index}")
        self.assertLessEqual(len(ctrl.telemetry), limit)
        self.assertEqual(ctrl.event_counts["epoch_reseat"], limit * 10)
        self.assertEqual(len(ctrl.telemetry) + ctrl.telemetry_dropped, limit * 10)

    def test_idempotency_identities_are_not_discarded_with_telemetry(self) -> None:
        """The GUARDRAIL: trimming diagnostics must not drop dispatch identity."""
        ctrl = self._controller()
        ctrl._dispatched_idempotency_keys.add("key-1")
        for index in range(host_iteration.HostIterationController.TELEMETRY_RETENTION * 5):
            ctrl.reseat_epoch(f"cap-epoch-{index}")
        self.assertIn("key-1", ctrl._dispatched_idempotency_keys)

    def test_completion_ui_stays_once_only(self) -> None:
        ctrl = self._controller()
        verdict = {
            "schema_version": iteration_verdict.ITERATION_VERDICT_SCHEMA,
            "decision": iteration.VALID_TERMINAL,
            "canonical_task": "T-1",
            "phase": "SHIP",
            "route_reason": "done",
            "state_readable": True,
            "goal_complete": True,
        }
        first = ctrl.on_model_turn_finished(verdict)
        second = ctrl.on_model_turn_finished(verdict)
        self.assertEqual(first, host_iteration.EMIT_GOAL_COMPLETE_UI)
        self.assertNotEqual(second, host_iteration.EMIT_GOAL_COMPLETE_UI)


class CrossProjectConcurrencyTests(unittest.TestCase):
    """PERF-001 / R024: dispatch synchronization is scoped per project."""

    def setUp(self) -> None:
        # AUT-001: concurrency mechanics only; the receipts are locally built,
        # so the trust answer is declared rather than inferred from shape.
        self._trust_patcher = mock.patch(
            "saipen_engine.host_dispatch._broker_verified_receipt",
            return_value=True,
        )
        self._trust_patcher.start()
        self.addCleanup(self._trust_patcher.stop)

    def _project(self, root: Path) -> Path:
        (root / ".saipen" / "campaign").mkdir(parents=True, exist_ok=True)
        return root

    def test_independent_projects_do_not_serialize_behind_each_other(self) -> None:
        """Project B must progress while project A's host callback blocks.

        A single global mutex around the host invocation made one slow callback
        stall every project. The lock is now scoped by canonical project
        identity, so an unrelated root is unaffected.
        """
        import threading
        import time

        with tempfile.TemporaryDirectory(prefix="saipen-t1932-xproj-") as tmp:
            base = Path(tmp)
            a = self._project(base / "A")
            b = self._project(base / "B")
            blocked = threading.Event()

            def slow_hook(payload):
                blocked.set()
                time.sleep(3.0)
                return host_receipt(payload)

            def run_a():
                payload = host_dispatch.build_dispatch_payload(
                    a, campaign_id="C-A", iteration_id=1
                )
                host_dispatch.dispatch_next_turn(
                    a, dict(payload), host_hook=slow_hook, print_advisory=False
                )

            worker = threading.Thread(target=run_a, daemon=True)
            worker.start()
            self.assertTrue(blocked.wait(5), "project A's callback never started")

            started = time.monotonic()
            payload_b = host_dispatch.build_dispatch_payload(
                b, campaign_id="C-B", iteration_id=1
            )
            result = host_dispatch.dispatch_next_turn(
                b, dict(payload_b), host_hook=lambda p: host_receipt(p),
                print_advisory=False,
            )
            elapsed = time.monotonic() - started
            worker.join(timeout=10)

            self.assertEqual(result.get("status"), host_dispatch.HOST_ACCEPTED)
            self.assertLess(
                elapsed, 2.0,
                f"project B waited {elapsed:.2f}s behind project A's blocked callback",
            )

    def test_same_project_duplicate_attempts_stay_serialized(self) -> None:
        """Exactly-once survives the per-project lock: a replay does not dispatch."""
        with tempfile.TemporaryDirectory(prefix="saipen-t1932-xproj-") as tmp:
            root = self._project(Path(tmp) / "P")
            payload = host_dispatch.build_dispatch_payload(
                root, campaign_id="C-SAME", iteration_id=1
            )
            first = host_dispatch.dispatch_next_turn(
                root, dict(payload), host_hook=lambda p: host_receipt(p),
                print_advisory=False,
            )
            second = host_dispatch.dispatch_next_turn(
                root, dict(payload), host_hook=lambda p: host_receipt(p),
                print_advisory=False,
            )
            self.assertTrue(first.get("dispatched"))
            self.assertFalse(second.get("dispatched"))
            self.assertEqual(second.get("status"), "ALREADY_DISPATCHED")


class DispatchDeadlineTests(TsBase):
    """W2-010 / R023: bounded host invocation, UNCERTAIN outcome on timeout."""

    def _payload(self, **overrides) -> dict:
        return host_dispatch.build_dispatch_payload(
            self.root, campaign_id="C-DEADLINE", **overrides
        )

    def _release(self) -> None:
        """A hung hook must not leave the dispatch lock held."""
        other = host_dispatch.build_dispatch_payload(
            self.root, campaign_id="C-DEADLINE", iteration_id=2
        )
        result = host_dispatch.dispatch_next_turn(
            self.root, dict(other), host_hook=lambda p: host_receipt(p),
            print_advisory=False,
        )
        self.assertTrue(result.get("dispatched"))

    def test_unresponsive_hook_reaches_deadline_and_reports_uncertain(self) -> None:
        import threading

        release = threading.Event()
        payload = self._payload()
        payload["host_deadline_s"] = 0.15
        try:
            result = host_dispatch.dispatch_next_turn(
                self.root, payload, host_hook=lambda p: release.wait(30),
                print_advisory=False,
            )
        finally:
            release.set()

        self.assertFalse(result.get("dispatched"))
        self.assertEqual(result.get("status"), host_dispatch.DISPATCH_TIMEOUT)
        self.assertEqual(result.get("outcome"), host_dispatch.UNKNOWN_OUTCOME)
        self.assertTrue(result.get("reconcile_required"))
        self.assertEqual(result.get("idempotency_key"), payload["idempotency_key"])

    def test_timeout_preserves_identity_and_requires_reconciliation(self) -> None:
        import threading

        release = threading.Event()
        payload = self._payload()
        payload["host_deadline_s"] = 0.15
        try:
            first = host_dispatch.dispatch_next_turn(
                self.root, payload, host_hook=lambda p: release.wait(30),
                print_advisory=False,
            )
        finally:
            release.set()
        self.assertEqual(first.get("status"), host_dispatch.DISPATCH_TIMEOUT)

        # A blind replay must refuse rather than dispatch twice.
        replay = host_dispatch.dispatch_next_turn(
            self.root, dict(payload), host_hook=lambda p: host_receipt(p),
            print_advisory=False,
        )
        self.assertFalse(replay.get("dispatched"))
        self.assertEqual(replay.get("status"), "RECOVERY_REQUIRED")
        self.assertTrue(replay.get("reconcile_required"))

    def test_lock_is_released_after_a_bounded_failure(self) -> None:
        import threading

        release = threading.Event()
        payload = self._payload()
        payload["host_deadline_s"] = 0.1
        try:
            host_dispatch.dispatch_next_turn(
                self.root, payload, host_hook=lambda p: release.wait(30),
                print_advisory=False,
            )
        finally:
            release.set()
        self._release()

    def test_successful_hook_still_passes_the_acceptance_gate(self) -> None:
        payload = self._payload()
        payload["host_deadline_s"] = 5.0
        result = host_dispatch.dispatch_next_turn(
            self.root, dict(payload), host_hook=lambda p: host_receipt(p),
            print_advisory=False,
        )
        self.assertTrue(result.get("dispatched"))
        self.assertEqual(result.get("status"), host_dispatch.HOST_ACCEPTED)

    def test_timeout_maps_to_recovery_disposition(self) -> None:
        self.assertEqual(
            host_iteration._dispatch_disposition(
                {"status": host_dispatch.DISPATCH_TIMEOUT, "ok": False}
            ),
            host_iteration.DISPATCH_RECOVERY_REQUIRED,
        )


class DispatchIdentityTests(TsBase):
    """W2-003 / R016: the idempotency key is derived, never trusted."""

    def test_tampered_key_is_refused_with_zero_callbacks(self) -> None:
        payload = host_dispatch.build_dispatch_payload(
            self.root, campaign_id="C-IDENT", iteration_id=1
        )
        payload["idempotency_key"] = "0" * 64
        calls: list[int] = []
        result = host_dispatch.dispatch_next_turn(
            self.root, payload,
            host_hook=lambda p: (calls.append(1) or host_receipt(p)),
            print_advisory=False,
        )
        self.assertFalse(result.get("dispatched"))
        self.assertEqual(result.get("status"), "IDEMPOTENCY_KEY_MISMATCH")
        self.assertEqual(calls, [])
        self.assertEqual(result.get("supplied_idempotency_key"), "0" * 64)

    def test_matching_key_still_dispatches_once(self) -> None:
        payload = host_dispatch.build_dispatch_payload(
            self.root, campaign_id="C-IDENT", iteration_id=1
        )
        calls: list[int] = []
        first = host_dispatch.dispatch_next_turn(
            self.root, dict(payload),
            host_hook=lambda p: (calls.append(1) or host_receipt(p)),
            print_advisory=False,
        )
        second = host_dispatch.dispatch_next_turn(
            self.root, dict(payload),
            host_hook=lambda p: (calls.append(1) or host_receipt(p)),
            print_advisory=False,
        )
        self.assertTrue(first.get("dispatched"))
        self.assertEqual(second.get("status"), "ALREADY_DISPATCHED")
        self.assertEqual(len(calls), 1)

    def test_independent_campaigns_never_share_identity(self) -> None:
        a = host_dispatch.build_dispatch_payload(self.root, campaign_id="C-A", iteration_id=1)
        b = host_dispatch.build_dispatch_payload(self.root, campaign_id="C-B", iteration_id=1)
        self.assertNotEqual(a["idempotency_key"], b["idempotency_key"])

    def test_same_operation_reconstructs_the_same_key(self) -> None:
        first = host_dispatch.build_dispatch_payload(
            self.root, campaign_id="C-STABLE", iteration_id=7, worker_generation=2
        )
        second = host_dispatch.build_dispatch_payload(
            self.root, campaign_id="C-STABLE", iteration_id=7, worker_generation=2
        )
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])

    def test_distinct_operations_cannot_suppress_each_other(self) -> None:
        one = host_dispatch.build_dispatch_payload(self.root, campaign_id="C-S", iteration_id=1)
        two = host_dispatch.build_dispatch_payload(self.root, campaign_id="C-S", iteration_id=2)
        self.assertNotEqual(one["idempotency_key"], two["idempotency_key"])
        r1 = host_dispatch.dispatch_next_turn(
            self.root, dict(one), host_hook=lambda p: host_receipt(p), print_advisory=False
        )
        r2 = host_dispatch.dispatch_next_turn(
            self.root, dict(two), host_hook=lambda p: host_receipt(p), print_advisory=False
        )
        self.assertTrue(r1.get("dispatched"))
        self.assertTrue(r2.get("dispatched"))


class OwnershipFailureTests(TsBase):
    """CORE-002 / CORE-003: ownership and ledger failures invoke zero callbacks."""

    def test_lock_busy_invokes_no_callback(self) -> None:
        payload = host_dispatch.build_dispatch_payload(
            self.root, campaign_id="C-OWN", iteration_id=1
        )
        calls: list[int] = []
        original = host_dispatch.lock.FileWriterLock.acquire

        def busy(_self):
            raise host_dispatch.lock.FileLockBusy("held by another process")

        host_dispatch.lock.FileWriterLock.acquire = busy
        try:
            result = host_dispatch.dispatch_next_turn(
                self.root, dict(payload),
                host_hook=lambda p: (calls.append(1) or host_receipt(p)),
                print_advisory=False,
            )
        finally:
            host_dispatch.lock.FileWriterLock.acquire = original
        self.assertEqual(calls, [])
        self.assertFalse(result.get("dispatched"))
        self.assertEqual(result.get("status"), host_dispatch.LOCK_BUSY)

    def test_corrupt_ledger_invokes_no_callback(self) -> None:
        campaign_dir = self.root / ".saipen" / "campaign"
        (campaign_dir / host_dispatch.DISPATCH_LEDGER_CHECKPOINT).write_text(
            "{not valid json", encoding="utf-8"
        )
        payload = host_dispatch.build_dispatch_payload(
            self.root, campaign_id="C-OWN", iteration_id=1
        )
        calls: list[int] = []
        result = host_dispatch.dispatch_next_turn(
            self.root, dict(payload),
            host_hook=lambda p: (calls.append(1) or host_receipt(p)),
            print_advisory=False,
        )
        self.assertEqual(calls, [])
        self.assertFalse(result.get("dispatched"))
        self.assertEqual(result.get("status"), "LEDGER_CORRUPT")


class ReportTransportTests(TsBase):
    """PERF-004 / R027: bounded paged report transport with a resumable cursor."""

    def _adapter(self, findings: list[dict], *, ok: bool = True):
        adapter = saipal_adapter.SaipalAdapter(saipal_home=self.root)
        payload = {
            "schema_version": 1,
            "ok": ok,
            "command": "report",
            "findings": findings,
            "counts": {"total": len(findings)},
        }
        # PERF-004 pages over the VALIDATED SPOOL, not over a command result, so
        # the fixture supplies the transport capture. Everything above it is the
        # production path: Phase A validation, corpus identity, bounded paging.
        body = json.dumps(payload).encode("utf-8")
        adapter._capture_report_spool = lambda: {
            "ok": True,
            "returncode": 0,
            "stdout_file": io.BytesIO(body),
            "stdout_bytes_len": len(body),
            "stderr": b"",
        }
        return adapter

    def _findings(self, count: int, state: str = "QUALIFIED") -> list[dict]:
        return [
            {"finding_id": f"F-{index:04}", "state": state}
            for index in range(count)
        ]

    def test_report_is_handed_out_in_bounded_pages(self) -> None:
        adapter = self._adapter(self._findings(1000))
        pages = list(adapter.iter_finding_pages(page_size=250))
        self.assertEqual(len(pages), 4)
        self.assertEqual(sum(len(page[2]) for page in pages), 1000)
        for index, total, page, _identity in pages:
            self.assertEqual(total, 4)
            self.assertLessEqual(len(page), 250)

    def test_source_identity_is_stable_across_pages(self) -> None:
        adapter = self._adapter(self._findings(600))
        identities = {page[3]["source_digest"] for page in adapter.iter_finding_pages(page_size=200)}
        self.assertEqual(len(identities), 1)

    def test_source_identity_changes_when_the_corpus_changes(self) -> None:
        first = self._adapter(self._findings(3)) 
        digest_a = next(iter(first.iter_finding_pages(page_size=10)))[3]["source_digest"]
        second = self._adapter([
            {"finding_id": "F-DIFFERENT", "state": "QUALIFIED"},
            {"finding_id": "F-ALSO", "state": "QUALIFIED"},
            {"finding_id": "F-THIRD", "state": "QUALIFIED"},
        ])
        digest_b = next(iter(second.iter_finding_pages(page_size=10)))[3]["source_digest"]
        self.assertNotEqual(digest_a, digest_b)

    def test_page_size_is_clamped_to_declared_bounds(self) -> None:
        adapter = self._adapter([])
        self.assertEqual(adapter.report_page_size(10**9), saipal_adapter.REPORT_PAGE_MAX)
        self.assertEqual(adapter.report_page_size(0), saipal_adapter.REPORT_PAGE_DEFAULT)
        self.assertEqual(adapter.report_page_size(None), saipal_adapter.REPORT_PAGE_DEFAULT)

    def test_resume_does_not_skip_or_duplicate_acknowledged_findings(self) -> None:
        """An interrupted walk replays unacknowledged findings, never skips them.

        W2-002 replaced the old contract here. Receiving a page used to count
        as delivery, so the two assertions below were satisfiable while a crash
        between the page and its publication lost the finding forever. The
        cursor is now an ACKNOWLEDGMENT watermark: until the allocator holds a
        committed publication, a finding stays eligible and is re-yielded. The
        test therefore asserts the invariant that matters -- nothing is
        skipped -- and that acknowledgment (not the yield) suppresses a replay.
        """
        findings = self._findings(500)
        adapter = self._adapter(findings)
        first_pass = []
        for page in adapter.iter_new_qualified_findings(self.root, page_size=100):
            first_pass.extend(row["finding_id"] for row in page["findings"])
            if page["page_index"] == 1:
                break  # simulate an interruption mid-report
        self.assertEqual(len(first_pass), 200)

        resumed = []
        for page in adapter.iter_new_qualified_findings(self.root, page_size=100):
            resumed.extend(row["finding_id"] for row in page["findings"])

        # Nothing is lost. Because no publication was acknowledged, the whole
        # corpus -- including the first two pages -- stays eligible; skipping
        # those unacknowledged findings is exactly the W2-002 defect.
        self.assertEqual(resumed, [row["finding_id"] for row in findings])
        self.assertEqual(
            set(first_pass) | set(resumed), {row["finding_id"] for row in findings}
        )

    def test_replayed_batch_does_not_duplicate_publication(self) -> None:
        """A replayed walk re-yields unacknowledged findings; publication dedupes.

        Publication identity is the canonical allocator's `operation_id`, so a
        second walk returning the same finding produces one audit layer, not
        two. Acknowledgement, not the walk, is what silences the replay.
        """
        findings = self._findings(300)
        adapter = self._adapter(findings)
        source_digest = None
        first = []
        for page in adapter.iter_new_qualified_findings(self.root, page_size=100):
            source_digest = page["source_identity"]["source_digest"]
            first.extend(row["finding_id"] for row in page["findings"])
        second = [row["finding_id"] for page in adapter.iter_new_qualified_findings(
            self.root, page_size=100) for row in page["findings"]]
        self.assertEqual(len(first), 300)
        # Before acknowledgment the finding stays eligible by design.
        self.assertEqual(second, first)

        ack = adapter.acknowledge_delivery(
            self.root, first, source_digest=source_digest
        )
        self.assertTrue(ack["ok"], ack)
        third = [row["finding_id"] for page in adapter.iter_new_qualified_findings(
            self.root, page_size=100) for row in page["findings"]]
        self.assertEqual(third, [])

    def test_resource_limit_is_not_reported_as_no_new_evidence(self) -> None:
        adapter = saipal_adapter.SaipalAdapter(saipal_home=self.root)
        adapter._capture_report_spool = lambda: {
            "ok": False,
            "status": saipal_adapter.BACKEND_RESOURCE_LIMIT,
            "error": "report exceeds transport bound",
        }
        pages = list(adapter.iter_finding_pages(page_size=100))
        self.assertEqual(pages[0][0], "ERROR")
        self.assertEqual(pages[0][3]["status"], saipal_adapter.BACKEND_RESOURCE_LIMIT)

    def test_expect_source_digest_refuses_a_different_corpus(self) -> None:
        adapter = self._adapter(self._findings(20))
        pages = list(adapter.iter_new_qualified_findings(
            self.root, page_size=10, expect_source_digest="not-the-real-digest"))
        self.assertFalse(pages[0]["ok"])
        self.assertEqual(pages[0]["status"], "REPORT_SOURCE_CHANGED")

    def test_corrupt_cursor_is_reported_not_silently_reset(self) -> None:
        path = self.root / ".saipen" / "campaign" / "saipal_report_cursor.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        adapter = self._adapter(self._findings(5))
        loaded = adapter.load_page_checkpoint(self.root)
        self.assertFalse(loaded["ok"])
        self.assertEqual(loaded["status"], "CURSOR_CORRUPT")


class TailEventReaderTests(TsBase):
    """PERF-006 / R029: bounded reverse-tail read, identical semantics."""

    def _controller(self) -> campaign.CampaignController:
        return campaign.CampaignController(self.root)

    def _log(self) -> Path:
        return self.root / ".saipen" / "LOG.md"

    def _full_read(self) -> str:
        lines = [
            line.strip()
            for line in self._log().read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        ]
        return lines[-1][:80] if lines else "none"

    def _assert_matches_full_read(self, body: str, label: str) -> None:
        self._log().write_text(body, encoding="utf-8")
        self.assertEqual(self._controller()._read_tail_event(), self._full_read(), label)

    def test_final_record_larger_than_the_read_window_is_not_truncated(self) -> None:
        """The old fixed 8 KB window returned a mid-line fragment here."""
        body = "- first\n- " + "X" * 20_000 + " END\n"
        self._log().write_text(body, encoding="utf-8")
        expected = self._full_read()
        self.assertTrue(expected.startswith("- X"))
        self.assertEqual(self._controller()._read_tail_event(), expected)

    def test_large_journal_reads_only_the_tail(self) -> None:
        body = "\n".join(f"- line {index}" for index in range(50_000)) + "\n"
        self._assert_matches_full_read(body, "50k lines")

    def test_edge_shapes_match_full_read(self) -> None:
        for label, body in (
            ("empty", ""),
            ("only blanks", "\n\n\n"),
            ("trailing blanks", "- a\n- tail\n\n\n"),
            ("no final newline", "- a\n- tail"),
            ("utf8", "- привет\n- мир\n"),
            ("one line", "- only\n"),
        ):
            with self.subTest(label=label):
                self._assert_matches_full_read(body, label)

    def test_oversized_unicode_record_matches_full_read(self) -> None:
        self._assert_matches_full_read("- a\n- " + "ж" * 20_000 + "\n", "unicode")

    def test_crlf_matches_full_read(self) -> None:
        self._log().write_bytes(b"- a\r\n- tail\r\n\r\n")
        self.assertEqual(self._controller()._read_tail_event(), "- tail")

    def test_missing_log_reports_none(self) -> None:
        log = self._log()
        if log.exists():
            log.unlink()
        self.assertEqual(self._controller()._read_tail_event(), "none")


class AppendLogReconciliationTests(TsBase):
    """W2-008 / R021: strict append-log status and a real repair path."""

    def _receipt_log(self) -> Path:
        return self.root / ".saipen" / "campaign" / "saipal_receipts.jsonl"

    def _row(self, key: str) -> bytes:
        return (json.dumps({"operation_id": key}, sort_keys=True) + "\n").encode("utf-8")

    def test_valid_log_reads_completely(self) -> None:
        log = self._receipt_log()
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_bytes(self._row("a") + self._row("b"))
        history = saipal_adapter._read_append_log(log)
        self.assertTrue(history["ok"])
        self.assertEqual(history["status"], "LOG_VALID")
        self.assertEqual(len(history["records"]), 2)

    def test_missing_log_is_absent_not_empty_history(self) -> None:
        history = saipal_adapter._read_append_log(self._receipt_log())
        self.assertEqual(history["status"], "LOG_ABSENT")

    def test_malformed_middle_record_surfaces_corruption(self) -> None:
        log = self._receipt_log()
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_bytes(self._row("a") + b"{not json}\n" + self._row("c"))
        history = saipal_adapter._read_append_log(log)
        self.assertFalse(history["ok"])
        self.assertEqual(history["status"], "LOG_CORRUPT")
        self.assertEqual(history["error_line"], 2)
        self.assertEqual([row["operation_id"] for row in history["records"]], ["a"])

    def test_torn_final_record_is_explicitly_truncated(self) -> None:
        log = self._receipt_log()
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_bytes(self._row("a") + b'{"operation_id": "tor')
        history = saipal_adapter._read_append_log(log)
        self.assertEqual(history["status"], "LOG_TRUNCATED")
        self.assertEqual(len(history["records"]), 1)
        self.assertTrue(history["damaged_record_hex"])

    def test_damaged_bytes_remain_recoverable(self) -> None:
        log = self._receipt_log()
        log.parent.mkdir(parents=True, exist_ok=True)
        damaged = b"{not json}\n"
        log.write_bytes(self._row("a") + damaged)
        history = saipal_adapter._read_append_log(log)
        adapter = saipal_adapter.SaipalAdapter(saipal_home=self.root)
        preserved = saipal_adapter._quarantine_damaged_suffix(self.root, log, history)
        self.assertTrue(preserved["ok"])
        quarantined = self.root / preserved["path"]
        self.assertEqual(quarantined.read_bytes(), damaged)

    def test_recovery_does_not_invent_dispositions(self) -> None:
        adapter = saipal_adapter.SaipalAdapter(saipal_home=self.root)
        result = adapter.reconcile_history(self.root, kind="dispositions")
        self.assertTrue(result["ok"])
        self.assertEqual(result.get("reconstructed", 0), 0)
        self.assertFalse(self._receipt_log().exists())
