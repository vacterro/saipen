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

Unenforceable moments (unreadable command line, unreadable hook payload,
unreachable checker, no bound project) are recorded the same honest way and
never pretended into a verdict.

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


class CommandLineFault(Exception):
    """This artifact could not read the command line it was started with."""


class _Arguments(argparse.ArgumentParser):
    """argparse reports a bad command line by exiting with status 2, which
    Codex reads as a hook-level failure and repeats forever (T-1630). The
    fault is raised to `main` instead, which records the capability boundary
    and lets the stop complete."""

    def error(self, message: str) -> None:
        raise CommandLineFault(message)


def read_command_line(argv: list[str] | None = None) -> tuple[argparse.Namespace, str | None]:
    """The options, and what is wrong with the command line when something is.

    Never exits: a foreign or missing ``--host``, a missing ``--saipen-root``,
    an argument argparse itself refuses, and an option of another generation
    all come back as one unreadable-command-line fault beside the defaults,
    decided by `main` through `record()`. The normal command line
    (``--host codex --saipen-root <root>``, all this hook is ever configured
    with) returns ``(args, None)`` unchanged.
    """
    parser = _Arguments(description=__doc__, allow_abbrev=False)
    parser.add_argument("--host", nargs="?")
    parser.add_argument("--saipen-root", type=Path, nargs="?")
    try:
        args, unread = parser.parse_known_args(argv)
    except CommandLineFault as exc:
        args = argparse.Namespace(host=None, saipen_root=None)
        return args, "hook command line: " + str(exc).replace("\n", " ")[:200]
    if args.host != "codex":
        return args, f"hook command line names host {args.host!r}; this artifact serves codex"
    if args.saipen_root is None:
        return args, "hook command line names no --saipen-root"
    if unread:
        # An argument of another generation: reading past it would silently
        # treat an invalid command line as valid (T-1630).
        return args, "hook command line: unrecognized option(s): " + " ".join(unread)[:200]
    return args, None


def project_root(cwd: str | None) -> Path | None:
    """The bound SAIPEN project for this Stop, or None.

    An explicit ``SAIPEN_PROJECT_ROOT`` naming a project wins; otherwise the
    nearest ancestor of the session cwd carrying canonical STATE. No project means no SAIPEN
    operational context at all, and the stop is ordinary chat.
    """
    declared = os.environ.get("SAIPEN_PROJECT_ROOT", "").strip()
    if declared:
        try:
            root = Path(declared).resolve()
        except OSError:
            root = None
        if root is not None and (root / ".saipen" / "STATE.md").is_file():
            return root
        # T-1636: a carrier that names nothing usable never hides the project
        # the session directory belongs to. The walk below finds it, and the
        # engine judges the carrier from there (BINDING_CARRIER_INVALID).
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


def preserve_refused(saipen_root: Path, project: Path, text: str) -> str | None:
    """Keep the reply the gate refused before anything corrects it; its reference.

    T-1657: the correction that follows asks for a compact surface, and detail
    written only into the refused reply would otherwise live in a host
    transcript alone. The engine owns the bytes and the overflow account kept
    beside them; this transport only hands the reply over. None when the
    engine cannot keep it: the stop is still handled, and nothing is claimed.
    """
    engine = Path(saipen_root) / "tools" / "saipen.py"
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(engine),
                "response",
                "preserve",
                "--stdin",
                "--json",
                "--project-root",
                str(project),
            ],
            # Bytes both ways, for the reason the checker call above gives.
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=CHECK_TIMEOUT_SECONDS,
            cwd=str(project),
        )
        kept = json.loads((proc.stdout or b"").decode("utf-8", errors="replace") or "null")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    reference = kept.get("ref") if isinstance(kept, dict) and kept.get("ok") is True else None
    return reference if isinstance(reference, str) and reference else None


def correction_reason(klass: str, errors: list[str], project: Path) -> str:
    """The continuation prompt that requires correction through the authority."""
    checker = (
        f"`saipen response check --stdin --classify --auto-eligibility --project-root {project}`"
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
    args, fault = read_command_line()
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
    if fault is not None:
        # The command line itself is unreadable (T-1630): this generation
        # cannot know which root it must enforce, so the exact capability
        # boundary is recorded instead of a guessed verdict -- argparse must
        # never exit 2 here, which Codex reads as a hook failure and repeats.
        # Outside a bound project the transport does nothing, whatever the
        # command line says.
        if project_root(event.get("cwd") or os.getcwd()) is None:
            return 0
        record(BOUNDARY_UNAVAILABLE.format(reason=fault))
        return 0
    reentry = event.get("stop_hook_active") is True
    text = event.get("last_assistant_message")
    if not isinstance(text, str):
        record(BOUNDARY_UNAVAILABLE.format(reason="Stop event has no last_assistant_message text"))
        return 0
    project = project_root(event.get("cwd") or os.getcwd())
    if project is None:
        # No SAIPEN project, whatever a carrier says: ordinary chat (T-1636).
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
    # T-1657: kept BEFORE the correction is requested or the boundary recorded.
    # An admission refusal judges the session, not a reply.
    kept = (
        None
        if klass == "ADMISSION_BLOCKED"
        else preserve_refused(args.saipen_root, project, text)
    )
    kept_note = f" The refused reply is kept at {kept}." if kept else ""
    if reentry:
        record(BOUNDARY_REENTRY.format(klass=klass, errors="; ".join(errors)) + kept_note)
        return 0
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": (
                    f"SAIPEN canonical delivery ({klass}; do not add prose):\n"
                    + verdict["delivery"]
                    if isinstance(verdict.get("delivery"), str) and verdict["delivery"]
                    else correction_reason(klass, errors, project) + kept_note
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
