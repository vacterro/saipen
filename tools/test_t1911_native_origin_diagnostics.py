"""T-1911 / SRC-324: an unsealed native envelope must say why, and a typed
host continuation must stay a continuation.

Measured incident: the ZAICODE hook tried to seal an operator origin, failed,
and still printed the admission answer (`ok: true, sealed: false`). The broker
refusal and the failing stage were discarded, so a genuine operator prompt was
recorded as `model_supplied` with no actionable diagnostic -- and the protected
continuation stayed refused.

Control on the other half: the native CLI delivers its continuation as
`/goal cc all`, which `is_continuation_command` did not read as one, while
ordinary prose containing "cc" must never become one.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import host_authority_client as HAC  # noqa: E402
from saipen_engine.cold_recovery import is_continuation_command  # noqa: E402
from saipen_engine.host_authority_transport import TransportError  # noqa: E402


def _load_guard():
    path = ROOT / "extensions" / "adapters" / "zaicode" / "saipen-guard.py"
    spec = importlib.util.spec_from_file_location("saipen_guard_zaicode_t1911", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GUARD = _load_guard()


class ContinuationContractTests(unittest.TestCase):
    """SRC-324 Gap C: one typed contract for the native continuation action."""

    def test_shortcut_spellings_remain_continuations(self):
        for text in ("cc", "cc all", "saipen continue"):
            with self.subTest(text=text):
                self.assertTrue(is_continuation_command(text), text)

    def test_typed_host_command_body_is_a_continuation(self):
        self.assertTrue(is_continuation_command("/goal cc all"))

    def test_prose_containing_cc_is_never_a_continuation(self):
        for text in (
            "recover and restore cc",
            "please cc me on the report",
            "/goal summarize cc usage",
            "/goal",
            "cc all the things, then tell me why",
        ):
            with self.subTest(text=text):
                self.assertFalse(is_continuation_command(text), text)


class SealDiagnosticTests(unittest.TestCase):
    """SRC-324 Gap A: the sealing half answers with a stage and a code."""

    def _diagnose(self, origin, fault=None, worker=None, worker_fault=None, sealed=False):
        return GUARD.seal_diagnostic(origin, fault, worker, worker_fault, sealed)

    def test_sealed_origin_reports_the_authenticated_stage(self):
        seal = self._diagnose({"ok": True}, worker={"ok": True}, sealed=True)
        self.assertTrue(seal["ok"], seal)
        self.assertEqual(seal["stage"], "sealed")
        self.assertEqual(seal["category"], "authenticated")

    def test_absent_service_is_distinguished_from_a_refusal(self):
        absent = self._diagnose(None, "absent")
        self.assertFalse(absent["ok"], absent)
        self.assertEqual(absent["stage"], "issue-origin")
        self.assertEqual(absent["code"], "ORIGIN_SERVICE_UNAVAILABLE")
        self.assertEqual(absent["category"], "unavailable")

        refused = self._diagnose({"ok": False, "code": "BROKER_REFUSED_IDENTITY"})
        self.assertEqual(refused["code"], "BROKER_REFUSED_IDENTITY")
        self.assertEqual(refused["category"], "refused")
        self.assertEqual(refused["stage"], "issue-origin")

    def test_impostor_endpoint_is_never_reported_as_recoverable_absence(self):
        seal = self._diagnose(None, "impostor")
        self.assertEqual(seal["code"], "ORIGIN_ENDPOINT_UNTRUSTED")
        self.assertEqual(seal["category"], "untrusted")

    def test_worker_registration_failure_is_its_own_stage(self):
        seal = self._diagnose(
            {"ok": True},
            worker={"ok": False, "code": "WORKER_NOT_HOST_CHILD"},
        )
        self.assertEqual(seal["stage"], "register-worker")
        self.assertEqual(seal["code"], "WORKER_NOT_HOST_CHILD")
        self.assertEqual(seal["category"], "refused")

        lost = self._diagnose({"ok": True}, worker=None, worker_fault="timeout")
        self.assertEqual(lost["stage"], "register-worker")
        self.assertEqual(lost["code"], "WORKER_SERVICE_UNAVAILABLE")

    def test_no_reply_and_no_fault_still_names_a_code(self):
        seal = self._diagnose(None)
        self.assertEqual(seal["code"], "ORIGIN_UNREACHABLE")
        self.assertFalse(seal["ok"])


class OriginFaultSeamTests(unittest.TestCase):
    """The plain client call discards the transport kind; the diagnostic keeps it."""

    def test_diagnose_returns_the_transport_fault(self):
        def refuse(*_args, **_kwargs):
            raise TransportError("absent", "no endpoint")

        with mock.patch.object(HAC.broker, "request", side_effect=refuse):
            self.assertIsNone(
                HAC.issue_operator_origin(
                    project=ROOT, session="s", host="zaicode", request_text="cc",
                    event_id="m-1", action="continue",
                )
            )
            reply, fault = HAC.issue_operator_origin(
                project=ROOT, session="s", host="zaicode", request_text="cc",
                event_id="m-1", action="continue", diagnose=True,
            )
        self.assertIsInstance(reply, dict)
        self.assertEqual(reply["code"], HAC.CODE_NOT_HOST_CLIENT)
        self.assertEqual(reply["recovery"]["state"], "not_a_host_client")
        self.assertEqual(fault, "absent")

    def test_impostor_fault_is_not_flattened_into_absence(self):
        def refuse(*_args, **_kwargs):
            raise TransportError("impostor", "not the service")

        with mock.patch.object(HAC.broker, "request", side_effect=refuse):
            reply, fault = HAC.register_operator_worker(
                {"kind": "operator-origin", "host": "zaicode"}, 1234, diagnose=True
            )
        self.assertIsNone(reply)
        self.assertEqual(fault, "impostor")


if __name__ == "__main__":
    unittest.main()
