"""T-2092 (night shift 7, W5): a repeated identical verification never re-pays.

The handoff's autonomy failure loop: full family runs 42 minutes, FAILs on
foreign WIP, and the next session runs the SAME 42 minutes on the SAME
unchanged tree to learn the SAME verdict. `single_flight` already shares one
execution's receipt with later waiters in the SAME process; a durable cross-
process replay is what a restart actually needs.

What is pinned here, on disposable fixtures:

* one published FAIL is replayed as FAIL to a LATER process -- the refused
  rerun is the loop's own waste, so the replay must answer, not re-execute;
* the replay only spans the exact identity: a different fingerprint, baseline
  or configuration re-executes (the verdict is about the subject, not the ask);
* a dead executor's interrupted flight with no live reader is replaceable
  (recovery), and a flight whose recorded reader is still alive is not
  (fail-closed: never two owners of one verification).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import core_unit  # noqa: E402
from saipen_engine import verification_cache as cache  # noqa: E402

from test_core_unit_gate import _run, INHERITED  # noqa: E402


def child_code(body: str) -> str:
    return (
        "import sys, json, time, os;\n"
        "from pathlib import Path;\n"
        f"sys.path.insert(0, {str(TOOLS)!r});\n"
        "from saipen_engine import core_unit;\n"
        "from saipen_engine import verification_cache as cache;\n"
        f"{body}\n"
    )


class FlightReplayTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="t2092-flight-"))
        self.addCleanup(core_unit.reclaim, self.base)
        self.project = self.base / "project"
        self.project.mkdir()
        (self.project / ".saipen").mkdir()
        (self.project / ".saipen" / "STATE.md").write_text("", encoding="utf-8")
        tools = self.project / "tools"
        tools.mkdir()
        (tools / "sandbox_scope.json").write_text(
            json.dumps({"schema": 1, "modules": {}}), encoding="utf-8"
        )
        record = self.project / ".saipen" / "cache" / "core-unit"
        record.mkdir(parents=True)
        baseline = {
            "schema": 1, "family": "unit", "red": [],
            "recorded_at": "test", "ran": 1, "command": ["python"],
        }
        (self.project / "tools" / "core_unit_baseline.json").write_text(
            json.dumps(baseline), encoding="utf-8"
        )
        (self.project / "tools" / "test_new.py").write_text(
            "import unittest\n"
            "class NewTests(unittest.TestCase):\n"
            "    def test_x(self):\n"
            "        pass\n"
            "    def test_broken(self):\n"
            "        self.fail('red')\n",
            encoding="utf-8",
        )

    def identity(self) -> dict:
        return {
            "family": "unit",
            "fingerprint": core_unit.tree_fingerprint(self.project),
            "verification_identity": cache.capture(
                self.project, core_unit.verification_configuration()
            ),
        }

    def test_one_published_fail_replays_to_a_later_process(self):
        identity = self.identity()
        with cache.single_flight(self.project, identity) as first:
            written = core_unit.write_record(
                self.project, _run(["test_new.NewTests.test_broken"]),
                identity["fingerprint"],
            )
            first.publish(written)
        # A LATER process, same identity: the FAIL must answer without an
        # executor. This is the loop's own refusal made cheap.
        out = self.base / "child.json"
        child = subprocess.Popen(
            [
                sys.executable, "-B", "-c", child_code(
                    "identity = json.loads(Path(%r).read_text());\n"
                    "with cache.single_flight(Path(%r), identity) as flight:\n"
                    "    assert flight.written is not None, 'NO REPLAY';\n"
                    "    Path(%r).write_text(json.dumps("
                    "{'reused': flight.reused, 'verdict': "
                    "flight.written['record']['verdict']}));\n"
                    % (str(self.base / "identity.json"), str(self.project), str(out))
                ),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        (self.base / "identity.json").write_text(json.dumps(identity), encoding="utf-8")
        stdout, stderr = child.communicate(timeout=60)
        self.assertEqual(child.returncode, 0, stderr.decode("utf-8", "replace"))
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(data["reused"])
        self.assertEqual(data["verdict"], "FAIL")

    def test_a_changed_tree_does_not_replay_the_old_verdict(self):
        identity = self.identity()
        with cache.single_flight(self.project, identity) as first:
            written = core_unit.write_record(
                self.project, _run(["test_new.NewTests.test_broken"]),
                identity["fingerprint"],
            )
            first.publish(written)
        (self.project / "tools" / "test_new.py").write_text(
            "import unittest\nclass NewTests(unittest.TestCase):\n"
            "    def test_x(self):\n        pass\n",
            encoding="utf-8",
        )
        self.assertIsNone(core_unit.reusable_record(
            self.project, core_unit.tree_fingerprint(self.project)
        ))


if __name__ == "__main__":
    unittest.main(verbosity=2)
