"""T-1750: a no-publish release gate settles what it refused and runs only its own validator.

Two defects measured on a disposable copy of a downstream project (T-1746
evidence, REPORT.md sections 7 and 9):

* a refused local validation returned stage NO_PUBLISH but left its operation
  PREPARED, so the next release answered RECOVERY_REQUIRED until `saipen
  recover` aborted an operation that had written nothing -- a recovery step
  manufactured by the refusal itself;
* `_gate_command` preferred any `tools/validate.py` in the project, so a
  managed project owning an unrelated script of that name ran it as its
  release gate.

The gate runs before the first closure target is appended, so its refusal
settles the operation exactly as recovery settles a PREPARED op with zero
targets. A refusal after a target landed still belongs to recovery.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_source_receipts as fixtures  # noqa: E402
from saipen_engine import release  # noqa: E402
from saipen_engine.journal import scan_pending  # noqa: E402
from test_t1746_crew_terminal_outcome import _DownstreamShape  # noqa: E402

RED_GATE = {"ok": False, "detail": "FAIL: fixture"}


class RefusedGateTests(_DownstreamShape):
    def _pending(self) -> list[str]:
        pending, conflicts = scan_pending(self.root)
        return [str(item.get("op_id")) for item in [*pending, *conflicts]]

    def _refused(self, plan) -> dict:
        ready, _gate, parity = self._patches()
        red = patch.object(release, "_run_gate", return_value=RED_GATE)
        with ready, red, parity:
            return release.execute_release(self.root, plan)

    def test_a_refused_gate_settles_its_own_operation(self):
        self._shape()
        plan = self._plan()
        canonical = self._canonical()
        refused = self._refused(plan)
        self.assertFalse(refused["ok"], refused)
        self.assertEqual(refused["stage"], "NO_PUBLISH", refused)
        self.assertNotIn(plan.op_id, self._pending())
        self.assertEqual(self._canonical(), canonical)
        # The next attempt plans and closes without a recover step.
        _closed, result = self._close()
        self.assertTrue(result["ok"], result)

    def test_a_refusal_after_a_target_landed_still_needs_recovery(self):
        self._shape()
        plan = self._plan()
        original = release._mark_target

        def refuse_after_first(journal, index):
            original(journal, index)
            raise release.ReleaseRefusal("RELEASE_FAILED", "fixture: refused mid-closure")

        ready, gate, parity = self._patches()
        mark = patch.object(release, "_mark_target", side_effect=refuse_after_first)
        with ready, gate, parity, mark:
            refused = release.execute_release(self.root, plan)
        self.assertFalse(refused["ok"], refused)
        self.assertIn(plan.op_id, self._pending())
        self.assertEqual(self._refusal().code, "RECOVERY_REQUIRED")


class GateCommandTests(_DownstreamShape):
    def test_an_unrelated_project_script_is_not_the_release_gate(self):
        self._shape()
        (self.root / "tools").mkdir(exist_ok=True)
        (self.root / "tools" / "validate.py").write_text(
            "raise SystemExit(0)\n", encoding="utf-8"
        )
        command = release._gate_command(self.root, "core")
        validator = fixtures.ROOT / "tools" / "validate.py"
        self.assertEqual(
            command[1:], [str(validator), "--project-root", str(self.root), "--gate", "core"]
        )

    def test_the_running_home_validates_itself(self):
        command = release._gate_command(fixtures.ROOT, "ship")
        self.assertEqual(command[1:], [str(fixtures.ROOT / "tools" / "validate.py"), "--gate", "ship"])


if __name__ == "__main__":
    unittest.main()
