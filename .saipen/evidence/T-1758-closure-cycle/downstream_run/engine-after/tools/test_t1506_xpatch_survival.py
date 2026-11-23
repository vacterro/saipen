"""T-1506: applied XPATCH bytes must survive into reachable Git history."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.saipen_engine import xpatch


T0 = "2026-09-01T10:00:00Z"
T1 = "2026-09-01T11:00:00Z"
T2 = "2026-09-01T12:00:00Z"


class XPatchCommitSurvivalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-xpatch-survival-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".saipen").mkdir()
        (self.root / ".saipen/IDENTITY.md").write_text(
            "---\nproject_lineage: lineage-" + "a" * 32 + "\n---\n", encoding="utf-8"
        )
        (self.root / "src").mkdir()
        (self.root / "src/session.py").write_bytes(b"old\n")
        (self.root / "src/other.py").write_bytes(b"old other\n")
        self.git("init", "-q")
        self.git("add", "src/session.py", "src/other.py")
        self.commit("baseline", "2026-09-01T10:30:00Z")
        # The untouched fixture, for a test that needs to run the same scenario
        # twice from the same starting state.
        self.pristine = self.root

    def git(self, *args: str, date: str | None = None) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        if date:
            env["GIT_AUTHOR_DATE"] = date
            env["GIT_COMMITTER_DATE"] = date
        result = subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def commit(self, message: str, date: str) -> None:
        self.git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            message,
            date=date,
        )

    def apply(self, contents: dict[str, bytes] | None = None) -> str:
        patch = xpatch.write_intent(
            self.root,
            source={
                "project_lineage": "lineage-" + "b" * 32,
                "work_id": "T-342",
                "agent": "saicont",
            },
            reason="survival fixture",
            contents=contents or {"src/session.py": b"new\n"},
            now=T0,
        )
        patch_id = patch["patch_id"]
        applied = xpatch.apply_proposal(self.root, patch_id, now=T1)
        self.assertEqual(applied["outcome"], xpatch.OUTCOME_APPLIED)
        return patch_id

    def test_applied_verified_bytes_without_a_commit_are_reported(self) -> None:
        patch_id = self.apply()
        xpatch.record_disposition(self.root, patch_id, "VERIFIED", now=T2)
        head_before = self.git("rev-parse", "HEAD").stdout
        status_before = self.git("status", "--porcelain").stdout
        report = xpatch.commit_survival(self.root)
        self.assertTrue(report["available"], report)
        self.assertEqual(report["problems"], [])
        self.assertEqual(
            report["uncommitted"], [{"patch_id": patch_id, "paths": ["src/session.py"]}]
        )
        self.assertEqual(self.git("rev-parse", "HEAD").stdout, head_before)
        self.assertEqual(self.git("status", "--porcelain").stdout, status_before)

    def test_qualifying_commit_clears_the_finding(self) -> None:
        self.apply()
        self.git("add", "src/session.py")
        self.commit("carry applied bytes", T2)
        self.assertEqual(xpatch.commit_survival(self.root)["uncommitted"], [])

    def test_commit_at_applied_instant_qualifies(self) -> None:
        self.apply()
        self.git("add", "src/session.py")
        self.commit("carry bytes at applied instant", T1)
        self.assertEqual(xpatch.commit_survival(self.root)["uncommitted"], [])

    def test_applied_without_disposition_is_still_inspected(self) -> None:
        patch_id = self.apply()
        self.assertEqual(
            xpatch.commit_survival(self.root)["uncommitted"],
            [{"patch_id": patch_id, "paths": ["src/session.py"]}],
        )

    def test_supersession_is_per_path(self) -> None:
        patch_id = self.apply({"src/session.py": b"new\n", "src/other.py": b"new other\n"})
        (self.root / "src/other.py").write_bytes(b"superseded\n")
        xpatch.record_disposition(self.root, patch_id, "SUPERSEDED", now=T2)
        report = xpatch.commit_survival(self.root)
        self.assertEqual(
            report["uncommitted"], [{"patch_id": patch_id, "paths": ["src/session.py"]}]
        )

    def test_crlf_bytes_committed_under_text_auto_are_not_reported(self) -> None:
        # T-1522: after_sha256 hashes the CRLF working-tree bytes the patch
        # applied, but `* text=auto` normalizes the committed blob to LF, so
        # comparing after_sha256 against the raw blob reported a correctly
        # committed CRLF path forever. The smudge-back comparison must clear it.
        (self.root / ".gitattributes").write_bytes(b"* text=auto\n")
        self.git("add", ".gitattributes")
        self.commit("declare text=auto", "2026-09-01T10:45:00Z")
        self.apply({"src/session.py": b"line-a\r\nline-b\r\n"})
        self.git("add", "src/session.py")
        self.commit("carry CRLF applied bytes", T2)
        self.assertEqual(self.git("status", "--porcelain", "src/session.py").stdout, "")
        self.assertEqual(xpatch.commit_survival(self.root)["uncommitted"], [])

    def test_the_crlf_verdict_does_not_depend_on_the_host_eol_config(self) -> None:
        # `core.eol` defaults to `native`, so `git cat-file --filters`
        # smudges the stored LF back to CRLF on a Windows host and to LF on a
        # Linux one. Matching the applied CRLF bytes against that smudge
        # therefore passed or failed purely by platform, and CI reported a
        # correctly committed CRLF path forever while the developer's machine
        # was green. Pin BOTH host configurations so the verdict belongs to
        # the repository, not to the machine running it.
        for eol in ("crlf", "lf"):
            with self.subTest(core_eol=eol):
                base = Path(tempfile.mkdtemp(prefix=f"saipen-eol-{eol}-"))
                self.addCleanup(shutil.rmtree, base, ignore_errors=True)
                root = base / "project"
                shutil.copytree(self.pristine, root)
                self.root = root
                self.git("config", "core.eol", eol)
                self.git("config", "core.autocrlf", "false")
                (root / ".gitattributes").write_bytes(b"* text=auto\n")
                self.git("add", ".gitattributes")
                self.commit("declare text=auto again", "2026-09-01T11:00:00Z")
                self.apply({"src/session.py": b"line-a\r\nline-b\r\n"})
                self.git("add", "src/session.py")
                self.commit("carry CRLF applied bytes", "2026-09-01T11:01:00Z")
                self.assertEqual(xpatch.commit_survival(root)["uncommitted"], [])

    def test_uncommitted_crlf_and_lf_bytes_are_still_reported(self) -> None:
        (self.root / ".gitattributes").write_bytes(b"* text=auto\n")
        self.git("add", ".gitattributes")
        self.commit("declare text=auto", "2026-09-01T10:45:00Z")
        crlf = self.apply({"src/session.py": b"line-a\r\nline-b\r\n"})
        self.assertEqual(
            xpatch.commit_survival(self.root)["uncommitted"],
            [{"patch_id": crlf, "paths": ["src/session.py"]}],
        )

    def test_bytes_reachable_only_from_a_stash_are_reported(self) -> None:
        # refs/stash is reachable from --all, but its bytes were never
        # committed to a branch; a path held only in a stash must still warn.
        patch_id = self.apply()
        self.git("stash", "push", "-u", "src/session.py")
        self.assertEqual(
            xpatch.commit_survival(self.root)["uncommitted"],
            [{"patch_id": patch_id, "paths": ["src/session.py"]}],
        )


if __name__ == "__main__":
    unittest.main()
