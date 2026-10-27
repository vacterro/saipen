"""HOST-INTEGRATION-01: one state model, one doctor and one repair for hosts.

Defect class: host integration was a scatter of booleans and error strings, and
they disagreed in front of the operator. The injector printed "provenance
verified" and the launcher answered `CANONICAL_RUNTIME_SOURCE_UNPROVEN` a minute
later; a hook being present was read as the host being healthy; a marker being
present was read as admission being mechanical; the one host with a
prompt-blocking hook had no supported way back when that hook blocked. Each
surface was locally right, and nobody could say what state a host was in.

This module says it, from one place:

* `capability_contract` -- what each registered host CAN do, read from the
  adapter registry and from nowhere else: its install surfaces, what it can
  intercept, where its host authority comes from, whether admission can be
  mechanical there, how it is launched and how it recovers. A cell the registry
  does not declare is reported as undeclared, never inferred from a file.
* `observe` / `derive_state` -- what each host IS right now, as one of nine
  states with the facts that produced it. Installed, fresh, healthy and
  verified are four separate facts and are never folded into each other.
* `doctor` -- the read-only view. It writes nothing and starts nothing.
* `repair` -- the one operator entry point. It reinstalls stale or broken host
  integrations through the canonical installer, restarts an authority service
  left over from another generation, and reports what still needs a person. It
  never touches a project.
* `mode` -- show or set the admission policy.

States (the first that applies):

    UNINSTALLED           SAIPEN is not installed for this host
    INSTALLING            an installation is staged and not yet activated
    BROKEN                an installed surface cannot run or cannot be read
    STALE_RUNTIME         installed bytes are not the canonical generation
    RECOVERING            the last prompt recovered the authority service
    AUTHORITY_UNAVAILABLE installed and current, the last prompt found no
                          provable host authority
    DEGRADED_UNVERIFIED   the last prompt proceeded UNVERIFIED for another reason
    INSTALLED_UNVERIFIED  installed and current; no health evidence yet, or the
                          host exposes no channel that could give any
    HEALTHY_VERIFIED      installed, current, and the last prompt was ADMITTED
                          by the separated authority

`HEALTHY_VERIFIED` is only ever derived from a recorded ADMITTED prompt that is
newer than the installed hook. A host without an evidence channel can be
installed and current forever and is still reported `INSTALLED_UNVERIFIED`:
that is the truth about what SAIPEN can see there, not a fault to repair.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import host_taxonomy as taxonomy

STATE_UNINSTALLED = "UNINSTALLED"
STATE_INSTALLING = "INSTALLING"
STATE_INSTALLED_UNVERIFIED = "INSTALLED_UNVERIFIED"
STATE_HEALTHY_VERIFIED = "HEALTHY_VERIFIED"
STATE_RECOVERING = "RECOVERING"
STATE_DEGRADED_UNVERIFIED = "DEGRADED_UNVERIFIED"
STATE_STALE_RUNTIME = "STALE_RUNTIME"
STATE_AUTHORITY_UNAVAILABLE = "AUTHORITY_UNAVAILABLE"
STATE_BROKEN = "BROKEN"
STATES = (
    STATE_UNINSTALLED,
    STATE_INSTALLING,
    STATE_INSTALLED_UNVERIFIED,
    STATE_HEALTHY_VERIFIED,
    STATE_RECOVERING,
    STATE_DEGRADED_UNVERIFIED,
    STATE_STALE_RUNTIME,
    STATE_AUTHORITY_UNAVAILABLE,
    STATE_BROKEN,
)
#: States `repair` acts on. Everything else is either fine or not SAIPEN's to fix.
REPAIRABLE = (STATE_BROKEN, STATE_STALE_RUNTIME, STATE_INSTALLING)

#: What the registry may declare for how a host recovers and degrades.
RECOVERY_AUTHORITY = "AUTHORITY_RESTART_THEN_DEGRADE"
RECOVERY_PRELAUNCH = "PRELAUNCH_RESYNC"
RECOVERY_NONE = "NONE"
DEGRADED_DEFAULT = "DEGRADED_ALLOWED_DEFAULT"
DEGRADED_NOT_APPLICABLE = "NOT_APPLICABLE"
LAUNCH_NATIVE = "NATIVE"
LAUNCH_NATIVE_OR_LAUNCHER = "NATIVE_OR_OPTIONAL_LAUNCHER"

UNDECLARED = "UNDECLARED"
#: A health record older than this is history, not the host's current state.
HEALTH_FRESH_SECONDS = 7 * 24 * 3600
#: Registry cells every first-class host must declare (no unexplained cell).
CONTRACT_FIELDS = (
    "install_surfaces",
    "tool_interception",
    "prompt_interception",
    "response_interception",
    "host_authority_source",
    "separated_authority",
    "mechanical_admission",
    "launch",
    "auto_recovery",
    "degraded_mode",
)


def source_root() -> Path:
    """The SAIPEN home this module runs from (a clone or an installed runtime)."""
    return Path(__file__).resolve().parents[2]


def load_registry(root: Path | None = None) -> dict:
    path = (root or source_root()) / "extensions" / "adapters" / "registry.json"
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _expand(surface: object) -> Path | None:
    """A registry surface as a path on this machine, or None when it names an
    unset host variable (that host is simply not configured here)."""
    text = str(surface or "").strip()
    if not text:
        return None
    expanded = os.path.expandvars(os.path.expanduser(text))
    if expanded.startswith("$"):
        return None
    return Path(expanded)


def capability_contract(adapter: dict) -> dict:
    """What this host can do, as the adapter registry declares it.

    Pure projection: every value is a registry field or a fixed function of
    one. A capability the registry does not state is `UNDECLARED` -- reporting
    a stronger capability than the registry claims is exactly the defect this
    contract exists to prevent, and guessing a weaker one hides a real claim.
    """
    install = adapter.get("install") if isinstance(adapter.get("install"), dict) else {}
    launch_executable = adapter.get("launch_executable")
    launch = {
        "routine": adapter.get("routine_launch") or UNDECLARED,
        "mode": LAUNCH_NATIVE_OR_LAUNCHER if launch_executable else LAUNCH_NATIVE,
        "launcher_command": adapter.get("launch_command"),
        "executable": launch_executable,
    }
    return {
        "id": adapter.get("id"),
        "name": adapter.get("name"),
        "install_surfaces": {
            key: install.get(key) for key in ("home", "skill", "instruction", "hook", "bespoke")
            if install.get(key)
        },
        "tool_interception": adapter.get("declared_strength") or UNDECLARED,
        "prompt_interception": adapter.get("pre_output_interception") or UNDECLARED,
        "response_interception": adapter.get("stop_output_interception") or UNDECLARED,
        "response_enforcement": adapter.get("response_enforcement") or UNDECLARED,
        "admission_enforcement": adapter.get("admission_enforcement") or UNDECLARED,
        "host_authority_source": adapter.get("admission_authority") or "NONE",
        "separated_authority": bool(adapter.get("admission_authority")),
        "mechanical_admission": adapter.get("admission_enforcement") == "MECHANICAL",
        "prompt_blocking": adapter.get("admission_required") is True,
        "launch": launch,
        "auto_recovery": adapter.get("auto_recovery") or UNDECLARED,
        "degraded_mode": adapter.get("degraded_mode") or UNDECLARED,
    }


def contract_gaps(contract: dict) -> list[str]:
    """Cells of one host's contract that the registry leaves undeclared."""
    gaps = [key for key in CONTRACT_FIELDS if contract.get(key) in (None, UNDECLARED)]
    if contract["launch"]["routine"] == UNDECLARED and "launch" not in gaps:
        gaps.append("launch")
    return gaps


def capability_matrix(root: Path | None = None) -> dict:
    """host id -> capability contract, for every registered adapter."""
    registry = load_registry(root)
    return {
        str(adapter.get("id")): capability_contract(adapter)
        for adapter in registry.get("adapters", [])
        if adapter.get("id")
    }


# --------------------------------------------------------------- observation


def health_path(host: str, home: Path | None = None, profile: Path | None = None) -> Path:
    base = Path(home) if home is not None else Path.home()
    if host == "claude" and profile is not None:
        from .claude_profiles import health_file

        return health_file(base, profile)
    return base / ".saipen" / "health" / f"{host}.json"


def read_health(host: str, home: Path | None = None, profile: Path | None = None) -> dict | None:
    """The last outcome the host's own hook recorded, or None. Diagnostics
    only: nothing decides admission from this file."""
    try:
        payload = json.loads(health_path(host, home, profile).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _mtime(path: Path | None) -> float | None:
    try:
        return path.stat().st_mtime if path is not None else None
    except OSError:
        return None


def _hook_facts(adapter: dict, runtime_root: Path | None, home: Path) -> dict:
    """The installed blocking hook: present, current, and what it delegates to."""
    declared = adapter.get("hook_install_surface") or (adapter.get("install") or {}).get("hook")
    surface = _expand(declared)
    facts: dict = {
        "declared": bool(adapter.get("hook_artifact")),
        "path": str(surface) if surface else None,
        "installed": bool(surface and surface.is_file()),
        "status": "absent",
        "delegated_root": None,
        "delegated_current": None,
        "problems": [],
        "installed_at": _mtime(surface),
    }
    if not facts["declared"] or surface is None:
        facts["status"] = "not-applicable"
        return facts
    if not facts["installed"]:
        return facts
    checker = runtime_root if runtime_root is not None else source_root()
    try:
        if adapter.get("hook_installer"):
            # The installer module of the runtime that is RUNNING, asked about
            # the runtime under inspection (`checker`). Importing it from
            # `checker` let the inspected copy judge itself: a stale or damaged
            # installation decided its own "current", and a repair's re-check
            # ran the code it had just replaced (T-1634).
            tools = str(source_root() / "tools")
            if tools not in sys.path:
                sys.path.insert(0, tools)
            from install_host_guard import install, is_retired

            if is_retired(surface):
                # The inert file an uninstall leaves for a host that was still
                # running: nothing is installed, and nothing needs repair.
                facts["installed"] = False
                facts["retired"] = True
                return facts

            options = {"profile": Path(adapter["profile"])} if adapter.get("profile") else {}
            result = install(str(adapter["id"]), home, checker, check=True, **options)
            facts["status"] = "current" if result.get("current") else "stale"
            facts["delegated_root"] = result.get("saipen_root")
            facts["delegated_current"] = bool(result.get("root_current"))
            facts["problems"] = list(result.get("problems") or [])
            if result.get("style_hook_conflicts"):
                facts["style_hook_conflicts"] = result["style_hook_conflicts"]
        else:
            from .runtime_bootstrap import hook_problems

            facts["problems"] = hook_problems(adapter, checker)
            facts["status"] = "current" if not facts["problems"] else "stale"
    except Exception as exc:
        facts["status"] = "unknown"
        facts["problems"] = [f"hook-unobservable:{type(exc).__name__}"]
    return facts


def _runtime_facts(
    adapter: dict,
    canonical: Path | None,
    expected: str | None,
    sharing: tuple[str, ...] = (),
) -> dict:
    """The installed runtime copy: present, provable, and current with its source.

    `sharing` names every adapter that declares the SAME runtime directory. One
    directory carries one installer record, so a record written for a sibling
    adapter describes this adapter's runtime just as truly.
    """
    from .runtime_bootstrap import (
        PROVENANCE_FILENAME,
        launcher_problems,
        marker_problems,
        read_provenance,
        surface_diff,
        surface_fingerprint,
    )

    install = adapter.get("install") if isinstance(adapter.get("install"), dict) else {}
    skill = _expand(install.get("skill"))
    facts: dict = {
        "declared": bool(install.get("skill")),
        "path": str(skill) if skill else None,
        "installed": bool(skill and skill.is_dir()),
        "generation": None,
        "expected_generation": expected,
        "current": None,
        "diff": [],
        "launcher_problems": [],
        "provenance_problems": [],
        "source": None,
        "staging": [],
    }
    if skill is None or not facts["installed"]:
        if skill is not None:
            facts["staging"] = _staging_leftovers(skill)
        return facts
    facts["staging"] = _staging_leftovers(skill)
    facts["generation"] = surface_fingerprint(skill)
    marker = read_provenance(skill)
    facts["source"] = marker.get("canonical_source_root") if isinstance(marker, dict) else None
    facts["marker"] = str(skill / PROVENANCE_FILENAME) if marker is not None else None
    if canonical is not None:
        problems = marker_problems(marker, str(adapter.get("id")), canonical, expected)
        recorded = str((marker or {}).get("adapter_id") or "")
        if "adapter_id" in problems and recorded in sharing:
            problems = [item for item in problems if item != "adapter_id"]
        facts["provenance_problems"] = problems
        facts["diff"] = surface_diff(canonical, skill, limit=6)
    facts["launcher_problems"] = launcher_problems(skill)
    facts["current"] = bool(
        facts["generation"] is not None
        and expected is not None
        and facts["generation"] == expected
        and not facts["diff"]
    )
    return facts


def _staging_leftovers(skill: Path) -> list[str]:
    """Stage or backup directories an interrupted install left beside a home."""
    try:
        parent, leaf = skill.parent, skill.name
        return sorted(
            item.name
            for item in parent.iterdir()
            if item.name.startswith(f".{leaf}.saipen-")
        )
    except OSError:
        return []


def authority_facts(home: Path | None = None) -> dict:
    """The authority service and the admission policy, read without starting
    anything. `running` False is the ordinary idle state: the service is
    started by the first prompt that needs it."""
    from . import host_authority_broker as broker
    from . import host_authority_client as client

    policy = client.policy(home)
    live = client.health()
    facts = {
        "running": bool(live),
        "pid": (live or {}).get("pid"),
        "instance": (live or {}).get("instance"),
        "generation": (live or {}).get("generation"),
        "expected_generation": broker.service_generation(),
        "saipen_root": (live or {}).get("saipen_root"),
        "endpoint": broker.endpoint_name(),
        "log": str(broker.log_path()),
        "identity_supported": _identity_supported(),
        "mode": policy["mode"],
        "mode_label": taxonomy.MODE_LABELS[policy["mode"]],
        "mode_source": policy["source"],
        "mode_path": policy["path"],
    }
    facts["generation_current"] = (
        None if not live else facts["generation"] == facts["expected_generation"]
    )
    if not live:
        try:
            status = client._exchange({"op": "ping"}, runtime=None, timeout=client.PING_TIMEOUT)
            facts["unanswered"] = status[1]
        except Exception:
            facts["unanswered"] = None
    return facts


def _identity_supported() -> bool:
    from . import host_authority_process as proc

    return proc.platform_supported()


def observe(adapter: dict, *, home: Path | None = None, canonical: Path | None = None,
            expected: str | None = None, authority: dict | None = None,
            sharing: tuple[str, ...] = ()) -> dict:
    """Every observable fact about one host, with nothing inferred."""
    base = Path(home) if home is not None else Path.home()
    contract = capability_contract(adapter)
    install = adapter.get("install") if isinstance(adapter.get("install"), dict) else {}
    host_home = _expand(install.get("home"))
    runtime = _runtime_facts(adapter, canonical, expected, sharing)
    runtime_root = Path(runtime["path"]) if runtime["installed"] and runtime["path"] else None
    hook = _hook_facts(adapter, runtime_root, base)
    instruction = "not-applicable"
    if install.get("instruction"):
        target = _expand(install.get("instruction"))
        if target is None or not target.is_file():
            instruction = "absent"
        elif runtime_root is not None:
            try:
                tools = str(source_root() / "tools")
                if tools not in sys.path:
                    sys.path.insert(0, tools)
                from autoinject import instruction_status

                instruction = instruction_status(adapter, runtime_root)
            except Exception:
                instruction = "unknown"
        else:
            instruction = "unknown"
    profile = Path(adapter["profile"]) if adapter.get("profile") else None
    health = read_health(str(adapter.get("id")), home, profile)
    return {
        "id": adapter.get("id"),
        "name": adapter.get("name"),
        "contract": contract,
        "installable": bool(install),
        #: A bespoke installer step with no declared runtime directory leaves
        #: nothing this view can inspect; that is said, never guessed around.
        "observable": bool(install.get("skill") or adapter.get("hook_artifact")),
        "host_present": bool(host_home and host_home.is_dir()),
        "host_home": str(host_home) if host_home else None,
        "runtime": runtime,
        "hook": hook,
        "instruction": instruction,
        "health": health,
        "authority": authority if contract["separated_authority"] else None,
    }


def _same_file(left: object, right: object) -> bool:
    return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(
        os.path.abspath(str(right))
    )


def _health_is_current(facts: dict) -> bool:
    """Is the recorded outcome evidence about THIS installation?

    The record names the hook file that wrote it. One written by any other
    file -- a fixture's hook started with this profile, a staged or kept
    generation run by hand, a source checkout's copy -- says nothing about the
    installed hook, in either direction (T-1634: such a record turned a
    HEALTHY_VERIFIED host into AUTHORITY_UNAVAILABLE). A record that does not
    say which hook wrote it proves as little.
    """
    health = facts.get("health") or {}
    at = health.get("at")
    if not isinstance(at, (int, float)):
        return False
    if time.time() - at > HEALTH_FRESH_SECONDS:
        return False
    installed = facts["hook"].get("path")
    if installed and not (health.get("hook") and _same_file(health["hook"], installed)):
        return False
    installed_at = facts["hook"].get("installed_at")
    return installed_at is None or at >= installed_at - 1


def derive_state(facts: dict) -> tuple[str, list[str], str | None]:
    """(state, reasons, next action) for one host's observed facts.

    The order is the order of the module docstring: the first state that
    applies wins, and every state names what was seen, never what was assumed.
    """
    runtime, hook = facts["runtime"], facts["hook"]
    contract = facts["contract"]
    reasons: list[str] = []
    if not facts["installable"]:
        return STATE_UNINSTALLED, ["this host has no installable surface in the registry"], None
    if not facts["host_present"]:
        return STATE_UNINSTALLED, ["the host application is not set up on this machine"], None
    if runtime["staging"] and not runtime["installed"]:
        return (
            STATE_INSTALLING,
            ["an installation was staged and never activated: " + ", ".join(runtime["staging"])],
            taxonomy.REPAIR,
        )
    if not facts.get("observable", True):
        return (
            STATE_INSTALLED_UNVERIFIED,
            [
                "this host is set up by a bespoke installer step with no declared runtime "
                "directory; nothing here can be inspected, so nothing is claimed"
            ],
            None,
        )
    installed_any = runtime["installed"] or hook["installed"]
    if not installed_any:
        return STATE_UNINSTALLED, ["SAIPEN is not installed for this host"], taxonomy.REPAIR
    # ---- BROKEN: something installed cannot run or cannot be read
    if runtime["declared"] and not runtime["installed"]:
        reasons.append("the hook is installed but the runtime it needs is missing")
    elif runtime["installed"] and runtime["generation"] is None:
        reasons.append("the installed runtime cannot prove any generation (files missing)")
    if hook["status"] == "unknown":
        reasons.append("the installed hook cannot be inspected")
    if hook["declared"] and runtime["installed"] and not hook["installed"]:
        reasons.append("the runtime is installed but its host hook is missing")
    if any(str(item).startswith("hook-interpreter-missing") for item in hook["problems"]):
        reasons.append("the hook names an interpreter that no longer exists")
    if runtime["launcher_problems"]:
        reasons.append("installed launcher: " + ", ".join(runtime["launcher_problems"]))
    if reasons:
        return STATE_BROKEN, reasons, taxonomy.REPAIR
    # ---- STALE_RUNTIME: installed bytes are not the canonical generation
    if runtime["installed"] and runtime["current"] is False:
        names = ", ".join(runtime["diff"][:3]) or "generation differs"
        reasons.append(f"installed runtime is not the source generation ({names})")
    if runtime["provenance_problems"]:
        reasons.append("installer record: " + ", ".join(runtime["provenance_problems"]))
    if hook["declared"] and hook["status"] == "stale":
        reasons.append(
            "host hook is not the installed generation"
            + (": " + ", ".join(str(item) for item in hook["problems"]) if hook["problems"] else "")
        )
    if facts["instruction"] in ("stale", "absent"):
        reasons.append(f"instruction block is {facts['instruction']}")
    if runtime["staging"]:
        reasons.append("an interrupted installation left: " + ", ".join(runtime["staging"]))
    authority = facts.get("authority") or {}
    if authority.get("running") and authority.get("generation_current") is False:
        reasons.append("the running authority service is an older generation")
    if reasons:
        return STATE_STALE_RUNTIME, reasons, taxonomy.REPAIR
    # ---- installed and current: what does the host's own evidence say?
    if not contract["mechanical_admission"]:
        return (
            STATE_INSTALLED_UNVERIFIED,
            [
                "installed and current; this host exposes no channel through which "
                "SAIPEN could verify a session, so nothing more can be claimed"
            ],
            None,
        )
    if authority and not authority.get("identity_supported"):
        return (
            STATE_AUTHORITY_UNAVAILABLE,
            ["this platform does not report process identity; admission cannot be mechanical"],
            None,
        )
    health = facts.get("health") or {}
    if not _health_is_current(facts):
        return (
            STATE_INSTALLED_UNVERIFIED,
            ["installed and current; no prompt has been observed through this installation yet"],
            None,
        )
    outcome = str(health.get("state") or "")
    code = str(health.get("code") or "")
    # The step says which proof refused under that code (T-1649).
    step = taxonomy.as_step(health.get("step"))
    named = f"{code}/{step}" if code and step else code
    if outcome == "ADMITTED":
        return STATE_HEALTHY_VERIFIED, ["the last prompt was ADMITTED by the host authority"], None
    if outcome in ("BLOCKED", "REFUSED"):
        entry = taxonomy.get(code) if taxonomy.known(code) else None
        return (
            STATE_BROKEN,
            [f"the last prompt was blocked ({named or 'unclassified'})"],
            entry.operator_action if entry else taxonomy.REPAIR,
        )
    entry = taxonomy.get(code) if taxonomy.known(code) else None
    action = entry.operator_action if entry and entry.operator_action != "none" else taxonomy.DOCTOR
    # T-1747: the step names who could not be proven; the table row above it
    # only names the family the refusal was filed under.
    summary = taxonomy.step_summary(step) or (
        entry.summary if entry else "the last prompt proceeded unverified"
    )
    if entry is not None and entry.family == taxonomy.FAMILY_AUTHORITY:
        if authority.get("running") and code in ("AUTHORITY_UNREACHABLE", "AUTHORITY_FAULT"):
            return (
                STATE_RECOVERING,
                [f"{summary} ({named}); the authority service is answering again"],
                None,
            )
        return STATE_AUTHORITY_UNAVAILABLE, [f"{summary} ({named})"], action
    return STATE_DEGRADED_UNVERIFIED, [f"{summary} ({named or 'unclassified'})"], action


def effective_admission(facts: dict, state: str) -> str:
    """The admission strength this host has RIGHT NOW, never the declared one."""
    contract = facts["contract"]
    if state in (STATE_UNINSTALLED, STATE_INSTALLING):
        return "NONE"
    if not contract["mechanical_admission"]:
        return str(contract["admission_enforcement"])
    if state == STATE_HEALTHY_VERIFIED:
        return "MECHANICAL"
    mode = ((facts.get("authority") or {}).get("mode")) or taxonomy.DEFAULT_MODE
    if state == STATE_INSTALLED_UNVERIFIED:
        return "MECHANICAL_UNOBSERVED"
    return "DEGRADED_UNVERIFIED" if mode == taxonomy.MODE_DEGRADED else "BLOCKING_STRICT"


def effective_response(facts: dict, state: str) -> str:
    contract = facts["contract"]
    declared = str(contract["response_enforcement"])
    if state in (STATE_UNINSTALLED, STATE_INSTALLING):
        return "NONE"
    if declared == "MECHANICAL" and (
        facts["hook"]["status"] != "current" or state == STATE_BROKEN
    ):
        # A hook that is not current, or whose runtime cannot run, enforces
        # nothing however the host is declared.
        return "INACTIVE"
    return declared


def _source_facts() -> dict:
    """This runtime's own standing: is it a canonical source, an installed
    runtime of one host, or neither -- and can its source be proven?"""
    from .runtime_bootstrap import (
        CanonicalSourceUnproven,
        canonical_source_root,
        read_provenance,
        surface_fingerprint,
    )

    here = source_root()
    marker = read_provenance(here)
    facts: dict = {
        "home": str(here),
        "kind": "installed-runtime" if marker is not None else "source-checkout",
        "adapter": (marker or {}).get("adapter_id") if isinstance(marker, dict) else None,
        "canonical": None,
        "generation": None,
        "proven": False,
        "detail": None,
        "version": None,
    }
    try:
        facts["version"] = (here / "VERSION").read_text(encoding="utf-8-sig").strip()
    except OSError:
        facts["version"] = None
    try:
        canonical = canonical_source_root(here)
    except CanonicalSourceUnproven as exc:
        facts["detail"] = str(exc)
        return facts
    facts["canonical"] = str(canonical)
    facts["generation"] = surface_fingerprint(canonical)
    facts["proven"] = facts["generation"] is not None
    if not facts["proven"]:
        facts["detail"] = "the canonical source cannot prove its shipped surface"
    return facts


def machine_runtime_view(canonical: Path | None) -> dict:
    """The machine runtime as the doctor reports it (T-1647): whether an
    account that cannot read this install has a runtime of its own, and whether
    that runtime is this generation. Informational: it never makes a host
    BROKEN and never changes the doctor's own verdict."""
    from . import machine_runtime

    try:
        status = machine_runtime.status(canonical=canonical)
    except (OSError, RuntimeError, ValueError) as exc:
        return {"code": machine_runtime.CODE_BROKEN, "reasons": [str(exc)[:200]]}
    registration = status.get("registration") or {}
    return {
        "code": status.get("code"),
        "root": status.get("root"),
        "saipen_runtime_ready": bool(status.get("saipen_runtime_ready")),
        "generation": status.get("generation"),
        "current": status.get("current"),
        "saipen_version": registration.get("saipen_version"),
        "state_schema": registration.get("state_schema"),
        "launcher": (status.get("launcher") or {}).get("windows"),
        "python_bundled": (status.get("python") or {}).get("bundled"),
        "source": status.get("source"),
        "reasons": list(status.get("reasons") or [])[:3],
        "action": status.get("action"),
    }


def refresh_machine_runtime(canonical: Path | None) -> dict | None:
    """The repair step for the machine runtime, or None when there is none.

    A machine runtime that exists FOLLOWS the source it was projected from, so
    an upgrade of that source never leaves the accounts that depend on it on
    the old generation. One that was never installed is not created here --
    installing it is a decision -- and one projected from another source is
    left alone: a second checkout, or a test tree, does not own it.
    """
    from . import machine_runtime

    if canonical is None or not machine_runtime.follows(canonical):
        return None
    before = machine_runtime.status(canonical=canonical)
    if before.get("code") == machine_runtime.CODE_READY:
        return None
    report = machine_runtime.install(canonical)
    return {
        "step": "machine:install",
        "ok": bool(report.get("ok")),
        "code": report.get("code"),
        "detail": "; ".join(str(item) for item in (report.get("reasons") or [])[:3])
        or str(report.get("detail") or ""),
    }


def launcher_engine(canonical: Path | None) -> Path:
    """The engine the PATH launcher runs: the canonical source's, the same one
    every installed host and the activation block refer to (T-1678)."""
    return (canonical or source_root()) / "tools" / "saipen.py"


def path_launcher_view(canonical: Path | None, home: Path | None) -> dict:
    """The per-user PATH launcher as the doctor reports it (T-1678).
    Informational, like the machine runtime: a missing one degrades the entry
    transport and never makes a host BROKEN."""
    from . import path_launcher

    try:
        report = path_launcher.status(launcher_engine(canonical), home)
    except (OSError, ValueError) as exc:
        return {"code": path_launcher.CODE_FOREIGN, "reasons": [str(exc)[:200]], "action": None}
    return {
        key: report.get(key)
        for key in ("code", "directory", "files", "reasons", "action", "shadowed_by")
        if report.get(key) is not None
    }


def refresh_path_launcher(canonical: Path | None, home: Path | None) -> dict | None:
    """The repair step for the PATH launcher, or None when there is none: it
    writes only a launcher that is missing, ours and stale, or a hand copy
    that already proves the engine. A foreign `saipen` and a PATH that names
    no declared directory are reported by the doctor and left alone."""
    from . import path_launcher

    if canonical is None:
        return None
    engine = launcher_engine(canonical)
    if path_launcher.status(engine, home)["code"] not in path_launcher.REPAIRABLE:
        return None
    report = path_launcher.install(engine, home)
    return {
        "step": "launcher:install",
        "ok": bool(report.get("ok")),
        "code": report.get("status") or report.get("code"),
        "detail": str(report.get("directory") or "")
        + "".join(f"; {item}" for item in (report.get("reasons") or [])[:2]),
    }


def doctor(*, home: Path | None = None, only: str | None = None,
           profile: Path | None = None) -> dict:
    """The read-only state of every registered host. Writes and starts nothing.

    `ok` is False only when an installed host is BROKEN or the source this
    runtime depends on cannot be proven: stale, degraded and unverified hosts
    are working hosts with an action, not a failed doctor.
    """
    from .runtime_surface import identity_session

    with identity_session():
        source = _source_facts()
        canonical = Path(source["canonical"]) if source["canonical"] else None
        authority = authority_facts(home)
        registry = load_registry(canonical or source_root())
        from .claude_profiles import adapter_for, directory, discover

        base = Path(home) if home is not None else Path.home()
        if profile is not None and only != "claude":
            raise ValueError("--profile requires --host claude")
        adapters = []
        for entry in registry.get("adapters", []):
            if entry.get("id") == "claude":
                profiles = ([directory(base, profile)] if profile is not None
                            else discover(base, entry))
                adapters.extend(adapter_for(entry, base, selected) for selected in profiles)
            else:
                adapters.append(entry)
        by_runtime: dict[str, list[str]] = {}
        for adapter in adapters:
            plan = adapter.get("install") if isinstance(adapter.get("install"), dict) else {}
            target = _expand(plan.get("skill"))
            if target is not None and adapter.get("id"):
                key = os.path.normcase(str(target))
                by_runtime.setdefault(key, []).append(str(adapter["id"]))
        hosts: list[dict] = []
        for adapter in adapters:
            host_id = str(adapter.get("id") or "")
            if not host_id or (only and host_id != only):
                continue
            plan = adapter.get("install") if isinstance(adapter.get("install"), dict) else {}
            target = _expand(plan.get("skill"))
            sharing = tuple(by_runtime.get(os.path.normcase(str(target)), ())) if target else ()
            facts = observe(
                adapter,
                home=home,
                canonical=canonical,
                expected=source["generation"],
                authority=authority,
                sharing=sharing,
            )
            state, reasons, action = derive_state(facts)
            if (action == taxonomy.REPAIR and adapter.get("profile")
                    and not _same_file(adapter["profile"], base / ".claude")):
                action = f'saipen host repair --host claude --profile "{adapter["profile"]}"'
            hosts.append(
                {
                    "id": host_id,
                    "profile": adapter.get("profile"),
                    "name": facts["name"],
                    "state": state,
                    "reasons": reasons,
                    "action": action,
                    "installed": facts["runtime"]["installed"] or facts["hook"]["installed"],
                    "host_present": facts["host_present"],
                    "runtime": (
                        "absent"
                        if not facts["runtime"]["installed"]
                        else "current" if facts["runtime"]["current"] else "stale"
                    ),
                    "hook": facts["hook"]["status"],
                    "instruction": facts["instruction"],
                    "admission": effective_admission(facts, state),
                    "response_enforcement": effective_response(facts, state),
                    "last_health": facts["health"],
                    "recoverable": state in REPAIRABLE
                    or state in (STATE_AUTHORITY_UNAVAILABLE, STATE_DEGRADED_UNVERIFIED),
                    "contract": facts["contract"],
                    "contract_gaps": contract_gaps(facts["contract"]),
                    "facts": {
                        "runtime": facts["runtime"],
                        "hook": facts["hook"],
                        "host_home": facts["host_home"],
                    },
                }
            )
    broken = [item["id"] for item in hosts if item["state"] == STATE_BROKEN]
    actionable = [item["id"] for item in hosts if item["action"]]
    problems: list[dict] = []
    if not source["proven"]:
        problems.append(
            taxonomy.problem(
                "source", "CANONICAL_RUNTIME_SOURCE_UNPROVEN", str(source["detail"] or "")
            )
        )
    if authority["mode_source"] == "invalid":
        problems.append(
            taxonomy.problem(
                "policy",
                "POLICY_INVALID",
                f"{authority['mode_path']} is unreadable or names no recognized mode",
            )
        )
    return {
        "ok": not broken and source["proven"],
        "code": "HOST_DOCTOR",
        "source": source,
        "policy": {
            "mode": authority["mode"],
            "label": authority["mode_label"],
            "source": authority["mode_source"],
            "path": authority["mode_path"],
        },
        "authority": authority,
        "machine_runtime": machine_runtime_view(canonical),
        "path_launcher": path_launcher_view(canonical, home),
        "hosts": hosts,
        "broken": broken,
        "needs_action": actionable,
        "problems": problems,
        "next_action": (
            taxonomy.REPAIR
            if any(item["state"] in REPAIRABLE and item["host_present"] for item in hosts)
            else next((item["action"] for item in hosts if item["action"]), None)
        ),
    }


# -------------------------------------------------------------------- repair


def _stop_authority() -> dict:
    from . import host_authority_client as client

    report = client.retire_service()
    return {"stopped": bool(report.get("retired")), "detail": str(report.get("detail") or "")}


def _start_authority(runtime_root: Path) -> dict:
    """Start the authority service FROM the installed runtime a hook delegates
    to, so the service and the hook it serves are one generation."""
    entry = Path(runtime_root) / "tools" / "authority_service.py"
    if not entry.is_file():
        return {"ok": False, "detail": f"service entry missing: {entry}"}
    try:
        proc = subprocess.run(
            [sys.executable, str(entry), "start", "--force", "--saipen-root", str(runtime_root),
             "--json"],
            capture_output=True,
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        payload = json.loads((proc.stdout or b"{}").decode("utf-8", errors="replace") or "{}")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}
    return payload if isinstance(payload, dict) else {"ok": False, "detail": "unreadable answer"}


def repair(*, home: Path | None = None, only: str | None = None,
           profile: Path | None = None) -> dict:
    """Bring installed hosts back to the canonical generation. One entry point.

    For every installed host that is BROKEN, STALE_RUNTIME or half-installed it
    runs the ONE canonical installer, host-scoped; the installer stages,
    self-tests and only then activates a hook, so a repair that fails leaves
    the previous generation in place. An authority service left over from
    another generation is retired and the installed one is started. Hosts that
    are not installed are left alone, and no project is read or written.
    """
    from .runtime_bootstrap import CanonicalSourceUnproven, _invoke_installer, canonical_source_root

    from .claude_profiles import write_directory

    selected = write_directory(home, profile)
    if profile is not None and not selected.is_dir():
        raise ValueError(f"Claude profile directory does not exist: {selected}")
    before = doctor(home=home, only=only, profile=profile)
    steps: list[dict] = []
    try:
        canonical = canonical_source_root(source_root())
    except CanonicalSourceUnproven as exc:
        canonical = None
        steps.append(
            {"step": "source", "ok": False, "code": "CANONICAL_RUNTIME_SOURCE_UNPROVEN",
             "detail": str(exc)}
        )
    restart_authority = False
    for item in before["hosts"]:
        if item["id"] == "claude" and not _same_file(item["profile"], selected):
            continue
        explicit_install = profile is not None and item["state"] == STATE_UNINSTALLED
        if (item["state"] not in REPAIRABLE and not explicit_install) or not item["host_present"]:
            continue
        if canonical is None:
            steps.append({"step": f"install:{item['id']}", "ok": False,
                          "code": "CANONICAL_RUNTIME_SOURCE_UNPROVEN",
                          "detail": "no proven source to install from"})
            continue
        if item["id"] == "claude":
            proc = _invoke_installer(canonical, item["id"], profile=selected)
        else:
            proc = _invoke_installer(canonical, item["id"])
        rc = proc.returncode if proc is not None else None
        tail = "\n".join(((proc.stdout or "") if proc is not None else "").splitlines()[-6:])
        steps.append(
            {
                "step": f"install:{item['id']}",
                "ok": rc == 0,
                "code": "INSTALLED" if rc == 0 else "BOOTSTRAP_INSTALL_FAILED",
                "installer_rc": rc,
                "detail": tail[-600:],
            }
        )
        if item["contract"]["separated_authority"]:
            restart_authority = True
    authority = before["authority"]
    if authority.get("running") and authority.get("generation_current") is False:
        restart_authority = True
    mechanical = [
        item for item in before["hosts"]
        if item["contract"]["separated_authority"] and item["host_present"]
    ]
    if restart_authority and authority.get("running"):
        steps.append({"step": "authority:stop", "ok": True, **_stop_authority()})
    if only is None:
        machine_step = refresh_machine_runtime(canonical)
        if machine_step is not None:
            steps.append(machine_step)
        launcher_step = refresh_path_launcher(canonical, home)
        if launcher_step is not None:
            steps.append(launcher_step)
    after = doctor(home=home, only=only, profile=profile)
    for item in after["hosts"]:
        if not item["contract"]["separated_authority"] or item["state"] in (
            STATE_UNINSTALLED, STATE_BROKEN, STATE_INSTALLING
        ):
            continue
        if after["authority"].get("running"):
            break
        root = item["facts"]["hook"].get("delegated_root") or item["facts"]["runtime"].get("path")
        if not root:
            continue
        started = _start_authority(Path(root))
        steps.append(
            {
                "step": "authority:start",
                "ok": bool(started.get("ok")),
                "code": "AUTHORITY_STARTED" if started.get("ok") else "AUTHORITY_UNREACHABLE",
                "detail": str(started.get("detail") or started.get("state") or ""),
            }
        )
        after = doctor(home=home, only=only, profile=profile)
        break
    remaining = [
        {"id": item["id"], "state": item["state"], "action": item["action"],
         "reasons": item["reasons"]}
        for item in after["hosts"]
        if (item["state"] in REPAIRABLE
            or (profile is not None and item["state"] == STATE_UNINSTALLED))
        and item["host_present"]
        and (item["id"] != "claude" or _same_file(item["profile"], selected))
    ]
    failed = [step for step in steps if not step.get("ok")]
    return {
        **after,
        "ok": not remaining and not failed and after["ok"],
        "code": "HOST_REPAIRED" if not remaining and not failed else "REPAIR_INCOMPLETE",
        "steps": steps,
        "remaining": remaining,
        "mechanical_hosts": [item["id"] for item in mechanical],
    }


def mode(value: str | None, *, home: Path | None = None) -> dict:
    """Show the admission policy, or set it: `strict`, `degraded` (alias
    `degraded_allowed`), or `default` to remove the operator's choice."""
    from . import host_authority_client as client

    if value is None:
        policy = client.policy(home)
        return {
            "ok": True,
            "code": "HOST_MODE",
            "mode": policy["mode"],
            "label": taxonomy.MODE_LABELS[policy["mode"]],
            "source": policy["source"],
            "path": policy["path"],
            "default": taxonomy.DEFAULT_MODE,
        }
    if str(value).strip().lower() == "default":
        return client.clear_authority_mode(home)
    return client.set_authority_mode(value, home)


# -------------------------------------------------------------------- render


def _cell(text: object, width: int) -> str:
    value = str(text if text not in (None, "") else "-")
    return value[: width - 1].ljust(width)


def render(report: dict) -> str:
    """The compact view a person reads. One line per host; the next action is
    printed only where there is one."""
    source = report.get("source") or {}
    policy = report.get("policy") or {}
    authority = report.get("authority") or {}
    lines = []
    standing = "proven" if source.get("proven") else "UNPROVEN"
    lines.append(
        f"SAIPEN source  {standing}  {source.get('kind')}  {source.get('version') or '?'}  "
        f"{source.get('canonical') or source.get('home')}"
    )
    lines.append(
        f"policy         {policy.get('label')} ({policy.get('source')})"
    )
    if authority.get("running"):
        freshness = (
            "current generation"
            if authority.get("generation_current")
            else "ANOTHER GENERATION (restart: saipen host repair)"
        )
        pid = authority.get("pid") or "?"
        lines.append(f"authority      running pid {pid}  {freshness}")
    else:
        lines.append("authority      idle (started by the first prompt that needs it)")
    machine = report.get("machine_runtime") or {}
    if machine.get("code"):
        # Other accounts on this machine run SAIPEN through it, or cannot.
        standing = str(machine["code"]).replace("MACHINE_RUNTIME_", "")
        tail = machine.get("root") if machine.get("saipen_runtime_ready") else machine.get("action")
        lines.append(f"machine        {standing}  {tail or '-'}")
    launcher = report.get("path_launcher") or {}
    if launcher.get("code"):
        # `saipen` typed in a shell, the first entry transport (T-1678).
        standing = str(launcher["code"]).replace("PATH_LAUNCHER_", "")
        tail = launcher.get("action") or launcher.get("directory")
        lines.append(f"path launcher  {standing}  {tail or '-'}")
    lines.append("")
    lines.append(
        _cell("host", 18) + _cell("state", 23) + _cell("runtime", 9) + _cell("hook", 15)
        + _cell("admission", 22) + "next action"
    )
    for item in report.get("hosts") or []:
        if not item.get("host_present") and not item.get("installed"):
            continue
        lines.append(
            _cell(item["id"], 18)
            + _cell(item["state"], 23)
            + _cell(item["runtime"], 9)
            + _cell(item["hook"], 15)
            + _cell(item["admission"], 22)
            + str(item.get("action") or "-")
        )
        if item.get("profile"):
            lines.append("    profile: " + str(item["profile"]))
        if item.get("action") or item["state"] == STATE_BROKEN:
            for reason in item.get("reasons") or []:
                lines.append("    " + str(reason)[:150])
    absent = [
        item["id"] for item in report.get("hosts") or []
        if not item.get("host_present") and not item.get("installed")
    ]
    if absent:
        lines.append("")
        lines.append("not on this machine: " + ", ".join(absent))
    for step in report.get("steps") or []:
        mark = "ok" if step.get("ok") else "FAILED"
        lines.append(f"repair {step.get('step')}: {mark} {step.get('code') or ''}".rstrip())
    for item in report.get("problems") or []:
        lines.append(f"problem [{item.get('code')}] {str(item.get('reason') or '')[:160]}")
    lines.append("")
    if report.get("code") in ("HOST_REPAIRED", "REPAIR_INCOMPLETE"):
        lines.append(
            "repair complete: selected installations are on the canonical generation"
            if report.get("ok")
            else "repair incomplete: " + ", ".join(
                f"{item['id']} {item['state']}" for item in report.get("remaining") or []
            )
        )
    elif report.get("next_action"):
        lines.append(f"next: {report['next_action']}")
    else:
        lines.append("nothing to do")
    return "\n".join(lines)


__all__ = [
    "CONTRACT_FIELDS",
    "REPAIRABLE",
    "STATES",
    "STATE_AUTHORITY_UNAVAILABLE",
    "STATE_BROKEN",
    "STATE_DEGRADED_UNVERIFIED",
    "STATE_HEALTHY_VERIFIED",
    "STATE_INSTALLED_UNVERIFIED",
    "STATE_INSTALLING",
    "STATE_RECOVERING",
    "STATE_STALE_RUNTIME",
    "STATE_UNINSTALLED",
    "authority_facts",
    "capability_contract",
    "capability_matrix",
    "contract_gaps",
    "derive_state",
    "doctor",
    "effective_admission",
    "effective_response",
    "health_path",
    "mode",
    "observe",
    "read_health",
    "render",
    "repair",
    "source_root",
]
