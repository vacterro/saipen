"""Same oracle for the adjacent public goal-entry authority bypass."""
from pathlib import Path
import contextlib
import io
import json
import os
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import codec, operator_task, pending_ingress
from saipen_engine.operations import goal_entry
from saipen_engine.state import parse_state
from test_t1363_zero_manual_entry import healthy
from test_operator_task_witness import start


class GoalAuthority(unittest.TestCase):
    def test_unwitnessed_goal_cannot_preempt_or_reset_trusted_work(self):
        project = healthy(self)
        text = "fix the importer and verify its acceptance"
        rc, payload, output = start(project, text, **{
            operator_task.ENV_TASK_SHA256: pending_ingress.ingress_digest(text)
        })
        self.assertEqual(rc, 0, output)
        before = parse_state(codec.read_doc(project / ".saipen/STATE.md"))
        with patch.dict(os.environ, {}, clear=True):
            result = goal_entry(project, "test-agent", "refactor authentication and run all tests")
        after = parse_state(codec.read_doc(project / ".saipen/STATE.md"))
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(after["task"], payload["ticket"], result.to_dict())
        for field in ("execution_intent", "goal_waves", "goal_tickets"):
            self.assertEqual(before.get(field), after.get(field), field)


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "run"
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(GoalAuthority)
        )
    (Path(__file__).parent / f"goal-{label}.txt").write_text(stream.getvalue(), encoding="utf-8")
    print(stream.getvalue())
    raise SystemExit(0 if result.wasSuccessful() else 1)
