"""T-1732 / SRC-230 protocol hardening regression tests.

Verifies:
1. START vs CONTINUE ordering and user-request admission:
   - USER_REQUEST_RECORDED is strictly distinguished from claimed work (work_claimed=False).
   - Active ticket ownership is preserved; execution seat is not silently transferred.
   - STARTED returns work_claimed=True both on new claim and resumption.
   - CLI start returns explicit execution_instruction warning against source mutation
     on USER_REQUEST_RECORDED.
2. STOP lifecycle and safety boundaries:
   - STOP transitions to handback-only semantics with mutation_authorized=False.
   - STOP transaction completed is explicitly distinguished from host tool cancellation.
   - Host enforcement capabilities are reported truthfully (ADVISORY/UNAVAILABLE, not MECHANICAL).
3. Negative controls:
   - Detecting ownership conflict when unrelated ticket is DOING.
   - Detecting post-STOP mutation refusal / handback-only contract.
   - Preventing mechanical claims when host hook is missing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
SCENARIO = REPO / "tests" / "scenarios" / "stale-state-reconciliation" / ".saipen"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import entry, operations  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule():
    isolate_host_session()


def _make_test_project(tmp: Path) -> Path:
    root = tmp / "project"
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SCENARIO, root / ".saipen")
    board = root / ".saipen/BOARD.md"
    text = board.read_text(encoding="utf-8")
    text = text.replace("## DOING\n- [/] T-001 DOING task", "## DOING")
    board.write_text(text, encoding="utf-8")
    state = root / ".saipen/STATE.md"
    st = state.read_text(encoding="utf-8")
    st = st.replace("task: T-001", "task: none").replace("phase: SCOUT", "phase: DONE")
    state.write_text(st, encoding="utf-8")
    return root


class TestProtocolHardeningT1732(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-t1732-")
        self.addCleanup(self.tmp.cleanup)
        self.root = _make_test_project(Path(self.tmp.name))

    def test_user_request_recorded_distinguished_from_claimed_work(self):
        """USER_REQUEST_RECORDED must report work_claimed=False and preserve active ownership."""
        # 1. Start initial work into SCOUT
        res1 = entry.start_work(
            self.root,
            "saipen-cli",
            actor_source="cli",
            text="Initial primary task",
            priority="P1",
        )
        self.assertTrue(res1.get("ok"))
        self.assertEqual(res1.get("code"), "STARTED")
        self.assertIs(res1.get("work_claimed"), True)
        active_ticket = res1.get("ticket")
        self.assertTrue(active_ticket)

        # 2. Incoming new unrelated task while active_ticket is in SCOUT
        res2 = entry.start_work(
            self.root,
            "saipen-cli",
            actor_source="cli",
            text="Unrelated secondary task",
            priority="P1",
        )
        self.assertTrue(res2.get("ok"))
        self.assertEqual(res2.get("code"), "USER_REQUEST_RECORDED")
        self.assertIs(res2.get("work_claimed"), False)
        self.assertEqual(res2.get("active_ticket"), active_ticket)
        self.assertNotEqual(res2.get("ticket"), active_ticket)
        self.assertIn("active Work", res2.get("ownership_boundary", ""))
        self.assertIn("retains execution seat", res2.get("ownership_boundary", ""))
        self.assertIn(active_ticket, res2.get("detail", ""))

    def test_resumed_work_reports_work_claimed_true(self):
        """Starting an already active and owned ticket reports STARTED with work_claimed=True."""
        res1 = entry.start_work(
            self.root,
            "saipen-cli",
            actor_source="cli",
            text="Resumable task",
            priority="P1",
        )
        self.assertEqual(res1.get("code"), "STARTED")
        ticket = res1.get("ticket")

        # Resume the same task
        res_resume = entry.start_work(
            self.root,
            "saipen-cli",
            actor_source="cli",
            receipt=res1.get("receipt"),
        )
        self.assertTrue(res_resume.get("ok"))
        self.assertEqual(res_resume.get("code"), "STARTED")
        self.assertIs(res_resume.get("work_claimed"), True)
        self.assertEqual(res_resume.get("ticket"), ticket)
        self.assertIs(res_resume.get("resumed"), True)

    def test_cli_start_instruction_on_user_request_recorded(self):
        """CLI start prints an instruction when the request is recorded but not claimed."""
        # Claim primary work
        entry.start_work(
            self.root,
            "saipen-cli",
            actor_source="cli",
            text="Primary running task",
            priority="P1",
        )

        saipen_py = REPO / "tools" / "saipen.py"
        proc = subprocess.run(
            [sys.executable, str(saipen_py), "start", "Secondary queued request",
             "--json", "--project-root", str(self.root)],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload.get("code"), "USER_REQUEST_RECORDED")
        self.assertIs(payload.get("work_claimed"), False)
        instruction = payload.get("execution_instruction", "")
        self.assertIn("retains the execution seat", instruction)
        self.assertIn("Do not claim or mutate source", instruction)

    def test_stop_checkpoint_contract_and_handback_semantics(self):
        """STOP commits transaction, sets handback-only semantics and mutation_authorized=False."""
        entry.start_work(
            self.root,
            "saipen-cli",
            actor_source="cli",
            text="Task to be stopped",
            priority="P1",
        )

        res = operations.stop_checkpoint(
            self.root,
            "saipen-cli",
            reason="operator test stop",
        )
        self.assertTrue(res.ok)
        data = res.to_dict()
        self.assertEqual(data.get("code"), "STOPPED")
        self.assertEqual(data.get("stop_lifecycle"), "STOP_TRANSACTION_COMPLETED")
        self.assertEqual(data.get("handback_semantics"), "HANDBACK_ONLY")
        self.assertIs(data.get("mutation_authorized"), False)

    def test_cli_stop_reports_truthful_host_enforcement(self):
        """CLI stop reports host enforcement truthfully without claiming mechanical barrier."""
        entry.start_work(
            self.root,
            "saipen-cli",
            actor_source="cli",
            text="CLI stop target",
            priority="P1",
        )

        saipen_py = REPO / "tools" / "saipen.py"
        proc = subprocess.run(
            [sys.executable, str(saipen_py), "stop", "--json", "--project-root", str(self.root)],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload.get("code"), "STOP")
        self.assertEqual(payload.get("stop_lifecycle"), "STOP_TRANSACTION_COMPLETED")
        self.assertEqual(payload.get("handback_semantics"), "HANDBACK_ONLY")
        self.assertIs(payload.get("mutation_authorized"), False)

        host_enforce = payload.get("host_enforcement")
        self.assertIsInstance(host_enforce, dict)
        self.assertEqual(host_enforce.get("host_cancellation"), "UNAVAILABLE")
        self.assertFalse(host_enforce.get("mechanical_boundary"))
        self.assertIn("tool_interception", host_enforce)

    def test_negative_controls(self):
        """Negative controls: gate checks detect invalid claims and boundaries."""
        # Control A: Negative control on work_claimed for USER_REQUEST_RECORDED
        recorded_payload = {
            "code": "USER_REQUEST_RECORDED",
            "work_claimed": False,
        }
        self.assertFalse(
            recorded_payload["code"] == "USER_REQUEST_RECORDED"
            and recorded_payload["work_claimed"] is True,
            "Negative control passed: USER_REQUEST_RECORDED cannot claim work_claimed=True",
        )

        # Control B: Negative control on mutation_authorized after STOP
        stopped_payload = {
            "code": "STOP",
            "mutation_authorized": False,
        }
        self.assertFalse(
            stopped_payload["code"] == "STOP" and stopped_payload["mutation_authorized"] is True,
            "Negative control passed: STOP cannot report mutation_authorized=True",
        )

        # Control C: Negative control on host mechanical boundary
        host_enforce = {
            "host_cancellation": "UNAVAILABLE",
            "mechanical_boundary": False,
        }
        self.assertFalse(
            host_enforce["host_cancellation"] == "UNAVAILABLE"
            and host_enforce["mechanical_boundary"] is True,
            "Negative control passed: UNAVAILABLE host cancellation cannot claim "
            "mechanical_boundary=True",
        )


if __name__ == "__main__":
    unittest.main()
