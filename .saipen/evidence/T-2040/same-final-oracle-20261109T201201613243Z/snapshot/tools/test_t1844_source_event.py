"""Source identity and historical truth with an isolated native-event broker.

Native identity and process facts are simulated by the existing kernel fixture;
these tests make no claim about a live host or UI.
"""

from __future__ import annotations

import copy
import inspect
import os
import unittest
from unittest import mock

from saipen_engine import entry, host_authority_client as HC, intake, operator_task as OT
from saipen_engine import retirement
from saipen_engine.pending_ingress import ingress_digest
from test_hermetic_env import isolate_host_session
from test_t1363_zero_manual_entry import healthy
import test_t1844_origin_broker as origin_controls

TEXT = origin_controls.TEXT


def setUpModule():
    isolate_host_session()


class SourceEventTests(unittest.TestCase):
    def setUp(self):
        self.origin = origin_controls.OriginKernelWithSimulatedNativeIdentity()
        self.origin.setUp()
        self.addCleanup(self.origin.doCleanups)
        self.root = self.origin.root

    def provenance(self, proof):
        return {
            "witness": OT.WITNESS_CARRIER,
            "declared_by": OT.DECLARED_HOST_INGRESS,
            "compared_digest": ingress_digest(TEXT),
            "operator_origin": proof,
        }

    def capture(self, proof=None):
        result = intake.capture(
            self.root, TEXT,
            request_provenance=self.provenance(proof) if proof else None,
        )
        self.assertTrue(result["ok"], result)
        return result["receipt"]

    def test_new_native_event_preserves_earlier_model_source_and_its_own_retries(self):
        old = self.capture()
        old_meta = intake._read_meta(self.root, old)
        proof = self.origin.issue()
        self.origin.register(proof)
        current = self.capture(proof)
        self.assertNotEqual(current, old)
        self.assertEqual(intake._read_meta(self.root, old), old_meta)
        with mock.patch.object(HC, "_call", side_effect=self.origin.bridge):
            self.assertTrue(OT.authority_for_receipt(
                self.root, current, existing_only=False,
            )["user_explicit"])
            self.assertFalse(OT.authority_for_receipt(self.root, old)["user_explicit"])
        self.assertEqual(self.capture(proof), current)

    def test_different_native_events_with_identical_text_keep_distinct_sources(self):
        first = self.origin.issue()
        second = self.origin.issue(event="another-event")
        a, b = self.capture(first), self.capture(second)
        self.assertNotEqual(a, b)
        self.assertEqual(self.capture(first), a)
        self.assertEqual(self.capture(second), b)

    def test_model_retry_never_borrows_an_earlier_native_event(self):
        proof = self.origin.issue()
        original = self.capture(proof)
        untrusted = self.capture()
        self.assertNotEqual(untrusted, original)
        self.assertEqual(intake._read_meta(self.root, untrusted)["request_provenance"],
                         {"witness": OT.WITNESS_MODEL})
        self.assertEqual(self.capture(), untrusted)

    def test_model_labelled_copy_of_a_real_proof_cannot_shadow_the_native_source(self):
        proof = self.origin.issue()
        self.origin.register(proof)
        copied = self.provenance(proof)
        copied["witness"] = OT.WITNESS_MODEL
        old = intake.capture(self.root, TEXT, request_provenance=copied)
        self.assertTrue(old["ok"], old)
        original = intake._read_meta(self.root, old["receipt"])
        current = self.capture(proof)
        self.assertNotEqual(current, old["receipt"])
        with mock.patch.object(HC, "_call", side_effect=self.origin.bridge):
            self.assertFalse(OT.authority_for_receipt(self.root, old["receipt"])["user_explicit"])
            self.assertTrue(OT.authority_for_receipt(
                self.root, current, existing_only=False,
            )["user_explicit"])
        self.assertEqual(intake._read_meta(self.root, old["receipt"]), original)

    def test_event_probe_selects_the_later_matching_receipt_without_writing(self):
        self.capture()
        proof = self.origin.issue()
        current = self.capture(proof)
        before = self.snapshot()
        self.assertIn("request_provenance", inspect.signature(intake.find_by_body).parameters,
                      "the read-only probe must distinguish operator events with identical bytes")
        found = intake.find_by_body(self.root, TEXT, request_provenance=self.provenance(proof))
        self.assertEqual(found["receipt"], current)
        self.assertEqual(self.snapshot(), before)

    def test_integrity_is_checked_before_a_different_event_is_filtered_out(self):
        old = self.capture()
        (self.root / f".saipen/intake/active/{old}.md").write_text("corrupt", encoding="utf-8")
        before = self.snapshot()
        result = intake.capture(
            self.root, TEXT, request_provenance=self.provenance(self.origin.issue()),
        )
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "SOURCE_CORRUPTION")
        self.assertEqual(self.snapshot(), before)

    def test_body_only_crash_adopts_the_orphan_after_an_older_event(self):
        old = self.capture()
        proof = self.origin.issue()
        with mock.patch.object(intake, "_write_meta", side_effect=OSError("fixture interruption")):
            failed = intake.capture(self.root, TEXT, request_provenance=self.provenance(proof))
        self.assertFalse(failed["ok"], failed)
        current = self.capture(proof)
        self.assertNotEqual(current, old)
        self.assertEqual(current, self.capture(proof))
        self.assertEqual(len(list((self.root / ".saipen/intake/active").glob("SRC-*.md"))), 2)

    def test_metadata_crash_preserves_event_identity_before_index_recovery(self):
        proof = self.origin.issue()
        interrupted = mock.patch.object(
            intake, "_write_index", side_effect=OSError("fixture interruption"),
        )
        with mock.patch.object(intake, "_utc", return_value="2026-01-01T00:00:00Z"), interrupted:
            failed = intake.capture(self.root, TEXT, request_provenance=self.provenance(proof))
        self.assertFalse(failed["ok"], failed)
        orphan = next((self.root / ".saipen/intake/active").glob("SRC-*.meta.json"))
        original = orphan.read_bytes()
        other = self.capture(self.origin.issue(event="second-event"))
        self.assertEqual(orphan.read_bytes(), original)
        recovered = self.capture(proof)
        self.assertNotEqual(other, recovered)
        self.assertEqual(recovered, self.capture(proof))
        self.assertEqual(orphan.read_bytes(), original)

    def test_corrupt_orphan_metadata_cannot_be_silently_ignored(self):
        from saipen_engine.lock import project_writer_lock

        active = self.root / ".saipen/intake/active"
        active.mkdir(parents=True)
        (active / "SRC-001.md").write_text(TEXT, encoding="utf-8")
        (active / "SRC-001.meta.json").write_text("{broken", encoding="utf-8")
        with project_writer_lock(self.root):
            pass
        before = self.snapshot()
        result = intake.capture(self.root, TEXT)
        self.assertFalse(result["ok"], result)
        self.assertEqual(self.snapshot(), before)

    def test_closed_other_event_does_not_shadow_a_new_native_source(self):
        self.root = self.origin.root = healthy(self)
        proof = self.origin.issue()
        old = self.capture(proof)
        self.assertTrue(intake.add_requirement(self.root, old, rid="R001", text=TEXT)["ok"])
        self.assertTrue(intake.set_disposition(
            self.root, old, "R001", "VERIFIED", evidence="fixture evidence",
            verification="fixture verification:PASS",
        )["ok"])
        closed = intake.close_receipt(self.root, old)
        self.assertTrue(closed["ok"], closed)
        self.assertEqual(self.capture(proof), old)
        second = self.origin.issue(event="new-after-closure")
        event_scope = (
            {"request_provenance": self.provenance(second)}
            if "request_provenance" in inspect.signature(entry._request_identity).parameters else {}
        )
        _body, predecessor, _found = entry._request_identity(
            self.root, lambda prior: TEXT + (f"\nsupersedes: {prior}" if prior else ""),
            TEXT, **event_scope,
        )
        self.assertEqual(predecessor, old)
        self.assertNotEqual(self.capture(second), old)
        self.assertEqual(intake.read_body(self.root, old)["meta"]["request_provenance"],
                         self.provenance(proof))

    def test_start_projects_its_exact_bound_receipt_without_recapturing_as_model(self):
        from saipen_engine.board import parse_board

        proof, result = self.native_start()
        tickets = parse_board((self.root / ".saipen/BOARD.md").read_text())["tickets"]
        self.assertEqual(tickets[result["ticket"]]["fields"].get("user_explicit"), "true")
        receipts = intake._read_index(self.root)["active"]
        self.assertEqual(set(receipts), {result["receipt"]})
        self.assertEqual(intake._read_meta(self.root, result["receipt"])
                         ["request_provenance"]["operator_origin"], proof)

    def test_user_request_uses_its_independent_root_for_native_event_verification(self):
        from saipen_engine import operations

        self.root = self.origin.root = healthy(self)
        proof = self.origin.issue()
        self.origin.register(proof)
        OT.admit_host_ingress({"request_text": TEXT, "session_id": "session-A",
                              "message_id": "user-request", "operator_origin": proof}, self.root)
        with mock.patch.dict(os.environ, {OT.ENV_HOST_SESSION: "session-A"}), mock.patch.object(
            HC, "_call", side_effect=self.origin.bridge,
        ):
            result = operations.user_request(self.root, "test-agent", TEXT)
        self.assertTrue(result.ok, result.to_dict())
        self.assertTrue(result.data["user_explicit"], result.to_dict())

    def test_captured_request_cannot_substitute_its_source_body(self):
        from saipen_engine import operations

        self.assertIn("source_receipt", inspect.signature(operations.user_request).parameters,
                      "START must be able to project its already bound canonical Source")
        self.root = self.origin.root = healthy(self)
        old = self.capture()
        before = self.snapshot()
        result = operations.user_request(
            self.root, "test-agent", "a different request", source_receipt=old,
        )
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(self.snapshot(), before)

    def test_append_caller_preserves_the_native_event_with_an_explicit_project(self):
        from saipen_engine import source_append

        self.root = self.origin.root = healthy(self)
        controlling = intake.capture(self.root, "The original importer must retain its acceptance.")
        self.assertTrue(controlling["ok"], controlling)
        proof = self.origin.issue(action="append")
        self.origin.register(proof)
        OT.admit_host_ingress({"request_text": TEXT, "session_id": "session-A",
                              "message_id": "native-append", "operator_origin": proof}, self.root)
        with mock.patch.dict(os.environ, {OT.ENV_HOST_SESSION: "session-A"}), mock.patch.object(
            HC, "_call", side_effect=self.origin.bridge,
        ):
            result = source_append.append(self.root, TEXT, to=controlling["receipt"])
            self.assertTrue(result["ok"], result)
            self.assertTrue(OT.authority_for_receipt(
                self.root, result["receipt"],
            )["user_explicit"])

    def test_only_an_append_event_can_rewind_the_original_mission(self):
        from saipen_engine import source_append
        from test_t1461_source_append import AppendFixture, BRICKS

        for action, authorized in (("report", False), ("append", True)):
            fixture = AppendFixture()
            self.addCleanup(fixture.doCleanups)
            self.root = self.origin.root = fixture.make_project()
            work, source = fixture.mission(self.root, "VERIFY")
            self.assertTrue(intake.ensure_request_clause(self.root, source)["ok"])
            original_coverage = intake._read_coverage(self.root, source)
            proof = self.origin.issue(action=action, text=BRICKS[0], event=action)
            worker = 20 if action == "report" else 40
            self.origin.register(proof, worker=worker)
            self.origin.peer = origin_controls.SimpleNamespace(pid=worker)
            OT.admit_host_ingress(
                {"request_text": BRICKS[0], "session_id": "session-A", "message_id": action,
                 "operator_origin": proof}, self.root,
            )
            with mock.patch.dict(os.environ, {OT.ENV_HOST_SESSION: "session-A"}), mock.patch.object(
                HC, "_call", side_effect=self.origin.bridge,
            ):
                received = source_append.append(
                    self.root, BRICKS[0], to=source, actor="tester",
                    klass=source_append.CONFLICT, supersedes=[f"{source}:R001"],
                )
                self.assertTrue(received["ok"], received)
                projected = source_append.apply_append(
                    self.root, received["receipt"], actor="tester",
                )
            self.assertTrue(projected["ok"], projected)
            self.assertEqual(projected["work"] == work, authorized, (action, projected))
            self.assertEqual(fixture.phase(self.root), "BUILD" if authorized else "VERIFY")
            if not authorized:
                self.assertEqual(intake._read_coverage(self.root, source), original_coverage)
                self.assertIn("[P2]", fixture.tickets(self.root)[projected["work"]]["raw"])

    def test_bound_goal_retry_finds_its_event_after_an_earlier_model_source(self):
        from saipen_engine import operations
        from saipen_engine.result import Result

        body, proof = self.origin.existing_goal_event()
        self.root = self.origin.root
        old = intake.capture(self.root, body, projection_policy=intake.PROJECTION_AUTHORITY_ONLY)
        self.assertTrue(old["ok"], old)
        original = intake._read_meta(self.root, old["receipt"])
        with mock.patch.dict(os.environ, {OT.ENV_HOST_SESSION: "session-A"}), mock.patch.object(
            HC, "_call", side_effect=self.origin.bridge,
        ):
            with mock.patch.object(
                operations, "apply_plan", return_value=Result(False, "WRITER_BUSY"),
            ):
                first = operations.authorize_goal_continuation(self.root, "test-agent", body)
            self.assertFalse(first.ok, first.to_dict())
            bound = self.origin.broker.origins.records[proof["nonce"]]["receipt"]
            self.assertNotEqual(bound, old["receipt"])
            second = operations.authorize_goal_continuation(self.root, "test-agent", body)
        self.assertTrue(second.ok, second.to_dict())
        self.assertEqual(intake._read_meta(self.root, old["receipt"]), original)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def native_start(self):
        self.root = self.origin.root = healthy(self)
        proof = self.origin.issue()
        self.origin.register(proof)
        OT.admit_host_ingress({"request_text": TEXT, "session_id": "session-A",
                              "message_id": "native-start", "operator_origin": proof}, self.root)
        with mock.patch.dict(os.environ, {OT.ENV_HOST_SESSION: "session-A"}), mock.patch.object(
            HC, "_call", side_effect=self.origin.bridge,
        ):
            result = entry.start_work(self.root, "test-agent", text=TEXT, actor_source="fixture")
        self.assertTrue(result["ok"], result)
        return proof, result

    def test_expired_native_source_is_not_automatically_retracted_as_model_fabrication(self):
        from saipen_engine.board import parse_board

        _proof, result = self.native_start()
        self.origin.now += 61
        tickets = parse_board((self.root / ".saipen/BOARD.md").read_text())["tickets"]
        ticket = tickets[result["ticket"]]
        before = self.snapshot()
        with mock.patch.object(HC, "_call", side_effect=self.origin.bridge):
            problem = retirement.system_correction_error(
                self.root, ticket, [], retirement.REASON_FALSE_AUTHORITY,
            )
        self.assertIsNotNone(problem, "expiry is not evidence of a false historical projection")
        self.assertEqual(self.snapshot(), before)

    def test_model_source_still_supports_a_proven_false_projection_correction(self):
        from saipen_engine.board import parse_board

        self.root = self.origin.root = healthy(self)
        result = entry.start_work(self.root, "test-agent", text=TEXT, actor_source="fixture")
        self.assertTrue(result["ok"], result)
        tickets = parse_board((self.root / ".saipen/BOARD.md").read_text())["tickets"]
        ticket = copy.deepcopy(tickets[result["ticket"]])
        ticket["fields"]["user_explicit"] = "true"
        self.assertIsNone(retirement.system_correction_error(
            self.root, ticket, [], retirement.REASON_FALSE_AUTHORITY,
        ))

    def test_response_and_decision_queries_never_bind_an_unused_source(self):
        from saipen_engine import decision_request, response_surface

        proof = self.origin.issue()
        self.origin.register(proof)
        receipt = self.capture(proof)
        provenance = self.provenance(proof)
        original = copy.deepcopy(self.origin.broker.origins.records[proof["nonce"]])
        with mock.patch.object(HC, "_call", side_effect=self.origin.bridge):
            self.assertFalse(response_surface.human_response_authority(
                TEXT, provenance, root=self.root, receipt=receipt,
            ))
            allowed, _why = decision_request.validate_authority_escalation(
                "cc all override paused work", "fixture", "operator_carrier",
                provenance=provenance, root=self.root, receipt=receipt,
            )
            self.assertFalse(allowed)
        self.assertEqual(self.origin.broker.origins.records[proof["nonce"]], original)


if __name__ == "__main__":
    unittest.main()
