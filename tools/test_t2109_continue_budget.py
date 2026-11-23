"""T-2109: a host-bounded continuation never runs unbounded repair inline.

Measured 2026-11-20: ZAICODE kills `saipen continue --json` at 15 s
(SAIPEN_CONTINUE_TIMEOUT_MS) and reports "the SAIPEN launcher did not answer
within 15000ms". The Auto-Doctor's remediation for a measured CURRENT_FAIL is
`saipen work reverify <id>`, which runs the project's own verification command
under the engine's full capture budget, and its revalidation runs the canonical
validator (24 s measured on the SAITULS project). One `cc` on such a project
took 4m37s here -- minutes past the host's kill window.

The contract these tests pin:

* a HOST continuation (the doctor is given a deadline) never starts
  `work reverify` inline; the route's canonical command is returned as the
  ACTION for the turn, with the doctor record saying DEFERRED;
* a spent inline budget defers the validator too, instead of starting a run
  that cannot finish;
* an unbounded caller (no deadline: the doctor's own direct callers) keeps the
  T-1792/T-1818 behavior unchanged;
* the inline validator uses whatever budget is left, never more.
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import conformance as C  # noqa: E402
import saipen as CLI  # noqa: E402


def reverify_route():
    return {
        "emitted": {
            "ok": False,
            "code": "CONFORMANCE_UNHEALTHY",
            "conformance_status": "CURRENT_FAIL",
            "action": "saipen work reverify T-2109",
            "canonical_next_command": "saipen work reverify T-2109",
            "remediation_commands": ["saipen work reverify T-2109"],
            "detail": "closure evidence missing",
        },
        "rc": 1,
    }


def validate_route():
    return {
        "emitted": {
            "ok": False,
            "code": "CONFORMANCE_UNHEALTHY",
            "conformance_status": "STALE_PASS",
            "action": "saipen validate",
            "canonical_next_command": "saipen validate",
            "detail": "STATE hash mismatch",
        },
        "rc": 1,
    }


class BoundedContinuationTests(unittest.TestCase):
    def test_a_host_bounded_reverify_is_deferred_not_executed(self):
        deadline = time.monotonic() + CLI._continue_inline_budget_seconds()
        with mock.patch.object(CLI, "_negotiate_capability", return_value="full"), \
                mock.patch("saipen_engine.debt.reverify_work") as reverify, \
                mock.patch.object(CLI, "_validate") as validator:
            result = CLI._auto_doctor(
                Path("unused"), reverify_route(), None, {"left": 5},
                deadline=deadline,
            )
        reverify.assert_not_called()
        validator.assert_not_called()
        doctor = result["emitted"]["doctor"]
        self.assertEqual(doctor["stage"], "DEFERRED")
        self.assertFalse(doctor["ok"])
        self.assertEqual(doctor["operation"], "work-reverify")
        self.assertEqual(doctor["action"], "saipen work reverify T-2109")
        # The action the agent must execute this turn survives verbatim.
        self.assertEqual(
            result["emitted"]["canonical_next_command"], "saipen work reverify T-2109"
        )
        self.assertEqual(result["rc"], 1)

    def test_a_spent_budget_does_not_start_the_validator(self):
        with mock.patch.object(CLI, "_negotiate_capability", return_value="full"), \
                mock.patch.object(CLI, "_validate") as validator:
            result = CLI._auto_doctor(
                Path("unused"), validate_route(), None, {"left": 5},
                deadline=time.monotonic() - 1.0,
            )
        validator.assert_not_called()
        doctor = result["emitted"]["doctor"]
        self.assertEqual(doctor["stage"], "DEFERRED")
        self.assertEqual(doctor["operation"], "validate")
        self.assertIn("action to execute in this turn", doctor["why_stopped"])

    def test_an_unbounded_caller_keeps_the_inline_repair(self):
        after = {"emitted": None, "rc": 0}
        decision = {
            "status": "CURRENT_PASS", "healthy": True,
            "status_block": {}, "reason": "measured", "remediation_command": None,
            "repair_status": None, "diagnostic": None,
        }

        def validate(*args, **kwargs):
            print(json.dumps({"ok": True, "code": "VALID"}))
            return 0

        with mock.patch.object(CLI, "_negotiate_capability", return_value="full"), \
                mock.patch("saipen_engine.debt.capture_findings", return_value=None), \
                mock.patch("saipen_engine.debt.reverify_work",
                           return_value={"ok": True, "code": "WORK_REVERIFIED"}) as reverify, \
                mock.patch.object(CLI, "_validate", side_effect=validate), \
                mock.patch.object(CLI, "_route_once", return_value=after), \
                mock.patch.object(C, "conformance_decision", return_value=decision):
            result = CLI._auto_doctor(Path("unused"), reverify_route(), None, {"left": 1})
        self.assertEqual(reverify.call_count, 1)
        self.assertEqual(result["doctor"]["stage"], "RESUMING")

    def test_the_inline_validator_gets_the_remaining_budget_not_the_capture_one(self):
        completed = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch("subprocess.run", return_value=completed) as run:
            CLI._run_canonical_validator(Path("unused"), timeout=3.5)
        self.assertEqual(run.call_args.kwargs["timeout"], 3.5)

    def test_the_budget_is_operator_tunable_and_never_disabled(self):
        default = CLI._continue_inline_budget_seconds()
        with mock.patch.dict(os.environ, {"SAIPEN_CONTINUE_INLINE_BUDGET_SECONDS": "3.5"}):
            self.assertEqual(CLI._continue_inline_budget_seconds(), 3.5)
        for unusable in ("", "0", "-1", "garbage", "nan", "inf", "-inf"):
            with self.subTest(value=unusable), \
                    mock.patch.dict(os.environ, {"SAIPEN_CONTINUE_INLINE_BUDGET_SECONDS": unusable}):
                self.assertEqual(CLI._continue_inline_budget_seconds(), default)

    def test_next_action_defers_the_repair_through_the_real_boundary(self):
        output = io.StringIO()
        with mock.patch.object(CLI, "_negotiate_capability", return_value="full"), \
                mock.patch("saipen_engine.debt.reverify_work") as reverify, \
                mock.patch.object(CLI, "_validate") as validator, \
                mock.patch.object(CLI, "_route_once", return_value=reverify_route()), \
                redirect_stdout(output):
            rc = CLI._next_action(
                Path("unused"), True, fallthrough_to_improve=True
            )
        self.assertEqual(rc, 1)
        result = json.loads(output.getvalue())
        self.assertEqual(result["doctor"]["stage"], "DEFERRED")
        self.assertEqual(result["canonical_next_command"], "saipen work reverify T-2109")
        reverify.assert_not_called()
        validator.assert_not_called()


if __name__ == "__main__":
    unittest.main()
