"""T-1592: the manifest's "Commit the file" advice must not stand unqualified.

`validate.py` refuses an untracked runtime file and advises committing it or
dropping the manifest entry. Following the first branch is unsafe when the
file's SUBJECT is also uncommitted: the commit turns a local manifest FAIL
into a red suite in every clone. Measured 2026-10-02 on this repo -- tracking
two untracked `tools/` tests made `--gate core` report zero manifest FAILs
here, while `git archive HEAD` extracted to a scratch tree ran the same two
modules as FAILED (5 tests, 4 failures, 1 ImportError).

`validate.py` cannot be imported -- it has no `__main__` guard and ends in
`sys.exit` -- so the function is executed from its real source here rather
than from a copy that could drift. `git` is stubbed, so these tests pin the
DECISION, not git.
"""

import contextlib
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def _run_uncommitted_symbols(fake_git, rel):
    """Exec the real `_uncommitted_symbols` out of validate.py against a stub git."""
    lines = (ROOT / "tools" / "validate.py").read_text(encoding="utf-8").splitlines()
    start = next(
        i for i, ln in enumerate(lines) if ln.startswith("def _uncommitted_symbols")
    )
    end = start + 1
    while end < len(lines) and not (
        lines[end].startswith("#:") or lines[end].startswith("def ")
    ):
        end += 1
    namespace = {"re": re, "Path": Path, "_git": fake_git}
    exec(compile("\n".join(lines[start:end]), "validate.py", "exec"), namespace)
    return namespace["_uncommitted_symbols"](rel)


#: What HEAD is stubbed to carry.
HEAD = {
    "tools/saipen_engine/__init__.py": "",
    "tools/saipen_engine/board.py": "CLOSURE_PROVENANCE_FIELDS = ()\n",
    "tools/committed_thing.py": "ALREADY_THERE = 1\n",
}
#: Present in this home, absent from HEAD -- the other half of the defect.
#: A name that exists in NEITHER is stdlib or third-party, which the check
#: deliberately ignores, so it cannot stand in for this case.
UNCOMMITTED = {"tools/brand_new_engine/wheel.py": "Thing = 1\n"}


class OrphanDetectionTests(unittest.TestCase):
    """One fixture tree, one stubbed HEAD, three outcomes."""

    def _run(self, source: str) -> list[str]:
        def fake_git(*args):
            if args[:1] == ("show",):
                body = HEAD.get(args[1].split(":", 1)[1])
                return (0, body) if body is not None else (1, "")
            return (1, "")

        old = os.getcwd()
        try:
            # chdir back BEFORE the temp tree is removed, or Windows refuses to
            # rmdir a directory that is still somebody's cwd.
            with tempfile.TemporaryDirectory() as td, contextlib.chdir(td):
                for rel, body in {**HEAD, **UNCOMMITTED}.items():
                    p = Path(rel)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(body, encoding="utf-8")
                Path("tools/test_thing.py").write_text(source, encoding="utf-8")
                return _run_uncommitted_symbols(fake_git, "tools/test_thing.py")
        finally:
            os.chdir(old)

    def test_a_symbol_absent_from_head_is_named(self):
        # THE DEFECT: the constant exists in this home only, so committing the
        # test alone ships an ImportError to every clone.
        self.assertEqual(
            self._run("from saipen_engine.board import CLOSURE_METADATA_FIELDS\n"),
            ["saipen_engine.board.CLOSURE_METADATA_FIELDS"],
        )

    def test_a_self_contained_test_reports_nothing(self):
        # POSITIVE CONTROL: the ordinary case must stay silent, or every green
        # home would drown in advice. Includes the stdlib names that a naive
        # lookup reports as orphans -- pathlib, unittest, __future__.
        self.assertEqual(
            self._run(
                "import json\n"
                "import pathlib\n"
                "import unittest\n"
                "from __future__ import annotations\n"
                "from saipen_engine.board import CLOSURE_PROVENANCE_FIELDS\n"
                "from committed_thing import ALREADY_THERE\n"
            ),
            [],
        )

    def test_a_module_absent_from_head_entirely_is_named(self):
        self.assertEqual(
            self._run("from brand_new_engine.wheel import Thing\n"),
            ["module brand_new_engine.wheel"],
        )


class AdviceStaysQualifiedTests(unittest.TestCase):
    """The FAIL text is a pinned baseline snapshot -- the fix ADDS, never rewrites."""

    def test_the_existing_fail_text_is_unchanged(self):
        source = (ROOT / "tools" / "validate.py").read_text(encoding="utf-8")
        self.assertIn(
            '"and every checkout of it does not. Commit the file or drop "',
            source,
        )

    def test_the_unsafe_branch_adds_a_warning_beside_the_fail(self):
        source = (ROOT / "tools" / "validate.py").read_text(encoding="utf-8")
        self.assertIn('"manifest-untracked-orphan"', source)
        self.assertIn("do NOT ", source)


if __name__ == "__main__":
    unittest.main()