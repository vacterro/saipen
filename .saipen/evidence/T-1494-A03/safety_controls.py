"""Disposable effect controls for gaps in the existing authority matrix."""
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import codec, goal_authority, operations
from test_hermetic_env import isolate_host_session
from test_t1363_zero_manual_entry import cli
from test_t1494_continuation_authority import ContinuationAuthorityTests as Fixtures


def setUpModule():
    isolate_host_session()


class SafetyControls(unittest.TestCase):
    bounded = Fixtures.bounded
    persistent = Fixtures.persistent
    read_state = Fixtures.read_state
    snapshot = Fixtures.snapshot
    spend = Fixtures.spend
    patch_state = Fixtures.patch_state

    def all_bytes(self, root):
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    def test_missing_and_corrupt_committed_grants_refuse_without_history_writes(self):
        for mode in ("missing", "corrupt"):
            with self.subTest(mode=mode):
                root = self.persistent()
                self.spend(root)
                manifests = list((root / ".saipen/recovery/settled").glob("*/operation.json"))
                grant_path = next(p for p in manifests if json.loads(p.read_text())["operation"] == "goal_entry")
                if mode == "missing":
                    grant_path.rename(grant_path.with_name("operation.unavailable"))
                else:
                    manifest = json.loads(grant_path.read_text())
                    manifest["receipt_metadata"]["goal_authority"]["goal_ingress"] = "goal-" + "f" * 16
                    grant_path.write_text(json.dumps(manifest), encoding="utf-8")
                before = self.all_bytes(root)
                self.assertTrue(goal_authority.prove(root, self.read_state(root)))
                code, payload, text = cli(root, "continue", "--json")
                self.assertNotEqual(code, 0, text)
                self.assertFalse(payload.get("ok"), text)
                self.assertEqual(self.all_bytes(root), before)

    def test_authorized_dry_run_persists_no_grant_or_journal(self):
        for kind in ("bounded", "persistent"):
            with self.subTest(kind=kind):
                root = self.bounded() if kind == "bounded" else self.persistent()
                if kind == "persistent":
                    self.spend(root)
                before = self.all_bytes(root)
                code, payload, text = cli(root, "continue", "--json", "--dry-run", operator_text="cc")
                self.assertEqual(code, 0, text)
                self.assertTrue(payload.get("ok"), text)
                self.assertEqual(self.all_bytes(root), before)
                self.assertEqual(self.read_state(root)["goal_tickets"], 20)

    def test_repeated_identical_cc_cannot_duplicate_operator_authorization(self):
        root = self.bounded()
        for attempt in range(2):
            code, payload, text = cli(root, "continue", "--json", operator_text="cc")
            self.assertEqual(code, 0, text)
            current = self.read_state(root)
            if attempt == 0:
                source = current["authority_source"]
            self.assertEqual(current["authority_source"], source)
            log = (root / ".saipen/LOG.md").read_text()
            self.assertEqual(log.count("DEC: goal reauthorized --"), 1)

    def test_operator_required_manual_wait_survives_persistent_cap(self):
        root = self.persistent()
        self.spend(root)
        wait = "WAIT: manual-verify -- run the required operator check and report pass or fail"
        self.patch_state(root, {"next_action": wait})
        before = self.all_bytes(root)
        _code, payload, text = cli(root, "continue", "--json")
        self.assertEqual(self.all_bytes(root), before, text)
        self.assertNotEqual(payload.get("code"), "VALVE_REAUTHORIZED", text)


if __name__ == "__main__":
    # Only this class: imported fixture tests do not enter the denominator.
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SafetyControls))
    sys.exit(0 if result.wasSuccessful() and result.testsRun == 4 else 1)
