"""Next-Work RED preparation only: no production or live checkpoint edits.

Run the actual canonical launcher over owned disposable projects. These controls
are not a complete T-1494 acceptance suite and grant no operator authority.
"""

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
sys.path.insert(0, str(ROOT / "tools"))

from test_reconcile_valve import ReconcileEndToEndTests, WAIT_FORM
from test_hermetic_env import isolate_host_session
from saipen_engine.state import parse_state


def setUpModule():
    isolate_host_session()


class BoundedContinuationControls(unittest.TestCase):
    def fixture(self):
        factory = ReconcileEndToEndTests("test_a_state_already_paused_at_the_cap_is_clean")
        root = factory._make_project(20, WAIT_FORM)
        absolute = root.resolve()
        assert absolute.parent == Path(tempfile.gettempdir()).resolve()
        assert absolute.name.startswith("t1181-valve-") and not root.is_symlink()
        self.addCleanup(factory.doCleanups)
        board = root / ".saipen/BOARD.md"
        stamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        board.write_text(
            board.read_text(encoding="utf-8").replace(
                "| verify: test", "| verify: test | owner: tester | claim_time: " + stamp
            ),
            encoding="utf-8",
        )
        return root

    def check_command(self, token):
        root = self.fixture()
        canonical = tuple(root / ".saipen" / name for name in ("STATE.md", "BOARD.md", "LOG.md"))
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in canonical}
        argv = [str(ROOT / "bin/saipen.cmd"), token, "--project-root", str(root), "--agent", "tester", "--json"]
        if os.name == "nt":
            argv = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *argv]
        env = {k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        run = subprocess.run(argv, capture_output=True, timeout=120, env=env)
        observed = parse_state(canonical[0].read_text(encoding="utf-8"))
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in canonical}
        record = {
            "kind": "unclaimed-next-work-red-control",
            "command": token,
            "original_operator_carrier": False,
            "returncode": run.returncode,
            "stdout": run.stdout.decode("utf-8", errors="replace"),
            "stderr": run.stderr.decode("utf-8", errors="replace"),
            "before": before,
            "after": after,
            "after_tickets": observed.get("goal_tickets"),
            "after_next_action": observed.get("next_action"),
            "fixture_root": str(root),
        }
        (HERE / f"{token}-before.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(observed.get("goal_tickets"), 20, record)
        self.assertEqual(observed.get("next_action"), WAIT_FORM, record)
        self.assertEqual(after, before, record)

    def test_agent_continue_cannot_renew_a_bounded_budget(self):
        self.check_command("continue")

    def test_agent_cc_is_not_itself_an_original_operator_carrier(self):
        self.check_command("cc")


if __name__ == "__main__":
    unittest.main()
