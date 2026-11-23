"""Declared outcomes survive native edits, REVIEW, finish and supersession.

NativeEscapeRegressionTests uses only pre-existing public operations: the same
oracle completes with real failures on pre-fix bytes, not an import failure.
Operator carriers below are explicit fixture doubles, never real authority.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import intake, operator_task, operations as ops, supersession  # noqa: E402
from saipen_engine.board import parse_board, set_ticket_field  # noqa: E402
from saipen_engine.journal import (  # noqa: E402
    Journal, auto_recover_pending, scan_pending, semantic_receipts_for_operation,
)
from saipen_engine.log import read_history_snapshot  # noqa: E402
from saipen_engine.pending_ingress import ingress_digest  # noqa: E402
from test_regression_gate import RegressionGateFixture, _ship_project  # noqa: E402

LIVE = "AC-01 [LIVE] signed-in product outcome"
UNIT = "AC-01 [UNIT] offline inspector outcome"
REPLACEMENT = "AC-02 [LIVE] equivalent signed-in outcome"


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def tree(root):
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def fixture_contract(path, contract):
    text = path.read_text(encoding="utf-8")
    raw = parse_board(text)["tickets"]["T-7"]["raw"]
    path.write_text(text.replace(raw, set_ticket_field(raw, "verify", contract), 1),
                    encoding="utf-8")


class ContractFixture(RegressionGateFixture):
    REGRESSION = ""

    def declare(self, contract=LIVE):
        result = ops.ticket_verify(self.project, "T-7", "tester", contract)
        self.assertTrue(result.ok, result.to_dict())

    def source(self, capsule, *, trusted=True):
        text = json.dumps(capsule, sort_keys=True) if isinstance(capsule, dict) else capsule
        if trusted:
            from test_operator_origin_support import native_operator

            action = ("append" if isinstance(capsule, dict)
                      and capsule.get("kind") == "acceptance_amendment" else "report")
            if isinstance(capsule, str) and capsule.startswith(supersession.GRANT_HEADER):
                action = "supersede"
            with native_operator(self.project, text, action=action):
                result = intake.capture(
                    self.project, text, source_kind="user_instruction",
                    request_provenance=operator_task.witness(text, root=self.project),
                    projection_policy="authority_only",
                )
                if result.get("ok"):
                    operator_task.authority_for_receipt(
                        self.project, result["receipt"], existing_only=False,
                    )
        else:
            result = intake.capture(
                self.project, text, source_kind="user_instruction",
                request_provenance=operator_task.witness(text, env={}),
                projection_policy="authority_only",
            )
        self.assertTrue(result["ok"], result)
        return result["receipt"]

    def observation(self, contract, *, work="T-7", ac_id="AC-01", witness="LIVE",
                    surface="chatgpt.com", trusted=True, build_event=None):
        from saipen_engine.acceptance import build_boundary

        if build_event is None:
            build_event = build_boundary(work, read_history_snapshot(self.project).events)
        source = self.source({
            "schema": 1, "kind": "acceptance_witness", "work": work,
            "contract_sha256": sha(contract), "build_boundary": build_event,
            "criteria": {ac_id: {"result": "PASS", "witness": witness, "surface": surface}},
        }, trusted=trusted)
        self.record(f"AC-EVIDENCE {ac_id} PASS manual witness={witness} surface={surface} "
                    f"source={source} -- reported observation fixture")
        return source

    def amendment(self, old=LIVE, new=REPLACEMENT, *, trusted=True, modify=None):
        evidence = ".saipen/evidence/retirement.json"
        path = self.project / evidence
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = '{"observed":"equivalent replacement outcome", "fixture":true}\n'
        path.write_text(raw, encoding="utf-8", newline="")
        value = {
            "schema": 1, "work": "T-7", "original_sha256": sha(old),
            "replacement_sha256": sha(new), "reason": "operator confirms equivalent replacement",
            "evidence": [{"path": evidence, "sha256": sha(raw)}],
            "mapping": {"AC-01": ["AC-02"]}, "remaining": ["AC-02"],
        }
        if modify:
            modify(value)
        relative = ".saipen/evidence/amendment.json"
        encoded = json.dumps(value, sort_keys=True)
        (self.project / relative).write_text(encoded, encoding="utf-8", newline="")
        authority = self.source({"schema": 1, "kind": "acceptance_amendment", "work": "T-7",
                                 "sha256": sha(encoded)}, trusted=trusted)
        return relative, authority

    def amend(self, relative, authority, new=REPLACEMENT, **kwargs):
        return ops.ticket_verify(self.project, "T-7", "tester", new,
                                 amendment=relative, authority=authority, **kwargs)

    def finish(self):
        self.assertTrue(self.to_review().ok)
        result = ops.transition_phase(self.project, "SHIP", "tester", "T-7", "local only")
        self.assertTrue(result.ok, result.to_dict())
        return ops.finish_ticket(self.project, "T-7", "tester")


class NativeEscapeRegressionTests(ContractFixture):
    def test_redefined_unit_outcome_cannot_spend_an_old_id_only_pass(self):
        self.declare(UNIT)
        self.record(
            "AC-EVIDENCE AC-01 PASS behavioral witness=UNIT surface=fixture -- original only"
        )
        replacement = "AC-01 [UNIT] replacement outcome never tested"
        relative, authority = self.amendment(
            old=UNIT, new=replacement,
            modify=lambda value: value.update(mapping={"AC-01": ["AC-01"]}, remaining=["AC-01"]),
        )
        before = tree(self.project)
        result = self.amend(relative, authority, replacement)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(tree(self.project), before)

    def test_deleting_a_declared_outcome_refuses_without_writes(self):
        self.declare()
        before = tree(self.project)
        result = ops.ticket_verify(self.project, "T-7", "tester", "offline fixture passes")
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(tree(self.project), before)

    def test_optionalizing_live_into_unit_refuses_without_writes(self):
        self.declare()
        before = tree(self.project)
        result = ops.ticket_verify(self.project, "T-7", "tester",
                                   "AC-01 [UNIT] signed-in product outcome")
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(tree(self.project), before)

    def test_fixture_only_live_cannot_enter_review(self):
        self.declare()
        self.record("AC-EVIDENCE AC-01 PASS behavioral witness=UNIT surface=fixture -- measured")
        before = tree(self.project)
        result = self.to_review()
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(tree(self.project), before)

    def test_fixture_only_live_cannot_finish(self):
        project = _ship_project(self, pair=True)
        board = project / ".saipen/BOARD.md"
        # Initial disposable SHIP fixture; never edit an actual project's history.
        fixture_contract(board, LIVE)
        self.assertTrue(ops.checkpoint(
            project, "tester", "RUN", "T-7",
            "AC-EVIDENCE AC-01 PASS behavioral witness=UNIT surface=fixture -- measured",
        ).ok)
        before = tree(project)
        result = ops.finish_ticket(project, "T-7", "tester")
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(tree(project), before)

    def test_ordinary_meaning_preserving_work_still_finishes(self):
        self.declare(UNIT)
        result = ops.ticket_verify(self.project, "T-7", "tester", UNIT + "; implementation changed")
        self.assertTrue(result.ok, result.to_dict())
        self.record("AC-EVIDENCE AC-01 PASS behavioral witness=UNIT surface=fixture -- measured")
        self.assertTrue(self.finish().ok)


class AmendmentTests(ContractFixture):
    def setUp(self):
        super().setUp()
        self.declare()

    def test_authorized_equivalent_retirement_preserves_contract_and_finishes(self):
        self.observation(REPLACEMENT, ac_id="AC-02")
        relative, authority = self.amendment()
        result = self.amend(relative, authority)
        self.assertTrue(result.ok, result.to_dict())
        records = semantic_receipts_for_operation(self.project, "ticket_verify")
        value = max((r["receipt_metadata"]["acceptance_contract"] for r in records
                     if (r.get("receipt_metadata") or {}).get("acceptance_contract")),
                    key=lambda item: item["event"])
        self.assertEqual((value["original"], value["replacement"]), (LIVE, REPLACEMENT))
        self.assertEqual(value["original_sha256"], sha(LIVE))
        self.assertEqual(value["amendment"]["authority"], authority)
        self.assertTrue(self.finish().ok)

    def test_digest_bound_unit_redefinition_remains_reachable(self):
        fixture = ContractFixture()
        fixture.setUp()
        original_project, self.project = self.project, fixture.project
        try:
            self.declare(UNIT)
            replacement = "AC-01 [UNIT] independently checked replacement outcome"
            self.observation(replacement, witness="UNIT", surface="fixture")
            relative, authority = self.amendment(
                old=UNIT, new=replacement,
                modify=lambda value: value.update(mapping={"AC-01": ["AC-01"]},
                                                  remaining=["AC-01"]),
            )
            self.assertTrue(self.amend(relative, authority, replacement).ok)
            self.assertTrue(self.finish().ok)
        finally:
            self.project = original_project
            fixture.doCleanups()

    def test_identical_unit_criteria_amendment_preserves_its_existing_check(self):
        fixture = ContractFixture()
        fixture.setUp()
        original_project, self.project = self.project, fixture.project
        try:
            self.declare(UNIT)
            self.record("AC-EVIDENCE AC-01 PASS behavioral witness=UNIT surface=fixture -- current")
            replacement = UNIT + "; implementation notes changed"
            relative, authority = self.amendment(
                old=UNIT, new=replacement,
                modify=lambda value: value.update(mapping={"AC-01": ["AC-01"]},
                                                  remaining=["AC-01"]),
            )
            self.assertTrue(self.amend(relative, authority, replacement).ok)
            self.assertTrue(self.finish().ok)
        finally:
            self.project = original_project
            fixture.doCleanups()

    def test_identical_live_criteria_amendment_preserves_its_existing_observation(self):
        self.observation(LIVE)
        replacement = LIVE + "; implementation notes changed"
        relative, authority = self.amendment(
            new=replacement,
            modify=lambda value: value.update(mapping={"AC-01": ["AC-01"]}, remaining=["AC-01"]),
        )
        self.assertTrue(self.amend(relative, authority, replacement).ok)
        self.assertTrue(self.finish().ok)

    def test_model_source_and_later_stronger_environment_grant_nothing(self):
        self.observation(REPLACEMENT, ac_id="AC-02")
        relative, authority = self.amendment(trusted=False)
        before = tree(self.project)
        body = intake.read_body(self.project, authority)["body"]
        with patch.dict("os.environ", {"SAIPEN_TASK_SHA256": ingress_digest(body)}):
            result = self.amend(relative, authority)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(tree(self.project), before)

    def test_wrong_actor_cannot_amend_an_owned_contract(self):
        before = tree(self.project)
        result = ops.ticket_verify(self.project, "T-7", "stranger", LIVE + "; extra context")
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(tree(self.project), before)

    def test_unsupported_mapping_or_evidence_never_retires_original(self):
        self.observation(REPLACEMENT, ac_id="AC-02")
        cases = (
            lambda v: v.update(mapping={}),
            lambda v: v.update(mapping={"AC-01": []}),
            lambda v: v.update(remaining=[]),
            lambda v: v.update(evidence=[]),
            lambda v: v.update(reason=""),
            lambda v: v.update(work="T-8"),
            lambda v: v.update(original_sha256="0" * 64),
            lambda v: v.update(extra=True),
        )
        for modify in cases:
            with self.subTest(modify=modify):
                relative, authority = self.amendment(modify=modify)
                before = tree(self.project)
                result = self.amend(relative, authority)
                self.assertFalse(result.ok, result.to_dict())
                self.assertEqual(tree(self.project), before)

    def test_operator_cannot_reduce_witness_floor_via_equivalence_label(self):
        new = "AC-02 [UNIT] equivalent signed-in outcome"
        self.record("AC-EVIDENCE AC-02 PASS behavioral witness=UNIT surface=fixture -- measured")
        relative, authority = self.amendment(new=new)
        self.assertFalse(self.amend(relative, authority, new).ok)

    def test_fixture_only_replacement_cannot_spend_retirement_approval(self):
        self.record("AC-EVIDENCE AC-02 PASS behavioral witness=UNIT surface=fixture -- measured")
        relative, authority = self.amendment()
        self.assertFalse(self.amend(relative, authority).ok)

    def test_manifest_tamper_and_replay_refuse(self):
        self.observation(REPLACEMENT, ac_id="AC-02")
        relative, authority = self.amendment()
        path = self.project / relative
        original = path.read_bytes()
        path.write_bytes(original + b" ")
        self.assertFalse(self.amend(relative, authority).ok)
        path.write_bytes(original)
        self.assertTrue(self.amend(relative, authority).ok)
        before = tree(self.project)
        self.assertFalse(self.amend(relative, authority).ok)
        self.assertEqual(tree(self.project), before)

    def test_duplicate_json_fields_refuse_even_with_exact_operator_approval(self):
        self.observation(REPLACEMENT, ac_id="AC-02")
        relative, _ = self.amendment()
        path = self.project / relative
        text = path.read_text().replace('"schema": 1', '"schema": 1, "schema": 1')
        path.write_text(text, encoding="utf-8", newline="")
        authority = self.source({"schema": 1, "kind": "acceptance_amendment", "work": "T-7",
                                 "sha256": sha(text)})
        self.assertFalse(self.amend(relative, authority).ok)

    def test_retirement_evidence_cas_refuses_changed_input_before_apply(self):
        self.observation(REPLACEMENT, ac_id="AC-02")
        relative, authority = self.amendment()
        before = self.canonical_digest()
        apply = ops.apply_plan

        def changed(root, plan):
            (root / ".saipen/evidence/retirement.json").write_text("changed", encoding="utf-8")
            return apply(root, plan)

        with patch.object(ops, "apply_plan", side_effect=changed):
            result = self.amend(relative, authority)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "STALE_STATE")
        self.assertEqual(self.canonical_digest(), before)

    def test_closure_revalidates_retained_amendment_bytes(self):
        self.observation(REPLACEMENT, ac_id="AC-02")
        relative, authority = self.amendment()
        self.assertTrue(self.amend(relative, authority).ok)
        (self.project / ".saipen/evidence/retirement.json").write_text("changed", encoding="utf-8")
        self.assertFalse(self.to_review().ok)

    def test_nonowned_or_nonregular_amendment_paths_refuse_without_writes(self):
        self.observation(REPLACEMENT, ac_id="AC-02")
        _, authority = self.amendment()
        for path in ("../amendment.json", "C:/foreign.json", ".saipen/evidence",
                     ".saipen/evidence/../amendment.json", "tools/saipen.py"):
            before = tree(self.project)
            self.assertFalse(self.amend(path, authority).ok)
            self.assertEqual(tree(self.project), before)

    def test_interrupted_amendment_recovers_at_each_native_write_boundary(self):
        for flag in ("NITRO_CRASH_AFTER_PREPARE", "NITRO_CRASH_AFTER_LOG",
                     "NITRO_CRASH_AFTER_BOARD", "NITRO_CRASH_AFTER_STATE",
                     "NITRO_CRASH_AFTER_VERIFIED"):
            fixture = ContractFixture()
            fixture.setUp()
            original_project, self.project = self.project, fixture.project
            try:
                self.declare()
                self.observation(REPLACEMENT, ac_id="AC-02")
                relative, authority = self.amendment()
                with patch.dict("os.environ", {flag: "1"}), self.assertRaises(SystemExit) as raised:
                    self.amend(relative, authority)
                self.assertEqual(raised.exception.code, 87)
                recovered = auto_recover_pending(self.project)
                self.assertTrue(recovered["ok"], recovered)
                current = parse_board((self.project / ".saipen/BOARD.md").read_text())
                if current["tickets"]["T-7"]["fields"]["verify"] == LIVE:
                    self.assertTrue(self.amend(relative, authority).ok)
                self.assertEqual(scan_pending(self.project), ([], []))
                self.assertTrue(self.finish().ok)
            finally:
                self.project = original_project
                fixture.doCleanups()

    def test_closed_authority_retains_immutable_approval(self):
        self.observation(REPLACEMENT, ac_id="AC-02")
        relative, authority = self.amendment()
        self.assertTrue(self.amend(relative, authority).ok)
        finished = self.finish()
        self.assertTrue(finished.ok, finished.to_dict())
        result = intake.add_requirement(self.project, authority, rid="R001",
                                        text="Apply the exact approved acceptance amendment")
        self.assertTrue(result["ok"], result)
        result = intake.set_disposition(self.project, authority, "R001", "VERIFIED", work="T-7",
                                       evidence=finished.data["event_id"],
                                       verification="Native amendment and closure gates passed")
        self.assertTrue(result["ok"], result)
        result = intake.close_receipt(self.project, authority)
        self.assertTrue(result["ok"], result)
        from saipen_engine.acceptance_contract import gate

        gate(self.project, "T-7", REPLACEMENT, read_history_snapshot(self.project).events)


class WitnessTests(ContractFixture):
    def test_label_alone_does_not_authenticate_a_live_observation(self):
        self.declare()
        self.record("AC-EVIDENCE AC-01 PASS manual witness=LIVE surface=chatgpt.com -- claimed")
        self.assertFalse(self.to_review().ok)

    def test_inferred_manual_label_does_not_authenticate_live(self):
        self.declare()
        self.record("AC-EVIDENCE AC-01 PASS inspection -- a producer inspected something")
        self.assertFalse(self.to_review().ok)

    def test_current_authenticated_live_report_admits_both_gates(self):
        self.declare()
        self.observation(LIVE)
        self.assertTrue(self.finish().ok)

    def test_unchanged_live_criteria_keep_observation_when_only_notes_change(self):
        self.declare()
        self.observation(LIVE)
        self.declare(LIVE + "; implementation note changed without new BUILD")
        self.assertTrue(self.finish().ok)

    def test_model_supplied_observation_is_not_live_proof(self):
        self.declare()
        self.observation(LIVE, trusted=False)
        self.assertFalse(self.to_review().ok)

    def test_wrong_work_contract_or_build_observation_refuses(self):
        for kwargs in ({"work": "T-8"}, {"contract": LIVE + "; changed"}, {"build_event": 999}):
            with self.subTest(kwargs=kwargs):
                self.declare()
                self.observation(**({"contract": LIVE} | kwargs))
                self.assertFalse(self.to_review().ok)

    def test_bad_source_cannot_hide_behind_a_good_observation(self):
        self.declare()
        self.observation(LIVE)
        self.observation(LIVE + "; other contract")
        self.assertFalse(self.to_review().ok)

    def test_raw_board_deletion_cannot_escape_journaled_original(self):
        self.declare()
        path = self.project / ".saipen/BOARD.md"
        fixture_contract(path, "only fixtures")
        self.assertFalse(self.to_review().ok)

    def test_receipt_selector_tamper_is_checked_before_work_filter(self):
        self.declare()
        self.observation(LIVE)
        record = semantic_receipts_for_operation(self.project, "ticket_verify")[-1]
        path = Journal(self.project, record["op_id"]).manifest
        value = json.loads(path.read_text())
        value["receipt_metadata"]["acceptance_contract"]["work"] = "T-999"
        path.write_text(json.dumps(value), encoding="utf-8")
        self.assertFalse(self.to_review().ok)

    def test_ambiguous_declared_criteria_refuse_without_writes(self):
        for text in (LIVE + "; " + LIVE, "AC-01 [OPTIONAL] product", "AC-01"):
            before = tree(self.project)
            result = ops.ticket_verify(self.project, "T-7", "tester", text)
            self.assertFalse(result.ok, result.to_dict())
            self.assertEqual(tree(self.project), before)

    def test_finish_rechecks_source_even_after_review_passed(self):
        self.declare()
        receipt = self.observation(LIVE)
        self.assertTrue(self.to_review().ok)
        self.assertTrue(ops.transition_phase(self.project, "SHIP", "tester", "T-7").ok)
        path = self.project / f".saipen/intake/active/{receipt}.md"
        path.write_text("tampered", encoding="utf-8")
        before = self.canonical_digest()
        self.assertFalse(ops.finish_ticket(self.project, "T-7", "tester").ok)
        self.assertEqual(self.canonical_digest(), before)

    def test_new_build_cannot_reuse_an_old_operator_observation(self):
        self.declare()
        self.observation(LIVE)
        self.assertTrue(ops.transition_phase(self.project, "BUILD", "tester", "T-7").ok)
        self.assertTrue(ops.transition_phase(self.project, "VERIFY", "tester", "T-7").ok)
        self.record("verify -> PASS [target: T-7] conf: high -- current cycle")
        self.assertFalse(self.to_review().ok)

    def test_review_source_cas_refuses_a_change_before_apply(self):
        self.declare()
        receipt = self.observation(LIVE)
        before = self.canonical_digest()
        apply = ops.apply_plan

        def changed(root, plan):
            path = root / f".saipen/intake/active/{receipt}.md"
            path.write_text("changed after admission", encoding="utf-8")
            return apply(root, plan)

        with patch.object(ops, "apply_plan", side_effect=changed):
            result = self.to_review()
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "STALE_STATE")
        self.assertEqual(self.canonical_digest(), before)

    def test_public_cli_exposes_the_existing_writer_and_strict_options(self):
        self.declare()
        self.observation(REPLACEMENT, ac_id="AC-02")
        relative, authority = self.amendment()
        from test_hermetic_env import hermetic_env
        from test_operator_origin_support import cold_command

        env = hermetic_env()
        command = cold_command(
            self.project,
            [sys.executable, str(TOOLS / "saipen.py"), "ticket", "verify", "T-7", REPLACEMENT,
             "--amendment", relative, "--authority", authority, "--agent", "tester",
             "--project-root", str(self.project), "--json"], env,
        )
        proc = subprocess.run(
            command, env=env,
            cwd=TOOLS.parent, capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["code"], "TICKET_VERIFIED")
        ticket = parse_board((self.project / ".saipen/BOARD.md").read_text())["tickets"]["T-7"]
        self.assertEqual(ticket["fields"]["verify"], REPLACEMENT)


class SupersessionTests(ContractFixture):
    def prepare_successor(self, *, equivalent=True, trusted=True):
        self.declare()
        self.assertTrue(ops.ticket_move(
            self.project, "block", "T-7", "tester", "successor work"
        ).ok)
        result = ops.ticket_add(self.project, "tester", "P1", "successor", [],
                                LIVE if equivalent else UNIT)
        self.assertTrue(result.ok, result.to_dict())
        successor = result.data["ticket"]
        self.assertTrue(ops.apply_claim(self.project, successor, "tester", explicit=True).ok)
        for phase in ("BUILD", "VERIFY"):
            self.assertTrue(ops.transition_phase(self.project, phase, "tester", successor).ok)
        if equivalent:
            from saipen_engine.acceptance import build_boundary

            boundary = build_boundary(successor, read_history_snapshot(self.project).events)
            report = self.source({"schema": 1, "kind": "acceptance_witness", "work": successor,
                                  "contract_sha256": sha(LIVE),
                                  "build_boundary": boundary,
                                  "criteria": {"AC-01": {"result": "PASS", "witness": "LIVE",
                                                         "surface": "chatgpt.com"}}})
            text = f"AC-EVIDENCE AC-01 PASS manual witness=LIVE surface=chatgpt.com source={report}"
        else:
            text = "AC-EVIDENCE AC-01 PASS behavioral witness=UNIT surface=fixture"
        self.assertTrue(ops.checkpoint(self.project, "tester", "RUN", successor, text).ok)
        result = ops.checkpoint(self.project, "tester", "RUN", successor,
                                "verify -> PASS [target: T-7] conf: high -- independent outcome")
        self.assertTrue(result.ok, result.to_dict())
        evidence = result.data["event_id"]
        for phase in ("REVIEW", "SHIP"):
            result = ops.transition_phase(self.project, phase, "tester", successor)
            self.assertTrue(result.ok, result.to_dict())
        result = ops.finish_ticket(self.project, successor, "tester")
        self.assertTrue(result.ok, result.to_dict())
        authority = self.source(f"{supersession.GRANT_HEADER}\n\n    T-7 - {successor}\n\nonly.\n",
                                trusted=trusted)
        return successor, evidence, authority

    def test_independently_completed_equivalent_successor_may_settle_old_work(self):
        successor, evidence, authority = self.prepare_successor()
        result = ops.supersede_ticket(self.project, "T-7", successor, "tester",
                                      evidence=evidence, authority=authority)
        self.assertTrue(result.ok, result.to_dict())
        old = parse_board((self.project / ".saipen/BOARD.md").read_text())["tickets"]["T-7"]
        self.assertEqual(old["fields"]["closure_mode"], "superseded_verified")

    def test_weaker_successor_and_model_authority_cannot_settle_live_work(self):
        for kwargs in ({"equivalent": False}, {"trusted": False}):
            # Separate fixtures are needed because completion is immutable.
            fixture = ContractFixture()
            fixture.setUp()
            original_project, self.project = self.project, fixture.project
            try:
                successor, evidence, authority = self.prepare_successor(**kwargs)
                before = tree(self.project)
                result = ops.supersede_ticket(self.project, "T-7", successor, "tester",
                                              evidence=evidence, authority=authority)
                self.assertFalse(result.ok, result.to_dict())
                self.assertEqual(tree(self.project), before)
            finally:
                self.project = original_project
                fixture.doCleanups()


if __name__ == "__main__":
    unittest.main()
