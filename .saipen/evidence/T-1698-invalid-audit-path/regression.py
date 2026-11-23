"""Fixed oracle: only argv[1]'s production audit module varies."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
SUBJECT = Path(sys.argv.pop(1)).resolve()
sys.path.insert(0, str(ROOT / "tools"))
from test_audit_inbox import AuditInboxFixture

spec = importlib.util.spec_from_file_location("saipen_engine._audit_path_subject", SUBJECT)
audit_inbox = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_inbox)


class InvalidPathTests(AuditInboxFixture):
    def invalid_pair(self, numbered=False):
        directory = self.root / "audit"
        directory.mkdir()
        names = ("1.md", "2.md") if numbered else ("a-empty.md", "b-encoding.txt")
        for name, body in zip(names, (b"", b"\xff")):
            (directory / name).write_bytes(body)

    def test_status_identifies_each_named_failure(self):
        self.invalid_pair()
        self.assertEqual(audit_inbox.status(self.root)["invalid"], [
            {"layer": None, "path": "audit/a-empty.md", "reason": "empty"},
            {"layer": None, "path": "audit/b-encoding.txt", "reason": "not-utf8"},
        ])

    def test_projection_identifies_each_named_failure(self):
        self.invalid_pair()
        self.assertEqual(audit_inbox.projection(self.root)["invalid"], [
            {"layer": None, "path": "audit/a-empty.md", "reason": "empty"},
            {"layer": None, "path": "audit/b-encoding.txt", "reason": "not-utf8"},
        ])

    def test_numbered_summary_shape_is_unchanged(self):
        self.invalid_pair(numbered=True)
        expected = [{"layer": 1, "reason": "empty"}, {"layer": 2, "reason": "not-utf8"}]
        self.assertEqual(audit_inbox.status(self.root)["invalid"], expected)
        self.assertEqual(audit_inbox.projection(self.root)["invalid"], expected)

    def test_diagnostics_preserve_every_fixture_byte(self):
        self.invalid_pair()
        def snapshot():
            return {str(path.relative_to(self.root)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in self.root.rglob("*") if path.is_file()}
        before = snapshot()
        audit_inbox.status(self.root)
        audit_inbox.projection(self.root)
        self.assertEqual(snapshot(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
