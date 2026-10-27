"""T-1913 / SRC-324 Gap B: issue_operator_origin bounded service recovery.

Defect: issue_operator_origin used a bare broker exchange while attempt_admission
had a bounded service-recovery lifecycle, so an absent broker left the hook unsealed
with no recovery.

Controls:
1. An absent broker is classified as recoverable and, where the existing
   hook-invocation proof permits it, the same trusted service is started and
   the original event identity seals within the hook budget.
2. An impostor endpoint is never replaced and never started over.
3. A failed recovery returns the exact stage and refusal code.
4. No retry storm: bounded attempts (at most 1 connect, 1 start, 1 retry).
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


def _load_guard():
    path = ROOT / "extensions" / "adapters" / "zaicode" / "saipen-guard.py"
    spec = importlib.util.spec_from_file_location("saipen_guard_zaicode_t1913", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GUARD = _load_guard()


class OriginRecoveryLifecycleTests(unittest.TestCase):
    """SRC-324 Gap B: bounded recovery for issue_operator_origin."""

    def test_absent_broker_with_hook_proof_recovers_and_seals(self):
        """An absent broker triggers ensure() and retries with the original event."""
        payloads_seen = []

        def fake_exchange(payload, runtime=None, timeout=None):
            payloads_seen.append(dict(payload))
            if len(payloads_seen) == 1:
                return None, "absent"
            proof = {
                "schema": 1,
                "kind": "operator-origin",
                "host": "zaicode",
                "nonce": "nonce-rec-1",
                "event_id": payload.get("event_id"),
                "action": payload.get("action"),
            }
            return {"ok": True, "code": None, "proof": proof}, None

        fake_ensure = mock.Mock(return_value={
            "ok": True, "state": "started", "started": True, "attempts": 2,
        })

        with mock.patch.object(HAC, "_exchange", side_effect=fake_exchange):
            with mock.patch.object(HAC, "ensure", fake_ensure):
                reply, fault = HAC.issue_operator_origin(
                    project=ROOT,
                    session="sess-1",
                    host="zaicode",
                    request_text="cc all",
                    event_id="turn-42",
                    action="continue",
                    diagnose=True,
                )

        self.assertIsNone(fault)
        self.assertIsNotNone(reply)
        self.assertTrue(reply.get("ok"))
        self.assertEqual(reply.get("proof", {}).get("event_id"), "turn-42")
        self.assertEqual(reply.get("proof", {}).get("nonce"), "nonce-rec-1")

        # ensure was called exactly once with host and saipen_root
        fake_ensure.assert_called_once()
        self.assertEqual(fake_ensure.call_args[1].get("host"), "zaicode")

        # _exchange was called exactly twice with identical event identity
        self.assertEqual(len(payloads_seen), 2)
        self.assertEqual(payloads_seen[0]["event_id"], "turn-42")
        self.assertEqual(payloads_seen[1]["event_id"], "turn-42")
        self.assertEqual(payloads_seen[0]["request_text"], "cc all")
        self.assertEqual(payloads_seen[1]["request_text"], "cc all")

        # Recovery metadata recorded the lifecycle
        recovery = reply.get("recovery")
        self.assertIsNotNone(recovery)
        self.assertEqual(recovery.get("attempted"), ["connect", "start", "retry"])
        self.assertTrue(recovery.get("started"))

    def test_impostor_endpoint_is_never_replaced_or_retried(self):
        """An impostor failure must NEVER trigger ensure() or start a second service."""
        fake_ensure = mock.Mock()
        exchange_calls = []

        def fake_exchange(payload, runtime=None, timeout=None):
            exchange_calls.append(payload)
            return None, "impostor"

        with mock.patch.object(HAC, "_exchange", side_effect=fake_exchange):
            with mock.patch.object(HAC, "ensure", fake_ensure):
                reply, fault = HAC.issue_operator_origin(
                    project=ROOT,
                    session="sess-1",
                    host="zaicode",
                    request_text="cc",
                    event_id="turn-imp",
                    action="continue",
                    diagnose=True,
                )

        self.assertIsNone(reply)
        self.assertEqual(fault, "impostor")
        fake_ensure.assert_not_called()
        self.assertEqual(len(exchange_calls), 1)

        # Passes through guard diagnostic to ORIGIN_ENDPOINT_UNTRUSTED
        diagnostic = GUARD.seal_diagnostic(reply, fault, None, None, False)
        self.assertFalse(diagnostic["ok"])
        self.assertEqual(diagnostic["stage"], "issue-origin")
        self.assertEqual(diagnostic["code"], "ORIGIN_ENDPOINT_UNTRUSTED")
        self.assertEqual(diagnostic["category"], "untrusted")

    def test_absent_broker_unauthorized_client_does_not_retry(self):
        """When ensure() refuses (e.g. not a hook client), no retry is attempted."""
        payloads_seen = []

        def fake_exchange(payload, runtime=None, timeout=None):
            payloads_seen.append(payload)
            return None, "absent"

        fake_ensure = mock.Mock(return_value={
            "ok": False,
            "state": "not_a_host_client",
            "code": HAC.CODE_NOT_HOST_CLIENT,
            "detail": "not a registered host application hook",
        })

        with mock.patch.object(HAC, "_exchange", side_effect=fake_exchange):
            with mock.patch.object(HAC, "ensure", fake_ensure):
                reply, fault = HAC.issue_operator_origin(
                    project=ROOT,
                    session="sess-1",
                    host="zaicode",
                    request_text="cc",
                    event_id="turn-non-hook",
                    action="continue",
                    diagnose=True,
                )

        self.assertIsNotNone(reply)
        self.assertFalse(reply.get("ok"))
        self.assertEqual(reply.get("code"), HAC.CODE_NOT_HOST_CLIENT)
        self.assertEqual(fault, "absent")
        fake_ensure.assert_called_once()
        # Exactly 1 connect attempt - no retry storm!
        self.assertEqual(len(payloads_seen), 1)

        # Passes through guard diagnostic to the exact refusal code
        diagnostic = GUARD.seal_diagnostic(reply, fault, None, None, False)
        self.assertFalse(diagnostic["ok"])
        self.assertEqual(diagnostic["stage"], "issue-origin")
        self.assertEqual(diagnostic["code"], HAC.CODE_NOT_HOST_CLIENT)
        self.assertEqual(diagnostic["category"], "refused")

    def test_retry_failure_returns_exact_broker_refusal_code(self):
        """If the broker starts but refuses the request on retry, the exact code is kept."""
        payloads_seen = []

        def fake_exchange(payload, runtime=None, timeout=None):
            payloads_seen.append(payload)
            if len(payloads_seen) == 1:
                return None, "absent"
            return {"ok": False, "code": "BROKER_HASH_MISMATCH", "detail": "checksum drift"}, None

        fake_ensure = mock.Mock(return_value={"ok": True, "state": "started", "started": True})

        with mock.patch.object(HAC, "_exchange", side_effect=fake_exchange):
            with mock.patch.object(HAC, "ensure", fake_ensure):
                reply, fault = HAC.issue_operator_origin(
                    project=ROOT,
                    session="sess-1",
                    host="zaicode",
                    request_text="cc",
                    event_id="turn-refused",
                    action="continue",
                    diagnose=True,
                )

        self.assertIsNone(fault)
        self.assertIsNotNone(reply)
        self.assertFalse(reply.get("ok"))
        self.assertEqual(reply.get("code"), "BROKER_HASH_MISMATCH")

        diagnostic = GUARD.seal_diagnostic(reply, fault, None, None, False)
        self.assertFalse(diagnostic["ok"])
        self.assertEqual(diagnostic["stage"], "issue-origin")
        self.assertEqual(diagnostic["code"], "BROKER_HASH_MISMATCH")
        self.assertEqual(diagnostic["category"], "refused")

    def test_retry_transport_timeout_is_bounded_and_classified(self):
        """If retry times out, no further retry is attempted and timeout is reported."""
        payloads_seen = []

        def fake_exchange(payload, runtime=None, timeout=None):
            payloads_seen.append(payload)
            if len(payloads_seen) == 1:
                return None, "absent"
            return None, "timeout"

        fake_ensure = mock.Mock(return_value={"ok": True, "state": "started", "started": True})

        with mock.patch.object(HAC, "_exchange", side_effect=fake_exchange):
            with mock.patch.object(HAC, "ensure", fake_ensure):
                reply, fault = HAC.issue_operator_origin(
                    project=ROOT,
                    session="sess-1",
                    host="zaicode",
                    request_text="cc",
                    event_id="turn-timeout",
                    action="continue",
                    diagnose=True,
                )

        self.assertIsNotNone(reply)
        self.assertFalse(reply.get("ok"))
        self.assertEqual(reply.get("code"), "BROKER_RECOVERY_TIMEOUT")
        self.assertEqual(fault, "timeout")
        # Bounded: 1 connect, 1 retry = 2 total
        self.assertEqual(len(payloads_seen), 2)

        diagnostic = GUARD.seal_diagnostic(reply, fault, None, None, False)
        self.assertEqual(diagnostic["stage"], "issue-origin")
        self.assertEqual(diagnostic["code"], "BROKER_RECOVERY_TIMEOUT")
        self.assertEqual(diagnostic["category"], "unavailable")

    def test_explicit_runtime_does_not_call_ensure(self):
        """An explicit diagnostic runtime is taken as given without ensure()."""
        fake_ensure = mock.Mock()
        with mock.patch.object(HAC, "_exchange", return_value=(None, "absent")):
            with mock.patch.object(HAC, "ensure", fake_ensure):
                reply, fault = HAC.issue_operator_origin(
                    project=ROOT,
                    session="sess-1",
                    host="zaicode",
                    request_text="cc",
                    event_id="turn-diag",
                    action="continue",
                    runtime=Path("/tmp/diagnostic-runtime"),
                    diagnose=True,
                )
        fake_ensure.assert_not_called()
        self.assertEqual(fault, "absent")


if __name__ == "__main__":
    unittest.main()
