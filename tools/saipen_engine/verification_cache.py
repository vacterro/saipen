"""Compatible verification identities and single-flight over existing OS locks.

This coordinates executions, never creates PASS. Every shared result is read
from an intact actual execution record; FAIL stays FAIL. Old records remain
readable but cannot establish newly required environment compatibility.
"""

from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path

from .lock import FileLockBusy, FileWriterLock
from .paths import (
    prove_owned_dir_chain,
    prove_owned_regular,
    read_bound_regular_bytes,
    safe_atomic_write_bytes,
)

_ACTIVE = contextvars.ContextVar("saipen_verification_flight", default=None)
_TOOLS = (
    "git",
    "node",
    "npm",
    "npx",
    "bash",
    "pwsh",
    "powershell",
    "opencode",
    "claude",
    "codex",
    "ruff",
)
_VERIFIERS = (
    "core_unit.py",
    "core_unit_shard.py",
    "test_runner.py",
    "focused_unit.py",
    "verification_cache.py",
    "process_tree.py",
    "verification_bootstrap.py",
    "verification_impact.py",
)


def _json_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()


def digest(value) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def file_identity(path: Path) -> dict:
    path = path.resolve()
    if not path.exists():
        return {"path": str(path), "exists": False}
    if not path.is_file():
        raise ValueError(f"verification dependency is not a regular file: {path}")
    before = path.stat()
    with path.open("rb") as stream:
        hashed = hashlib.file_digest(stream, "sha256").hexdigest()
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise ValueError(f"verification dependency changed while hashing: {path}")
    return {"path": str(path), "exists": True, "sha256": hashed}


_NPM_PACKAGES = {
    "npm": "npm",
    "npx": "npm",
    "codex": "@openai/codex",
    "opencode": "opencode-ai",
    "claude": "@anthropic-ai/claude-code",
}


def _package_identity(root: Path, memo: dict) -> dict:
    """Bind script shims to their actual installed runtime and declared dependencies."""
    from .core_unit import tree_fingerprint

    root = root.resolve()
    key = str(root)
    if "node_modules" not in root.parts:
        return {"root": key, "unknown_runtime_closure": True}
    if key in memo:
        return {"reference": key}
    memo[key] = True
    metadata = json.loads((root / "package.json").read_text(encoding="utf-8"))
    dependencies = {}
    for name in sorted(
        {**(metadata.get("dependencies") or {}), **(metadata.get("optionalDependencies") or {})}
    ):
        if not re.fullmatch(r"(?:@[a-zA-Z0-9_.-]+/)?[a-zA-Z0-9_.-]+", name) or name in {".", ".."}:
            raise ValueError("verification runtime declares an unsafe dependency name")
        found = next(
            (
                parent / "node_modules" / name
                for parent in (root, *root.parents)
                if (parent / "node_modules" / name / "package.json").is_file()
            ),
            None,
        )
        dependencies[name] = _package_identity(found, memo) if found else None
    return {
        "root": key,
        "tree_sha256": tree_fingerprint(root, exclude_top=(".git",)),
        "dependencies": dependencies,
    }


def _tool_identity(name: str, path: str | None, memo: dict) -> dict | None:
    if not path:
        return None
    resolved = Path(path).resolve()
    value = file_identity(resolved)
    # An unrelated package.json in a user-home ancestor is not this executable's
    # runtime. Never turn an identity probe into a walk over the whole profile.
    package = next(
        (
            p
            for p in resolved.parents
            if "node_modules" in p.parts and (p / "package.json").is_file()
        ),
        None,
    )
    if package is None and name in _NPM_PACKAGES and resolved.suffix.lower() in {".cmd", ".ps1"}:
        candidate = resolved.parent / "node_modules" / _NPM_PACKAGES[name]
        if (candidate / "package.json").is_file():
            package = candidate
        else:
            value["unknown_runtime_closure"] = True
    if package is not None:
        value["package"] = _package_identity(package, memo)
    return value


#: T-1865: which names decide identity. A record captured before this rule
#: hashed the whole environment, so it agrees with no capture taken after it --
#: not because its tree changed, but because the question changed. Naming the
#: rule makes that difference legible instead of surfacing as the generic
#: "missing or incompatible verification environment identity".
IDENTITY_RULE = "canonical-child-2"


def capture(root: Path, configuration: dict) -> dict:
    """Observed compatibility, with no raw inherited environment values stored.

    Live external service/host acceptance remains at its owning fresh gate; a
    generic unit result does not authorize that separate acceptance.
    """
    from .test_runner import TestFamily, family_environment, identity_environment

    env = family_environment(TestFamily("identity", (sys.executable,), 1))
    home = Path.home()
    codex_home = Path(env.get("CODEX_HOME") or home / ".codex")
    config_paths = [
        codex_home / "config.toml",
        codex_home / "hooks.json",
        home / ".claude/settings.json",
        home / ".config/opencode/opencode.json",
        home / ".config/opencode/plugins/saipen-guard.js",
        home / ".config/opencode/plugin/saipen-guard.js",
        home / ".gitconfig",
        home / ".config/git/config",
    ]
    if env.get("APPDATA"):
        config_paths.extend(
            [
                Path(env["APPDATA"]) / "opencode/opencode.json",
                Path(env["APPDATA"]) / "opencode/plugins/saipen-guard.js",
            ]
        )
    interpreter = Path(sys.executable)
    runtime = [interpreter]
    if os.name == "nt":
        runtime.append(
            interpreter.parent / f"python{sys.version_info.major}{sys.version_info.minor}.dll"
        )
    names = configuration.get("environment_tools")
    if names is None:
        names = _TOOLS
    if not isinstance(names, (list, tuple)) or any(not isinstance(name, str) for name in names):
        raise ValueError("verification environment tool scope must be a declared list")
    tools = {name: shutil.which(name, path=env.get("PATH")) for name in names}
    for variable in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM"):
        if env.get(variable):
            config_paths.append(Path(env[variable]))
    memo = {}
    return {
        "schema": 1,
        "configuration": configuration,
        "python": {
            "version": sys.version,
            "implementation": sys.implementation.name,
            "prefix": sys.prefix,
            "runtime": [file_identity(p) for p in runtime],
        },
        "platform": {
            "os": os.name,
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "node": platform.node(),
        },
        "environment_sha256": digest(identity_environment(env)),
        "identity_rule": IDENTITY_RULE,
        "toolchain": {name: _tool_identity(name, path, memo) for name, path in tools.items()},
        "configuration_files": [file_identity(path) for path in config_paths],
        "verifiers": {name: file_identity(Path(__file__).with_name(name)) for name in _VERIFIERS},
        "baseline": file_identity(root / "tools/core_unit_baseline.json"),
    }


def compatible(root: Path, recorded: object) -> bool:
    if not isinstance(recorded, dict) or not isinstance(recorded.get("configuration"), dict):
        return False
    try:
        return recorded == capture(root, recorded["configuration"])
    except (OSError, ValueError):
        return False


def incompatibility(recorded: object) -> str | None:
    """Why a record cannot establish compatibility, or None when it does.

    A refusal that names only "incompatible" leaves the reader unable to tell a
    changed TREE (re-run and the answer changes) from an identity captured
    under an older RULE (re-running is the only way forward, and it will
    succeed). Both are legitimate refusals; they are not the same instruction.
    """
    if not isinstance(recorded, dict) or not isinstance(recorded.get("configuration"), dict):
        return "record carries no verification environment identity"
    rule = recorded.get("identity_rule")
    if rule != IDENTITY_RULE:
        return (
            f"record was captured under verification identity rule {rule or 'legacy (pre-rule)'}; "
            f"this engine requires {IDENTITY_RULE} -- re-run the verifier to capture a current record"
        )
    return None


def replay_supported(recorded: dict) -> bool:
    def unknown(value):
        if isinstance(value, dict):
            return value.get("unknown_runtime_closure") is True or any(
                unknown(child) for child in value.values()
            )
        return isinstance(value, list) and any(unknown(child) for child in value)

    return not unknown(recorded.get("toolchain") or {})


def _write(root: Path, path: Path, payload: dict):
    safe_atomic_write_bytes(
        path, _json_bytes(payload), kind="verification flight", ownership_root=root
    )


def _read_state(root: Path, path: Path) -> dict:
    try:
        prove_owned_dir_chain(path.parent, kind="verification state", ownership_root=root)
        info = prove_owned_regular(path, kind="verification state")
        value = json.loads(read_bound_regular_bytes(path, info, max_bytes=256 * 1024))
    except FileNotFoundError:
        return {}
    if not isinstance(value, dict):
        raise ValueError("verification state is not an object")
    if not isinstance(value.get("project"), str):
        raise ValueError("verification state has no local project binding")
    if value["project"] != str(root.resolve()):
        # A disposable copied project does not inherit its source's local
        # execution lease. The original namespace is never touched.
        return {}
    return value


def _acquire(lock: FileWriterLock, deadline: float):
    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError("verification executor is still busy; no duplicate was launched")
        try:
            lock.acquire()
            return
        except FileLockBusy:
            time.sleep(0.05)


def _valid_key(value) -> bool:
    return (
        isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
    )


def _acquire_observed(lock, deadline, observation):
    started = time.monotonic()
    try:
        _acquire(lock, deadline)
    finally:
        observation["coordination_wait_wall_s"] = round(
            observation.get("coordination_wait_wall_s", 0) + time.monotonic() - started, 6
        )


def _observe(root: Path, path: Path, payload: dict):
    # Advisory: missing telemetry cannot turn a valid execution into a failure.
    with contextlib.suppress(OSError, ValueError):
        _write(root, path, payload)


def _load_written(root: Path, reference: object, identity: dict) -> dict | None:
    if not isinstance(reference, dict):
        return None
    try:
        path = root / reference["path"]
        if not path.resolve().is_relative_to((root / ".saipen/evidence").resolve()):
            return None
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != reference.get("sha256"):
            return None
        record = json.loads(raw)
        if not isinstance(record, dict):
            return None
        if (
            record.get("fingerprint") != identity.get("fingerprint")
            or record.get("verification_identity") != identity.get("verification_identity")
            or record.get("family") != identity.get("family")
            or record.get("verdict") not in {"PASS", "FAIL"}
        ):
            return None
        if record.get("verdict") == "PASS" and (
            type(record.get("ran")) is not int or record["ran"] < 1
        ):
            return None
        if record["family"] == "unit":
            from . import core_unit

            if core_unit.full_scope_problem(record):
                return None
            baseline, error = core_unit.load_baseline(root)
            required = ("status", "exit_code", "ran", "red", "new_red", "fixed", "problems")
            if error or any(name not in record for name in required):
                return None
            if core_unit.judge(record, baseline["red"])["verdict"] != record["verdict"]:
                return None
        elif record["family"] == "focused-unit":
            from .focused_unit import record_problem

            if record["verdict"] == "PASS" and record_problem(
                root, record, verification_identity=identity["verification_identity"]
            ):
                return None
        else:
            return None
        return {"path": reference["path"], "sha256": reference["sha256"], "record": record}
    except (KeyError, OSError, ValueError, TypeError, AttributeError):
        return None


class Flight:
    def __init__(self, root: Path, path: Path, identity: dict, prior: dict, requested: int):
        self.root, self.path, self.identity = root, path, identity
        self.state = prior
        self.requested = requested
        self.written = None
        self.reused = False
        self.joined = False

    def publish(self, written: dict):
        valid = _load_written(self.root, written, self.identity)
        if valid is None:
            raise ValueError("verification result does not match its requested immutable identity")
        if not compatible(self.root, self.identity.get("verification_identity")):
            raise ValueError("verification environment changed during execution")
        self.state.update(
            status="COMPLETE",
            finished_ns=time.time_ns(),
            result={"path": written["path"], "sha256": written["sha256"]},
        )
        _write(self.root, self.path, self.state)
        self.written = valid


def register_sandbox(path: Path):
    """Attach existing owner-stamped sandboxes to an execution's recovery record."""
    current = _ACTIVE.get()
    if current is None:
        return
    current.state.setdefault("sandboxes", []).append(str(path.resolve()))
    from .core_unit import SANDBOX_OWNER

    stamp_path = path / SANDBOX_OWNER
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    stamp["verification_flight"] = current.state["execution"]
    stamp_path.write_text(json.dumps(stamp), encoding="utf-8")
    _write(current.root, current.path, current.state)


def _readers_alive(state: dict) -> bool:
    from .core_unit import SANDBOX_OWNER, pid_alive
    from .inflight import _process_created

    temp = Path(tempfile.gettempdir()).resolve()
    for raw in state.get("sandboxes") or []:
        path = Path(raw).resolve()
        if path.parent != temp or not path.name.startswith("saipen-core-unit-"):
            raise ValueError(
                "verification recovery names a sandbox outside its owned temp namespace"
            )
        try:
            owner = json.loads((path / SANDBOX_OWNER).read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        except (OSError, ValueError):
            raise ValueError("verification recovery sandbox ownership is unreadable") from None
        if owner.get("verification_flight") != state.get("execution"):
            raise ValueError("verification recovery sandbox has a different execution owner")
        pid = owner.get("reader")
        if os.name != "nt" and owner.get("spawn_phase") == "STARTING" and pid is None:
            if owner.get("spawn_guard") == "posix-pipe-v1":
                continue  # The bootstrap cannot release a verifier before PID registration.
            raise ValueError("interrupted spawn has no bound reader; platform recovery required")
        if type(pid) is int and pid_alive(pid):
            created = owner.get("reader_created")
            observed = _process_created(pid)
            if created is None or observed is None or abs(created - observed) < 2:
                return True
        elif type(pid) is int and os.name != "nt":
            from .process_tree import ProcessTree

            if ProcessTree.group_pids(pid):
                return True
    return False


@contextlib.contextmanager
def single_flight(
    root: Path,
    identity: dict,
    *,
    fresh=False,
    timeout=33000,
    available=None,
    request_started_ns=None,
    request_started_monotonic=None,
    consumer=None,
):
    """One execution per compatible identity; OS death releases ownership.

    Waiter cancellation never cancels the executor. An interrupted executor's
    still-live recorded reader prevents an overlapping replacement.
    """
    root = root.resolve()
    key = digest(identity)
    registered = time.time_ns()
    requested = request_started_ns or registered
    began = request_started_monotonic or time.monotonic()
    deadline = began + timeout
    path = root / ".saipen/cache/verification-flights" / f"{key}.json"
    observation_path = root / ".saipen/cache/verification-observations" / f"{uuid.uuid4().hex}.json"
    observation = {
        "schema": 1,
        "kind": "single-flight-request",
        "key": key,
        "family": identity.get("family"),
        "fingerprint": identity.get("fingerprint"),
        "requested_ns": requested,
        "pid": os.getpid(),
        "fresh": bool(fresh),
        "status": "REQUESTED",
    }
    if consumer is not None:
        observation["ticket"] = consumer
    _observe(root, observation_path, observation)
    lock = FileWriterLock(root / ".saipen/locks" / f"verification-{key}.lock", root)
    executor = None
    try:
        _acquire_observed(lock, deadline, observation)
        prior = _read_state(root, path)
        if prior and (prior.get("schema") != 1 or prior.get("identity") != identity):
            raise ValueError("verification flight identity is mismatched or incomplete")
        flight = Flight(root, path, identity, prior, requested)
        if prior.get("identity") == identity and prior.get("status") == "COMPLETE":
            written = _load_written(root, prior.get("result"), identity)
            replay = replay_supported(identity.get("verification_identity") or {})
            joined = (prior.get("finished_ns") or 0) >= (requested if replay else registered)
            if written is None:
                raise ValueError(
                    "shared verification result is stale, incomplete or digest-mismatched"
                )
            if replay and (joined or not fresh):
                flight.written, flight.reused, flight.joined = written, True, joined
        if (
            flight.written is None
            and available is not None
            and not fresh
            and replay_supported(identity.get("verification_identity") or {})
        ):
            flight.state = {
                "schema": 1,
                "project": str(root),
                "identity": identity,
                "pid": os.getpid(),
                "execution": uuid.uuid4().hex,
                "started_ns": time.time_ns(),
                "sandboxes": [],
            }
            flight.publish(available)
            flight.reused = True
        if flight.written is None:
            # Serialize incompatible configurations too: they cannot overwrite
            # the single project in-flight marker or oversubscribe the host.
            executor = FileWriterLock(root / ".saipen/locks/verification-executor.lock", root)
            _acquire_observed(executor, deadline, observation)
            lane_path = root / ".saipen/cache/verification-executor.json"
            lane = _read_state(root, lane_path)
            if lane.get("key") and lane["key"] != key:
                if not _valid_key(lane["key"]):
                    raise ValueError("verification executor lease identity is invalid")
                old_state = _read_state(root, path.with_name(f"{lane['key']}.json"))
                if old_state.get("status") in {"RUNNING", "INTERRUPTED"} and _readers_alive(
                    old_state
                ):
                    raise ValueError("previous verification has a live owned reader")
            if prior.get("status") in {"RUNNING", "INTERRUPTED"} and _readers_alive(prior):
                raise ValueError(
                    "interrupted verification still has a live owned reader; replacement refused"
                )
            flight.state = {
                "schema": 1,
                "project": str(root),
                "identity": identity,
                "status": "RUNNING",
                "started_ns": time.time_ns(),
                "pid": os.getpid(),
                "execution": uuid.uuid4().hex,
                "sandboxes": [],
            }
            _write(root, path, flight.state)
            _write(root, lane_path, {"schema": 1, "project": str(root), "key": key})
        token = _ACTIVE.set(flight if flight.written is None else None)
        try:
            yield flight
            if flight.written is None:
                raise ValueError(
                    "verification exited without publishing a complete execution receipt"
                )
            observation.update(
                status="COMPLETE",
                reused=flight.reused,
                joined=flight.joined,
                verdict=flight.written["record"]["verdict"],
                record=flight.written["path"],
            )
        except BaseException:
            if flight.written is None:
                flight.state.update(status="INTERRUPTED", finished_ns=time.time_ns())
                _write(root, path, flight.state)
            raise
        finally:
            _ACTIVE.reset(token)
    finally:
        observation.update(elapsed_wall_s=round(time.monotonic() - began, 6))
        if observation["status"] == "REQUESTED":
            observation["status"] = "INTERRUPTED"
        _observe(root, observation_path, observation)
        if executor is not None:
            executor.release()
        lock.release()
