"""Budget policy parity and read-only import cost (SRC-289 W5/W7)."""
from __future__ import annotations
import json
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

PROBE = r'''import json, sys, time
from pathlib import Path
start = time.perf_counter()
from saipen_engine.state import goal_valve_wait_is_proven
values = {"execution_intent":"goal","goal_waves":3,"goal_tickets":20,
          "next_action":"WAIT: safety valve reached (3 waves / 20 tickets) -- run 'cc' to continue"}
proof = goal_valve_wait_is_proven(values, {"goal_waves":3,"goal_tickets":20})
modules = sorted(name for name in sys.modules if name.startswith("saipen_engine."))
represented = sum(Path(sys.modules[name].__file__).stat().st_size
                  for name in modules if getattr(sys.modules[name], "__file__", None))
print(json.dumps({"proof":proof, "writer_engine_loaded":"saipen_engine.operations" in sys.modules,
                  "module_count":len(modules), "represented_source_bytes":represented,
                  "elapsed_seconds":time.perf_counter()-start, "modules":modules}))
'''

class BudgetOwnerTests(unittest.TestCase):
    def test_boundary_matrix_preserves_bounded_goal_semantics(self):
        from saipen_engine import goal_authority, router
        for intent in ("normal", "converge", "goal"):
            for waves in (0, 2, 3, 4):
                for tickets in (0, 19, 20, 25):
                    state = {"execution_intent":intent, "goal_waves":waves, "goal_tickets":tickets}
                    expected = intent == "goal" and (waves >= 3 or tickets >= 20)
                    with self.subTest(state=state):
                        self.assertEqual(router._goal_valve_exhausted(state), expected)
                        description = goal_authority.describe(TOOLS / "nonexistent-fixture", state)
                        self.assertEqual(description["checkpoint_due"], expected)

    def test_public_operations_caps_are_preserved(self):
        from saipen_engine.operations import GOAL_TICKET_CAP, GOAL_WAVE_CAP
        self.assertEqual((GOAL_WAVE_CAP, GOAL_TICKET_CAP), (3, 20))

    def test_read_only_boundary_proof_does_not_import_mutation_engine(self):
        run = subprocess.run(
            [sys.executable, "-B", "-c", PROBE], cwd=TOOLS, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=30, check=False,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertTrue(result["proof"])
        self.assertFalse(result["writer_engine_loaded"], result)

if __name__ == "__main__":
    unittest.main()

