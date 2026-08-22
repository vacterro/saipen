"""Regressions for the 2026-08-21 Second-Wave and Performance audit.

The audit arrived after the Core wave.  These tests use hostile persisted
evidence and direct I/O instrumentation so the accepted findings cannot be
"fixed" by changing prose or by teaching a fixture to accept the old bug.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(TOOLS))

import saipen as CLI  # noqa: E402
import freshness  # noqa: E402
from saipen_engine import conformance as C  # noqa: E402
from saipen_engine import context as CTX  # noqa: E402
from saipen_engine import crew  # noqa: E402
from saipen_engine import fast_check  # noqa: E402
from saipen_engine import intent  # noqa: E402
from saipen_engine import journal  # noqa: E402
from saipen_engine import operations  # noqa: E402
from saipen_engine import producer as P  # noqa: E402
from saipen_engine import release  # noqa: E402
from saipen_engine import state as S  # noqa: E402
from saipen_engine import subs  # noqa: E402
from saipen_engine.plan import Result  # noqa: E402


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _project() -> Path:
    root = Path(tempfile.mkdtemp(prefix="saipen-external-audit-"))
    fixture = ROOT / "tests/scenarios/done-wait-deadlock-goal-mode/.saipen"
    shutil.copytree(fixture, root / ".saipen")
    # Scenario runs may leave untracked runtime receipts beside the immutable
    # fixture.  This test owns a fresh evidence namespace explicitly.
    shutil.rmtree(root / ".saipen/recovery", ignore_errors=True)
    state_path = root / ".saipen/STATE.md"
    state_path.write_text(
        S.patch_state(
            state_path.read_text(encoding="utf-8"),
            {"saipen_home": str(ROOT.resolve())},
        ),
        encoding="utf-8",
        newline="\n",
    )
    return root


def _cli(root: Path, command: str) -> tuple[int, dict]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rc = CLI.main([command, "--project-root", str(root), "--json"])
    return rc, json.loads(output.getvalue())


def _operation_record(op_id: str) -> dict:
    return {
        "op_id": op_id,
        "operation": "probe",
        "created_at": "2026-01-01T00:00:00Z",
        "agent": "probe",
        "project_identity": "probe-project",
        "project_lineage": None,
        "semantic_payload_hash": "h",
        "preconditions": {},
        "read_preconditions": {},
        "verification_policy": "none",
        "status": "COMMITTED",
        "progress_index": 1,
        "targets": [
            {
                "path": "x.txt",
                "role": "generic",
                "action": "write",
                "before_hash": "a",
                "after_hash": "b",
                "applied": True,
            }
        ],
    }


class ExternalAudit20260821(unittest.TestCase):
    def add_project(self) -> Path:
        root = _project()
        self.addCleanup(shutil.rmtree, root, True)
        return root

    def test_quality_corrupt_journal_is_one_fail_closed_public_class(self):
        root = self.add_project()
        recovery = root / ".saipen" / "recovery"
        recovery.write_text("not a directory\n", encoding="utf-8")
        before = _tree_hash(root)

        for projection in (CTX.context_cold, CTX.context_hot, CTX.context_audit):
            result = projection(root)
            self.assertFalse(result.ok, projection.__name__)
            self.assertEqual(result.code, "CORRUPT_JOURNAL", projection.__name__)
            self.assertIn("OPS_DIR", result.message, projection.__name__)

        with self.assertRaises(release.ReleaseRefusal) as raised:
            release._recovery_preflight(root)
        self.assertEqual(raised.exception.code, "CORRUPT_JOURNAL")
        self.assertIn("OPS_DIR", raised.exception.detail)
        self.assertEqual(_tree_hash(root), before, "read-only corrupt refusals wrote bytes")

    def test_quality_block_parked_done_binds_latest_phase_event_and_ticket(self):
        state = {"phase": "DONE", "transition_from": "BUILD", "last_event": 10}
        board = {"tickets": {"T-1": {"section": "## BLOCKED"}}}
        canonical = {
            "event": 9,
            "ticket": "T-1",
            "taxonomy": "DEC",
            "op_id": "ticket-probe",
            "text": "ticket block via SAIOPS (active) -- reason",
        }
        unrelated_tail = {
            "event": 10,
            "ticket": "T-2",
            "taxonomy": "RUN",
            "op_id": "transition-probe",
            "text": "transition to BUILD",
        }
        error = fast_check.block_parked_evidence_error(
            state, board, (canonical, unrelated_tail)
        )
        self.assertIsNotNone(error)
        self.assertIn("invalid phase transition", error)

        exact = {**canonical, "event": 10}
        self.assertIsNone(fast_check.block_parked_evidence_error(state, board, (exact,)))

        neutral_tail = {
            "event": 10,
            "ticket": None,
            "taxonomy": "RUN",
            "op_id": "checkpoint-probe",
            "text": "verification checkpoint",
        }
        self.assertIsNone(
            fast_check.block_parked_evidence_error(
                state, board, (canonical, neutral_tail)
            )
        )

    def test_w2_001_corrupt_newer_fail_never_resurrects_pass(self):
        root = self.add_project()
        C.generate_conformance_receipt(root, gate="core", exit_code=0)
        C.generate_conformance_receipt(root, gate="core", exit_code=1)
        receipts = sorted((root / C.RECEIPT_DIRNAME).glob("*.json"))
        self.assertEqual(len(receipts), 2)
        newest = max(
            receipts,
            key=lambda path: json.loads(path.read_text(encoding="utf-8"))["timestamp_utc"],
        )
        self.assertEqual(json.loads(newest.read_text(encoding="utf-8"))["verdict"], "FAIL")
        newest.write_text("{broken", encoding="utf-8")

        status = C.conformance_status(root, "core")
        self.assertEqual(status["status"], C.STATUS_INVALID)
        self.assertNotEqual(status["status"], C.STATUS_CURRENT_PASS)
        rc, projection = _cli(root, "status")
        self.assertEqual(rc, 0, projection)
        self.assertIn("conformance_status", projection)
        self.assertEqual(projection["conformance_status"]["status"], C.STATUS_INVALID)

    def test_w2_001_schema_version_decoder_is_total(self):
        bad_values = [None, True, False, -1, 0, 3, "2", 2.0, [], {}]
        for value in bad_values:
            with self.subTest(value=value):
                root = self.add_project()
                out = root / C.RECEIPT_DIRNAME
                out.mkdir(parents=True, exist_ok=True)
                candidate = {"kind": "conformance_receipt", "gate": "core"}
                if value is not None:
                    candidate["schema_version"] = value
                (out / "hostile.json").write_text(json.dumps(candidate), encoding="utf-8")
                result = C.conformance_status(root, "core")
                self.assertEqual(result["status"], C.STATUS_INVALID, result)

    def test_w2_002_live_generation_requires_newer_takeover_before_cleanup(self):
        root = self.add_project()
        ns = P.producer_namespace(root, "saitranslate")
        current = P.ProducerEpoch.claim(ns)
        generation = P.StagingGeneration(ns, "saitranslate", "live-generation").begin()
        generation.add_payload("payload.txt", b"partial")

        first = P.StagingGeneration.recover(ns)
        self.assertEqual(first["removed_staging"], [])
        self.assertTrue(generation.staging_dir.is_dir())
        self.assertEqual(P.ProducerEpoch.current(ns), current)

        takeover = P.ProducerEpoch.claim(ns)
        self.assertEqual(takeover, current + 1)
        second = P.StagingGeneration.recover(ns)
        self.assertEqual(second["removed_staging"], [generation.generation_id])
        self.assertFalse(generation.staging_dir.exists())

    def test_w2_003_epoch_decoder_rejects_rollback_and_coercion_zero_namespace_write(self):
        bad_values = [-1, True, False, "1", 1.0, None, [], {}]
        for value in bad_values:
            with self.subTest(value=value):
                root = self.add_project()
                ns = P.producer_namespace(root, "saitranslate")
                ns.mkdir(parents=True, exist_ok=True)
                epoch_path = ns / P.EPOCH_FILENAME
                epoch_path.write_text(
                    json.dumps({"epoch": value, "owner": "owner", "claimed_at": "stamp"}),
                    encoding="utf-8",
                )
                before = _tree_hash(ns)
                with self.assertRaises(P.ProducerError):
                    P.ProducerEpoch.current(ns)
                with self.assertRaises(P.ProducerError):
                    P.ProducerEpoch.claim(ns)
                with self.assertRaises(P.ProducerError):
                    P.StagingGeneration(ns, "saitranslate", "must-not-exist").begin()
                self.assertEqual(_tree_hash(ns), before)

    def test_w2_004_invalid_core_state_blocks_prepare_before_first_write(self):
        root = self.add_project()
        (root / ".saipen/STATE.md").write_text("---\nphase: [broken\n", encoding="utf-8")
        before = _tree_hash(root)
        result = intent.ensure_producer_ready(root, "saiwiki", current_capability="full")
        self.assertEqual(result["code"], "VALIDATION_FAILED", result)
        self.assertEqual(_tree_hash(root), before)
        self.assertFalse((root / ".saipen/extensions/subs/saiwiki").exists())

    def test_w2_004_dead_home_and_malformed_identity_are_zero_write(self):
        root = self.add_project()
        state_path = root / ".saipen/STATE.md"
        state_path.write_text(
            S.patch_state(
                state_path.read_text(encoding="utf-8"),
                {"saipen_home": str(root / "missing-home")},
            ),
            encoding="utf-8",
        )
        before = _tree_hash(root)
        result = intent.ensure_producer_ready(root, "saiwiki", current_capability="full")
        self.assertEqual(result["code"], "HOME_REQUIRED", result)
        self.assertEqual(_tree_hash(root), before)

        root = self.add_project()
        (root / ".saipen/IDENTITY.md").write_text("not canonical\n", encoding="utf-8")
        before = _tree_hash(root)
        result = intent.ensure_producer_ready(root, "saiwiki", current_capability="full")
        self.assertEqual(result["code"], "VALIDATION_FAILED", result)
        self.assertEqual(_tree_hash(root), before)

    def test_w2_005_all_read_routes_share_active_checkpoint_encoding_law(self):
        encoders = {
            "utf8-bom": lambda text: b"\xef\xbb\xbf" + text.encode("utf-8"),
            "utf16-le": lambda text: b"\xff\xfe" + text.encode("utf-16-le"),
            "utf16-be": lambda text: b"\xfe\xff" + text.encode("utf-16-be"),
        }
        for name in ("STATE.md", "BOARD.md", "LOG.md"):
            for encoding, encode in encoders.items():
                with self.subTest(file=name, encoding=encoding):
                    root = self.add_project()
                    path = root / ".saipen" / name
                    text = path.read_text(encoding="utf-8")
                    path.write_bytes(encode(text))
                    before = _tree_hash(root)

                    for command in ("status", "next"):
                        rc, payload = _cli(root, command)
                        self.assertNotEqual(rc, 0, (command, payload))
                        self.assertEqual(payload["code"], "VALIDATION_FAILED")
                    for projection in (
                        CTX.context_cold(root),
                        CTX.context_hot(root),
                        CTX.context_audit(root),
                    ):
                        self.assertFalse(projection.ok, projection)
                        self.assertEqual(projection.code, "VALIDATION_FAILED")
                    mutation = operations.set_goal_intent(root, "test", "must not write")
                    self.assertFalse(mutation.ok, mutation)
                    self.assertEqual(mutation.code, "VALIDATION_FAILED")
                    self.assertEqual(_tree_hash(root), before)

    def test_perf_001_snapshot_ignores_100mb_scratch_but_binds_relevant_inputs(self):
        root = self.add_project()
        scratch = root / ".saipen/extensions/subs/saipython/kitchen/pen/irrelevant.bin"
        scratch.parent.mkdir(parents=True, exist_ok=True)
        with scratch.open("wb") as handle:
            handle.truncate(100 * 1024 * 1024)

        real_read = Path.read_bytes
        scratch_reads = 0

        def counting_read(path: Path):
            nonlocal scratch_reads
            if path == scratch:
                scratch_reads += 1
            return real_read(path)

        with mock.patch.object(Path, "read_bytes", counting_read):
            snapshot = crew.crew_snapshot(root, current_capability="full")
        self.assertEqual(scratch_reads, 0)
        self.assertTrue(
            snapshot.input_hashes[".saipen/extensions/subs"].startswith(
                journal.DIRECTORY_LISTING_PREFIX
            )
        )

        specs = crew._root_dependency_specs(root)
        before = crew._capture_dependencies(specs)
        board = root / ".saipen/BOARD.md"
        board.write_text(board.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        after = crew._capture_dependencies(specs)
        self.assertNotEqual(before[".saipen/BOARD.md"], after[".saipen/BOARD.md"])

        shared = root / ".saipen/extensions/subs"
        listing_before = after[".saipen/extensions/subs"]
        (shared / "sainew.md").write_text("new charter\n", encoding="utf-8")
        listing_after = crew._capture_dependencies(specs)[".saipen/extensions/subs"]
        self.assertNotEqual(listing_before, listing_after)

    def test_memory_source_identity_failure_never_falls_back_to_whole_tree(self):
        root = self.add_project()
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                mock.patch.object(
                    freshness,
                    "compute_source_identity",
                    side_effect=freshness.FreshnessError("unstable source"),
                )
            )
            stack.enter_context(
                mock.patch.object(
                    Path,
                    "rglob",
                    side_effect=AssertionError("whole-tree fallback must not run"),
                )
            )
            stack.enter_context(
                self.assertRaisesRegex(P.ProducerError, "authoritative source identity")
            )
            P._live_source_identity(root)

    def test_perf_002_crew_apply_reuses_one_planning_snapshot(self):
        root = self.add_project()
        # Ensure on-disk STATE already has converge crew intent so crew_apply
        # doesn't take the intent-setting branch before reaching snapshot.
        from saipen_engine import state as S2

        _sp = root / ".saipen/STATE.md"
        _sp.write_text(
            S2.transition_execution_intent(
                _sp.read_text(encoding="utf-8"), "converge", converge_target="crew"
            ),
            encoding="utf-8",
        )
        # Re-apply saipen_home which transition may have preserved but ensure it is set to ROOT
        _sp.write_text(
            S2.patch_state(_sp.read_text(encoding="utf-8"), {"saipen_home": str(ROOT.resolve())}),
            encoding="utf-8",
        )
        fake = SimpleNamespace(
            root=root,
            state={"execution_intent": "converge", "converge_target": "crew"},
            saipen_home=str(ROOT),
            home_problem=None,
            epoch=SimpleNamespace(op_id="epoch-1"),
        )
        plan = {"action": {"action": "FINALIZE"}, "crew_complete": False}
        final = Result(ok=True, code="FINALIZED")
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                mock.patch("saipen_engine.fast_check.validate_project", return_value=[])
            )
            stack.enter_context(mock.patch.object(crew, "pending_ops", return_value=[]))
            capture = stack.enter_context(
                mock.patch.object(crew, "crew_snapshot", return_value=fake)
            )
            stack.enter_context(
                mock.patch.object(crew, "_crew_plan_from_snapshot", return_value=plan)
            )
            finalize = stack.enter_context(
                mock.patch.object(crew, "_finalize_crew_from_snapshot", return_value=final)
            )
            result = crew.crew_apply(root, current_capability="full", current_agent="test")
        self.assertTrue(result.ok, result)
        capture.assert_called_once()
        finalize.assert_called_once_with(fake, current_agent="test")

    def test_perf_002_autonomous_final_and_defer_use_planning_snapshot(self):
        root = self.add_project()
        fake = SimpleNamespace(epoch=SimpleNamespace(op_id="epoch-1"))
        final = Result(ok=True, code="FINALIZED")
        with mock.patch.object(crew, "_finalize_crew_from_snapshot", return_value=final) as call:
            got = intent._execute_crew_action(
                root,
                "FINALIZE",
                None,
                "full",
                "test",
                str(ROOT),
                planning_snapshot=fake,
            )
        self.assertTrue(got.ok)
        call.assert_called_once_with(fake, current_agent="test")

        with contextlib.ExitStack() as stack:
            defer = stack.enter_context(
                mock.patch("saipen_engine.operations.defer_for_crew", return_value=final)
            )
            stack.enter_context(
                mock.patch.object(
                    crew, "crew_snapshot", side_effect=AssertionError("unexpected recapture")
                )
            )
            got = intent._execute_crew_action(
                root,
                "DEFER_FOR_CREW",
                None,
                "full",
                "test",
                str(ROOT),
                action_inputs=("T-1",),
                planning_snapshot=fake,
            )
        self.assertTrue(got.ok)
        defer.assert_called_once_with(root, "T-1", "test", "epoch-1", dry_run=False)

    def test_perf_003_semantic_snapshot_reads_each_manifest_once(self):
        root = self.add_project()
        ops = root / journal.OPS_DIR
        for index in range(7):
            op_dir = ops / f"probe-{index}"
            op_dir.mkdir(parents=True, exist_ok=True)
            (op_dir / "operation.json").write_text(
                json.dumps(_operation_record(op_dir.name)), encoding="utf-8"
            )
            if index == 0:
                (op_dir / "progress.json").write_text(
                    json.dumps({"status": "COMMITTED", "progress_index": 1}),
                    encoding="utf-8",
                )
        real_read = Path.read_bytes
        reads = {"operation.json": 0, "progress.json": 0}

        def counting_read(path: Path):
            if path.name in reads and root in path.parents:
                reads[path.name] += 1
            return real_read(path)

        with mock.patch.object(Path, "read_bytes", counting_read):
            snapshot = journal.semantic_receipt_snapshot(root)
            initial_reads = dict(reads)
            closing = journal.semantic_receipt_digest(root)
        self.assertEqual(snapshot.errors, ())
        self.assertEqual(initial_reads, {"operation.json": 7, "progress.json": 1})
        self.assertEqual(reads, {"operation.json": 14, "progress.json": 2})
        self.assertEqual(snapshot.digest, closing)

    def test_quality_progress_sidecar_is_bound_into_semantic_cas(self):
        root = self.add_project()
        op_dir = root / journal.SETTLED_DIR / "progress-race"
        op_dir.mkdir(parents=True, exist_ok=True)
        (op_dir / "operation.json").write_text(
            json.dumps(_operation_record(op_dir.name)), encoding="utf-8"
        )
        before = journal.semantic_receipt_snapshot(root)
        self.assertEqual(before.errors, ())

        (op_dir / "progress.json").write_text(
            json.dumps({"status": "ABORTED", "progress_index": 0}),
            encoding="utf-8",
        )
        after = journal.semantic_receipt_snapshot(root)
        closing = journal.semantic_receipt_digest(root)

        self.assertEqual(after.errors, ())
        self.assertNotEqual(before.digest, after.digest)
        self.assertEqual(after.digest, closing)
        self.assertEqual(after.records[0]["status"], "ABORTED")

    def test_perf_003_closing_digest_detects_corrupt_membership_race(self):
        root = self.add_project()
        before = journal.semantic_receipt_digest(root)
        orphan = root / journal.OPS_DIR / "orphan-no-manifest"
        orphan.mkdir(parents=True)

        after = journal.semantic_receipt_digest(root)
        snapshot = journal.semantic_receipt_snapshot(root)
        self.assertNotEqual(before, after)
        self.assertEqual(after, snapshot.digest)
        self.assertIn("orphan-no-manifest", snapshot.corrupt_op_ids)
        self.assertTrue(
            any("no operation.json" in error for error in snapshot.errors),
            snapshot.errors,
        )

    def test_quality_compaction_refuses_unsafe_queue_before_writes(self):
        root = self.add_project()
        ops_entry = root / journal.OPS_DIR / "compact-zero-write"
        ops_entry.mkdir(parents=True, exist_ok=True)
        (ops_entry / "operation.json").write_text(
            json.dumps(_operation_record(ops_entry.name)), encoding="utf-8"
        )
        queue = root / journal.CLEANUP_QUEUE_DIR
        queue.parent.mkdir(parents=True, exist_ok=True)
        queue.write_text("not a directory\n", encoding="utf-8")

        result = journal.compact_committed(root)

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "CORRUPT_JOURNAL")
        self.assertTrue(ops_entry.exists(), result)

    def test_quality_compaction_never_follows_settled_symlink(self):
        root = self.add_project()
        settled = root / journal.SETTLED_DIR
        settled.parent.mkdir(parents=True, exist_ok=True)
        outside = Path(tempfile.mkdtemp(prefix="saipen-compaction-outside-"))
        self.addCleanup(shutil.rmtree, outside, True)
        entry = outside / "outside-op"
        entry.mkdir()
        (entry / "operation.json").write_text(
            json.dumps(_operation_record(entry.name)), encoding="utf-8"
        )
        staged = entry / "secret.staged"
        staged.write_text("must survive\n", encoding="utf-8")
        marker_dir = outside / ".cleanup-needed"
        marker_dir.mkdir()
        (marker_dir / entry.name).write_text("", encoding="utf-8")
        try:
            os.symlink(outside, settled, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlink unavailable: {exc}")

        result = journal.compact_committed(root)

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "CORRUPT_JOURNAL")
        self.assertEqual(staged.read_text(encoding="utf-8"), "must survive\n")
        self.assertTrue((marker_dir / entry.name).exists())

    # ── 2026-08-22 live-session regressions: targeted collect deadlock ─────
    # Reproduced on the real project: `sub collect saihunt` failed post-write
    # verification because verify_sub_collect iterated ALL manifest entries and
    # saipython/saitest/saiui carried stale `last_collect` markers whose
    # identities were absent from Core BOARD/LOG. A TARGETED intake must not
    # fail over an unrelated producer's stale evidence.

    def _collect_fixture(self):
        root = self.add_project()
        subs = root / ".saipen" / "extensions" / "subs"
        target_dir = subs / "target"
        other_dir = subs / "other"
        target_dir.mkdir(parents=True)
        other_dir.mkdir(parents=True)
        (target_dir / "kitchen").mkdir()
        (other_dir / "kitchen").mkdir()
        identity_a = "sha256:" + "a" * 64
        identity_b = "sha256:" + "b" * 64
        (subs / "MANIFEST.md").write_text(
            "# SubSaipen Manifest\n\n"
            f"- target -- .saipen/extensions/subs/target/ | last_collect: {identity_a}@2026-01-01T00:00:00Z\n"
            f"- other -- .saipen/extensions/subs/other/ | last_collect: {identity_b}@2026-01-01T00:00:00Z\n",
            encoding="utf-8",
        )
        target_outbox = target_dir / "kitchen" / "OUTBOX.md"
        target_outbox.write_text(
            "# OUTBOX\n\n"
            "## TARGET-1: probe\n"
            "- **status:** ready\n"
            "- **summary:** probe\n"
            "- **main_project_refs:** []\n"
            "- **critical:** false\n"
            "- **severity:** P3\n"
            "- **producer:** target\n"
            "- **source_head:** 00aa12db9f01c55cb76c3e2a6e6ba35c33a4135c\n"
            "- **source_tree_fingerprint:** git-delta-v1:ccb6e0f9a721e7c2129e14998c54f1d2cd703605adb61d9e70311bd126857d43\n"
            "- **role_revision:** sha256:4edb04181cb07e0946afd06fbe711166fa9dcc403e56b52e9be3844f0a71b0a5\n"
            "- **coverage:** probe\n"
            "- **payload:** []\n"
            "- **verified:** PASS -- probe\n"
            "- **instructions:** None.\n"
            "- **details:** probe\n",
            encoding="utf-8",
        )
        other_outbox = other_dir / "kitchen" / "OUTBOX.md"
        other_outbox.write_text(
            "# OUTBOX\n\n"
            "## OTHER-1: probe\n"
            "- **status:** ready\n"
            "- **summary:** probe\n"
            "- **main_project_refs:** []\n"
            "- **critical:** false\n"
            "- **severity:** P3\n"
            "- **producer:** other\n"
            "- **source_head:** 00aa12db9f01c55cb76c3e2a6e6ba35c33a4135c\n"
            "- **source_tree_fingerprint:** git-delta-v1:ccb6e0f9a721e7c2129e14998c54f1d2cd703605adb61d9e70311bd126857d43\n"
            "- **role_revision:** sha256:4edb04181cb07e0946afd06fbe711166fa9dcc403e56b52e9be3844f0a71b0a5\n"
            "- **coverage:** probe\n"
            "- **payload:** []\n"
            "- **verified:** PASS -- probe\n"
            "- **instructions:** None.\n"
            "- **details:** probe\n",
            encoding="utf-8",
        )
        return root, target_outbox

    def test_verify_sub_collect_is_target_scoped(self):
        root, _ = self._collect_fixture()
        targets = [
            {"path": ".saipen/LOG.md", "role": "log", "action": "write"},
            {"path": ".saipen/BOARD.md", "role": "board", "action": "write"},
            {"path": ".saipen/extensions/subs/MANIFEST.md", "role": "manifest", "action": "write"},
        ]
        # The `other` producer's last_collect identity is absent from Core
        # BOARD/LOG. A TARGETED collect of `target` must not surface it, while
        # the target producer's OWN stale marker still fails closed (the
        # targeted scope validates the collected producer itself).
        errors = journal.verify_sub_collect(
            root,
            targets,
            {"producers": ["target"], "package_identities": ["x"], "tickets": ["T-1"]},
        )
        joined = " ".join(errors)
        self.assertNotIn("other:", joined, errors)
        self.assertIn("target:", joined, errors)
        # Legacy metadata without producers keeps the full-manifest scope: the
        # unrelated stale marker must surface (fail-closed for old receipts).
        legacy = journal.verify_sub_collect(root, targets, None)
        self.assertTrue(any("other:" in e for e in legacy), legacy)

    def test_manifest_marker_alone_is_not_collect_witness(self):
        root, _ = self._collect_fixture()
        identity_a = "sha256:" + "a" * 64
        # Marker present, NO durable sub_collect receipt -> NOT a witness.
        self.assertFalse(
            subs._durable_collect_witness(root, identity_a + "@2026-01-01T00:00:00Z", identity_a)
        )
        # With a COMMITTED sub_collect receipt binding the identity -> witness.
        op_dir = root / journal.SETTLED_DIR / "sub-collect-witness"
        op_dir.mkdir(parents=True)
        record = _operation_record("sub-collect-witness")
        record["operation"] = "sub_collect"
        record["status"] = "COMMITTED"
        record["receipt_metadata"] = {
            "operation": "sub_collect",
            "status": "COMMITTED",
            "package_identities": [identity_a],
            "producers": ["target"],
            "tickets": ["T-1"],
        }
        (op_dir / "operation.json").write_text(json.dumps(record), encoding="utf-8")
        self.assertTrue(
            subs._durable_collect_witness(root, identity_a + "@2026-01-01T00:00:00Z", identity_a)
        )
        # A RESOLVED/accept_live collect with every target applied is durable.
        op_dir2 = root / journal.SETTLED_DIR / "sub-collect-witness2"
        op_dir2.mkdir(parents=True)
        record2 = _operation_record("sub-collect-witness2")
        record2["operation"] = "sub_collect"
        record2["status"] = "RESOLVED"
        record2["resolution"] = "accept_live"
        record2["resolution_applied_targets"] = ["x.txt"]
        record2["resolution_skipped_targets"] = []
        record2["targets"] = [
            {
                "path": "x.txt",
                "role": "generic",
                "action": "write",
                "before_hash": "a",
                "after_hash": "b",
                "applied": True,
            }
        ]
        record2["receipt_metadata"] = {
            "operation": "sub_collect",
            "status": "COMMITTED",
            "package_identities": [identity_a],
            "producers": ["target"],
            "tickets": ["T-1"],
        }
        (op_dir2 / "operation.json").write_text(json.dumps(record2), encoding="utf-8")
        self.assertTrue(
            subs._durable_collect_witness(root, identity_a + "@2026-01-01T00:00:00Z", identity_a)
        )

    def test_collect_refuses_semantic_receipt_corruption_zero_write(self):
        # CORE-002 (audit fdc73e06): a malformed unrelated settled receipt must
        # NOT collapse a valid committed collection witness into "no evidence"
        # and silently permit a duplicate Core review ticket. sub_collect must
        # refuse CORRUPT_JOURNAL with zero writes when the semantic receipt
        # snapshot is corrupt.
        root, _ = self._collect_fixture()
        identity_a = "sha256:" + "a" * 64
        op_dir = root / journal.SETTLED_DIR / "sub-collect-corrupt"
        op_dir.mkdir(parents=True)
        record = _operation_record("sub-collect-corrupt")
        record["operation"] = "sub_collect"
        record["status"] = "COMMITTED"
        record["receipt_metadata"] = {
            "operation": "sub_collect",
            "status": "COMMITTED",
            "package_identities": [identity_a],
            "producers": ["target"],
            "tickets": ["T-1"],
        }
        (op_dir / "operation.json").write_text(json.dumps(record), encoding="utf-8")
        # Add an unrelated malformed settled receipt in the same namespace.
        bad_dir = root / journal.SETTLED_DIR / "unrelated-corrupt"
        bad_dir.mkdir(parents=True)
        (bad_dir / "operation.json").write_text("{broken", encoding="utf-8")
        board_before = (root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        before = _tree_hash(root)
        result = subs.sub_collect(root, "target", dry_run=False)
        self.assertEqual(result.code, "CORRUPT_JOURNAL", result)
        self.assertEqual(_tree_hash(root), before, "corrupt refusal wrote bytes")
        self.assertEqual((root / ".saipen" / "BOARD.md").read_text(encoding="utf-8"), board_before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
