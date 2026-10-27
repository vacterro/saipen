"""Read-only provider/account discovery for `saipen launch --list`.

The operator asked (SRC-184) for one place to SEE which provider accounts exist
on this machine, what state each is in, and whether it is launchable -- without
a secret ever being read, and without discovery mutating anything.

This module answers exactly that and nothing more. It is deliberately a
projection over surfaces that already exist rather than a second account
registry:

* the adapter registry (`extensions/adapters/registry.json`) says which hosts
  SAIPEN knows and which of them declare a launch executable;
* `claude_profiles.discover` (T-1635) already finds every Claude profile on the
  machine -- the default, the launch environment and sibling `~/.claude-*`
  directories;
* `host_integration.observe` already answers installed/current/health for a
  host.

So the account rows are built from those three, and the one thing this module
adds is the row shape: alias, provider, account, profile directory, installed,
authenticated, launchability, managed/direct, and plan/limits as UNKNOWN.

WHAT IT NEVER DOES
------------------
* It does not open a credentials file. `authenticated` is answered from the
  PRESENCE of the provider's own auth marker file, never its contents, and the
  reason string names the marker it looked for. A missing marker is
  `unknown`, not `no`: a provider may authenticate through a mechanism this
  read-only probe cannot see, and guessing `no` there would be a lie that
  changes the operator's next action.
* It does not write. There is no `mkdir`, no repair, no import and no settings
  rewrite on any path in this module. SRC-184 requires discovery to be
  read-only unless repair/import/setup was explicitly asked for, and this verb
  has no such request to honour.
* It does not invent an alias. An alias is a short ergonomic spelling of an
  account that really exists; the registry's own account declarations and the
  discovered profile directories are the only sources. Aliases are never
  treated as canonical identity (SRC-184), so the canonical key of a row is
  ``provider`` + the profile directory, and the alias is carried beside it.

MANAGED vs DIRECT
-----------------
SRC-184 fixes the fail-open order MANAGED_AVAILABLE ->
MANAGED_UNAVAILABLE_BUT_DIRECT_SAFE -> DIRECT_UNSAFE. This module reports the
first half honestly and does not claim the rest: `managed` is available only
when SAIPEN has an installed runtime for that host that it can prove, and
`direct` is available only when the provider's own executable is on PATH. The
row states which of those two facts it actually measured.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

#: Provider id -> the directory-name prefix its account profiles use beside the
#: default home. SRC-184's own examples are `~/.claude-account2` and
#: `~/.codex-account2`, so the family is the provider's default directory name.
PROVIDER_DEFAULT_HOME = {
    "claude": ".claude",
    "codex": ".codex",
    "gemini": ".gemini",
    "agents": ".agents",
}

#: Files that mean "this profile carries provider authentication". The probe
#: tests PRESENCE only. These are the markers the installed providers write:
#: Claude keeps `.credentials.json` beside `.claude.json`, Codex keeps
#: `auth.json`, and Gemini keeps `oauth_creds.json` for its CLI login.
AUTH_MARKERS = {
    "claude": (".credentials.json", ".claude.json"),
    "codex": ("auth.json",),
    "gemini": ("oauth_creds.json",),
}

#: The human-facing account label for a profile directory. The default profile
#: is account 1; `-account2` is account 2, `-account3free` is account 3. The
#: number is read from the directory the machine actually has, never assumed.
def account_number(profile: Path, default_home: Path) -> int | None:
    """The account number a profile directory actually carries.

    The machine's own names are the contract. Beside `~/.claude` this host has
    `~/.claude-account2` and `~/.codex-account3free`, so the suffix may be
    `2`, `account2` or `account3free`: the number is the first run of digits
    after the optional `account` word, and a suffix with no digits at all means
    no account number rather than a guess of 1.
    """
    name = profile.name
    if name == default_home.name:
        return 1
    prefix = default_home.name + "-"
    if not name.startswith(prefix):
        return None
    suffix = name[len(prefix) :]
    if suffix.startswith("account"):
        suffix = suffix[len("account") :]
    digits = ""
    for char in suffix:
        if not char.isdigit():
            break
        digits += char
    return int(digits) if digits else None


def account_alias(provider: str, number: int | None) -> str | None:
    """The SRC-184 short spelling: cl2, cx3, ag1.

    An alias exists only when a number does, because an alias is a spelling of
    an account that the machine really carries. It is never canonical identity.
    """
    prefix = {"claude": "cl", "codex": "cx", "antigravity": "ag", "gemini": "gm"}.get(provider)
    if prefix is None or number is None:
        return None
    return f"{prefix}{number}"


def _authentication(profile: Path, provider: str) -> dict:
    """Marker-presence only. No file is opened, so no secret is read."""
    for marker in AUTH_MARKERS.get(provider, ()):
        if (profile / marker).exists():
            return {"state": "marker-present", "marker": marker}
    return {"state": "unknown", "marker": None}


def _profiles(base: Path, default_name: str) -> list[Path]:
    """The default profile plus every sibling account profile on this machine.

    One directory level, no recursion, no settings read. A profile is listed
    only when it IS a directory: a file called `.claude-account2` is not an
    account.
    """
    found: list[Path] = []
    default = base / default_name
    if default.is_dir():
        found.append(default)
    prefix = default_name + "-"
    try:
        for path in sorted(base.iterdir()):
            if path.is_dir() and path.name.startswith(prefix):
                found.append(path)
    except OSError:
        pass
    return found


def _registry() -> list[dict]:
    path = Path(__file__).resolve().parents[2] / "extensions" / "adapters" / "registry.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    adapters = data.get("adapters") if isinstance(data, dict) else None
    return [item for item in adapters or [] if isinstance(item, dict)]


def _managed(adapter: dict) -> dict:
    """Is a SAIPEN-installed runtime present for this host?

    Read from the registry's declared install plan alone. Proving that runtime
    CURRENT is `host doctor`'s job and is deliberately not repeated here: an
    account list that silently performed a freshness audit would be slow and
    would blur two different questions.
    """
    install = adapter.get("install") if isinstance(adapter.get("install"), dict) else {}
    skill = install.get("skill")
    if not skill:
        return {"state": "unavailable", "reason": "the adapter declares no installed runtime"}
    expanded = Path(os.path.expandvars(os.path.expanduser(str(skill))))
    if not expanded.is_dir():
        return {"state": "unavailable", "reason": "the declared runtime is not installed"}
    return {"state": "available", "path": str(expanded)}


def _direct(adapter: dict) -> dict:
    """Can the provider's own executable be started from PATH?"""
    executable = adapter.get("launch_executable")
    if not executable:
        return {"state": "unavailable", "reason": "the adapter declares no launch executable"}
    found = shutil.which(str(executable))
    if found is None:
        return {"state": "unavailable", "reason": f"{executable} is not on PATH"}
    return {"state": "available", "executable": found}


def _launchability(managed: dict, direct: dict) -> str:
    """SRC-184's fail-open order, answered only as far as it was measured.

    MANAGED_AVAILABLE is only claimed when a managed runtime exists. Otherwise a
    startable direct route is MANAGED_UNAVAILABLE_BUT_DIRECT_SAFE. With neither
    proven the answer is DIRECT_UNSAFE, which is a statement about what this
    read-only probe could prove, not a claim that the account is broken.
    """
    if managed["state"] == "available":
        return "MANAGED_AVAILABLE"
    if direct["state"] == "available":
        return "MANAGED_UNAVAILABLE_BUT_DIRECT_SAFE"
    return "DIRECT_UNSAFE"


def _row(adapter: dict, profile: Path, base: Path, default_home: Path) -> dict:
    provider = str(adapter.get("id") or "")
    number = account_number(profile, default_home)
    managed = _managed(adapter)
    direct = _direct(adapter)
    authentication = _authentication(profile, provider)
    return {
        # The canonical key: a provider and a real directory. The alias below
        # is a convenience spelling and is never used as identity (SRC-184).
        "provider": provider,
        "profile": str(profile),
        "alias": account_alias(provider, number),
        "account": number,
        "installed": profile.is_dir(),
        "authenticated": authentication["state"],
        "authentication_marker": authentication["marker"],
        "launchable": managed["state"] == "available" or direct["state"] == "available",
        "launchability": _launchability(managed, direct),
        "managed": managed,
        "direct": direct,
        # SRC-184: best-effort plan and limits, and UNKNOWN is a launchable
        # state. These probes are not implemented yet and are never guessed.
        "identity": "unknown",
        "plan": "unknown",
        "limits": "unknown",
        "launch_executable": adapter.get("launch_executable"),
    }


def discover_accounts(home: Path | None = None) -> dict:
    """Every provider account this machine carries, as read-only rows.

    `home` is the directory the account profiles live under. It defaults to the
    real home; a caller passes a scratch directory to keep a fixture away from
    the operator's own accounts.
    """
    base = Path(home) if home is not None else Path.home()
    registry = {str(item.get("id") or ""): item for item in _registry()}
    rows: list[dict] = []

    for provider, default_name in sorted(PROVIDER_DEFAULT_HOME.items()):
        adapter = registry.get(provider)
        if adapter is None:
            continue
        default_home = base / default_name
        profiles = _profiles(base, default_name)
        if not profiles:
            # A provider with no profile directory at all is still one honest
            # row: "not installed here" is information, and omitting it would
            # make a missing provider look like an unasked question.
            rows.append(
                {
                    "provider": provider,
                    "profile": None,
                    "alias": None,
                    "account": None,
                    "installed": False,
                    "authenticated": "unknown",
                    "authentication_marker": None,
                    "launchable": _direct(adapter)["state"] == "available",
                    "launchability": _launchability(_managed(adapter), _direct(adapter)),
                    "managed": _managed(adapter),
                    "direct": _direct(adapter),
                    "identity": "unknown",
                    "plan": "unknown",
                    "limits": "unknown",
                    "launch_executable": adapter.get("launch_executable"),
                }
            )
            continue
        for profile in profiles:
            rows.append(_row(adapter, profile, base, default_home))

    for provider in sorted(registry):
        if provider in PROVIDER_DEFAULT_HOME:
            continue
        adapter = registry[provider]
        install = adapter.get("install") if isinstance(adapter.get("install"), dict) else {}
        host_home = install.get("home")
        if not host_home:
            continue
        declared = str(host_home)
        if home is not None:
            # An explicit home scopes the WHOLE answer, not only the account
            # families. A declared `~/...` home is resolved against it, and a
            # declared machine-global home (`$ZAICODE_HOME/...`) is skipped:
            # reporting the operator's real directory while a caller asked
            # about a scratch tree would make the argument a half-promise.
            if not declared.startswith("~/"):
                continue
            expanded = base / declared[2:]
        else:
            expanded = Path(os.path.expandvars(os.path.expanduser(declared)))
        if not expanded.is_dir():
            continue
        managed = _managed(adapter)
        direct = _direct(adapter)
        rows.append(
            {
                "provider": provider,
                "profile": str(expanded),
                "alias": None,
                "account": None,
                "installed": True,
                "authenticated": "unknown",
                "authentication_marker": None,
                "launchable": managed["state"] == "available" or direct["state"] == "available",
                "launchability": _launchability(managed, direct),
                "managed": managed,
                "direct": direct,
                "identity": "unknown",
                "plan": "unknown",
                "limits": "unknown",
                "launch_executable": adapter.get("launch_executable"),
            }
        )

    return {
        "ok": True,
        "code": "LAUNCH_ACCOUNT_LIST",
        "home": str(base),
        "secrets_read": False,
        "mutation": "none",
        "accounts": rows,
    }
