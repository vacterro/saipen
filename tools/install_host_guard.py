"""Install native Kiro/Gemini/Codex/Claude hooks without touching unrelated user hooks.

Reports artifact/config freshness separately from runtime health. Installation
cannot prove host execution; health and effective enforcement remain UNKNOWN.
Host trust (Codex's hash-bound `/hooks` review) is an external boundary this
installer never marks satisfied.

T-1624, three rules for a hook that can block a prompt:

* STAGE, VERIFY, ACTIVATE. The new artifact is written beside the active one,
  must start, must stay silent outside a project and must let a prompt through
  when its engine is missing, and only then replaces the active artifact. A
  hook that fails any of that is never activated; the previous generation keeps
  running and is kept afterwards as the rollback generation.
* THE HOOK RUNS THE INSTALLED RUNTIME. Where the registry says so
  (`hook_delegate: installed_runtime`), the command names the host's own
  installed runtime copy, not the source checkout it was installed from: a
  checkout is edited, moved and half-written, and every prompt of every session
  was executing whatever it held at that moment.
* THE INTERPRETER IS A VARIABLE. A hook command is current when everything
  after its interpreter matches and that interpreter exists. Comparing the
  interpreter to the one running the CHECK made a correct hook read stale to
  any checker started with another Python, and the prompt boundary refused on
  it.
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

from saipen_engine.host_authority_identity import HOOK_BOOTSTRAP, hook_script
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


def _argv_of(invocation: str) -> list[list[str]]:
    """Every way a host shell could split a hook command (POSIX, then cmd)."""
    found: list[list[str]] = []
    for posix in (True, False):
        try:
            argv = shlex.split(invocation, posix=posix)
        except ValueError:
            continue
        if not posix:
            argv = [token.strip("\"'") for token in argv]
        if argv and argv not in found:
            found.append(argv)
    return found


def _interpreters_of(invocation: str) -> list[str]:
    """The interpreter under EACH way a host shell could split the command.

    A command is written for one shell and `_argv_of` cannot know which. The
    POSIX split of the cmd.exe spelling strips the backslashes of an unquoted
    path, so reading only the first split named an interpreter that exists
    nowhere (T-1634): every Codex, Gemini and Kiro entry then read as "its
    interpreter is gone", and a correct hook checked under another spelling of
    the same Python was stale for ever.
    """
    return [argv[0] for argv in _argv_of(invocation) if argv and argv[0]]


def _interpreter_exists(interpreter: str) -> bool:
    if any(sep in interpreter for sep in ("/", "\\")):
        return Path(interpreter).is_file()
    import shutil

    return shutil.which(interpreter) is not None


def interpreter_of(invocation: str) -> str | None:
    """The interpreter a hook command starts, or None when it names none.

    The reading that exists on this machine; when none does, the one that is
    still a path, so a missing interpreter is named as it was written.
    """
    found = _interpreters_of(invocation)
    for interpreter in found:
        if _interpreter_exists(interpreter):
            return interpreter
    for interpreter in found:
        if any(sep in interpreter for sep in ("/", "\\")):
            return interpreter
    return found[0] if found else None


def interpreter_missing(invocation: str) -> bool:
    """Does this hook command name an interpreter that is not on this machine?

    A hook whose interpreter was uninstalled or upgraded away cannot start at
    all, which the host reports as a hook error on every event. That is a
    broken hook, not a stale one, and it has its own name in the result.
    Missing means missing under every shell's reading of the command.
    """
    found = _interpreters_of(invocation)
    return bool(found) and not any(_interpreter_exists(item) for item in found)


def _same_modulo_interpreter(configured_head: str, expected_head: str) -> bool:
    """Same command head, with the interpreter treated as the variable it is."""
    for left in _argv_of(configured_head):
        for right in _argv_of(expected_head):
            if len(left) == len(right) and len(left) > 1 and left[1:] == right[1:]:
                return True
            if (
                len(left) == len(right)
                and len(left) > 1
                and [os.path.normcase(item).replace("\\", "/") for item in left[1:]]
                == [os.path.normcase(item).replace("\\", "/") for item in right[1:]]
            ):
                return True
    return False


def _same_invocation(configured: str, expected: str) -> bool:
    """Same hook command, with the SAIPEN root and the interpreter treated as
    the variables they are.

    The supported scheduled injector installs from its published snapshot while
    `autoinject.hook_status` checks against the repository clone. Comparing the
    embedded root as contract makes those two spellings permanently unequal, so
    a correct, enforcing hook reported stale on every run and the freshness
    surface became noise. The interpreter is the same kind of variable
    (T-1624): the command names the Python that INSTALLED the hook, and a
    checker running under another one -- `pythonw`, a virtual environment, a
    second installed version -- compared its own path against it and called a
    correct hook stale. Everything else must still match exactly, and an
    interpreter that does not exist is not a match (`interpreter_missing`).
    """
    root = saipen_root_of(configured)
    if root is None or not root_resolves(root):
        return False
    marker = "--saipen-root"
    if marker not in expected:
        return False
    configured_head = configured[: configured.rfind(marker)]
    expected_head = expected[: expected.rfind(marker)]
    if configured_head == expected_head:
        return True
    if interpreter_missing(configured):
        return False
    return _same_modulo_interpreter(configured_head, expected_head)


def hook_argv(host: str, artifact: Path, root: Path) -> list[str]:
    """The one hook invocation every spelling below quotes.

    It starts the artifact through `HOOK_BOOTSTRAP`, never as the interpreter's
    script argument: a command whose script file is gone must do nothing, and
    an interpreter handed a missing script exits 2, which a host reads as a
    hook that blocks. `--saipen-root` stays the LAST argument.
    """
    return [
        sys.executable,
        "-c",
        HOOK_BOOTSTRAP,
        str(artifact),
        "--host",
        host,
        "--saipen-root",
        str(root),
    ]


def command(host: str, artifact: Path, root: Path) -> str:
    argv = hook_argv(host, artifact, root)
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
    argv = hook_argv(host, artifact, root)
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
        if isinstance(value, str) and "--saipen-root" in value and artifact_name in value:
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


def _same_process_entry(owned: dict, expected: dict) -> bool:
    """Same argv process hook, with the SAIPEN root and the interpreter as the
    variables they are (T-1935).

    ZAICODE executes `command` plus `args` with `shell:false`, so its hook is
    the one place the invocation is already split into argv. Comparing the args
    list verbatim made the embedded `--saipen-root` contract: `host doctor`
    inspects a host whose installed runtime copy is the checker, and a hook
    that correctly names the source root then differed from an expectation
    built around that copy and read stale on every run. T-1338 settled that the
    root is a spelling of "where the engine lives"; T-1342 settled that the
    generation it proves is contract. T-1624 settled the same for the
    interpreter, which is the Python that installed the hook.

    So: every other field exact, the root value free but required to prove the
    accepted generation, and a different interpreter accepted only when it
    exists on this machine.
    """
    if {k: v for k, v in owned.items() if k not in ("command", "args")} != {
        k: v for k, v in expected.items() if k not in ("command", "args")
    }:
        return False
    named = str(owned.get("command", ""))
    wanted = str(expected.get("command", ""))
    if named != wanted and interpreter_missing(named):
        return False
    marker = "--saipen-root"
    args_owned = [str(item) for item in (owned.get("args") or [])]
    args_wanted = [str(item) for item in (expected.get("args") or [])]
    if len(args_owned) != len(args_wanted):
        return False
    if marker not in args_owned or marker not in args_wanted:
        return False
    at = args_owned.index(marker)
    if at != args_wanted.index(marker) or at + 1 >= len(args_owned):
        return False
    # Everything except the value AFTER the marker must be identical.
    if args_owned[:at] != args_wanted[:at] or args_owned[at + 2 :] != args_wanted[at + 2 :]:
        return False
    return root_resolves(args_owned[at + 1])


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
        groups.append(
            {"matcher": matcher, "hooks": [expected]} if matcher else {"hooks": [expected]}
        )
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


#: Hook events and their timeouts, in seconds. A prompt-path event must outlast
#: the hook's own engine budget (20 s) so that the HOOK decides what a slow
#: engine means -- a host that kills the hook first decides it silently.
CLAUDE_EVENTS = (
    ("SessionStart", None, 30),
    ("UserPromptSubmit", None, 30),
    ("PostToolUse", "Bash", 30),
    ("PostModelSwitch", None, 30),
    ("PreToolUse", "^AskUserQuestion$", 30),
    ("Stop", None, 60),
)
SELF_TEST_TIMEOUT = 40


def delegated_root(entry: dict, home: Path, source: Path) -> Path:
    """The runtime a host hook executes.

    The source it is installed from, unless the registry declares
    `hook_delegate: installed_runtime` and this host's installed runtime copy
    exists and proves the SAME generation as that source -- then the hook runs
    the installed copy, which nobody edits in place. An installed copy that is
    absent or behind is not delegated to: a hook must never be pointed at bytes
    its installer did not just prove.
    """
    if entry.get("hook_delegate") != "installed_runtime":
        return source
    install_plan = entry.get("install") if isinstance(entry.get("install"), dict) else {}
    skill = install_plan.get("skill")
    if not isinstance(skill, str):
        return source
    candidate = home / skill.removeprefix("~/") if skill.startswith("~/") else Path(skill)
    try:
        if candidate.is_dir() and same_runtime_generation(source, candidate):
            return candidate
    except OSError:
        return source
    return source


def self_test(artifact: Path, host: str) -> dict:
    """Prove a hook artifact is safe to put on the prompt path. Never raises.

    Five runs of the artifact itself, each in a throwaway home so nothing of
    the operator's is read or written:

    1. it starts (`--self-test`);
    2. outside any project it does nothing and exits clean;
    3. inside a project whose runtime is MISSING it lets the prompt through --
       the property whose absence locked the operator out. A hook that would
       block there is refused here, before it can;
    4. a runtime that answers, but with no admission verdict (it refused its
       own command line), is not read as a refusal of the prompt;
    5. a command line of another generation -- an argument it does not know, a
       value that is missing -- is never answered with a non-zero exit status,
       which a host reads as a hook that blocks.
    """
    import tempfile as _tempfile

    def run(arguments: list[str], event: dict | None, cwd: Path) -> tuple[int, str, str]:
        proc = subprocess.run(
            [sys.executable, str(artifact), "--host", host, *arguments],
            input=(json.dumps(event).encode("utf-8") if event is not None else b""),
            capture_output=True,
            timeout=SELF_TEST_TIMEOUT,
            cwd=str(cwd),
            env={
                key: value
                for key, value in os.environ.items()
                if not key.startswith("SAIPEN_")
            },
            check=False,
        )
        return (
            proc.returncode,
            proc.stdout.decode("utf-8", errors="replace").strip(),
            proc.stderr.decode("utf-8", errors="replace").strip(),
        )

    try:
        with _tempfile.TemporaryDirectory(prefix="saipen-hook-selftest-") as scratch:
            base = Path(scratch)
            empty_home = base / "home"
            empty_home.mkdir()
            missing_runtime = base / "no-runtime"
            plain = base / "plain"
            plain.mkdir()
            project = base / "project"
            (project / ".saipen").mkdir(parents=True)
            (project / ".saipen" / "STATE.md").write_text("---\nphase: DONE\n---\n", "utf-8")
            common = ["--saipen-root", str(missing_runtime), "--home", str(empty_home)]

            code, out, err = run([*common, "--self-test"], None, plain)
            if code != 0 or '"ok": true' not in out:
                return {"ok": False, "step": "start", "detail": (err or out)[-300:]}

            code, out, err = run(
                common, {"hook_event_name": "UserPromptSubmit", "cwd": str(plain),
                         "session_id": "self-test"}, plain
            )
            if code != 0 or out:
                return {"ok": False, "step": "outside-project", "detail": (err or out)[-300:]}

            code, out, err = run(
                common, {"hook_event_name": "UserPromptSubmit", "cwd": str(project),
                         "session_id": "self-test"}, project
            )
            try:
                answer = json.loads(out) if out else {}
            except ValueError:
                return {"ok": False, "step": "engine-missing", "detail": out[-300:]}
            if code != 0 or not isinstance(answer, dict) or answer.get("decision") == "block":
                return {
                    "ok": False,
                    "step": "engine-missing",
                    "detail": "the hook blocks a prompt when its runtime is missing: "
                    + (err or out)[-240:],
                }

            prompt = {"hook_event_name": "UserPromptSubmit", "cwd": str(project),
                      "session_id": "self-test"}
            refusing = base / "refusing-runtime"
            (refusing / "tools").mkdir(parents=True)
            (refusing / "tools" / "saipen.py").write_text(
                'print(\'{"ok": false, "code": "VALIDATION_FAILED"}\')\nraise SystemExit(2)\n',
                "utf-8",
            )
            for step, arguments, fault in (
                (
                    "engine-off-schema",
                    ["--saipen-root", str(refusing), "--home", str(empty_home)],
                    "the hook blocks a prompt when its runtime answers with no verdict: ",
                ),
                (
                    "foreign-command-line",
                    ["--home", str(empty_home), "--argument-of-another-generation", "x",
                     "--saipen-root"],
                    "the hook answers a command line it cannot read by blocking: ",
                ),
            ):
                code, out, err = run(arguments, prompt, project)
                try:
                    answer = json.loads(out) if out else {}
                except ValueError:
                    answer = None
                if code != 0 or not isinstance(answer, dict) or answer.get("decision") == "block":
                    return {"ok": False, "step": step, "detail": fault + (err or out)[-240:]}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "step": "run", "detail": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "step": "complete", "detail": "starts, stays silent, fails open"}


def codex_self_test(artifact: Path) -> dict:
    """Prove a Codex artifact records an unreadable command line (T-1630).

    Three malformed command lines -- an argument of another generation, a
    missing value, a foreign host -- against the artifact itself inside a
    throwaway bound project, each with a controlled Stop payload. argparse
    answers a bad command line with exit 2, which Codex reads as a hook-level
    failure and corrects forever, so the artifact must exit 0 with a parseable,
    non-blocking capability boundary naming the command line instead. Never
    raises; an artifact that cannot say that is never activated.
    """
    import tempfile as _tempfile

    def run(arguments: list[str], event: dict, cwd: Path) -> tuple[int, str, str]:
        proc = subprocess.run(
            [sys.executable, str(artifact), *arguments],
            input=json.dumps(event).encode("utf-8"),
            capture_output=True,
            timeout=SELF_TEST_TIMEOUT,
            cwd=str(cwd),
            env={
                key: value
                for key, value in os.environ.items()
                if not key.startswith("SAIPEN_")
            },
            check=False,
        )
        return (
            proc.returncode,
            proc.stdout.decode("utf-8", errors="replace").strip(),
            proc.stderr.decode("utf-8", errors="replace").strip(),
        )

    probes = (
        (
            "unknown-option",
            [
                "--host",
                "codex",
                "--saipen-root",
                str(ROOT),
                "--argument-of-another-generation",
                "x",
            ],
        ),
        ("missing-root-value", ["--host", "codex", "--saipen-root"]),
        ("foreign-host", ["--host", "claude", "--saipen-root", str(ROOT)]),
    )
    try:
        with _tempfile.TemporaryDirectory(prefix="saipen-codex-selftest-") as scratch:
            project = Path(scratch) / "project"
            (project / ".saipen").mkdir(parents=True)
            (project / ".saipen" / "STATE.md").write_text("---\nphase: DONE\n---\n", "utf-8")
            event = {
                "hook_event_name": "Stop",
                "cwd": str(project),
                "session_id": "codex-self-test",
                "last_assistant_message": "An ordinary explanation.",
            }
            for step, arguments in probes:
                code, out, err = run(arguments, event, project)
                try:
                    answer = json.loads(out) if out else None
                except ValueError:
                    answer = None
                if (
                    code != 0
                    or not isinstance(answer, dict)
                    or answer.get("stopReason") != "SAIPEN_STOP_BOUNDARY_UNENFORCED"
                    or "SAIPEN_CAPABILITY_BOUNDARY" not in str(answer.get("systemMessage", ""))
                    or "hook command line" not in str(answer.get("systemMessage", ""))
                    or answer.get("decision") is not None
                ):
                    return {
                        "ok": False,
                        "step": step,
                        "detail": f"exit {code}: " + (err or out)[-240:],
                    }
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "step": "run", "detail": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": True,
        "step": "complete",
        "detail": "an unreadable command line records the boundary, never exit 2",
    }


def artifact_probe(artifact: Path, host: str, verify: bool = True) -> dict:
    """The artifact self-test for the host this artifact serves. Never raises.

    Codex gets the command-line fault probe (T-1630); every other host keeps
    the five-run `self_test` unchanged. `verify` False skips both -- the same
    fixture escape hatch `install(verify=False)` has always had.
    """
    if not verify:
        return {"ok": True, "step": "unverified"}
    if host == "codex":
        return codex_self_test(artifact)
    return self_test(artifact, host)


def previous_artifact(artifact: Path) -> Path:
    """Where the generation a new hook replaced is kept for rollback."""
    return artifact.with_name(artifact.name + ".previous")


#: What stands where a hook stood after an uninstall under a live host.
RETIRED_HOOK = Path(__file__).resolve().parent / "retired_host_hook.py"
RETIRED_MARKER = b"SAIPEN_RETIRED_HOST_HOOK = True"
#: A fixture's answer to "is a host alive", for the uninstaller run as a
#: process (both installer scripts read it). It decides only whether an inert
#: file is left behind, never what is removed from a hook configuration.
HOST_ALIVE_ENV = "SAIPEN_UNINSTALL_HOST_ALIVE"


def is_retired(artifact: Path) -> bool:
    """Is this file the inert stand-in an uninstall left for a live host?"""
    try:
        return artifact.is_file() and RETIRED_MARKER in artifact.read_bytes()
    except OSError:
        return False


def machine_profile() -> Path | None:
    """The user's profile directory as the OPERATING SYSTEM records it.

    Not `Path.home()`: that follows USERPROFILE/HOME, and a sandbox that
    redirects them to run an installer is exactly what must not be mistaken
    for the operator's machine when the question is machine-global.
    """
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            buffer = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            # CSIDL_PROFILE, current value: resolved from the user's token.
            if ctypes.windll.shell32.SHGetFolderPathW(None, 0x28, None, 0, buffer) != 0:
                return None
            return Path(buffer.value) if buffer.value else None
        import pwd

        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except Exception:
        return None


def host_alive(entry: dict, home: Path, live_host: bool | None = None) -> bool:
    """May a running host still hold this hook's command?

    Unknown is yes: leaving an inert file is free, and deleting the script a
    loaded command still names blocks every prompt of that session. Only the
    machine's own profile is probed (`machine_profile`): which processes are
    alive is machine-global, so a home that an environment merely points at --
    every fixture and sandbox -- has no live host unless the caller says so
    (`live_host`, or `SAIPEN_UNINSTALL_HOST_ALIVE=1` for a fixture that drives
    the uninstaller as a process).
    """
    if live_host is not None:
        return live_host
    declared = os.environ.get(HOST_ALIVE_ENV, "").strip()
    if declared in ("0", "1"):
        return declared == "1"
    profile = machine_profile()
    try:
        if profile is None or Path(home).resolve() != profile.resolve():
            return False
    except OSError:
        return False
    try:
        from saipen_engine import host_authority_broker as broker
        from saipen_engine import host_authority_process as proc

        images = [str(entry.get("launch_executable") or entry.get("id") or "")]
        images += list(broker.settings().get("host_images") or [])
        return proc.any_live([item for item in images if item]) is not False
    except Exception:
        return True


def _operator_home(home: Path) -> bool:
    """Is this the real per-user home, as opposed to a fixture's?"""
    try:
        return Path(home).resolve() == Path.home().resolve()
    except OSError:
        return False


def sync_authority_service(entry: dict, home: Path, *, removing: bool = False) -> dict | None:
    """Retire a running authority service that is not this generation.

    A service outlives the files it was started from: after an install it would
    keep answering with the PREVIOUS generation's code until something ended
    it, and every diagnostic would be about a runtime no longer on disk. Only
    for a host that declares a separated authority, only on the operator's real
    home (a fixture never reaches the operator's service), and only when the
    generations differ -- an unchanged service is left alone, because ending it
    costs every open session a re-delivery.
    """
    if not entry.get("admission_authority") or not _operator_home(home):
        return None
    try:
        from saipen_engine import host_authority_broker as broker
        from saipen_engine import host_authority_client as client

        live = client.health()
        if not live:
            return {"retired": False, "detail": "not running"}
        if not removing and live.get("generation") == broker.service_generation():
            return {"retired": False, "detail": "current generation"}
        return client.retire_service()
    except Exception as exc:
        return {"retired": False, "detail": f"{type(exc).__name__}: {exc}"}


def install(
    host: str, home: Path, root: Path = ROOT, *, check: bool = False, verify: bool = True,
    profile: Path | None = None,
) -> dict:
    """Install (or with `check`, only observe) one native guard hook.

    The result names the SAIPEN root the configured hook delegates to
    (`saipen_root`) and whether that root proves the accepted generation
    (`root_current`): the wrapper executes `<saipen_root>/tools/saipen.py`, so a
    current wrapper over a stale delegated engine is not a current hook.
    `problems` names every reason the hook is not current, so a diagnostic
    never has to say "stale" and stop. `verify` False skips the staged
    self-test: it exists for fixtures that build a throwaway home many times
    and prove the artifact elsewhere, and no installer entry point passes it.
    """
    with identity_session():
        return _install(host, home, root, check=check, verify=verify, profile=profile)


def _install(host: str, home: Path, root: Path, *, check: bool, verify: bool = True,
             profile: Path | None = None) -> dict:
    registry = json.loads(
        (root / "extensions/adapters/registry.json").read_text(encoding="utf-8-sig")
    )
    entry = next(item for item in registry["adapters"] if item["id"] == host)
    if host == "claude":
        from saipen_engine.claude_profiles import adapter_for, write_directory

        entry = adapter_for(entry, home, write_directory(home, profile))
    elif profile is not None:
        raise ValueError("--profile is only supported for Claude Code")
    artifact = home / entry["hook_install_surface"].removeprefix("~/")
    config = home / entry["hook_config_surface"].removeprefix("~/")
    delegate = delegated_root(entry, home, root)
    invocation = command(host, artifact, delegate)
    reasons: list[str] = []
    service: dict | None = None
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
                (owned == [(".*", expected["hooks"][0])] and _named_root_is_current(named))
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
        # Question-only PreToolUse closes the control handback bypass. No
        # bootstrap/read/shell tool inherits this matcher.
        hooks = data.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise ValueError("hooks must be an object")
        configured = True
        named_root = None
        for event, matcher, timeout in CLAUDE_EVENTS:
            expected_hook = {"type": "command", "command": invocation, "timeout": timeout}
            owned = _own_event_hooks(hooks, event, expected_hook, artifact.name, matcher)
            configured = (
                configured and len(owned) == 1 and _same_claude_entry(owned[0], expected_hook)
            )
            if len(owned) != 1:
                reasons.append(f"config-entry-missing:{event}" if not owned
                               else f"config-entry-duplicated:{event}")
            elif not _same_claude_entry(owned[0], expected_hook):
                named = str(owned[0].get("command", ""))
                reasons.append(
                    f"hook-interpreter-missing:{interpreter_of(named)}"
                    if interpreter_missing(named)
                    else f"config-entry-differs:{event}"
                )
            if event == "Stop" and len(owned) == 1:
                named_root = saipen_root_of(str(owned[0].get("command", "")))
        style_conflicts = _style_hook_conflicts(hooks, artifact.name)
    elif host == "zaicode":
        configured = False
        # ZAICODE (a ZCode fork) reads ~/.zcode/cli/config.json. Its hooks run
        # as argv process hooks (shell:false), so the installed artifact is
        # started through HOOK_BOOTSTRAP with no intervening shell -- the
        # broker's max_shells:0 policy requires exactly that.
        hooks = data.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise ValueError("hooks must be an object")
        hooks["enabled"] = True
        hooks.setdefault("timeoutMs", 30000)
        hooks.setdefault("maxOutputBytes", 256 * 1024)
        events = hooks.setdefault("events", {})
        if not isinstance(events, dict):
            raise ValueError("events must be an object")
        groups = events.setdefault("UserPromptSubmit", [])
        if not isinstance(groups, list):
            raise ValueError("UserPromptSubmit must be an array")
        expected_hook = {
            "type": "process",
            "command": sys.executable,
            "args": [
                "-c",
                HOOK_BOOTSTRAP,
                str(artifact),
                "--host",
                host,
                "--saipen-root",
                str(delegate),
            ],
            "timeoutMs": 30000,
        }
        expected_group = {"hooks": [expected_hook]}
        owned: list[dict] = []
        preserved: list[dict] = []
        inserted = False
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise ValueError("malformed UserPromptSubmit hook group")
            remaining = []
            for hook in group["hooks"]:
                if not isinstance(hook, dict):
                    raise ValueError("malformed hook entry")
                args = hook.get("args")
                is_ours = (
                    hook.get("type") == "process"
                    and isinstance(args, list)
                    and any(str(item).endswith(artifact.name) for item in args)
                    and "--saipen-root" in [str(item) for item in args]
                )
                if is_ours:
                    owned.append(hook)
                    if not inserted:
                        remaining.append(expected_hook)
                        inserted = True
                else:
                    remaining.append(hook)
            if remaining:
                preserved.append({**group, "hooks": remaining})
        # The root the config ACTUALLY names, not the one this run would write:
        # `root_current` is a claim about the installed file. Every other branch
        # reads it from the owned entry for the same reason (T-1935).
        named_root = None
        if len(owned) == 1:
            args_owned = [str(item) for item in (owned[0].get("args") or [])]
            if "--saipen-root" in args_owned:
                at = args_owned.index("--saipen-root")
                if at + 1 < len(args_owned):
                    named_root = args_owned[at + 1]
        if named_root is None and not check:
            named_root = str(delegate)
        configured = len(owned) == 1 and _same_process_entry(owned[0], expected_hook)
        if not inserted:
            preserved.append(expected_group)
        events["UserPromptSubmit"] = preserved
        style_conflicts = []
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
            configured = (data == expected and _named_root_is_current(named_command)) or (
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
    artifact_current = installed and content_bytes(artifact.read_bytes()) == content_bytes(shipped)
    if not installed:
        reasons.append("artifact-missing")
    elif not artifact_current:
        reasons.append("artifact-stale")
    if not configured and not reasons:
        reasons.append("config-entry-differs")
    if named_root is not None and not root_current:
        reasons.append("delegated-root-stale")
    current = artifact_current and configured
    activation = None
    if not check:
        # Preserve original settings once by content identity; never overwrite
        # a user's earlier backup. Malformed config is refused before writes.
        encoded = (json.dumps(data, indent=2) + "\n").encode("utf-8")
        if host in ("claude", "codex"):
            # T-1630: the Codex branch stages and verifies too -- an artifact
            # that fails its probe must never replace the installed artifact
            # or touch the shared hooks.json.
            activation = _activate_verified(
                host,
                artifact,
                shipped,
                config,
                encoded,
                original,
                already_current=current,
                verify=verify,
            )
        else:
            _backup_config(config, original, encoded)
            atomic_write(artifact, shipped)
            atomic_write(config, encoded)
        if activation is None or activation["activated"]:
            installed = current = configured = True
            reasons = []
            named_root = str(delegate)
            root_current = root_resolves(named_root)
            service = sync_authority_service(entry, home)
        else:
            reasons.append("install-preflight-failed:" + str(activation.get("step")))
    result = {
        "host": host,
        "capability": True,
        "installed": installed,
        "current": current,
        "configured": configured,
        "saipen_root": named_root,
        "root_current": root_current,
        "problems": reasons,
        "health": None,
        "effective": "UNKNOWN" if current else "ENFORCEMENT_GAP",
        "artifact": str(artifact),
        "config": str(config),
    }
    if activation is not None:
        result["activation"] = activation
    if service is not None:
        result["authority_service"] = service
    if host == "codex":
        result["proof_preflight"] = codex_hook_preflight(home, hooks_json_present=config.is_file())
    if host == "claude":
        result["style_hook_conflicts"] = style_conflicts
    return result


def _backup_config(config: Path, original: bytes | None, encoded: bytes) -> None:
    if original is None or original == encoded:
        return
    import hashlib

    backup = config.with_name(
        config.name + "." + hashlib.sha256(original).hexdigest()[:16] + ".bak"
    )
    if not backup.exists():
        atomic_write(backup, original)


def _activate_verified(
    host: str,
    artifact: Path,
    shipped: bytes,
    config: Path,
    encoded: bytes,
    original: bytes | None,
    *,
    already_current: bool,
    verify: bool = True,
) -> dict:
    """Stage, verify, activate -- and take it back if the active hook fails.

    Nothing the host reads changes until the staged artifact has passed
    `artifact_probe`. After activation the ACTIVE artifact is tested once more, and
    a failure restores the previous artifact and the previous configuration
    bytes: the operator is left exactly where they were, with a named reason.
    """
    if already_current:
        return {"activated": True, "step": "already-current", "changed": False, "rollback": False}
    staged = artifact.with_name(artifact.name + ".staged")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    try:
        staged.write_bytes(shipped)
        verdict = artifact_probe(staged, host, verify)
    except OSError as exc:
        verdict = {"ok": False, "step": "stage", "detail": str(exc)}
    if not verdict.get("ok"):
        if staged.exists():
            staged.unlink()
        return {
            "activated": False,
            "code": "INSTALL_PREFLIGHT_FAILED",
            "step": verdict.get("step"),
            "detail": verdict.get("detail"),
            "changed": False,
            "rollback": False,
        }
    prior = artifact.read_bytes() if artifact.is_file() else None
    _backup_config(config, original, encoded)
    try:
        if (
            prior is not None
            and content_bytes(prior) != content_bytes(shipped)
            # An uninstall's inert stand-in is not a generation to roll back to.
            and RETIRED_MARKER not in prior
        ):
            atomic_write(previous_artifact(artifact), prior)
        os.replace(staged, artifact)
        atomic_write(config, encoded)
        verdict = artifact_probe(artifact, host, verify)
    except OSError as exc:
        verdict = {"ok": False, "step": "activate", "detail": str(exc)}
    finally:
        if staged.exists():
            staged.unlink()
    if verdict.get("ok"):
        return {"activated": True, "step": "activated", "changed": True, "rollback": False,
                "previous": str(previous_artifact(artifact)) if prior is not None else None}
    # The active hook failed after activation: put the operator back.
    if prior is not None:
        atomic_write(artifact, prior)
    elif artifact.exists():
        artifact.unlink()
    if original is not None:
        atomic_write(config, original)
    elif config.exists():
        config.unlink()
    return {
        "activated": False,
        "code": "INSTALL_PREFLIGHT_FAILED",
        "step": "post-activation:" + str(verdict.get("step")),
        "detail": verdict.get("detail"),
        "changed": False,
        "rollback": True,
    }


def rollback(host: str, home: Path, root: Path = ROOT, *, profile: Path | None = None) -> dict:
    """Put the previous hook generation back. One action, no arguments beyond
    the host: the artifact kept by the last activation replaces the active one
    after passing the same self-test a new artifact must pass."""
    registry = json.loads(
        (root / "extensions/adapters/registry.json").read_text(encoding="utf-8-sig")
    )
    entry = next(item for item in registry["adapters"] if item["id"] == host)
    if host == "claude":
        from saipen_engine.claude_profiles import adapter_for, write_directory

        entry = adapter_for(entry, home, write_directory(home, profile))
    artifact = home / entry["hook_install_surface"].removeprefix("~/")
    kept = previous_artifact(artifact)
    if not kept.is_file():
        return {"host": host, "rolled_back": False, "detail": "no previous hook generation is kept"}
    verdict = artifact_probe(kept, host)
    if not verdict.get("ok"):
        return {"host": host, "rolled_back": False,
                "detail": "the kept generation fails its self-test: " + str(verdict.get("detail"))}
    current = artifact.read_bytes() if artifact.is_file() else None
    atomic_write(artifact, kept.read_bytes())
    if current is not None:
        atomic_write(kept, current)
    return {"host": host, "rolled_back": True, "artifact": str(artifact)}


def _uninstall_entry_is_ours(hook: dict, host: str, artifact: Path) -> bool:
    """Match the actual guard invocation, never a mention inside user prose."""
    action = hook.get("action") if isinstance(hook.get("action"), dict) else {}
    commands = (hook.get("command"), hook.get("commandWindows"), action.get("command"))
    expected = os.path.normcase(str(artifact)).replace("\\", "/")
    for invocation in commands:
        if not isinstance(invocation, str):
            continue
        for posix in (True, False):
            try:
                argv = [arg.strip("\"'") for arg in shlex.split(invocation, posix=posix)]
            except ValueError:
                continue
            # Both spellings: the bootstrap form, and the plain script form
            # every installation made before it still carries.
            script = hook_script(argv)
            if len(argv) < 6 or os.path.normcase(script or "").replace("\\", "/") != expected:
                continue
            try:
                if argv[argv.index("--host") + 1] == host and argv[argv.index("--saipen-root") + 1]:
                    return True
            except (ValueError, IndexError):
                continue
    return False


def uninstall(
    host: str, home: Path, root: Path = ROOT, *, live_host: bool | None = None,
    profile: Path | None = None,
) -> dict:
    """Remove this host's configured guard entries and unchanged guard artifact.

    While a host application is alive (`host_alive`) the artifact is not
    deleted but replaced by the inert `RETIRED_HOOK`: a running session keeps
    the hook command it loaded, and a command whose script is gone blocks."""
    home = home.resolve()
    registry = json.loads((root / "extensions/adapters/registry.json").read_text(encoding="utf-8"))
    entry = next(item for item in registry["adapters"] if item["id"] == host)
    allowed_root = home
    if host == "claude":
        from saipen_engine.claude_profiles import adapter_for, write_directory

        allowed_root = write_directory(home, profile)
        if allowed_root.is_symlink():
            raise ValueError("Claude profile is a link")
        entry = adapter_for(entry, home, allowed_root)
    artifact = home / entry["hook_install_surface"].removeprefix("~/")
    config = home / entry["hook_config_surface"].removeprefix("~/")
    for path in (artifact, config):
        if path.is_symlink() or not path.resolve().is_relative_to(allowed_root.resolve()):
            raise ValueError("hook uninstall path escapes the selected home")
    removed = 0
    if config.exists():
        original = config.read_bytes()
        data = json.loads(original.decode("utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("hook config must be a JSON object")
        hooks = data.get("hooks", {})
        if host == "kiro":
            if not isinstance(hooks, list):
                raise ValueError("Kiro hooks must be an array")
            kept = [
                h
                for h in hooks
                if not isinstance(h, dict) or not _uninstall_entry_is_ours(h, host, artifact)
            ]
            removed = len(hooks) - len(kept)
            data["hooks"] = kept
            if removed and not kept and set(data) <= {"version", "hooks"}:
                data = {}
        else:
            if not isinstance(hooks, dict):
                raise ValueError("hooks must be an object")
            for event, groups in list(hooks.items()):
                if not isinstance(groups, list):
                    raise ValueError("hook event must be an array")
                kept_groups = []
                for group in groups:
                    if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                        raise ValueError("malformed hook group")
                    kept = [
                        h
                        for h in group["hooks"]
                        if not isinstance(h, dict)
                        or not _uninstall_entry_is_ours(h, host, artifact)
                    ]
                    own_count = len(group["hooks"]) - len(kept)
                    removed += own_count
                    if kept or not own_count or set(group) - {"matcher", "hooks"}:
                        kept_groups.append({**group, "hooks": kept})
                if kept_groups:
                    hooks[event] = kept_groups
                elif groups:
                    hooks.pop(event)
            if removed and not hooks:
                data.pop("hooks", None)
        if removed:
            atomic_write(config.with_name(config.name + ".uninstalled.bak"), original)
            restored = False
            # Restore exact original bytes when no later user edit prevents it.
            for backup in sorted(config.parent.glob(config.name + ".*.bak")):
                if (
                    not re.fullmatch(re.escape(config.name) + r"\.[0-9a-f]{16}\.bak", backup.name)
                    or backup.is_symlink()
                ):
                    continue
                try:
                    content = backup.read_bytes()
                    previous = json.loads(content.decode("utf-8-sig"))
                except (OSError, ValueError):
                    continue
                if previous == data:
                    atomic_write(config, content)
                    restored = True
                    break
            if not restored:
                if not data:
                    config.unlink()
                else:
                    atomic_write(config, (json.dumps(data, indent=2) + "\n").encode("utf-8"))
    artifact_removed = False
    artifact_retired = False
    if artifact.is_file():
        shipped = root / entry["hook_artifact"]
        ours = content_bytes(artifact.read_bytes()) == content_bytes(shipped.read_bytes())
        if ours or is_retired(artifact):
            if host_alive(entry, home, live_host):
                atomic_write(artifact, RETIRED_HOOK.read_bytes())
                artifact_retired = True
            else:
                artifact.unlink()
            artifact_removed = ours
    # The rollback generation and a stranded stage belong to this installer and
    # are of no use once the hook itself is gone.
    for leftover in (previous_artifact(artifact), artifact.with_name(artifact.name + ".staged")):
        if leftover.is_file() and not leftover.is_symlink():
            leftover.unlink()
    result = {
        "host": host,
        "removed_hooks": removed,
        "artifact_removed": artifact_removed,
        "artifact_retired": artifact_retired,
    }
    # With the hook gone nothing asks the authority service any more.
    service = sync_authority_service(entry, home, removing=True)
    if service is not None:
        result["authority_service"] = service
    if host == "claude":
        from saipen_engine.claude_profiles import health_file

        health = health_file(home, allowed_root)
    else:
        health = home / ".saipen" / "health" / f"{host}.json"
    if health.is_file() and not health.is_symlink():
        health.unlink()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", choices=("kiro", "gemini", "codex", "claude", "zaicode"))
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument(
        "--rollback", action="store_true", help="put the previous hook generation back"
    )
    args = parser.parse_args()
    try:
        if args.profile is not None and args.host not in ("claude",):
            raise ValueError("--profile is only supported for Claude Code")
        if sum((args.uninstall, args.check, args.rollback)) > 1:
            raise ValueError("--check, --uninstall and --rollback are mutually exclusive")
        if args.rollback:
            result = rollback(args.host, args.home, profile=args.profile)
            print(json.dumps(result, indent=2))
            return 0 if result.get("rolled_back") else 1
        result = (
            uninstall(args.host, args.home, profile=args.profile)
            if args.uninstall
            else install(args.host, args.home, check=args.check, profile=args.profile)
        )
        print(json.dumps(result, indent=2))
        activation = result.get("activation") if isinstance(result, dict) else None
        if isinstance(activation, dict) and not activation.get("activated"):
            # The previous hook is still the active one; say so with a failing
            # exit code so the canonical installer reports it instead of
            # printing "installed".
            return 1
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"effective": "UNKNOWN", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
