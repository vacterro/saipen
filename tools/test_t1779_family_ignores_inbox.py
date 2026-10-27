"""T-1779: an operator drop into audit/ is input, not the family's subject.

`core_unit.tree_fingerprint` and the family's sandbox copy took every file
outside `.git` and `.saipen`, so a handoff landing in the project's audit inbox
moved the fingerprint: on 2026-10-14 two drops re-snapshotted one family run
and a third denied an identical-code PASS record its reuse. The top-level inbox
is now left out of both the copy and the fingerprint; everything else stays
subject, a directory named audit below the top level included.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import core_unit  # noqa: E402
from saipen_engine.test_runner import _ignore_copy  # noqa: E402


class FamilyIgnoresTheInbox(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.mkdtemp(prefix="t1779-")
        self.addCleanup(shutil.rmtree, tmp, True)
        self.root = Path(tmp) / "project"
        (self.root / "tools").mkdir(parents=True)
        (self.root / "tools" / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.root / "audit").mkdir()
        (self.root / "audit" / "SAIPEN_old.md").write_text("an old drop\n", encoding="utf-8")
        (self.root / ".saipen").mkdir()
        (self.root / ".saipen" / "STATE.md").write_text("---\nphase: DONE\n---\n", encoding="utf-8")

    def test_a_drop_into_the_inbox_leaves_the_fingerprint(self) -> None:
        before = core_unit.tree_fingerprint(self.root)
        (self.root / "audit" / "SAIHANDOFF_new.md").write_text("a new drop\n", encoding="utf-8")
        (self.root / "audit" / "nested").mkdir()
        (self.root / "audit" / "nested" / "x.md").write_text("more\n", encoding="utf-8")
        self.assertEqual(core_unit.tree_fingerprint(self.root), before)

    def test_a_tested_file_still_moves_the_fingerprint(self) -> None:
        before = core_unit.tree_fingerprint(self.root)
        (self.root / "tools" / "engine.py").write_text("VALUE = 2\n", encoding="utf-8")
        self.assertNotEqual(core_unit.tree_fingerprint(self.root), before)

    def test_an_audit_directory_below_the_top_level_is_subject(self) -> None:
        before = core_unit.tree_fingerprint(self.root)
        (self.root / "tools" / "audit").mkdir()
        (self.root / "tools" / "audit" / "check.py").write_text("OK = True\n", encoding="utf-8")
        self.assertNotEqual(core_unit.tree_fingerprint(self.root), before)

    def test_the_sandbox_copy_holds_no_inbox_and_matches_the_fingerprint(self) -> None:
        sandbox = Path(tempfile.mkdtemp(prefix="t1779-sandbox-"))
        self.addCleanup(shutil.rmtree, sandbox, True)
        target = sandbox / "copy"
        core_unit.copy_tree_consistent(self.root, target, _ignore_copy)
        self.assertFalse((target / "audit").exists())
        self.assertTrue((target / "tools" / "engine.py").is_file())
        self.assertTrue((target / ".saipen" / "STATE.md").is_file())
        self.assertEqual(core_unit.tree_fingerprint(target), core_unit.tree_fingerprint(self.root))


if __name__ == "__main__":
    unittest.main()
