"""Impact selection must prefer explicit full escalation to omitted coverage."""

import copy
import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from saipen_engine import core_unit, focused_unit, verification_impact as impact
from test_core_unit_gate import CoreUnitFixture, _run
from test_hermetic_env import isolate_host_session

PURE = "def add(value):\n    return value + 1\n"
LEAF_TEST = ("import unittest\nfrom pure import add\n"
             "class Leaf(unittest.TestCase):\n"
             "    def test_add(self):\n        self.assertEqual(add(1),2)\n")
OTHER_TEST = ("import unittest\nclass Other(unittest.TestCase):\n"
              "    def test_other(self):\n        self.assertTrue(True)\n")


def setUpModule():
    isolate_host_session()


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def seed(root):
    write(root, "tools/pure.py", PURE)
    write(root, "tools/test_leaf.py", LEAF_TEST)
    write(root, "tools/test_other.py", OTHER_TEST)


class ImpactPlans(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="t1836-impact-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        seed(self.root)

    def plan(self, *paths):
        return impact.plan(self.root, list(paths or ("tools/pure.py",)))

    def test_known_static_subset_has_source_inventory_and_reasons(self):
        plan = self.plan()
        self.assertEqual(plan["tier"], "IMPACT", plan["unknown_coverage"])
        self.assertEqual(plan["selected_tests"], ["test_leaf"])
        self.assertEqual(plan["selector_modules"], ["pure", "test_leaf"])
        self.assertEqual(plan["focused_tests"], ["test_leaf"])
        self.assertFalse(plan["executed"])
        self.assertEqual(len(plan["source_inventory_sha256"]), 64)
        self.assertIn("tools/pure.py", plan["selection_reasons"]["test_leaf"][0])

    def test_transitive_consumers_are_required_integrations(self):
        write(self.root, "tools/middle.py",
              "from pure import add\ndef twice(x): return add(add(x))\n")
        write(self.root, "tools/test_middle.py", LEAF_TEST.replace("from pure import add",
              "from middle import twice as add").replace("add(1),2", "add(1),3"))
        plan = self.plan()
        self.assertIn("test_middle", plan["selected_tests"])
        self.assertIn("test_middle", plan["integration_tests"])
        self.assertIn("middle", plan["selector_modules"])

    def test_new_unrelated_test_is_selected_when_in_change_inventory(self):
        write(self.root, "tools/test_added.py", OTHER_TEST)
        plan = self.plan("tools/pure.py", "tools/test_added.py")
        self.assertIn("test_added", plan["selected_tests"])
        self.assertIn("test_added", plan["test_inventory"])

    def test_relative_import_and_package_initializer_are_dependencies(self):
        write(self.root, "tools/pkg/__init__.py", "from .leaf import add\n")
        write(self.root, "tools/pkg/leaf.py", PURE)
        write(self.root, "tools/test_pkg.py",
              LEAF_TEST.replace("from pure import add", "from pkg import add"))
        plan = self.plan("tools/pkg/leaf.py")
        self.assertEqual(plan["tier"], "IMPACT", plan["unknown_coverage"])
        self.assertIn("test_pkg", plan["selected_tests"])
        self.assertIn("pkg.leaf", plan["selector_modules"])

    def test_standard_library_shadowing_does_not_hide_local_dependencies(self):
        write(self.root, "tools/math.py", "from pure import add\n")
        write(self.root, "tools/test_shadow.py", "import math\n")
        plan = self.plan()
        self.assertEqual(plan["tier"], "FULL")
        self.assertTrue(any("collision" in issue for issue in plan["unknown_coverage"]))

    def test_protocol_markdown_fixture_adapter_and_validator_require_full(self):
        for name in ("saipen/CORE.md", "tests/fixtures/sample.json", "extensions/adapter.py",
                     "tools/validate.py", "tools/test_fixture_shared.py"):
            with self.subTest(name=name):
                write(self.root, name, "# contract\n")
                plan = self.plan(name)
                self.assertEqual(plan["tier"], "FULL")
                self.assertEqual(plan["selected_tests"], plan["test_inventory"])
                self.assertTrue(all(plan["selection_reasons"][test]
                                    for test in plan["selected_tests"]))

    def test_shared_fixture_hooks_are_not_treated_as_a_leaf(self):
        write(self.root, "tools/support.py", "def setUpModule():\n    pass\n")
        self.assertEqual(self.plan("tools/support.py")["tier"], "FULL")

    def test_unresolved_dynamic_file_and_reflection_dependencies_escalate(self):
        for source in ("import missing_external\n", "x=__import__('pure')\n",
                       "x=open('hidden.md').read()\n", "x=getattr(object,'__dict__')\n",
                       "import unittest\nx=unittest.os.environ\n"):
            with self.subTest(source=source):
                write(self.root, "tools/test_unknown.py", source)
                plan = self.plan()
                self.assertEqual(plan["tier"], "FULL")
                self.assertTrue(plan["unknown_coverage"])

    def test_alias_escape_callback_and_builtin_shadowing_are_unknown(self):
        for source in ("import unittest\nu=unittest\nlen=u.os.open\n",
                       "def invoke(callback): return callback('hidden.py')\n",
                       "from operator import attrgetter\n",
                       "import unittest\nclass Foreign(unittest.TestCase):\n"
                       "    __module__='another_module'\n",
                       "def invoke(len): return len('hidden.py')\n"):
            with self.subTest(source=source):
                write(self.root, "tools/test_unknown.py", source)
                self.assertEqual(self.plan()["tier"], "FULL")

    def test_syntax_error_load_tests_and_no_consumer_escalate(self):
        for name, text in (("tools/broken.py", "def broken(\n"),
                           ("tools/test_loader.py", "def load_tests(*args): return args[0]\n"),
                           ("tools/uncovered.py", "VALUE = 1\n")):
            with self.subTest(name=name):
                path = write(self.root, name, text)
                self.assertEqual(self.plan(name)["tier"], "FULL")
                path.unlink()

    def test_deletion_and_unknown_nonpython_path_do_not_look_unaffected(self):
        self.assertEqual(self.plan("tools/deleted.py")["tier"], "FULL")
        write(self.root, "tools/data.txt", "data")
        self.assertEqual(self.plan("tools/data.txt")["tier"], "FULL")

    def test_stale_or_modified_plan_is_rejected(self):
        selection = self.plan()
        self.assertIsNone(impact.problem(self.root, selection))
        forged = copy.deepcopy(selection)
        forged["selected_tests"] = []
        self.assertIsNotNone(impact.problem(self.root, forged))
        write(self.root, "tools/test_new.py", OTHER_TEST)
        self.assertIsNotNone(impact.problem(self.root, selection))

    def test_no_changes_is_a_nonexecuted_static_plan_and_paths_are_confined(self):
        plan = impact.plan(self.root, [".saipen/STATE.md"])
        self.assertEqual(plan["tier"], "STATIC")
        self.assertFalse(plan["executed"])
        for bad in ("../outside.py", "/outside.py", "C:/outside.py", ""):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                impact.plan(self.root, [bad])

    def test_real_git_inventory_includes_added_tests_and_preserves_spaces(self):
        for args in (("init", "-q"), ("add", "."),
                     ("-c", "user.name=fixture", "-c", "user.email=fixture@invalid",
                      "commit", "-qm", "fixture")):
            result = subprocess.run(["git", "-C", str(self.root), *args],
                                    stdin=subprocess.DEVNULL, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
        write(self.root, "tools/test_added.py", OTHER_TEST)
        write(self.root, "tools/has space.py", "VALUE=1\n")
        changes = impact.git_changes(self.root)
        self.assertIn("tools/test_added.py", changes)
        self.assertIn("tools/has space.py", changes)

    def test_missing_git_is_an_explicit_scope_diagnostic(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("git")), \
                self.assertRaisesRegex(ValueError, "explicit --changed"):
            impact.git_changes(self.root)


class ImpactExecution(CoreUnitFixture):
    def setUp(self):
        super().setUp()
        seed(self.project)
        write(self.project, "tools/verification_policy.json", json.dumps(focused_unit.POLICY))
        self.assertTrue(self.to("VERIFY").ok)

    def run_impact(self):
        selection = impact.plan(self.project, ["tools/pure.py"])
        self.assertEqual(selection["tier"], "IMPACT", selection["unknown_coverage"])
        return focused_unit.run_focused(self.project, ["test_*.py"], timeout=30,
                                        selection=selection)

    def test_real_selected_run_keeps_family_scope_and_does_not_run_unrelated_red(self):
        write(self.project, "tools/test_other.py", OTHER_TEST.replace(
            "self.assertTrue(True)", "self.fail('outside changed scope')"))
        record = self.run_impact()
        self.assertEqual(record["verdict"], "PASS", record.get("problem"))
        self.assertEqual(record["family"], "focused-unit")
        self.assertEqual(record["verification_tier"], "IMPACT")
        self.assertEqual(record["ran"], 1)
        self.assertIsNone(focused_unit.record_problem(self.project, record))
        self.assertIsNotNone(focused_unit.publication_gate(self.project))

    def test_unrelated_import_error_cannot_disappear_in_a_filtered_run(self):
        write(self.project, "tools/test_import.py",
              "raise RuntimeError('unexpected import error')\n")
        record = self.run_impact()
        self.assertEqual(record["verdict"], "FAIL")
        self.assertTrue(any("test_import" in name for name in record["runs"][0]["red"]))
        self.assertNotIn("origin mismatch", record["problem"])

    def test_imported_testcase_occurrences_and_fixture_order_are_preserved(self):
        support = (
            "import unittest\nfrom pure import add\nPHASE=0\nCOUNT=0\n"
            "def setUpModule():\n    global PHASE,COUNT\n    PHASE=1\n    COUNT=0\n"
            "def tearDownModule():\n    global PHASE\n"
            "    if COUNT!=2: raise AssertionError('canonical multiplicity lost')\n"
            "    PHASE=3\nclass Shared(unittest.TestCase):\n"
            "    def test_add(self):\n        global COUNT\n"
            "        self.assertEqual(PHASE,1)\n        COUNT+=1\n"
            "        self.assertEqual(add(1),2)\n"
        )
        write(self.project, "tools/support.py", support)
        write(self.project, "tools/test_alias.py", "from support import Shared\n")
        write(self.project, "tools/test_alias_two.py", "from support import Shared\n")
        write(self.project, "tools/test_leaf.py", "import support\n" + LEAF_TEST.replace(
            "self.assertEqual(add(1),2)",
            "self.assertEqual(support.PHASE,3)\n        self.assertEqual(add(1),2)"))
        record = self.run_impact()
        self.assertEqual(record["verdict"], "PASS", record.get("problem"))
        self.assertEqual(record["ran"], 3)
        self.assertIn("support", record["impact_selection"]["selector_modules"])
        manifest = record["runs"][0]["manifest"]
        self.assertEqual(sum(item[0] == "support.Shared.test_add"
                             for item in manifest["inventory"]), 2)
        tampered = copy.deepcopy(record)
        tampered["runs"][0]["manifest"]["selected_indices"] = [
            manifest["selected_indices"][0]] * 2
        self.assertIn("omits or duplicates", focused_unit.record_problem(self.project, tampered))

    def test_nested_canonical_modules_use_the_same_discovery_root(self):
        write(self.project, "tools/pkg/__init__.py", "")
        write(self.project, "tools/pkg/leaf.py", PURE)
        write(self.project, "tools/pkg/test_nested.py", LEAF_TEST.replace(
            "from pure import add", "from pkg.leaf import add"))
        selection = impact.plan(self.project, ["tools/pkg/leaf.py"])
        self.assertEqual(selection["tier"], "IMPACT", selection["unknown_coverage"])
        record = focused_unit.run_focused(self.project, ["test_*.py"], timeout=30,
                                          selection=selection)
        self.assertEqual(record["verdict"], "PASS", record.get("problem"))
        self.assertEqual(record["ran"], 1)

    def test_runtime_preload_cannot_replace_an_analyzed_module(self):
        original = core_unit.SHARD_RUNNER
        wrapper = self.project.parent / "preload_driver.py"
        wrapper.write_text(
            "import sys,types,runpy\nmodule=types.ModuleType('pure')\n"
            "module.__file__='/foreign/pure.py'\nmodule.add=lambda value:value+1\n"
            "sys.modules['pure']=module\n"
            f"runpy.run_path({str(original)!r},run_name='__main__')\n", encoding="utf-8")
        with mock.patch.object(core_unit, "SHARD_RUNNER", wrapper):
            record = self.run_impact()
        self.assertEqual(record["verdict"], "FAIL")
        self.assertIn("origin mismatch", record["problem"])

    def test_full_or_static_plan_does_not_execute_or_create_citation(self):
        before = {name: (self.project / ".saipen" / name).read_bytes()
                  for name in ("STATE.md", "BOARD.md", "LOG.md")}
        output = io.StringIO()
        with redirect_stdout(output):
            rc = core_unit.main(["impact", "T-7", "--project-root", str(self.project),
                                 "--changed", "saipen/CORE.md"])
        self.assertEqual(rc, 1)
        self.assertFalse(json.loads(output.getvalue())["executed"])
        self.assertEqual(before, {name: (self.project / ".saipen" / name).read_bytes()
                                  for name in before})

    def test_cli_plan_is_read_only_and_real_impact_producer_cites_scoped_record(self):
        base = ["impact", "T-7", "--agent", "tester", "--project-root", str(self.project),
                "--changed", "tools/pure.py", "--timeout", "30"]
        before = (self.project / ".saipen/LOG.md").read_bytes()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(core_unit.main([*base, "--plan"]), 0)
        self.assertEqual(before, (self.project / ".saipen/LOG.md").read_bytes())
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(core_unit.main(base), 0)
        result = json.loads(output.getvalue())
        record = json.loads((self.project / result["record"]).read_text())
        self.assertEqual(record["verification_tier"], "IMPACT")
        from verification_metrics import collect

        economics = collect(self.project)
        self.assertEqual(economics["impact"]["records"], 1)
        self.assertEqual(economics["focused"]["records"], 0)
        self.assertGreater(economics["impact"]["measured_wall_s"], 0)
        self.assertIn("FOCUSED-UNIT-EVIDENCE", (self.project / ".saipen/LOG.md").read_text())
        self.assertIsNotNone(focused_unit.publication_gate(self.project))

    def test_explicit_cli_scope_still_includes_git_added_tests(self):
        for args in (("init", "-q"), ("add", "."),
                     ("-c", "user.name=fixture", "-c", "user.email=fixture@invalid",
                      "commit", "-qm", "fixture")):
            result = subprocess.run(["git", "-C", str(self.project), *args],
                                    stdin=subprocess.DEVNULL, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
        write(self.project, "tools/test_added.py", OTHER_TEST)
        output = io.StringIO()
        with redirect_stdout(output):
            rc = core_unit.main(["impact", "T-7", "--agent", "tester", "--project-root",
                                 str(self.project), "--changed", "tools/pure.py",
                                 "--timeout", "30"])
        self.assertEqual(rc, 0, output.getvalue())
        record = json.loads((self.project / json.loads(output.getvalue())["record"]).read_text())
        self.assertIn("test_added", record["impact_selection"]["selected_tests"])
        self.assertEqual(record["ran"], 2)

    def test_forged_full_label_and_scope_configuration_are_rejected(self):
        record = self.run_impact()
        self.assertEqual(record["verdict"], "PASS", record.get("problem"))
        self.assertIsNone(focused_unit.record_problem(self.project, record))
        record["verification_tier"] = "FULL"
        self.assertIn("contract", focused_unit.record_problem(self.project, record))
        with self.assertRaisesRegex(ValueError, "scope"):
            core_unit.write_record(self.project, record["runs"][0], record["fingerprint"])
        selection = impact.plan(self.project, ["tools/pure.py"])
        self.assertNotEqual(focused_unit.configuration(["test_*.py"], 30),
                            focused_unit.configuration(["test_*.py"], 30, selection))

    def test_relabelled_unit_record_cannot_keep_an_impact_configuration(self):
        impact_record = self.run_impact()
        written = core_unit.write_record(self.project, _run([], ran=1),
                                         impact_record["fingerprint"])
        data = written["record"]
        data["verification_identity"] = impact_record["verification_identity"]
        (self.project / written["path"]).write_text(json.dumps(data), encoding="utf-8")
        self.assertIsNotNone(focused_unit.publication_gate(self.project))
