"""T-37: `own_patch` cannot close a BUILD that recorded no implementation delta.

Measured live on this repository (vacterro-saiwebsite improve 20261013-1
IMP-002 vocabulary): a throwaway project ran the canonical lifecycle with a
BUILD record that said `implementation_delta none: ...` and then closed
FINISHED under `--closure-mode own_patch` -- the default mode -- with no
refusal of any kind. The closure asserted an implementation patch the BUILD
itself says does not exist, which is the weakest provenance the engine can
write.

The BUILD record is machine grammar inside the LOG, so the gate reads it
rather than trusting the declared mode, and the refusal names the two modes
that actually fit a no-delta closure so the corrected command is one line
away (T-1377's rule).

Implementation in saipen_engine/operations.py: `no_delta_build_events` + one
guard in `_plan_finish_ticket`.

Run standalone:
    python tools/test_vacterro_t37_no_delta_closure.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import operations as _ops  # noqa: E402

finish_ticket = _ops.finish_ticket
no_delta_build_events = getattr(_ops, "no_delta_build_events", None)
from test_public_closure_cli import _with_published_release  # noqa: E402
from test_orchestration_repair import (  # noqa: E402
    OrchestrationFixture,
)


def _finish_project(case: unittest.TestCase, build_text: str, ticket: str = "T-7") -> Path:
    """A SHIP-ready project whose LOG carries exactly one BUILD record."""
    project = case.make_project(phase="SHIP", active=True)
    (project / ".saipen" / "STATE.md").write_text(
        (project / ".saipen" / "STATE.md")
        .read_text(encoding="utf-8")
        .replace("task: T-7", f"task: {ticket}", 1)
        .replace("transition_from: SCOUT", "transition_from: REVIEW", 1),
        encoding="utf-8",
    )
    (project / ".saipen" / "BOARD.md").write_text(
        f"## DOING\n- [/] {ticket} [P1] Existing Work | verify: existing proof | "
        f"owner: tester | claim_time: 2026-10-14T00:00:00Z\n"
        f"## TODO\n## DONE\n## BLOCKED\n",
        encoding="utf-8",
    )
    (project / ".saipen" / "LOG.md").write_text(
        "- 24.08.26 00:00 [E-001] [agent: tester] RUN: fixture -> start\n"
        f"- 24.08.26 00:01 [E-002] [{ticket}] [agent: tester] {build_text}\n"
        f"- 24.08.26 00:02 [E-003] [{ticket}] [agent: tester] RUN: transition to VERIFY\n"
        f"- 24.08.26 00:03 [E-004] [{ticket}] [agent: tester] RUN: verify -> PASS "
        f"[target: {ticket}] conf: high -- hermetic suite green\n"
        "- 24.08.26 00:04 [E-005] [agent: tester] RUN: transition to SHIP\n",
        encoding="utf-8",
    )
    return project


class NoDeltaClosure(OrchestrationFixture):
    def _run(self, project: Path, ticket: str, **kwargs):
        return finish_ticket(project, ticket, "tester", **kwargs)

    def test_the_no_delta_build_record_is_found(self) -> None:
        if no_delta_build_events is None:
            self.fail("saipen_engine.operations exposes no no_delta_build_events")
        events = [
            {"ticket": "T-7", "text": "RUN: build -> implementation_delta none: nothing changed"},
            {"ticket": "T-8", "text": "RUN: build -> implementation_delta none: another ticket"},
            {"ticket": "T-7", "text": "RUN: build -> src/app.ts and tests/app.test.ts changed"},
        ]
        found = no_delta_build_events("T-7", events)
        self.assertEqual(len(found), 1)
        self.assertIn("implementation_delta none", found[0]["text"])
        self.assertEqual(no_delta_build_events("T-9", events), [])

    def test_own_patch_refuses_a_no_delta_build_and_names_the_alternates(self) -> None:
        project = _finish_project(
            self, "RUN: build -> implementation_delta none: nothing changed here"
        )
        result = self._run(project, "T-7", closure_mode="own_patch")
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "VALIDATION_FAILED")
        self.assertIn("inherited_verified", result.message)
        self.assertIn("--implementation-source", result.message)
        self.assertIn("cohort", result.message)
        self.assertIn("--closure-cohort", result.message)
        # Zero-write: the board keeps the ticket exactly where it was.
        self.assertIn("[/] T-7", (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))

    def test_a_real_delta_build_still_closes_own_patch(self) -> None:
        project = _finish_project(self, "RUN: build -> src/app.ts and tests/app.test.ts changed")
        result = self._run(project, "T-7", closure_mode="own_patch")
        self.assertTrue(result.ok, getattr(result, "message", result.data))
        self.assertIn("[x] T-7", (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))

    def test_the_no_delta_ticket_closes_through_the_named_alternate(self) -> None:
        project = _finish_project(
            self, "RUN: build -> implementation_delta none: nothing changed here"
        )
        authority = _with_published_release(project)
        result = self._run(
            project, "T-7", closure_mode="inherited_verified", implementation_source=authority
        )
        self.assertTrue(result.ok, getattr(result, "message", result.data))


if __name__ == "__main__":
    unittest.main()
