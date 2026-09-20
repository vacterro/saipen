"""SRC-085 M3: CURRENT_FAIL and CONTINUE may not coexist unexplained.

AUDAPACK carried-debt reproduction: the strict gate reported CURRENT_FAIL while
`saipen status` advertised `next_action: saipen continue` and
`automation.disposition: CONTINUE`; the accepted-debt rationale existed only in
historical LOG prose, so a machine consumer saw two incompatible authorities.

The contract these controls pin (DESIGN A -- the red gate owns routing, and no
acceptance surface exists yet, so an unaccepted CURRENT_FAIL can never buy a
CONTINUE):

* `conformance_decision` carries a closed machine `disposition`;
* an idle route (`reason: maintain`) under REMEDIATION_REQUIRED is rewritten to
  the ONE canonical remediation (`saipen validate`) through the same gate chain
  every production surface applies;
* clean conformance keeps ordinary continuation, and UNPROVEN (NOT_RUN / stale)
  does NOT stop a fresh project;
* active Work routes are not owned by the idle gate;
* `status --json` exposes the disposition, and its automation block stops
  advertising CONTINUE while the red gate holds the route.

Run standalone:
    python -m unittest tools.test_src085_conformance_disposition
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
for _entry in (str(TOOLS), str(TOOLS.parent)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from saipen_engine import conformance as C  # noqa: E402
from saipen_engine import router as router_mod  # noqa: E402
from test_t1412_conformance_truth import T1412Base, write_receipt  # noqa: E402


def _idle(action: str = "saipen continue") -> dict:
    return {"ok": True, "action": action, "reason": "maintain"}


class DispositionMappingTests(unittest.TestCase):
    def test_the_closed_mapping(self) -> None:
        rows = (
            (C.STATUS_CURRENT_PASS, C.CONFORMANCE_DISPOSITION_HEALTHY),
            (C.STATUS_CURRENT_FAIL, C.CONFORMANCE_DISPOSITION_REMEDIATION_REQUIRED),
            (C.STATUS_NOT_RUN, C.CONFORMANCE_DISPOSITION_UNPROVEN),
            (C.STATUS_STALE_PASS, C.CONFORMANCE_DISPOSITION_UNPROVEN),
            (C.STATUS_STALE_FAIL, C.CONFORMANCE_DISPOSITION_UNPROVEN),
            (C.STATUS_INVALID, C.CONFORMANCE_DISPOSITION_INVALID),
            (C.STATUS_VERSION_MISMATCH, C.CONFORMANCE_DISPOSITION_INVALID),
        )
        for status, expected in rows:
            with self.subTest(status=status):
                self.assertEqual(C.conformance_disposition(status), expected)
        self.assertEqual(C.conformance_disposition(None), C.CONFORMANCE_DISPOSITION_UNPROVEN)


class IdleGateTests(T1412Base):
    def test_current_fail_owns_the_idle_continuation(self) -> None:
        root = self.make_project("fail-idle")
        write_receipt(root, "FAIL")
        decision = C.conformance_decision(root, gate="core")
        self.assertEqual(decision["status"], C.STATUS_CURRENT_FAIL)
        self.assertEqual(
            decision["disposition"], C.CONFORMANCE_DISPOSITION_REMEDIATION_REQUIRED
        )
        gated = router_mod.gate_route(root, _idle())
        self.assertIsNotNone(gated)
        self.assertFalse(gated["ok"])
        self.assertEqual(gated["action"], "saipen validate")
        self.assertEqual(gated["reason"], "conformance-remediation")
        self.assertEqual(gated["canonical_next_command"], "saipen validate")
        self.assertEqual(gated["code"], "CONFORMANCE_UNHEALTHY")

    def test_clean_conformance_keeps_ordinary_continuation(self) -> None:
        root = self.make_project("pass-idle")
        write_receipt(root, "PASS")
        self.assertEqual(
            C.conformance_decision(root, gate="core")["disposition"],
            C.CONFORMANCE_DISPOSITION_HEALTHY,
        )
        self.assertIsNone(router_mod.gate_route(root, _idle()))

    def test_unproven_is_not_a_stop(self) -> None:
        root = self.make_project("not-run-idle")
        self.assertIsNone(router_mod.gate_route(root, _idle()))

    def test_active_work_route_is_not_owned_by_the_idle_gate(self) -> None:
        root = self.make_project("fail-active")
        write_receipt(root, "FAIL")
        active = {"ok": True, "action": "PHASE SHIP T-1", "reason": "finish"}
        self.assertIsNone(router_mod.gate_route(root, active))

    def test_the_idle_route_never_wraps_the_remediation_in_its_own_refusal(self) -> None:
        root = self.make_project("fail-already-validate")
        write_receipt(root, "FAIL")
        self.assertIsNone(router_mod.gate_route(root, _idle("saipen validate")))

    def test_crew_route_still_uses_the_crew_gate(self) -> None:
        root = self.make_project("fail-crew")
        write_receipt(root, "FAIL")
        crew = {"ok": True, "action": "saipen crew", "reason": "crew-converge"}
        gated = router_mod.gate_route(root, crew)
        self.assertIsNotNone(gated)
        self.assertFalse(gated["ok"])
        self.assertEqual(gated["canonical_next_command"], "saipen validate")


class StatusSurfaceTests(T1412Base):
    def test_explain_next_agrees_with_status_and_next_on_a_red_gate(self) -> None:
        root = self.make_project("fail-explain")
        write_receipt(root, "FAIL")

        rc, status, text = self.run_cli(root, "status")
        self.assertEqual(rc, 0, text)
        rc, explanation, text = self.run_cli(root, "explain-next")
        self.assertEqual(rc, 0, text)
        rc, route, text = self.run_cli(root, "next")
        self.assertNotEqual(rc, 0, text)

        self.assertEqual(explanation["selected_action"], "saipen validate")
        self.assertEqual(explanation["selected_action"], status["computed_next_action"])
        self.assertEqual(explanation["selected_action"], route["action"])
        self.assertEqual(explanation["carrier"]["code"], "CONFORMANCE_UNHEALTHY")
        self.assertEqual(
            explanation["carrier"]["canonical_next_command"], "saipen validate"
        )
        self.assertFalse(explanation["human_required"])
        self.assertEqual(explanation["owner"], "agent")

    def test_explain_next_keeps_a_healthy_route_executable(self) -> None:
        root = self.make_project("pass-explain")
        write_receipt(root, "PASS")
        rc, explanation, text = self.run_cli(root, "explain-next")
        self.assertEqual(rc, 0, text)
        self.assertEqual(explanation["selected_action"], "saipen continue")
        self.assertEqual(explanation["disposition"], "EXECUTE_SELF")
        self.assertFalse(explanation["human_required"])

    def test_status_exposes_the_disposition_and_stops_advertising_continue(self) -> None:
        root = self.make_project("fail-status")
        write_receipt(root, "FAIL")

        rc, payload, text = self.run_cli(root, "status")
        self.assertEqual(rc, 0, text)
        conf = payload["conformance_status"]
        self.assertEqual(conf["status"], "CURRENT_FAIL")
        self.assertEqual(conf["disposition"], "REMEDIATION_REQUIRED")
        self.assertEqual(conf["remediation_command"], "saipen validate")
        self.assertEqual(payload["computed_reason"], "conformance-remediation")
        self.assertEqual(payload["computed_next_action"], "saipen validate")
        automation = payload["automation"]
        self.assertEqual(automation["disposition"], "BLOCKED")
        self.assertEqual(automation["reason_code"], "conformance-remediation")
        self.assertEqual(automation["remediation_command"], "saipen validate")
        self.assertIsNone(automation["next_command"])

        rc, _payload, text = self.run_cli(root, "status", json_output=False)
        self.assertEqual(rc, 0, text)
        self.assertIn("Conformance: CURRENT_FAIL", text)
        self.assertIn("Disposition: REMEDIATION_REQUIRED", text)

    def test_clean_conformance_keeps_continue_in_the_automation_block(self) -> None:
        root = self.make_project("pass-status")
        write_receipt(root, "PASS")
        rc, payload, text = self.run_cli(root, "status")
        self.assertEqual(rc, 0, text)
        self.assertEqual(payload["conformance_status"]["disposition"], "HEALTHY")
        self.assertEqual(payload["automation"]["disposition"], "CONTINUE")


if __name__ == "__main__":
    unittest.main()
