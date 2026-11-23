"""T-2106: P0 reauth deadlock, WAIT erasure on DONE, 4-way alignment, and host policy.

Covers the regressions documented in
``audit/SAIHANDOFF_P0_REAUTH_DEADLOCK_ANTIGRAVITY_ZAICODE_20261119.md``:

  1. ``finish_ticket`` and ``transition(..., "DONE")`` on a bounded consumer
     goal keep a tripped safety-valve ``WAIT:`` intact instead of erasing it to
     ``saipen continue``, ``PHASE SCOUT``, or ``saipen crew``.
  2. ``binding_brake``, CLI ``claim``, and direct ``operations.apply_claim``
     refuse ``WAIT_BLOCKED`` when ``budget_exhausted`` holds without renewal
     even if a prior finish erased ``WAIT:`` (preventing ``goal_tickets`` > 20).
  3. On a drifted consumer valve (``goal_tickets=31``, ``next_action='saipen continue'``),
     ``reconcile``, ``saipen status --json``, ``saipen explain-next --json``,
     ``saipen start``, and ``saipen cc --json`` all agree on ``WAIT_USER`` /
     ``RECONCILE_REAUTH_REQUIRED`` and ``canonical_next_command: null``.
  4. Non-prompt-hook hosts (``antigravity``, ``gemini``) expose accurate
     ``host_capability`` metadata on ``reset_authority`` / ``cc`` while still
     enforcing ``operator_carrier`` (no ``model_supplied`` bypass).
  5. ``saipen/REGISTRY.json`` exposes ``protocol_admission.host_authority.hosts.zaicode``.
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import (  # noqa: E402
    codec,
    entry,
    goal_authority,
    host_authority_broker,
    operations,
    reconcile,
    router,
    state,
)
from test_hermetic_env import isolate_host_session  # noqa: E402

CURRENT_STYLE_CONTRACT = "ded-069a4c52"

CONSUMER_LINEAGE = "lineage-fedcba9876543210fedcba9876543210"
HOME_LINEAGE = "lineage-0123456789abcdef0123456789abcdef"
VALVE_WAIT = "WAIT: safety valve reached (0 waves / 20 tickets) -- run 'cc' to continue"


def setUpModule() -> None:
    isolate_host_session()


def _init_git_repo(root: Path, rel: str = "tools/x.py") -> None:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", rel], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=root, check=True)
    target.write_text("value = 2\n", encoding="utf-8")


def _build_consumer_project(
    root: Path,
    *,
    phase: str = "DONE",
    task: str = "none",
    next_action: str = "saipen continue",
    goal_tickets: int = 31,
    goal_waves: int = 0,
    with_doing: bool = False,
) -> Path:
    (root / ".saipen").mkdir(parents=True, exist_ok=True)
    (root / ".saipen" / "IDENTITY.md").write_text(
        f"---\nproject_lineage: {CONSUMER_LINEAGE}\n---\n",
        encoding="utf-8",
    )
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "# Log",
        "- 01.01.20 00:00 [E-001] [agent: a] [op: goal-1] DEC: goal pivot -- work",
    ]
    ev = 2
    for idx in range(goal_tickets):
        lines.append(
            f"- 01.01.20 00:01 [E-{ev:03d}] [agent: a] [op: tick-{idx}] "
            f"DEC: goal_tickets {idx}->{idx + 1}"
        )
        ev += 1
    if with_doing:
        lines.extend(
            [
                f"- 01.01.20 00:02 [E-{ev:03d}] [T-1] [agent: a] [op: ticket-1] DEC: add T-1 [P1] ship work",
                f"- 01.01.20 00:02 [E-{ev + 1:03d}] [T-2] [agent: a] [op: ticket-2] DEC: add T-2 [P1] next work",
                f"- 01.01.20 00:02 [E-{ev + 2:03d}] [T-1] [agent: a] [op: claim-1] "
                "DEC: claim via SAIOPS -- owner a",
                f"- 01.01.20 00:03 [E-{ev + 3:03d}] [T-1] [agent: a] [op: tr-1] RUN: transition to SCOUT",
                f"- 01.01.20 00:03 [E-{ev + 4:03d}] [T-1] [agent: a] [op: cp-1] DEC: SCOUT: PASS [target: T-1] conf: high -- ok",
                f"- 01.01.20 00:03 [E-{ev + 5:03d}] [T-1] [agent: a] [op: tr-2] RUN: transition to BUILD",
                f"- 01.01.20 00:03 [E-{ev + 6:03d}] [T-1] [agent: a] [op: cp-2] DEC: BUILD: PASS [target: T-1] conf: high -- ok",
                f"- 01.01.20 00:03 [E-{ev + 7:03d}] [T-1] [agent: a] [op: tr-3] RUN: transition to VERIFY",
                f"- 01.01.20 00:03 [E-{ev + 8:03d}] [T-1] [agent: a] [op: cp-3] RUN: verify -> PASS [target: T-1] conf: high -- ok",
                f"- 01.01.20 00:03 [E-{ev + 9:03d}] [T-1] [agent: a] [op: tr-4] RUN: transition to REVIEW",
                f"- 01.01.20 00:03 [E-{ev + 10:03d}] [T-1] [agent: a] [op: cp-4] DEC: REVIEW: PASS [target: T-1] conf: high -- ok",
                f"- 01.01.20 00:03 [E-{ev + 11:03d}] [T-1] [agent: a] [op: tr-5] RUN: transition to SHIP",
            ]
        )
        ev += 12
        board_text = (
            "# Board\n"
            "## DOING\n"
            "- [/] T-1 [P1] ship work | owner: a | claim_time: 2020-01-01T00:00:00Z | verify: ok\n"
            "## TODO\n"
            "- [ ] T-2 [P1] next work | verify: ok\n"
            "## DONE\n"
            "## BLOCKED\n"
        )
    else:
        lines.extend(
            [
                f"- 01.01.20 00:02 [E-{ev:03d}] [T-1] [agent: a] [op: ticket-1] DEC: add T-1 [P1] ship work",
                f"- 01.01.20 00:02 [E-{ev + 1:03d}] [T-2] [agent: a] [op: ticket-2] DEC: add T-2 [P1] next work",
                f"- 01.01.20 00:02 [E-{ev + 2:03d}] [T-1] [agent: a] [op: claim-1] "
                "DEC: claim via SAIOPS -- owner a",
                f"- 01.01.20 00:03 [E-{ev + 3:03d}] [T-1] [agent: a] [op: tr-1] RUN: transition to SCOUT",
                f"- 01.01.20 00:03 [E-{ev + 4:03d}] [T-1] [agent: a] [op: tr-2] RUN: transition to BUILD",
                f"- 01.01.20 00:03 [E-{ev + 5:03d}] [T-1] [agent: a] [op: tr-3] RUN: transition to VERIFY",
                f"- 01.01.20 00:03 [E-{ev + 6:03d}] [T-1] [agent: a] [op: tr-4] RUN: transition to REVIEW",
                f"- 01.01.20 00:03 [E-{ev + 7:03d}] [T-1] [agent: a] [op: tr-5] RUN: transition to SHIP",
            ]
        )
        ev += 8
        board_text = (
            "# Board\n"
            "## DOING\n"
            "## TODO\n"
            "- [ ] T-2 [P1] next work | verify: ok\n"
            "## DONE\n"
            "- [x] T-1 [P1] ship work | verify: ok | closure_mode: own_patch\n"
            "## BLOCKED\n"
        )
    (root / ".saipen" / "LOG.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / ".saipen" / "BOARD.md").write_text(board_text, encoding="utf-8")
    (root / ".saipen" / "STATE.md").write_text(
        f"---\n"
        f"phase: {phase}\n"
        f"task: {task}\n"
        f'next_action: "{next_action}"\n'
        f"blocker: none\n"
        f"transition_from: {'REVIEW' if with_doing else 'SHIP'}\n"
        f"saipen_version: 8\n"
        f"schema_version: 3\n"
        f"style_contract: {CURRENT_STYLE_CONTRACT}\n"
        f"agent: a\n"
        f"mode: full\n"
        f"updated: {now}\n"
        f"last_event: {ev - 1}\n"
        f"execution_intent: goal\n"
        f"goal_waves: {goal_waves}\n"
        f"goal_tickets: {goal_tickets}\n"
        f"continuation_authority: operator_required\n"
        f"authority_source: E-001\n"
        f"authority_until: budget\n"
        f"safety_valve_mode: hard_wait\n"
        f"saipen_home: {REPO}\n"
        f"---\n",
        encoding="utf-8",
    )
    return root


def _cli(root: Path, *args: str, env_extra: dict | None = None) -> tuple[int, dict]:
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, str(TOOLS / "saipen.py"), "--project-root", str(root), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    payload = {}
    if proc.stdout.strip().startswith("{"):
        payload = json.loads(proc.stdout)
    return proc.returncode, payload


class ReauthDeadlockRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="saipen-t2106-")
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    def test_finish_ticket_and_transition_done_preserve_tripped_consumer_valve_wait(self):
        root = self.base / "finish-preserves-wait"
        _init_git_repo(root)
        # Step through a real SHIP ticket holding a tripped consumer safety valve.
        (root / ".saipen").mkdir()
        (root / ".saipen" / "IDENTITY.md").write_text(
            f"---\nproject_lineage: {CONSUMER_LINEAGE}\n---\n", encoding="utf-8"
        )
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        seed_lines = [
            "# Log",
            "- 01.01.20 00:00 [E-001] [agent: a] [op: goal-1] DEC: goal pivot -- work",
        ]
        ev = 2
        for idx in range(19):
            seed_lines.append(
                f"- 01.01.20 00:01 [E-{ev:03d}] [agent: a] [op: seed-{idx}] "
                f"DEC: goal_tickets {idx}->{idx + 1}"
            )
            ev += 1
        seed_lines.extend(
            [
                f"- 01.01.20 00:01 [E-{ev:03d}] [T-1] [agent: a] [op: ticket-1] DEC: add T-1 [P1] one",
                f"- 01.01.20 00:01 [E-{ev + 1:03d}] [T-2] [agent: a] [op: ticket-2] DEC: add T-2 [P1] two",
            ]
        )
        (root / ".saipen" / "LOG.md").write_text("\n".join(seed_lines) + "\n", encoding="utf-8")
        (root / ".saipen" / "BOARD.md").write_text(
            "# Board\n## DOING\n## TODO\n- [ ] T-1 [P1] one | verify: ok\n- [ ] T-2 [P1] two | verify: ok\n## DONE\n## BLOCKED\n",
            encoding="utf-8",
        )
        (root / ".saipen" / "STATE.md").write_text(
            f"---\nphase: DONE\ntask: none\nnext_action: \"saipen continue\"\nblocker: none\n"
            f"transition_from: SHIP\nsaipen_version: 8\nschema_version: 3\n"
            f"style_contract: {CURRENT_STYLE_CONTRACT}\nagent: a\nmode: full\nupdated: {now}\n"
            f"last_event: {ev + 1}\nexecution_intent: goal\ngoal_waves: 0\ngoal_tickets: 19\n"
            f"continuation_authority: operator_required\nauthority_source: E-001\n"
            f"authority_until: budget\nsafety_valve_mode: hard_wait\nsaipen_home: {REPO}\n---\n",
            encoding="utf-8",
        )
        claimed = operations.apply_claim(root, "T-1", "a")
        self.assertTrue(claimed.ok, claimed.to_dict())
        self.assertTrue(operations.transition_phase(root, "BUILD", "a", "T-1", "BUILD T-1").ok)
        self.assertTrue(operations.transition_phase(root, "VERIFY", "a", "T-1", "VERIFY T-1").ok)
        self.assertTrue(
            operations.checkpoint(
                root, "a", "RUN", "T-1", "verify -> PASS [target: T-1] conf: high -- ok"
            ).ok
        )
        # VERIFY -> REVIEW trips the 20-ticket consumer cap and writes VALVE_WAIT.
        rev = operations.transition_phase(root, "REVIEW", "a", "T-1", "REVIEW T-1")
        self.assertTrue(rev.ok, rev.to_dict())
        self.assertEqual(rev.data["goal_tickets"], 20)
        self.assertEqual(rev.data["next_action"], VALVE_WAIT)
        self.assertTrue(
            operations.checkpoint(
                root, "a", "DEC", "T-1", "REVIEW: PASS [target: T-1] conf: high -- ok"
            ).ok
        )
        self.assertTrue(operations.transition_phase(root, "SHIP", "a", "T-1", "SHIP T-1").ok)
        sc = operations.record_scope(root, "T-1", "a", ["tools/x.py"])
        self.assertTrue(sc.ok, sc.to_dict())

        fin = operations.finish_ticket(root, "T-1", "a", closure_mode="own_patch")
        self.assertTrue(fin.ok, fin.to_dict())
        post = state.parse_state(codec.read_doc(root / ".saipen" / "STATE.md"))
        self.assertEqual(post["phase"], "DONE")
        self.assertEqual(post["task"], "none")
        self.assertEqual(post["next_action"], VALVE_WAIT)
        self.assertEqual(fin.data["next_action"], VALVE_WAIT)
        # Reconcile stays CLEAN while WAIT is intact, and status/explain-next/cc/claim agree.
        clean_rec = reconcile.reconcile_protocol_state(root, "a", dry_run=True)
        self.assertTrue(clean_rec["ok"], clean_rec)
        rc_s, st = _cli(root, "status", "--json")
        self.assertEqual(rc_s, 0, st)
        self.assertEqual(st["automation"]["disposition"], "WAIT_USER", st["automation"])
        self.assertTrue(st["automation"]["operator_action_due"], st["automation"])
        rc_e, ex = _cli(root, "explain-next", "--json")
        self.assertEqual(rc_e, 0, ex)
        self.assertEqual(ex["disposition"], "WAIT_USER", ex)
        self.assertTrue(ex["human_required"], ex)
        rc_c, cc = _cli(root, "cc", "--json")
        self.assertNotEqual(rc_c, 0)
        self.assertEqual(cc.get("code"), "RECONCILE_REAUTH_REQUIRED", cc)
        self.assertIsNone(cc.get("canonical_next_command"), cc)
        # Claiming T-2 over the tripped valve MUST refuse even in DONE phase with TODO work present.
        claim_blocked = operations.apply_claim(root, "T-2", "a")
        self.assertFalse(claim_blocked.ok)
        self.assertEqual(claim_blocked.code, "WAIT_BLOCKED")
        rc, cli_claim = _cli(root, "claim", "T-2", "--json")
        self.assertNotEqual(rc, 0)
        self.assertEqual(cli_claim.get("code"), "WAIT_BLOCKED")

    def test_transition_to_done_from_add_preserves_consumer_safety_valve_wait(self):
        root = _build_consumer_project(
            self.base / "add-done",
            phase="ADD",
            task="none",
            next_action="PHASE ADD",
            goal_tickets=20,
            with_doing=False,
        )
        # Legal ADD -> DONE transition under an exhausted consumer safety valve.
        st_path = root / ".saipen" / "STATE.md"
        st_path.write_text(
            state.patch_state(
                codec.read_doc(st_path),
                {"transition_from": "HUNT", "next_action": VALVE_WAIT},
            ),
            encoding="utf-8",
        )
        res = operations.transition_phase(root, "DONE", "a", None, "end add under tripped valve")
        self.assertTrue(res.ok, res.to_dict())
        post = state.parse_state(codec.read_doc(st_path))
        self.assertEqual(post["phase"], "DONE")
        self.assertEqual(post["next_action"], VALVE_WAIT)
        self.assertEqual(res.data["next_action"], VALVE_WAIT)

    def test_drifted_state_without_wait_still_refuses_claims_and_aligns_four_surfaces(self):
        root = _build_consumer_project(
            self.base / "drifted-31",
            phase="DONE",
            task="none",
            next_action="saipen continue",
            goal_tickets=31,
            with_doing=False,
        )
        before_state = (root / ".saipen" / "STATE.md").read_bytes()
        before_board = (root / ".saipen" / "BOARD.md").read_bytes()

        # 1. binding_brake and claim paths fail closed even without WAIT: in next_action.
        parsed = state.parse_state(before_state.decode("utf-8"))
        brake = state.binding_brake(parsed)
        self.assertIsNotNone(brake)
        self.assertEqual(brake[0], "wait")

        direct = operations.apply_claim(root, "T-2", "a")
        self.assertFalse(direct.ok)
        self.assertEqual(direct.code, "WAIT_BLOCKED")

        rc_claim, cli_claim = _cli(root, "claim", "T-2", "--json")
        self.assertNotEqual(rc_claim, 0)
        self.assertEqual(cli_claim.get("code"), "WAIT_BLOCKED")
        self.assertEqual((root / ".saipen" / "STATE.md").read_bytes(), before_state)
        self.assertEqual((root / ".saipen" / "BOARD.md").read_bytes(), before_board)

        # 2. reconcile never emits canonical_next_command="saipen continue" on consumer lock.
        rec = reconcile.reconcile_protocol_state(root, "a", dry_run=True)
        self.assertFalse(rec["ok"])
        self.assertEqual(rec["code"], "RECONCILE_REAUTH_REQUIRED")
        self.assertEqual(rec["remediation"], reconcile.SAFETY_VALVE_TRIPPED)
        self.assertIsNone(rec["canonical_next_command"], rec)
        self.assertEqual(rec.get("required_ingress"), "operator_carrier", rec)

        # 3. Four-way CLI alignment: status, explain-next, start, cc all stop with WAIT_USER/reauth.
        rc_s, st = _cli(root, "status", "--json")
        self.assertEqual(rc_s, 0, st)
        self.assertEqual(st["automation"]["disposition"], "WAIT_USER", st["automation"])
        self.assertTrue(st["automation"]["operator_action_due"], st["automation"])
        self.assertIsNone(st["automation"]["next_command"], st["automation"])

        rc_e, ex = _cli(root, "explain-next", "--json")
        self.assertEqual(rc_e, 0, ex)
        self.assertEqual(ex["disposition"], "WAIT_USER", ex)
        self.assertTrue(ex["human_required"], ex)
        self.assertEqual(ex["owner"], "user", ex)

        start_res = entry.start_work(root, "a", actor_source="state", text="check audit")
        self.assertFalse(start_res["ok"])
        self.assertIsNone(start_res["reconciliation"]["canonical_next_command"], start_res)

        rc_c, cc = _cli(root, "cc", "--json")
        self.assertNotEqual(rc_c, 0)
        self.assertEqual(cc.get("code"), "RECONCILE_REAUTH_REQUIRED", cc)
        self.assertIsNone(cc.get("canonical_next_command"), cc)
        self.assertEqual(cc.get("required_ingress"), "operator_carrier", cc)
        self.assertTrue(cc.get("operator_action_due"), cc)

    def test_reconcile_gate_distinguishes_reauthorize_from_wait_consumer(self):
        # Control (T-1751): canonical_next_command="saipen continue" yields None.
        route = {"ok": True, "action": "saipen continue", "reason": "maintain"}
        viable = {
            "ok": False,
            "code": "RECONCILE_REAUTH_REQUIRED",
            "remediation": reconcile.SAFETY_VALVE_TRIPPED,
            "operator_decision_available": True,
            "canonical_next_command": "saipen continue",
        }
        self.assertIsNone(router.reconcile_gate(self.base, route, reconciled=viable))

        # Bounded consumer with no operator carrier: refuses with WAIT_USER/reauth decision.
        blocked = {
            "ok": False,
            "code": "RECONCILE_REAUTH_REQUIRED",
            "remediation": reconcile.SAFETY_VALVE_TRIPPED,
            "operator_decision_available": False,
            "canonical_next_command": None,
            "detail": "safety valve reached",
            "operator_action": "Send fresh cc via prompt hook",
        }
        gated = router.reconcile_gate(self.base, route, reconciled=blocked)
        self.assertIsNotNone(gated)
        self.assertFalse(gated["ok"])
        self.assertEqual(gated["reason"], "reconcile-decision")
        self.assertIsNone(gated["canonical_next_command"])
        self.assertTrue(gated["requires_human"])

    def test_non_prompt_hook_host_capability_is_truthful_and_cannot_bypass_carrier(self):
        root = _build_consumer_project(
            self.base / "host-cap",
            phase="DONE",
            task="none",
            next_action=VALVE_WAIT,
            goal_tickets=20,
        )
        for host_id in ("antigravity", "gemini", "freebuff"):
            with self.subTest(host_id=host_id):
                res = goal_authority.reset_authority(
                    root,
                    {"execution_intent": "goal", "goal_waves": 0, "goal_tickets": 20},
                    host=host_id,
                )
                self.assertEqual(res["mode"], "wait")
                self.assertEqual(res["required_ingress"], "operator_carrier")
                self.assertIsNone(res["canonical_next_command"])
                cap = res.get("host_capability") or {}
                self.assertEqual(cap.get("host"), host_id)
                self.assertFalse(cap.get("host_prompt_available"))
                self.assertFalse(cap.get("can_deliver_operator_carrier"))
                self.assertIn("authenticated", res["operator_action"])
                self.assertIn("agent", res["operator_action"])
                self.assertNotIn("Restore the host ingress bridge", res["operator_action"])

        # Spoofing host env vars MUST NEVER grant continuation authority.
        rc, cc = _cli(root, "cc", "--json", env_extra={"SAIPEN_HOST": "antigravity"})
        self.assertNotEqual(rc, 0)
        self.assertEqual(cc.get("code"), "RECONCILE_REAUTH_REQUIRED")
        self.assertIsNone(cc.get("canonical_next_command"))
        self.assertFalse((cc.get("host_capability") or {}).get("host_prompt_available"))

    def test_zaicode_host_policy_registered_under_protocol_admission(self):
        settings = host_authority_broker.settings()
        zaicode = (settings.get("hosts") or {}).get("zaicode")
        self.assertIsInstance(zaicode, dict, settings)
        images = {str(x).lower() for x in (zaicode.get("host_images") or [])}
        self.assertIn("zaicode.exe", images)
        self.assertIn("zcode.exe", images)
        self.assertEqual(int(zaicode.get("max_shells")), 0)
        self.assertEqual(int(zaicode.get("max_bridges")), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
