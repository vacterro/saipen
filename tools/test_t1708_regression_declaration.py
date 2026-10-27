"""T-1708: existing Work can strengthen its real regression gate canonically.

Drive the journaled API and the native CLI, then the real VERIFY gate. The
same verifier runs against the missing route and its correction; fixture
setup never requires that route. Declaration cannot rewrite verify text,
grant authority, relax the gate, or amend historical DONE.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import intake  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.board_compaction import resolve_detail  # noqa: E402
from saipen_engine.operations import ticket_verify  # noqa: E402
from saipen_engine.state import parse_state  # noqa: E402
from test_hermetic_env import hermetic_env, isolate_host_session  # noqa: E402
from test_regression_gate import (  # noqa: E402
    RegressionGateFixture,
    S1,
    S2,
    V1,
    _evidence,
)
from test_ticket_verify_preimage import FIRST, SECOND, _build  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def _memory(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)).replace("\\", "/"): path.read_bytes()
        for path in (root / ".saipen").rglob("*")
        if path.is_file() and "locks" not in path.relative_to(root).parts
    }


def _row(root: Path) -> dict:
    parsed = parse_board((root / ".saipen/BOARD.md").read_text(encoding="utf-8"))
    if parsed["errors"]:
        raise AssertionError(parsed["errors"])
    return parsed["tickets"]["T-7"]


def _state(root: Path) -> dict:
    return parse_state((root / ".saipen/STATE.md").read_text(encoding="utf-8"))


def _declare(case, root: Path, value="required", *, dry_run=False):
    try:
        return ticket_verify(root, "T-7", "tester", None, dry_run=dry_run, regression=value)
    except TypeError as exc:
        case.fail(f"existing canonical ticket_verify cannot declare regression: {exc}")


class DeclarationTests(unittest.TestCase):
    def setUp(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="t1708-declaration-"))
        self.addCleanup(shutil.rmtree, base, True)
        self.root = _build(base, FIRST)

    def cli(self, *args, capability="full") -> dict:
        run = subprocess.run(
            [sys.executable, "-B", str(TOOLS / "saipen.py"), "--project-root",
             str(self.root), "--agent", "tester", "--json", *args],
            cwd=self.root, env=hermetic_env(SAIPEN_CAPABILITY=capability),
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        self.assertIn(run.returncode, (0, 1, 2), run.stderr)
        try:
            return json.loads(run.stdout)
        except json.JSONDecodeError:
            self.fail(f"native CLI returned no structured result: {run.stdout} {run.stderr}")

    def test_declaration_preserves_contract_sources_seat_phase_and_goal(self):
        receipt = intake.capture(self.root, "Keep the original falsifiable clause.", work="T-7")
        self.assertTrue(receipt["ok"], receipt)
        before_row, before_state = _row(self.root), _state(self.root)
        before_source = {
            key: value for key, value in _memory(self.root).items() if "/intake/" in key
        }
        result = _declare(self, self.root)
        self.assertTrue(result.ok, result.to_dict())
        after = _row(self.root)
        self.assertEqual(after["fields"].get("regression"), "required")
        fields = dict(after["fields"])
        fields.pop("regression")
        self.assertEqual(fields, before_row["fields"])
        self.assertEqual(after["section"], before_row["section"])
        for key, value in before_state.items():
            if key not in {"last_event", "updated"}:
                self.assertEqual(_state(self.root).get(key), value, key)
        self.assertEqual({key: _memory(self.root)[key] for key in before_source}, before_source)
        log = (self.root / ".saipen/LOG.md").read_text(encoding="utf-8")
        self.assertIn("regression", log)
        self.assertNotIn("superseded clause", log)

    def test_dry_run_writes_no_canonical_bytes(self):
        before = _memory(self.root)
        result = _declare(self, self.root, dry_run=True)
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(_memory(self.root), before)
        self.assertNotIn("regression", _row(self.root)["fields"])

    def test_invalid_values_cannot_remove_or_relax_the_gate(self):
        result = _declare(self, self.root)
        self.assertTrue(result.ok, result.to_dict())
        before = _memory(self.root)
        for value in ("", "none", "optional", "off", "required\nowner: other", True, 17):
            with self.subTest(value=value):
                result = _declare(self, self.root, value)
                self.assertFalse(result.ok, result.to_dict())
                self.assertEqual(result.code, "VALIDATION_FAILED")
                self.assertEqual(_memory(self.root), before)

    def test_done_history_is_refused_without_writes(self):
        board = self.root / ".saipen/BOARD.md"
        board.write_text("## DOING\n## TODO\n## DONE\n- [x] T-8 [P1] Historical Work "
                         "| verify: historical contract\n## BLOCKED\n" +
                         "- [ ] T-7 [P1] Existing Work | verify: " + FIRST + "\n",
                         encoding="utf-8")
        before = _memory(self.root)
        try:
            result = ticket_verify(self.root, "T-8", "tester", None, regression="required")
        except TypeError as exc:
            self.fail(f"canonical regression declaration is missing: {exc}")
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "TICKET_NOT_WORKABLE")
        self.assertEqual(_memory(self.root), before)

    def test_missing_ticket_is_refused_without_writes(self):
        before = _memory(self.root)
        try:
            result = ticket_verify(self.root, "T-404", "tester", None, regression="required")
        except TypeError as exc:
            self.fail(f"canonical regression declaration is missing: {exc}")
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "TICKET_NOT_FOUND")
        self.assertEqual(_memory(self.root), before)

    def test_existing_verify_updater_keeps_the_preimage_and_declared_gate(self):
        self.assertTrue(_declare(self, self.root).ok)
        result = ticket_verify(self.root, "T-7", "tester", SECOND)
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(_row(self.root)["fields"]["verify"], SECOND)
        self.assertEqual(_row(self.root)["fields"]["regression"], "required")
        self.assertIn(FIRST, (self.root / ".saipen/LOG.md").read_text(encoding="utf-8"))

    def test_oversized_original_contract_is_preserved_losslessly(self):
        long_clause = "UNCHANGED_LONG_CLAUSE " + "falsifiable proof " * 180
        result = ticket_verify(self.root, "T-7", "tester", long_clause)
        self.assertTrue(result.ok, result.to_dict())
        before = resolve_detail(self.root, _row(self.root)["fields"]["detail_ref"])
        self.assertTrue(_declare(self, self.root).ok)
        after = resolve_detail(self.root, _row(self.root)["fields"]["detail_ref"])
        self.assertIn(long_clause.strip().encode(), after["original_record"])
        self.assertEqual(before["original_record"].split(b" | verify: ")[1].split(b" | owner:")[0],
                         after["original_record"].split(b" | verify: ")[1].split(b" | owner:")[0])

    def test_native_cli_updates_only_the_declared_field(self):
        before = _row(self.root)["fields"]
        result = self.cli("ticket", "regression", "T-7", "required")
        self.assertTrue(result.get("ok"), result)
        after = dict(_row(self.root)["fields"])
        self.assertEqual(after.pop("regression"), "required")
        self.assertEqual(after, before)

    def test_native_cli_dry_run_is_write_free(self):
        before = _memory(self.root)
        result = self.cli("--dry-run", "ticket", "regression", "T-7", "required")
        self.assertTrue(result.get("ok"), result)
        self.assertEqual(_memory(self.root), before)

    def test_native_cli_read_only_cannot_declare_the_field(self):
        before = _memory(self.root)
        result = self.cli("ticket", "regression", "T-7", "required", capability="read-only")
        self.assertFalse(result.get("ok"), result)
        self.assertEqual(result.get("code"), "CAPABILITY_DENIED")
        self.assertEqual(_memory(self.root), before)

    def test_native_cli_refuses_invalid_value_and_extra_operands(self):
        before = _memory(self.root)
        for operands in (("off",), ("required", "extra")):
            with self.subTest(operands=operands):
                result = self.cli("ticket", "regression", "T-7", *operands)
                self.assertFalse(result.get("ok"), result)
                self.assertEqual(result.get("code"), "VALIDATION_FAILED")
                self.assertEqual(_memory(self.root), before)


class DeclaredGateTests(RegressionGateFixture):
    REGRESSION = ""

    def test_declaring_required_activates_the_current_cycle_gate(self):
        self.assertTrue(_declare(self, self.project).ok)
        before = self.canonical_digest()
        result = self.to_review()
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "INCOMPLETE_TICKET")
        self.assertIn("regression: required", result.message)
        self.assertEqual(self.canonical_digest(), before)
        self.record(_evidence("FAIL", V1, S1))
        self.record(_evidence("PASS", V1, S2))
        self.assertTrue(self.to_review().ok)

    def test_without_declaration_the_existing_unrequired_gate_is_unchanged(self):
        self.assertTrue(self.to_review().ok)


if __name__ == "__main__":
    unittest.main()
