"""Decision B is an independently witnessed exact scope, never a reference's syntax."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import accepted_debt as debt, intake  # noqa: E402
from saipen_engine.journal import ensure_project_lineage  # noqa: E402
from test_accepted_debt import Fixture, REASON  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_operator_origin_support import native_operator, use_case_owner  # noqa: E402


def setUpModule():
    isolate_host_session()


def tree_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def legacy_record(root):
    evidence = [{"event": f"E-{event['event']}", "file": file, "line_number": line,
                 "line_sha256": debt._line_sha256(raw)}
                for file, line, raw, event in debt._iter_history(root) if event["event"] in (3, 4)]
    return {"schema_version": debt.SCHEMA_VERSION, "kind": "accepted_legacy_debt",
            "record_id": "AD-000001", "project_lineage": ensure_project_lineage(root),
            "project_identity": str(root.resolve()).lower(), "check_id": debt.RULE_ID,
            "check_version": debt.CHECK_VERSION, "authority": "SRC-999999",
            "accepted_missing_events": ["E-3", "E-4"], "evidence": evidence,
            "reason": REASON, "created_at": "2026-08-08T00:04:00Z"}


def write_record(root, record):
    record = {k: v for k, v in record.items() if k != "integrity_digest"}
    record["integrity_digest"] = debt._integrity_digest(record)
    path = root / debt.ACCEPTED_DEBT_DIR / (record["record_id"] + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return path


class AuthorityNegativeTests(Fixture):
    def setUp(self):
        super().setUp()
        ensure_project_lineage(self.root)

    def assert_refused_unchanged(self, authority):
        before = tree_bytes(self.root)
        result = self.register(["E-3", "E-4"], authority=authority)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(tree_bytes(self.root), before)

    def test_missing_source_reference_grants_no_acceptance(self):
        self.assert_refused_unchanged("SRC-999999")

    def test_existing_event_is_not_a_decision(self):
        self.assert_refused_unchanged("E-1")

    def test_project_lineage_is_not_operator_permission(self):
        self.assert_refused_unchanged(ensure_project_lineage(self.root))

    def test_existing_model_source_is_not_a_decision(self):
        source = intake.capture(self.root, "diagnose only; no debt acceptance", force=True)
        self.assertTrue(source["ok"], source)
        self.assert_refused_unchanged(source["receipt"])

    def test_forged_operator_label_does_not_authenticate_capsule(self):
        lineage = ensure_project_lineage(self.root)
        evidence = {f"E-{event['event']}": debt._line_sha256(raw)
                    for _file, _line, raw, event in debt._iter_history(self.root)
                    if event["event"] in (3, 4)}
        capsule = {
            "kind": "saipen-accepted-debt-decision", "schema": 1,
            "project_lineage": lineage, "check_id": debt.RULE_ID,
            "check_version": debt.CHECK_VERSION, "events": ["E-3", "E-4"],
            "event_hashes": evidence, "decision": "ACCEPT_LEGACY_DEBT",
            "statement": REASON, "expires_at": "2099-01-01T00:00:00Z",
        }
        source = intake.capture(
            self.root, json.dumps(capsule), force=True,
            projection_policy=intake.PROJECTION_AUTHORITY_ONLY,
            request_provenance={"witness": "operator_carrier", "declared_by": "host_ingress"},
        )
        self.assertTrue(source["ok"], source)
        self.assert_refused_unchanged(source["receipt"])

    def test_integrity_and_receipt_shape_do_not_authenticate_legacy_record(self):
        lineage = ensure_project_lineage(self.root)
        evidence = [{"event": f"E-{event['event']}", "file": file, "line_number": line,
                     "line_sha256": debt._line_sha256(raw)}
                    for file, line, raw, event in debt._iter_history(self.root)
                    if event["event"] in (3, 4)]
        record = {
            "schema_version": debt.SCHEMA_VERSION, "kind": "accepted_legacy_debt",
            "record_id": "AD-000001", "project_lineage": lineage,
            "project_identity": str(self.root.resolve()).lower(),
            "check_id": debt.RULE_ID, "check_version": debt.CHECK_VERSION,
            "authority": "SRC-999999", "accepted_missing_events": ["E-3", "E-4"],
            "evidence": evidence, "reason": REASON, "created_at": "2026-08-08T00:04:00Z",
        }
        record["integrity_digest"] = debt._integrity_digest(record)
        directory = self.root / debt.ACCEPTED_DEBT_DIR
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "AD-000001.json").write_text(json.dumps(record), encoding="utf-8")
        missing = [(f"E-{event['event']}", file, raw)
                   for file, _line, raw, event in debt._iter_history(self.root)
                   if event["event"] in (3, 4)]
        before = tree_bytes(self.root)
        verdict = debt.evaluate_provenance(self.root, missing)
        self.assertFalse(verdict["accepted"], verdict)
        self.assertEqual(verdict.get("authority_status"), "UNKNOWN")
        self.assertEqual(tree_bytes(self.root), before)


class NativeDecisionTests(Fixture):
    CATEGORY = "actual_broker_with_explicitly_simulated_native_identity"

    def setUp(self):
        super().setUp()
        ensure_project_lineage(self.root)
        self.host = use_case_owner(self, self.root)
        self._debt_host = self.host

    def approval(self, events=("E-3", "E-4"), *, edit=None, action="resolve-gate"):
        from saipen_engine.operations import authority_capture

        planned = debt.preview(self.root, list(events))
        self.assertTrue(planned["ok"], planned)
        capsule = planned["capsule"]
        capsule.update(statement=REASON, expires_at="2099-01-01T00:00:00Z")
        if edit:
            edit(capsule)
        text = json.dumps(capsule)
        with native_operator(self.root, text, action=action):
            result = authority_capture(self.root, "probe", text)
        self.assertTrue(result.ok, result.to_dict())
        return result.data["receipt"]

    def apply(self, receipt, events=("E-3", "E-4")):
        return debt.register(self.root, agent="probe", events=list(events), reason=REASON,
                             authority=receipt)

    def test_real_kernel_accepts_exact_scoped_native_decision(self):
        original = self.log_bytes()
        receipt = self.approval()
        result = self.apply(receipt)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["authority_status"], "KNOWN")
        missing = [(f"E-{e['event']}", file, raw)
                   for file, _line, raw, e in debt._iter_history(self.root) if e["event"] in (3, 4)]
        verdict = debt.evaluate_provenance(self.root, missing)
        self.assertTrue(verdict["accepted"], verdict)
        self.assertEqual(verdict["authority_status"], "KNOWN")
        self.assertEqual(self.log_bytes(), original)

    def missing(self, root=None):
        root = root or self.root
        return [(f"E-{e['event']}", file, raw)
                for file, _line, raw, e in debt._iter_history(root) if e["event"] in (3, 4)]

    def refused(self, receipt, events=("E-3", "E-4")):
        before = tree_bytes(self.root)
        result = self.apply(receipt, events)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result.get("authority_status"), "UNKNOWN")
        self.assertEqual(tree_bytes(self.root), before)

    def test_unrelated_native_report_does_not_grant_decision_b(self):
        self.refused(self.approval(action="report"))

    def test_native_decision_cannot_widen_approved_event_set(self):
        self.refused(self.approval(events=("E-3",)))

    def test_native_decision_for_another_lineage_is_refused(self):
        receipt = self.approval(edit=lambda c: c.update(
            project_lineage="lineage-" + "f" * 32))
        self.refused(receipt)

    def test_expired_approval_never_reserves_a_new_effect(self):
        self.refused(self.approval(edit=lambda c: c.update(expires_at="2000-01-01T00:00:00Z")))

    def test_changed_history_after_approval_does_not_mutate_registration(self):
        receipt = self.approval()
        path = self.root / ".saipen/LOG.md"
        path.write_text(path.read_text().replace("provenance A", "changed provenance A"),
                        encoding="utf-8")
        self.refused(receipt)

    def revoke(self, receipt):
        provenance = intake.read_body(self.root, receipt)["meta"]["request_provenance"]
        proof = provenance["operator_origin"]
        result = self.host.fixture.broker.handle(
            {"op": "revoke-origin", "host": "claude", "proof": proof},
            self.host.fixture.native_peer,
        )
        self.assertTrue(result["ok"], result)

    def test_revoked_native_decision_is_refused(self):
        receipt = self.approval()
        self.revoke(receipt)
        self.refused(receipt)

    def test_revoked_accepted_decision_becomes_unknown_without_rewriting_history(self):
        receipt = self.approval()
        self.assertTrue(self.apply(receipt)["ok"])
        before = tree_bytes(self.root)
        self.revoke(receipt)
        verdict = debt.evaluate_provenance(self.root, self.missing())
        self.assertFalse(verdict["accepted"], verdict)
        self.assertEqual(verdict["authority_status"], "UNKNOWN")
        self.assertEqual(tree_bytes(self.root), before)

    def test_unregistered_worker_cannot_spend_a_readable_proof(self):
        receipt = self.approval()
        self.host.workers[str(self.root.resolve())] = 30
        self.refused(receipt)

    def test_accepted_scope_survives_delivery_expiry_and_task_churn(self):
        receipt = self.approval()
        self.assertTrue(self.apply(receipt)["ok"])
        self.host.fixture.now += 1000
        state = self.root / ".saipen/STATE.md"
        state.write_text(state.read_text().replace("task: none", "task: T-99"), encoding="utf-8")
        self.assertTrue(debt.evaluate_provenance(self.root, self.missing())["accepted"])

    def test_verified_acceptance_survives_actual_lineage_preserving_move(self):
        receipt = self.approval()
        self.assertTrue(self.apply(receipt)["ok"])
        moved = self.root.parent / "moved-project"
        shutil.copytree(self.root, moved)
        # Both paths are proven children of this test's own temporary root.
        self.assertEqual(self.root.parent.resolve(), Path(self._tmp.name).resolve())
        shutil.rmtree(self.root)
        self.assertTrue(debt.evaluate_provenance(moved, self.missing(moved))["accepted"])

    def test_same_scoped_source_repeat_writes_nothing(self):
        receipt = self.approval()
        first = self.apply(receipt)
        self.assertTrue(first["ok"], first)
        before = tree_bytes(self.root)
        second = self.apply(receipt)
        self.assertTrue(second["ok"], second)
        self.assertEqual(second["code"], "ALREADY_APPLIED")
        self.assertEqual(tree_bytes(self.root), before)

    def test_reserved_effect_retry_reuses_its_original_bytes(self):
        from saipen_engine import journal

        receipt = self.approval()
        with mock.patch.object(journal, "run_mutation",
                               return_value={"ok": False, "code": "WRITER_BUSY"}):
            first = self.apply(receipt)
        self.assertFalse(first["ok"], first)
        with mock.patch.object(debt, "_utc", return_value="2098-01-01T00:00:00Z"):
            result = self.apply(receipt)
        self.assertTrue(result["ok"], result)
        record = debt.load_record(self.root, result["record_id"])
        self.assertNotEqual(record["created_at"], "2098-01-01T00:00:00Z")

    def test_issuer_reservation_loss_never_inherits_a_journal_claim(self):
        receipt = self.approval()
        self.assertTrue(self.apply(receipt)["ok"])
        provenance = intake.read_body(self.root, receipt)["meta"]["request_provenance"]
        proof = provenance["operator_origin"]
        self.host.fixture.broker.origins.records[proof["nonce"]]["debt_grant"] = None
        self.assertFalse(debt.evaluate_provenance(self.root, self.missing())["accepted"])

    def test_preview_is_read_only_and_grants_nothing(self):
        before = tree_bytes(self.root)
        result = debt.preview(self.root, ["E-3", "E-4"])
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["authority_status"], "UNKNOWN")
        self.assertEqual(result["capsule"]["statement"], "")
        self.assertEqual(tree_bytes(self.root), before)

    def test_read_only_capability_still_forbids_an_authorized_mutation(self):
        import os

        receipt = self.approval()
        before = tree_bytes(self.root)
        with mock.patch.dict(os.environ, {"SAIPEN_CAPABILITY": "read-only"}):
            result = self.apply(receipt)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "CAPABILITY_READ_ONLY")
        self.assertEqual(tree_bytes(self.root), before)

    def test_public_registrar_and_validator_use_the_same_native_authority(self):
        receipt = self.approval()
        result = self.register(["E-3", "E-4"], authority=receipt)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        validation = self.run_validator()
        self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)
        self.assertIn("WARN [accepted-legacy-debt]:", validation.stdout)
        self.assertEqual(self.provenance_fail_lines(validation.stdout), [])

    def test_unverified_legacy_record_cannot_be_laundered_by_rebind(self):
        path = write_record(self.root, legacy_record(self.root))
        before = tree_bytes(self.root)
        import hashlib

        result = debt.rebind(self.root, "AD-000001", agent="probe", reason="rotate",
                             expected_before=hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["authority_status"], "UNKNOWN")
        self.assertEqual(tree_bytes(self.root), before)

    def test_fresh_scoped_decision_appends_instead_of_promoting_legacy_authority(self):
        path = write_record(self.root, legacy_record(self.root))
        original = path.read_bytes()
        receipt = self.approval()
        result = self.apply(receipt)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["record_id"], "AD-000002")
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(debt.load_record(self.root, "AD-000001")["authority"], "SRC-999999")
        verdict = debt.evaluate_provenance(self.root, self.missing())
        self.assertTrue(verdict["accepted"], verdict)
        self.assertEqual(verdict["record_id"], "AD-000002")

    def test_changed_legacy_predecessor_invalidates_the_scoped_replacement(self):
        record = legacy_record(self.root)
        write_record(self.root, record)
        receipt = self.approval()
        record["reason"] = "changed after approval"
        write_record(self.root, record)
        before = tree_bytes(self.root)
        self.assertFalse(self.apply(receipt)["ok"])
        self.assertEqual(tree_bytes(self.root), before)

    def test_model_written_real_journal_cannot_replace_a_native_effect_reservation(self):
        import hashlib
        from saipen_engine import debt_authority, journal

        receipt = self.approval()
        record = legacy_record(self.root)
        record["authority"] = receipt
        record["authorization"] = debt_authority.source_shape(self.root, record)
        record["registration_op_id"] = debt_authority.operation(record)
        record["journal_op_id"] = record["registration_op_id"]
        record["integrity_digest"] = debt._integrity_digest(record)
        raw = debt_authority.record_bytes(record)
        rel = f"{debt.ACCEPTED_DEBT_DIR}/AD-000001.json"
        result = journal.run_mutation(
            self.root, op_id=record["registration_op_id"], operation="accepted_debt.register",
            agent="probe", project_identity=record["project_identity"],
            semantic_payload_hash=hashlib.sha256(raw).hexdigest(),
            targets=[{"path": rel, "role": "report", "action": "write", "content": raw,
                      "before_hash": "", "after_hash": hashlib.sha256(raw).hexdigest()}],
            preconditions={rel: ""}, verification_policy="none",
        )
        self.assertTrue(result["ok"], result)
        verdict = debt.evaluate_provenance(self.root, self.missing())
        self.assertFalse(verdict["accepted"], verdict)
        self.assertEqual(verdict["authority_status"], "UNKNOWN")

    def prepared_crash(self, boundary="PREPARE"):
        import os

        receipt = self.approval()
        with mock.patch.dict(os.environ, {f"NITRO_CRASH_AFTER_{boundary}": "1"}), \
                self.assertRaises(SystemExit) as crash:
            self.apply(receipt)
        self.assertEqual(crash.exception.code, 87)
        provenance = intake.read_body(self.root, receipt)["meta"]["request_provenance"]
        proof = provenance["operator_origin"]
        grant = self.host.fixture.broker.origins.records[proof["nonce"]]["debt_grant"]
        self.assertEqual((self.root / debt.ACCEPTED_DEBT_DIR / "AD-000001.json").exists(),
                         boundary == "VERIFIED")
        return receipt, grant["operation"]

    def test_prepared_crash_recovers_the_reserved_artifact_without_new_approval(self):
        from saipen_engine import journal

        original = self.log_bytes()
        _receipt, operation = self.prepared_crash()
        recovered = journal.recover(self.root, operation)
        self.assertTrue(recovered["ok"], recovered)
        self.assertEqual(recovered["code"], "ABORTED")
        result = self.apply(_receipt)
        self.assertTrue(result["ok"], result)
        actual = debt.load_record(self.root, result["record_id"])
        self.assertEqual(actual["registration_attempt"], 1)
        self.assertEqual(actual["retry_of"], operation)
        self.assertTrue(debt.evaluate_provenance(self.root, self.missing())["accepted"])
        before = tree_bytes(self.root)
        self.assertTrue(journal.recover(self.root, actual["registration_op_id"])["ok"])
        self.assertEqual(tree_bytes(self.root), before)
        self.assertEqual(self.log_bytes(), original)

    def test_changed_source_after_crash_refuses_before_writing_the_acceptance(self):
        from saipen_engine import journal

        receipt, operation = self.prepared_crash()
        source = self.root / f".saipen/intake/active/{receipt}.md"
        source.write_text("changed after approval", encoding="utf-8")
        recovered = journal.recover(self.root, operation)
        self.assertEqual(recovered["code"], "ABORTED")
        self.assertFalse(self.apply(receipt)["ok"])
        self.assertFalse((self.root / debt.ACCEPTED_DEBT_DIR / "AD-000001.json").exists())

    def test_revoked_pending_decision_never_recovers_as_accepted(self):
        from saipen_engine import journal

        original = self.log_bytes()
        receipt, operation = self.prepared_crash()
        self.revoke(receipt)
        recovered = journal.recover(self.root, operation)
        self.assertEqual(recovered["code"], "ABORTED")
        self.assertFalse(self.apply(receipt)["ok"])
        self.assertFalse(debt.evaluate_provenance(self.root, self.missing())["accepted"])
        self.assertEqual(self.log_bytes(), original)

    def test_malformed_broker_registration_does_not_reserve_permission(self):
        receipt = self.approval()
        provenance = intake.read_body(self.root, receipt)["meta"]["request_provenance"]
        proof = provenance["operator_origin"]
        result = self.host.fixture.broker.handle(
            {"op": "prepare-origin-debt", "project": str(self.root), "proof": proof,
             "record": []}, self.host.fixture.peer,
        )
        self.assertFalse(result["ok"], result)
        self.assertIsNone(self.host.fixture.broker.origins.records[proof["nonce"]].get("debt_grant"))

    def test_verified_crash_rechecks_and_commits_the_actual_approved_artifact(self):
        from saipen_engine import journal

        _receipt, operation = self.prepared_crash("VERIFIED")
        # A target exists but is not accepted before its operation commits.
        self.assertFalse(debt.evaluate_provenance(self.root, self.missing())["accepted"])
        result = journal.recover(self.root, operation)
        self.assertTrue(result["ok"], result)
        self.assertTrue(debt.evaluate_provenance(self.root, self.missing())["accepted"])

    def test_revocation_after_written_crash_remains_a_visible_recovery_conflict(self):
        from saipen_engine import journal

        receipt, operation = self.prepared_crash("VERIFIED")
        self.revoke(receipt)
        result = journal.recover(self.root, operation)
        self.assertFalse(result["ok"], result)
        self.assertFalse(debt.evaluate_provenance(self.root, self.missing())["accepted"])
        self.assertEqual(journal.Journal(self.root, operation).read()["status"], "CONFLICT")

    def test_committed_operation_does_not_report_a_missing_target_repaired(self):
        receipt = self.approval()
        result = self.apply(receipt)
        self.assertTrue(result["ok"], result)
        path = self.root / debt.ACCEPTED_DEBT_DIR / (result["record_id"] + ".json")
        path.unlink()
        result = self.apply(receipt)
        self.assertFalse(result["ok"], result)
        self.assertFalse(path.exists())

    def test_stale_locations_need_rebind_instead_of_false_idempotent_success(self):
        receipt = self.approval()
        self.assertTrue(self.apply(receipt)["ok"])
        logs = self.root / ".saipen/logs"
        logs.mkdir(exist_ok=True)
        shutil.move(str(self.root / ".saipen/LOG.md"), str(logs / "LOG-001.md"))
        before = tree_bytes(self.root)
        result = self.apply(receipt)
        self.assertFalse(result["ok"], result)
        self.assertEqual(tree_bytes(self.root), before)

    def test_fresh_native_capture_does_not_promote_an_old_model_source(self):
        capsule = debt.preview(self.root, ["E-3", "E-4"])["capsule"]
        capsule.update(statement=REASON, expires_at="2099-01-01T00:00:00Z")
        old = intake.capture(self.root, json.dumps(capsule), force=True,
                             projection_policy=intake.PROJECTION_AUTHORITY_ONLY)
        self.assertTrue(old["ok"], old)
        original = intake.read_body(self.root, old["receipt"])["meta"]
        receipt = self.approval()
        self.assertNotEqual(receipt, old["receipt"])
        self.assertTrue(self.apply(receipt)["ok"])
        self.assertEqual(intake.read_body(self.root, old["receipt"])["meta"], original)
        self.refused(old["receipt"])

    def test_modified_native_proof_in_source_metadata_is_not_authority(self):
        receipt = self.approval()
        path = self.root / f".saipen/intake/active/{receipt}.meta.json"
        meta = json.loads(path.read_text())
        meta["request_provenance"]["operator_origin"]["mac"] = "0" * 64
        path.write_text(json.dumps(meta), encoding="utf-8")
        self.refused(receipt)

    def test_changed_committed_target_claim_cannot_replace_the_reserved_digest(self):
        from saipen_engine import journal

        receipt = self.approval()
        result = self.apply(receipt)
        self.assertTrue(result["ok"], result)
        manifest = journal.Journal(self.root, result["journal_op_id"]).manifest
        value = json.loads(manifest.read_text())
        value["targets"][0]["after_hash"] = "0" * 16
        manifest.write_text(json.dumps(value), encoding="utf-8")
        self.assertFalse(debt.evaluate_provenance(self.root, self.missing())["accepted"])
