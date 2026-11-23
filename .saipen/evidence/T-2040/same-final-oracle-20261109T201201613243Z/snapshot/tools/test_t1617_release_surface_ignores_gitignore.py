"""T-1617: the release surface must not demand paths Git refuses to carry.

`version_metadata_paths` enumerated every locale README under
`.saipen/saitranslate/kitchen` as release metadata. `.gitignore` excludes that
whole kitchen, so the binding ship gate demanded staged a set that `git add`
refuses without `-f` -- unsatisfiable by construction. It stayed silent only
while no translation run left locale READMEs behind.

The invariant under test: the release surface is the set of paths that survive
a fresh clone. A path the repository ignores cannot be on it.

Run standalone:
    python tools/test_t1617_release_surface_ignores_gitignore.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.release_contract import (  # noqa: E402
    _git_ignored,
    version_metadata_paths,
)


class IgnoredKitchenIsNotReleaseSurfaceTests(unittest.TestCase):
    def _repo(self, tmp: Path, ignore_kitchen: bool) -> Path:
        subprocess.run(["git", "init", "-q", str(tmp)], check=True)
        subprocess.run(["git", "-C", str(tmp), "config", "user.email", "t@e"], check=True)
        subprocess.run(["git", "-C", str(tmp), "config", "user.name", "t"], check=True)
        (tmp / ".gitignore").write_text(
            "/.saipen/saitranslate/kitchen/\n" if ignore_kitchen else "", encoding="utf-8"
        )
        kitchen = tmp / ".saipen" / "saitranslate" / "kitchen"
        for loc in ("ar", "zh"):
            d = kitchen / loc
            d.mkdir(parents=True, exist_ok=True)
            (d / f"README_{loc.upper()}.md").write_text("x", encoding="utf-8")
        return tmp

    def test_ignored_locale_readmes_are_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._repo(tmp, ignore_kitchen=True)
            paths = {p.as_posix() for p in version_metadata_paths(tmp)}
            self.assertNotIn(".saipen/saitranslate/kitchen/ar/README_AR.md", paths)
            self.assertNotIn(".saipen/saitranslate/kitchen/zh/README_ZH.md", paths)

    def test_unignored_locale_readmes_are_kept(self):
        """The filter must key on Git's own answer, not on the path shape: a
        repository that DOES track its kitchen keeps the full surface."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._repo(tmp, ignore_kitchen=False)
            paths = {p.as_posix() for p in version_metadata_paths(tmp)}
            self.assertIn(".saipen/saitranslate/kitchen/ar/README_AR.md", paths)

    def test_tracked_root_mirrors_are_always_listed(self):
        """README.ee/ded/ja.md are the published translations and are listed
        unconditionally -- the filter must never reach them."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._repo(tmp, ignore_kitchen=True)
            paths = {p.as_posix() for p in version_metadata_paths(tmp)}
            for name in (
                "README.ee.md",
                "README.ded.md",
                "README.ja.md",
                "VERSION",
                "CHANGELOG.md",
            ):
                self.assertIn(name, paths)

    def test_filter_fails_closed_without_git(self):
        """A non-Git project must lose NO release surface. An unrunnable Git
        answers False, so the path is kept exactly as it was before."""
        self.assertFalse(_git_ignored(Path("/nonexistent-repo-xyz"), Path("anything.md")))

    def test_real_tree_keeps_no_ignored_kitchen_paths(self):
        """The live tree: the kitchen holds 32 locale READMEs and none is
        tracked, so none may appear on the release surface."""
        paths = {p.as_posix() for p in version_metadata_paths(ROOT)}
        kitchen = [
            p for p in paths if p.startswith(".saipen/saitranslate/kitchen/")
        ]
        self.assertEqual(kitchen, [], f"ignored kitchen leaked onto release surface: {kitchen}")


if __name__ == "__main__":
    unittest.main()