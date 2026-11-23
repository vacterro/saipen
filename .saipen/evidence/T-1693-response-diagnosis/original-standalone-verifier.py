"""Fixed SRC-199 witnesses. Operator carriers here are disposable test doubles."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from saipen_engine import operator_task, pending_ingress, response_surface as RS

# Identical oracle/fixtures; ONLY the authenticated production subject changes.
if os.environ.get("SAIPEN_DIAGNOSIS_SUBJECT"):
    spec = importlib.util.spec_from_file_location(
        "saipen_engine._diagnosis_subject", os.environ["SAIPEN_DIAGNOSIS_SUBJECT"]
    )
    RS = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = RS
    spec.loader.exec_module(RS)

REQUEST = "Explain why the agent deviated from SAIPEN."
FIXTURES = TOOLS.parent / "tests/fixtures/protocol-diagnosis"
HASHES = {
    "a.md": "1378f149861acd5a345e16c97b0b0a863b667aecd054a3b8a728d1227fe6ed15",
    "b.md": "a6d6ca9591ea8f052ad6ac6d569cbdaae14910da387dd61543932dafb077d0a1",
}


class DiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="saipen-t1693-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.carrier = operator_task.witness(
            REQUEST, env={operator_task.ENV_TASK_SHA256: pending_ingress.ingress_digest(REQUEST)}
        )
        for name, digest in HASHES.items():
            raw = (FIXTURES / name).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
            target = self.root / ".saipen/evidence" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)

    def check(self, text, request=REQUEST, authority=None):
        if authority is None:
            authority = operator_task.witness(
                request, env={operator_task.ENV_TASK_SHA256: pending_ingress.ingress_digest(request)}
            )
        return RS.classify_final_response(
            text, operational_turn=False, style_contract=None,
            human_request=request, request_authority=authority,
            diagnosis_root=self.root,
        )

    def packet(self, witness="a.md"):
        text = (FIXTURES / witness).read_text(encoding="utf-8")
        quote = text.splitlines()[0]
        return {
            "type": "PROTOCOL_DIAGNOSIS", "request": REQUEST,
            "observed": [{"ref": f".saipen/evidence/{witness}",
                          "sha256": HASHES[witness], "quote": quote}],
            "rule": {"id": "EXEC-RESPONSE-01", "owner": "saipen/EXECUTION.md"},
            "assessment": "UNVERIFIED", "cause": {"kind": "UNKNOWN", "reason": "Original operator/host transcript is absent; the artifact cannot reveal internal intent."},
            "correction": {"status": "PROPOSED", "text": "Explain the request/delivery mismatch with attributed evidence; preserve legitimate refusals."},
            "recovery": "UNVERIFIED", "host": "freebuff", "enforcement": "ADVISORY",
            "semantic_review": "REQUIRED",
        }

    def assertRejected(self, text):
        klass, errors = self.check(text)
        self.assertEqual(klass, RS.CLASS_INVALID_OPERATIONAL_PROSE)
        self.assertTrue(errors)

    def test_a_inventory_cannot_replace_diagnosis(self):
        self.assertRejected((FIXTURES / "a.md").read_text(encoding="utf-8"))

    def test_b_generic_handoff_cannot_replace_diagnosis(self):
        self.assertRejected((FIXTURES / "b.md").read_text(encoding="utf-8"))

    def test_c_rule_needs_owner_and_bound_evidence(self):
        for field in ("rule", "observed"):
            packet = self.packet(); del packet[field]
            with self.subTest(field=field): self.assertRejected(json.dumps(packet))
        packet = self.packet(); packet["rule"]["owner"] = "saipen/STYLE.md"
        self.assertRejected(json.dumps(packet))

    def test_d_hidden_motive_is_not_observed_cause(self):
        packet = self.packet()
        packet["cause"] = {"kind": "INTERNAL_MOTIVE", "text": "The agent deliberately disobeyed."}
        self.assertRejected(json.dumps(packet))

    def test_e_successful_recovery_cannot_be_invented(self):
        packet = self.packet(); packet["recovery"] = "RECOVERED"
        self.assertRejected(json.dumps(packet))

    def test_f_freebuff_cannot_claim_mechanical_enforcement(self):
        packet = self.packet(); packet["enforcement"] = "MECHANICAL"
        self.assertRejected(json.dumps(packet))

    def test_g_cited_diagnosis_with_bounded_uncertainty(self):
        for witness in HASHES:
            with self.subTest(witness=witness):
                klass, errors = self.check(json.dumps(self.packet(witness)))
                self.assertEqual((klass, errors), (RS.CLASS_ORDINARY_CHAT, []))

    def test_h_truthful_refusal_is_not_misconduct(self):
        packet = self.packet(); packet["assessment"] = "LEGITIMATE_REFUSAL"
        packet["recovery"] = "REFUSED"
        packet["observed"][0]["quote"] = "SAIPEN в read-only блокировке"
        self.assertEqual(self.check(json.dumps(packet)), (RS.CLASS_ORDINARY_CHAT, []))

    def test_i_implementation_handoff_keeps_its_own_contract(self):
        self.assertEqual(self.check("Implementation and tests listed here.", "write an implementation handoff"), (RS.CLASS_ORDINARY_CHAT, []))

    def test_j_compact_status_is_not_diagnosis(self):
        self.assertEqual(RS.reason_for_request("give me a summary"), "summary")

    def test_k_witnessed_detailed_artifact_is_still_allowed(self):
        self.assertEqual(self.check("Evidence and findings.", "prepare the audit"), (RS.CLASS_ORDINARY_CHAT, []))

    def test_l_unverified_host_is_reported_truthfully(self):
        packet = self.packet(); packet["enforcement"] = "UNVERIFIED"
        self.assertEqual(self.check(json.dumps(packet)), (RS.CLASS_ORDINARY_CHAT, []))

    def test_changed_quote_digest_path_and_request_are_rejected(self):
        for key, value in [("quote", "fiction"), ("sha256", "0"*64), ("ref", "../../outside")]:
            packet = self.packet(); packet["observed"][0][key] = value
            with self.subTest(key=key): self.assertRejected(json.dumps(packet))
        packet = self.packet(); packet["request"] = "write an implementation handoff"
        self.assertRejected(json.dumps(packet))

    def test_no_caller_root_is_not_evidence(self):
        klass, errors = RS.classify_final_response(
            json.dumps(self.packet()), operational_turn=False,
            human_request=REQUEST, request_authority=self.carrier,
        )
        self.assertEqual(klass, RS.CLASS_INVALID_OPERATIONAL_PROSE)
        self.assertTrue(errors)

    def test_request_classes_come_from_ingress(self):
        for request, kind in [(REQUEST,"PROTOCOL_DIAGNOSIS"),
                              ("write an implementation handoff","IMPLEMENTATION_HANDOFF"),
                              ("give me a summary","ENGINEERING_STATUS"),
                              ("report the recovery refusal","RECOVERY_REPORT"),
                              ("prepare the audit","AUDIT")]:
            with self.subTest(request=request):
                self.assertEqual(RS.request_class_for_request(request),kind)

    def test_quoted_or_negated_request_never_grants_diagnosis(self):
        for request in [f'"{REQUEST}"',f"example: {REQUEST}",f"do not {REQUEST}"]:
            self.assertNotEqual(RS.artifact_for_request(request),"PROTOCOL_DIAGNOSIS")

    def test_model_supplied_request_cannot_authorize_artifact(self):
        self.assertFalse(RS.human_response_authority(REQUEST,{"witness":"model_supplied"}))

    def test_layered_gate_discloses_semantic_limit_and_preserves_admission(self):
        kwargs = dict(admission=None, admission_consulted=False, operational_turn=True,
                      style_contract=None, human_request=REQUEST, request_authority=self.carrier,
                      diagnosis_root=self.root)
        verdict = RS.gate_final_response(json.dumps(self.packet()), **kwargs)
        self.assertTrue(verdict["ok"])
        self.assertEqual(verdict["diagnosis_verification"], "STRUCTURE_AND_CITATIONS_ONLY")
        self.assertEqual(verdict["semantic_review"], "REQUIRED")
        kwargs.update(admission={"permitted":False,"state":"REFUSED","problems":[]}, admission_consulted=True)
        self.assertFalse(RS.gate_final_response(json.dumps(self.packet()), **kwargs)["ok"])

    def test_malformed_values_refuse_instead_of_crashing(self):
        for field in ["assessment","host","rule","cause","observed","recovery"]:
            packet = self.packet(); packet[field]=[]
            with self.subTest(field=field): self.assertRejected(json.dumps(packet))

    def test_correction_is_not_an_execution_receipt(self):
        packet=self.packet();packet["correction"]["status"]="IMPLEMENTED"
        self.assertRejected(json.dumps(packet))


if __name__ == "__main__": unittest.main()
