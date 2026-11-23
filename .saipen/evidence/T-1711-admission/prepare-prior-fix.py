"""Prepare a bounded scratch correction while the live tree is under test."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "prior-fix-scratch.json"
if OUTPUT.exists():
    raise SystemExit("Existing evidence is immutable")
temp_root = Path(tempfile.gettempdir()).resolve()
scratch = Path(tempfile.mkdtemp(prefix="saipen-t1711-prior-fix-", dir=temp_root)).resolve()
if not scratch.is_relative_to(temp_root):
    raise SystemExit("scratch escaped its bounded temporary root")
project = scratch / "project"

def ignore(directory, names):
    skipped = {"__pycache__", ".pytest_cache", ".ruff_cache"}
    if Path(directory) == ROOT:
        skipped.update({".git", ".saipen"})
    return set(names) & skipped

shutil.copytree(ROOT, project, ignore=ignore)
module_path = project / "tools/saipen_engine/regression_execution.py"
tests_path = project / "tools/test_t1711_regression_execution.py"
module = module_path.read_text(encoding="utf-8")
changes = [
    ('material["verifier"] != value["after"]["verifier"]\n',
     'material["verifier"] != value["after"]["verifier"]\n'
     '            or _sha(material["contract_raw"]) != value.get("contract_sha256")\n'
     '            or _sha(_json(_manifest(material["prior"]))) != value["before"]["subject"]\n'),
    ('"contract_path": material["contract_path"],\n',
     '"contract_path": material["contract_path"],\n'
     '            "contract_sha256": _sha(material["contract_raw"]),\n'),
    ('for carrier in material["contract"]["before"].values():\n'
     '            if carrier is not None:\n'
     '                preconditions[carrier] = hash_bytes(_read(root, carrier))\n',
     'for target, carrier in material["contract"]["before"].items():\n'
     '            if carrier is not None:\n'
     '                preconditions[carrier] = hash_bytes(material["prior"][target])\n'),
]
for before, after in changes:
    if module.count(before) != 1:
        raise SystemExit("unexpected candidate module; preserve rather than guessing")
    module = module.replace(before, after)
module_path.write_text(module, encoding="utf-8", newline="\n")
tests = tests_path.read_text(encoding="utf-8")
anchor = '    def test_original_source_changed_by_a_verifier_cannot_be_admitted(self):\n'
added = '''    def test_preserved_prior_input_changes_invalidate_execution(self):
        self.assertTrue(self.execute().ok)
        carrier = self.project / ".saipen/evidence/before.py"
        original = carrier.read_bytes()
        carrier.write_text("def answer(): return 99\\n", encoding="utf-8")
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(self.canonical_digest(), before)
        carrier.write_bytes(original)
        self.assertTrue(self.to_review().ok)

    def test_changed_input_contract_cannot_spend_the_measured_pair(self):
        self.assertTrue(self.execute().ok)
        alternative = self.project / ".saipen/evidence/alternative.py"
        alternative.write_bytes((self.project / ".saipen/evidence/before.py").read_bytes())
        self.contract["before"]["subject.py"] = ".saipen/evidence/alternative.py"
        self.write_contract()
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(self.canonical_digest(), before)

    def test_prior_material_changed_before_commit_refuses_without_canonical_writes(self):
        self.assertIsNotNone(EXECUTION)
        original = EXECUTION._binding
        calls = []

        def move_after_fresh_binding(*args, **kwargs):
            binding = original(*args, **kwargs)
            calls.append(binding)
            if len(calls) == 2:
                (self.project / ".saipen/evidence/before.py").write_text(
                    "def answer(): return 99\\n", encoding="utf-8"
                )
            return binding

        with patch.object(EXECUTION, "_binding", move_after_fresh_binding):
            self.assert_refused_without_canonical_writes()

'''
if tests.count(anchor) != 1:
    raise SystemExit("unexpected oracle anchor")
tests = tests.replace(anchor, added + anchor)
tests_path.write_text(tests, encoding="utf-8", newline="\n")
paths = ["tools/saipen_engine/regression_execution.py", "tools/test_t1711_regression_execution.py"]
hashes = {relative: {"live_before_sha256": hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
                     "scratch_sha256": hashlib.sha256((project / relative).read_bytes()).hexdigest()}
          for relative in paths}
run = subprocess.run([sys.executable, "-B", "tools/test_t1711_regression_execution.py"],
                     cwd=project, capture_output=True, text=True,
                     encoding="utf-8", errors="replace", timeout=240)
record = {"scratch_root": str(scratch), "project": str(project), "owned_paths": hashes,
          "exit_code": run.returncode, "stdout": run.stdout, "stderr": run.stderr,
          "scope": "scratch only; live production is still frozen and unchanged"}
OUTPUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: record[key] for key in ("project", "owned_paths", "exit_code")}))
print(" | ".join(run.stderr.splitlines()[-4:]))
if run.returncode:
    raise SystemExit(run.returncode)
