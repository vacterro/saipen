"""The native hook gives origin recovery, worker binding and renewal one budget."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import time
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import host_authority_client as client  # noqa: E402


def guard_module():
    path = ROOT / "extensions" / "adapters" / "zaicode" / "saipen-guard.py"
    spec = importlib.util.spec_from_file_location("saipen_guard_t1913_budget", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HookDeadlineTests(unittest.TestCase):
    def test_expired_deadline_does_not_contact_broker(self):
        with mock.patch.object(client, "_exchange") as exchange:
            answer, fault = client.issue_operator_origin(
                project=ROOT, session="s", host="zaicode", request_text="cc all",
                event_id="native-1", action="continue", diagnose=True,
                deadline=time.monotonic() - 1,
            )
        exchange.assert_not_called()
        self.assertEqual(fault, "timeout")
        self.assertEqual(answer["code"], "BROKER_RECOVERY_TIMEOUT")

    def test_impostor_arriving_during_recovery_cannot_start_service(self):
        with mock.patch.object(client, "_exchange", side_effect=[
            (None, "absent"), (None, "impostor"),
        ]) as exchange, mock.patch.object(client.broker, "spawn") as spawn:
            answer, fault = client.issue_operator_origin(
                project=ROOT, session="s", host="zaicode", request_text="cc all",
                event_id="native-1", action="continue", diagnose=True,
                deadline=time.monotonic() + 5,
            )
        self.assertEqual(fault, "impostor")
        self.assertEqual(answer["code"], client.CODE_SERVER_UNPROVEN)
        self.assertEqual(answer["recovery"]["state"], "impostor")
        self.assertEqual(exchange.call_count, 2)
        spawn.assert_not_called()

    def test_worker_exchange_uses_remaining_budget(self):
        with mock.patch.object(client, "_exchange", return_value=({"ok": True}, None)) as exchange:
            answer, fault = client.register_operator_worker(
                {"host": "zaicode"}, 42, deadline=time.monotonic() + 0.25,
                diagnose=True,
            )
        self.assertTrue(answer["ok"])
        self.assertIsNone(fault)
        self.assertGreater(exchange.call_args.kwargs["timeout"], 0)
        self.assertLessEqual(exchange.call_args.kwargs["timeout"], 0.25)

    def test_hook_passes_same_deadline_through_seal_and_renewal(self):
        guard = guard_module()
        args = Namespace(host="zaicode", saipen_root=ROOT, home=None, self_test=False)
        event = {"host_ingress": {"request_text": "cc all", "message_id": "native-1"},
                 "session_id": "s", "cwd": str(ROOT)}
        origin = {"ok": True, "proof": {"kind": "operator-origin", "host": "zaicode"}}
        output = io.StringIO()
        with mock.patch.object(guard, "read_command_line", return_value=(args, None)), \
                mock.patch.object(guard, "project_root", return_value=ROOT), \
                mock.patch.object(guard.sys, "stdin", io.StringIO(json.dumps(event))), \
                mock.patch.object(client, "issue_operator_origin", return_value=(origin, None)) as issue, \
                mock.patch.object(client, "register_operator_worker", return_value=({"ok": True}, None)) as worker, \
                mock.patch("saipen_engine.operator_task.admit_host_ingress",
                           return_value={"ok": True, "destination_op": "continue"}), \
                mock.patch.object(guard, "_valve_tripped", return_value=True), \
                mock.patch.object(guard, "_renew", return_value={"ok": True}) as renew, \
                contextlib.redirect_stdout(output):
            self.assertEqual(guard.main(), 0)
        deadlines = [issue.call_args.kwargs["deadline"],
                     worker.call_args.kwargs["deadline"],
                     renew.call_args.kwargs["deadline"]]
        self.assertEqual(deadlines, [deadlines[0]] * 3)
        self.assertTrue(json.loads(output.getvalue())["sealed"])


if __name__ == "__main__":
    unittest.main()
