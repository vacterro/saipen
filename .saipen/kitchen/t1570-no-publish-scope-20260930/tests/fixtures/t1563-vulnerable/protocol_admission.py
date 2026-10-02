"""PROTOCOL-ADMISSION-01: the one runtime owner of session protocol admission.

Defect class: an assistant reply reaches the user although the protocol
authority that governs it was never established in that session. The failure
was reported from the field as a model that "did not read STYLE.md" and "did not
invoke the voice skill" and then wrote a paragraph explaining why it had not.
Post-generation checks (EXEC-RESPONSE, chat style) measure a reply that already
exists; they cannot decide whether the speaker was allowed to speak. That
decision is this module's alone.

Layering, each layer answering a different question and none able to
compensate for an earlier failure (`response_surface.gate_final_response`):

    binding          which project and host does this protocol apply to?
    ADMISSION        was the required authority actually established?   <- here
    EXEC-RESPONSE    is the operational response structurally valid?
    chat style       does the visible reply obey language and style?

Admission is machine-derived, never asserted. The evidence is what the runtime
itself delivered or resolved -- the byte fingerprints of BOOT, STYLE and
EXECUTION as delivered, the activation block the host loads, the skills the
runtime resolved by identity, the host hook and its enforcement claim -- written
to a ledger by a host hook event. "I read STYLE.md" is not an event and is
recorded nowhere. A model cannot satisfy admission by talking: `establish` and
`invalidate` are host-transport operations, gated HERE in the write boundary
(not only in the CLI wrapper), and the ledger is protected runtime namespace.

Transport authority (mechanical, inside this module): a mutating call must
present a capability `hook:<event>:<mac>` where `<mac>` is HMAC-SHA256 over
`saipen-admission-transport:<verb>:<event>:<session>` keyed by the per-project
transport key (`.saipen/cache/admission/.transport.key`, created once by the
HOST channel via `bootstrap_transport_key`, never by this module). An ordinary
Python or shell route can set an environment variable or spell a record by
hand; it cannot compute the MAC without the key, and the key sits in the
guard-protected canonical namespace, so every model tool route that names it is
refused before it runs. Honest scope limit: same-user code that has already
exfiltrated the key bytes through a route the guard cannot see can forge a
capability; that is the same-user limit every file on the machine shares, and
it is recorded here instead of being papered over.

Record provenance: the ledger record carries BOTH a plain SHA-256 `seal`
(corruption detection only -- it never proves who wrote the record) and a keyed
`provenance` HMAC over the sealed body (host-written provenance). A record
whose plain seal is valid but whose provenance does not verify -- a forged
current-looking record with a recomputed seal -- is ABSENT to `evaluate`:
it is never ADMITTED evidence.

States (existing SAIPEN vocabulary; `ADMITTED` is already the tool-admission
word):

    UNBOUND   no SAIPEN project is bound here; the protocol does not apply
    BINDING   a project is bound and admission is satisfiable, not yet established
    ADMITTED  the ledger record is current for this session, model and provider
    STALE     the record exists but a generation it proved has changed
    REFUSED   admission cannot be established now (a required proof is missing)

Only ADMITTED (or UNBOUND, where nothing governs) permits a reply. A token is
generational: it names the fingerprints it proved, and every component that
changes -- STYLE, EXECUTION, BOOT, the host activation block, the skill
contract, the runtime, the bound project, the host hook, the session, the model,
the provider -- makes the old token fail. There is no grace turn.

Bootstrap does not deadlock: this module gates USER-VISIBLE output only. Reading
authorities, resolving skills, computing fingerprints and running `saipen init`
are ordinary tool activity and are never routed through admission.

Scope limits, recorded as data in the adapter registry per host and never
generalized here: admission is enforced only where a host exposes both an
evidence channel (a delivery hook) and an interception point. `consulted()`
answers that from the registry; a host that cannot observe delivery is reported
UNAVAILABLE, never given a declaration-only pass.
"""

from __future__ import annotations

import glob
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1

STATE_UNBOUND = "UNBOUND"
STATE_BINDING = "BINDING"
STATE_ADMITTED = "ADMITTED"
STATE_STALE = "STALE"
STATE_REFUSED = "REFUSED"
STATES = (STATE_UNBOUND, STATE_BINDING, STATE_ADMITTED, STATE_STALE, STATE_REFUSED)

#: The one refusal code for any state that does not permit a reply. The `state`
#: field says which; a second code per state would be a second vocabulary.
CODE_REQUIRED = "PROTOCOL_ADMISSION_REQUIRED"
#: `establish` and `invalidate` are runtime transport operations, gated inside
#: the write boundary itself: a capability must name the host transport event
#: and carry the keyed MAC a shell route cannot compute.
CODE_TRANSPORT_REQUIRED = "PROTOCOL_ADMISSION_TRANSPORT_REQUIRED"
TRANSPORT_ENV = "SAIPEN_ADMISSION_TRANSPORT"
TRANSPORT_PREFIX = "hook:"

LEDGER_DIR = Path(".saipen") / "cache" / "admission"
#: Per-project transport key. Lives inside the guard-protected admission
#: namespace so every model tool route that names it is refused. Created only
#: by the host channel (`bootstrap_transport_key`); this module never mints
#: the authority it later requires.
TRANSPORT_KEY_NAME = ".transport.key"

#: Authority documents whose delivered bytes admission proves.
AUTHORITY_DOCUMENTS = ("BOOT.md", "STYLE.md", "EXECUTION.md")

#: Host instruction contract handling when the activation block is present but
#: differs from the source template. Publication is operator-gated (the injector
#: refuses a dirty tree), so a stale block is reported, not refused; an ABSENT
#: block is refused. Data, so an owner can tighten it without touching code.
DEFAULT_POLICY = {
    "documents": list(AUTHORITY_DOCUMENTS),
    "agents_absent": "refuse",
    "agents_stale": "diagnose",
    "skills": [],
}

_PROVIDER_ENV = (
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_BEDROCK_BASE_URL",
    "ANTHROPIC_VERTEX_PROJECT_ID",
)

_MAX_DIAGNOSTIC = 480


@dataclass(frozen=True)
class Context:
    """The facts a host transport observed; the owner infers none of them."""

    project_root: Path | None
    session_id: str
    host: str
    model: str | None = None
    provider: str | None = None
    #: Where the protocol authorities are read from. None = the running install.
    authority_root: Path | None = None
    #: The operator's home (instruction surfaces, skill locations). None = real.
    home: Path | None = None
    #: The adapter registry entry set. None = the shipped registry.
    adapters: dict | None = None
    #: The admission policy. None = the shipped registry's section.
    policy: dict | None = None


def _sha(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n")


def load_policy() -> dict:
    """The admission policy from the protocol registry, or the built-in default."""
    try:
        from .registry import load_registry

        section = load_registry().get("protocol_admission")
    except Exception:  # an unreadable registry is a REFUSED admission, not a crash
        section = None
    return section if isinstance(section, dict) else dict(DEFAULT_POLICY)


def _adapters(ctx: Context) -> dict:
    if ctx.adapters is not None:
        return ctx.adapters
    try:
        registry = json.loads(
            (
                Path(__file__).resolve().parents[2] / "extensions" / "adapters" / "registry.json"
            ).read_text(encoding="utf-8-sig")
        )
    except (OSError, ValueError):
        return {}
    return {entry["id"]: entry for entry in registry.get("adapters", []) if "id" in entry}


def host_claims(ctx: Context) -> dict:
    """The registry's per-boundary capability claims for this host."""
    entry = _adapters(ctx).get(ctx.host) or {}
    keys = (
        "pre_output_interception",
        "stop_output_interception",
        "admission_enforcement",
        "response_enforcement",
        "style_enforcement",
    )
    return {key: entry.get(key) for key in keys}


def consulted(ctx: Context) -> bool:
    """Is admission enforceable on this host? Only a MECHANICAL claim is consulted.

    A host with no evidence channel cannot prove delivery; consulting admission
    there would block every reply forever or pass on a declaration. Neither is
    acceptable, so the gate reports the layer as not enforceable instead.
    """
    return host_claims(ctx).get("admission_enforcement") == "MECHANICAL"


def _authority_root(ctx: Context) -> Path | None:
    if ctx.authority_root is not None:
        return ctx.authority_root
    try:
        from .state import running_home

        return running_home()
    except Exception:
        return None


def read_authority(ctx: Context, name: str) -> str | None:
    root = _authority_root(ctx)
    if root is None:
        return None
    for candidate in (root / "saipen" / name, root / name):
        try:
            return candidate.read_text(encoding="utf-8-sig")
        except OSError:
            continue
    return None


def _expand(ctx: Context, surface: str) -> Path:
    if surface.startswith("~"):
        base = ctx.home if ctx.home is not None else Path.home()
        return base / surface[1:].lstrip("/\\")
    return Path(surface)


def _front_matter_name(text: str) -> str | None:
    match = re.match(r"\A---\s*\n(.*?)\n---", _norm(text), re.DOTALL)
    if not match:
        return None
    found = re.search(r"(?m)^name:\s*(\S+)\s*$", match.group(1))
    return found.group(1).strip("\"'") if found else None


def resolve_skill(ctx: Context, contract: dict) -> dict:
    """Resolve one skill contract by IDENTITY, never by a path the model names.

    A location counts only when its SKILL.md declares the contract's own `name`;
    a same-named directory holding another skill is not the skill. The
    observed field failure (`anthropic-skills:caveman` -> Unknown skill) was an
    identity the host did not know while the skill sat in a location the host
    does not search: the contract therefore lists every location the operator's
    machine is known to keep it in, and the runtime -- which can read any of
    them -- delivers the bytes itself instead of asking the model to invoke a
    name the host may not resolve.
    """
    name = str(contract.get("name") or "")
    for pattern in contract.get("locations") or []:
        expanded = str(_expand(ctx, str(pattern)))
        for directory in sorted(glob.glob(expanded)):
            skill_file = Path(directory) / "SKILL.md"
            try:
                raw = skill_file.read_bytes()
            except OSError:
                continue
            text = raw.decode("utf-8", errors="replace")
            if _front_matter_name(text) == name:
                return {
                    "name": name,
                    "resolved": True,
                    "path": str(skill_file),
                    "fingerprint": _sha(_norm(text)),
                    "text": text,
                }
    return {"name": name, "resolved": False, "aliases": list(contract.get("aliases") or [])}


def _agents_component(ctx: Context, policy: dict) -> tuple[str | None, str | None, str | None]:
    """(fingerprint, problem, warning) for the host instruction contract."""
    entry = _adapters(ctx).get(ctx.host) or {}
    surfaces = list(entry.get("instruction_surfaces") or [])
    for loader in entry.get("instruction_loaders") or []:
        surfaces.extend(loader.get("surfaces") or [])
    block = None
    for surface in surfaces:
        try:
            text = _expand(ctx, str(surface)).read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        found = re.search(r"<!-- SAIPEN:BEGIN -->.*?<!-- SAIPEN:END -->", text, re.DOTALL)
        if found:
            block = _norm(found.group(0)).strip()
            break
    if block is None:
        rule = policy.get("agents_absent", "refuse")
        message = f"host {ctx.host} delivers no SAIPEN activation block"
        return (None, message, None) if rule == "refuse" else (None, None, message)
    warning = None
    try:
        from autoinject import instruction_status

        install = _expand(ctx, str((entry.get("install") or {}).get("skill") or "~"))
        status = instruction_status(entry, install)
    except Exception:
        status = "unknown"
    if status not in ("current",):
        message = f"host {ctx.host} activation block is {status}"
        if policy.get("agents_stale", "diagnose") == "refuse":
            return (_sha(block), message, None)
        warning = message
    return (_sha(block), None, warning)


def _host_component(ctx: Context) -> tuple[str | None, str | None]:
    """(fingerprint, problem): is the host's evidence and enforcement hook current?"""
    entry = _adapters(ctx).get(ctx.host)
    if entry is None:
        return (None, f"host {ctx.host!r} is not a registered adapter")
    claims = host_claims(ctx)
    if claims.get("admission_enforcement") != "MECHANICAL":
        return (
            None,
            f"host {ctx.host} declares admission_enforcement="
            f"{claims.get('admission_enforcement')}: no evidence channel to prove it",
        )
    if not entry.get("hook_installer"):
        return (f"declared:{ctx.host}", None)
    try:
        from install_host_guard import install

        home = ctx.home if ctx.home is not None else Path.home()
        result = install(ctx.host, home, Path(__file__).resolve().parents[2], check=True)
    except Exception as exc:
        return (None, f"host hook cannot be observed: {type(exc).__name__}")
    if not (result.get("current") and result.get("configured")):
        return (None, f"host {ctx.host} hook is not installed and current")
    return (_sha(json.dumps({"host": ctx.host, "artifact": entry.get("hook_artifact")})), None)


def _project_component(ctx: Context) -> tuple[str | None, str | None]:
    if ctx.project_root is None:
        return (None, "no project root")
    root = Path(ctx.project_root)
    try:
        identity = (root / ".saipen" / "IDENTITY.md").read_text(encoding="utf-8-sig")
        state = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8-sig")
    except OSError:
        return (None, "project has no readable IDENTITY.md and STATE.md")
    home = re.search(r'(?m)^saipen_home:\s*"?([^"\n]*)"?\s*$', state)
    return (
        _sha(json.dumps({"identity": _norm(identity), "home": home.group(1) if home else ""})),
        None,
    )


def _runtime_component(ctx: Context) -> str:
    version = read_authority(ctx, "VERSION")
    if version is None:
        try:
            version = (Path(__file__).resolve().parents[2] / "VERSION").read_text(
                encoding="utf-8-sig"
            )
        except OSError:
            version = "unknown"
    return _sha(json.dumps({"version": version.strip(), "schema": SCHEMA_VERSION}))


def provider_fingerprint(env: dict | None = None) -> str:
    """The provider as the runtime observes it, from process environment only."""
    source = os.environ if env is None else env
    seen = {key: source.get(key, "") for key in _PROVIDER_ENV if source.get(key)}
    return _sha(json.dumps(seen, sort_keys=True))[:16] if seen else "default"


def components(ctx: Context, policy: dict) -> dict:
    """Every proof admission needs: fingerprints, problems, warnings, skills."""
    proofs: dict[str, str] = {}
    problems: list[dict] = []
    warnings: list[str] = []
    texts: dict[str, str] = {}

    def problem(name: str, reason: str) -> None:
        problems.append({"component": name, "reason": reason})

    project, why = _project_component(ctx)
    if project:
        proofs["project"] = project
    else:
        problem("project", why or "unbound")

    for name in policy.get("documents") or AUTHORITY_DOCUMENTS:
        text = read_authority(ctx, str(name))
        if text is None:
            problem(f"authority:{name}", f"{name} is not readable from the authority root")
            continue
        texts[str(name)] = _norm(text)
        proofs[f"authority:{name}"] = _sha(_norm(text))
    if "STYLE.md" in texts:
        try:
            from .chat_style import compile_style_contract

            compile_style_contract(texts["STYLE.md"])
        except Exception as exc:
            problem("authority:STYLE.md", f"STYLE.md cannot be compiled: {exc}")

    agents, agents_problem, agents_warning = _agents_component(ctx, policy)
    if agents:
        proofs["agents"] = agents
    if agents_problem:
        problem("agents", agents_problem)
    if agents_warning:
        warnings.append(agents_warning)

    host, host_problem = _host_component(ctx)
    if host:
        proofs["host"] = host
    if host_problem:
        problem("host", host_problem)

    skills: list[dict] = []
    for contract in policy.get("skills") or []:
        resolved = resolve_skill(ctx, contract)
        skills.append({**resolved, "critical": bool(contract.get("critical"))})
        if resolved["resolved"]:
            proofs[f"skill:{resolved['name']}"] = resolved["fingerprint"]
        elif contract.get("critical"):
            problem(
                f"skill:{resolved['name']}",
                f"critical skill {resolved['name']!r} is unresolvable "
                f"(aliases {resolved.get('aliases') or []})",
            )
        else:
            warnings.append(f"skill {resolved['name']!r} is unresolvable (not critical)")
    proofs["skills-contract"] = _sha(
        json.dumps(
            [
                {k: c.get(k) for k in ("name", "critical", "aliases", "locations")}
                for c in policy.get("skills") or []
            ],
            sort_keys=True,
        )
    )
    proofs["runtime"] = _runtime_component(ctx)
    return {
        "proofs": proofs,
        "problems": problems,
        "warnings": warnings,
        "texts": texts,
        "skills": skills,
    }


def generation(proofs: dict) -> str:
    return "adm-" + _sha(json.dumps(proofs, sort_keys=True))[:32]


# ---------------------------------------------------------------- ledger


def _ledger_path(project_root: Path, session_id: str) -> Path:
    return Path(project_root) / LEDGER_DIR / (_sha(session_id)[:24] + ".json")


def _transport_key_path(project_root: Path) -> Path:
    return Path(project_root) / LEDGER_DIR / TRANSPORT_KEY_NAME


def bootstrap_transport_key(project_root: Path | str) -> bytes:
    """Create the per-project transport key ONCE, or return the existing bytes.

    Host-channel bootstrap: the host hook calls this before its first mutating
    admission call. Create-only (O_EXCL, 0600) -- an existing key is returned
    untouched, and this module itself never calls this on its own behalf: the
    write boundary must not mint the authority it verifies.
    """
    path = _transport_key_path(Path(project_root))
    try:
        data = path.read_bytes()
        if data:
            return data
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = secrets.token_bytes(32)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path.read_bytes()
    with os.fdopen(fd, "wb") as stream:
        stream.write(fresh)
    return fresh


def _read_transport_key(project_root: Path | None) -> bytes | None:
    if project_root is None:
        return None
    try:
        data = _transport_key_path(Path(project_root)).read_bytes()
    except OSError:
        return None
    return data or None


def _transport_mac(key: bytes, verb: str, event: str, session_id: str) -> str:
    domain = f"saipen-admission-transport:{verb}:{event}:{session_id}".encode("utf-8")
    return hmac.new(key, domain, "sha256").hexdigest()


def verify_transport(
    project_root: Path | str | None, verb: str, session_id: str, value: object
) -> tuple[bool, str | None, str | None]:
    """Is `value` a genuine host-owned transport capability for this mutation?

    The capability is `hook:<event>:<mac>`; the MAC is keyed by the per-project
    transport key and binds the verb, the host event and the session, so a
    captured or invented string does not transfer. An environment variable a
    shell sets is not a capability: without the key bytes there is no MAC.
    Returns (ok, detail, event).
    """
    if not isinstance(value, str) or not value.startswith(TRANSPORT_PREFIX):
        return False, "no host transport presented; a shell call is not a hook event", None
    # rsplit: the EVENT may itself contain colons (SessionStart:compact); the
    # MAC is the one component that never does.
    parts = value[len(TRANSPORT_PREFIX) :].rsplit(":", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return False, "transport capability is not hook:<event>:<mac>", None
    event, mac = parts
    key = _read_transport_key(Path(project_root) if project_root else None)
    if key is None:
        return False, "project has no host transport key", None
    if not hmac.compare_digest(_transport_mac(key, verb, event, session_id), mac):
        return False, "transport capability does not verify", None
    return True, None, event


def _seal(record: dict) -> str:
    body = {k: v for k, v in record.items() if k not in ("seal", "provenance")}
    return _sha(json.dumps(body, sort_keys=True))


def _provenance(record: dict, key: bytes) -> str:
    body = {k: v for k, v in record.items() if k != "provenance"}
    return hmac.new(key, json.dumps(body, sort_keys=True).encode("utf-8"), "sha256").hexdigest()


def _read_record(project_root: Path, session_id: str) -> dict | None:
    """The ledger record, or None. Corrupt, unreadable or UNPROVEN is ABSENT:
    an old token that cannot be proven is not reusable, and a forged record
    whose plain seal was recomputed by hand proves nothing."""
    try:
        record = json.loads(_ledger_path(project_root, session_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("schema") != SCHEMA_VERSION:
        return None
    # The record names its own session: a legitimate record transplanted to
    # another session's ledger filename is not that session's evidence.
    if record.get("session") != session_id:
        return None
    if record.get("seal") != _seal(record):
        return None
    key = _read_transport_key(project_root)
    if key is None:
        return None
    if not hmac.compare_digest(record.get("provenance") or "", _provenance(record, key)):
        return None
    return record


def _write_record(project_root: Path, session_id: str, record: dict, transport_event: str) -> None:
    """The canonical ledger writer. Callers are host transports that already
    passed `verify_transport`; the writer itself needs the key, so an ordinary
    caller cannot mint a proven record through it."""
    key = _read_transport_key(project_root)
    if key is None:
        raise ValueError("no host transport key; the host channel must bootstrap first")
    record = {k: v for k, v in record.items() if k not in ("seal", "provenance")}
    record["session"] = session_id
    record["transport"] = transport_event
    record["seal"] = _seal(record)
    record["provenance"] = _provenance(record, key)
    path = _ledger_path(project_root, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(record, stream, sort_keys=True)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def invalidate(
    project_root: Path | None,
    session_id: str,
    reason: str,
    transport: object = None,
) -> dict:
    """Delete the session's record. A host-transport operation, gated here.

    Returns {ok, removed, code}: ok False with CODE_TRANSPORT_REQUIRED when the
    caller presented no genuine capability (the record is left untouched).
    """
    if transport is None:
        transport = os.environ.get(TRANSPORT_ENV, "")
    admitted, _detail, _event = verify_transport(project_root, "invalidate", session_id, transport)
    if not admitted:
        return {"ok": False, "removed": False, "code": CODE_TRANSPORT_REQUIRED, "detail": _detail}
    if project_root is None:
        return {"ok": True, "removed": False, "code": None}
    path = _ledger_path(Path(project_root), session_id)
    try:
        path.unlink()
        return {"ok": True, "removed": True, "code": None}
    except OSError:
        return {"ok": True, "removed": False, "code": None}


# ---------------------------------------------------------------- verdicts


def _verdict(state: str, **fields) -> dict:
    permitted = state in (STATE_ADMITTED, STATE_UNBOUND)
    return {
        "state": state,
        "permitted": permitted,
        "applies": state != STATE_UNBOUND,
        "code": None if permitted else CODE_REQUIRED,
        **fields,
    }


def diagnostic(verdict: dict) -> str:
    """The runtime-authored, bounded diagnostic. The model whose admission
    failed never writes it, and it never contains free-form advice."""
    parts = [f"SAIPEN PROTOCOL ADMISSION {verdict.get('state')}"]
    reasons = [p["reason"] for p in verdict.get("problems") or []]
    reasons += [f"{name} changed" for name in verdict.get("stale") or []]
    if not reasons and verdict.get("state") == STATE_BINDING:
        reasons = ["authority not yet delivered to this session"]
    if reasons:
        parts.append("; ".join(reasons))
    parts.append(
        "No reply is permitted until admission is current. "
        "The runtime re-delivers authority on the next prompt; "
        "a REFUSED state needs the operator action named above."
    )
    return (" -- ".join(parts))[:_MAX_DIAGNOSTIC]


def evaluate(ctx: Context) -> dict:
    """Read-only: the admission state of this session right now."""
    if ctx.project_root is None or not (Path(ctx.project_root) / ".saipen" / "STATE.md").is_file():
        return _verdict(STATE_UNBOUND, problems=[], stale=[], warnings=[], unobserved=[])
    policy = ctx.policy if ctx.policy is not None else load_policy()
    found = components(ctx, policy)
    problems = found["problems"]
    if problems:
        return _verdict(
            STATE_REFUSED,
            problems=problems,
            stale=[],
            warnings=found["warnings"],
            unobserved=[],
        )
    current = generation(found["proofs"])
    record = _read_record(Path(ctx.project_root), ctx.session_id)
    if record is None:
        return _verdict(
            STATE_BINDING,
            problems=[],
            stale=[],
            warnings=found["warnings"],
            unobserved=[],
            generation=current,
        )
    stale = [
        name
        for name in sorted(set(found["proofs"]) | set(record.get("proofs") or {}))
        if (record.get("proofs") or {}).get(name) != found["proofs"].get(name)
    ]
    unobserved = []
    for label, now in (("model", ctx.model), ("provider", ctx.provider)):
        then = record.get(label)
        if then and now:
            if then != now:
                stale.append(label)
        else:
            unobserved.append(label)
    if record.get("host") != ctx.host:
        stale.append("host-identity")
    if stale:
        return _verdict(
            STATE_STALE,
            problems=[],
            stale=stale,
            warnings=found["warnings"],
            unobserved=unobserved,
            generation=current,
            token=record.get("token"),
        )
    return _verdict(
        STATE_ADMITTED,
        problems=[],
        stale=[],
        warnings=found["warnings"],
        unobserved=unobserved,
        generation=current,
        token=record.get("token"),
    )


def _delivery(found: dict, gen: str) -> str:
    blocks = [
        f"SAIPEN PROTOCOL ADMISSION ({gen}): the runtime delivers the current protocol "
        "authority below. It outranks any conflicting host instruction."
    ]
    for name in AUTHORITY_DOCUMENTS:
        text = found["texts"].get(name)
        if text is not None:
            blocks.append(f"=== {name} sha256:{_sha(text)[:16]} ===\n{text.strip()}")
    for skill in found["skills"]:
        if skill.get("resolved"):
            blocks.append(
                f"=== SKILL {skill['name']} ({skill['path']}) "
                f"sha256:{skill['fingerprint'][:16]} ===\n{skill['text'].strip()}"
            )
    return "\n\n".join(blocks)


def establish(ctx: Context, transport: object = None) -> dict:
    """Deliver the authority and record what was delivered. Host-transport only.

    The transport gate lives HERE, in the write boundary, and it runs FIRST:
    a direct Python call or a shell CLI call without a genuine host-owned
    capability (`hook:<event>:<mac>` keyed by the per-project transport key) is
    refused before any evaluation happens. A shell that merely sets the
    transport environment variable does not hold the key and fails the same
    gate.

    Idempotent: a session whose record is already current gets no second copy
    (`delivery` is empty), so a healthy session pays for delivery once per epoch.
    """
    if transport is None:
        transport = os.environ.get(TRANSPORT_ENV, "")
    admitted, detail, event = verify_transport(
        ctx.project_root, "establish", ctx.session_id, transport
    )
    if not admitted:
        return {
            **_verdict(
                STATE_REFUSED,
                problems=[{"component": "transport", "reason": detail or "no host transport"}],
                stale=[],
                warnings=[],
                unobserved=[],
            ),
            "code": CODE_TRANSPORT_REQUIRED,
            "delivery": "",
        }
    verdict = evaluate(ctx)
    if verdict["state"] in (STATE_UNBOUND, STATE_REFUSED, STATE_ADMITTED):
        return {**verdict, "delivery": ""}
    policy = ctx.policy if ctx.policy is not None else load_policy()
    found = components(ctx, policy)
    if found["problems"]:  # defended: evaluate() already returned REFUSED
        return {
            **_verdict(STATE_REFUSED, problems=found["problems"], stale=[], warnings=[]),
            "delivery": "",
        }
    gen = generation(found["proofs"])
    token = "tok-" + _sha(json.dumps([gen, ctx.session_id, ctx.model, ctx.provider]))[:32]
    delivered = {
        name: _sha(found["texts"][name]) for name in AUTHORITY_DOCUMENTS if name in found["texts"]
    }
    delivered.update(
        {f"skill:{s['name']}": s["fingerprint"] for s in found["skills"] if s.get("resolved")}
    )
    _write_record(
        Path(ctx.project_root),
        ctx.session_id,
        {
            "schema": SCHEMA_VERSION,
            "host": ctx.host,
            "model": ctx.model,
            "provider": ctx.provider,
            "proofs": found["proofs"],
            "generation": gen,
            "token": token,
            "delivered": delivered,
        },
        transport_event=event or "hook",
    )
    return {
        **_verdict(
            STATE_ADMITTED,
            problems=[],
            stale=[],
            warnings=found["warnings"],
            unobserved=[],
            generation=gen,
            token=token,
        ),
        "delivery": _delivery(found, gen),
    }


def capability_matrix(adapters: dict | None = None) -> dict:
    """Per host, the separately recorded enforcement boundaries."""
    ctx = Context(project_root=None, session_id="", host="", adapters=adapters)
    return {
        name: {
            key: entry.get(key)
            for key in (
                "pre_output_interception",
                "stop_output_interception",
                "admission_enforcement",
                "response_enforcement",
                "style_enforcement",
            )
        }
        for name, entry in _adapters(ctx).items()
    }


__all__ = [
    "CODE_REQUIRED",
    "CODE_TRANSPORT_REQUIRED",
    "Context",
    "STATES",
    "TRANSPORT_ENV",
    "TRANSPORT_KEY_NAME",
    "TRANSPORT_PREFIX",
    "bootstrap_transport_key",
    "capability_matrix",
    "consulted",
    "diagnostic",
    "establish",
    "evaluate",
    "generation",
    "host_claims",
    "invalidate",
    "load_policy",
    "provider_fingerprint",
    "resolve_skill",
    "verify_transport",
]
