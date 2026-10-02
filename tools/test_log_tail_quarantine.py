"""A foreign suffix after the checkpointed tail, and the repair that cuts it.

Measured live on this install's own project, 29.09.26: an agent working in
another project ran `tools/_log_append.py` from this project's root. `--help`
became a LOG line, and three of that agent's own events followed it -- E-2602,
E-2603 and E-2604, ids this ledger had spent months earlier, with a parent edge
to E-2601. Every verb then refused HISTORY_LEDGER_CORRUPT, and `recover` said
FORENSICALLY_UNRECOVERABLE with no command: "no local mutation can reconstruct
the missing truth". Nothing was missing. The ledger through the checkpointed
`last_event` was intact; the damage was a suffix no checkpoint ever bound.

`saipen recover quarantine-log-tail` is the exit. It cuts that suffix, keeps
the ledger through `last_event` byte for byte, preserves the original LOG, and
refuses by name whenever the cut is not provable.
"""

from __future__ import annotations

import hashlib
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

def quarantine_log_tail(*args, **kwargs):
    # Import at execution, not collection: the behavioral public-CLI control
    # must reach a pre-fix runtime that has no quarantine API.
    from saipen_engine.operations import quarantine_log_tail as repair

    return repair(*args, **kwargs)

from saipen_engine.paths import identity_file_content, new_project_lineage  # noqa: E402
from test_hermetic_env import hermetic_env, isolate_host_session  # noqa: E402

HOME = TOOLS.parent


def setUpModule() -> None:
    isolate_host_session()


STATE = (
    "---\nphase: BUILD\ntask: T-1\nnext_action: \"PHASE BUILD T-1\"\nblocker: \"\"\n"
    "transition_from: SCOUT\nsaipen_version: 8\nschema_version: 3\nlast_event: {last}\n"
    "style_contract: " + CURRENT_STYLE_CONTRACT + "\nsaipen_home: \"{home}\"\nmode: full\n"
    "updated: 2026-09-29T00:00:00Z\nagent: test-agent\n---\n"
)
BOARD = (
    "## DOING\n- [/] T-1 [P1] quarantine fixture | verify: the cut runs "
    "| owner: test-agent | claim_time: 2026-09-29T00:00:00Z\n"
    "## TODO\n## DONE\n## BLOCKED\n"
)
PREFIX = (
    "- 29.09.26 10:00 [E-1300] [T-1] [agent: test-agent] [op: ticket-fixture] "
    "DEC: ticket added via SAIOPS\n"
    "- 29.09.26 10:01 [E-1301] [parent: E-1300] [T-1] [agent: test-agent] "
    "[op: claim-fixture] DEC: claimed via SAIOPS -- owner test-agent\n"
    "- 29.09.26 10:02 [E-1302] [parent: E-1301] [T-1] [agent: test-agent] "
    "[op: checkpoint-fixture] RUN: SCOUT -- the checkpointed tail\n"
)
#: The measured shape: a bare flag, then another project's events with ids this
#: ledger already spent and a parent edge into its own old history.
FOREIGN = (
    "--help\n"
    "- 29.09.26 20:47 [E-1301] [parent: E-1300] [T-261] [agent: buffy] "
    "[op: scout-4c1f9a2b] RUN: SCOUT -- another project's line\n"
    "- 29.09.26 20:48 [E-1302] [parent: E-1301] [T-261] [agent: buffy] "
    "[op: build-7b1e2c9d] RUN: build -> another project's build\n"
)


def project(base: Path, log: str = PREFIX + FOREIGN, last: int = 1302) -> Path:
    root = base / "project"
    saipen = root / ".saipen"
    saipen.mkdir(parents=True)
    (saipen / "STATE.md").write_text(
        STATE.format(home=HOME.as_posix(), last=last), encoding="utf-8"
    )
    (saipen / "BOARD.md").write_text(BOARD, encoding="utf-8")
    (saipen / "LOG.md").write_text(log, encoding="utf-8")
    (saipen / "IDENTITY.md").write_text(
        identity_file_content(new_project_lineage()), encoding="utf-8"
    )
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    return root


def cli(root: Path, *argv: str) -> dict:
    completed = subprocess.run(
        [sys.executable, str(TOOLS / "saipen.py"), "--project-root", str(root), *argv, "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=hermetic_env(), timeout=600,
    )
    return json.loads(completed.stdout)


class QuarantineLogTailTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="tailq-")
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name).resolve()

    def log_bytes(self, root: Path) -> bytes:
        return (root / ".saipen" / "LOG.md").read_bytes()

    def test_the_fixture_really_is_the_deadlock(self) -> None:
        """Guard: the strict read refuses ordinary work exactly as measured."""
        root = project(self.base)
        from saipen_engine.operations import checkpoint

        blocked = checkpoint(root, "test-agent", "RUN", "T-1", "ordinary work").to_dict()
        self.assertFalse(blocked.get("ok"), blocked)
        self.assertEqual(blocked.get("code"), "HISTORY_LEDGER_CORRUPT", blocked)

    def test_public_recovery_same_damage_preserves_bytes_and_resumes(self) -> None:
        """Same oracle reaches the old runtime, not an absent-API import.

        Pre-fix: checkpoint HISTORY_LEDGER_CORRUPT; bare recover reports
        FORENSICALLY_UNRECOVERABLE and no canonical repair. Post-fix must name
        the repair, preserve original/prefix bytes and pass validate.
        """
        root = project(self.base)
        before = self.log_bytes(root)
        blocked = cli(root, "checkpoint", "RUN", "ordinary work")
        self.assertEqual(blocked.get("code"), "HISTORY_LEDGER_CORRUPT", blocked)
        recovery = cli(root, "recover")
        self.assertEqual(self.log_bytes(root), before, "diagnosis must not cut bytes")
        route = recovery.get("canonical_next_command")
        self.assertEqual(route, "saipen recover quarantine-log-tail", recovery)
        repaired = cli(root, "recover", "quarantine-log-tail")
        self.assertTrue(repaired.get("ok"), repaired)
        self.assertEqual((root / repaired["evidence_path"]).read_bytes(), before)
        self.assertEqual(repaired["evidence_sha256"], hashlib.sha256(before).hexdigest())
        prefix = before[:before.index(b"--help")]
        self.assertTrue(self.log_bytes(root).startswith(prefix))
        self.assertIn(b"LOG foreign tail quarantined", self.log_bytes(root))
        self.assertTrue(cli(root, "validate").get("ok"))

    def test_the_cut_keeps_the_ledger_and_records_itself(self) -> None:
        root = project(self.base)
        result = quarantine_log_tail(root, "test-agent").to_dict()
        self.assertTrue(result.get("ok"), result)
        self.assertEqual(result.get("code"), "LOG_TAIL_QUARANTINED")
        self.assertEqual(result.get("claimed_ids"), ["E-1301", "E-1302"])
        self.assertEqual(result.get("non_event_lines"), 1)
        lines = self.log_bytes(root).decode("utf-8").splitlines()
        self.assertEqual(lines[:3], PREFIX.splitlines(), "the kept ledger moved")
        self.assertEqual(len(lines), 4, lines)
        self.assertIn("[E-1303] [parent: E-1302]", lines[3])
        self.assertIn("LOG foreign tail quarantined", lines[3])
        self.assertNotIn("buffy", "\n".join(lines))

    def test_the_original_bytes_are_preserved(self) -> None:
        root = project(self.base)
        before = self.log_bytes(root)
        result = quarantine_log_tail(root, "test-agent").to_dict()
        evidence = root / result["evidence_path"]
        self.assertEqual(evidence.read_bytes(), before)
        self.assertEqual(result["evidence_sha256"], hashlib.sha256(before).hexdigest())

    def test_ordinary_work_resumes_and_validates(self) -> None:
        root = project(self.base)
        self.assertTrue(quarantine_log_tail(root, "test-agent").ok)
        from saipen_engine.operations import checkpoint

        after = checkpoint(root, "test-agent", "RUN", "T-1", "ordinary work")
        self.assertTrue(after.ok, getattr(after, "message", after))
        why = cli(root, "validate")
        self.assertTrue(why.get("ok"), why)

    def test_a_suffix_id_above_the_tail_is_never_cut(self) -> None:
        """It may be a genuine event whose checkpoint never landed."""
        log = PREFIX + FOREIGN + (
            "- 29.09.26 20:49 [E-1303] [parent: E-1302] [T-1] [agent: test-agent] "
            "[op: checkpoint-late] RUN: uncheckpointed\n"
        )
        root = project(self.base, log=log)
        before = self.log_bytes(root)
        result = quarantine_log_tail(root, "test-agent").to_dict()
        self.assertFalse(result.get("ok"), result)
        self.assertIn("E-1303", result.get("message", ""))
        self.assertIn("above the checkpointed E-1302", result.get("message", ""))
        self.assertEqual(self.log_bytes(root), before, "a refusal must write nothing")

    def test_a_stale_last_event_is_not_a_cut_boundary(self) -> None:
        """STATE behind a legal tail means the suffix holds a real event."""
        root = project(self.base, last=1301)
        before = self.log_bytes(root)
        result = quarantine_log_tail(root, "test-agent").to_dict()
        self.assertFalse(result.get("ok"), result)
        self.assertIn("tail quarantine not provable", result.get("message", ""))
        self.assertEqual(self.log_bytes(root), before)

    def test_damage_before_the_tail_still_refuses(self) -> None:
        # A duplicate id in the middle of the ledger, well before the tail.
        damaged = PREFIX.replace("[E-1301] [parent: E-1300]", "[E-1300] [parent: E-1300]")
        root = project(self.base, log=damaged + FOREIGN)
        before = self.log_bytes(root)
        result = quarantine_log_tail(root, "test-agent").to_dict()
        self.assertFalse(result.get("ok"), result)
        self.assertEqual(result.get("code"), "HISTORY_LEDGER_CORRUPT", result)
        self.assertIn("damaged before the checkpointed tail", result.get("message", ""))
        self.assertEqual(self.log_bytes(root), before)

    def test_a_legal_log_refuses_rather_than_writing_a_no_op(self) -> None:
        root = project(self.base, log=PREFIX)
        before = self.log_bytes(root)
        result = quarantine_log_tail(root, "test-agent").to_dict()
        self.assertFalse(result.get("ok"), result)
        self.assertEqual(result.get("code"), "VALIDATION_FAILED")
        self.assertEqual(self.log_bytes(root), before)

    def test_a_comment_only_suffix_is_not_a_tail(self) -> None:
        log = PREFIX + "# a note\n\n"
        root = project(self.base, log=log)
        before = self.log_bytes(root)
        result = quarantine_log_tail(root, "test-agent").to_dict()
        self.assertFalse(result.get("ok"), result)
        self.assertEqual(self.log_bytes(root), before)

    def test_recover_names_the_exit_instead_of_unrecoverable(self) -> None:
        """The measured dead end: FORENSICALLY_UNRECOVERABLE, command null."""
        root = project(self.base)
        verdict = cli(root, "recover", "--dry-run")
        self.assertEqual(verdict.get("code"), "HISTORY_LEDGER_CORRUPT", verdict)
        self.assertEqual(
            verdict.get("canonical_next_command"), "saipen recover quarantine-log-tail", verdict
        )
        self.assertIsNone(verdict.get("terminal_disposition"), verdict)

    def test_recover_stays_unrecoverable_when_the_cut_is_not_provable(self) -> None:
        root = project(self.base, last=1301)
        verdict = cli(root, "recover", "--dry-run")
        self.assertEqual(verdict.get("code"), "HISTORY_LEDGER_CORRUPT", verdict)
        self.assertIsNone(verdict.get("canonical_next_command"), verdict)
        self.assertEqual(verdict.get("terminal_disposition"), "FORENSICALLY_UNRECOVERABLE")

    def test_the_canonical_command_reaches_it(self) -> None:
        root = project(self.base)
        record = cli(root, "recover", "quarantine-log-tail")
        self.assertTrue(record.get("ok"), record)
        self.assertEqual(record.get("code"), "LOG_TAIL_QUARANTINED")
        self.assertTrue(cli(root, "validate").get("ok"))

    def test_the_command_takes_no_other_argument(self) -> None:
        root = project(self.base)
        before = self.log_bytes(root)
        record = cli(root, "recover", "quarantine-log-tail", "normalize-log")
        self.assertFalse(record.get("ok"), record)
        self.assertEqual(self.log_bytes(root), before)

    def test_every_repair_evidence_root_is_durable_and_byte_bound(self) -> None:
        """A preserved LOG whose digest the ledger records must keep its bytes.

        `normalize-log` and `quarantine-log-tail` both keep the LOG they
        rewrote, and neither root was on the runtime-namespace policy: a
        managed project would have released it as debris candidates and let
        Git's CRLF conversion break the digest the DEC names.
        """
        from saipen_engine import operations
        from saipen_engine import runtime_namespace as rn

        roots = [
            value
            for name, value in vars(operations).items()
            if name.endswith("_EVIDENCE_ROOT") and str(value).startswith(".saipen/recovery/")
        ]
        self.assertIn(operations.QUARANTINE_EVIDENCE_ROOT, roots)
        byte_bound = {pattern for pattern, _probe in rn.BYTE_BOUND_PATTERNS}
        for root in roots:
            with self.subTest(root=root):
                self.assertTrue(rn.is_durable_protected(root + "/op/LOG.md"))
                self.assertIsNone(rn.runtime_class(root + "/op/LOG.md"))
                self.assertIn(root + "/**", byte_bound)

    def test_reconcile_never_plans_on_the_cut_ledger(self) -> None:
        """The observation is the cut; only the op that writes the cut may ask."""
        from saipen_engine.operations import REPAIR_OBSERVABLE, TAIL_QUARANTINE_OBSERVABLE

        self.assertTrue(set(TAIL_QUARANTINE_OBSERVABLE).isdisjoint(REPAIR_OBSERVABLE))


if __name__ == "__main__":
    unittest.main(verbosity=2)
