"""Real CLI consumers share exact executions; incompatible or corrupt proof refuses."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import unittest
from contextlib import suppress
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import core_unit, verification_cache as cache  # noqa: E402
from test_core_unit_gate import CoreUnitFixture, _run  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule():
    isolate_host_session()


def wait_for(predicate, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("owned verification barrier did not become ready")


class CompatibilityTests(CoreUnitFixture):
    def test_changed_effective_environment_refuses_pass_reuse_and_ship(self):
        self.reach_review()
        with mock.patch.dict(os.environ, {"SAIPEN_TEST_MODE": "first"}):
            written = self.cite(_run([]))
            self.assertIsNotNone(core_unit.reusable_record(self.project, self.fingerprint()))
        with mock.patch.dict(os.environ, {"SAIPEN_TEST_MODE": "second"}):
            self.assertIsNone(core_unit.reusable_record(self.project, self.fingerprint()))
            self.assertFalse(
                cache.compatible(self.project, written["record"]["verification_identity"])
            )
            self.assertIn("environment", self.to("SHIP").message)

    def fingerprint(self):
        return core_unit.tree_fingerprint(self.project)

    def test_configuration_and_interpreter_changes_are_not_compatible(self):
        configuration = core_unit.verification_configuration(jobs=1, timeout=30)
        first = cache.capture(self.project, configuration)
        second = cache.capture(self.project, {**configuration, "timeout": 31})
        self.assertNotEqual(first, second)
        with mock.patch.object(cache.sys, "version", sys.version + " changed"):
            self.assertFalse(cache.compatible(self.project, first))

    def test_profile_configuration_changes_without_source_change_invalidate(self):
        profile = self.project.parent / "profile"
        profile.mkdir()
        settings = profile / "config.toml"
        settings.write_text("mode = 'first'\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"CODEX_HOME": str(profile)}):
            before = self.fingerprint()
            identity = cache.capture(self.project, {"family": "unit"})
            settings.write_text("mode = 'second'\n", encoding="utf-8")
            self.assertEqual(before, self.fingerprint())
            self.assertFalse(cache.compatible(self.project, identity))

    def test_latest_compatible_red_never_resurrects_an_older_pass(self):
        older = core_unit.write_record(self.project, _run([]), self.fingerprint())
        path = self.project / older["path"]
        path.rename(path.with_name(f"{self.fingerprint()[:16]}-20000101T000000Z.json"))
        core_unit.write_record(self.project, _run(["test_new.New.test_red"]), self.fingerprint())
        self.assertIsNone(core_unit.reusable_record(self.project, self.fingerprint()))

    def test_tool_bytes_change_even_when_path_size_and_mtime_do_not(self):
        tool = self.project.parent / "tool.exe"
        tool.write_bytes(b"first")
        metadata = tool.stat()
        with mock.patch.object(cache, "_TOOLS", ("probe",)), mock.patch.object(
            cache.shutil, "which", return_value=str(tool)
        ):
            identity = cache.capture(self.project, {"family": "unit"})
            tool.write_bytes(b"other")
            os.utime(tool, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
            self.assertFalse(cache.compatible(self.project, identity))

    def test_stripped_host_carriers_do_not_make_equivalent_test_environments_different(self):
        with mock.patch.dict(os.environ, {"SAIPEN_AGENT": "first", "PYTHONPATH": "first"}):
            first = cache.capture(self.project, {"family": "unit"})
        with mock.patch.dict(os.environ, {"SAIPEN_AGENT": "second", "PYTHONPATH": "second"}):
            second = cache.capture(self.project, {"family": "unit"})
        self.assertEqual(first, second)

    def test_runtime_manifest_search_never_treats_a_home_ancestor_as_a_package(self):
        home = self.project.parent / "profile"
        binary = home / "bin/tool.exe"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"tool")
        (home / "package.json").write_text("{}", encoding="utf-8")
        with mock.patch.object(
            core_unit, "tree_fingerprint", side_effect=AssertionError("broad walk")
        ):
            identity = cache._tool_identity("probe", str(binary), {})
        self.assertNotIn("package", identity)

    def test_unknown_script_runtime_disables_historical_replay(self):
        shim = self.project.parent / "unknown/opencode.cmd"
        shim.parent.mkdir()
        shim.write_text("@echo off\n", encoding="utf-8")
        identity = cache._tool_identity("opencode", str(shim), {})
        self.assertFalse(cache.replay_supported({"toolchain": {"opencode": identity}}))

    def test_legacy_unknown_environment_is_readable_but_not_reusable(self):
        written = core_unit.write_record(self.project, _run([]), self.fingerprint())
        path = self.project / written["path"]
        data = json.loads(path.read_text())
        del data["verification_identity"]
        path.write_text(json.dumps(data))
        self.assertIsNone(core_unit.reusable_record(self.project, self.fingerprint()))
        self.assertEqual(core_unit.judge(data, [])["verdict"], "PASS")


class FlightRecoveryTests(CoreUnitFixture):
    def guard_directory_after_owner_death(self, before_registration):
        barrier = self.project / ".saipen/guard.json"
        code = (
            "import sys,json,time,os; from pathlib import Path; "
            f"sys.path.insert(0,{str(TOOLS)!r}); "
            "from saipen_engine.process_tree import ProcessTree; tree=ProcessTree()\n"
            "def note(process):\n"
            f" Path({str(barrier)!r}).write_text(json.dumps("
            "{'group':process.pid,'directory':tree._guard_dir.name}))\n"
            + (" time.sleep(60)\n" if before_registration else "")
            + "process=tree.start([sys.executable,'-c','import time; time.sleep(60)'],"
            "env={**os.environ,'SAIPEN_CANONICAL_TEST_CHILD':'1'},"
            + ("on_started=note)\n" if before_registration else ")\nnote(process)\n")
            + "time.sleep(60)\n"
        )
        owner = subprocess.Popen([sys.executable, "-B", "-c", code],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        group, directory = None, None
        try:
            wait_for(barrier.is_file)
            info = json.loads(barrier.read_text())
            group, directory = info["group"], Path(info["directory"])
            owner.kill()
            owner.wait(timeout=10)
            from saipen_engine.process_tree import ProcessTree

            wait_for(lambda: not ProcessTree.group_pids(group))
            self.assertFalse(directory.exists(), "dead owner's guard directory leaked")
        finally:
            if owner.poll() is None:
                owner.kill()
                owner.wait(timeout=10)
            if group is not None:
                with suppress(ProcessLookupError):
                    os.killpg(group, signal.SIGKILL)
            if directory is not None:
                # Only the private path returned by our own launcher is ours.
                self.assertTrue(directory.name.startswith("saipen-process-guard-"))
                for name in ("reader-ready", "guardian.json"):
                    with suppress(FileNotFoundError):
                        (directory / name).unlink()
                with suppress(FileNotFoundError):
                    directory.rmdir()

    @unittest.skipIf(os.name == "nt", "POSIX pipe guardian")
    def test_dead_owner_reclaims_guard_before_reader_registration(self):
        self.guard_directory_after_owner_death(True)

    @unittest.skipIf(os.name == "nt", "POSIX pipe guardian")
    def test_dead_owner_reclaims_guard_after_reader_registration(self):
        self.guard_directory_after_owner_death(False)

    def identity(self):
        return {
            "family": "unit",
            "fingerprint": core_unit.tree_fingerprint(self.project),
            "verification_identity": cache.capture(
                self.project, core_unit.verification_configuration()
            ),
        }

    def publish(self, flight, red=()):
        written = core_unit.write_record(self.project, _run(red), flight.identity["fingerprint"])
        flight.publish(written)
        return written

    def test_cached_failure_is_shared_as_failure(self):
        identity = self.identity()
        with cache.single_flight(self.project, identity) as first:
            self.publish(first, ["test_new.New.test_red"])
        with cache.single_flight(self.project, identity) as second:
            self.assertTrue(second.reused)
            self.assertEqual(second.written["record"]["verdict"], "FAIL")

    def test_tampered_receipt_and_scope_mismatch_fail_closed(self):
        identity = self.identity()
        with cache.single_flight(self.project, identity) as first:
            written = self.publish(first)
        path = self.project / written["path"]
        path.write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError), cache.single_flight(self.project, identity):
            self.fail("tampered result was admitted")
        incompatible = {**identity, "family": "focused-unit"}
        with self.assertRaises(ValueError), cache.single_flight(
            self.project, incompatible
        ) as flight:
            flight.publish(written)

    def test_cancelled_executor_does_not_keep_the_os_owner(self):
        identity = self.identity()
        with self.assertRaises(KeyboardInterrupt), cache.single_flight(self.project, identity):
            raise KeyboardInterrupt()
        with cache.single_flight(self.project, identity, timeout=2) as recovered:
            self.assertIsNone(recovered.written)
            self.publish(recovered)

    def test_waiter_timeout_does_not_cancel_the_executor(self):
        identity = self.identity()
        with cache.single_flight(self.project, identity) as first:
            with self.assertRaises(TimeoutError), cache.single_flight(
                self.project, identity, timeout=0.05
            ):
                self.fail("second executor started")
            self.publish(first)
        with cache.single_flight(self.project, identity) as reused:
            self.assertTrue(reused.reused)

    def test_incompatible_requests_are_bounded_by_one_project_executor(self):
        identity = self.identity()
        other = {**identity, "family": "focused-unit"}
        with cache.single_flight(self.project, identity) as first:
            with self.assertRaises(TimeoutError), cache.single_flight(
                self.project, other, timeout=0.05
            ):
                self.fail("incompatible concurrent executor started")
            self.publish(first)

    def test_owner_process_death_releases_the_execution_lock(self):
        identity = self.identity()
        request = self.project / ".saipen/request.json"
        # This fixture carrier is input to the process test, not operator authority.
        request.write_text(json.dumps(identity))
        ready = self.project / ".saipen/ready"
        code = (
            "import sys,json,time; from pathlib import Path; "
            f"sys.path.insert(0,{str(TOOLS)!r}); "
            "from saipen_engine.verification_cache import single_flight; "
            f"root=Path({str(self.project)!r}); "
            f"identity=json.loads(Path({str(request)!r}).read_text()); "
            f"\nwith single_flight(root,identity):\n Path({str(ready)!r}).write_text('ready')\n"
            " time.sleep(30)\n"
        )
        process = subprocess.Popen(
            [sys.executable, "-B", "-c", code],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            wait_for(ready.exists)
            process.kill()
            process.communicate(timeout=10)
            with cache.single_flight(self.project, identity, timeout=2) as recovered:
                self.assertIsNone(recovered.written)
                self.publish(recovered)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=10)


class RealConcurrentCliTests(CoreUnitFixture):
    def concurrent(self, *, fail=False, fresh=False):
        self.assertTrue(self.to("VERIFY").ok)
        events = self.project / ".saipen/cache/executions.txt"
        release = self.project / ".saipen/cache/release"
        entered = self.project / ".saipen/cache/entered"
        source = (
            "import pathlib,time,unittest\nclass Probe(unittest.TestCase):\n"
            "    def test_control(self):\n"
            f"        events=pathlib.Path({str(events)!r})\n"
            "        events.parent.mkdir(parents=True,exist_ok=True)\n"
            "        with events.open('a') as stream: stream.write('executed\\n')\n"
            f"        pathlib.Path({str(entered)!r}).write_text('ready')\n"
            f"        release=pathlib.Path({str(release)!r}); end=time.monotonic()+15\n"
            "        while not release.exists() and time.monotonic()<end: time.sleep(0.01)\n"
            "        self.assertTrue(release.exists(), 'release barrier missing')\n"
            + ("        self.fail('deliberate red')\n" if fail else "")
        )
        (self.project / "tools/test_probe.py").write_text(source, encoding="utf-8")
        command = [
            sys.executable,
            "-B",
            str(TOOLS / "core_unit.py"),
            "evidence",
            "T-7",
            "--project-root",
            str(self.project),
            "--agent",
            "tester",
            "--jobs",
            "1",
            "--timeout",
            "30",
        ]
        if fresh:
            command.append("--fresh")
        processes = [
            subprocess.Popen(
                command,
                cwd=self.project,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            for _ in range(3)
        ]
        try:
            wait_for(entered.exists)
            observations = self.project / ".saipen/cache/verification-observations"
            wait_for(lambda: len(list(observations.glob("*.json"))) == 3)
            consumers = [json.loads(path.read_text()) for path in observations.glob("*.json")]
            self.assertEqual({row.get("ticket") for row in consumers}, {"T-7"})
            release.write_text("release")
            results = []
            for process in processes:
                out, err = process.communicate(timeout=30)
                self.assertEqual(process.returncode, 1 if fail else 0, out + err)
                results.append(json.loads(out))
            self.assertEqual(events.read_text().splitlines(), ["executed"])
            self.assertEqual(len({row["record"] for row in results}), 1)
            self.assertEqual(sum(row["shared"] for row in results), 2)
            self.assertTrue(all(row["verdict"] == ("FAIL" if fail else "PASS") for row in results))
            records = list((self.project / core_unit.RECORD_DIR_REL).glob("*.json"))
            self.assertEqual(len(records), 1)
        finally:
            release.parent.mkdir(parents=True, exist_ok=True)
            release.write_text("release")
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=10)

    def test_three_compatible_consumers_share_one_real_execution(self):
        self.concurrent()

    def test_concurrent_fresh_consumers_join_the_same_new_execution(self):
        self.concurrent(fresh=True)

    def test_real_failure_is_propagated_to_every_consumer(self):
        self.concurrent(fail=True)


if __name__ == "__main__":
    unittest.main()
