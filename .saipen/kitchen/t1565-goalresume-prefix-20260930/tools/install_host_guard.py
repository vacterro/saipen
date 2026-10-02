"""Install native Kiro/Gemini/Codex/Claude hooks without touching unrelated user hooks.

Reports artifact/config freshness separately from runtime health. Installation
cannot prove host execution; health and effective enforcement remain UNKNOWN.
Host trust (Codex's hash-bound `/hooks` review) is an external boundary this
installer never marks satisfied.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import tomllib

from saipen_engine.runtime_surface import (
    identity_session,
    normalize_content as content_bytes,
    runtime_generation_identity,  # noqa: F401  (re-exported for parity tests)
    same_runtime_generation,
)

ROOT = Path(__file__).resolve().parent.parent
NAME = "saipen-guard"


def codex_hook_preflight(home: Path, *, hooks_json_present: bool) -> dict:
    """Report independent host-proof boundaries without changing user hooks.

    A trust record in config.toml is not a current host execution verdict. The
    installer can identify dual hook representations, but only a live host run
    can prove trust, checker reachability, and a refused effect.
    """
    config_toml = home / ".codex" / "config.toml"
    inline_events: list[str] = []
    config_error = None
    if config_toml.is_file():
        try:
            parsed = tomllib.loads(config_toml.read_text(encoding="utf-8-sig"))
            hooks = parsed.get("hooks", {})
            if not isinstance(hooks, dict):
                raise ValueError("hooks must be a TOML table")
            inline_events = sorted(key for key in hooks if key != "state")
        except (OSError, UnicodeError, ValueError) as exc:
            config_error = str(exc)
    if config_error is not None:
        representation = "HOOK_CONFIG_UNREADABLE"
    elif hooks_json_present and inline_events:
        representation = "DUAL_HOOK_REPRESENTATION"
    else:
        representation = "SINGLE_HOOK_REPRESENTATION"
    return {
        "hook_trust": "HOOK_TRUST_UNPROVEN",
        "hook_representation": representation,
        "inline_events": inline_events,
        "config_error": config_error,
        "host_execution": "UNPROVEN",
        "checker_reachability": "UNPROVEN",
        "refused_effect": "UNPROVEN",
    }


def saipen_root_of(invocation: str) -> str | None:
    """The SAIPEN root a configured hook command names, or None.

    `--saipen-root` is the LAST argument `command` emits, so everything after
    the flag is the path -- quoted by `list2cmdline`/`shlex.join` exactly the
    way they quoted it on the way in.
    """
    if not invocation:
        return None
    marker = "--saipen-root"
    index = invocation.rfind(marker)
    if index < 0:
        return None
    tail = invocation[index + len(marker) :].strip()
    if not tail:
        return None
    if tail[0] == '"' and tail.endswith('"') and len(tail) > 1:
        return tail[1:-1]
    if tail[0] == "'" and tail.endswith("'") and len(tail) > 1:
        return tail[1:-1]
    return tail


def root_resolves(root: str | None, expected: Path | str | None = None) -> bool:
    """Does the named SAIPEN root prove the SAME accepted generation?

    T-1342: `BOOT.md exists` is NOT identity. Any directory can hold a
    `BOOT.md`, and the hook delegates enforcement to `<root>/tools/saipen.py`,
    so a root that merely "looks like SAIPEN" can run an engine from another
    release while the wrapper bytes look current. A different PATH is fine; a
    different GENERATION is not. The named root is accepted only when its
    bounded generation fingerprint matches the distribution/source authority
    (`ROOT`, or `expected` when supplied). Missing, unreadable and
    BOOT.md-only roots are STALE/UNKNOWN, never CURRENT.
    """
    if not root or not root.strip():
        return False
    try:
        return same_runtime_generation(ROOT if expected is None else expected, Path(root.strip()))
    except OSError:
        return False


def _named_root_is_current(command: str) -> bool:
    """Must the hook command's `--saipen-root` name the ACCEPTED generation?

    T-1342: an exact command-string match only proves the wrapper bytes were
    written once. The hook executes `<root>/tools/saipen.py guard`, so a
    byte-current entry that delegates to a root carrying a stale engine is
    still not current. This check is unconditional; the T-1338 soft compare
    exists for a different root SPELLING, never for a different generation.
    """
    root = saipen_root_of(command)
    return root is not None and root_resolves(root)


def _same_invocation(configured: str, expected: str) -> bool:
    """Same hook command, with the SAIPEN root treated as the variable it is.

    The supported scheduled injector installs from its published snapshot while
    `autoinject.hook_status` checks against the repository clone. Comparing the
    embedded root as contract makes those two spellings permanently unequal, so
    a correct, enforcing hook reported stale on every run and the freshness
    surface became noise. Everything EXCEPT the root must still match exactly.
    """
    root = saipen_root_of(configured)
    if root is None or not root_resolves(root):
        return False
    marker = "--saipen-root"
    return (
        configured[: configured.rfind(marker)] == expected[: expected.rfind(marker)]
        if marker in expected
        else False
    )


def command(host: str, artifact: Path, root: Path) -> str:
    argv = [sys.executable, str(artifact), "--host", host, "--saipen-root", str(root)]
    if host == "claude":
        # T-1558: Claude Code runs hook commands through Git Bash on Windows, so
        # the command is a POSIX one. A backslash path inside a POSIX shell loses
        # its separators, and `cmd.exe /c` becomes a path (T-1475): forward
        # slashes and shlex quoting are the spelling both shells resolve.
        return shlex.join(arg.replace("\\", "/") if os.sep == "\\" else arg for arg in argv)
    if os.name == "nt":
        # Hook commands are interpreted by cmd.exe on this platform. Refuse
        # expansion/control characters rather than invent shell escaping.
        if any(any(c in arg for c in "%!&|<>^\r\n") for arg in argv):
            raise ValueError("hook command path contains Windows shell control characters")
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


def command_pair(host: str, artifact: Path, root: Path) -> tuple[str, str]:
    """The same hook invocation as (POSIX spelling, cmd.exe spelling).

    Codex's handler schema carries `command` plus an optional Windows-only
    `commandWindows` override, so one install writes both spellings.
    """
    argv = [sys.executable, str(artifact), "--host", host, "--saipen-root", str(root)]
    if os.name == "nt":
        if any(any(c in arg for c in "%!&|<>^\r\n") for arg in argv):
            raise ValueError("hook command path contains Windows shell control characters")
    return shlex.join(argv), subprocess.list2cmdline(argv)


def _codex_entry_is_ours(hook: dict, artifact_name: str) -> bool:
    """Is this Codex handler entry ours?

    The Codex hook-handler schema has no name field to own by, so ownership is
    invocation identity: a command that names the SAIPEN guard artifact and
    carries `--saipen-root`.
    """
    for key in ("command", "commandWindows"):
        value = hook.get(key)
        if (
            isinstance(value, str)
            and "--saipen-root" in value
            and artifact_name in value
        ):
            return True
    return False


def _same_codex_entry(owned: dict, expected: dict) -> bool:
    """Same hook definition, with the SAIPEN root treated as the variable.

    Everything except the two invocation spellings must match exactly; each
    spelling must match its own counterpart modulo `--saipen-root` (T-1338),
    and the root it names must prove the accepted generation (T-1342).
    """
    if {k: v for k, v in owned.items() if k not in ("command", "commandWindows")} != {
        k: v for k, v in expected.items() if k not in ("command", "commandWindows")
    }:
        return False
    return _same_invocation(
        str(owned.get("command", "")), str(expected.get("command", ""))
    ) and _same_invocation(
        str(owned.get("commandWindows", "")), str(expected.get("commandWindows", ""))
    )


#: A host hook that carries its own copy of the voice or language rule. STYLE.md
#: is the one owner (`saipen response style`); a second, hand-written copy is
#: what contradicted the `reply_language` pin on every prompt.
_STYLE_RULE_TEXT = re.compile(r"(?i)caveman|STYLE\.md|reply_language|own language|style check")


def _own_event_hooks(
    hooks: dict, event: str, expected: dict, artifact_name: str, matcher: str | None = None
) -> list[dict]:
    """Replace this installer's entries for one event with `expected`, in place.

    Every unrelated group and hook survives untouched. The first owned entry is
    replaced where it stood, so a re-install is byte-stable; when there is none,
    a new group (carrying `matcher` when one is required) is appended. Returns
    the owned entries that were found, each marked `_matcher_ok` for whether its
    group carries the matcher the event needs.
    """
    groups = hooks.setdefault(event, [])
    if not isinstance(groups, list):
        raise ValueError(f"{event} must be an array")
    owned: list[dict] = []
    inserted = False
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
            raise ValueError(f"malformed {event} hook group")
        remaining = []
        for hook in group["hooks"]:
            if not isinstance(hook, dict):
                raise ValueError("malformed hook entry")
            if _codex_entry_is_ours(hook, artifact_name):
                owned.append({**hook, "_matcher_ok": group.get("matcher") == matcher})
                if not inserted:
                    remaining.append(expected)
                    inserted = True
            else:
                remaining.append(hook)
        group["hooks"] = remaining
    if not inserted:
        groups.append({"matcher": matcher, "hooks": [expected]} if matcher else {"hooks": [expected]})
    return owned


def _same_claude_entry(owned: dict, expected: dict) -> bool:
    """Same hook definition with the SAIPEN root treated as the variable (T-1338),
    and the generation it names as contract (T-1342)."""
    if not owned.get("_matcher_ok", True):
        return False
    if {k: v for k, v in owned.items() if k not in ("command", "_matcher_ok")} != {
        k: v for k, v in expected.items() if k != "command"
    }:
        return False
    return _same_invocation(str(owned.get("command", "")), str(expected.get("command", "")))


def _style_hook_conflicts(hooks: dict, artifact_name: str) -> list[dict]:
    """Operator-owned prompt hooks that carry their own voice or language rule.

    Reported, never removed: the hook is the operator's. The conflict is still a
    finding, because two sources of the language rule is the defect.
    """
    found: list[dict] = []
    for event in ("UserPromptSubmit", "SessionStart"):
        groups = hooks.get(event)
        for group in groups if isinstance(groups, list) else []:
            entries = group.get("hooks") if isinstance(group, dict) else None
            for hook in entries if isinstance(entries, list) else []:
                if (
                    isinstance(hook, dict)
                    and not _codex_entry_is_ours(hook, artifact_name)
                    and _STYLE_RULE_TEXT.search(str(hook.get("command", "")))
                ):
                    found.append({"event": event, "command": str(hook["command"])[:200]})
    return found


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == data:
        return
    fd, temp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def install(host: str, home: Path, root: Path = ROOT, *, check: bool = False) -> dict:
    """Install (or with `check`, only observe) one native guard hook.

    The result names the SAIPEN root the configured hook delegates to
    (`saipen_root`) and whether that root proves the accepted generation
    (`root_current`): the wrapper executes `<saipen_root>/tools/saipen.py`, so a
    current wrapper over a stale delegated engine is not a current hook.
    """
    with identity_session():
        return _install(host, home, root, check=check)


def _install(host: str, home: Path, root: Path, *, check: bool) -> dict:
    registry = json.loads((root / "extensions/adapters/registry.json").read_text())
    entry = next(item for item in registry["adapters"] if item["id"] == host)
    artifact = home / entry["hook_install_surface"].removeprefix("~/")
    config = home / entry["hook_config_surface"].removeprefix("~/")
    invocation = command(host, artifact, root)
    original = config.read_bytes() if config.exists() else None
    data = json.loads(original.decode("utf-8-sig")) if original is not None else {}
    if not isinstance(data, dict):
        raise ValueError("hook config must be a JSON object")
    if host == "gemini":
        hooks = data.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise ValueError("hooks must be an object")
        groups = hooks.setdefault("BeforeTool", [])
        if not isinstance(groups, list):
            raise ValueError("BeforeTool must be an array")
        expected = {
            "matcher": ".*",
            "hooks": [
                {
                    "name": NAME,
                    "type": "command",
                    "command": invocation,
                    "timeout": 30000,
                }
            ],
        }
        preserved = []
        owned = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise ValueError("malformed BeforeTool hook group")
            remaining = []
            for hook in group["hooks"]:
                if not isinstance(hook, dict):
                    raise ValueError("malformed hook entry")
                if hook.get("name") == NAME:
                    owned.append((group.get("matcher"), hook))
                else:
                    remaining.append(hook)
            if remaining or not group["hooks"]:
                preserved.append({**group, "hooks": remaining})
        named = str(owned[0][1].get("command", "")) if len(owned) == 1 else ""
        named_root = saipen_root_of(named)
        configured = (
            len(owned) == 1
            and owned[0][0] == ".*"
            and (
                (
                    owned == [(".*", expected["hooks"][0])]
                    and _named_root_is_current(named)
                )
                or (
                    {k: v for k, v in owned[0][1].items() if k != "command"}
                    == {k: v for k, v in expected["hooks"][0].items() if k != "command"}
                    and _same_invocation(named, expected["hooks"][0]["command"])
                )
            )
        )
        hooks["BeforeTool"] = [*preserved, expected]
    elif host == "codex":
        # T-1551: Codex hooks.json is a SHARED host file. Preserve every
        # unrelated event and hook entry; own exactly the Stop command hooks
        # this installer produced, replacing ours in place so a re-install is
        # byte-stable (Codex records hook trust against the hook definition's
        # hash, so churn here would silently un-trust a correct install).
        posix_invocation, windows_invocation = command_pair(host, artifact, root)
        expected = {
            "type": "command",
            "command": posix_invocation,
            "commandWindows": windows_invocation,
            "timeout": 60,
            "statusMessage": "SAIPEN EXEC-RESPONSE-01 final-response gate",
        }
        hooks = data.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise ValueError("hooks must be an object")
        groups = hooks.setdefault("Stop", [])
        if not isinstance(groups, list):
            raise ValueError("Stop must be an array")
        owned = []
        inserted = False
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise ValueError("malformed Stop hook group")
            remaining = []
            for hook in group["hooks"]:
                if not isinstance(hook, dict):
                    raise ValueError("malformed hook entry")
                if _codex_entry_is_ours(hook, artifact.name):
                    owned.append(hook)
                    if not inserted:
                        remaining.append(expected)
                        inserted = True
                else:
                    remaining.append(hook)
            group["hooks"] = remaining
        named = str(owned[0].get("command", "")) if len(owned) == 1 else ""
        named_root = saipen_root_of(named) if named else None
        configured = len(owned) == 1 and _same_codex_entry(owned[0], expected)
        if not inserted:
            groups.append({"hooks": [expected]})
    elif host == "claude":
        # T-1558: settings.json is the operator's SHARED file (theme, statusLine,
        # every other hook). Own exactly the Stop and UserPromptSubmit entries
        # this installer produced; both events run the one artifact, which
        # dispatches on `hook_event_name`.
        # (event, matcher, timeout seconds). Every event the admission transport
        # needs: SessionStart and PostModelSwitch invalidate, UserPromptSubmit is
        # the pre-generation boundary, PostToolUse (Bash only) admits the same
        # turn a real `saipen init` binds a project, Stop is the post-render gate.
        # PreToolUse is deliberately absent: bootstrap tool activity is never gated.
        events = (
            ("SessionStart", None, 60),
            ("UserPromptSubmit", None, 60),
            ("PostToolUse", "Bash", 60),
            ("PostModelSwitch", None, 30),
            ("Stop", None, 60),
        )
        hooks = data.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise ValueError("hooks must be an object")
        configured = True
        named_root = None
        for event, matcher, timeout in events:
            expected_hook = {"type": "command", "command": invocation, "timeout": timeout}
            owned = _own_event_hooks(hooks, event, expected_hook, artifact.name, matcher)
            configured = (
                configured and len(owned) == 1 and _same_claude_entry(owned[0], expected_hook)
            )
            if event == "Stop" and len(owned) == 1:
                named_root = saipen_root_of(str(owned[0].get("command", "")))
        style_conflicts = _style_hook_conflicts(hooks, artifact.name)
    else:
        expected = {
            "version": "v1",
            "hooks": [
                {
                    "name": NAME,
                    "trigger": "PreToolUse",
                    "matcher": ".*",
                    "action": {"type": "command", "command": invocation},
                    "timeout": 30,
                }
            ],
        }
        if data and (
            data.get("version") != "v1" or any(h.get("name") != NAME for h in data.get("hooks", []))
        ):
            raise ValueError("reserved SAIPEN hook file contains unrelated configuration")
        configured = False
        named_root = None
        if isinstance(data, dict) and len(data.get("hooks") or []) == 1:
            # Same rule as the Gemini branch: the SAIPEN root is a variable,
            # everything else is contract (T-1338) -- and the generation it
            # names is contract too (T-1342).
            entry_now = data["hooks"][0]
            entry_want = expected["hooks"][0]
            action_now = entry_now.get("action") or {}
            action_want = entry_want["action"]
            named_command = str(action_now.get("command", ""))
            named_root = saipen_root_of(named_command)
            configured = (
                data == expected and _named_root_is_current(named_command)
            ) or (
                data.get("version") == expected["version"]
                and {k: v for k, v in entry_now.items() if k != "action"}
                == {k: v for k, v in entry_want.items() if k != "action"}
                and {k: v for k, v in action_now.items() if k != "command"}
                == {k: v for k, v in action_want.items() if k != "command"}
                and _same_invocation(named_command, action_want["command"])
            )
        data = expected
    shipped = (root / entry["hook_artifact"]).read_bytes()
    installed = artifact.is_file()
    root_current = named_root is not None and root_resolves(named_root)
    current = (
        installed
        and content_bytes(artifact.read_bytes()) == content_bytes(shipped)
        and configured
    )
    if not check:
        # Preserve original settings once by content identity; never overwrite
        # a user's earlier backup. Malformed config is refused before writes.
        encoded = (json.dumps(data, indent=2) + "\n").encode("utf-8")
        if original is not None and original != encoded:
            import hashlib

            backup = config.with_name(
                config.name + "." + hashlib.sha256(original).hexdigest()[:16] + ".bak"
            )
            if not backup.exists():
                atomic_write(backup, original)
        atomic_write(artifact, shipped)
        atomic_write(config, encoded)
        installed = current = configured = True
        named_root = str(root)
        root_current = root_resolves(named_root)
    result = {
        "host": host,
        "capability": True,
        "installed": installed,
        "current": current,
        "configured": configured,
        "saipen_root": named_root,
        "root_current": root_current,
        "health": None,
        "effective": "UNKNOWN" if current else "ENFORCEMENT_GAP",
        "artifact": str(artifact),
        "config": str(config),
    }
    if host == "codex":
        result["proof_preflight"] = codex_hook_preflight(
            home, hooks_json_present=config.is_file()
        )
    if host == "claude":
        result["style_hook_conflicts"] = style_conflicts
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", choices=("kiro", "gemini", "codex", "claude"))
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.host, args.home, check=args.check), indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"effective": "UNKNOWN", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
