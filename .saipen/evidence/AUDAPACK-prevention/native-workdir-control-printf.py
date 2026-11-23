"""Sacrificial native OpenCode counterexample; never touches AUDAPACK."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
import test_opencode_bound_launch_smoke as smoke


def setUpModule():
    smoke.setUpModule()


class NativeWorkdirControl(smoke.BoundOpenCodeNativeSmoke):
    def test_workdir_cannot_hide_a_canonical_append(self):
        root = smoke.project_with_doing_owner("test-agent", agent="test-agent")
        log = root / ".saipen" / "LOG.md"
        before = log.read_bytes()
        actions = [("bash", {
            "command": 'printf "typed completion" >> LOG.md',
            "workdir": str(root / ".saipen"),
            "description": "Sacrificial canonical append prevention control",
        })]
        proc, _probe, requests = self._launch(root, None, actions)
        unchanged = log.read_bytes() == before
        self.assertTrue(
            unchanged and smoke._provider_reports_tool_code(
                requests, "PROTECTED_CANONICAL_NAMESPACE"
            ),
            {"canonical_bytes_unchanged": unchanged, "returncode": proc.returncode,
             "requests": requests, "output": proc.stdout + proc.stderr},
        )


if __name__ == "__main__":
    unittest.main()
