"""T-2093 (night shift 8, W4): the replay decision matrix, end to end.

The night-7 suite proved ONE replay cell (published FAIL answers a later
process) and one anti-cell inside the SAME process (`reusable_record`). The
handoff's matrix has twelve; this suite covers the rows that guard real
autonomy decisions, each stating replay-allowed / re-execute and the exact
identity binding:

* PASS and FAIL of the SAME identity replay to a later process (no waste);
* changed tree, changed baseline, changed configuration: NO replay of the
  old verdict -- each is a different identity and re-executes;
* corrupted or missing published bytes: replay refuses (digest/absence);
* a FAIL replay is ADVISORY evidence of unchanged failure -- it is reused
  as the answer to a repeated ask, and it is never a SHIP authority:
  `publication_gate`/`ship_gate` treat it as any other FAIL record.

Fixtures are disposable temp trees; nothing touches a real project.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import core_unit  # noqa: E402
from saipen_engine import verification_cache as cache  # noqa: E402

from test_core_unit_gate import _run  # noqa: E402


def child_code(body: str) -> str:
    return (
        "import sys, json, time, os;\n"
        "from pathlib import Path;\n"
        f"sys.path.insert(0, {str(TOOLS)!r});\n"
        "from saipen_engine import core_unit;\n"
        "from saipen_engine import verification_cache as cache;\n"
        f"{body}\n"
    )


class ReplayMatrixTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="t2093-matrix-"))
        self.addCleanup(core_unit.reclaim, self.base)
        self.project = self.base / "project"
        (self.project / ".saipen").mkdir(parents=True)
        (self.project / ".saipen" / "STATE.md").write_text("", encoding="utf-8")
        tools = self.project / "tools"
        tools.mkdir()
        (tools / "sandbox_scope.json").write_text(
            json.dumps({"schema": 1, "modules": {}}), encoding="utf-8"
        )
        (tools / "core_unit_baseline.json").write_text(json.dumps(
            {"schema": 1, "family": "unit", "red": [], "recorded_at": "test",
             "ran": 1, "command": ["python"]}
        ), encoding="utf-8")
        (tools / "test_new.py").write_text(
            "import unittest\n"
            "class NewTests(unittest.TestCase):\n"
            "    def test_x(self):\n"
            "        pass\n"
            "    def test_broken(self):\n"
            "        self.fail('red')\n",
            encoding="utf-8",
        )

    def identity(self, configuration=None) -> dict:
        return {
            "family": "unit",
            "fingerprint": core_unit.tree_fingerprint(self.project),
            "verification_identity": cache.capture(
                self.project, configuration or core_unit.verification_configuration()
            ),
        }

    def publish(self, identity, run=None):
        with cache.single_flight(self.project, identity) as first:
            first.publish(core_unit.write_record(
                self.project, run or _run(["test_new.NewTests.test_broken"]),
                identity["fingerprint"],
            ))

    def child_answer(self, identity) -> dict:
        """What a LATER OS process sees for this identity, or {'launched': 1}."""
        identity_path = self.base / "identity.json"
        identity_path.write_text(json.dumps(identity), encoding="utf-8")
        out = self.base / "child.json"
        proc = subprocess.Popen(
            [sys.executable, "-B", "-c", child_code(
                "identity = json.loads(Path(%r).read_text());\n"
                "try:\n"
                "    with cache.single_flight(Path(%r), identity) as flight:\n"
                "        Path(%r).write_text(json.dumps("
                "{'reused': flight.reused, 'verdict': "
                "flight.written['record']['verdict']}));\n"
                "except Exception as exc:\n"
                "    Path(%r).write_text(json.dumps("
                "{'launched': 1, 'detail': str(exc)}));\n"
                % (str(identity_path), str(self.project), str(out), str(out))
            )],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        stdout, stderr = proc.communicate(timeout=120)
        self.assertEqual(
            proc.returncode, 0,
            stderr.decode("utf-8", "replace") + stdout.decode("utf-8", "replace"),
        )
        return json.loads(out.read_text(encoding="utf-8"))

    # Row 1: same identity + PASS replays (a repeated green answers cheap).
    def test_same_identity_pass_replays_to_a_later_process(self):
        identity = self.identity()
        # `_run` produces the record the cache validates; a red-free run is a
        # PASS record exactly like a real green execution's.
        self.publish(identity, _run([]))
        answer = self.child_answer(identity)
        self.assertTrue(answer.get("reused"))
        self.assertEqual(answer.get("verdict"), "PASS")

    # Row 2: same identity + FAIL replays as FAIL (unchanged-failure loop cut).
    def test_same_identity_fail_replays_to_a_later_process(self):
        identity = self.identity()
        self.publish(identity)
        answer = self.child_answer(identity)
        self.assertTrue(answer.get("reused"))
        self.assertEqual(answer.get("verdict"), "FAIL")

    # Row 3: changed tree fingerprint -> different identity, no replay.
    def test_changed_tree_reexecutes_in_a_later_process(self):
        identity = self.identity()
        self.publish(identity)
        (self.project / "tools" / "test_new.py").write_text(
            "import unittest\n"
            "class NewTests(unittest.TestCase):\n"
            "    def test_x(self):\n"
            "        pass\n",
            encoding="utf-8",
        )
        # The later process asks the NEW fingerprint with NO available record:
        # single_flight must not answer from the old verdict. It must raise
        # out (no published record), which the child reports as launched.
        answer = self.child_answer(self.identity())
        self.assertEqual(answer.get("launched"), 1)

    # Row 4: changed baseline -> the identity's judgment basis changed.
    def test_changed_baseline_reexecutes(self):
        identity = self.identity()
        self.publish(identity)
        (self.project / "tools" / "core_unit_baseline.json").write_text(json.dumps(
            {"schema": 1, "family": "unit",
             "red": ["test_new.NewTests.test_broken"], "recorded_at": "test2",
             "ran": 1, "command": ["python"]}
        ), encoding="utf-8")
        # Same tree bytes, but a red now EXPECTED: the judge's verdict for the
        # replayed record would disagree with the recorded one, so the cache
        # must refuse to re-present it as this baseline's answer.
        answer = self.child_answer(self.identity())
        self.assertEqual(answer.get("launched"), 1)

    # Row 5: changed verification configuration -> different identity.
    def test_changed_configuration_reexecutes(self):
        identity = self.identity()
        self.publish(identity)
        other = self.identity(core_unit.verification_configuration(timeout=257))
        self.assertNotEqual(
            identity["verification_identity"], other["verification_identity"]
        )
        answer = self.child_answer(other)
        self.assertEqual(answer.get("launched"), 1)

    # Row 6: corrupted published bytes -> replay refuses, re-executes.
    def test_corrupted_published_record_never_replays(self):
        identity = self.identity()
        self.publish(identity)
        record_path = next(
            (self.project / ".saipen/evidence/core-unit").glob("*.json")
        )
        raw = json.loads(record_path.read_text(encoding="utf-8"))
        raw["red"] = raw.get("red", []) + ["fabricated.test_red"]
        record_path.write_text(json.dumps(raw), encoding="utf-8")
        answer = self.child_answer(identity)
        self.assertEqual(answer.get("launched"), 1)

    # Row 7: missing published bytes -> replay refuses, re-executes.
    def test_missing_published_record_never_replays(self):
        identity = self.identity()
        self.publish(identity)
        for path in (self.project / ".saipen/evidence/core-unit").glob("*.json"):
            path.unlink()
        answer = self.child_answer(identity)
        self.assertEqual(answer.get("launched"), 1)

    # Row 8: FAIL replay is advisory, never a SHIP authority.
    def test_a_replayed_fail_is_never_a_ship_pass(self):
        identity = self.identity()
        self.publish(identity)
        answer = self.child_answer(identity)
        self.assertEqual(answer.get("verdict"), "FAIL")
        # The FAIL record, reused or not, is exactly what the publication
        # gate must keep refusing: no focused/FAIL record ships a ticket.
        # The gate only engages for a project that DECLARES the family and
        # opts in through the verification policy; a stub of each is enough.
        engine = self.project / "tools/saipen_engine"
        engine.mkdir()
        (engine / "test_runner.py").write_text(
            "def _families():\n    return []\n", encoding="utf-8"
        )
        (self.project / "tools/verification_policy.json").write_text(json.dumps(
            {"schema": 1, "ticket": "focused", "publication": "full"}
        ), encoding="utf-8")
        from saipen_engine.focused_unit import publication_gate  # noqa: E402

        problem = publication_gate(self.project)
        self.assertIsNotNone(
            problem,
            "a FAIL record must never satisfy the publication gate",
        )
        # With only a FAIL record of this tree, the gate demands a full
        # admissible run: the replayed FAIL never stood in for one.
        self.assertIn("full core-unit run", problem)


if __name__ == "__main__":
    unittest.main(verbosity=2)
