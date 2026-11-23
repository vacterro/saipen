"""SAILEARN HOME loss controls and durable artifact publication tests."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from saipen_engine.storage import StoragePolicyError, configure_root, empty_policy
from saipen_engine.storage_artifacts import (
    declare_store,
    load_registry,
    promote_artifact,
    validate_storage,
)
from test_orchestration_repair import OrchestrationFixture

ROOT = Path(__file__).resolve().parent.parent


class StorageArtifactsTests(OrchestrationFixture):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="storage-artifacts-", dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        # The family runs in an OS-temp copy. Give this fixture its own real
        # TEMP boundary so its explicit durable store is outside that boundary.
        os_temp = self.base / "os-temporary"
        os_temp.mkdir()
        self.enterContext(patch.dict(os.environ, {
            name: str(os_temp) for name in ("TEMP", "TMP", "TMPDIR")
        }))
        self.enterContext(patch.object(tempfile, "tempdir", str(os_temp)))
        self.project = self.base / "sailearn"
        (self.project / ".saipen").mkdir(parents=True)
        self.scratch = self.base / "cleanup" / "sailearn-home"
        self.scratch.mkdir(parents=True)
        self.durable = self.base / "durable"
        self.durable.mkdir()
        self.policy = empty_policy()
        self.policy["durable_roots"] = [str(self.base)]
        self.policy["ephemeral_roots"] = [str(self.base / "cleanup")]

    def declare_durable(self) -> None:
        declare_store(
            self.project,
            "SAILEARN_HOME",
            "DURABLE",
            self.durable,
            lifetime="PROJECT",
            owner="SAILEARN",
            recovery="PARTIAL",
            policy=self.policy,
        )

    def test_sailearn_model_home_under_cleanup_root_is_blocked_before_commit(self) -> None:
        for name in ("adapter", "model_card", "registry_manifest"):
            with self.subTest(name=name):
                with self.assertRaises(StoragePolicyError) as failure:
                    declare_store(
                        self.project,
                        "SAILEARN_HOME",
                        "DURABLE",
                        self.scratch / name,
                        lifetime="PROJECT",
                        owner="SAILEARN",
                        recovery="PARTIAL",
                        policy=self.policy,
                    )
                self.assertEqual(failure.exception.code, "STORAGE_POLICY_VIOLATION")
        self.assertFalse((self.project / ".saipen" / "STORES.json").exists())

    def test_transient_checkpoint_promotes_before_registry_pointer(self) -> None:
        declare_store(
            self.project,
            "TRAINING_SCRATCH",
            "EPHEMERAL",
            self.scratch,
            lifetime="RUN",
            owner="SAILEARN",
            recovery="RECONSTRUCTABLE",
            policy=self.policy,
        )
        self.declare_durable()
        source = self.scratch / "checkpoint.bin"
        source.write_bytes(b"trained candidate")
        self.assertEqual(load_registry(self.project)["artifacts"], {})
        result = promote_artifact(
            self.project,
            "SAIBUD8",
            source,
            "SAILEARN_HOME",
            policy=self.policy,
        )
        record = result["record"]
        self.assertEqual(Path(record["path"]).read_bytes(), b"trained candidate")
        self.assertEqual(record["sha256"], hashlib.sha256(b"trained candidate").hexdigest())
        self.assertTrue(record["provenance"]["transient_source"])
        source.unlink()
        self.assertEqual(validate_storage(self.project, policy=self.policy), [])

    def test_source_disappears_mid_copy_without_registry_commit(self) -> None:
        self.declare_durable()
        source = self.scratch / "checkpoint.bin"
        source.write_bytes(b"candidate")
        import saipen_engine.storage_artifacts as artifacts

        def vanish(src: Path, *args: object) -> None:
            src.unlink()
            raise FileNotFoundError(src)

        with patch.object(artifacts, "_copy_object", side_effect=vanish), self.assertRaises(
            FileNotFoundError
        ):
            promote_artifact(self.project, "SAIBUD8", source, "SAILEARN_HOME", policy=self.policy)
        self.assertEqual(load_registry(self.project)["artifacts"], {})

    def test_legacy_ephemeral_registry_reference_is_detected_and_migrated(self) -> None:
        self.declare_durable()
        source = self.scratch / "adapter.bin"
        source.write_bytes(b"legacy adapter")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        registry_path = self.project / ".saipen" / "STORAGE_REGISTRY.json"
        registry_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "artifacts": {
                        "SAIBUD7": {
                            "store": "SAILEARN_HOME",
                            "path": str(source),
                            "sha256": digest,
                            "size": source.stat().st_size,
                            "recovery": "PARTIAL",
                            "provenance": {"source": "historical"},
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        findings = validate_storage(self.project, policy=self.policy)
        self.assertEqual(findings[0]["code"], "STORAGE_POLICY_VIOLATION")
        other = self.scratch / "new-model.bin"
        other.write_bytes(b"new model")
        with self.assertRaises(StoragePolicyError) as blocked:
            promote_artifact(self.project, "SAIBUD8", other, "SAILEARN_HOME", policy=self.policy)
        self.assertEqual(blocked.exception.code, "STORAGE_REGISTRY_INVALID")
        result = promote_artifact(
            self.project,
            "SAIBUD7",
            source,
            "SAILEARN_HOME",
            migration=True,
            policy=self.policy,
        )
        self.assertEqual(result["record"]["provenance"]["migrated_from"], str(source))
        self.assertTrue(source.exists())
        self.assertEqual(validate_storage(self.project, policy=self.policy), [])

    def test_missing_durable_artifact_reports_recovery_class(self) -> None:
        self.declare_durable()
        source = self.scratch / "adapter.bin"
        source.write_bytes(b"lost model")
        result = promote_artifact(
            self.project, "SAIBUD7", source, "SAILEARN_HOME", policy=self.policy
        )
        Path(result["record"]["path"]).unlink()
        findings = validate_storage(self.project, policy=self.policy)
        self.assertEqual(findings[0]["code"], "STORAGE_ARTIFACT_MISSING")
        self.assertEqual(findings[0]["recovery"], "PARTIAL")
        self.assertEqual(findings[0]["artifact"], "SAIBUD7")

    def test_registry_publication_failure_preserves_previous_pointer(self) -> None:
        self.declare_durable()
        first = self.scratch / "first.bin"
        first.write_bytes(b"accepted")
        promote_artifact(self.project, "SAIBUD8", first, "SAILEARN_HOME", policy=self.policy)
        before = load_registry(self.project)
        candidate = self.scratch / "candidate.bin"
        candidate.write_bytes(b"candidate")
        import saipen_engine.storage_artifacts as artifacts

        with patch.object(
            artifacts, "_write_json", side_effect=OSError("simulated crash")
        ), self.assertRaises(OSError):
            promote_artifact(
                self.project, "SAIBUD9", candidate, "SAILEARN_HOME", policy=self.policy
            )
        self.assertEqual(load_registry(self.project), before)
        self.assertEqual(validate_storage(self.project, policy=self.policy), [])

    def test_reconstructable_record_requires_and_reports_rebuild_command(self) -> None:
        declare_store(
            self.project,
            "SAILEARN_HOME",
            "DURABLE",
            self.durable,
            lifetime="PROJECT",
            owner="SAILEARN",
            recovery="RECONSTRUCTABLE",
            policy=self.policy,
        )
        source = self.scratch / "model-card.json"
        source.write_text("{}", encoding="utf-8")
        with self.assertRaises(StoragePolicyError) as failure:
            promote_artifact(
                self.project, "ModelCard8", source, "SAILEARN_HOME", policy=self.policy
            )
        self.assertEqual(failure.exception.code, "STORAGE_RECOVERY_UNPROVEN")
        result = promote_artifact(
            self.project,
            "ModelCard8",
            source,
            "SAILEARN_HOME",
            provenance={"rebuild_command": "python build_card.py --model SAIBUD8"},
            policy=self.policy,
        )
        Path(result["record"]["path"]).unlink()
        findings = validate_storage(self.project, policy=self.policy)
        self.assertEqual(findings[0]["rebuild_command"], "python build_card.py --model SAIBUD8")

    def test_missing_registry_is_not_treated_as_fresh_installation(self) -> None:
        self.declare_durable()
        registry = self.project / ".saipen" / "STORAGE_REGISTRY.json"
        self.assertTrue(registry.is_file())
        registry.unlink()
        findings = validate_storage(self.project, policy=self.policy)
        self.assertEqual(findings[0]["code"], "STORAGE_REGISTRY_MISSING")
        self.assertEqual(findings[0]["recovery"], "PARTIAL")

    def test_transient_project_may_declare_only_scratch_under_cleanup_root(self) -> None:
        transient = self.base / "cleanup" / "test-project"
        (transient / ".saipen").mkdir(parents=True)
        declare_store(
            transient,
            "TEST_SCRATCH",
            "EPHEMERAL",
            transient / "scratch",
            lifetime="RUN",
            owner="test-runner",
            recovery="RECONSTRUCTABLE",
            policy=self.policy,
        )
        self.assertEqual(validate_storage(transient, policy=self.policy), [])

    def test_policy_change_during_copy_prevents_canonical_publication(self) -> None:
        import saipen_engine.storage_artifacts as artifacts

        config = self.base / "machine-config"
        source = self.scratch / "candidate.bin"
        source.write_bytes(b"candidate")
        real_copy = artifacts._copy_object

        def copy_and_change(*args: object) -> None:
            real_copy(*args)
            configure_root("ephemeral-add", self.base / "another-cleanup")

        with patch.dict(os.environ, {"SAIPEN_USER_CONFIG_HOME": str(config)}):
            configure_root("durable-set", self.base)
            configure_root("ephemeral-add", self.base / "cleanup")
            declare_store(
                self.project,
                "SAILEARN_HOME",
                "DURABLE",
                self.durable,
                lifetime="PROJECT",
                owner="SAILEARN",
                recovery="PARTIAL",
            )
            with patch.object(
                artifacts, "_copy_object", side_effect=copy_and_change
            ), self.assertRaises(StoragePolicyError) as failure:
                promote_artifact(self.project, "SAIBUD8", source, "SAILEARN_HOME")
            self.assertEqual(failure.exception.code, "STORAGE_POLICY_CHANGED")
            self.assertEqual(load_registry(self.project)["artifacts"], {})

    def test_adapter_directory_promotes_as_verified_tree(self) -> None:
        self.declare_durable()
        adapter = self.scratch / "adapter"
        adapter.mkdir()
        (adapter / "adapter_model.safetensors").write_bytes(b"weights")
        (adapter / "adapter_config.json").write_text('{"r": 8}', encoding="utf-8")
        empty = adapter / "empty-metadata"
        empty.mkdir()
        result = promote_artifact(
            self.project, "SAIBUD8_Adapter", adapter, "SAILEARN_HOME", policy=self.policy
        )
        durable = Path(result["record"]["path"])
        self.assertEqual(result["record"]["kind"], "directory")
        self.assertEqual((durable / "adapter_model.safetensors").read_bytes(), b"weights")
        self.assertTrue((durable / "empty-metadata").is_dir())
        (adapter / "adapter_model.safetensors").unlink()
        (adapter / "adapter_config.json").unlink()
        empty.rmdir()
        adapter.rmdir()
        self.assertEqual(validate_storage(self.project, policy=self.policy), [])

    def test_modified_promoted_adapter_tree_is_detected(self) -> None:
        self.declare_durable()
        adapter = self.scratch / "adapter"
        adapter.mkdir()
        (adapter / "adapter_model.safetensors").write_bytes(b"weights")
        result = promote_artifact(
            self.project, "SAIBUD8_Adapter", adapter, "SAILEARN_HOME", policy=self.policy
        )
        (Path(result["record"]["path"]) / "adapter_model.safetensors").write_bytes(b"tampered")
        findings = validate_storage(self.project, policy=self.policy)
        self.assertEqual(findings[0]["code"], "STORAGE_HASH_MISMATCH")

    def test_live_checker_and_finish_gate_refuse_lost_canonical_artifact(self) -> None:
        from saipen_engine.fast_check import validate_project
        from saipen_engine.operations import finish_ticket

        fixture = self.make_project(active=True)
        shutil.copytree(fixture / ".saipen", self.project / ".saipen", dirs_exist_ok=True)
        with patch.dict(os.environ, {"SAIPEN_USER_CONFIG_HOME": str(self.base / "config")}):
            configure_root("durable-set", self.base)
            configure_root("ephemeral-add", self.base / "cleanup")
            self.declare_durable()
            source = self.scratch / "adapter.bin"
            source.write_bytes(b"accepted adapter")
            result = promote_artifact(self.project, "SAIBUD8", source, "SAILEARN_HOME")
            self.to_ship(self.project, "T-7")
            self.assertEqual(validate_project(self.project), [])
            self.assertTrue(finish_ticket(self.project, "T-7", "tester", dry_run=True).ok)
            paths = [self.project / ".saipen" / name for name in
                     ("STATE.md", "BOARD.md", "LOG.md", "STORAGE_REGISTRY.json")]
            before = [path.read_bytes() for path in paths]
            Path(result["record"]["path"]).unlink()
            errors = validate_project(self.project)
            self.assertTrue(any("STORAGE_ARTIFACT_MISSING" in error for error in errors), errors)
            refused = finish_ticket(self.project, "T-7", "tester")
            self.assertFalse(refused.ok, refused.to_dict())
            self.assertEqual(refused.code, "STORAGE_ARTIFACT_MISSING")
            self.assertEqual([path.read_bytes() for path in paths], before)

    def test_public_cli_blocks_temp_home_and_preserves_promoted_adapter_after_loss(self) -> None:
        fixture = self.make_project(active=True)
        shutil.copytree(fixture / ".saipen", self.project / ".saipen", dirs_exist_ok=True)
        environment = {
            **os.environ,
            "SAIPEN_USER_CONFIG_HOME": str(self.base / "config"),
            "SAIPEN_CAPABILITY": "full",
            "PYTHONIOENCODING": "utf-8",
        }

        def cli(*args: str, expected: int = 0) -> dict:
            run = subprocess.run(
                [sys.executable, "-B", str(ROOT / "tools" / "saipen.py"),
                 "--project-root", str(self.project), "--json", "storage", *args],
                env=environment, capture_output=True, text=True, encoding="utf-8", timeout=30,
            )
            self.assertEqual(run.returncode, expected, run.stdout + run.stderr)
            return json.loads(run.stdout)

        cli("durable", "add", str(self.base))
        cli("ephemeral", "add", str(self.base / "cleanup"))
        refusal = cli("store", "declare", "SAILEARN_HOME", "DURABLE", str(self.scratch),
                      "PROJECT", "SAILEARN", "PARTIAL", expected=1)
        self.assertEqual(refusal["code"], "STORAGE_POLICY_VIOLATION")
        cli("store", "declare", "SAILEARN_HOME", "DURABLE", str(self.durable),
            "PROJECT", "SAILEARN", "PARTIAL")
        source = self.scratch / "adapter.bin"
        source.write_bytes(b"accepted adapter")
        record = cli("promote", "SAIBUD8", str(source), "SAILEARN_HOME")["record"]
        source.unlink()
        self.assertEqual(cli("verify")["code"], "STORAGE_VALID")
        self.assertEqual(Path(record["path"]).read_bytes(), b"accepted adapter")


if __name__ == "__main__":
    unittest.main()
