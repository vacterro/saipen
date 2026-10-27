"""T-1757: the claim admits the continuation the router prescribes.

`continue --json` answered `PHASE SCOUT T-1751` (reason `audit-inbox`) while
`claim T-1751` refused NOT_TOP_WORKABLE: `plan_claim` asked only the BOARD Pick
Rule, never the audit-inbox route the router obeys (SOURCE-AUDIT-INBOX-01).
The way through was `--explicit`, which wrote a DEC saying the Pick Rule had
been stepped over (E-15126), and START wrote the same words when it claimed
the request it was handed (E-15078). Two owners decided the next Work and the
LOG recorded an override nobody made.

The claim now asks the router's own seam (`audit_inbox_projection`) and
decision (`audit_route_owns`), and a claim on a stated basis names it.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen import main as saipen_main  # noqa: E402
from saipen_engine import audit_inbox  # noqa: E402
from saipen_engine.entry import start_work  # noqa: E402
from saipen_engine.operations import apply_claim, plan_claim  # noqa: E402
from test_explicit_claim import AGENT, ExplicitClaimFixture  # noqa: E402

LAYER = "audit/1.md"
BODY = "# audit\n\nthe finding T-2 answers\n"


class ClaimFollowsRouteTests(ExplicitClaimFixture):
    def bind_audit_to(self, work: str) -> None:
        path = self.root / LAYER
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(BODY, encoding="utf-8")
        captured = audit_inbox.capture_layer(self.root, LAYER, work=work)
        self.assertTrue(captured.get("ok"), captured)
        audit_inbox.bind_layer(
            self.root,
            LAYER,
            layer=1,
            generation=1,
            file_sha256=captured["file_sha256"],
            size_bytes=len(BODY.encode("utf-8")),
            receipt_id=captured["receipt"],
            receipt_sha256=captured["file_sha256"],
            binding="exact",
            linked_work=work,
            state=audit_inbox.ACTIVE,
        )

    def routed(self) -> dict:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            saipen_main(["next", "--json", "--project-root", str(self.root), "--agent", AGENT])
        return json.loads(out.getvalue())

    def claim_line(self, ticket: str) -> str:
        return [ln for ln in self.log_text().splitlines() if f"[{ticket}]" in ln][-1]

    def test_the_router_names_the_audit_work_below_the_pick_rule_top(self):
        self.bind_audit_to("T-2")
        route = self.routed()
        self.assertEqual(route.get("action"), "PHASE SCOUT T-2", route)
        self.assertEqual(route.get("reason"), "audit-inbox", route)

    def test_the_claim_admits_what_the_router_prescribes(self):
        self.bind_audit_to("T-2")
        out = apply_claim(self.root, "T-2", AGENT)
        self.assertTrue(out.get("ok"), out)
        line = self.claim_line("T-2")
        self.assertIn("audit route (SOURCE-AUDIT-INBOX-01)", line)
        self.assertNotIn("EXPLICIT claim over PICK-01", line)

    def test_a_ticket_neither_rule_names_still_refuses(self):
        out = plan_claim(self.root, "T-2", AGENT)
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("code"), "NOT_TOP_WORKABLE")

    def test_a_stated_basis_is_named_instead_of_an_override(self):
        out = apply_claim(self.root, "T-2", AGENT, explicit=True, basis="user request SRC-009")
        self.assertTrue(out.get("ok"), out)
        line = self.claim_line("T-2")
        self.assertIn("user request SRC-009, ahead of PICK-01 topmost workable T-1", line)
        self.assertNotIn("EXPLICIT claim over PICK-01", line)

    def test_start_names_the_request_it_was_handed(self):
        # The request names the lower Work, so START claims below the Pick
        # Rule's top: the DEC states the request, never an override.
        started = start_work(self.root, AGENT, actor_source="explicit", text="lower probe")
        self.assertEqual(started.get("code"), "STARTED", started)
        self.assertEqual(started.get("ticket"), "T-2", started)
        claims = [
            ln for ln in self.log_text().splitlines()
            if "[T-2]" in ln and "claimed via SAIOPS" in ln
        ]
        self.assertEqual(len(claims), 1, claims)
        self.assertIn(
            f"user request {started['receipt']}, ahead of PICK-01 topmost workable T-1",
            claims[0],
        )
        self.assertNotIn("EXPLICIT claim over PICK-01", claims[0])

    def test_the_route_admits_only_the_work_it_names(self):
        # The audit route continues with T-1, so it lends T-2 nothing.
        self.bind_audit_to("T-1")
        self.assertEqual(self.routed().get("action"), "PHASE SCOUT T-1")
        out = plan_claim(self.root, "T-2", AGENT)
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("code"), "NOT_TOP_WORKABLE")

    def test_a_bare_explicit_override_keeps_its_record(self):
        apply_claim(self.root, "T-2", AGENT, explicit=True)
        self.assertIn(
            "EXPLICIT claim over PICK-01: topmost workable was T-1", self.claim_line("T-2")
        )


if __name__ == "__main__":
    unittest.main()
