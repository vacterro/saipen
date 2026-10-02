"""T-1284: the producer severity policy, proven in-process cell by cell.

`saipen_engine.producer_gate` is the one mapping from gate to producer
severity that tools/validate.py imports. It shipped in v8.0.1 naming an
in-process test matrix that never existed, while run_scenarios proved the
table by launching validate.py thirteen times (7.9 s here). This module is
that matrix: the whole gate x producer x finding-class surface against an
explicit oracle, the closed input contract, and a red control proving the
matrix notices a wrong mapping. run_producer_gate_probes keeps seven
validate.py sentinels that prove the wiring.

Coverage of the thirteen former subprocess runs, case by case:
  1, 1c   default gate soft + visible WARN   -> sentinel (one run)
  1b      ship gate soft                     -> matrix rows "ship"
  2       collect:saiwiki hardens saiwiki    -> sentinel + matrix
  2b      collect:saitranslate leaves QQ soft -> sentinel (with 5) + matrix
  3       converge hardens QQ                -> sentinel + matrix
  4       malformed EE soft at ship          -> matrix (MALFORMED at ship) +
                                                parse test below
  5       malformed EE FAILs collect:EE      -> sentinel + parse test below
  6, 6b   fresh exact EE + QQ pass converge  -> sentinel (one run)
  7       collect with no ready package      -> sentinel 9, same validator branch
  8       converge names a missing package   -> sentinel (EE missing, with 3)
  9       misspelled collect:saiwki          -> sentinel + contract test below
  10      unknown gate exits 2               -> sentinel (CLI is the subject) +
                                                contract test below
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import producer_gate as pg  # noqa: E402
from saipen_engine.subs import parse_outbox  # noqa: E402

GATES = (
    "core",
    "ship",
    "crew",
    "converge",
    "collect:saiwiki",
    "collect:saitranslate",
    "collect:saihunt",
)
PRODUCERS = ("saiwiki", "saitranslate", "saihunt", "saipython", None)
CLASSES = ("MALFORMED", "STALE", "INCOMPLETE", "NOT_READY", "MISSING")

#: The oracle: the only (gate, producer) cells that FAIL, for every class.
#: A consumed producer is hard; the closure's required producers are hard at
#: converge; everything else is a visible WARN.
HARD = frozenset(
    {
        ("collect:saiwiki", "saiwiki"),
        ("collect:saitranslate", "saitranslate"),
        ("collect:saihunt", "saihunt"),
        ("converge", "saiwiki"),
        ("converge", "saitranslate"),
    }
)

READY_PACKAGE = (
    "# OUTBOX\n\n"
    "## PROBE-1: probe package\n"
    "- **status:** ready\n"
    "- **producer:** saitranslate\n"
    "- **summary:** probe package\n"
    "- **critical:** none\n"
    "- **coverage:** complete\n"
    "- **payload:** probe\n"
    "- **instructions:** apply\n"
    "- **verified:** PASS -- probe suite green\n"
    "- **source_head:** 0000000\n"
    "- **source_tree_fingerprint:** git-delta-v1:" + "0" * 64 + "\n"
    "- **role_revision:** sha256:" + "0" * 64 + "\n"
)


def matrix_mismatches(severity) -> list[str]:
    """Every cell where ``severity`` disagrees with the oracle."""
    wrong = []
    for gate in GATES:
        context = pg.parse_gate_context(gate)
        for producer in PRODUCERS:
            for finding in CLASSES:
                want = "FAIL" if (gate, producer) in HARD else "WARN"
                got = severity(context, producer, finding)
                if got != want:
                    wrong.append(f"{gate} x {producer} x {finding}: want {want}, got {got}")
    return wrong


def validator_producer_slugs() -> set[str]:
    """The slug literals tools/validate.py passes to producer_problem."""
    tree = ast.parse((TOOLS / "validate.py").read_text(encoding="utf-8"))
    slugs = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "producer_problem"
            and len(node.args) >= 2
        ):
            slug = node.args[1]
            if not (isinstance(slug, ast.Constant) and isinstance(slug.value, str)):
                raise AssertionError(f"producer_problem slug is not a literal: {ast.dump(slug)}")
            slugs.add(slug.value)
    return slugs


class SeverityMatrixTests(unittest.TestCase):
    def test_the_closed_class_set_is_the_one_the_oracle_covers(self):
        self.assertEqual(pg.FINDING_CLASSES, frozenset(CLASSES))
        self.assertEqual(set(pg.CONVERGE_REQUIRED_PRODUCERS), {"saiwiki", "saitranslate"})

    def test_the_policy_matches_the_truth_table(self):
        self.assertEqual(matrix_mismatches(pg.severity), [])
        self.assertEqual(len(GATES) * len(PRODUCERS) * len(CLASSES), 175)

    def test_red_control_a_wrong_mapping_goes_red(self):
        def collect_hardens_everyone(gate, producer, finding):
            return "FAIL" if gate.kind == "collect" else pg.severity(gate, producer, finding)

        def converge_forgets_qq(gate, producer, finding):
            if gate.kind == "converge" and producer == "saiwiki":
                return "WARN"
            return pg.severity(gate, producer, finding)

        def ship_is_hard(gate, producer, finding):
            return "FAIL" if gate.kind == "ship" else pg.severity(gate, producer, finding)

        def stale_is_soft_when_consumed(gate, producer, finding):
            return "WARN" if finding == "STALE" else pg.severity(gate, producer, finding)

        for wrong in (
            collect_hardens_everyone,
            converge_forgets_qq,
            ship_is_hard,
            stale_is_soft_when_consumed,
        ):
            with self.subTest(policy=wrong.__name__):
                self.assertNotEqual(matrix_mismatches(wrong), [])

    def test_an_unknown_finding_class_refuses_even_at_a_soft_gate(self):
        for gate in ("core", "collect:saiwiki"):
            with self.subTest(gate=gate), self.assertRaises(ValueError):
                pg.severity(pg.parse_gate_context(gate), "saiwiki", "BOGUS")


class GateContractTests(unittest.TestCase):
    def test_no_gate_means_core(self):
        self.assertEqual(pg.parse_gate_context(None), pg.GateContext("core"))

    def test_unknown_and_malformed_gates_refuse_instead_of_falling_back(self):
        for raw in ("nonsense", "Core", "", "converge:saiwiki", "ship:saiwiki", "collect"):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, "unknown --gate"):
                pg.parse_gate_context(raw)
        for raw in ("collect:", "collect:Saiwiki", "collect:sai wiki", "collect:9wiki"):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, "needs a producer"):
                pg.parse_gate_context(raw)

    def test_a_misspelled_producer_stays_a_hard_collect_gate(self):
        # A typo never becomes the soft default: the validator then finds no
        # ready package from `saiwki` and FAILs (sentinel 9).
        context = pg.parse_gate_context("collect:saiwki")
        self.assertEqual((context.kind, context.producer), ("collect", "saiwki"))
        self.assertEqual(pg.severity(context, "saiwiki", "STALE"), "WARN")
        self.assertEqual(pg.severity(context, "saiwki", "MISSING"), "FAIL")

    def test_the_gate_context_is_closed_by_construction(self):
        for kind, producer in (("bogus", None), ("core", "saiwiki"), ("collect", None)):
            with self.subTest(kind=kind, producer=producer), self.assertRaises(ValueError):
                pg.GateContext(kind, producer)


class ValidatorWiringTests(unittest.TestCase):
    def test_every_slug_the_validator_reports_is_mapped(self):
        slugs = validator_producer_slugs()
        self.assertGreaterEqual(len(slugs), 2, slugs)
        for slug in slugs:
            with self.subTest(slug=slug):
                self.assertIn(pg.finding_class_for_slug(slug), pg.FINDING_CLASSES)

    def test_an_unmapped_slug_fails_closed(self):
        with self.assertRaises(ValueError):
            pg.finding_class_for_slug("producer-package-bogus")

    def test_the_probe_fixtures_parse_as_the_sentinels_assume(self):
        malformed = parse_outbox("this is not an OUTBOX at all\n", "saitranslate")
        self.assertTrue(malformed.errors)
        ready = parse_outbox(READY_PACKAGE, "saitranslate")
        self.assertEqual(ready.errors, ())
        self.assertEqual([package.status for package in ready.packages], ["ready"])


if __name__ == "__main__":
    unittest.main()
