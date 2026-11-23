"""SRC-344 (audit/28.md) AUT-001: host acceptance must verify its issuer.

The old validator decided trust by (a) comparing fields the caller wrote and
(b) rejecting a list of suspicious substrings in the host name. Both are
answers the same untrusted actor controls, so `accepting_host="invented-host"`
with matching fields returned `(True, "HOST_ACCEPTED", "")` -- reproduced in
`.saipen/evidence/T-1945-trust-repair/TRIAGE.txt`.

These cases deliberately do NOT patch `_broker_verified_receipt`: they are the
real gate. The mechanics suites patch it once in `setUp` because they cover
dispatch behaviour and say so where they do it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import host_dispatch  # noqa: E402


PAYLOAD = {
    "campaign_id": "camp-auto-1",
    "iteration_id": 3,
    "worker_generation": 2,
    "idempotency_key": "idem-abc",
    "project_lineage": "lineage-5f3a",
}


def receipt(**overrides) -> dict:
    """A receipt with EVERY field matching, written by the caller.

    Matching fields are the point: the pre-fix validator called this accepted
    because the only thing it asked was whether two dicts agreed.
    """
    body = {
        "schema_version": 1,
        "status": host_dispatch.HOST_ACCEPTED,
        "campaign_id": PAYLOAD["campaign_id"],
        "iteration_id": PAYLOAD["iteration_id"],
        "worker_generation": PAYLOAD["worker_generation"],
        "idempotency_key": PAYLOAD["idempotency_key"],
        "project_lineage": PAYLOAD["project_lineage"],
        "accepted_request_id": PAYLOAD["idempotency_key"],
        "accepting_host": "zaicode",
    }
    body.update(overrides)
    return body


class HostIdentityIsNotASubstringTest(unittest.TestCase):
    """H01/H02: a host name is a claim, and no live broker reproduces this one."""

    def test_invented_host_is_refused(self) -> None:
        ok, status, detail = host_dispatch.validate_host_acceptance_receipt(
            PAYLOAD, receipt(accepting_host="invented-host")
        )
        self.assertFalse(ok, "an invented host name must not be accepted")
        self.assertEqual(status, host_dispatch.ACCEPTANCE_UNVERIFIED)
        self.assertIn("not authenticated", detail)

    def test_any_plausible_host_name_is_refused_without_a_broker(self) -> None:
        for host in ("zaicode", "claude", "native_scheduler", "invented-host", "x"):
            with self.subTest(host=host):
                ok, status, _detail = host_dispatch.validate_host_acceptance_receipt(
                    PAYLOAD, receipt(accepting_host=host)
                )
                self.assertFalse(ok, f"{host!r} was accepted with no broker answer")
                self.assertEqual(status, host_dispatch.ACCEPTANCE_UNVERIFIED)

    def test_all_matching_fields_do_not_prove_acceptance(self) -> None:
        """H02: field equality is agreement between two caller-written dicts."""
        body = receipt()
        # Every field the validator reads agrees with the payload.
        for field in (
            "campaign_id",
            "iteration_id",
            "worker_generation",
            "idempotency_key",
            "project_lineage",
        ):
            self.assertEqual(body[field], PAYLOAD[field])
        ok, status, _detail = host_dispatch.validate_host_acceptance_receipt(PAYLOAD, body)
        self.assertFalse(ok, "matching fields alone must never be acceptance")
        self.assertEqual(status, host_dispatch.ACCEPTANCE_UNVERIFIED)

    def test_a_broker_answer_is_required_not_a_blacklist(self) -> None:
        """A name containing no banned word is refused; a banned word is too.

        The old rule was a substring blacklist, so this pair distinguishes
        "identity verified" from "name looked suspicious".
        """
        for host in ("invented-host", "unverified", "totally-fake"):
            with self.subTest(host=host):
                ok, _status, _detail = host_dispatch.validate_host_acceptance_receipt(
                    PAYLOAD, receipt(accepting_host=host)
                )
                self.assertFalse(ok)


class PersistedRequestIsNotAcceptanceTest(unittest.TestCase):
    """H03: REQUEST_PERSISTED is the state BEFORE a host accepts."""

    def test_persisted_request_reports_pending(self) -> None:
        ok, status, detail = host_dispatch.validate_host_acceptance_receipt(
            PAYLOAD,
            receipt(status=host_dispatch.DISPATCH_REQUEST_PERSISTED),
        )
        self.assertFalse(ok, "a persisted request must not satisfy acceptance")
        self.assertEqual(status, host_dispatch.DISPATCH_REQUEST_PERSISTED)
        self.assertIn("no host has accepted it yet", detail)

    def test_persisted_request_is_not_reported_as_host_accepted(self) -> None:
        _ok, status, _detail = host_dispatch.validate_host_acceptance_receipt(
            PAYLOAD,
            receipt(status=host_dispatch.DISPATCH_REQUEST_PERSISTED),
        )
        self.assertNotEqual(status, host_dispatch.HOST_ACCEPTED)
        self.assertNotEqual(status, host_dispatch.TURN_STARTED)

    def test_host_accepted_never_implies_turn_started(self) -> None:
        """H10: acceptance and a started turn are separate evidenced states."""
        with mock.patch.object(host_dispatch, "_broker_verified_receipt", return_value=True):
            ok, status, _detail = host_dispatch.validate_host_acceptance_receipt(
                PAYLOAD, receipt(status=host_dispatch.HOST_ACCEPTED)
            )
        self.assertTrue(ok)
        self.assertEqual(status, host_dispatch.HOST_ACCEPTED)
        self.assertNotEqual(status, host_dispatch.TURN_STARTED)


class MalformedReceiptIsATypedRefusalTest(unittest.TestCase):
    """H04/H05: malformed numbers refuse; they do not raise out of the gate."""

    def test_non_numeric_iteration_id_does_not_raise(self) -> None:
        try:
            ok, status, detail = host_dispatch.validate_host_acceptance_receipt(
                PAYLOAD, receipt(iteration_id="not-an-int")
            )
        except Exception as exc:
            self.fail(f"malformed iteration_id raised {type(exc).__name__}: {exc}")
        self.assertFalse(ok)
        self.assertEqual(status, host_dispatch.ACCEPTANCE_UNVERIFIED)
        self.assertIn("iteration_id", detail)

    def test_non_numeric_worker_generation_does_not_raise(self) -> None:
        try:
            ok, status, detail = host_dispatch.validate_host_acceptance_receipt(
                PAYLOAD, receipt(worker_generation="x")
            )
        except Exception as exc:
            self.fail(f"malformed worker_generation raised {type(exc).__name__}: {exc}")
        self.assertFalse(ok)
        self.assertEqual(status, host_dispatch.ACCEPTANCE_UNVERIFIED)
        self.assertIn("worker_generation", detail)

    def test_boolean_is_not_an_integer_field(self) -> None:
        for field in ("iteration_id", "worker_generation"):
            with self.subTest(field=field):
                ok, status, detail = host_dispatch.validate_host_acceptance_receipt(
                    PAYLOAD, receipt(**{field: True})
                )
                self.assertFalse(ok)
                self.assertEqual(status, host_dispatch.ACCEPTANCE_UNVERIFIED)
                self.assertIn("boolean", detail)

    def test_numeric_strings_still_compare(self) -> None:
        """A JSON round-trip yields strings; a right answer must still pass."""
        with mock.patch.object(host_dispatch, "_broker_verified_receipt", return_value=True):
            ok, status, _detail = host_dispatch.validate_host_acceptance_receipt(
                PAYLOAD, receipt(iteration_id="3", worker_generation="2")
            )
        self.assertTrue(ok, "a numeric string of the right value is not malformed")
        self.assertEqual(status, host_dispatch.HOST_ACCEPTED)


class BoundReceiptFieldsTest(unittest.TestCase):
    """H06/H07: lineage and identity still bind when the issuer is trusted."""

    def test_wrong_project_lineage_is_refused(self) -> None:
        with mock.patch.object(host_dispatch, "_broker_verified_receipt", return_value=True):
            ok, status, detail = host_dispatch.validate_host_acceptance_receipt(
                PAYLOAD, receipt(project_lineage="lineage-other")
            )
        self.assertFalse(ok)
        self.assertEqual(status, host_dispatch.ACCEPTANCE_UNVERIFIED)
        self.assertIn("project_lineage", detail)

    def test_wrong_iteration_is_refused_even_when_trusted(self) -> None:
        with mock.patch.object(host_dispatch, "_broker_verified_receipt", return_value=True):
            ok, status, detail = host_dispatch.validate_host_acceptance_receipt(
                PAYLOAD, receipt(iteration_id=9)
            )
        self.assertFalse(ok)
        self.assertEqual(status, host_dispatch.ACCEPTANCE_UNVERIFIED)
        self.assertIn("iteration_id", detail)

    def test_missing_request_identity_is_refused_for_that_reason(self) -> None:
        """Structural defects are named before the trust verdict.

        This ordering matters: telling a caller "unauthenticated" about a
        receipt that is missing a required field hides the field it must add.
        """
        body = receipt()
        for field in ("accepted_request_id", "request_id", "request_digest"):
            body.pop(field, None)
        ok, status, detail = host_dispatch.validate_host_acceptance_receipt(PAYLOAD, body)
        self.assertFalse(ok)
        self.assertEqual(status, host_dispatch.ACCEPTANCE_UNVERIFIED)
        self.assertIn("request identity", detail)


class TrustedIssuerTest(unittest.TestCase):
    """H09: with a broker that does reproduce the record, acceptance is real."""

    def test_verified_receipt_is_accepted_for_the_exact_operation(self) -> None:
        with mock.patch.object(host_dispatch, "_broker_verified_receipt", return_value=True):
            ok, status, detail = host_dispatch.validate_host_acceptance_receipt(
                PAYLOAD, receipt()
            )
        self.assertTrue(ok, detail)
        self.assertEqual(status, host_dispatch.HOST_ACCEPTED)

    def test_a_verified_receipt_for_another_request_is_still_refused(self) -> None:
        """Trust answers "who wrote this", never "which request it answers"."""
        with mock.patch.object(host_dispatch, "_broker_verified_receipt", return_value=True):
            ok, status, _detail = host_dispatch.validate_host_acceptance_receipt(
                PAYLOAD, receipt(idempotency_key="idem-DIFFERENT")
            )
        self.assertFalse(ok)
        self.assertEqual(status, host_dispatch.ACCEPTANCE_UNVERIFIED)

    def test_the_broker_boundary_is_the_shared_one(self) -> None:
        """AUT-001 asks for the established boundary, not a second inventory."""
        from saipen_engine import host_authority_client

        with mock.patch.object(
            host_authority_client, "verify_record", return_value=False
        ) as guard:
            ok, _status, _detail = host_dispatch.validate_host_acceptance_receipt(
                PAYLOAD, receipt()
            )
        self.assertFalse(ok, "the shared boundary answering False must refuse")
        self.assertTrue(guard.called, "the shared verify_record must be consulted")

    def test_an_unsealed_record_is_refused_by_the_shared_boundary(self) -> None:
        """No live broker means no acceptance -- not "probably fine"."""
        ok, status, detail = host_dispatch.validate_host_acceptance_receipt(
            PAYLOAD, receipt()
        )
        self.assertFalse(ok)
        self.assertEqual(status, host_dispatch.ACCEPTANCE_UNVERIFIED)
        self.assertIn("not authenticated", detail)


if __name__ == "__main__":
    unittest.main()
