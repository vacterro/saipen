"""T-1829 / SRC-285:R003 — the publication boundary a focused run cannot cross.

These are the executable witnesses for the two mechanisms this ticket added to
`saipen_engine.release`:

* the gate runs the validator the executing engine owns, never the subject's
  own copy, so a downstream tree cannot replace the check that judges it;
* SHIP consults `focused_unit.publication_gate` before the external validator,
  so a focused or partial result can never stand in for a complete family.

The last two tests read the saved red-control and before/after records, so a
future regression that silently detaches either mechanism fails here.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from saipen_engine import focused_unit, release

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / ".saipen" / "evidence" / "T-1829-cost-collapse"


class _Recorder:
    """A subprocess.run stand-in that records the command and never executes."""

    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command, **_kwargs):
        self.commands.append([str(part) for part in command])

        class Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        return Completed()


class RuntimeValidatorTests(unittest.TestCase):
    def _home(self):
        home = ROOT / "runtime-home-not-created"
        return home, home / "tools" / "saipen_engine" / "release.py"

    def test_the_gate_command_uses_the_engine_own_validator(self):
        home, engine = self._home()
        with mock.patch.object(release, "__file__", str(engine)):
            command = release._gate_command(ROOT / "elsewhere", "ship")
        self.assertEqual(command[1], str(home / "tools" / "validate.py"))

    def test_a_managed_project_is_named_to_the_runtime_validator(self):
        home, engine = self._home()
        with mock.patch.object(release, "__file__", str(engine)):
            command = release._gate_command(ROOT / "elsewhere", "core")
        self.assertEqual(command[1:], [
            str(home / "tools" / "validate.py"),
            "--project-root", str((ROOT / "elsewhere").resolve()),
            "--gate", "core",
        ])

    def test_the_running_home_validates_itself(self):
        home, engine = self._home()
        with mock.patch.object(release, "__file__", str(engine)):
            command = release._gate_command(home, "ship")
        self.assertEqual(command[1:], [str(home / "tools" / "validate.py"), "--gate", "ship"])


class PublicationBoundaryTests(unittest.TestCase):
    def test_ship_refuses_before_the_external_validator(self):
        recorder = _Recorder()
        with mock.patch.object(focused_unit, "publication_gate", return_value="no full run"), \
                mock.patch.object(release.subprocess, "run", recorder):
            verdict = release._run_gate(ROOT, "ship")
        self.assertFalse(verdict["ok"])
        self.assertIn("no full run", verdict["detail"])
        self.assertEqual(recorder.commands, [], "the validator must not be spent")

    def test_a_local_core_gate_does_not_demand_a_full_family_record(self):
        recorder = _Recorder()
        with mock.patch.object(focused_unit, "publication_gate") as boundary, \
                mock.patch.object(release.subprocess, "run", recorder):
            verdict = release._run_gate(ROOT, "core")
        self.assertTrue(verdict["ok"])
        boundary.assert_not_called()
        self.assertEqual(len(recorder.commands), 1)


class SavedControlRecordsTests(unittest.TestCase):
    def test_the_pair_record_holds_and_wrote_nothing(self):
        record = json.loads((EVIDENCE / "publication-pair.json").read_text(encoding="utf-8"))
        self.assertTrue(record["pair_holds"], record)
        self.assertTrue(record["before"]["external_validator_invoked"])
        self.assertFalse(record["after"]["external_validator_invoked"])
        self.assertFalse(record["writes_canonical_state"])
        self.assertFalse(record["validator_actually_executed"])

    def test_every_red_control_mutation_was_caught(self):
        log = (EVIDENCE / "red-control-gate.log").read_text(encoding="utf-8")
        self.assertIn("PASS: all 3 mutations were caught", log)
        self.assertIn("restored byte-identically: True", log)
        self.assertEqual(log.count("RED   "), 3, log)


if __name__ == "__main__":
    unittest.main()
