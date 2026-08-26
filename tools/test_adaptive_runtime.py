"""Focused Wave-1 adaptive-runtime regressions."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.runtime import (  # noqa: E402
    CAPABILITY_NAMES,
    RuntimeInfoError,
    load_runtime_info,
    runtime_projection,
)
import saipen as cli  # noqa: E402


class AdaptiveRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-runtime-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.project = self.base / "project"
        memory = self.project / ".saipen"
        memory.mkdir(parents=True)
        (memory / "STATE.md").write_text(
            "---\n"
            "phase: BUILD\n"
            "task: T-001\n"
            'next_action: "PHASE BUILD T-001"\n'
            "blocker: none\n"
            "transition_from: SCOUT\n"
            "saipen_version: 7\n"
            "agent: persisted-seat\n"
            "mode: full\n"
            "updated: 2026-08-25T00:00:00Z\n"
            "execution_intent: normal\n"
            "---\n",
            encoding="utf-8",
        )
        (memory / "BOARD.md").write_text(
            "# Board\n## DOING\n- [/] T-001 fixture\n## TODO\n## DONE\n## BLOCKED\n",
            encoding="utf-8",
        )
        (memory / "LOG.md").write_text(
            "# Log\n\n- 25.08.26 00:00 [E-001] [T-001] [agent: persisted-seat] RUN: fixture\n",
            encoding="utf-8",
        )
        self.env = {
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "SAIPEN_USER_CONFIG_HOME": str(self.base / "user-config"),
        }
        self.env.pop("SAIPEN_RUNTIME_INFO", None)

    def _write_info(self, name: str, payload: object) -> Path:
        path = self.base / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def _tree(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.project).as_posix(): path.read_bytes()
            for path in self.project.rglob("*")
            if path.is_file()
        }

    def _cli(self, *args: str, env: dict[str, str] | None = None):
        process = subprocess.run(
            [
                sys.executable,
                str(TOOLS / "saipen.py"),
                "--project-root",
                str(self.project),
                *args,
                "--json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=self.env if env is None else env,
            timeout=30,
        )
        payload = json.loads(process.stdout) if process.stdout.strip() else {}
        return process, payload

    def test_absent_metadata_is_unknown_not_false(self):
        result = runtime_projection("opencode", env={})
        self.assertEqual("opencode", result["agent"])
        self.assertFalse(result["runtime_info_present"])
        self.assertIsNone(result["provider"])
        self.assertEqual(set(CAPABILITY_NAMES), set(result["capabilities"]))
        self.assertTrue(all(value is None for value in result["capabilities"].values()))

    def test_explicit_metadata_and_tristate_capabilities(self):
        path = self._write_info(
            "runtime.json",
            {
                "schema_version": 1,
                "harness": "opencode",
                "provider": "openai",
                "model": "model-x",
                "variant": "high",
                "capabilities": {"shell": True, "browser": False},
            },
        )
        result = runtime_projection("seat-7", path, env={})
        self.assertEqual("seat-7", result["agent"])
        self.assertEqual("opencode", result["harness"])
        self.assertEqual("openai", result["provider"])
        self.assertTrue(result["capabilities"]["shell"])
        self.assertFalse(result["capabilities"]["browser"])
        self.assertIsNone(result["capabilities"]["mcp"])

    def test_explicit_path_precedes_environment_path(self):
        explicit = self._write_info("explicit.json", {"model": "explicit"})
        environmental = self._write_info("environment.json", {"model": "environment"})
        result = load_runtime_info(explicit, env={"SAIPEN_RUNTIME_INFO": str(environmental)})
        self.assertEqual("explicit", result["model"])
        self.assertEqual("explicit_cli", result["source"])

    def test_runtime_document_cannot_override_agent_seat(self):
        path = self._write_info("bad-agent.json", {"agent": "forged", "model": "x"})
        with self.assertRaisesRegex(RuntimeInfoError, "must not define 'agent'"):
            runtime_projection("real-seat", path, env={})

    def test_malformed_and_non_regular_metadata_fail_controlled(self):
        malformed = self.base / "bad.json"
        malformed.write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeInfoError, "malformed JSON"):
            load_runtime_info(malformed, env={})
        directory = self.base / "directory.json"
        directory.mkdir()
        with self.assertRaisesRegex(RuntimeInfoError, "regular non-symlink"):
            load_runtime_info(directory, env={})

    def test_duplicate_fields_and_boolean_schema_are_rejected(self):
        duplicate = self.base / "duplicate.json"
        duplicate.write_text('{"model":"a","model":"b"}', encoding="utf-8")
        with self.assertRaisesRegex(RuntimeInfoError, "repeats JSON field 'model'"):
            load_runtime_info(duplicate, env={})
        boolean_schema = self._write_info("bool-schema.json", {"schema_version": True})
        with self.assertRaisesRegex(RuntimeInfoError, "schema_version must be 1"):
            load_runtime_info(boolean_schema, env={})

    def test_oversized_metadata_is_refused_before_parse(self):
        oversized = self.base / "oversized.json"
        oversized.write_bytes(b"{" + b" " * (64 * 1024) + b"}")
        with self.assertRaisesRegex(RuntimeInfoError, "cannot be read safely"):
            load_runtime_info(oversized, env={})

    def test_agent_flag_never_guesses_model_provider_or_capabilities(self):
        before = self._tree()
        process, payload = self._cli("--agent", "opencode", "runtime")
        self.assertEqual(0, process.returncode, process.stderr + process.stdout)
        self.assertEqual("RUNTIME", payload["code"])
        self.assertEqual("opencode", payload["agent"])
        self.assertIsNone(payload["provider"])
        self.assertIsNone(payload["model"])
        self.assertTrue(all(value is None for value in payload["capabilities"].values()))
        self.assertEqual(before, self._tree(), "read-only runtime command wrote project state")

    def test_bare_runtime_inherits_persisted_agent_without_handover(self):
        before = self._tree()
        process, payload = self._cli("runtime")
        self.assertEqual(0, process.returncode, process.stderr + process.stdout)
        self.assertEqual("persisted-seat", payload["agent"])
        self.assertEqual(before, self._tree())

    def test_cli_explicit_runtime_info_keeps_agent_separate(self):
        info = self._write_info(
            "cli.json",
            {"harness": "codex", "provider": "provider-y", "capabilities": {"patch": True}},
        )
        process, payload = self._cli(
            "--agent", "ownership-seat", "runtime", "--runtime-info", str(info)
        )
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertEqual("ownership-seat", payload["agent"])
        self.assertEqual("codex", payload["harness"])
        self.assertEqual("provider-y", payload["provider"])
        self.assertTrue(payload["capabilities"]["patch"])

    def test_cli_environment_metadata_and_explicit_precedence(self):
        environmental = self._write_info("env.json", {"model": "from-env"})
        explicit = self._write_info("cli-wins.json", {"model": "from-cli"})
        env = {**self.env, "SAIPEN_RUNTIME_INFO": str(environmental)}
        process, payload = self._cli("runtime", "--runtime-info", str(explicit), env=env)
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertEqual("from-cli", payload["model"])
        self.assertEqual("explicit_cli", payload["runtime_info_source"])

    def test_cli_environment_metadata_loads_without_explicit_flag(self):
        environmental = self._write_info("env-only.json", {"model": "from-env"})
        env = {**self.env, "SAIPEN_RUNTIME_INFO": str(environmental)}
        process, payload = self._cli("runtime", env=env)
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertEqual("from-env", payload["model"])
        self.assertEqual("environment", payload["runtime_info_source"])

    def test_malformed_cli_input_has_no_traceback_and_zero_writes(self):
        malformed = self.base / "malformed.json"
        malformed.write_text("[]", encoding="utf-8")
        before = self._tree()
        process, payload = self._cli("runtime", "--runtime-info", str(malformed))
        self.assertEqual(1, process.returncode)
        self.assertEqual("VALIDATION_FAILED", payload["code"])
        self.assertNotIn("Traceback", process.stderr + process.stdout)
        self.assertEqual(before, self._tree())

    def test_runtime_info_is_refused_on_non_runtime_command(self):
        info = self._write_info("unused.json", {"model": "x"})
        before = self._tree()
        process, payload = self._cli("status", "--runtime-info", str(info))
        self.assertEqual(2, process.returncode)
        self.assertEqual("VALIDATION_FAILED", payload["code"])
        self.assertEqual(before, self._tree())

    def test_runtime_is_classified_read_only_and_canonical_agent_cc_still_routes(self):
        self.assertFalse(cli._command_mutates("runtime", []))
        before = self._tree()
        process, payload = self._cli("--agent", "opencode", "cc", "--dry-run")
        self.assertEqual(0, process.returncode, process.stderr + process.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual("cc", payload["route"])
        self.assertEqual(before, self._tree())


if __name__ == "__main__":
    unittest.main(verbosity=2)
