"""SRC-112: a cold continuation consumes authority; it cannot grant itself one.

The operator carrier below is an explicit external test double, never a claim
about a production host. Disposable fixtures earn their counter history.
"""

from __future__ import annotations

import hashlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import codec, intake, operations, state  # noqa: E402
from saipen_engine.iteration_verdict import project_iteration_verdict  # noqa: E402
from saipen_engine.reconcile import _derived_goal_counters  # noqa: E402
from saipen_engine.log import read_history_snapshot  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1363_zero_manual_entry import cli, project  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


OBJECTIVE = "Complete every runnable repository ticket until the goal is complete"


class ContinuationAuthorityTests(unittest.TestCase):
    def bounded(self, tickets=20):
        lines = [
            "# Log",
            "- 09.10.26 00:00 [E-1] [agent: test-agent] DEC: goal pivot -- bounded work",
        ]
        for index in range(tickets):
            lines.append(
                f"- 09.10.26 00:00 [E-{index + 2}] [parent: E-{index + 1}] "
                f"[agent: test-agent] DEC: goal_tickets {index}->{index + 1}"
            )
        action = (
            f"WAIT: safety valve reached (0 waves / {tickets} tickets) -- run 'cc' to continue"
            if tickets >= 20 else "saipen continue"
        )
        root = project(
            self, log="\n".join(lines) + "\n", execution_intent="goal",
            goal_waves=0, goal_tickets=tickets, next_action=action,
        )
        self.patch_state(root, {"saipen_home": str(TOOLS.parent)})
        return root

    def persistent(self):
        from test_operator_origin_support import native_operator, use_case_owner

        root = project(self)
        self.patch_state(root, {"saipen_home": str(TOOLS.parent)})
        use_case_owner(self, root)
        with native_operator(root, OBJECTIVE, action="goal"):
            result = operations.goal_entry(root, "test-agent", OBJECTIVE)
        self.assertTrue(result.ok, result.to_dict())
        return root

    def read_state(self, root):
        return state.parse_state(codec.read_doc(root / ".saipen" / "STATE.md"))

    def snapshot(self, root):
        return tuple((root / ".saipen" / name).read_bytes()
                     for name in ("STATE.md", "BOARD.md", "LOG.md"))

    def spend(self, root, *, tickets=20, waves=None):
        """A coherent disposable counter boundary, not an edit to a live run."""
        current = self.read_state(root)
        target = {"goal_tickets": tickets}
        if waves is not None:
            target["goal_waves"] = waves
        for key, desired in target.items():
            for value in range(current.get(key) or 0, desired):
                recorded = operations.checkpoint(
                    root, "test-agent", "DEC", None, f"{key} {value}->{value + 1}",
                )
                self.assertTrue(recorded.ok, recorded.to_dict())
        wave_count = target.get("goal_waves", current.get("goal_waves") or 0)
        next_action = (
            f"WAIT: safety valve reached ({wave_count} waves / {tickets} tickets) "
            "-- run 'cc' to continue"
        )
        self.patch_state(root, {**target, "next_action": next_action})

    def patch_state(self, root, fields):
        path = root / ".saipen" / "STATE.md"
        path.write_text(state.patch_state(codec.read_doc(path), fields), encoding="utf-8")

    def test_explicit_operator_goal_records_persistent_authority_and_source(self):
        current = self.read_state(self.persistent())
        self.assertEqual(current.get("continuation_authority"), "operator_persistent")
        self.assertRegex(current.get("authority_source") or "", r"^E-[1-9][0-9]*$")
        self.assertEqual(current.get("authority_until"), "goal_complete")
        self.assertEqual(current.get("safety_valve_mode"), "checkpoint")

    def test_model_supplied_goal_does_not_create_persistent_authority(self):
        root = project(self)
        result = operations.goal_entry(root, "test-agent", OBJECTIVE)
        self.assertTrue(result.ok, result.to_dict())
        self.assertNotEqual(
            self.read_state(root).get("continuation_authority"), "operator_persistent",
        )

    def test_agent_boot_continue_cannot_reset_an_ordinary_bounded_run(self):
        root = self.bounded()
        before = self.snapshot(root)
        _code, payload, text = cli(root, "continue", "--json")
        self.assertEqual(self.snapshot(root), before, text)
        self.assertEqual(self.read_state(root)["goal_tickets"], 20)
        self.assertIn(
            "safety valve", str(payload.get("next_action") or payload.get("detail")), text,
        )

    def test_bounded_status_requires_the_operator_and_synthetic_cc_is_absent(self):
        root = self.bounded()
        code, payload, text = cli(root, "status", "--json")
        self.assertEqual(code, 0, text)
        self.assertEqual(payload["automation"]["disposition"], "WAIT_USER", text)
        self.assertTrue(payload["automation"]["operator_action_due"], text)
        self.assertIsNone(payload["automation"]["next_command"], text)

    def test_persistent_cap_status_is_a_checkpoint_without_operator_action(self):
        root = self.persistent()
        self.spend(root)
        code, payload, text = cli(root, "status", "--json")
        self.assertEqual(code, 0, text)
        self.assertEqual(payload["automation"]["disposition"], "CONTINUE", text)
        self.assertFalse(payload["automation"]["operator_action_due"], text)
        self.assertEqual(payload["automation"]["next_command"], "cc", text)
        self.assertEqual(payload["computed_next_action"], "saipen continue", text)

    def test_persistent_cold_continue_checkpoints_then_resumes_same_work(self):
        root = self.persistent()
        original = self.read_state(root)
        self.spend(root)
        code, payload, text = cli(root, "continue", "--json")
        self.assertEqual(code, 0, text)
        current = self.read_state(root)
        self.assertEqual((current["goal_waves"], current["goal_tickets"]), (0, 0), text)
        for key in ("task", "phase", "goal_ingress", "authority_source", "continuation_authority"):
            self.assertEqual(current[key], original[key], (key, text))
        log = (root / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("DEC: goal checkpoint --", log)
        self.assertIn("safety review", log)
        self.assertEqual(_derived_goal_counters(read_history_snapshot(root).events),
                         {"goal_waves": 0, "goal_tickets": 0})
        self.assertNotEqual(payload.get("code"), "WAIT_USER", text)

    def test_authorized_persistent_goal_crosses_every_cap_without_a_human_grant(self):
        """AC-07: the same operator grant funds 20, 21, 28, 50 and 100 tickets.

        Each boundary is an independent budget window on ONE isolated project.
        The checkpoints must renew the budget WITHOUT consuming a new operator
        event: authority_source, goal_ingress and the single `goal pivot` line
        all survive every crossing, and only `goal checkpoint` markers appear.
        """
        root = self.persistent()
        granted = self.read_state(root)
        for boundary in (20, 21, 28, 50, 100):
            self.spend(root, tickets=boundary)
            code, payload, text = cli(root, "continue", "--json")
            self.assertEqual(code, 0, text)
            current = self.read_state(root)
            self.assertEqual(
                (current["goal_waves"], current["goal_tickets"]), (0, 0),
                f"boundary {boundary}: {text}",
            )
            for key in ("task", "phase", "goal_ingress", "authority_source",
                        "continuation_authority", "authority_until", "safety_valve_mode"):
                self.assertEqual(current[key], granted[key], (boundary, key, text))
            self.assertEqual(
                _derived_goal_counters(read_history_snapshot(root).events),
                {"goal_waves": 0, "goal_tickets": 0}, text,
            )
            self.assertNotEqual(payload.get("code"), "WAIT_USER", f"boundary {boundary}: {text}")
        log = (root / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertEqual(log.count("DEC: goal checkpoint --"), len((20, 21, 28, 50, 100)))
        self.assertEqual(log.count("DEC: goal pivot --"), 1)
        self.assertNotIn("DEC: goal reauthorized --", log)
        _code, status_payload, status_text = cli(root, "status", "--json")
        self.assertEqual(status_payload["automation"]["disposition"], "CONTINUE", status_text)
        self.assertFalse(status_payload["automation"]["operator_action_due"], status_text)
        self.assertEqual(status_payload["automation"].get("next_command"), "cc", status_text)

    def test_explicit_fresh_operator_cc_can_reset_the_bounded_cap(self):
        root = self.bounded()
        code, _payload, text = cli(root, "continue", "--json", operator_text="cc")
        self.assertEqual(code, 0, text)
        current = self.read_state(root)
        self.assertEqual((current["goal_waves"], current["goal_tickets"]), (0, 0), text)
        self.assertEqual(current.get("continuation_authority"), "operator_required")
        self.assertEqual(current.get("authority_until"), "budget")
        self.assertEqual(current.get("safety_valve_mode"), "hard_wait")
        self.assertRegex(current.get("authority_source", ""), r"^E-[1-9][0-9]*$")
        self.assertIn("DEC: goal reauthorized --", (root / ".saipen" / "LOG.md").read_text())

    def test_a_different_operator_carrier_is_not_a_fresh_cc(self):
        root = self.bounded()
        before = self.snapshot(root)
        cli(root, "continue", "--json", operator_text="inspect the README")
        self.assertEqual(self.snapshot(root), before)

    def test_a_model_source_cannot_be_upgraded_by_a_later_cc_carrier(self):
        root = self.bounded()
        captured = intake.capture(root, "cc", source_kind="user_instruction")
        before = self.snapshot(root)
        with patch.dict(os.environ, {
            "SAIPEN_TASK_SHA256": hashlib.sha256(b"cc").hexdigest(),
        }):
            result = operations.reauthorize_valve(
                root, "test-agent", operator_authority_source=captured["receipt"],
            )
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(self.snapshot(root), before)

    def test_under_cap_continue_never_grants_a_fresh_budget(self):
        root = self.persistent()
        code, _payload, text = cli(root, "continue", "--json")
        self.assertEqual(code, 0, text)
        current = self.read_state(root)
        self.assertEqual((current["goal_waves"], current["goal_tickets"]), (1, 0))
        self.assertNotIn("goal checkpoint --", (root / ".saipen" / "LOG.md").read_text())

    def test_wave_cap_uses_the_same_persistent_checkpoint_policy(self):
        root = self.persistent()
        self.spend(root, tickets=0, waves=3)
        code, _payload, text = cli(root, "continue", "--json")
        self.assertEqual(code, 0, text)
        self.assertEqual(self.read_state(root)["goal_waves"], 0)

    def test_legitimate_user_safety_brakes_survive_persistent_authority(self):
        for action in (
            "WAIT: user brake -- stop here", "WAIT: destructive-op -- remove the database",
            "WAIT: first-publish -- choose repository visibility",
        ):
            root = self.persistent()
            self.spend(root)
            self.patch_state(root, {"next_action": action})
            before = self.snapshot(root)
            cli(root, "continue", "--json")
            self.assertEqual(self.snapshot(root), before, action)

    def test_missing_or_invented_source_cannot_reuse_persistent_authority(self):
        root = self.persistent()
        self.spend(root)
        self.patch_state(root, {"authority_source": "E-999999"})
        before = self.snapshot(root)
        cli(root, "continue", "--json")
        self.assertEqual(self.snapshot(root), before)
        _code, payload, _text = cli(root, "status", "--json")
        self.assertNotEqual(payload.get("automation", {}).get("disposition"), "CONTINUE")

    def test_iteration_does_not_call_a_persistent_checkpoint_a_human_wait(self):
        root = self.persistent()
        self.spend(root)
        verdict = project_iteration_verdict(root)
        self.assertFalse(verdict["requires_human"], verdict)
        self.assertEqual(verdict["decision"], "AUTO_KICK", verdict)

    def test_authority_from_a_different_goal_cannot_reset_the_budget(self):
        root = self.persistent()
        self.spend(root)
        self.patch_state(root, {"goal_ingress": "goal-" + "f" * 16})
        before = self.snapshot(root)
        cli(root, "continue", "--json")
        self.assertEqual(self.snapshot(root), before)

    def test_inconsistent_authority_tuple_is_invalid(self):
        root = self.persistent()
        self.patch_state(root, {"safety_valve_mode": "hard_wait"})
        _code, payload, _text = cli(root, "status", "--json")
        self.assertNotEqual(payload.get("automation", {}).get("disposition"), "CONTINUE")

    def test_intent_exit_removes_the_authority_family(self):
        root = self.persistent()
        text = codec.read_doc(root / ".saipen" / "STATE.md")
        current = state.parse_state(state.transition_execution_intent(text, "normal"))
        for key in (
            "continuation_authority", "authority_source", "authority_until", "safety_valve_mode",
        ):
            self.assertNotIn(key, current)

    def test_persistent_checkpoint_then_core_validator_is_green(self):
        root = self.persistent()
        self.spend(root)
        code, _payload, text = cli(root, "continue", "--json")
        self.assertEqual(code, 0, text)
        code, payload, text = cli(root, "validate", "--json")
        self.assertEqual(code, 0, text)
        self.assertTrue(payload["ok"], text)


if __name__ == "__main__":
    unittest.main()
