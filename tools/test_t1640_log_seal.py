"""T-1640: the LOG cap is applied by the engine, not printed at an agent.

CORE states a cap for the active LOG (300 lines / 64 KiB) and the validator
warned about it on every run with the instruction "seal it at the next
checkpoint". Nobody could: `.saipen/LOG.md` and `.saipen/logs/` are protected
canonical namespaces, so the guard refused the agent, and no engine verb did
it instead. Measured on this repository, 2026-10-07: 6113 lines / 2 MB.

`operations.seal_log` is that verb and entering CLEAN runs it. These tests
hold it to the properties a ledger move needs: the sealed bytes are the active
LOG's bytes, the history is the same history plus one event, an interrupted
seal converges, nothing is sealed under the cap or outside CLEAN, and a sealed
segment that changed under the plan refuses the seal. The route the refusals
and the validator name is `saipen transition CLEAN`, because that is the
spelling a guarded shell admits while no Work is active.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import log as L  # noqa: E402
from saipen_engine.fast_check import validate_project  # noqa: E402
from saipen_engine.journal import (  # noqa: E402
    auto_recover_pending,
    op_id_provenance,
    scan_pending,
)
from saipen_engine.operations import checkpoint, seal_log  # noqa: E402
from saipen_engine.state import parse_state  # noqa: E402
from test_guard_hostile_matrix import fresh_project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

ENGINE = TOOLS / "saipen.py"
AGENT = "test-agent"


def setUpModule() -> None:
    isolate_host_session()


def _cli(root: Path, *args: str):
    """One engine call bound to the fixture twice over: root first, cwd too."""
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PWD"] = str(root)
    proc = subprocess.run(
        [sys.executable, "-B", str(ENGINE), "--project-root", str(root), *args],
        stdin=subprocess.DEVNULL, capture_output=True, env=env, cwd=str(root),
        timeout=300, check=False,
    )
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


def _findings(root: Path) -> list[str]:
    """Every WARN and FAIL line the validator's core gate prints for `root`."""
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PWD"] = str(root)
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(TOOLS / "validate.py"), "--gate", "core"],
        stdin=subprocess.DEVNULL, capture_output=True, env=env, cwd=str(root),
        timeout=600, check=False,
    )
    text = proc.stdout.decode("utf-8", errors="replace")
    return [line for line in text.splitlines() if line.startswith(("WARN", "FAIL"))]


def _live_ops():
    """The LIVE operations module: some suites purge `sys.modules`, and a patch
    applied to a stale copy decorates a module the engine no longer uses."""
    importlib.import_module("saipen_engine.operations")
    return sys.modules["saipen_engine.operations"]


def _events(first: int, last: int, *, parent: int | None = None, width: int = 0) -> list[str]:
    out = []
    for event in range(first, last + 1):
        before = event - 1 if event > first else parent
        link = f" [parent: E-{before}]" if before is not None else ""
        out.append(
            f"- 12.09.26 00:00 [E-{event}]{link} [agent: {AGENT}] RUN: fixture event {event}"
            + (" " + "x" * width if width else "")
        )
    return out


def _project(
    *,
    first: int = 100,
    last: int = 450,
    newline: str = "\n",
    heading: tuple[str, ...] = ("# Log",),
    phase: str = "CLEAN",
    width: int = 0,
    sealed: tuple[tuple[int, int], ...] = (),
) -> Path:
    """A project in `phase` whose active LOG holds E-first..E-last.

    `sealed` names earlier segments as (first, last) ranges; the chain runs
    through them into the active LOG, as a real ledger's does.
    """
    root = fresh_project(
        phase=phase, next_action="PHASE CLEAN" if phase == "CLEAN" else "saipen continue"
    )
    memory = root / ".saipen"
    state = memory / "STATE.md"
    state.write_text(
        state.read_text(encoding="utf-8").replace("last_event: 100", f"last_event: {last}"),
        encoding="utf-8",
    )
    parent = None
    for number, (start, end) in enumerate(sealed, 1):
        (memory / "logs").mkdir(exist_ok=True)
        body = ["# Log", *_events(start, end, parent=parent)]
        (memory / "logs" / f"LOG-{number:03d}.md").write_bytes(
            ("\n".join(body) + "\n").encode("utf-8")
        )
        parent = end
    body = [*heading, *_events(first, last, parent=parent, width=width)]
    (memory / "LOG.md").write_bytes((newline.join(body) + newline).encode("utf-8"))
    assert validate_project(root) == [], validate_project(root)
    return root


def _active(root: Path) -> bytes:
    return (root / ".saipen" / "LOG.md").read_bytes()


def _segments(root: Path) -> dict[str, bytes]:
    logs = root / ".saipen" / "logs"
    return {p.name: p.read_bytes() for p in sorted(logs.iterdir())} if logs.is_dir() else {}


def _history(root: Path):
    snapshot = L.read_history_snapshot(root)
    return snapshot, L.snapshot_contract_errors(snapshot)


class SealTests(unittest.TestCase):
    def test_the_segment_is_the_active_log_byte_for_byte(self):
        root = _project()
        before = _active(root)
        events_before = [e["event"] for e in _history(root)[0].events]

        result = seal_log(root, AGENT)

        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(result.code, "LOG_SEALED")
        self.assertEqual(result["segment"], ".saipen/logs/LOG-001.md")
        self.assertEqual(_segments(root), {"LOG-001.md": before})
        self.assertEqual(result["sealed_sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual((result["sealed_from"], result["sealed_to"]), ("E-100", "E-450"))
        self.assertEqual(result["sealed_events"], 351)
        self.assertEqual(result["sealed_bytes"], len(before))

        snapshot, errors = _history(root)
        self.assertEqual(errors, [])
        self.assertEqual([e["event"] for e in snapshot.events], [*events_before, 451])
        self.assertEqual(validate_project(root), [])

    def test_the_fresh_tail_is_one_event_that_continues_the_chain(self):
        root = _project()
        result = seal_log(root, AGENT)
        self.assertTrue(result.ok, result.to_dict())

        lines = _active(root).decode("utf-8").splitlines()
        self.assertEqual(lines[0], "# Log")
        self.assertEqual(len(lines), 2)
        event = L.parse_log_line(lines[1])
        self.assertEqual((event["event"], event["parent"]), (451, 450))
        self.assertEqual(event["taxonomy"], "DEC")
        self.assertEqual(op_id_provenance(event["op_id"]), "canonical")
        self.assertEqual(event["op_id"], result.op_id)
        for fact in ("E-100..E-450", ".saipen/logs/LOG-001.md", result["sealed_sha256"][:16]):
            self.assertIn(fact, event["text"])
        self.assertLessEqual(len(lines[1].encode("utf-8")), 1024)
        state = parse_state((root / ".saipen" / "STATE.md").read_text(encoding="utf-8"))
        self.assertEqual(state["last_event"], 451)
        self.assertEqual(state["phase"], "CLEAN")

    def test_the_tail_keeps_the_log_s_own_newlines_and_heading(self):
        root = _project(newline="\r\n", heading=("# Log -- project ledger", ""))
        before = _active(root)
        self.assertTrue(seal_log(root, AGENT).ok)
        self.assertEqual(_segments(root)["LOG-001.md"], before)
        tail = _active(root)
        self.assertTrue(tail.startswith(b"# Log -- project ledger\r\n- "), tail[:60])
        self.assertTrue(tail.endswith(b"\r\n"))
        self.assertEqual(tail.count(b"\n"), tail.count(b"\r\n"))

    def test_the_number_follows_the_newest_segment_and_older_ones_are_untouched(self):
        root = _project(first=41, last=400, sealed=((1, 20), (21, 40)))
        older = _segments(root)
        before = _active(root)

        result = seal_log(root, AGENT)

        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(result["segment"], ".saipen/logs/LOG-003.md")
        self.assertEqual(_segments(root), {**older, "LOG-003.md": before})
        snapshot, errors = _history(root)
        self.assertEqual(errors, [])
        self.assertEqual([e["event"] for e in snapshot.events], list(range(1, 402)))

    def test_bytes_alone_cross_the_cap(self):
        root = _project(first=100, last=199, width=700)
        self.assertLess(len(_active(root).splitlines()), L.ACTIVE_LOG_MAX_LINES)
        self.assertGreater(len(_active(root)), L.ACTIVE_LOG_MAX_BYTES)
        self.assertTrue(seal_log(root, AGENT).ok)

    def test_the_project_works_on_after_a_seal(self):
        root = _project()
        self.assertTrue(seal_log(root, AGENT).ok)
        after = checkpoint(root, AGENT, "RUN", None, "the first ordinary event after a seal")
        self.assertTrue(after.ok, after.to_dict())
        snapshot, errors = _history(root)
        self.assertEqual(errors, [])
        self.assertEqual(snapshot.tail, 452)
        self.assertEqual(len(_active(root).decode("utf-8").splitlines()), 3)
        self.assertEqual(validate_project(root), [])

    def test_a_dry_run_names_the_plan_and_writes_nothing(self):
        root = _project()
        before = (_active(root), _segments(root), (root / ".saipen" / "STATE.md").read_bytes())
        planned = seal_log(root, AGENT, dry_run=True)
        self.assertTrue(planned.ok, planned.to_dict())
        self.assertTrue(planned["dry_run"])
        self.assertEqual(
            planned.changed_files,
            [".saipen/logs/LOG-001.md", ".saipen/LOG.md", ".saipen/STATE.md"],
        )
        self.assertEqual(
            before, (_active(root), _segments(root), (root / ".saipen" / "STATE.md").read_bytes())
        )
        self.assertEqual(scan_pending(root), ([], []))


class RefusalTests(unittest.TestCase):
    def assert_untouched(self, root: Path, before: tuple) -> None:
        self.assertEqual(before, (_active(root), _segments(root)))
        self.assertEqual(scan_pending(root), ([], []))

    def test_nothing_is_sealed_under_the_cap(self):
        root = _project(first=100, last=110)
        before = (_active(root), _segments(root))
        result = seal_log(root, AGENT)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "VALIDATION_FAILED")
        self.assertIs(result["due"], False)
        self.assertEqual((result["lines"], result["bytes"]), (12, len(before[0])))
        self.assert_untouched(root, before)

    def test_the_cap_is_exclusive_and_owned_by_one_module(self):
        self.assertFalse(L.seal_due(L.ACTIVE_LOG_MAX_LINES, L.ACTIVE_LOG_MAX_BYTES))
        self.assertTrue(L.seal_due(L.ACTIVE_LOG_MAX_LINES + 1, 0))
        self.assertTrue(L.seal_due(0, L.ACTIVE_LOG_MAX_BYTES + 1))
        source = (TOOLS / "validate.py").read_text(encoding="utf-8")
        self.assertIn("seal_due(active_lines, active_bytes)", source)
        self.assertNotIn("active_lines > 300", source)

    def test_a_seal_outside_clean_is_refused_and_names_the_way_in(self):
        root = _project(phase="DONE")
        before = (_active(root), _segments(root))
        result = seal_log(root, AGENT)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "ILLEGAL_PHASE")
        self.assertEqual(result["next_action"], "saipen transition CLEAN")
        self.assert_untouched(root, before)

    def test_a_seal_is_refused_while_work_is_in_flight(self):
        root = _project()
        claimed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (root / ".saipen" / "BOARD.md").write_text(
            "## DOING\n"
            f"- [/] T-9001 live work | verify: x | owner: other-agent | claim_time: {claimed}\n"
            "## TODO\n## DONE\n## BLOCKED\n",
            encoding="utf-8",
        )
        self.assertEqual(validate_project(root, current_agent=AGENT), [])
        before = (_active(root), _segments(root))
        result = seal_log(root, AGENT)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "VALIDATION_FAILED")
        self.assertIn("T-9001", result.message)
        self.assert_untouched(root, before)

    def test_not_due_is_answered_before_the_gates_that_only_matter_when_due(self):
        # Entering CLEAN reports every refused step except "not due", so a
        # short LOG beside someone else's live Work must not read as a failure.
        root = _project(first=100, last=110)
        claimed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (root / ".saipen" / "BOARD.md").write_text(
            "## DOING\n"
            f"- [/] T-9001 live work | verify: x | owner: other-agent | claim_time: {claimed}\n"
            "## TODO\n## DONE\n## BLOCKED\n",
            encoding="utf-8",
        )
        result = seal_log(root, AGENT)
        self.assertFalse(result.ok)
        self.assertIs(result["due"], False)

    def test_a_ledger_the_write_gate_refuses_is_not_sealed_into_history(self):
        # An event that names a parent newer than itself: the active LOG is
        # the writer's to get right, and a seal must not make it history.
        root = _project()
        text = _active(root).decode("utf-8")
        broken = text.replace("[E-300] [parent: E-299]", "[E-300] [parent: E-301]")
        self.assertNotEqual(text, broken)
        (root / ".saipen" / "LOG.md").write_bytes(broken.encode("utf-8"))
        before = (_active(root), _segments(root))
        result = seal_log(root, AGENT)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "VALIDATION_FAILED")
        self.assertIn("E-300", result.message)
        self.assert_untouched(root, before)


class BindingTests(unittest.TestCase):
    """The sealed history a seal was planned against is the one it lands on."""

    def _apply_after(self, tamper):
        ops = _live_ops()
        real = ops.apply_plan

        def apply_plan(root, plan):
            tamper(Path(root))
            return real(root, plan)

        return patch.object(ops, "apply_plan", apply_plan)

    def test_an_older_segment_changed_under_the_plan_refuses_the_seal(self):
        root = _project(first=41, last=400, sealed=((1, 20), (21, 40)))
        before = _active(root)

        def tamper(base: Path) -> None:
            path = base / ".saipen" / "logs" / "LOG-001.md"
            path.write_bytes(path.read_bytes() + b"\n")

        with self._apply_after(tamper):
            result = _live_ops().seal_log(root, AGENT)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "STALE_STATE")
        self.assertIn(".saipen/logs/LOG-001.md", result.message)
        self.assertEqual(_active(root), before)
        self.assertNotIn("LOG-003.md", _segments(root))

    def test_a_segment_that_appeared_under_the_plan_is_never_overwritten(self):
        root = _project()
        before = _active(root)

        def tamper(base: Path) -> None:
            (base / ".saipen" / "logs").mkdir(exist_ok=True)
            (base / ".saipen" / "logs" / "LOG-001.md").write_bytes(b"# foreign\n")

        with self._apply_after(tamper):
            result = _live_ops().seal_log(root, AGENT)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "STALE_STATE")
        self.assertEqual(_segments(root), {"LOG-001.md": b"# foreign\n"})
        self.assertEqual(_active(root), before)

    def test_the_bindings_are_the_tree_the_snapshot_was_validated_against(self):
        ops = _live_ops()
        root = _project(first=41, last=400, sealed=((1, 20), (21, 40)))
        docs = ops._read(root)[0]
        bound = ops._sealed_segment_bindings(root, docs)
        self.assertEqual(sorted(bound), [".saipen/logs/LOG-001.md", ".saipen/logs/LOG-002.md"])
        path = root / ".saipen" / "logs" / "LOG-002.md"
        path.write_bytes(path.read_bytes() + b"\n")
        self.assertIsNone(ops._sealed_segment_bindings(root, docs))

    def test_the_plan_binds_each_sealed_file_and_not_the_tree_it_writes_into(self):
        ops = _live_ops()
        root = _project(first=41, last=400, sealed=((1, 20), (21, 40)))
        captured = {}
        real = ops.apply_plan

        def apply_plan(base, plan):
            captured["plan"] = plan
            return real(base, plan)

        with patch.object(ops, "apply_plan", apply_plan):
            self.assertTrue(ops.seal_log(root, AGENT).ok)
        plan = captured["plan"]
        self.assertNotIn(".saipen/logs", plan.preconditions)
        self.assertEqual(plan.preconditions[".saipen/logs/LOG-003.md"], "")
        for name in ("LOG-001.md", "LOG-002.md"):
            self.assertIn(f".saipen/logs/{name}", plan.preconditions)
        self.assertEqual(plan.targets[0].path, ".saipen/logs/LOG-003.md")
        self.assertEqual(
            [t.role for t in plan.targets], ["generic", "log", "state"]
        )


class InterruptedSealTests(unittest.TestCase):
    def test_a_seal_interrupted_at_any_point_converges(self):
        for env_name in (
            "NITRO_CRASH_AFTER_PREPARE",
            "NITRO_CRASH_AFTER_GENERIC",
            "NITRO_CRASH_AFTER_LOG",
            "NITRO_CRASH_AFTER_STATE",
            "NITRO_CRASH_AFTER_VERIFIED",
        ):
            with self.subTest(env_name=env_name):
                root = _project(first=41, last=400, sealed=((1, 20), (21, 40)))
                older = _segments(root)
                before = _active(root)
                with patch.dict(os.environ, {env_name: "1"}, clear=False), self.assertRaises(
                    SystemExit
                ) as raised:
                    seal_log(root, AGENT)
                self.assertEqual(raised.exception.code, 87)
                self.assertTrue(scan_pending(root)[0], env_name)

                recovered = auto_recover_pending(root)
                self.assertTrue(recovered["ok"], (env_name, recovered))
                if "LOG-003.md" not in _segments(root):
                    # Interrupted before the first byte: aborted, and the
                    # canonical retry is the same seal.
                    self.assertEqual(_active(root), before)
                    self.assertTrue(seal_log(root, AGENT).ok)
                self.assertEqual(_segments(root), {**older, "LOG-003.md": before})
                snapshot, errors = _history(root)
                self.assertEqual(errors, [], env_name)
                self.assertEqual([e["event"] for e in snapshot.events], list(range(1, 402)))
                self.assertEqual(len(_active(root).decode("utf-8").splitlines()), 2)
                self.assertEqual(validate_project(root), [])
                self.assertEqual(scan_pending(root), ([], []))

    def test_the_interrupted_shape_holds_both_copies_never_neither(self):
        root = _project()
        before = _active(root)
        with patch.dict(
            os.environ, {"NITRO_CRASH_AFTER_GENERIC": "1"}, clear=False
        ), self.assertRaises(SystemExit):
            seal_log(root, AGENT)
        self.assertEqual(_segments(root), {"LOG-001.md": before})
        self.assertEqual(_active(root), before)


class CleanRouteTests(unittest.TestCase):
    """Entering CLEAN seals when due, by either verb that enters it."""

    def cli(self, root: Path, *args: str):
        return _cli(root, *args)

    def test_entering_clean_seals_a_log_past_its_cap(self):
        for words in (("transition", "CLEAN"), ("clean",)):
            with self.subTest(words=words):
                root = _project(phase="DONE")
                code, out, err = self.cli(root, *words, "--json")
                self.assertEqual(code, 0, (out, err))
                answer = json.loads(out)
                self.assertEqual(answer["phase"], "CLEAN")
                seal = answer["log_seal"]
                self.assertTrue(seal["ok"], seal)
                self.assertEqual(seal["code"], "LOG_SEALED")
                segment = (root / seal["segment"]).read_bytes().decode("utf-8")
                self.assertTrue(
                    segment.rstrip().endswith("RUN: transition to CLEAN"), segment[-200:]
                )
                self.assertEqual(len(_active(root).decode("utf-8").splitlines()), 2)
                self.assertEqual(_history(root)[1], [])
                state = parse_state((root / ".saipen" / "STATE.md").read_text(encoding="utf-8"))
                self.assertEqual(state["phase"], "CLEAN")

    def test_the_named_route_is_one_a_guarded_shell_admits(self):
        # The finding this ticket closes named an act nobody could perform.
        # `saipen clean` would repeat it: the guard reads that spelling as an
        # ordinary shell line and refuses it while no Work is active.
        from saipen_engine import guard_events

        root = _project(phase="DONE")
        named = seal_log(root, AGENT)["next_action"]
        self.assertEqual(named, "saipen transition CLEAN")
        self.assertIsNotNone(guard_events._saipen_cli_verb(named))
        source = (TOOLS / "validate.py").read_text(encoding="utf-8")
        self.assertIn("`saipen transition CLEAN` seals", source)
        self.assertIn("`saipen transition CLEAN` scrubs", source)

    def test_the_plain_answer_names_what_ran(self):
        root = _project(phase="DONE")
        code, out, err = self.cli(root, "transition", "CLEAN")
        self.assertEqual(code, 0, (out, err))
        self.assertIn("log_seal: LOG_SEALED -- .saipen/logs/LOG-001.md", out.splitlines())
        self.assertNotIn("board_scrub:", out)

    def test_another_transition_seals_nothing(self):
        root = _project(phase="CLEAN")
        before = _active(root)
        code, out, err = self.cli(root, "transition", "DONE", "--json")
        self.assertEqual(code, 0, (out, err))
        self.assertNotIn("log_seal", json.loads(out))
        self.assertEqual(_segments(root), {})
        self.assertTrue(_active(root).startswith(before))

    def test_entering_clean_says_nothing_about_a_log_under_its_cap(self):
        root = _project(first=100, last=110, phase="DONE")
        code, out, err = self.cli(root, "transition", "CLEAN", "--json")
        self.assertEqual(code, 0, (out, err))
        answer = json.loads(out)
        self.assertNotIn("log_seal", answer)
        self.assertEqual(_segments(root), {})

    def test_a_dry_run_of_the_entry_seals_nothing(self):
        for words in (("transition", "CLEAN"), ("clean",)):
            with self.subTest(words=words):
                root = _project(phase="DONE")
                before = _active(root)
                code, out, err = self.cli(root, *words, "--dry-run", "--json")
                self.assertEqual(code, 0, (out, err))
                self.assertNotIn("log_seal", json.loads(out))
                self.assertEqual(_active(root), before)
                self.assertEqual(_segments(root), {})


class ValidatorFindingTests(unittest.TestCase):
    """The finding names a command, and that command clears the finding."""

    def test_the_finding_names_the_route_and_the_route_clears_it(self):
        root = _project(phase="DONE")
        found = [line for line in _findings(root) if "[log-soft-cap]" in line]
        self.assertEqual(len(found), 1, found)
        self.assertIn(".saipen/LOG.md is 352 lines", found[0])
        self.assertIn("past the 300 line / 64 KB cap", found[0])
        self.assertIn("`saipen transition CLEAN` seals it", found[0])

        code, out, err = _cli(root, "transition", "CLEAN", "--json")
        self.assertEqual(code, 0, (out, err))
        self.assertTrue(json.loads(out)["log_seal"]["ok"])
        after = _findings(root)
        self.assertEqual([line for line in after if "soft-cap" in line], [])
        self.assertEqual([line for line in after if line.startswith("FAIL")], [])

    def test_a_log_under_its_cap_is_not_reported(self):
        root = _project(first=100, last=110, phase="DONE")
        self.assertEqual([line for line in _findings(root) if "soft-cap" in line], [])


if __name__ == "__main__":
    unittest.main()
