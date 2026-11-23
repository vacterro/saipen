"""T-1667: entering CLEAN runs the bounded journal compaction it orders.

phases/clean.md step 4 told an agent to run `journal.compact_committed`, a
function with no production caller and no verb, inside a namespace the guard
protects -- reachable only by importing the engine in a shell. Entering CLEAN
now runs it under the writer lock and reports what it dropped and what it
left, beside the BOARD scrub and the LOG seal:

* a COMMITTED operation left in the working directory moves to the settled
  ledger with its staged bytes dropped and its record intact;
* a queued post-settlement cleanup is retried and its marker cleared;
* staged bytes a settlement left before the queue existed are found by one
  sweep per checkout, so later passes stay bounded by the queue;
* an operation of any other status keeps every byte;
* nothing to act on says nothing, and validation stays clean throughout.
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.fast_check import validate_project  # noqa: E402
from saipen_engine.journal import (  # noqa: E402
    CLEANUP_QUEUE_DIR,
    LEGACY_SWEEP_MARKER,
    OPS_DIR,
    SETTLED_DIR,
)
from saipen_engine.operations import compact_journal  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1640_board_scrub import AGENT, _cli, _done, _project  # noqa: E402

PAYLOAD = b"staged bytes of a write that already committed\n" * 64


def setUpModule() -> None:
    isolate_host_session()


def _settled_op(root: Path) -> Path:
    """One real COMMITTED operation, written by the engine itself."""
    before = set((root / SETTLED_DIR).iterdir()) if (root / SETTLED_DIR).is_dir() else set()
    code, out, err = _cli(root, "checkpoint", "RUN", "a note for the journal", "--json")
    assert code == 0, (out, err)
    fresh = sorted(set((root / SETTLED_DIR).iterdir()) - before)
    assert len(fresh) == 1, fresh
    return fresh[0]


def _record(entry: Path) -> bytes:
    return (entry / "operation.json").read_bytes()


class CleanEntryTests(unittest.TestCase):
    def project(self) -> Path:
        root = _project([_done(f"T-{n}", prose="short ") for n in range(1, 4)], phase="DONE")
        self.addCleanup(shutil.rmtree, root, True)
        return root

    def enter_clean(self, root: Path) -> dict:
        code, out, err = _cli(root, "transition", "CLEAN", "--json")
        self.assertEqual(code, 0, (out, err))
        return json.loads(out)

    def test_a_committed_operation_in_the_working_directory_is_compacted(self):
        root = self.project()
        settled = _settled_op(root)
        record = _record(settled)
        unsettled = root / OPS_DIR / settled.name
        unsettled.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(settled), str(unsettled))
        (unsettled / "BOARD.md.staged").write_bytes(PAYLOAD)
        self.assertEqual(validate_project(root), [])

        report = self.enter_clean(root)["journal_compaction"]
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["compacted"], [settled.name], report)
        self.assertEqual(report["before"]["staged_bytes"], len(PAYLOAD))
        self.assertEqual(report["after"], {"ops": 0, "queued": 0, "staged_bytes": 0})
        self.assertFalse(unsettled.exists())
        self.assertEqual(_record(settled), record, "the settled record keeps every byte")
        self.assertEqual(list(settled.glob("*.staged")), [])
        self.assertEqual(validate_project(root), [])

    def test_a_queued_cleanup_is_retried_and_its_marker_cleared(self):
        root = self.project()
        settled = _settled_op(root)
        (settled / "LOG.md.staged").write_bytes(PAYLOAD)
        queue = root / CLEANUP_QUEUE_DIR
        queue.mkdir(parents=True, exist_ok=True)
        (queue / settled.name).write_text("", encoding="utf-8")

        report = self.enter_clean(root)["journal_compaction"]
        self.assertTrue(report["ok"], report)
        self.assertIn(settled.name, report["compacted"])
        self.assertEqual(report["before"]["queued"], 1)
        self.assertEqual(report["after"]["queued"], 0)
        self.assertEqual(list(settled.glob("*.staged")), [])
        self.assertFalse((queue / settled.name).exists())
        self.assertEqual(validate_project(root), [])

    def test_after_the_one_legacy_sweep_nothing_to_compact_says_nothing(self):
        root = self.project()
        first = self.enter_clean(root)["journal_compaction"]
        self.assertTrue(first["ok"], first)
        self.assertEqual((first["legacy_queued"], first["compacted"]), ([], []))
        self.assertTrue((root / LEGACY_SWEEP_MARKER).is_file())
        _cli(root, "transition", "DONE", "--json")
        self.assertNotIn("journal_compaction", self.enter_clean(root))
        refused = compact_journal(root, AGENT).to_dict()
        self.assertFalse(refused["ok"])
        self.assertIs(refused["due"], False)

    def test_staged_bytes_older_than_the_queue_are_found_once(self):
        root = self.project()
        resolved, kept = _settled_op(root), _settled_op(root)
        for entry, status in ((resolved, "RESOLVED"), (kept, "VERIFIED")):
            record = json.loads(_record(entry).decode("utf-8"))
            record["status"] = status
            (entry / "operation.json").write_text(json.dumps(record), encoding="utf-8")
            (entry / "0_legacy.staged").write_bytes(PAYLOAD)
        records = {entry: _record(entry) for entry in (resolved, kept)}

        report = self.enter_clean(root)["journal_compaction"]
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["legacy_queued"], [resolved.name], report)
        self.assertEqual(report["compacted"], [resolved.name], report)
        self.assertEqual(report["before"]["staged_bytes"], len(PAYLOAD))
        self.assertEqual(report["after"]["staged_bytes"], 0)
        self.assertEqual(list(resolved.glob("*.staged")), [])
        self.assertEqual(len(list(kept.glob("*.staged"))), 1, "only COMMITTED/RESOLVED lose bytes")
        self.assertEqual({e: _record(e) for e in records}, records)
        self.assertEqual(validate_project(root), [])


class StatusTests(unittest.TestCase):
    """Only COMMITTED/RESOLVED operations lose staged bytes."""

    def test_an_operation_of_another_status_keeps_every_byte(self):
        root = _project([_done("T-1", prose="short ")], phase="DONE")
        self.addCleanup(shutil.rmtree, root, True)
        settled = _settled_op(root)
        live = root / OPS_DIR / settled.name
        live.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(settled), str(live))
        record = json.loads(_record(live).decode("utf-8"))
        record["status"] = "VERIFIED"
        (live / "operation.json").write_text(json.dumps(record), encoding="utf-8")
        (live / "BOARD.md.staged").write_bytes(PAYLOAD)
        before = {p.name: p.read_bytes() for p in live.iterdir()}

        report = compact_journal(root, AGENT).to_dict()
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["compacted"], [])
        self.assertIn(settled.name, report["skipped"])
        self.assertEqual({p.name: p.read_bytes() for p in live.iterdir()}, before)
        self.assertEqual(report["after"]["staged_bytes"], len(PAYLOAD))

    def test_a_preview_writes_nothing(self):
        root = _project([_done("T-1", prose="short ")], phase="DONE")
        self.addCleanup(shutil.rmtree, root, True)
        settled = _settled_op(root)
        live = root / OPS_DIR / settled.name
        live.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(settled), str(live))
        (live / "BOARD.md.staged").write_bytes(PAYLOAD)
        preview = compact_journal(root, AGENT, dry_run=True).to_dict()
        self.assertEqual(preview["code"], "DRY_RUN", preview)
        self.assertTrue((live / "BOARD.md.staged").is_file())


if __name__ == "__main__":
    unittest.main()
