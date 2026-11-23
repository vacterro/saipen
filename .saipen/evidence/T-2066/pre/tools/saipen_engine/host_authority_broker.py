"""The SAIPEN host-authority broker: the separated local admission authority.

Defect class this closes: T-1563 established that a same-user Python hook cannot
prove host provenance, because the hook and any model-executed Python run as the
same OS principal, so every locally minted token is self-attestation. That
conclusion is right, and on its own it left the operator with a GUI that could
not be used: Claude Code's prompt boundary refused every prompt and the only
honest diagnostic was "a separated host authority is required".

This module IS that separated authority -- a local service that

* runs as its own process, outside the hook's process, and outlives a Claude GUI
  restart;
* keeps its signing key in memory only, so no writable file is authority and no
  capability can be forged from readable bytes;
* identifies the client by OS-derived process identity rather than by anything
  the client sends, and accepts exactly one shape: the host application's own
  hook invocation (`host_authority_identity`). "Somewhere under the host" is
  not that shape -- a command the model runs through the host's shell tool is
  under the host too, and it is refused;
* issues short-lived capabilities bound to the host adapter, the project, the
  Claude session, the model, the provider, the delivered authority fingerprints
  and a broker generation, and refuses a capability presented against any other
  binding;
* owns the admission ledger write, so the ledger record's provenance can only be
  checked against this live broker;
* fails closed when it cannot identify a client, and never accepts prose, prompt
  text, an environment variable or a magic phrase as admission.

Security boundary, stated honestly. The trust anchor is what the operating
system reports about live processes: a verified host image (its code signer
where the platform has one), started shells that carry exactly the hook command,
and the shipped hook bytes. That separates the host's own hook from a model's
tool call, from an unrelated same-user script and from an interpreter renamed
after the host. It is not a boundary against code injected INTO the host
process, a same-user process that rewrites the installed hook, or a forged
parent -- no same-user local scheme can prove those away, and none is claimed.
Identity is derived, never accepted: the request carries a project, a session
and a host name because those select the scope, and no identity claim at all.

Reads are not secrets. `ping`, `status`, `evaluate`, `verify` and
`verify-record` answer anyone: each is a question about a value only this
process can reproduce, so answering it gives the asker nothing to forge with
and lets a diagnostic run from an ordinary terminal tell the truth. Writing --
`admission`, `invalidate`, `authorize` -- is the hook's alone.

The broker answers one JSON frame per connection and never crashes on a
malformed request; `serve` is bounded and returns when its stop event is set.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
import secrets
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import host_authority_identity as identity_proof
from . import host_authority_process as proc
from . import host_authority_transport as transport

SERVICE = "saipen-authority-broker"
WIRE_VERSION = 1
SCHEMA_VERSION = 1
CAPABILITY_PREFIX = "cap"

#: How long a minted capability is accepted. Short by design: a stale session
#: re-admits automatically on its next prompt.
DEFAULT_TTL_SECONDS = 900
#: A broker that has never served an authenticated client for this long exits.
#: Zero disables the idle exit.
DEFAULT_IDLE_SECONDS = 1800
DEFAULT_ANCESTRY_LIMIT = 16
#: Bounded identity report attached to refusals, so the operator sees the chain.
MAX_CHAIN_REPORTED = 8
#: How many refusal lines one service writes to its log. A refusal is rare and
#: each line is bounded; the cap stops a local process that keeps asking from
#: growing the file, and the counts in `status` go on past it.
REFUSAL_LOG_LINES = 64

#: Image names that count as "the host application". Configuration, not policy
#: code: an operator whose GUI binary differs edits the registry, not this file.
HOST_IMAGES = ("claude.exe", "claude", "claude-code", "claude-code.exe")
#: Code-signer names a host image must carry where the platform reports one.
HOST_SIGNERS = ("Anthropic, PBC",)
#: How long a runtime-generation identity is believed before it is re-read.
#: Proving a generation hashes the whole shipped surface; doing that for every
#: prompt was most of the prompt's latency.
DEFAULT_IDENTITY_CACHE_SECONDS = 30
#: A test or diagnostic broker on an EXPLICIT runtime root may carry its own
#: policy here. The operator's real runtime root never reads this file, and a
#: broker on another root serves another endpoint, so a relaxed policy cannot
#: reach a production hook.
POLICY_OVERRIDE_NAME = "policy.json"

MODE_STRICT = "strict"
MODE_DEGRADED = "degraded"
MODES = (MODE_STRICT, MODE_DEGRADED)

#: Refusal codes. Registered in REGISTRY.json `error_codes`.
CODE_NOT_AUTHENTICATED = "BROKER_CLIENT_NOT_AUTHENTICATED"
CODE_IDENTITY_UNAVAILABLE = "BROKER_PEER_IDENTITY_UNAVAILABLE"
CODE_BAD_REQUEST = "BROKER_BAD_REQUEST"
CODE_CAPABILITY_INVALID = "BROKER_CAPABILITY_INVALID"
CODE_CAPABILITY_EXPIRED = "BROKER_CAPABILITY_EXPIRED"
CODE_CAPABILITY_REPLAY = "BROKER_CAPABILITY_REPLAY"
CODE_BINDING_MISMATCH = "BROKER_BINDING_MISMATCH"
CODE_GENERATION_STALE = "BROKER_GENERATION_STALE"
CODE_UNKNOWN_OP = "BROKER_UNKNOWN_OP"
CODE_EXISTS = "BROKER_ALREADY_RUNNING"
#: Ops that write or grant, and therefore require the hook-invocation proof.
WRITE_OPS = (
    "authorize",
    "admission",
    "invalidate",
    "issue-origin",
    "register-origin-worker",
    "revoke-origin",
)
#: Ops that only answer a question about values this process can reproduce.
READ_OPS = ("evaluate", "verify", "verify-record")
#: The one line the operator surface uses when nothing answers.
AUTHORITY_HINT = (
    "no host-authority broker answered; the prompt boundary starts it automatically "
    "when the asking process is the host application's own hook"
)

_CAPABILITY_FIELDS = (
    "instance",
    "capability_id",
    "expires",
    "project",
    "session",
    "host",
    "model",
    "provider",
    "adapter",
    "authority",
    "generation",
)

DEFAULT_SETTINGS = {
    "host_images": list(HOST_IMAGES),
    "host_signers": list(HOST_SIGNERS),
    "hook_shells": list(identity_proof.DEFAULT_SHELLS),
    "bridge_images": [],
    "ancestry_limit": DEFAULT_ANCESTRY_LIMIT,
    "max_shells": 4,
    "max_bridges": 2,
    "capability_ttl_seconds": DEFAULT_TTL_SECONDS,
    "idle_exit_seconds": DEFAULT_IDLE_SECONDS,
    "identity_cache_seconds": DEFAULT_IDENTITY_CACHE_SECONDS,
    "hosts": {},
}
_LIST_SETTINGS = ("host_images", "host_signers", "hook_shells", "bridge_images")
_INT_SETTINGS = (
    "ancestry_limit",
    "max_shells",
    "max_bridges",
    "capability_ttl_seconds",
    "idle_exit_seconds",
    "identity_cache_seconds",
)


# ------------------------------------------------------------------ helpers


def _sha(text: object, size: int = 64) -> str:
    return hashlib.sha256(str(text).encode("utf-8", errors="replace")).hexdigest()[:size]


def _now() -> float:
    return time.time()


def _bind_fingerprint(value: object, size: int = 24) -> str:
    return _sha(value, size)


def runtime_root(explicit: Path | None = None) -> Path:
    """The per-user directory holding this service's non-authoritative runtime
    state (singleton lock, health file, spawn log). Nothing in it is authority:
    the signing key lives in broker memory only."""
    if explicit is not None:
        return Path(explicit)
    return Path.home() / ".saipen" / "authority"


def scope(explicit: Path | None = None) -> str:
    """The endpoint scope token. One broker per user runtime root, so every
    process of this user -- and only this user -- meets the same endpoint."""
    root = runtime_root(explicit)
    return _sha(os.path.normcase(str(root.resolve())), 24)


def endpoint_name(explicit: Path | None = None) -> str:
    return transport.endpoint(scope(explicit))


def instance_id() -> str:
    return "broker-" + secrets.token_hex(12)


def settings(policy: dict | None = None, host: str | None = None) -> dict:
    """The broker's own settings from the protocol registry, with defaults."""
    merged = dict(DEFAULT_SETTINGS)
    if policy is None:
        try:
            from .registry import load_registry

            policy = (load_registry().get("protocol_admission") or {}).get("host_authority")
        except Exception:
            policy = None
    if isinstance(policy, dict):
        for key in DEFAULT_SETTINGS:
            if key in policy:
                merged[key] = policy[key]
    # Per-host authority policy (T-417): the registry may declare a distinct
    # host image/signer/shell shape for each host. A host that does not
    # declare one keeps the global policy, so claude keeps its current policy.
    if isinstance(host, str) and host:
        hosts = merged.get("hosts")
        if not isinstance(hosts, dict):
            hosts = (policy.get("hosts") if isinstance(policy, dict) else None) or {}
        override = hosts.get(host) if isinstance(hosts, dict) else None
        if isinstance(override, dict):
            for key in DEFAULT_SETTINGS:
                if key in override:
                    merged[key] = override[key]
    for key in _LIST_SETTINGS:
        merged[key] = [str(item) for item in (merged.get(key) or [])]
    for key in _INT_SETTINGS:
        try:
            merged[key] = int(merged[key])
        except (TypeError, ValueError):
            merged[key] = DEFAULT_SETTINGS[key]
    if not isinstance(merged.get("hosts"), dict):
        merged["hosts"] = {}
    return merged


def runtime_policy_override(runtime: Path | None) -> dict | None:
    """The policy file of an EXPLICIT runtime root, or None.

    None for the operator's default root, always: production policy comes from
    the protocol registry and from nowhere else.
    """
    if runtime is None:
        return None
    try:
        payload = json.loads((Path(runtime) / POLICY_OVERRIDE_NAME).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def service_generation() -> str:
    """A content identity of the code this service runs: the modules that make
    an admission decision. Reported by `ping` so a diagnostic can say that the
    running service predates the installed runtime; never used to grant."""
    digest = hashlib.sha256()
    here = Path(__file__).resolve().parent
    for name in (
        "host_authority_broker.py",
        "host_authority_identity.py",
        "host_authority_process.py",
        "host_authority_transport.py",
        "claude_profiles.py",
        "host_taxonomy.py",
        "protocol_admission.py",
    ):
        try:
            digest.update(name.encode("utf-8") + b"\0" + (here / name).read_bytes())
        except OSError:
            digest.update(name.encode("utf-8") + b"\0missing")
    return "svc-" + digest.hexdigest()[:24]


def hook_artifacts(host: str, home: object = None) -> tuple[str, ...]:
    """Where a host's hook is installed: the registry's surface under the
    operator's home (or the diagnostic home a test carrier names). A path
    alone admits nobody -- the bytes there must be the shipped ones and the
    host itself must have started them. One reader for the service's proof
    and for the client's decision whether a start makes sense at all."""
    try:
        from . import protocol_admission as pa

        entry = pa._adapters(pa.Context(project_root=None, session_id="", host=host)).get(host)
    except Exception:
        entry = None
    surface = str((entry or {}).get("hook_install_surface") or "")
    if not surface:
        return ()
    base = Path(str(home)) if home else Path.home()
    if surface.startswith("~"):
        return (str(base / surface[1:].lstrip("/\\")),)
    return (surface,)


def binding(project: Path | str | None, session: str, host: str, model, provider) -> dict:
    """The scope a capability is bound to. Every field is compared, not hashed
    away: two projects, sessions, models or providers never share a capability."""
    try:
        resolved = Path(project).resolve() if project else ""
    except (OSError, ValueError):
        resolved = str(project or "")
    return {
        "project": _bind_fingerprint(os.path.normcase(str(resolved))),
        "session": _bind_fingerprint(session),
        "host": str(host or ""),
        "model": str(model or ""),
        "provider": str(provider or ""),
    }


def adapter_fingerprint(saipen_root: Path | None, host: str | None = None) -> str:
    """The installed host adapter's own bytes. The broker reads the artifact
    itself; a client never supplies this field."""
    if saipen_root is None:
        return ""
    host = str(host or "claude")
    try:
        from . import protocol_admission as pa

        entry = (
            pa._adapters(pa.Context(project_root=None, session_id="", host=host)).get(host) or {}
        )
        artifact = entry.get("hook_artifact")
        if not artifact:
            artifact = f"extensions/adapters/{host}/saipen-guard.py"
    except Exception:
        artifact = f"extensions/adapters/{host}/saipen-guard.py"
    try:
        return hashlib.sha256((Path(saipen_root) / str(artifact)).read_bytes()).hexdigest()
    except OSError:
        return ""


# ------------------------------------------------------------------- capability


@dataclass(frozen=True)
class Minted:
    capability: str
    fields: dict


class Authority:
    """The broker's in-memory authority: one ephemeral key, one generation.

    The key is generated per broker process and never written anywhere. A broker
    restart therefore invalidates every capability it issued, which is what
    "generation" means here: the client re-admits automatically instead of the
    old token surviving a changed authority.
    """

    def __init__(self, *, ttl_seconds: int = DEFAULT_TTL_SECONDS, clock=_now) -> None:
        self.key = secrets.token_bytes(32)
        self.instance = instance_id()
        self.ttl_seconds = int(ttl_seconds)
        self.clock = clock
        self.started = clock()
        self._issued: dict[str, tuple[dict, float]] = {}
        self._lock = threading.Lock()

    def _mac(self, fields: dict) -> str:
        material = "|".join(str(fields.get(name, "")) for name in _CAPABILITY_FIELDS)
        return hmac.new(self.key, material.encode("utf-8"), hashlib.sha256).hexdigest()

    def mint(
        self,
        binding_fields: dict,
        *,
        generation: str,
        adapter: str,
        authority: str,
    ) -> Minted:
        issued = self.clock()
        expires = issued + self.ttl_seconds
        fields = {
            "instance": self.instance,
            "capability_id": secrets.token_hex(8),
            "issued": issued,
            "expires": expires,
            **binding_fields,
            "adapter": adapter,
            "authority": authority,
            "generation": generation,
        }
        fields["mac"] = self._mac(fields)
        capability = ".".join(
            [
                CAPABILITY_PREFIX,
                fields["instance"],
                str(int(expires)),
                fields["capability_id"],
                fields["mac"],
            ]
        )
        with self._lock:
            self._issued[fields["capability_id"]] = (dict(fields), expires)
            if len(self._issued) > 4096:
                cutoff = issued - self.ttl_seconds
                self._issued = {
                    key: value for key, value in self._issued.items() if value[1] > cutoff
                }
        return Minted(capability=capability, fields=fields)

    def verify(self, capability: object, binding_fields: dict) -> tuple[bool, str | None, str]:
        """(ok, refusal code, detail). Replay, expiry, a foreign generation and a
        transplanted binding are all distinct refusals, never one generic error.

        Two independent things are required: the capability must name an entry
        THIS process minted (so replay from a written-down string fails), and its
        mac must recompute from the broker's in-memory key (so a forged shape
        fails even if a capability id were guessed).
        """
        if not isinstance(capability, str) or not capability:
            return False, CODE_CAPABILITY_INVALID, "no capability presented"
        parts = capability.split(".")
        if len(parts) != 5 or parts[0] != CAPABILITY_PREFIX:
            return False, CODE_CAPABILITY_INVALID, "malformed capability"
        _, instance, expires_text, capability_id, mac = parts
        if instance != self.instance:
            return False, CODE_CAPABILITY_INVALID, "capability was issued by another generation"
        try:
            expires = float(expires_text)
        except ValueError:
            return False, CODE_CAPABILITY_INVALID, "unreadable expiry"
        with self._lock:
            known = self._issued.get(capability_id)
        if known is None:
            return False, CODE_CAPABILITY_REPLAY, "capability is not one this broker issued"
        fields, minted_expires = known
        if self.clock() > expires or self.clock() > minted_expires:
            return False, CODE_CAPABILITY_EXPIRED, "capability has expired"
        if str(int(expires)) != str(int(minted_expires)):
            return False, CODE_CAPABILITY_INVALID, "presented expiry is not the minted expiry"
        for name in ("project", "session", "host", "model", "provider"):
            if str(fields.get(name, "")) != str(binding_fields.get(name, "")):
                return (
                    False,
                    CODE_BINDING_MISMATCH,
                    f"capability is bound to another {name}",
                )
        if not hmac.compare_digest(self._mac(fields), str(mac)):
            return False, CODE_CAPABILITY_INVALID, "capability mac does not verify"
        return True, None, "capability verified against the issuing broker"


def capability_fields(capability: str) -> dict:
    """A JSON-safe, non-secret view of a capability for diagnostics."""
    parts = str(capability or "").split(".")
    if len(parts) != 5:
        return {"valid_shape": False}
    return {
        "valid_shape": True,
        "prefix": parts[0],
        "instance": parts[1],
        "expires": parts[2],
        "capability_id": parts[3],
    }


# ------------------------------------------------------------------- ledger


class Ledger:
    """The admission ledger, owned by the broker.

    The provenance of every record is an HMAC under the broker's in-memory key,
    so a record written by an ordinary same-user process cannot be made to look
    authoritative: verification is a question only this live broker can answer.
    """

    def __init__(self, authority: Authority) -> None:
        self.authority = authority

    #: The two fields that carry integrity rather than content.
    UNSEALED = ("seal", "provenance")

    def _provenance(self, body: dict) -> dict:
        material = json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return {
            "kid": self.authority.instance,
            "alg": "hmac-sha256",
            "mac": hmac.new(self.authority.key, material, hashlib.sha256).hexdigest(),
        }

    def seal_payload(self, record: dict) -> dict:
        """Key an owner-built event without turning an admission into intent."""
        body = {key: value for key, value in record.items() if key != "provenance"}
        return {**body, "provenance": self._provenance(body)}

    def seal(self, record: dict, capability: str, delivery_digest: dict) -> dict:
        """The record the owner reads, plus the provenance only this broker can
        reproduce. The corruption seal is the owner's own function, computed over
        the same body, so a broker record and a locally built one are the same
        shape and the difference between them is the keyed provenance."""
        from . import protocol_admission as pa

        body = {key: value for key, value in record.items() if key not in self.UNSEALED}
        body["delivered"] = delivery_digest
        body["capability_shape"] = capability_fields(capability)
        body["seal"] = pa._seal(body)
        body["provenance"] = self._provenance(body)
        return body

    def verify(self, record: dict) -> tuple[bool, str]:
        provenance = record.get("provenance")
        if not isinstance(provenance, dict):
            return False, "record carries no provenance"
        if provenance.get("kid") != self.authority.instance:
            return False, "record was provenanced by another generation"
        if provenance.get("alg") != "hmac-sha256":
            return False, "record provenance algorithm is not this broker's"
        body = {key: value for key, value in record.items() if key != "provenance"}
        material = json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
        expected = hmac.new(self.authority.key, material, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(provenance.get("mac") or ""), expected):
            return False, "record provenance mac does not verify"
        return True, "record verified against the issuing broker"

    @staticmethod
    def path(project_root: Path, session: str) -> Path:
        from . import protocol_admission as pa

        return Path(pa._ledger_path(Path(project_root), session))

    def read(self, project_root: Path, session: str) -> dict | None:
        try:
            record = json.loads(self.path(project_root, session).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(record, dict) or record.get("schema") != SCHEMA_VERSION:
            return None
        if record.get("session") != session:
            return None
        return record

    def write(self, project_root: Path, session: str, record: dict) -> bool:
        path = self.path(project_root, session)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        temporary = path.with_name(f"{path.name}.{os.getpid()}.{secrets.token_hex(4)}.partial")
        try:
            temporary.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, path)
        except OSError:
            with contextlib.suppress(OSError):
                temporary.unlink()
            return False
        return True

    def remove(self, project_root: Path, session: str) -> bool:
        with contextlib.suppress(OSError):
            self.path(project_root, session).unlink()
            return True
        return False


# ------------------------------------------------------------------- broker


@dataclass
class Stats:
    started: float = field(default_factory=_now)
    served: int = 0
    authenticated: int = 0
    refused: int = 0
    last_client: dict | None = None
    last_refusal: dict | None = None
    last_activity: float = field(default_factory=_now)


class Broker:
    """One live authority. Holds the key, the ledger and the counts."""

    def __init__(
        self,
        *,
        saipen_root: Path | None = None,
        runtime: Path | None = None,
        config: dict | None = None,
        max_requests: int | None = None,
        clock=_now,
        authenticator=None,
        refusal_sink=None,
    ) -> None:
        #: A caller that CONSTRUCTS a broker in its own process may supply the
        #: client authenticator. The shipped service never does (`run_service`
        #: passes nothing), so this is not a way into a running authority: it
        #: is how the capability, ledger and lifecycle logic is exercised
        #: without a host, while `identify` itself is proven on real processes.
        self._authenticator = authenticator
        #: Where a refused client leaves its one line (T-1649). The shipped
        #: service passes `service_log_line`; a broker constructed in another
        #: process writes nothing unless it is given a sink, so a test or a
        #: diagnostic never prints into its caller's stream.
        self._refusal_sink = refusal_sink
        self._refusal_lines = 0
        self.config = dict(config) if config is not None else settings()
        for key, value in DEFAULT_SETTINGS.items():
            self.config.setdefault(key, list(value) if isinstance(value, list) else value)
        self.authority = Authority(
            ttl_seconds=int(self.config.get("capability_ttl_seconds") or DEFAULT_TTL_SECONDS),
            clock=clock,
        )
        self.ledger = Ledger(self.authority)
        from .operator_origin import OperatorOrigins

        self.origins = OperatorOrigins(
            self.ledger,
            clock=clock,
            ancestry=proc.ancestry,
            ttl=self.authority.ttl_seconds,
        )
        self.saipen_root = Path(saipen_root) if saipen_root else None
        self.runtime = runtime_root(runtime)
        self.max_requests = max_requests
        self.stats = Stats()
        self.stop = threading.Event()
        self.clock = clock
        self.generation = service_generation()
        #: Runtime-generation identities this service currently believes, and
        #: when it started believing them (`identity_cache_seconds`).
        self._identity_memo: dict = {}
        self._identity_born = clock()

    # ---------------------------------------------------------- identity

    def _hook_artifacts(self, host: str, home: object) -> tuple[str, ...]:
        return hook_artifacts(host, home)

    def _artifact_current(self, host: str):
        """A check that an installed hook file carries the shipped bytes."""

        def current(script: str) -> bool:
            try:
                from . import protocol_admission as pa
                from .runtime_surface import normalize_content

                entry = (
                    pa._adapters(pa.Context(project_root=None, session_id="", host=host)).get(host)
                    or {}
                )
                artifact = entry.get("hook_artifact")
                if not artifact or self.saipen_root is None:
                    return False
                shipped = (Path(self.saipen_root) / str(artifact)).read_bytes()
                installed = Path(script).read_bytes()
            except Exception:
                return False
            return normalize_content(installed) == normalize_content(shipped)

        return current

    def identify(
        self, peer, host: str = "claude", home: object = None
    ) -> tuple[bool, str | None, dict]:
        """Authenticate the client from the OS, never from the request.

        The answer is a proof or a reason: `detail["reason"]` names exactly
        which part of the hook invocation could not be shown, and that reason
        is what the operator's diagnostic repeats.
        """
        if self._authenticator is not None:
            return self._authenticator(peer, host, home)
        # Per-host policy (T-417): a host that declares its own image/signer/
        # shell shape overrides the global policy for this identify() call.
        host_cfg = dict(self.config)
        hosts = host_cfg.get("hosts")
        if isinstance(hosts, dict) and isinstance(hosts.get(host), dict):
            host_cfg.update(hosts.get(host) or {})
        limit = int(host_cfg.get("ancestry_limit") or DEFAULT_ANCESTRY_LIMIT)
        if peer is None or getattr(peer, "pid", None) is None or not proc.platform_supported():
            return (
                False,
                CODE_IDENTITY_UNAVAILABLE,
                {
                    "transport": getattr(peer, "kind", "unknown"),
                    "reason": identity_proof.REASON_IDENTITY_UNAVAILABLE,
                    "detail": "the platform reported no client identity for this connection",
                    "identity": {"supported": proc.platform_supported(), "chain": []},
                },
            )
        signers = tuple(host_cfg.get("host_signers") or ()) if proc.signing_supported() else ()
        policy = identity_proof.IdentityPolicy(
            host=str(host or ""),
            host_images=tuple(host_cfg.get("host_images") or ()),
            hook_artifacts=self._hook_artifacts(str(host or ""), home),
            host_signers=signers,
            shells=tuple(host_cfg.get("hook_shells") or identity_proof.DEFAULT_SHELLS),
            bridge_images=tuple(host_cfg.get("bridge_images") or ()),
            max_shells=int(host_cfg.get("max_shells") or 4),
            max_bridges=int(host_cfg.get("max_bridges") or 2),
            profile_hook="hooks/saipen-guard.py" if host == "claude" else None,
        )
        from .claude_profiles import hook_for_process

        proof = identity_proof.prove_hook_invocation(
            proc.ancestry(int(peer.pid), limit),
            policy,
            signer_of=proc.image_signer,
            artifact_current=self._artifact_current(str(host or "")),
            hook_for_host=lambda pid: hook_for_process(pid, Path(str(home)) if home else None),
            report_limit=MAX_CHAIN_REPORTED,
        )
        view = {
            "transport": getattr(peer, "kind", "unknown"),
            "pid": int(peer.pid),
            "host_image": (proof.host_image or "").rsplit("/", 1)[-1] or None,
            "host_pid": proof.host_pid,
            "host_signer": proof.host_signer,
            "hook_pid": proof.hook_pid,
            "profile": proof.profile,
            "chain": [
                {key: item.get(key) for key in ("pid", "ppid", "image", "name")}
                for item in proof.chain
            ],
        }
        if proof.ok:
            return True, None, view
        view.update(
            {
                "reason": proof.reason,
                "detail": proof.detail,
                "host_images": list(policy.host_images),
                "host_signers": list(policy.host_signers),
                "identity": {"supported": True, "chain": view["chain"], "detail": proof.detail},
            }
        )
        code = (
            CODE_IDENTITY_UNAVAILABLE
            if proof.reason == identity_proof.REASON_IDENTITY_UNAVAILABLE
            else CODE_NOT_AUTHENTICATED
        )
        return False, code, view

    def _components(self, ctx, policy: dict) -> dict:
        """`protocol_admission.components` against this service's identity memo.

        The memo is dropped every `identity_cache_seconds`, so a stale hook or
        a reinstalled runtime is noticed within that window instead of being
        re-proved on every prompt.
        """
        from . import protocol_admission as pa
        from .runtime_surface import identity_memo

        ttl = int(self.config.get("identity_cache_seconds") or 0)
        now = self.clock()
        if ttl <= 0 or now - self._identity_born > ttl or now < self._identity_born:
            self._identity_memo = {}
            self._identity_born = now
        with identity_memo(self._identity_memo):
            return pa.components(ctx, policy)

    # ------------------------------------------------------------ ops

    def handle(self, payload: object, peer) -> dict:
        self.stats.served += 1
        if not isinstance(payload, dict):
            return self._refuse(CODE_BAD_REQUEST, "request is not a JSON object")
        op = payload.get("op")
        if payload.get("v") not in (None, WIRE_VERSION):
            return self._refuse(CODE_BAD_REQUEST, "unsupported wire version")
        if op == "ping":
            return self._ping()
        if op == "status":
            return self._status(peer, payload)
        if op == "shutdown":
            # Stopping the service is never a trust decision: whoever may ask
            # for this may already end the process. Its key dies with it, so
            # every session simply re-admits against the next generation.
            self.stop.set()
            return {"ok": True, "code": "BROKER_SHUTDOWN", "detail": "shutdown requested"}
        if op == "verify-origin":
            self.stats.last_activity = self.clock()
            return self.origins.verify(payload, peer)
        if op == "verify-source-origin":
            self.stats.last_activity = self.clock()
            return self.origins.received_source(payload)
        if op == "prepare-origin-goal":
            return self.origins.prepare_goal(payload, peer)
        if op == "verify-origin-goal":
            return self.origins.verify_goal(payload, peer)
        if op == "verify-origin-campaign":
            return self.origins.verify_campaign(payload, peer)
        if op == "prepare-origin-debt":
            return self.origins.prepare_debt(payload, peer)
        if op == "verify-origin-debt":
            return self.origins.verify_debt(payload)
        if op in READ_OPS:
            self.stats.last_activity = self.clock()
            if op == "evaluate":
                return self._evaluate(payload)
            if op == "verify":
                return self._verify(payload)
            return self._verify_record(payload)
        if op not in WRITE_OPS:
            return self._refuse(CODE_UNKNOWN_OP, f"unknown op {op!r}")
        host_arg = payload.get("host")
        if not host_arg and isinstance(payload.get("proof"), dict):
            proof_obj = payload["proof"]
            proof_data = (
                proof_obj.get("proof") if isinstance(proof_obj.get("proof"), dict) else proof_obj
            )
            if isinstance(proof_data, dict):
                host_arg = proof_data.get("host")
        ok, code, detail = self.identify(peer, host_arg or "", payload.get("home"))
        if not ok:
            # The identity detail is the refusal detail: it names what the OS
            # saw, which is the only thing that explains a refusal here.
            self.stats.last_refusal = {
                "at": self.clock(),
                "op": op,
                "code": code,
                "reason": detail.get("reason"),
                "detail": detail.get("detail"),
            }
            self._log_refusal(op, code, payload.get("host"), detail)
            return self._refuse(
                code, str(detail.get("detail") or "client refused"), identity=detail
            )
        self.stats.authenticated += 1
        self.stats.last_client = detail
        self.stats.last_activity = self.clock()
        if op == "issue-origin":
            scope_fields, refusal = self._scope(payload)
            if refusal is not None:
                return refusal
            if payload.get("event") != "UserPromptSubmit":
                return self._refuse(CODE_BAD_REQUEST, "operator issue requires a native user event")
            return self.origins.issue(
                scope_fields,
                detail,
                text=payload.get("request_text"),
                event_id=payload.get("event_id"),
                action=payload.get("action"),
            )
        if op == "register-origin-worker":
            return self.origins.register_worker(payload.get("proof"), detail, payload.get("worker"))
        if op == "revoke-origin":
            return self.origins.revoke(payload.get("proof"), detail)
        if op == "authorize":
            return self._authorize(payload, detail)
        if op == "admission":
            return self._admission(payload, detail)
        return self._invalidate(payload, detail)

    def _refuse(self, code: str | None, detail: str, **extra) -> dict:
        self.stats.refused += 1
        return {"ok": False, "code": code, "detail": detail, **extra}

    def _log_refusal(self, op: object, code: object, host: object, detail: dict) -> None:
        """One bounded line for a client the OS proof refused (T-1649).

        `status` keeps only the last refusal and only while this process lives,
        so an intermittent one was gone before anyone asked. The line names the
        step that refused and the image names of the process chain the OS
        reported: what was SEEN, never a capability, a key or request content.
        """
        if self._refusal_sink is None or self._refusal_lines >= REFUSAL_LOG_LINES:
            return
        self._refusal_lines += 1

        def short(value: object, limit: int = 48) -> str:
            return " ".join(str(value or "").split())[:limit]

        def image(item: dict) -> str:
            path = str(item.get("name") or item.get("image") or "").replace("\\", "/")
            return short(path.rsplit("/", 1)[-1])

        seen = [item for item in (detail.get("chain") or []) if isinstance(item, dict)]
        chain = [image(item) for item in seen[:MAX_CHAIN_REPORTED]]
        record = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.clock())),
            "event": "client_refused",
            "op": short(op, 24),
            "code": short(code),
            "step": short(detail.get("reason")) or None,
            "host": short(host, 24) or None,
            "pid": detail.get("pid") if isinstance(detail.get("pid"), int) else None,
            "chain": chain,
        }
        if self._refusal_lines == REFUSAL_LOG_LINES:
            record["capped"] = True
        line = json.dumps(record, ensure_ascii=True, sort_keys=True)
        with contextlib.suppress(OSError, ValueError):
            self._refusal_sink(line)

    def _ping(self) -> dict:
        return {
            "ok": True,
            "service": SERVICE,
            "instance": self.authority.instance,
            "started": self.authority.started,
            "protocol": WIRE_VERSION,
            "generation": self.generation,
            "pid": os.getpid(),
            "saipen_root": str(self.saipen_root) if self.saipen_root else None,
        }

    def _status(self, peer, payload: dict | None = None) -> dict:
        request = payload or {}
        ok, code, detail = self.identify(peer, request.get("host") or "claude", request.get("home"))
        view = {
            "ok": True,
            "service": SERVICE,
            "instance": self.authority.instance,
            "protocol": WIRE_VERSION,
            "generation": self.generation,
            "pid": os.getpid(),
            "started": self.authority.started,
            "uptime": self.clock() - self.authority.started,
            "served": self.stats.served,
            "authenticated_requests": self.stats.authenticated,
            "refused_requests": self.stats.refused,
            "last_client": self.stats.last_client,
            "last_refusal": self.stats.last_refusal,
            "host_signers": list(self.config.get("host_signers") or []),
            "signing_supported": proc.signing_supported(),
            "authenticated": ok,
            "identity_supported": proc.platform_supported(),
            "peer_identity_supported": transport.peer_supported(),
            "transport": transport.endpoint(scope(self.runtime)),
            "runtime_root": str(self.runtime),
            "host_images": list(self.config.get("host_images") or []),
            "capability_ttl_seconds": int(
                self.config.get("capability_ttl_seconds") or DEFAULT_TTL_SECONDS
            ),
            "saipen_root": str(self.saipen_root) if self.saipen_root else None,
        }
        if not ok:
            view["code"] = code
            view["detail"] = detail
        return view

    def _scope(self, payload: dict) -> tuple[dict | None, dict | None]:
        """(binding, refusal). The project must really be a bound SAIPEN project."""
        project = payload.get("project")
        session = payload.get("session")
        host = payload.get("host")
        if not isinstance(session, str) or not session:
            return None, self._refuse(CODE_BAD_REQUEST, "session is required")
        if not isinstance(host, str) or not host:
            return None, self._refuse(CODE_BAD_REQUEST, "host is required")
        if not project:
            return None, self._refuse(CODE_BAD_REQUEST, "project is required")
        try:
            root = Path(str(project)).resolve()
        except (OSError, ValueError):
            return None, self._refuse(CODE_BAD_REQUEST, "project path is unreadable")
        if not (root / ".saipen" / "STATE.md").is_file():
            return None, self._refuse(CODE_BAD_REQUEST, f"not a bound SAIPEN project: {root}")
        return {
            "root": root,
            "session": session,
            "host": host,
            "model": payload.get("model"),
            "provider": payload.get("provider"),
            "authority_root": payload.get("authority_root"),
            "home": payload.get("home"),
            "event": payload.get("event") or "hook",
            "profile": payload.get("profile"),
        }, None

    def _context(self, scope_fields: dict):
        from . import protocol_admission as pa

        return pa.Context(
            project_root=scope_fields["root"],
            session_id=scope_fields["session"],
            host=scope_fields["host"],
            model=scope_fields["model"],
            provider=scope_fields["provider"],
            authority_root=(
                Path(scope_fields["authority_root"]) if scope_fields["authority_root"] else None
            ),
            home=Path(scope_fields["home"]) if scope_fields["home"] else None,
            profile=Path(scope_fields["profile"]) if scope_fields.get("profile") else None,
        )

    def _authorize(self, payload: dict, identity: dict) -> dict:
        """Read-only: may this authenticated client act on this scope at all?"""
        scope_fields, refusal = self._scope(payload)
        if refusal is not None:
            return refusal
        capability = payload.get("capability")
        if capability:
            ok, code, detail = self.authority.verify(
                capability,
                binding(
                    scope_fields["root"],
                    scope_fields["session"],
                    scope_fields["host"],
                    scope_fields["model"],
                    scope_fields["provider"],
                ),
            )
            return {
                "ok": ok,
                "code": code,
                "detail": detail,
                "event": payload.get("verb") or "hook",
                "identity": identity,
            }
        self.stats.last_activity = self.clock()
        return {
            "ok": True,
            "code": None,
            "detail": "client is the host application's own hook invocation",
            "event": payload.get("verb") or "hook",
            "identity": identity,
        }

    def _admission(self, payload: dict, identity: dict) -> dict:
        from . import protocol_admission as pa

        scope_fields, refusal = self._scope(payload)
        if refusal is not None:
            return refusal
        proven_profile = identity.get("profile")
        claimed_profile = scope_fields.get("profile")
        if proven_profile:
            if claimed_profile and identity_proof.norm_path(
                claimed_profile
            ) != identity_proof.norm_path(proven_profile):
                return self._refuse(
                    CODE_BINDING_MISMATCH,
                    "requested profile differs from the host's observed profile",
                )
            scope_fields["profile"] = proven_profile
        ctx = self._context(scope_fields)
        policy = pa.load_policy()
        if payload.get("fresh"):
            # A new, resumed, cleared or compacted context holds nothing the
            # old record proved: drop it before deciding anything.
            self.ledger.remove(scope_fields["root"], scope_fields["session"])
        found = self._components(ctx, policy)
        if found["problems"]:
            # The authority states what is wrong and nothing more. Whether the
            # prompt may proceed unverified is the operator's policy, applied
            # by the owner that asked.
            verdict = pa._verdict(
                pa.STATE_REFUSED,
                problems=found["problems"],
                stale=[],
                warnings=found["warnings"],
                unobserved=[],
            )
            verdict["delivery"] = ""
            verdict["failed_component"] = "authority"
            return {"ok": False, **verdict, "identity": identity}

        generation = pa.generation(found["proofs"])
        scope_binding = binding(
            scope_fields["root"],
            scope_fields["session"],
            scope_fields["host"],
            scope_fields["model"],
            scope_fields["provider"],
        )
        adapter = adapter_fingerprint(self.saipen_root, scope_fields.get("host"))
        authority_digest = _sha(json.dumps(found["proofs"], sort_keys=True))
        record = self.ledger.read(scope_fields["root"], scope_fields["session"])
        proven = bool(record) and self.ledger.verify(record)[0]

        if proven:
            stale = pa.staleness(record, ctx, found["proofs"])
            if not stale:
                return {
                    "ok": True,
                    **pa._verdict(
                        pa.STATE_ADMITTED,
                        problems=[],
                        stale=[],
                        warnings=found["warnings"],
                        unobserved=[],
                        generation=generation,
                        token=record.get("token"),
                    ),
                    "delivery": "",
                    "previous_state": pa.STATE_ADMITTED,
                    "capability": record.get("capability"),
                    "capability_fields": record.get("capability_shape"),
                    "record_written": False,
                    "instance": self.authority.instance,
                    "identity": identity,
                }
            state = pa.STATE_STALE
            stale_names = stale
        else:
            state = pa.STATE_BINDING
            stale_names = []

        minted = self.authority.mint(
            scope_binding,
            generation=generation,
            adapter=adapter,
            authority=authority_digest,
        )
        token = "tok-" + _sha(
            json.dumps(
                [
                    generation,
                    scope_fields["session"],
                    scope_fields["model"],
                    scope_fields["provider"],
                ]
            ),
            32,
        )
        delivered = {
            name: _sha(found["texts"][name])
            for name in pa.AUTHORITY_DOCUMENTS
            if name in found["texts"]
        }
        delivered.update(
            {
                f"skill:{skill['name']}": skill["fingerprint"]
                for skill in found["skills"]
                if skill.get("resolved")
            }
        )
        record_body = {
            "schema": SCHEMA_VERSION,
            "session": scope_fields["session"],
            "host": scope_fields["host"],
            "model": scope_fields["model"],
            "provider": scope_fields["provider"],
            "proofs": found["proofs"],
            "generation": generation,
            "token": token,
            "adapter": adapter,
            "authority": authority_digest,
            "binding": scope_binding,
            "issued": minted.fields["issued"],
            "expires": minted.fields["expires"],
            "capability": minted.capability,
            "event": scope_fields["event"],
            "client": identity,
        }
        record_body = self.ledger.seal(record_body, minted.capability, delivered)
        written = self.ledger.write(scope_fields["root"], scope_fields["session"], record_body)
        verdict = pa._verdict(
            pa.STATE_ADMITTED,
            problems=[],
            stale=stale_names,
            warnings=found["warnings"],
            unobserved=[],
            generation=generation,
            token=token,
        )
        verdict["delivery"] = pa._delivery(found, generation)
        return {
            "ok": True,
            **verdict,
            # What the session was before this handshake: BINDING (nothing yet)
            # or STALE (a proven generation changed). The answer is ADMITTED
            # either way, because this call just minted and wrote the record.
            "previous_state": state,
            "capability": minted.capability,
            "capability_fields": capability_fields(minted.capability),
            "record_written": written,
            "expires": minted.fields["expires"],
            "instance": self.authority.instance,
            "identity": identity,
        }

    def _invalidate(self, payload: dict, identity: dict) -> dict:
        scope_fields, refusal = self._scope(payload)
        if refusal is not None:
            return refusal
        removed = self.ledger.remove(scope_fields["root"], scope_fields["session"])
        return {
            "ok": True,
            "code": None,
            "removed": removed,
            "reason": str(payload.get("reason") or ""),
            "identity": identity,
        }

    def _evaluate(self, payload: dict) -> dict:
        """Read-only: what is this session's admission state right now?

        Answers anyone and writes nothing. The state comes from this service's
        own key and ledger, so a caller learns whether a record is genuine and
        current and gains nothing it could present anywhere.
        """
        from . import protocol_admission as pa

        scope_fields, refusal = self._scope(payload)
        if refusal is not None:
            return refusal
        ctx = self._context(scope_fields)
        found = self._components(ctx, pa.load_policy())
        base = {"ok": True, "instance": self.authority.instance}
        if found["problems"]:
            return {
                **base,
                **pa._verdict(
                    pa.STATE_REFUSED,
                    problems=found["problems"],
                    stale=[],
                    warnings=found["warnings"],
                    unobserved=[],
                ),
            }
        generation = pa.generation(found["proofs"])
        record = self.ledger.read(scope_fields["root"], scope_fields["session"])
        if not record or not self.ledger.verify(record)[0]:
            return {
                **base,
                **pa._verdict(
                    pa.STATE_BINDING,
                    problems=[],
                    stale=[],
                    warnings=found["warnings"],
                    unobserved=[],
                    generation=generation,
                ),
            }
        stale = pa.staleness(record, ctx, found["proofs"])
        return {
            **base,
            **pa._verdict(
                pa.STATE_STALE if stale else pa.STATE_ADMITTED,
                problems=[],
                stale=stale,
                warnings=found["warnings"],
                unobserved=pa.unobserved(record, ctx),
                generation=generation,
                token=record.get("token"),
            ),
        }

    def _verify(self, payload: dict) -> dict:
        capability = payload.get("capability")
        scope_fields, refusal = self._scope(payload)
        if refusal is not None:
            return refusal
        ok, code, detail = self.authority.verify(
            capability,
            binding(
                scope_fields["root"],
                scope_fields["session"],
                scope_fields["host"],
                scope_fields["model"],
                scope_fields["provider"],
            ),
        )
        return {"ok": ok, "code": code, "detail": detail}

    def _verify_record(self, payload: dict) -> dict:
        record = payload.get("record")
        if not isinstance(record, dict):
            return self._refuse(CODE_BAD_REQUEST, "record is required")
        ok, detail = self.ledger.verify(record)
        return {"ok": ok, "code": None if ok else CODE_CAPABILITY_INVALID, "detail": detail}


# ------------------------------------------------------------- lifecycle


def health(runtime: Path | None = None, *, timeout: float = 1.0) -> dict | None:
    """The running broker's own report, or None when nothing answers."""
    try:
        reply = transport.request(
            endpoint_name(runtime), {"v": WIRE_VERSION, "op": "ping"}, timeout=timeout
        )
    except transport.TransportError:
        return None
    return reply if isinstance(reply, dict) and reply.get("ok") else None


def _pid_alive(pid: int) -> bool:
    try:
        if os.name == "nt":
            fact = proc.process_fact(int(pid))
            return fact is not None
        os.kill(int(pid), 0)
    except (OSError, ValueError, ProcessLookupError):
        return False
    return True


def lock_path(runtime: Path | None = None) -> Path:
    return runtime_root(runtime) / "broker.lock"


def status_path(runtime: Path | None = None) -> Path:
    return runtime_root(runtime) / "broker.json"


def service_log_line(line: str) -> None:
    """One line into the running service's log: `spawn` opens that file as the
    service's stderr, which is the file the recovery diagnostics name."""
    print(line, file=sys.stderr, flush=True)


def log_path(runtime: Path | None = None) -> Path:
    return runtime_root(runtime) / "broker.log"


def acquire_lock(runtime: Path | None = None) -> tuple[bool, str]:
    """Singleton by owner pid: (acquired, detail). A stale lock is reclaimed."""
    path = lock_path(runtime)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, f"runtime directory is not writable: {exc}"
    for _attempt in range(2):
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                holder = json.loads(path.read_text(encoding="utf-8"))
                pid = int(holder.get("pid") or 0)
            except (OSError, ValueError, TypeError):
                pid = 0
            if pid and _pid_alive(pid):
                return False, f"another broker is already running (pid {pid})"
            with contextlib.suppress(OSError):
                path.unlink()
            continue
        except OSError as exc:
            return False, f"lock cannot be created: {exc}"
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(json.dumps({"pid": os.getpid(), "started": _now()}))
        return True, "acquired"
    return False, "another broker holds the lock"


def release_lock(runtime: Path | None = None) -> None:
    with contextlib.suppress(OSError):
        lock_path(runtime).unlink()


def write_status(payload: dict, runtime: Path | None = None) -> bool:
    path = status_path(runtime)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError:
        return False
    return True


def read_status(runtime: Path | None = None) -> dict | None:
    try:
        payload = json.loads(status_path(runtime).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def spawn(
    saipen_root: Path | None,
    *,
    runtime: Path | None = None,
    wait: float = 6.0,
) -> dict:
    """Start a detached broker process and wait for it to answer. Bounded.

    The child is fully detached: it is not a terminal job, it survives the GUI,
    and it inherits no stdin. Its stdout and stderr go to the runtime log, which
    is the file the recovery diagnostics point the operator at.
    """
    entry = Path(__file__).resolve().parents[1] / "authority_service.py"
    if not entry.is_file():
        return {"ok": False, "started": False, "detail": f"service entry is missing: {entry}"}
    log = log_path(runtime)
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        stream = open(log, "ab")  # noqa: SIM115 - the child owns this handle
    except OSError as exc:
        return {"ok": False, "started": False, "detail": f"spawn log is not writable: {exc}"}
    argv = [sys.executable, str(entry), "serve"]
    if saipen_root is not None:
        argv += ["--saipen-root", str(saipen_root)]
    if runtime is not None:
        argv += ["--runtime", str(runtime)]
    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP on Windows; a new session
    # elsewhere. Both spellings are passed explicitly: each platform ignores
    # the other's, and nothing about this call is hidden in a dict.
    detached = (0x00000008 | 0x00000200) if os.name == "nt" else 0
    try:
        child = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=stream,
            close_fds=True,
            creationflags=detached,
            start_new_session=os.name != "nt",
        )
    except (OSError, ValueError) as exc:
        stream.close()
        return {"ok": False, "started": False, "detail": f"broker could not be started: {exc}"}
    deadline = _now() + max(0.0, wait)
    attempts = 0
    while _now() < deadline:
        time.sleep(min(0.15, max(0.0, deadline - _now())))
        attempts += 1
        remaining = deadline - _now()
        if remaining <= 0:
            break
        report = health(runtime, timeout=min(1.0, remaining))
        if report:
            return {
                "ok": True,
                "started": True,
                "pid": child.pid,
                "attempts": attempts,
                "instance": report.get("instance"),
                "log": str(log),
            }
    return {
        "ok": False,
        "started": True,
        "pid": child.pid,
        "attempts": attempts,
        "detail": "the started broker did not answer within the wait budget",
        "log": str(log),
    }


def run_service(
    *,
    saipen_root: Path | None = None,
    runtime: Path | None = None,
    idle_seconds: int | None = None,
    max_requests: int | None = None,
    stop: threading.Event | None = None,
) -> int:
    """Run the broker until stopped. Returns a process exit code."""
    config = settings()
    override = runtime_policy_override(runtime)
    if override:
        config = settings({**config, **override})
    idle = int(config.get("idle_exit_seconds") or 0) if idle_seconds is None else int(idle_seconds)
    acquired, detail = acquire_lock(runtime)
    if not acquired:
        return 0 if "already running" in detail else 1
    broker = Broker(
        saipen_root=saipen_root,
        runtime=runtime,
        config=config,
        max_requests=max_requests,
        refusal_sink=service_log_line,
    )
    stop_event = stop if stop is not None else broker.stop
    watchdog: threading.Thread | None = None

    def idle_watch() -> None:
        # The key lives in this process, so leaving costs every open session a
        # full re-delivery. Idle alone is therefore not a reason to go: the
        # service stays while a host application is still running, and leaves
        # once it is idle AND no host is left to serve. Where the platform
        # cannot list processes, plain idleness decides, as before.
        # Only the operator's real endpoint waits for hosts: a diagnostic or
        # test service on an explicit runtime root serves nobody's session and
        # leaves on idleness alone, or it would outlive every run that made it.
        images = list(config.get("host_images") or []) if runtime is None else []
        if runtime is None:
            hosts = config.get("hosts")
            if isinstance(hosts, dict):
                for override in hosts.values():
                    if isinstance(override, dict):
                        images.extend(str(item) for item in (override.get("host_images") or []))
        images = list(dict.fromkeys(images))
        while not stop_event.wait(5.0):
            if broker.clock() - broker.stats.last_activity <= idle:
                continue
            if images and proc.any_live(images):
                continue
            stop_event.set()
            return

    write_status(
        {
            "ok": True,
            "pid": os.getpid(),
            "instance": broker.authority.instance,
            "generation": broker.generation,
            "started": broker.authority.started,
            "runtime_root": str(broker.runtime),
            "saipen_root": str(saipen_root) if saipen_root else None,
            "log": str(log_path(runtime)),
        },
        runtime,
    )
    if idle > 0:
        watchdog = threading.Thread(target=idle_watch, daemon=True)
        watchdog.start()
    try:
        transport.serve(
            transport.endpoint(scope(runtime)),
            broker.handle,
            stop=stop_event,
            max_requests=max_requests,
        )
    except transport.TransportError as exc:
        write_status({"ok": False, "code": exc.kind, "detail": exc.detail}, runtime)
        return 1
    finally:
        broker.stop.set()
        release_lock(runtime)
        with contextlib.suppress(OSError):
            status_path(runtime).unlink()
    return 0


def request(
    payload: dict,
    *,
    runtime: Path | None = None,
    timeout: float = 5.0,
    verify_server=None,
) -> dict:
    """One client call. Raises transport.TransportError when nothing answers,
    or when `verify_server` rejects whoever serves the endpoint."""
    body = {"v": WIRE_VERSION, **payload}
    return transport.request(
        endpoint_name(runtime), body, timeout=timeout, verify_server=verify_server
    )


__all__ = [
    "AUTHORITY_HINT",
    "MODES",
    "MODE_DEGRADED",
    "MODE_STRICT",
    "READ_OPS",
    "SERVICE",
    "WIRE_VERSION",
    "WRITE_OPS",
    "Authority",
    "Broker",
    "Ledger",
    "acquire_lock",
    "adapter_fingerprint",
    "binding",
    "capability_fields",
    "endpoint_name",
    "health",
    "hook_artifacts",
    "instance_id",
    "log_path",
    "read_status",
    "release_lock",
    "request",
    "run_service",
    "runtime_policy_override",
    "runtime_root",
    "scope",
    "service_generation",
    "settings",
    "spawn",
    "status_path",
    "write_status",
]
