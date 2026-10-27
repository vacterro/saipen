"""T-1792: one cc refreshes stale conformance through the canonical validator.

Integration cases use real disposable Git projects and the actual validator;
unit cases inject races and instrument failures without touching live ledgers.
The original crew route must resume in the same invocation, on durable proof.
"""

from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import saipen as CLI  # noqa: E402
import test_continue_chain as chain  # noqa: E402
import test_t1412_conformance_truth as fixtures  # noqa: E402
from saipen_engine import audit_manifest, conformance as C, operations  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule():
    isolate_host_session()


class ContinuationIntegration(fixtures.T1412Base):
    def project(self, name="doctor", **kwargs):
        root = self.make_project(name, state=fixtures._ROUTER_STATE, **kwargs)
        self.assert_fast_gate_clean(root)
        self.assertTrue(audit_manifest.ensure(root)["ok"])
        return root

    def snapshot(self, root):
        return {
            p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file() and ".git" not in p.parts
        }

    def invoke(self, root, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            rc = CLI.main(["--project-root", str(root), "--json", *args])
        return rc, json.loads(output.getvalue())

    def test_stale_state_receipt_is_refreshed_and_original_route_resumes(self):
        root = self.project()
        fixtures.write_receipt(root, "PASS")
        # Model a legitimate checkpoint update, preserving all fast invariants.
        state = root / ".saipen/STATE.md"
        state.write_text(state.read_text(encoding="utf-8").replace(
            "2026-09-19T21:00:00Z", "2026-09-19T21:00:01Z"
        ), encoding="utf-8")
        self.assertEqual(C.conformance_decision(root)["status"], "STALE_PASS")
        before = self.snapshot(root)
        rc, result, text = self.run_cli(root, "cc")
        self.assertEqual(rc, 0, text)
        self.assertEqual(result["action"], "saipen crew", result)
        self.assertEqual(result["doctor"]["stage"], "RESUMING", result)
        self.assertEqual(result["doctor"]["status_after"], "CURRENT_PASS")
        self.assertTrue(C.conformance_decision(root)["healthy"])
        after = self.snapshot(root)
        changed = {p for p in before.keys() | after.keys() if before.get(p) != after.get(p)}
        receipts = {p for p in changed if "/index/" not in p}
        self.assertEqual(len(receipts), 1, changed)
        self.assertTrue(all(p.startswith(C.RECEIPT_DIRNAME + "/") for p in changed), changed)
        self.assertEqual(result["doctor"]["receipt_after"]["project_identity"],
                         C.conformance_decision(root)["status_block"]["receipt"]["project_identity"])
        # A second healthy cc performs no repair and makes no new receipt.
        rc, second, text = self.run_cli(root, "cc")
        self.assertEqual(rc, 0, text)
        self.assertNotIn("doctor", second)
        self.assertEqual(after, self.snapshot(root))

    def test_absent_and_old_validator_evidence_are_refreshed(self):
        for status in ("NOT_RUN", "VALIDATOR_VERSION_MISMATCH"):
            with self.subTest(status=status):
                root = self.project(status)
                if status != "NOT_RUN":
                    fixtures.write_receipt(root, "PASS", validator_version="0")
                self.assertEqual(C.conformance_decision(root)["status"], status)
                rc, result, text = self.run_cli(root, "continue")
                self.assertEqual(rc, 0, text)
                self.assertEqual(result["action"], "saipen crew", result)
                self.assertEqual(result["doctor"]["status_before"], status)
                self.assertEqual(result["doctor"]["status_after"], "CURRENT_PASS")

    def test_unsafe_evidence_is_never_automatically_revalidated(self):
        seeds = (
            ("CURRENT_FAIL", {"verdict": "FAIL"}),
            ("STALE_FAIL", {"verdict": "FAIL", "source_head": "old", "source_fp": "old"}),
            ("INVALID_RECEIPT", {"verdict": "PASS", "tamper": True}),
        )
        for status, kwargs in seeds:
            with self.subTest(status=status):
                root = self.project(status)
                fixtures.write_receipt(root, **kwargs)
                self.assertEqual(C.conformance_decision(root)["status"], status)
                before = self.snapshot(root)
                rc, result, _ = self.run_cli(root, "cc")
                self.assertEqual(rc, 1, result)
                self.assertEqual(result["conformance_status"], status)
                self.assertNotIn("doctor", result)
                self.assertEqual(before, self.snapshot(root))

    def test_canonical_validator_failure_stops_on_its_real_findings(self):
        root = self.project(commit_identity=False)
        fixtures.write_receipt(root, "PASS", source_head="old", source_fp="old")
        rc, result, _ = self.run_cli(root, "cc")
        self.assertEqual(rc, 1, result)
        self.assertEqual(result["conformance_status"], "CURRENT_FAIL", result)
        self.assertEqual(result["doctor"]["stage"], "BLOCKED")
        self.assertFalse(result["doctor"]["ok"])
        self.assertNotEqual(result.get("action"), "saipen crew")
        self.assertFalse(C.conformance_decision(root)["healthy"])

    def test_dry_run_and_next_leave_every_byte_unchanged(self):
        for args in (("cc", "--dry-run"), ("next",)):
            with self.subTest(args=args):
                root = self.project("preview-" + args[0])
                fixtures.write_receipt(root, "PASS", source_head="old", source_fp="old")
                before = self.snapshot(root)
                rc, result, _ = self.run_cli(root, *args)
                self.assertEqual(rc, 1, result)
                self.assertEqual(result["conformance_status"], "STALE_PASS")
                if "--dry-run" in args:
                    self.assertEqual(result["doctor"]["stage"], "DIAGNOSING")
                self.assertEqual(before, self.snapshot(root))

    def test_read_only_cc_does_not_mint_a_receipt(self):
        root = self.project()
        fixtures.write_receipt(root, "PASS", source_head="old", source_fp="old")
        before = self.snapshot(root)
        with mock.patch.object(CLI, "_negotiate_capability", return_value="read-only"), \
                mock.patch.object(CLI, "_validate") as validator:
            rc, result = self.invoke(root, "cc")
        self.assertEqual(rc, 0, result)
        self.assertEqual(result["reason"], "read-only-mode")
        self.assertEqual(result["action"], "saipen status")
        validator.assert_not_called()
        self.assertEqual(before, self.snapshot(root))

    def test_chain_finish_revalidates_and_continues_in_the_same_cc(self):
        root = self.project()
        added = operations.ticket_add(root, "tester", "P1", "fixture work", [], "fixture passes")
        self.assertTrue(added.ok, added.to_dict())
        ticket = added.data["ticket"]
        claimed = operations.apply_claim(root, ticket, "tester", explicit=True)
        self.assertTrue(claimed.ok, claimed.to_dict())
        chain.ContinueChainTests._advance_to_ship(self, root, ticket)
        fixtures.write_receipt(root, "PASS")
        with mock.patch.object(CLI, "_validate", wraps=CLI._validate) as validator:
            rc, result = self.invoke(root, "cc")
        self.assertEqual(rc, 0, result)
        self.assertEqual(result["action"], "saipen crew", result)
        self.assertEqual(validator.call_count, 1)
        steps = result["continue_trace"]
        self.assertEqual([s["operation"] for s in steps], ["ticket_done", "validate"], result)
        self.assertEqual(steps[0]["ticket"], ticket)
        self.assertEqual(steps[1]["stage"], "RESUMING")
        self.assertTrue(C.conformance_decision(root)["healthy"])

    def test_a_receipt_restaled_after_validation_stops_after_one_attempt(self):
        root = self.project()
        fixtures.write_receipt(root, "PASS", source_head="old", source_fp="old")
        validate = CLI._validate

        def raced(project, as_json):
            rc = validate(project, as_json)
            state = root / ".saipen/STATE.md"
            state.write_text(state.read_text(encoding="utf-8").replace(
                "2026-09-19T21:00:00Z", "2026-09-19T21:00:01Z"
            ), encoding="utf-8")
            return rc

        with mock.patch.object(CLI, "_validate", side_effect=raced) as validator:
            rc, result = self.invoke(root, "cc")
        self.assertEqual(rc, 1, result)
        self.assertEqual(validator.call_count, 1)
        self.assertEqual(result["conformance_status"], "STALE_PASS")
        self.assertIn("no second revalidation", result["doctor"]["why_stopped"])


class TypedStaleReasons(fixtures.T1412Base):
    """T-1823: the real producers stamp the closed code for every staleness.

    The Auto-Doctor's authority to repair is read from these codes, so they are
    asserted against REAL receipts (real Git project, real conformance_status),
    not against a synthetic payload: what the doctor may repair must be exactly
    what this function reports as recoverable.
    """

    def status(self, name, verdict, **kwargs):
        root = self.make_project(name, state=fixtures._STATE)
        fixtures.write_receipt(root, verdict, **kwargs)
        return root, C.conformance_status(root, gate="core")

    def test_a_drifted_receipt_is_typed_recoverable(self):
        _, st = self.status("drift", "FAIL", source_head="OLD_HEAD", source_fp="OLD_FP")
        self.assertEqual(st["status"], C.STATUS_STALE_FAIL, st)
        self.assertEqual(st["stale_reason"], C.STALE_REASON_SOURCE_BINDING_STALE, st)
        self.assertTrue(C.stale_recoverable(st))

    def test_an_aged_receipt_is_typed_recoverable(self):
        old = "2020-01-01T00:00:00.000000Z"
        _, st = self.status("aged", "FAIL", ts=old)
        self.assertEqual(st["status"], C.STATUS_STALE_FAIL, st)
        self.assertEqual(st["stale_reason"], C.STALE_REASON_AGED_BEYOND_WINDOW, st)
        self.assertTrue(C.stale_recoverable(st))

    def test_a_fabricated_future_receipt_is_never_recoverable(self):
        future = "2099-01-01T00:00:00.000000Z"
        _, st = self.status("future", "FAIL", ts=future)
        self.assertEqual(st["status"], C.STATUS_STALE_FAIL, st)
        self.assertEqual(st["stale_reason"], C.STALE_REASON_FUTURE_TIMESTAMP, st)
        self.assertFalse(C.stale_recoverable(st), st)
        # The decision carries the same typed code, so a repair consumer that
        # reads the decision (not the status block) sees it too.
        fresh = self.make_project("fresh-decision", state=fixtures._STATE)
        self.assertIsNone(C.conformance_decision(fresh)["stale_reason"])

    def test_a_current_or_absent_status_carries_no_recoverable_code(self):
        root = self.make_project("current", state=fixtures._STATE)
        fixtures.write_receipt(root, "PASS")
        st = C.conformance_status(root, gate="core")
        self.assertEqual(st["status"], C.STATUS_CURRENT_PASS, st)
        self.assertIsNone(st["stale_reason"])
        self.assertFalse(C.stale_recoverable(st))
        for unknown in (None, {}, {"status": "STALE_FAIL"}, {"stale_reason": "invented"}):
            self.assertFalse(C.stale_recoverable(unknown), unknown)


class DoctorBoundaries(unittest.TestCase):
    def refused(self, status="STALE_PASS"):
        return {"emitted": {
            "ok": False, "code": "CONFORMANCE_UNHEALTHY", "conformance_status": status,
            "canonical_next_command": "saipen validate", "detail": "STATE hash mismatch",
        }, "rc": 1}

    def decision(self, status="CURRENT_PASS"):
        return {"status": status, "healthy": status == "CURRENT_PASS",
                "status_block": {"status": status}, "reason": "measured condition",
                "remediation_command": "saipen validate", "repair_status": "REFRESH_REQUIRED",
                "diagnostic": None}

    def doctor(self, *, validated=None, decision=None, after=None, budget=None):
        validated = validated if validated is not None else {"ok": True, "code": "VALID"}

        def validate(*args):
            print(json.dumps(validated))
            return 0 if validated.get("ok") else 1

        after = after if after is not None else {"emitted": None, "rc": 0}
        with mock.patch.object(CLI, "_negotiate_capability", return_value="full"), \
                mock.patch.object(CLI, "_validate", side_effect=validate) as validator, \
                mock.patch.object(CLI, "_route_once", return_value=after), \
                mock.patch.object(C, "conformance_decision",
                                  return_value=decision or self.decision()):
            result = CLI._auto_doctor(Path("unused"), self.refused(), None,
                                      budget if budget is not None else {"left": 1})
        return result, validator.call_count

    def test_failed_validator_cannot_resume_when_the_new_route_has_no_gate(self):
        result, count = self.doctor(validated={"ok": False, "code": "INSTALL_IDENTITY_MISMATCH"})
        self.assertEqual(count, 1)
        self.assertEqual(result["rc"], 1)
        self.assertEqual(result["emitted"]["code"], "INSTALL_IDENTITY_MISMATCH")
        self.assertFalse(result["emitted"]["doctor"]["ok"])

    def test_a_zero_exit_without_current_receipt_never_resumes(self):
        result, count = self.doctor(decision=self.decision("NOT_RUN"))
        self.assertEqual(count, 1)
        self.assertEqual(result["emitted"]["code"], "CONFORMANCE_UNHEALTHY")
        self.assertEqual(result["emitted"]["conformance_status"], "NOT_RUN")
        self.assertFalse(result["emitted"]["ok"])

    def test_a_new_integrity_refusal_keeps_its_exact_code(self):
        result, _ = self.doctor(after={"emitted": {
            "ok": False, "code": "RECOVERY_CONFLICT", "detail": "op is contested",
        }, "rc": 1})
        self.assertEqual(result["emitted"]["code"], "RECOVERY_CONFLICT")
        self.assertEqual(result["emitted"]["doctor"]["stage"], "BLOCKED")

    def test_spent_shared_budget_prevents_a_second_validation(self):
        result, count = self.doctor(budget={"left": 0})
        self.assertEqual(count, 0)
        self.assertIn("budget", result["emitted"]["doctor"]["why_stopped"])

    def test_unknown_conformance_after_recovery_is_a_real_boundary(self):
        with mock.patch.object(CLI, "_negotiate_capability", return_value="full"), \
                mock.patch.object(CLI, "_validate", side_effect=lambda *_: print(
                    json.dumps({"ok": True, "code": "VALID"})) or 0), \
                mock.patch.object(CLI, "_route_once", return_value={"emitted": None, "rc": 0}), \
                mock.patch.object(C, "conformance_decision", side_effect=OSError("unreadable")):
            result = CLI._auto_doctor(Path("unused"), self.refused(), None, {"left": 1})
        self.assertEqual(result["emitted"]["code"], "CONFORMANCE_UNAVAILABLE")
        self.assertEqual(result["rc"], 1)
        self.assertFalse(result["emitted"]["doctor"]["ok"])

    def test_unrelated_refusals_and_health_do_not_run_the_validator(self):
        for route in ({"emitted": None}, {"emitted": {
            "ok": False, "code": "RECOVERY_REQUIRED", "canonical_next_command": "saipen recover",
        }}, self.refused("CURRENT_FAIL"), self.refused("INVALID_RECEIPT")):
            with self.subTest(route=route), mock.patch.object(CLI, "_validate") as validator:
                self.assertIs(CLI._auto_doctor(Path("unused"), route, None, {"left": 1}), route)
                validator.assert_not_called()

    def test_doctor_auto_reverifies_work_and_resumes(self):
        route = {
            "emitted": {
                "ok": False,
                "code": "CONFORMANCE_UNHEALTHY",
                "conformance_status": "CURRENT_FAIL",
                "canonical_next_command": "saipen work reverify T-104",
                "remediation_commands": ["saipen work reverify T-104"],
                "detail": "closure evidence missing",
            },
            "rc": 1,
        }
        after_route = {"emitted": None, "rc": 0}
        with mock.patch.object(CLI, "_negotiate_capability", return_value="full"), \
                mock.patch("saipen_engine.debt.capture_findings", return_value={"ok": True}), \
                mock.patch("saipen_engine.debt.reverify_work", return_value={"ok": True, "code": "WORK_REVERIFIED"}) as reverify_mock, \
                mock.patch.object(CLI, "_validate", side_effect=lambda *_: print(json.dumps({"ok": True, "code": "VALID"})) or 0) as validator, \
                mock.patch.object(CLI, "_route_once", return_value=after_route), \
                mock.patch.object(C, "conformance_decision", return_value=self.decision("CURRENT_PASS")):
            result = CLI._auto_doctor(Path("unused"), route, None, {"left": 1})
        self.assertEqual(reverify_mock.call_count, 1)
        self.assertEqual(validator.call_count, 1)
        self.assertIsNone(result.get("emitted"))
        self.assertEqual(result["doctor"]["stage"], "RESUMING")
        self.assertEqual(result["doctor"]["operation"], "work-reverify")
        self.assertEqual(result["doctor"]["action"], "saipen work reverify T-104")
        self.assertTrue(result["doctor"]["ok"])

    def test_doctor_dry_run_reverify_plans_and_diagnoses(self):
        route = {
            "emitted": {
                "ok": False,
                "code": "CONFORMANCE_UNHEALTHY",
                "conformance_status": "CURRENT_FAIL",
                "canonical_next_command": "saipen work reverify T-104",
                "remediation_commands": ["saipen work reverify T-104"],
                "detail": "closure evidence missing",
            },
            "rc": 1,
        }
        with mock.patch.object(CLI, "_negotiate_capability", return_value="full"), \
                mock.patch("saipen_engine.debt.reverify_work") as reverify_mock, \
                mock.patch.object(CLI, "_validate") as validator:
            result = CLI._auto_doctor(Path("unused"), route, None, {"left": 1}, dry_run=True)
        reverify_mock.assert_not_called()
        validator.assert_not_called()
        doctor = (result.get("emitted") or {}).get("doctor")
        self.assertIsNotNone(doctor)
        self.assertEqual(doctor["stage"], "DIAGNOSING")
        self.assertEqual(doctor["action"], "saipen work reverify T-104")
        self.assertIn("dry run: the doctor would execute", doctor["why_stopped"])


if __name__ == "__main__":
    unittest.main()
