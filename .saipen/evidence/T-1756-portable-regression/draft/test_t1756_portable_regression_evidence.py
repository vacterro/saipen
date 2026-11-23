"""T-1756: a measured regression pair stays evidence in the next session.

The verifier identity hashed the whole ambient environment of whichever
process asked (`regression_execution._runtime`: os.environ minus SAIPEN_*),
and the VERIFY -> REVIEW gate recomputed it in its own process. Every host
session carries its own identifiers -- session id, process id, messaging
socket -- so a pair measured in one session went STALE_REGRESSION_EVIDENCE in
the next with command, runtime, oracle, context and subject unchanged
(measured on T-1747, 2026-10-13: verifier 93a2f591, then 7d00adcc over the
same subject digests), and the Work could not leave VERIFY until the pair was
measured again.

The environment a pair ran under is now part of its record, bound by the
record's own receipt digest, and the gate judges the verifier the pair
actually ran. Oracle, runtime, command, context and subject are still read
from the tree and the interpreter at the gate.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import operations  # noqa: E402
from saipen_engine import regression_execution as execution  # noqa: E402
from test_regression_gate import RegressionGateFixture  # noqa: E402

CHECK = """import unittest
from subject import answer
class Control(unittest.TestCase):
    def test_answer(self): self.assertEqual(answer(), 2)
if __name__ == "__main__": unittest.main()
"""
#: Two host sessions differ in carriers like these and in nothing the
#: verifier reads.
SESSION_A = {"CLAUDE_CODE_SESSION_ID": "session-a", "T1756_TERMINAL": "window-1"}
SESSION_B = {"CLAUDE_CODE_SESSION_ID": "session-b", "T1756_TERMINAL": "window-2"}


class PortableEvidenceTests(RegressionGateFixture):
    def setUp(self):
        super().setUp()
        self.assertTrue(
            self.project.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
        )
        (self.project / "subject.py").write_text("def answer(): return 2\n", encoding="utf-8")
        (self.project / "check.py").write_text(CHECK, encoding="utf-8")
        evidence = self.project / ".saipen/evidence"
        evidence.mkdir(exist_ok=True)
        (evidence / "before.py").write_text("def answer(): return 1\n", encoding="utf-8")
        self.contract_path = evidence / "contract.json"
        self.contract_path.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "command": ["{python}", "-B", "check.py"],
                    "format": "unittest",
                    "context": ["subject.py", "check.py"],
                    "oracle_files": ["check.py"],
                    "subject_files": ["subject.py"],
                    "before": {"subject.py": ".saipen/evidence/before.py"},
                    "timeout": 30,
                }
            ),
            encoding="utf-8",
        )
        self.assertTrue(
            operations.ticket_verify(
                self.project, "T-7", "tester", None, regression="required",
                evidence_profile="executed",
            ).ok
        )

    def execute(self):
        result = execution.execute_pair(self.project, "T-7", "tester", self.contract_path)
        self.assertTrue(result.ok, result.to_dict())
        return result

    def test_the_next_session_admits_the_measured_pair(self):
        with patch.dict(os.environ, SESSION_A):
            self.execute()
        with patch.dict(os.environ, SESSION_B):
            before = self.canonical_digest()
            review = self.to_review()
        self.assertTrue(review.ok, review.to_dict())
        self.assertNotEqual(self.canonical_digest(), before)

    def test_the_record_carries_the_environment_it_ran_under(self):
        with patch.dict(os.environ, SESSION_A):
            result = self.execute()
        record = json.loads((self.project / result.data["record"]).read_text(encoding="utf-8"))
        self.assertRegex(record.get("environment_digest") or "", re.compile(r"^[0-9a-f]{64}$"))
        with patch.dict(os.environ, SESSION_B):
            remeasured = execution._load(self.project, self.contract_path)
        self.assertNotEqual(remeasured["environment_digest"], record["environment_digest"])

    def test_a_changed_oracle_still_refuses(self):
        self.execute()
        (self.project / "check.py").write_text(CHECK + "# weakened\n", encoding="utf-8")
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(self.canonical_digest(), before)

    def test_a_changed_subject_still_refuses(self):
        self.execute()
        (self.project / "subject.py").write_text("def answer(): return 3 - 1\n", encoding="utf-8")
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(self.canonical_digest(), before)

    def test_a_changed_runtime_still_refuses(self):
        self.execute()
        real = execution._runtime

        def another_interpreter(command):
            runtime, argv, environment = real(command)
            return {**runtime, "sha256": "0" * 64}, argv, environment

        with patch.object(execution, "_runtime", another_interpreter):
            before = self.canonical_digest()
            self.assertFalse(self.to_review().ok)
            self.assertEqual(self.canonical_digest(), before)

    def test_a_malformed_recorded_environment_is_not_trusted(self):
        material = execution._load(
            self.project, self.contract_path, environment_digest="not-a-digest"
        )
        self.assertEqual(
            material["environment_digest"],
            execution._load(self.project, self.contract_path)["environment_digest"],
        )


if __name__ == "__main__":
    unittest.main()
