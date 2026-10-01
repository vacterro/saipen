"""Claude Code transport for the canonical chat and response gate (T-1558).

No protocol policy, no response schema and no style rule live here. Two Claude
Code hook events are forwarded to the SAME canonical authority the Codex and
OpenCode gates use -- ``tools/saipen.py`` -- and its one verdict is mapped onto
Claude Code hook output:

* ``UserPromptSubmit`` -- the chat contract generated from STYLE.md
  (``saipen response style --json``) is injected as ``additionalContext``
  before the model writes a word, so the pinned ``reply_language`` and the
  chat budget do not depend on the model having read STYLE.md, and no
  hand-written copy of the language rule sits in a host configuration to
  contradict it.
* ``Stop`` -- the outgoing final message (``last_assistant_message``) is
  checked by ``saipen response check --classify``. A reply that is not an
  accepted boundary or a style-compliant chat reply is refused once
  (``{"decision": "block"}``) with a correction prompt.

Stop re-entry is deliberate and bounded, exactly as in the Codex transport: the
first invalid stop of a turn requests one correction; a stop that is already a
Stop-hook continuation (``stop_hook_active``) records the capability boundary
instead of requesting another, because a second continuation would be an
uncontrolled loop and terminal fail-closed correction is NOT claimed. Moments
the gate cannot enforce (unreadable event, unreachable checker) are recorded the
same honest way and never pretended into a verdict. Outside a SAIPEN project the
transport does nothing.

The human's own request (read from the transcript, tool results excluded) is
forwarded so a genuine report, audit or handoff request earns the detailed
budget; the reply never authorizes itself.
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
CONTEXT_TIMEOUT_SECONDS = 20
TRANSCRIPT_TAIL_BYTES = 512 * 1024
MAX_REQUEST_CHARS = 2000

BOUNDARY_REENTRY = (
    "SAIPEN_CAPABILITY_BOUNDARY CLAUDE_STOP_REENTRY_NO_FAIL_CLOSED: this Stop is "
    "already a Stop-hook continuation (stop_hook_active) and the one enforced "
    "correction round for this turn is exhausted. Claude Code cannot retract the "
    "already rendered message, and a second continuation would be an "
    "uncontrolled loop. The invalid response is recorded here as unenforced "
    "({klass}: {errors}). Terminal fail-closed correction is NOT claimed."
)

BOUNDARY_UNAVAILABLE = (
    "SAIPEN_CAPABILITY_BOUNDARY CLAUDE_STOP_GATE_UNAVAILABLE: the canonical "
    "response checker could not be consulted ({reason}), so the outgoing message "
    "is recorded as unenforced. Installed current hook bytes and checker "
    "reachability are the only enforcement boundaries; none is claimed stronger."
)

_SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)


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


def _run_engine(saipen_root: Path, project: Path, args: list[str], *, stdin: str | None, timeout: int):
    """One canonical engine call. Bytes both ways: text mode would use the host
    LOCALE (cp1251 on the operator's Windows host), where an Estonian diacritic
    does not exist, and the encode would raise."""
    proc = subprocess.run(
        [sys.executable, str(Path(saipen_root) / "tools" / "saipen.py"), *args],
        input=stdin.encode("utf-8") if stdin is not None else None,
        capture_output=True,
        timeout=timeout,
        cwd=str(project),
    )
    payload = json.loads((proc.stdout or b"").decode("utf-8", errors="replace") or "")
    return payload if isinstance(payload, dict) else None


def last_human_request(transcript_path: object) -> str:
    """The human's latest request from the transcript tail, or ''.

    Tool results are user-role entries too and are not requests; injected
    system reminders are stripped. Best effort: an unreadable transcript is an
    empty request, which authorizes nothing.
    """
    if not isinstance(transcript_path, str) or not transcript_path:
        return ""
    try:
        path = Path(transcript_path)
        size = path.stat().st_size
        with path.open("rb") as stream:
            if size > TRANSCRIPT_TAIL_BYTES:
                stream.seek(size - TRANSCRIPT_TAIL_BYTES)
            raw = stream.read()
    except OSError:
        return ""
    lines = raw.decode("utf-8", errors="replace").splitlines()
    if size > TRANSCRIPT_TAIL_BYTES and lines:
        lines = lines[1:]  # the first line of a mid-file seek is a fragment
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("type") != "user":
            continue
        if entry.get("isMeta") or entry.get("isSidechain"):
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
            return text[:MAX_REQUEST_CHARS]
    return ""


def canonical_verdict(saipen_root: Path, project: Path, text: str, request: str) -> dict | None:
    """The canonical authority's verdict, or None when it cannot be had."""
    args = [
        "response",
        "check",
        "--stdin",
        "--json",
        "--classify",
        "--auto-eligibility",
        "--project-root",
        str(project),
    ]
    if request:
        args.extend(["--request", request])
    try:
        payload = _run_engine(saipen_root, project, args, stdin=text, timeout=CHECK_TIMEOUT_SECONDS)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if payload is None or not isinstance(payload.get("ok"), bool):
        return None
    return payload


def correction_reason(klass: str, errors: list[str], project: Path) -> str:
    """The continuation prompt that requires correction through the authority."""
    checker = (
        "`saipen response check --stdin --classify --auto-eligibility "
        f"--project-root {project}`"
    )
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


def handle_prompt(saipen_root: Path, project: Path) -> int:
    """Inject the generated chat contract before the reply is written."""
    try:
        payload = _run_engine(
            saipen_root,
            project,
            ["response", "style", "--json"],
            stdin=None,
            timeout=CONTEXT_TIMEOUT_SECONDS,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0
    context = payload.get("context") if payload else None
    if not isinstance(context, str) or not context.strip():
        return 0
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": context,
                }
            }
        )
    )
    return 0


def handle_stop(saipen_root: Path, project: Path, event: dict) -> int:
    reentry = event.get("stop_hook_active") is True
    text = event.get("last_assistant_message")
    if not isinstance(text, str):
        record(BOUNDARY_UNAVAILABLE.format(reason="Stop event has no last_assistant_message text"))
        return 0
    verdict = canonical_verdict(
        saipen_root, project, text, last_human_request(event.get("transcript_path"))
    )
    if verdict is None:
        record(
            BOUNDARY_UNAVAILABLE.format(
                reason="canonical response checker unreachable or its output invalid"
            )
        )
        return 0
    if verdict.get("ok") is True:
        # VALID_BOUNDARY or ORDINARY_CHAT: nothing to intercept.
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
    raw_errors = verdict.get("errors")
    errors = [str(item) for item in raw_errors][:3] if isinstance(raw_errors, list) else []
    if reentry:
        record(BOUNDARY_REENTRY.format(klass=klass, errors="; ".join(errors)))
        return 0
    print(json.dumps({"decision": "block", "reason": correction_reason(klass, errors, project)}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("claude",), required=True)
    parser.add_argument("--saipen-root", type=Path, required=True)
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
    if name not in ("Stop", "UserPromptSubmit"):
        # Not a supported event: this transport gates nothing.
        return 0
    project = project_root(event.get("cwd") or os.getcwd())
    if project is None:
        if os.environ.get("SAIPEN_PROJECT_ROOT", "").strip():
            record(
                BOUNDARY_UNAVAILABLE.format(
                    reason="explicit SAIPEN_PROJECT_ROOT is not a bound SAIPEN project"
                )
            )
        # No SAIPEN project: ordinary non-operational chat.
        return 0
    if name == "UserPromptSubmit":
        return handle_prompt(args.saipen_root, project)
    return handle_stop(args.saipen_root, project, event)


if __name__ == "__main__":
    raise SystemExit(main())
