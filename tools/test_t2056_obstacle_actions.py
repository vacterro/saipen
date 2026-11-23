"""T-2056: a CURRENT_FAIL hands back permitted actions, never a dead end.

Measured live (2026-11-14): `saipen cc` answered a CURRENT_FAIL with
``CURRENT_FAIL has no registered executable repair`` and ``action: null``. The
agent then had exactly two moves -- ask the operator, or invent new Work -- and
the operator was handed an obligation the protocol could have discharged itself.

The engine already owned both halves of the answer and never joined them:
``finding_ownership`` says WHO owns a finding, ``finding_route`` names the live
Work that already owns its subject. This module pins the join:

* a subject with a live owner becomes ``saipen claim <T-###>`` -- never
  ``saipen start`` (the duplicate-record loop SRC-276 F-01 measured);
* an unowned finding becomes ``saipen ticket add``, so the repair is Work
  instead of an obligation;
* an operator-gated class stays silent without a witnessed decision, EXACTLY as
  ``finding_ownership`` already refuses -- a permitted action is never a
  manufactured authority;
* an unreadable BOARD yields the ownership class and no command: the projection
  never invents a route and never fails the verdict;
* the list is bounded, and the remainder is counted so nothing is dropped.
"""

from __future__ import annotations

import shlex
import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import conformance as C  # noqa: E402
from saipen_engine import findings  # noqa: E402
import test_conformance_repair_boundary as fixtures  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

BOARD_WITH_OWNER = """# BOARD

## DOING
- [/] T-9 [P1] existing owner of the blocked subject | verify: the subject is repaired | owner: agent | claim_time: 2026-11-14T00:00:00Z

## TODO

## BLOCKED

## DONE
"""

BOARD_WITH_OWNER_AND_FAMILY = """# BOARD

## DOING
- [/] T-9 [P1] existing owner of the blocked subject | verify: the subject is repaired | owner: agent | claim_time: 2026-11-14T00:00:00Z
- [/] T-10 [P1] second owner of the blocked subject | verify: the subject is repaired | owner: agent | claim_time: 2026-11-14T00:00:00Z | blocker: work_closure_evidence T-9

## TODO

## BLOCKED

## DONE
"""


def setUpModule() -> None:
    isolate_host_session()


def diagnostics(*messages: str) -> dict:
    problems = [findings.classify("problem", message) for message in messages]
    return {
        "status": "complete",
        "ruleset_version": findings.RULESET_VERSION,
        "ruleset_fingerprint": findings.ruleset_fingerprint(),
        "problem_count": len(problems),
        "warning_count": 0,
        "problems": problems,
    }


class ObstacleBecomesAction(fixtures.RepairBoundaryTests):
    def fail_with(self, name: str, *messages: str, board: str | None = None) -> dict:
        kwargs = {"board": board} if board is not None else {}
        root = self.make_project(name, **kwargs)
        C.generate_conformance_receipt(
            root, gate="core", exit_code=1, blocking_findings=diagnostics(*messages)
        )
        return C.conformance_decision(root)

    def test_a_live_owner_subject_becomes_its_claim(self) -> None:
        decision = self.fail_with(
            "action-owner",
            "ticket T-9 is ## DONE but carries no current-cycle verification evidence (classifier: none)",
            board=BOARD_WITH_OWNER,
        )
        self.assertEqual(decision["repair_status"], "ENGINEERING_REQUIRED")
        self.assertEqual(decision["primary_action"], "saipen claim T-9")
        self.assertEqual(decision["remediation_command"], "saipen claim T-9")
        action = decision["repair_actions"][0]
        self.assertEqual(action["owner"], "T-9")
        self.assertEqual(action["route_code"], "ROUTED_TO_OWNER")
        self.assertNotIn("saipen start", action["command"])

    def test_an_unowned_finding_becomes_work_not_an_obligation(self) -> None:
        decision = self.fail_with(
            "action-unowned", "ORPHAN_RECEIPT SRC-009 is not linked to any Work"
        )
        action = decision["repair_actions"][0]
        self.assertEqual(action["route_code"], "NO_OWNER")
        self.assertTrue(action["command"].startswith("saipen ticket add "))
        self.assertIs(action["operator_action_due"], False)
        self.assertEqual(decision["primary_action"], action["command"])

    def test_an_unwitnessed_operator_class_stays_silent(self) -> None:
        decision = self.fail_with(
            "action-operator",
            "SOURCE_CREDENTIALS_UNSAFE credential pattern in .saipen/evidence/x",
        )
        actions = decision["repair_actions"]
        self.assertTrue(actions, "the finding is still reported")
        for action in actions:
            self.assertEqual(action["owner_class"], "OPERATOR_DECISION")
            self.assertIs(action["operator_action_due"], False)
            self.assertIsNone(action["command"])
        self.assertIsNone(decision["primary_action"])
        # No human obligation was manufactured by the class alone.
        self.assertEqual(decision["diagnostic"].get("operator_action_count"), 0)

    def test_an_external_finding_creates_no_local_work(self) -> None:
        decision = self.fail_with(
            "action-external", "OUTBOX.md fails strict OUTBOX parsing"
        )
        action = decision["repair_actions"][0]
        self.assertEqual(action["owner_class"], "UNAVAILABLE_EXTERNAL")
        self.assertEqual(action["route_code"], "EXTERNAL_OWNER")
        self.assertIsNone(action["command"])
        self.assertIsNone(decision["primary_action"])

    def test_an_unreadable_board_yields_no_invented_route(self) -> None:
        root = self.make_project("action-noboard")
        (root / ".saipen" / "BOARD.md").unlink()
        actions = C._repair_actions(
            root,
            diagnostics("ORPHAN_RECEIPT SRC-009 is not linked to any Work")["problems"],
        )
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["owner_class"], "ENGINE_INTERNAL")
        self.assertEqual(actions[0]["route_code"], "BOARD_UNREADABLE")
        self.assertIsNone(actions[0]["command"])

    def test_a_silent_finding_never_hides_a_permitted_repair(self) -> None:
        # A silent class (external/operator) and a permitted move in ONE finding
        # set: the executable repair must survive at the head of the list, so a
        # finding the engine cannot act on never blocks the work it can.
        decision = self.fail_with(
            "action-silent-head",
            "OUTBOX.md fails strict OUTBOX parsing",
            "ORPHAN_RECEIPT SRC-009 is not linked to any Work",
            board=BOARD_WITH_OWNER,
        )
        actions = decision["repair_actions"]
        self.assertEqual(actions[0]["owner_class"], "ENGINE_INTERNAL")
        self.assertTrue(actions[0]["command"].startswith("saipen "), actions[0]["command"])
        # The silent half is still reported, exactly once, and carries no command.
        silent = [a for a in actions if a["owner_class"] == "UNAVAILABLE_EXTERNAL"]
        self.assertEqual(len(silent), 1)
        self.assertIsNone(silent[0]["command"])

    def test_silent_findings_never_occupy_the_action_bound(self) -> None:
        roots = {
            "action-bound-silent-external": "OUTBOX.md fails strict OUTBOX parsing",
            "action-bound-silent-operator": "SOURCE_CREDENTIALS_UNSAFE credential pattern in .saipen/evidence/x",
        }
        for name, blocker in roots.items():
            with self.subTest(name=name):
                decision = self.fail_with(
                    name,
                    blocker,
                    *[
                        f"ORPHAN_RECEIPT SRC-{index:03d} is not linked to any Work"
                        for index in range(1, 8)
                    ],
                )
                self.assertEqual(
                    len(decision["repair_actions"]), C.MAX_REPAIR_ACTIONS
                )
                # The blocker itself is counted as an input finding, so the
                # reported total is every blocking finding, executable or silent.
                self.assertEqual(decision["diagnostic"]["actions_total"], 8)
                for action in decision["repair_actions"]:
                    self.assertTrue(action["command"].startswith("saipen "), action["command"])

    def test_the_action_list_is_bounded_and_counts_the_rest(self) -> None:
        decision = self.fail_with(
            "action-bounded",
            *[
                f"ORPHAN_RECEIPT SRC-{index:03d} is not linked to any Work"
                for index in range(1, 10)
            ],
        )
        self.assertLessEqual(len(decision["repair_actions"]), C.MAX_REPAIR_ACTIONS)
        self.assertEqual(decision["diagnostic"]["actions_total"], 9)

    def test_every_action_is_a_command_the_cli_can_run(self) -> None:
        decision = self.fail_with(
            "action-command-shape",
            "closed receipt SRC-003 archive bundle invalid: missing metadata",
            "ORPHAN_RECEIPT SRC-009 is not linked to any Work",
            board=BOARD_WITH_OWNER,
        )
        commands = [a["command"] for a in decision["repair_actions"] if a["command"]]
        self.assertTrue(commands)
        for command in commands:
            self.assertTrue(command.startswith("saipen "), command)
            # `saipen ticket claim` was the resolver's unrunnable verb (T-2056).
            self.assertNotIn("saipen ticket claim", command)

    def test_generated_ticket_text_survives_the_real_cli_parser(self) -> None:
        # The projection embeds validator prose in double quotes. Shell
        # expansion metacharacters and non-ASCII must be neutralised so the
        # command is executable on both PowerShell and POSIX hosts.
        message = (
            'ORPHAN_RECEIPT SRC-009 is not linked to any Work: "$(rm -rf /)" '
            "`backtick` caf\u00e9 \u201cellipsis\u201d %APPDATA% \\\\path"
        )
        root = self.make_project("action-command-metachars")
        C.generate_conformance_receipt(
            root,
            gate="core",
            exit_code=1,
            blocking_findings=diagnostics(message),
        )
        # The classifier degrades the hostile body into a short subject id, so
        # drive `_one_line` directly: proving the sanitizer is the only way
        # this test can exercise the path.
        hostile = C._one_line(message, 160)
        for raw in ("$(rm -rf /)", "`backtick`", "café", "\u201c", "%APPDATA%", "\\"):
            self.assertNotIn(raw, hostile)
        command = C.conformance_decision(root)["repair_actions"][0]["command"]
        self.assertTrue(command.startswith("saipen "), command)
        for raw in ("$(rm -rf /)", "`backtick`", "café", "\u201c", "%APPDATA%", "\\"):
            self.assertNotIn(raw, command)
        argv = shlex.split(command, posix=True)
        self.assertEqual(argv[1:3], ["ticket", "add"])
        # The REAL CLI parses the generated argv: dry-run proves the grammar
        # without writing anything.
        rc, payload, _raw = self.run_cli(root, "--dry-run", *argv[1:])
        self.assertEqual(rc, 0, payload)
        self.assertTrue(payload.get("ok"), payload)
        self.assertTrue(payload.get("dry_run"), payload)

    def test_an_ambiguous_subject_never_becomes_a_ticket(self) -> None:
        # Two live Works claim the same subject: minting a third would
        # reproduce the duplicate-ownership defect SRC-276 F-01 measured.
        decision = self.fail_with(
            "action-ambiguous",
            "ticket T-9 is ## DONE but carries no current-cycle verification evidence (classifier: none)",
            board=BOARD_WITH_OWNER_AND_FAMILY,
        )
        actions = decision["repair_actions"]
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["route_code"], "AMBIGUOUS")
        self.assertIsNone(actions[0]["command"])

    def test_an_unresolved_route_never_becomes_a_ticket(self) -> None:
        root = self.make_project("action-unresolved")
        problems = diagnostics(
            "ORPHAN_RECEIPT SRC-009 is not linked to any Work"
        )["problems"]
        with mock.patch(
            "saipen_engine.finding_route.resolve", side_effect=RuntimeError("broken resolver")
        ):
            actions = C._repair_actions(root, problems)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["route_code"], "UNRESOLVED")
        self.assertIsNone(actions[0]["command"])

    def test_an_unknown_owner_finds_no_invented_move(self) -> None:
        decision = self.fail_with(
            "action-unknown-owner", "unmapped rule fired on subject with no owner"
        )
        actions = decision["repair_actions"]
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["owner_class"], "UNKNOWN")
        self.assertEqual(actions[0]["route_code"], "OWNER_UNKNOWN")
        self.assertTrue(actions[0]["command"].startswith("saipen ticket add "))


if __name__ == "__main__":
    unittest.main()
