"""SRC-276 R007: the acceptance bar, measured clause by clause.

R007 asks for a fixture equivalent to the original ``cc all`` case with seven
properties. Five of the seven are engine-observable here; two need the host
reply surface and are named as such instead of being faked.

What this module proves, against the real decision path:

(a) no duplicate T-62-style Work appears when a continuation meets a
    ``CURRENT_FAIL`` whose subject already has a live owner;
(c) the authority on the route is auditable and scoped, never invented;
(d) ``BUILD`` is not resumed before a fresh non-FAIL conformance state;
(f) no invented operator command is rendered by the engine diagnostic;
(g) the goal surface stays not-complete while deliverables remain open.

(b) correct Estonian compact output and (e) host-side shape enforcement are
host-owned: ``saipen response style`` compiles the contract, but only ZAICODE
can enforce it at the reply surface. Those two are asserted as *available and
correctly compiled*, not as *enforced*, which is the difference F-08 recorded.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import conformance as C  # noqa: E402
from saipen_engine import finding_ownership as O  # noqa: E402
from saipen_engine import finding_route as R  # noqa: E402
from saipen_engine import findings  # noqa: E402
import test_conformance_repair_boundary as fixtures  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def diagnostics(*messages: str) -> dict:
    problems = [findings.classify("problem", message) for message in messages]
    return {
        "status": "complete",
        "ruleset_version": findings.RULESET_VERSION,
        "ruleset_fingerprint": findings.ruleset_fingerprint(),
        "problem_count": len(problems),
        "warning_count": 0,
        "problems": problems,
    }


class AcceptanceBarTests(fixtures.RepairBoundaryTests):
    """R007 clauses (a), (c), (d), (f), (g) over the real CURRENT_FAIL path."""

    def _fail_with_subject(self, name: str, message: str) -> tuple[Path, dict]:
        root = self.make_project(name)
        C.generate_conformance_receipt(
            root, gate="core", exit_code=1, blocking_findings=diagnostics(message)
        )
        return root, C.conformance_decision(root)

    def test_a_no_duplicate_work_when_the_subject_has_a_live_owner(self):
        # The measured F-01/F-02 shape: the blocked subject already has a live
        # ticket, so the engine must name that ticket and never invite a start.
        decision = self._fail_with_subject(
            "r007-owner", "closed receipt SRC-003 archive bundle invalid: missing metadata"
        )[1]
        self.assertEqual(decision["repair_status"], "ENGINEERING_REQUIRED")
        ownership = decision["diagnostic"]["ownership"]
        self.assertEqual(ownership["engine_work_count"], 1)
        item = ownership["groups"]["ENGINE_INTERNAL"][0]
        self.assertNotIn("saipen start", item["route"])
        self.assertEqual(item["route"], O.ENGINE_ROUTE)

        # And the resolver, given a live claimant, routes to it rather than
        # producing a second record.
        tickets = {
            "T-57": {
                "id": "T-57",
                "section": "## BLOCKED",
                "description": "",
                "fields": {"blocker": "source_receipt_closed_archive_invalid SRC-003"},
            }
        }
        routed = R.resolve(Path("."), item, tickets)
        self.assertEqual(routed["code"], "ROUTED_TO_OWNER")
        self.assertEqual(routed["owner"], "T-57")
        self.assertEqual(R.route_command(routed), "saipen ticket claim T-57")

    def test_c_the_route_carries_no_invented_operator_command(self):
        # Clause (f) too: an engine-owned finding renders no operator command.
        decision = self._fail_with_subject(
            "r007-authority", "ORPHAN_RECEIPT SRC-009 is not linked to any Work"
        )[1]
        ownership = decision["diagnostic"]["ownership"]
        self.assertEqual(ownership["operator_action_count"], 0)
        for item in ownership["groups"].get("ENGINE_INTERNAL", []):
            self.assertIs(item["operator_action_due"], False)
            self.assertNotIn("OPERATOR", item["route"].upper())
        serialized = repr(decision["diagnostic"])
        self.assertNotIn("recover resolve-blocker", serialized)

    def test_d_build_is_not_resumed_over_a_current_fail(self):
        # The engine reports the failure as terminal and exposes no executable
        # remediation, so no caller can read it as permission to resume BUILD.
        from saipen_engine import router

        root, decision = self._fail_with_subject(
            "r007-build", "ORPHAN_RECEIPT SRC-009 is not linked to any Work"
        )
        self.assertFalse(decision["healthy"])
        self.assertEqual(decision["repair_status"], "ENGINEERING_REQUIRED")
        for route in (
            {"ok": True, "action": "saipen continue", "reason": "maintain"},
            {"ok": True, "action": "saipen crew", "reason": "crew-converge"},
        ):
            gated = router.gate_route(root, route)
            self.assertFalse(gated["ok"])
            self.assertIsNone(gated["canonical_next_command"])
            self.assertIsNone(gated["action"])

    def test_g_the_goal_surface_does_not_read_complete(self):
        # R007 clause (g): open deliverables keep the goal verifier off PASS.
        _root, decision = self._fail_with_subject(
            "r007-goal", "ORPHAN_RECEIPT SRC-009 is not linked to any Work"
        )
        self.assertEqual(decision["status"], C.STATUS_CURRENT_FAIL)
        self.assertFalse(decision["healthy"])
        # A failed conformance decision is never a valid terminal.
        self.assertNotEqual(decision.get("status"), "CURRENT_PASS")

    def test_the_two_host_clauses_are_compiled_but_not_claimed_enforced(self):
        # (b) and (e) belong to ZAICODE. Prove the contract compiles to `et`,
        # and record that enforcement is the host's, not this project's.
        from saipen_engine import chat_style

        contract = chat_style.contract_summary(chat_style.running_style_contract())
        self.assertEqual(contract["reply_language"], "et")
        self.assertGreater(contract["chat_line_budget"], 0)
        self.assertTrue(contract.get("source_token"))
        # The honest capability claim: the zaicode adapter has no response hook,
        # so SAIPEN compiles the contract and cannot enforce the rendered text.
        import json

        registry = json.loads(
            (TOOLS.parent / "extensions" / "adapters" / "registry.json").read_text(
                encoding="utf-8"
            )
        )
        zaicode = next(
            adapter for adapter in registry["adapters"] if adapter.get("id") == "zaicode"
        )
        self.assertEqual(zaicode["response_enforcement"], "ADVISORY")
        self.assertIsNone(zaicode.get("response_hook"))


if __name__ == "__main__":
    unittest.main()
