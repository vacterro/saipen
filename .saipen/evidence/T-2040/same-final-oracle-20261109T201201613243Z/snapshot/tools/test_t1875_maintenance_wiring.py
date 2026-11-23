"""T-1875 / SRC-304: the continuous-maintenance controller must be REACHABLE.

T-1871 shipped `saipen_engine/maintenance.py` and eight green tests over it, and
closed DONE. The module had no production caller: `git ls-files` did not track
it, an AST scan of `tools/` found zero references outside its own file, and no
writer anywhere could produce the `continuous_maintenance` grant it reads. The
campaign therefore could not run, and its green tests proved only that
un-reachable code behaves as un-reachable code does. T-1878 then retired that
module and its self-referential suite, so the behaviour it claimed to add is
pinned here instead -- against the route `continue` actually takes.

These tests pin the four defects that made the campaign fictitious. Each one is
a red-before-green oracle: the assertion fails on the pre-fix tree.

1. `continuous_maintenance` was unreachable: `grant_fields` and
   `current_binding` hard-wired `goal_complete`, so every operator capsule that
   asked for a standing campaign was refused as "not this exact existing goal".
2. `is_continuous_maintenance` accepted a bare STATE tuple as authority, so a
   hand-edited state file could claim a campaign no operator ever signed. The
   proven predicate is what routing must consume.
3. The `audit-inbox-unworkable` idle boundary classified as STOP even under a
   fully authorized campaign, which is acceptance H16 -- an external blocker
   must not block independent authorized improvement.
4. `continuous_maintenance_gate` must refuse an unproven claim before the
   fallthrough spends an improvement cycle on it.
"""

from __future__ import annotations

import inspect
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import continue_loop, goal_authority, router  # noqa: E402

CM_STATE = {
    "execution_intent": "goal",
    "continuation_authority": "operator_persistent",
    "authority_source": "SRC-304",
    "authority_until": "continuous_maintenance",
    "safety_valve_mode": "checkpoint",
    "goal_ingress": "goal-0123456789abcdef",
}

UNWORKABLE_ROUTE = {
    "ok": True,
    "action": "saipen audit status",
    "reason": "audit-inbox-unworkable",
    "stop_reason": "NO_ADMISSIBLE_WORK",
    "executable_behavior": "RESTATE_AND_STOP",
}


class ReachabilityTests(unittest.TestCase):
    def test_a_capsule_can_request_the_campaign_scope(self):
        """Defect 1: `current_binding` hard-wired `goal_complete`.

        `grant_fields` could already WRITE the campaign scope; what no caller
        could do was ask for it. `authorize_goal_continuation` rebuilt the
        binding with no scope argument, compared it to the operator's capsule,
        and refused every campaign capsule as "not this exact existing goal".
        Pre-fix this call raised TypeError: unexpected keyword argument 'until'.
        """
        self.assertIn(
            "until",
            inspect.signature(goal_authority.current_binding).parameters,
            "the operator capsule must be able to state its own grant scope",
        )

    def test_a_campaign_capsule_is_not_silently_narrowed(self):
        """The granted scope must survive into the binding, not collapse."""
        granted = goal_authority.grant_fields("SRC-304", until="continuous_maintenance")
        self.assertEqual(granted["authority_until"], "continuous_maintenance")
        self.assertEqual(granted["continuation_authority"], "operator_persistent")
        self.assertEqual(granted["safety_valve_mode"], "checkpoint")

    def test_unknown_scope_still_collapses_to_the_bounded_scope(self):
        """The closed set is not widened: an invented scope is not a campaign."""
        self.assertEqual(
            goal_authority.grant_fields("SRC-304", until="forever")["authority_until"],
            "goal_complete",
        )

    def test_bounded_state_does_not_claim_a_campaign(self):
        bounded = {
            "execution_intent": "goal",
            "continuation_authority": "operator_required",
            "authority_source": "E-1",
            "authority_until": "budget",
            "safety_valve_mode": "hard_wait",
        }
        self.assertFalse(goal_authority.is_continuous_maintenance(bounded))
        self.assertFalse(goal_authority.continuous_maintenance_proven(TOOLS.parent, bounded))


class ProofTests(unittest.TestCase):
    def test_shape_alone_is_not_proof(self):
        """Defect 2: a well-formed tuple is not an operator grant."""
        self.assertTrue(goal_authority.is_continuous_maintenance(CM_STATE))
        # No committed goal journal backs this tuple in an empty project.
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(goal_authority.continuous_maintenance_proven(Path(td), CM_STATE))

    def test_absent_project_root_never_proves_a_campaign(self):
        self.assertFalse(goal_authority.continuous_maintenance_proven(None, CM_STATE))


class RoutingTests(unittest.TestCase):
    def test_external_audit_blocker_yields_to_a_proven_campaign(self):
        """Defect 3 (H16): the external blocker must not stop independent work."""
        with patch.object(goal_authority, "is_continuous_maintenance", return_value=True):
            verdict = continue_loop.classify_route(UNWORKABLE_ROUTE, CM_STATE, {"tickets": {}})
        self.assertEqual(verdict, continue_loop.IDLE_MAINTAIN)

    def test_external_audit_blocker_still_stops_without_a_campaign(self):
        """H02: the ordinary goal contract keeps its STOP."""
        bounded = {
            "execution_intent": "goal",
            "continuation_authority": "operator_required",
            "authority_source": "E-1",
            "authority_until": "budget",
            "safety_valve_mode": "hard_wait",
        }
        verdict = continue_loop.classify_route(UNWORKABLE_ROUTE, bounded, {"tickets": {}})
        self.assertEqual(verdict, continue_loop.STOP)

    def test_non_idle_routes_are_never_rewritten_by_the_gate(self):
        """The gate owns exactly the idle boundary, nothing else."""
        with tempfile.TemporaryDirectory() as td:
            busy = {"ok": True, "action": "PHASE SCOUT T-1", "reason": "next-todo"}
            self.assertIsNone(router.continuous_maintenance_gate(Path(td), busy))

    def test_gate_refuses_an_unproven_claim_on_the_idle_boundary(self):
        """Defect 4: an unproven claim never buys autonomous discovery."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".saipen").mkdir(parents=True)
            (root / ".saipen" / "STATE.md").write_text(
                "---\n"
                + "".join(f"{key}: {value}\n" for key, value in CM_STATE.items())
                + "---\n",
                encoding="utf-8",
            )
            routed = {
                "ok": True,
                "action": "saipen continue",
                "reason": "maintain",
                "stop_reason": "NO_ADMISSIBLE_WORK",
            }
            with patch(
                "saipen_engine.state.parse_state", return_value=dict(CM_STATE)
            ), patch(
                "saipen_engine.goal_authority.continuous_maintenance_proven",
                return_value=False,
            ):
                rewrite = router.continuous_maintenance_gate(root, routed)
            self.assertIsNotNone(rewrite)
            self.assertEqual(rewrite["code"], "CONTINUATION_AUTHORITY_UNPROVEN")
            self.assertFalse(rewrite["ok"])


class ProductionWiringTests(unittest.TestCase):
    def test_the_controller_module_has_a_production_caller(self):
        """The defect T-1871 shipped: a module with zero production callers.

        This asserts on the LIVE wiring rather than on the module's own
        behaviour, because the module behaved correctly the entire time it was
        unreachable. Importing `maintenance` from the continuation path is what
        makes it part of the product.
        """
        source = (TOOLS / "saipen.py").read_text(encoding="utf-8")
        fallthrough = source.split("def _continue_improve_fallthrough", 1)[1]
        fallthrough = fallthrough.split("\ndef ", 1)[0]
        self.assertIn(
            "continuous_maintenance_proven", fallthrough,
            "the improvement fallthrough must consume the PROVEN campaign predicate",
        )


if __name__ == "__main__":
    unittest.main()
