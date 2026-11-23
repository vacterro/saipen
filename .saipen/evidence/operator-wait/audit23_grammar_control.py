"""Fixed audit/23 grammar controls; preparation never edits a live project."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import entry, state
from saipen_engine.errors import CODES
from saipen_engine.result import Result
from test_fixture_support import CURRENT_STYLE_CONTRACT

STATE = (
    "---\nphase: BLOCKED\ntask: none\n"
    'next_action: "WAIT: blocked -- operator input required"\n'
    "blocker: OPERATOR_INPUT_REQUIRED\ntransition_from: DONE\n"
    "saipen_version: 8\nschema_version: 3\nlast_event: 45\n"
    f"style_contract: {CURRENT_STYLE_CONTRACT}\n"
    f"saipen_home: {ROOT.as_posix()}\n"
    'agent: fixture\nmode: full\nupdated: "2026-10-03T23:00:00Z"\n---\n'
)


class GrammarControls(unittest.TestCase):
    def test_writer_refuses_freeform_operator_value(self):
        with self.assertRaises(ValueError):
            state.patch_state(STATE, {"next_action": "operator: do something manually"})

    def test_writer_refuses_malformed_phase(self):
        for value in ("PHASE scout T-1", "PHASE NO_SUCH_PHASE", "PHASE BUILD"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                state.patch_state(STATE, {"next_action": value})

    def test_writer_refuses_empty_run(self):
        with self.assertRaises(ValueError):
            state.patch_state(STATE, {"next_action": "RUN:"})

    def test_writer_refuses_malformed_resume(self):
        for value in ("RESUME:", "RESUME: not a ticket", "RESUME: T-1 NO_SUCH_PHASE"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                state.patch_state(STATE, {"next_action": value})

    def test_strict_reader_refuses_legacy_operator_value(self):
        corrupt = STATE.replace(
            "WAIT: blocked -- operator input required", "operator: do something manually"
        )
        fields, error = state.parse_state_or_error(corrupt)
        self.assertIsNone(fields)
        self.assertIsNotNone(error)

    def test_valid_wait_round_trips(self):
        value = "WAIT: blocked -- supply a release-root PATH; 0 of 751 sessions are agent-runnable"
        rendered = state.patch_state(STATE, {"next_action": value})
        fields, error = state.parse_state_or_error(rendered)
        self.assertIsNone(error)
        self.assertEqual(fields["next_action"], value)

    def test_wait_is_a_binding_brake(self):
        fields, error = state.parse_state_or_error(STATE)
        self.assertIsNone(error)
        self.assertIsNotNone(state.binding_brake(fields, empty_todo=True))

    def test_existing_valid_forms_are_preserved(self):
        for value in (
            "PHASE SCOUT T-1", "PHASE DONE", "RUN: python -B tools/check.py",
            "RESUME: T-1 BUILD", "saipen continue",
        ):
            with self.subTest(value=value):
                rendered = state.patch_state(STATE, {"next_action": value})
                fields, error = state.parse_state_or_error(rendered)
                self.assertIsNone(error)
                self.assertEqual(fields["next_action"], value)

    def test_wait_operator_is_registered(self):
        self.assertIn(entry.WAIT_OPERATOR, CODES)

    def test_actual_entry_wait_has_no_unregistered_marker(self):
        outcome = entry._decision_wait(
            {"command": "saipen recover"}, receipt=None, ticket=None,
            detail="operator decision required",
        )
        result = Result(
            outcome["ok"], outcome["code"],
            {key: value for key, value in outcome.items() if key not in ("ok", "code")},
        ).to_dict()
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "WAIT_OPERATOR")
        self.assertNotIn("unregistered_code", result)


def main():
    stage = sys.argv[1]
    if stage not in ("original", "current"):
        raise SystemExit("stage must be original or current")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(GrammarControls)
    )
    subject = hashlib.sha256()
    for relative in (
        "saipen/REGISTRY.json", "tools/saipen_engine/phases.py",
        "tools/saipen_engine/state.py", "tools/saipen_engine/entry.py",
        "tools/saipen_engine/result.py",
    ):
        subject.update(relative.encode() + b"\0" + (ROOT / relative).read_bytes())
    record = {
        "scope": "audit/23 preparation; no claim or live project mutation",
        "stage": stage,
        "verifier": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "subject": subject.hexdigest(), "ran": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "passed": result.wasSuccessful(),
        "transcript": stream.getvalue(),
    }
    path = HERE / f"grammar-{stage}.json"
    if path.exists():
        raise SystemExit(f"refusing to overwrite preserved evidence: {path}")
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in record.items() if key != "transcript"}))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
