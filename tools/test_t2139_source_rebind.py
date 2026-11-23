"""T-2139 (ZAICODE audit findings B/C): rebind + recover diagnostic shape.

Measured on _ZAICODE: the BOARD rows T-435/T-444/T-500 are gone with zero
scrub copies, so `source recover` answers ROWS_UNRECOVERABLE (finding B) and
the receipts' primary Work (T-444 under SRC-329) can never finish where it
is; the audit's proposed minimal change 2 adds the authorized primary
re-point, `saipen source rebind <SRC-###> --work <T-###> --reason CODE
--authority <SRC-###>`. These controls hold that land:

  primary moves            rebind re-points linked_work to a live target and
                           records previous/reason/authority/timestamp
  membership preserved     the old primary stays in linked_works
  coverage untouched       the coverage bytes do not change across a rebind
  no-op refused            re-binding the current primary answers REBIND_NOOP
                           with zero writes
  unknown/DONE target      a pruned or finished target cannot carry the receipt
  authority required       an unknown authority receipt refuses the move
  reason required          a reason token is mandatory

Run standalone:
    python tools/test_t2139_source_rebind.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import intake  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from test_dependency_resume_liveness import ResumeFixture  # noqa: E402

BODY = (
    "# User request\n\n"
    "priority: P1\n"
    "verify: the primary re-bind is canonical\n\n"
    "## Request\n\n"
    "the recorded primary row is gone; re-point the receipt to a live owner\n"
)


class RebindTests(ResumeFixture):
    def capture(self, project: Path, work: str) -> str:
        captured = intake.capture(
            project, BODY, source_kind="user_instruction", work=work
        )
        self.assertTrue(captured.get("ok"), captured)
        self.assertEqual(captured.get("linked_work"), work, captured)
        return captured["receipt"]

    def meta(self, project: Path, receipt: str) -> dict:
        return intake._read_meta(project, receipt) or {}

    def meta_bytes(self, project: Path, receipt: str) -> bytes:
        return (project / ".saipen" / "intake" / "active" / f"{receipt}.meta.json").read_bytes()

    def coverage_bytes(self, project: Path, receipt: str) -> bytes:
        return (project / ".saipen" / "intake" / "coverage" / f"{receipt}.json").read_bytes()

    def rebind(self, project: Path, receipt: str, work: str, **kwargs) -> dict:
        return intake.rebind_work_to(
            project,
            receipt,
            work,
            reason=kwargs.pop("reason", "PRIMARY_ROW_LOST"),
            authority=kwargs.pop("authority", receipt),
            **kwargs,
        )

    def move_to_done(self, project: Path, work: str) -> None:
        board = (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        parsed = parse_board(board)
        fresh = self.rebuild_board(parsed, done_ids={work})
        (project / ".saipen" / "BOARD.md").write_text(fresh, encoding="utf-8")

    def rebuild_board(self, parsed: dict, done_ids: set[str]) -> str:
        sections = {"## DOING": [], "## TODO": [], "## DONE": [], "## BLOCKED": []}
        for tid, ticket in parsed["tickets"].items():
            line = str(ticket["raw"] or "").strip()
            key = ticket["section"]
            if tid in done_ids:
                key = "## DONE"
                if line.startswith("- [ ]"):
                    line = line.replace("- [ ]", "- [x]", 1)
            sections.setdefault(key, []).append(line)
        out = []
        for header in ("## DOING", "## TODO", "## DONE", "## BLOCKED"):
            out.append(header)
            out.extend(sections.get(header, []))
        return "\n".join(out) + "\n"

    # -- the controls ---------------------------------------------------

    def test_rebind_moves_primary_and_records_provenance(self) -> None:
        project = self.make_project()
        a = self.add(project, "lost row owner")
        b = self.add(project, "live new owner")
        receipt = self.capture(project, a)
        coverage_before = self.coverage_bytes(project, receipt)

        result = self.rebind(project, receipt, b, reason="PRIMARY_ROW_LOST")

        self.assertTrue(result.get("ok"), result)
        self.assertEqual(result.get("code"), "SOURCE_REBOUND")
        self.assertEqual(result.get("previous_linked_work"), a)
        self.assertEqual(result.get("linked_work"), b)
        record = self.meta(project, receipt)
        self.assertEqual(record["linked_work"], b)
        self.assertEqual(
            set(record["linked_works"]), {a, b}, "the old primary stays a member"
        )
        self.assertEqual(record["previous_linked_work"], a)
        history = record["rebinds"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["from"], a)
        self.assertEqual(history[0]["to"], b)
        self.assertEqual(history[0]["reason"], "PRIMARY_ROW_LOST")
        self.assertTrue(history[0]["at"])
        self.assertTrue(history[0]["op_id"].startswith("source-rebind-"))
        index = intake._read_index(project)
        entry = index["active"][receipt]
        self.assertEqual(entry["linked_work"], b)
        self.assertEqual(set(entry["linked_works"]), {a, b})
        self.assertEqual(
            self.coverage_bytes(project, receipt),
            coverage_before,
            "a rebind never rewrites clause coverage",
        )

    def test_rebind_noop_refuses_without_a_trace(self) -> None:
        project = self.make_project()
        a = self.add(project, "the only owner")
        receipt = self.capture(project, a)
        before = self.meta_bytes(project, receipt)

        result = intake.rebind_work_to(
            project, receipt, a, reason="PRIMARY_ROW_LOST", authority=receipt
        )

        self.assertFalse(result.get("ok"), result)
        self.assertEqual(result.get("code"), "REBIND_NOOP")
        self.assertEqual(self.meta_bytes(project, receipt), before)

    def test_rebind_unknown_target_refuses(self) -> None:
        project = self.make_project()
        a = self.add(project, "the only owner")
        receipt = self.capture(project, a)
        before = self.meta_bytes(project, receipt)

        result = self.rebind(project, receipt, "T-999")

        self.assertFalse(result.get("ok"), result)
        self.assertEqual(result.get("code"), "ORPHAN_RECEIPT")
        self.assertIn("missing from BOARD", result["detail"])
        self.assertEqual(self.meta_bytes(project, receipt), before)

    def test_rebind_finished_target_refuses(self) -> None:
        project = self.make_project()
        a = self.add(project, "the only owner")
        b = self.add(project, "already finished owner")
        receipt = self.capture(project, a)
        before = self.meta_bytes(project, receipt)
        self.move_to_done(project, b)
        parsed = parse_board((project / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))
        self.assertEqual(parsed["tickets"][b]["section"], "## DONE")

        result = self.rebind(project, receipt, b)

        self.assertFalse(result.get("ok"), result)
        self.assertEqual(result.get("code"), "ORPHAN_RECEIPT")
        self.assertIn("not workable", result["detail"])
        self.assertEqual(self.meta_bytes(project, receipt), before)

    def test_rebind_missing_authority_refuses(self) -> None:
        project = self.make_project()
        a = self.add(project, "lost row owner")
        b = self.add(project, "live new owner")
        receipt = self.capture(project, a)
        before = self.meta_bytes(project, receipt)

        fake = "SRC-999"
        self.assertIsNone(intake._read_meta(project, fake))
        result = self.rebind(project, receipt, b, authority=fake)

        self.assertFalse(result.get("ok"), result)
        self.assertEqual(result.get("code"), "SOURCE_RECEIPT_MISSING")
        self.assertIn(fake, result["detail"])
        self.assertEqual(self.meta_bytes(project, receipt), before)

    def test_rebind_requires_a_reason_token(self) -> None:
        project = self.make_project()
        a = self.add(project, "lost row owner")
        b = self.add(project, "live new owner")
        receipt = self.capture(project, a)
        before = self.meta_bytes(project, receipt)

        for bad in ("", "because I said so", "lowercase"):
            result = intake.rebind_work_to(
                project, receipt, b, reason=bad, authority=receipt
            )
            self.assertFalse(result.get("ok"), bad)
            self.assertEqual(result.get("code"), "VALIDATION_FAILED", bad)
        self.assertEqual(self.meta_bytes(project, receipt), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
