"""Guard-side client of the SAIPEN host-authority broker.

The Claude Code hook and the canonical engine never mint admission, and this
module is where they stop pretending they can. It asks the broker, and the
broker answers after proving from the operating system that the request comes
from the host's own hook invocation. Nothing here decides an admission state:
the verdict, the capability and the ledger record all come back from the
broker, and a request this module cannot deliver is reported as a typed
failure rather than invented.

Recovery is bounded and explicit. When no broker answers, the client attempts
exactly one automatic start and retries the handshake once. Every step is
recorded in the returned `recovery` block so the diagnostic the operator sees
can name the component that failed and the recovery that was attempted,
instead of repeating that an authority "is required".

The server is authenticated too. An endpoint name is only a name: before a
request is sent on the operator's real endpoint, the process serving it must be
the SAIPEN service entry of a registered runtime. Anything else is
`AUTHORITY_IMPOSTOR` -- never trusted, never replaced, never obeyed.

The operator's admission policy lives in one operator-owned file
(`~/.saipen/authority.json`). Absent, it is the product default,
DEGRADED_ALLOWED: a host that can run is not locked out by an integration that
could not prove itself. `strict` is the operator's explicit opt-in. A file that
is present and unreadable or unrecognized is STRICT, so a damaged policy never
reads as a silent downgrade -- the same rule the hook applies on its own when
the engine cannot be run at all.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path

from . import host_authority_broker as broker
from . import host_authority_process as proc
from . import host_authority_transport as transport
from . import host_taxonomy as taxonomy

#: One admission handshake. The hook's own budget is 20s, so this stays small.
REQUEST_TIMEOUT = 8.0
#: A provenance question is answered from memory; it must not stall a reply.
VERIFY_TIMEOUT = 2.0
PING_TIMEOUT = 1.0
MAX_CHAIN = 8

CODE_UNREACHABLE = "BROKER_UNREACHABLE"
CODE_NOT_HOST_CLIENT = "BROKER_NOT_A_HOST_CLIENT"
CODE_SERVER_UNPROVEN = "BROKER_SERVER_UNPROVEN"

SOURCE_DEFAULT = "default"
SOURCE_OPERATOR = "operator"
SOURCE_INVALID = "invalid"

SERVICE_ENTRY = "authority_service.py"


def mode_path(home: Path | None = None) -> Path:
    base = Path(home) if home is not None else Path.home()
    return base / ".saipen" / "authority.json"


def policy(home: Path | None = None) -> dict:
    """The admission policy in force and where it came from.

    `source` is `default` (no file: DEGRADED_ALLOWED), `operator` (the file
    names a recognized mode) or `invalid` (the file is there and cannot be
    read as a mode: STRICT, never a silent downgrade).
    """
    path = mode_path(home)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return {"mode": taxonomy.DEFAULT_MODE, "source": SOURCE_DEFAULT, "path": str(path)}
    except OSError:
        return {"mode": taxonomy.MODE_STRICT, "source": SOURCE_INVALID, "path": str(path)}
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        payload = None
    mode = taxonomy.normalize_mode(payload.get("mode")) if isinstance(payload, dict) else None
    if mode is None:
        return {"mode": taxonomy.MODE_STRICT, "source": SOURCE_INVALID, "path": str(path)}
    return {"mode": mode, "source": SOURCE_OPERATOR, "path": str(path)}


def authority_mode(home: Path | None = None) -> str:
    """The admission mode in force: `degraded` (DEGRADED_ALLOWED) or `strict`."""
    return policy(home)["mode"]


def set_authority_mode(mode: object, home: Path | None = None) -> dict:
    """Write the operator's mode choice, atomically. Refuses an unrecognized
    value loudly rather than falling back, and never writes anything else."""
    normalized = taxonomy.normalize_mode(mode)
    if normalized is None:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "detail": "mode must be one of strict, degraded (alias: degraded_allowed)",
        }
    path = mode_path(home)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                record = {"mode": normalized, "set_by": "operator"}
                stream.write(json.dumps(record, indent=2) + "\n")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    except OSError as exc:
        return {"ok": False, "code": "IO_FAILED", "detail": str(exc)}
    return {
        "ok": True,
        "code": "AUTHORITY_MODE_SET",
        "mode": normalized,
        "label": taxonomy.MODE_LABELS[normalized],
        "path": str(path),
    }


def clear_authority_mode(home: Path | None = None) -> dict:
    """Remove the operator's choice so the product default is in force again."""
    path = mode_path(home)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        return {"ok": False, "code": "IO_FAILED", "detail": str(exc)}
    return {
        "ok": True,
        "code": "AUTHORITY_MODE_SET",
        "mode": taxonomy.DEFAULT_MODE,
        "label": taxonomy.MODE_LABELS[taxonomy.DEFAULT_MODE],
        "path": str(path),
        "source": SOURCE_DEFAULT,
    }


# ------------------------------------------------------- server authentication


def _norm(path: object) -> str:
    return os.path.normcase(os.path.abspath(str(path))).replace("\\", "/")


def trusted_service_entries() -> set[str]:
    """Every path the SAIPEN service entry may legitimately run from: this
    runtime, the installed runtimes the adapter registry declares, and the
    canonical source this runtime was installed from. Read from the registry
    and the installer's marker, never from the endpoint."""
    home = Path(__file__).resolve().parents[2]
    homes = {home}
    try:
        from .runtime_bootstrap import _adapter_skill, _expand, _registry, read_provenance

        for adapter in _registry(home).get("adapters", []):
            skill = _adapter_skill(adapter)
            if not skill:
                continue
            try:
                homes.add(_expand(skill))
            except (OSError, ValueError):
                continue
        record = read_provenance(home)
        source = record.get("canonical_source_root") if isinstance(record, dict) else None
        if isinstance(source, str) and source.strip():
            homes.add(Path(source))
    except Exception:
        pass
    return {_norm(Path(item) / "tools" / SERVICE_ENTRY) for item in homes}


def server_trusted(pid: object) -> bool:
    """Is the process serving the endpoint the SAIPEN service entry?"""
    if not isinstance(pid, int) or pid <= 0:
        return False
    fact = proc.process_fact(pid)
    argv = list(fact.argv or []) if fact is not None else []
    if len(argv) < 3 or argv[2] != "serve":
        return False
    return _norm(argv[1]) in trusted_service_entries()


def _exchange(
    payload: dict, *, runtime: Path | None, timeout: float
) -> tuple[dict | None, str | None]:
    """(reply, failure kind). The operator's real endpoint is authenticated; an
    explicit `runtime` is an isolated diagnostic endpoint and is taken as given."""
    verify = server_trusted if runtime is None else None
    try:
        reply = broker.request(payload, runtime=runtime, timeout=timeout, verify_server=verify)
    except transport.TransportError as exc:
        return None, exc.kind
    return (reply, None) if isinstance(reply, dict) else (None, "frame")


def _call(payload: dict, *, runtime: Path | None, timeout: float) -> dict | None:
    return _exchange(payload, runtime=runtime, timeout=timeout)[0]


def health(runtime: Path | None = None) -> dict | None:
    reply = _call({"op": "ping"}, runtime=runtime, timeout=PING_TIMEOUT)
    return reply if reply and reply.get("ok") else None


def status(runtime: Path | None = None) -> dict | None:
    """The broker's own health report, including whether THIS process was
    accepted as a host hook. The socket identifies the caller; this module
    never sends an identity claim."""
    return _call({"op": "status"}, runtime=runtime, timeout=PING_TIMEOUT)


def _authority_hosts() -> list[str]:
    """Every registered host that declares a separated authority."""
    try:
        from . import protocol_admission as pa

        adapters = pa._adapters(pa.Context(project_root=None, session_id="", host=""))
    except Exception:
        return []
    return [
        str(name)
        for name, entry in adapters.items()
        if isinstance(entry, dict) and entry.get("admission_authority")
    ]


def hook_invocation(host: str | None = None, home: object = None, limit: int = 16) -> dict:
    """Is THIS process a host application's own hook invocation?

    Defect class: the prompt path started the service for any process that had
    a host application somewhere above it. A command a model runs through the
    host's shell tool is such a process, and so is every child of a test suite
    an agent starts inside a host session: with no service running, a fixture
    started the operator's REAL service -- from the fixture's own bytes, on the
    operator's endpoint -- and the operator's hook then met a service it could
    not trust. "A host is above me" is the name-level answer `identify_self`
    prints; it is not a reason to start anything.

    The answer here is the shape the service itself demands
    (`host_authority_identity.prove_hook_invocation`), asked of this process's
    own ancestry, minus the two observations only the service makes
    authoritative: the host image's code signer and the hook's bytes. A caller
    the service would refuse on shape gains nothing from a start, so none is
    made on its behalf. Never raises; proves nothing to anyone but the caller.
    """
    from . import host_authority_identity as identity_proof
    from .claude_profiles import hook_for_process

    config = broker.settings()
    reason, detail = identity_proof.REASON_IDENTITY_UNAVAILABLE, ""
    for candidate in [str(host)] if host else _authority_hosts():
        try:
            proof = identity_proof.prove_hook_invocation(
                proc.ancestry(os.getpid(), limit),
                identity_proof.IdentityPolicy(
                    host=candidate,
                    host_images=tuple(config.get("host_images") or ()),
                    hook_artifacts=broker.hook_artifacts(candidate, home),
                    shells=tuple(config.get("hook_shells") or identity_proof.DEFAULT_SHELLS),
                    profile_hook="hooks/saipen-guard.py" if candidate == "claude" else None,
                ),
                hook_for_host=lambda pid: hook_for_process(pid, Path(home) if home else None),
            )
        except Exception as exc:  # pragma: no cover - defensive only
            reason, detail = identity_proof.REASON_IDENTITY_UNAVAILABLE, type(exc).__name__
            continue
        if proof.ok:
            return {"ok": True, "host": candidate, "reason": None, "detail": proof.detail}
        reason, detail = str(proof.reason), proof.detail
    return {"ok": False, "host": None, "reason": reason, "detail": detail}


def identify_self(
    host_images: object = None,
    limit: int = 16,
    *,
    host: str | None = None,
    home: object = None,
) -> dict:
    """What this process is to a host application, as far as it can see itself.

    `ok` is the NAME-level answer the diagnostics print: a host application is
    somewhere above this process. `hook` is the one that decides whether
    starting the service is worthwhile (`hook_invocation`). Neither proves
    anything to the service, which reads the same facts for itself.
    """
    images = list(host_images or broker.settings().get("host_images") or [])
    report = proc.describe(os.getpid(), limit)
    ancestor = proc.host_ancestor(os.getpid(), images, limit)
    shape = hook_invocation(host, home, limit)
    return {
        "ok": ancestor is not None,
        "hook": bool(shape["ok"]),
        "hook_reason": shape["reason"],
        "host_image": ancestor.name if ancestor else None,
        "host_pid": ancestor.pid if ancestor else None,
        "host_images": images,
        "supported": report.get("supported"),
        "chain": (report.get("chain") or [])[:MAX_CHAIN],
        "detail": report.get("detail"),
    }


def ensure(
    saipen_root: Path | None = None,
    *,
    runtime: Path | None = None,
    wait: float = 6.0,
    force: bool = False,
    host: str | None = None,
    home: object = None,
) -> dict:
    """Ping, and if nothing answers, start one detached broker and wait for it.

    Bounded: at most one start attempt and a `wait`-second budget. Returns what
    was attempted whether or not it worked, so the caller can report recovery
    instead of a dead end. The prompt path starts the service only for the
    host's own hook invocation (`hook_invocation`): that is the one caller the
    service can admit, so it is the one caller a start is worth making for.
    `force` is the operator's explicit repair, which needs no such reason.
    """
    report = health(runtime)
    if report:
        return {
            "ok": True,
            "state": "running",
            "found": True,
            "started": False,
            "attempts": 1,
            "instance": report.get("instance"),
            "health": report,
        }
    identity = identify_self(host=host, home=home)
    if not identity["hook"] and not force:
        return {
            "ok": False,
            "state": "not_a_host_client",
            "found": False,
            "started": False,
            "attempts": 1,
            "code": CODE_NOT_HOST_CLIENT,
            "identity": identity,
            "detail": (
                "this process is not a registered host application's own hook "
                f"invocation ({identity['hook_reason']}), so no authority service "
                "was started on its behalf"
            ),
        }
    started = broker.spawn(saipen_root, runtime=runtime, wait=wait)
    return {
        "ok": bool(started.get("ok")),
        "state": "started" if started.get("ok") else "start_failed",
        "found": False,
        "started": bool(started.get("started")),
        "attempts": 1 + int(started.get("attempts") or 0),
        "instance": started.get("instance"),
        "pid": started.get("pid"),
        "log": started.get("log"),
        "identity": identity,
        "detail": started.get("detail"),
    }


def _payload(
    *,
    project: Path | str | None,
    session: str,
    host: str,
    model: object = None,
    provider: object = None,
    authority_root: Path | str | None = None,
    home: Path | str | None = None,
    event: str | None = None,
    capability: object = None,
    verb: str | None = None,
    fresh: bool = False,
) -> dict:
    payload: dict = {
        "project": str(project) if project else "",
        "session": str(session or ""),
        "host": str(host or ""),
        "model": str(model) if model else "",
        "provider": str(provider) if provider else "",
    }
    if authority_root:
        payload["authority_root"] = str(authority_root)
    if home:
        payload["home"] = str(home)
    if host == "claude":
        from .claude_profiles import directory

        payload["profile"] = str(directory(Path(home) if home else None))
    if event:
        payload["event"] = str(event)
    if capability:
        payload["capability"] = str(capability)
    if verb:
        payload["verb"] = str(verb)
    if fresh:
        payload["fresh"] = True
    return payload


def _recovery(
    *,
    attempted: list[str],
    ensured: dict | None = None,
    log: object = None,
) -> dict:
    # `answered` is the state when the first call was served and no recovery was
    # needed: saying `unreachable` there would send the operator hunting for a
    # service that is running.
    block = {
        "component": "SAIPEN host-authority broker",
        "attempted": list(attempted),
        "started": bool((ensured or {}).get("started")),
        "state": (ensured or {}).get("state") or "answered",
        "log": str(log or (ensured or {}).get("log") or broker.log_path()),
        "identity": (ensured or {}).get("identity"),
        "detail": (ensured or {}).get("detail"),
    }
    return block


def _unanswered(kind: str | None) -> str:
    """The failure an unanswered call means, from how it went unanswered."""
    if kind == "impostor":
        return "AUTHORITY_IMPOSTOR"
    if kind in ("timeout", "io", "frame"):
        return "AUTHORITY_FAULT"
    return "AUTHORITY_UNREACHABLE"


def attempt_admission(
    *,
    project: Path | str | None,
    session: str,
    host: str,
    model: object = None,
    provider: object = None,
    authority_root: Path | str | None = None,
    home: Path | str | None = None,
    event: str = "UserPromptSubmit",
    runtime: Path | None = None,
    fresh: bool = False,
) -> dict:
    """One admission handshake with automatic, bounded recovery.

    Returns `{reachable, refused, verdict, recovery, code, failure, detail}` and
    never raises. `reachable` False means no trusted broker answered even after
    the recovery attempt; `refused` True means a broker answered and refused
    THIS client. `failure` is the registered taxonomy code for whichever of
    those happened, and None when a verdict came back.
    """
    payload = _payload(
        project=project,
        session=session,
        host=host,
        model=model,
        provider=provider,
        authority_root=authority_root,
        home=home,
        event=event,
        fresh=fresh,
    )
    attempted = ["connect"]
    reply, kind = _exchange(
        {"op": "admission", **payload}, runtime=runtime, timeout=REQUEST_TIMEOUT
    )
    ensured: dict | None = None
    saipen_root = Path(authority_root) if authority_root else None
    if reply is None and kind != "impostor" and runtime is None:
        # An endpoint served by something else is never "recovered" by starting
        # a second service against it: the name is taken, and saying so is the
        # whole recovery. An EXPLICIT runtime is a diagnostic endpoint and is
        # taken as given: nothing is started on its behalf, so what a test or
        # a diagnostic observes never depends on where it was launched from.
        ensured = ensure(saipen_root, runtime=runtime, host=host, home=home)
        attempted.append("start")
        if ensured.get("ok"):
            attempted.append("retry")
            reply, kind = _exchange(
                {"op": "admission", **payload}, runtime=runtime, timeout=REQUEST_TIMEOUT
            )
    recovery = _recovery(attempted=attempted, ensured=ensured)
    if reply is None:
        failure = _unanswered(kind)
        if kind == "impostor":
            recovery["state"] = "impostor"
        elif ensured is None:
            # Nothing answered and nothing was started (an explicit diagnostic
            # endpoint). `answered` here told the operator a service was up.
            recovery["state"] = "unanswered"
        return {
            "reachable": False,
            "refused": False,
            "verdict": None,
            "recovery": recovery,
            "code": CODE_SERVER_UNPROVEN if kind == "impostor" else CODE_UNREACHABLE,
            "failure": failure,
            "detail": recovery.get("detail") or taxonomy.get(failure).summary,
        }
    if reply.get("state") is None and reply.get("ok") is False:
        # A broker answered and refused THIS client: the service is up, the
        # binding is not recognized, and the recovery state must say so instead
        # of claiming the authority was missing.
        recovery["state"] = "refused"
        recovery["refused_code"] = reply.get("code")
        recovery["refused_detail"] = reply.get("detail")
        recovery["broker_identity"] = reply.get("identity")
        return {
            "reachable": True,
            "refused": True,
            "verdict": None,
            "recovery": recovery,
            "code": reply.get("code"),
            "failure": taxonomy.from_broker(reply.get("code")),
            "detail": reply.get("detail"),
            "identity": reply.get("identity"),
        }
    return {
        "reachable": True,
        "refused": False,
        "verdict": reply,
        "recovery": recovery,
        "code": None,
        "failure": None,
        "detail": None,
    }


def evaluate(
    *,
    project: Path | str | None,
    session: str,
    host: str,
    model: object = None,
    provider: object = None,
    authority_root: Path | str | None = None,
    home: Path | str | None = None,
    runtime: Path | None = None,
) -> dict | None:
    """The broker's read-only view of this session, or None when nothing
    trusted answers. Starts nothing and writes nothing."""
    reply = _call(
        {
            "op": "evaluate",
            **_payload(
                project=project,
                session=session,
                host=host,
                model=model,
                provider=provider,
                authority_root=authority_root,
                home=home,
            ),
        },
        runtime=runtime,
        timeout=REQUEST_TIMEOUT,
    )
    if not reply or reply.get("state") is None:
        return None
    return reply


def invalidate(
    *,
    project: Path | str | None,
    session: str,
    host: str = "claude",
    reason: str = "",
    model: object = None,
    provider: object = None,
    authority_root: Path | str | None = None,
    home: Path | str | None = None,
    runtime: Path | None = None,
) -> dict | None:
    """Remove this session's record through the broker. None when no broker
    answers: with no authority there is no provable record to remove."""
    return _call(
        {
            "op": "invalidate",
            **_payload(
                project=project,
                session=session,
                host=host,
                model=model,
                provider=provider,
                authority_root=authority_root,
                home=home,
                event=reason,
            ),
        },
        runtime=runtime,
        timeout=REQUEST_TIMEOUT,
    )


def authorize(
    *,
    project: Path | str | None,
    session: str,
    host: str,
    verb: str,
    model: object = None,
    provider: object = None,
    capability: object = None,
    authority_root: Path | str | None = None,
    home: Path | str | None = None,
    runtime: Path | None = None,
) -> dict | None:
    """May this authenticated client perform `verb` here? None when unreachable."""
    return _call(
        {
            "op": "authorize",
            **_payload(
                project=project,
                session=session,
                host=host,
                model=model,
                provider=provider,
                authority_root=authority_root,
                home=home,
                capability=capability,
                verb=verb,
            ),
        },
        runtime=runtime,
        timeout=REQUEST_TIMEOUT,
    )


def verify_capability(
    capability: object,
    *,
    project: Path | str | None,
    session: str,
    host: str,
    model: object = None,
    provider: object = None,
    runtime: Path | None = None,
) -> bool:
    """True only when the live broker reproduces this capability for this scope."""
    reply = inspect_capability(
        capability,
        project=project,
        session=session,
        host=host,
        model=model,
        provider=provider,
        runtime=runtime,
    )
    return bool(reply and reply.get("ok"))


def inspect_capability(
    capability: object,
    *,
    project: Path | str | None,
    session: str,
    host: str,
    model: object = None,
    provider: object = None,
    runtime: Path | None = None,
) -> dict | None:
    """The broker's verdict on a PRESENTED capability: `{ok, code, detail}`,
    or None when no broker answers (which verifies nothing)."""
    if not capability:
        return {"ok": False, "code": "BROKER_CAPABILITY_INVALID", "detail": "no capability"}
    return _call(
        {
            "op": "verify",
            **_payload(
                project=project,
                session=session,
                host=host,
                model=model,
                provider=provider,
                capability=capability,
            ),
        },
        runtime=runtime,
        timeout=VERIFY_TIMEOUT,
    )


def issue_operator_origin(
    *, project: Path | str, session: str, host: str, request_text: str,
    event_id: str, action: str, model: object = None, provider: object = None,
    home: Path | str | None = None,
) -> dict | None:
    """A native callback offers exact human intent; the broker authenticates it."""
    return _call(
        {"op": "issue-origin", **_payload(
            project=project, session=session, host=host, model=model, provider=provider,
            home=home, event="UserPromptSubmit",
        ), "request_text": request_text, "event_id": event_id, "action": action},
        runtime=None, timeout=REQUEST_TIMEOUT,
    )


def register_operator_worker(proof: dict, worker: int, *, home=None) -> dict | None:
    """The native spawner binds its observed worker; a model caller is refused."""
    return _call(
        {"op": "register-origin-worker", "host": proof.get("host"),
         "home": str(home) if home else None, "proof": proof, "worker": worker},
        runtime=None, timeout=REQUEST_TIMEOUT,
    )


def revoke_operator_origin(proof: dict, *, home=None) -> dict | None:
    """The proven native host revokes an origin, not a client-supplied flag."""
    return _call(
        {"op": "revoke-origin", "host": proof.get("host"),
         "home": str(home) if home else None, "proof": proof},
        runtime=None, timeout=REQUEST_TIMEOUT,
    )


def prepare_operator_goal(
    proof, *, project, operation, semantic_hash, grant, authorization=None,
) -> bool:
    """Reserve exactly one scoped goal using the registered worker's OS identity."""
    reply = _call(
        {"op": "prepare-origin-goal", "project": str(Path(project).resolve()),
         "proof": proof, "operation": operation, "semantic_hash": semantic_hash, "grant": grant,
         "authorization": authorization},
        runtime=None, timeout=REQUEST_TIMEOUT,
    )
    return bool(reply and reply.get("ok") is True)


def verify_operator_goal(proof, *, project, operation, grant) -> bool:
    """An accepted goal can continue only in its broker-reserved scope."""
    if not isinstance(proof, dict) or proof.get("kind") != "operator-origin":
        return False
    reply = _call(
        {"op": "verify-origin-goal", "project": str(Path(project).resolve()),
         "proof": proof, "operation": operation},
        runtime=None, timeout=VERIFY_TIMEOUT,
    )
    return bool(reply and reply.get("ok") is True
                and reply.get("kind") == "operator-goal-verdict"
                and reply.get("operation") == operation and reply.get("grant") == grant)


def verify_operator_origin(
    proof: object,
    *,
    project: Path | str | None,
    request_digest: str,
    session: str | None = None,
    receipt: str | None = None,
    existing_only: bool = False,
) -> bool:
    """Verify exact operator intent at the authenticated production endpoint.

    Admission of a session proves neither this message's human origin nor its
    scope. No diagnostic endpoint or model-selected runtime is accepted here.
    The broker owns event identity, scope, revocation and delivery consumption;
    an unsupported broker operation is unverified, never a legacy fallback.
    """
    if (not isinstance(proof, dict) or proof.get("kind") != "operator-origin"
            or not project or not isinstance(request_digest, str)
            or len(request_digest) != 64
            or any(char not in "0123456789abcdef" for char in request_digest)):
        return False
    try:
        project_path = str(Path(project).resolve())
    except (OSError, ValueError):
        return False
    reply = _call(
        {"op": "verify-origin", "project": project_path,
         "request_digest": request_digest, "session": session,
         "receipt": receipt, "proof": proof, "existing_only": existing_only},
        runtime=None, timeout=VERIFY_TIMEOUT,
    )
    return bool(
        reply and reply.get("ok") is True
        and reply.get("kind") == "operator-origin-verdict"
        and reply.get("request_digest") == request_digest
        and _norm(reply.get("project")) == _norm(project_path)
        and reply.get("action") == proof.get("action")
    )


def verify_operator_source(proof, *, project, receipt, request_digest) -> bool:
    """Read accepted Source origin; this does not grant current operator powers.

    The live separated issuer owns the original Source binding. No Source file,
    proof-shaped dictionary or caller-selected endpoint supplies that binding.
    """
    if (not isinstance(proof, dict) or proof.get("kind") != "operator-origin" or not project
            or not isinstance(receipt, str) or not receipt.startswith("SRC-")
            or not receipt[4:].isdigit() or not isinstance(request_digest, str)
            or len(request_digest) != 64
            or any(char not in "0123456789abcdef" for char in request_digest)):
        return False
    try:
        project_path = str(Path(project).resolve())
    except (OSError, ValueError):
        return False
    reply = _call(
        {"op": "verify-source-origin", "project": project_path, "receipt": receipt,
         "proof": proof, "request_digest": request_digest},
        runtime=None, timeout=VERIFY_TIMEOUT,
    )
    return bool(reply and reply.get("ok") is True
                and reply.get("kind") == "operator-source-origin"
                and reply.get("receipt") == receipt
                and reply.get("request_digest") == request_digest
                and _norm(reply.get("project")) == _norm(project_path)
                and reply.get("action") == proof.get("action"))


def verify_record(record: object, *, runtime: Path | None = None) -> bool:
    """Is this ledger record one the live broker wrote?

    A record with no provenance, a provenance from another generation, or a mac
    this broker cannot reproduce is False. No broker at all is also False: a
    record is never authoritative merely because it is well formed.
    """
    if not isinstance(record, dict) or not isinstance(record.get("provenance"), dict):
        return False
    reply = _call(
        {"op": "verify-record", "record": record}, runtime=runtime, timeout=VERIFY_TIMEOUT
    )
    return bool(reply and reply.get("ok"))


def shutdown(runtime: Path | None = None) -> dict:
    reply = _call({"op": "shutdown"}, runtime=runtime, timeout=REQUEST_TIMEOUT)
    if reply is None:
        return {"ok": False, "code": CODE_UNREACHABLE, "detail": "no broker answered"}
    return reply


def _is_service_process(pid: object) -> bool:
    """Is this pid a SAIPEN authority service, by what the OS says it runs?
    Path-independent on purpose: it decides only whether ending the process is
    ending OUR service, never whether the service may be trusted."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    fact = proc.process_fact(pid)
    argv = list(fact.argv or []) if fact is not None else []
    return (
        len(argv) >= 3
        and argv[2] == "serve"
        and Path(argv[1].replace("\\", "/")).name == SERVICE_ENTRY
    )


def retire_service(runtime: Path | None = None, *, wait: float = 5.0) -> dict:
    """End the running authority service so the next prompt starts the
    installed generation.

    Asks first. A service of an older generation may not understand the
    question (it authenticated `shutdown`, and an installer is not a hook), so
    when it is still answering afterwards the process named by its own status
    file is ended -- but only when the OS confirms that pid IS the service.
    Every session re-admits against the next generation; nothing else is lost,
    because the key never left that process.
    """
    import time

    if not broker.health(runtime, timeout=PING_TIMEOUT):
        return {"ok": True, "retired": False, "detail": "not running"}
    with contextlib.suppress(transport.TransportError):
        broker.request({"op": "shutdown"}, runtime=runtime, timeout=PING_TIMEOUT)
    deadline = time.time() + max(0.0, wait)
    while time.time() < deadline:
        if not broker.health(runtime, timeout=0.3):
            return {"ok": True, "retired": True, "detail": "shut down on request"}
        time.sleep(0.15)
    stored = broker.read_status(runtime) or {}
    pid = stored.get("pid")
    if isinstance(pid, int) and _is_service_process(pid):
        try:
            os.kill(pid, 15)
        except OSError as exc:
            return {"ok": False, "retired": False, "detail": f"could not end pid {pid}: {exc}"}
        deadline = time.time() + max(0.0, wait)
        while time.time() < deadline:
            if not broker.health(runtime, timeout=0.3):
                broker.release_lock(runtime)
                return {"ok": True, "retired": True, "detail": f"ended pid {pid}"}
            time.sleep(0.15)
    return {
        "ok": False,
        "retired": False,
        "detail": "the service is still answering and its process could not be identified",
    }


#: Where "this unverified session was already handed the authority" is noted.
#: Deliberately NOT the admission ledger directory: nothing here is a record.
DELIVERY_DIR = Path(".saipen") / "cache" / "delivery"


def _delivery_note(project: Path | str, session: str) -> Path:
    import hashlib

    name = hashlib.sha256(str(session).encode("utf-8")).hexdigest()[:24] + ".delivered"
    return Path(project) / DELIVERY_DIR / name


def already_delivered(project: Path | str | None, session: str, generation: str) -> bool:
    """Was this authority generation already handed to this session?

    A plain note, and deliberately nothing more: it is not a record, carries no
    provenance and admits nobody. Its one job is economy. A session that runs
    UNVERIFIED has no ledger record to say "already delivered", so without this
    every prompt of a degraded session paid for the whole authority text again.
    A stale or hand-written note can only withhold a re-delivery from a session
    that is already marked unverified; it can never grant anything.
    """
    if project is None:
        return False
    try:
        noted = _delivery_note(project, session).read_text(encoding="utf-8")
    except OSError:
        return False
    return noted.strip() == generation


def note_delivered(project: Path | str | None, session: str, generation: str | None) -> None:
    """Note (or with None, forget) what an unverified session was handed."""
    if project is None:
        return
    path = _delivery_note(project, session)
    try:
        if generation is None:
            path.unlink()
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(generation, encoding="utf-8")
    except OSError:
        pass


def describe_recovery(outcome: dict) -> str:
    """One bounded sentence naming the failed component and the attempted
    recovery. The operator reads this instead of "authority is required"."""
    recovery = outcome.get("recovery") or {}
    attempted = ", ".join(recovery.get("attempted") or []) or "none"
    detail = outcome.get("detail") or recovery.get("detail") or "no detail reported"
    log = recovery.get("log")
    text = (
        f"component {recovery.get('component') or 'SAIPEN host-authority broker'} "
        f"recovery-attempted [{attempted}] state {recovery.get('state')} -- {detail}"
    )
    if log:
        text += f" (log {log})"
    return text[:480]


def recovery_actions(outcome: dict, problems: object = None) -> list[str]:
    """The ONE operator action this failure leaves open, from the taxonomy.

    A list for wire compatibility; it holds a single entry on purpose. Three
    alternatives are three guesses the operator has to make."""
    listed = list(problems or [])
    failure = outcome.get("failure") if isinstance(outcome, dict) else None
    if failure and not listed:
        listed = [{"code": failure}]
    return [taxonomy.first_action(listed)]


def degraded_notice(
    problems: object = None, *, brief: bool = False, repair: str | None = None
) -> str:
    """The visible marker for a degraded session. Never claims admission.

    Plain words first -- what works and what is not verified -- then the
    specific missing proof and the one action that restores it, so the
    operator is never shown a bare downgrade they cannot act on. `brief` is the
    same marker for every later prompt of a session that was already told: one
    line, the code and the action, because repeating the paragraph on every
    prompt is noise the operator learns to stop reading.

    `repair` is the repair command of THIS session's installation (T-1747):
    the bare one repairs the default installation of every host and leaves a
    second configuration profile exactly as broken as it found it.
    """
    described = taxonomy.describe(list(problems or []))
    action = taxonomy.first_action(described)
    if repair and action == taxonomy.REPAIR:
        action = repair

    def named(item: dict) -> str:
        # The step is what tells one refusal under a code from another.
        step = taxonomy.as_step(item.get("step"))
        return f"{item.get('code')}/{step}" if step else str(item.get("code"))

    def said(item: dict) -> object:
        # A step names who could not be proven; the row above it only says
        # which family the refusal was filed under.
        return (
            taxonomy.step_summary(taxonomy.as_step(item.get("step")))
            or item.get("summary")
            or item.get("reason")
        )

    if brief:
        codes = ", ".join(named(item) for item in described[:3]) or "not proven"
        return (
            f"SAIPEN degraded mode: admission unverified ({codes}; "
            f"SAIPEN_ADMISSION_UNVERIFIED). Restore with: {action}"
        )
    reasons = "; ".join(f"{named(item)}: {said(item)}" for item in described[:3])
    why = f" Not verified because: {reasons}." if reasons else ""
    # The cap is spent on the explanation, never on the command: a repair
    # command cut in the middle of a profile path repairs nothing.
    tail = " To restore verification run: " + action
    head = (
        "SAIPEN is running in degraded mode. Model access works, but host admission "
        "is not mechanically verified (SAIPEN_ADMISSION_UNVERIFIED)." + why + " No "
        "admission record was written and nothing here claims ADMITTED."
    )
    return head[: max(0, 900 - len(tail))] + tail


__all__ = [
    "CODE_NOT_HOST_CLIENT",
    "CODE_SERVER_UNPROVEN",
    "CODE_UNREACHABLE",
    "SOURCE_DEFAULT",
    "SOURCE_INVALID",
    "SOURCE_OPERATOR",
    "already_delivered",
    "attempt_admission",
    "authority_mode",
    "authorize",
    "clear_authority_mode",
    "degraded_notice",
    "describe_recovery",
    "ensure",
    "evaluate",
    "health",
    "hook_invocation",
    "identify_self",
    "inspect_capability",
    "invalidate",
    "issue_operator_origin",
    "mode_path",
    "note_delivered",
    "policy",
    "prepare_operator_goal",
    "recovery_actions",
    "register_operator_worker",
    "retire_service",
    "revoke_operator_origin",
    "server_trusted",
    "set_authority_mode",
    "shutdown",
    "status",
    "trusted_service_entries",
    "verify_capability",
    "verify_operator_goal",
    "verify_operator_origin",
    "verify_operator_source",
    "verify_record",
]
