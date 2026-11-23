"""T-1612: reproduction status and finding class are ORTHOGONAL facts.

The defect this pins is a contradiction between two validator arms of the same
`sweep-ticket-link` gate:

  arm A  a `CONFIRMED` disposition that authorizes a ticket needs `reproduced=y`
         -- an unverified finding cannot authorize canonical work;
  arm B  `ACCIDENTAL_SUCCESS` + `reproduced=y` is rejected as "recorded as PASS".

Arm B read `reproduced=y` as "this finding is a PASS of the suspected defect".
It is not: `reproduced=y` says the observed behaviour was reproduced, and a
reproduced observation can be a correct result that does NOT establish the
suspected defect -- an accidental-success condition, a false premise, a
misleading pass condition. That is exactly what `ACCIDENTAL_SUCCESS` names, so
the two arms together made the truthful state unrepresentable, and five
completed, immutable sweep rows in a live project could not validate without
rewriting history to a false disposition.

Arm A is the invariant that matters and it is unchanged: a ticket needs
reproduction evidence, whatever the class. What these tests pin is that no class
-- `ACCIDENTAL_SUCCESS` included -- is a substitute for reproduction, and that
reproduction is not a substitute for a canonical ticket either.

The satisfiability table at the bottom is the anti-recurrence half: it walks the
legal state space and requires a reproducible `ACCIDENTAL_SUCCESS` to be
representable, and it walks validate.py's own AST to require that no finding
class is ever compared against the reproduction flag again under ANY
classification.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import improve  # noqa: E402
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402

VALIDATOR = TOOLS / "validate.py"
TICKET = "T-900"

REPORT_HEADER = (
    "agent: probe\nrole: core\nmodel_or_runtime: test\n"
    "project: PROJ\nsaipen_version: 7.220.0\n"
    "protocol_fingerprint: deadbeef\nsource_head: abc\n"
    "source_tree_fingerprint: beef\n"
    "context_scope: tools/\ncontext_available: partial\n"
    "report_status: complete\n\n"
)


def _project(
    disposition: str,
    reproduced: str,
    *,
    finding_class: str = "LOGIC_ERROR",
    ticket: str = TICKET,
    ticket_on_board: bool = True,
    cycle_status: str = "active",
) -> Path:
    """A minimal real project whose only moving part is the sweep row."""
    root = Path(tempfile.mkdtemp(prefix="saipen-t1612-"))
    saipen = root / ".saipen"
    saipen.mkdir()
    (saipen / "LOG.md").write_text(
        "- 09.08.26 00:00 [E-900] [T-none] DEC: base\n", encoding="utf-8"
    )
    board = ["# Board", "## DOING"]
    if ticket_on_board and ticket != "-":
        board.append(
            f"- [ ] {ticket} [P1] swept ticket | verify: probe | "
            f"source_reports: IMP-001"
        )
    board += ["## TODO", "## DONE", "## BLOCKED"]
    (saipen / "BOARD.md").write_text("\n".join(board) + "\n", encoding="utf-8")
    (saipen / "STATE.md").write_text(
        '---\nphase: DONE\ntask: none\nnext_action: "saipen continue"\n'
        'blocker: ""\ntransition_from: SHIP\nsaipen_version: 7\n'
        "schema_version: 3\nlast_event: 900\nstyle_contract: "
        + CURRENT_STYLE_CONTRACT
        + '\nsaipen_home: "."\nagent: probe\nmode: full\n'
        'updated: 2026-08-09T00:00:00Z\n---\n',
        encoding="utf-8",
    )
    cycle = improve.register_cycle(
        root, "imp-t1612", f"# IMPROVE CYCLE ROSTER\ncycle_status: {cycle_status}\n"
    )
    improve.register_seat(cycle, "seat1", "core", "saipen_improve_A.md")
    report = cycle / "seat1" / "saipen_improve_A.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        REPORT_HEADER
        + f"IMP-001 [P1] [{finding_class}] [reproduced] [ticket]\n"
        + "expected: x\nactual: y\nevidence: z\n",
        encoding="utf-8",
    )
    # The truth table's `ticket` dimension is the ROW's ticket: a ref the board
    # cannot resolve and a bare "-" fail the same gate (no canonical ticket),
    # so the fixture writes the honest "-" rather than a dangling ref.
    row_ticket = ticket if (ticket_on_board and ticket != "-") else "-"
    (cycle / "SWEEP.md").write_text(
        f"# SWEEP\n- IMP-001 [{disposition}] {row_ticket} "
        f"report=seat1/saipen_improve_A.md reproduced={reproduced}\n",
        encoding="utf-8",
    )
    return root


def _validate(root: Path) -> tuple[int, str]:
    done = subprocess.run(
        [sys.executable, str(VALIDATOR), "--project-root", str(root)],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    return done.returncode, done.stdout + done.stderr


class AccidentalSuccessReproductionOrthogonality(unittest.TestCase):
    """Red control 5 is the reproduction gate, never a class check."""

    def test_confirmed_reproduced_ordinary_finding_with_ticket_is_valid(self):
        rc, out = _validate(_project("CONFIRMED", "y"))
        self.assertEqual(rc, 0, out)

    def test_confirmed_unreproduced_finding_cannot_authorize_a_ticket(self):
        rc, out = _validate(_project("CONFIRMED", "n"))
        self.assertNotEqual(rc, 0, out)
        self.assertIn("unverified finding cannot authorize a ticket", out)

    def test_reproduced_accidental_success_authorizes_its_own_ticket(self):
        """The repaired state: reproduced, correct result, real defect found."""
        rc, out = _validate(_project("CONFIRMED", "y", finding_class="ACCIDENTAL_SUCCESS"))
        self.assertEqual(rc, 0, out)

    def test_reproduced_accidental_success_is_not_a_pass_of_the_hypothesis(self):
        """`reproduced=y` confers no authority: the ticket gates still bind."""
        rc, out = _validate(
            _project(
                "CONFIRMED",
                "y",
                finding_class="ACCIDENTAL_SUCCESS",
                ticket="T-901",
                ticket_on_board=False,
            )
        )
        self.assertNotEqual(rc, 0, out)
        self.assertIn("has no canonical ticket", out)

    def test_unreproduced_finding_cannot_buy_authority_with_the_class(self):
        rc, out = _validate(
            _project("CONFIRMED", "n", finding_class="ACCIDENTAL_SUCCESS")
        )
        self.assertNotEqual(rc, 0, out)
        self.assertIn("unverified finding cannot authorize a ticket", out)

    def test_completed_cycle_accidental_success_validates_without_rewriting(self):
        """An immutable, completed record keeps validating as written."""
        rc, out = _validate(
            _project(
                "CONFIRMED",
                "y",
                finding_class="ACCIDENTAL_SUCCESS",
                cycle_status="complete",
            )
        )
        self.assertEqual(rc, 0, out)

    def test_contradictory_record_still_fails(self):
        """No ticket on a CONFIRMED disposition, whatever the class."""
        for finding_class in ("LOGIC_ERROR", "ACCIDENTAL_SUCCESS"):
            with self.subTest(finding_class=finding_class):
                rc, out = _validate(
                    _project(
                        "CONFIRMED",
                        "y",
                        finding_class=finding_class,
                        ticket="-",
                        ticket_on_board=False,
                    )
                )
                self.assertNotEqual(rc, 0, out)
                self.assertIn("has no canonical ticket", out)

    def test_unconfirmed_disposition_carrying_a_ticket_still_fails(self):
        for disposition in ("INVALID", "NOT_REPRODUCED", "ALREADY_FIXED"):
            with self.subTest(disposition=disposition):
                rc, out = _validate(
                    _project(
                        disposition, "y", finding_class="ACCIDENTAL_SUCCESS"
                    )
                )
                self.assertNotEqual(rc, 0, out)
                self.assertIn("must never produce a ticket", out)


class SatisfiabilityTruthTable(unittest.TestCase):
    """The legal state space, walked rather than assumed."""

    # (disposition, reproduced, ticket present, expected verdict)
    TABLE = (
        ("CONFIRMED", "y", True, True),
        ("CONFIRMED", "n", True, False),
        ("CONFIRMED", "y", False, False),
        ("CONFIRMED", "n", False, False),
        ("INVALID", "y", True, False),
        ("INVALID", "n", True, False),
        ("INVALID", "n", False, True),
        ("ALREADY_FIXED", "y", True, False),
        ("NOT_REPRODUCED", "y", True, False),
        ("NOT_REPRODUCED", "n", False, True),
    )

    def test_every_class_admits_a_reproducible_state_that_authorizes_a_ticket(self):
        """For every finding class, reproduced + CONFIRMED + ticket is legal."""
        for finding_class in sorted(improve.FINDING_CLASS):
            if finding_class == "PROTOCOL_VIOLATION":
                continue  # carries its own reasoning gates (red 15/16)
            with self.subTest(finding_class=finding_class):
                rc, out = _validate(
                    _project("CONFIRMED", "y", finding_class=finding_class)
                )
                self.assertEqual(rc, 0, out)

    def test_truth_table_verdicts(self):
        for disposition, reproduced, on_board, expected_valid in self.TABLE:
            for finding_class in ("LOGIC_ERROR", "ACCIDENTAL_SUCCESS"):
                with self.subTest(
                    disposition=disposition,
                    reproduced=reproduced,
                    ticket=on_board,
                    finding_class=finding_class,
                ):
                    rc, out = _validate(
                        _project(
                            disposition,
                            reproduced,
                            finding_class=finding_class,
                            ticket_on_board=on_board,
                        )
                    )
                    self.assertEqual(rc == 0, expected_valid, out)

    def test_validator_never_compares_a_finding_class_to_reproduction(self):
        """Anti-recurrence: no classification may re-couple class and repro."""
        tree = ast.parse(VALIDATOR.read_text(encoding="utf-8-sig"))
        classes = set(improve.FINDING_CLASS)
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            segment = ast.get_source_segment(
                VALIDATOR.read_text(encoding="utf-8-sig"), node
            ) or ""
            literals = {
                n.value
                for n in ast.walk(node)
                if isinstance(n, ast.Constant) and n.value in classes
            }
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            if literals and names & {"_repro", "reproduced"}:
                offenders.append(segment)
        self.assertEqual(offenders, [], "class/reproduction coupling reintroduced")


if __name__ == "__main__":
    unittest.main()