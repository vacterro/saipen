"""Storage class and root controls for the SAILEARN HOME loss."""

from __future__ import annotations

import os
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from saipen_engine import storage

ROOT = Path(__file__).resolve().parents[1]


class StoragePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="storage-policy-", dir=ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        # The family runs in an OS-temp copy. Give this fixture its own real
        # TEMP boundary so its explicit durable store is outside that boundary.
        os_temp = self.base / "os-temporary"
        os_temp.mkdir()
        self.enterContext(patch.dict(os.environ, {
            name: str(os_temp) for name in ("TEMP", "TMP", "TMPDIR")
        }))
        self.enterContext(patch.object(tempfile, "tempdir", str(os_temp)))
        self.config = self.base / "user-config"
        self.durable = self.base / "durable"
        self.cleanup_root = self.base / "auto-cleaned"
        self.policy = storage.empty_policy()
        self.policy["durable_roots"] = [str(self.durable.resolve())]
        self.policy["ephemeral_roots"] = [str(self.cleanup_root.resolve())]

    def test_os_temporary_root_cannot_hold_durable_state(self) -> None:
        path = Path(tempfile.gettempdir()) / "sailearn-home" / "models"
        result = storage.classify_path(path, "DURABLE", policy=self.policy)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "STORAGE_POLICY_VIOLATION")
        self.assertEqual(result["required_class"], "DURABLE")
        self.assertTrue(result["matched_ephemeral_root"])

    def test_custom_cleanup_root_catches_nested_and_relative_paths(self) -> None:
        nested = self.cleanup_root / "sailearn-home" / "registry" / "model.json"
        absolute = storage.classify_path(nested, "DURABLE", policy=self.policy)
        relative = storage.classify_path(
            "registry/model.json",
            "DURABLE",
            policy=self.policy,
            base=self.cleanup_root / "sailearn-home",
        )
        for result in (absolute, relative):
            self.assertEqual(result["code"], "STORAGE_POLICY_VIOLATION", result)
            self.assertEqual(result["matched_ephemeral_root"], str(self.cleanup_root.resolve()))

    @unittest.skipUnless(os.name == "nt", "Windows path spelling control")
    def test_windows_case_and_slash_variants_do_not_bypass_cleanup_root(self) -> None:
        variant = str(self.cleanup_root / "sailearn-home" / "adapter.safetensors")
        variant = variant.upper().replace("\\", "/")
        result = storage.classify_path(variant, "DURABLE", policy=self.policy)
        self.assertEqual(result["code"], "STORAGE_POLICY_VIOLATION", result)

    def test_scratch_and_cache_are_disposable_but_unknown_durable_is_not(self) -> None:
        scratch = self.cleanup_root / "training" / "checkpoint.tmp"
        self.assertEqual(
            storage.classify_path(scratch, "EPHEMERAL", policy=self.policy)["code"],
            "EPHEMERAL_ALLOWED",
        )
        self.assertEqual(
            storage.classify_path(scratch, "CACHE", policy=self.policy)["code"],
            "CACHE_ALLOWED",
        )
        unknown = self.base / "unclassified" / "registry.json"
        self.assertEqual(
            storage.classify_path(unknown, "DURABLE", policy=self.policy)["code"],
            "UNKNOWN_REQUIRES_EXPLICIT_DECISION",
        )

    def test_operator_durable_root_allows_store_without_touching_user_file(self) -> None:
        user_file = self.base / "user-owned.txt"
        user_file.write_text("leave me alone\n", encoding="utf-8")
        result = storage.configure_root("durable-set", self.durable, user_config_home=self.config)
        self.assertTrue(result["ok"], result)
        self.assertEqual(user_file.read_text(encoding="utf-8"), "leave me alone\n")
        loaded = storage.load_policy(self.config)
        self.assertEqual(loaded["durable_roots"], [str(self.durable.resolve())])
        self.assertEqual(
            storage.classify_path(self.durable / "models" / "adapter", "DURABLE", policy=loaded)[
                "code"
            ],
            "DURABLE_ALLOWED",
        )

    def test_config_itself_cannot_be_written_under_os_temp(self) -> None:
        with self.assertRaises(storage.StoragePolicyError) as caught:
            storage.configure_root(
                "durable-set",
                self.durable,
                user_config_home=Path(tempfile.gettempdir()) / "storage-policy-user-config",
            )
        self.assertEqual(caught.exception.code, "STORAGE_POLICY_VIOLATION")

    def test_registered_cleanup_root_cannot_be_a_trusted_durable_root(self) -> None:
        storage.configure_root("ephemeral-add", self.cleanup_root, user_config_home=self.config)
        with self.assertRaises(storage.StoragePolicyError) as caught:
            storage.configure_root(
                "durable-add",
                self.cleanup_root / "sailearn-home",
                user_config_home=self.config,
            )
        self.assertEqual(caught.exception.code, "STORAGE_POLICY_VIOLATION")
        self.assertEqual(storage.load_policy(self.config)["durable_roots"], [])

    def test_existing_symlink_into_cleanup_root_is_classified_by_target(self) -> None:
        self.cleanup_root.mkdir()
        alias = self.base / "alias"
        try:
            alias.symlink_to(self.cleanup_root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("host cannot create a directory symlink")
        result = storage.classify_path(alias / "sailearn-home", "DURABLE", policy=self.policy)
        self.assertEqual(result["code"], "STORAGE_POLICY_VIOLATION", result)

    def test_stale_writer_cannot_erase_a_new_ephemeral_root(self) -> None:
        storage.configure_root("durable-set", self.durable, user_config_home=self.config)
        original = storage.load_policy(self.config)
        stale = deepcopy(original)
        stale["scratch_root"] = str((self.base / "scratch").resolve())
        storage.configure_root("ephemeral-add", self.cleanup_root, user_config_home=self.config)
        with self.assertRaises(storage.StoragePolicyError) as failure:
            storage.save_policy(stale, user_config_home=self.config, expected_policy=original)
        self.assertEqual(failure.exception.code, "STORAGE_POLICY_CHANGED")
        self.assertIn(
            str(self.cleanup_root.resolve()), storage.load_policy(self.config)["ephemeral_roots"]
        )

    def test_existing_machine_policy_under_custom_cleanup_root_is_refused(self) -> None:
        home = self.cleanup_root / "user-config"
        home.mkdir(parents=True)
        selected = storage.empty_policy()
        selected["ephemeral_roots"] = [str(self.cleanup_root.resolve())]
        (home / storage.POLICY_FILE).write_text(json.dumps(selected), encoding="utf-8")
        with self.assertRaises(storage.StoragePolicyError) as failure:
            storage.load_policy(home)
        self.assertEqual(failure.exception.code, "STORAGE_POLICY_VIOLATION")


if __name__ == "__main__":
    unittest.main()
