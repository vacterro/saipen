"""T-405: `ticket verify` must not destroy the clause it supersedes.

The verify field is a ticket's falsifiable acceptance surface. `ticket_verify`
replaces it in place, so before T-405 the previous clause existed nowhere in
the project the moment the verb returned: the BOARD held only the new text and
the DEC event carried a constant string. Nothing in SAIPEN could answer "what
did this ticket claim before the rewrite", which is the question every falsifiable
clause exists to make checkable.

These tests drive the REAL mutator against a real project tree. The property
under test is deliberately a whole-tree property -- "the clause is recoverable
from SAIPEN alone" -- because a fix that preserved it somewhere an operator
would never look would not be a fix.

The red control: restoring the constant message at the `_event_line` call in
`operations.ticket_verify` fails `test_superseded_clause_is_recoverable` with
zero survivors. Measured on the pre-fix bytes -- survivors: [].
"""

import datetime as dt
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.journal import ensure_project_lineage  # noqa: E402
from saipen_engine.operations import ticket_verify  # noqa: E402
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402

SAIPEN_HOME = ROOT

FIRST = "SENTINEL_ALPHA the pre-fix subject produced the documented refusal"
SECOND = "SENTINEL_BETA the post-fix subject satisfies the same oracle"


def _build(base: Path, verify: str) -> Path:
    """A minimal but VALID project: STATE, BOARD, LOG, lineage."""
    project = base / "project"
    (project / ".saipen").mkdir(parents=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (project / ".saipen" / "STATE.md").write_text(
        "---\n"
        "phase: BUILD\n"
        "task: T-7\n"
        'next_action: "PHASE BUILD T-7"\n'
        'blocker: ""\n'
        "transition_from: SCOUT\n"
        "saipen_version: 7\n"
        "schema_version: 3\n"
        "last_event: 1\n"
        "style_contract: " + CURRENT_STYLE_CONTRACT + "\n"
        f'saipen_home: "{SAIPEN_HOME}"\n'
        "agent: tester\n"
        "requires:\n  - filesystem\n  - python\n"
        "mode: full\n"
        f'updated: "{now}"\n'
        "execution_intent: goal\n"
        "goal_waves: 1\n"
        "goal_tickets: 0\n"
        "---\n",
        encoding="utf-8",
    )
    (project / ".saipen" / "BOARD.md").write_text(
        f"## DOING\n- [/] T-7 [P1] Existing Work | verify: {verify} | "
        f"owner: tester | claim_time: {now}\n"
        "## TODO\n## DONE\n## BLOCKED\n",
        encoding="utf-8",
    )
    (project / ".saipen" / "LOG.md").write_text(
        "- 24.08.26 00:00 [E-001] [T-7] [agent: tester] RUN: fixture -> PASS\n",
        encoding="utf-8",
    )
    ensure_project_lineage(project)
    return project


def _recoverable_from(project: Path, needle: str) -> list[str]:
    """Every project-relative file whose bytes still carry `needle`."""
    hits = []
    for path in sorted(project.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if needle in text:
            hits.append(str(path.relative_to(project)).replace("\\", "/"))
    return hits


class TicketVerifyPreimageTests(unittest.TestCase):
    def setUp(self):
        base = Path(tempfile.mkdtemp(prefix="t405-preimage-"))
        self.addCleanup(lambda: shutil.rmtree(base, ignore_errors=True))
        self.base = base

    def _rewrite(self, prior: str, new: str):
        project = _build(self.base / prior[:12].replace("SENTINEL_", "s"), prior)
        result = ticket_verify(project, "T-7", "tester", new)
        self.assertTrue(result.ok, result.to_dict())
        return project

    def test_superseded_clause_is_recoverable(self):
        """The core property: the old clause survives the rewrite somewhere."""
        project = self._rewrite(FIRST, SECOND)
        survivors = _recoverable_from(project, FIRST)
        self.assertTrue(
            survivors,
            "the superseded verify clause was destroyed by ticket_verify; "
            "no file in the project still carries it",
        )
        # It must be durable history, not a scratch artifact of a pending op.
        self.assertIn(".saipen/LOG.md", survivors)

    def test_oversized_superseded_clause_is_preserved(self):
        """Preservation must not depend on the clause being short.

        The bounded producer externalizes an oversized event into a journaled
        detail artifact. The clause is still recoverable -- from a different
        file -- which is why the assertion is a tree search and not a grep of
        LOG.md alone.
        """
        long_prior = "SENTINEL_GAMMA " + ("falsifiable clause text " * 400)
        project = _build(self.base / "oversized", long_prior)
        result = ticket_verify(project, "T-7", "tester", SECOND)
        self.assertTrue(result.ok, result.to_dict())
        survivors = _recoverable_from(project, "SENTINEL_GAMMA")
        self.assertTrue(survivors, "an oversized clause was destroyed")

    def test_first_verify_keeps_the_constant_event(self):
        """No prior clause means nothing to preserve, and nothing is invented."""
        project = _build(self.base / "first", "")
        result = ticket_verify(project, "T-7", "tester", FIRST)
        self.assertTrue(result.ok, result.to_dict())
        log = (project / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("ticket verify updated via SAIOPS", log)
        self.assertNotIn("superseded clause", log)


if __name__ == "__main__":
    unittest.main()