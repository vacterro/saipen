"""T-2052: convergence stage labels project from receipt_metadata.

A canonical operation record carries its convergence stage at
``receipt_metadata.stage`` (see ``convergence._converged_receipts`` and the
stage readers around it).  ``ConvergenceVerdict.as_dict`` is the only
projection the Run-to-Closure gate reads: ``automation._latest_i_created_at``
looks for a ``stage == "I"`` row, so an empty label makes a valid E-I chain
look like a missing final I and blocks C3/C4 while the semantic verdict is
still true.

The oracle is anchored on the canonical record shape, never on a private
attribute of the projection, and it keeps the refusing half: a record without
a metadata stage must project "" and must not reach the closure gate as a
completion.
"""
from __future__ import annotations

import unittest

from saipen_engine import automation
from saipen_engine.convergence import ConvergenceVerdict

STAGES = ("E", "F", "G", "H", "I")
CREATED = "2026-11-13T11:45:14Z"
STAGE_VERDICTS = {
    "E": "PASS",
    "F": "CLEAN",
    "G": "COMPLETED",
    "H": "PASS",
    "I": "CLEAN",
}


def _record(stage: str, created: str = CREATED) -> dict:
    return {
        "receipt_metadata": {"stage": stage, "verdict": STAGE_VERDICTS[stage]},
        "op_id": f"convergence-{stage}",
        "created_at": created,
    }


class StageProjectionTests(unittest.TestCase):
    def test_canonical_metadata_stage_labels_survive_projection(self) -> None:
        verdict = ConvergenceVerdict(True, (), stages=tuple(_record(s) for s in STAGES))
        projected = verdict.as_dict()
        self.assertEqual([row["stage"] for row in projected["stages"]], list(STAGES))

    def test_projection_does_not_invent_a_missing_stage(self) -> None:
        projected = ConvergenceVerdict(True, (), stages=({"op_id": "missing"},)).as_dict()
        self.assertEqual(projected["stages"][0]["stage"], "")
        self.assertIsNone(automation._latest_i_created_at(projected))

    def test_verdict_identity_and_timestamp_are_preserved(self) -> None:
        record = _record("I")
        projected = ConvergenceVerdict(True, (), stages=(record,)).as_dict()
        self.assertTrue(projected["ok"])
        row = projected["stages"][0]
        self.assertEqual(row["stage"], "I")
        self.assertEqual(row["verdict"], "CLEAN")
        self.assertEqual(row["op_id"], record["op_id"])
        self.assertEqual(row["created_at"], CREATED)

    def test_current_chain_reaches_the_closure_gate(self) -> None:
        projected = ConvergenceVerdict(
            True, (), stages=tuple(_record(s) for s in STAGES)
        ).as_dict()
        self.assertEqual(automation._latest_i_created_at(projected), CREATED)

    def test_a_stale_chain_without_a_final_i_still_refuses(self) -> None:
        # Same tree, same receipt bytes, only the final forced-HUNT receipt is
        # gone: the gate must see no I and therefore no completed closure.
        projected = ConvergenceVerdict(
            True, (), stages=tuple(_record(s) for s in STAGES[:-1])
        ).as_dict()
        self.assertIsNone(automation._latest_i_created_at(projected))


if __name__ == "__main__":
    unittest.main()
