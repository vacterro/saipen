"""Lost canonical storage registry cannot be recreated by store declaration."""

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
