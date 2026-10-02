"""Prove declaration cannot silently reinitialize lost canonical registry state."""
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
from saipen_engine import storage_artifacts as artifacts
import test_storage_artifacts as fixtures

OUT = ROOT / ".saipen/evidence/T-1579-storage-safety/lost-registry-candidate"
OUT.mkdir(parents=True, exist_ok=True)
subject = ROOT / "tools/saipen_engine/storage_artifacts.py"
before = subject.read_text(encoding="utf-8")
anchor = '''        current = load_stores(root)
        old = current["stores"].get(name)
'''
replacement = '''        current = load_stores(root)
        if (
            any(store["class"] == "DURABLE" for store in current["stores"].values())
            and not (root / ".saipen" / REGISTRY_FILE).is_file()
        ):
            raise StoragePolicyError(
                "STORAGE_REGISTRY_MISSING",
                "declared DURABLE stores have lost their canonical registry; "
                "inventory surviving objects and provenance before recovery",
            )
        old = current["stores"].get(name)
'''
if before.count(anchor) != 1:
    raise RuntimeError("declaration anchor changed")
candidate = before.replace(anchor, replacement, 1)
oracle = '''"""Lost canonical storage registry cannot be recreated by store declaration."""

import unittest
from unittest.mock import patch

import test_storage_artifacts as fixtures
from saipen_engine import storage_artifacts as artifacts
from saipen_engine.storage import StoragePolicyError


class LostRegistryDeclarationTests(unittest.TestCase):
    setUp = fixtures.StorageArtifactsTests.setUp
    tearDown = fixtures.StorageArtifactsTests.tearDown
    declare_durable = fixtures.StorageArtifactsTests.declare_durable

    def test_lost_registry_refuses_new_or_existing_store_without_any_write(self):
        self.declare_durable()
        registry = self.project / ".saipen" / artifacts.REGISTRY_FILE
        registry.unlink()
        declaration = self.project / ".saipen" / artifacts.STORES_FILE
        before = declaration.read_bytes()
        for name, path in (("SECOND_STORE", self.durable / "second"),
                           ("SAILEARN_HOME", self.durable)):
            with self.subTest(name=name):
                with self.assertRaises(StoragePolicyError) as failure:
                    artifacts.declare_store(
                        self.project, name, "DURABLE", path,
                        lifetime="PROJECT", owner="SAILEARN", recovery="PARTIAL",
                        policy=self.policy,
                    )
                self.assertEqual(failure.exception.code, "STORAGE_REGISTRY_MISSING")
                self.assertFalse(registry.exists())
                self.assertEqual(declaration.read_bytes(), before)

    def test_first_durable_declaration_still_creates_initial_registry(self):
        registry = self.project / ".saipen" / artifacts.REGISTRY_FILE
        self.assertFalse(registry.exists())
        self.declare_durable()
        self.assertTrue(registry.is_file())
        self.assertEqual(artifacts.load_registry(self.project)["artifacts"], {})

    def test_machine_policy_declaration_refuses_lost_registry_without_any_write(self):
        self.declare_durable()
        registry = self.project / ".saipen" / artifacts.REGISTRY_FILE
        registry.unlink()
        declaration = self.project / ".saipen" / artifacts.STORES_FILE
        before = declaration.read_bytes()
        with patch.object(artifacts, "load_policy", return_value=self.policy), patch.object(
            artifacts, "_machine_policy_lock", return_value=artifacts.nullcontext()
        ), self.assertRaises(StoragePolicyError) as failure:
            artifacts.declare_store(
                self.project, "SECOND_STORE", "DURABLE", self.durable / "second",
                lifetime="PROJECT", owner="SAILEARN", recovery="PARTIAL",
            )
        self.assertEqual(failure.exception.code, "STORAGE_REGISTRY_MISSING")
        self.assertFalse(registry.exists())
        self.assertEqual(declaration.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
'''
(OUT / "storage_artifacts.py.draft").write_text(candidate, encoding="utf-8", newline="")
(OUT / "test_storage_lost_registry.py.draft").write_text(oracle, encoding="utf-8", newline="")
node = next(node for node in ast.parse(candidate).body
            if isinstance(node, ast.FunctionDef) and node.name == "declare_store")
original_declare = artifacts.declare_store
exec(compile(ast.Module(body=[node], type_ignores=[]), str(subject), "exec"), artifacts.__dict__)
candidate_declare = artifacts.declare_store
artifacts.declare_store = original_declare
tests = {"__name__": "t1579_lost_registry_oracle"}
exec(compile(oracle, "test_storage_lost_registry.py", "exec"), tests)
controls = []
for label, declare in (("before", original_declare), ("candidate", candidate_declare)):
    output = io.StringIO()
    with patch.object(artifacts, "declare_store", declare):
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(tests["LostRegistryDeclarationTests"])
        )
    record = {"variant": label, "passed": result.wasSuccessful(), "ran": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors),
              "oracle_sha256": hashlib.sha256(oracle.encode()).hexdigest(), "output": output.getvalue()}
    (OUT / f"oracle-{label}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    controls.append({key: value for key, value in record.items() if key != "output"})
manifest = {"subject": {"path": subject.relative_to(ROOT).as_posix(),
                        "before_sha256": hashlib.sha256(subject.read_bytes()).hexdigest(),
                        "after_sha256": hashlib.sha256(candidate.encode()).hexdigest()},
            "oracle": {"path": "tools/test_storage_lost_registry.py",
                       "after_sha256": hashlib.sha256(oracle.encode()).hexdigest()}, "controls": controls}
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps(controls))
sys.exit(0 if not controls[0]["passed"] and controls[1]["passed"] else 1)
