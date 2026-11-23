"""A declared nested repository must move the OUTER fingerprint (T-47 / SAIT-001).

Measured on _zaicode before this rule existed: `zcode/` is its own Git
repository and the outer repo gitignores it (`/zcode/`), so `git diff` in the
outer root never saw a single product byte. Editing a tracked file under
`zcode/packages/ui/src/i18n/` left the outer identity byte-identical at
`git-delta-v1:8100e16...`. That is not a small gap: `compute_source_identity`
is what `require_fresh`, the improve strict-cycle bar, `saipen improve verify`
and the T-76 discovery gate all read. Every one of them was blind to the code
that actually ships.

Declaration, not discovery, is the design: a `.git` walk on every identity call
would cost more than the capture it protects and would silently bind
repositories the project never meant to. So a project says which ones count, in
`.saipen/source-nested-repos.json`.

Both directions are pinned below: a nested edit moves the outer identity, and a
nested repo that stops being a work tree FAILS the capture instead of quietly
dropping out of it -- a freshness guarantee that silently stops covering its
source is worse than none, because it is believed. And the no-declaration path
is byte-identical to the pre-rule behaviour, so every other project is
untouched.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from freshness import (  # noqa: E402
    NESTED_REPOS_CONFIG_REL,
    FreshnessError,
    compute_source_identity,
)

CONFIG_REL = NESTED_REPOS_CONFIG_REL


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class NestedSourceBinding(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)

        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@example.invalid")
        git(self.root, "config", "user.name", "t")
        (self.root / "outer.txt").write_text("outer\n", encoding="utf-8")
        git(self.root, "add", "outer.txt")
        git(self.root, "commit", "-q", "-m", "outer")

        # A real nested repository, exactly the shape that hid from the delta.
        self.nested = self.root / "zcode"
        self.nested.mkdir()
        git(self.nested, "init", "-q")
        git(self.nested, "config", "user.email", "t@example.invalid")
        git(self.nested, "config", "user.name", "t")
        (self.nested / "product.txt").write_text("v1\n", encoding="utf-8")
        git(self.nested, "add", "product.txt")
        git(self.nested, "commit", "-q", "-m", "product v1")
        # The outer repo gitignores it, which is why the delta never saw it.
        (self.root / ".gitignore").write_text("/zcode/\n", encoding="utf-8")
        git(self.root, "add", ".gitignore")
        git(self.root, "commit", "-q", "-m", "ignore nested")

    def declare(self, repos: list[str]) -> None:
        path = self.root / CONFIG_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"schema_version": 1, "nested_repos": repos}),
            encoding="utf-8",
        )
        # .saipen is excluded from the delta by design, so the declaration
        # itself is bound through the binding bytes rather than the diff.

    def fingerprint(self) -> str:
        return compute_source_identity(self.root).source_tree_fingerprint

    # --- the defect: an edit inside the nested tree was invisible ----------

    def test_without_declaration_the_nested_edit_is_invisible(self) -> None:
        """The red control. This is the measured _zaicode behaviour."""
        before = self.fingerprint()
        (self.nested / "product.txt").write_text("v2\n", encoding="utf-8")
        self.assertEqual(
            self.fingerprint(),
            before,
            "if this ever passes the same way, the fixture stopped reproducing "
            "the defect and the green case below would prove nothing",
        )

    def test_declared_nested_edit_moves_the_outer_identity(self) -> None:
        self.declare(["zcode"])
        before = self.fingerprint()
        (self.nested / "product.txt").write_text("v2\n", encoding="utf-8")
        after = self.fingerprint()
        self.assertNotEqual(after, before)
        self.assertTrue(after.startswith("git-delta-v1:"))

    def test_declared_nested_commit_moves_the_outer_identity(self) -> None:
        self.declare(["zcode"])
        before = self.fingerprint()
        (self.nested / "product.txt").write_text("v2\n", encoding="utf-8")
        git(self.nested, "add", "product.txt")
        git(self.nested, "commit", "-q", "-m", "product v2")
        self.assertNotEqual(self.fingerprint(), before)

    def test_declaring_the_repo_itself_moves_the_identity(self) -> None:
        """Declaring coverage is itself a change in what is bound."""
        before = self.fingerprint()
        self.declare(["zcode"])
        self.assertNotEqual(self.fingerprint(), before)

    def test_outer_only_edit_still_moves_the_identity(self) -> None:
        self.declare(["zcode"])
        before = self.fingerprint()
        (self.root / "outer.txt").write_text("changed\n", encoding="utf-8")
        self.assertNotEqual(self.fingerprint(), before)

    # --- a guarantee that quietly stops covering is worse than none -------

    def test_missing_nested_repo_fails_closed(self) -> None:
        self.declare(["zcode", "not-there"])
        with self.assertRaises(FreshnessError) as ctx:
            self.fingerprint()
        self.assertIn("missing", str(ctx.exception))

    def test_nested_path_that_is_not_a_work_tree_fails_closed(self) -> None:
        plain = self.root / "plain"
        plain.mkdir()
        (plain / "x.txt").write_text("x\n", encoding="utf-8")
        self.declare(["zcode", "plain"])
        with self.assertRaises(FreshnessError) as ctx:
            self.fingerprint()
        self.assertIn("not its own work tree root", str(ctx.exception))

    def test_escaping_declaration_is_refused(self) -> None:
        self.declare(["../elsewhere"])
        with self.assertRaises(FreshnessError) as ctx:
            self.fingerprint()
        self.assertIn("escapes the project root", str(ctx.exception))

    def test_malformed_declaration_fails_closed(self) -> None:
        path = self.root / CONFIG_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(FreshnessError):
            self.fingerprint()

    def test_wrong_shape_declaration_fails_closed(self) -> None:
        path = self.root / CONFIG_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"nested_repos": "zcode"}), encoding="utf-8")
        with self.assertRaises(FreshnessError):
            self.fingerprint()

    # --- every other project must be untouched ---------------------------

    def test_no_declaration_keeps_the_legacy_shape(self) -> None:
        ident = compute_source_identity(self.root)
        self.assertTrue(ident.source_tree_fingerprint.startswith("git-delta-v1:"))
        self.assertEqual(len(ident.source_tree_fingerprint.split(":")[1]), 64)

    def test_empty_declaration_list_is_the_same_as_none(self) -> None:
        before = self.fingerprint()
        self.declare([])
        self.assertEqual(self.fingerprint(), before)

    def test_declaration_order_does_not_matter(self) -> None:
        self.declare(["zcode"])
        one = self.fingerprint()
        self.declare(["zcode", "zcode"])
        self.assertEqual(self.fingerprint(), one)


if __name__ == "__main__":
    unittest.main()
