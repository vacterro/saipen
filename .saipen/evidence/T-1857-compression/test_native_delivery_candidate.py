"""Candidate protocol tests with explicit ports; NOT native LIVE evidence."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(HERE)]
subject = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "native_delivery_candidate.py"
sys.argv = sys.argv[:1]
spec = importlib.util.spec_from_file_location("native_delivery_candidate", subject)
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="saipen-native-candidate-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        worker = self.root / "tools/native_operator_worker.py"
        worker.parent.mkdir()
        worker.write_text("# placeholder never executed by test ports\n", encoding="utf-8")
        self.event = {
            "event": "UserPromptSubmit", "host": "zaicode", "cwd": str(self.root),
            "session_id": "native-session", "host_ingress": {
                "message_id": "actual-accepted-message-id", "session_id": "native-session",
                "request_text": "cc",
            },
        }
        self.proof = {
            "kind": "operator-origin", "action": "continue", "host": "zaicode",
            "session": "native-session", "event_id": "actual-accepted-message-id",
            "nonce": "fixture-only-not-a-native-MAC",
        }

    def packet(self):
        return {**candidate.checked_input(self.event), "operator_origin": self.proof}

    def test_malformed_native_event_never_issues_or_spawns(self):
        for update in ({"event": "before_tool"}, {"session_id": ""}):
            event = {**self.event, **update}
            client, tree = Mock(), Mock()
            result = candidate.deliver(event, self.root, client=client, tree_factory=tree)
            self.assertFalse(result["ok"])
            client.issue_operator_origin.assert_not_called()
            tree.assert_not_called()
        self.event["host_ingress"]["message_id"] = None
        with self.assertRaises(ValueError):
            candidate.checked_input(self.event)

    def test_issuer_refusal_and_malformed_reply_never_spawn(self):
        for reply in (None, {}, {"ok": False}, "not a broker object"):
            with self.subTest(reply=reply):
                client, tree = Mock(), Mock()
                client.issue_operator_origin.return_value = reply
                result = candidate.deliver(self.event, self.root, client=client, tree_factory=tree)
                self.assertFalse(result["ok"])
                tree.assert_not_called()

    def producer_ports(self, *, register=True):
        order = []
        client = Mock()
        client.issue_operator_origin.side_effect = lambda **kw: (
            order.append(("issue", kw)) or {"ok": True, "proof": self.proof})
        client.register_operator_worker.side_effect = lambda proof, pid: (
            order.append(("register", pid)) or {"ok": register})
        child = Mock(pid=231)
        child.poll.return_value = None
        child.returncode = 0

        def communicate(raw, timeout):
            order.append(("send", json.loads(raw)))
            return json.dumps({"ok": True, "sealed": True,
                               "continuation": {"exit_code": 1, "answer": {"ok": False}}}).encode(), b""

        child.communicate.side_effect = communicate
        owned = Mock()

        def start(argv, **options):
            order.append(("spawn", argv))
            self.spawn_options = options
            self.assertEqual(options["stdin"], candidate.subprocess.PIPE)
            options["on_started"](child)
            return child

        owned.start.side_effect = start
        factory = Mock()
        factory.return_value.__enter__ = Mock(return_value=owned)
        factory.return_value.__exit__ = Mock(return_value=False)
        return order, client, child, factory

    def test_fresh_native_input_does_not_inherit_an_old_task_carrier(self):
        order, client, child, factory = self.producer_ports()
        with patch.dict(candidate.os.environ, {
            "SAIPEN_TASK_FILE": "old-session-task.txt",
            "SAIPEN_TASK_SHA256": "a" * 64,
            "SAIPEN_HOST_SESSION": "old-session",
        }):
            result = candidate.deliver(self.event, self.root, client=client, tree_factory=factory)
        self.assertTrue(result["ok"])
        environment = self.spawn_options.get("env", {})
        self.assertNotIn("SAIPEN_TASK_FILE", environment)
        self.assertEqual(environment.get("SAIPEN_TASK_SHA256"), candidate.ingress_digest("cc"))
        self.assertEqual(environment.get("SAIPEN_HOST_SESSION"), "native-session")

    def test_actual_created_worker_is_bound_before_any_packet(self):
        order, client, child, factory = self.producer_ports()
        answer = candidate.deliver(self.event, self.root, client=client, tree_factory=factory)
        self.assertEqual([name for name, _ in order], ["issue", "spawn", "register", "send"])
        self.assertEqual(order[2][1], child.pid)
        self.assertEqual(order[3][1]["request_text"], "cc")
        self.assertEqual(order[3][1]["event_id"], "actual-accepted-message-id")
        self.assertEqual(answer["continuation"]["answer"], {"ok": False})
        client.revoke_operator_origin.assert_not_called()

    def test_registration_failure_sends_nothing_and_revokes_unconsumed_proof(self):
        order, client, child, factory = self.producer_ports(register=False)
        result = candidate.deliver(self.event, self.root, client=client, tree_factory=factory)
        self.assertFalse(result["ok"])
        self.assertNotIn("send", [name for name, _ in order])
        child.communicate.assert_not_called()
        client.revoke_operator_origin.assert_called_once_with(self.proof)
        factory.return_value.__exit__.assert_called_once()

    def test_worker_reverifies_before_any_ingress_or_continuation(self):
        admit, continuation = Mock(), Mock()
        denied = candidate.consume(self.packet(), self.root, verify=lambda *a, **kw: False,
                                   admit=admit, continuation=continuation)
        self.assertFalse(denied["ok"])
        admit.assert_not_called()
        continuation.assert_not_called()

    def test_wrong_event_action_and_project_refuse_even_with_positive_test_verifier(self):
        for key, value in (("event_id", "other-message"), ("action", "start"),
                           ("session", "another-session")):
            packet = self.packet()
            packet["operator_origin"] = {**self.proof, key: value}
            admit = Mock()
            result = candidate.consume(packet, self.root, verify=lambda *a, **kw: True,
                                       admit=admit, continuation=Mock())
            self.assertFalse(result["ok"])
            admit.assert_not_called()
        admit = Mock()
        result = candidate.consume(self.packet(), self.root / "other",
                                   verify=lambda *a, **kw: True, admit=admit, continuation=Mock())
        self.assertFalse(result["ok"])
        admit.assert_not_called()

    def test_kernel_refusal_after_valid_test_ingress_is_preserved(self):
        order = []
        def verify(*args, **kwargs):
            order.append("verify")
            return True  # explicit test port, not a genuine native-origin observation
        def admit(*args, **kwargs):
            order.append("admit")
            return {"ok": True, "ingress_id": "fixture-ingress"}
        def continuation(root):
            order.append("canonical-continue")
            return 1, {"ok": False, "code": "CONFORMANCE_UNHEALTHY"}
        result = candidate.consume(self.packet(), self.root, verify=verify,
                                   admit=admit, continuation=continuation)
        self.assertEqual(order, ["verify", "admit", "canonical-continue"])
        self.assertTrue(result["ok"], "only the ingress delivery succeeded")
        self.assertFalse(result["continuation"]["answer"]["ok"])
        self.assertEqual(result["continuation"]["exit_code"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
