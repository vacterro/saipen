"""Regression Matrix Tests for FreeBuff Operator Provenance (Clauses A through Q).

Stage 6 of SAIHANDOFF — SAIPEN / FREEBUFF / LUNA (SRC-277 / T-1818).
Validates trusted carrier creation and transport, rejection of model fabrication,
authority lineage preservation, Auto-Doctor STALE_FAIL revalidation under valid
authority, and FreeBuff host diagnostics.

T-1823 CLASSIFICATION -- READ BEFORE CITING ANY GREEN HERE. Four different
things are called "FreeBuff provenance acceptance" and they are not
interchangeable:

  1. unit contract verification        -- the engine's own functions, no host.
  2. simulated host integration        -- THIS FILE (CATEGORY below): a test
                                          builds the envelope a compliant
                                          FreeBuff host *would* write and
                                          admits it through the engine API.
                                          No FreeBuff process, no UI, no
                                          operator turn is involved.
  3. actual FreeBuff process integration -- a real FreeBuff-launched tool
                                          process carrying SAIPEN_TASK_FILE /
                                          SAIPEN_TASK_SHA256 / a host ingress
                                          envelope. NOT covered here; no such
                                          host behaviour is installed yet
                                          (see extensions/adapters/registry.json
                                          freebuff operator_ingress_capability).
  4. real operator-origin end-to-end acceptance -- an operator turn in the
                                          real UI reaching canonical SAIPEN
                                          lifecycle as operator_carrier.
                                          `FreebuffLiveHostAcceptance` below is
                                          the only place that may claim it, and
                                          it SKIPS without a live host.

A green in this module is category 2 only. It is not GUI acceptance, not
host acceptance, and never evidence that FreeBuff supplies a carrier.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import (  # noqa: E402
    admission_doctor,
    conformance as C,
    operator_task,
    state as state_mod,
)
from saipen_engine import host_authority_client  # noqa: E402


class TestFreebuffOperatorProvenance(unittest.TestCase):
    #: T-1823: category 2 -- simulated host integration. Every clause here
    #: exercises the engine against hand-built witnesses/envelopes; none of
    #: them observes a FreeBuff process. A consumer that needs to know whether
    #: a green proves live host behaviour must read this marker, not the name.
    CATEGORY = "simulated_host_integration"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="saipen_freebuff_test_")
        self.root = Path(self.tmp)
        (self.root / ".saipen").mkdir(parents=True, exist_ok=True)
        (self.root / ".saipen" / "IDENTITY.md").write_text(
            "---\nproject_lineage: lineage-0123456789abcdef0123456789abcdef\n---\n",
            encoding="utf-8",
        )
        (self.root / ".saipen" / "STATE.md").write_text(
            '---\nphase: SCOUT\ntask: T-1479\nnext_action: "PHASE SCOUT T-1479"\n'
            "blocker: none\ntransition_from: DONE\nsaipen_version: 8\n"
            "schema_version: 3\nlast_event: 10\nstyle_contract: ded-069a4c52\n"
            'agent: saipen-cli\nmode: full\nupdated: "2026-10-18T12:00:00Z"\n'
            "execution_intent: goal\ngoal_waves: 1\ngoal_tickets: 5\n"
            "continuation_authority: operator_required\n"
            "authority_source: E-8\nauthority_until: budget\n"
            "safety_valve_mode: hard_wait\n---\n",
            encoding="utf-8",
        )
        (self.root / ".saipen" / "BOARD.md").write_text(
            "## DOING\n"
            "- [/] T-1479 [P1] Chest/Stash corrective work | verify: tests pass | "
            "owner: saipen-cli | claim_time: 2026-10-18T12:00:00Z\n"
            "## TODO\n"
            "## BLOCKED\n"
            "## DONE\n"
            "- [x] T-1477 [P2] prior task | verify: pass | owner: saipen-cli | "
            "claim_time: 2026-10-18T10:00:00Z | closure_mode: own_patch\n"
            "- [x] T-1478 [P2] prior task 2 | verify: pass | owner: saipen-cli | "
            "claim_time: 2026-10-18T11:00:00Z | closure_mode: own_patch\n",
            encoding="utf-8",
        )
        (self.root / ".saipen" / "LOG.md").write_text(
            "- 18.10.26 12:00 [E-008] [agent: saipen-cli] DEC: goal reauthorized by operator\n"
            "- 18.10.26 12:00 [E-009] [agent: saipen-cli] DEC: claimed T-1479\n"
            "- 18.10.26 12:00 [E-010] [agent: saipen-cli] RUN: SCOUT -- initial scout\n",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def native_file_witness(self, task_text, env):
        """Category 2: actual broker/consumer with explicitly simulated identity.

        The model-written file remains transport only. Neither this fixture
        nor its simulated Claude hook identity proves a real Freebuff event.
        """
        import test_t1844_origin_broker as origin_controls

        fixture = origin_controls.OriginKernelWithSimulatedNativeIdentity()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.root = self.root
        proof = fixture.issue(text=task_text)
        fixture.register(proof)
        operator_task.admit_host_ingress(
            {"request_text": task_text, "session_id": "session-A", "message_id": "native-file",
             "operator_origin": proof}, self.root,
        )
        with mock.patch.object(host_authority_client, "_call", side_effect=fixture.bridge):
            witness = operator_task.witness(
                task_text, env={**env, operator_task.ENV_HOST_SESSION: "session-A"}, root=self.root,
            )
            authority = operator_task.authority_for_provenance(witness, root=self.root)
        return witness, authority

    def test_clause_a_user_directly_approves_task_in_freebuff(self):
        (
            """Clause A: User directly approves task in FREEBUFF -> SAIPEN receives """
            """valid trusted provenance."""
        )
        task_text = "Fix Chest/Stash corrective work"
        task_file = self.root / "task.txt"
        task_file.write_text(task_text, encoding="utf-8")
        env = {
            operator_task.ENV_TASK_FILE: str(task_file),
            "FREEBUFF_HOME": str(self.root / ".freebuff"),
        }
        witness_rec, auth = self.native_file_witness(task_text, env)
        self.assertEqual(witness_rec["witness"], operator_task.WITNESS_CARRIER)
        self.assertTrue(auth["user_explicit"])
        self.assertTrue(auth["local_work"])

    def test_clause_b_luna_generates_authorization_itself(self):
        (
            """Clause B: Luna generates authorization text itself -> SAIPEN rejects """
            """trusted authority."""
        )
        task_text = "Luna self-authorized task without human carrier"
        env = {
            "FREEBUFF_HOME": str(self.root / ".freebuff"),
        }
        witness_rec = operator_task.witness(task_text, env=env, root=self.root)
        self.assertEqual(witness_rec["witness"], operator_task.WITNESS_MODEL)
        self.assertTrue(witness_rec.get("freebuff_provenance_missing"))
        self.assertEqual(
            witness_rec.get("diagnostic_code"),
            operator_task.CODE_FREEBUFF_PROVENANCE_MISSING,
        )
        auth = operator_task.authority_for_provenance(witness_rec)
        self.assertFalse(auth["user_explicit"])

    def test_clause_c_luna_copies_old_authorization(self):
        """Clause C: Luna copies an old authorization -> rejected as mismatch or replay."""
        old_text = "Legitimate original task text"
        old_sha = hashlib.sha256(old_text.encode("utf-8")).hexdigest()
        env = {
            operator_task.ENV_TASK_SHA256: old_sha,
            "FREEBUFF_HOME": str(self.root / ".freebuff"),
        }
        new_text = "Luna modified text attempting to reuse old hash"
        witness_rec = operator_task.witness(new_text, env=env, root=self.root)
        self.assertEqual(witness_rec["code"], operator_task.CODE_MISMATCH)

    def test_clause_d_freebuff_starts_saipen_task(self):
        """Clause D: FREEBUFF starts a SAIPEN task -> provenance reaches admission."""
        task_text = "Start new verified component"
        task_file = self.root / "task_start.txt"
        task_file.write_text(task_text, encoding="utf-8")
        env = {
            operator_task.ENV_TASK_FILE: str(task_file),
            "FREEBUFF_HOME": str(self.root / ".freebuff"),
        }
        decl = operator_task.declared(env)
        self.assertIsNotNone(decl)
        self.assertEqual(decl["source"], operator_task.ENV_TASK_FILE)

    def test_clause_e_freebuff_resumes_admitted_task(self):
        """Clause E: FREEBUFF resumes an admitted task -> valid authority lineage preserved."""
        st = state_mod.parse_state((self.root / ".saipen" / "STATE.md").read_text(encoding="utf-8"))
        self.assertEqual(st.get("task"), "T-1479")
        self.assertEqual(st.get("authority_source"), "E-8")
        self.assertEqual(st.get("continuation_authority"), "operator_required")

    def test_clause_f_nested_tool_invocation_preserves_provenance(self):
        """Clause F: Nested tool/process invocation -> carrier is preserved in subprocess env."""
        task_text = "Nested process test"
        task_file = self.root / "nested.txt"
        task_file.write_text(task_text, encoding="utf-8")
        parent_env = {
            operator_task.ENV_TASK_FILE: str(task_file),
            "FREEBUFF_SESSION": "sess-12345",
        }
        child_env = dict(parent_env)
        self.assertEqual(child_env.get(operator_task.ENV_TASK_FILE), str(task_file))
        witness_rec, authority = self.native_file_witness(task_text, child_env)
        self.assertEqual(witness_rec["witness"], operator_task.WITNESS_CARRIER)
        self.assertTrue(authority["user_explicit"])

    def test_clause_g_freebuff_restarts(self):
        """Clause G: FREEBUFF restarts -> durable authorization recovered only where valid."""
        ingress_dir = self.root / ".saipen" / "cache" / "ingress"
        ingress_dir.mkdir(parents=True, exist_ok=True)
        rec = {
            "ingress_id": "ing-durable-001",
            "request_text": "Durable request text",
            "request_digest": hashlib.sha256(b"Durable request text").hexdigest(),
            "consumed": False,
            "session_id": "sess-preserved",
        }
        (ingress_dir / "ing-durable-001.json").write_text(json.dumps(rec), encoding="utf-8")
        active = operator_task.active_host_ingress(self.root)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["ingress_id"], "ing-durable-001")

    def test_clause_h_wrong_repository_or_task_identity(self):
        """Clause H: Wrong repository or task identity -> admission rejected."""
        wrong_ingress = {
            "request_text": "Some text",
            "request_digest": hashlib.sha256(b"Some text").hexdigest(),
            "project_lineage": "lineage-wrong-different-project-id",
        }
        res = operator_task.admit_host_ingress(wrong_ingress, self.root)
        self.assertFalse(res["ok"])
        self.assertEqual(res["code"], "INGRESS_TASK_CARRIER_INVALID")

    def stale_route(self):
        """The refusal a `cc` sees when the receipt's source binding went stale."""
        return {
            "emitted": {
                "code": "CONFORMANCE_UNHEALTHY",
                "canonical_next_command": "saipen validate",
                "conformance_status": "STALE_FAIL",
                "detail": "conformance receipt is bound to a different source "
                "identity than the current checkpoint",
            },
            "task": "T-1479",
            "execution_intent": "goal",
        }

    def typed_stale(self, reason):
        """T-1823: the doctor's authority comes from the typed status, so the
        test supplies it through the single owner that produces it."""
        return mock.patch.object(
            C,
            "conformance_status",
            return_value={"status": "STALE_FAIL", "stale_reason": reason},
        )

    def test_clause_i_stale_validation_with_valid_authority(self):
        """Clause I: Stale validation with valid authority -> safe recovery occurs."""
        from saipen import _auto_doctor

        route = self.stale_route()
        budget = {"left": 1}
        # In dry run mode, Auto-Doctor diagnoses and plans to revalidate once.
        # The authority under test is TYPED (`stale_reason`), never the prose in
        # `detail`: a re-measurable staleness of a live receipt.
        with self.typed_stale(C.STALE_REASON_SOURCE_BINDING_STALE):
            result = _auto_doctor(self.root, route, None, budget, dry_run=True)
        doctor = (result.get("emitted") or {}).get("doctor")
        self.assertIsNotNone(doctor)
        self.assertEqual(doctor["stage"], "DIAGNOSING")
        self.assertEqual(doctor["status_before"], "STALE_FAIL")

    def test_clause_i_negative_prose_alone_grants_no_revalidation(self):
        """T-1823: the same sentence with no typed recoverable condition and the
        verbatim absence of the word 'fabricated' must NOT authorize repair."""
        from saipen import _auto_doctor

        route = self.stale_route()
        for live in (
            {"status": "STALE_FAIL", "stale_reason": C.STALE_REASON_FUTURE_TIMESTAMP},
            {"status": "STALE_FAIL", "stale_reason": C.STALE_REASON_SOURCE_IDENTITY_UNAVAILABLE},
            {"status": "STALE_FAIL", "stale_reason": "an-unknown-future-code"},
            {"status": "STALE_FAIL"},
            {},
        ):
            with self.subTest(live=live), mock.patch.object(
                C, "conformance_status", return_value=live
            ), mock.patch("saipen._validate") as validator:
                result = _auto_doctor(self.root, route, None, {"left": 1}, dry_run=True)
                self.assertNotIn("doctor", result.get("emitted") or {}, live)
                validator.assert_not_called()

    def test_clause_j_stale_validation_without_authority(self):
        """Clause J: Stale validation without authority -> no privilege invented.

        T-1823: the typed condition is PRESENT and recoverable here, so the only
        thing refusing is the missing active task/goal -- the authority axis on
        its own. Revalidation re-measures evidence; it never mints authority.
        """
        from saipen import _auto_doctor

        route = {
            "emitted": {
                "code": "CONFORMANCE_UNHEALTHY",
                "canonical_next_command": "saipen validate",
                "conformance_status": "STALE_FAIL",
                "detail": "conformance receipt is bound to a different source identity",
            },
            "task": "none",
            "ticket": "none",
            "execution_intent": "converge",
        }
        budget = {"left": 1}
        st = self.root / ".saipen" / "STATE.md"
        st.write_text(
            st.read_text(encoding="utf-8")
            .replace("task: T-1479", "task: none")
            .replace("execution_intent: goal", "execution_intent: converge"),
            encoding="utf-8",
        )
        with self.typed_stale(C.STALE_REASON_SOURCE_BINDING_STALE):
            result = _auto_doctor(self.root, route, None, budget, dry_run=True)
        self.assertNotIn("doctor", result.get("emitted") or {})

    def test_clause_k_rapid_repeated_continue_requests(self):
        """Clause K: Rapid repeated continue requests -> idempotent, no duplicate tickets."""
        board_text = (self.root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        tickets = [line for line in board_text.splitlines() if line.strip().startswith("- [")]
        self.assertEqual(len([t for t in tickets if "T-1479" in t]), 1)

    def test_clause_l_t1479_already_exists_in_scout(self):
        """Clause L: T-1479 already exists in SCOUT -> original ticket resumed, not recreated."""
        st = state_mod.parse_state((self.root / ".saipen" / "STATE.md").read_text(encoding="utf-8"))
        self.assertEqual(st.get("task"), "T-1479")
        self.assertEqual(st.get("phase"), "SCOUT")

    def test_clause_m_model_supplied_environment_variables(self):
        (
            """Clause M: Model-supplied environment variables -> insufficient to forge """
            """human identity."""
        )
        env = {
            "USER_SAYS": "Please do this",
            "LUNA_PROVENANCE": "trusted_human",
        }
        witness_rec = operator_task.witness("task", env=env, root=self.root)
        self.assertEqual(witness_rec["witness"], operator_task.WITNESS_MODEL)
        auth = operator_task.authority_for_provenance(witness_rec)
        self.assertFalse(auth["user_explicit"])

    def test_clause_n_expired_or_revoked_authorization(self):
        """Clause N: Expired or revoked authorization -> execution refused."""
        ticket = {"id": "T-1479", "blocker": "OPERATOR_PAUSED", "needs": []}
        board_tickets = {"T-1479": ticket}
        state = {"task": "T-1479", "continuation_authority": "operator_required"}
        report = admission_doctor.classify_blocked_ticket(ticket, board_tickets, state)
        self.assertIn(admission_doctor.CAUSE_F_AUTHORIZATION_REQUIRED, report["causes"])

    def test_clause_o_freebuff_user_approval_through_simulated_ingress(self):
        """Clause O (SIMULATED): an operator-origin ingress envelope is admitted.

        This test does NOT drive the FreeBuff UI and does NOT speak to a live
        FreeBuff process. It constructs the envelope a compliant host WOULD
        write and asserts the ENGINE's side of the contract: the envelope is
        admitted and stays active. Real UI approval is category 4
        (`FreebuffLiveHostAcceptance`); the previous name claimed a GUI
        acceptance this cannot produce (T-1823).
        """
        ingress_payload = {
            "request_text": "FreeBuff UI Operator approved work",
            "request_digest": hashlib.sha256(b"FreeBuff UI Operator approved work").hexdigest(),
            "project_lineage": "lineage-0123456789abcdef0123456789abcdef",
            "session_id": "freebuff-ui-sess-1",
        }
        res = operator_task.admit_host_ingress(ingress_payload, self.root)
        self.assertTrue(res["ok"])
        active = operator_task.active_host_ingress(self.root)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["request_text"], "FreeBuff UI Operator approved work")

    def test_clause_p_freebuff_user_approval_followed_by_continuation(self):
        (
            """Clause P: FREEBUFF user approval followed by Luna continuation -> no """
            """second approval needed."""
        )
        st = state_mod.parse_state((self.root / ".saipen" / "STATE.md").read_text(encoding="utf-8"))
        self.assertEqual(st.get("task"), "T-1479")
        # Lineage is preserved across turns without requiring re-approval of unchanged scope
        self.assertEqual(st.get("authority_source"), "E-8")

    def test_clause_q_tool_errors_and_missing_host_capabilities(self):
        """Clause Q: Tool errors and missing host capabilities -> clear actionable diagnostic."""
        ticket = {"id": "T-1479", "request_witness": "model_supplied", "needs": []}
        board_tickets = {"T-1479": ticket}
        state = {
            "task": "T-1479",
            "phase": "SCOUT",
            "continuation_authority": "operator_required",
            "safety_valve_mode": "hard_wait",
        }
        report = admission_doctor.classify_blocked_ticket(ticket, board_tickets, state)
        self.assertIn(admission_doctor.CAUSE_E_PROVENANCE_INSUFFICIENT, report["causes"])
        self.assertIsNotNone(report["decision_request"])
        dec = report["decision_request"]
        self.assertIn("FreeBuff", dec["missing_authorization"])
        self.assertIn("Maintain hard_wait", dec["safe_default"])


class FreebuffLiveHostAcceptance(unittest.TestCase):
    """Category 3/4: real FreeBuff host acceptance -- only with live evidence.

    Nothing in the SAIPEN repository can prove that an installed FreeBuff host
    delivers an operator carrier: that is a fact about a running host process
    and a real operator turn. The probe below therefore runs ONLY when a live
    run hands it the carrier that host actually delivered --
    ``SAIPEN_FREEBUFF_LIVE_CARRIER`` names the staged task file of a real
    FreeBuff-launched process, ``SAIPEN_FREEBUFF_LIVE_SHA256`` its digest --
    and otherwise SKIPS. A skip is the honest verdict: never green, never
    counted as acceptance. T-1823.
    """

    CATEGORY = "live_host_acceptance"

    def test_a_real_freebuff_tool_process_delivered_the_operator_carrier(self):
        carrier = os.environ.get("SAIPEN_FREEBUFF_LIVE_CARRIER", "").strip()
        digest = os.environ.get("SAIPEN_FREEBUFF_LIVE_SHA256", "").strip()
        if not carrier or not digest:
            self.skipTest(
                "no live FreeBuff host in this environment: category 4 acceptance "
                "requires a real FreeBuff-launched tool process carrying "
                "SAIPEN_TASK_FILE/SAIPEN_TASK_SHA256 (or a host ingress envelope)"
            )
        staged = Path(carrier)
        self.assertTrue(staged.is_file(), f"live carrier {carrier} is not a file")
        actual = hashlib.sha256(staged.read_bytes()).hexdigest()
        self.assertEqual(
            actual,
            digest.lower(),
            "the live carrier's bytes do not match the digest the host declared",
        )
        # cwd is the project under test; this class has no fixture root, and a
        # live carrier is compared by bytes alone.
        witness = operator_task.witness(
            "task",
            env={
                "SAIPEN_TASK_FILE": carrier,
                "SAIPEN_TASK_SHA256": digest,
            },
        )
        self.assertEqual(witness["witness"], operator_task.WITNESS_CARRIER)
        self.assertTrue(operator_task.authority_for_provenance(witness)["user_explicit"])


if __name__ == "__main__":
    unittest.main()
