"""T-1584: the production ZCode host must not be adapter-registry silence.

The T-1583 incident (a STYLE-breaking reply escaping on the live production
host) proved the production ZCode CLI reaches the model as instructions only,
yet the host class had no registry entry -- so every boundary report (the
guard's no-target status projection, effective_strength) answered "unknown
host adapter", which reads as silence about the real limit. These controls
pin the honest registration: ADVISORY response enforcement, no hook surface,
production home surfaces, and a projection that names the boundary.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.admission import (  # noqa: E402
    ADAPTER_REGISTRY,
    effective_strength,
)

REGISTRY_PATH = REPO / "extensions" / "adapters" / "registry.json"


def registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


class ProductionZcodeBoundaryTests(unittest.TestCase):
    def test_registry_entry_states_the_true_boundary(self):
        entry = ADAPTER_REGISTRY.get("zcode-production")
        self.assertIsNotNone(entry, "production ZCode host is registry silence")
        # The two fields the incident verdict turned on: the response ceiling
        # is instructions-only, and no hook surface exists to install.
        self.assertEqual(entry["response_enforcement"], "ADVISORY")
        self.assertIsNone(entry["hook_install_surface"])
        self.assertIsNone(entry["hook_artifact"])
        self.assertFalse(entry["blocking_capability"])
        self.assertEqual(entry["declared_strength"], "ADVISORY")
        # The production home is the REAL ~/.zcode, not the dev $ZAICODE_HOME.
        self.assertIn("~/.zcode/AGENTS.md", entry["instruction_surfaces"])
        self.assertIn("~/.agents/skills/saipen", entry["skill_surfaces"])
        # Closed vocabulary, not free text: the first insert of this entry
        # shipped a typo'd CANANONICAL_RUNTIME_STATUS that no assertion saw.
        caps = entry["execution_capabilities"]
        self.assertEqual(caps["structured_progress"], "CANONICAL_RUNTIME_STATUS")
        self.assertEqual(caps["final_response_gate"], "ADVISORY")

    def test_effective_strength_is_not_unknown_host_adapter(self):
        # Pre-fix silence: an unregistered host answers ENFORCEMENT_GAP /
        # "unknown host adapter", which reports nothing true about it. The
        # registered answer must degrade truthfully instead.
        verdict = effective_strength("zcode-production")
        self.assertNotEqual(verdict["reason"], "unknown host adapter")
        self.assertEqual(verdict["effective"], "ADVISORY")

    def test_guard_status_projection_reports_the_boundary(self):
        # The canonical report the operator reads: the real CLI's no-target
        # guard projection (saipen.py guard). Read-only -- it journals nothing.
        proc = subprocess.run(
            [sys.executable, str(REPO / "tools" / "saipen.py"), "guard", "--json"],
            capture_output=True,
            text=True,
            cwd=str(REPO),
            timeout=180,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        view = json.loads(proc.stdout)
        reported = (view.get("adapters") or {}).get("zcode-production")
        self.assertIsNotNone(
            reported, "guard status projection is silent about production ZCode"
        )
        self.assertEqual(reported["response_enforcement"], "ADVISORY")
        self.assertEqual(reported["effective"], "ADVISORY")
        self.assertIsNone(reported["response_hook"])

    def test_dev_zaicode_entry_stays_a_distinct_isolated_home(self):
        # Production registration must not collapse the two homes: the dev
        # entry stays variable-guarded ($ZAICODE_HOME), so an unset variable
        # still means "ZAICODE dev runs are not configured on this machine".
        dev = ADAPTER_REGISTRY.get("zaicode")
        self.assertIsNotNone(dev)
        self.assertEqual(dev["instruction_surfaces"], ["$ZAICODE_HOME/.zcode/AGENTS.md"])
        self.assertEqual(dev["skill_surfaces"], ["$ZAICODE_HOME/.zcode/skills/saipen"])
        # One authority: the shipped file and the loaded registry agree.
        self.assertEqual(
            {e["id"] for e in registry()["adapters"]}, set(ADAPTER_REGISTRY)
        )


if __name__ == "__main__":
    unittest.main()
