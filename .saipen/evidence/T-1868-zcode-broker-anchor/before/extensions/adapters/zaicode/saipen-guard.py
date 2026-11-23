"""ZAICODE transport for authenticated operator ingress.

This artifact is the host's own hook: it mints nothing itself. For an operator
event it asks the separated SAIPEN host-authority broker to seal an
`operator_origin`, binds that origin to the delivered ingress envelope, and
writes the envelope into the engine's ingress cache. A model can write the same
bytes; it cannot produce a broker-sealed origin.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

MAX_BYTES = 256 * 1024


def project_root(cwd: str | None) -> Path | None:
    if not cwd:
        return None
    try:
        start = Path(cwd).resolve()
    except OSError:
        return None
    for node in (start, *start.parents):
        if (node / ".saipen" / "STATE.md").is_file():
            return node
    return None


def _declared_ingress(event: dict) -> dict | None:
    """The ingress this event delivers, or None when it carries no request.

    ZCODE sends `prompt` on its `UserPromptSubmit` hook input
    (`createCompatibleHookStdin` in the CLI's `configured-runner-input`), never
    a `host_ingress` key. Reading only that key meant every real operator
    message was dropped here with `ingress_id: null` -- the hook ran, answered
    green, and sealed nothing, so the engine saw no operator carrier and
    recorded the operator's own words as `model_supplied`. That is why a
    bounded run kept demanding reauthorization the operator had already given.

    A declared envelope is still honoured first and unchanged: something that
    carries one says what its own fields are. Everything else is built from the
    host's fields, and the DIGEST is computed with the engine's own
    `ingress_digest`, so the admission path recomputes exactly the value that
    was declared instead of rejecting a format the hook invented.
    """
    declared = event.get("host_ingress")
    if isinstance(declared, dict):
        return declared

    name = event.get("hook_event_name") or event.get("hookEventName")
    if name != "UserPromptSubmit":
        return None
    prompt = event.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return None
    if len(prompt.encode("utf-8")) > MAX_BYTES:
        return None

    tools = None
    for entry in sys.path:
        candidate = Path(entry)
        if (candidate / "saipen_engine" / "pending_ingress.py").is_file():
            tools = candidate
            break
    if tools is None:
        return None
    try:
        from saipen_engine.pending_ingress import ingress_digest
    except Exception:
        return None

    envelope = {
        "request_text": prompt,
        "request_digest": ingress_digest(prompt),
    }
    session = event.get("session_id") or event.get("sessionId")
    if isinstance(session, str) and session:
        envelope["session_id"] = session
    # A host turn id names THIS delivery; two sends of the same words are two
    # deliveries, and the engine keys its cache on the message, not the text.
    for key in ("turnId", "turn_id", "traceId", "trace_id"):
        value = event.get(key)
        if isinstance(value, str) and value:
            envelope["message_id"] = value
            break
    return envelope


def read_command_line(argv: list[str] | None = None) -> tuple[argparse.Namespace, str | None]:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--host", nargs="?")
    parser.add_argument("--saipen-root", type=Path, nargs="?")
    parser.add_argument("--home", type=Path, nargs="?")
    parser.add_argument("--self-test", action="store_true")
    try:
        args, unread = parser.parse_known_args(argv)
    except SystemExit as exc:
        ns = argparse.Namespace(host=None, saipen_root=None, home=None, self_test=False, unread=0)
        return ns, f"hook command line: {exc}"
    args.unread = len(unread)
    if args.host not in (None, "zaicode"):
        return args, f"hook command line names host {args.host!r}; this artifact serves zaicode"
    if args.self_test:
        return args, None
    if args.saipen_root is None:
        return args, "hook command line names no --saipen-root"
    return args, None


def main() -> int:
    args, fault = read_command_line()
    if fault:
        print(json.dumps({"ok": False, "code": "HOOK_COMMAND_FAULT", "detail": fault}))
        return 0
    if getattr(args, "self_test", False):
        return 0

    try:
        event = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        event = {}
    if not isinstance(event, dict):
        event = {}

    host = str(args.host or "zaicode")
    root = args.saipen_root
    home = args.home

    if root is not None:
        tools = root / "tools"
        if str(tools) not in sys.path:
            sys.path.insert(0, str(tools))

    project = project_root(event.get("cwd") if isinstance(event.get("cwd"), str) else None)
    if project is None:
        print(json.dumps({"ok": False, "code": "PROJECT_UNBOUND", "detail": "no SAIPEN project for this event"}))
        return 0

    session = event.get("session_id")
    if not isinstance(session, str) or not session:
        session = event.get("sessionId")
    session = str(session or "")

    ingress = event.get("host_ingress")
    if not isinstance(ingress, dict):
        print(json.dumps({"ok": True, "ingress_id": None, "sealed": False}))
        return 0
    if ingress is None:
        print(json.dumps({"ok": True, "ingress_id": None, "sealed": False}))
        return 0

    text = str(ingress.get("request_text") or "")
    message_id = str(ingress.get("message_id") or "")
    action = "continue"

    try:
        from saipen_engine import host_authority_client as HAC
        from saipen_engine import operator_task
    except Exception as exc:
        print(json.dumps({"ok": False, "code": "ENGINE_UNREACHABLE", "detail": f"runtime import failed: {type(exc).__name__}"}))
        return 0

    origin = None
    sealed = False
    worker_result = None
    try:
        origin = HAC.issue_operator_origin(
            project=project,
            session=session,
            host=host,
            request_text=text,
            event_id=message_id,
            action=action,
            home=home,
        )
    except Exception as exc:
        origin = {"ok": False, "code": "ENGINE_UNREACHABLE", "detail": f"{type(exc).__name__}"}

    if isinstance(origin, dict) and origin.get("ok") is True:
        sealed = True
        try:
            worker = os.getppid()
            worker_result = HAC.register_operator_worker(origin, worker, home=home)
            if not (isinstance(worker_result, dict) and worker_result.get("ok") is True):
                sealed = False
        except Exception as exc:
            sealed = False
            worker_result = {"ok": False, "code": "ENGINE_UNREACHABLE", "detail": f"{type(exc).__name__}"}

    envelope = dict(ingress)
    if sealed and isinstance(origin, dict):
        envelope["operator_origin"] = origin

    try:
        result = operator_task.admit_host_ingress(envelope, project, event_session=session or None)
    except Exception as exc:
        print(json.dumps({"ok": False, "code": "ENGINE_UNREACHABLE", "detail": f"admit failed: {type(exc).__name__}"}))
        return 0

    if not isinstance(result, dict):
        result = {"ok": False, "code": "ENGINE_UNREACHABLE", "detail": "no admission answer"}
    result["sealed"] = sealed
    if sealed and isinstance(origin, dict):
        result["operator_origin"] = origin
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
