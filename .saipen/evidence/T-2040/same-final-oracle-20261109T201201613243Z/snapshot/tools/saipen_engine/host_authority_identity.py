"""Proof that an authority request came from the host's own hook invocation.

Defect class: the first separated authority (T-1623) admitted any process that
had the host application somewhere above it. Every command a model runs through
the host's shell tool is such a process, so the one caller the boundary exists
to refuse -- model-executed code asking for its own admission -- passed. A copy
of an ordinary interpreter renamed to the host's image name passed as well.

"Descendant of the host" is therefore not the claim. The claim proven here is
narrower and is the only one the host alone can make true:

    host application            a verified image (name, and its code signer
        |                       where the platform can report one)
        +-- hook shell(s)       each started to run EXACTLY the hook command
              |                 and nothing else
              +-- hook          the installed hook artifact, shipped bytes,
                    |           declaring the same host the request names
                    +-- engine  optionally, the engine the hook started

A shell tool wraps a model's command in its own bootstrap, so its command line
is never exactly the hook command; a hook command re-run from inside such a
shell sits under that extra shell and fails the same test. A renamed
interpreter carries its own publisher's signature, not the host's.

Limits, stated because a boundary that hides them is worth less: this proves
the SHAPE of the invocation from what the operating system reports about live
processes. It is not a defense against code running inside the host process, a
same-user process that rewrites the installed hook, or one that forges its
parent with a debugging API. Those are outside what any same-user local scheme
can prove, and nothing here claims otherwise.

Pure logic: the caller supplies the observed chain and the two observations
that need the platform (`signer_of`, `artifact_current`), so every branch is
testable without spawning a process.
"""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass, field
from typing import Callable, Sequence

#: Refusal reasons. Detail codes of one wire refusal, never policy by themselves.
REASON_IDENTITY_UNAVAILABLE = "IDENTITY_UNAVAILABLE"
REASON_NOT_HOST_DESCENDANT = "NOT_HOST_DESCENDANT"
REASON_HOOK_NOT_FOUND = "HOOK_NOT_FOUND"
REASON_HOOK_CHAIN_UNRECOGNIZED = "HOOK_CHAIN_UNRECOGNIZED"
REASON_HOOK_HOST_MISMATCH = "HOOK_HOST_MISMATCH"
REASON_HOOK_ARTIFACT_MISMATCH = "HOOK_ARTIFACT_MISMATCH"
REASON_HOST_IMAGE_UNVERIFIED = "HOST_IMAGE_UNVERIFIED"
REASON_PARENT_REUSED = "PARENT_REUSED"

DEFAULT_SHELLS = (
    "bash.exe",
    "bash",
    "sh.exe",
    "sh",
    "dash",
    "zsh",
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "pwsh",
)
#: The interpreter program every installed hook command starts with:
#:
#:     <python> -c <HOOK_BOOTSTRAP> <hook artifact> --host <id> --saipen-root <root>
#:
#: Defect class: lockout by absence. An interpreter asked to run a script that
#: is not there exits with status 2, and a host reads status 2 from a hook as
#: "block this event" -- measured on Claude Code 2.1.291, every prompt was
#: refused with the interpreter's "can't open file" as the only text. A hook
#: file can be absent while its command is still loaded: the host snapshots
#: hook commands at start, so a session that predates an uninstall, a manual
#: delete or a quarantine keeps running a command whose script is gone. The
#: bootstrap runs the hook when it exists and does nothing when it does not,
#: so the command cannot fail closed by its own absence.
#:
#: No quote character on purpose: the string travels through POSIX shells and
#: through cmd.exe, and each quotes it whole.
HOOK_BOOTSTRAP = (
    "import os,runpy,sys;a=sys.argv[1];sys.argv=sys.argv[1:];"
    "os.path.isfile(a) and runpy.run_path(a,run_name=__name__)"
)
#: Engine entries the hook is allowed to have started, relative to its root.
DEFAULT_ENGINE_ENTRIES = ("tools/saipen.py",)
#: An interpreter launcher may re-execute itself once (venv shims, `py`).
_MAX_REEXEC = 2
_MAX_ENGINE_HOPS = 2


@dataclass(frozen=True)
class IdentityPolicy:
    """What counts as the host, its hook and the shells that may run the hook."""

    host: str
    host_images: tuple[str, ...]
    #: Installed hook artifact paths (any spelling; compared normalized).
    hook_artifacts: tuple[str, ...]
    #: Code-signer names the host image must carry. Empty: not required.
    host_signers: tuple[str, ...] = ()
    shells: tuple[str, ...] = DEFAULT_SHELLS
    engine_entries: tuple[str, ...] = DEFAULT_ENGINE_ENTRIES
    max_shells: int = 4
    #: Host-application-owned intermediaries between the hook and the host image
    #: that are not shells (e.g. an Electron host's CLI child). They are named
    #: explicitly per host; a generic intermediary is never accepted.
    bridge_images: tuple[str, ...] = ()
    max_bridges: int = 2
    profile_hook: str | None = None


@dataclass(frozen=True)
class Proof:
    ok: bool
    reason: str | None = None
    detail: str = ""
    host_pid: int | None = None
    host_image: str | None = None
    host_signer: str | None = None
    hook_pid: int | None = None
    hook_root: str | None = None
    shells: int = 0
    chain: list[dict] = field(default_factory=list)
    profile: str | None = None

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "detail": self.detail,
            "host_pid": self.host_pid,
            "host_image": self.host_image,
            "host_signer": self.host_signer,
            "hook_pid": self.hook_pid,
            "hook_root": self.hook_root,
            "shells": self.shells,
            "chain": self.chain,
            "profile": self.profile,
        }


def norm_path(value: object) -> str:
    """One spelling for a path-like token: forward slashes, case-folded where
    the platform is, and an MSYS drive (`/c/x`) read as the drive it names."""
    text = str(value or "").strip().strip("\"'").replace("\\", "/")
    if len(text) >= 3 and text[0] == "/" and text[2] == "/" and text[1].isalpha():
        text = text[1] + ":" + text[2:]
    while "//" in text[1:]:
        text = text[0] + text[1:].replace("//", "/")
    if len(text) > 3:
        text = text.rstrip("/")
    return text.lower() if os.name == "nt" or (len(text) > 1 and text[1] == ":") else text


def _basename(value: object) -> str:
    return norm_path(value).rsplit("/", 1)[-1]


def _stem(name: str) -> str:
    return name[:-4] if name.endswith(".exe") else name


def _name_matches(image: object, wanted: Sequence[str]) -> bool:
    path = norm_path(image)
    name = path.rsplit("/", 1)[-1]
    for candidate in wanted:
        target = norm_path(candidate)
        if not target:
            continue
        if "/" in target:
            if path == target:
                return True
        elif name == target or _stem(name) == _stem(target):
            return True
    return False


#: A host that updates itself while it runs cannot replace its own image on
#: Windows, so its updater renames the running file: Claude Code leaves
#: `claude.exe.old.<ms>.<pid>` beside the new `claude.exe` (T-1650). The process
#: is still that host. The retired name ends in the pid of the process it
#: belongs to, which is what tells the running host from a file that is merely
#: named like one: the suffix is honoured only when it carries the pid of the
#: process whose image it is.
_RETIRED_IMAGE_RE = re.compile(r"(?P<image>.+)\.old\.(?P<stamp>\d{6,20})\.(?P<pid>\d{1,10})")


def retired_image(image: object, pid: object) -> str | None:
    """The image a self-updated host was started as, or None.

    `image` is the path the platform reports now. The answer is that path with
    the updater's suffix removed, and only when the suffix names `pid`.
    """
    match = _RETIRED_IMAGE_RE.fullmatch(norm_path(image))
    if match is None:
        return None
    try:
        if int(match.group("pid")) != int(str(pid)):
            return None
    except (TypeError, ValueError):
        return None
    return match.group("image")


def _host_matches(fact: object, wanted: Sequence[str]) -> bool:
    """Is this process a registered host application, renamed or not?"""
    image = getattr(fact, "image", None)
    if _name_matches(image, wanted):
        return True
    started_as = retired_image(image, getattr(fact, "pid", None))
    return started_as is not None and _name_matches(started_as, wanted)


def _renamed_host(facts: Sequence, wanted: Sequence[str]) -> str | None:
    """The name of a chain member that is a renamed copy of a host image but is
    not recognised as the host, or None. It changes no verdict: it is what the
    refusal says so the operator knows a restart, not a repair, is the cure."""
    names = {norm_path(item).rsplit("/", 1)[-1] for item in wanted if str(item).strip()}
    for fact in facts:
        name = _basename(getattr(fact, "image", None))
        if any(name.startswith(known + ".") for known in names if known):
            if not _host_matches(fact, wanted):
                return name
    return None


def _not_host(detail: str, facts: Sequence, wanted: Sequence[str]) -> str:
    renamed = _renamed_host(facts, wanted)
    if renamed is None:
        return detail
    return (
        f"{detail}; a renamed copy of the host image is running ({renamed}): the host "
        "application was updated while running -- restart it"
    )


def _same_token(left: str, right: str, *, executable: bool = False) -> bool:
    """Two command tokens name the same thing. Flags compare exactly; anything
    path-like compares by normalized path; an executable given without a
    directory compares by name, because the shell resolved it through PATH."""
    if left == right:
        return True
    a, b = norm_path(left), norm_path(right)
    if a == b:
        return True
    if executable and ("/" not in a or "/" not in b):
        return _stem(a.rsplit("/", 1)[-1]) == _stem(b.rsplit("/", 1)[-1])
    return False


def _same_argv(payload: Sequence[str], argv: Sequence[str]) -> bool:
    if len(payload) != len(argv) or not argv:
        return False
    if not _same_token(payload[0], argv[0], executable=True):
        return False
    return all(_same_token(a, b) for a, b in zip(payload[1:], argv[1:]))


def _payload_tokens(payload: str) -> list[list[str]]:
    """Every way a shell could have split its command string."""
    found: list[list[str]] = []
    for posix in (True, False):
        try:
            tokens = shlex.split(payload, posix=posix)
        except ValueError:
            continue
        if not posix:
            tokens = [token.strip("\"'") for token in tokens]
        if tokens and tokens not in found:
            found.append(tokens)
    return found


def _flag(argv: Sequence[str], name: str) -> str | None:
    for index, token in enumerate(argv):
        if token == name and index + 1 < len(argv):
            return argv[index + 1]
        if token.startswith(name + "="):
            return token.split("=", 1)[1]
    return None


def hook_script(argv: Sequence[str] | None) -> str | None:
    """The script an interpreter command line runs, or None.

    Strict on purpose. Two spellings exist and nothing else is a script: the
    FIRST argument (the engine, and hooks installed before the bootstrap), or
    the argument after `-c` and EXACTLY the installer's `HOOK_BOOTSTRAP`.
    Reading past any other option would let `-X <hook path> other.py` pass an
    option value off as the script being run, and accepting any other `-c`
    program would let arbitrary code name the hook as its "script".
    """
    if not argv or len(argv) < 2:
        return None
    token = argv[1]
    if token == "-c":
        if len(argv) >= 4 and argv[2] == HOOK_BOOTSTRAP and not argv[3].startswith("-"):
            return argv[3]
        return None
    return None if token.startswith("-") else token


_script = hook_script


#: The flag after which a shell's command line carries the command to run.
_COMMAND_FLAGS = ("-c", "/c", "-command", "-encodedcommand")


def _shell_payloads(argv: Sequence[str]) -> list[list[str]]:
    """Every reading of "the command this shell was started to run"."""
    readings: list[list[str]] = []
    if len(argv) >= 3:
        readings.extend(_payload_tokens(argv[-1]))
    for index, token in enumerate(argv[1:], start=1):
        if token.lower() in _COMMAND_FLAGS:
            tail = list(argv[index + 1 :])
            if len(tail) > 1 and tail not in readings:
                readings.append(tail)
            break
    return readings


def _view(fact) -> dict:
    argv = list(getattr(fact, "argv", None) or [])
    return {
        "pid": fact.pid,
        "ppid": fact.ppid,
        "image": fact.image,
        "name": fact.name,
        "argv": [token[:160] for token in argv[:8]],
    }


def prove_hook_invocation(
    chain: Sequence,
    policy: IdentityPolicy,
    *,
    signer_of: Callable[[str], str | None] | None = None,
    artifact_current: Callable[[str], bool] | None = None,
    hook_for_host: Callable[[int], str | None] | None = None,
    report_limit: int = 8,
) -> Proof:
    """Decide whether `chain` (peer first, then each parent) is the host's hook.

    Never raises. A chain this function cannot read to the end is refused with
    the reason that stopped it, and that reason is what the operator is shown.
    """
    facts = list(chain or [])
    view = [_view(fact) for fact in facts[:report_limit]]

    def refuse(reason: str, detail: str, **extra) -> Proof:
        return Proof(ok=False, reason=reason, detail=detail, chain=view, **extra)

    if not facts:
        return refuse(REASON_IDENTITY_UNAVAILABLE, "the platform reported no process identity")

    # A parent that started AFTER its child is not that child's parent: the pid
    # was reused. Everything above the reused link is unrelated.
    for index in range(len(facts) - 1):
        child, parent = facts[index], facts[index + 1]
        child_born = getattr(child, "created", None)
        parent_born = getattr(parent, "created", None)
        if child_born is not None and parent_born is not None and parent_born > child_born:
            facts = facts[: index + 1]
            if not any(_host_matches(item, policy.host_images) for item in facts):
                return refuse(
                    REASON_PARENT_REUSED,
                    f"process {child.pid} names a parent pid that was reused by a newer process",
                )
            break

    artifacts = {norm_path(item) for item in policy.hook_artifacts if str(item).strip()}

    # 1. The hook: the peer itself, or the process that started the peer's engine.
    hook_index = None
    for index, fact in enumerate(facts[: _MAX_ENGINE_HOPS + 1]):
        script = _script(getattr(fact, "argv", None))
        profile_candidate = bool(
            script and policy.profile_hook
            and norm_path(script).endswith("/" + norm_path(policy.profile_hook))
        )
        if script is not None and (norm_path(script) in artifacts or profile_candidate):
            hook_index = index
            break
    if hook_index is None:
        if not any(_host_matches(item, policy.host_images) for item in facts):
            return refuse(
                REASON_NOT_HOST_DESCENDANT,
                _not_host(
                    "the connecting process is not started by a registered host application",
                    facts,
                    policy.host_images,
                ),
            )
        return refuse(
            REASON_HOOK_NOT_FOUND,
            "the connecting process is under the host application but is not the "
            "installed host hook or the engine it started (a shell tool call is not a hook)",
        )
    hook = facts[hook_index]
    hook_argv = list(hook.argv or [])
    hook_root = _flag(hook_argv, "--saipen-root")
    declared_host = _flag(hook_argv, "--host")
    if declared_host != policy.host:
        return refuse(
            REASON_HOOK_HOST_MISMATCH,
            f"the hook declares host {declared_host!r}, the request names {policy.host!r}",
            hook_pid=hook.pid,
        )
    # Below the hook only the engine it started may sit.
    for fact in facts[:hook_index]:
        script = _script(getattr(fact, "argv", None))
        allowed = {
            norm_path(f"{hook_root}/{entry}") for entry in policy.engine_entries if hook_root
        }
        if script is None or norm_path(script) not in allowed:
            return refuse(
                REASON_HOOK_NOT_FOUND,
                "the connecting process was started by the hook but is not its engine",
                hook_pid=hook.pid,
            )

    # 2. Above the hook: an interpreter re-exec of the same command, then shells
    #    that were each started to run exactly this hook command.
    cursor = hook_index + 1
    reexec = 0
    while (
        cursor < len(facts)
        and reexec < _MAX_REEXEC
        and facts[cursor].argv
        and _same_argv(list(facts[cursor].argv), hook_argv)
        and not _name_matches(facts[cursor].image, policy.shells)
    ):
        cursor += 1
        reexec += 1
    shells = 0
    while cursor < len(facts) and _name_matches(facts[cursor].image, policy.shells):
        shell = facts[cursor]
        if not any(
            _same_argv(tokens, hook_argv) for tokens in _shell_payloads(list(shell.argv or []))
        ):
            return refuse(
                REASON_HOOK_CHAIN_UNRECOGNIZED,
                f"shell {shell.pid} above the hook was not started to run exactly the hook "
                "command, so this is not the host's own hook invocation",
                hook_pid=hook.pid,
                hook_root=hook_root,
            )
        shells += 1
        cursor += 1
        if shells > policy.max_shells:
            return refuse(
                REASON_HOOK_CHAIN_UNRECOGNIZED,
                "too many shells between the hook and the host application",
                hook_pid=hook.pid,
                hook_root=hook_root,
            )

    # 2b. Named host-owned intermediaries (not shells) between hook and host.
    bridges = 0
    while cursor < len(facts) and _name_matches(facts[cursor].image, policy.bridge_images):
        cursor += 1
        bridges += 1
        if bridges > policy.max_bridges:
            return refuse(
                REASON_HOOK_CHAIN_UNRECOGNIZED,
                "too many intermediaries between the hook and the host application",
                hook_pid=hook.pid,
                hook_root=hook_root,
            )

    # 3. The host application itself, directly above.
    if cursor >= len(facts) or not _host_matches(facts[cursor], policy.host_images):
        above = facts[cursor].name if cursor < len(facts) else None
        if not any(_host_matches(item, policy.host_images) for item in facts):
            return refuse(
                REASON_NOT_HOST_DESCENDANT,
                _not_host(
                    "the hook was not started by a registered host application",
                    facts,
                    policy.host_images,
                ),
                hook_pid=hook.pid,
                hook_root=hook_root,
            )
        return refuse(
            REASON_HOOK_CHAIN_UNRECOGNIZED,
            f"the hook was started through {above!r}, not directly by the host application",
            hook_pid=hook.pid,
            hook_root=hook_root,
        )
    host = facts[cursor]
    if policy.profile_hook:
        try:
            selected_hook = hook_for_host(host.pid) if hook_for_host else None
        except Exception:
            selected_hook = None
        if selected_hook is None:
            return refuse(REASON_IDENTITY_UNAVAILABLE,
                          "the host's configuration profile could not be observed",
                          host_pid=host.pid, hook_pid=hook.pid, hook_root=hook_root)
        if norm_path(_script(hook_argv)) != norm_path(selected_hook):
            return refuse(REASON_HOOK_ARTIFACT_MISMATCH,
                          "the hook belongs to another configuration profile than the host",
                          host_pid=host.pid, hook_pid=hook.pid, hook_root=hook_root)
    signer = None
    if policy.host_signers:
        try:
            signer = signer_of(str(host.image)) if signer_of and host.image else None
        except Exception:
            signer = None
        if signer not in policy.host_signers:
            return refuse(
                REASON_HOST_IMAGE_UNVERIFIED,
                f"host image {host.name!r} is not signed by a registered publisher "
                f"(found {signer!r})",
                host_pid=host.pid,
                host_image=host.image,
                hook_pid=hook.pid,
                hook_root=hook_root,
            )

    # 4. The hook's own bytes are the shipped ones.
    script = _script(hook_argv) or ""
    try:
        current = artifact_current(script) if artifact_current else True
    except Exception:
        current = False
    if not current:
        return refuse(
            REASON_HOOK_ARTIFACT_MISMATCH,
            "the installed hook is not the shipped artifact of this SAIPEN generation",
            host_pid=host.pid,
            host_image=host.image,
            hook_pid=hook.pid,
            hook_root=hook_root,
        )
    return Proof(
        ok=True,
        detail="the request came from the host application's own hook invocation",
        host_pid=host.pid,
        host_image=host.image,
        host_signer=signer,
        hook_pid=hook.pid,
        hook_root=hook_root,
        shells=shells,
        chain=view,
        profile=(norm_path(selected_hook).rsplit("/", 2)[0] if policy.profile_hook else None),
    )


__all__ = [
    "DEFAULT_ENGINE_ENTRIES",
    "DEFAULT_SHELLS",
    "HOOK_BOOTSTRAP",
    "REASON_HOOK_ARTIFACT_MISMATCH",
    "REASON_HOOK_CHAIN_UNRECOGNIZED",
    "REASON_HOOK_HOST_MISMATCH",
    "REASON_HOOK_NOT_FOUND",
    "REASON_HOST_IMAGE_UNVERIFIED",
    "REASON_IDENTITY_UNAVAILABLE",
    "REASON_NOT_HOST_DESCENDANT",
    "REASON_PARENT_REUSED",
    "IdentityPolicy",
    "Proof",
    "hook_script",
    "norm_path",
    "prove_hook_invocation",
]
