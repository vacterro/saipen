"""T-1781: own_patch closure reads the ticket's LATEST BUILD record.

The foreign T-37 guard (adopted here) refuses `--closure-mode own_patch` when
a BUILD record declared `implementation_delta none`. It read every BUILD
record of the ticket, so a ticket whose first BUILD found nothing to change
and whose later BUILD carried a real patch could never close as its own
patch. The latest BUILD record is the claim the closure makes.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.operations import finish_ticket  # noqa: E402
from test_orchestration_repair import OrchestrationFixture  # noqa: E402

NO_DELTA = "RUN: build -> implementation_delta none: investigated, nothing to change"
PATCH = "RUN: build -> src/app.ts and tests/app.test.ts changed"


def _project(case: OrchestrationFixture, *builds: str) -> Path:
    """A SHIP-ready project whose LOG carries the given BUILD records in order."""
    project = case.make_project(phase="SHIP", active=True)
    state = project / ".saipen" / "STATE.md"
    state.write_text(
        state.read_text(encoding="utf-8").replace(
            "transition_from: SCOUT", "transition_from: REVIEW", 1
        ),
        encoding="utf-8",
    )
    (project / ".saipen" / "BOARD.md").write_text(
        "## DOING\n- [/] T-7 [P1] Existing Work | verify: existing proof | "
        "owner: tester | claim_time: 2026-10-14T00:00:00Z\n## TODO\n## DONE\n## BLOCKED\n",
        encoding="utf-8",
    )
    lines = ["- 24.08.26 00:00 [E-001] [agent: tester] RUN: fixture -> start"]
    event = 1
    for text in builds:
        event += 1
        lines.append(f"- 24.08.26 00:{event:02d} [E-{event:03d}] [T-7] [agent: tester] {text}")
    for text in (
        "RUN: transition to VERIFY",
        "RUN: verify -> PASS [target: T-7] conf: high -- hermetic suite green",
    ):
        event += 1
        lines.append(f"- 24.08.26 00:{event:02d} [E-{event:03d}] [T-7] [agent: tester] {text}")
    event += 1
    lines.append(
        f"- 24.08.26 00:{event:02d} [E-{event:03d}] [agent: tester] RUN: transition to SHIP"
    )
    (project / ".saipen" / "LOG.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return project


class LatestBuildDecides(OrchestrationFixture):
    def test_a_later_patch_build_closes_as_its_own_patch(self) -> None:
        project = _project(self, NO_DELTA, PATCH)
        result = finish_ticket(project, "T-7", "tester", closure_mode="own_patch")
        self.assertTrue(result.ok, getattr(result, "message", result.data))
        self.assertIn("[x] T-7", (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))

    def test_a_later_no_delta_build_still_refuses_own_patch(self) -> None:
        project = _project(self, PATCH, NO_DELTA)
        result = finish_ticket(project, "T-7", "tester", closure_mode="own_patch")
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "VALIDATION_FAILED")
        self.assertIn("implementation_delta none", result.message)
        self.assertIn("[/] T-7", (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
