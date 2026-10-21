"""Optional explicit host-launch envelopes for SAIPEN adapters.

An adapter can consume ``SAIPEN_AGENT`` but that environment value does not
authenticate who started its host. This module owns the optional boundary that
creates an explicit provenance override: an
explicit SAIPEN seat, a resolved project root, its portable lineage when
present, and the supported host process are joined once before the host starts.

No session identifier enters this path. Generic launches bypass this helper;
when they carry no explicit actor, Core's single protocol snapshot owns
canonical ``STATE.agent`` inheritance and every safety check.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

from . import host_authority_client, host_taxonomy
from .paths import ENV_AGENT, ENV_PROJECT_LINEAGE, ENV_PROJECT_ROOT, project_lineage_identity


def _registry_adapters() -> list[dict]:
    """The adapter registry entries, or [] when the registry cannot be read."""
    path = Path(__file__).resolve().parents[2] / "extensions" / "adapters" / "registry.json"
    try:
        registry = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    adapters = registry.get("adapters") if isinstance(registry, dict) else None
    return [item for item in adapters or [] if isinstance(item, dict)]


def registry_launch_hosts() -> dict[str, str]:
    """Registry host id -> the executable a launch starts.

    T-1624. The launchable hosts are whatever the adapter registry DECLARES
    (`launch_executable`), read here and listed nowhere else. The table used to
    be a literal in this file, so a host could be a first-class adapter with a
    prompt-blocking hook and still be answered `unsupported SAIPEN host
    launch` -- the registry and the launcher disagreed about the same host.
    """
    return {
        str(item["id"]): str(item["launch_executable"])
        for item in _registry_adapters()
        if item.get("id") and item.get("launch_executable")
    }


def launch_degrades(host_id: str) -> bool:
    """May this host start when its installed runtime could not be proven?

    STRICT operator policy never permits degradation. Otherwise the registry's
    `degraded_mode` decides: a degrading host starts with a warning, and a host
    whose tool gate fails closed keeps its refusal.
    """
    if host_authority_client.authority_mode() == host_taxonomy.MODE_STRICT:
        return False
    for item in _registry_adapters():
        if str(item.get("id")) == host_id:
            return item.get("degraded_mode") == "DEGRADED_ALLOWED_DEFAULT"
    return False


SUPPORTED_HOSTS = registry_launch_hosts()
_SEAT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}$")

#: T-1343. An interlock, not a feature: set to ``1`` it refuses to create a host
#: process, naming the executable that would have been started.
#:
#: A test harness cannot prove by inspection that every path into this function
#: is stubbed. The T-1327 launch fixture believed it had replaced `prelaunch`
#: and had replaced a DIFFERENT module object of the same file, so the real
#: prelaunch ran, `subprocess.run` was reached and the operator's real OpenCode
#: host started -- with its own MCP children -- and the suite hung until the
#: process tree was killed by hand. A timeout would have been a slower way to
#: find that out; this fails BEFORE the process exists.
#:
#: It is read from the PROCESS environment on purpose. The launch environment
#: this module builds is fixture-controlled and gets scrubbed; the process
#: environment belongs to whoever started the interpreter, so a fixture cannot
#: drop the interlock by accident. A run that means to start a real host
#: (`tools/test_opencode_bound_launch_smoke.py`) clears the variable in the
#: child environment it builds, which makes the intent reviewable.
ENV_FORBID_HOST_SPAWN = "SAIPEN_FORBID_HOST_SPAWN"

#: A host identity is never a SAIPEN seat. It names the process being launched,
#: not an acting actor, so a launch that injects it as seat authority would make
#: `SAIPEN_AGENT` contradict canonical ownership. Both the registry key and the
#: executable it maps to are host metadata (BOOT.md step 2), and host metadata is
#: diagnostic context, never an actor.
_HOST_IDENTITIES = frozenset(
    name.lower() for name in (*SUPPORTED_HOSTS, *SUPPORTED_HOSTS.values())
)


class HostLaunchRefusal(ValueError):
    """The requested launch cannot establish an explicit bounded envelope."""


def build_launch_environment(
    project_root: Path | str,
    seat: str,
    *,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build one bounded launch environment from an explicit SAIPEN seat.

    ``seat`` is mandatory input for this optional explicit launcher. The
    resulting environment value is provenance, not authenticated identity.
    """
    actor = seat.strip() if isinstance(seat, str) else ""
    if not _SEAT_RE.fullmatch(actor):
        raise HostLaunchRefusal(
            "launch requires an explicit SAIPEN seat matching "
            "[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}"
        )
    if actor.lower() in _HOST_IDENTITIES:
        raise HostLaunchRefusal(
            f"launch seat {actor!r} is a host identity, not a SAIPEN seat: a host "
            "name is never project-seat authority. Launch the host generically "
            "(no --agent) for canonical attribution, or move ownership with the "
            "explicit handover operation"
        )

    root = Path(project_root).resolve()
    if not root.is_dir() or not (root / ".saipen").is_dir():
        raise HostLaunchRefusal(f"launch project root has no owned .saipen directory: {root}")

    env = dict(os.environ if base_env is None else base_env)
    env[ENV_AGENT] = actor
    env[ENV_PROJECT_ROOT] = str(root)
    lineage = project_lineage_identity(root)
    if lineage:
        env[ENV_PROJECT_LINEAGE] = lineage
    else:
        # Never leak another project's ambient lineage into this launch.
        env.pop(ENV_PROJECT_LINEAGE, None)
    return env


def prelaunch_runtime(host_id: str, *, resync: bool = True) -> dict:
    """Prove the installed generation BEFORE this host process starts.

    T-1327 TARGET C. The supported launch path owns runtime freshness; the
    operator does not. This is the only moment at which the bytes a new process
    will load can honestly be changed, which is why the check lives here and
    not inside a running guard: a loaded plugin is never hot-replaced.
    """
    from .runtime_bootstrap import (
        PRELAUNCH_CURRENT,
        PRELAUNCH_RESYNCED,
        CanonicalSourceUnproven,
        prelaunch,
    )

    try:
        report = prelaunch(host_id, resync=resync)
    except CanonicalSourceUnproven as exc:
        raise HostLaunchRefusal(
            f"installed runtime freshness cannot be proven for {host_id}: {exc}"
        ) from exc
    if not report.get("ok") or report.get("code") not in (PRELAUNCH_CURRENT, PRELAUNCH_RESYNCED):
        raise HostLaunchRefusal(
            f"installed {host_id} runtime is not the canonical generation "
            f"({report.get('code')}: {report.get('detail')}); "
            f"engine_diff={report.get('engine_diff')} "
            f"hook={report.get('hook_problems')} "
            f"launcher={report.get('launcher_problems')} "
            f"provenance={report.get('provenance_problems')}"
        )
    return report


def launch_host(
    host: str,
    project_root: Path | str,
    seat: str,
    host_args: Sequence[str] = (),
    *,
    base_env: Mapping[str, str] | None = None,
    prelaunch: bool = True,
) -> int:
    """Start one supported host with the canonical actor/project envelope.

    The envelope now includes the RUNTIME GENERATION: freshness is proven (and
    resynced when stale) before the process exists, so the started host loads
    the canonical installed generation without any operator injection step.
    """
    host_id = host.strip().lower()
    executable_name = SUPPORTED_HOSTS.get(host_id)
    if executable_name is None:
        raise HostLaunchRefusal(
            f"unsupported SAIPEN host launch {host!r}; supported: "
            + ", ".join(sorted(SUPPORTED_HOSTS))
        )

    env = build_launch_environment(project_root, seat, base_env=base_env)
    if prelaunch:
        try:
            prelaunch_runtime(host_id)
        except HostLaunchRefusal as exc:
            if not launch_degrades(host_id):
                raise HostLaunchRefusal(
                    f"{exc}; operator action: {host_taxonomy.REPAIR}"
                ) from exc
            # The host itself still works and its own hook degrades truthfully:
            # say what could not be proven and start it anyway.
            print(
                f"SAIPEN: starting {host_id} without a proven installed runtime ({exc}). "
                "The session will run degraded until: saipen host repair",
                file=sys.stderr,
            )
    executable = shutil.which(executable_name, path=env.get("PATH"))
    if executable is None:
        raise HostLaunchRefusal(f"supported host executable is unavailable: {executable_name}")

    if os.environ.get(ENV_FORBID_HOST_SPAWN, "").strip() == "1":
        raise HostLaunchRefusal(
            f"{ENV_FORBID_HOST_SPAWN}=1 forbids starting a real host process; "
            f"this launch had selected {executable} for host {host_id!r}. "
            "No process was created."
        )

    try:
        completed = subprocess.run(
            [executable, *host_args],
            cwd=str(Path(project_root).resolve()),
            env=env,
            check=False,
        )
    except OSError as exc:
        raise HostLaunchRefusal(f"failed to start {host_id}: {exc}") from exc
    return completed.returncode
