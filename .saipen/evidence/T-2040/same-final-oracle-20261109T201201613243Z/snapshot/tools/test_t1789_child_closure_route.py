"""T-1789: a child Work never dispenses its parent's clause.

SRC-248 linked a parent (T-1769) and repair children (T-1762, T-1770). Each
child was built, verified and gated, and its finish refused SOURCE_UNRESOLVED
on clauses the blocked parent owned; `closure_readiness` routed
`saipen source disp SRC-248 SRC-248:R001 ...` -- the parent's clause. The agent
handed the seat back instead, the child returned to the top of TODO and the
router picked it again (T-1770 twice: E-15310, then E-15634..E-15646).

The route now follows the coverage row's owner: when every open clause belongs
to another Work, the child waits on that owner; a clause the child owns is
still named for `source disp`, and the source still closes only complete.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import intake  # noqa: E402
from saipen_engine.closure_readiness import closure_readiness  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_request_clause_closure import drive  # noqa: E402
from test_t1363_zero_manual_entry import cli, healthy, receipts_of  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def _parent_and_child(case: unittest.TestCase) -> tuple[Path, str, str]:
    """T-1 owns the receipt and an open derived clause; T-2 joins the receipt."""
    root = healthy(case)
    drive(case, root)
    receipt = receipts_of(root)[0]
    intake.ensure_request_clause(root, receipt)
    added = intake.add_requirement(
        root, receipt, rid="R002", text="the parent's own open clause",
        clause_class="requirement",
    )
    case.assertTrue(added.get("ok"), added)
    code, payload, text = cli(
        root, "ticket", "add", "P1", "child repair", "--verify", "proof", "--json"
    )
    case.assertEqual(code, 0, text)
    child = payload.get("ticket")
    # Active Work carries its receipt on its own BOARD row (the same fixture
    # move test_t1645 makes); `repair-metadata` only migrates DONE rows.
    board = root / ".saipen" / "BOARD.md"
    text = board.read_text(encoding="utf-8")
    line = next(row for row in text.splitlines() if f"] {child} [" in row)
    board.write_text(text.replace(line, f"{line} | source_receipts: {receipt}"), encoding="utf-8")
    linked = intake.link_work_to(root, receipt, child)
    case.assertTrue(linked.get("ok"), linked)
    return root, receipt, child


class ChildClosureRouteTests(unittest.TestCase):
    def test_a_child_waits_on_the_owner_of_every_open_clause(self):
        root, receipt, child = _parent_and_child(self)
        decision = closure_readiness(root, child)
        self.assertFalse(decision["ready"], decision)
        self.assertEqual(decision["code"], "SOURCE_UNRESOLVED", decision)
        route = decision["canonical_next_command"]
        self.assertTrue(
            route.startswith(f'saipen ticket block {child} "ACTIVE_DEPENDENCY:T-1 -- '),
            route,
        )
        self.assertIn(f"{receipt}:R002", route)
        self.assertNotIn("source disp", route)

    def test_the_owner_itself_is_still_routed_to_dispense(self):
        root, receipt, _child = _parent_and_child(self)
        decision = closure_readiness(root, "T-1")
        self.assertEqual(
            decision["canonical_next_command"],
            f"saipen source disp {receipt} {receipt}:R002 <STATUS> --evidence <REF>",
        )

    def test_a_child_with_its_own_open_clause_dispenses_that_one(self):
        root, receipt, child = _parent_and_child(self)
        added = intake.add_requirement(
            root, receipt, rid="R003", text="the child's own open clause",
            clause_class="requirement",
        )
        self.assertTrue(added.get("ok"), added)
        owned = intake.set_disposition(root, receipt, "R003", "BLOCKED", work=child)
        self.assertTrue(owned.get("ok"), owned)
        decision = closure_readiness(root, child)
        self.assertEqual(
            decision["canonical_next_command"],
            f"saipen source disp {receipt} {receipt}:R003 <STATUS> --evidence <REF>",
        )


if __name__ == "__main__":
    unittest.main()
