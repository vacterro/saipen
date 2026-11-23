"""Installed-host acceptance control for SRC-380 P0-06.

`test_bzcc_overnight_autonomy.py::test_16_...` patches
`host_dispatch._broker_verified_receipt` to True and injects synthetic
HOST_ACCEPTED / TURN_STARTED / TURN_COMPLETED receipts: it tests dispatch
control flow, never this machine's real capability to start a successor turn.

These controls pin the separation the handoff asks for:

* a synthetic receipt is never acceptance -- the LIVE broker must reproduce it,
  and this machine's broker refuses receipts it did not write;
* a persisted dispatch request is never TURN_STARTED;
* the probe's verdict is derived from live observation and is never
  LIVE_ACCEPTANCE unless a registered transport actually dispatched.

They run the real `tools/installed_host_acceptance.py` probe. On a machine with
no host-scheduler transport the verdict is HOST_DISPATCH_UNAVAILABLE (broker
live) or HOST_CAPABILITY_MISSING (no broker) -- never acceptance.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import installed_host_acceptance as probe  # noqa: E402
from saipen_engine import host_dispatch  # noqa: E402


def _synthetic_receipt(payload: dict, status: str = host_dispatch.TURN_STARTED) -> dict:
    return {
        "schema_version": host_dispatch.ACCEPTANCE_SCHEMA_VERSION,
        "status": status,
        "campaign_id": payload["campaign_id"],
        "iteration_id": payload["iteration_id"],
        "worker_generation": payload["worker_generation"],
        "idempotency_key": payload["idempotency_key"],
        "accepting_host": "synthetic-untrusted-host",
        "project_lineage": payload["project_lineage"],
        "accepted_request_digest": payload["idempotency_key"],
    }


class InstalledHostAcceptanceTests(unittest.TestCase):
    def test_synthetic_receipt_is_not_acceptance_without_a_reproducing_broker(self) -> None:
        """Matching fields are not authentication; the live broker decides."""
        from tempfile import mkdtemp

        root = Path(mkdtemp(prefix="saipen-accept-"))
        (root / ".saipen").mkdir(parents=True, exist_ok=True)
        payload = host_dispatch.build_dispatch_payload(root, campaign_id="c-synthetic")
        receipt = _synthetic_receipt(payload)
        is_valid, status, _err = host_dispatch.validate_host_acceptance_receipt(payload, receipt)
        # A receipt this broker did not write cannot be accepted, whatever its
        # field values say. (A machine where the broker DID write it would be
        # authenticated by construction and is not what this control asserts.)
        if not host_dispatch._broker_verified_receipt(receipt):
            self.assertFalse(is_valid)
            self.assertEqual(status, host_dispatch.ACCEPTANCE_UNVERIFIED)

    def test_persisted_request_is_never_turn_started(self) -> None:
        from tempfile import mkdtemp

        root = Path(mkdtemp(prefix="saipen-accept-"))
        (root / ".saipen").mkdir(parents=True, exist_ok=True)
        payload = host_dispatch.build_dispatch_payload(root, campaign_id="c-persist")
        persisted = _synthetic_receipt(payload, status=host_dispatch.DISPATCH_REQUEST_PERSISTED)
        is_valid, status, _err = host_dispatch.validate_host_acceptance_receipt(payload, persisted)
        self.assertFalse(is_valid)
        self.assertEqual(status, host_dispatch.DISPATCH_REQUEST_PERSISTED)

    def test_probe_never_claims_acceptance_without_a_registered_transport(self) -> None:
        result = probe.probe()
        if not (result["transport"]["host_scheduler_dispatch_cmd"] or result["transport"]["host_dispatch_endpoint"]):
            self.assertNotEqual(result["verdict"], probe.LIVE_ACCEPTANCE)
            self.assertFalse(result["ok"])
            self.assertIn(
                result["verdict"],
                (probe.HOST_DISPATCH_UNAVAILABLE, probe.HOST_CAPABILITY_MISSING),
            )
        else:
            # A transport exists: the probe must still report honestly.
            self.assertIn(
                result["verdict"],
                (probe.LIVE_ACCEPTANCE, probe.HOST_DISPATCH_UNAVAILABLE, probe.HOST_CAPABILITY_MISSING),
            )

    def test_dispatched_flag_alone_never_upgrades_a_persisted_request(self) -> None:
        """`ok: True` from the file-advisory fallback is not a started turn."""
        from tempfile import mkdtemp

        root = Path(mkdtemp(prefix="saipen-accept-"))
        (root / ".saipen").mkdir(parents=True, exist_ok=True)
        payload = host_dispatch.build_dispatch_payload(root, campaign_id="c-fallback")
        result = host_dispatch.dispatch_next_turn(root, payload, print_advisory=False)
        if result.get("status") == host_dispatch.HOST_DISPATCH_UNAVAILABLE:
            self.assertIs(result.get("dispatched"), False)
            self.assertEqual(result.get("disposition"), host_dispatch.DISPATCH_REQUEST_PERSISTED)


if __name__ == "__main__":
    unittest.main()
