"""T-1670 (SRC-191): what one route loads is the budget, not the repository.

`test_protocol_registry` capped `human_markdown_total`, the sum of every
markdown file under `saipen/`, and re-derived the cap six times (300 -> 327
KiB) as protocol law grew. On 2026-10-07 it stood at 334844 of 334848 bytes
and blocked T-1663 although no route an agent executes loads more than its own
declared budget. These controls pin the route model that replaces it:

* PRE-FIX     -- a small clause in a document no route loads trips the old
                 aggregate cap and passes every route budget.
* GROWTH      -- unrelated growth raises the total, leaves every route byte
                 count alone and stays PASS.
* OVERFLOW    -- mandatory growth past a route budget (BOOT, a phase) FAILs.
* TRANSITIVE  -- a declared `requires` chain A -> B -> C is counted whole.
* OPTIONAL    -- a conditional reference never inflates the mandatory load.
* BOOT        -- growth in VERIFY or FUTURE leaves the cold load byte-identical.
* FILE        -- no single document may exceed `single_doc`, routed or not.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
PROTOCOL = ROOT / "saipen"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import protocol_budget  # noqa: E402

#: The aggregate tripwire `test_protocol_registry` enforced before T-1670.
OLD_AGGREGATE_CAP = 327 * 1024
CLAUSE = "\nA small, valid clause of protocol law, routed nowhere.\n"


class Scratch(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="saipen-t1670-")
        self.addCleanup(self._tmp.cleanup)
        self.protocol = Path(self._tmp.name) / "saipen"
        shutil.copytree(PROTOCOL, self.protocol)

    def grow(self, rel: str, text: str) -> None:
        path = self.protocol / rel
        path.write_bytes(path.read_bytes() + text.encode("utf-8"))

    def registry(self) -> dict:
        return json.loads((self.protocol / "REGISTRY.json").read_text(encoding="utf-8-sig"))

    def write_registry(self, registry: dict) -> None:
        (self.protocol / "REGISTRY.json").write_text(json.dumps(registry, indent=2), "utf-8")

    def routes(self, measured: dict) -> dict[str, int]:
        return {name: measured[name] for name in measured["budgets"]}

    def unrouted(self) -> str:
        """A protocol document no route names, directly or through a surface."""
        measured = protocol_budget.load_profiles(self.protocol)
        named = {
            doc
            for routes in measured["profiles"].values()
            for route in routes
            for doc in (*route["must"], *route["conditional"])
        }
        surfaces = self.registry()["load_profiles"]["surfaces"]
        named |= {doc for spec in surfaces.values() for doc in spec.get("files", ())}
        candidates = [rel for rel in measured["documents"] if "/" not in rel and rel not in named]
        self.assertIn("UI.md", candidates)
        return "UI.md"


class RouteBudgetTests(Scratch):
    def test_pre_fix_control_a_routed_nowhere_clause_tripped_only_the_aggregate(self):
        before = protocol_budget.load_profiles(self.protocol)
        need = OLD_AGGREGATE_CAP - before["human_markdown_total"] + 1
        self.grow(self.unrouted(), CLAUSE * (need // len(CLAUSE) + 1))
        after = protocol_budget.load_profiles(self.protocol)
        self.assertGreater(after["human_markdown_total"], OLD_AGGREGATE_CAP)
        self.assertEqual(self.routes(after), self.routes(before))
        self.assertEqual(protocol_budget.check(self.protocol), [])
        self.assertIn("human_markdown_total", after["informational"])

    def test_unrelated_growth_raises_the_total_and_moves_no_route(self):
        before = protocol_budget.load_profiles(self.protocol)
        self.grow(self.unrouted(), CLAUSE * 200)
        after = protocol_budget.load_profiles(self.protocol)
        self.assertGreater(after["human_markdown_total"], before["human_markdown_total"])
        self.assertEqual(self.routes(after), self.routes(before))
        self.assertEqual(protocol_budget.check(self.protocol), [])

    def test_mandatory_growth_past_a_route_budget_fails(self):
        for rel, profile in (("BOOT.md", "cold"), ("phases/build.md", "ordinary_phase")):
            with self.subTest(rel=rel):
                self.setUp()
                measured = protocol_budget.load_profiles(self.protocol)
                # The route counts the largest phase, so the grown document
                # must become it: a whole budget's worth of bytes always does.
                self.grow(rel, "x" * measured["budgets"][profile])
                errors = protocol_budget.check(self.protocol)
                self.assertTrue(any(error.startswith(f"{profile} ") for error in errors), errors)

    def test_a_declared_dependency_chain_is_counted_whole(self):
        before = protocol_budget.load_profiles(self.protocol)
        (self.protocol / "B.md").write_text("b" * 300, encoding="utf-8")
        (self.protocol / "C.md").write_text("c" * 200, encoding="utf-8")
        registry = self.registry()
        registry["load_profiles"]["requires"] = {"phases/done.md": ["B.md"], "B.md": ["C.md"]}
        self.write_registry(registry)
        after = protocol_budget.load_profiles(self.protocol)
        self.assertEqual(after["ordinary_continue"], before["ordinary_continue"] + 500)
        route = after["profiles"]["ordinary_continue"][0]
        self.assertEqual(route["transitive"], ["B.md", "C.md"])
        self.assertEqual(route["bytes"], sum(route["must"].values()))
        self.assertEqual(after["cold"], before["cold"])

    def test_a_dependency_cycle_is_a_declaration_error(self):
        registry = self.registry()
        registry["load_profiles"]["requires"] = {"CORE.md": ["OPS.md"], "OPS.md": ["CORE.md"]}
        self.write_registry(registry)
        with self.assertRaisesRegex(ValueError, "cycle"):
            protocol_budget.load_profiles(self.protocol)

    def test_an_optional_reference_does_not_inflate_the_mandatory_load(self):
        before = protocol_budget.load_profiles(self.protocol)
        registry = self.registry()
        routes = registry["load_profiles"]["profiles"]["ordinary_phase"]["routes"]
        routes[0]["conditional"].append("FUTURE.md")
        self.write_registry(registry)
        after = protocol_budget.load_profiles(self.protocol)
        self.assertEqual(after["ordinary_phase"], before["ordinary_phase"])
        self.assertIn("FUTURE.md", after["profiles"]["ordinary_phase"][0]["conditional"])

    def test_verify_or_future_growth_leaves_the_cold_load_byte_identical(self):
        before = protocol_budget.load_profiles(self.protocol)
        cold_before = before["profiles"]["cold"]
        self.grow("phases/verify.md", CLAUSE * 20)
        self.grow("FUTURE.md", CLAUSE * 20)
        after = protocol_budget.load_profiles(self.protocol)
        self.assertEqual(after["profiles"]["cold"], cold_before)
        self.assertEqual(after["cold"], before["cold"])

    def test_one_enormous_document_fails_even_where_no_route_loads_it(self):
        measured = protocol_budget.load_profiles(self.protocol)
        rel = self.unrouted()
        limit = measured["budgets"]["single_doc"]
        self.grow(rel, "y" * (limit - measured["documents"][rel] + 1))
        errors = protocol_budget.check(self.protocol)
        self.assertEqual(errors, [f"file {rel} {limit + 1} > single_doc {limit}"])

    def test_the_summary_is_one_line_per_route_and_names_the_total_informational(self):
        lines = protocol_budget.summary(self.protocol)
        budgets = self.registry()["load_profiles"]["budgets"]
        self.assertEqual(len(lines), len(budgets) + 2)
        for line, name in zip(lines, budgets):
            self.assertTrue(line.startswith(name) and line.endswith("PASS"), line)
        self.assertTrue(lines[-1].endswith("informational"), lines[-1])

    def test_the_command_line_summary_exits_by_the_route_verdict(self):
        proc = subprocess.run(
            [sys.executable, "-B", str(TOOLS / "protocol_budget.py"), "--summary"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("human markdown total", proc.stdout)
        self.assertLessEqual(len(proc.stdout.splitlines()), 12)


if __name__ == "__main__":
    unittest.main()
