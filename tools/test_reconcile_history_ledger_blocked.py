"""T-1322: immutable-ledger corruption is a PRECISE blocked class, not a dead end.

The SAITULS live surface (13.09.26) presented a LOG history that fails the
immutable-ledger contract (duplicate/out-of-order E-IDs, an illegal SAIPATCH
line, a dangling parent edge). That is a DISTINCT historical-corruption class:
automatic byte repair would fabricate history, so canonical recovery MUST NOT
reconstruct it.

Required behaviour, proved here:
  * `reconcile_protocol_state` -- the operation behind `saipen recover` and the
    exact preview Fleet classifies -- refuses with the precise, registered code
    `HISTORY_LEDGER_CORRUPT`, never the opaque generic `VALIDATION_FAILED`;
  * the exact underlying diagnostics survive in `detail` (it names the
    immutable-ledger contract, not "something went wrong");
  * ZERO canonical writes: STATE/BOARD/LOG are byte-identical before and after,
    on the dry-run PLAN and on the real APPLY attempt;
  * the code is one of the registered `error_codes`, so it survives the Result
    closure and reaches the outer Fleet/continue surface as a machine-readable
    blocked classification (`BOUND_RECOVERY_REQUIRED_BLOCKED` +
    `reason_code: HISTORY_LEDGER_CORRUPT`);
  * the deferred ledger repair is NOT implemented here -- no reconstruction, no
    deletion, no synthesized operation identity.
"""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402
from test_hermetic_env import hermetic_env  # noqa: E402
from test_regression_gate import RegressionGateFixture  # noqa: E402


def _live(name: str):
    importlib.import_module(name)
    return sys.modules[name]


def _state_text(saipen_home: Path) -> str:
    # `saipen_home` MUST resolve to THIS running install for the history gate to
    # apply: that is the only ledger the running install is the authority for
    # (a foreign/sub project carries its own history).
    return (
        "---\n"
        "phase: SHIP\n"
        "task: T-001\n"
        'next_action: "PHASE SHIP T-001"\n'
        "blocker: none\n"
        "transition_from: REVIEW\n"
        "saipen_version: 7\n"
        "schema_version: 3\n"
        "last_event: 2\n"
        'style_contract: ' + CURRENT_STYLE_CONTRACT + '\n'
        "agent: tester\n"
        "requires:\n  - filesystem\n  - python\n"
        "mode: full\n"
        "updated: 2026-08-30T00:00:00Z\n"
        f"saipen_home: {saipen_home.as_posix()}\n"
        "---\n"
    )


class ImmutableLedgerBlockedTests(unittest.TestCase):
    def _make_corrupt_ledger_project(self) -> Path:
        home = _live("saipen_engine.state").running_home()
        root = Path(tempfile.mkdtemp(prefix="t1322-ledger-"))
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        (root / ".saipen").mkdir(parents=True)
        (root / ".saipen" / "STATE.md").write_text(
            _state_text(home), encoding="utf-8"
        )
        (root / ".saipen" / "BOARD.md").write_text(
            "## DOING\n- [/] T-001 [P1] fix | verify: test\n## TODO\n## DONE\n## BLOCKED\n",
            encoding="utf-8",
        )
        # A DUPLICATE E-ID is an immutable-ledger violation: the same event
        # identity appears twice, so the ledger is void. No byte-level repair is
        # legal (which of the two is the real record?).
        (root / ".saipen" / "LOG.md").write_text(
            "# Log\n"
            "- 30.08.26 00:00 [E-0001] [agent: tester] DEC: seed\n"
            "- 30.08.26 00:01 [E-0001] [agent: tester] DEC: duplicated identity\n",
            encoding="utf-8",
        )
        return root

    def _canonical_bytes(self, root: Path) -> dict[str, bytes]:
        return {
            name: (root / ".saipen" / name).read_bytes()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        }

    def test_dry_run_is_a_precise_blocked_class_with_zero_writes(self) -> None:
        root = self._make_corrupt_ledger_project()
        before = self._canonical_bytes(root)

        result = _live("saipen_engine.reconcile").reconcile_protocol_state(
            root, "tester", dry_run=True
        )

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "HISTORY_LEDGER_CORRUPT", result)
        self.assertNotEqual(result["code"], "VALIDATION_FAILED", result)
        self.assertIn("immutable-ledger", result["detail"], result)
        self.assertEqual(
            result["terminal_disposition"], "FORENSICALLY_UNRECOVERABLE", result
        )
        self.assertFalse(result["needs_local_mutation"], result)
        self.assertFalse(result["operator_decision_available"], result)
        self.assertIsNone(result["canonical_next_command"], result)
        self.assertEqual(result["blocking_surface"], "log", result)
        self.assertIsNone(result["blocking_field"], result)
        self.assertEqual(result["evidence_reference"], ".saipen/LOG.md", result)
        # The exact offending identity survives the refusal.
        self.assertIn("E-1", result["detail"], result)
        self.assertEqual(self._canonical_bytes(root), before, "dry-run wrote bytes")

    def test_apply_attempt_refuses_and_writes_nothing(self) -> None:
        root = self._make_corrupt_ledger_project()
        before = self._canonical_bytes(root)

        result = _live("saipen_engine.reconcile").reconcile_protocol_state(
            root, "tester", dry_run=False
        )

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "HISTORY_LEDGER_CORRUPT", result)
        self.assertEqual(
            result["terminal_disposition"], "FORENSICALLY_UNRECOVERABLE", result
        )
        self.assertEqual(self._canonical_bytes(root), before, "apply wrote bytes")

    def test_code_is_registered_so_fleet_can_report_it(self) -> None:
        # A code absent from the closed set would be rejected at the Result
        # boundary, collapsing the precise class back into a crash/dead end.
        self.assertIn("HISTORY_LEDGER_CORRUPT", _live("saipen_engine.errors").CODES)
        self.assertEqual(
            _live("saipen_engine.fleet").CLASS_BLOCKED,
            "BOUND_RECOVERY_REQUIRED_BLOCKED",
        )
        # The precise code survives a Result construction (the closure that would
        # reject an unregistered refusal code).
        result = _live("saipen_engine.result").Result(
            ok=False, code="HISTORY_LEDGER_CORRUPT", message="ledger corrupt"
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "HISTORY_LEDGER_CORRUPT")

    def test_fleet_reports_terminal_forensic_block_instead_of_recover_loop(self) -> None:
        root = self._make_corrupt_ledger_project()
        paths = _live("saipen_engine.paths")
        lineage = paths.new_project_lineage()
        (root / ".saipen" / "IDENTITY.md").write_text(
            paths.identity_file_content(lineage), encoding="utf-8"
        )

        result = _live("saipen_engine.fleet").preflight(
            root, host_root=root, host_lineage=lineage
        )

        self.assertEqual(result["reason_code"], "HISTORY_LEDGER_CORRUPT", result)
        self.assertEqual(
            result["terminal_disposition"], "FORENSICALLY_UNRECOVERABLE", result
        )
        self.assertFalse(result["needs_local_mutation"], result)
        self.assertFalse(result["operator_decision_available"], result)
        self.assertIsNone(result["canonical_next_command"], result)


class PublicLedgerDiagnosticTests(RegressionGateFixture):
    """A05: public routes must agree with the actual recovery owner."""

    REGRESSION = ""
    COMMANDS = (("status",), ("next",), ("continue",),
                ("recover", "--dry-run"), ("explain-next",))

    def native(self, root: Path, words: tuple[str, ...]) -> tuple[int, dict]:
        completed = subprocess.run(
            [sys.executable, "-B", str(TOOLS / "saipen.py"),
             "--project-root", str(root), *words, "--json"],
            cwd=root, env=hermetic_env(SAIPEN_CAPABILITY="no-publish"),
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45,
        )
        self.assertIn(completed.returncode, (0, 1), completed.stderr)
        value = json.loads(completed.stdout)
        if words == ("explain-next",):
            self.assertEqual(completed.returncode, 0, value)
            self.assertEqual(value["code"], "EXPLAIN_NEXT", value)
            return 1 if not value["carrier"].get("ok", True) else 0, value["carrier"]
        return completed.returncode, value

    def bytes(self, root: Path) -> dict[str, bytes]:
        return {name: (root / ".saipen" / name).read_bytes()
                for name in ("STATE.md", "BOARD.md", "LOG.md")}

    def append_missing_parent(self) -> None:
        path = self.project / ".saipen/LOG.md"
        with path.open("a", encoding="utf-8") as stream:
            stream.write("- 24.08.26 00:04 [E-004] [parent: E-3133] [T-7] "
                         "[agent: tester] RUN: missing historical parent\n")

    def assert_terminal_parity(self) -> None:
        before = self.bytes(self.project)
        for words in self.COMMANDS:
            with self.subTest(command=words):
                rc, value = self.native(self.project, words)
                self.assertEqual(rc, 1, value)
                self.assertFalse(value["ok"], value)
                self.assertEqual(value["code"], "HISTORY_LEDGER_CORRUPT", value)
                self.assertEqual(value["terminal_disposition"],
                                 "FORENSICALLY_UNRECOVERABLE", value)
                self.assertIsNone(value["canonical_next_command"], value)
                self.assertFalse(value["needs_local_mutation"], value)
                self.assertFalse(value["safe_auto_repair_available"], value)
                self.assertFalse(value["operator_decision_available"], value)
                self.assertTrue(value["read_only_diagnosis_only"], value)
                self.assertEqual(value["evidence_reference"], ".saipen/LOG.md", value)
                self.assertIsNone(value.get("action"), value)
                self.assertIn("immutable-ledger", value["detail"], value)
                self.assertEqual(self.bytes(self.project), before, words)

    def test_missing_parent_routes_are_terminal_and_write_nothing(self) -> None:
        self.append_missing_parent()
        self.assert_terminal_parity()

    def test_duplicate_event_routes_are_terminal_and_write_nothing(self) -> None:
        path = self.project / ".saipen/LOG.md"
        lines = path.read_text(encoding="utf-8").splitlines()
        lines.insert(1, "- 24.08.26 00:01 [E-001] [T-7] "
                     "[agent: tester] RUN: duplicate historical identity")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assert_terminal_parity()

    def test_out_of_order_history_routes_are_terminal_and_write_nothing(self) -> None:
        path = self.project / ".saipen/LOG.md"
        lines = path.read_text(encoding="utf-8").splitlines()
        lines[1], lines[2] = lines[2], lines[1]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assert_terminal_parity()

    def test_unbacked_head_does_not_hide_the_precise_ledger_owner(self) -> None:
        self.append_missing_parent()
        path = self.project / ".saipen/STATE.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace("phase: VERIFY", "phase: DONE")
        text = text.replace("task: T-7", "task: none")
        text = text.replace("PHASE VERIFY T-7", "SCOUT: next workable ticket")
        path.write_text(text, encoding="utf-8")
        self.assert_terminal_parity()

    def test_healthy_status_next_and_recover_remain_healthy_without_writes(self) -> None:
        before = self.bytes(self.project)
        for words in (("status",), ("next",), ("recover", "--dry-run")):
            rc, value = self.native(self.project, words)
            self.assertEqual(rc, 0, value)
            self.assertTrue(value["ok"], value)
            self.assertNotEqual(value.get("terminal_disposition"),
                                "FORENSICALLY_UNRECOVERABLE", value)
            self.assertEqual(self.bytes(self.project), before, words)

    def test_repairable_checkpoint_keeps_its_registered_recovery_route(self) -> None:
        path = self.project / ".saipen/STATE.md"
        path.write_text(path.read_text(encoding="utf-8").replace("last_event: 3", "last_event: 99"),
                        encoding="utf-8")
        before = self.bytes(self.project)
        for words in (("status",), ("next",)):
            rc, value = self.native(self.project, words)
            self.assertEqual(rc, 1, value)
            self.assertEqual(value["action"], "saipen recover", value)
            self.assertNotEqual(value.get("code"), "HISTORY_LEDGER_CORRUPT", value)
            self.assertEqual(self.bytes(self.project), before)
        _rc, recovery = self.native(self.project, ("recover", "--dry-run"))
        self.assertNotEqual(recovery.get("terminal_disposition"),
                            "FORENSICALLY_UNRECOVERABLE", recovery)
        self.assertEqual(self.bytes(self.project), before)

    def test_proven_foreign_tail_keeps_the_same_executable_quarantine_route(self) -> None:
        from test_log_tail_quarantine import project

        with tempfile.TemporaryDirectory(prefix="a05-proven-quarantine-") as directory:
            root = project(Path(directory))
            before = self.bytes(root)
            for words in self.COMMANDS:
                with self.subTest(command=words):
                    rc, value = self.native(root, words)
                    self.assertEqual(rc, 1, value)
                    self.assertEqual(value["code"], "HISTORY_LEDGER_CORRUPT", value)
                    self.assertIsNone(value["terminal_disposition"], value)
                    self.assertEqual(value["canonical_next_command"],
                                     "saipen recover quarantine-log-tail", value)
                    self.assertTrue(value["operator_decision_available"], value)
                    self.assertEqual(self.bytes(root), before, words)

    def test_healthy_route_requires_no_additional_strict_history_read(self) -> None:
        reconcile = _live("saipen_engine.reconcile")
        diagnostic = getattr(reconcile, "checkpoint_ledger_diagnostic", None)
        self.assertIsNotNone(diagnostic, "shared recovery diagnostic is absent")
        with mock.patch("saipen_engine.operations._read", side_effect=AssertionError("extra read")):
            self.assertIsNone(diagnostic(self.project, {"ok": True, "action": "PHASE VERIFY T-7"}))

    def test_manifest_runtime_preflight_keeps_recovery_error_precedence(self) -> None:
        self.append_missing_parent()
        reconcile = _live("saipen_engine.reconcile")
        diagnostic = getattr(reconcile, "checkpoint_ledger_diagnostic", None)
        self.assertIsNotNone(diagnostic, "shared recovery diagnostic is absent")
        unavailable = {"ok": False, "code": "SAIPEN_HOST_RUNTIME_UNAVAILABLE",
                       "detail": "controlled manifest access denial"}
        before = self.bytes(self.project)
        with mock.patch("saipen_engine.audit_manifest.ensure", return_value=unavailable):
            self.assertEqual(
                reconcile.reconcile_protocol_state(self.project, "tester", dry_run=True),
                unavailable,
            )
            self.assertIsNone(
                diagnostic(self.project, {"ok": False, "reason": "checkpoint-invalid"})
            )
        self.assertEqual(self.bytes(self.project), before)


if __name__ == "__main__":
    unittest.main()
