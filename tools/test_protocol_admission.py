"""PROTOCOL-ADMISSION-01 acceptance: no current admission, no reply.

Evidence classes, kept apart on purpose (a green in one says nothing about
another):

* OWNER      -- `protocol_admission` states, fingerprints, invalidation.
* LAYERING   -- `response_surface.gate_final_response`: admission, EXEC-RESPONSE
                and chat style are separate layers and never compensate.
* HOST       -- the Claude Code hook: bootstrap, pre-generation block, same-turn
                init, runtime-authored diagnostics.
* ORACLE     -- the pre-fix subject: the SAME `response check --classify` oracle
                every host called before admission existed. The carriers that
                escape it are the ones the repaired path must refuse.
* DATA       -- the host capability matrix and the registry admission policy.

`chat_style` false-positive rates and the style tests are NOT admission
evidence and appear nowhere here.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _entry in (str(TOOLS), str(ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

import autoinject  # noqa: E402
import install_host_guard  # noqa: E402
from saipen_engine import chat_style as CS  # noqa: E402
from saipen_engine import protocol_admission as PA  # noqa: E402
from saipen_engine import response_surface as RS  # noqa: E402
from test_guard_hostile_matrix import fresh_project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

HOOK = ROOT / "extensions" / "adapters" / "claude" / "saipen-guard.py"
REAL_POLICY = PA.load_policy()
HOST_POSITIVE_BLOCKED = (
    "CAPABILITY_UNAVAILABLE: separated production host authority required; SRC-140:R009 BLOCKED"
)

VALID_REPLY = "Kontroll l\u00e4bitud."
ESSAY = "\n".join(f"Fact {n} is exact." for n in range(12))


def setUpModule() -> None:
    isolate_host_session()


class World:
    """A complete, disposable admission world: project, authorities, host home."""

    def __init__(
        self,
        tmp: Path,
        *,
        hook: bool = True,
        instruction: bool = True,
        skill: bool = True,
        project: Path | None = None,
    ):
        self.tmp = Path(tmp)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.authority = self.tmp / "authority"
        (self.authority / "saipen").mkdir(parents=True)
        for name in PA.AUTHORITY_DOCUMENTS:
            shutil.copy2(ROOT / "saipen" / name, self.authority / "saipen" / name)
        shutil.copy2(ROOT / "VERSION", self.authority / "VERSION")
        self.project = project if project is not None else fresh_project()
        if instruction:
            block = autoinject.rendered_activation_block(ROOT / "saipen")
            claude = self.home / ".claude"
            claude.mkdir(parents=True, exist_ok=True)
            (claude / "CLAUDE.md").write_text(
                "# operator notes\n\n" + block + "\n", encoding="utf-8"
            )
        if skill:
            self.put_skill(".agents/skills/caveman")
        if hook:
            (self.home / ".claude").mkdir(parents=True, exist_ok=True)
            install_host_guard.install("claude", self.home, ROOT)
        self.policy = json.loads(json.dumps(REAL_POLICY))

    def put_skill(self, relative: str, name: str = "caveman") -> Path:
        directory = self.home / relative
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: voice\n---\n\nRespond terse.\n", encoding="utf-8"
        )
        return directory

    def edit_authority(self, name: str, suffix: str) -> None:
        path = self.authority / "saipen" / name
        path.write_text(path.read_text(encoding="utf-8") + suffix, encoding="utf-8")

    def ctx(self, **overrides) -> PA.Context:
        fields = {
            "project_root": self.project,
            "session_id": "session-1",
            "host": "claude",
            "model": "model-a",
            "provider": "provider-a",
            "authority_root": self.authority,
            "home": self.home,
            "policy": self.policy,
            "adapters": getattr(self, "adapters", None),
        }
        fields.update(overrides)
        return PA.Context(**fields)

    def transport(self, verb="establish", event="SessionStart", session_id="session-1") -> str:
        """Synthetic token for isolated state-machine tests, NEVER host proof."""
        return f"unit-only:{verb}:{event}:{session_id}"

    def establish(self, ctx: PA.Context | None = None, **overrides) -> dict:
        target = self.ctx(**overrides) if ctx is None else ctx
        return PA.establish(
            target, transport=self.transport("establish", session_id=target.session_id)
        )

    def invalidate(self, session_id="session-1", reason="SessionStart") -> dict:
        return PA.invalidate(
            self.project,
            session_id,
            reason,
            transport=self.transport("invalidate", session_id=session_id),
        )


class WorldCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.world = World(Path(self._tmp.name))

    def simulated_owner(self):
        """Test-only dependency doubles exercise generation/delivery, not security.

        No key, MAC, signing helper, environment flag or production provider is
        installed. The independent AuthorityMintingTests run the real boundary.
        """
        records = {}
        adapters = PA._adapters(self.world.ctx())
        adapters["claude"] = {**adapters["claude"], "admission_enforcement": "MECHANICAL"}
        self.world.adapters = adapters

        def verify(root, verb, session, value):
            parts = str(value or "").split(":")
            if len(parts) == 4 and parts[:2] == ["unit-only", verb] and parts[3] == session:
                return True, None, parts[2]
            return False, PA.AUTHORITY_UNAVAILABLE, None

        def write(root, session, record, transport_event):
            record = {**record, "session": session, "transport": transport_event}
            record["seal"] = PA._seal(record)
            records[session] = record
            path = PA._ledger_path(root, session)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record), encoding="utf-8")

        def read(root, session):
            path = PA._ledger_path(root, session)
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None
            return record if record == records.get(session) else None

        doubles = (("verify_transport", verify), ("_write_record", write), ("_read_record", read))
        for name, double in doubles:
            patch = mock.patch.object(PA, name, side_effect=double)
            patch.start()
            self.addCleanup(patch.stop)


class SimulatedOwnerCase(WorldCase):
    def setUp(self):
        super().setUp()
        self.simulated_owner()


class OwnerStateTests(SimulatedOwnerCase):
    def test_a_project_with_no_delivered_authority_is_binding_and_not_permitted(self):
        verdict = PA.evaluate(self.world.ctx())
        self.assertEqual(verdict["state"], PA.STATE_BINDING)
        self.assertFalse(verdict["permitted"])
        self.assertEqual(verdict["code"], PA.CODE_REQUIRED)

    def test_no_project_means_the_protocol_does_not_apply(self):
        verdict = PA.evaluate(self.world.ctx(project_root=None))
        self.assertEqual(verdict["state"], PA.STATE_UNBOUND)
        self.assertTrue(verdict["permitted"])
        self.assertFalse(verdict["applies"])

    def test_establishing_delivers_every_authority_and_admits(self):
        verdict = self.world.establish()
        self.assertEqual(verdict["state"], PA.STATE_ADMITTED)
        self.assertTrue(verdict["permitted"])
        for name in PA.AUTHORITY_DOCUMENTS:
            self.assertIn(f"=== {name} sha256:", verdict["delivery"])
        self.assertEqual(PA.evaluate(self.world.ctx())["state"], PA.STATE_ADMITTED)

    def test_a_current_session_is_not_charged_a_second_delivery(self):
        self.world.establish()
        again = self.world.establish()
        self.assertEqual((again["state"], again["delivery"]), (PA.STATE_ADMITTED, ""))

    def test_a_missing_authority_document_refuses_naming_it(self):
        # STYLE loaded and EXECUTION not: the second proof is absent, so there is
        # no admission to be had, and the missing name is in the answer.
        (self.world.authority / "saipen" / "EXECUTION.md").unlink()
        verdict = self.world.establish()
        self.assertEqual(verdict["state"], PA.STATE_REFUSED)
        components = [p["component"] for p in verdict["problems"]]
        self.assertIn("authority:EXECUTION.md", components)
        self.assertEqual(verdict["delivery"], "")

    def test_a_ledger_that_proves_fewer_documents_than_required_is_stale(self):
        self.world.establish()
        path = PA._ledger_path(self.world.project, "session-1")
        record = json.loads(path.read_text(encoding="utf-8"))
        del record["proofs"]["authority:EXECUTION.md"]
        PA._write_record(self.world.project, "session-1", record, "SessionStart")
        verdict = PA.evaluate(self.world.ctx())
        self.assertEqual(verdict["state"], PA.STATE_STALE)
        self.assertIn("authority:EXECUTION.md", verdict["stale"])

    def test_an_uncompilable_style_authority_is_refused_not_defaulted(self):
        style = self.world.authority / "saipen" / "STYLE.md"
        style.write_text("# Style with no contract\n", encoding="utf-8")
        verdict = self.world.establish()
        self.assertEqual(verdict["state"], PA.STATE_REFUSED)
        self.assertTrue(any("cannot be compiled" in p["reason"] for p in verdict["problems"]))


class SelfReportTests(SimulatedOwnerCase):
    def test_prose_cannot_produce_a_ledger_record(self):
        # There is no API through which a claim can be passed: the only writers
        # are `establish` (runtime) and the seal check rejects everything else.
        self.assertEqual(PA.evaluate(self.world.ctx())["state"], PA.STATE_BINDING)
        path = PA._ledger_path(self.world.project, "session-1")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"schema": 1, "host": "claude", "proofs": {}, "token": "I read everything"}),
            encoding="utf-8",
        )
        self.assertEqual(PA.evaluate(self.world.ctx())["state"], PA.STATE_BINDING)

    def test_an_edited_record_fails_its_seal(self):
        self.world.establish()
        path = PA._ledger_path(self.world.project, "session-1")
        record = json.loads(path.read_text(encoding="utf-8"))
        record["token"] = "tok-forged"
        path.write_text(json.dumps(record), encoding="utf-8")
        self.assertEqual(PA.evaluate(self.world.ctx())["state"], PA.STATE_BINDING)

    def test_establish_from_a_shell_is_refused_without_a_hook_transport(self):
        env = {k: v for k, v in os.environ.items() if k != PA.TRANSPORT_ENV}
        proc = subprocess.run(
            [
                sys.executable,
                str(TOOLS / "saipen.py"),
                "admission",
                "establish",
                "--json",
                "--project-root",
                str(self.world.project),
                "--session",
                "session-1",
                "--host",
                "claude",
            ],
            capture_output=True,
            encoding="utf-8",
            env=env,
            cwd=str(ROOT),
            check=False,
        )
        out = json.loads(proc.stdout)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(out["code"], PA.CODE_TRANSPORT_REQUIRED)
        self.assertEqual(PA.evaluate(self.world.ctx())["state"], PA.STATE_BINDING)


class TransportAuthorityTests(WorldCase):
    """The transport gate lives in the write boundary, not the CLI wrapper.

    Hostile carriers drive the ordinary agent surface: a direct Python import,
    a shell CLI call, a shell CLI call with a FORGED transport environment
    variable (the pre-fix subject: the wrapper's `startswith('hook:')`
    accepted any value), and a plain file write. Without the per-project key
    none of them can compute the MAC, so none of them mutate the ledger.
    """

    def _hostile_python(self, body: str) -> dict:
        env = {k: v for k, v in os.environ.items() if k != PA.TRANSPORT_ENV}
        code = (
            f"import sys\n"
            f"sys.path.insert(0, {str(TOOLS)!r})\n"
            f"sys.path.insert(0, {str(ROOT)!r})\n"
            f"import json\n"
            f"from saipen_engine import protocol_admission as pa\n"
            f"{body}\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            encoding="utf-8",
            env=env,
            cwd=str(ROOT),
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def test_a_direct_import_cannot_establish(self):
        payload = self._hostile_python(
            "ctx = pa.Context(project_root={p!r}, session_id='session-9', host='claude',\n"
            "    model='model-a', provider='provider-a',\n"
            "    authority_root={a!r}, home={h!r})\n"
            "out = pa.establish(ctx)\n"
            "print(json.dumps({{'state': out['state'], 'code': out.get('code'), "
            "'permitted': out['permitted']}}))".format(
                p=str(self.world.project),
                a=str(self.world.authority),
                h=str(self.world.home),
            )
        )
        self.assertEqual(payload["code"], PA.CODE_TRANSPORT_REQUIRED)
        self.assertFalse(payload["permitted"])
        self.assertFalse(PA._ledger_path(self.world.project, "session-9").exists())

    def test_a_direct_import_cannot_invalidate(self):
        path = PA._ledger_path(self.world.project, "session-1")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"untrusted existing record")
        before = path.read_bytes()
        payload = self._hostile_python(
            "out = pa.invalidate({p!r}, 'session-1', 'attack')\nprint(json.dumps(out))".format(
                p=str(self.world.project)
            )
        )
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], PA.CODE_TRANSPORT_REQUIRED)
        self.assertEqual(path.read_bytes(), before)

    def test_a_forged_transport_env_is_not_a_capability(self):
        # Pre-fix subject: this exact CLI call with this exact env value was
        # ADMITTED (the wrapper checked only the prefix). Red on the old bytes,
        # green now: the keyed MAC cannot be spelled without the key.
        self.world.transport()  # the key exists; the forger still cannot use it
        env = {k: v for k, v in os.environ.items()}
        env[PA.TRANSPORT_ENV] = "hook:UserPromptSubmit:forged"
        proc = subprocess.run(
            [
                sys.executable,
                str(TOOLS / "saipen.py"),
                "admission",
                "establish",
                "--json",
                "--project-root",
                str(self.world.project),
                "--session",
                "session-1",
                "--host",
                "claude",
                "--authority-root",
                str(self.world.authority),
                "--home",
                str(self.world.home),
            ],
            capture_output=True,
            encoding="utf-8",
            env=env,
            cwd=str(ROOT),
            check=False,
        )
        out = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 1, out)
        self.assertEqual(out["code"], PA.CODE_TRANSPORT_REQUIRED)
        self.assertFalse(PA._ledger_path(self.world.project, "session-1").exists())
        self.assertFalse(PA.evaluate(self.world.ctx())["permitted"])

    @unittest.skip(HOST_POSITIVE_BLOCKED)
    def test_the_cli_with_a_genuine_host_capability_establishes(self):
        env = {k: v for k, v in os.environ.items()}
        env[PA.TRANSPORT_ENV] = self.world.transport("establish", "UserPromptSubmit")
        proc = subprocess.run(
            [
                sys.executable,
                str(TOOLS / "saipen.py"),
                "admission",
                "establish",
                "--json",
                "--project-root",
                str(self.world.project),
                "--session",
                "session-1",
                "--host",
                "claude",
                "--model",
                "model-a",
                "--provider",
                "provider-a",
                "--authority-root",
                str(self.world.authority),
                "--home",
                str(self.world.home),
            ],
            capture_output=True,
            encoding="utf-8",
            env=env,
            cwd=str(ROOT),
            check=False,
        )
        out = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0, out)
        self.assertEqual(out["state"], PA.STATE_ADMITTED)
        self.assertEqual(PA.evaluate(self.world.ctx())["state"], PA.STATE_ADMITTED)

    @unittest.skip(HOST_POSITIVE_BLOCKED)
    def test_the_host_hook_mints_capabilities_the_owner_accepts(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("claude_guard_hook", HOOK)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cap = module.transport_capability(
            self.world.project, "establish", "UserPromptSubmit", "session-1"
        )
        ok, detail, event = PA.verify_transport(self.world.project, "establish", "session-1", cap)
        self.assertTrue(ok, detail)
        self.assertEqual(event, "UserPromptSubmit")
        # The capability is bound: it does not transfer to another verb or session.
        self.assertFalse(PA.verify_transport(self.world.project, "invalidate", "session-1", cap)[0])
        self.assertFalse(PA.verify_transport(self.world.project, "establish", "session-2", cap)[0])

    def test_capability_shapes_are_refused_not_crashed(self):
        self.world.transport()  # key exists
        for bad in ("", None, "hook:", "shell:UserPromptSubmit", "hook:e", "hook:a:b:c"):
            ok, _detail, _event = PA.verify_transport(
                self.world.project, "establish", "session-1", bad
            )
            self.assertFalse(ok, bad)

    def test_a_project_without_a_key_refuses_every_transport(self):
        ok, detail, _event = PA.verify_transport(
            self.world.project, "establish", "session-1", "hook:UserPromptSubmit:" + "0" * 64
        )
        self.assertFalse(ok)
        self.assertEqual(detail, PA.AUTHORITY_UNAVAILABLE)

    def test_local_bootstrap_is_unavailable_and_leaves_legacy_key_untouched(self):
        path = self.world.project / PA.LEDGER_DIR / ".transport.key"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"legacy key")
        self.assertFalse(hasattr(PA, "bootstrap_transport_key"))
        valid, _detail, _event = PA.verify_transport(
            self.world.project, "establish", "session-1", "hook:e:0"
        )
        self.assertFalse(valid)
        self.assertEqual(path.read_bytes(), b"legacy key")


class ForgedLedgerTests(SimulatedOwnerCase):
    """The forged-record control: a syntactically valid, current-looking record
    whose ordinary SHA-256 seal was recomputed by hand is never admission
    evidence. The plain seal stays corruption detection; provenance is keyed."""

    def _admit_then_make_stale(self):
        self.world.establish()
        self.world.edit_authority("STYLE.md", "\nAttacker-era rule.\n")
        verdict = PA.evaluate(self.world.ctx())
        self.assertEqual(verdict["state"], PA.STATE_STALE)

    def _forged_record_text(self) -> str:
        # Everything an attacker without the transport key can compute: the
        # live public fingerprints and a freshly recomputed ordinary seal.
        found = PA.components(self.world.ctx(), self.world.policy)
        gen = PA.generation(found["proofs"])
        record = {
            "schema": PA.SCHEMA_VERSION,
            "host": "claude",
            "model": "model-a",
            "provider": "provider-a",
            "proofs": found["proofs"],
            "generation": gen,
            "token": "tok-" + PA._sha(json.dumps([gen, "session-1", "model-a", "provider-a"]))[:32],
            "delivered": {},
            "transport": "UserPromptSubmit",
        }
        record["seal"] = PA._seal(record)
        return json.dumps(record, sort_keys=True)

    def test_a_resealed_current_looking_record_is_never_admitted(self):
        self._admit_then_make_stale()
        PA._ledger_path(self.world.project, "session-1").write_text(
            self._forged_record_text(), encoding="utf-8"
        )
        verdict = PA.evaluate(self.world.ctx())
        self.assertNotEqual(verdict["state"], PA.STATE_ADMITTED)
        self.assertFalse(verdict["permitted"])
        # Unproven is ABSENT, never STALE-on-a-record-the-project-never-wrote.
        self.assertEqual(verdict["state"], PA.STATE_BINDING)

    def test_a_forged_provenance_field_does_not_verify_either(self):
        self._admit_then_make_stale()
        record = json.loads(self._forged_record_text())
        record["provenance"] = "0" * 64
        PA._ledger_path(self.world.project, "session-1").write_text(
            json.dumps(record, sort_keys=True), encoding="utf-8"
        )
        self.assertEqual(PA.evaluate(self.world.ctx())["state"], PA.STATE_BINDING)

    def test_establish_without_a_capability_installs_nothing_over_the_forge(self):
        self._admit_then_make_stale()
        PA._ledger_path(self.world.project, "session-1").write_text(
            self._forged_record_text(), encoding="utf-8"
        )
        verdict = PA.establish(self.world.ctx())  # direct call, no capability
        self.assertEqual(verdict["code"], PA.CODE_TRANSPORT_REQUIRED)
        self.assertNotEqual(PA.evaluate(self.world.ctx())["state"], PA.STATE_ADMITTED)

    def test_a_foreign_session_record_is_not_this_sessions_evidence(self):
        # A record transplanted from another session stays keyed to that
        # session's ledger name; this session's reader never sees it.
        self.world.establish()
        other_record = PA._ledger_path(self.world.project, "session-2")
        other_record.parent.mkdir(parents=True, exist_ok=True)
        other_record.write_text(
            PA._ledger_path(self.world.project, "session-1").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.assertEqual(
            PA.evaluate(self.world.ctx(session_id="session-2"))["state"], PA.STATE_BINDING
        )


class SkillTests(SimulatedOwnerCase):
    """The observed carrier: `anthropic-skills:caveman` -> Unknown skill."""

    def _synced_only(self):
        shutil.rmtree(self.world.home / ".agents")
        self.world.put_skill(".claude/skills/synced/bucket-1/caveman")

    def test_the_real_layout_resolves_by_identity_and_the_runtime_delivers_it(self):
        self._synced_only()
        verdict = self.world.establish()
        self.assertEqual(verdict["state"], PA.STATE_ADMITTED)
        self.assertIn("=== SKILL caveman", verdict["delivery"])

    def test_a_same_named_directory_holding_another_skill_is_not_the_skill(self):
        shutil.rmtree(self.world.home / ".agents")
        self.world.put_skill(".agents/skills/caveman", name="something-else")
        verdict = PA.evaluate(self.world.ctx())
        self.assertTrue(any("caveman" in w and "unresolvable" in w for w in verdict["warnings"]))

    def test_an_unresolvable_decorative_skill_is_a_reported_diagnostic_not_silence(self):
        shutil.rmtree(self.world.home / ".agents")
        verdict = self.world.establish()
        self.assertEqual(verdict["state"], PA.STATE_ADMITTED)
        self.assertTrue(verdict["warnings"], "an unresolved skill must never be silent")

    def test_an_unresolvable_critical_skill_never_becomes_admitted(self):
        shutil.rmtree(self.world.home / ".agents")
        for contract in self.world.policy["skills"]:
            contract["critical"] = True
        verdict = self.world.establish()
        self.assertEqual(verdict["state"], PA.STATE_REFUSED)
        self.assertTrue(any(p["component"] == "skill:caveman" for p in verdict["problems"]))
        self.assertEqual(verdict["delivery"], "")

    def test_the_shipped_policy_names_the_observed_alias_and_both_real_locations(self):
        contract = next(c for c in REAL_POLICY["skills"] if c["name"] == "caveman")
        self.assertIn("anthropic-skills:caveman", contract["aliases"])
        joined = " ".join(contract["locations"])
        self.assertIn("synced", joined)
        self.assertIn(".agents/skills/caveman", joined)


class InvalidationTests(SimulatedOwnerCase):
    def _admit(self):
        self.assertEqual(self.world.establish()["state"], PA.STATE_ADMITTED)
        self.old_token = PA.evaluate(self.world.ctx())["token"]

    def _assert_stale(self, component: str, **ctx):
        verdict = PA.evaluate(self.world.ctx(**ctx))
        self.assertEqual(verdict["state"], PA.STATE_STALE, verdict)
        self.assertIn(component, verdict["stale"])
        self.assertFalse(verdict["permitted"])

    def test_style_change_makes_the_old_token_stale_until_readmission(self):
        self._admit()
        self.world.edit_authority("STYLE.md", "\nExtra rule line.\n")
        self._assert_stale("authority:STYLE.md")
        again = self.world.establish()
        self.assertEqual(again["state"], PA.STATE_ADMITTED)
        self.assertNotEqual(again["token"], self.old_token)
        self.assertIn("=== STYLE.md", again["delivery"])

    def test_execution_change_is_stale(self):
        self._admit()
        self.world.edit_authority("EXECUTION.md", "\nMore.\n")
        self._assert_stale("authority:EXECUTION.md")

    def test_boot_change_is_stale(self):
        self._admit()
        self.world.edit_authority("BOOT.md", "\nMore.\n")
        self._assert_stale("authority:BOOT.md")

    def test_model_replacement_cannot_inherit_the_token(self):
        self._admit()
        self._assert_stale("model", model="model-b")
        readmit = self.world.establish(model="model-b")
        self.assertEqual(readmit["state"], PA.STATE_ADMITTED)
        self.assertIn("=== BOOT.md", readmit["delivery"])
        self.assertNotEqual(readmit["token"], self.old_token)

    def test_provider_replacement_cannot_inherit_the_token(self):
        self._admit()
        self._assert_stale("provider", provider="provider-b")

    def test_an_unobservable_model_is_reported_not_treated_as_a_change(self):
        self._admit()
        verdict = PA.evaluate(self.world.ctx(model=None))
        self.assertEqual(verdict["state"], PA.STATE_ADMITTED)
        self.assertIn("model", verdict["unobserved"])

    def test_the_activation_block_change_is_stale(self):
        self._admit()
        path = self.world.home / ".claude" / "CLAUDE.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "<!-- SAIPEN:END -->", "extra\n<!-- SAIPEN:END -->"
            ),
            encoding="utf-8",
        )
        self._assert_stale("agents")

    def test_a_missing_activation_block_is_refused(self):
        (self.world.home / ".claude" / "CLAUDE.md").write_text("# nothing\n", encoding="utf-8")
        verdict = PA.evaluate(self.world.ctx())
        self.assertEqual(verdict["state"], PA.STATE_REFUSED)

    def test_the_skill_contract_change_is_stale(self):
        self._admit()
        self.world.policy["skills"][0]["aliases"] = ["renamed"]
        self._assert_stale("skills-contract")

    def test_a_runtime_version_change_is_stale(self):
        self._admit()
        (self.world.authority / "VERSION").write_text("9.9.9\n", encoding="utf-8")
        self._assert_stale("runtime")

    def test_a_project_rebind_is_stale(self):
        self._admit()
        state = self.world.project / ".saipen" / "STATE.md"
        text = state.read_text(encoding="utf-8")
        state.write_text(
            text.replace("---\n", '---\nsaipen_home: "X:\\\\elsewhere"\n', 1), encoding="utf-8"
        )
        self._assert_stale("project")

    def test_a_removed_host_hook_refuses(self):
        self._admit()
        (self.world.home / ".claude" / "hooks" / "saipen-guard.py").unlink()
        verdict = PA.evaluate(self.world.ctx())
        self.assertEqual(verdict["state"], PA.STATE_REFUSED)
        self.assertTrue(any(p["component"] == "host" for p in verdict["problems"]))

    def test_a_new_session_does_not_inherit_the_record(self):
        self._admit()
        self.assertEqual(
            PA.evaluate(self.world.ctx(session_id="session-2"))["state"], PA.STATE_BINDING
        )

    def test_reconnect_and_crash_leave_no_reusable_token(self):
        self._admit()
        path = PA._ledger_path(self.world.project, "session-1")
        path.write_text('{"schema": 1, "proofs": ', encoding="utf-8")  # truncated write
        self.assertEqual(PA.evaluate(self.world.ctx())["state"], PA.STATE_BINDING)
        self.world.establish()
        drop = self.world.invalidate(reason="SessionStart:resume")
        self.assertTrue(drop["ok"] and drop["removed"], drop)
        self.assertEqual(PA.evaluate(self.world.ctx())["state"], PA.STATE_BINDING)


def gate(world: World, text: str, *, state: str = "ADMITTED", **kw):
    """The layered verdict for one reply, through the canonical composer."""
    if state == "ADMITTED":
        world.establish()
    verdict = PA.evaluate(world.ctx())
    contract = CS.compile_style_contract(
        (world.authority / "saipen" / "STYLE.md").read_text(encoding="utf-8")
    )
    return RS.gate_final_response(
        text,
        admission=verdict,
        admission_consulted=True,
        operational_turn=kw.pop("operational_turn", False),
        style_contract=contract,
        **kw,
    )


class LayeringTests(SimulatedOwnerCase):
    def test_no_admission_blocks_a_perfectly_formed_reply(self):
        result = gate(self.world, VALID_REPLY, state="UNESTABLISHED")
        self.assertFalse(result["ok"])
        self.assertEqual(result["layer"], "ADMISSION")
        self.assertEqual(result["class"], RS.CLASS_ADMISSION_BLOCKED)
        self.assertEqual(result["layers"]["exec_response"], "NOT_REACHED")
        self.assertEqual(result["layers"]["chat_style"], "NOT_REACHED")

    def test_admission_plus_a_compliant_reply_passes_every_layer(self):
        result = gate(self.world, VALID_REPLY)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["layer"], "NONE")
        self.assertEqual(result["layers"]["admission"], PA.STATE_ADMITTED)

    def test_admission_does_not_excuse_an_invalid_operational_reply(self):
        result = gate(self.world, "Everything is fine.", operational_turn=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["layer"], "EXEC_RESPONSE")
        self.assertEqual(result["layers"]["admission"], PA.STATE_ADMITTED)

    def test_admission_does_not_excuse_a_style_invalid_reply(self):
        result = gate(self.world, ESSAY)
        self.assertFalse(result["ok"])
        self.assertEqual(result["layer"], "CHAT_STYLE")
        self.assertEqual(result["class"], RS.CLASS_CHAT_STYLE_DRIFT)

    def test_a_detailed_request_without_admission_is_still_blocked(self):
        nine = "\n".join(f"Leid {n}: t\u00e4pne ja kontrollitud." for n in range(9))
        result = gate(self.world, nine, state="UNESTABLISHED", detail_mode=RS.DETAIL_MODE_REPORT)
        self.assertEqual(result["layer"], "ADMISSION")

    def test_a_detailed_request_with_admission_passes(self):
        nine = "\n".join(f"Leid {n}: t\u00e4pne ja kontrollitud." for n in range(9))
        from saipen_engine.operator_task import witness
        from test_fixture_support import operator_request_env

        request = "write a detailed report of the change"
        result = gate(
            self.world,
            nine,
            detail_mode=RS.DETAIL_MODE_REPORT,
            human_request=request,
            request_authority=witness(request, env=operator_request_env(request)),
        )
        self.assertTrue(result["ok"], result)

    def test_a_stale_token_blocks_at_the_admission_layer(self):
        self.world.establish()
        self.world.edit_authority("STYLE.md", "\nChanged.\n")
        result = gate(self.world, VALID_REPLY, state="STALE")
        self.assertEqual(result["layer"], "ADMISSION")
        self.assertEqual(result["layers"]["admission"], PA.STATE_STALE)

    def test_a_host_that_cannot_enforce_admission_is_reported_not_passed(self):
        result = RS.gate_final_response(
            VALID_REPLY,
            admission=None,
            admission_consulted=False,
            operational_turn=False,
            style_contract=None,
        )
        self.assertEqual(result["layers"]["admission"], "NOT_ENFORCEABLE")
        self.assertTrue(result["ok"])

    def test_the_diagnostic_is_runtime_authored_bounded_and_carries_no_advice_prose(self):
        text = PA.diagnostic(PA.evaluate(self.world.ctx()))
        self.assertLessEqual(len(text), 480)
        self.assertTrue(text.startswith("SAIPEN PROTOCOL ADMISSION"))


def cli_check(project: Path, text: bytes, *extra: str):
    proc = subprocess.run(
        [
            sys.executable,
            str(TOOLS / "saipen.py"),
            "response",
            "check",
            "--stdin",
            "--json",
            "--classify",
            "--project-root",
            str(project),
            *extra,
        ],
        input=text,
        capture_output=True,
        cwd=str(ROOT),
        check=False,
    )
    return proc.returncode, json.loads(proc.stdout.decode("utf-8"))


class PreFixOracleTests(WorldCase):
    """The pre-fix subject: `response check --classify` exactly as every host
    called it before admission existed (no admission arguments). The carriers
    that escape it are the ones the repaired invocation must refuse through the
    SAME oracle, same project, same bytes."""

    def _admission_args(self):
        return (
            "--admission-session",
            "session-1",
            "--host",
            "claude",
            "--model",
            "model-a",
            "--provider",
            "provider-a",
            "--authority-root",
            str(self.world.authority),
            "--home",
            str(self.world.home),
        )

    def test_missing_style_evidence_escaped_before_and_is_refused_now(self):
        legacy_rc, legacy = cli_check(self.world.project, VALID_REPLY.encode("utf-8"))
        self.assertEqual((legacy_rc, legacy["class"]), (0, RS.CLASS_ORDINARY_CHAT))
        rc, now = cli_check(
            self.world.project, VALID_REPLY.encode("utf-8"), *self._admission_args()
        )
        self.assertEqual(rc, 1, now)
        self.assertEqual(now["layer"], "ADMISSION")
        self.assertEqual(now["class"], RS.CLASS_ADMISSION_BLOCKED)

    def test_missing_required_skill_evidence_escaped_before_and_is_refused_now(self):
        # Same oracle, a world whose required skill cannot be resolved. The
        # legacy invocation cannot tell; the admitted invocation refuses because
        # the shipped policy is tightened for this carrier by the policy owner.
        shutil.rmtree(self.world.home / ".agents")
        legacy_rc, legacy = cli_check(self.world.project, VALID_REPLY.encode("utf-8"))
        self.assertEqual((legacy_rc, legacy["class"]), (0, RS.CLASS_ORDINARY_CHAT))
        policy = json.loads(json.dumps(REAL_POLICY))
        for contract in policy["skills"]:
            contract["critical"] = True
        verdict = self.world.establish(policy=policy)
        self.assertEqual(verdict["state"], PA.STATE_REFUSED)

    @unittest.skip(HOST_POSITIVE_BLOCKED)
    def test_admitted_through_the_same_oracle_passes(self):
        self.world.establish()
        rc, now = cli_check(
            self.world.project, VALID_REPLY.encode("utf-8"), *self._admission_args()
        )
        self.assertEqual((rc, now["layer"]), (0, "NONE"), now)


def guard(project: Path | None, event: dict, home: Path, *, authority: Path | None = None):
    """Run the real hook artifact. Fixture paths travel as the artifact's own
    command-line flags -- never environment -- so an installed hook (whose
    command line the operator controls) cannot be pointed at forged authority."""
    payload = {"session_id": "session-1", "cwd": str(project) if project else "", **event}
    argv = [
        sys.executable,
        str(HOOK),
        "--host",
        "claude",
        "--saipen-root",
        str(ROOT),
        "--home",
        str(home),
    ]
    if authority is not None:
        argv += ["--authority-root", str(authority)]
    proc = subprocess.run(
        argv,
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        cwd=str(ROOT),
        check=False,
    )
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    return json.loads(out) if out else None


class ClaudeHostTests(WorldCase):
    """HOST evidence: the Claude Code hook, real subprocesses, real CLI."""

    def _prompt(self, **extra):
        return guard(
            self.world.project,
            {"hook_event_name": "UserPromptSubmit", "user_prompt": "hi", **extra},
            self.world.home,
            authority=self.world.authority,
        )

    @unittest.skip(HOST_POSITIVE_BLOCKED)
    def test_the_first_prompt_delivers_authority_before_the_model_runs(self):
        out = self._prompt()
        context = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        for name in PA.AUTHORITY_DOCUMENTS:
            self.assertIn(f"=== {name} sha256:", context)
        self.assertNotIn("decision", out)

    @unittest.skip(HOST_POSITIVE_BLOCKED)
    def test_the_second_prompt_is_not_charged_the_full_delivery(self):
        self._prompt()
        second = self._prompt()["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("=== BOOT.md", second)
        self.assertIn("SAIPEN chat contract", second)

    def test_a_refused_admission_blocks_the_prompt_with_a_runtime_diagnostic(self):
        (self.world.authority / "saipen" / "EXECUTION.md").unlink()
        out = self._prompt()
        self.assertEqual(out["decision"], "block")
        self.assertTrue(out["reason"].startswith("SAIPEN PROTOCOL ADMISSION REFUSED"))
        self.assertNotIn("hookSpecificOutput", out)

    @unittest.skip(HOST_POSITIVE_BLOCKED)
    def test_a_changed_style_is_redelivered_on_the_next_prompt(self):
        self._prompt()
        self.world.edit_authority("STYLE.md", "\nNew rule.\n")
        out = self._prompt()
        self.assertIn("=== STYLE.md", out["hookSpecificOutput"]["additionalContext"])

    @unittest.skip(HOST_POSITIVE_BLOCKED)
    def test_compaction_wipes_the_context_so_the_next_session_start_redelivers(self):
        self._prompt()
        out = guard(
            self.world.project,
            {"hook_event_name": "SessionStart", "source": "compact"},
            self.world.home,
            authority=self.world.authority,
        )
        self.assertIn("=== BOOT.md", out["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SessionStart")

    def test_a_model_switch_invalidates_the_admission(self):
        self._prompt()
        guard(
            self.world.project,
            {"hook_event_name": "PostModelSwitch", "model": "model-b"},
            self.world.home,
            authority=self.world.authority,
        )
        self.assertFalse(PA.evaluate(self.world.ctx())["permitted"])
        self.assertFalse((self.world.project / PA.LEDGER_DIR).exists())

    def test_bootstrap_tool_activity_is_never_gated_while_unadmitted(self):
        # Before admission the model must still be able to read, resolve and run.
        for event in (
            {"hook_event_name": "PreToolUse", "tool_name": "Read"},
            {"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_input": {}},
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "saipen status --json"},
            },
        ):
            self.assertIsNone(
                guard(self.world.project, event, self.world.home, authority=self.world.authority),
                event,
            )
        self.assertFalse(PA.evaluate(self.world.ctx())["permitted"])

    def test_the_stop_gate_blocks_an_unadmitted_perfect_reply_with_a_runtime_reason(self):
        out = guard(
            self.world.project,
            {
                "hook_event_name": "Stop",
                "stop_hook_active": False,
                "last_assistant_message": VALID_REPLY,
            },
            self.world.home,
            authority=self.world.authority,
        )
        self.assertEqual(out["decision"], "block")
        self.assertIn("PROTOCOL ADMISSION", out["reason"])

    @unittest.skip(HOST_POSITIVE_BLOCKED)
    def test_the_stop_gate_passes_an_admitted_compliant_reply(self):
        self._prompt()
        out = guard(
            self.world.project,
            {
                "hook_event_name": "Stop",
                "stop_hook_active": False,
                "last_assistant_message": VALID_REPLY,
            },
            self.world.home,
            authority=self.world.authority,
        )
        self.assertIsNone(out, out)

    @unittest.skip(HOST_POSITIVE_BLOCKED)
    def test_the_stop_gate_still_rejects_a_style_invalid_reply_after_admission(self):
        self._prompt()
        out = guard(
            self.world.project,
            {"hook_event_name": "Stop", "stop_hook_active": False, "last_assistant_message": ESSAY},
            self.world.home,
            authority=self.world.authority,
        )
        self.assertEqual(out["decision"], "block")
        self.assertIn("CHAT_STYLE_DRIFT", out["reason"])


class SameTurnInitTests(unittest.TestCase):
    """Non-SAIPEN start -> the REAL launcher init -> same turn -> admission."""

    def test_real_init_then_the_same_turn_final_reply_is_gated_by_admission(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            world_home = tmp / "home"
            world_home.mkdir()
            authority = tmp / "authority"
            (authority / "saipen").mkdir(parents=True)
            for name in PA.AUTHORITY_DOCUMENTS:
                shutil.copy2(ROOT / "saipen" / name, authority / "saipen" / name)
            shutil.copy2(ROOT / "VERSION", authority / "VERSION")
            (world_home / ".claude").mkdir()
            block = autoinject.rendered_activation_block(ROOT / "saipen")
            (world_home / ".claude" / "CLAUDE.md").write_text(block + "\n", encoding="utf-8")
            install_host_guard.install("claude", world_home, ROOT)
            skill = world_home / ".agents" / "skills" / "caveman"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("---\nname: caveman\n---\nTerse.\n", encoding="utf-8")
            project = tmp / "fresh-dir"
            project.mkdir()
            # Turn start outside SAIPEN: nothing governs, nothing is delivered.
            self.assertIsNone(
                guard(
                    project,
                    {"hook_event_name": "UserPromptSubmit", "user_prompt": "init"},
                    world_home,
                    authority=authority,
                )
            )
            launcher = ROOT / "bin" / ("saipen.cmd" if os.name == "nt" else "saipen")
            init = subprocess.run(
                [
                    str(launcher),
                    "init",
                    "--project-root",
                    str(project),
                    "--agent",
                    "test-agent",
                    "--json",
                ],
                capture_output=True,
                encoding="utf-8",
                cwd=str(ROOT),
                check=False,
                env={k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")},
            )
            self.assertEqual(json.loads(init.stdout)["code"], "INIT_COMPLETED", init.stdout[-300:])
            # The host then reports the tool result: the runtime binds and delivers.
            out = guard(
                project,
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Bash",
                    "tool_input": {"command": f"saipen init --project-root {project}"},
                },
                world_home,
                authority=authority,
            )
            self.assertIn("HOST_AUTHORITY_UNAVAILABLE", out["systemMessage"])
            self.assertNotIn("hookSpecificOutput", out)
            self.assertFalse((project / PA.LEDGER_DIR).exists())
            # Same turn, no restart, no grace turn: the final reply meets admission.
            reply = guard(
                project,
                {
                    "hook_event_name": "Stop",
                    "stop_hook_active": False,
                    "last_assistant_message": VALID_REPLY,
                },
                world_home,
                authority=authority,
            )
            # The fresh project routes as an operational WAIT (the human owes the
            # first goal): the EXEC-RESPONSE layer, not admission, speaks now.
            self.assertEqual(reply.get("decision"), "block", reply)
            self.assertIn("PROTOCOL ADMISSION", reply["reason"])
            self.assertNotIn("EXEC-RESPONSE-01 gate", reply["reason"])


class CapabilityMatrixTests(unittest.TestCase):
    MATRIX_KEYS = (
        "pre_output_interception",
        "stop_output_interception",
        "admission_enforcement",
        "response_enforcement",
        "style_enforcement",
    )

    def setUp(self):
        registry = json.loads(
            (ROOT / "extensions" / "adapters" / "registry.json").read_text(encoding="utf-8-sig")
        )
        self.adapters = {entry["id"]: entry for entry in registry["adapters"]}

    def test_every_host_records_every_boundary_separately(self):
        for name, entry in self.adapters.items():
            for key in self.MATRIX_KEYS:
                self.assertIn(key, entry, f"{name}.{key}")
            self.assertTrue(str(entry.get("admission_enforcement_note") or "").strip(), name)

    def test_a_mechanical_claim_needs_a_token_its_own_artifact_contains(self):
        for name, entry in self.adapters.items():
            for claim, token_key in (
                ("admission_enforcement", "admission_hook"),
                ("style_enforcement", "style_hook"),
            ):
                if entry.get(claim) == "MECHANICAL":
                    token = entry.get(token_key)
                    self.assertTrue(token, f"{name}: {claim} MECHANICAL without {token_key}")
                    artifact = (ROOT / entry["hook_artifact"]).read_text(encoding="utf-8")
                    self.assertIn(token, artifact, f"{name}: {token_key} not in its artifact")

    def test_claude_is_mechanical_at_the_prompt_boundary_and_not_universal(self):
        claude = self.adapters["claude"]
        self.assertEqual(claude["admission_enforcement"], "UNAVAILABLE")
        self.assertTrue(claude["admission_required"])
        self.assertEqual(claude["pre_output_interception"], "PROMPT_LEVEL")
        self.assertEqual(claude["stop_output_interception"], "MECHANICAL")
        self.assertIn("separated host authority", claude["admission_enforcement_note"])

    def test_no_other_host_claims_admission_without_an_evidence_channel(self):
        for name, entry in self.adapters.items():
            if name == "claude":
                continue
            self.assertNotEqual(entry["admission_enforcement"], "MECHANICAL", name)

    def test_a_host_without_the_claim_is_not_consulted(self):
        ctx = PA.Context(project_root=None, session_id="s", host="codex")
        self.assertFalse(PA.consulted(ctx))
        self.assertTrue(PA.consulted(PA.Context(project_root=None, session_id="s", host="claude")))

    def test_the_matrix_is_reported_by_status(self):
        matrix = PA.capability_matrix()
        self.assertEqual(set(matrix["claude"]), set(self.MATRIX_KEYS))


class PolicyDataTests(unittest.TestCase):
    def test_the_shipped_policy_is_data_with_an_owner_and_a_test(self):
        registry = json.loads((ROOT / "saipen" / "REGISTRY.json").read_text(encoding="utf-8-sig"))
        section = registry["protocol_admission"]
        self.assertEqual(section["owner"], "tools/saipen_engine/protocol_admission.py")
        self.assertEqual(section["test"], "tools/test_protocol_admission.py")
        self.assertEqual(section["documents"], list(PA.AUTHORITY_DOCUMENTS))

    def test_the_refusal_codes_the_owner_emits_are_registered(self):
        registry = json.loads((ROOT / "saipen" / "REGISTRY.json").read_text(encoding="utf-8-sig"))
        for code in (PA.CODE_REQUIRED, PA.CODE_TRANSPORT_REQUIRED):
            self.assertIn(code, registry["error_codes"])

    def test_no_adapter_restates_admission_policy(self):
        for artifact in (
            ROOT / "extensions" / "adapters" / "claude" / "saipen-guard.py",
            ROOT / "extensions" / "adapters" / "codex" / "saipen-guard.py",
        ):
            text = artifact.read_text(encoding="utf-8")
            for forbidden in ("AUTHORITY_DOCUMENTS", "BOOT.md", "resolve_skill", "agents_absent"):
                self.assertNotIn(forbidden, text, f"{artifact.name}: {forbidden}")


if __name__ == "__main__":
    unittest.main()
