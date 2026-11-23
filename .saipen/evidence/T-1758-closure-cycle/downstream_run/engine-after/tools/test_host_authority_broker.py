"""T-1623/T-1624 regression matrix for the separated SAIPEN host-authority broker.

Evidence classes, kept apart on purpose:

* AUTHORITY  -- the broker's own decisions once a client is proven: what a
                capability binds, what survives a restart, what an expiry does.
                These cases CONSTRUCT a broker in-process and hand it an
                authenticator that says "proven" (`PROVEN`): the subject is the
                capability, ledger and lifecycle logic, not the proof.
* IDENTITY   -- the proof itself, with nothing injected: who the shipped broker
                refuses, and that its reason is specific.
* OWNER      -- how `protocol_admission` consumes the broker: admission,
                staleness, refresh, and the ledger provenance question.
* HOST       -- the real Claude Code hook artifact, the shipped service entry
                as its own process, and a host stand-in that starts the hook
                the way the host does (`test_host_fixture.HostFixture`).
* ATTACK     -- the same-user callers the boundary exists to refuse.

The host stand-in is a copy of this interpreter named like the host
application. Under the shipped policy that is exactly an interpreter renamed
after the host, and the service refuses it for its code signer -- asserted
here on a real service process. The positive host cases therefore run a
service on an explicit runtime root whose policy file drops the signer
requirement; an explicit root is another endpoint than the operator's, and the
operator's real root never reads such a file.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _entry in (str(TOOLS), str(ROOT), str(ROOT / "bootstrap")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from saipen_engine import host_authority_broker as HB  # noqa: E402
from saipen_engine import host_authority_client as HC  # noqa: E402
from saipen_engine import host_authority_identity as HI  # noqa: E402
from saipen_engine import host_authority_transport as HT  # noqa: E402
from saipen_engine import protocol_admission as PA  # noqa: E402
from test_host_fixture import HostFixture  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_protocol_admission import World  # noqa: E402


def setUpModule() -> None:
    # T-1685: the operator's host profile and binding never reach a fixture.
    isolate_host_session()


def isolate_profile(test: unittest.TestCase, tmp: Path) -> Path:
    """Point this process at a disposable per-user runtime root.

    The broker's runtime root is per-user (`Path.home()/.saipen/authority`), so a
    test that wants to meet the DEFAULT endpoint must move the user home rather
    than write into the operator's. Nothing in the broker reads an environment
    variable for AUTHORITY; this only relocates non-authoritative runtime state.
    """
    profile = tmp / "userprofile"
    profile.mkdir(parents=True, exist_ok=True)
    patcher = mock.patch.dict(
        os.environ,
        {
            "USERPROFILE": str(profile),
            "HOME": str(profile),
            "HOMEDRIVE": "",
            "HOMEPATH": "",
        },
    )
    patcher.start()
    test.addCleanup(patcher.stop)
    return profile / ".saipen" / "authority"


HOST_IMAGES = ["claude.exe", "claude", "claude-code", "claude-code.exe"]
WINDOWS = os.name == "nt"
NON_HOOK_REFUSALS = (
    HI.REASON_NOT_HOST_DESCENDANT,
    HI.REASON_HOOK_NOT_FOUND,
    HI.REASON_IDENTITY_UNAVAILABLE,
    HI.REASON_PARENT_REUSED,
)


def PROVEN(peer, host, home):
    """Stands in for a PASSED hook-invocation proof. Never a claim about the
    proof: `IdentityTests` and the host cases prove that separately."""
    return (
        True,
        None,
        {
            "transport": getattr(peer, "kind", "unknown"),
            "pid": getattr(peer, "pid", None),
            "host_image": "claude.exe",
            "host_pid": 1,
            "chain": [],
        },
    )


class Harness:
    """A real broker on a real endpoint in a per-test runtime root."""

    def __init__(
        self, runtime: Path, *, config: dict | None = None, clock=None, proven: bool = False
    ) -> None:
        self.runtime = Path(runtime)
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.broker = HB.Broker(
            saipen_root=ROOT,
            runtime=self.runtime,
            config=dict(config or HB.settings()),
            clock=clock or HB._now,
            authenticator=PROVEN if proven else None,
        )
        self.stop = threading.Event()
        self.thread = threading.Thread(
            target=HT.serve,
            kwargs={
                "name": HB.endpoint_name(self.runtime),
                "handler": self.broker.handle,
                "stop": self.stop,
            },
            daemon=True,
        )
        self.thread.start()
        self.await_ready()

    def await_ready(self, timeout: float = 15.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if HB.health(self.runtime, timeout=0.5):
                return
            time.sleep(0.05)
        raise AssertionError("the broker never became reachable")

    @property
    def instance(self) -> str:
        return self.broker.authority.instance

    def close(self) -> None:
        self.stop.set()
        self.thread.join(timeout=5)

    def admitted(
        self,
        world: World,
        *,
        session: str = "session-1",
        event: str = "UserPromptSubmit",
        model: object = "model-a",
        provider: object = "provider-a",
        project: object = None,
    ) -> dict:
        return HB.request(
            {
                "op": "admission",
                "project": str(project if project is not None else world.project),
                "session": session,
                "host": "claude",
                "model": model,
                "provider": provider,
                "authority_root": str(world.authority),
                "home": str(world.home),
                "event": event,
            },
            runtime=self.runtime,
        )

    def verify(self, capability: str, world: World, **overrides) -> dict:
        fields = {
            "session": "session-1",
            "model": "model-a",
            "provider": "provider-a",
            **overrides,
        }
        return HB.request(
            {
                "op": "verify",
                "project": str(fields.pop("project", world.project)),
                "host": "claude",
                **fields,
                "capability": capability,
            },
            runtime=self.runtime,
        )


class BrokerCase(unittest.TestCase):
    """A broker that treats its client as proven (see `PROVEN`).

    The broker serves the world's own runtime root, so `world.ctx()` meets it
    and nothing here can reach an authority outside the test.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.world = World(self.tmp)
        self.config = {**HB.settings(), "identity_cache_seconds": 0}
        self.harness = Harness(self.world.runtime, config=self.config, proven=True)
        self.addCleanup(self.harness.close)


class IdentityTests(unittest.TestCase):
    """The shipped policy and the shipped proof, with nothing injected."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.world = World(self.tmp)
        self.harness = Harness(self.world.runtime)
        self.addCleanup(self.harness.close)

    def test_the_shipped_policy_names_host_images_and_their_code_signer(self):
        settings = HB.settings()
        self.assertEqual(settings["host_images"], HOST_IMAGES)
        self.assertNotIn("python.exe", settings["host_images"])
        self.assertEqual(settings["host_signers"], ["Anthropic, PBC"])
        self.assertGreater(int(settings["capability_ttl_seconds"]), 0)
        self.assertGreater(int(settings["identity_cache_seconds"]), 0)

    def test_an_arbitrary_same_user_python_client_is_refused(self):
        reply = self.harness.admitted(self.world)
        self.assertFalse(reply["ok"], reply)
        reason = reply["identity"]["reason"]
        self.assertIn(reason, NON_HOOK_REFUSALS, reply)
        expected = (HB.CODE_IDENTITY_UNAVAILABLE
                    if reason == HI.REASON_IDENTITY_UNAVAILABLE
                    else HB.CODE_NOT_AUTHENTICATED)
        self.assertEqual(reply["code"], expected, reply)
        self.assertTrue(reply["detail"])
        self.assertFalse((self.world.project / PA.LEDGER_DIR).exists())
        self.assertEqual(self.harness.broker.stats.last_refusal["op"], "admission")

    def test_a_client_that_merely_imports_the_hook_gains_nothing(self):
        reply = self.harness.admitted(self.world)
        self.assertNotIn("capability", reply)
        self.assertNotIn("token", reply)
        self.assertEqual(PA.evaluate(self.world.ctx())["state"], PA.STATE_BINDING)
        self.assertFalse(PA.evaluate(self.world.ctx())["permitted"])
        self.assertFalse((self.world.project / PA.LEDGER_DIR).exists())

    def test_every_write_op_requires_the_proof_and_reads_do_not(self):
        base = {
            "project": str(self.world.project),
            "session": "session-1",
            "host": "claude",
            "home": str(self.world.home),
            "authority_root": str(self.world.authority),
        }
        for op in HB.WRITE_OPS:
            with self.subTest(op=op):
                reply = HB.request({"op": op, **base}, runtime=self.harness.runtime)
                self.assertFalse(reply["ok"])
                self.assertEqual(reply["code"], HB.CODE_NOT_AUTHENTICATED)
        # A read answers anyone and gives nothing to forge with: it is a
        # question about values only this process can reproduce.
        state = HB.request({"op": "evaluate", **base}, runtime=self.harness.runtime)
        self.assertEqual(state["state"], PA.STATE_BINDING)
        probe = HB.request(
            {"op": "verify-record", "record": {"provenance": {"kid": "x"}}},
            runtime=self.harness.runtime,
        )
        self.assertFalse(probe["ok"])

    def test_an_ordinary_process_is_not_a_hook_invocation_and_starts_nothing(self):
        # This interpreter is the suite, never a host's hook -- whether or not
        # the suite itself was started from inside a host session.
        shape = HC.hook_invocation("claude", self.world.home)
        self.assertFalse(shape["ok"], shape)
        self.assertIn(shape["reason"], NON_HOOK_REFUSALS, shape)
        self.assertFalse(HC.identify_self(host="claude", home=self.world.home)["hook"])
        unserved = self.tmp / "unserved-runtime"
        report = HC.ensure(ROOT, runtime=unserved, host="claude", home=self.world.home)
        self.assertEqual(
            (report["ok"], report["started"], report["state"]),
            (False, False, "not_a_host_client"),
        )
        self.assertEqual(report["code"], HC.CODE_NOT_HOST_CLIENT)
        self.assertIn("hook invocation", report["detail"])
        self.assertFalse(HB.health(unserved))
        self.assertIsNone(HB.read_status(unserved))

    def test_health_is_answerable_without_disclosing_an_identity(self):
        ping = HB.health(self.harness.runtime)
        self.assertTrue(ping["ok"])
        self.assertEqual(ping["service"], HB.SERVICE)
        self.assertEqual(ping["instance"], self.harness.instance)
        self.assertEqual(ping["generation"], HB.service_generation())

    def test_stopping_the_service_is_not_a_trust_decision(self):
        reply = HB.request({"op": "shutdown"}, runtime=self.harness.runtime)
        self.assertTrue(reply["ok"])
        self.assertEqual(reply["code"], "BROKER_SHUTDOWN")


class CapabilityTests(BrokerCase):
    def test_a_host_client_is_admitted_and_gets_a_session_bound_capability(self):
        reply = self.harness.admitted(self.world)
        self.assertTrue(reply["ok"], reply)
        self.assertEqual(reply["state"], PA.STATE_ADMITTED)
        self.assertTrue(reply["verified"])
        self.assertTrue(reply["record_written"])
        self.assertTrue(reply["capability"].startswith(HB.CAPABILITY_PREFIX + "."))
        self.assertIn("=== BOOT.md sha256:", reply["delivery"])
        self.assertTrue((self.world.project / PA.LEDGER_DIR).exists())

    def test_a_current_session_is_not_charged_a_second_delivery(self):
        self.harness.admitted(self.world)
        again = self.harness.admitted(self.world)
        self.assertEqual((again["state"], again["delivery"]), (PA.STATE_ADMITTED, ""))
        self.assertFalse(again["record_written"])

    def test_a_capability_transplanted_to_another_session_or_model_is_refused(self):
        capability = self.harness.admitted(self.world)["capability"]
        for overrides in (
            {"session": "session-2"},
            {"model": "model-b"},
            {"provider": "provider-b"},
        ):
            with self.subTest(**overrides):
                probe = self.harness.verify(capability, self.world, **overrides)
                self.assertFalse(probe["ok"], probe)
                self.assertEqual(probe["code"], HB.CODE_BINDING_MISMATCH)

    def test_a_capability_from_another_broker_generation_is_refused(self):
        first = self.harness.admitted(self.world)["capability"]
        self.harness.close()
        second = Harness(self.tmp / "runtime2", config=self.config, proven=True)
        self.addCleanup(second.close)
        probe = second.verify(first, self.world)
        self.assertFalse(probe["ok"])
        self.assertEqual(probe["code"], HB.CODE_CAPABILITY_INVALID)

    def test_an_expired_capability_is_refused(self):
        now = [1000.0]
        harness = Harness(
            self.tmp / "runtime-expiry", config=self.config, clock=lambda: now[0], proven=True
        )
        self.addCleanup(harness.close)
        reply = harness.admitted(self.world)
        self.assertTrue(reply["ok"])
        now[0] += HB.DEFAULT_TTL_SECONDS + 1
        probe = harness.verify(reply["capability"], self.world)
        self.assertFalse(probe["ok"])
        self.assertEqual(probe["code"], HB.CODE_CAPABILITY_EXPIRED)

    def test_a_sha256_shaped_capability_forges_nothing(self):
        forged = ".".join(
            [
                HB.CAPABILITY_PREFIX,
                self.harness.instance,
                str(int(time.time()) + 600),
                "deadbeefdeadbeef",
                hashlib.sha256(b"ordinary data").hexdigest(),
            ]
        )
        probe = self.harness.verify(forged, self.world)
        self.assertFalse(probe["ok"])
        self.assertEqual(probe["code"], HB.CODE_CAPABILITY_REPLAY)

    def test_a_capability_is_bound_to_the_project_it_was_minted_for(self):
        (self.tmp / "w2").mkdir()
        other = World(self.tmp / "w2")
        capability = self.harness.admitted(self.world)["capability"]
        probe = self.harness.verify(capability, other)
        self.assertFalse(probe["ok"])
        self.assertEqual(probe["code"], HB.CODE_BINDING_MISMATCH)
        self.assertFalse((other.project / PA.LEDGER_DIR).exists())


class LedgerTests(BrokerCase):
    def test_the_owner_reads_the_broker_record_and_refuses_a_hand_built_one(self):
        self.harness.admitted(self.world)
        self.assertEqual(PA.evaluate(self.world.ctx())["state"], PA.STATE_ADMITTED)

        path = PA._ledger_path(self.world.project, "session-1")
        record = json.loads(path.read_text(encoding="utf-8"))
        forged = dict(record)
        forged["provenance"] = {
            "kid": self.harness.instance,
            "alg": "hmac-sha256",
            "mac": "0" * 64,
        }
        path.write_text(json.dumps(forged), encoding="utf-8")
        self.assertIsNone(PA._read_record(self.world.project, "session-1"))
        self.assertEqual(PA.evaluate(self.world.ctx())["state"], PA.STATE_BINDING)
        self.assertFalse(PA.evaluate(self.world.ctx())["permitted"])

    def test_an_edited_record_fails_the_broker_provenance_too(self):
        self.harness.admitted(self.world)
        path = PA._ledger_path(self.world.project, "session-1")
        record = json.loads(path.read_text(encoding="utf-8"))
        record["token"] = "tok-forged"
        path.write_text(json.dumps(record), encoding="utf-8")
        self.assertIsNone(PA._read_record(self.world.project, "session-1"))

    def test_invalidation_through_the_broker_removes_the_record(self):
        self.harness.admitted(self.world)
        reply = HB.request(
            {
                "op": "invalidate",
                "project": str(self.world.project),
                "session": "session-1",
                "host": "claude",
                "reason": "SessionStart:resume",
            },
            runtime=self.harness.runtime,
        )
        self.assertTrue(reply["ok"])
        self.assertTrue(reply["removed"])
        self.assertEqual(PA.evaluate(self.world.ctx())["state"], PA.STATE_BINDING)

    def test_the_ledger_write_is_still_refused_for_an_ordinary_caller(self):
        with self.assertRaises(PermissionError):
            PA._write_record(self.world.project, "session-1", {"schema": 1}, "UserPromptSubmit")
        self.assertFalse((self.world.project / PA.LEDGER_DIR).exists())


class OwnerLifecycleTests(BrokerCase):
    def test_authority_bytes_changing_makes_the_session_stale_and_redelivers(self):
        self.harness.admitted(self.world)
        self.world.edit_authority("STYLE.md", "\nNew rule.\n")
        reply = self.harness.admitted(self.world)
        self.assertEqual(
            (reply["state"], reply["previous_state"]), (PA.STATE_ADMITTED, PA.STATE_STALE)
        )
        self.assertIn("authority:STYLE.md", reply["stale"])
        self.assertIn("=== STYLE.md", reply["delivery"])
        self.assertTrue(reply["record_written"])

    def test_a_model_or_provider_switch_invalidates_the_session(self):
        self.harness.admitted(self.world)
        reply = self.harness.admitted(self.world, model="model-b")
        self.assertEqual(
            (reply["state"], reply["previous_state"]), (PA.STATE_ADMITTED, PA.STATE_STALE)
        )
        self.assertIn("model", reply["stale"])
        again = self.harness.admitted(self.world, provider="provider-b")
        self.assertEqual(again["previous_state"], PA.STATE_STALE)
        self.assertIn("provider", again["stale"])

    def test_a_new_session_admits_fresh_and_never_reuses_the_old_record(self):
        self.harness.admitted(self.world)
        reply = self.harness.admitted(self.world, session="session-2")
        self.assertEqual(reply["previous_state"], PA.STATE_BINDING)
        self.assertIn("=== BOOT.md", reply["delivery"])

    def test_a_broker_crash_leaves_no_reusable_admission(self):
        self.harness.admitted(self.world)
        self.harness.close()  # a crash, not a graceful invalidation
        verdict = PA.evaluate(self.world.ctx())
        self.assertEqual(verdict["state"], PA.STATE_BINDING)
        self.assertFalse(verdict["permitted"])

    def test_a_broker_restart_readmits_the_same_session_automatically(self):
        first = self.harness.admitted(self.world)
        self.harness.close()
        revived = Harness(self.harness.runtime, config=self.config, proven=True)
        self.addCleanup(revived.close)
        self.assertNotEqual(revived.instance, first["instance"])
        reply = revived.admitted(self.world)
        self.assertEqual(reply["state"], PA.STATE_ADMITTED)
        self.assertNotEqual(reply["capability"], first["capability"])
        self.assertTrue(reply["record_written"])
        self.assertEqual(PA.evaluate(self.world.ctx())["state"], PA.STATE_ADMITTED)

    def test_a_shutdown_request_ends_the_service_and_retires_its_key(self):
        self.harness.admitted(self.world)
        self.harness.close()
        self.assertIsNone(HB.health(self.harness.runtime))
        with self.assertRaises(HT.TransportError):
            HB.request({"op": "ping"}, runtime=self.harness.runtime, timeout=1.0)

    def test_a_duplicate_broker_launch_is_refused_and_the_owner_keeps_serving(self):
        runtime = self.tmp / "runtime-lock"
        self.assertTrue(HB.acquire_lock(runtime)[0])
        self.addCleanup(HB.release_lock, runtime)
        acquired, detail = HB.acquire_lock(runtime)
        self.assertFalse(acquired)
        self.assertIn("another broker is already running", detail)
        self.assertTrue(HB.health(self.harness.runtime))

    def test_a_stale_lock_is_reclaimed_after_a_kill(self):
        runtime = self.tmp / "runtime-crashed"
        HB.lock_path(runtime).parent.mkdir(parents=True, exist_ok=True)
        HB.lock_path(runtime).write_text(
            json.dumps({"pid": 999999999, "started": 0}), encoding="utf-8"
        )
        acquired, detail = HB.acquire_lock(runtime)
        self.assertTrue(acquired, detail)
        HB.release_lock(runtime)

    def test_project_switch_admits_the_new_project_and_leaves_the_old_one_alone(self):
        self.harness.admitted(self.world)
        (self.tmp / "w2").mkdir()
        other = World(self.tmp / "w2")
        reply = self.harness.admitted(other)
        self.assertEqual(reply["previous_state"], PA.STATE_BINDING)
        self.assertIn("=== BOOT.md", reply["delivery"])
        self.assertTrue((other.project / PA.LEDGER_DIR).exists())
        self.assertTrue((self.world.project / PA.LEDGER_DIR).exists())


class DiagnosticTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.world = World(self.tmp)

    def test_an_absent_broker_names_the_failure_the_recovery_and_one_action(self):
        verdict = PA.establish(self.world.ctx())
        self.assertFalse(verdict["permitted"])
        self.assertEqual(verdict["failure"], "AUTHORITY_UNREACHABLE")
        text = PA.diagnostic(verdict)
        self.assertTrue(text.startswith("SAIPEN PROTOCOL ADMISSION REFUSED"))
        self.assertIn("HOST_AUTHORITY_UNAVAILABLE", text)
        self.assertIn("[AUTHORITY_UNREACHABLE]", text)
        self.assertIn("SAIPEN host-authority broker", text)
        self.assertIn("automatic recovery attempted [connect]", text)
        self.assertIn("Do this: saipen host repair", text)
        self.assertLessEqual(len(text), PA._MAX_DIAGNOSTIC)
        # ONE action, not a menu of guesses.
        self.assertEqual(verdict["actions"], ["saipen host repair"])
        self.assertFalse((self.world.project / PA.LEDGER_DIR).exists())

    def test_no_environment_variable_and_no_prompt_text_changes_the_answer(self):
        with contextlib.ExitStack() as stack:
            for name in (PA.TRANSPORT_ENV, "SAIPEN_AGENT"):
                stack.enter_context(
                    mock.patch.dict(os.environ, {name: "hook:UserPromptSubmit:forged"})
                )
            verdict = PA.establish(self.world.ctx(), transport="hook:UserPromptSubmit:forged")
        self.assertFalse(verdict["permitted"])
        self.assertEqual(verdict["code"], PA.CODE_TRANSPORT_REQUIRED)
        self.assertEqual(verdict["failure"], "CAPABILITY_FORGED")
        self.assertFalse((self.world.project / PA.LEDGER_DIR).exists())

    def test_the_policy_file_decides_and_only_a_recognized_value_is_obeyed(self):
        empty = self.tmp / "nobody"
        empty.mkdir()
        self.assertEqual(HC.authority_mode(empty), HB.MODE_DEGRADED, "the product default")
        self.assertEqual(HC.authority_mode(self.world.home), HB.MODE_STRICT, "the world chose it")
        mode_file = self.world.home / ".saipen" / "authority.json"
        mode_file.write_text('{"mode": "DEgraded "}', encoding="utf-8")
        self.assertEqual(HC.authority_mode(self.world.home), HB.MODE_DEGRADED)
        mode_file.write_text('{"mode": "whatever"}', encoding="utf-8")
        self.assertEqual(HC.authority_mode(self.world.home), HB.MODE_STRICT)
        self.assertFalse(HC.set_authority_mode("loose", self.world.home)["ok"])

    def test_degraded_permits_the_prompt_claims_nothing_and_writes_no_record(self):
        HC.set_authority_mode("degraded", self.world.home)
        verdict = PA.establish(self.world.ctx())
        self.assertTrue(verdict["permitted"])
        self.assertFalse(verdict["verified"])
        self.assertEqual(verdict["state"], PA.STATE_DEGRADED)
        self.assertEqual(verdict["marker"], PA.DEGRADED_MARKER)
        self.assertIn("=== BOOT.md", verdict["delivery"])
        self.assertIn(PA.DEGRADED_MARKER, verdict["notice"])
        self.assertIn("nothing here claims ADMITTED", verdict["notice"])
        self.assertFalse(PA._ledger_path(self.world.project, "session-1").exists())
        self.assertIsNone(PA.evaluate(self.world.ctx()).get("token"))

    def test_a_missing_authority_document_degrades_and_names_the_repair(self):
        HC.set_authority_mode("degraded", self.world.home)
        (self.world.authority / "saipen" / "EXECUTION.md").unlink()
        verdict = PA.establish(self.world.ctx())
        self.assertTrue(verdict["permitted"])
        self.assertEqual(verdict["state"], PA.STATE_DEGRADED)
        self.assertIn(
            "AUTHORITY_DOCUMENT_UNREADABLE", [p["code"] for p in verdict["problems"]]
        )
        self.assertNotIn("=== EXECUTION.md", verdict["delivery"])
        self.assertIn("=== BOOT.md", verdict["delivery"], "what CAN be delivered still is")


class ClaudeHostPathTests(unittest.TestCase):
    """The shipped service entry as its own PROCESS, the installed hook, and a
    host stand-in that starts the hook the way the host does."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.world = World(self.tmp, mode=None)
        self.host = HostFixture(
            self.tmp,
            home=self.world.home,
            project=self.world.project,
            authority=self.world.authority,
            service="none",
        )
        self.addCleanup(self.host.close)
        if not self.host.available:
            self.skipTest("no stand-in host interpreter on this platform")

    def state(self, session: str = "session-1") -> dict:
        return PA.evaluate(
            self.world.ctx(
                session_id=session,
                model=None,
                provider=PA.provider_fingerprint(),
                runtime=self.host.runtime,
            )
        )

    def test_the_normal_host_path_is_admitted_without_a_magic_phrase(self):
        self.host.start_service_process()
        prompt = self.host.prompt(user_prompt="ordinary request")
        self.assertIn("hookSpecificOutput", prompt, prompt)
        context = prompt["hookSpecificOutput"]["additionalContext"]
        for name in PA.AUTHORITY_DOCUMENTS:
            self.assertIn(f"=== {name} sha256:", context)
        self.assertNotIn("decision", prompt)
        self.assertNotIn("systemMessage", prompt)
        self.assertNotIn("HOST_AUTHORITY_UNAVAILABLE", json.dumps(prompt))
        self.assertEqual(self.state()["state"], PA.STATE_ADMITTED)
        status = HC.status(self.host.runtime)
        self.assertGreaterEqual(status["authenticated_requests"], 1)
        self.assertEqual(status["last_client"]["host_image"], "claude.exe" if WINDOWS else "claude")
        # The session is admitted, so the next prompt is not charged the full
        # delivery again.
        second = self.host.prompt(user_prompt="second request")
        self.assertNotIn("decision", second)
        self.assertNotIn("=== BOOT.md", second["hookSpecificOutput"]["additionalContext"])

    def test_a_host_restart_admits_the_new_session_automatically(self):
        self.host.start_service_process()
        self.host.prompt(user_prompt="one")
        restarted = self.host.prompt(user_prompt="two", session="session-restarted")
        self.assertIn("=== BOOT.md", restarted["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("decision", restarted)
        self.assertEqual(self.state("session-restarted")["state"], PA.STATE_ADMITTED)

    def test_a_killed_service_costs_one_re_delivery_and_never_a_refusal(self):
        self.host.start_service_process()
        self.host.prompt(user_prompt="one")
        self.host.stop_service_process(kill=True)
        # The key that signed the record died with the process, so nothing can
        # verify that record any more. With no service the session is simply
        # not proven: under the default policy the prompt proceeds, marked.
        orphaned = self.host.prompt(user_prompt="two")
        self.assertNotIn("decision", orphaned)
        self.assertIn(PA.DEGRADED_MARKER, orphaned["systemMessage"])
        # The service comes back as a NEW generation and the same session is
        # admitted again, with a fresh delivery.
        self.host.start_service_process()
        recovered = self.host.prompt(user_prompt="three")
        self.assertNotIn("decision", recovered)
        self.assertNotIn("systemMessage", recovered)
        self.assertIn("=== BOOT.md", recovered["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.state()["state"], PA.STATE_ADMITTED)

    def test_a_shell_tool_call_under_the_host_is_refused_by_the_real_service(self):
        self.host.start_service_process()
        HC.set_authority_mode("strict", self.world.home)
        for via in ("tool", "nested"):
            with self.subTest(via=via):
                out = self.host.prompt(via=via, session=f"session-{via}")
                self.assertEqual(out["decision"], "block")
                self.assertIn("AUTHORITY_CLIENT_UNPROVEN", out["reason"])
                self.assertIn(HI.REASON_HOOK_CHAIN_UNRECOGNIZED, out["reason"])
                self.assertFalse(
                    PA._ledger_path(self.world.project, f"session-{via}").exists()
                )
        self.assertGreaterEqual(HC.status(self.host.runtime)["refused_requests"], 2)

    def test_an_absent_service_is_started_by_the_hook_and_the_shipped_policy_is_enforced(self):
        # The DEFAULT endpoint of a disposable profile, with nothing overridden:
        # the hook starts the service by itself, and that service -- under the
        # shipped policy -- refuses a host image that carries this
        # interpreter's publisher instead of the host's. The prompt is not
        # locked out by that: the default policy lets it proceed, marked.
        runtime = isolate_profile(self, self.tmp)
        self.addCleanup(self.stop_default_service, runtime)
        self.host.explicit_endpoint = False
        self.assertFalse(HB.health(runtime))
        prompt = self.host.run(
            {"hook_event_name": "UserPromptSubmit", "user_prompt": "first prompt"},
            env=self.profile_env(),
        )
        self.assertNotIn("decision", prompt, prompt)
        self.assertTrue(HB.health(runtime), "the hook did not start the authority service")
        started = HB.read_status(runtime)
        self.assertTrue(started and started.get("pid"))
        if HB.proc.signing_supported():
            self.assertIn("AUTHORITY_CLIENT_UNPROVEN", prompt["systemMessage"])
            refusal = HC.status(runtime)["last_refusal"]
            self.assertEqual(refusal["reason"], HI.REASON_HOST_IMAGE_UNVERIFIED)
            self.assertFalse(PA._ledger_path(self.world.project, "session-1").exists())
        # STRICT turns the same refusal into a block that names what was tried.
        HC.set_authority_mode("strict", self.world.home)
        blocked = self.host.run(
            {"hook_event_name": "UserPromptSubmit", "user_prompt": "second prompt"},
            env=self.profile_env(),
        )
        if HB.proc.signing_supported():
            self.assertEqual(blocked["decision"], "block")
            self.assertIn("Do this:", blocked["reason"])

    def test_a_tool_call_under_the_host_never_starts_the_service(self):
        # The same disposable profile and the same absent service, but the
        # caller is a command the host's shell TOOL ran, not the host's hook.
        # While "a host application is above me" decided the start, this call
        # launched a real service on the default endpoint -- from a suite run
        # inside a host session that endpoint is the operator's -- only for
        # that service to refuse the very caller it was started for.
        runtime = isolate_profile(self, self.tmp)
        self.addCleanup(self.stop_default_service, runtime)
        self.host.explicit_endpoint = False
        for via in ("tool", "nested"):
            with self.subTest(via=via):
                prompt = self.host.run(
                    {"hook_event_name": "UserPromptSubmit", "user_prompt": "a tool call"},
                    session=f"session-{via}",
                    via=via,
                    env=self.profile_env(),
                )
                # Not locked out either: the default policy lets it proceed,
                # marked, with the truthful reason that nothing answered.
                self.assertNotIn("decision", prompt, prompt)
                self.assertIn("AUTHORITY_UNREACHABLE", prompt["systemMessage"])
                self.assertFalse(HB.health(runtime), "a non-hook caller started the service")
                self.assertIsNone(HB.read_status(runtime))
                self.assertFalse(PA._ledger_path(self.world.project, f"session-{via}").exists())

    def profile_env(self) -> dict:
        return {
            key: os.environ[key]
            for key in ("USERPROFILE", "HOME", "HOMEDRIVE", "HOMEPATH")
            if key in os.environ
        }

    def stop_default_service(self, runtime: Path) -> None:
        stored = HB.read_status(runtime) or {}
        pid = stored.get("pid")
        with contextlib.suppress(Exception):
            HB.request({"op": "shutdown"}, runtime=runtime, timeout=2.0)
        deadline = time.time() + 12.0
        while time.time() < deadline and HB.health(runtime, timeout=0.3):
            time.sleep(0.2)
        if pid and HB._pid_alive(int(pid)):
            with contextlib.suppress(OSError, TypeError, ValueError):
                os.kill(int(pid), 9)
            deadline = time.time() + 12.0
            while time.time() < deadline and HB._pid_alive(int(pid)):
                time.sleep(0.2)


if __name__ == "__main__":
    unittest.main()
