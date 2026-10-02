import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

_MODULE = Path(__file__).resolve().parent / "release_provenance.py"
_spec = importlib.util.spec_from_file_location("release_provenance", _MODULE)
release_provenance = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(release_provenance)

ReceiptError = release_provenance.ReceiptError


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


class RepositoryFixture(unittest.TestCase):
    """A real repository, because the load-bearing check IS the repository."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-release-prov-")
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "t")
        (self.root / "a.txt").write_text("one\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "first")
        (self.root / "b.txt").write_text("two\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "second")
        self.head = subprocess.run(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()

    def tearDown(self) -> None:
        self.tmp.cleanup()


class WriteTests(RepositoryFixture):
    def test_a_no_publish_receipt_is_terminal_and_names_the_real_commit(self):
        record = release_provenance.write_receipt(
            self.root, work="T-9", commit="HEAD", mode="no-publish", note="bug fix, nothing cut"
        )
        self.assertEqual(record["status"], "COMMITTED")
        self.assertEqual(record["release_stage"], "COMMITTED")
        self.assertEqual(record["mode"], "no-publish")
        self.assertEqual(record["release_commit"], self.head)
        self.assertNotIn(
            "commit", record, "the bare spelling is the one that hides genuine receipts"
        )
        self.assertEqual(release_provenance.verify_receipt(self.root), [])

    def test_the_receipt_is_where_a_clone_can_see_it(self):
        release_provenance.write_receipt(
            self.root, work="T-9", commit="HEAD", mode="no-publish"
        )
        path = self.root / ".saipen" / "kitchen" / "release_receipt.json"
        self.assertTrue(path.is_file())
        self.assertEqual(release_provenance.read_receipt(self.root)["work"], "T-9")

    def test_a_commit_that_does_not_exist_is_refused(self):
        # The red control for the whole tool: the identity is checked, so a
        # receipt cannot be recorded for work that was never committed.
        with self.assertRaises(ReceiptError) as caught:
            release_provenance.write_receipt(
                self.root,
                work="T-9",
                commit="deadbeef" * 5,
                mode="no-publish",
            )
        self.assertIn("does not resolve", str(caught.exception))
        self.assertFalse((self.root / ".saipen" / "kitchen" / "release_receipt.json").exists())

    def test_an_empty_commit_is_refused(self):
        with self.assertRaises(ReceiptError):
            release_provenance.write_receipt(
                self.root, work="T-9", commit="   ", mode="no-publish"
            )

    def test_an_unknown_mode_is_refused(self):
        with self.assertRaises(ReceiptError):
            release_provenance.build_receipt(
                self.root, work="T-9", commit="HEAD", mode="shipped-ish"
            )


class VerifyTests(RepositoryFixture):
    def good(self) -> dict:
        return release_provenance.build_receipt(
            self.root, work="T-9", commit="HEAD", mode="no-publish"
        )

    def test_a_good_receipt_verifies(self):
        self.assertEqual(release_provenance.verify_receipt(self.root, self.good()), [])

    def test_a_receipt_naming_a_commit_that_is_gone_fails(self):
        record = self.good()
        record["release_commit"] = "0" * 40
        problems = release_provenance.verify_receipt(self.root, record)
        self.assertTrue(any("does not resolve" in p for p in problems), problems)

    def test_a_receipt_with_a_bare_commit_key_is_reported(self):
        record = self.good()
        record["commit"] = record["release_commit"]
        problems = release_provenance.verify_receipt(self.root, record)
        self.assertTrue(any("bare `commit`" in p for p in problems), problems)

    def test_a_non_terminal_receipt_is_reported(self):
        record = self.good()
        record["status"] = "IN_FLIGHT"
        problems = release_provenance.verify_receipt(self.root, record)
        self.assertTrue(any("not terminal" in p for p in problems), problems)

    def test_a_receipt_without_an_op_id_is_reported(self):
        record = self.good()
        record.pop("op_id")
        problems = release_provenance.verify_receipt(self.root, record)
        self.assertTrue(any("op_id" in p for p in problems), problems)

    def test_a_missing_receipt_is_an_error_not_a_pass(self):
        with self.assertRaises(ReceiptError):
            release_provenance.read_receipt(self.root)


class CliTests(RepositoryFixture):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["python", str(_MODULE), "--project-root", str(self.root), *args],
            capture_output=True, text=True, check=False,
        )

    def test_write_then_verify_over_the_cli(self):
        written = self.run_cli(
            "write", "--work", "T-9", "--commit", "HEAD", "--mode", "no-publish"
        )
        self.assertEqual(written.returncode, 0, written.stderr)
        verified = self.run_cli("verify")
        self.assertEqual(verified.returncode, 0, verified.stderr + verified.stdout)

    def test_the_cli_refuses_a_fabricated_identity(self):
        result = self.run_cli(
            "write", "--work", "T-9", "--commit", "0" * 40, "--mode", "no-publish"
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("does not resolve", result.stderr)


if __name__ == "__main__":
    unittest.main()
