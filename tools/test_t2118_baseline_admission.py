"""T-2118: absorbed reds publish only with an owner disposition (SRC-437 P0)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import core_unit  # noqa: E402
from test_core_unit_gate import INHERITED, CoreUnitFixture, _run  # noqa: E402

from saipen_engine.operations import checkpoint  # noqa: E402

POLICY_REL = "tools/verification_policy.json"
POLICY = {"schema": 1, "ticket": "focused", "publication": "full"}


class BaselineAdmissionTests(CoreUnitFixture):
    """``red_owners`` attribution closes INV iv-2 without code changes."""

    def setUp(self):
        super().setUp()
        (self.project / POLICY_REL).write_text(json.dumps(POLICY), encoding="utf-8")

    def owners_baseline(self, owners) -> None:
        data = {
            "schema": core_unit.SCHEMA_VERSION,
            "family": core_unit.FAMILY_NAME,
            "red": INHERITED,
            "red_owners": owners,
        }
        (self.project / core_unit.BASELINE_REL).write_text(
            json.dumps(data), encoding="utf-8"
        )

    def gate(self):
        from saipen_engine.focused_unit import publication_gate

        return publication_gate(self.project)

    def test_undecided_owner_blocks_publication(self):
        self.owners_baseline(
            {"test_old.OldTests.test_known_red": {"ticket": "T-2049", "disposition": "undecided"}}
        )
        self.cite(_run(INHERITED))
        problem = self.gate()
        self.assertIsNotNone(problem)
        self.assertIn("undecided", problem)
        self.assertIn("T-2118", problem)
        self.assertIn("test_old.OldTests.test_known_red", problem)

    def test_resolved_owner_publishes(self):
        # T-2132 (Campaign VII P0-A): a resolved owner must now be TERMINAL in
        # both canonical projections -- a closing-op journal event AND the
        # ## DONE board row. The old witness shape (a RUN checkpoint mention
        # for the live T-7) was the P0-A hole and is re-pinned to refuse in
        # test_t2122_red_owner_fail_closed; publication survives only with a
        # genuinely finished owner.
        witness = checkpoint(self.project, "tester", "RUN", "T-7", "witness row")
        self.assertTrue(witness.ok, witness.to_dict())
        self.owners_baseline(
            {"test_old.OldTests.test_known_red": {"ticket": "T-7", "disposition": "resolved"}}
        )
        self.cite(_run(INHERITED))
        board = (
            "## DONE\n"
            "- [x] T-7 [P1] owner probe | verify: probe "
            "| owner: tester | claim_time: 2026-11-21T00:00:00Z\n"
        )
        (self.project / ".saipen" / "BOARD.md").write_text(board, encoding="utf-8")
        with (self.project / ".saipen" / "LOG.md").open("a", encoding="utf-8") as fh:
            fh.write(
                "- 24.08.26 06:57 [E-002] [parent: E-001] [T-7] [agent: tester] "
                "[op: finish-26c9329cf5764d18933ce908a4bfadb0] "
                "DEC: ticket finished via SHIP\n"
            )
        self.assertIsNone(self.gate())

    def test_baseline_without_owners_stays_permissive(self):
        # Pre-attribution baselines keep today's behavior (the live project).
        self.write_baseline(INHERITED)
        self.cite(_run(INHERITED))
        self.assertIsNone(self.gate())

    def test_malformed_owner_entry_is_refused(self):
        for malformed in ("T-2049", {"disposition": "resolved"}, {"ticket": ""}):
            with self.subTest(malformed=malformed):
                self.owners_baseline({"test_old.OldTests.test_known_red": malformed})
                self.cite(_run(INHERITED))
                problem = self.gate()
                self.assertIsNotNone(problem)
                self.assertIn("malformed", problem)

    def test_undecided_name_not_carried_publishes(self):
        self.owners_baseline(
            {"test_other.Old.test_x": {"ticket": "T-2077", "disposition": "undecided"}}
        )
        self.cite(_run(INHERITED))
        self.assertIsNone(self.gate())


if __name__ == "__main__":
    unittest.main()
