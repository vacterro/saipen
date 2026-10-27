"""T-1771: a measured pair survives the closure path it was measured for.

`saipen work regression` binds each linked source receipt's Contract digest
into its receipt, so a finish can prove the pair was measured under the same
conditions. A receipt captured by `saipen user-request` holds no clause until
its request clause is derived, and the closure path derives it -- after the
measurement. The finish then moved the binding it was checking and refused
`STALE_REGRESSION_EVIDENCE: execution binding changed: source_receipts`, and
since `work regression` runs only in VERIFY and SHIP -> VERIFY is not an edge,
the only way out was SHIP -> BUILD -> VERIFY -> re-measure (_SAIRELAY T-8,
imp-_sairelay-20261013-1 saipen-cli-01 RUN-1/IMP-001; SRC-248 R004).

The oracle runs that chain through the CLI alone and finishes once. The
derivation is a write, so it waits for the binding to admit the caller as
the owner of the active Work: a call refused before that writes nothing.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import intake  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1363_zero_manual_entry import cli, healthy  # noqa: E402

REQUEST = "make answer() in subject.py return 2"

CHECK = """import unittest
from subject import answer


class Control(unittest.TestCase):
    def test_answer(self):
        self.assertEqual(answer(), 2)


if __name__ == "__main__":
    unittest.main()
"""


def setUpModule() -> None:
    isolate_host_session()


class MeasureThenFinish(unittest.TestCase):
    def _at_verify(self, *, derived: bool = False) -> tuple[Path, str, str]:
        """A user-request Work built and in VERIFY, its pair not yet measured.

        `derived` derives the request clause before the measurement, so the
        Contract the pair binds is the one the closure path leaves.
        """
        root = healthy(self)
        code, payload, text = cli(root, "user-request", REQUEST, "--verify", "check.py", "--json")
        self.assertEqual(code, 0, text)
        ticket = payload.get("ticket") or "T-1"
        receipt = payload.get("receipt")
        self.assertTrue(receipt, payload)
        if derived:
            self.assertTrue(intake.ensure_request_clause(root, receipt).get("ok"))
        steps = [
            ("claim", ticket, "--json"),
            ("ticket", "regression", ticket, "required", "--evidence", "executed", "--json"),
            ("transition", "BUILD", ticket, "scout done", "--json"),
        ]
        for args in steps:
            code, _payload, text = cli(root, *args)
            self.assertEqual(code, 0, f"{args} -> {text}")
        (root / "subject.py").write_text("def answer():\n    return 2\n", encoding="utf-8")
        (root / "check.py").write_text(CHECK, encoding="utf-8")
        evidence = root / ".saipen" / "evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "before.py").write_text("def answer():\n    return 1\n", encoding="utf-8")
        (evidence / "contract.json").write_text(
            json.dumps(
                {
                    "schema": 1,
                    "command": ["{python}", "-B", "check.py"],
                    "format": "unittest",
                    "context": ["subject.py", "check.py"],
                    "oracle_files": ["check.py"],
                    "subject_files": ["subject.py"],
                    "before": {"subject.py": ".saipen/evidence/before.py"},
                    "timeout": 60,
                }
            ),
            encoding="utf-8",
        )
        steps = [
            ("checkpoint", "RUN", ticket, "build -> answer() returns 2", "--json"),
            ("transition", "VERIFY", ticket, "build done", "--json"),
        ]
        for args in steps:
            code, _payload, text = cli(root, *args)
            self.assertEqual(code, 0, f"{args} -> {text}")
        return root, ticket, receipt

    def _measured(self, *, derived: bool = False) -> tuple[Path, str, str]:
        """A user-request Work driven to SHIP over one measured regression pair."""
        root, ticket, receipt = self._at_verify(derived=derived)
        steps = [
            ("work", "regression", ticket, "--file", ".saipen/evidence/contract.json", "--json"),
            (
                "checkpoint",
                "RUN",
                ticket,
                f"verify -> PASS [target: {ticket}] conf: high -- check.py green on the "
                "fixed subject, red on the pre-fix one",
                "--json",
            ),
            ("transition", "REVIEW", ticket, "verify green", "--json"),
            ("transition", "SHIP", ticket, "review passed", "--json"),
        ]
        for args in steps:
            code, _payload, text = cli(root, *args)
            self.assertEqual(code, 0, f"{args} -> {text}")
        return root, ticket, receipt

    def test_the_fixture_measured_a_receipt_with_no_clause_yet_at_capture(self) -> None:
        # Instrument control: the request receipt is captured clause-less.
        root = healthy(self)
        code, payload, text = cli(root, "user-request", REQUEST, "--verify", "check.py", "--json")
        self.assertEqual(code, 0, text)
        contract = intake._read_contract(root, payload["receipt"]) or {}
        self.assertEqual(contract.get("clauses"), {}, contract)

    def test_the_first_finish_after_one_measurement_closes(self) -> None:
        root, ticket, _receipt = self._measured()
        code, payload, text = cli(
            root, "ticket", "done", ticket, "--closure-mode", "own_patch", "--json"
        )
        self.assertEqual((code, (payload or {}).get("code")), (0, "FINISHED"), text)

    def test_a_contract_changed_after_measurement_still_refuses(self) -> None:
        root, ticket, receipt = self._measured(derived=True)
        # A non-actionable clause moves the Contract and leaves coverage whole,
        # so the refusal is the binding's own and not the coverage gate's.
        added = intake.add_requirement(
            root,
            receipt,
            rid="R002",
            text="context derived after the measurement",
            clause_class="context",
        )
        self.assertTrue(added.get("ok"), added)
        code, _payload, text = cli(
            root, "ticket", "done", ticket, "--closure-mode", "own_patch", "--json"
        )
        self.assertNotEqual(code, 0, text)
        self.assertIn("STALE_REGRESSION_EVIDENCE", text)

    def test_a_call_refused_to_another_session_writes_no_clause(self) -> None:
        root, ticket, receipt = self._at_verify()
        code, payload, text = cli(
            root,
            "work",
            "regression",
            ticket,
            "--file",
            ".saipen/evidence/contract.json",
            "--json",
            agent="another-session",
        )
        self.assertNotEqual(code, 0, text)
        self.assertIn("actively claimed by another agent", text)
        self.assertEqual((payload or {}).get("changed_files"), [], text)
        contract = intake._read_contract(root, receipt) or {}
        self.assertEqual(contract.get("clauses"), {}, contract)

    def test_a_call_refused_for_its_inputs_writes_no_clause(self) -> None:
        root, ticket, receipt = self._at_verify()
        code, payload, text = cli(
            root, "work", "regression", ticket, "--file", ".saipen/evidence/absent.json", "--json"
        )
        self.assertNotEqual(code, 0, text)
        self.assertEqual((payload or {}).get("changed_files"), [], text)
        contract = intake._read_contract(root, receipt) or {}
        self.assertEqual(contract.get("clauses"), {}, contract)


if __name__ == "__main__":
    unittest.main()
