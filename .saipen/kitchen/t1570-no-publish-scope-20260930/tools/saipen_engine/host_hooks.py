"""Host hook commands that run their own payload as shell commands (T-1475).

Field incident, T-1446 soak 2026-09-22 and again 2026-09-23/24: empty files
named `BLOCKED`, `` M` ``, `str`, `5` appeared at the root of saipen_home, and
the only SAIPEN process running could not have written them. The writer was
host configuration, not SAIPEN (E-8945): `~/.claude/settings.json` hooks of the
form

    cmd.exe /d /v:off /s /c '""%USERPROFILE%\\.claude\\hooks\\x.cmd""'

Claude Code runs hook commands through Git Bash on Windows. MSYS rewrites the
single-slash switches `/d` and `/c` into drive paths, so cmd.exe never receives
`/c`, starts INTERACTIVE, and executes the hook's JSON payload from stdin as
command lines in the session cwd. The payload of a Read hook is the text that
was read: a line such as `goal_tickets N-> M` redirects into a file `` M` ``,
and `x" & <command> & rem` runs a command. The hook itself never runs.

SAIPEN cannot change host configuration, and a root stray FAILs
`[root-file-set]` with no cause attached. This module is the read-only
detector that names the cause: it parses the host settings files and reports
every hook command that starts cmd.exe with single-slash switches. Measured
remediation: invoke the hook script or its executable directly; the `//c`
spelling does not survive MSYS quoting of the `""path""` argument.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

CODE = "HOST_HOOK_RUNS_PAYLOAD"

#: cmd.exe (bare, quoted, or by path) followed by switches, one of which is a
#: single-slash /c or /k. `//c` is already MSYS-escaped and is not matched.
_CMD_SWITCH_RE = re.compile(
    r"""^\s*["']?(?:[^\s"']*[\\/])?cmd(?:\.exe)?["']?"""
    r"""(?:\s+/[A-Za-z](?::[A-Za-z]+)?)*\s+/[cCkK](?=\s|$)""",
    re.IGNORECASE,
)

REMEDIATION = (
    "invoke the hook script or its executable directly (for example the "
    "`.cmd` path, or `<tool>.exe hook-augment`) instead of `cmd.exe /c`; under "
    "Git Bash a single-slash switch becomes a path, cmd.exe starts interactive "
    "and runs the hook payload -- text the agent read -- as commands"
)


def settings_paths(project_root: Path | str, home: Path | str | None = None) -> list[Path]:
    """The host settings files whose hooks run inside this project."""
    root = Path(project_root)
    base = Path(home) if home is not None else Path.home()
    return [
        base / ".claude" / "settings.json",
        root / ".claude" / "settings.json",
        root / ".claude" / "settings.local.json",
    ]


def payload_hooks(settings_text: str) -> list[dict]:
    """Every hook command in one settings document that runs its payload."""
    try:
        data = json.loads(settings_text)
    except ValueError:
        return []
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(hooks, dict):
        return []
    found: list[dict] = []
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            entries = group.get("hooks")
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                command = entry.get("command")
                if isinstance(command, str) and _CMD_SWITCH_RE.match(command):
                    found.append(
                        {
                            "event": str(event),
                            "matcher": str(group.get("matcher") or "*"),
                            "command": command,
                        }
                    )
    return found


def hazards(
    project_root: Path | str,
    home: Path | str | None = None,
    platform: str | None = None,
) -> list[dict]:
    """Read-only: host hooks that would run their payload in this project.

    Only Windows is affected (the MSYS path rewrite); elsewhere the answer is
    empty. An unreadable or malformed settings file is skipped, never raised.
    """
    if (platform or sys.platform) != "win32":
        return []
    found: list[dict] = []
    for path in settings_paths(project_root, home):
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        for hook in payload_hooks(text):
            found.append({"code": CODE, "settings": str(path), **hook})
    return found


def stray_hint(
    project_root: Path | str,
    home: Path | str | None = None,
    platform: str | None = None,
) -> str:
    """One sentence naming the likely writer of a root stray, or ''."""
    found = hazards(project_root, home, platform)
    if not found:
        return ""
    named = "; ".join(
        f"{hook['settings']} {hook['event']}/{hook['matcher']}" for hook in found[:4]
    )
    more = f" and {len(found) - 4} more" if len(found) > 4 else ""
    return f"Likely writer ({CODE}): host hook(s) {named}{more} -- {REMEDIATION}"
