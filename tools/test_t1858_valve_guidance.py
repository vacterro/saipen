"""A safety-valve refusal names authenticated ingress, not an ineffective replay."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import automation, board, codec, goal_authority, state as state_module  # noqa: E402
from test_t1363_zero_manual_entry import cli, project  # noqa: E402


class ValveGuidanceTests(unittest.TestCase):
    def bounded_project(self, tickets=20):
        lines = ["# Log", "- 09.10.26 00:00 [E-1] [agent: test-agent] DEC: goal pivot -- bounded"]
        lines.extend(
            f"- 09.10.26 00:00 [E-{i + 2}] [parent: E-{i + 1}] [agent: test-agent] "
            f"DEC: goal_tickets {i}->{i + 1}"
            for i in range(tickets)
        )
        root = project(
            self, log="\n".join(lines) + "\n", execution_intent="goal",
            goal_waves=0, goal_tickets=tickets,
            next_action=(f"WAIT: safety valve reached (0 waves / {tickets} tickets) "
                         "-- run 'cc' to continue"),
        )
        path = root / ".saipen/STATE.md"
        path.write_text(
            state_module.patch_state(codec.read_doc(path), {"saipen_home": str(TOOLS.parent)}),
            encoding="utf-8",
        )
        return root

    def test_overshot_28_ticket_budget_still_requires_native_authority(self):
        root = self.bounded_project(tickets=28)
        before = tuple((root / ".saipen" / name).read_bytes()
                       for name in ("STATE.md", "BOARD.md", "LOG.md"))
        code, payload, text = cli(root, "continue", "--json")
        self.assertNotEqual(code, 0, text)
        self.assertEqual(payload["code"], "RECONCILE_REAUTH_REQUIRED")
        self.assertEqual(before, tuple((root / ".saipen" / name).read_bytes()
                                      for name in ("STATE.md", "BOARD.md", "LOG.md")))
        # An explicit native-origin test double exercises the kernel recovery.
        # This is not a LIVE ZAICODE event or proof that its hook is installed.
        code, payload, text = cli(root, "continue", "--json", operator_text="cc")
        self.assertEqual(code, 0, text)
        current = state_module.parse_state(codec.read_doc(root / ".saipen/STATE.md"))
        self.assertEqual((current["goal_waves"], current["goal_tickets"]), (0, 0))
        self.assertEqual(current["safety_valve_mode"], "hard_wait")

    def test_queue_length_does_not_consume_the_completed_ticket_budget(self):
        from saipen_engine import router
        from test_t1807_audit_liveness_regression import _valid_state_text
        from test_t1857_shared_blockers import board_text, ticket

        for queued in (28, 1000):
            with self.subTest(queued=queued):
                items = {f"T-{i}": ticket(f"T-{i}", section="## TODO")
                         for i in range(1, queued + 1)}
                result = router.route_next(_valid_state_text(), board_text(items))
                self.assertEqual(result["action"], "PHASE SCOUT T-1")
        self.assertTrue(goal_authority.budget_exhausted({
            "execution_intent": "goal", "goal_waves": 0, "goal_tickets": 28,
        }))

    def test_native_resume_spellings_are_equivalent_without_weakening_hard_wait(self):
        # cold_command supplies an explicit native-origin TEST DOUBLE. This
        # proves the kernel, never a production host's ingress integration.
        for operator_text in ("cc", "saipen continue", "continue"):
            with self.subTest(operator_text=operator_text):
                root = self.bounded_project()
                code, payload, text = cli(root, "continue", "--json", operator_text=operator_text)
                self.assertEqual(code, 0, text)
                current = state_module.parse_state(codec.read_doc(root / ".saipen/STATE.md"))
                self.assertEqual((current["goal_waves"], current["goal_tickets"]), (0, 0), payload)
                self.assertEqual(current["safety_valve_mode"], "hard_wait")
                self.assertEqual(current["continuation_authority"], "operator_required")

    def test_bounded_reset_refusal_names_missing_native_ingress(self):
        state = {"execution_intent": "goal", "continuation_authority": "operator_required",
                 "goal_waves": 3, "goal_tickets": 25}
        before = dict(state)
        with patch.object(goal_authority, "protocol_home", return_value=False), patch.object(
            goal_authority, "fresh_cc_provenance", return_value=None
        ):
            refusal = goal_authority.reset_authority(Path("untrusted-disposable-root"), state)
        self.assertEqual(refusal["mode"], "wait")
        self.assertEqual(refusal.get("required_ingress"), "operator_carrier")
        self.assertIsNone(refusal.get("canonical_next_command"))
        self.assertIn("authenticated", refusal.get("operator_action", ""))
        self.assertIn("agent", refusal.get("operator_action", ""))
        self.assertEqual(state, before)

    def test_all_modifier_resumes_the_existing_goal_with_real_origin(self):
        for args, original in (
            (("cc", "all"), "cc all"),
            (("continue", "all"), "saipen continue all"),
        ):
            with self.subTest(original=original):
                root = self.bounded_project()
                code, payload, text = cli(root, *args, "--json", operator_text=original)
                self.assertEqual(code, 0, text)
                current = state_module.parse_state(codec.read_doc(root / ".saipen/STATE.md"))
                self.assertEqual(current["goal_tickets"], 0)
                self.assertEqual(current["execution_intent"], "goal")
                self.assertEqual(current["safety_valve_mode"], "hard_wait")
                self.assertNotIn("objective", payload)

    def test_all_modifier_cannot_supply_operator_authority(self):
        root = self.bounded_project()
        before = tuple((root / ".saipen" / name).read_bytes()
                       for name in ("STATE.md", "BOARD.md", "LOG.md"))
        code, payload, text = cli(root, "cc", "all", "--json")
        self.assertNotEqual(code, 0, text)
        self.assertEqual(payload["code"], "RECONCILE_REAUTH_REQUIRED", text)
        self.assertEqual(before, tuple((root / ".saipen" / name).read_bytes()
                                      for name in ("STATE.md", "BOARD.md", "LOG.md")))

    def test_automation_keeps_hard_wait_and_exposes_the_missing_input(self):
        wait = "WAIT: safety valve reached (3 waves / 25 tickets) -- run 'cc' to continue"
        block = automation.automation_block(
            Path("untrusted-disposable-root"),
            state={"phase": "REVIEW", "next_action": wait},
            board=board.parse_board("\n".join(board.REQUIRED_HEADINGS) + "\n"),
            routed={"ok": True, "action": wait, "reason": "wait"},
        )
        self.assertEqual(block["disposition"], "WAIT_USER")
        self.assertTrue(block["operator_action_due"])
        self.assertIsNone(block["next_command"])
        self.assertEqual(block.get("required_ingress"), "operator_carrier")
        self.assertIn("authenticated", block.get("operator_action", ""))

    def test_resume_policy_rejects_malformed_argument_shapes(self):
        from saipen_engine import commands
        from saipen_engine.registry import RegistryError

        for arguments in (None, "all", [[1]], [["all"]]):
            with self.subTest(arguments=arguments), patch.dict(
                commands._REGISTRY,
                {"commands": {"resume": {"arguments": arguments, "operator_inputs": ["cc"]}}},
            ), self.assertRaises(RegistryError):
                commands.resume_policy()

    def test_declared_resume_twins_do_not_invent_other_shortcuts(self):
        from saipen_engine.commands import resume_policy

        inputs = resume_policy()["operator_inputs"]
        for expected in ("cc", "\u0441\u0441", "cc all", "\u0441\u0441 all"):
            self.assertIn(expected, inputs)
        for unrelated in ("ss", "sc", "ccc", "c cc"):
            self.assertNotIn(unrelated, inputs)


if __name__ == "__main__":
    unittest.main()
