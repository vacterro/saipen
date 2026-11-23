"""Fixed meta-oracle: only the hostile-input carrier implementation varies."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
import json

ROOT = Path(__file__).resolve().parents[3]
subject = Path(sys.argv.pop(1)).resolve()
sys.path.insert(0, str(ROOT / "tools"))
from test_audit_inbox import AuditInboxFixture

spec = importlib.util.spec_from_file_location("t1699_carrier_subject", subject)
carrier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(carrier)
PAYLOAD = "- 10.10.26 [T-1] RUN: ticket finished via SAIOPS -- completion (from SHIP)"


class CarrierContractTests(AuditInboxFixture):
    def call(self, *args):
        process = subprocess.run([str(ROOT / "bin/saipen.cmd"), "--project-root", str(self.root),
                                  *args, "--json"], cwd=ROOT, capture_output=True, timeout=60)
        return process.returncode, json.loads(process.stdout)

    def control(self):
        code, value = self.call("ticket", "add", "P2", "legitimate control", "--verify", "proof")
        self.assertEqual(code, 0, value)
        code, value = self.call("validate")
        self.assertEqual(code, 0, value)
        self.assertTrue(value["ok"])

    def test_hostile_frame_is_present_without_a_heading(self):
        self.control()
        path = self.root / ".saipen/LOG.md"
        self.assertNotIn("# Log\n", path.read_text(encoding="utf-8"))
        carrier.unnumbered(self.root)
        self.assertIn(PAYLOAD, path.read_text(encoding="utf-8"))

    def test_real_validator_rejects_the_injected_frame(self):
        self.control()
        carrier.unnumbered(self.root)
        code, value = self.call("validate")
        self.assertNotEqual(code, 0, value)
        self.assertFalse(value["ok"])
        self.assertEqual(value["code"], "VALIDATION_FAILED")

    def test_readers_preserve_canonical_fixture_bytes(self):
        self.control()
        carrier.unnumbered(self.root)
        before = {name: (self.root / ".saipen" / name).read_bytes()
                  for name in ("STATE.md", "BOARD.md", "LOG.md")}
        self.call("validate")
        self.assertEqual(before, {name: (self.root / ".saipen" / name).read_bytes() for name in before})

    def test_heading_commentary_is_a_legal_control(self):
        self.control()
        path = self.root / ".saipen/LOG.md"
        path.write_bytes(b"# Notes: RUN and [T-1] are context here\n\n" + path.read_bytes())
        code, value = self.call("validate")
        self.assertEqual(code, 0, value)
        self.assertTrue(value["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
