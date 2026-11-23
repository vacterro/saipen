"""T-2122: owner attribution is fail-closed outside the valid vocabulary.

Post-T-2118 regression (SRC-440 handoff wave B): unknown disposition strings,
empty dispositions and non-dict ``red_owners`` shapes were silently admitted
to publication. The valid model is CLOSED: ``undecided`` and ``resolved`` with
a well-formed ``ticket``, and a ``resolved`` owner must be witnessed in the
project journal. Everything else refuses.
"""

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
RED_NAME = INHERITED[0]


class OwnerAttributionFailClosedTests(CoreUnitFixture):
    """Every unknown/malformed attribution shape must REFUSE publication."""

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

    def expect_refusal(self, marker: str) -> None:
        problem = self.gate()
        self.assertIsNotNone(problem, marker)
        self.assertIn(marker.split(":")[0].strip().lower(), problem.lower())

    # -- handoff table (measured fail-open before this fix) ----------------

    def test_unknown_disposition_refuses(self):
        self.owners_baseline({RED_NAME: {"ticket": "T-2049", "disposition": "WHATEVER"}})
        self.cite(_run(INHERITED))
        self.expect_refusal("disposition")

    def test_empty_disposition_refuses(self):
        self.owners_baseline({RED_NAME: {"ticket": "T-2049", "disposition": ""}})
        self.cite(_run(INHERITED))
        self.expect_refusal("disposition")

    def test_null_disposition_refuses(self):
        self.owners_baseline({RED_NAME: {"ticket": "T-2049", "disposition": None}})
        self.cite(_run(INHERITED))
        self.expect_refusal("disposition")

    def test_red_owners_string_refuses(self):
        self.owners_baseline("T-2049 undecided")
        self.cite(_run(INHERITED))
        self.expect_refusal("malformed")

    def test_red_owners_list_refuses(self):
        self.owners_baseline([RED_NAME])
        self.cite(_run(INHERITED))
        self.expect_refusal("malformed")

    # -- entry shapes -------------------------------------------------------

    def test_owner_entry_string_refuses(self):
        self.owners_baseline({RED_NAME: "T-2049"})
        self.cite(_run(INHERITED))
        self.expect_refusal("malformed")

    def test_owner_entry_list_refuses(self):
        self.owners_baseline({RED_NAME: ["T-2049", "undecided"]})
        self.cite(_run(INHERITED))
        self.expect_refusal("malformed")

    def test_missing_ticket_refuses(self):
        self.owners_baseline({RED_NAME: {"disposition": "undecided"}})
        self.cite(_run(INHERITED))
        self.expect_refusal("malformed")

    def test_invalid_ticket_id_refuses(self):
        for bad in ("", "T-XX", "2049", "T-", None, 2049):
            with self.subTest(ticket=bad):
                self.owners_baseline({RED_NAME: {"ticket": bad, "disposition": "resolved"}})
                self.cite(_run(INHERITED))
                self.expect_refusal("malformed")

    # -- resolved needs a witnessed owner -----------------------------------

    def test_resolved_without_journal_witness_refuses(self):
        self.owners_baseline({RED_NAME: {"ticket": "T-9999", "disposition": "resolved"}})
        self.cite(_run(INHERITED))
        self.expect_refusal("not terminal")

    def test_undecided_still_refuses_same_as_t2118(self):
        self.owners_baseline({RED_NAME: {"ticket": "T-2049", "disposition": "undecided"}})
        self.cite(_run(INHERITED))
        problem = self.gate()
        self.assertIsNotNone(problem)
        self.assertIn("undecided", problem)

    # -- publication boundary stays coherent --------------------------------

    def test_tampered_baseline_after_record_refuses(self):
        from saipen_engine.focused_unit import publication_gate

        self.owners_baseline({RED_NAME: {"ticket": "T-2049", "disposition": "undecided"}})
        self.cite(_run(INHERITED))
        self.assertIsNotNone(self.gate())
        # remove the attribution AFTER the record was written: the cited run
        # was produced against different baseline bytes, so the digest check
        # must refuse, not silently admit.
        self.owners_baseline({})
        problem = publication_gate(self.project)
        self.assertIsNotNone(problem)

    def test_live_owner_with_journal_mention_refuses(self):
        # T-2132 (Campaign VII P0-A): this exact shape was the hole -- a RUN
        # checkpoint mention for a live DOING owner authorized publication.
        # Re-pinned: the mention is not a terminal proof; only a finished
        # owner (closing-op event + ## DONE row) publishes, which the
        # OwnerTerminalResolutionTests pins from both sides.
        result = checkpoint(self.project, "tester", "RUN", "T-7", "closure witness row")
        self.assertTrue(result.ok, result.to_dict())
        self.owners_baseline({RED_NAME: {"ticket": "T-7", "disposition": "resolved"}})
        self.cite(_run(INHERITED))
        self.expect_refusal("not terminal")


if __name__ == "__main__":
    unittest.main()


class OwnerTerminalResolutionTests(OwnerAttributionFailClosedTests):
    """T-2132 (Campaign VII P0-A): a journal mention is not a resolution proof.

    Reproduced live on 713f49c76: an owner sitting in DOING with a single RUN
    checkpoint mention in the journal authorized publication of an inherited
    red marked ``resolved``. A mention is evidence something happened, not
    proof the right thing happened; ``resolved`` requires the owner to be
    TERMINAL in BOTH canonical projections -- a closing operation event for
    the owner ticket in one consistent history snapshot, and the owner row
    projected into ``## DONE`` on the BOARD. Anything else refuses.
    """

    def log_append(self, line: str) -> None:
        with (self.project / ".saipen" / "LOG.md").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def finish_owner_event(self, ticket: str = "T-7") -> None:
        self.log_append(
            f"- 24.08.26 06:57 [E-002] [parent: E-001] [{ticket}] "
            f"[agent: tester] [op: finish-26c9329cf5764d18933ce908a4bfadb0] "
            f"DEC: ticket finished via SHIP"
        )

    def board_section(self, ticket: str, section: str) -> None:
        marker = {"## DOING": "- [/] ", "## TODO": "- [ ] ",
                  "## BLOCKED": "- [ ] ", "## DONE": "- [x] "}[section]
        board = (
            f"{section}\n"
            f"{marker}{ticket} [P1] owner probe | verify: probe "
            f"| owner: tester | claim_time: 2026-11-21T00:00:00Z\n"
        )
        (self.project / ".saipen" / "BOARD.md").write_text(board, encoding="utf-8")

    def resolved_cite(self, ticket: str = "T-7") -> None:
        self.owners_baseline({RED_NAME: {"ticket": ticket, "disposition": "resolved"}})
        self.cite(_run(INHERITED))

    def test_doing_owner_with_run_mention_refuses(self):
        result = checkpoint(self.project, "tester", "RUN", "T-7", "closure witness row")
        self.assertTrue(result.ok, result.to_dict())
        self.resolved_cite()
        self.expect_refusal("not terminal")

    def test_todo_owner_with_run_mention_refuses(self):
        result = checkpoint(self.project, "tester", "RUN", "T-7", "passing mention")
        self.assertTrue(result.ok, result.to_dict())
        self.resolved_cite()
        self.board_section("T-7", "## TODO")
        self.expect_refusal("not terminal")

    def test_blocked_owner_with_mention_refuses(self):
        result = checkpoint(self.project, "tester", "RUN", "T-7", "passing mention")
        self.assertTrue(result.ok, result.to_dict())
        self.resolved_cite()
        self.board_section("T-7", "## BLOCKED")
        self.expect_refusal("not terminal")

    def test_closing_event_for_another_ticket_never_resolves_this_owner(self):
        self.resolved_cite()
        self.finish_owner_event("T-8")
        self.board_section("T-7", "## DONE")
        self.expect_refusal("not terminal")

    def test_done_board_row_without_closing_event_refuses(self):
        # Both projections must agree: a DONE row with no journaled closing
        # operation is a scheduling projection without terminal proof.
        result = checkpoint(self.project, "tester", "RUN", "T-7", "mention without closing op")
        self.assertTrue(result.ok, result.to_dict())
        self.resolved_cite()
        self.board_section("T-7", "## DONE")
        self.expect_refusal("not terminal")

    def test_closing_event_without_done_row_refuses(self):
        self.resolved_cite()
        self.finish_owner_event("T-7")
        self.expect_refusal("not terminal")

    def test_terminal_owner_in_both_projections_publishes(self):
        self.resolved_cite()
        self.board_section("T-7", "## DONE")
        self.finish_owner_event("T-7")
        self.assertIsNone(self.gate())


if __name__ == "__main__":
    unittest.main()
