"""T-1358: a refusal that names no route is a dead end.

Measured live on `_PROBLIP` (lineage-1cdb1699, phase DONE, task none, agent
buffy). `reconcile._state_next_action_repairs` refuses a legacy `next_action`
whenever the phase is not ticket-bearing, and that refusal carried
`terminal_disposition: RECOVERY_BLOCKED`, which makes `_blocked_recovery_fields`
suppress the command line entirely. So `saipen recover` answered
`operator_decision_available: false` and `canonical_next_command: null`, every
phase command refused on the same field, `transition DONE -> BUILD` was
ILLEGAL, and no verb in the engine owned `next_action`. Reads worked. Nothing
else did, and nothing ever would.

Two defects, one shape:

* the refusal pre-empted the BOARD findings in the same run and reported them
  as an empty list, so the operator could not even see what else was wrong;
* the field had no operator gate at all, while `blocker` -- the field beside it
  -- has had one for exactly this reason.

`saipen recover resolve-next-action <next-action>` is that gate, built to the
same shape: the operator decides the VALUE, the engine still checks it against
the executable grammar, the original bytes are archived, and the DEC names the
field and the authority.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402

from saipen_engine.paths import identity_file_content, new_project_lineage  # noqa: E402
from saipen_engine.reconcile import reconcile_protocol_state  # noqa: E402
from test_hermetic_env import hermetic_env, isolate_host_session  # noqa: E402

HOME = TOOLS.parent


def setUpModule() -> None:
    isolate_host_session()


#: The measured field shape: phase DONE, task none, a free-text next_action.
LEGACY_NEXT_ACTION = "BOARD empty; producer packages SAIT-002 + W-002 ready - collect with eee"
STATE = (
    '---\n'
    'phase: DONE\n'
    'task: none\n'
    'next_action: "{next_action}"\n'
    'blocker: ""\n'
    'transition_from: SHIP\n'
    'saipen_version: 8\n'
    'schema_version: 3\n'
    'last_event: 45\n'
    'style_contract: ' + CURRENT_STYLE_CONTRACT + '\n'
    'saipen_home: "{home}"\n'
    'agent: buffy\n'
    'mode: full\n'
    'updated: "2026-09-15T00:00:00Z"\n'
    '---\n'
)
BOARD = "## DOING\n## TODO\n- [ ] T-9 [P1] real todo | verify: x\n## DONE\n## BLOCKED\n"
LOG = (
    "- 12.09.26 00:00 [E-44] [T-9] [agent: buffy] [op: ticket-fixture] "
    "DEC: ticket added via SAIOPS\n"
    "- 15.09.26 00:00 [E-45] [agent: buffy] RUN: ccc converge\n"
)


def project(base: Path, next_action: str = LEGACY_NEXT_ACTION) -> Path:
    root = base / "problip"
    saipen = root / ".saipen"
    saipen.mkdir(parents=True)
    (saipen / "STATE.md").write_text(
        STATE.format(next_action=next_action, home=HOME.as_posix()), encoding="utf-8"
    )
    (saipen / "BOARD.md").write_text(BOARD, encoding="utf-8")
    (saipen / "LOG.md").write_text(LOG, encoding="utf-8")
    (saipen / "IDENTITY.md").write_text(
        identity_file_content(new_project_lineage()), encoding="utf-8"
    )
    return root


class NextActionDeadlockTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t1358-")
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name).resolve()

    def cli(self, root: Path, *argv: str) -> dict:
        from test_operator_origin_support import cold_command

        env = hermetic_env()
        command = cold_command(
            root, [sys.executable, str(TOOLS / "saipen.py"), "--project-root", str(root),
                   *argv, "--json"], env,
        )
        completed = subprocess.run(
            command,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env, timeout=600,
        )
        try:
            return json.loads(completed.stdout)
        except ValueError:  # pragma: no cover - a crash is its own failure
            raise AssertionError(
                f"{argv} produced no record (rc={completed.returncode})\n"
                f"{completed.stdout[-600:]}\n{completed.stderr[-600:]}"
            ) from None

    def next_action(self, root: Path) -> str:
        for line in (root / ".saipen" / "STATE.md").read_text(encoding="utf-8").splitlines():
            if line.startswith("next_action:"):
                return line
        raise AssertionError("STATE carries no next_action")

    def test_a_projectable_legacy_next_action_is_repaired(self) -> None:
        """SRC-325 P0-002: the field no longer holds the checkpoint.

        Before T-1915 this fixture refused, because the phase is not
        ticket-bearing. The router projects `PHASE SCOUT T-9` from the same
        bytes, so the field is now repaired and the deadlock is gone. The
        refusal itself -- and the reachable route it names -- is held by
        `test_t1915_terminal_next_action.test_a_foreign_live_seat_keeps_the
        _operator_gate`, where routing genuinely cannot decide.
        """
        root = project(self.base)
        record = reconcile_protocol_state(root, "buffy", dry_run=True)
        refused = [r for r in record.get("changed", {}).get("state", []) if r.get("refuse")]
        self.assertFalse(refused, record)
        repairs = [
            r for r in record["changed"]["state"] if r.get("field") == "next_action"
        ]
        self.assertEqual(len(repairs), 1, record)
        self.assertEqual(repairs[0]["to"], "PHASE SCOUT T-9")

    def test_the_recovery_runs_without_an_operator_decision(self) -> None:
        root = project(self.base)
        record = self.cli(root, "recover")
        self.assertTrue(record.get("ok"), record)
        self.assertNotIn(LEGACY_NEXT_ACTION, self.next_action(root))
        self.assertFalse(record.get("operator_decisions"), record)

    def test_the_named_route_runs_from_the_state_that_names_it(self) -> None:
        root = project(self.base)
        from test_t1729_operator_gate import fixture_authority
        receipt = fixture_authority(root, resolve=("next_action",), next_action="saipen continue")
        repaired = self.cli(root, "recover", "resolve-next-action", receipt)
        self.assertTrue(repaired.get("ok"), repaired)
        self.assertIn('next_action: "saipen continue"', self.next_action(root))
        self.assertTrue(self.cli(root, "validate").get("ok"))

    def test_the_operator_decides_the_value_not_the_grammar(self) -> None:
        root = project(self.base)
        refused = self.cli(root, "recover", "resolve-next-action", "just", "some", "prose")
        self.assertFalse(refused.get("ok"), refused)
        self.assertIn(
            LEGACY_NEXT_ACTION,
            self.next_action(root),
            "a refused decision must leave the original value standing",
        )

    def test_the_decision_is_recorded_against_its_own_field(self) -> None:
        """The DEC used to say `STATE.blocker clear` whatever was authorized."""
        root = project(self.base)
        from test_t1729_operator_gate import fixture_authority
        receipt = fixture_authority(root, resolve=("next_action",), next_action="saipen continue")
        result = self.cli(root, "recover", "resolve-next-action", receipt)
        self.assertTrue(result["ok"], result)
        tail = (root / ".saipen" / "LOG.md").read_text(encoding="utf-8").strip().splitlines()[-1]
        self.assertIn("operator gate decision -- " + receipt, tail)
        self.assertIn("fields:next_action", tail)
        self.assertNotIn("fields:blocker", tail)

    def test_a_wait_value_with_its_separator_is_suppliable(self) -> None:
        """`WAIT: <category> -- <text>` is the canonical WAIT grammar.

        The decision loop used to stop at any token starting with two dashes,
        so the separator ended the decision and the rest of the line fell
        through as unknown arguments -- the one shape a blocked project is most
        likely to need could not be supplied at all. A bare `--` belongs to the
        decision; only a real `--flag` ends it.

        Global flags go BEFORE the decision, because that bare separator also
        ends the CLI's own flag parsing.
        """
        root = project(self.base)
        from test_t1729_operator_gate import fixture_authority
        receipt = fixture_authority(root, resolve=("next_action",),
                                    next_action="WAIT: blocked -- waiting")
        from test_operator_origin_support import cold_command

        env = hermetic_env()
        command = cold_command(
            root, [sys.executable, str(TOOLS / "saipen.py"), "--json", "--project-root", str(root),
                   "recover", "resolve-next-action", receipt], env,
        )
        completed = subprocess.run(
            command,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env, timeout=600,
        )
        record = json.loads(completed.stdout)
        self.assertTrue(record.get("ok"), record)
        self.assertIn('next_action: "WAIT: blocked -- waiting"', self.next_action(root))

    def test_an_empty_decision_refuses(self) -> None:
        root = project(self.base)
        record = self.cli(root, "recover", "resolve-next-action")
        self.assertFalse(record.get("ok"), record)
        self.assertIn(LEGACY_NEXT_ACTION, self.next_action(root))

    def test_the_route_is_reachable_through_the_guard(self) -> None:
        """A printed command the guard refuses is not a route (T-1357)."""
        from saipen_engine.guard_events import _saipen_cli_verb

        self.assertEqual(
            _saipen_cli_verb("saipen recover resolve-next-action saipen continue"),
            "recover",
        )


class UnknownPhaseGrammarTests(unittest.TestCase):
    """T-1606 / SRC-167:R002: the grammar must name a real phase.

    The grammar matched `[A-Za-z_-]+` and then checked only casing and the
    ticket-bearing rule, so `PHASE NO_SUCH_PHASE` passed: an uppercase single
    token that is not in the § 1.6 enum. A cold reader would load
    `phases/no_such_phase.md` and find nothing to execute, which is the same
    dead end the ticket-attachment rule exists to prevent.
    """

    def test_an_unknown_uppercase_phase_is_refused(self) -> None:
        from saipen_engine import phases

        error = phases.phase_next_action_error("PHASE NO_SUCH_PHASE")
        self.assertIsNotNone(error, "an unknown phase name passed the grammar")
        self.assertIn("NO_SUCH_PHASE", error)

    def test_every_enum_phase_is_still_accepted(self) -> None:
        """The control: the gate must not narrow the legal set."""
        from saipen_engine import phases

        for name in sorted(phases.ALL_PHASES):
            with self.subTest(phase=name):
                value = (
                    f"PHASE {name} T-1"
                    if name in phases.TICKET_BEARING_PHASES
                    else f"PHASE {name}"
                )
                self.assertIsNone(phases.phase_next_action_error(value), value)

    def test_a_wait_payload_is_still_a_prefix_not_a_phase(self) -> None:
        """`WAIT:` is its own next_action form; it never reaches this checker
        because every caller gates on the `PHASE ` prefix first."""
        from saipen_engine import phases

        self.assertIsNotNone(phases.phase_next_action_error("PHASE WAIT"))
        self.assertFalse("WAIT" in phases.ALL_PHASES)

    def test_the_validator_agrees_with_the_engine_on_every_verdict(self) -> None:
        """SRC-167:R002 requires ONE grammar across writer and validator.

        `tools/validate.py` keeps its own copy of this rule (the constitution's
        own ADD example once wrote the forbidden `PHASE PLAN T-###`, so the
        check is spelled out there next to the sentence it enforces). A copy is
        two things to change: the engine gained the enum check and the
        validator did not, which is exactly the "enforced on only one surface"
        defect the rule exists to prevent. Compare verdicts, not just the
        unknown-phase case, so a future narrowing cannot pass on one side.
        """
        import ast
        from saipen_engine import phases

        source = (Path(__file__).parent / "validate.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        pieces = [
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and getattr(node.targets[0], "id", None) == "_PHASE_NA_RE"
        ] + [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_phase_next_action_error"
        ]
        self.assertEqual(len(pieces), 2, "validate.py's rule moved or was renamed")
        namespace = {
            "re": __import__("re"),
            "ALL_PHASES": phases.ALL_PHASES,
            "TICKET_BEARING_PHASES": phases.TICKET_BEARING_PHASES,
        }
        exec(compile(ast.Module(body=pieces, type_ignores=[]), "<validate>", "exec"), namespace)
        validator = namespace["_phase_next_action_error"]

        values = ["PHASE NO_SUCH_PHASE", "PHASE WAIT", "PHASE BANANA", "PHASE build"]
        for name in sorted(phases.ALL_PHASES):
            values.append(
                f"PHASE {name} T-1" if name in phases.TICKET_BEARING_PHASES else f"PHASE {name}"
            )
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(
                    validator(value) is None,
                    phases.phase_next_action_error(value) is None,
                    f"engine and validator disagree about {value!r}",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
