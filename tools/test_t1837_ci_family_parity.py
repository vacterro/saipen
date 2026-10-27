"""CI and local unit dispatch share complete execution, never a relaxed baseline."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from saipen_engine import core_unit, test_runner


TOOLS = Path(__file__).resolve().parent


def complete(**changes):
    return {
        "status": "PASS",
        "exit_code": 0,
        "ran": 2,
        "red": [],
        "headers": 0,
        "unparsed": 0,
        "tallied": 0,
        "sections": {},
        "fingerprint": "fixture",
        "jobs": 2,
        **changes,
    }


def brief(report):
    return [
        {key: value for key, value in item.items() if key != "verification_identity"}
        for item in report["families"]
    ]


class EmptyPartitionTests(unittest.TestCase):
    def members(self):
        def member(indices, **changes):
            return complete(
                ran=len(indices),
                membership_required=True,
                manifest={
                    "discovered": 2,
                    "selected": len(indices),
                    "inventory_sha256": "a" * 64,
                    "selected_indices": indices,
                },
                **changes,
            )

        return [member([0, 1]), member([], status="FAIL", exit_code=5, tallied=None)]

    def test_only_proved_empty_worker_is_neutral_and_raw_result_stays_visible(self):
        merged = core_unit.merge_shards(self.members())
        self.assertEqual(core_unit.judge(merged, [])["verdict"], "PASS", merged)
        self.assertEqual((merged["ran"], merged["status"], merged["exit_code"]), (2, "PASS", 0))
        self.assertEqual(merged["empty_shards"], [1])
        self.assertEqual((merged["shards"][1]["ran"], merged["shards"][1]["exit_code"]), (0, 5))

    def test_missing_mismatched_duplicate_and_error_members_still_refuse(self):
        for mutation in ("no-manifest", "wrong-digest", "duplicate", "error", "timeout"):
            members = self.members()
            if mutation == "no-manifest":
                members[1].pop("manifest")
            elif mutation == "wrong-digest":
                members[1]["manifest"]["inventory_sha256"] = "b" * 64
            elif mutation == "duplicate":
                members[0]["manifest"]["selected_indices"] = [0, 0]
            elif mutation == "error":
                members[1].update(red=["unittest.loader._FailedTest.test_bad"], headers=1)
            else:
                members[1].update(status="TIMEOUT", exit_code=None)
            with self.subTest(mutation=mutation):
                self.assertEqual(
                    core_unit.judge(core_unit.merge_shards(members), [])["verdict"], "FAIL"
                )

    def test_an_empty_whole_family_is_never_a_valid_partition(self):
        member = self.members()[1]
        member["manifest"]["discovered"] = 0
        merged = core_unit.merge_shards([member])
        self.assertEqual(core_unit.judge(merged, [])["verdict"], "FAIL")
        self.assertEqual(merged["empty_shards"], [])
        self.assertEqual(core_unit.judge(complete(ran=0), [])["verdict"], "FAIL")


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="saipen-ci-dispatch-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "subject"
        self.root.mkdir()
        (self.root / "state.txt").write_text("untouched", encoding="utf-8")

    def cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = test_runner.main(["--project-root", str(self.root), *args, "--json"])
        return code, json.loads(output.getvalue())

    def test_unit_cli_uses_existing_full_engine_without_a_lifecycle_citation(self):
        with mock.patch.object(
            core_unit, "run_family", return_value=complete()
        ) as execute, mock.patch.object(
            test_runner, "_run_family", side_effect=AssertionError("raw CI path")
        ):
            code, report = self.cli("--family", "unit", "--jobs", "2")
        self.assertEqual(code, 0, report)
        execute.assert_called_once_with(self.root.resolve(), jobs=2)
        self.assertEqual(report["families"][0]["ran"], 2)
        self.assertEqual(list(self.root.iterdir()), [self.root / "state.txt"])

    def test_whole_suite_uses_same_engine_and_keeps_other_families(self):
        registry = (core_unit.family(), test_runner.TestFamily("other", ("sentinel",), 5))
        with mock.patch.object(test_runner, "_families", return_value=registry), mock.patch.object(
            core_unit, "run_family", return_value=complete()
        ) as execute, mock.patch.object(
            test_runner, "_run_family", return_value={"name": "other", "status": "PASS"}
        ) as other:
            report = test_runner.run_canonical_suite(self.root, jobs=2)
        self.assertTrue(report["ok"], report)
        self.assertEqual([item["name"] for item in report["families"]], ["unit", "other"])
        self.assertEqual(execute.call_args.kwargs, {"jobs": 2})
        self.assertEqual(execute.call_args.args[0], other.call_args.args[0])
        self.assertEqual(other.call_args.args[1].name, "other")

    def test_ci_never_consults_an_inherited_red_allowance(self):
        name = "test_known.C.test_red"
        run = complete(
            status="FAIL",
            exit_code=1,
            red=[name],
            headers=1,
            tallied=1,
            sections={
                name: "FAIL: test_red (test_known.C.test_red)\nAssertionError: original cause"
            },
        )
        with mock.patch.object(core_unit, "run_family", return_value=run), mock.patch.object(
            core_unit, "load_baseline", side_effect=AssertionError("relaxed CI")
        ):
            code, report = self.cli("--family", "unit")
        self.assertEqual(code, 1, report)
        item = report["families"][0]
        self.assertEqual(item["failures"], [name])
        self.assertEqual(item["causes"][name], "AssertionError: original cause")

    def test_incomplete_timeout_partition_and_scoped_output_cannot_pass(self):
        bad = [
            complete(ran=0),
            complete(ran=None),
            complete(status="TIMEOUT", exit_code=None, timeout_s=3),
            complete(membership_required=True, membership_proof=None),
            complete(partition_error="duplicate/omitted occurrence"),
            complete(scope_kind="impact-subset"),
            complete(sandboxes_leaked=["owned-temp"]),
            complete(exit_code=7, stderr="startup traceback: concrete launch failure"),
        ]
        for run in bad:
            with self.subTest(run=run), mock.patch.object(
                core_unit, "run_family", return_value=run
            ):
                code, report = self.cli("--family", "unit")
            self.assertEqual(code, 1, report)
            self.assertFalse(report["ok"])
            self.assertTrue(report["families"][0]["detail"])
            if run.get("stderr"):
                self.assertIn("concrete launch failure", report["families"][0]["detail"])

    def test_historical_preclose_descendant_observation_is_preserved(self):
        # T-1633 observes owned children before ProcessTree.__exit__ reaps them.
        # Actual CLI tests below also check that every observed PID is now gone.
        with mock.patch.object(
            core_unit, "run_family", return_value=complete(processes_leaked=[123])
        ):
            code, report = self.cli("--family", "unit")
        self.assertEqual(code, 0, report)
        self.assertEqual(report["families"][0]["processes_leaked"], [123])

    def test_engine_failure_is_a_named_failed_family(self):
        with mock.patch.object(core_unit, "run_family", side_effect=OSError("copy refused")):
            code, report = self.cli("--family", "unit")
        self.assertEqual(code, 1)
        self.assertEqual(report["families"][0]["name"], "unit")
        self.assertIn("copy refused", report["families"][0]["detail"])

    def test_invalid_job_counts_refuse_before_any_execution(self):
        for value in ("0", "-2"):
            with self.subTest(value=value), mock.patch.object(
                core_unit, "run_family"
            ) as execute, contextlib.redirect_stderr(io.StringIO()), self.assertRaises(
                SystemExit
            ) as error:
                self.cli("--family", "unit", "--jobs", value)
            self.assertNotEqual(error.exception.code, 0)
            execute.assert_not_called()
        with self.assertRaises(ValueError):
            test_runner.run_canonical_suite(self.root, jobs=0)

    def test_unknown_family_does_not_execute_the_unit_engine(self):
        with mock.patch.object(core_unit, "run_family") as execute:
            code, report = self.cli("--family", "missing", "--jobs", "2")
        self.assertEqual(code, 1)
        self.assertIn("unknown family", report["families"][0]["detail"])
        execute.assert_not_called()


class ActualCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="saipen-ci-actual-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "subject"
        (self.root / "tools").mkdir(parents=True)
        (self.root / ".saipen").mkdir()
        for name in ("STATE", "BOARD", "LOG"):
            (self.root / ".saipen" / (name + ".md")).write_text(
                "unchanged " + name, encoding="utf-8"
            )

    def write(self, name, text):
        path = self.root / "tools" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def invoke(self, jobs, runner=None):
        before = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        run = subprocess.run(
            [
                sys.executable,
                "-B",
                str(runner or TOOLS / "test_runner.py"),
                "--project-root",
                str(self.root),
                "--family",
                "unit",
                "--jobs",
                str(jobs),
                "--json",
            ],
            cwd=self.base,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
        )
        after = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(before, after, "CI command changed its original subject/state")
        report = json.loads(run.stdout)
        self.assertEqual(run.returncode, 0 if report["ok"] else 1, run.stderr)
        for item in report["families"]:
            for pid in item.get("processes_leaked") or []:
                self.assertFalse(
                    core_unit.pid_alive(pid), f"owned child {pid} survived command return"
                )
        return report

    def test_real_sequential_and_sharded_discovery_preserve_imported_occurrences(self):
        self.write(
            "test_a.py",
            "import unittest\nclass Shared(unittest.TestCase):\n"
            " def test_one(self): self.assertEqual(1, 1)\n"
            " def test_two(self): self.assertTrue(True)\n",
        )
        self.write("test_b.py", "from test_a import Shared\n")
        self.write(
            "test_c.py",
            "import unittest\nclass Other(unittest.TestCase):\n"
            " def test_three(self): self.assertEqual(3, 3)\n",
        )
        records = [self.invoke(jobs) for jobs in (1, 2)]
        for report in records:
            self.assertTrue(report["ok"], brief(report))
            self.assertEqual(report["families"][0]["ran"], 5)
        self.assertEqual(records[1]["families"][0]["membership_proof"]["occurrences"], 5)

    def test_real_sharded_red_and_error_keep_names_causes_despite_baseline(self):
        self.write(
            "test_a.py",
            "import unittest\nclass Red(unittest.TestCase):\n"
            " def test_red(self): self.fail('deliberate red witness')\n",
        )
        self.write(
            "test_b.py",
            "import unittest\nclass Broken(unittest.TestCase):\n"
            " def test_error(self): raise RuntimeError('deliberate error witness')\n",
        )
        (self.root / "tools/core_unit_baseline.json").write_text(
            json.dumps({"schema": 1, "red": ["test_a.Red.test_red", "test_b.Broken.test_error"]}),
            encoding="utf-8",
        )
        report = self.invoke(2)
        self.assertFalse(report["ok"], report)
        item = report["families"][0]
        self.assertEqual(item["ran"], 2)
        self.assertEqual(item["failures"], ["test_a.Red.test_red", "test_b.Broken.test_error"])
        self.assertIn("deliberate red witness", item["causes"]["test_a.Red.test_red"])
        self.assertIn("deliberate error witness", item["causes"]["test_b.Broken.test_error"])

    def test_real_import_failure_remains_visible(self):
        self.write("test_a.py", "raise RuntimeError('import failure witness')\n")
        self.write(
            "test_b.py",
            "import unittest\nclass Good(unittest.TestCase):\n"
            " def test_good(self): self.assertTrue(True)\n",
        )
        report = self.invoke(2)
        self.assertFalse(report["ok"], report)
        item = report["families"][0]
        self.assertEqual(item["ran"], 2)
        self.assertTrue(any("test_a" in name for name in item["failures"]))
        self.assertIn("import failure witness", str(item["causes"]))

    def test_installed_engine_uses_same_interface_from_an_unrelated_directory(self):
        self.write(
            "test_pass.py",
            "import unittest\nclass Good(unittest.TestCase):\n"
            " def test_good(self): self.assertTrue(True)\n",
        )
        home = self.base / "installed/tools"
        home.mkdir(parents=True)
        shutil.copy2(TOOLS / "test_runner.py", home / "test_runner.py")
        shutil.copytree(
            TOOLS / "saipen_engine",
            home / "saipen_engine",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        report = self.invoke(2, home / "test_runner.py")
        self.assertTrue(report["ok"], brief(report))
        self.assertEqual(report["families"][0]["ran"], 1)


if __name__ == "__main__":
    unittest.main()
