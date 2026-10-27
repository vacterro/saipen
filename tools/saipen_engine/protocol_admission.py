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

Authority limit (T-1563): a Python hook and model-executed Python run as
the same OS principal. Either can import the hook or read its project key.
Neither an underscore, an environment variable, a protected path classifier,
nor moving the signing helper into the adapter establishes host provenance.
Local authority bootstrap, key reads, MAC minting and record signing stay
unavailable, and legacy hook:<event>:<mac> strings are refused with everything
else that a same-user caller could mint for itself.

The separated authority (T-1623): `saipen_engine.host_authority_broker` is that
host-owned service. It runs as its own process, holds its signing key in memory
only, identifies the asking process from the OPERATING SYSTEM rather than from
anything the request says, and owns the ledger write. This module asks it and
transports its answer; it never mints. `establish` and `invalidate` therefore
delegate, and a client the broker cannot place in the host's own process tree is
refused exactly as an ordinary import always was -- the broker is the reason the
refusal is now a specific, recoverable diagnostic instead of a dead end.

Record provenance remains REQUIRED. A plain SHA-256 seal detects corruption
only; legacy HMAC records made with the retrievable project key are not trusted.
No record is accepted until provenance can be checked against a genuinely
separated authority -- which means, in practice, that the live broker must
reproduce the record's keyed provenance. A record that fails that check is not
an error to stop on: it is discarded and admission is established again, so a
restarted authority costs one re-delivery and never a lockout.

The decision table (T-1624, `host_taxonomy`). T-1623 made admission real and
left the host hostage to it: an authority that could not be proven blocked every
prompt, and whether a failure blocked was decided by a substring of its reason.
Every problem this owner reports is now a registered failure code, and one
table decides from the code:

    ADMIT            the authority proved the host's hook and wrote the record
    ALLOW_DEGRADED   nothing blocking, admission not proven, policy allows it:
                     the prompt proceeds, marked UNVERIFIED, claiming nothing
    BLOCK            a conflict -- a forged, replayed or transplanted
                     capability, a project binding that contradicts the project
                     -- in EVERY mode; or any failure under STRICT

"Could not be proven" is not "unsafe": an unreachable authority, a stale hook, a
damaged runtime or a host the platform will not identify leave the operator a
working model and a truthful marker. DEGRADED_ALLOWED is the default policy and
STRICT is the operator's explicit opt-in; neither is ever changed silently, and
a degraded permit never writes a record and never reads as ADMITTED.

States (existing SAIPEN vocabulary; `ADMITTED` is already the tool-admission
word):

    UNBOUND   no SAIPEN project is bound here; the protocol does not apply
    BINDING   a project is bound and admission is satisfiable, not yet established
    ADMITTED  the ledger record is current for this session, model and provider
    STALE     the record exists but a generation it proved has changed
    REFUSED   admission cannot be established now (a required proof is missing)

Only ADMITTED (or UNBOUND, where nothing governs) permits a reply under STRICT
policy; DEGRADED_ALLOWED also permits a session that is merely not proven,
without claiming admission, and never one that carries a blocking failure. A token is
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

import contextlib
import glob
import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path

try:
    from . import host_taxonomy as taxonomy
except ImportError:
    # This file is also importable by its name alone: the T-1563 paired carrier
    # imports the frozen vulnerable subject and this one through the SAME
    # statement. The taxonomy is the only module-level dependency and has none
    # of its own, so the plain import is the same module either way.
    import host_taxonomy as taxonomy

SCHEMA_VERSION = 1

STATE_UNBOUND = "UNBOUND"
STATE_BINDING = "BINDING"
STATE_ADMITTED = "ADMITTED"
STATE_STALE = "STALE"
STATE_REFUSED = "REFUSED"
#: The operator's explicit, never-silent fallback. It permits a prompt and
#: claims nothing: no record, no capability, no mechanical admission.
STATE_DEGRADED = "DEGRADED"
STATES = (
    STATE_UNBOUND,
    STATE_BINDING,
    STATE_ADMITTED,
    STATE_STALE,
    STATE_REFUSED,
    STATE_DEGRADED,
)

#: The one refusal code for any state that does not permit a reply. The `state`
#: field says which; a second code per state would be a second vocabulary.
CODE_REQUIRED = "PROTOCOL_ADMISSION_REQUIRED"
#: `establish` and `invalidate` are runtime transport operations, gated inside
#: the write boundary itself. No local MAC or caller-supplied hook name can
#: satisfy it while separated host authority is unavailable.
CODE_TRANSPORT_REQUIRED = "PROTOCOL_ADMISSION_TRANSPORT_REQUIRED"
TRANSPORT_ENV = "SAIPEN_ADMISSION_TRANSPORT"
TRANSPORT_PREFIX = "hook:"

LEDGER_DIR = Path(".saipen") / "cache" / "admission"
AUTHORITY_UNAVAILABLE = (
    "HOST_AUTHORITY_UNAVAILABLE: the separated SAIPEN host-authority broker did not "
    "establish admission for this session"
)
#: The separate claim a degraded permit makes: it is NOT admission.
DEGRADED_MARKER = "SAIPEN_ADMISSION_UNVERIFIED"

#: Binding refusals of the ONE binding owner (`paths.resolve_project_root`) ->
#: the failure they mean for a prompt. A carrier that names a different project
#: than the one the session is in is a conflict and blocks in every mode; a
#: carrier that names nothing usable is a broken integration and degrades.
_BINDING_FAILURES = {
    "PROJECT_LINEAGE_MISMATCH": "BINDING_FOREIGN_PROJECT",
    "PROJECT_BINDING_AMBIGUOUS": "BINDING_CONFLICT",
    "PROJECT_BINDING_INVALID": "BINDING_CARRIER_INVALID",
}

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
    "host_authority": {
        "host_images": ["claude.exe", "claude", "claude-code", "claude-code.exe"],
        "host_signers": ["Anthropic, PBC"],
        "ancestry_limit": 16,
        "capability_ttl_seconds": 900,
        "idle_exit_seconds": 1800,
        "identity_cache_seconds": 30,
    },
}

_PROVIDER_ENV = (
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_BEDROCK_BASE_URL",
    "ANTHROPIC_VERTEX_PROJECT_ID",
)

#: A refused prompt carries the failure, the recovery that was attempted and
#: the operator's next action. The bound grew from 480 when the dead-end
#: sentence `a separated host authority is required` was replaced by a
#: diagnostic that names the component that failed.
_MAX_DIAGNOSTIC = 720
#: Every refusal opens with this, whatever follows.
DIAGNOSTIC_PREFIX = "SAIPEN PROTOCOL ADMISSION"


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
    #: The directory the host session is really in. When given, the binding
    #: owner judges every ambient project carrier against it; None means the
    #: caller named the project itself and no carrier is consulted.
    event_cwd: Path | None = None
    #: Project carriers (`SAIPEN_PROJECT_ROOT`, `SAIPEN_PROJECT_LINEAGE`). None
    #: = this process's environment.
    carriers: dict | None = None
    #: The authority service's runtime root. None = the operator's real one;
    #: a diagnostic or test carrier names an isolated endpoint here.
    runtime: Path | None = None
    #: Claude configuration directory. The broker replaces it with OS-proven identity.
    profile: Path | None = None

    def __post_init__(self) -> None:
        # A caller may hand any of these over as text (a CLI flag, a JSON
        # payload). Every reader below joins paths, and a string there was a
        # TypeError in the middle of a verdict instead of an answer.
        for name in ("project_root", "authority_root", "home", "event_cwd", "runtime", "profile"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, Path):
                object.__setattr__(self, name, Path(str(value)))
        if self.host == "claude" and self.profile is None:
            from saipen_engine.claude_profiles import directory

            object.__setattr__(self, "profile", directory(self.home))


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
    """Should the reply gate require admission for this host?

    A required boundary remains closed when its authority is UNAVAILABLE.
    Losing the MECHANICAL claim must not silently bypass the admission layer.
    """
    entry = _adapters(ctx).get(ctx.host) or {}
    return entry.get("admission_required") is True or (
        host_claims(ctx).get("admission_enforcement") == "MECHANICAL"
    )


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
    if ctx.host == "claude" and ctx.profile is not None:
        from saipen_engine.claude_profiles import surface as profile_surface

        return profile_surface(surface, ctx.home or Path.home(), ctx.profile)
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


def _agents_component(
    ctx: Context, policy: dict
) -> tuple[str | None, tuple[str, str] | None, str | None]:
    """(fingerprint, (failure code, reason) | None, warning) for the host
    instruction contract."""
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
        return (
            (None, ("ACTIVATION_BLOCK_ABSENT", message), None)
            if rule == "refuse"
            else (None, None, message)
        )
    warning = None
    try:
        from autoinject import instruction_status

        install = _expand(ctx, str((entry.get("install") or {}).get("skill") or "~"))
        status = instruction_status(entry, install)
    except Exception:
        status = "unknown"
    if status != "current":
        message = f"host {ctx.host} activation block is {status}"
        if policy.get("agents_stale", "diagnose") == "refuse":
            return (_sha(block), ("ACTIVATION_BLOCK_STALE", message), None)
        warning = message
    return (_sha(block), None, warning)


def _host_component(ctx: Context) -> tuple[str | None, tuple[str, str] | None]:
    """(fingerprint, (failure code, reason) | None): is the host's evidence and
    enforcement hook current?"""
    entry = _adapters(ctx).get(ctx.host)
    if entry is None:
        return (None, ("HOST_UNREGISTERED", f"host {ctx.host!r} is not a registered adapter"))
    claims = host_claims(ctx)
    if claims.get("admission_enforcement") != "MECHANICAL":
        return (
            None,
            (
                "HOST_EVIDENCE_UNAVAILABLE",
                f"host {ctx.host} declares admission_enforcement="
                f"{claims.get('admission_enforcement')}: no evidence channel to prove it",
            ),
        )
    if not entry.get("hook_installer"):
        return (f"declared:{ctx.host}", None)
    try:
        from install_host_guard import install

        home = ctx.home if ctx.home is not None else Path.home()
        options = {"profile": ctx.profile} if ctx.host == "claude" else {}
        result = install(ctx.host, home, Path(__file__).resolve().parents[2], check=True, **options)
    except Exception as exc:
        return (None, ("HOOK_UNOBSERVABLE", f"host hook cannot be observed: {type(exc).__name__}"))
    if not (result.get("current") and result.get("configured")):
        return (None, ("HOOK_STALE", f"host {ctx.host} hook is not installed and current"))
    identity = {"host": ctx.host, "artifact": entry.get("hook_artifact")}
    if ctx.profile is not None:
        identity["profile"] = os.path.normcase(os.path.abspath(ctx.profile))
    return (_sha(json.dumps(identity)), None)


def binding_problems(ctx: Context) -> list[dict]:
    """Does a project carrier contradict the project this session is in?

    The BINDING layer, decided by its one owner (`paths.resolve_project_root`)
    from the directory the session is really in. Consulted only when the host
    transport supplied that directory: a caller that names the project itself
    has made the binding explicit, and an ambient variable does not overrule it.
    A different project named by a carrier is a conflict and blocks in every
    mode; a carrier that names nothing usable is a broken integration.
    """
    if ctx.event_cwd is None or ctx.project_root is None:
        return []
    carriers = os.environ if ctx.carriers is None else ctx.carriers
    host_root = str(carriers.get("SAIPEN_PROJECT_ROOT") or "").strip() or None
    host_lineage = str(carriers.get("SAIPEN_PROJECT_LINEAGE") or "").strip() or None
    if host_root is None and host_lineage is None:
        return []
    try:
        from .paths import _nearest_checkpoint_root, project_lineage_identity, resolve_project_root

        resolved = resolve_project_root(
            Path(ctx.event_cwd),
            host_root=host_root,
            host_lineage=host_lineage,
            honor_environment=False,
            authority="observe",
        )
        if resolved.root is None:
            failure = _BINDING_FAILURES.get(str(getattr(resolved, "code", "") or ""))
            if failure is None:
                return []
            return [taxonomy.problem("binding", failure, str(resolved.source))]
        # An explicit host root is the caller's own binding to the resolver and
        # is not second-guessed there. Here it is an AMBIENT carrier, so it is
        # also judged against the project the session directory belongs to.
        here = _nearest_checkpoint_root(Path(ctx.event_cwd).resolve())
        if here is not None and host_root is not None:
            named = project_lineage_identity(resolved.root)
            local = project_lineage_identity(here)
            if named and local and named != local:
                return [
                    taxonomy.problem(
                        "binding",
                        "BINDING_CONFLICT",
                        f"SAIPEN_PROJECT_ROOT names {resolved.root} but the session directory "
                        f"belongs to {here}; two different projects claim this session",
                    )
                ]
    except Exception as exc:
        return [
            taxonomy.problem(
                "binding",
                "BINDING_CARRIER_INVALID",
                f"project carrier could not be judged: {type(exc).__name__}",
            )
        ]
    return []


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


def admission_mode(ctx: Context) -> str:
    """The admission policy in force: `degraded` (DEGRADED_ALLOWED, the default
    when the operator wrote nothing) or `strict`. Read from an operator-owned
    file that only `saipen host mode` writes; a file that is present and
    unrecognized is STRICT, so an explicit choice is never silently weakened."""
    try:
        from .host_authority_client import authority_mode

        return authority_mode(ctx.home)
    except Exception:
        return taxonomy.MODE_STRICT


def degraded(ctx: Context) -> bool:
    return admission_mode(ctx) == taxonomy.MODE_DEGRADED


def degradable_only(problems: list) -> bool:
    """Is every recorded problem a registered, degradable failure?

    Decided by `host_taxonomy` from each problem's failure CODE, never from its
    wording. A problem that carries no registered code is not degradable: an
    unclassified failure is never waved through.
    """
    return taxonomy.degradable(problems)


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

    def problem(name: str, code: str, reason: str) -> None:
        problems.append(taxonomy.problem(name, code, reason))

    project, why = _project_component(ctx)
    if project:
        proofs["project"] = project
    else:
        problem("project", "PROJECT_IDENTITY_UNREADABLE", why or "unbound")

    for name in policy.get("documents") or AUTHORITY_DOCUMENTS:
        text = read_authority(ctx, str(name))
        if text is None:
            problem(
                f"authority:{name}",
                "AUTHORITY_DOCUMENT_UNREADABLE",
                f"{name} is not readable from the authority root",
            )
            continue
        texts[str(name)] = _norm(text)
        proofs[f"authority:{name}"] = _sha(_norm(text))
    if "STYLE.md" in texts:
        try:
            from .chat_style import compile_style_contract

            compile_style_contract(texts["STYLE.md"])
        except Exception as exc:
            problem(
                "authority:STYLE.md",
                "AUTHORITY_DOCUMENT_INVALID",
                f"STYLE.md cannot be compiled: {exc}",
            )

    agents, agents_problem, agents_warning = _agents_component(ctx, policy)
    if agents:
        proofs["agents"] = agents
    if agents_problem:
        problem("agents", *agents_problem)
    if agents_warning:
        warnings.append(agents_warning)

    host, host_problem = _host_component(ctx)
    if host:
        proofs["host"] = host
    if host_problem:
        problem("host", *host_problem)

    skills: list[dict] = []
    for contract in policy.get("skills") or []:
        resolved = resolve_skill(ctx, contract)
        skills.append({**resolved, "critical": bool(contract.get("critical"))})
        if resolved["resolved"]:
            proofs[f"skill:{resolved['name']}"] = resolved["fingerprint"]
        elif contract.get("critical"):
            problem(
                f"skill:{resolved['name']}",
                "SKILL_UNRESOLVED",
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


_ACTIVE = threading.local()


@contextlib.contextmanager
def _runtime_scope(runtime: Path | None):
    """Carry the caller's authority endpoint to the ledger helpers below.

    `_read_record` and `verify_transport` keep their small positional
    signatures -- the state-machine tests replace them with doubles of exactly
    that shape -- so the endpoint a Context names travels beside the call
    instead of through it.
    """
    previous = getattr(_ACTIVE, "runtime", None)
    _ACTIVE.runtime = runtime
    try:
        yield
    finally:
        _ACTIVE.runtime = previous


def _runtime() -> Path | None:
    return getattr(_ACTIVE, "runtime", None)


def verify_transport(
    project_root: Path | str | None,
    verb: str,
    session_id: str,
    value: object,
    *,
    host: str | None = None,
    model: object = None,
    provider: object = None,
    authority_root: Path | str | None = None,
    home: Path | str | None = None,
) -> tuple[bool, str | None, str | None]:
    """Verified only by the separated broker, and never by shape.

    Two things can be true here and they are not the same: a capability that the
    live broker minted and can reproduce, and a live broker accepting THIS
    process as the host's own hook. A caller-supplied key, an environment
    string, a hook name, a legacy `hook:<event>:<mac>` or any ordinary SHA-256
    value is none of those, because nothing local can sign what the broker signs.
    """
    if project_root is None:
        return False, AUTHORITY_UNAVAILABLE, None
    from . import host_authority_client

    reply = host_authority_client.authorize(
        project=project_root,
        session=session_id,
        host=host or "claude",
        verb=verb,
        model=model,
        provider=provider,
        capability=value,
        authority_root=authority_root,
        home=home,
        runtime=_runtime(),
    )
    if reply is None:
        return False, AUTHORITY_UNAVAILABLE, None
    if not reply.get("ok"):
        return (
            False,
            "".join(
                [
                    AUTHORITY_UNAVAILABLE,
                    "; the broker refused this client (",
                    str(reply.get("code") or "unknown"),
                    "): ",
                    str(reply.get("detail") or ""),
                ]
            ),
            None,
        )
    return True, None, str(reply.get("event") or "hook")


def _seal(record: dict) -> str:
    body = {k: v for k, v in record.items() if k not in ("seal", "provenance")}
    return _sha(json.dumps(body, sort_keys=True))


def _verify_record_provenance(record: dict) -> bool:
    """Provenance is a question only the live broker can answer.

    The record's keyed provenance is an HMAC under a key that exists in broker
    memory and nowhere on disk, so a same-user process can copy, seal and shape
    a record without ever producing one this returns True for. No broker is a
    refusal, never a pass: a well-formed record is not evidence.
    """
    try:
        from .host_authority_client import verify_record

        return verify_record(record, runtime=_runtime())
    except Exception:
        return False


def _read_record(project_root: Path, session_id: str) -> dict | None:
    """Read-only. Corrupt, transplanted, unsigned or unproven records are absent.

    Absent, not fatal: a record this cannot prove is simply not evidence, and
    the next handshake establishes admission again. A restarted authority
    therefore costs one re-delivery and never a refusal.
    """
    try:
        record = json.loads(_ledger_path(project_root, session_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("schema") != SCHEMA_VERSION:
        return None
    if record.get("session") != session_id or record.get("seal") != _seal(record):
        return None
    if not record.get("provenance") or not _verify_record_provenance(record):
        return None
    return record


def _write_record(project_root: Path, session_id: str, record: dict, transport_event: str) -> None:
    """UNAVAILABLE: the separated broker owns the authoritative write.

    Do not reopen this writer with a caller-supplied key or verifier, and do not
    route the broker's own ledger write through here: the broker holds its key
    and its ledger, and an ordinary engine caller holds neither. What a hook can
    still do is ask (`host_authority_client.attempt_admission`).
    """
    raise PermissionError(AUTHORITY_UNAVAILABLE)


def invalidate(
    project_root: Path | None,
    session_id: str,
    reason: str,
    transport: object = None,
    *,
    host: str | None = None,
    model: object = None,
    provider: object = None,
    authority_root: Path | str | None = None,
    home: Path | str | None = None,
    runtime: Path | None = None,
) -> dict:
    """Drop the session's record through the broker. A host-transport operation.

    The broker both authenticates the caller and performs the delete, so
    invalidation on SessionStart, PostModelSwitch or a changed authority is
    mechanical rather than asserted. Returns {ok, removed, code}: ok False with
    CODE_TRANSPORT_REQUIRED when no genuine capability reached the broker.

    `removed` False with `ok` True is also the truthful answer when NO authority
    is alive at all: the record's provenance died with the key that signed it,
    so there is no admission left to revoke and nothing here pretends to revoke
    it. `unproven` says so.
    """
    if project_root is None:
        return {"ok": True, "removed": False, "code": None}
    from . import host_authority_client

    # Whatever an unverified session was handed, a changed context or model
    # is handed again: the note is economy, never evidence.
    host_authority_client.note_delivered(project_root, session_id, None)
    with _runtime_scope(runtime):
        reply = host_authority_client.invalidate(
            project=project_root,
            session=session_id,
            host=host or "claude",
            reason=reason,
            model=model,
            provider=provider,
            authority_root=authority_root,
            home=home,
            runtime=runtime,
        )
        if reply is not None and reply.get("ok"):
            return {"ok": True, "removed": bool(reply.get("removed")), "code": None}
        admitted, detail, _event = verify_transport(
            project_root, "invalidate", session_id, transport
        )
    if not admitted:
        return {
            "ok": False,
            "removed": False,
            "code": CODE_TRANSPORT_REQUIRED,
            "detail": detail,
            "failure": (
                taxonomy.from_broker(reply.get("code")) if reply else "AUTHORITY_UNREACHABLE"
            ),
        }
    path = _ledger_path(Path(project_root), session_id)
    try:
        path.unlink()
        return {"ok": True, "removed": True, "code": None}
    except OSError:
        return {"ok": True, "removed": False, "code": None}


# ---------------------------------------------------------------- verdicts


def _verdict(state: str, **fields) -> dict:
    permitted = state in (STATE_ADMITTED, STATE_UNBOUND, STATE_DEGRADED)
    return {
        "state": state,
        "permitted": permitted,
        #: A permit is not the same claim as admission: only these two states
        #: were mechanically proven. DEGRADED permits and verifies nothing.
        "verified": state in (STATE_ADMITTED, STATE_UNBOUND),
        "applies": state != STATE_UNBOUND,
        "code": None if permitted else CODE_REQUIRED,
        **fields,
    }


def scoped_repair(ctx: Context) -> str | None:
    """The repair command of the installation THIS session runs, or None.

    T-1747: `saipen host repair` repairs the default installation of every
    host. A Claude session started with another configuration profile was told
    to run it, ran it, and was degraded again on the next start, because that
    profile is repaired only by name. None means the bare command is the right
    one: another host, or the default profile.
    """
    if ctx.host != "claude" or ctx.profile is None:
        return None
    base = Path(ctx.home) if ctx.home is not None else Path.home()
    selected = os.path.normcase(os.path.abspath(ctx.profile))
    if selected == os.path.normcase(os.path.abspath(base / ".claude")):
        return None
    return f'{taxonomy.REPAIR} --host claude --profile "{Path(ctx.profile)}"'


def _unstarted_step(recovery: dict | None) -> str | None:
    """Why no authority service was started for this process, as a step.

    With no service running, the client starts one only for the host's own
    hook invocation. When it declines, the reason is the same closed code the
    service would have answered with, and it is the only thing that says the
    session is unverified because of WHO asked, not because nothing is there.
    """
    block = recovery or {}
    if block.get("state") != "not_a_host_client":
        return None
    return taxonomy.as_step((block.get("identity") or {}).get("hook_reason"))


def _lead(problems: list) -> dict | None:
    """The problem a diagnostic leads with: the first blocking one, else the first."""
    listed = [item for item in problems or [] if isinstance(item, dict)]
    stopping = taxonomy.blocking(listed)
    return (stopping or listed or [None])[0]


def diagnostic(verdict: dict) -> str:
    """The runtime-authored, bounded diagnostic. The model whose admission
    failed never writes it, and it never contains free-form advice.

    A refusal always carries four things, in this order: what is wrong in plain
    words, the registered failure code, what the runtime already tried, and the
    ONE action left to the operator. A message that says only that an authority
    "is required" tells the operator nothing they can act on.
    """
    state = verdict.get("state")
    problems = [item for item in (verdict.get("problems") or []) if isinstance(item, dict)]
    lead = _lead(problems)
    parts = [f"{DIAGNOSTIC_PREFIX} {state}"]
    if lead is not None:
        entry = taxonomy.get(lead["code"]) if taxonomy.known(lead.get("code")) else None
        summary = entry.summary if entry else "An unclassified failure was reported."
        parts.append(f"{summary} [{lead.get('code') or 'UNCLASSIFIED'}]")
        reasons = "; ".join(str(item.get("reason") or "") for item in problems[:3])
        if reasons:
            parts.append(reasons[:260])
    stale = [f"{name} changed" for name in verdict.get("stale") or []]
    if stale:
        parts.append("; ".join(stale))
    elif lead is None and state == STATE_BINDING:
        parts.append("authority not yet delivered to this session")
    recovery = verdict.get("recovery")
    if isinstance(recovery, dict) and recovery.get("attempted"):
        attempted = ", ".join(str(item) for item in recovery.get("attempted") or [])
        parts.append(f"automatic recovery attempted [{attempted}]; state {recovery.get('state')}")
    if lead is not None:
        parts.append("Do this: " + taxonomy.first_action(problems))
    else:
        parts.append(
            "No reply is permitted until admission is current. "
            "The runtime re-delivers authority on the next prompt."
        )
    return (" -- ".join(parts))[:_MAX_DIAGNOSTIC]


def staleness(record: dict, ctx: Context, proofs: dict) -> list[str]:
    """Every component whose proven value changed, plus the session labels the
    runtime can still observe. The broker asks the identical question before it
    decides whether a token it is holding is still current or must be replaced.
    """
    stale = [
        name
        for name in sorted(set(proofs) | set(record.get("proofs") or {}))
        if (record.get("proofs") or {}).get(name) != proofs.get(name)
    ]
    for label, now in (("model", ctx.model), ("provider", ctx.provider)):
        then = record.get(label)
        if then and now and then != now:
            stale.append(label)
    if record.get("host") != ctx.host:
        stale.append("host-identity")
    return stale


def unobserved(record: dict, ctx: Context) -> list[str]:
    """Labels the runtime cannot compare today: neither side proves anything."""
    return [
        label
        for label, now in (("model", ctx.model), ("provider", ctx.provider))
        if not record.get(label) or not now
    ]


def _typed(problems: object) -> list[dict]:
    """Problems as a list of TYPED problems.

    An answer from an authority service of another generation may carry
    problems this table does not know. Those are not decided on their wording
    and not dropped: together they are one registered failure, the generation
    mismatch that produced them.
    """
    listed = [item for item in (problems or []) if isinstance(item, dict)]
    if all(taxonomy.known(item.get("code")) for item in listed):
        return listed
    reasons = "; ".join(str(item.get("reason") or "") for item in listed[:3])
    return [
        taxonomy.problem(
            "transport",
            "AUTHORITY_GENERATION_MISMATCH",
            "the authority service reported problems this runtime cannot classify: " + reasons,
        )
    ]


def _refusal(problems: list, *, warnings: list | None = None, recovery: dict | None = None) -> dict:
    lead = _lead(problems) or {}
    transport_failed = any(item.get("component") == "transport" for item in problems)
    return {
        **_verdict(
            STATE_REFUSED,
            problems=list(problems),
            stale=[],
            warnings=list(warnings or []),
            unobserved=[],
        ),
        "code": CODE_TRANSPORT_REQUIRED if transport_failed else CODE_REQUIRED,
        "failure": lead.get("code"),
        "failure_step": lead.get("step"),
        "delivery": "",
        "recovery": recovery or {},
        "actions": [taxonomy.first_action(problems)],
    }


def _degraded_verdict(
    *,
    found: dict | None = None,
    generation_value: str | None = None,
    problems: list | None = None,
    stale: list | None = None,
) -> dict:
    """The policy's fallback. It permits, and it claims nothing: no record, no
    capability and no mechanical admission.

    The problems travel WITH the verdict so the marker the operator sees is
    specific -- which proof was missing -- instead of a silent downgrade that
    hides why the session is unverified.
    """
    fields = {}
    if found is not None:
        fields["warnings"] = list(found.get("warnings") or [])
    listed = list(problems or [])
    verdict = _verdict(
        STATE_DEGRADED, problems=listed, stale=list(stale or []), unobserved=[], **fields
    )
    if generation_value:
        verdict["generation"] = generation_value
    verdict["degraded"] = True
    verdict["marker"] = DEGRADED_MARKER
    lead = _lead(listed) or {}
    verdict["failure"] = lead.get("code")
    verdict["failure_step"] = lead.get("step")
    verdict["delivery"] = ""
    return verdict


def _unbound(ctx: Context) -> bool:
    return (
        ctx.project_root is None
        or not (Path(ctx.project_root) / ".saipen" / "STATE.md").is_file()
    )


def evaluate(ctx: Context) -> dict:
    """Read-only: the admission state of this session right now.

    The answer is the decision table applied to what is observable: a blocking
    problem is REFUSED in every mode; anything else that is not a proven,
    current record is REFUSED/BINDING/STALE under STRICT and a DEGRADED permit
    under DEGRADED_ALLOWED.
    """
    if _unbound(ctx):
        return _verdict(STATE_UNBOUND, problems=[], stale=[], warnings=[], unobserved=[])
    mode = admission_mode(ctx)
    allow = mode == taxonomy.MODE_DEGRADED
    binding = binding_problems(ctx)
    if taxonomy.blocking(binding):
        return _refusal(binding)
    with _runtime_scope(ctx.runtime):
        remote = None
        if ctx.policy is None and ctx.adapters is None:
            # The live authority already holds every identity this would
            # re-derive; asking it is one frame instead of re-hashing the
            # shipped surface. An injected policy or registry is a caller's own
            # world, which only the local path can judge.
            try:
                from . import host_authority_client

                remote = host_authority_client.evaluate(
                    project=ctx.project_root,
                    session=ctx.session_id,
                    host=ctx.host,
                    model=ctx.model,
                    provider=ctx.provider,
                    authority_root=_authority_root(ctx),
                    home=ctx.home,
                    runtime=ctx.runtime,
                )
            except Exception:
                remote = None
        if remote is not None:
            state = remote.get("state")
            problems = _typed(remote.get("problems")) if remote.get("problems") else []
            warnings = list(remote.get("warnings") or [])
            if state == STATE_ADMITTED and not problems:
                return _verdict(
                    STATE_ADMITTED,
                    problems=[],
                    stale=[],
                    warnings=warnings,
                    unobserved=list(remote.get("unobserved") or []),
                    generation=remote.get("generation"),
                    token=remote.get("token"),
                )
            if problems:
                if taxonomy.decide(mode, problems) == taxonomy.DECISION_BLOCK:
                    return _refusal(problems, warnings=warnings)
                return _degraded_verdict(
                    found={"warnings": warnings},
                    generation_value=remote.get("generation"),
                    problems=problems,
                )
            if allow:
                return _degraded_verdict(
                    found={"warnings": warnings},
                    generation_value=remote.get("generation"),
                    problems=[],
                    stale=list(remote.get("stale") or []),
                )
            return _verdict(
                STATE_STALE if state == STATE_STALE else STATE_BINDING,
                problems=[],
                stale=list(remote.get("stale") or []),
                warnings=warnings,
                unobserved=list(remote.get("unobserved") or []),
                generation=remote.get("generation"),
                token=remote.get("token"),
            )
        policy = ctx.policy if ctx.policy is not None else load_policy()
        found = components(ctx, policy)
        problems = binding + found["problems"]
        if problems:
            if taxonomy.decide(mode, problems) == taxonomy.DECISION_BLOCK:
                return _refusal(problems, warnings=found["warnings"])
            return _degraded_verdict(
                found=found, generation_value=generation(found["proofs"]), problems=problems
            )
        current = generation(found["proofs"])
        record = _read_record(Path(ctx.project_root), ctx.session_id)
    if record is None:
        if allow:
            return _degraded_verdict(found=found, generation_value=current, problems=[])
        return _verdict(
            STATE_BINDING,
            problems=[],
            stale=[],
            warnings=found["warnings"],
            unobserved=[],
            generation=current,
        )
    stale = staleness(record, ctx, found["proofs"])
    unobserved_labels = unobserved(record, ctx)
    if stale:
        if allow:
            return _degraded_verdict(
                found=found, generation_value=current, problems=[], stale=stale
            )
        return _verdict(
            STATE_STALE,
            problems=[],
            stale=stale,
            warnings=found["warnings"],
            unobserved=unobserved_labels,
            generation=current,
            token=record.get("token"),
        )
    return _verdict(
        STATE_ADMITTED,
        problems=[],
        stale=[],
        warnings=found["warnings"],
        unobserved=unobserved_labels,
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


def _establish_presented(ctx: Context, event: str | None) -> dict:
    """The write boundary accepted a PRESENTED capability.

    In production this can only be a capability the live broker minted and can
    reproduce; the path stays because it is the exact shape every host
    transport is required to satisfy, and it is the one the state-machine tests
    drive with their own doubles.
    """
    verdict = evaluate(ctx)
    if verdict["state"] in (STATE_UNBOUND, STATE_REFUSED, STATE_ADMITTED):
        return {**verdict, "delivery": ""}
    policy = ctx.policy if ctx.policy is not None else load_policy()
    found = components(ctx, policy)
    if found["problems"]:
        return _refusal(found["problems"], warnings=found["warnings"])
    gen = generation(found["proofs"])
    token = "tok-" + _sha(json.dumps([gen, ctx.session_id, ctx.model, ctx.provider]))[:32]
    delivered = {
        name: _sha(found["texts"][name]) for name in AUTHORITY_DOCUMENTS if name in found["texts"]
    }
    delivered.update(
        {
            f"skill:{skill['name']}": skill["fingerprint"]
            for skill in found["skills"]
            if skill.get("resolved")
        }
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


def establish(ctx: Context, transport: object = None, *, fresh: bool = False) -> dict:
    """Ask the separated authority to admit this session. It owns the write.

    The layers decide in order and the first failure wins:

    1. BINDING. A project carrier that contradicts the project the session is
       in refuses in every mode, before any authority is asked.
    2. A PRESENTED capability is a claim. One the live authority reproduces is
       accepted; one it does not is a forgery or a replay and refuses in every
       mode -- an unverifiable claim is never "merely unproven".
    3. The authority. When it admits, that answer IS the verdict: it proved the
       hook from the OS, computed the fingerprints itself, minted the capability
       and wrote the ledger record.
    4. The policy. Whatever is left is a typed list of what could not be
       established. `host_taxonomy.decide` turns it into a refusal (STRICT, or
       any blocking failure) or into a DEGRADED permit that delivers the
       authority bytes, names what was not proven and claims no admission.

    `fresh` drops the session's record first: a new, resumed, cleared or
    compacted context holds nothing the old record proved.
    """
    from . import host_authority_client

    if _unbound(ctx):
        return {
            **_verdict(STATE_UNBOUND, problems=[], stale=[], warnings=[], unobserved=[]),
            "delivery": "",
        }
    mode = admission_mode(ctx)
    if fresh:
        host_authority_client.note_delivered(ctx.project_root, ctx.session_id, None)
    binding = binding_problems(ctx)
    if taxonomy.blocking(binding):
        return _refusal(binding)
    with _runtime_scope(ctx.runtime):
        presented = transport if transport is not None else os.environ.get(TRANSPORT_ENV, "")
        if presented:
            admitted, transport_detail, event = verify_transport(
                ctx.project_root, "establish", ctx.session_id, presented
            )
            if admitted:
                return _establish_presented(ctx, event)
            return _refusal(
                [
                    *binding,
                    taxonomy.problem(
                        "transport",
                        "CAPABILITY_FORGED",
                        transport_detail or AUTHORITY_UNAVAILABLE,
                    ),
                ]
            )
        outcome = host_authority_client.attempt_admission(
            project=ctx.project_root,
            session=ctx.session_id,
            host=ctx.host,
            model=ctx.model,
            provider=ctx.provider,
            authority_root=_authority_root(ctx),
            home=ctx.home,
            event="establish",
            runtime=ctx.runtime,
            fresh=fresh,
        )
        recovery = outcome.get("recovery") or {}
        reply = outcome.get("verdict") if outcome.get("reachable") else None
        if reply is not None and reply.get("state") == STATE_ADMITTED:
            verdict = dict(reply)
            verdict["recovery"] = recovery
            verdict["actions"] = []
            verdict["failure"] = None
            if binding:
                # A carrier that names nothing usable does not unmake a proven
                # admission of the project the session is really in.
                verdict["warnings"] = list(verdict.get("warnings") or []) + [
                    str(item.get("reason")) for item in binding
                ]
            return verdict
        problems = list(binding)
        if reply is not None:
            # The authority answered with what is wrong, in its own words.
            problems += _typed(reply.get("problems"))
        elif outcome.get("refused"):
            # The authority is up and could not place THIS caller: say what it
            # saw, not that an authority is missing.
            seen = (outcome.get("identity") or {}).get("reason")
            problems.append(
                taxonomy.problem(
                    "transport",
                    str(outcome.get("failure") or "AUTHORITY_CLIENT_UNPROVEN"),
                    str(outcome.get("detail") or "the authority refused this client")
                    + (f" ({seen})" if seen else ""),
                    step=seen,
                )
            )
        else:
            problems.append(
                taxonomy.problem(
                    "transport",
                    str(outcome.get("failure") or "AUTHORITY_UNREACHABLE"),
                    " ".join(
                        [AUTHORITY_UNAVAILABLE, host_authority_client.describe_recovery(outcome)]
                    ),
                    step=_unstarted_step(recovery),
                )
            )
        policy = ctx.policy if ctx.policy is not None else load_policy()
        found = components(ctx, policy)
        if reply is None:
            # No authority spoke for the protocol, so this runtime's own view of
            # it is what there is: a damaged install is reported beside the
            # reason the authority could not be asked.
            seen = {(item.get("component"), item.get("code")) for item in problems}
            problems += [
                item
                for item in found["problems"]
                if (item.get("component"), item.get("code")) not in seen
            ]
    if taxonomy.decide(mode, problems) == taxonomy.DECISION_BLOCK:
        return _refusal(problems, warnings=found["warnings"], recovery=recovery)
    gen = generation(found["proofs"])
    verdict = _degraded_verdict(found=found, generation_value=gen, problems=problems)
    repeat = host_authority_client.already_delivered(ctx.project_root, ctx.session_id, gen)
    # The authority text is handed to an unverified session ONCE per context;
    # afterwards the prompt carries only the short marker and the contract.
    verdict["delivery"] = "" if repeat else _delivery(found, gen)
    action = taxonomy.first_action(problems)
    scoped = scoped_repair(ctx)
    if scoped and action == taxonomy.REPAIR:
        action = scoped
    verdict["notice"] = host_authority_client.degraded_notice(
        problems, brief=repeat, repair=scoped
    )
    verdict["recovery"] = recovery
    verdict["actions"] = [action]
    if not repeat:
        host_authority_client.note_delivered(ctx.project_root, ctx.session_id, gen)
    return verdict


def decision_table() -> dict:
    """The policy this owner applies, as data: every registered failure and
    what each admission mode does with it. Read by the doctor view, the adapter
    documentation and the tests, so none of them restates it."""
    rows = []
    for entry in taxonomy.table():
        problem = [{"component": "table", "code": entry["code"], "reason": ""}]
        rows.append(
            {
                **entry,
                "strict": taxonomy.decide(taxonomy.MODE_STRICT, problem),
                "degraded_allowed": taxonomy.decide(taxonomy.MODE_DEGRADED, problem),
            }
        )
    return {
        "default_mode": taxonomy.DEFAULT_MODE,
        "modes": dict(taxonomy.MODE_LABELS),
        "admitted": {
            "strict": taxonomy.decide(taxonomy.MODE_STRICT, [], admitted=True),
            "degraded_allowed": taxonomy.decide(taxonomy.MODE_DEGRADED, [], admitted=True),
        },
        "not_yet_admitted": {
            "strict": taxonomy.decide(taxonomy.MODE_STRICT, []),
            "degraded_allowed": taxonomy.decide(taxonomy.MODE_DEGRADED, []),
        },
        "failures": rows,
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
    "AUTHORITY_UNAVAILABLE",
    "CODE_REQUIRED",
    "CODE_TRANSPORT_REQUIRED",
    "DEGRADED_MARKER",
    "DIAGNOSTIC_PREFIX",
    "STATES",
    "STATE_DEGRADED",
    "TRANSPORT_ENV",
    "TRANSPORT_PREFIX",
    "Context",
    "admission_mode",
    "binding_problems",
    "capability_matrix",
    "consulted",
    "decision_table",
    "degradable_only",
    "degraded",
    "diagnostic",
    "establish",
    "evaluate",
    "generation",
    "host_claims",
    "invalidate",
    "load_policy",
    "provider_fingerprint",
    "resolve_skill",
    "staleness",
    "unobserved",
    "verify_transport",
]
