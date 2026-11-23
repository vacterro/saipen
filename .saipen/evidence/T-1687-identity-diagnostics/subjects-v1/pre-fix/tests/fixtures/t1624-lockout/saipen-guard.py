"""Claude Code transport for protocol admission and the final-response gate.

No protocol policy, no response schema, no style rule and no admission rule live
here. Claude Code hook events are forwarded to the SAME canonical authority the
Codex and OpenCode gates use -- ``tools/saipen.py`` -- and its one verdict is
mapped onto Claude Code hook output. The chain each verdict comes from is
binding, ADMISSION, EXEC-RESPONSE, chat style; a later layer never compensates
for an earlier failure (``saipen_engine.response_surface.gate_final_response``).

T-1563: no separated host authority exists in this installation. This same-user
transport cannot mint signing authority. The admission events below currently
report refusal, rather than successful establishment or invalidation. They are
the integration points for a future genuinely separated host provider.

Events and what each one can honestly do:

* ``SessionStart`` -- the session is new, resumed, cleared, compacted or forked:
  the context the model held is gone or replaced, so the recorded admission is
  invalidated and the runtime delivers the authority again
  (``saipen admission establish``), as ``additionalContext``.
* ``UserPromptSubmit`` -- the pre-generation boundary. The runtime establishes
  admission and delivers the authority BEFORE the model runs. When admission
  cannot be established the prompt is blocked (``decision: block``): the model
  does not run, and the only text that reaches the user is the bounded
  diagnostic the runtime wrote. The model never authors it.
* ``PostToolUse`` -- only for a real ``saipen init`` that just bound a project:
  admission is established in the SAME turn, before the final reply, so a
  session that started outside SAIPEN needs no restart and no grace turn.
* ``PostModelSwitch`` -- the model changed: the old admission is invalidated.
* ``Stop`` -- the final message is checked through the layered gate. Claude Code
  offers no hook that intercepts assistant text before it is displayed
  (``MessageDisplay`` replaces text on screen only, and its input schema is not
  documented), so Stop is post-render: it can require ONE correction, never
  retract. That boundary is recorded in the adapter registry, not hidden here.

Stop re-entry is deliberate and bounded, as in the Codex transport: the first
refused stop of a turn requests one correction; a stop that is already a
Stop-hook continuation (``stop_hook_active``) records the capability boundary
instead of looping. Moments the gate cannot enforce are recorded honestly and
never pretended into a verdict. Outside a SAIPEN project the transport does
nothing, and bootstrap tool activity is never gated: only user-visible output is.

The human's own request (read from the transcript; tool results, skill payloads
and non-human origins excluded) is forwarded so a genuine report, audit or
handoff request earns the detailed budget; the reply never authorizes itself.
``--home`` and ``--authority-root`` are diagnostic command-line flags used by the
test carriers. They are never environment variables: the installed command line
is the operator's, and an environment override would be a way round the gate.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

MAX_BYTES = 256 * 1024
CHECK_TIMEOUT_SECONDS = 60
ADMISSION_TIMEOUT_SECONDS = 45
# One agentic turn is one human prompt followed by hundreds of tool results, so
# the request can sit megabytes behind the end of the transcript (measured: a 3 MB
# transcript whose only human entry was its first line).
TRANSCRIPT_MAX_BYTES = 64 * 1024 * 1024
MAX_REQUEST_CHARS = 2000

BOUNDARY_REENTRY = (
    "SAIPEN_CAPABILITY_BOUNDARY CLAUDE_STOP_REENTRY_NO_FAIL_CLOSED: this Stop is "
    "already a Stop-hook continuation (stop_hook_active) and the one enforced "
    "correction round for this turn is exhausted. Claude Code cannot retract the "
    "already rendered message, and a second continuation would be an "
    "uncontrolled loop. The refused response is recorded here as unenforced "
    "({klass}: {errors}). Terminal fail-closed correction is NOT claimed."
)

BOUNDARY_UNAVAILABLE = (
    "SAIPEN_CAPABILITY_BOUNDARY CLAUDE_STOP_GATE_UNAVAILABLE: the canonical "
    "response checker could not be consulted ({reason}), so the outgoing message "
    "is recorded as unenforced. Installed current hook bytes and checker "
    "reachability are the only enforcement boundaries; none is claimed stronger."
)

ADMISSION_UNAVAILABLE = (
    "SAIPEN PROTOCOL ADMISSION REFUSED -- the admission authority could not be "
    "consulted ({reason}). No reply is permitted until it can be. The operator "
    "must restore the SAIPEN runtime named in this hook's command line."
)

_SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)
_INIT_COMMAND = re.compile(r"(?i)\bsaipen(?:\.cmd|\.py)?\b[^\n;&|]*\binit\b")
_PROJECT_ROOT_FLAG = re.compile(r"--project-root[ =]+(?:\"([^\"]+)\"|'([^']+)'|(\S+))")
TRANSPORT_ENV = "SAIPEN_ADMISSION_TRANSPORT"


def project_root(cwd: str | None) -> Path | None:
    """The bound SAIPEN project for this event, or None.

    Explicit ``SAIPEN_PROJECT_ROOT`` wins; otherwise the nearest ancestor of the
    session cwd carrying canonical STATE. No project means no SAIPEN context at
    all, and the event is ordinary chat.
    """
    declared = os.environ.get("SAIPEN_PROJECT_ROOT", "").strip()
    if declared:
        try:
            root = Path(declared).resolve()
            return root if (root / ".saipen" / "STATE.md").is_file() else None
        except OSError:
            return None
    if cwd:
        try:
            start = Path(cwd).resolve()
        except OSError:
            return None
        for node in (start, *start.parents):
            if (node / ".saipen" / "STATE.md").is_file():
                return node
    return None


def _run_engine(
    saipen_root: Path,
    project: Path,
    args: list[str],
    *,
    stdin: str | None,
    timeout: int,
    transport: str | None = None,
    operator_request: str | None = None,
):
    """One canonical engine call. Bytes both ways: text mode would use the host
    LOCALE (cp1251 on the operator's Windows host), where an Estonian diacritic
    does not exist, and the encode would raise."""
    env = dict(os.environ)
    env.pop(TRANSPORT_ENV, None)
    if transport:
        env[TRANSPORT_ENV] = transport
    if operator_request:
        # Native transcript USER bytes bind response depth only. This does
        # not mint admission or supply Work preemption authority.
        import hashlib

        env["SAIPEN_TASK_SHA256"] = hashlib.sha256(
            operator_request.replace("\r\n", "\n").replace("\r", "\n").strip().encode("utf-8")
        ).hexdigest()
    proc = subprocess.run(
        [sys.executable, str(Path(saipen_root) / "tools" / "saipen.py"), *args],
        input=stdin.encode("utf-8") if stdin is not None else None,
        capture_output=True,
        timeout=timeout,
        cwd=str(project),
        env=env,
    )
    payload = json.loads((proc.stdout or b"").decode("utf-8", errors="replace") or "")
    return payload if isinstance(payload, dict) else None


def _read_transcript(transcript_path: object) -> list[str]:
    if not isinstance(transcript_path, str) or not transcript_path:
        return []
    try:
        path = Path(transcript_path)
        size = path.stat().st_size
        with path.open("rb") as stream:
            if size > TRANSCRIPT_MAX_BYTES:
                stream.seek(size - TRANSCRIPT_MAX_BYTES)
            raw = stream.read()
    except OSError:
        return []
    lines = raw.decode("utf-8", errors="replace").splitlines()
    if size > TRANSCRIPT_MAX_BYTES and lines:
        lines = lines[1:]  # the first line of a mid-file seek is a fragment
    return lines


def last_human_request(transcript_path: object) -> str:
    """The human's latest request from the transcript, or ''.

    Tool results, skill payloads (`isMeta`) and any entry whose `origin` is not
    a human are user-role entries too and are not requests; injected system
    reminders are stripped. Best effort: an unreadable transcript is an empty
    request, which authorizes nothing.
    """
    for line in reversed(_read_transcript(transcript_path)):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("type") != "user":
            continue
        if entry.get("isMeta") or entry.get("isSidechain"):
            continue
        origin = entry.get("origin")
        if isinstance(origin, dict) and origin.get("kind") not in (None, "human"):
            continue
        message = entry.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):
            if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                continue
            content = "\n".join(
                str(b.get("text", ""))
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
        if not isinstance(content, str):
            continue
        text = _SYSTEM_REMINDER.sub("", content).strip()
        if text:
            return text if len(text) <= MAX_REQUEST_CHARS else ""
    return ""


def last_model(transcript_path: object) -> str | None:
    """The model that wrote the latest assistant entry, or None (unobservable)."""
    for line in reversed(_read_transcript(transcript_path)):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        message = entry.get("message") if isinstance(entry, dict) else None
        if (
            isinstance(entry, dict)
            and entry.get("type") == "assistant"
            and isinstance(message, dict)
        ):
            model = message.get("model")
            if isinstance(model, str) and model and not model.startswith("<"):
                return model
    return None


def admission_args(event: dict, project: Path, options: argparse.Namespace) -> list[str]:
    """The observed session facts, forwarded; the owner infers none of them."""
    args = [
        "--project-root",
        str(project),
        "--session",
        str(event.get("session_id") or ""),
        "--host",
        "claude",
    ]
    model = event.get("model") if isinstance(event.get("model"), str) else None
    model = model or last_model(event.get("transcript_path"))
    if model:
        args += ["--model", model]
    if options.home:
        args += ["--home", str(options.home)]
    if options.authority_root:
        args += ["--authority-root", str(options.authority_root)]
    return args


def canonical_verdict(
    saipen_root: Path, project: Path, text: str, request: str, event: dict, options
) -> dict | None:
    """The canonical layered verdict, or None when it cannot be had."""
    args = [
        "response",
        "check",
        "--stdin",
        "--json",
        "--classify",
        "--auto-eligibility",
        "--project-root",
        str(project),
        "--admission-session",
        str(event.get("session_id") or ""),
        "--host",
        "claude",
    ]
    model = event.get("model") if isinstance(event.get("model"), str) else None
    model = model or last_model(event.get("transcript_path"))
    if model:
        args += ["--model", model]
    if options.home:
        args += ["--home", str(options.home)]
    if options.authority_root:
        args += ["--authority-root", str(options.authority_root)]
    if request:
        args.extend(["--request", request])
    try:
        payload = _run_engine(
            saipen_root,
            project,
            args,
            stdin=text,
            timeout=CHECK_TIMEOUT_SECONDS,
            operator_request=request or None,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if payload is None or not isinstance(payload.get("ok"), bool):
        return None
    return payload


def correction_reason(verdict: dict, project: Path) -> str:
    """The continuation prompt that requires correction through the authority."""
    klass = verdict.get("class")
    errors = [str(item) for item in (verdict.get("errors") or [])][:3]
    checker = (
        f"`saipen response check --stdin --classify --auto-eligibility --project-root {project}`"
    )
    if klass == "ADMISSION_BLOCKED":
        # Runtime-authored: the diagnostic and the compact contract come from the
        # owner. The model that lacked admission does not write either.
        return (verdict.get("diagnostic") or "SAIPEN PROTOCOL ADMISSION REFUSED") + (
            " " + str(verdict.get("contract") or "")
        ).rstrip()
    if klass == "AUTONOMOUS_HANDBACK":
        return (
            "SAIPEN EXEC-RESPONSE-01 gate (AUTONOMOUS_HANDBACK): eligible canonical "
            "work remains, so returning control is invalid. Do not hand back: run "
            "exactly `saipen continue --json`, open its load_path and execute the "
            "returned action in this turn. When the canonical route genuinely needs "
            "the operator, assemble the control surface with `saipen response render "
            "--stdin`, verify the exact text with " + checker + ", and reply with "
            "only that verified surface."
        )
    if klass == "CHAT_STYLE_DRIFT":
        return (
            "SAIPEN chat-style gate (CHAT_STYLE_DRIFT): this reply breaks the "
            "measurable chat contract of STYLE.md (" + "; ".join(errors) + "). "
            "Rewrite it as one short message in the pinned reply language, within "
            "the chat line budget, without a banned opener, closer or apology, "
            "and reply with only that message. Read the contract with `saipen "
            "response style --json`; verify the exact text with " + checker + "."
        )
    return (
        "SAIPEN EXEC-RESPONSE-01 gate (INVALID_OPERATIONAL_PROSE): this operational "
        "response is not an accepted canonical boundary ("
        + "; ".join(errors)
        + "). Assemble the control surface with `saipen response render --stdin`, "
        "verify the exact text with " + checker + ", and reply with only that "
        "verified surface. Ordinary non-operational conversation must not carry "
        "operational report shapes."
    )


def record(boundary: str) -> None:
    """Surface the exact capability boundary and let the stop complete."""
    print(json.dumps({"continue": True, "systemMessage": boundary}))


def _admission(saipen_root: Path, project: Path, verb: str, event: dict, options, name: str):
    args = ["admission", verb, "--json", *admission_args(event, project, options)]
    if verb == "invalidate":
        args += ["--reason", name]
    try:
        return _run_engine(
            saipen_root,
            project,
            args,
            stdin=None,
            timeout=ADMISSION_TIMEOUT_SECONDS,
            # No local signer: same-user Python cannot prove host provenance.
            # The canonical owner refuses until a separated authority exists.
            transport=None,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _inject(event_name: str, verdict: dict) -> None:
    parts = [str(verdict.get("delivery") or "").strip(), str(verdict.get("contract") or "").strip()]
    context = "\n\n".join(part for part in parts if part)
    if context:
        print(
            json.dumps(
                {"hookSpecificOutput": {"hookEventName": event_name, "additionalContext": context}}
            )
        )


def handle_session_start(saipen_root: Path, project: Path, event: dict, options) -> int:
    source = str(event.get("source") or "startup")
    # Every source changes what the model holds (new, resumed, cleared, compacted,
    # forked): the recorded admission proves delivery into a context that is gone.
    _admission(saipen_root, project, "invalidate", event, options, f"SessionStart:{source}")
    verdict = _admission(saipen_root, project, "establish", event, options, "SessionStart")
    if verdict is None or not verdict.get("permitted"):
        # SessionStart cannot block anything; the prompt boundary will.
        diagnostic = (verdict or {}).get("diagnostic") or ADMISSION_UNAVAILABLE.format(
            reason="engine unreachable"
        )
        print(json.dumps({"systemMessage": diagnostic}))
        return 0
    _inject("SessionStart", verdict)
    return 0


def handle_prompt(saipen_root: Path, project: Path, event: dict, options) -> int:
    """The pre-generation boundary: admit, deliver, or block the prompt."""
    verdict = _admission(saipen_root, project, "establish", event, options, "UserPromptSubmit")
    if verdict is None:
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": ADMISSION_UNAVAILABLE.format(reason="engine unreachable"),
                }
            )
        )
        return 0
    if not verdict.get("permitted"):
        print(json.dumps({"decision": "block", "reason": verdict.get("diagnostic") or ""}))
        return 0
    _inject("UserPromptSubmit", verdict)
    return 0


def handle_post_tool(saipen_root: Path, project: Path | None, event: dict, options) -> int:
    """A real `saipen init` just bound this project: admit in the SAME turn."""
    if event.get("tool_name") != "Bash":
        return 0
    tool_input = event.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not _INIT_COMMAND.search(command):
        return 0
    if project is None:
        flagged = _PROJECT_ROOT_FLAG.search(command)
        candidate = next((g for g in (flagged.groups() if flagged else ()) if g), None)
        project = project_root(candidate) if candidate else None
    if project is None:
        return 0
    verdict = _admission(saipen_root, project, "establish", event, options, "PostToolUse")
    if verdict is None or not verdict.get("permitted"):
        diagnostic = (verdict or {}).get("diagnostic") or ADMISSION_UNAVAILABLE.format(
            reason="engine unreachable"
        )
        print(json.dumps({"systemMessage": diagnostic}))
        return 0
    _inject("PostToolUse", verdict)
    return 0


def handle_stop(saipen_root: Path, project: Path, event: dict, options) -> int:
    reentry = event.get("stop_hook_active") is True
    text = event.get("last_assistant_message")
    if not isinstance(text, str):
        record(BOUNDARY_UNAVAILABLE.format(reason="Stop event has no last_assistant_message text"))
        return 0
    verdict = canonical_verdict(
        saipen_root, project, text, last_human_request(event.get("transcript_path")), event, options
    )
    if verdict is None:
        record(
            BOUNDARY_UNAVAILABLE.format(
                reason="canonical response checker unreachable or its output invalid"
            )
        )
        return 0
    if verdict.get("ok") is True:
        # Every consulted layer passed: nothing to intercept.
        return 0
    klass = verdict.get("class")
    if not isinstance(klass, str) or not klass:
        record(
            BOUNDARY_UNAVAILABLE.format(
                reason="canonical authority returned no response class ("
                + str(verdict.get("detail") or verdict.get("code") or "unknown")[:200]
                + ")"
            )
        )
        return 0
    errors = [str(item) for item in (verdict.get("errors") or [])][:3]
    if reentry:
        record(BOUNDARY_REENTRY.format(klass=klass, errors="; ".join(errors)))
        return 0
    delivery = verdict.get("delivery")
    correction = (
        f"SAIPEN canonical delivery ({klass}; do not add prose):\n" + delivery
        if isinstance(delivery, str) and delivery
        else correction_reason(verdict, project)
    )
    print(json.dumps({"decision": "block", "reason": correction}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("claude",), required=True)
    parser.add_argument("--saipen-root", type=Path, required=True)
    parser.add_argument("--home", type=Path, default=None, help="diagnostic: operator home")
    parser.add_argument(
        "--authority-root", type=Path, default=None, help="diagnostic: protocol authority root"
    )
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
    except OSError:
        raw = b""
    if len(raw) > MAX_BYTES:
        record(BOUNDARY_UNAVAILABLE.format(reason="hook event exceeds bounded size"))
        return 0
    try:
        event = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        record(BOUNDARY_UNAVAILABLE.format(reason="hook event is not readable JSON"))
        return 0
    if not isinstance(event, dict):
        return 0
    name = event.get("hook_event_name")
    if name not in ("SessionStart", "UserPromptSubmit", "PostToolUse", "PostModelSwitch", "Stop"):
        # Not a supported event: this transport gates nothing. PreToolUse is
        # deliberately absent: bootstrap tool activity is never gated.
        return 0
    project = project_root(event.get("cwd") or os.getcwd())
    if name == "PostToolUse":
        return handle_post_tool(args.saipen_root, project, event, args)
    if project is None:
        if os.environ.get("SAIPEN_PROJECT_ROOT", "").strip():
            record(
                BOUNDARY_UNAVAILABLE.format(
                    reason="explicit SAIPEN_PROJECT_ROOT is not a bound SAIPEN project"
                )
            )
        # No SAIPEN project: ordinary non-operational chat.
        return 0
    if name == "SessionStart":
        return handle_session_start(args.saipen_root, project, event, args)
    if name == "UserPromptSubmit":
        return handle_prompt(args.saipen_root, project, event, args)
    if name == "PostModelSwitch":
        _admission(args.saipen_root, project, "invalidate", event, args, "PostModelSwitch")
        return 0
    return handle_stop(args.saipen_root, project, event, args)


if __name__ == "__main__":
    raise SystemExit(main())
