"""Probe: what the boundary route's explain-next now reports."""

from __future__ import annotations

import json
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_conformance_repair_boundary as B  # noqa: E402
import test_t1412_conformance_truth as fixtures  # noqa: E402


class Probe(B.RealValidatorBoundaryTests):
    def runTest(self):
        root, home = self.installed_fixture(False)
        with patch.object(fixtures, "SAIPEN_CLI", home / "tools/saipen.py"):
            rc, payload, text = self.run_cli(root, "validate")
            print("validate rc", rc, "canonical_next_command",
                  repr(payload.get("canonical_next_command")))
            print("diagnostic kind", payload.get("diagnostic", {}).get("kind"))
            for command in ("next", "continue", "status", "explain-next"):
                _, current, output = self.run_cli(root, command)
                print(command, json.dumps({
                    "disposition": current.get("disposition"),
                    "automation_disposition": (current.get("automation") or {}).get("disposition"),
                    "canonical_next_command": current.get("canonical_next_command"),
                    "action": current.get("action"),
                    "human_required": current.get("human_required"),
                }, sort_keys=True))


if __name__ == "__main__":
    suite = unittest.TestSuite()
    suite.addTest(Probe())
    runner = unittest.TextTestRunner(verbosity=0)
    runner.run(suite)