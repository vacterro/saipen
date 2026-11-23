"""W-A (SRC-436 INV-8; SRC-437 IV): the delta-class boundary of the corridor.

RED datum, measured in this repository 2026-11-20: T-2115 -- a source-delta
ticket (2 new engine test files, commit ``ae206267c``) closed through SHIP on
its own focused citation (E-22043) while the family record carried 109
inherited reds. The focused branch admitted every ticket class; the wave
contract reserves the corridor for delta-free Work and keeps source-delta
Work owned by the declared family.

The declaration rides the machine-owned VERIFY boundary reason:
``saipen transition VERIFY <T-###> delta-class: source`` (or ``none``).
"""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import core_unit  # noqa: E402
from saipen_engine.operations import transition_phase  # noqa: E402
from test_core_unit_gate import CoreUnitFixture, _run  # noqa: E402

POLICY_REL = "tools/verification_policy.json"
POLICY = {"schema": 1, "ticket": "focused", "publication": "full"}
RECORD_REL = ".saipen/evidence/focused-unit/run.json"


class DeltaClassBoundaryTests(CoreUnitFixture):
    def setUp(self):
        super().setUp()
        (self.project / POLICY_REL).write_text(json.dumps(POLICY), encoding="utf-8")
        (self.project / "tools/test_focus.py").write_text(
            "import unittest\nclass Focus(unittest.TestCase):\n"
            "    def test_ok(self): self.assertEqual(2 + 2, 4)\n",
            encoding="utf-8",
        )

    def focused_record(self):
        from saipen_engine.verification_cache import capture

        data = {
            "schema": 1,
            "family": "focused-unit",
            "fingerprint": core_unit.tree_fingerprint(self.project),
            "patterns": ["test_focus.py"],
            "runs": [{"pattern": "test_focus.py", **_run([])}],
            "ran": 10,
            "verdict": "PASS",
            "verification_identity": capture(self.project, {
                "family": "focused-unit", "patterns": ["test_focus.py"], "timeout": 300,
            }),
        }
        path = self.project / RECORD_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.record(
            f"FOCUSED-UNIT-EVIDENCE PASS conf: high ran:{data['ran']} "
            f"record:{RECORD_REL} sha256:{digest}"
        )
        return path

    def declare(self, kind: str):
        """Enter VERIFY carrying the machine-owned delta-class declaration."""
        return transition_phase(self.project, "VERIFY", "tester", "T-7", f"delta-class: {kind}")

    def test_source_delta_with_focused_only_is_refused_at_ship(self):
        result = self.declare("source")
        self.assertTrue(result.ok, result.to_dict())
        self.focused_record()
        self.assertTrue(self.to("REVIEW").ok)
        refused = self.to("SHIP")
        self.assertFalse(refused.ok, refused.to_dict())
        self.assertIn("core-unit family", refused.message)
        self.assertIn("source delta", refused.message)
        self.assertIn("focused evidence cannot substitute", refused.message)

    def proof_family_record(self):
        """Campaign VIII outcome C: a full-family record of the CURRENT tree."""
        return core_unit.write_record(
            self.project, _run([]), core_unit.tree_fingerprint(self.project)
        )

    def test_undeclared_cycle_with_a_proof_keeps_the_corridor(self):
        # Pre-W-A undeclared flow: the corridor still answers the ticket
        # whose tree carries a family record (outcome C). Campaign VIII
        # (T-2133 activation) removed the proof-less legacy route --
        # see LegacyNoTokenCycleTests for the refusals.
        self.assertTrue(self.to("VERIFY").ok)
        self.proof_family_record()
        self.focused_record()
        self.assertTrue(self.to("REVIEW").ok)
        self.assertTrue(self.to("SHIP").ok)

    def test_declared_none_with_a_proof_keeps_the_corridor(self):
        result = self.declare("none")
        self.assertTrue(result.ok, result.to_dict())
        self.proof_family_record()
        self.focused_record()
        self.assertTrue(self.to("REVIEW").ok)
        self.assertTrue(self.to("SHIP").ok)

    def test_delta_class_reads_only_the_boundary_reason(self):
        boundary = {
            "ticket": "T-7",
            "taxonomy": "RUN",
            "text": "transition to VERIFY -- delta-class: source",
        }
        self.assertEqual(
            core_unit._current_cycle_delta_class("T-7", [boundary]), "source"
        )
        self.assertEqual(
            core_unit._current_cycle_delta_class(
                "T-7", [dict(boundary, text="transition to VERIFY -- delta-class: none")]
            ),
            "none",
        )
        self.assertIsNone(
            core_unit._current_cycle_delta_class(
                "T-7", [dict(boundary, text="transition to VERIFY")]
            )
        )

    def test_no_cycle_or_foreign_prose_is_never_a_declaration(self):
        self.assertIsNone(core_unit._current_cycle_delta_class("T-7", []))
        self.assertIsNone(
            core_unit._current_cycle_delta_class(
                "T-7",
                [{
                    "ticket": "T-7",
                    "taxonomy": "RUN",
                    "text": "prose cannot declare a delta class; delta-class: source belongs to the boundary",
                }],
            )
        )
        self.assertIsNone(
            # A foreign ticket's boundary never declares this ticket's class.
            core_unit._current_cycle_delta_class(
                "T-9",
                [dict(boundary={"ticket": "T-7", "taxonomy": "RUN",
                                "text": "transition to VERIFY -- delta-class: source"})],
            )
        )


class MeasuredSourceDeltaTests(DeltaClassBoundaryTests):
    """T-2133 (Campaign VII P0-B): bytes, not declarations, own the corridor.

    RED datum, isolated fixtures, 2026-11-21: a ticket really changed
    ``saipen/CORE.md`` between its BUILD entry and the VERIFY declaration,
    cited a FRESH focused record (fingerprint matching the changed tree),
    declared ``delta-class: none`` (or omitted the declaration) and SHIPPED
    focused-only. The boundary grammar was machine-owned but the reason VALUE
    was caller-supplied, so the focused branch believed the claim.

    The engine now mints a machine-measured ``tree-identity:<fp16>`` token on
    the BUILD boundary (end-anchored: caller prose can never occupy the last
    position), and ``ship_gate`` compares it with the current tree before
    it may take the focused corridor. A cycle whose BUILD boundary predates
    the tokens (no identity) keeps the declared-class rule -- the honest
    activation bound recorded in ``_current_cycle_delta_class``.
    """

    def mint_build_identity(self):
        """Leave BUILD and re-enter it, minting a real boundary event."""
        self.assertTrue(self.to("VERIFY").ok)
        entry = self.to("BUILD")
        self.assertTrue(entry.ok, entry.to_dict())
        return entry

    def change_source(self):
        (self.project / "saipen" / "CORE.md").write_text(
            "# core changed by the ticket\n", encoding="utf-8"
        )

    def test_real_source_change_with_declared_none_refuses_focused_ship(self):
        self.mint_build_identity()
        self.change_source()
        result = self.declare("none")  # the lying declaration
        self.assertTrue(result.ok, result.to_dict())
        self.focused_record()  # fresh: bound to the CHANGED tree
        self.assertTrue(self.to("REVIEW").ok)
        refused = self.to("SHIP")
        self.assertFalse(refused.ok, refused.to_dict())
        self.assertIn("core-unit family", refused.message)
        self.assertIn("BUILD boundary", refused.message)
        self.assertIn("T-2133", refused.message)
        self.assertIn("focused evidence cannot substitute", refused.message)

    def test_real_source_change_with_omitted_declaration_refuses_focused_ship(self):
        self.mint_build_identity()
        self.change_source()
        self.assertTrue(self.to("VERIFY").ok)  # no declaration at all
        self.focused_record()
        self.assertTrue(self.to("REVIEW").ok)
        refused = self.to("SHIP")
        self.assertFalse(refused.ok, refused.to_dict())
        self.assertIn("T-2133", refused.message)

    def test_identity_without_change_keeps_the_focused_corridor(self):
        # The fast path survives: a measured-unchanged cycle still ships on
        # its focused citation (handoff acceptance: delta-free Work keeps it).
        self.mint_build_identity()
        result = self.declare("none")
        self.assertTrue(result.ok, result.to_dict())
        self.focused_record()
        self.assertTrue(self.to("REVIEW").ok)
        self.assertTrue(self.to("SHIP").ok)

    def test_declared_source_still_refuses_with_a_unchanged_measured_identity(self):
        # Conservative order: a source confession takes the family corridor
        # even when the measured identity agrees (the oracle is "or", not "xor").
        self.mint_build_identity()
        result = self.declare("source")
        self.assertTrue(result.ok, result.to_dict())
        self.focused_record()
        self.assertTrue(self.to("REVIEW").ok)
        refused = self.to("SHIP")
        self.assertFalse(refused.ok, refused.to_dict())
        self.assertIn("source delta", refused.message)

    def test_identity_reads_only_this_tickets_build_boundary(self):
        boundary = {
            "ticket": "T-7",
            "taxonomy": "RUN",
            "text": "transition to BUILD -- prep tree-identity:0123456789abcdef",
        }
        self.assertEqual(
            core_unit._cycle_boundary_identity("T-7", "BUILD", [boundary]), "0123456789abcdef"
        )
        # A foreign ticket's boundary never measures this ticket's cycle.
        self.assertIsNone(
            core_unit._cycle_boundary_identity(
                "T-9", "BUILD", [dict(boundary, ticket="T-7")]
            )
        )
        # Prose can never mint one: only the end-anchored machine token counts.
        self.assertIsNone(
            core_unit._cycle_boundary_identity(
                "T-7", "BUILD", [
                    dict(boundary, text="prose mentions tree-identity:0123456789abcdef mid-line"),
                ]
            )
        )
        # Legacy boundaries without a token stay honestly unmeasured.
        self.assertIsNone(
            core_unit._cycle_boundary_identity(
                "T-7", "BUILD", [dict(boundary, text="transition to BUILD -- prep")]
            )
        )


class LegacyNoTokenCycleTests(MeasuredSourceDeltaTests):
    """Campaign VIII P0 (T-2133 activation): legacy cycles get no corridor.

    RED datum, hermetic reproduction 2026-11-21: a ticket sitting in a
    PRE-T-2133 BUILD cycle (no machine-minted tree identity) really changed
    ``saipen/CORE.md``, declared ``delta-class: none``, cited a fresh focused
    record bound to the modified tree -- and SHIPPED focused-only. The
    missing measurement itself was the authorization; the declaration was
    the only oracle. Campaign VIII closes it: a legacy cycle may take the
    corridor only with an independent no-delta proof -- a full-family record
    whose fingerprint IS the current tree and whose baseline IS the current
    baseline (the whole family already ran on exactly these bytes).
    """

    def family_record_for_the_current_tree(self):
        written = core_unit.write_record(
            self.project, _run([]), core_unit.tree_fingerprint(self.project)
        )
        return written

    def test_legacy_cycle_with_source_change_and_declared_none_refuses(self):
        self.change_source()
        result = self.declare("none")  # the only oracle -- a claim
        self.assertTrue(result.ok, result.to_dict())
        self.focused_record()
        self.assertTrue(self.to("REVIEW").ok)
        refused = self.to("SHIP")
        self.assertFalse(refused.ok, refused.to_dict())
        self.assertIn("no measured tree identity", refused.message)
        self.assertIn("Campaign VIII", refused.message)
        self.assertIn("focused", refused.message)

    def test_legacy_cycle_with_omitted_declaration_and_source_change_refuses(self):
        self.change_source()
        self.assertTrue(self.to("VERIFY").ok)
        self.focused_record()
        self.assertTrue(self.to("REVIEW").ok)
        refused = self.to("SHIP")
        self.assertFalse(refused.ok, refused.to_dict())
        self.assertIn("no measured tree identity", refused.message)

    def test_legacy_cycle_without_change_still_needs_a_proof(self):
        # Outcome D: a missing measurement never authorizes the corridor,
        # even for an honestly unchanged tree -- the proof, not hope, opens it.
        result = self.declare("none")
        self.assertTrue(result.ok, result.to_dict())
        self.focused_record()
        self.assertTrue(self.to("REVIEW").ok)
        refused = self.to("SHIP")
        self.assertFalse(refused.ok, refused.to_dict())
        self.assertIn("no measured tree identity", refused.message)

    def test_legacy_cycle_with_a_current_tree_family_record_takes_the_corridor(self):
        # Outcome C: the independent no-delta proof -- a full-family record
        # OF THE CURRENT TREE -- opens the corridor for a legacy cycle.
        result = self.declare("none")
        self.assertTrue(result.ok, result.to_dict())
        self.family_record_for_the_current_tree()
        self.focused_record()
        self.assertTrue(self.to("REVIEW").ok)
        allowed = self.to("SHIP")
        self.assertTrue(allowed.ok, allowed.to_dict())

    def test_a_family_record_of_a_different_tree_is_no_proof(self):
        # The proof must match TODAY's bytes: a stale record of an older
        # tree leaves the legacy corridor closed.
        result = self.declare("none")
        self.assertTrue(result.ok, result.to_dict())
        stale = core_unit.write_record(
            self.project, _run([]), "0123456789abcdef" + "0" * 48
        )
        self.assertTrue(stale["path"])
        self.focused_record()
        self.assertTrue(self.to("REVIEW").ok)
        refused = self.to("SHIP")
        self.assertFalse(refused.ok, refused.to_dict())
        self.assertIn("no measured tree identity", refused.message)


if __name__ == "__main__":
    unittest.main()
