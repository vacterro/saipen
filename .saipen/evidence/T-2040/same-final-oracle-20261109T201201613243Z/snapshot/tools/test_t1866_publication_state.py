"""T-1866: an `own_patch` DONE must STATE its publication truth.

SRC-295 F-03, measured on another project's session: `saipen ticket done T-251
--closure-mode own_patch` answered FINISHED, and fifteen minutes later
`git status --short` still listed the modified implementation files. The
closure had asserted an implementation patch the repository did not hold as
published work, and nothing on the DONE line said so.

The engine already refuses the OPPOSITE lie (T-37: `own_patch` on a BUILD that
recorded `implementation_delta none`) and already refuses to INHERIT an
unpublished DONE as publication authority (closure.resolve_implementation_source:
"DONE is an evidence claim, never proof of publication"). What was missing is
the one fact a reader of the DONE line cannot otherwise see: is this ticket's
delta PUBLISHED, or is it still waiting for a release?

Design note, because the obvious stricter gate is the wrong repair: making
`own_patch` REFUSE until a release names the ticket would fail closed on every
ordinary ticket whenever publication is blocked for reasons the ticket does not
own (this repository has 206 foreign staged paths sitting in the shared index
today). That converts an evidence defect into an operator obligation -- every
ticket would need a human to stage and release before it could close. The
repair is therefore to RECORD the truth on the closure, derived mechanically
from committed release evidence, never inferred from prose, and to keep the
downstream refusal (an unpublished DONE is not publication authority) exactly
as strict as it already is.

Run standalone:
    python -B tools/test_t1866_publication_state.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import closure as _closure  # noqa: E402
from saipen_engine.operations import finish_ticket  # noqa: E402
from test_orchestration_repair import OrchestrationFixture  # noqa: E402
from test_public_closure_cli import _with_published_release  # noqa: E402

PATCH = "RUN: build -> src/app.ts and tests/app.test.ts changed"
NO_DELTA = "RUN: build -> implementation_delta none: investigated, nothing to change"


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
        "RUN: transition to SHIP",
    ):
        event += 1
        lines.append(f"- 24.08.26 00:{event:02d} [E-{event:03d}] [T-7] [agent: tester] {text}")
    (project / ".saipen" / "LOG.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return project


def _done_row(project: Path) -> str:
    board = (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
    for line in board.splitlines():
        if line.startswith("- [x] T-7"):
            return line
    raise AssertionError("T-7 is not on a DONE line:\n" + board)


class OwnPatchStatesItsPublicationTruth(OrchestrationFixture):
    def test_an_unpublished_own_patch_closure_says_pending(self) -> None:
        """The F-03 shape: the delta is real, the release does not exist yet."""
        project = _project(self, PATCH)
        result = finish_ticket(project, "T-7", "tester", closure_mode="own_patch")
        self.assertTrue(result.ok, getattr(result, "message", result.data))
        row = _done_row(project)
        self.assertIn("[x] T-7", row)
        self.assertIn("publication_state: pending", row)

    def test_a_published_own_patch_closure_says_published(self) -> None:
        """Publication evidence is read, not asserted: a real receipt flips it."""
        project = _project(self, PATCH)
        _with_published_release(project, "0.4.2")
        # `_with_published_release` writes a REAL receipt, but names no ticket;
        # the resolver requires the evidence to name the Work it publishes.
        receipt = project / ".saipen" / "kitchen" / "release_receipt.json"
        record = json.loads(receipt.read_text(encoding="utf-8"))
        record["ticket_id"] = "T-7"
        receipt.write_text(json.dumps(record), encoding="utf-8")
        result = finish_ticket(project, "T-7", "tester", closure_mode="own_patch")
        self.assertTrue(result.ok, getattr(result, "message", result.data))
        self.assertIn("publication_state: published", _done_row(project))

    def test_the_pending_state_names_its_own_publish_route(self) -> None:
        """A state with no route is a dead end; the route is the next canonical act."""
        project = _project(self, PATCH)
        result = finish_ticket(project, "T-7", "tester", closure_mode="own_patch")
        self.assertTrue(result.ok, getattr(result, "message", result.data))
        log = (project / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("publication_state pending", log)
        self.assertIn("saipen cohort ship", log)

    def test_pending_is_derived_from_evidence_not_from_the_request(self) -> None:
        """No caller can CLAIM published: the resolver decides, in this same run."""
        project = _project(self, PATCH)
        result = finish_ticket(project, "T-7", "tester", closure_mode="own_patch")
        self.assertTrue(result.ok, getattr(result, "message", result.data))
        verdict = _closure.resolve_implementation_source(project, "T-7")
        self.assertFalse(
            verdict.ok,
            "a pending own_patch DONE must never resolve as publication authority",
        )

    # -- the controls: what must not change -------------------------------
    def test_the_no_delta_refusal_is_untouched(self) -> None:
        """T-37 still wins: no delta at all is a false claim, not a pending one."""
        project = _project(self, NO_DELTA)
        result = finish_ticket(project, "T-7", "tester", closure_mode="own_patch")
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "VALIDATION_FAILED")
        self.assertIn("implementation_delta none", result.message)

    def test_an_inherited_closure_claims_no_patch_state(self) -> None:
        """`inherited_verified` adds no code, so it has no publication of its own."""
        project = _project(self, PATCH)
        source = _with_published_release(project)
        result = finish_ticket(
            project, "T-7", "tester",
            closure_mode="inherited_verified", implementation_source=source,
        )
        self.assertTrue(result.ok, getattr(result, "message", result.data))
        row = _done_row(project)
        self.assertNotIn("publication_state", row)


if __name__ == "__main__":
    unittest.main()
