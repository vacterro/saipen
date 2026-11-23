"""T-2049 safety suite: the collector keeps proof and refuses what it cannot prove.

Every destructive route here runs against a disposable project, and the
zero-write guarantee is checked from the bytes on disk, not from the report.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from saipen_engine import gc
from saipen_engine.command_effects import classify_invocation, is_known_verb

SAIPEN_PY = str(Path(__file__).with_name("saipen.py"))


def _git(root: Path, *argv: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *argv],
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
            "HOME": str(root),
            "PATH": os.environ["PATH"],
        },
    )


class GcSafety(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "proj"
        self.root.mkdir()
        _git(self.root, "init")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # ---------------------------------------------------------------- helpers

    def _write(self, relative: str, payload: bytes = b"x") -> Path:
        node = self.root / relative
        node.parent.mkdir(parents=True, exist_ok=True)
        node.write_bytes(payload)
        return node

    def _commit_all(self) -> None:
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "--allow-empty", "-m", "seed")

    def _assert_zero_write(self) -> None:
        self.assertFalse((self.root / ".saipen/GC_STATE.json").exists())
        self.assertFalse((self.root / ".saipen/gc").exists())

    def _unborn_root(self) -> None:
        # A repository with a commit is what the guard proves; keep it unborn so
        # the guard's unborn branch is the one under test.
        pass

    # ------------------------------------------------------------------ tests

    def test_plan_and_audit_write_nothing(self) -> None:
        cache = self._write("work/__pycache__/module.pyc", b"bytecode")
        self._commit_all()
        before = cache.read_bytes()
        plan = gc.plan(self.root)
        self.assertTrue(plan["git_guard"]["ok"], plan["git_guard"])
        audit = gc.audit(self.root)
        self.assertIn("schema", audit)
        self.assertEqual(cache.read_bytes(), before)
        self._assert_zero_write()
        self.assertEqual(plan["state_health"], "missing")

    def test_hard_link_inside_a_cache_tree_is_kept(self) -> None:
        # A second name for the bytes means the owner is not proven: the whole
        # cache-named directory is kept, and the class names why it was.
        cache = self._write("work/__pycache__/module.pyc", b"bytecode")
        alias = self._write("work/__pycache__/alias.pyc")
        alias.unlink()
        alias.hardlink_to(cache)
        self._commit_all()
        plan = gc.plan(self.root)
        paths = {entry["path"] for entry in plan["targets"]}
        kept = {entry["path"]: entry["class"] for entry in plan["kept_entries"]}
        self.assertNotIn("work/__pycache__", paths)
        self.assertIn(kept.get("work/__pycache__"), (gc.UNKNOWN_OWNERSHIP, gc.PROTECTED_GIT))

    def test_user_content_inside_a_cache_tree_is_kept(self) -> None:
        # A cache-named tree holding non-bytecode content is user data, not
        # rebuildable cache: nothing about it may be reclaimed.
        self._write("work/__pycache__/notes.txt", b"do not delete me")
        plan = gc.plan(self.root)
        paths = {entry["path"] for entry in plan["targets"]}
        self.assertNotIn("work/__pycache__", paths)
        self.assertTrue((self.root / "work/__pycache__/notes.txt").exists())

    def test_ephemeral_cache_is_the_only_planned_class(self) -> None:
        # Only an UNTRACKED cache tree with nothing but rebuildable bytecode is
        # a plan target; committing it hands Git ownership and keeps it.
        self._write("src/module.py", b"print(1)\n")
        self._commit_all()
        cache = self._write("work/__pycache__/module.pyc", b"bytecode")
        plan = gc.plan(self.root)
        self.assertEqual([entry["path"] for entry in plan["targets"]], ["work/__pycache__"])
        self.assertEqual(plan["targets"][0]["class"], gc.EPHEMERAL_REPRODUCIBLE)
        self.assertTrue(cache.exists())

    def test_tracked_descendant_refuses_the_whole_directory(self) -> None:
        # The work/__pycache__/tracked.pyc regression: protecting a path's exact
        # identity does not protect its descendants, so a directory target with
        # ANY Git-owned descendant is refused whole.
        self._write("work/__pycache__/tracked.pyc", b"bytecode")
        self._commit_all()
        plan = gc.plan(self.root)
        paths = {entry["path"] for entry in plan["targets"]}
        kept = {entry["path"]: entry["class"] for entry in plan["kept_entries"]}
        self.assertNotIn("work/__pycache__", paths)
        self.assertEqual(kept.get("work/__pycache__"), gc.PROTECTED_GIT)

    def test_staged_descendant_refuses_the_whole_directory(self) -> None:
        self._write("work/__pycache__/module.pyc", b"bytecode")
        _git(self.root, "add", "work/__pycache__/module.pyc")
        plan = gc.plan(self.root)
        self.assertNotIn(
            "work/__pycache__", {entry["path"] for entry in plan["targets"]}
        )
        kept = {entry["path"]: entry["class"] for entry in plan["kept_entries"]}
        self.assertEqual(kept.get("work/__pycache__"), gc.PROTECTED_GIT)

    def test_dirty_descendant_refuses_the_whole_directory(self) -> None:
        self._write("work/__pycache__/module.pyc", b"tracked")
        self._commit_all()
        (self.root / "work/__pycache__/module.pyc").write_bytes(b"changed")
        plan = gc.plan(self.root)
        self.assertNotIn(
            "work/__pycache__", {entry["path"] for entry in plan["targets"]}
        )

    def test_reparse_ancestor_never_traverses_to_outside_bytes(self) -> None:
        outside = Path(self._tmp.name) / "outside"
        (outside / "old").mkdir(parents=True)
        (outside / "old/app.js").write_bytes(b"foreign build payload\n")
        junction = self.root / "dist"
        made = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
            capture_output=True,
        )
        if made.returncode != 0:
            self.skipTest(f"junction unavailable on this host: {made.stderr!r}")
        self._write("src/module.py", b"print(1)\n")
        self._commit_all()

        plan = gc.plan(self.root)

        self.assertNotIn(
            "dist/old", {entry["path"] for entry in plan["targets"]}
        )
        self.assertTrue((outside / "old/app.js").exists())
        outcome = gc.execute(self.root, "test-agent")
        self.assertTrue(outcome["ok"], outcome)
        self.assertEqual(outcome["bytes_reclaimed"], 0)
        self.assertTrue((outside / "old/app.js").exists())

    def test_dirty_tracked_bytecode_file_is_kept(self) -> None:
        self._write("src/module.py", b"print(1)\n")
        self._commit_all()
        self._write("build/old/mod.pyc", b"tracked")
        self._commit_all()
        (self.root / "build/old/mod.pyc").write_bytes(b"changed")
        plan = gc.plan(self.root)
        self.assertNotIn(
            "build/old", {entry["path"] for entry in plan["targets"]}
        )

    def test_repeated_collection_after_a_collected_tree_is_a_no_op(self) -> None:
        self._write("src/module.py", b"print(1)\n")
        self._commit_all()
        cache = self._write("work/__pycache__/module.pyc", b"collectable bytecode")
        first = gc.execute(self.root, "test-agent")
        self.assertTrue(first["ok"], first)
        self.assertGreater(first["bytes_reclaimed"], 0)
        self.assertFalse(cache.exists())
        second = gc.execute(self.root, "test-agent")
        self.assertTrue(second["ok"], second)
        self.assertEqual(second["bytes_reclaimed"], 0)
        self.assertEqual(second["bytes_planned"], 0)
        self.assertEqual(second["targets"], [])

    def test_protected_prefixes_are_never_candidates(self) -> None:
        self._write(".saipen/cache/legacy.pyc", b"canonical proof")
        self._write("saipen/generated/legacy.pyc", b"canonical carrier")
        self._commit_all()
        inventory = gc.inventory(self.root)
        names = {entry["path"] for entry in inventory["entries"]}
        self.assertFalse([name for name in names if name.startswith((".saipen/", "saipen/"))])
        plan = gc.plan(self.root)
        self.assertNotIn(".saipen/cache", {entry["path"] for entry in plan["targets"]})

    def test_nested_repository_cache_is_foreign_owned(self) -> None:
        self._write("src/module.py", b"print(1)\n")
        self._commit_all()
        nested = self.root / "foreign"
        nested.mkdir()
        _git(nested, "init")
        cache = self._write("foreign/work/__pycache__/module.pyc", b"bytecode")

        plan = gc.plan(self.root)

        self.assertNotIn(
            "foreign/work/__pycache__", {entry["path"] for entry in plan["targets"]}
        )
        self.assertTrue(cache.exists())

    def test_case_insensitive_guard_match_protects_git_owned_bytes(self) -> None:
        guarded = {"Work/__pycache__/Tracked.pyc"}
        with mock.patch.object(gc.os.path, "normcase", lambda value: value.casefold()):
            hit = gc._guarded_hit("work/__pycache__", guarded)
        self.assertEqual(hit, "Work/__pycache__/Tracked.pyc")

    def test_git_ownership_is_refreshed_for_each_target_before_deletion(self) -> None:
        first = self._write("a/__pycache__/a.pyc", b"a")
        second = self._write("b/__pycache__/b.pyc", b"b")
        original_guard = gc.git_guard
        probes = 0

        def changing_guard(root):
            nonlocal probes
            probes += 1
            if probes == 2:
                guard = original_guard(root)
                guard["staged"] = {"a/__pycache__/a.pyc"}
                guard["guarded"] = set(guard["guarded"]) | guard["staged"]
                return guard
            return original_guard(root)

        with mock.patch.object(gc, "git_guard", changing_guard):
            outcome = gc.execute(self.root, "test-agent")

        states = {item["path"]: item["state"] for item in outcome["targets"]}
        self.assertEqual(states["a/__pycache__"], gc.RECONCILE_REQUIRED)
        self.assertTrue(first.exists())
        self.assertFalse(second.exists())

    def test_git_guard_failure_yields_an_empty_plan(self) -> None:
        # A probe that cannot COMPLETE is a refusal, never an empty protection
        # set: a non-repository root must plan nothing at all.
        outside = Path(self._tmp.name) / "not-a-repo"
        outside.mkdir()
        (outside / "work").mkdir()
        (outside / "work/__pycache__").mkdir()
        (outside / "work/__pycache__/module.pyc").write_bytes(b"bytecode")
        plan = gc.plan(outside)
        self.assertEqual(plan["targets"], [])
        self.assertEqual(plan["bytes_planned"], 0)
        self.assertFalse(plan["git_guard"]["ok"])
        self.assertIn("GIT_GUARD_FAILED", [b["code"] for b in plan["blockers"]])

    def test_type_corrupt_state_is_refused_not_silently_normalized(self) -> None:
        self._write("src/module.py", b"print(1)\n")
        self._commit_all()
        cache = self._write("work/__pycache__/module.pyc", b"bytecode")
        state = self.root / ".saipen/GC_STATE.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        for field in ("runs", "config", "closure_sources", "maintenance"):
            with self.subTest(field=field):
                payload = {"schema": gc.SCHEMA, "counted_done": [], field: "not a value"}
                state.write_text(json.dumps(payload), encoding="utf-8")
                health = gc.read_state(self.root)
                self.assertEqual(health["status"], "corrupt", field)
                outcome = gc.execute(self.root, "test-agent")
                self.assertFalse(outcome["ok"], outcome)
                self.assertEqual(outcome["code"], "CORRUPT_GC_STATE")
                self.assertTrue(cache.exists())
                verdict = gc.assess(self.root)
                self.assertFalse(verdict["due"], verdict)

    def test_guard_probe_failure_classes_share_one_complete_refusal_schema(self) -> None:
        from unittest import mock

        failures = (
            ("GIT_UNAVAILABLE", "git is not resolvable"),
            ("GIT_TIMEOUT", "git status exceeded 120s"),
            ("GIT_EXEC_FAILED", "permission denied"),
            ("GIT_COMMAND_FAILED", "broken index"),
            ("GIT_MALFORMED_OUTPUT", "invalid NUL stream"),
            ("GIT_ROOT_MISMATCH", "nested worktree root"),
        )
        for code, detail in failures:
            with self.subTest(code=code):
                guard = {
                    "ok": False,
                    "code": code,
                    "detail": detail,
                    "tracked": set(),
                    "staged": set(),
                    "dirty": set(),
                    "nested": set(),
                    "guarded": set(),
                }
                with mock.patch.object(gc, "git_guard", return_value=guard):
                    plan = gc.plan(self.root)
                self.assertEqual(plan["targets"], [])
                self.assertEqual(plan["bytes_planned"], 0)
                self.assertEqual(plan["git_guard"], {"ok": False, "code": code, "detail": detail})
                self.assertEqual(plan["blockers"][0]["code"], "GIT_GUARD_FAILED")
                self.assertIn(code, plan["blockers"][0]["detail"])

    def test_guard_refusal_never_deletes_or_consumes_debt(self) -> None:
        outside = Path(self._tmp.name) / "not-a-repo-execute"
        cache = outside / "work/__pycache__/module.pyc"
        cache.parent.mkdir(parents=True)
        cache.write_bytes(b"bytecode")
        state = gc.load_state(outside)
        state["maintenance"] = {
            **state["maintenance"],
            "state": gc.DEBT_DUE,
            "reason": "20 committed closures await collection",
        }
        gc.save_state(outside, state)
        before = gc.state_path(outside).read_bytes()

        outcome = gc.execute(outside, "test-agent")

        self.assertFalse(outcome["ok"], outcome)
        self.assertEqual(outcome["code"], "GIT_GUARD_FAILED")
        self.assertEqual(outcome["bytes_planned"], 0)
        self.assertEqual(outcome["bytes_reclaimed"], 0)
        self.assertEqual(outcome["targets"], [])
        self.assertFalse(outcome["git_guard"]["ok"])
        self.assertNotEqual(outcome["git_guard"]["code"], "GIT_GUARD_FAILED")
        self.assertIn(outcome["git_guard"]["code"], outcome["detail"])
        self.assertTrue(cache.exists())
        self.assertEqual(gc.state_path(outside).read_bytes(), before)
        self.assertNotIn("last_run", gc.load_state(outside))
        self.assertEqual(gc.load_state(outside)["maintenance"]["state"], gc.DEBT_DUE)

    def test_dry_run_collection_writes_nothing_and_deletes_nothing(self) -> None:
        cache = self._write("work/__pycache__/module.pyc", b"bytecode")
        self._commit_all()
        report = gc.execute(self.root, "test-agent", dry_run=True)
        self.assertTrue(report["dry_run"])
        self.assertTrue(cache.exists())
        self._assert_zero_write()

    def test_bare_collection_without_confirm_is_the_zero_write_plan(self) -> None:
        # The CLI's bare `saipen gc run` degrades to the plan; the ENGINE keeps
        # the same discipline for any caller that has not proven a seat.
        self._write("src/module.py", b"print(1)\n")
        self._commit_all()
        cache = self._write("work/__pycache__/module.pyc", b"bytecode")
        plan = gc.plan(self.root)
        self.assertEqual(len(plan["targets"]), 1)
        self.assertTrue(cache.exists())
        self._assert_zero_write()

    def test_corrupt_state_refuses_destructive_work_and_preserves_the_bytes(self) -> None:
        self._write("work/__pycache__/module.pyc", b"bytecode")
        self._commit_all()
        bad = b"{ this is not json"
        state = self.root / ".saipen/GC_STATE.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_bytes(bad)
        outcome = gc.execute(self.root, "test-agent")
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["code"], "CORRUPT_GC_STATE")
        self.assertEqual(outcome["bytes_reclaimed"], 0)
        self.assertEqual(state.read_bytes(), bad)
        self.assertTrue((self.root / "work/__pycache__/module.pyc").exists())

    def test_maintenance_refuses_on_corrupt_state(self) -> None:
        self._commit_all()
        state = self.root / ".saipen/GC_STATE.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_bytes(b"[]")
        outcome = gc.maintenance_checkpoint(self.root, "test-agent")
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["code"], "CORRUPT_GC_STATE")
        self.assertEqual(state.read_bytes(), b"[]")

    def test_repair_preserves_bad_bytes_and_rebuilds_from_history(self) -> None:
        self._write("work/__pycache__/module.pyc", b"bytecode")
        self._commit_all()
        state = self.root / ".saipen/GC_STATE.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        bad = b"{ broken"
        state.write_bytes(bad)
        outcome = gc.repair(self.root, "test-agent")
        self.assertTrue(outcome["ok"], outcome)
        self.assertEqual(outcome["code"], "GC_STATE_REPAIRED")
        preserved = self.root / outcome["preserved_bytes"]
        self.assertEqual(preserved.read_bytes(), bad)
        health = gc.read_state(self.root)
        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["state"]["counted_done"], [])

    def test_counter_is_a_distinct_closure_counter(self) -> None:
        # A duplicate DONE must not schedule extra work: sync counts DISTINCT
        # committed closure identities, and a replay leaves the total flat.
        self._commit_all()
        log = self.root / ".saipen/LOG.md"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(
            "- 1.1 [E-1] [parent: -] [T-2050] [op: finish-abc123] DONE: measured\n",
            encoding="utf-8",
        )
        first = gc.sync_counter(self.root)
        second = gc.sync_counter(self.root)
        self.assertTrue(first["ok"], first)
        self.assertTrue(second["ok"], second)
        self.assertEqual(first["counted"], second["counted"])
        self.assertEqual(first["counted"], 1)
        self.assertEqual(second["added"], [])


class GcCliSafety(unittest.TestCase):
    """The `saipen gc` adapter's own contract, exercised through the process.

    Every route here runs in a disposable project with a disposable cache, and
    the destructive route is the only one allowed to remove anything: the point
    of the class is that every other route leaves the bytes and the ledger
    exactly where they were.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "proj"
        self.root.mkdir()
        _git(self.root, "init")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        (self.root / ".saipen").mkdir()
        (self.root / ".saipen/STATE.md").write_bytes(b"phase: BUILD\n")
        (self.root / "src").mkdir()
        (self.root / "src/module.py").write_bytes(b"print(1)\n")
        self.cache = self.root / "work/__pycache__"
        self.cache.mkdir(parents=True)
        (self.cache / "module.pyc").write_bytes(b"bytecode")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _saipen(self, *argv: str) -> tuple[int, dict]:
        proc = subprocess.run(
            [sys.executable, SAIPEN_PY, *argv, "--json"],
            cwd=self.root,
            capture_output=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "SAIPEN_NO_COLOR": "1"},
        )
        try:
            return proc.returncode, json.loads(proc.stdout.decode("utf-8"))
        except json.JSONDecodeError:
            self.fail(
                f"saipen {' '.join(argv)} produced no JSON: {proc.stdout!r} {proc.stderr!r}"
            )

    def test_read_only_verbs_keep_the_ledger_untouched(self) -> None:
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        for verb in ("status", "audit", "assess", "inventory", "plan"):
            code, report = self._saipen("gc", verb)
            self.assertEqual(code, 0, report)
            self.assertNotIn(
                report.get("code") if isinstance(report, dict) else None,
                ("VALIDATION_FAILED", "GIT_GUARD_FAILED"),
            )
        after = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.root / ".saipen/GC_STATE.json").exists())
        self.assertTrue(self.cache.exists())

    def test_bare_run_and_dry_run_are_the_zero_write_plan(self) -> None:
        code_plan, plan = self._saipen("gc", "plan")
        self.assertEqual(code_plan, 0, plan)
        self.assertEqual([t["path"] for t in plan["targets"]], ["work/__pycache__"])

        code, report = self._saipen("gc", "run")
        self.assertEqual(code, 1, report)
        self.assertFalse(report["dry_run"])
        self.assertIn("--confirm", report["refused"])
        self.assertTrue(self.cache.exists())

        code, report = self._saipen("gc", "run", "--dry-run")
        self.assertEqual(code, 0, report)
        self.assertTrue(report["dry_run"])
        self.assertTrue(self.cache.exists())

        self.assertFalse((self.root / ".saipen/GC_STATE.json").exists())
        self.assertFalse((self.root / ".saipen/gc").exists())

    def test_confirmed_run_collects_only_the_rebuildable_cache(self) -> None:
        code, report = self._saipen("gc", "run", "--confirm")
        self.assertEqual(code, 0, report)
        self.assertEqual(report["code"], "GC_RUN_COMPLETE")
        self.assertEqual(report["bytes_reclaimed"], report["bytes_planned"])
        self.assertTrue(report["accounting_matches"])
        # User-owned source survives; only the cache tree is gone.
        self.assertFalse(self.cache.exists())
        self.assertTrue((self.root / "src/module.py").exists())
        run_record = self.root / ".saipen/gc/runs" / f"{report['run_id']}.json"
        self.assertTrue(run_record.exists())
        (run_record.read_bytes())

    def test_unknown_verb_is_rejected_and_writes_nothing(self) -> None:
        code, report = self._saipen("gc", "bogus")
        self.assertEqual(code, 2, report)
        self.assertEqual(report["code"], "VALIDATION_FAILED")
        self.assertFalse((self.root / ".saipen/GC_STATE.json").exists())
        self.assertTrue(self.cache.exists())

    def test_corrupt_state_refuses_the_confirmed_route(self) -> None:
        state = self.root / ".saipen/GC_STATE.json"
        bad = b"{ not json"
        state.write_bytes(bad)
        code, report = self._saipen("gc", "run", "--confirm")
        self.assertEqual(code, 1, report)
        self.assertEqual(report["code"], "CORRUPT_GC_STATE")
        self.assertEqual(state.read_bytes(), bad)
        self.assertTrue(self.cache.exists())


class GcProductionWiring(unittest.TestCase):
    """T-2049's production trigger: a committed closure -- and only that.

    The ledger route is stubbed so the assertion is about the trigger alone:
    the collector runs after a DONE closure is durable, never on a refused or
    previewed transition, and its own failure can never rewrite the outcome
    the closure route already returned.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "proj"
        self.root.mkdir()
        self.calls: list[tuple[Path, str]] = []
        self._lock = threading.Lock()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _plan(self) -> object:
        # A plan shape the baseline probe can read and then step aside for:
        # the assertion here is about the trigger, not about the plan builder.
        return SimpleNamespace(semantic_request={}, targets=[], preconditions={})

    def _run(self, destination: str, *, ok: bool = True):
        from unittest import mock

        from saipen_engine import operations
        from saipen_engine.result import Result

        def spy(root: Path, agent: str) -> None:
            with self._lock:
                self.calls.append((Path(root), agent))

        with mock.patch.object(operations, "_plan_transition", return_value=self._plan()), \
             mock.patch.object(operations, "apply_plan",
                               return_value=Result(ok=ok, code="TRANSITIONED")), \
             mock.patch.object(gc, "maintenance_checkpoint", spy):
            return operations.transition_phase(
                self.root, destination, "wiring-agent", "T-2049", "wiring proof"
            )

    def test_committed_done_invokes_the_collector_after_the_ledger(self) -> None:
        applied = self._run("DONE")
        self.assertTrue(applied.ok, applied)
        self.assertEqual(self.calls, [(self.root, "wiring-agent")])

    def test_refused_closure_never_invokes_the_collector(self) -> None:
        applied = self._run("DONE", ok=False)
        self.assertFalse(applied.ok)
        self.assertEqual(self.calls, [])

    def test_non_closure_transitions_never_invoke_the_collector(self) -> None:
        applied = self._run("BUILD")
        self.assertTrue(applied.ok, applied)
        self.assertEqual(self.calls, [])


class GcCommandAdmissionTests(unittest.TestCase):
    """CMD-EFFECT-01: the collector is an admitted verb with closed classes.

    Before these rows existed, `gc` fell to the machine table's unknown class
    (`EXECUTION`), so a zero-write `gc status` carried a destructive
    invocation's authority and fleet obligation. The registry command list and
    the effect table are the two owners that must agree.
    """

    def test_gc_is_a_known_verb(self) -> None:
        self.assertTrue(is_known_verb("gc"), "saipen gc must dispatch")
        self.assertTrue(is_known_verb("gc", ["status"]))

    def test_read_only_routes_are_recovery_class(self) -> None:
        for action in ("status", "audit", "assess", "inventory", "plan"):
            with self.subTest(action=action):
                self.assertEqual(
                    classify_invocation("gc", [action]),
                    "RECOVERY",
                    f"gc {action} is a zero-write canonical repair view",
                )

    def test_mutating_routes_are_execution_class(self) -> None:
        for argv in (["run"], ["run", "--confirm"], ["maintenance"], ["repair"]):
            with self.subTest(argv=argv):
                self.assertEqual(classify_invocation("gc", argv), "EXECUTION")

    def test_bare_gc_is_a_known_recovery_probe(self) -> None:
        self.assertEqual(classify_invocation("gc", []), "RECOVERY")


class GcGeneratedBuildTests(unittest.TestCase):
    """A manifest-proven build is collectable; the cache rule never judges it.

    This is the plan/execute contradiction the refresh exists to close: the
    manifest route proves a build structurally and by inventory digest, while
    the generic re-audit demanded bytecode suffixes and therefore refused every
    legal build target at execution time.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "proj"
        self.root.mkdir()
        _git(self.root, "init")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        self._write("src/module.py", b"print(1)\n")
        self._commit_all()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, relative: str, payload: bytes) -> Path:
        node = self.root / relative
        node.parent.mkdir(parents=True, exist_ok=True)
        node.write_bytes(payload)
        return node

    def _commit_all(self) -> None:
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "--allow-empty", "-m", "seed")

    def _manifest(self, old_digest: str, new_digest: str) -> Path:
        path = self.root / gc.MANIFEST_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema": gc.SCHEMA,
                    "builds": [
                        {
                            "id": "B-1",
                            "path": "dist/old",
                            "owner": "test-builder",
                            "recipe": "python -m build",
                            "inventory_sha256": old_digest,
                            "superseded_by": "B-2",
                        },
                        {
                            "id": "B-2",
                            "path": "dist/new",
                            "owner": "test-builder",
                            "recipe": "python -m build",
                            "inventory_sha256": new_digest,
                            "verified": True,
                        },
                    ],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def test_manifest_build_is_planned_and_collected(self) -> None:
        self._write("dist/old/app.js", b"old build payload\n")
        self._write("dist/new/app.js", b"new verified build payload\n")
        old_digest = gc.inventory_digest(self.root, "dist/old")
        new_digest = gc.inventory_digest(self.root, "dist/new")
        self._manifest(old_digest, new_digest)

        plan = gc.plan(self.root)
        planned = {item["path"]: item for item in plan["targets"]}
        self.assertIn("dist/old", planned)
        self.assertEqual(
            planned["dist/old"]["class"], gc.GENERATED_BUILD_SUPERSEDED, planned["dist/old"]
        )
        self.assertNotIn("dist/new", {item["path"] for item in plan["targets"]})

        outcome = gc.execute(self.root, "test-agent")
        self.assertTrue(outcome["ok"], outcome)
        self.assertGreater(outcome["bytes_reclaimed"], 0)
        self.assertFalse((self.root / "dist/old").exists())
        self.assertTrue((self.root / "dist/new/app.js").exists())
        self.assertTrue((self.root / "src/module.py").exists())

    def test_successor_with_a_linked_ancestor_cannot_authorize_deletion(self) -> None:
        self._write("dist/old/app.js", b"old build payload\n")
        outside = Path(self._tmp.name) / "outside"
        outside.mkdir()
        (outside / "app.js").write_bytes(b"outside bytes\n")
        link = self.root / "dist/new"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlink unavailable: {exc}")
        old_digest = gc.inventory_digest(self.root, "dist/old")
        self._manifest(old_digest, gc.inventory_digest(self.root, "dist/new"))

        plan = gc.plan(self.root)

        self.assertNotIn("dist/old", {item["path"] for item in plan["targets"]})
        self.assertTrue((self.root / "dist/old/app.js").exists())
        self.assertTrue((outside / "app.js").exists())

    def test_successor_with_a_nested_git_boundary_cannot_authorize_deletion(self) -> None:
        self._write("dist/old/app.js", b"old build payload\n")
        self._write("dist/new/app.js", b"foreign successor\n")
        _git(self.root / "dist/new", "init")
        old_digest = gc.inventory_digest(self.root, "dist/old")
        self._manifest(old_digest, gc.inventory_digest(self.root, "dist/new"))

        plan = gc.plan(self.root)

        self.assertNotIn("dist/old", {item["path"] for item in plan["targets"]})
        self.assertTrue((self.root / "dist/old/app.js").exists())

    def test_successor_inventory_must_still_match_its_manifest(self) -> None:
        self._write("dist/old/app.js", b"old build payload\n")
        self._write("dist/new/app.js", b"new verified build payload\n")
        old_digest = gc.inventory_digest(self.root, "dist/old")
        new_digest = gc.inventory_digest(self.root, "dist/new")
        self._manifest(old_digest, new_digest)
        self._write("dist/new/app.js", b"successor changed after verification\n")

        plan = gc.plan(self.root)

        self.assertNotIn("dist/old", {item["path"] for item in plan["targets"]})
        self.assertTrue((self.root / "dist/old/app.js").exists())

    def test_manifest_recipe_and_successor_bytes_change_the_retry_fingerprint(self) -> None:
        self._write("dist/old/app.js", b"old build payload\n")
        self._write("dist/new/app.js", b"new verified build payload\n")
        old_digest = gc.inventory_digest(self.root, "dist/old")
        new_digest = gc.inventory_digest(self.root, "dist/new")
        manifest = self._manifest(old_digest, new_digest)
        first = gc.maintenance_fingerprint(self.root)

        document = json.loads(manifest.read_text(encoding="utf-8"))
        document["builds"][0]["recipe"] = "python -m build --clean"
        manifest.write_text(json.dumps(document), encoding="utf-8")
        recipe_changed = gc.maintenance_fingerprint(self.root)
        self.assertNotEqual(first, recipe_changed)

        self._write("dist/new/app.js", b"changed successor bytes\n")
        successor_changed = gc.maintenance_fingerprint(self.root)
        self.assertNotEqual(recipe_changed, successor_changed)

    def test_manifest_status_changes_the_retry_fingerprint(self) -> None:
        missing = gc.maintenance_fingerprint(self.root)
        path = self.root / gc.MANIFEST_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not-json", encoding="utf-8")
        corrupt = gc.maintenance_fingerprint(self.root)
        self.assertNotEqual(missing, corrupt)

    def test_a_modified_manifest_build_is_refused_not_collected(self) -> None:
        self._write("dist/old/app.js", b"old build payload\n")
        self._write("dist/new/app.js", b"new verified build payload\n")
        old_digest = gc.inventory_digest(self.root, "dist/old")
        new_digest = gc.inventory_digest(self.root, "dist/new")
        self._manifest(old_digest, new_digest)
        self._write("dist/old/app.js", b"modified after the manifest\n")

        outcome = gc.execute(self.root, "test-agent")
        self.assertTrue(outcome["ok"], outcome)
        self.assertTrue((self.root / "dist/old/app.js").exists())
        committed = [
            target
            for target in outcome["targets"]
            if target["path"] == "dist/old" and target["state"] == "COMMITTED"
        ]
        self.assertEqual(committed, [], outcome["targets"])


class GcTriggerTests(unittest.TestCase):
    """The 20/40 interval and the budget trigger both collect, nothing else does."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "proj"
        self.root.mkdir()
        _git(self.root, "init")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        self._write("src/module.py", b"print(1)\n")
        self._commit_all()
        (self.root / ".saipen").mkdir()
        (self.root / ".saipen/LOG.md").write_text("", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, relative: str, payload: bytes) -> Path:
        node = self.root / relative
        node.parent.mkdir(parents=True, exist_ok=True)
        node.write_bytes(payload)
        return node

    def _commit_all(self) -> None:
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "--allow-empty", "-m", "seed")

    def _closure(self, ticket: str) -> None:
        log = self.root / ".saipen/LOG.md"
        with log.open("a", encoding="utf-8") as handle:
            handle.write(f"- 1.1 [E-1] [T-{ticket}] [op: finish-{ticket}] DONE: measured\n")

    def _cache(self) -> Path:
        node = self._write("work/__pycache__/module.pyc", b"collectable bytecode")
        return node

    def test_twenty_distinct_closures_trigger_collection(self) -> None:
        for index in range(1, 21):
            self._closure(index)
        cache = self._cache()
        self.assertTrue(gc.sync_counter(self.root)["ok"])
        verdict = gc.assess(self.root)
        self.assertTrue(verdict["due"], verdict)
        self.assertEqual(verdict["pending"], 20)
        self.assertEqual(verdict["next_threshold"], 40)
        outcome = gc.execute(self.root, "test-agent")
        self.assertTrue(outcome["ok"], outcome)
        self.assertFalse(cache.exists())
        self.assertEqual(gc.assess(self.root)["due"], False)

    def test_a_closure_committed_without_a_settlement_receipt_is_still_counted(self) -> None:
        # The crash window: a process dies between the committed closure and the
        # settlement hook. The counter is derived from canonical history at the
        # NEXT checkpoint, so the closure is counted and the debt stays owed.
        for index in range(1, 21):
            self._closure(index)
        self.assertFalse(gc.settlement_records(self.root))
        sync = gc.sync_counter(self.root)
        self.assertEqual(sync["counted"], 20)
        verdict = gc.assess(self.root)
        self.assertTrue(verdict["due"], verdict)

    def test_nineteen_closures_stay_short_of_the_interval(self) -> None:
        for index in range(1, 20):
            self._closure(index)
        gc.sync_counter(self.root)
        verdict = gc.assess(self.root)
        self.assertFalse(verdict["due"], verdict)
        self.assertEqual(verdict["pending"], 19)

    def test_interval_consumption_survives_late_runs_at_21_and_40(self) -> None:
        for index in range(1, 22):
            self._closure(index)
        gc.sync_counter(self.root)
        self.assertTrue(gc.assess(self.root)["due"])
        self._cache()
        gc.execute(self.root, "test-agent")
        for index in range(22, 40):
            self._closure(index)
        gc.sync_counter(self.root)
        at_39 = gc.assess(self.root)
        self.assertFalse(at_39["due"], at_39)
        self.assertEqual(at_39["next_threshold"], 40)

        self._closure(40)
        gc.sync_counter(self.root)
        at_40 = gc.assess(self.root)
        self.assertTrue(at_40["due"], at_40)
        self._cache()
        gc.execute(self.root, "test-agent")
        self._closure(41)
        gc.sync_counter(self.root)
        at_41 = gc.assess(self.root)
        self.assertFalse(at_41["due"], at_41)
        self.assertEqual(at_41["next_threshold"], 60)

    def test_forty_is_the_next_threshold_not_twenty_again(self) -> None:
        for index in range(1, 41):
            self._closure(index)
        cache = self._cache()
        gc.execute(self.root, "test-agent")
        self.assertFalse(cache.exists())
        for index in range(41, 61):
            self._closure(index)
        cache = self._cache()
        verdict = gc.assess(self.root)
        self.assertTrue(verdict["due"], verdict)
        self.assertGreaterEqual(verdict["pending"], 20)
        self.assertEqual(verdict["next_threshold"], 80, verdict)
        outcome = gc.execute(self.root, "test-agent")
        self.assertTrue(outcome["ok"], outcome)
        self.assertFalse(cache.exists())

    def test_an_early_budget_trigger_executes(self) -> None:
        gc.save_state(
            self.root,
            {
                **gc.load_state(self.root),
                "config": {
                    **gc.load_state(self.root)["config"],
                    "generated_build_budget_gib": 1.0 / (1024 ** 3),
                },
            },
        )
        self._write("dist/old/app.js", b"superseded build payload\n")
        self._write("dist/new/app.js", b"new verified build payload\n")
        (self.root / gc.MANIFEST_REL).parent.mkdir(parents=True, exist_ok=True)
        (self.root / gc.MANIFEST_REL).write_text(
            json.dumps(
                {
                    "schema": gc.SCHEMA,
                    "builds": [
                        {
                            "id": "B-1",
                            "path": "dist/old",
                            "owner": "test-builder",
                            "recipe": "python -m build",
                            "inventory_sha256": gc.inventory_digest(self.root, "dist/old"),
                            "superseded_by": "B-2",
                        },
                        {
                            "id": "B-2",
                            "path": "dist/new",
                            "owner": "test-builder",
                            "recipe": "python -m build",
                            "inventory_sha256": gc.inventory_digest(self.root, "dist/new"),
                            "verified": True,
                        },
                    ],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        verdict = gc.assess(self.root)
        self.assertTrue(verdict["due"], verdict)
        self.assertIn("storage budget breached", verdict["reason"])
        outcome = gc.execute(self.root, "test-agent")
        self.assertTrue(outcome["ok"], outcome)
        self.assertFalse((self.root / "dist/old").exists())
        self.assertTrue((self.root / "dist/new/app.js").exists())


class GcSettlementTests(unittest.TestCase):
    """T-2059: one committed closure settles exactly one maintenance checkpoint.

    Both public routes (`ticket done` through operations.finish_ticket and a
    real `transition DONE`) reach the same canonical settlement; the distinct
    closure identity is deduplicated by the durable settlement ledger, so an
    overlap cannot run the collector twice and a replay cannot lose the count.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "proj"
        self.root.mkdir()
        self.calls: list[tuple[Path, str]] = []
        self._lock = threading.Lock()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, destination: str, *, ok: bool = True, op_id: str = "transition-x"):
        from unittest import mock

        from saipen_engine import operations
        from saipen_engine.result import Result

        def spy(root: Path, agent: str) -> None:
            with self._lock:
                self.calls.append((Path(root), agent))
            return {"ok": True, "code": "GC_NOT_DUE", "due": False}

        plan = SimpleNamespace(
            semantic_request={"ticket": "T-2059"}, targets=[], preconditions={},
            op_id=op_id,
        )
        with mock.patch.object(operations, "_plan_transition", return_value=plan), \
             mock.patch.object(operations, "apply_plan",
                               return_value=Result(ok=ok, code="TRANSITIONED")), \
             mock.patch.object(gc, "maintenance_checkpoint", spy):
            return operations.transition_phase(
                self.root, destination, "settle-agent", "T-2059", "settlement proof"
            )

    def test_ticket_done_route_reaches_the_collector(self) -> None:
        from unittest import mock

        from saipen_engine import operations
        from saipen_engine.result import Result

        plan = SimpleNamespace(
            semantic_request={}, targets=[], preconditions={}, op_id="finish-x"
        )

        def spy(root: Path, agent: str) -> None:
            self.calls.append((Path(root), agent))
            return {"ok": True, "code": "GC_NOT_DUE", "due": False}

        with mock.patch.object(operations, "_plan_finish_ticket", return_value=plan), \
             mock.patch.object(operations, "apply_plan",
                               return_value=Result(ok=True, code="FINISHED")), \
             mock.patch.object(gc, "maintenance_checkpoint", spy):
            outcome = operations.finish_ticket(self.root, "T-2060", "done-agent")
        self.assertTrue(outcome.ok, outcome)
        self.assertEqual(self.calls, [(self.root, "done-agent")])
        ledger = gc.settlement_records(self.root)
        self.assertEqual(
            [record["ticket"] for record in ledger if record.get("state") == "done"],
            ["T-2060"],
        )

    def test_overlapping_routes_settle_one_collector_run(self) -> None:
        from unittest import mock

        from saipen_engine import operations
        from saipen_engine.result import Result

        def spy(root: Path, agent: str) -> None:
            self.calls.append((Path(root), agent))
            return {"ok": True, "code": "GC_NOT_DUE", "due": False}

        transition_plan = SimpleNamespace(
            semantic_request={"ticket": "T-2059"}, targets=[], preconditions={},
            op_id="transition-x",
        )
        finish_plan = SimpleNamespace(
            semantic_request={}, targets=[], preconditions={}, op_id="finish-x"
        )
        with mock.patch.object(operations, "_plan_transition", return_value=transition_plan), \
             mock.patch.object(operations, "apply_plan",
                               return_value=Result(ok=True, code="TRANSITIONED")), \
             mock.patch.object(operations, "_plan_finish_ticket", return_value=finish_plan), \
             mock.patch.object(gc, "maintenance_checkpoint", spy):
            operations.transition_phase(self.root, "DONE", "agent", "T-2059", "first")
            operations.finish_ticket(self.root, "T-2059", "agent")
        self.assertEqual(self.calls, [(self.root, "agent")])

    def test_checkpoint_exception_becomes_a_durable_failure_receipt(self) -> None:
        from unittest import mock

        from saipen_engine import operations
        from saipen_engine.result import Result

        plan = SimpleNamespace(
            semantic_request={"ticket": "T-2059"}, targets=[], preconditions={},
            op_id="transition-x",
        )
        with mock.patch.object(operations, "_plan_transition", return_value=plan), \
             mock.patch.object(operations, "apply_plan",
                               return_value=Result(ok=True, code="TRANSITIONED")), \
             mock.patch.object(gc, "settle_ticket_completion",
                               side_effect=RuntimeError("disk vanished")):
            outcome = operations.transition_phase(
                self.root, "DONE", "agent", "T-2059", "failure proof"
            )
        # The committed closure is NEVER rewritten by maintenance trouble.
        self.assertTrue(outcome.ok, outcome)
        failures = gc.maintenance_failures(self.root)
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["code"], "GC_MAINTENANCE_FAILED")
        self.assertEqual(failures[0]["error_type"], "RuntimeError")

    def test_pending_receipt_replays_but_done_receipt_deduplicates(self) -> None:
        from unittest import mock

        gc.record_settlement(
            self.root, "T-2059", "transition-crashed", state="pending"
        )

        def spy(root: Path, agent: str) -> dict:
            self.calls.append((Path(root), agent))
            return {"ok": True, "code": "GC_NOT_DUE", "due": False}

        with mock.patch.object(gc, "maintenance_checkpoint", spy):
            replay = gc.settle_ticket_completion(
                self.root,
                "T-2059",
                "agent",
                settlement_id="transition-crashed",
            )
            completed = gc.settle_ticket_completion(
                self.root,
                "T-2059",
                "agent",
                settlement_id="another-public-route",
            )

        self.assertEqual(replay["code"], "GC_NOT_DUE")
        self.assertEqual(completed["code"], "ALREADY_SETTLED")
        self.assertEqual(self.calls, [(self.root, "agent")])
        records = gc.settlement_records(self.root)
        self.assertEqual([record["state"] for record in records], ["pending", "done"])

    def test_settlement_replay_does_not_rerun_maintenance(self) -> None:
        from unittest import mock

        def spy(root: Path, agent: str) -> None:
            self.calls.append((Path(root), agent))
            return {"ok": True, "code": "GC_NOT_DUE", "due": False}

        with mock.patch.object(gc, "maintenance_checkpoint", spy):
            first = gc.settle_ticket_completion(self.root, "T-2059", "agent")
            replay = gc.settle_ticket_completion(self.root, "T-2059", "agent")
            same_op = gc.settle_ticket_completion(
                self.root, "T-2059", "agent", settlement_id="transition-x"
            )
        self.assertEqual(first["code"], "GC_NOT_DUE")
        self.assertEqual(self.calls, [(self.root, "agent")])
        self.assertEqual(replay["code"], "ALREADY_SETTLED")
        self.assertEqual(same_op["code"], "ALREADY_SETTLED")


class GcDebtTests(unittest.TestCase):
    """T-2059: durable maintenance debt and the no-progress fingerprint.

    An over-budget protected evidence tree must not spin: the first zero-
    progress run records OPEN debt, an identical retry is suppressed, a changed
    fingerprint reactivates, and nothing but an honest collection settles.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "proj"
        self.root.mkdir()
        for argv in (("init",), ("config", "user.email", "t@t"), ("config", "user.name", "t")):
            subprocess.run(["git", "-C", str(self.root), *argv], check=True, capture_output=True)
        src = self.root / "src/module.py"
        src.parent.mkdir(parents=True)
        src.write_bytes(b"print(1)\n")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(self.root), "commit", "--allow-empty", "-m", "seed"],
            check=True, capture_output=True,
        )
        log = self.root / ".saipen/LOG.md"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("", encoding="utf-8")
        for index in range(1, 21):
            log.write_text(
                log.read_text(encoding="utf-8")
                + f"- 1.1 [E-{index}] [T-{index}] [op: finish-{index}] DONE: measured\n",
                encoding="utf-8",
            )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _over_budget_evidence(self) -> None:
        state = gc.load_state(self.root)
        gc.save_state(
            self.root,
            {
                **state,
                "config": {
                    **state["config"],
                    "evidence_budget_gib": 1.0 / (1024 ** 3),
                },
            },
        )
        evidence = self.root / ".saipen/evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "canonical.json").write_bytes(b'{"proof": true}\n')

    def test_protected_budget_overrun_records_open_debt_and_stays_due(self) -> None:
        self._over_budget_evidence()
        outcome = gc.maintenance_checkpoint(self.root, "debt-agent")
        self.assertTrue(outcome["ok"], outcome)
        state = gc.load_state(self.root)
        debt = state["maintenance"]
        self.assertEqual(debt["state"], gc.DEBT_BLOCKED_PROTECTED_BUDGET, debt)
        self.assertEqual(outcome["bytes_reclaimed"], 0)
        verdict = gc.assess(self.root)
        self.assertTrue(verdict["due"], verdict)

    def test_identical_fingerprint_suppresses_the_expensive_retry(self) -> None:
        self._over_budget_evidence()
        first = gc.maintenance_checkpoint(self.root, "debt-agent")
        self.assertTrue(first["ok"], first)
        calls: list[str] = []

        from unittest import mock

        real_execute = gc.execute

        def spy(root, agent, **kwargs):
            calls.append(agent)
            return real_execute(root, agent, **kwargs)

        with mock.patch.object(gc, "execute", spy):
            second = gc.maintenance_checkpoint(self.root, "debt-agent")
        self.assertEqual(calls, [], "an identical fingerprint must not re-execute")
        self.assertEqual(second["code"], "GC_RETRY_SUPPRESSED")
        self.assertTrue(second["retry_suppressed"])
        self.assertTrue(second["due"], "suppression must preserve open due debt")
        self.assertEqual(second["blocked"], gc.DEBT_BLOCKED_PROTECTED_BUDGET)
        # The debt is OPEN, never settled by suppression.
        debt = gc.load_state(self.root)["maintenance"]
        self.assertEqual(debt["state"], gc.DEBT_BLOCKED_PROTECTED_BUDGET)

    def test_changed_fingerprint_reactivates_maintenance(self) -> None:
        self._over_budget_evidence()
        first = gc.maintenance_checkpoint(self.root, "debt-agent")
        self.assertTrue(first["ok"], first)
        second = gc.maintenance_checkpoint(self.root, "debt-agent")
        self.assertEqual(second["code"], "GC_RETRY_SUPPRESSED")
        # A meaningful input changed: the protected evidence grows.
        evidence = self.root / ".saipen/evidence"
        (evidence / "canonical.json").write_bytes(b'{"proof": true, "more": 1}\n')
        verdict = gc.assess(self.root)
        self.assertTrue(verdict["due"], verdict)
        self.assertNotIn("suppressed", verdict)

    def test_successful_collection_is_the_only_settled_debt(self) -> None:
        cache = self.root / "work/__pycache__"
        cache.mkdir(parents=True)
        (cache / "module.pyc").write_bytes(b"bytecode")
        outcome = gc.maintenance_checkpoint(self.root, "debt-agent")
        self.assertTrue(outcome["ok"], outcome)
        self.assertGreater(outcome["bytes_reclaimed"], 0)
        debt = gc.load_state(self.root)["maintenance"]
        self.assertEqual(debt["state"], gc.DEBT_SETTLED)
        verdict = gc.assess(self.root)
        self.assertFalse(verdict["due"], verdict)

    def _capture_execute(self) -> object:
        """Wrap the collector so the run report can be asserted, not only the verdict."""
        self.collected: dict = {}
        original = gc.execute

        def spy(root, agent, **kwargs):
            report = original(root, agent, **kwargs)
            self.collected = report
            return report

        return spy

    def test_a_partial_collection_never_settles_the_debt(self) -> None:
        from unittest import mock

        for name in ("a", "b"):
            cache = self.root / name / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "module.pyc").write_bytes(b"bytecode")
        kept = self.root / "b/__pycache__/module.pyc"
        original = gc._remove_tree

        def stub(node, root, progress, run_id):
            if node.parent.name == "b":
                gc._append_progress(
                    progress,
                    {
                        "run_id": run_id,
                        "event": gc.PARTIAL,
                        "path": "b/__pycache__",
                        "error": "OS denied the deletion",
                    },
                )
                return 0, ["b/__pycache__: OS denied the deletion"]
            return original(node, root, progress, run_id)

        with mock.patch.object(gc, "_remove_tree", stub), \
             mock.patch.object(gc, "execute", self._capture_execute()):
            outcome = gc.maintenance_checkpoint(self.root, "partial-agent")

        self.assertTrue(outcome["ok"], outcome)
        self.assertEqual(outcome["code"], "GC_RUN_COMPLETE")
        self.assertGreater(outcome["bytes_reclaimed"], 0)
        states = {
            target["path"]: target["state"]
            for target in self.collected["targets"]
        }
        self.assertEqual(states["a/__pycache__"], gc.COMMITTED)
        self.assertEqual(states["b/__pycache__"], gc.PARTIAL)
        # Bytes are gone but the collection is incomplete: debt stays OPEN.
        self.assertFalse((self.root / "a/__pycache__").exists())
        self.assertTrue(kept.exists())
        debt = gc.load_state(self.root)["maintenance"]
        self.assertEqual(debt["state"], gc.DEBT_PARTIAL, debt)
        verdict = gc.assess(self.root)
        self.assertTrue(verdict["due"], verdict)


class GcReleaseSettlementTests(unittest.TestCase):
    """T-2059: the release closure settles through the same hook.

    `_apply_finish_targets` applies the canonical closure of a release through
    the release journal, so it never passes through `operations.finish_ticket`:
    the settlement is wired at the release's own COMMITTED edge, and a CREW
    release that closes no ticket settles nothing.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "proj"
        self.root.mkdir()
        _git(self.root, "init")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        self._write("src/module.py", b"print(1)\n")
        self._commit_all()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, relative: str, payload: bytes) -> Path:
        node = self.root / relative
        node.parent.mkdir(parents=True, exist_ok=True)
        node.write_bytes(payload)
        return node

    def _commit_all(self) -> None:
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "--allow-empty", "-m", "seed")

    def _plan(self, **overrides) -> object:
        from saipen_engine.release import _settle_release_closure

        fields = {
            "ticket_id": "T-2061",
            "targeted_ticket": None,
            "crew_closure": False,
            "current_agent": "release-agent",
            "op_id": "release-abc123",
        }
        fields.update(overrides)
        result = {"ok": True, "code": "RELEASED"}
        _settle_release_closure(self.root, SimpleNamespace(**fields), result)
        return result

    def test_committed_release_settles_the_named_ticket(self) -> None:
        result = self._plan()
        self.assertEqual(result["settlement"]["source"], "release")
        ledger = gc.settlement_records(self.root)
        done = [
            record["ticket"] for record in ledger if record.get("state", "done") == "done"
        ]
        self.assertEqual(done, ["T-2061"])

    def test_release_and_finish_routes_settle_one_ticket_once(self) -> None:
        self._plan()
        gc.settle_ticket_completion(self.root, "T-2061", "release-agent")
        ledger = gc.settlement_records(self.root)
        done = [
            record["ticket"] for record in ledger if record.get("state", "done") == "done"
        ]
        self.assertEqual(done, ["T-2061"])

    def test_a_crew_release_closes_no_ticket_and_settles_nothing(self) -> None:
        result = self._plan(crew_closure=True, ticket_id="")
        self.assertNotIn("settlement", result)
        self.assertFalse(gc.settlement_records(self.root))

    def test_a_failed_release_never_settles(self) -> None:
        from saipen_engine.release import _settle_release_closure

        plan = SimpleNamespace(
            ticket_id="T-2061",
            targeted_ticket=None,
            crew_closure=False,
            current_agent="release-agent",
            op_id="release-failed",
        )
        result = {"ok": False, "code": "RELEASE_FAILED"}
        _settle_release_closure(self.root, plan, result)
        self.assertNotIn("settlement", result)
        self.assertFalse(gc.settlement_records(self.root))


if __name__ == "__main__":
    unittest.main()
