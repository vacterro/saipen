"""Codex Stop-event transport for the canonical EXEC-RESPONSE-01 gate (T-1551).

No protocol policy and no response schema live here. The supported Codex Stop
event supplies the outgoing final message (``last_assistant_message``); this
file forwards that text to the SAME canonical authority the OpenCode text gate
uses -- ``tools/saipen.py response check --classify --stdin`` -- and maps that
one verdict onto Codex hook output. The four response classes are decided in
``saipen_engine.response_surface``; an adapter that restated them would be a
second response validator.

Stop re-entry is deliberate and bounded. The first invalid stop of a turn
requests exactly ONE correction continuation (``{"decision": "block"}``, which
Codex turns into a continuation prompt). A stop that is already a Stop-hook
continuation (``stop_hook_active``) records the exact capability boundary
instead of requesting another one: Codex continues by injecting a new user
prompt with no finite correction limit, cannot retract the already-rendered
message, and exposes no turn ingress or tool context at Stop, so a second
continuation would be an uncontrolled loop and terminal fail-closed correction
is NOT claimed.

Unenforceable moments (unreadable hook payload, unreachable checker, no bound
project) are recorded the same honest way and never pretended into a verdict.

Trust is an external host boundary: Codex skips non-managed hooks until the
operator reviews and trusts the hash-bound hook definition via ``/hooks``.
This file never marks itself trusted and never edits host trust state.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

MAX_BYTES = 256 * 1024
CHECK_TIMEOUT_SECONDS = 60

#: The exact capability boundary recorded when the one correction round is
#: spent. Kept literal so evidence can cite it verbatim.
BOUNDARY_REENTRY = (
    "SAIPEN_CAPABILITY_BOUNDARY CODEX_STOP_REENTRY_NO_FAIL_CLOSED: this Stop is "
    "already a Stop-hook continuation (stop_hook_active) and the one enforced "
    "correction round for this turn is exhausted. Codex continues by injecting a "
    "new user prompt with no finite correction limit, cannot retract the already "
    "rendered message, and exposes no turn ingress or tool context at Stop; a "
    "second continuation would be an uncontrolled loop. The invalid operational "
    "response is recorded here as unenforced ({klass}: {errors}). Terminal "
    "fail-closed correction is NOT claimed."
)

BOUNDARY_UNAVAILABLE = (
    "SAIPEN_CAPABILITY_BOUNDARY CODEX_STOP_GATE_UNAVAILABLE: the canonical "
    "response checker could not be consulted ({reason}), so the outgoing message "
    "is recorded as unenforced. Installed current hook bytes, host hook trust "
    "(Codex /hooks hash-bound review) and checker reachability are the only "
    "enforcement boundaries; none is claimed stronger."
)


def project_root(cwd: str | None) -> Path | None:
    """The bound SAIPEN project for this Stop, or None.

    Explicit ``SAIPEN_PROJECT_ROOT`` wins; otherwise the nearest ancestor of
    the session cwd carrying canonical STATE. No project means no SAIPEN
    operational context at all, and the stop is ordinary chat.
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


def canonical_verdict(saipen_root: Path, project: Path, text: str) -> dict | None:
    """The canonical authority's verdict, or None when it cannot be had."""
    engine = Path(saipen_root) / "tools" / "saipen.py"
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(engine),
                "response",
                "check",
                "--stdin",
                "--json",
                "--classify",
                "--auto-eligibility",
                "--project-root",
                str(project),
            ],
            # Bytes, not text mode: text mode encodes with the host LOCALE
            # (cp1251 on the operator's Windows host), where an Estonian
            # diacritic does not exist -- the encode raised, the checker was
            # reported unreachable and every such reply passed UNENFORCED.
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=CHECK_TIMEOUT_SECONDS,
            cwd=str(project),
        )
        payload = json.loads((proc.stdout or b"").decode("utf-8", errors="replace") or "")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("ok"), bool):
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
    print(
        json.dumps(
            {
                "continue": True,
                "stopReason": "SAIPEN_STOP_BOUNDARY_UNENFORCED",
                "systemMessage": boundary,
            }
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("codex",), required=True)
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
    if not isinstance(event, dict) or event.get("hook_event_name") != "Stop":
        # Not the supported event: this transport gates nothing.
        return 0
    reentry = event.get("stop_hook_active") is True
    text = event.get("last_assistant_message")
    if not isinstance(text, str):
        record(
            BOUNDARY_UNAVAILABLE.format(
                reason="Stop event has no last_assistant_message text"
            )
        )
        return 0
    project = project_root(event.get("cwd") or os.getcwd())
    if project is None:
        if os.environ.get("SAIPEN_PROJECT_ROOT", "").strip():
            record(
                BOUNDARY_UNAVAILABLE.format(
                    reason="explicit SAIPEN_PROJECT_ROOT is not a bound SAIPEN project"
                )
            )
            return 0
        # No SAIPEN project: ordinary non-operational chat.
        return 0
    verdict = canonical_verdict(args.saipen_root, project, text)
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
        # The authority ran but could not classify (for example canonical
        # status was unavailable). That is not an enforceable verdict.
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
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": correction_reason(klass, errors, project),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
