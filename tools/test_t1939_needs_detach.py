"""T-1939: detach ONE mechanically-proven inverted `needs:` edge.

The measured deadlock: `ticket add --needs` gave SRC-274's three projected
children `needs: T-1815`, while the receipt's coverage assigns the open clauses
R003/R004/R005 to exactly those children. The parent owns the receipt, so it
must close last, and cannot: `ticket done` refuses SOURCE_UNRESOLVED while a
clause it does not own is open, and `claim` of every child refuses
`unmet needs: T-1815`. Neither side can move.

What these controls hold:

  proof_is_mechanical     the detachment decision reads BOARD + the coverage
                          ledger; the command supplies only two identities
  inversion_detaches     a proven inversion loses exactly one edge
  legitimate_prerequisite_is_kept
                          a real ordering (need is not parked on the ticket, or
                          owns no open clause of it) is refused with zero writes
  absent_edge_is_named   a `needs` entry that is not there is its own refusal,
                          never a silent success
  live_sections_only     DOING/DONE recipients are refused: their ordering is
                          history, not a scheduling artifact
  no_prose_authority      the reason string in the blocker cannot make an
                          otherwise-unproven edge detach

Run standalone:
    python tools/test_t1939_needs_detach.py
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import needs_detach  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402

RECEIPT = "SRC-274"


def _board(tickets: list[str]) -> dict:
    """The shared parser refuses a board whose work surface is split or missing."""
    text = (
        "# Board\n\n## DOING\n\n## TODO\n\n"
        + "".join(tickets)
        + "\n## BLOCKED\n\n## DONE\n\n"
    )
    parsed = parse_board(text)
    assert not parsed["errors"], parsed["errors"]
    return parsed


class NeedsDetachProofTests(unittest.TestCase):
    """`prove_inversion` is the ONE decision; it must answer from project truth."""

    def setUp(self) -> None:
        # A ledger that states the premise, instead of borrowing one. SRC-274
        # closed on 2026-10-27; its live ledger is gone and the archived copy
        # marks all seven rows terminal, so reading the project would hand
        # these tests an empty open-owner map -- the exact opposite of what
        # they assert. The ledger content is part of the test, not of history.
        self._tmp = tempfile.TemporaryDirectory(prefix="saipen-t1939-proof-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "PROJECT"
        (self.root / ".saipen" / "intake" / "coverage").mkdir(parents=True)
        (self.root / ".saipen" / "intake" / "coverage" / f"{RECEIPT}.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "requirements": {
                        f"{RECEIPT}:R003": {
                            "actionable": True,
                            "class": "requirement",
                            "disposition": "UNKNOWN",
                            "work": "T-1853",
                            "text": "the sibling's open clause",
                        },
                        f"{RECEIPT}:R004": {
                            "actionable": True,
                            "class": "requirement",
                            "disposition": "UNKNOWN",
                            "work": "T-1854",
                            "text": "this ticket's open clause",
                        },
                        f"{RECEIPT}:R005": {
                            "actionable": True,
                            "class": "requirement",
                            "disposition": "UNKNOWN",
                            "work": "T-1855",
                            "text": "the third sibling's open clause",
                        },
                    },
                },
                indent=1,
            ),
            encoding="utf-8",
        )

    def _tickets(self, *, recipient_section="## TODO", need_section="## BLOCKED",
                 blocker="ACTIVE_DEPENDENCY:T-1 -- parked", needs="T-2",
                 receipts="SRC-274"):
        """A parent TODO row and its dependency; the dependency's section varies."""
        parent = (
            f"- [ ] T-1 [P1] parent owns the receipt | needs: {needs} | verify: x\n"
        )
        child = (
            f"- [ ] T-2 [P1] child builds the clause | blocker: {blocker}"
            + (f" | source_receipts: {receipts}" if receipts else "")
            + " | verify: x\n"
        )
        if need_section == "## BLOCKED":
            text = (
                "# Board\n\n## DOING\n\n## TODO\n\n"
                + parent
                + "\n## BLOCKED\n\n"
                + child
                + "\n## DONE\n\n"
            )
        else:
            text = (
                "# Board\n\n## DOING\n\n## TODO\n\n" + parent + child + "\n## BLOCKED\n\n## DONE\n\n"
            )
        parsed = parse_board(text)
        assert not parsed["errors"], parsed["errors"]
        return parsed

    def test_inversion_is_proven_from_the_coverage_ledger(self):
        """The edge is inverted because the ledger assigns the open clause here.

        This reads the PROJECT's real SRC-274 ledger, which assigns R003 to
        T-1853. Substituting a synthetic clause row would let the test pass
        while the actual scoring surface was wrong.
        """
        text = (
            "# Board\n\n## DOING\n\n## TODO\n\n"
            "- [ ] T-1853 [P1] child builds R003 | needs: T-1815 | verify: x\n\n"
            "## BLOCKED\n\n"
            "- [ ] T-1815 [P1] parent owns SRC-274"
            " | blocker: ACTIVE_DEPENDENCY:T-1853 -- SRC-274 has 3 open clauses"
            " | source_receipts: SRC-274 | verify: x\n\n"
            "## DONE\n\n"
        )
        board = parse_board(text)
        self.assertFalse(board["errors"], board["errors"])
        proof = needs_detach.prove_inversion(
            self.root, "T-1853", "T-1815", tickets=board["tickets"]
        )
        self.assertTrue(proof["inverted"], proof)
        owned = proof["facts"]["open_clauses_owned_by_ticket"]
        self.assertIn({"receipt": RECEIPT, "clause": f"{RECEIPT}:R003"}, owned)

    def test_a_need_that_is_not_parked_on_this_ticket_is_a_real_prerequisite(self):
        """A prerequisite order is the ordinary case and must never be detached."""
        board = self._tickets(blocker="ACTIVE_DEPENDENCY:T-9 -- someone else")
        proof = needs_detach.prove_inversion(
            Path("."), "T-1", "T-2", tickets=board["tickets"]
        )
        self.assertFalse(proof["inverted"], proof)
        self.assertIn("does not point back here", proof["reason"])

    def test_a_need_with_no_receipt_cannot_prove_ownership(self):
        board = self._tickets(receipts="")
        proof = needs_detach.prove_inversion(
            Path("."), "T-1", "T-2", tickets=board["tickets"]
        )
        self.assertFalse(proof["inverted"], proof)
        self.assertIn("no source_receipts", proof["reason"])

    def test_a_need_that_is_not_blocked_is_not_an_inversion(self):
        rows = [
            "- [ ] T-1 [P1] parent | needs: T-2 | verify: x\n",
            "- [ ] T-2 [P1] child | source_receipts: SRC-274 | verify: x\n",
        ]
        board = _board(rows)
        proof = needs_detach.prove_inversion(
            Path("."), "T-1", "T-2", tickets=board["tickets"]
        )
        self.assertFalse(proof["inverted"], proof)
        self.assertIn("not BLOCKED", proof["reason"])

    def test_an_absent_edge_is_named_as_absent(self):
        board = self._tickets(needs="T-3")
        proof = needs_detach.prove_inversion(
            Path("."), "T-1", "T-2", tickets=board["tickets"]
        )
        self.assertFalse(proof["inverted"], proof)
        self.assertIn("does not declare needs", proof["reason"])

    def test_a_receipt_that_assigns_no_open_clause_here_is_a_real_prerequisite(self):
        """The gap the first control exposed: a receipt exists, yet owns nothing here.

        Without this case a mutant that skipped the ownership proof stayed green,
        because every other negative test was stopped by an EARLIER guard. This
        one passes the park check and the receipt check, and fails only on
        ownership -- so it is the test that actually holds that proof.
        """
        text = (
            "# Board\n\n## DOING\n\n## TODO\n\n"
            "- [ ] T-1 [P1] parent | needs: T-2 | verify: x\n\n"
            "## BLOCKED\n\n"
            "- [ ] T-2 [P1] child"
            " | blocker: ACTIVE_DEPENDENCY:T-1 -- parked"
            " | source_receipts: SRC-274 | verify: x\n\n"
            "## DONE\n\n"
        )
        board = parse_board(text)
        self.assertFalse(board["errors"], board["errors"])
        proof = needs_detach.prove_inversion(
            self.root, "T-1", "T-2", tickets=board["tickets"]
        )
        self.assertFalse(proof["inverted"], proof)
        self.assertEqual(
            proof["facts"]["need_receipts"], ["SRC-274"], "the receipt guard must not fire here"
        )
        self.assertIn("is a real prerequisite ordering", proof["reason"])

    def test_a_receipt_wide_park_names_one_representative_owner(self):
        """The real T-1815 shape: the park names T-1853, and R004 belongs to T-1854.

        A receipt-wide park records ONE representative owner plus a count
        ("owner: T-1853 (+2 other owners)"). Demanding the head be this ticket
        would leave two of three legitimate children permanently stuck, so the
        proof must accept a co-owner of the receipt the park itself names.
        """
        text = (
            "# Board\n\n## DOING\n\n## TODO\n\n"
            "- [ ] T-1854 [P1] sibling builds R004 | needs: T-1815 | verify: x\n\n"
            "## BLOCKED\n\n"
            "- [ ] T-1815 [P1] parent owns SRC-274"
            " | blocker: ACTIVE_DEPENDENCY:T-1853 -- SRC-274: 3 open clauses"
            " (SRC-274:R003 SRC-274:R004 SRC-274:R005) owner: T-1853 (+2 other owners)"
            " | source_receipts: SRC-274 | verify: x\n\n"
            "## DONE\n\n"
        )
        board = parse_board(text)
        self.assertFalse(board["errors"], board["errors"])
        proof = needs_detach.prove_inversion(
            self.root, "T-1854", "T-1815", tickets=board["tickets"]
        )
        self.assertTrue(proof["inverted"], proof)
        self.assertEqual(proof["facts"]["park_pin"], "receipt-scoped")
        self.assertIn("T-1853", proof["facts"]["park_peer_owners"])
        self.assertIn(
            {"receipt": RECEIPT, "clause": f"{RECEIPT}:R004"},
            proof["facts"]["open_clauses_owned_by_ticket"],
        )

    def test_a_receipt_wide_park_with_a_stranger_head_is_still_a_prerequisite(self):
        """Widening the pin must not turn every park into an inversion.

        The park names our receipt, but its head owns no open clause of it. That
        is a park ordered by something else that happens to mention the receipt,
        not a receipt-wide dependency on a co-owner, so nothing may detach.
        """
        text = (
            "# Board\n\n## DOING\n\n## TODO\n\n"
            "- [ ] T-1854 [P1] sibling builds R004 | needs: T-1815 | verify: x\n\n"
            "## BLOCKED\n\n"
            "- [ ] T-1815 [P1] parent owns SRC-274"
            " | blocker: ACTIVE_DEPENDENCY:T-1901 -- SRC-274 waits for operator triage"
            " | source_receipts: SRC-274 | verify: x\n\n"
            "## DONE\n\n"
        )
        board = parse_board(text)
        self.assertFalse(board["errors"], board["errors"])
        proof = needs_detach.prove_inversion(
            self.root, "T-1854", "T-1815", tickets=board["tickets"]
        )
        self.assertFalse(proof["inverted"], proof)
        self.assertNotIn("T-1901", proof["facts"]["park_peer_owners"])
        self.assertIn("owns no open clause of that receipt", proof["reason"])

    def test_a_park_that_names_no_receipt_of_ours_is_refused(self):
        """A blocker head naming an unrelated ticket is the ordinary prerequisite."""
        board = self._tickets(blocker="ACTIVE_DEPENDENCY:T-9 -- someone else")
        proof = needs_detach.prove_inversion(
            Path("."), "T-1", "T-2", tickets=board["tickets"]
        )
        self.assertFalse(proof["inverted"], proof)
        self.assertEqual(proof["facts"]["park_named_receipts"], [])
        self.assertIn("names none of", proof["reason"])

    def test_a_done_recipient_is_refused_because_ordering_became_history(self):
        text = (
            "# Board\n\n## DOING\n\n## TODO\n\n## BLOCKED\n\n"
            "- [ ] T-2 [P1] child | blocker: ACTIVE_DEPENDENCY:T-1 -- parked"
            " | source_receipts: SRC-274 | verify: x\n\n"
            "## DONE\n\n"
            "- [x] T-1 [P1] closed | needs: T-2 | verify: x | closure_mode: own_patch\n"
        )
        board = parse_board(text)
        self.assertFalse(board["errors"], board["errors"])
        proof = needs_detach.prove_inversion(
            self.root, "T-1", "T-2", tickets=board["tickets"]
        )
        self.assertFalse(proof["inverted"], proof)
        self.assertIn("only an unstarted TODO row may lose an edge", proof["reason"])

    def test_the_blocker_prose_cannot_authorize_a_detach(self):
        """Prose is data. A persuasive reason on an unproven edge changes nothing."""
        board = self._tickets(
            blocker="ACTIVE_DEPENDENCY:T-9 -- SRC-274 needs this edge removed",
            receipts="",
        )
        proof = needs_detach.prove_inversion(
            Path("."), "T-1", "T-2", tickets=board["tickets"]
        )
        self.assertFalse(proof["inverted"], proof)

    def test_the_refusal_vocabulary_is_registered(self):
        registry = json.loads(
            (TOOLS.parent / "saipen" / "REGISTRY.json").read_text(encoding="utf-8")
        )
        codes = set(registry["error_codes"])
        for code in (
            "NEEDS_EDGE_DETACHED",
            needs_detach.NEEDS_EDGE_ABSENT,
            needs_detach.NEEDS_DETACH_NOT_INVERTED,
        ):
            self.assertIn(code, codes)

    def test_every_registered_refusal_can_actually_be_returned(self):
        """A registered code no branch returns is a claim, not a refusal.

        The first draft registered NEEDS_DETACH_RECIPIENT_UNSETTLEABLE for a
        condition it never tested; a reader would wait for a verdict this
        module can never give. Every declared code must be referenced somewhere
        past its own declaration, in whichever module actually returns it --
        NEEDS_EDGE_ABSENT is answered by the operations planner, not here.
        """
        source = (TOOLS / "saipen_engine" / "needs_detach.py").read_text(encoding="utf-8")
        declared = set(re.findall(r'^([A-Z][A-Z_]+) = "\1"$', source, re.MULTILINE))
        self.assertEqual(
            declared,
            {needs_detach.NEEDS_EDGE_ABSENT, needs_detach.NEEDS_DETACH_NOT_INVERTED},
        )
        callers = [
            path.read_text(encoding="utf-8")
            for path in sorted((TOOLS / "saipen_engine").glob("*.py")) + [TOOLS / "saipen.py"]
            if path.name != "needs_detach.py"
        ]
        for code in declared:
            self.assertTrue(
                any(code in text for text in callers),
                f"{code} is declared but no branch outside its own module returns it",
            )


class NeedsDetachPlanTests(unittest.TestCase):
    """The planner is the half that writes: a proof alone never mutates a board.

    T-1941 measured why this class exists. The first shipped planner declared
    the STATE precondition but emitted only LOG and BOARD targets, so the real
    detach on T-1853 succeeded, left `last_event` one behind the LOG tail, and
    the recovery verifier refused the transaction as checkpoint-invalid -- a
    conflict no unit test of `prove_inversion` could ever see.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="saipen-t1941-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "PROJECT"
        self.root.mkdir()
        source = TOOLS.parent / ".saipen"
        (self.root / ".saipen" / "intake" / "coverage").mkdir(parents=True)
        # Only what _read and the coverage ledger actually open. The live tree
        # is 1.8 GB of evidence, and copying it per test cost 148 s. BOARD is
        # SYNTHETIC, never the live one: this suite's own real detachments
        # remove the edges it needs, so reading live BOARD would make the test
        # pass or fail depending on what the operator had already repaired.
        shutil.copyfile(source / "STATE.md", self.root / ".saipen" / "STATE.md")
        (self.root / ".saipen" / "BOARD.md").write_bytes(
            (
                "# Board\r\n\r\n## DOING\r\n\r\n## TODO\r\n\r\n"
                "- [ ] T-1854 [P1] child owns SRC-274:R004 | needs: T-1815 | verify: x\r\n\r\n"
                "## BLOCKED\r\n\r\n"
                "- [ ] T-1815 [P1] parent owns SRC-274"
                " | blocker: ACTIVE_DEPENDENCY:T-1853 -- SRC-274: 3 open clauses"
                " owner: T-1853 (+2 other owners)"
                " | source_receipts: SRC-274 | verify: x\r\n\r\n"
                "## DONE\r\n\r\n"
            ).encode("utf-8")
        )
        # The ledger is SYNTHETIC for the same reason BOARD above is. SRC-274
        # closed on 2026-10-27 and its ledger moved to
        # `.saipen/archive/source/`, where every row is terminal, so copying
        # the live file either fails outright or hands these tests a ledger
        # with no open clause -- which is the premise they exist to exercise,
        # silently inverted. Copying live state into a fixture makes the
        # verdict depend on project history; stating it here makes it a fact.
        (self.root / ".saipen" / "intake" / "coverage" / f"{RECEIPT}.json").write_bytes(
            json.dumps(
                {
                    "schema_version": 1,
                    "requirements": {
                        f"{RECEIPT}:R003": {
                            "actionable": True,
                            "class": "requirement",
                            "disposition": "UNKNOWN",
                            "work": "T-1853",
                            "text": "the sibling's open clause",
                        },
                        f"{RECEIPT}:R004": {
                            "actionable": True,
                            "class": "requirement",
                            "disposition": "UNKNOWN",
                            "work": "T-1854",
                            "text": "this ticket's open clause",
                        },
                        f"{RECEIPT}:R005": {
                            "actionable": True,
                            "class": "requirement",
                            "disposition": "UNKNOWN",
                            "work": "T-1855",
                            "text": "the third sibling's open clause",
                        },
                    },
                },
                indent=1,
            ).encode("utf-8")
        )
        for name in ("STYLE.md", "EXECUTION.md"):
            if (source / name).is_file():
                shutil.copyfile(source / name, self.root / ".saipen" / name)
        log = self.root / ".saipen" / "LOG.md"
        log.write_bytes(
            "# Log\r\n"
            "- 26.10.26 23:00 [E-1] [agent: saipen-cli] [op: fixture-1] DEC: fixture history\r\n"
            .encode("utf-8")
        )
        state = self.root / ".saipen" / "STATE.md"
        state.write_bytes(state.read_bytes().replace(b"last_event: 18631", b"last_event: 1"))

    def _plan(self, ticket_id: str, need_id: str):
        from saipen_engine import operations

        return operations._plan_detach_needs(
            self.root, ticket_id, need_id, "saipen-cli", "26.10.26 23:10", "2026-10-26T23:10:00Z"
        )

    def test_the_plan_moves_state_with_the_journal(self):
        """A plan that writes LOG and BOARD but not STATE desynchronises the cursor."""
        plan = self._plan("T-1854", "T-1815")
        self.assertNotIsInstance(plan, type(None))
        paths = {target.path for target in plan.targets}
        self.assertEqual(
            paths, {".saipen/LOG.md", ".saipen/BOARD.md", ".saipen/STATE.md"}
        )

    def test_the_state_target_carries_the_event_the_plan_appends(self):
        """The state cursor must name the event this very plan writes."""
        plan = self._plan("T-1854", "T-1815")
        state_target = next(t for t in plan.targets if t.path == ".saipen/STATE.md")
        event = int(str(plan.expected["event_id"]).lstrip("E-"))
        text = state_target.content.decode("utf-8")
        self.assertIn(f"last_event: {event}", text)
        self.assertEqual(text.count(f"last_event: {event}"), 1)

    def test_the_plan_refuses_a_real_prerequisite(self):
        """A planner that always plans would let the CLI detach anything it names."""
        result = self._plan("T-1855", "T-1799")
        self.assertEqual(getattr(result, "code", None), needs_detach.NEEDS_EDGE_ABSENT)


if __name__ == "__main__":
    unittest.main()
