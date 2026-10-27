"""T-1916 (SRC-325 §10): work performed OUTSIDE the canonical lifecycle.

A blocked protocol state does not stop an operator from fixing code, and it
does not stop an agent from editing files through workspace tools while the
lifecycle refuses to move. The field incident is exactly that: application
files were repaired during a reconciliation deadlock, and the ledger never saw
it.

The classifier here must tell the truth about that delta:

* it reports the real changed paths with their observed digests and stamps;
* it attributes a clause only when the CHANGED BYTES carry it;
* it never writes, never backdates, never mints an event;
* presence is not verification, so the record says NOT_EXECUTED;
* publication authority stays closed no matter how complete the delta is.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402
from test_hermetic_env import hermetic_env, isolate_host_session  # noqa: E402

from saipen_engine.handoff_reconciliation import (  # noqa: E402
    EXTERNAL_ACCEPTED_FOR_ADMISSION,
    EXTERNAL_NO_DELTA,
    EXTERNAL_PARTIAL_DELTA,
    EXTERNAL_QUARANTINED,
    EXTERNAL_UNAVAILABLE,
    classify_external_delta,
)
from saipen_engine.paths import identity_file_content, new_project_lineage  # noqa: E402

HOME = TOOLS.parent


def setUpModule() -> None:
    isolate_host_session()


STATE = (
    "---\n"
    "phase: BUILD\n"
    "task: T-9\n"
    "next_action: \"PHASE BUILD T-9\"\n"
    "blocker: none\n"
    "transition_from: SCOUT\n"
    "saipen_version: 8\n"
    "schema_version: 3\n"
    "last_event: 45\n"
    "style_contract: " + CURRENT_STYLE_CONTRACT + "\n"
    "saipen_home: \"" + HOME.as_posix() + "\"\n"
    "agent: buffy\n"
    "mode: full\n"
    "updated: \"2026-10-25T00:00:00Z\"\n"
    "---\n"
)
BOARD = "## DOING\n- [/] T-9 [P1] repair launcher | verify: x\n## TODO\n## DONE\n## BLOCKED\n"
LOG = (
    "- 25.10.26 00:00 [E-44] [T-9] [agent: buffy] [op: ticket-fixture] "
    "DEC: ticket added via SAIOPS\n"
    "- 25.10.26 00:00 [E-45] [T-9] [agent: buffy] RUN: ccc converge\n"
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )


class ExternalWorkTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="t1916-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        _git(self.root, "init", "-q")
        _git(self.root, "config", "user.email", "fixture@example.invalid")
        _git(self.root, "config", "user.name", "fixture")
        (self.root / "launcher.py").write_text(
            "def start():\n    return 'stale watcher'\n", encoding="utf-8"
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "baseline")

    def test_a_clean_tree_carries_no_external_work(self) -> None:
        record = classify_external_delta(
            self.root, objective="Repair launcher startup and watcher"
        )
        self.assertEqual(record.disposition, EXTERNAL_NO_DELTA, record)
        self.assertEqual(record.paths, [])
        self.assertFalse(record.history_written)
        self.assertEqual(record.verification, "NOT_EXECUTED")

    def test_covering_delta_is_admissible_but_never_verified(self) -> None:
        (self.root / "launcher.py").write_text(
            "def start():\n    return 'launcher startup watcher repaired'\n",
            encoding="utf-8",
        )
        record = classify_external_delta(
            self.root, objective="Repair launcher startup and watcher"
        )
        self.assertEqual(record.disposition, EXTERNAL_ACCEPTED_FOR_ADMISSION, record)
        self.assertEqual(record.clauses_covered, record.clauses_total)
        # Presence on disk is not a passing run.
        self.assertEqual(record.verification, "NOT_EXECUTED")
        self.assertEqual(record.work_settlement, "ADMISSION_REQUIRED")
        self.assertEqual(record.publication_authority, "CLOSED")
        self.assertFalse(record.history_written)

    def test_provenance_is_the_bytes_that_exist_now(self) -> None:
        (self.root / "launcher.py").write_text(
            "def start():\n    return 'launcher startup watcher repaired'\n",
            encoding="utf-8",
        )
        record = classify_external_delta(
            self.root, objective="Repair launcher startup and watcher"
        )
        self.assertEqual([entry["path"] for entry in record.paths], ["launcher.py"])
        entry = record.paths[0]
        self.assertEqual(len(entry["sha256"]), 64)
        self.assertTrue(entry["observed_mtime"].endswith("Z"))
        self.assertTrue(entry["present"])
        self.assertEqual(entry["class"], "PROJECT")

    def test_protocol_memory_is_marked_not_credited_as_project_work(self) -> None:
        (self.root / ".saipen").mkdir()
        (self.root / ".saipen" / "NOTE.md").write_text("scratch\n", encoding="utf-8")
        record = classify_external_delta(
            self.root, objective="Repair launcher startup and watcher"
        )
        classes = {entry["path"]: entry["class"] for entry in record.paths}
        self.assertEqual(classes.get(".saipen/NOTE.md"), "PROTOCOL_MEMORY")

    def test_a_delta_nothing_can_attribute_is_quarantined(self) -> None:
        (self.root / "css").mkdir()
        (self.root / "css" / "theme.css").write_text(
            ".window { color: gold; }\n", encoding="utf-8"
        )
        record = classify_external_delta(
            self.root, objective="Repair launcher startup and watcher"
        )
        self.assertEqual(record.disposition, EXTERNAL_QUARANTINED, record)
        self.assertEqual(record.work_settlement, "ATTRIBUTION_REQUIRED")
        self.assertEqual(record.clauses_covered, 0)
        # Quarantine is not deletion: the delta is still identified.
        self.assertEqual(
            [entry["path"] for entry in record.paths], ["css/theme.css"]
        )

    def test_a_delta_with_no_objective_is_never_silently_credited(self) -> None:
        (self.root / "launcher.py").write_text("x\n", encoding="utf-8")
        record = classify_external_delta(self.root)
        self.assertEqual(record.disposition, EXTERNAL_QUARANTINED, record)
        self.assertEqual(record.clauses_total, 0)
        self.assertEqual(record.work_settlement, "ATTRIBUTION_REQUIRED")

    def test_partial_coverage_names_the_outstanding_clauses(self) -> None:
        (self.root / "launcher.py").write_text(
            "def start():\n    return 'launcher startup watcher repaired'\n",
            encoding="utf-8",
        )
        record = classify_external_delta(
            self.root,
            objective=(
                "1. Repair launcher startup watcher\n"
                "2. Publish the signed installer to the download mirror."
            ),
        )
        self.assertEqual(record.disposition, EXTERNAL_PARTIAL_DELTA, record)
        self.assertGreaterEqual(record.clauses_covered, 1)
        self.assertTrue(record.uncovered_clauses)
        self.assertEqual(record.next_exact_action, "IMPLEMENT_MISSING_DELTA")

    def test_no_worktree_is_honest_absence_not_a_clean_bill(self) -> None:
        bare = self.root.parent / (self.root.name + "-nogit")
        bare.mkdir()
        self.addCleanup(lambda: bare.exists() and bare.rmdir())
        record = classify_external_delta(bare, objective="Repair launcher startup")
        self.assertEqual(record.disposition, EXTERNAL_UNAVAILABLE, record)
        self.assertEqual(record.work_settlement, "UNOBSERVABLE")
        self.assertEqual(record.paths, [])

    def test_classification_writes_nothing(self) -> None:
        """The whole point: evidence in, zero canonical bytes out."""
        (self.root / "launcher.py").write_text("changed\n", encoding="utf-8")
        before = _tree_state(self.root)
        classify_external_delta(self.root, objective="Repair launcher startup watcher")
        classify_external_delta(self.root)
        self.assertEqual(_tree_state(self.root), before)


def _tree_state(root: Path) -> dict:
    """Every file's relative path plus digest, EXCLUDING .git internals."""
    state: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and ".git/" not in path.relative_to(root).as_posix():
            state[path.relative_to(root).as_posix()] = path.read_bytes().hex()[:64]
    return state


class ExternalDeltaCommandTests(unittest.TestCase):
    """`saipen source delta <SRC>` -- reachable, read-only, honest."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="t1916c-")
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve()
        self.root = self.base / "problip"
        saipen = self.root / ".saipen"
        saipen.mkdir(parents=True)
        (saipen / "STATE.md").write_text(STATE, encoding="utf-8")
        (saipen / "BOARD.md").write_text(BOARD, encoding="utf-8")
        (saipen / "LOG.md").write_text(LOG, encoding="utf-8")
        (saipen / "IDENTITY.md").write_text(
            identity_file_content(new_project_lineage()), encoding="utf-8"
        )
        (self.root / "launcher.py").write_text("baseline\n", encoding="utf-8")
        _git(self.root, "init", "-q")
        _git(self.root, "config", "user.email", "fixture@example.invalid")
        _git(self.root, "config", "user.name", "fixture")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "baseline")

    def cli(self, *argv: str) -> dict:
        from test_operator_origin_support import cold_command

        env = hermetic_env()
        command = cold_command(
            self.root,
            [
                sys.executable,
                str(TOOLS / "saipen.py"),
                "--project-root",
                str(self.root),
                *argv,
                "--json",
            ],
            env,
        )
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=600,
        )
        try:
            return json.loads(completed.stdout)
        except ValueError:  # pragma: no cover - a crash is its own failure
            raise AssertionError(
                f"{argv} produced no record (rc={completed.returncode})\n"
                f"{completed.stdout[-600:]}\n{completed.stderr[-600:]}"
            ) from None

    def test_the_verb_is_reachable_and_reports_the_delta(self) -> None:
        (self.root / "launcher.py").write_text("repaired\n", encoding="utf-8")
        record = self.cli("source", "delta", "SRC-999")
        self.assertTrue(record.get("ok"), record)
        self.assertEqual(record.get("code"), EXTERNAL_QUARANTINED, record)
        self.assertEqual(
            [entry["path"] for entry in record.get("paths") or []], ["launcher.py"]
        )
        self.assertFalse(record.get("history_written"))
        self.assertEqual(record.get("verification"), "NOT_EXECUTED")

    def test_the_verb_needs_its_receipt(self) -> None:
        record = self.cli("source", "delta")
        self.assertFalse(record.get("ok"), record)
        self.assertEqual(record.get("code"), "VALIDATION_FAILED")

    def test_the_verb_changes_no_canonical_byte(self) -> None:
        (self.root / "launcher.py").write_text("repaired\n", encoding="utf-8")
        before = _tree_state(self.root)
        self.cli("source", "delta", "SRC-999")
        self.assertEqual(_tree_state(self.root), before)


if __name__ == "__main__":
    unittest.main()
