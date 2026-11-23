"""T-1888: the git object store stays whole, and the claim stays falsifiable.

The ticket asserted 889 of 1133 HEAD-reachable commits and 395 of 396 tags were
unreadable. Measurement disproved it. A one-off script would let the claim
recur unchallenged, so the measurement becomes a test: it fails the moment a
HEAD-reachable object or a tag genuinely stops resolving, and it names the
foreign ref that legitimately lives outside HEAD.

What this file does NOT assert, deliberately:

* It does not require `git fsck` to exit 0. This store carries a foreign ref
  (`refs/codex/turn-diffs/.../base`) pointing at an absent object. That ref is
  outside HEAD, is another tool's namespace, and its removal is the tracked
  INV-22 operator action. Asserting a clean fsck would either fail forever on a
  known-and-owned defect or force this test to mutate the store. Instead the
  test asserts what the ticket's verify clause actually says -- no missing
  object *reachable from HEAD* -- and pins the foreign ref by name so that if it
  ever disappears, this test notices.

* It does not repair anything. Closing a disproven finding must not leave a
  mutation behind, or the next reader cannot tell diagnosis from tampering.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: The one foreign ref this store carries, pinned so its disappearance or its
#: repair is a visible event rather than a silent change in what fsck means.
FOREIGN_REF = (
    "refs/codex/turn-diffs/captures/1785165795234/"
    "fb80dcb4-2cd2-4789-9618-a9409baff787/base"
)


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True,
    )


def _has_git_store() -> bool:
    """Whether this checkout carries a real object store to measure.

    The ticket is about a git object store, so these tests are meaningless in a
    source copy shipped without `.git` (an installed tree, a release tarball).
    Skipping is honest there; asserting would either fail a healthy copy or,
    worse, pass vacuously on `rev-list` of an empty repo.
    """
    probe = _git("rev-parse", "--git-dir")
    return probe.returncode == 0 and (ROOT / ".git").exists()


requires_store = unittest.skipUnless(
    _has_git_store(), "no git object store in this copy to measure",
)


@requires_store
class HeadReachabilityTests(unittest.TestCase):
    """Verify clause 1: no missing object reachable from HEAD."""

    def test_every_head_reachable_commit_resolves(self) -> None:
        listed = _git("rev-list", "HEAD")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        commits = [line for line in listed.stdout.split() if line]
        self.assertGreater(len(commits), 0, "HEAD has no commits to check")

        missing = []
        for commit in commits:
            if _git("cat-file", "-e", commit).returncode != 0:
                missing.append(commit)
        self.assertEqual(
            missing, [],
            f"{len(missing)} of {len(commits)} HEAD-reachable commits are "
            f"unreadable: {missing[:5]}",
        )

    def test_every_tag_resolves(self) -> None:
        listed = _git("for-each-ref", "refs/tags", "--format=%(refname)")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        tags = [line for line in listed.stdout.splitlines() if line.strip()]
        self.assertGreater(len(tags), 0, "the store has no tags to check")

        unreadable = [
            tag for tag in tags if _git("rev-parse", "--verify", tag).returncode != 0
        ]
        self.assertEqual(
            unreadable, [],
            f"{len(unreadable)} of {len(tags)} tags are unreadable: {unreadable[:5]}",
        )

    def test_history_search_still_works(self) -> None:
        found = _git("log", "-S", "finding_invalidated", "--oneline")
        self.assertEqual(found.returncode, 0, found.stderr)
        self.assertTrue(
            [line for line in found.stdout.splitlines() if line.strip()],
            "git log -S found no commit for a string that is known to be in history",
        )


@requires_store
class ForeignRefTests(unittest.TestCase):
    """The one real defect, pinned and kept outside the HEAD-scoped claim."""

    def test_the_foreign_ref_is_still_outside_head(self) -> None:
        pointer = _git("rev-parse", "--verify", FOREIGN_REF)
        if pointer.returncode != 0:
            self.skipTest("the foreign ref is gone; INV-22 may have cleaned it")
        target = pointer.stdout.strip()

        for scope in (("rev-list", "HEAD"), ("rev-list", "--all")):
            reachable = _git(*scope)
            # `--all` fails loudly on this store because of the bad ref itself;
            # that is the defect, not a test failure, so only inspect its stdout.
            self.assertNotIn(
                target, reachable.stdout.split(),
                f"{target} became reachable through {' '.join(scope)}, so the "
                f"corruption is no longer outside the ticket's scope",
            )

    def test_the_foreign_ref_is_not_this_tickets_object(self) -> None:
        pointer = _git("rev-parse", "--verify", FOREIGN_REF)
        if pointer.returncode != 0:
            self.skipTest("the foreign ref is gone")
        target = pointer.stdout.strip()
        # A raw `cat-file -e` exit status is not carried by `rev-parse`; ask for
        # the type, which fails when the object is genuinely absent.
        self.assertNotEqual(
            _git("cat-file", "-t", target).returncode, 0,
            "the foreign ref now resolves to a real object; re-measure whether "
            "this ticket's premise applies to it",
        )


@requires_store
class TheStoreIsNotTouchedTests(unittest.TestCase):
    """A disproven finding must not leave a repair behind."""

    def test_measurement_writes_nothing(self) -> None:
        before = _git("status", "--porcelain")
        _git("rev-list", "HEAD")
        _git("for-each-ref", "refs/tags")
        after = _git("status", "--porcelain")
        self.assertEqual(
            before.stdout, after.stdout,
            "read-only measurement changed the working tree",
        )


if __name__ == "__main__":
    unittest.main()
