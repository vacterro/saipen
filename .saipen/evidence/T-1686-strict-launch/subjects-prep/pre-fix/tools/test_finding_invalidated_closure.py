"""T-406: a ticket whose PREMISE was disproven needs a closure verb.

The vocabulary had no member for that shape. `own_patch` asserts a patch that
does not exist, `inherited_verified` demands committed release evidence naming
a ticket that published the behaviour, `external_implementation` records an
implementation living in another repository. When a finding opened a ticket
and later measurement disproved it -- measured here on this very repository's
own CORE-001 channel -- every honest closure was a lie and the ticket parked
forever with no route forward.

`finding_invalidated` is that member. It is falsifiable rather than permissive:
the closure must name the E-### event that disproved the premise, and that
event must belong to THIS ticket's own LOG chain.

These tests drive the REAL `finish_ticket`, not the helpers, because the
grammar check and the LOG-history gate are separate owners and proving either
one in isolation is how a gap like this gets written in the first place.

The gate is deliberately structural. A stronger check -- matching the word
`INVALID` in the cited event -- would read free text for a magic phrase, which
is the Narrative Authority Leakage `log.py` documents at length. There is a
test here that pins that decision: prose alone never closes the ticket.
"""

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.board import CLOSURE_MODES, parse_board  # noqa: E402
from saipen_engine.journal import ensure_project_lineage  # noqa: E402
from saipen_engine.operations import (  # noqa: E402
    closure_request_error,
    finish_ticket,
    invalidation_error,
)
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402

SAIPEN_HOME = ROOT
SAIPEN_PY = TOOLS / "saipen.py"


def _build(base: Path) -> Path:
    """A DOING ticket whose own DEC checkpoint already records the disproof."""
    project = base / "project"
    (project / ".saipen").mkdir(parents=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (project / ".saipen" / "STATE.md").write_text(
        "---\n"
        "phase: SHIP\n"
        "task: T-7\n"
        'next_action: "PHASE SHIP T-7"\n'
        'blocker: ""\n'
        "transition_from: REVIEW\n"
        "saipen_version: 7\n"
        "schema_version: 3\n"
        "last_event: 2\n"
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
        f"## DOING\n- [/] T-7 [P1] Premise later disproven | verify: falsifiable "
        f"claim that measurement refuted | owner: tester | claim_time: {now}\n"
        "## TODO\n## DONE\n## BLOCKED\n",
        encoding="utf-8",
    )
    # E-001 belongs to T-7 and records the disproof. E-002 belongs to T-9 and
    # must never be able to close T-7. E-003/E-004 are the VERIFY boundary the
    # closure gate demands of every mode -- `finding_invalidated` relaxes
    # PROVENANCE, not the phase and evidence gates.
    (project / ".saipen" / "LOG.md").write_text(
        "- 24.08.26 00:00 [E-001] [T-7] [agent: tester] DEC: premise disproven "
        "at HEAD\n"
        "- 24.08.26 00:01 [E-002] [T-9] [agent: tester] DEC: unrelated checkpoint\n"
        "- 24.08.26 00:02 [E-003] [parent: E-002] [T-7] [agent: tester] "
        "[op: transition-d29438dce1ad4d98a76f08af115c4740] "
        "RUN: transition to VERIFY\n"
        "- 24.08.26 00:03 [E-004] [parent: E-003] [T-7] [agent: tester] "
        "[op: checkpoint-93c984bfcb1246e5a019cf7db28c5db7] "
        "RUN: PASS -- the vocabulary already exists at HEAD and this ticket's "
        "premise is therefore refuted; conf: high\n",
        encoding="utf-8",
    )
    ensure_project_lineage(project)
    return project


def _fields(project: Path, ticket_id: str = "T-7") -> dict:
    board = parse_board((project / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))
    return board["tickets"][ticket_id]["fields"]


class GrammarTests(unittest.TestCase):
    def test_the_mode_is_registered(self):
        self.assertIn("finding_invalidated", CLOSURE_MODES)

    def test_the_mode_requires_named_evidence(self):
        why = closure_request_error("finding_invalidated", None, None, None)
        self.assertIsNotNone(why)
        self.assertIn("--invalidated-by", why)

    def test_evidence_is_refused_with_every_other_mode(self):
        for mode in ("own_patch", "inherited_verified", "cohort"):
            why = closure_request_error(mode, None, None, None, "E-001")
            self.assertIsNotNone(why, f"{mode} accepted invalidation evidence")
            self.assertIn("finding_invalidated", why)

    def test_malformed_evidence_is_refused(self):
        why = closure_request_error("finding_invalidated", None, None, None, "not-an-event")
        self.assertIsNotNone(why)
        self.assertIn("E-###", why)


_SCOPE_EVENTS = [
    {"event": 1, "ticket": "T-7", "taxonomy": "DEC", "text": "anything at all"},
    {"event": 2, "ticket": "T-9", "taxonomy": "DEC", "text": "a stranger's event"},
]


class EvidenceScopeTests(unittest.TestCase):
    """The gate is STRUCTURAL. Prose is never authority."""

    def test_own_event_is_admissible(self):
        self.assertIsNone(invalidation_error(_SCOPE_EVENTS, "E-1", ticket_id="T-7"))

    def test_a_strangers_event_is_refused(self):
        why = invalidation_error(_SCOPE_EVENTS, "E-2", ticket_id="T-7")
        self.assertIsNotNone(why)
        self.assertIn("T-9", why)

    def test_an_absent_event_is_refused(self):
        self.assertIsNotNone(invalidation_error(_SCOPE_EVENTS, "E-99", ticket_id="T-7"))

    def test_event_text_is_never_matched(self):
        """Prose cannot decide this. Only identity can."""
        # An event that SHOUTS about invalidity is still only admissible for
        # its own ticket -- and one that says nothing is admissible for its
        # own. That is the whole design.
        events = [{"event": 5, "ticket": "T-7", "taxonomy": "DEC", "text": "PASS -- fine"}]
        self.assertIsNone(invalidation_error(events, "E-5", ticket_id="T-7"))


class FinishTests(unittest.TestCase):
    """Drive the REAL closure, so grammar and LOG history both have to agree."""

    def setUp(self):
        base = Path(tempfile.mkdtemp(prefix="t406-invalidated-"))
        self.addCleanup(lambda: shutil.rmtree(base, ignore_errors=True))
        self.project = _build(base)

    def _finish(self, **kwargs):
        return finish_ticket(self.project, "T-7", "tester", **kwargs)

    def test_a_premise_disproof_closes_the_ticket(self):
        result = self._finish(
            closure_mode="finding_invalidated", invalidation_evidence="E-1"
        )
        self.assertTrue(result.ok, result.to_dict())
        fields = _fields(self.project)
        self.assertEqual(fields.get("closure_mode"), "finding_invalidated")
        self.assertEqual(fields.get("implementation_delta"), "none")
        self.assertEqual(fields.get("invalidation_evidence"), "E-1")

    def test_a_strangers_event_cannot_close_it(self):
        result = self._finish(
            closure_mode="finding_invalidated", invalidation_evidence="E-2"
        )
        self.assertFalse(result.ok)
        self.assertIn("T-9", result.to_dict()["message"])

    def test_an_unnamed_disproof_is_refused(self):
        result = self._finish(closure_mode="finding_invalidated")
        self.assertFalse(result.ok)
        self.assertIn("--invalidated-by", result.to_dict()["message"])

    def test_the_ticket_is_still_doing_after_every_refusal(self):
        self._finish(closure_mode="finding_invalidated", invalidation_evidence="E-2")
        board = parse_board(
            (self.project / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        )
        self.assertEqual(board["tickets"]["T-7"]["section"], "## DOING")
        self.assertNotIn("closure_mode", board["tickets"]["T-7"]["fields"])


class PublicCliTests(unittest.TestCase):
    """The flag an operator actually types has to exist.

    Everything above drives the engine in-process. That cannot see a flag
    missing from the parser, renamed in the option table, or dropped between
    dispatch and the closure call -- the seam where this feature is most
    likely to be half-wired and still green.
    """

    def setUp(self):
        base = Path(tempfile.mkdtemp(prefix="t406-cli-"))
        self.addCleanup(lambda: shutil.rmtree(base, ignore_errors=True))
        self.project = _build(base)

    def _run(self, *args):
        proc = subprocess.run(
            [
                sys.executable,
                str(SAIPEN_PY),
                "--project-root",
                str(self.project),
                "--agent",
                "tester",
                "--json",
                *args,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
            timeout=180,
        )
        try:
            return proc.returncode, json.loads(proc.stdout) if proc.stdout.strip() else {}
        except ValueError:
            return proc.returncode, {"_unparseable_stdout": proc.stdout}

    def test_the_flag_is_wired_into_the_parser_table(self):
        from saipen import _TICKET_DONE_OPTIONS

        self.assertEqual(
            _TICKET_DONE_OPTIONS.get("--invalidated-by"), "invalidation_evidence"
        )

    def test_the_cli_closes_the_ticket_on_a_named_disproof(self):
        rc, payload = self._run(
            "ticket", "done", "T-7",
            "--closure-mode", "finding_invalidated",
            "--invalidated-by", "E-001",
        )
        self.assertEqual(rc, 0, payload)
        self.assertTrue(payload.get("ok"), payload)
        fields = _fields(self.project)
        self.assertEqual(fields.get("closure_mode"), "finding_invalidated")
        self.assertEqual(fields.get("invalidation_evidence"), "E-001")

    def test_the_cli_refuses_a_strangers_event(self):
        rc, payload = self._run(
            "ticket", "done", "T-7",
            "--closure-mode", "finding_invalidated",
            "--invalidated-by", "E-002",
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("T-9", payload.get("message", ""))

    def test_the_cli_refuses_the_mode_without_evidence(self):
        rc, payload = self._run(
            "ticket", "done", "T-7",
            "--closure-mode", "finding_invalidated",
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("--invalidated-by", payload.get("message", ""))


class BoardValidationTests(unittest.TestCase):
    """The DONE line must stay self-consistent however it was written."""

    def _fields(self, body: str) -> dict:
        board = parse_board(f"## DONE\n{body}\n## BLOCKED\n")
        return board["tickets"]["T-7"]["fields"]

    def test_invalidation_evidence_needs_the_mode(self):
        from saipen_engine.board import closure_metadata_errors

        ticket = {
            "id": "T-7",
            "section": "## DONE",
            "fields": self._fields(
                "- [x] T-7 [P1] t | verify: v | closure_mode: own_patch | "
                "invalidation_evidence: E-1"
            ),
        }
        self.assertTrue(closure_metadata_errors(ticket))

    def test_the_mode_needs_the_evidence(self):
        from saipen_engine.board import closure_metadata_errors

        ticket = {
            "id": "T-7",
            "section": "## DONE",
            "fields": self._fields(
                "- [x] T-7 [P1] t | verify: v | closure_mode: finding_invalidated"
            ),
        }
        self.assertTrue(closure_metadata_errors(ticket))

    def test_the_pair_together_validates(self):
        from saipen_engine.board import closure_metadata_errors

        ticket = {
            "id": "T-7",
            "section": "## DONE",
            "fields": self._fields(
                "- [x] T-7 [P1] t | verify: v | closure_mode: finding_invalidated | "
                "implementation_delta: none | invalidation_evidence: E-1"
            ),
        }
        self.assertEqual(closure_metadata_errors(ticket), [])

    def test_a_malformed_evidence_value_is_refused(self):
        from saipen_engine.board import closure_metadata_errors

        ticket = {
            "id": "T-7",
            "section": "## DONE",
            "fields": self._fields(
                "- [x] T-7 [P1] t | verify: v | closure_mode: finding_invalidated | "
                "invalidation_evidence: yesterday"
            ),
        }
        self.assertTrue(closure_metadata_errors(ticket))


if __name__ == "__main__":
    unittest.main()