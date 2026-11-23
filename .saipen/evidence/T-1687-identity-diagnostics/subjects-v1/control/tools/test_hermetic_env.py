"""Hermetic test environment: an outer host session never binds a fixture.

Production SAIPEN honours the host/session carriers on purpose -- a verified
`SAIPEN_PROJECT_ROOT`/`SAIPEN_PROJECT_LINEAGE` pair outranks the Git worktree,
`SAIPEN_AGENT` names the acting seat, `SAIPEN_CAPABILITY` narrows the session.
A test suite launched from inside such a session (an OpenCode seat running
`python -m unittest`) inherits all of them. Every fixture that resolves a
project, spawns the CLI or drives the guard then binds the OPERATOR's live
project instead of its disposable one: measured with a valid foreign binding,
eleven guard/adapter/recovery families failed and the fixtures ran their
recovery against the foreign project.

The repair belongs to the harness, never to the production binding checks:
`isolate_host_session()` removes the host-session carriers for the lifetime of
one test module and restores them afterwards. A test that verifies binding
inheritance sets the carriers it is testing explicitly, exactly as before.

Usage, once per test module that builds SAIPEN fixtures::

    from test_hermetic_env import isolate_host_session

    def setUpModule() -> None:
        isolate_host_session()
"""

from __future__ import annotations

import os
import contextlib
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

#: Every variable through which a HOST SESSION declares something the engine
#: or a host adapter acts on. None of them is test input unless a test sets it.
HOST_SESSION_VARIABLES = (
    "SAIPEN_AUTONOMY_RUN_ID",
    "SAIPEN_AUTONOMY_WORKER",
    "SAIPEN_LEASE_GENERATION",
    "SAIPEN_PROJECT_ROOT",
    "SAIPEN_PROJECT_LINEAGE",
    "SAIPEN_AGENT",
    "SAIPEN_CAPABILITY",
    "SAIPEN_HOST_ENFORCEMENT",
    "SAIPEN_RUNTIME_INFO",
    "SAIPEN_SKILL_ROOT",
    "SAIPEN_GUARD_STARTUP_PROBE",
    # T-1442: the host adapter's session carrier. Inherited, it made a fixture's
    # parent read as claimed in the operator's session: test_continue_chain and
    # test_conformance_repair_boundary failed inside a live host session and
    # passed outside one. `paths.PROJECT_BINDING_ENV` already names it; the
    # tripwire below keeps this list a superset of that one.
    "SAIPEN_HOST_SESSION",
    # SAIGPU: an operator's `SAIPEN_GPU=on` would start a real GPU lane beside
    # every fixture `supervise`; stripped, the fixture's own (absent) switch
    # decides, which is OFF.
    "SAIPEN_GPU",
    # T-1497: the operator's SAIMAIL mailbox; set, every fixture `continue`
    # would read a real inbox at turn entry.
    "SAIMAIL_WORKSPACE",
    # T-1504: the operator's ZAICODE HOME; set, an injector fixture that only
    # redirects USERPROFILE would install into the real ZAICODE profile.
    "ZAICODE_HOME",
    # T-1685: the operator's Claude configuration profile. It outranks HOME in
    # `claude_profiles.directory`, so an installer fixture that only redirects
    # HOME wrote hooks, settings and a skill into the live second profile.
    "CLAUDE_CONFIG_DIR",
)

#: T-1343. The interlock `saipen_engine.host_launch` checks before it creates a
#: host process. It is SET by the harness rather than stripped by it: a fixture
#: that reaches the spawn boundary did so because a stub was missed, and a
#: missed stub is exactly the case that cannot be caught by inspecting the
#: fixture. The T-1327 launch test patched a different module object of the
#: same file, the real prelaunch ran, and the operator's real OpenCode host
#: started and hung the suite.
#:
#: A module that MEANS to start a real host clears it in the child environment
#: it builds (`hermetic_env(..., SAIPEN_FORBID_HOST_SPAWN=None)`), so the
#: intent is one reviewable line instead of a silent default.
FORBID_HOST_SPAWN = "SAIPEN_FORBID_HOST_SPAWN"

#: T-1647. Where the engine looks for the machine runtime. Like the interlock
#: above it is SET, not stripped: the machine runtime is one directory for the
#: whole machine, so a fixture that reads it sees the operator's real install,
#: and a fixture that repairs "its" hosts would refresh that install from a
#: test tree. Pointed at a path that does not exist, every fixture finds no
#: machine runtime unless it builds one and names it.
MACHINE_ROOT = "SAIPEN_MACHINE_ROOT"


def no_machine_runtime() -> str:
    """A machine-runtime root that never exists, one per test process."""
    return str(Path(tempfile.gettempdir()) / f"saipen-no-machine-runtime-{os.getpid()}")


#: T-1662. The repository this file runs from, named so that no engine process
#: a test starts may write its project memory. A child that loses its explicit
#: root binds the working directory's project, and from inside the repository
#: that project is the repository: the write succeeds against the wrong ledger
#: and nothing fails. Like the two above it is SET, not stripped -- and its name
#: does not open with `SAIPEN`, because a helper that drops every variable
#: that does (many modules build a child environment that way) must not be
#: able to drop this one.
FORBID_PROJECT_WRITE = "FORBID_SAIPEN_PROJECT_WRITE"
REPOSITORY_ROOT = str(Path(__file__).resolve().parent.parent)


#: T-1353. The isolation snapshot lives HERE, in one process-global record,
#: not in this module's globals.
#:
#: `python -m unittest tools.test_a tools.test_b` loads the named modules under
#: the DOTTED spelling while those modules flat-import their siblings, so this
#: file can be two live module objects in one interpreter -- measured: the mix
#: produces two `test_hermetic_env`. Two copies each holding their own snapshot
#: each strip and each restore, and the second restore puts back what the first
#: already restored: the environment is repaired twice from two different
#: pictures of "before", inside the layer every other fixture trusts for its
#: isolation. A registry keyed in `sys.modules` is reached identically by every
#: copy, so they cooperate instead of racing.
_REGISTRY_NAME = "_saipen_hermetic_isolation"


def _registry() -> types.SimpleNamespace:
    record = sys.modules.get(_REGISTRY_NAME)
    if record is None:
        record = types.ModuleType(_REGISTRY_NAME)
        record.depth = 0
        record.removed = {}
        record.previous_interlock = None
        sys.modules[_REGISTRY_NAME] = record
    return record


def isolate_authority_endpoint() -> None:
    """Point this module's DEFAULT authority endpoint at one nothing serves.

    T-1624. The separated host-authority service is per user, so a suite run on
    a machine where it is alive talked to it: admission tests passed with no
    service running and failed with one, and every such run left refusals in
    the operator's live service. A fixture that wants a service starts its own
    on an explicit runtime root; everything else must meet an empty endpoint.

    In-process only, and only the default: an explicit runtime root is used as
    given. Nothing is started on the isolated endpoint either -- the automatic
    start would launch a real service process for the operator's real root.

    Applied ONCE per process and undone by `restore_authority_endpoint`, which
    the last `isolate_host_session` cleanup calls: the state lives in the same
    registry as the carriers. It first registered three module cleanups of its
    own per call, which stacked a patch on a patch for every nested isolation
    and put callables with arguments in front of the one restore each
    isolation owns -- the harness's own reference-count controls went red.
    """
    record = _registry()
    if getattr(record, "authority", None) is not None:
        return
    tools = str(Path(__file__).resolve().parent)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from saipen_engine import host_authority_broker as broker
    from saipen_engine import host_authority_client as client

    isolated = Path(tempfile.mkdtemp(prefix="saipen-test-authority-"))
    original_root = broker.runtime_root
    original_ensure = client.ensure

    def runtime_root(explicit=None):
        return Path(explicit) if explicit is not None else isolated

    def ensure(saipen_root=None, *, runtime=None, wait=6.0, force=False, **scope):
        if runtime is not None:
            return original_ensure(
                saipen_root, runtime=runtime, wait=wait, force=force, **scope
            )
        return {
            "ok": False,
            "state": "isolated_test_endpoint",
            "found": False,
            "started": False,
            "attempts": 1,
            "detail": "the suite's isolated authority endpoint is never started",
        }

    broker.runtime_root = runtime_root
    client.ensure = ensure
    record.authority = (broker, client, original_root, original_ensure, isolated)


def restore_authority_endpoint() -> None:
    """Undo `isolate_authority_endpoint`. Safe to call when nothing is isolated."""
    record = _registry()
    held = getattr(record, "authority", None)
    if held is None:
        return
    broker, client, original_root, original_ensure, isolated = held
    broker.runtime_root = original_root
    client.ensure = original_ensure
    record.authority = None
    shutil.rmtree(isolated, True)


def isolated_authority_runtime() -> Path:
    """The unserved authority endpoint root of this isolation, for a CHILD.

    The isolation above is in-process. A hook or CLI a test starts resolves the
    default endpoint again, from the operator's real profile: its verdict was
    then the live service's, and one module's hook cases went red only on a
    machine whose service was alive. Such a child is handed this root
    explicitly (`--runtime`); an explicit root is also never started, so the
    child cannot launch a service either.

    Raises when the default endpoint is NOT isolated: handing a child the
    operator's real root while believing it disposable is the failure this
    exists to prevent, and it must not be reachable by forgetting a call.
    """
    tools = str(Path(__file__).resolve().parent)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from saipen_engine import host_authority_broker as broker

    root = Path(broker.runtime_root())
    if root == Path.home() / ".saipen" / "authority":
        raise RuntimeError(
            "the authority endpoint is not isolated: call isolate_host_session() "
            "in setUpModule before starting a child that may ask an authority"
        )
    return root


def isolate_host_session() -> dict[str, str]:
    """Remove host-session carriers now; restore them when the module ends.

    Call from `setUpModule`. The removed values are returned for diagnostics
    and put back by a module cleanup, so the next module -- and the operator's
    shell -- sees the environment exactly as it was.

    It also arms the real-host spawn interlock for the lifetime of the module
    (see `FORBID_HOST_SPAWN`); that too is undone by the cleanup.

    Reference-counted across every copy of this file (see `_REGISTRY_NAME`):
    the FIRST call takes the picture and strips, later calls only raise the
    count, and the environment is restored exactly once, by the last cleanup
    to run. Nesting is therefore safe, and so is being imported twice.
    """
    record = _registry()
    if record.depth == 0:
        record.removed = {
            key: os.environ.pop(key) for key in HOST_SESSION_VARIABLES if key in os.environ
        }
        record.previous_interlock = os.environ.get(FORBID_HOST_SPAWN)
        record.previous_machine_root = os.environ.get(MACHINE_ROOT)
        record.previous_project_write = os.environ.get(FORBID_PROJECT_WRITE)
    else:
        for key in HOST_SESSION_VARIABLES:
            os.environ.pop(key, None)
    record.depth += 1
    os.environ[FORBID_HOST_SPAWN] = "1"
    os.environ[MACHINE_ROOT] = no_machine_runtime()
    os.environ[FORBID_PROJECT_WRITE] = REPOSITORY_ROOT
    # T-1624: the operator's live authority service is host-session state too.
    isolate_authority_endpoint()

    def restore() -> None:
        record.depth -= 1
        # An intermediate cleanup still STRIPS. Only the restore of the
        # original picture waits for the last one. A module that sets a
        # carrier on purpose -- the binding-inheritance tests do -- must not
        # leak it into whatever module runs next just because another
        # isolation is still open, which is what returning early here without
        # stripping would have caused.
        for key in HOST_SESSION_VARIABLES:
            os.environ.pop(key, None)
        if record.depth > 0:
            os.environ[FORBID_HOST_SPAWN] = "1"
            os.environ[MACHINE_ROOT] = no_machine_runtime()
            os.environ[FORBID_PROJECT_WRITE] = REPOSITORY_ROOT
            return
        restore_authority_endpoint()
        os.environ.update(record.removed)
        if record.previous_interlock is None:
            os.environ.pop(FORBID_HOST_SPAWN, None)
        else:
            os.environ[FORBID_HOST_SPAWN] = record.previous_interlock
        previous_machine_root = getattr(record, "previous_machine_root", None)
        if previous_machine_root is None:
            os.environ.pop(MACHINE_ROOT, None)
        else:
            os.environ[MACHINE_ROOT] = previous_machine_root
        previous_project_write = getattr(record, "previous_project_write", None)
        if previous_project_write is None:
            os.environ.pop(FORBID_PROJECT_WRITE, None)
        else:
            os.environ[FORBID_PROJECT_WRITE] = previous_project_write
        record.removed = {}
        record.previous_interlock = None
        record.previous_machine_root = None
        record.previous_project_write = None

    unittest.addModuleCleanup(restore)
    return dict(record.removed)


@contextlib.contextmanager
def nested_run():
    """Protect outer module cleanups while a test runs an inner unittest suite.

    unittest drains its process-wide cleanup list at the end of each suite.
    Only cleanups registered inside this block belong to the nested run;
    restoring the outer list preserves its order even when the inner run fails.
    """
    cleanups = unittest.case._module_cleanups
    held = list(cleanups)
    del cleanups[:]
    try:
        yield
    finally:
        cleanups[:0] = held


def borrow(test: unittest.TestCase) -> unittest.TestResult:
    """Run one test without module/class fixtures or an outer suite teardown."""
    fixtures = (type(test).setUpClass, type(test).tearDownClass)
    inherited = (unittest.TestCase.setUpClass, unittest.TestCase.tearDownClass)
    if any(own.__func__ is not base.__func__ for own, base in zip(fixtures, inherited)):
        raise ValueError(
            f"{type(test).__qualname__} has a class fixture; use nested_run() with a suite"
        )
    result = unittest.TestResult()
    with nested_run():
        test.run(result)
    return result


def project_write_interlock() -> str | None:
    """Observe the held repository through the interlock's owning test helper."""
    return os.environ.get(FORBID_PROJECT_WRITE)


def retained_fixtures() -> list:
    """The process-global list that keeps disposable fixtures alive.

    T-1353, same reason as the isolation registry: a module that holds its
    `TemporaryDirectory` handles in its own globals holds them once PER COPY,
    and a copy that goes out of scope takes its handles' directories with it
    while another copy's assertions are still reading them.
    """
    record = _registry()
    if not hasattr(record, "fixtures"):
        record.fixtures = []
    return record.fixtures


def hermetic_env(base: dict[str, str] | None = None, **overrides: str | None) -> dict[str, str]:
    """A child-process environment with no host-session carrier.

    `overrides` are applied last; a value of None removes the key. Use it where
    a subprocess must be hermetic independent of module setup.

    The real-host spawn interlock travels INTO the child by default, because a
    child that reaches the spawn boundary is the same accident as a parent that
    does. Pass `SAIPEN_FORBID_HOST_SPAWN=None` to run a deliberate real-host
    smoke.
    """
    env = dict(os.environ if base is None else base)
    for key in HOST_SESSION_VARIABLES:
        env.pop(key, None)
    env[FORBID_HOST_SPAWN] = "1"
    env[MACHINE_ROOT] = no_machine_runtime()
    env[FORBID_PROJECT_WRITE] = REPOSITORY_ROOT
    for key, value in overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return env


_HOSTILE = (
    ("SAIPEN_PROJECT_ROOT", str(Path(tempfile.gettempdir()) / "saipen-foreign-project")),
    ("SAIPEN_PROJECT_LINEAGE", "lineage-" + "f" * 32),
    ("SAIPEN_AGENT", "foreign-seat"),
)


class HermeticEnvironmentTests(unittest.TestCase):
    """The helper itself: hostile outer values never reach a fixture."""

    def test_hermetic_env_strips_every_carrier_and_keeps_overrides(self) -> None:
        base = {**dict(_HOSTILE), "PATH": os.environ.get("PATH", ""), "KEEP": "1"}
        env = hermetic_env(base, SAIPEN_AGENT="fixture-seat", KEEP=None)
        for key in HOST_SESSION_VARIABLES:
            if key != "SAIPEN_AGENT":
                self.assertNotIn(key, env)
        self.assertEqual(env["SAIPEN_AGENT"], "fixture-seat")
        self.assertNotIn("KEEP", env)

    def test_a_child_process_sees_no_outer_binding(self) -> None:
        env = hermetic_env({**os.environ, **dict(_HOSTILE)})
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                "import json, os; print(json.dumps({k: os.environ.get(k) for k in "
                + repr(list(HOST_SESSION_VARIABLES))
                + "}))",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
            check=True,
        )
        self.assertNotIn("foreign", probe.stdout)
        self.assertNotIn("lineage-", probe.stdout)

    def test_every_engine_binding_carrier_is_stripped(self) -> None:
        """T-1442: one owner. The engine's own list of project-binding carriers
        (`paths.PROJECT_BINDING_ENV`) is what production treats as a binding;
        the harness must strip every SAIPEN_ name in it."""
        tools = str(Path(__file__).resolve().parent)
        if tools not in sys.path:
            sys.path.insert(0, tools)
        from saipen_engine.paths import PROJECT_BINDING_ENV

        engine = {name for name in PROJECT_BINDING_ENV if name.startswith("SAIPEN_")}
        self.assertIn("SAIPEN_HOST_SESSION", engine)
        self.assertEqual(sorted(engine - set(HOST_SESSION_VARIABLES)), [])


if __name__ == "__main__":
    unittest.main()
