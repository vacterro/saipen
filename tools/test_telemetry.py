"""SRC-108: execution-time telemetry is derived, read-only and honest.

`saipen_engine.telemetry` answers "how long did it take, where did the time go,
when did real progress last happen" from the canonical LOG alone. These tests
freeze a LOG with known timestamps and prove the arithmetic, the honesty rules
(unobserved gaps, unknown counters, minute precision) and that asking the
question never writes anything or feeds a decision.

Run standalone:
    python tools/test_telemetry.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import telemetry  # noqa: E402
from saipen_engine.journal import ensure_project_lineage  # noqa: E402

UTC = dt.timezone.utc
TALLINN = dt.timezone(dt.timedelta(hours=3))


def _line(n: int, when: str, ticket: str | None, agent: str, op: str, tax: str, text: str) -> str:
    subject = f" [{ticket}]" if ticket else ""
    return f"- {when} [E-{n:03d}]{subject} [agent: {agent}] [op: {op}-{n:04x}] {tax}: {text}\n"


#: T-7 claimed 10:00, BUILD 10:05, a model replacement mid-BUILD, VERIFY 10:40,
#: blocked 10:50-11:10, resumed at VERIFY, REVIEW 11:20, finished 11:25; T-8
#: claimed 11:30; a 2-hour silence; a stop checkpoint; T-8 BUILD after midnight.
LOG = "".join(
    [
        "# Log\n",
        _line(1, "22.09.26 10:00", "T-7", "a", "claim", "DEC", "claimed via SAIOPS -- owner a"),
        _line(2, "22.09.26 10:05", "T-7", "a", "transition", "RUN", "transition to BUILD"),
        _line(3, "22.09.26 10:20", "T-7", "b", "checkpoint", "RUN", "build -> half done"),
        _line(4, "22.09.26 10:40", "T-7", "b", "transition", "RUN", "transition to VERIFY"),
        _line(5, "22.09.26 10:50", "T-7", "b", "ticket", "DEC",
              "ticket block via SAIOPS (active) -- waiting on T-9"),
        _line(6, "22.09.26 11:10", "T-7", "b", "ticket", "DEC",
              "ticket unblock via SAIOPS -- resumes at VERIFY"),
        _line(7, "22.09.26 11:20", "T-7", "b", "transition", "RUN", "transition to REVIEW"),
        _line(8, "22.09.26 11:25", "T-7", "b", "finish", "DEC",
              "ticket finished via SAIOPS -- completion (from SHIP)"),
        _line(9, "22.09.26 11:30", "T-8", "b", "claim", "DEC", "claimed via SAIOPS -- owner b"),
        _line(10, "22.09.26 13:30", "T-8", "b", "checkpoint", "RUN", "scout -> read the code"),
        _line(11, "22.09.26 20:50", None, "b", "stop", "DEC", "stop checkpoint"),
        _line(12, "22.09.26 21:10", "T-8", "c", "transition", "RUN", "transition to BUILD"),
        _line(13, "22.09.26 21:20", "T-8", "c", "checkpoint", "RUN", "build -> wrote it"),
    ]
)


def _state(task: str, phase: str) -> str:
    return (
        "---\n"
        f"phase: {phase}\n"
        f"task: {task}\n"
        f'next_action: "PHASE {phase} {task}"\n'
        'blocker: ""\n'
        "transition_from: SCOUT\n"
        "saipen_version: 8\n"
        "schema_version: 3\n"
        "last_event: 13\n"
        "style_contract: ded-4ae736e4\n"
        'saipen_home: "."\n'
        "agent: c\n"
        "mode: full\n"
        'updated: "2026-09-22T21:20:00Z"\n'
        "---\n"
    )


class TelemetryFixture(unittest.TestCase):
    def setUp(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="saipen-telemetry-"))
        self.addCleanup(lambda: shutil.rmtree(base, ignore_errors=True))
        self.root = base / "project"
        (self.root / ".saipen").mkdir(parents=True)
        (self.root / ".saipen" / "STATE.md").write_text(_state("T-8", "BUILD"), encoding="utf-8")
        (self.root / ".saipen" / "BOARD.md").write_text(
            "## DOING\n## TODO\n## DONE\n## BLOCKED\n", encoding="utf-8"
        )
        (self.root / ".saipen" / "LOG.md").write_text(LOG, encoding="utf-8")
        ensure_project_lineage(self.root)
        self.now = dt.datetime(2026, 9, 22, 21, 30, tzinfo=UTC)

    def stats(self, **kwargs) -> dict:
        return telemetry.stats(self.root, now=self.now, tz=kwargs.pop("tz", UTC), **kwargs)

    def rewrite_log(self, text: str) -> None:
        (self.root / ".saipen" / "LOG.md").write_text(text, encoding="utf-8")

    def digest(self) -> str:
        sha = hashlib.sha256()
        for path in sorted((self.root / ".saipen").rglob("*")):
            if path.is_file():
                sha.update(path.relative_to(self.root).as_posix().encode() + path.read_bytes())
        return sha.hexdigest()


class ArithmeticTests(TelemetryFixture):
    def test_two_checkpoints_give_their_interval(self):
        items = telemetry.intervals(telemetry.load(self.root))
        self.assertEqual(items[0]["seconds"], 5 * 60)
        self.assertEqual(items[0]["class"], "UNKNOWN")  # claimed, no phase yet

    def test_a_phase_change_starts_a_new_phase_duration(self):
        work = self.stats(work_id="T-7")["work"]
        self.assertEqual(work["by_class_s"]["BUILD"], 35 * 60)
        self.assertEqual(work["by_class_s"]["VERIFY"], 10 * 60 + 10 * 60)
        self.assertEqual(work["by_class_s"]["REVIEW"], 5 * 60)

    def test_a_model_replacement_does_not_reset_work_elapsed(self):
        """Agent a hands T-7 to agent b mid-BUILD; the Work clock keeps running."""
        work = self.stats(work_id="T-7")["work"]
        self.assertEqual(work["agents"], ["a", "b"])
        self.assertEqual(work["observed_s"], 85 * 60)  # claim 10:00 .. finish 11:25
        self.assertEqual(work["by_class_s"]["UNKNOWN"], 5 * 60)  # claimed, no phase yet
        self.assertEqual(work["time_to_first_progress_s"], 5 * 60)
        self.assertEqual(work["terminal"], "DONE")

    def test_blocked_time_is_not_active_time(self):
        today = self.stats()["days"][0]
        self.assertEqual(today["blocked_s"], 20 * 60)
        self.assertEqual(today["active_s"], today["observed_s"] - 20 * 60)

    def test_a_long_silence_and_time_after_a_stop_are_unobserved(self):
        items = telemetry.intervals(telemetry.load(self.root))
        silence = next(item for item in items if item["event"] == 10)
        after_stop = next(item for item in items if item["event"] == 11)
        self.assertEqual((silence["observed"], after_stop["observed"]), (False, False))
        self.assertEqual(after_stop["class"], "UNOBSERVED")

    def test_the_day_rollup_crosses_work_items(self):
        today = self.stats()["days"][0]
        self.assertEqual(today["work_touched"], 2)
        self.assertEqual(today["work_completed"], 1)
        self.assertEqual(today["work_completions"], 1)
        # A reopened-and-reshipped ticket finishes twice but is one Work item,
        # so the distinct count can never read larger than the touched count.
        self.assertLessEqual(today["work_completed"], today["work_touched"])
        self.assertEqual(today["verified_slices"], 1)
        self.assertEqual(today["checkpoints"], 13)
        self.assertEqual(today["checkpoint_pace"]["longest_s"], 7 * 3600 + 20 * 60)

    def test_a_reopened_ticket_counts_as_one_work_item_and_two_finishes(self):
        """A ticket shipped, reopened by a regression and re-shipped is one Work
        item with two completions. Reporting the event count under the name
        "work completed" made the day read as 38 completed of 31 touched."""
        log = LOG + _line(
            14, "22.09.26 11:40", "T-7", "b", "finish", "DEC",
            "ticket finished via SAIOPS -- completion (from SHIP)",
        )
        self.rewrite_log(log)
        today = self.stats()["days"][0]
        self.assertEqual((today["work_completed"], today["work_completions"]), (1, 2))
        self.assertEqual(today["work_touched"], 2)

    def test_local_midnight_splits_an_interval(self):
        """21:10-21:20 UTC is 00:10-00:20 on the next Tallinn day."""
        self.now = dt.datetime(2026, 9, 22, 21, 30, tzinfo=UTC)
        days = self.stats(tz=TALLINN, days=2)["days"]
        self.assertEqual(days[0]["date"], "2026-09-23")
        self.assertEqual(days[0]["by_class_s"], {"BUILD": 10 * 60})
        self.assertEqual(days[1]["date"], "2026-09-22")
        self.assertNotIn("BUILD", {k for k, v in days[1]["by_class_s"].items() if k == "T-8"})

    def test_current_work_measures_from_its_claim_and_phase_entry(self):
        current = self.stats()["current"]
        self.assertEqual(current["task"], "T-8")
        self.assertEqual(current["work_elapsed_s"], 10 * 3600)  # claimed 11:30
        self.assertEqual(current["phase_elapsed_s"], 20 * 60)   # BUILD at 21:10
        self.assertEqual(current["since_checkpoint_s"], 10 * 60)
        self.assertEqual(current["since_progress_s"], 20 * 60)  # prose is not progress


class HonestyTests(TelemetryFixture):
    def test_unreconstructible_counters_are_unknown_not_zero(self):
        today = self.stats()["days"][0]
        for field in ("worker_generations", "agent_incarnations", "manual_recoveries"):
            self.assertIsNone(today[field], field)

    def test_an_undated_event_is_dropped_not_guessed(self):
        path = self.root / ".saipen" / "LOG.md"
        path.write_text(
            LOG.replace("- 22.09.26 10:00 [E-001]", "- [E-001]"), encoding="utf-8"
        )
        self.assertEqual(len(telemetry.load(self.root)), 12)

    def test_stats_writes_nothing(self):
        before = self.digest()
        self.stats()
        self.stats(work_id="T-7")
        self.assertEqual(self.digest(), before)

    def test_json_is_deterministic_for_a_frozen_fixture(self):
        first = json.dumps(self.stats(days=2), sort_keys=True)
        self.assertEqual(json.dumps(self.stats(days=2), sort_keys=True), first)

    def test_an_unreadable_history_degrades_to_telemetry_unavailable(self):
        (self.root / ".saipen" / "LOG.md").unlink()
        payload = self.stats()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "TELEMETRY_UNAVAILABLE")


class NoAuthorityTests(unittest.TestCase):
    def test_no_engine_module_decides_anything_from_telemetry(self):
        """Time observes: nothing in the engine imports it to decide."""
        engine = TOOLS / "saipen_engine"
        importing = re.compile(
            r"^\s*(from \.telemetry"
            r"|from \. import .*telemetry"
            r"|import .*telemetry)",
            re.MULTILINE,
        )
        users = [
            path.name
            for path in engine.glob("*.py")
            if importing.search(path.read_text(encoding="utf-8", errors="replace"))
        ]
        self.assertEqual(users, [])


if __name__ == "__main__":
    unittest.main()
