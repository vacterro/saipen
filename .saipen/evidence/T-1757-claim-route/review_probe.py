"""T-1757 REVIEW: the verify clause on the real CLI, independent of the module.

    python review_probe.py <tools-dir>

Every answer comes from `python tools/saipen.py ...` in a subprocess against a
fixture project, never from an in-process call, so this is a second road to
the same claim. The last case is an observation, not an assertion: it measures
whether the claim and `next` can still name different Work.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(sys.argv[1]).resolve()
sys.argv = [sys.argv[0]]
sys.path.insert(0, str(TOOLS))

from test_explicit_claim import AGENT, ExplicitClaimFixture  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1757_claim_follows_route import ClaimFollowsRouteTests  # noqa: E402

OBSERVED: dict = {}


def setUpModule() -> None:
    isolate_host_session()


class RealCli(ExplicitClaimFixture):
    def cli(self, *args: str) -> dict:
        done = subprocess.run(
            [sys.executable, "-B", str(TOOLS / "saipen.py"), "--project-root", str(self.root),
             "--agent", AGENT, "--json", *args],
            cwd=self.root, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300,
        )
        blob = (done.stdout or "") + (done.stderr or "")
        try:
            return json.loads(blob)
        except ValueError:
            return {"ok": False, "code": "UNPARSED", "detail": blob[-600:]}

    def claims(self, ticket: str) -> list:
        return [ln for ln in self.log_text().splitlines()
                if f"[{ticket}]" in ln and "claimed via SAIOPS" in ln]

    def test_a_the_routed_work_is_claimed_without_the_flag(self):
        ClaimFollowsRouteTests.bind_audit_to(self, "T-2")
        route = self.cli("next")
        self.assertEqual((route.get("action"), route.get("reason")),
                         ("PHASE SCOUT T-2", "audit-inbox"), route)
        answer = self.cli("claim", "T-2")
        self.assertTrue(answer.get("ok"), answer)
        line = self.claims("T-2")[-1]
        self.assertIn("audit route (SOURCE-AUDIT-INBOX-01), ahead of PICK-01 topmost workable T-1",
                      line)
        OBSERVED["routed claim DEC"] = line.split("DEC: ", 1)[1]

    def test_b_a_ticket_no_rule_names_still_refuses(self):
        before = self.log_text()
        answer = self.cli("claim", "T-2")
        self.assertEqual(answer.get("code"), "NOT_TOP_WORKABLE", answer)
        self.assertEqual(self.log_text(), before)
        OBSERVED["unrouted claim"] = answer.get("code")

    def test_c_the_route_lends_nothing_to_other_work(self):
        ClaimFollowsRouteTests.bind_audit_to(self, "T-1")
        answer = self.cli("claim", "T-2")
        self.assertEqual(answer.get("code"), "NOT_TOP_WORKABLE", answer)
        OBSERVED["claim beside the routed Work"] = answer.get("code")

    def test_d_start_names_its_request(self):
        started = self.cli("start", "lower probe")
        self.assertEqual((started.get("code"), started.get("ticket")), ("STARTED", "T-2"), started)
        line = self.claims("T-2")[-1]
        self.assertIn(f"user request {started['receipt']}, ahead of PICK-01 topmost workable T-1",
                      line)
        self.assertNotIn("EXPLICIT claim over PICK-01", line)
        OBSERVED["START claim DEC"] = line.split("DEC: ", 1)[1]

    def test_e_observe_a_route_above_start(self):
        # Observation only: a crew convergence target outranks the audit branch
        # in the router. Does the claim still admit the audit Work there?
        ClaimFollowsRouteTests.bind_audit_to(self, "T-2")
        state = self.root / ".saipen" / "STATE.md"
        text = state.read_text(encoding="utf-8")
        lines = [ln for ln in text.splitlines()
                 if not ln.startswith(("execution_intent:", "converge_target:"))]
        closing = len(lines) - 1 - lines[::-1].index("---")
        lines[closing:closing] = ["execution_intent: converge", "converge_target: crew"]
        state.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        route = self.cli("next")
        answer = self.cli("claim", "T-2")
        OBSERVED["under a crew target, next"] = (
            f"{route.get('action')} ({route.get('reason') or route.get('code')})"
        )
        OBSERVED["under a crew target, claim T-2"] = (
            f"{answer.get('code')}: {str(answer.get('message') or answer.get('detail') or '')[:160]}"
        )


if __name__ == "__main__":
    program = unittest.main(exit=False, verbosity=1)
    print(json.dumps(OBSERVED, indent=2, ensure_ascii=False))
    sys.exit(0 if program.result.wasSuccessful() else 1)
