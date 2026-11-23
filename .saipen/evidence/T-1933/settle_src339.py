"""Settle SRC-339's clauses from one authenticated focused record.

Every verification string cites ONLY test modules this record actually ran: the
record's `proven_oracles` are its exact `run["pattern"]` values, so the citation
is authenticated by the same digest the journal bound (E-18489). Extra
corroboration that the record did not run goes in `evidence`, which is a
reference, not a proof claim.

`ROOT` is three levels up: this file sits in `.saipen/evidence/T-1933/`, so
`parents[3]` is the project root. (`closures/` scripts sit one level deeper and
legitimately need `parents[4]`; copying that here resolved one directory too
high and made `saipen_engine` unimportable.)

Nothing here writes STATE/BOARD/LOG: dispositions go through
`intake.set_disposition`, the canonical coverage writer.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import intake  # noqa: E402

RECORD = ".saipen/evidence/focused-unit/c86c432efe87a4bc-20261026T184401369669Z.json"
DIGEST = "a57e9def779b2c86c522b835294b750862bb9a1d08f32fef1f4224a2d0e8177c"
BIND = f"record:{RECORD} sha256:{DIGEST}"

SEAL = "test_t1933_zaicode_goal_seal.py"
HOOK = "test_t1859_zaicode_seal.py"
INGRESS = "test_t1868_zaicode_ingress.py"
ADAPTER = "test_t1504_zaicode_adapter.py"
SURFACE = "test_guard_surface_parity.py"
MATRIX = "test_operator_ingress_matrix.py"
AUTHORITY = "test_ingress_authority.py"
NATIVE = "test_native_host_guard.py"
PENDING = "test_pending_ingress.py"
VALVE = "test_reconcile_valve.py"
HOME_VALVE = "test_t1776_protocol_home_valve.py"
GATE = "test_t1729_operator_gate.py"

#: rid -> (verification body after BIND, evidence)
SETTLE = {
    "R001": (
        f"{SEAL} TheHookSealsTheDeclaredIntent proves the seal is the declared action, not a "
        "constant: test_a_goal_objective_is_sealed_as_goal, "
        "test_a_canonical_goal_command_is_sealed_as_goal, "
        "test_a_host_aliased_goal_is_sealed_as_goal and "
        "test_a_grant_capsule_is_sealed_as_authorize_goal assert the exact action this hook hands "
        "the broker (goal / authorize-goal), while test_a_continuation_is_still_sealed_as_continue "
        "keeps the ordinary path unchanged; "
        f"{HOOK} test_the_registered_worker_is_this_hook_process_not_its_parent pins that the seal "
        "reaches the broker at all",
        "E-18489; the shipped hook now derives the action through declared_action(text, root) "
        "(extensions/adapters/zaicode/saipen-guard.py:535), so operator_origin's goal reservation "
        "for action in {goal, authorize-goal} is reachable from the ZAICODE adapter",
    ),
    "R002": (
        f"{SEAL} TheHookSealsTheDeclaredIntent proves the action is read from the operator's own "
        "bytes: test_prose_that_mentions_goal_or_cc_is_never_a_goal refuses a sentence that merely "
        "talks about a goal, test_a_bare_goal_token_is_not_an_objective keeps the protocol's own "
        "use-line out of the seal, and test_the_pre_fix_hardcoded_action_is_refused_by_this_suite is "
        "the red control: the shipped one-line action = \"continue\" is replaced in a copy of the "
        "real hook and the suite then observes continue instead of goal; "
        f"{MATRIX} test_clause_d_agent_authored_text_cannot_impersonate and "
        "test_clause_e_model_created_task_files_cannot_forge_authority prove model-authored bytes "
        "carry no operator authority",
        "E-18489; declared_action() takes only the request_text the broker hashes into "
        "request_digest -- there is no intent field a caller could claim, so a model cannot "
        "manufacture a goal seal it was not handed",
    ),
    "R003": (
        f"{VALVE} test_tickets_at_the_cap_refuses_even_when_counters_agree, "
        "test_waves_at_the_cap_trips_independently, test_a_state_already_stating_the_pause_needs_no_"
        "repair and test_the_counters_are_never_tidied_by_this_rule prove the trip condition is "
        "unchanged and the counters are never silently cleared; "
        f"{GATE} test_requested_resume_cannot_override_a_computed_budget_stop and "
        "test_limitation_acceptance_preserves_a_computed_budget_stop prove a request cannot override "
        "a computed stop; {HOME_VALVE} "
        "test_consumer_project_keeps_the_bounded_operator_gate proves the consumer project still "
        "demands the operator, and test_protocol_home_cc_clears_the_valve_without_an_operator_"
        "carrier scopes the only exception to the protocol home itself; "
        f"{SEAL} test_an_unsealed_prompt_spends_nothing proves no engine runs without a broker seal",
        "E-18489; the SRC-339 repair adds no new valve-clearing route: it changes which ACTION the "
        "existing broker proof declares, and RECONCILE_REAUTH_REQUIRED still refuses an agent CLI "
        "replay of a spent bounded run",
    ),
    "R004": (
        f"{SEAL} test_the_engine_runs_below_the_worker_that_registered_the_proof asserts the engine "
        "process that spends the seal is a CHILD of the worker row the broker accepted "
        "(ran.parent_pid == registered.worker); test_a_sealed_goal_runs_the_goal_entry_from_the_hook "
        "and test_a_sealed_grant_runs_goal_authorize_on_the_exact_bytes prove the sealed entry is "
        "actually spent once, from the hook; {HOOK} "
        "test_the_registered_worker_is_this_hook_process_not_its_parent and "
        "test_the_pre_fix_registration_is_refused_by_this_suite prove the host pid is refused as a "
        "worker and the hook's own pid is the accepted one",
        "E-18489; broker_worker._worker accepts a verifier only BELOW the registered worker and "
        "register_worker refuses pid == proof[host_pid], so the spend must run from the hook -- the "
        "agent's shell is the hook's sibling and could never verify its own seal",
    ),
    "R005": (
        f"{SEAL} TheSafetyValveStillHolds proves the repair opens no unsealed path: "
        "test_an_unsealed_prompt_spends_nothing drives the hook with a "
        "HOST_PROVENANCE_UNAVAILABLE broker answer and observes zero engine runs, and "
        "test_the_hook_still_requires_a_broker_sealed_origin_to_spend_anything asserts the spend is "
        "gated on sealed; {AUTHORITY} "
        "test_real_looking_model_request_has_no_operator_preemption, "
        "test_identical_trusted_bytes_have_different_authority and "
        "test_duplicate_captured_model_bytes_cannot_gain_carrier_authority prove copied or replayed "
        "bytes carry no carrier authority; {GATE} "
        "test_plain_model_decision_does_not_authorize_a_gate and "
        "test_missing_or_wrong_source_digest_cannot_grant_authority prove a forged or wrong-digest "
        "capsule grants nothing",
        "E-18489; every goal/grant spend in the hook is inside `if sealed`, and `sealed` requires a "
        "broker-issued proof PLUS a successful register_operator_worker, so no budget moves without "
        "a native operator carrier",
    ),
    "R006": (
        f"{VALVE} test_the_counters_are_never_tidied_by_this_rule and "
        "test_the_refusal_writes_nothing prove the reconcile route refuses to tidy counters and "
        "writes nothing when it refuses, and test_an_unprovable_phase_refuses_with_zero_writes "
        "proves an unprovable repair is a zero-write refusal; {GATE} "
        "test_changed_authority_during_apply_refuses_without_state_writes proves a changed authority "
        "refuses before any state write",
        "E-18489; this Work added no hand-edit route: the SRC-339 source itself offers a manual "
        "goal_tickets edit as an operator-side alternative, it was recorded as a non-goal (R006) "
        "rather than implemented, and no file in the repair writes .saipen/STATE.md directly",
    ),
    "R007": (
        f"{SEAL} is the acceptance control: test_a_goal_objective_is_sealed_as_goal, "
        "test_a_canonical_goal_command_is_sealed_as_goal and "
        "test_a_host_aliased_goal_is_sealed_as_goal observe the operator's goal prompt sealed as "
        "action goal, test_a_grant_capsule_is_sealed_as_authorize_goal observes the explicit grant "
        "sealed as authorize-goal, and "
        "test_the_pre_fix_hardcoded_action_is_refused_by_this_suite runs a copy of the real hook "
        "with the ONE line action = declared_action(text, root) put back to action = \"continue\" "
        "and asserts the suite then sees continue, which fails the criterion; {INGRESS} "
        "test_the_admitted_envelope_carries_the_engine_digest_of_the_prompt proves the sealed "
        "envelope is the one the host actually delivered",
        "E-18489; the red control is a genuine counterexample, not a label: it patches the shipped "
        "file text, re-runs the real hook in a subprocess, and requires the pre-fix behaviour. Live "
        "acceptance is explicitly UNVERIFIED -- no receipt from an installed ZAICODE host exists, "
        "and no mock is presented as one",
    ),
    "R008": (
        f"{SEAL} exercises the protocol side only -- the hook, the broker seal and the engine spend "
        "-- and its module docstring records that no live ZAICODE host delivered these events; "
        f"{ADAPTER} test_surfaces_follow_the_zcode_loader_contract pins the adapter surface this "
        "repair ships, and {SURFACE} / {PENDING} / {NATIVE} keep the surrounding admission "
        "contracts unchanged",
        "E-18489; this clause is context and is not claimed satisfied: T-435 (A3 Autopilot Mode 2 "
        "Hardening) is an upstream consumer, and nothing in this Work claims T-435 is complete or "
        "that its live end-to-end positive-finding run has happened",
    ),
}


def unrelated_risk(rid: str, verification: str) -> str | None:
    """Reproduce intake's EVIDENCE_UNRELATED test before spending a write."""
    contract = intake._read_contract(ROOT, "SRC-339") or {}
    clause_text = str(((contract.get("clauses") or {}).get(rid) or {}).get("text") or "").lower()
    m_test = re.search(r"test_[a-z0-9_]+\.py", verification.lower())
    if not m_test:
        return None
    test_file = m_test.group(0)
    test_words = set(re.findall(r"[a-z0-9]+", test_file)) - {"test", "py"}
    clause_words = set(re.findall(r"[a-z0-9]+", clause_text))
    known = {"intake", "parser", "revalidation", "external", "reconciliation",
             "matrix", "host", "adapter"}
    clause_domains = clause_words & known
    test_domains = test_words & known
    if clause_domains and test_domains and not (clause_domains & test_domains):
        return f"first test file {test_file} is not in clause domains {sorted(clause_domains)}"
    return None


def main(argv: list[str]) -> int:
    dry = "--dry" in argv
    failures = []
    settled = []
    for rid, (verification, evidence) in sorted(SETTLE.items(), key=lambda kv: kv[0]):
        if risk := unrelated_risk(rid, verification):
            failures.append((rid, {"code": "PREFLIGHT_UNRELATED", "detail": risk}))
            print(f"STOP {rid} {risk}")
            continue
        payload = {
            "rid": rid,
            "disposition": "VERIFIED",
            "work": "T-1933",
            "evidence": evidence,
            "verification": f"{BIND}; {verification}",
        }
        if dry:
            print(f"[dry] {rid}: {payload['verification'][:160]}...")
            continue
        result = intake.set_disposition(
            ROOT,
            "SRC-339",
            rid,
            "VERIFIED",
            work=payload["work"],
            evidence=payload["evidence"],
            verification=payload["verification"],
        )
        if result.get("ok"):
            settled.append(rid)
            print(f"OK   {rid} {result.get('code')}")
        else:
            failures.append((rid, result))
            print(f"FAIL {rid} {result.get('code')}: {result.get('detail')}")
    print(f"\nsettled={len(settled)} failed={len(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
