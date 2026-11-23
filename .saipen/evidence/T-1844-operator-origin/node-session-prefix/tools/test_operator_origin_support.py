"""Explicitly simulated native-event owner for legacy and cold CLI fixtures.

Only this test wrapper redirects the client to its disposable endpoint. The
real broker, HMAC ledger, Sources and goal journals are exercised. Native client
identity and registered worker facts are simulated, as in the kernel controls;
this is never evidence of an actual host/UI or a production endpoint admission.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
import runpy
import subprocess
import sys
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock
from uuid import uuid4

from saipen_engine import host_authority_broker as HB, host_authority_client as HC
from saipen_engine import host_authority_process as HP, host_authority_transport as HT
from saipen_engine import operator_task as OT
import test_t1844_origin_broker as controls

ORIGIN_OPS = frozenset({
    "issue-origin", "register-origin-worker", "revoke-origin", "verify-origin",
    "verify-source-origin", "prepare-origin-goal", "verify-origin-goal",
})


class SimulatedOperatorHost:
    def __init__(self):
        self.fixture = controls.OriginKernelWithSimulatedNativeIdentity()
        self.fixture.setUp()
        self.runtime = Path(self.fixture.tmp.name) / "cold-endpoint"
        self.runtime.mkdir()
        self.workers = {}
        self.event_workers = {}
        self.next_pid = 1000
        self.session = "simulated-native-" + uuid4().hex
        self.stop = threading.Event()
        self.thread = threading.Thread(
            target=HT.serve,
            kwargs={"name": HB.endpoint_name(self.runtime), "handler": self.handle,
                    "stop": self.stop},
            daemon=True,
        )
        self.thread.start()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if HB.health(self.runtime, timeout=0.5):
                break
            time.sleep(0.01)
        else:
            self.close()
            raise AssertionError("simulated operator endpoint did not start")

    def handle(self, payload, _transport_peer):
        # This is the explicitly simulated OS identity boundary, not the real
        # service's authenticator. The production client and broker stay strict.
        return self.fixture.broker.handle(payload, self.fixture.peer)

    def select(self, root):
        self.fixture.root = Path(root)
        pid = self.workers.get(str(Path(root).resolve()), 21)
        self.fixture.peer = SimpleNamespace(pid=pid, kind="simulated-worker")

    def offer(self, root, text, *, action, event_id=None):
        self.select(root)
        event = event_id or uuid4().hex
        issued = self.fixture.broker.handle(
            {"op": "issue-origin", "project": str(root), "session": self.session,
             "host": "claude", "event": "UserPromptSubmit", "request_text": text,
             "event_id": event, "action": action},
            self.fixture.native_peer,
        )
        if not issued.get("ok"):
            # An invalid human capsule is still invalid. Do not fabricate an
            # issuer positive so a consumer's refusal test can proceed.
            return None
        proof = issued["proof"]
        self.next_pid += 1
        pid = self.next_pid
        self.fixture.facts[pid] = HP.ProcessFact(
            pid, 10, "simulated-worker.exe", "fixture worker", created=pid,
        )
        self.fixture.register(proof, worker=pid)
        self.workers[str(Path(root).resolve())] = pid
        self.event_workers[proof["nonce"]] = pid
        self.select(root)
        admitted = OT.admit_host_ingress(
            {"request_text": text, "session_id": self.session, "message_id": event,
             "operator_origin": proof}, root,
        )
        if not admitted.get("ok"):
            raise AssertionError(admitted)
        return proof

    def select_source(self, root, receipt):
        from saipen_engine import intake

        found = intake.read_body(root, receipt)
        provenance = (found.get("meta") or {}).get("request_provenance") or {}
        proof = provenance.get("operator_origin") or {}
        pid = self.event_workers.get(proof.get("nonce"))
        if pid is not None:
            self.fixture.peer = SimpleNamespace(pid=pid, kind="simulated-source-worker")

    @contextlib.contextmanager
    def direct(self, root, text=None, *, action="goal", event_id=None):
        self.select(root)
        if text is not None:
            self.offer(root, text, action=action, event_id=event_id)
        original = HC._call

        def client(payload, *, runtime, timeout):
            if payload.get("op") not in ORIGIN_OPS:
                return original(payload, runtime=runtime, timeout=timeout)
            return self.fixture.bridge(payload, runtime=runtime, timeout=timeout)

        with mock.patch.dict(os.environ, {OT.ENV_HOST_SESSION: self.session}), mock.patch.object(
            HC, "_call", side_effect=client,
        ):
            yield self

    def close(self):
        self.stop.set()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            raise AssertionError("simulated operator endpoint did not stop")
        self.fixture.doCleanups()


_registry = SimpleNamespace(host=None)


def host_for(root, *, create=False):
    if _registry.host is None and create:
        _registry.host = SimulatedOperatorHost()
        current = _registry.host
        original = HC._call

        def client(payload, *, runtime, timeout):
            if payload.get("op") not in ORIGIN_OPS:
                return original(payload, runtime=runtime, timeout=timeout)
            if payload.get("project"):
                current.select(payload["project"])
            return current.fixture.bridge(payload, runtime=runtime, timeout=timeout)

        patcher = mock.patch.object(HC, "_call", side_effect=client)
        patcher.start()

        def cleanup():
            patcher.stop()
            current.close()
            if _registry.host is current:
                _registry.host = None

        unittest.addModuleCleanup(cleanup)
    if _registry.host is not None:
        _registry.host.select(root)
    return _registry.host


@contextlib.contextmanager
def native_operator(root, text=None, *, action="goal", event_id=None):
    with host_for(root, create=True).direct(root, text, action=action, event_id=event_id) as host:
        yield host


def use_case_owner(case, root):
    """Keep the isolated issuer reachable for later direct proof queries."""
    host = host_for(root, create=True)
    if not getattr(case, "_operator_owner_installed", False):
        original = HC._call

        def client(payload, *, runtime, timeout):
            if payload.get("op") not in ORIGIN_OPS:
                return original(payload, runtime=runtime, timeout=timeout)
            host.select(payload.get("project") or root)
            return host.fixture.bridge(payload, runtime=runtime, timeout=timeout)

        patcher = mock.patch.object(HC, "_call", side_effect=client)
        patcher.start()
        case.addCleanup(patcher.stop)
        case._operator_owner_installed = True
    return host


def cold_command(root, command, env, *, operator_text=None, action=None):
    host = host_for(root, create=operator_text is not None)
    if host is None or (
        operator_text is None and str(Path(root).resolve()) not in host.workers
    ):
        return command
    if operator_text is not None:
        # These legacy START fixtures describe fresh objectives. Their native
        # event grants that objective, while kernel controls separately retain
        # the narrower start/report/continue permissions.
        intended = "continue" if any(a in ("continue", "cc", "ccc") for a in command[2:]) \
            else "goal"
        if "goal" in command[2:] and "authorize" in command[2:]:
            intended = "authorize-goal"
        host.offer(root, operator_text, action=action or intended)
    elif "--receipt" in command:
        index = command.index("--receipt")
        if index + 1 < len(command):
            host.select_source(root, command[index + 1])
    env[OT.ENV_HOST_SESSION] = host.session
    index = 1
    while command[index] in ("-B", "-u"):
        index += 1
    return [*command[:index], str(Path(__file__).resolve()), "--cold-cli", str(host.runtime),
            *command[index:]]


def _cold_main():
    runtime, script, *args = sys.argv[2:]
    original = HC._call

    def fixture_call(payload, *, runtime=None, timeout):
        selected = Path(endpoint) if payload.get("op") in ORIGIN_OPS else runtime
        return original(payload, runtime=selected, timeout=timeout)

    endpoint = runtime
    original_popen = subprocess.Popen
    tools = Path(__file__).resolve().parent
    nested_entries = {tools / "saipen.py", tools / "validate.py"}

    def fixture_popen(command, *positional, **options):
        # Keep the actual nested validator/CLI, including its failure modes.
        # Only its diagnostic broker transport follows this simulated host.
        if (isinstance(command, (list, tuple)) and len(command) >= 2
                and Path(command[0]).resolve() == Path(sys.executable).resolve()
                and Path(command[1]).resolve() in nested_entries):
            command = [command[0], str(Path(__file__).resolve()), "--cold-cli", endpoint,
                       *command[1:]]
        return original_popen(command, *positional, **options)

    sys.argv = [script, *args]
    with mock.patch.object(HC, "_call", side_effect=fixture_call), \
            mock.patch.object(subprocess, "Popen", side_effect=fixture_popen):
        runpy.run_path(script, run_name="__main__")


if __name__ == "__main__" and sys.argv[1:2] == ["--cold-cli"]:
    _cold_main()
