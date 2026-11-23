"""T-1563 ordinary-process attacks; no host authority is assumed by these tests.

The positive vulnerable control and repaired control use the identical carrier
and evaluate oracle. These controls prove refusal, not working host admission.
The original positive host tests must remain red until a separated host exists.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from saipen_engine import protocol_admission as PA  # noqa: E402
from saipen_engine import response_surface as RS  # noqa: E402
from t1563_transport_carrier import run  # noqa: E402
from test_protocol_admission import World, guard  # noqa: E402

SUBJECT = ROOT / "tests" / "fixtures" / "t1563-vulnerable"
HOOK = ROOT / "extensions" / "adapters" / "claude" / "saipen-guard.py"


class AuthorityMintingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.world = World(Path(self.temp.name))

    def test_identical_ordinary_import_carrier_admits_only_the_frozen_vulnerable_subject(self):
        identity = json.loads((SUBJECT / "subject.json").read_text(encoding="utf-8"))
        self.assertEqual(
            hashlib.sha256((SUBJECT / "protocol_admission.py").read_bytes()).hexdigest(),
            identity["sha256"],
        )
        common = dict(
            project=self.world.project, authority=self.world.authority, home=self.world.home
        )
        old = run(SUBJECT, **common)
        self.assertEqual((old["before"], old["result"], old["after"]),
                         ("BINDING", "ADMITTED", "ADMITTED"))
        # Use another session world so the old subject cannot contaminate the
        # repaired oracle. The program and all observed context fields match.
        with tempfile.TemporaryDirectory() as raw:
            clean = World(Path(raw))
            new = run(TOOLS / "saipen_engine", project=clean.project,
                      authority=clean.authority, home=clean.home)
        self.assertFalse(new["admitted"], new)
        self.assertEqual(new["error"], "AttributeError")

    def test_every_former_key_or_signing_entry_is_unavailable(self):
        for name in ("bootstrap_transport_key", "_read_transport_key", "_transport_key_path",
                     "_transport_mac", "_provenance"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(PA, name))

    def test_direct_ledger_writer_refuses_before_any_filesystem_write(self):
        with self.assertRaises(PermissionError):
            PA._write_record(self.world.project, "session-1", {"schema": 1}, "UserPromptSubmit")
        self.assertFalse((self.world.project / PA.LEDGER_DIR).exists())

    def test_direct_establish_refuses_and_writes_nothing(self):
        out = PA.establish(self.world.ctx())
        self.assertFalse(out["permitted"])
        self.assertEqual(out["code"], PA.CODE_TRANSPORT_REQUIRED)
        self.assertFalse((self.world.project / PA.LEDGER_DIR).exists())

    def test_direct_invalidate_refuses_and_preserves_bytes(self):
        path = PA._ledger_path(self.world.project, "session-1")
        path.parent.mkdir(parents=True)
        path.write_bytes(b"existing record")
        out = PA.invalidate(self.world.project, "session-1", "attack")
        self.assertFalse(out["ok"])
        self.assertEqual(path.read_bytes(), b"existing record")

    def test_readable_legacy_key_and_mac_cannot_unlock_any_event_session_or_verb(self):
        import hmac

        path = self.world.project / PA.LEDGER_DIR / ".transport.key"
        path.parent.mkdir(parents=True)
        key = b"attacker knows this project key"
        path.write_bytes(key)
        for verb in ("establish", "invalidate"):
            for event in ("UserPromptSubmit", "SessionStart", "PostToolUse"):
                domain = f"saipen-admission-transport:{verb}:{event}:session-1".encode()
                cap = f"hook:{event}:{hmac.new(key, domain, 'sha256').hexdigest()}"
                self.assertFalse(PA.verify_transport(self.world.project, verb, "session-1", cap)[0])
                self.assertFalse(PA.establish(self.world.ctx(), transport=cap)["permitted"])
                result = PA.invalidate(self.world.project, "session-1", "attack", cap)
                self.assertFalse(result["ok"])
        self.assertEqual(path.read_bytes(), key)

    def test_sha_seal_and_even_legacy_keyed_provenance_are_non_authoritative(self):
        import hmac

        for provenance in (None, "made up", "legacy-keyed"):
            record = {"schema": 1, "session": "session-1", "proofs": {}}
            record["seal"] = PA._seal(record)
            if provenance == "legacy-keyed":
                key = b"readable legacy key"
                record["provenance"] = hmac.new(
                    key, json.dumps(record, sort_keys=True).encode(), "sha256"
                ).hexdigest()
            elif provenance:
                record["provenance"] = provenance
            path = PA._ledger_path(self.world.project, "session-1")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record), encoding="utf-8")
            self.assertIsNone(PA._read_record(self.world.project, "session-1"))
            self.assertFalse(PA.evaluate(self.world.ctx())["permitted"])

    def test_ordinary_import_of_host_adapter_cannot_mint_authority_either(self):
        spec = importlib.util.spec_from_file_location("t1563_claude", HOOK)
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        self.assertFalse(hasattr(hook, "transport_capability"))
        out = guard(self.world.project, {"hook_event_name": "UserPromptSubmit",
                    "session_id": "session-1", "user_prompt": "ordinary request"},
                    self.world.home, authority=self.world.authority)
        self.assertEqual(out["decision"], "block", out)
        self.assertIn("HOST_AUTHORITY_UNAVAILABLE", out["reason"])
        self.assertFalse((self.world.project / PA.LEDGER_DIR).exists())

    def test_unavailable_claim_keeps_the_final_admission_layer_closed(self):
        ctx = self.world.ctx()
        self.assertTrue(PA.consulted(ctx))
        out = RS.gate_final_response(
            "Kontroll l\u00e4bitud.", admission=PA.evaluate(ctx),
            admission_consulted=PA.consulted(ctx), operational_turn=False,
            style_contract=None,
        )
        self.assertEqual(out["class"], "ADMISSION_BLOCKED", out)

    def test_real_init_still_binds_the_same_session_but_cannot_invent_host_admission(self):
        project = Path(self.temp.name) / "fresh-project"
        project.mkdir()
        launcher = ROOT / "bin" / ("saipen.cmd" if os.name == "nt" else "saipen")
        process = subprocess.run(
            [str(launcher), "init", "--project-root", str(project),
             "--agent", "test-agent", "--json"],
            capture_output=True, encoding="utf-8", check=False,
            env={k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")},
        )
        self.assertEqual(json.loads(process.stdout)["code"], "INIT_COMPLETED")
        self.assertTrue((project / ".saipen" / "STATE.md").exists())
        out = guard(project, {"hook_event_name": "PostToolUse", "session_id": "session-1",
                    "tool_name": "Bash", "tool_input": {"command": "saipen init"}},
                    self.world.home, authority=self.world.authority)
        self.assertIn("HOST_AUTHORITY_UNAVAILABLE", out["systemMessage"])
        self.assertFalse((project / PA.LEDGER_DIR).exists())

    def test_all_module_function_entries_are_bounded_and_classified(self):
        tree = ast.parse(Path(PA.__file__).read_text(encoding="utf-8"))
        authority_entries = {"establish", "invalidate", "_write_record"}
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            kind = "UNAVAILABLE" if node.name in authority_entries else "SAFE_READ_ONLY"
            self.assertIn(kind, ("HOST_ONLY_MECHANICAL", "SAFE_READ_ONLY", "UNAVAILABLE"))
            for call in ast.walk(node):
                if not isinstance(call, ast.Call):
                    continue
                # Direct-source coverage of ALL functions: no remaining secret
                # mint/read/sign operation may be hidden behind a new name.
                name = getattr(call.func, "attr", getattr(call.func, "id", ""))
                self.assertNotIn(name, {"token_bytes", "mkstemp", "fdopen", "open"})
                if name == "replace" and isinstance(call.func, ast.Attribute):
                    self.assertNotEqual(getattr(call.func.value, "id", ""), "os")
                if kind == "SAFE_READ_ONLY":
                    self.assertNotIn(name, {"write_bytes", "write_text", "mkdir", "unlink"})


if __name__ == "__main__":
    unittest.main()
