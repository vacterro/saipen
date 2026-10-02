"""Prepare and measure the missing local-only source-gate leg without root writes."""
from __future__ import annotations

import ast
import hashlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import intake

OUT = ROOT / ".saipen/evidence/T-1570-source-gate-candidate"
OUT.mkdir(parents=True, exist_ok=True)
source_path = ROOT / "tools/saipen_engine/intake.py"
test_path = ROOT / "tools/test_no_publish_source_scope.py"
before = source_path.read_text(encoding="utf-8")
anchor = '''        linked = item.get("linked_work")
        if not linked:
            # UNPROJECTED authoritative receipt: no Work owns its closure, so
'''
replacement = '''        if not publish and current_work:
            # The current Work's complete linkage/coverage was checked above.
            # Unowned or otherwise unrelated coverage cannot constrain a local
            # closure: no source bytes leave the repository. Integrity remains
            # global, including for these receipts.
            continue
        linked = item.get("linked_work")
        if not linked:
            # UNPROJECTED authoritative receipt: no Work owns its closure, so
'''
if before.count(anchor) != 1:
    raise RuntimeError("source gate anchor changed")
candidate = before.replace(anchor, replacement, 1).replace(
    '      and unprojected authoritative receipts -- stays global: a corrupt or\n'
    '      unowned source must freeze every publication.\n',
    '      and unprojected authoritative receipts -- stays global for publication.\n'
    '      Integrity remains global for local closure too.\n',
    1,
).replace(
    '    fail-closed, but another Work\'s scope cannot block it -- there is no\n'
    '    artifact for that Work\'s bytes to reach.\n',
    '    fail-closed, but unrelated scope or unprojected coverage cannot block it:\n'
    '    no artifact leaves the repository. A target-free call remains global.\n',
    1,
)
addition = '''
    def _unprojected(self):
        captured = intake.capture(
            self.root, "unprojected independent operator request", source_kind="user_instruction"
        )
        self.assertTrue(captured["ok"], captured)
        receipt = captured["receipt"]
        added = intake.add_requirement(self.root, receipt, rid="R001", text="still owed elsewhere")
        self.assertTrue(added["ok"], added)
        return receipt

    def _historical_scope(self):
        self._scope_file("historical.py")
        self._record_scope("T-003", ["historical.py"])
        self._record_scope("T-001", ["current.py"])

    def test_unprojected_unrelated_obligation_allows_local_execution_without_discharge(self):
        self._project()
        orphan = self._unprojected()
        before = {
            path: data for path, data in self._snapshot().items()
            if path.startswith(".saipen/intake/")
        }
        plan = self._plan()
        with patch.object(release, "_run_gate", return_value={"ok": True}):
            result = release.execute_release(self.root, plan)
        self.assertTrue(result["ok"], result)
        self._assert_closed(plan)
        after = {
            path: data for path, data in self._snapshot().items()
            if path.startswith(".saipen/intake/")
        }
        self.assertEqual(before, after)
        self.assertEqual(
            intake.coverage_summary(self.root, orphan)["unresolved"], [f"{orphan}:R001"]
        )

    def test_unprojected_obligation_still_blocks_publication(self):
        self._project()
        orphan = self._unprojected()
        self._historical_scope()
        before = self._snapshot()
        result = release._preflight_plan(self.root, replace(self._plan(), mode="full"))
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["stage"], "SOURCE_COVERAGE", result)
        self.assertEqual(result["source_gate"]["code"], "SOURCE_UNRESOLVED", result)
        self.assertEqual(result["source_gate"]["receipt"], orphan, result)
        self.assertEqual(before, self._snapshot())

    def test_unprojected_receipt_corruption_still_blocks_local_closure(self):
        self._project()
        orphan = self._unprojected()
        body = self.root / f".saipen/intake/active/{orphan}.md"
        body.write_bytes(body.read_bytes() + b" changed")
        gate = intake.release_gate(self.root, "T-001", publish=False)
        self.assertFalse(gate["ok"], gate)
        self.assertEqual(gate["code"], "SOURCE_CORRUPTION", gate)

    def test_local_current_receipt_missing_board_projection_still_blocks(self):
        self._project()
        extra = intake.capture(
            self.root, "extra current obligation", source_kind="user_instruction", work="T-001"
        )["receipt"]
        board = self.root / ".saipen/BOARD.md"
        board.write_text(
            board.read_text(encoding="utf-8").replace(f",{extra}", ""), encoding="utf-8"
        )
        gate = intake.release_gate(self.root, "T-001", publish=False)
        self.assertFalse(gate["ok"], gate)
        self.assertEqual(gate["code"], "SOURCE_LINKAGE_MISSING", gate)

    def test_unrelated_dangling_projection_does_not_block_local_closure(self):
        parked = self._project()
        board = self.root / ".saipen/BOARD.md"
        board.write_text(
            "\\n".join(line for line in board.read_text(encoding="utf-8").splitlines()
                      if not line.startswith("- [ ] T-003")) + "\\n", encoding="utf-8"
        )
        gate = intake.release_gate(self.root, "T-001", publish=False)
        self.assertTrue(gate["ok"], gate)
        self.assertFalse(intake.coverage_complete(self.root, parked))
        public = intake.release_gate(self.root, "T-001")
        self.assertFalse(public["ok"], public)
        self.assertEqual(public["code"], "SOURCE_WORK_ACTIVE", public)

    def test_target_free_local_gate_keeps_global_coverage(self):
        self._project()
        self._unprojected()
        gate = intake.release_gate(self.root, publish=False)
        self.assertFalse(gate["ok"], gate)
        self.assertEqual(gate["code"], "SOURCE_WORK_ACTIVE", gate)

'''
test_before = test_path.read_text(encoding="utf-8")
test_anchor = '\n\nif __name__ == "__main__":'
if test_before.count(test_anchor) != 1:
    raise RuntimeError("test insertion anchor changed")
oracle = test_before.replace(test_anchor, "\n" + addition + test_anchor, 1)
(OUT / "intake.py.draft").write_text(candidate, encoding="utf-8", newline="")
(OUT / "test_no_publish_source_scope.py.draft").write_text(oracle, encoding="utf-8", newline="")

node = next(node for node in ast.parse(candidate).body
            if isinstance(node, ast.FunctionDef) and node.name == "release_gate")
namespace = dict(intake.__dict__)
exec(compile(ast.Module(body=[node], type_ignores=[]), str(source_path), "exec"), namespace)
candidate_gate = namespace["release_gate"]
test_namespace = {"__name__": "t1570_candidate_oracle", "__file__": str(test_path)}
exec(compile(oracle, str(test_path), "exec"), test_namespace)
test_class = test_namespace["LocalSourceClosure"]
records = []
for label, gate in (("before", intake.release_gate), ("candidate", candidate_gate)):
    output = io.StringIO()
    with patch.object(intake, "release_gate", gate):
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(test_class)
        )
    record = {"variant": label, "ran": result.testsRun, "passed": result.wasSuccessful(),
              "failures": len(result.failures), "errors": len(result.errors),
              "oracle_sha256": hashlib.sha256(oracle.encode()).hexdigest(), "output": output.getvalue()}
    (OUT / f"oracle-{label}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    records.append({key: value for key, value in record.items() if key != "output"})
manifest = {"subject": {"path": source_path.relative_to(ROOT).as_posix(),
                         "before_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                         "after_sha256": hashlib.sha256(candidate.encode()).hexdigest()},
            "oracle": {"path": test_path.relative_to(ROOT).as_posix(),
                       "before_sha256": hashlib.sha256(test_path.read_bytes()).hexdigest(),
                       "after_sha256": hashlib.sha256(oracle.encode()).hexdigest()}, "controls": records}
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps(records))
sys.exit(0 if not records[0]["passed"] and records[1]["passed"] else 1)
