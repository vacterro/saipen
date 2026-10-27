"""T-1790: large foreign-clause sets keep an executable, bounded route."""

from __future__ import annotations

import shlex
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import intake  # noqa: E402
from saipen_engine.closure_readiness import closure_readiness  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1363_zero_manual_entry import cli  # noqa: E402
from test_t1789_child_closure_route import _parent_and_child  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def _many_clauses(case: unittest.TestCase) -> tuple[Path, str, str, list[str]]:
    root, receipt, child = _parent_and_child(case)
    clauses = [f"{receipt}:R{number:03d}" for number in range(2, 36)]
    for clause in clauses[1:]:
        result = intake.add_requirement(
            root, receipt, rid=clause, text="another parent-owned requirement",
            clause_class="requirement",
        )
        case.assertTrue(result.get("ok"), result)
    return root, receipt, child, clauses


class DependencyRouteBudgetTests(unittest.TestCase):
    def test_large_route_executes_and_preserves_every_unresolved_clause(self):
        root, receipt, child, clauses = _many_clauses(self)
        decision = closure_readiness(root, child)
        self.assertFalse(decision["ready"], decision)
        self.assertEqual(decision["code"], "SOURCE_UNRESOLVED", decision)
        route = decision["canonical_next_command"]
        self.assertLess(len(route), 200, route)
        self.assertIn("ACTIVE_DEPENDENCY:T-1", route)
        self.assertIn(receipt, route)
        self.assertIn("34 open clauses", route)
        for clause in clauses[:3]:
            self.assertIn(clause, route)
        for clause in clauses[3:]:
            self.assertNotIn(clause, route)
        self.assertTrue(set(clauses).issubset(decision["unresolved"]), decision)
        coverage = root / ".saipen/intake/coverage" / f"{receipt}.json"
        before = coverage.read_bytes()
        code, result, text = cli(root, *shlex.split(route)[1:], "--json")
        self.assertEqual(code, 0, text)
        self.assertEqual(result.get("code"), "BLOCK", result)
        self.assertEqual(result.get("ticket"), child, result)
        self.assertEqual(coverage.read_bytes(), before)

    def test_single_clause_is_counted_without_hiding_its_identity(self):
        root, receipt, child = _parent_and_child(self)
        decision = closure_readiness(root, child)
        route = decision["canonical_next_command"]
        self.assertIn("1 open clause", route)
        self.assertIn(f"{receipt}:R002", route)
        self.assertNotIn("more", route)
        self.assertLess(len(route), 200, route)

    def test_many_foreign_owners_do_not_expand_the_route_again(self):
        root, receipt, child, clauses = _many_clauses(self)
        owners = {clause: f"T-{number}" for number, clause in enumerate(clauses, 100)}
        with patch("saipen_engine.closure_readiness._clause_owners", return_value=owners):
            decision = closure_readiness(root, child)
        route = decision["canonical_next_command"]
        self.assertLess(len(route), 200, route)
        self.assertIn("ACTIVE_DEPENDENCY:T-100", route)
        self.assertIn(receipt, route)
        self.assertIn("34 open clauses", route)
        self.assertIn("33 other owners", route)
        self.assertTrue(set(clauses).issubset(decision["unresolved"]), decision)


if __name__ == "__main__":
    unittest.main()
