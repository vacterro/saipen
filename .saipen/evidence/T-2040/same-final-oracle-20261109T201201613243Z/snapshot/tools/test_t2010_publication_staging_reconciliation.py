"""T-2010 / SRC-371:R004: a RECORDED foreign-staging blocker is reconciled live.

The defect: the router classified a `PUBLICATION_STAGING_BLOCKED ... foreign
path(s)` blocker from recorded PROSE alone. `board.project_blockers` is
prose-only by contract ("no filesystem probe"), so a stale line -- "206 foreign
paths are pre-staged" (written 2026-10-22) -- kept asking the operator to
"Resolve foreign staged-batch ownership" while the real index held ZERO foreign
entries (measured 2026-11-02: 864 staged, 0 foreign owner).

SRC-371:R004 required exactly this durable ownership projection into the
canonical modules and was marked VERIFIED while the routing path still trusted
the prose.

The repair: `router.reconcile_publication_staging_blocker` proves the recorded
claim against the live index at the one seam that sees the project root. An
uncorroborated claim is corrected; a corroborated one (real foreign entries
present) is returned UNTOUCHED, so the protection is never weakened.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import board, router  # noqa: E402
from test_t1807_audit_liveness_regression import _valid_state_text  # noqa: E402

RECORDED = (
    "PUBLICATION_STAGING_BLOCKED: 206 foreign paths are pre-staged in the "
    "shared tree (none of them this ticket's scope)"
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _repo_with_staged(root: Path, *, foreign: bool) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "user.email", "t@example.com")
    (root / "README.md").write_text("# repo\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "init")
    owned = root / "tools"
    owned.mkdir(parents=True, exist_ok=True)
    (owned / "engine.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "add", "tools/engine.py")
    if foreign:
        foreign_dir = root / "wintage"
        foreign_dir.mkdir(parents=True, exist_ok=True)
        (foreign_dir / "config.json").write_text("{}\n", encoding="utf-8")
        _git(root, "add", "wintage/config.json")


def _staging_blocker(tickets: dict) -> dict:
    proj = board.project_blockers(tickets)
    return next(g for g in proj["groups"] if g["cause"] == "publication-staging")


class StagingBlockerIsReconciledAgainstTheLiveIndexTests(unittest.TestCase):
    def test_a_stale_foreign_label_is_corrected_to_the_measured_index(self):
        """The recorded '206 foreign' line is not corroborated -> corrected."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            _repo_with_staged(root, foreign=False)
            recorded = _staging_blocker(
                {"T-1816": {"id": "T-1816", "section": "## BLOCKED", "checkbox": " ",
                            "needs": [], "priority": "P2", "fields": {"blocker": RECORDED}}}
            )
            reconciled = router.reconcile_publication_staging_blocker(root, recorded)
            self.assertIsNotNone(reconciled, "the stale claim must be reconciled")
            self.assertEqual(reconciled["foreign_staged_count"], 0)
            self.assertGreaterEqual(reconciled["live_staged_count"], 1)
            self.assertIs(reconciled["recorded_claim_corroborated"], False)
            self.assertNotIn(
                "foreign staged-batch ownership",
                reconciled["recovery_operation"]["operator_action"],
            )
            self.assertIn("T-1644", reconciled["recovery_operation"]["operator_action"])

    def test_a_genuine_foreign_entry_retains_live_measured_protection(self):
        """Corroborated ownership stays blocked, with current measured counts."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            _repo_with_staged(root, foreign=True)
            recorded = _staging_blocker(
                {"T-1817": {"id": "T-1817", "section": "## BLOCKED", "checkbox": " ",
                            "needs": [], "priority": "P2", "fields": {"blocker": RECORDED}}}
            )
            reconciled = router.reconcile_publication_staging_blocker(root, recorded)
            self.assertEqual(reconciled["foreign_staged_count"], 1)
            self.assertTrue(reconciled["recorded_claim_corroborated"])
            self.assertFalse(reconciled["recovery_internally_authorized"])

    def test_a_non_staging_blocker_is_never_touched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            _repo_with_staged(root, foreign=False)
            other = {"cause": "blocked_external", "root_cause": "upstream"}
            self.assertIsNone(
                router.reconcile_publication_staging_blocker(root, other)
            )

    def test_route_next_carries_the_reconciled_evidence(self):
        """The router's idle route reconciles the blocker when it sees the root."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            _repo_with_staged(root, foreign=False)
            items = {
                "T-1816": {"id": "T-1816", "section": "## BLOCKED", "checkbox": " ",
                           "needs": [], "priority": "P2", "fields": {"blocker": RECORDED}},
            }
            board_text = (
                "## BLOCKED\n"
                f"- [ ] T-1816 [P2] fixture | blocker: {RECORDED}\n\n"
                "## TODO\n\n## DOING\n\n## DONE\n"
            )
            res = router.route_next(
                _valid_state_text(), board_text, project_root=root
            )
            self.assertTrue(res.get("publication_staging_reconciled"), res)
            self.assertEqual(res["primary_blocker"]["foreign_staged_count"], 0)
            self.assertIs(res["primary_blocker"]["recorded_claim_corroborated"], False)

    def test_without_a_project_root_the_recorded_claim_stands(self):
        """No root -> no probe -> the recorded prose is reported unchanged."""
        items = {
            "T-1816": {"id": "T-1816", "section": "## BLOCKED", "checkbox": " ",
                       "needs": [], "priority": "P2", "fields": {"blocker": RECORDED}},
        }
        board_text = (
            "## BLOCKED\n"
            f"- [ ] T-1816 [P2] fixture | blocker: {RECORDED}\n\n"
            "## TODO\n\n## DOING\n\n## DONE\n"
        )
        res = router.route_next(_valid_state_text(), board_text)
        self.assertNotIn("publication_staging_reconciled", res)
        self.assertNotIn("foreign_staged_count", res.get("primary_blocker") or {})


    def test_no_git_repository_cannot_yield_verified_empty_staging(self):
        """P0-01 negative control: an empty directory without a Git repository must fail closed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            recorded = _staging_blocker(
                {"T-1816": {"id": "T-1816", "section": "## BLOCKED", "checkbox": " ",
                            "needs": [], "priority": "P2", "fields": {"blocker": RECORDED}}}
            )
            from saipen_engine import isolated_release
            inv = isolated_release.inventory_staged_entries(root)
            self.assertEqual(inv["verification_status"], isolated_release.INVALID_REPOSITORY)
            self.assertIsNone(inv["index_metadata"])

            reconciled = router.reconcile_publication_staging_blocker(root, recorded)
            self.assertIsNone(reconciled, "an unverified repository probe must never reconcile recorded blockers")

    def test_missing_git_binary_fails_closed(self):
        """P0-01 negative control: missing git binary fails closed with GIT_COMMAND_FAILED."""
        from unittest.mock import patch
        from saipen_engine import isolated_release

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            recorded = _staging_blocker(
                {"T-1816": {"id": "T-1816", "section": "## BLOCKED", "checkbox": " ",
                            "needs": [], "priority": "P2", "fields": {"blocker": RECORDED}}}
            )
            with patch("subprocess.run", side_effect=FileNotFoundError("git not found")):
                inv = isolated_release.inventory_staged_entries(root)
                self.assertEqual(inv["verification_status"], isolated_release.GIT_COMMAND_FAILED)
                reconciled = router.reconcile_publication_staging_blocker(root, recorded)
                self.assertIsNone(reconciled)

    def test_corrupt_or_unreadable_index_fails_closed(self):
        """P0-01 negative control: corrupt or unreadable index fails closed with INDEX_UNREADABLE."""
        from unittest.mock import patch
        from saipen_engine import isolated_release

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            _repo_with_staged(root, foreign=False)
            recorded = _staging_blocker(
                {"T-1816": {"id": "T-1816", "section": "## BLOCKED", "checkbox": " ",
                            "needs": [], "priority": "P2", "fields": {"blocker": RECORDED}}}
            )
            with patch.object(Path, "read_bytes", side_effect=PermissionError("locked index")):
                inv = isolated_release.inventory_staged_entries(root)
                self.assertEqual(inv["verification_status"], isolated_release.INDEX_UNREADABLE)
                reconciled = router.reconcile_publication_staging_blocker(root, recorded)
                self.assertIsNone(reconciled)

    def test_ambiguous_provenance_is_not_proof_of_ownership(self):
        """P0-02 negative control: staged files of ambiguous provenance must not clear foreign blocker."""
        from saipen_engine import isolated_release

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            _repo_with_staged(root, foreign=False)
            ambig = root / "unknown_pkg" / "ambiguous.dat"
            ambig.parent.mkdir(parents=True, exist_ok=True)
            ambig.write_text("mystery payload", encoding="utf-8")
            _git(root, "add", "unknown_pkg/ambiguous.dat")

            recorded = _staging_blocker(
                {"T-1816": {"id": "T-1816", "section": "## BLOCKED", "checkbox": " ",
                            "needs": [], "priority": "P2", "fields": {"blocker": RECORDED}}}
            )
            inv = isolated_release.inventory_staged_entries(root)
            self.assertEqual(inv["verification_status"], isolated_release.VERIFIED_COMPLETE)
            self.assertEqual(inv["classification_summary"].get(isolated_release.CLASS_AMBIGUOUS_PROVENANCE), 1)

            reconciled = router.reconcile_publication_staging_blocker(root, recorded)
            self.assertEqual(reconciled["ambiguous_staged_count"], 1)
            self.assertEqual(reconciled["foreign_staged_count"], 0)
            self.assertFalse(reconciled["recovery_internally_authorized"])

    def test_concurrent_index_changes_are_detected(self):
        """P0-03: detect concurrent index changes between initial snapshot and completion."""
        from unittest.mock import patch
        from saipen_engine import isolated_release

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            _repo_with_staged(root, foreign=False)
            recorded = _staging_blocker(
                {"T-1816": {"id": "T-1816", "section": "## BLOCKED", "checkbox": " ",
                            "needs": [], "priority": "P2", "fields": {"blocker": RECORDED}}}
            )

            orig_run = subprocess.run
            def mutating_run(cmd, *args, **kwargs):
                res = orig_run(cmd, *args, **kwargs)
                if isinstance(cmd, list) and "diff" in cmd:
                    c_file = root / "tools" / "concurrent.py"
                    c_file.write_text("z = 9\n", encoding="utf-8")
                    orig_run(["git", "-C", str(root), "add", "tools/concurrent.py"], check=True)
                return res

            with patch("subprocess.run", side_effect=mutating_run):
                inv = isolated_release.inventory_staged_entries(root)
                self.assertEqual(inv["verification_status"], isolated_release.CONCURRENT_MODIFICATION)
                reconciled = router.reconcile_publication_staging_blocker(root, recorded)
                self.assertIsNone(reconciled)


if __name__ == "__main__":
    unittest.main()
