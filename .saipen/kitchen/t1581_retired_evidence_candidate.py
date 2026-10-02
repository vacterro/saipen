import ast
import hashlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools"))
import audit_checks as A
from saipen_engine.retirement import bound_artifact_errors, load_ticket_retirement

out = root / ".saipen/evidence/T-1581-retired-evidence-candidate"
out.mkdir(parents=True, exist_ok=True)
subject = root / "tools/audit_checks.py"
oracle = root / "tools/test_t1581_phase_rename_knowledge.py"
before = subject.read_bytes()
text = before.decode("utf-8")

def replace_once(old, new):
    global text
    if old not in text:
        old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
    assert text.count(old) == 1, old[:60]
    text = text.replace(old, new)

replace_once(
    'from saipen_engine.knowledge import validate_knowledge, write_index',
    'from saipen_engine.knowledge import validate_knowledge, write_index\n'
    'from saipen_engine.retirement import bound_artifact_errors, load_ticket_retirement',
)
replace_once(
    '    changed = 0\n    for path in tree.rglob("*"):',
    '''    immutable_evidence = set()
    for record_path in (tree / ".saipen/archive/retired").glob("T-*.json"):
        record, errors, _exists = load_ticket_retirement(tree, record_path.stem)
        if record is not None and not errors:
            errors = bound_artifact_errors(tree, record_path.stem, record["evidence"])
        if errors or record is None:
            return "phase rename needs valid retirement evidence: " + "; ".join(errors)
        if record["evidence"]["kind"] == "artifact":
            immutable_evidence.add(tree / record["evidence"]["ref"])
    changed = 0
    for path in tree.rglob("*"):''',
)
replace_once(
    '''        if path.is_relative_to(milestone_root) or any(
            path.is_relative_to(authority_root) for authority_root in immutable_source_roots
        ):''',
    '''        if path in immutable_evidence or path.is_relative_to(milestone_root) or any(
            path.is_relative_to(authority_root) for authority_root in immutable_source_roots
        ):''',
)
after = text.encode("utf-8")
tests = r'''

class RetirementEvidenceRenameTests(PhaseRenameKnowledgeTests):
    """The same rename preserves byte-bound proofs and rejects corrupt input."""

    def setUp(self):
        super().setUp()
        import json
        from saipen_engine.retirement import (
            artifact_digest, board_record_digest, load_ticket_retirement,
        )

        self.evidence_rel = ".saipen/evidence/incident/proof.txt"
        self.evidence = self.source / self.evidence_rel
        self.evidence.parent.mkdir(parents=True)
        self.evidence.write_bytes(b"SCOUT finding\r\nscout source preserved\r\n")
        self.mutable = self.evidence.parent / "live.txt"
        self.mutable.write_bytes(b"SCOUT ordinary live content\n")
        row = "- [ ] T-1580 SCOUT misroute | verify: prove binding"
        record = {
            "schema_version": 2, "ticket": "T-1580", "section": "## BLOCKED",
            "board_record": row, "board_record_sha256": board_record_digest(row),
            "source_receipts": ["SRC-157", "SRC-158"],
            "reason": "MISROUTED_PROJECT_BINDING",
            "authority_receipt": "SRC-160", "authority_sha256": "a" * 64,
            "authority_grant": "T-1580 / SRC-157,SRC-158",
            "retired_by": "tester", "retired_at": "2026-10-01T00:00:00Z",
            "retirement_event": "E-101", "evidence_bound_event": "E-101",
            "discovery_event": None, "evidence_note": None,
            "restored_parent": None, "restored_parent_owner": None,
            "evidence": {"kind": "artifact", "ref": self.evidence_rel,
                         "sha256": artifact_digest(self.evidence.read_bytes())},
        }
        self.record = self.source / ".saipen/archive/retired/T-1580.json"
        self.record.parent.mkdir(parents=True)
        self.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(load_ticket_retirement(self.source, "T-1580")[1], [])

    def run_probe(self, before_validation=None):
        from saipen_engine.retirement import bound_artifact_errors, load_ticket_retirement

        def validate_proof(tree):
            if before_validation:
                before_validation(tree)
            record, errors, _exists = load_ticket_retirement(tree, "T-1580")
            if not errors:
                errors = bound_artifact_errors(tree, "T-1580", record["evidence"])
            if errors:
                raise AssertionError("; ".join(errors))

        return super().run_probe(validate_proof)

    def test_bound_artifact_and_retired_record_remain_exact_bytes(self):
        original_evidence = self.evidence.read_bytes()
        original_record = self.record.read_bytes()
        self.assertIsNone(self.run_probe())
        tree = self.destination / "phase-rename"
        self.assertEqual((tree / self.evidence_rel).read_bytes(), original_evidence)
        self.assertEqual((tree / ".saipen/archive/retired/T-1580.json").read_bytes(), original_record)
        self.assertEqual(self.evidence.read_bytes(), original_evidence)
        self.assertIn(b"SCOUTX", (tree / ".saipen/evidence/incident/live.txt").read_bytes())

    def test_corrupt_original_artifact_is_refused_before_rename(self):
        self.evidence.write_bytes(b"SCOUT corrupt evidence\n")
        with self.assertRaises(AssertionError):
            self.run_probe()

    def test_missing_original_artifact_is_refused_before_rename(self):
        self.evidence.unlink()
        with self.assertRaises(AssertionError):
            self.run_probe()
'''
# The probe's honest production refusal is an error string, not an exception.
# Accept that same refusal before and after the implementation delta.
tests = tests.replace('''        with self.assertRaises(AssertionError):
            self.run_probe()''', '''        try:
            error = self.run_probe()
        except AssertionError:
            return
        self.assertIsNotNone(error)
        self.assertIn("retirement evidence", error)''')
old_oracle = oracle.read_bytes()
anchor = b'\nif __name__ == "__main__":'
assert old_oracle.count(anchor) == 1
new_oracle = old_oracle.replace(anchor, tests.encode("utf-8") + anchor)
(out / "audit_checks.before.py").write_bytes(before)
(out / subject.name).write_bytes(after)
(out / oracle.name).write_bytes(new_oracle)
spec = importlib.util.spec_from_file_location("t1581_retirement_oracle", out / oracle.name)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original_function = A.phase_rename_probe
# Candidate adds imports; dependencies retain their real production meanings.
A.bound_artifact_errors, A.load_ticket_retirement = bound_artifact_errors, load_ticket_retirement
runs = {}
for variant, code in (("before", before), ("candidate", after)):
    node = next(n for n in ast.parse(code.decode()).body
                if isinstance(n, ast.FunctionDef) and n.name == "phase_rename_probe")
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(subject), "exec"), A.__dict__)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(module)
    )
    (out / f"oracle-{variant}.txt").write_text(stream.getvalue(), encoding="utf-8")
    runs[variant] = {"ran": result.testsRun, "failures": len(result.failures),
                     "errors": len(result.errors), "ok": result.wasSuccessful()}
A.phase_rename_probe = original_function
manifest = {"subject": "tools/audit_checks.py", "oracle": "tools/" + oracle.name,
            "before_sha256": hashlib.sha256(before).hexdigest(),
            "after_sha256": hashlib.sha256(after).hexdigest(),
            "oracle_before_sha256": hashlib.sha256(old_oracle).hexdigest(),
            "oracle_sha256": hashlib.sha256(new_oracle).hexdigest(), "runs": runs}
(out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps(manifest, indent=2))
sys.exit(0 if not runs["before"]["ok"] and runs["candidate"]["ok"] else 1)
