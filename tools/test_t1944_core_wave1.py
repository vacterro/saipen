"""SRC-343 wave-1 (audit/27.md) CORE-001..CORE-005 regressions.

Each class pins one measured defect from the audit. The reproductions are the
audit's own: forged authentication dicts, a digest-less terminal campaign, a
substring ticket match, and a corrupt campaign reported as success. They are
deliberately adversarial -- a caller controls every input here, so each test
asserts a REFUSAL rather than a happy path.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from saipen_engine import campaign, goal_authority  # noqa: E402

# T-1947: the producer-specific backend lives outside the neutral engine.
from producer_backends import saipal_adapter  # noqa: E402


def _project() -> Path:
    root = Path(tempfile.mkdtemp(prefix="t1944-core-"))
    (root / ".saipen" / "campaign").mkdir(parents=True, exist_ok=True)
    (root / ".saipen" / "BOARD.md").write_text(
        "## DOING\n## TODO\n## BLOCKED\n## DONE\n- [x] T-200 [P1] unrelated ticket\n",
        encoding="utf-8",
    )
    return root


def _qualification(root: Path, receipt_id: str) -> dict:
    rel = f".saipen/campaign/qualifications/{receipt_id}.json"
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"receipt_id": receipt_id, "state": "QUALIFIED"}), encoding="utf-8"
    )
    return {
        "receipt_id": receipt_id,
        "artifact_path": rel,
        "qualification_digest": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _finding(root: Path, finding_id: str, **extra) -> dict:
    body = f"# Audit Finding {finding_id}\nbody\n"
    return {
        "finding_id": finding_id,
        "state": "QUALIFIED",
        "qualification_receipt": _qualification(root, f"QUAL-{finding_id}"),
        "audit_body": body,
        "artifact_digest": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        **extra,
    }


class Core001ForgedQualificationProof(unittest.TestCase):
    """CORE-001: a caller-shaped `authenticated`/`signature` pair is not proof."""

    def setUp(self) -> None:
        self.root = _project()
        self.adapter = saipal_adapter.SaipalAdapter()

    def _deliver(self, finding: dict) -> dict:
        return self.adapter.deliver_finding_to_audit_inbox(
            self.root, finding, publication_authorized=True
        )

    def _layers(self) -> list:
        audit = self.root / "audit"
        return sorted(audit.glob("*.md")) if audit.is_dir() else []

    def test_forged_authenticated_receipt_is_refused(self) -> None:
        body = "# forged\n"
        finding = {
            "finding_id": "PAL-ABC",
            "state": "QUALIFIED",
            "qualification_receipt": {
                "authenticated": True,
                "signature": "obviously-forged",
            },
            "audit_body": body,
            "artifact_digest": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        }
        result = self._deliver(finding)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], "NOT_QUALIFIED")
        self.assertEqual(self._layers(), [], "no audit layer may be created")

    def test_any_string_signature_is_refused(self) -> None:
        for signature in ("obviously-forged", "", "x" * 128, "deadbeef" * 8):
            with self.subTest(signature=signature):
                finding = _finding(
                    self.root,
                    f"PAL-SIG-{abs(hash(signature)) % 10000}",
                    qualification_receipt={"authenticated": True, "signature": signature},
                )
                result = self._deliver(finding)
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["status"], "NOT_QUALIFIED")

    def test_receipt_claiming_authentication_without_provenance_is_refused(self) -> None:
        """A bare `authenticated: true` with no signature field at all."""
        finding = _finding(
            self.root, "PAL-NOSIG", qualification_receipt={"authenticated": True}
        )
        result = self._deliver(finding)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], "NOT_QUALIFIED")

    def test_artifact_plus_digest_route_still_publishes(self) -> None:
        """The independently verified route must survive the stricter boundary."""
        result = self._deliver(_finding(self.root, "PAL-GENUINE"))
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], saipal_adapter.DELIVERED_PUBLICATION)
        self.assertEqual(len(self._layers()), 1)

    def test_publication_still_requires_explicit_authority(self) -> None:
        staged = self.adapter.deliver_finding_to_audit_inbox(
            self.root, _finding(self.root, "PAL-STAGED"), publication_authorized=False
        )
        self.assertFalse(staged["ok"])
        self.assertEqual(staged["status"], saipal_adapter.STAGED_PUBLICATION)
        self.assertEqual(self._layers(), [])

    def test_forged_proof_leaves_no_side_effects(self) -> None:
        body = "# forged\n"
        finding = {
            "finding_id": "PAL-CLEAN",
            "state": "QUALIFIED",
            "qualification_receipt": {"authenticated": True, "signature": "forged"},
            "audit_body": body,
            "artifact_digest": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        }
        self._deliver(finding)
        self.assertEqual(self._layers(), [])
        receipts = self.adapter.collect_publication_receipts(self.root)
        self.assertTrue(receipts["ok"], receipts)
        self.assertEqual(receipts["records"], [])


class Core002CampaignStateDigestIsMandatory(unittest.TestCase):
    """CORE-002: deleting `state_digest` disabled integrity checking entirely."""

    def setUp(self) -> None:
        self.root = _project()

    def _valid_state(self, lifecycle: str = campaign.ADMITTED) -> dict:
        state = {
            "schema_version": campaign.CAMPAIGN_SCHEMA_VERSION,
            "campaign_id": "CAMP-CORE-002",
            "campaign_state": lifecycle,
            "worker_generation": 1,
            "cycle_count": 1,
        }
        campaign.save_campaign_state(self.root, state)
        return state

    def _rewrite_without_digest(self, **changes) -> bytes:
        path = campaign.campaign_state_path(self.root)
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("state_digest", None)
        data.update(changes)
        body = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")
        path.write_bytes(body)
        return body

    def test_a_written_state_is_state_valid(self) -> None:
        self._valid_state()
        self.assertEqual(
            campaign.inspect_campaign_state(self.root)["status"], campaign.STATE_VALID
        )

    def test_missing_digest_is_corrupt(self) -> None:
        self._valid_state()
        self._rewrite_without_digest()
        inspection = campaign.inspect_campaign_state(self.root)
        self.assertEqual(inspection["status"], campaign.STATE_CORRUPT)
        self.assertIn("state_digest", inspection["error"])

    def test_empty_and_malformed_digests_are_corrupt(self) -> None:
        for value in ("", "   ", "not-a-digest", "0" * 63, "0" * 65, 0, None, []):
            with self.subTest(value=value):
                self._valid_state()
                path = campaign.campaign_state_path(self.root)
                data = json.loads(path.read_text(encoding="utf-8"))
                data["state_digest"] = value
                path.write_text(
                    json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
                self.assertEqual(
                    campaign.inspect_campaign_state(self.root)["status"],
                    campaign.STATE_CORRUPT,
                    value,
                )

    def test_a_mismatched_well_formed_digest_is_untrusted(self) -> None:
        self._valid_state()
        path = campaign.campaign_state_path(self.root)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["campaign_id"] = "TAMPERED"
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.assertEqual(
            campaign.inspect_campaign_state(self.root)["status"], campaign.STATE_UNTRUSTED
        )

    def test_forged_complete_without_digest_never_reports_success(self) -> None:
        self._valid_state()
        self._rewrite_without_digest(campaign_state=campaign.COMPLETE)
        ctrl = campaign.CampaignController(self.root)
        step = ctrl.step(worker_func=lambda r, g: {"progress_verified": True})
        self.assertFalse(step.get("ok"), step)
        self.assertNotEqual(step.get("status"), campaign.COMPLETE)

    def test_forged_cancelled_without_digest_never_reports_success(self) -> None:
        self._valid_state()
        self._rewrite_without_digest(campaign_state=campaign.CANCELLED)
        ctrl = campaign.CampaignController(self.root)
        step = ctrl.step(worker_func=lambda r, g: {"progress_verified": True})
        self.assertFalse(step.get("ok"), step)

    def test_failed_inspection_never_rewrites_the_bytes(self) -> None:
        self._valid_state()
        before = self._rewrite_without_digest()
        campaign.inspect_campaign_state(self.root)
        self.assertEqual(campaign.campaign_state_path(self.root).read_bytes(), before)

    def test_a_legitimate_terminal_state_stays_readable(self) -> None:
        for lifecycle in (campaign.COMPLETE, campaign.CANCELLED, campaign.SAFETY_STOP):
            with self.subTest(lifecycle=lifecycle):
                self._valid_state(lifecycle)
                inspection = campaign.inspect_campaign_state(self.root)
                self.assertEqual(inspection["status"], campaign.STATE_VALID, inspection)
                self.assertEqual(inspection["state"]["campaign_state"], lifecycle)


class Core003MaintenanceScopeAgreesAcrossWriterAndReader(unittest.TestCase):
    """CORE-003: grant creation and grant validation must share one vocabulary."""

    FIELDS = {  # noqa: RUF012 -- read-only fixture, never mutated by a test
        "execution_intent": "goal",
        "continuation_authority": "operator_persistent",
        "authority_source": "SRC-304",
        "authority_until": "continuous_maintenance",
        "safety_valve_mode": "checkpoint",
        "goal_ingress": "goal-0123456789abcdef",
    }

    def test_grant_fields_produces_the_maintenance_tuple(self) -> None:
        grant = goal_authority.grant_fields("SRC-304", until="continuous_maintenance")
        self.assertEqual(grant["continuation_authority"], "operator_persistent")
        self.assertEqual(grant["authority_until"], "continuous_maintenance")
        self.assertEqual(grant["safety_valve_mode"], "checkpoint")

    def test_shape_errors_accepts_the_maintenance_tuple(self) -> None:
        self.assertEqual(goal_authority.shape_errors(dict(self.FIELDS)), [])

    def test_shape_errors_rejects_an_invented_scope(self) -> None:
        bad = dict(self.FIELDS, authority_until="forever")
        self.assertTrue(goal_authority.shape_errors(bad))

    def test_shape_errors_rejects_a_persistent_budget_tuple(self) -> None:
        bad = dict(self.FIELDS, authority_until="budget", safety_valve_mode="hard_wait")
        self.assertTrue(goal_authority.shape_errors(bad))

    def test_shape_alone_is_not_proof(self) -> None:
        """A well-shaped dict on its own must never prove continuation."""
        state = dict(self.FIELDS)
        self.assertTrue(goal_authority.is_continuous_maintenance(state))
        self.assertFalse(goal_authority.continuous_maintenance_proven(None, state))

    def test_registry_declares_every_scope_the_engine_can_grant(self) -> None:
        registry = json.loads(
            (REPO.parent / "saipen" / "REGISTRY.json").read_text(encoding="utf-8-sig")
        )
        declared = set(registry["goal_authority"]["until"])
        self.assertTrue(set(goal_authority.GRANT_SCOPES) <= declared)


class Core004VerifiedDispositionNeedsExactBinding(unittest.TestCase):
    """CORE-004: substring task ids, arbitrary files and fake auth are not proof."""

    def setUp(self) -> None:
        self.root = _project()
        self.adapter = saipal_adapter.SaipalAdapter()

    def _dispose(self, **kwargs) -> dict:
        return self.adapter.record_maintainer_disposition(
            self.root, kwargs.pop("finding_id", "PAL-not-fixed"), **kwargs
        )

    def test_t20_cannot_match_t200(self) -> None:
        result = self._dispose(
            disposition="VERIFIED", task_id="T-20", verification_evidence=".saipen/BOARD.md"
        )
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], "DISPOSITION_UNVERIFIED")
        self.assertIn("does not exist", result["error"])

    def test_missing_task_is_refused(self) -> None:
        result = self._dispose(
            disposition="VERIFIED", task_id="T-999", verification_evidence=".saipen/BOARD.md"
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "DISPOSITION_UNVERIFIED")

    def test_a_task_under_todo_is_not_done(self) -> None:
        (self.root / ".saipen" / "BOARD.md").write_text(
            "## DOING\n## TODO\n- [ ] T-300 [P1] open\n## BLOCKED\n## DONE\n",
            encoding="utf-8",
        )
        result = self._dispose(
            disposition="VERIFIED", task_id="T-300", verification_evidence=".saipen/BOARD.md"
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "DISPOSITION_UNVERIFIED")

    def test_board_md_is_not_evidence_for_an_arbitrary_finding(self) -> None:
        """A T-200 row exists, yet BOARD.md alone never substantiates a repair."""
        result = self._dispose(
            disposition="VERIFIED", task_id="T-200", verification_evidence=".saipen/BOARD.md"
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "DISPOSITION_UNVERIFIED")

    def test_fake_authenticated_signature_is_refused(self) -> None:
        result = self._dispose(
            disposition="VERIFIED",
            task_id="T-200",
            verification_evidence={"authenticated": True, "signature": "made-up"},
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "DISPOSITION_UNVERIFIED")

    def test_a_genuine_done_task_with_receipt_still_records(self) -> None:
        (self.root / ".saipen" / "BOARD.md").write_text(
            "## DOING\n## TODO\n## BLOCKED\n## DONE\n"
            "- [x] T-200 [P1] unrelated | verify: proof\n",
            encoding="utf-8",
        )
        receipt = self.root / ".saipen" / "evidence" / "t200.json"
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text('{"result": "pass"}\n', encoding="utf-8")
        result = self._dispose(
            disposition="VERIFIED",
            task_id="T-200",
            verification_evidence=".saipen/evidence/t200.json",
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "DISPOSITION_RECORDED")

    def test_invalid_attempts_append_nothing(self) -> None:
        log = self.root / ".saipen" / "campaign" / "dispositions.jsonl"
        for kwargs in (
            {"task_id": "T-20", "verification_evidence": ".saipen/BOARD.md"},
            {
                "task_id": "T-200",
                "verification_evidence": {"authenticated": True, "signature": "x"},
            },
            {"task_id": "T-404", "verification_evidence": ".saipen/BOARD.md"},
        ):
            with self.subTest(**kwargs):
                self._dispose(disposition="VERIFIED", **kwargs)
        self.assertFalse(log.exists() and log.read_text(encoding="utf-8").strip())


class Core005CampaignStatusDistinguishesCorruption(unittest.TestCase):
    """CORE-005: a corrupt campaign was reported as `ok: true, campaign: null`."""

    def setUp(self) -> None:
        self.root = _project()

    def _status(self) -> tuple[int, dict]:
        proc = subprocess.run(
            [
                sys.executable,
                str(REPO / "saipen.py"),
                "campaign",
                "status",
                "--project-root",
                str(self.root),
                "--json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        try:
            payload = json.loads(proc.stdout)
        except ValueError:
            payload = {"raw": proc.stdout}
        return proc.returncode, payload

    def test_absent_campaign_is_explicit(self) -> None:
        code, payload = self._status()
        self.assertEqual(code, 0, payload)
        self.assertTrue(payload["ok"])
        self.assertIsNone(payload["campaign"])
        self.assertEqual(payload["state_status"], campaign.STATE_ABSENT)

    def test_corrupt_json_is_not_success(self) -> None:
        campaign.campaign_state_path(self.root).write_text("{invalid", encoding="utf-8")
        code, payload = self._status()
        self.assertEqual(code, 1, payload)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["state_status"], campaign.STATE_CORRUPT)

    def test_incompatible_schema_is_reported(self) -> None:
        campaign.campaign_state_path(self.root).write_text(
            json.dumps(
                {"schema_version": 99, "campaign_id": "X", "campaign_state": campaign.ADMITTED}
            ),
            encoding="utf-8",
        )
        code, payload = self._status()
        self.assertEqual(code, 1, payload)
        self.assertEqual(payload["state_status"], campaign.STATE_INCOMPATIBLE)

    def test_missing_digest_is_reported_consistent_with_core_002(self) -> None:
        state = {
            "schema_version": campaign.CAMPAIGN_SCHEMA_VERSION,
            "campaign_id": "CAMP-STATUS",
            "campaign_state": campaign.ADMITTED,
        }
        campaign.save_campaign_state(self.root, state)
        path = campaign.campaign_state_path(self.root)
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("state_digest")
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        code, payload = self._status()
        self.assertEqual(code, 1, payload)
        self.assertEqual(payload["state_status"], campaign.STATE_CORRUPT)

    def test_valid_campaign_returns_its_state(self) -> None:
        campaign.save_campaign_state(
            self.root,
            {
                "schema_version": campaign.CAMPAIGN_SCHEMA_VERSION,
                "campaign_id": "CAMP-OK",
                "campaign_state": campaign.ADMITTED,
            },
        )
        code, payload = self._status()
        self.assertEqual(code, 0, payload)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["state_status"], campaign.STATE_VALID)
        self.assertEqual(payload["campaign"]["campaign_id"], "CAMP-OK")

    def test_status_never_modifies_persisted_bytes(self) -> None:
        campaign.campaign_state_path(self.root).write_text("{invalid", encoding="utf-8")
        before = campaign.campaign_state_path(self.root).read_bytes()
        self._status()
        self.assertEqual(campaign.campaign_state_path(self.root).read_bytes(), before)

    def test_status_and_step_agree_on_validity(self) -> None:
        campaign.campaign_state_path(self.root).write_text("{invalid", encoding="utf-8")
        _, payload = self._status()
        inspection = campaign.inspect_campaign_state(self.root)
        self.assertEqual(payload["state_status"], inspection["status"])


if __name__ == "__main__":
    unittest.main()
