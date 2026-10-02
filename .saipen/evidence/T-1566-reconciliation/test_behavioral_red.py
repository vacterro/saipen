"""Behavioral RED: collection succeeds against old runtime without the new API."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOME = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


class BehavioralRed(unittest.TestCase):
    def test_old_runtime_reaches_forensic_dead_end_with_identical_oracle(self):
        with tempfile.TemporaryDirectory(prefix="tail-red-", dir=HOME / ".saipen/tmp") as raw:
            subject = Path(raw) / "subject"
            built = subprocess.run(
                [sys.executable, str(HOME / ".saipen/evidence/T-1565-foreign-tail/build_prefix.py"), str(subject)],
                capture_output=True, encoding="utf-8", errors="replace", timeout=60,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            oracle = subject / "tools/test_log_tail_quarantine.py"
            self.assertEqual(oracle.read_bytes(), (HOME / "tools/test_log_tail_quarantine.py").read_bytes())
            tested = subprocess.run(
                [sys.executable, "-m", "unittest", "test_log_tail_quarantine.QuarantineLogTailTests.test_public_recovery_same_damage_preserves_bytes_and_resumes", "-v"],
                cwd=subject / "tools", capture_output=True, encoding="utf-8", errors="replace", timeout=60,
            )
            text = tested.stdout + tested.stderr
            (OUT / "foreign-tail-behavioral-red.log").write_text(text, encoding="utf-8")
            self.assertNotEqual(tested.returncode, 0)
            self.assertIn("Ran 1 test", text)
            self.assertIn("FORENSICALLY_UNRECOVERABLE", text)
            self.assertIn("canonical_next_command", text)
            self.assertNotIn("ImportError", text)
            self.assertNotIn("ModuleNotFoundError", text)
            hashes = {
                rel: hashlib.sha256((subject / rel).read_bytes()).hexdigest()
                for rel in ("tools/test_log_tail_quarantine.py", "tools/saipen_engine/operations.py", "tools/saipen_engine/log.py", "tools/saipen_engine/reconcile.py", "tools/saipen.py")
            }
            (OUT / "foreign-tail-behavioral-red.json").write_text(
                json.dumps({"oracle": "test_public_recovery_same_damage_preserves_bytes_and_resumes", "red": True, "collection_succeeded": True, "subject_sha256": hashes, "log_sha256": hashlib.sha256(text.encode()).hexdigest()}, indent=2), encoding="utf-8",
            )


if __name__ == "__main__":
    unittest.main()
