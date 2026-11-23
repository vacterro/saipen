"""T-2094 (night 9, W3): a wildcard must reach the declared scope it selects.

The measured defect: `tools/sandbox_scope.json` already declared the four
T-2093 modules with no heavy tree, but `resolve(root, ["test_t2093_*.py"])`
compared the literal pattern with manifest keys and answered FULL. The two
PASS records of that night paid copy_wall_s 102.219 and 69.547 for a copy the
declarations had already proven unnecessary.

What this module pins:

  * one selector: wildcard expansion is `select_modules`, the same contract
    the focused runner executes, so `resolve`, the preflight refusal and the
    runner cannot disagree about which modules a pattern set selects;
  * a wildcard whose every selected module is declared resolves DECLARED with
    the union of their trees; one undeclared module keeps the whole run FULL;
  * the resolved decision records the selected modules, and any change to the
    selection or the manifest that changes copied bytes refuses the old record;
  * matching is the bare-filename, case-sensitive `fnmatchcase` contract on
    every platform, so a Windows run and a POSIX run agree.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import core_unit, sandbox_scope  # noqa: E402
from saipen_engine.focused_unit import _patterns  # noqa: E402


class PatternScopeTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="t2094-scope-"))
        self.tools = self.root / "tools"
        self.tools.mkdir()
        (self.root / ".saipen/evidence").mkdir(parents=True)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.root, ignore_errors=True)

    def module(self, name: str) -> Path:
        path = self.tools / name
        path.write_text("", encoding="utf-8")
        return path

    def manifest(self, modules: dict) -> None:
        (self.tools / "sandbox_scope.json").write_text(
            json.dumps({"schema": 1, "modules": modules}), encoding="utf-8"
        )

    # -- selection ----------------------------------------------------------

    def test_one_exact_module_is_declared(self):
        self.module("test_one.py")
        self.manifest({"test_one.py": []})
        scope = sandbox_scope.resolve(self.root, ["test_one.py"])
        self.assertEqual(scope["mode"], sandbox_scope.DECLARED)
        self.assertEqual(scope["selected"], ["test_one.py"])
        self.assertEqual(scope["trees"], [])

    def test_four_exact_modules_union_their_trees(self):
        for name in ("test_a.py", "test_b.py", "test_c.py", "test_d.py"):
            self.module(name)
        self.manifest({
            "test_a.py": [],
            "test_b.py": [".saipen/evidence"],
            "test_c.py": [],
            "test_d.py": [".git"],
        })
        scope = sandbox_scope.resolve(
            self.root, ["test_d.py", "test_b.py", "test_a.py", "test_c.py"]
        )
        self.assertEqual(scope["mode"], sandbox_scope.DECLARED)
        self.assertEqual(scope["trees"], [".git", ".saipen/evidence"])
        self.assertEqual(
            scope["selected"],
            ["test_a.py", "test_b.py", "test_c.py", "test_d.py"],
        )

    def test_a_wildcard_over_four_declared_modules_is_declared(self):
        # R5: the exact night-9 red. Literal comparison answered FULL here.
        for name in ("test_t2093_a.py", "test_t2093_b.py",
                     "test_t2093_c.py", "test_t2093_d.py"):
            self.module(name)
        self.manifest({name: [] for name in (
            "test_t2093_a.py", "test_t2093_b.py",
            "test_t2093_c.py", "test_t2093_d.py",
        )})
        scope = sandbox_scope.resolve(self.root, ["test_t2093_*.py"])
        self.assertEqual(scope["mode"], sandbox_scope.DECLARED,
                         "a wildcard whose every selected module is declared "
                         "must not fall back to a FULL copy")
        self.assertEqual(scope["trees"], [])
        self.assertEqual(scope["undeclared"], [])
        self.assertEqual(len(scope["selected"]), 4)

    def test_a_wildcard_with_one_undeclared_module_is_full(self):
        for name in ("test_mix_a.py", "test_mix_b.py", "test_mix_c.py"):
            self.module(name)
        self.manifest({"test_mix_a.py": [], "test_mix_b.py": []})
        scope = sandbox_scope.resolve(self.root, ["test_mix_*.py"])
        self.assertEqual(scope["mode"], sandbox_scope.FULL)
        self.assertEqual(scope["undeclared"], ["test_mix_c.py"])

    def test_a_wildcard_without_matches_is_full_and_says_so(self):
        self.manifest({"test_other.py": []})
        scope = sandbox_scope.resolve(self.root, ["test_absent_*.py"])
        self.assertEqual(scope["mode"], sandbox_scope.FULL)
        self.assertEqual(scope["undeclared"], ["test_absent_*.py"])
        self.assertEqual(scope["selected"], [])

    def test_overlapping_patterns_are_deduplicated(self):
        self.module("test_over.py")
        self.manifest({"test_over.py": []})
        scope = sandbox_scope.resolve(
            self.root, ["test_over.py", "test_ov*.py", "test_*.py"]
        )
        self.assertEqual(scope["mode"], sandbox_scope.DECLARED)
        self.assertEqual(scope["selected"], ["test_over.py"])

    def test_an_exact_declared_name_without_a_file_is_full(self):
        # The selection is what the runner will execute, not what the manifest
        # hopes exists: a declared module that is gone selects nothing.
        self.manifest({"test_gone.py": []})
        scope = sandbox_scope.resolve(self.root, ["test_gone.py"])
        self.assertEqual(scope["mode"], sandbox_scope.FULL)
        self.assertEqual(scope["undeclared"], ["test_gone.py"])

    def test_matching_is_case_sensitive_on_every_platform(self):
        self.module("Test_Upper.py")
        self.manifest({})
        selected, unmatched = sandbox_scope.select_modules(
            self.root, ["test_*.py"]
        )
        self.assertEqual(selected, [])
        self.assertEqual(unmatched, ["test_*.py"])

    def test_matching_is_bare_filename_only(self):
        self.module("test_here.py")
        selected, unmatched = sandbox_scope.select_modules(
            self.root, ["tools/test_*.py"]
        )
        self.assertEqual(selected, [])
        self.assertEqual(unmatched, ["tools/test_*.py"])
        with self.assertRaises(ValueError):
            _patterns(["tools/test_*.py"])

    def test_selection_and_runner_share_one_selector(self):
        for name in ("test_x.py", "test_y.py", "helper.py"):
            self.module(name)
        self.assertEqual(
            sandbox_scope.select_modules(self.root, ["test_*.py"]),
            (["test_x.py", "test_y.py"], []),
        )
        self.assertEqual(
            sandbox_scope.select_modules(self.root, ["test_[xy].py"]),
            (["test_x.py", "test_y.py"], []),
        )

    # -- evidence binding ---------------------------------------------------

    def test_the_decision_records_the_selected_modules(self):
        self.module("test_named.py")
        self.manifest({"test_named.py": []})
        scope = sandbox_scope.resolve(self.root, ["test_*.py"])
        self.assertEqual(scope["selected"], ["test_named.py"])
        self.assertEqual(scope["declared_by"], {"test_named.py": []})

    def test_a_new_matching_module_moves_the_selection_and_the_fingerprint(self):
        self.module("test_grow.py")
        self.manifest({"test_grow.py": []})
        before = sandbox_scope.resolve(self.root, ["test_grow*.py"])
        fingerprint_before = core_unit.tree_fingerprint(self.root)
        self.module("test_grow_two.py")
        self.manifest({"test_grow.py": [], "test_grow_two.py": []})
        after = sandbox_scope.resolve(self.root, ["test_grow*.py"])
        self.assertEqual(before["selected"], ["test_grow.py"])
        self.assertEqual(after["selected"], ["test_grow.py", "test_grow_two.py"])
        self.assertNotEqual(
            core_unit.tree_fingerprint(self.root), fingerprint_before,
            "a new matching module changes the tested tree, so a record from "
            "the old selection cannot describe it",
        )

    def test_a_deleted_test_leaves_the_selection(self):
        first = self.module("test_keep.py")
        second = self.module("test_drop.py")
        self.manifest({"test_keep.py": [], "test_drop.py": []})
        self.assertEqual(
            sandbox_scope.resolve(self.root, ["test_*.py"])["selected"],
            ["test_drop.py", "test_keep.py"],
        )
        second.unlink()
        self.assertEqual(
            sandbox_scope.resolve(self.root, ["test_*.py"])["selected"],
            ["test_keep.py"],
        )
        self.assertTrue(first.exists())

    def test_a_focused_record_is_refused_after_a_new_matching_module(self):
        # The DoD clause end to end: a new module that the wildcard selects
        # moves the tested tree, so the earlier PASS cannot stand in for it.
        from saipen_engine.focused_unit import record_problem, run_focused

        (self.tools / "test_grow.py").write_text(
            "import unittest\n\n"
            "class Grow(unittest.TestCase):\n"
            "    def test_ok(self):\n"
            "        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        self.manifest({"test_grow.py": []})
        record = run_focused(self.root, ["test_grow*.py"], timeout=60)
        self.assertEqual(record["verdict"], "PASS", record.get("problem"))
        self.assertIsNone(record_problem(self.root, record))

        (self.tools / "test_grow_two.py").write_text("", encoding="utf-8")
        self.manifest({"test_grow.py": [], "test_grow_two.py": []})
        issue = record_problem(self.root, record)
        self.assertIsNotNone(issue)
        self.assertIn("different tree", issue)

    def test_a_changed_manifest_declaration_refuses_the_recorded_scope(self):
        self.module("test_scope.py")
        self.manifest({"test_scope.py": []})
        recorded = sandbox_scope.resolve(self.root, ["test_scope.py"])
        self.assertIsNone(sandbox_scope.is_current(
            recorded, sandbox_scope.resolve(self.root, ["test_scope.py"])
        ))
        self.manifest({"test_scope.py": [".saipen/evidence"]})
        current = sandbox_scope.resolve(self.root, ["test_scope.py"])
        issue = sandbox_scope.is_current(recorded, current)
        self.assertIsNotNone(issue)
        self.assertIn("sandbox scope changed", issue)

    def test_replay_after_a_wildcard_gains_a_declaration_is_refused(self):
        self.module("test_replay_a.py")
        self.module("test_replay_b.py")
        self.manifest({"test_replay_a.py": []})
        recorded = sandbox_scope.resolve(self.root, ["test_replay_*.py"])
        self.assertEqual(recorded["mode"], sandbox_scope.FULL)
        self.manifest({"test_replay_a.py": [], "test_replay_b.py": []})
        current = sandbox_scope.resolve(self.root, ["test_replay_*.py"])
        self.assertEqual(current["mode"], sandbox_scope.DECLARED)
        self.assertIsNotNone(sandbox_scope.is_current(recorded, current),
                             "a FULL record must not stand in for a run the "
                             "manifest now narrows")

    def test_identity_ignores_unrelated_manifest_entries(self):
        self.module("test_self.py")
        self.module("test_other.py")
        self.manifest({"test_self.py": []})
        first = sandbox_scope.resolve(self.root, ["test_self.py"])
        self.manifest({"test_self.py": [], "test_other.py": [".git"]})
        second = sandbox_scope.resolve(self.root, ["test_self.py"])
        self.assertEqual(
            sandbox_scope.identity(first), sandbox_scope.identity(second)
        )
        self.assertIsNone(sandbox_scope.is_current(first, second))


if __name__ == "__main__":
    unittest.main(verbosity=2)
