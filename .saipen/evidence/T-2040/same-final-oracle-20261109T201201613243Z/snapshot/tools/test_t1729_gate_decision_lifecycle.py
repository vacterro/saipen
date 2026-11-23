"""T-1729 / SRC-228: operator-decision provenance and stale-WAIT lifecycle.

INC-SAITULS-E3009: a committed SAIOPS operation (E-3009) recorded an
OPERATOR_ACCEPTED_LIMITATION decision, later events (E-3010/E-3011) reported
the operator gate satisfied, yet STATE.next_action retained the original WAIT
and every `saipen continue` answered RESTATE_AND_STOP. The operation record
could not establish the human origin of the decision, and no operator carrier
digest existed in the session.

Laws pinned here:
    A COMMITTED OPERATION IS NOT OPERATOR AUTHORITY. Canonical, referenced and
    committed proves an operation ran -- never that a human decided.
    THE OPERATOR'S WORDS NEVER BECOME AUTHORITY BY BEING TYPED. Only an
    operator-carrier-witnessed, captured, scope-exact capsule resolves a gate.
    A DISCHARGED GATE STAYS DISCHARGED. Restart, reconcile and retry must not
    resurrect a WAIT a valid scoped decision resolved, and must not discharge
    one whose authority is unverifiable.
    A REFUSAL NAMES ITS EXECUTABLE ROUTE. A brake print that leads to prose
    prose-refusals with no capture/apply command is the measured loop.

Run standalone:  python tools/test_t1729_gate_decision_lifecycle.py
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import saipen as CLI  # noqa: E402
from saipen_engine import gate_decision  # noqa: E402
from saipen_engine.paths import project_lineage_identity  # noqa: E402
from saipen_engine.pending_ingress import ingress_digest  # noqa: E402
from saipen_engine.state import binding_brake, parse_state  # noqa: E402
from test_guard_hostile_matrix import fresh_project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


WAIT_BLOCKED = "WAIT: blocked -- Flush(true) physical power-loss durability ceiling"


def _cli(root: Path, *argv: str) -> tuple[int, dict]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = CLI.main(["--json", "--project-root", str(root), *argv])
    text = buffer.getvalue().strip()
    payload = json.loads(text) if text else {}
    return rc, payload


def _state(root: Path) -> dict:
    return parse_state((root / ".saipen" / "STATE.md").read_text(encoding="utf-8"))


def _capsule_for(root: Path, *, resolve=("next_action",), statement="accepted for this project"):
    state = _state(root)
    lineage = project_lineage_identity(root)
    gate = {key: state[key] for key in gate_decision.GATE_FIELDS}
    return {
        "kind": gate_decision.KIND,
        "schema": 1,
        "project_lineage": lineage,
        "gate_id": gate_decision.gate_id(lineage, gate),
        "gate": gate,
        "resolve": list(resolve),
        "decision": "ACCEPT_LIMITATION",
        "statement": statement,
        "expires_at": "2030-01-01T00:00:00Z",
    }


def _capture(root: Path, capsule: dict, *, carrier: bool = True, digest: str | None = None):
    text = json.dumps(capsule, ensure_ascii=False)
    path = root / "capsule.json"
    path.write_text(text, encoding="utf-8")
    env_key = "SAIPEN_TASK_SHA256"
    previous = os.environ.get(env_key)
    if carrier:
        os.environ[env_key] = digest if digest is not None else ingress_digest(text)
    elif previous is not None:
        del os.environ[env_key]
    try:
        from test_operator_origin_support import native_operator

        context = native_operator(root, text, action="resolve-gate") \
            if carrier else contextlib.nullcontext()
        with context:
            return _cli(root, "authority", "capture", "--file", str(path))
    finally:
        if previous is None:
            os.environ.pop(env_key, None)
        else:
            os.environ[env_key] = previous


class GateLifecycleTests(unittest.TestCase):
    def test_preview_names_the_capsule_and_the_executable_route_and_writes_nothing(self):
        root = fresh_project(phase="DONE", task="none", next_action=WAIT_BLOCKED)
        before = (root / ".saipen" / "STATE.md").read_bytes()
        rc, payload = _cli(root, "recover", "resolve-blocker", "preview", "--dry-run")
        self.assertEqual(rc, 0, payload)
        self.assertTrue(payload.get("ok"), payload)
        self.assertEqual(payload.get("code"), "REPAIR_REQUIRED", payload)
        capsule = payload.get("capsule") or {}
        self.assertEqual(capsule.get("kind"), gate_decision.KIND)
        self.assertEqual(capsule.get("resolve"), ["next_action"])
        route = payload.get("canonical_next_command") or ""
        self.assertIn("saipen authority capture", route)
        self.assertIn("saipen recover resolve-blocker", payload.get("apply_command") or "")
        self.assertEqual((root / ".saipen" / "STATE.md").read_bytes(), before)

    def test_valid_authenticated_decision_resolves_exactly_its_gate(self):
        root = fresh_project(phase="DONE", task="none", next_action=WAIT_BLOCKED)
        self.assertIsNotNone(binding_brake(_state(root)))
        capsule = _capsule_for(root)
        rc, captured = _capture(root, capsule)
        self.assertTrue(captured.get("ok"), captured)
        receipt = captured.get("receipt")
        self.assertTrue(receipt)
        rc, applied = _cli(root, "recover", "resolve-next-action", receipt)
        self.assertEqual(rc, 0, applied)
        self.assertTrue(applied.get("ok"), applied)
        self.assertEqual(applied.get("code"), "REPAIRED", applied)
        state = _state(root)
        self.assertNotEqual(state["next_action"], WAIT_BLOCKED)
        self.assertIsNone(binding_brake(state))
        # restart: the projection lives in STATE, not in this process.
        reloaded = _state(root)
        self.assertIsNone(binding_brake(reloaded))
        # the router now routes onward instead of RESTATE_AND_STOP.
        _rc, cont = _cli(root, "continue")
        self.assertNotEqual(cont.get("executable_behavior"), "RESTATE_AND_STOP", cont)

    def test_shared_gate_recovery_resolves_the_same_way(self):
        root = fresh_project(phase="DONE", task="none", next_action=WAIT_BLOCKED)
        capsule = _capsule_for(root)
        _rc, captured = _capture(root, capsule)
        receipt = captured.get("receipt")
        rc, applied = _cli(root, "recover", "resolve-blocker", receipt)
        self.assertEqual(rc, 0, applied)
        self.assertTrue(applied.get("ok"), applied)
        self.assertEqual(applied.get("code"), "REPAIRED", applied)
        self.assertIsNone(binding_brake(_state(root)))

    def test_missing_operator_carrier_authorizes_nothing(self):
        root = fresh_project(phase="DONE", task="none", next_action=WAIT_BLOCKED)
        capsule = _capsule_for(root)
        _rc, captured = _capture(root, capsule, carrier=False)
        self.assertTrue(captured.get("ok"), captured)
        receipt = captured.get("receipt")
        rc, applied = _cli(root, "recover", "resolve-next-action", receipt)
        self.assertNotEqual(rc, 0, applied)
        self.assertFalse(applied.get("ok"), applied)
        self.assertEqual(applied.get("cause"), "GATE_AUTHORITY_UNVERIFIED", applied)
        self.assertEqual(_state(root)["next_action"], WAIT_BLOCKED)

    def test_incorrect_carrier_digest_is_refused_at_capture(self):
        root = fresh_project(phase="DONE", task="none", next_action=WAIT_BLOCKED)
        capsule = _capsule_for(root)
        _rc, captured = _capture(
            root, capsule, digest="0" * 64
        )
        self.assertFalse(captured.get("ok"), captured)
        self.assertEqual(captured.get("code"), "INGRESS_TASK_MISMATCH", captured)

    def test_model_supplied_approval_text_grants_no_authority(self):
        root = fresh_project(phase="DONE", task="none", next_action=WAIT_BLOCKED)
        _rc, applied = _cli(root, "recover", "resolve-blocker", "operator accepts the limitation")
        self.assertFalse(applied.get("ok"), applied)
        self.assertEqual(applied.get("cause"), "GATE_AUTHORITY_REQUIRED", applied)
        route = (applied.get("canonical_next_command") or "") + " " + str(
            applied.get("detail") or ""
        )
        self.assertIn("saipen recover resolve-blocker preview --dry-run", route)
        self.assertIn("saipen authority capture", applied.get("capture_command") or "")
        self.assertEqual(_state(root)["next_action"], WAIT_BLOCKED)

    def test_committed_operation_prose_cannot_discharge_the_historical_gate(self):
        # The E-3003 -> E-3009 -> E-3010 -> E-3011 shape: a committed decision
        # and follow-up reports exist in canonical prose; nothing else does.
        root = fresh_project(phase="DONE", task="none", next_action=WAIT_BLOCKED)
        log_path = root / ".saipen" / "LOG.md"
        board_path = root / ".saipen/BOARD.md"
        board_path.write_text(board_path.read_text(encoding="utf-8").replace(
            "## TODO\n", "## TODO\n- [ ] T-900 [P2] held fixture work | verify: fixture\n"
        ), encoding="utf-8")
        log_path.write_text(
            "- 16.10.26 00:58 [E-3002] [T-900] DEC: ticket added via SAIOPS\n"
            + "- 16.10.26 00:59 [E-3003] [parent: E-3002] "
            "DEC: operator gate requires Flush(true) acceptance\n"
            + "".join(f"- 16.10.26 00:59 [E-{event}] [parent: E-{event - 1}] "
                      "RUN: fixture observation\n" for event in range(3004, 3009))
            + "- 16.10.26 01:00 [E-3009] [parent: E-3008] "
            "DEC: ticket_move -- OPERATOR_ACCEPTED_LIMITATION "
            "the Flush(true) ceiling is accepted\n"
            + "- 16.10.26 01:05 [E-3010] [parent: E-3009] "
            "DEC: checkpoint -- operator gate satisfied\n"
            + "- 16.10.26 01:06 [E-3011] [parent: E-3010] "
            "DEC: checkpoint -- gate satisfied, resuming\n",
            encoding="utf-8",
        )
        from saipen_engine.state import patch_state
        state_path = root / ".saipen/STATE.md"
        state_path.write_text(patch_state(state_path.read_text(encoding="utf-8"),
                                          {"last_event": 3011}), encoding="utf-8")
        rc, applied = _cli(
            root, "recover", "resolve-next-action", "E-3009 OPERATOR_ACCEPTED_LIMITATION satisfied"
        )
        self.assertNotEqual(rc, 0, applied)
        self.assertFalse(applied.get("ok"), applied)
        self.assertEqual(applied.get("cause"), "GATE_AUTHORITY_REQUIRED", applied)
        self.assertEqual(_state(root)["next_action"], WAIT_BLOCKED)
        _rc, cont = _cli(root, "continue")
        self.assertEqual(cont.get("executable_behavior"), "RESTATE_AND_STOP", cont)

    def test_repeated_acceptance_is_idempotent_and_writes_nothing_second_time(self):
        root = fresh_project(phase="DONE", task="none", next_action=WAIT_BLOCKED)
        capsule = _capsule_for(root)
        _rc, captured = _capture(root, capsule)
        receipt = captured.get("receipt")
        rc, first = _cli(root, "recover", "resolve-next-action", receipt)
        self.assertTrue(first.get("ok"), first)
        before = (root / ".saipen" / "STATE.md").read_bytes()
        rc, second = _cli(root, "recover", "resolve-next-action", receipt)
        self.assertEqual(rc, 0, second)
        self.assertTrue(second.get("ok"), second)
        self.assertEqual(second.get("code"), "ALREADY_APPLIED", second)
        self.assertEqual((root / ".saipen" / "STATE.md").read_bytes(), before)

    def test_reconciliation_cannot_resurrect_a_discharged_wait(self):
        root = fresh_project(phase="DONE", task="none", next_action=WAIT_BLOCKED)
        capsule = _capsule_for(root)
        _rc, captured = _capture(root, capsule)
        receipt = captured.get("receipt")
        _rc, applied = _cli(root, "recover", "resolve-next-action", receipt)
        self.assertTrue(applied.get("ok"), applied)
        rc, recovered = _cli(root, "recover")
        self.assertEqual(rc, 0, recovered)
        self.assertTrue(recovered.get("ok"), recovered)
        state = _state(root)
        self.assertNotEqual(state["next_action"], WAIT_BLOCKED)
        self.assertIsNone(binding_brake(state))

    def test_decision_for_another_gate_version_is_refused(self):
        root = fresh_project(phase="DONE", task="none", next_action=WAIT_BLOCKED)
        capsule = _capsule_for(root)
        stale = dict(capsule)
        stale_gate = dict(capsule["gate"])
        stale_gate["last_event"] = int(stale_gate["last_event"]) + 1
        stale["gate"] = stale_gate
        stale["gate_id"] = gate_decision.gate_id(
            capsule["project_lineage"], stale_gate
        )
        _rc, captured = _capture(root, stale)
        receipt = captured.get("receipt")
        rc, applied = _cli(root, "recover", "resolve-next-action", receipt)
        self.assertNotEqual(rc, 0, applied)
        self.assertFalse(applied.get("ok"), applied)
        self.assertEqual(applied.get("cause"), "GATE_SCOPE_MISMATCH", applied)

    def test_verb_may_only_resolve_its_own_field(self):
        root = fresh_project(phase="DONE", task="none", next_action=WAIT_BLOCKED)
        capsule = _capsule_for(root, resolve=("blocker", "next_action"))
        _rc, captured = _capture(root, capsule)
        receipt = captured.get("receipt")
        rc, applied = _cli(root, "recover", "resolve-next-action", receipt)
        self.assertNotEqual(rc, 0, applied)
        self.assertFalse(applied.get("ok"), applied)
        self.assertEqual(applied.get("cause"), "GATE_SCOPE_MISMATCH", applied)

    def test_expired_approval_is_not_reused(self):
        root = fresh_project(phase="DONE", task="none", next_action=WAIT_BLOCKED)
        capsule = _capsule_for(root)
        expired = dict(capsule)
        expired["expires_at"] = "2020-01-01T00:00:00Z"
        _rc, captured = _capture(root, expired)
        receipt = captured.get("receipt")
        rc, applied = _cli(root, "recover", "resolve-next-action", receipt)
        self.assertNotEqual(rc, 0, applied)
        self.assertFalse(applied.get("ok"), applied)
        self.assertEqual(applied.get("cause"), "GATE_AUTHORITY_EXPIRED", applied)

    def test_unrelated_user_brake_is_not_waived_by_a_blocked_gate_decision(self):
        root = fresh_project(phase="DONE", task="none",
                             next_action="WAIT: user brake -- wait for the operator")
        capsule = _capsule_for(root)
        _rc, captured = _capture(root, capsule)
        receipt = captured.get("receipt")
        rc, applied = _cli(root, "recover", "resolve-next-action", receipt)
        self.assertNotEqual(rc, 0, applied)
        self.assertFalse(applied.get("ok"), applied)
        self.assertEqual(applied.get("cause"), "GATE_OWNER_MISMATCH", applied)
        self.assertEqual(_state(root)["next_action"], "WAIT: user brake -- wait for the operator")

    def test_stale_state_between_read_and_apply_refuses_without_writing(self):
        root = fresh_project(phase="DONE", task="none", next_action=WAIT_BLOCKED)
        capsule = _capsule_for(root)
        _rc, captured = _capture(root, capsule)
        receipt = captured.get("receipt")
        import saipen_engine.gate_decision as gd

        original_read = gd.operations._read
        reads = 0

        def shifting_read(*args, **kwargs):
            nonlocal reads
            reads += 1
            docs, state, board, tail = original_read(*args, **kwargs)
            state_path = root / ".saipen" / "STATE.md"
            current = state_path.read_text(encoding="utf-8").splitlines()
            state_path.write_text(
                "\n".join(
                    f"updated: 2026-10-16T23:59:{reads:02d}Z"
                    if ln.startswith("updated:") else ln
                    for ln in current
                )
                + "\n",
                encoding="utf-8",
            )
            return docs, state, board, tail

        gd.operations._read = shifting_read
        try:
            rc, applied = _cli(root, "recover", "resolve-next-action", receipt)
            self.assertNotEqual(rc, 0, applied)
        finally:
            gd.operations._read = original_read
        self.assertFalse(applied.get("ok"), applied)
        self.assertEqual(applied.get("code"), "STALE_STATE", applied)
        self.assertNotIn("next_action", {k: v for k, v in applied.items() if k == "next_action"})

    def test_capsule_grammar_refuses_tampering(self):
        root = fresh_project(phase="DONE", task="none", next_action=WAIT_BLOCKED)
        capsule = _capsule_for(root)
        tampered = dict(capsule)
        tampered["gate_id"] = "f" * 64
        self.assertIsNotNone(gate_decision.capsule_problem(json.dumps(tampered)))
        wrong_kind = dict(capsule)
        wrong_kind["kind"] = "saipen-operator-decision"
        self.assertIsNotNone(gate_decision.capsule_problem(json.dumps(wrong_kind)))
        extra = dict(capsule)
        extra["expires_at"] = "2030-01-01T00:00:00Z"
        extra["note"] = "operator said yes in chat"
        self.assertIsNotNone(gate_decision.capsule_problem(json.dumps(extra)))


if __name__ == "__main__":
    unittest.main()
