"""Disposable OS-process controls for the undeployed native sender candidate.

The broker is a test double. These tests do not prove a trusted native host.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(HERE)]

from native_delivery_candidate import deliver  # noqa: E402
from saipen_engine.pending_ingress import ingress_digest  # noqa: E402
from saipen_engine.process_tree import ProcessTree  # noqa: E402


WORKER = '''import json, os, pathlib, sys
packet = json.loads(sys.stdin.buffer.read().decode("utf-8"))
pathlib.Path("packet_seen.txt").write_text(packet["request_text"], encoding="utf-8")
print(json.dumps({"ok": True, "sealed": True, "pid": os.getpid(),
                  "digest": os.getenv("SAIPEN_TASK_SHA256"),
                  "session": os.getenv("SAIPEN_HOST_SESSION"),
                  "old_file": os.getenv("SAIPEN_TASK_FILE")}))
'''


class BrokerDouble:
    def __init__(self, *, register_ok=True):
        self.register_ok = register_ok
        self.registered_pid = None
        self.revoked = False

    def issue_operator_origin(self, **intent):
        return {"ok": True, "proof": {"kind": "operator-origin", **intent}}

    def register_operator_worker(self, proof, pid):
        self.registered_pid = pid
        return {"ok": self.register_ok}

    def revoke_operator_origin(self, proof):
        self.revoked = True


class NativeProcessCandidateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="saipen-native-process-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        worker = self.root / "tools/native_operator_worker.py"
        worker.parent.mkdir()
        worker.write_text(WORKER, encoding="utf-8")
        self.event = {
            "event": "UserPromptSubmit", "host": "zaicode", "cwd": str(self.root),
            "session_id": "fixture-session", "host_ingress": {
                "message_id": "fixture-event", "session_id": "fixture-session",
                "request_text": "cc",
            },
        }

    def test_actual_child_receives_only_fresh_carrier_after_registration(self):
        broker = BrokerDouble()
        with patch.dict("os.environ", {
            "SAIPEN_TASK_FILE": "stale-task.txt",
            "SAIPEN_TASK_SHA256": "a" * 64,
            "SAIPEN_HOST_SESSION": "stale-session",
        }):
            answer = deliver(self.event, self.root, client=broker)
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(answer["pid"], broker.registered_pid)
        self.assertEqual(answer["digest"], ingress_digest("cc"))
        self.assertEqual(answer["session"], "fixture-session")
        self.assertIsNone(answer["old_file"])
        self.assertEqual((self.root / "packet_seen.txt").read_text(encoding="utf-8"), "cc")
        self.assertFalse(broker.revoked)

    def test_registration_refusal_never_delivers_packet_and_reaps_child(self):
        broker = BrokerDouble(register_ok=False)
        tree = ProcessTree()
        answer = deliver(self.event, self.root, client=broker, tree_factory=lambda: tree)
        self.assertFalse(answer["ok"])
        self.assertIsNotNone(broker.registered_pid)
        self.assertFalse((self.root / "packet_seen.txt").exists())
        self.assertTrue(broker.revoked)
        self.assertIsNotNone(tree.process.poll())
        for stream in (tree.process.stdin, tree.process.stdout, tree.process.stderr):
            self.assertTrue(stream.closed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
