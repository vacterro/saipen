"""A crashed worker's claim follows only its proven same-run successor."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import admission, entry, operations, supervisor, watchdog, worker  # noqa: E402
from saipen_engine.plan import apply_plan  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.paths import project_lineage_identity, unbound_environment  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1363_zero_manual_entry import project  # noqa: E402


def setUpModule():
    isolate_host_session()


class ClaimContinuityTests(unittest.TestCase):
    def setUp(self):
        self.root = project(self)
        result = operations.ticket_add(
            self.root, "test-agent", "P1", "repair the fixture", [], "fixture repaired"
        )
        self.assertTrue(result.ok, result.to_dict())
        self.ticket = result.data["ticket"]
        self.run = "continuity-run"

    def env(self, generation, *, run=None, session=None, **extra):
        return unbound_environment(
            os.environ,
            SAIPEN_AUTONOMY_RUN_ID=run or self.run,
            SAIPEN_AUTONOMY_WORKER=f"worker-{generation}",
            SAIPEN_LEASE_GENERATION=str(generation),
            SAIPEN_HOST_SESSION=session or f"session-{generation}",
            SAIPEN_PROJECT_ROOT=str(self.root),
            SAIPEN_PROJECT_LINEAGE=project_lineage_identity(self.root),
            **extra,
        )

    def claim(self, env):
        with patch.dict(os.environ, env, clear=True):
            return operations.apply_claim(self.root, self.ticket, "test-agent")

    def snapshot(self):
        return tuple(
            (self.root / ".saipen" / name).read_bytes()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        )

    def fields(self):
        return parse_board((self.root / ".saipen/BOARD.md").read_text(encoding="utf-8"))["tickets"][
            self.ticket
        ]["fields"]

    def predecessor(self):
        # Real lease acquisition and canonical claim; no hand-written claim witness.
        watchdog.acquire_lease(self.root, "worker-1", run_id=self.run)
        result = self.claim(self.env(1))
        self.assertTrue(result.ok, result.to_dict())
        return self.fields()

    def replace(self, *, run=None):
        watchdog.fence(self.root, "worker-1", 1)
        result = supervisor.replace_worker(self.root, "worker-2", run_id=run or self.run)
        self.assertTrue(result["ok"], result)

    def test_a_same_run_successor_adopts_exact_work(self):
        before = self.predecessor()
        self.replace()
        result = self.claim(self.env(2))
        self.assertTrue(result.ok, result.to_dict())
        self.assertTrue(result.data.get("continued_generation"), result.to_dict())
        self.assertEqual(self.fields()["claim_run"], before["claim_run"])
        self.assertEqual(self.fields()["claim_generation"], "2")
        self.assertNotEqual(self.fields()["claim_session"], before["claim_session"])

    def test_b_foreign_live_window_refuses_without_mutation(self):
        self.predecessor()
        before = self.snapshot()
        result = self.claim(self.env(1, session="foreign-window"))
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(self.snapshot(), before)
        replacement = supervisor.replace_worker(self.root, "worker-2", run_id=self.run)
        self.assertFalse(replacement["ok"], replacement)

    def test_c_fenced_predecessor_cannot_mutate_after_adoption(self):
        self.predecessor()
        self.replace()
        self.assertTrue(self.claim(self.env(2)).ok)
        before = self.snapshot()
        with patch.dict(os.environ, self.env(1), clear=True):
            result = operations.checkpoint(
                self.root, "test-agent", "RUN", self.ticket, "stale generation"
            )
            view = admission.protocol_snapshot(self.root, session_id="session-1")
        self.assertFalse(result.ok, result.to_dict())
        self.assertIsNotNone(view["block"])
        self.assertEqual(self.snapshot(), before)

    def test_d_restart_run_cannot_adopt(self):
        self.predecessor()
        self.replace(run="different-run")
        before = self.snapshot()
        result = self.claim(self.env(2, run="different-run"))
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(self.snapshot(), before)

    def lapse_claim(self):
        # Age the claim past CLAIM_LIVENESS_WINDOW; the only hand edit is the clock.
        path = self.root / ".saipen/BOARD.md"
        text = path.read_text(encoding="utf-8")
        claim_time = self.fields()["claim_time"]
        path.write_text(
            text.replace(f"claim_time: {claim_time}", "claim_time: 2026-01-01T00:00:00Z"),
            encoding="utf-8",
        )
        self.assertEqual(self.fields()["claim_time"], "2026-01-01T00:00:00Z")

    def test_g_supervised_worker_adopts_lapsed_legacy_claim(self):
        legacy = unbound_environment(
            os.environ,
            SAIPEN_HOST_SESSION="legacy-window",
            SAIPEN_PROJECT_ROOT=str(self.root),
            SAIPEN_PROJECT_LINEAGE=project_lineage_identity(self.root),
        )
        self.assertTrue(self.claim(legacy).ok)
        self.lapse_claim()
        watchdog.acquire_lease(self.root, "worker-1", run_id=self.run)
        result = self.claim(self.env(1))
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(self.fields()["claim_generation"], "1")

    def test_h_restarted_run_adopts_claim_only_after_it_lapses(self):
        before = self.predecessor()
        self.replace(run="different-run")
        self.lapse_claim()
        result = self.claim(self.env(2, run="different-run"))
        self.assertTrue(result.ok, result.to_dict())
        self.assertFalse(result.data.get("continued_generation"), result.to_dict())
        self.assertNotEqual(self.fields()["claim_run"], before["claim_run"])
        self.assertEqual(self.fields()["claim_generation"], "2")

    def test_heartbeat_never_holds_the_canonical_writer_mutex(self):
        # A worker's canonical APPLY fails fast on WRITER_BUSY, so a beat that
        # held the project mutex turned every collision into a dead cycle.
        self.predecessor()
        seen = []
        original = watchdog._save

        def save_while_worker_applies(root, payload):
            with patch.dict(os.environ, self.env(1), clear=True):
                seen.append(
                    operations.checkpoint(self.root, "test-agent", "RUN", self.ticket, "beat")
                )
            original(root, payload)

        with patch.object(watchdog, "_save", save_while_worker_applies):
            watchdog.heartbeat(self.root, "worker-1", 1)
        self.assertEqual(len(seen), 1)
        self.assertTrue(seen[0].ok, seen[0].to_dict())

    def test_lease_read_survives_a_concurrent_replace(self):
        # Windows reports a read racing the heartbeat's os.replace as
        # PermissionError; that is contention, never a missing lease.
        self.predecessor()
        target = (self.root / watchdog.CACHE_REL).resolve()
        original = Path.read_text
        raised = []

        def racing_read(path, *args, **kwargs):
            if Path(path).resolve() == target and not raised:
                raised.append(path)
                raise PermissionError(13, "sharing violation", str(path))
            return original(path, *args, **kwargs)

        with patch.dict(os.environ, self.env(1), clear=True), patch.object(
            Path, "read_text", racing_read
        ):
            current = watchdog.current_carrier(self.root)
        self.assertEqual(len(raised), 1)
        self.assertIsNotNone(current)

    def test_lease_write_survives_a_concurrent_reader(self):
        self.predecessor()
        original = watchdog.safe_atomic_write_bytes
        raised = []

        def racing_replace(*args, **kwargs):
            if not raised:
                raised.append(args[0])
                raise PermissionError(13, "sharing violation", str(args[0]))
            return original(*args, **kwargs)

        with patch.object(watchdog, "safe_atomic_write_bytes", racing_replace):
            payload = watchdog.heartbeat(self.root, "worker-1", 1)
        self.assertEqual(len(raised), 1)
        self.assertEqual(payload["status"], watchdog.HEALTHY)

    def test_supervisor_survives_a_heartbeat_io_failure(self):
        script = self.root / "agent.py"
        script.write_text("import time\ntime.sleep(0.5)\n", encoding="utf-8")

        def failing_beat(*_args, **_kwargs):
            raise PermissionError(13, "sharing violation")

        with patch.object(watchdog, "heartbeat", failing_beat):
            result = worker.supervise(
                self.root,
                [sys.executable, str(script)],
                max_cycles=1,
                slice_timeout=20,
                heartbeat_every=0.05,
                backoff=(0,),
                env=unbound_environment(os.environ, SAIPEN_GPU="off"),
            )
        self.assertEqual(result["history"][0]["returncode"], 0, result)

    def test_e_wrong_lineage_or_project_refuses(self):
        self.predecessor()
        self.replace()
        for key, value in (
            ("SAIPEN_PROJECT_LINEAGE", "wrong-lineage"),
            ("SAIPEN_PROJECT_ROOT", str(self.root / "elsewhere")),
        ):
            with self.subTest(key=key):
                env = self.env(2)
                env[key] = value
                before = self.snapshot()
                result = self.claim(env)
                self.assertFalse(result.ok, result.to_dict())
                self.assertEqual(self.snapshot(), before)

    def test_f_replay_does_not_transfer_ownership_twice(self):
        self.predecessor()
        self.replace()
        first = self.claim(self.env(2))
        self.assertTrue(first.ok, first.to_dict())
        before = self.snapshot()
        again = self.claim(self.env(2))
        self.assertTrue(again.ok, again.to_dict())
        self.assertFalse(again.data.get("continued_generation"), again.to_dict())
        # An ordinary SELF heartbeat may advance claim_time, never LOG/STATE.
        after = self.snapshot()
        self.assertEqual((after[0], after[2]), (before[0], before[2]))

    def test_journal_replay_is_idempotent(self):
        self.predecessor()
        self.replace()
        with patch.dict(os.environ, self.env(2), clear=True):
            clock = operations._operation_clock()
            plan = operations._plan_claim(
                self.root,
                self.ticket,
                "test-agent",
                clock.now,
                clock.utc,
                instant=clock.instant,
            )
            first = apply_plan(self.root, plan)
            self.assertTrue(first.ok, first.to_dict())
            before = self.snapshot()
            again = apply_plan(self.root, plan)
            self.assertTrue(again.ok, again.to_dict())
            self.assertEqual(again.code, "ALREADY_APPLIED")
            self.assertEqual(self.snapshot(), before)

    def test_successor_requires_canonical_claim_before_checkpoint(self):
        self.predecessor()
        self.replace()
        before = self.snapshot()
        with patch.dict(os.environ, self.env(2), clear=True):
            view = admission.protocol_snapshot(self.root, session_id="session-2")
            result = operations.checkpoint(
                self.root, "test-agent", "RUN", self.ticket, "unclaimed successor"
            )
        self.assertEqual(view["route"], f"saipen claim {self.ticket}")
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(self.snapshot(), before)

    def test_start_reuses_the_canonical_claim_branch(self):
        watchdog.acquire_lease(self.root, "worker-1", run_id=self.run)
        task = "implement the continuous fixture"
        with patch.dict(os.environ, self.env(1), clear=True):
            first = entry.start_work(self.root, "test-agent", actor_source="explicit", text=task)
        self.assertTrue(first["ok"], first)
        self.ticket = first["ticket"]
        self.replace()
        with patch.dict(os.environ, self.env(2), clear=True):
            second = entry.start_work(self.root, "test-agent", actor_source="explicit", text=task)
        self.assertTrue(second["ok"], second)
        self.assertEqual(second["ticket"], first["ticket"])
        self.assertEqual(second["receipt"], first["receipt"])
        self.assertEqual(self.fields()["claim_generation"], "2")

    def test_fence_between_plan_and_apply_refuses_without_mutation(self):
        self.predecessor()
        self.replace()
        with patch.dict(os.environ, self.env(2), clear=True):
            clock = operations._operation_clock()
            plan = operations._plan_claim(
                self.root,
                self.ticket,
                "test-agent",
                clock.now,
                clock.utc,
                instant=clock.instant,
            )
            watchdog.fence(self.root, "worker-2", 2)
            before = self.snapshot()
            result = apply_plan(self.root, plan)
            self.assertFalse(result.ok, result.to_dict())
            self.assertEqual(result.code, "FENCED_LEASE_GENERATION")
            self.assertEqual(self.snapshot(), before)

    def test_lost_watchdog_evidence_never_authorizes_continuation(self):
        self.predecessor()
        self.replace()
        # Disposable fixture only: an absent cache cannot prove its old fences.
        (self.root / watchdog.CACHE_REL).unlink()
        before = self.snapshot()
        result = self.claim(self.env(2))
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(self.snapshot(), before)

    def test_predecessor_witness_survives_two_replacements(self):
        self.predecessor()
        self.replace()
        watchdog.fence(self.root, "worker-2", 2)
        third = supervisor.replace_worker(self.root, "worker-3", run_id=self.run)
        self.assertTrue(third["ok"], third)
        result = self.claim(self.env(3))
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(self.fields()["claim_generation"], "3")

    def test_checkpoint_preserves_current_claim_witness(self):
        self.predecessor()
        self.replace()
        self.assertTrue(self.claim(self.env(2)).ok)
        before = self.fields()
        with patch.dict(os.environ, self.env(2), clear=True):
            result = operations.checkpoint(
                self.root, "test-agent", "RUN", self.ticket, "durable progress"
            )
        self.assertTrue(result.ok, result.to_dict())
        for key in ("claim_run", "claim_generation", "claim_session"):
            self.assertEqual(self.fields()[key], before[key])

    def test_unreadable_predecessor_claim_is_not_continuation_authority(self):
        self.predecessor()
        self.replace()
        ticket = parse_board((self.root / ".saipen/BOARD.md").read_text())["tickets"][self.ticket]
        for changes in ({"claim_time": "invalid"}, {"owner": "", "claim_time": ""}):
            with self.subTest(changes=changes), patch.dict(os.environ, self.env(2), clear=True):
                malformed = {**ticket, "fields": {**ticket["fields"], **changes}}
                self.assertFalse(watchdog.can_continue_claim(self.root, malformed))

    def test_real_supervise_generations_claim_then_crash_and_continue(self):
        script = self.root / "agent.py"
        script.write_text(
            "import json, os, subprocess, sys\n"
            "from pathlib import Path\n"
            "generation = int(os.environ['SAIPEN_LEASE_GENERATION'])\n"
            "os.environ['SAIPEN_HOST_SESSION'] = 'chaos-' + str(generation)\n"
            f"cli = {str(TOOLS / 'saipen.py')!r}\n"
            f"ticket = {self.ticket!r}\n"
            "if generation > 1:\n"
            "    route = subprocess.run([sys.executable, cli, 'continue', '--json'],\n"
            "                           capture_output=True, text=True)\n"
            "    Path('route.json').write_text(route.stdout, encoding='utf-8')\n"
            "p = subprocess.run([sys.executable, cli, 'claim', ticket, '--json'],\n"
            "                   capture_output=True, text=True)\n"
            "Path('generation-' + str(generation) + '.json').write_text(\n"
            "    p.stdout, encoding='utf-8')\n"
            "if p.returncode: print(p.stdout, p.stderr); sys.exit(p.returncode)\n"
            "if generation == 1: os._exit(137)\n"
            "p = subprocess.run([sys.executable, cli, 'checkpoint', 'RUN', ticket,\n"
            "                    'successor continued exact Work', '--json'],\n"
            "                   capture_output=True, text=True)\n"
            "print(p.stdout, p.stderr)\n"
            "sys.exit(p.returncode)\n",
            encoding="utf-8",
        )
        result = worker.supervise(
            self.root,
            [sys.executable, str(script)],
            max_cycles=2,
            slice_timeout=20,
            heartbeat_every=0.1,
            backoff=(0,),
            env=unbound_environment(os.environ, SAIPEN_GPU="off"),
        )
        self.assertEqual(result["counters"]["worker_generation_count"], 2, result)
        second = json.loads((self.root / "generation-2.json").read_text(encoding="utf-8"))
        self.assertTrue(second["ok"], second)
        self.assertTrue(second.get("continued_generation"), second)
        route = json.loads((self.root / "route.json").read_text(encoding="utf-8"))
        self.assertEqual(route["action"], f"saipen claim {self.ticket}", route)
        self.assertEqual(result["history"][1]["returncode"], 0, result)
        self.assertEqual(result["counters"]["manual_continue_count"], 0)
        self.assertEqual(result["counters"]["stolen_lease_count"], 0)


if __name__ == "__main__":
    unittest.main()
