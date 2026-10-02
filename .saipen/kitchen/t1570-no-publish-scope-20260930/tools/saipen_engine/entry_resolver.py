"""Deterministic SAIPEN entry resolution: which transport runs a command (T-1501).

The field failure this exists for (SRC-114): a cold or scheduled host read
BOOT.md, STYLE.md and EXECUTION.md, then could not run a single SAIPEN command.
`python -m saipen` answered "No module named saipen", `where saipen` found
nothing, and the model was left improvising interpreter paths. The logical
command (`status --json`) was known; the physical transport was not.

This module answers only the transport question. `host_bootstrap` already
owns project binding, the controlled home candidates, host admission and the
dead-pointer diagnosis; this layer composes it and adds the three facts it
never decided:

  * which launcher is CANONICAL -- a `saipen` found on PATH or in a home's
    `bin/` is trusted only when its bytes name the canonical engine and an
    interpreter that exists; a same-name file from another install is
    reported as a provenance mismatch and never used;
  * which transport to use, in order: PATH_LAUNCHER, DIRECT_LAUNCHER,
    DIRECT_ENGINE (the interpreter executing this resolver plus the canonical
    `tools/saipen.py`);
  * whether the requested command may MUTATE on this host. Discovery is not
    admission: an unregistered host keeps its transport for read-only
    commands and is refused every mutating one.

Read-only. It never installs, never writes, never scans a disk and never
guesses a path: every candidate comes from `host_bootstrap`'s controlled list.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

from . import host_bootstrap

PATH_LAUNCHER = "PATH_LAUNCHER"
DIRECT_LAUNCHER = "DIRECT_LAUNCHER"
DIRECT_ENGINE = "DIRECT_ENGINE"
RUNTIME_REBOUND = "RUNTIME_REBOUND"
HUMAN_REQUIRED = "HUMAN_REQUIRED"
HOST_UNSUPPORTED = "HOST_UNSUPPORTED"
PROJECT_UNBOUND = "PROJECT_UNBOUND"
RUNTIME_UNAVAILABLE = "RUNTIME_UNAVAILABLE"

TRANSPORTS = (PATH_LAUNCHER, DIRECT_LAUNCHER, DIRECT_ENGINE)
CODES = (
    *TRANSPORTS,
    RUNTIME_REBOUND,
    HUMAN_REQUIRED,
    HOST_UNSUPPORTED,
    PROJECT_UNBOUND,
    RUNTIME_UNAVAILABLE,
)

#: The descriptive entry contract shipped at every home root (clone and
#: flattened install alike). Runtime identity is proven here, never read
#: from that file.
ENTRY_CONTRACT = "SAIPEN_ENTRY.json"

#: The one form `bootstrap/cli_launcher.render_launchers` writes:
#: `"<python>" "<engine>"` (Windows) or `exec "<python>" "<engine>"` (POSIX).
_LAUNCHER_TARGET = re.compile(r'"([^"]+)"\s+"([^"]+)"\s+(?:%\*|"\$@")')


def _same_path(left: str | Path, right: str | Path) -> bool:
    try:
        return os.path.normcase(str(Path(left).resolve())) == os.path.normcase(
            str(Path(right).resolve())
        )
    except (OSError, ValueError):
        return False


def prove_launcher(path: str | Path, engine: str | Path) -> dict:
    """Is ``path`` a launcher for the canonical ``engine``, proven from its bytes?

    A filename proves nothing: any install can drop a `saipen` on PATH. The
    launcher is canonical only when its rendered target is exactly the engine
    the resolver proved and its interpreter exists on this host.
    """
    record = {"path": str(path), "ok": False, "python": None, "engine": None, "why": ""}
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")[:4096]
    except OSError as exc:
        record["why"] = f"launcher unreadable: {type(exc).__name__}"
        return record
    match = _LAUNCHER_TARGET.search(text)
    if match is None:
        record["why"] = "launcher bytes are not the canonical rendered form"
        return record
    python, target = match.group(1), match.group(2)
    record.update(python=python, engine=target)
    if not _same_path(target, engine):
        record["why"] = f"provenance mismatch: launcher runs {target}, canonical engine is {engine}"
        return record
    if not Path(python).is_file():
        record["why"] = f"launcher interpreter does not exist on this host: {python}"
        return record
    record["ok"] = True
    return record


def _runtime_identity(bound: dict) -> dict:
    """What proves the chosen runtime, from its own bytes -- nothing guessed."""
    home = Path(bound["saipen_home"])
    chosen = next(
        (
            row
            for row in bound.get("attempted", [])
            if row.get("ok") and row.get("home") == bound["saipen_home"]
        ),
        {},
    )
    identity = {
        "home": bound["saipen_home"],
        "engine": bound.get("engine"),
        "protocol_dir": bound.get("protocol_dir"),
        "proven_by": chosen.get("source"),
        "proof": "activation contract and engine present in the home's own bytes",
        "version": None,
        "installer_provenance": None,
    }
    with contextlib.suppress(OSError):
        identity["version"] = (home / "VERSION").read_text(encoding="utf-8").strip() or None
    try:
        marker = json.loads((home / ".saipen_runtime.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        marker = None
    if isinstance(marker, dict):
        identity["installer_provenance"] = {
            key: marker.get(key)
            for key in ("adapter_id", "runtime_fingerprint", "installer_generation")
        }
    return identity


def command_effect(command: list[str] | tuple[str, ...] | None) -> str | None:
    """The canonical effect class of a logical command, or None when none given."""
    if not command:
        return None
    from .command_effects import classify_invocation

    return classify_invocation(command[0], list(command[1:]))


def resolve_entry(
    project_root: Path | str | None = None,
    *,
    host: str | None = None,
    env: dict | None = None,
    command: list[str] | tuple[str, ...] | None = None,
    start: Path | str | None = None,
    honor_environment: bool = True,
    engine_root: Path | str | None = None,
) -> dict:
    """Resolve the authorized transport for one logical command on one host.

    Returns a structured record; `argv_prefix + <logical command>` is the exact
    invocation when `ok` is true. Codes never collapse: PROJECT_UNBOUND,
    RUNTIME_UNAVAILABLE and HOST_UNSUPPORTED are distinct failures, and a
    stale persisted binding keeps its transport while naming the convergence
    command the entry runner executes (`RUNTIME_REBOUND` once it has).
    """
    from .command_effects import DIAGNOSTIC

    source_env = dict(os.environ if env is None else env)
    bound = host_bootstrap.resolve_bootstrap(
        project_root,
        host=host,
        start=start,
        env=source_env,
        honor_environment=honor_environment,
        engine_root=engine_root,
    )
    effect = command_effect(command)
    result: dict = {
        "ok": False,
        "code": RUNTIME_UNAVAILABLE,
        "transport": None,
        "argv_prefix": None,
        "exec_prefix": None,
        "command_form": None,
        "project_root": bound.get("project_root"),
        "project_lineage": bound.get("project_lineage"),
        "saipen_home": bound.get("saipen_home"),
        "runtime_identity": None,
        "host_admission": {
            "host": bound.get("host"),
            "known": bool((bound.get("host_record") or {}).get("known")),
            "mutation_admitted": False,
        },
        "requested_command": list(command) if command else None,
        "command_effect": effect,
        "command_allowed": False,
        "binding": bound.get("binding"),
        "degraded": [],
        "diagnostics": [],
        "attempted": bound.get("attempted", []),
        "next_action": None,
        "bootstrap_code": bound.get("code"),
        "module_invocation": "unsupported",
    }
    diagnostics = result["diagnostics"]

    def note(code: str, detail: str) -> None:
        diagnostics.append({"code": code, "detail": detail})

    if bound.get("code") == host_bootstrap.NOT_SAIPEN or (
        bound.get("code") == host_bootstrap.UNAVAILABLE
        and bound.get("boundary") == host_bootstrap.BOUNDARY_PROJECT
    ):
        result["code"] = PROJECT_UNBOUND
        note("project_binding_failure", str(bound.get("detail") or "no SAIPEN project"))
        result["next_action"] = "run from the managed project, or pass --project-root <path>"
        return result
    if not bound.get("runtime_discovered") or not bound.get("engine"):
        result["code"] = RUNTIME_UNAVAILABLE
        note("runtime_unavailable", str(bound.get("detail") or bound.get("remediation") or ""))
        if (bound.get("binding") or {}).get("persisted_home_dead"):
            note("stale_runtime_binding", str(bound["binding"].get("reason") or ""))
        result["next_action"] = bound.get("remediation") or None
        return result

    engine = bound["engine"]
    result["runtime_identity"] = _runtime_identity(bound)

    # PATH first, but a PATH hit is only a candidate until its bytes prove it.
    transport = argv = execute = None
    which = shutil.which("saipen", path=source_env.get("PATH", ""))
    if which:
        proof = prove_launcher(which, engine)
        if proof["ok"]:
            transport, argv = PATH_LAUNCHER, [str(Path(which))]
            execute = [str(Path(proof["python"])), str(Path(engine))]
            result["command_form"] = "saipen"
        else:
            note("provenance_mismatch", f"{which}: {proof['why']}")
    else:
        note("missing_path_launcher", "no `saipen` on PATH; PATH failure alone is not a blocker")
    if transport is None:
        launcher = bound.get("launcher") or {}
        path = launcher.get("windows") if os.name == "nt" else launcher.get("posix")
        if launcher.get("ok") and path:
            proof = prove_launcher(path, engine)
            if proof["ok"]:
                transport, argv = DIRECT_LAUNCHER, [str(Path(path))]
                execute = [str(Path(proof["python"])), str(Path(engine))]
                note("direct_launcher_available", str(path))
            else:
                note("provenance_mismatch", f"{path}: {proof['why']}")
        elif launcher.get("why"):
            note("no_direct_launcher", str(launcher["why"]))
    if transport is None:
        python = sys.executable
        if python and Path(python).is_file():
            transport, argv = DIRECT_ENGINE, [str(Path(python)), str(Path(engine))]
            execute = argv
            note("direct_engine_available", f"{python} {engine}")
        else:
            result["code"] = RUNTIME_UNAVAILABLE
            note("runtime_unavailable", "no launcher proves and no interpreter is executing")
            return result
    result["transport"] = transport
    result["argv_prefix"] = argv
    # What a program should spawn: the launcher's PROVEN target. A `.cmd`
    # launcher hands its arguments to cmd.exe, which re-parses them, so a
    # runner that passed command text through it let `"` plus `&` in one
    # token run an arbitrary command. `argv_prefix` stays the host-facing form.
    result["exec_prefix"] = execute
    if result["command_form"] is None:
        result["command_form"] = " ".join(f'"{part}"' for part in argv)
    if transport != PATH_LAUNCHER:
        result["degraded"].append("no_canonical_path_launcher")

    binding = bound.get("binding") or {}
    if binding.get("persisted_home_dead"):
        result["degraded"].append("stale_runtime_binding")
        note("stale_runtime_binding", str(binding.get("reason") or "persisted saipen_home is dead"))
        result["next_action"] = "saipen rebind-home --auto"

    if bound.get("code") == host_bootstrap.HOST_UNSUPPORTED:
        # Discovery stays visible; admission is refused. A read-only command
        # may still run where the host allows observation.
        result["code"] = HOST_UNSUPPORTED
        note("host_unsupported", str(bound.get("remediation") or ""))
        result["command_allowed"] = effect == DIAGNOSTIC
        result["next_action"] = bound.get("remediation") or None
        return result

    result["host_admission"]["mutation_admitted"] = True
    result["ok"] = True
    result["code"] = transport
    result["command_allowed"] = True
    return result
