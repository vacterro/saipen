"""Claude configuration directories; observe metadata, never account credentials."""

from __future__ import annotations

import copy
import contextlib
import hashlib
import os
from pathlib import Path

ENVIRONMENT = "CLAUDE_CONFIG_DIR"


def directory(home: Path | None = None, profile: Path | str | None = None) -> Path:
    base = Path(home) if home is not None else Path.home()
    selected = profile if profile is not None else os.environ.get(ENVIRONMENT)
    if selected:
        return Path(os.path.expandvars(os.path.expanduser(str(selected)))).absolute()
    return base / ".claude"


def surface(value: str, home: Path, profile: Path) -> Path:
    if value == "~/.claude" or value.startswith("~/.claude/"):
        return profile / value.removeprefix("~/.claude").lstrip("/")
    if value.startswith("~/"):
        return home / value[2:]
    return Path(os.path.expandvars(os.path.expanduser(value)))


def adapter_for(adapter: dict, home: Path, profile: Path) -> dict:
    """Project the existing registry's surfaces into one named profile."""
    result = copy.deepcopy(adapter)
    for key in ("hook_install_surface", "hook_config_surface"):
        if result.get(key):
            result[key] = str(surface(result[key], home, profile))
    for key in ("home", "skill", "instruction", "hook"):
        if result.get("install", {}).get(key):
            result["install"][key] = str(surface(result["install"][key], home, profile))
    for key in ("instruction_surfaces", "skill_surfaces"):
        if key in result:
            result[key] = [str(surface(value, home, profile)) for value in result[key]]
    result["profile"] = str(profile)
    return result


def discover(home: Path, adapter: dict) -> list[Path]:
    """Default, launch environment, declared launchers and sibling profiles.

    The directory probe is one level only. No settings or credentials are read.
    """
    candidates = [home / ".claude"]
    if os.environ.get(ENVIRONMENT):
        candidates.append(directory(home))
    for launcher in adapter.get("launchers", []):
        if isinstance(launcher, dict) and isinstance(launcher.get("env"), dict):
            selected = launcher["env"].get(ENVIRONMENT)
            if isinstance(selected, str) and selected:
                candidates.append(surface(selected, home, home / ".claude"))
    with contextlib.suppress(OSError):
        candidates.extend(sorted(path for path in home.glob(".claude-*") if path.is_dir()))
    unique = {}
    for path in candidates:
        unique.setdefault(os.path.normcase(os.path.abspath(path)), path)
    return list(unique.values())


def health_file(home: Path, profile: Path) -> Path:
    key = os.path.normcase(os.path.abspath(profile))
    default = os.path.normcase(os.path.abspath(home / ".claude"))
    suffix = "" if key == default else "-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return home / ".saipen" / "health" / f"claude{suffix}.json"


def hook_for_process(pid: int, home: Path | None = None) -> str | None:
    """The hook of the OS-observed host's profile; unknown never means default."""
    from .host_authority_process import environment_value

    observed, selected = environment_value(pid, ENVIRONMENT)
    if not observed:
        return None
    if selected and not Path(selected).is_absolute():
        return None
    base = Path(home) if home is not None else Path.home()
    # Empty explicitly selects the default, regardless of the service's environment.
    profile = directory(base, selected) if selected else base / ".claude"
    return str(profile / "hooks" / "saipen-guard.py")
