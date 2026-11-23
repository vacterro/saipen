"""Antigravity CLI (agy.exe) native transport for SAIPEN host authority.

This artifact is the host's own hook: it mints nothing itself. For an operator
event (PreInvocation) it asks the separated SAIPEN host-authority broker to seal an
`operator_origin`, binds that origin to the delivered ingress envelope, and
writes the envelope into the engine's ingress cache. A model can write the same
bytes; it cannot produce a broker-sealed origin.

Supports all native Antigravity lifecycle hooks:
- PreInvocation: gates user prompts, mints operator origin, executes pending continue/goal
- SessionStart: invalidates stale session capability
- PreToolUse: evaluates tool execution permissions
- PostToolUse: tool completion telemetry
- PostInvocation: turn completion telemetry
- Stop: loop termination boundary
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path

MAX_BYTES = 256 * 1024
RENEWAL_TIMEOUT = 20.0
HOOK_WORK_BUDGET = 27.0

_FAULT_CLASS = {
    "absent": ("unavailable", "no broker service is listening on the endpoint"),
    "timeout": ("unavailable", "the broker did not answer inside the hook budget"),
    "io": ("unavailable", "the broker endpoint closed during the exchange"),
    "frame": ("unavailable", "the broker answered outside the frame contract"),
    "bind": ("conflict", "another process holds the broker endpoint"),
    "impostor": ("untrusted", "the endpoint failed server identity verification"),
}


def seal_diagnostic(origin, fault, worker_result, worker_fault, sealed: bool) -> dict:
    """Typed, non-secret answer for the SEALING half of this hook."""
    if sealed:
        return {
            "ok": True,
            "stage": "sealed",
            "code": "SEALED",
            "category": "authenticated",
            "detail": "broker-sealed origin bound to a registered worker",
        }

    def refusal(stage: str, reply, transport_fault: str | None) -> dict:
        prefix = "ORIGIN" if stage == "issue-origin" else "WORKER"
        category, detail = _FAULT_CLASS.get(
            str(transport_fault or ""), ("refused", "the broker refused this request")
        )
        recovery = reply.get("recovery") if isinstance(reply, dict) else None
        if isinstance(reply, dict) and reply.get("code") and transport_fault != "impostor":
            code = str(reply["code"])
            category = (
                "refused"
                if isinstance(recovery, dict) and recovery.get("state") == "not_a_host_client"
                else category
            )
            if isinstance(reply.get("detail"), str):
                detail = reply["detail"]
            elif isinstance(recovery, dict) and isinstance(recovery.get("detail"), str):
                detail = recovery["detail"]
        elif transport_fault in ("absent", "timeout", "io", "frame"):
            code = f"{prefix}_SERVICE_UNAVAILABLE"
        elif transport_fault == "bind":
            code = f"{prefix}_ENDPOINT_CONFLICT"
        elif transport_fault == "impostor":
            code = f"{prefix}_ENDPOINT_UNTRUSTED"
        elif transport_fault:
            code = f"{prefix}_TRANSPORT_{str(transport_fault).upper()}"
        elif isinstance(reply, dict) and reply.get("code"):
            code = str(reply["code"])
            category = "refused"
        else:
            code = f"{prefix}_UNREACHABLE"
            category = "unavailable"
        answer = {"ok": False, "stage": stage, "code": code, "category": category, "detail": detail}
        if isinstance(recovery, dict):
            answer["recovery"] = recovery
        return answer

    if not (isinstance(origin, dict) and origin.get("ok") is True):
        return refusal("issue-origin", origin, fault)
    if not (isinstance(worker_result, dict) and worker_result.get("ok") is True):
        return refusal("register-worker", worker_result, worker_fault)
    return {
        "ok": False,
        "stage": "envelope",
        "code": "ENVELOPE_NOT_SEALED",
        "category": "refused",
        "detail": "proof authenticated but was not bound to the delivered envelope",
    }


def _launcher_text(root: Path | None) -> str:
    if root is not None and (root / "tools" / "saipen.py").is_file():
        return f'python "{root / "tools" / "saipen.py"}"'
    return "saipen"


def _seal_notice(seal: object) -> dict:
    seal = seal if isinstance(seal, dict) else {}
    code = str(seal.get("code") or "ORIGIN_UNREACHABLE")
    stage = str(seal.get("stage") or "issue-origin")
    category = str(seal.get("category") or "unavailable")
    detail = str(seal.get("detail") or "the broker could not seal this prompt")
    recovery = seal.get("recovery") if isinstance(seal.get("recovery"), dict) else {}
    log = recovery.get("log")
    notice = (
        f"SAIPEN: this prompt was NOT authenticated ({code}, {category}, stage {stage}). "
        f"{detail} It was recorded as model_supplied, so a bounded run will still ask for "
        "authorization."
    )
    if isinstance(log, str) and log:
        notice += f" Service log: {log}"
    notice += " Do this: saipen host doctor"
    return {"systemMessage": notice, "additionalContext": notice}


def project_root(cwd: str | None = None, workspace_paths: list[str] | None = None) -> Path | None:
    candidates: list[str] = []
    if workspace_paths and isinstance(workspace_paths, list):
        for p in workspace_paths:
            if isinstance(p, str) and p:
                candidates.append(p)
    if cwd:
        candidates.append(cwd)
    candidates.append(os.getcwd())
    for item in candidates:
        try:
            start = Path(item).resolve()
        except OSError:
            continue
        for node in (start, *start.parents):
            if (node / ".saipen" / "STATE.md").is_file():
                return node
    return None


def _declared_ingress(event: dict) -> dict | None:
    declared = event.get("host_ingress")
    if isinstance(declared, dict):
        return declared

    prompt = event.get("lastUserInput")
    if not isinstance(prompt, str) or not prompt.strip():
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
    session = event.get("conversationId") or event.get("session_id") or event.get("sessionId")
    if isinstance(session, str) and session:
        envelope["session_id"] = session
    for key in ("turnId", "turn_id", "traceId", "trace_id", "invocationNum"):
        value = event.get(key)
        if value is not None and str(value):
            envelope["message_id"] = str(value)
            break
    return envelope


_GOAL_ROUTE = "saipen goal"
_GOAL_SHORTCUTS = frozenset({"gg"})
_CAPSULE_KIND = "saipen-goal-continuation"
_HOST_WRAPPERS = ("saipen", "goal")


def _goal_shortcut(token: str, root: Path | None) -> bool:
    if root is not None:
        tools = root / "tools"
        if str(tools) not in sys.path:
            sys.path.insert(0, str(tools))
    try:
        from saipen_engine.commands import load_shortcut_table, resolve_shortcut

        table = load_shortcut_table()
        key = resolve_shortcut(token, table=table)
        return key is not None and table.get(key) == _GOAL_ROUTE
    except Exception:
        return token.strip().lower() in _GOAL_SHORTCUTS


def _goal_objective(text: str, root: Path | None = None) -> str | None:
    if root is not None:
        tools = root / "tools"
        if str(tools) not in sys.path:
            sys.path.insert(0, str(tools))
        registry = root / "saipen"
    else:
        registry = None
    try:
        from saipen_engine.cold_recovery import goal_objective_text

        return goal_objective_text(
            text,
            protocol_dir=registry if registry and (registry / "REGISTRY.json").is_file() else None,
        )
    except Exception:
        pass
    return _goal_objective_local(text, root)


def _goal_objective_local(text: str, root: Path | None = None) -> str | None:
    raw = str(text or "")
    if len([line for line in raw.splitlines() if line.strip()]) > 1:
        return None
    compact = " ".join(raw.split())
    if not compact:
        return None
    aliased = compact.startswith("/")
    body = compact[1:].strip() if aliased else compact
    if not body:
        return None
    lowered = body.lower()
    for wrapper in _HOST_WRAPPERS:
        if lowered == wrapper:
            return None
        if lowered.startswith(wrapper + " "):
            body = body[len(wrapper) :].strip()
            aliased = True
            break
    if not body:
        return None
    tokens = body.split()
    canonical = False
    if tokens[0].lower() == "saipen":
        tokens = tokens[1:]
        canonical = True
        if not tokens:
            return None
    head, rest = tokens[0], tokens[1:]
    if not rest:
        return None
    if head.lower() == "goal" and (canonical or aliased):
        if rest[0].lower() == "authorize":
            return None
        return " ".join(rest)
    if _goal_shortcut(head, root):
        return " ".join(rest)
    return None


def _grant_file(text: str) -> str | None:
    compact = " ".join(str(text or "").split())
    aliased = compact.startswith("/")
    body = compact[1:].strip() if aliased else compact
    for wrapper in _HOST_WRAPPERS:
        if body.lower().startswith(wrapper + " "):
            body = body[len(wrapper) :].strip()
            aliased = True
            break
    tokens = body.split()
    if len(tokens) == 2 and tokens[0].lower() == "saipen":
        tokens = tokens[1:]
    if len(tokens) != 4 or tokens[0].lower() != "goal":
        return None
    if tokens[1].lower() != "authorize" or tokens[2] != "--file":
        return None
    raw = tokens[3].strip("\"'")
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        return None
    return raw


def _grant_capsule(text: str) -> bool:
    stripped = str(text or "").lstrip()
    if not stripped.startswith("{"):
        return False
    if len(stripped.encode("utf-8")) > MAX_BYTES:
        return False
    try:
        value = json.loads(stripped)
    except ValueError:
        return False
    return isinstance(value, dict) and value.get("kind") == _CAPSULE_KIND


def declared_action(text: str, root: Path | None = None) -> str:
    if _grant_capsule(text):
        return "authorize-goal"
    if _grant_file(text) is not None:
        return "authorize-goal"
    if _goal_objective(text, root) is not None:
        return "goal"
    return "continue"


def grant_capsule_text(text: str, project: Path) -> str | None:
    if _grant_capsule(text):
        return str(text)
    relative = _grant_file(text)
    if relative is None:
        return None
    try:
        path = (project / relative).resolve()
        path.relative_to(project.resolve())
        data = path.read_bytes()
    except (OSError, ValueError):
        return None
    if len(data) > MAX_BYTES:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _valve_tripped(project: Path, root: Path | None) -> bool:
    if root is not None:
        tools = root / "tools"
        if str(tools) not in sys.path:
            sys.path.insert(0, str(tools))
    try:
        from saipen_engine import goal_authority
        from saipen_engine.state import parse_state

        text = (project / ".saipen" / "STATE.md").read_text(encoding="utf-8-sig")
        return bool(goal_authority.budget_exhausted(parse_state(text)))
    except Exception:
        return False


def _engine_reply(
    project: Path,
    root: Path,
    argv: list[str],
    *,
    deadline: float | None,
    prefix: str,
    timeout: float | None = None,
) -> dict:
    entry = root / "tools" / "saipen.py"
    if not entry.is_file():
        return {"ok": False, "code": f"{prefix}_UNAVAILABLE", "detail": "no engine entry point"}
    remaining = (
        (deadline - time.monotonic())
        if deadline is not None
        else (timeout if timeout is not None else RENEWAL_TIMEOUT)
    )
    if remaining <= 0:
        return {
            "ok": False,
            "code": f"{prefix}_TIMEOUT",
            "detail": "hook callback budget exhausted",
        }
    try:
        proc = subprocess.run(
            [sys.executable, str(entry), *argv, "--json", "--project-root", str(project)],
            cwd=str(project),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=min(RENEWAL_TIMEOUT, remaining),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "code": f"{prefix}_UNAVAILABLE", "detail": type(exc).__name__}
    text = (proc.stdout or "").strip()
    doc = None
    if text:
        try:
            doc = json.loads(text)
        except ValueError:
            doc = None
    if not isinstance(doc, dict):
        for raw_line in reversed(text.splitlines()):
            stripped = raw_line.strip()
            if not stripped.startswith("{"):
                continue
            try:
                candidate = json.loads(stripped)
            except ValueError:
                continue
            if isinstance(candidate, dict):
                doc = candidate
                break
    if isinstance(doc, dict):
        return {"ok": bool(doc.get("ok")), "code": doc.get("code"), "document": doc}
    return {"ok": False, "code": f"{prefix}_UNREADABLE"}


def _renew(project: Path, root: Path | None, *, deadline: float | None = None) -> dict | None:
    if root is None or not (root / "tools" / "saipen.py").is_file():
        return None
    reply = _engine_reply(project, root, ["continue"], deadline=deadline, prefix="RENEWAL")
    if "document" not in reply:
        return reply
    doc = reply["document"]
    return {
        "ok": bool(doc.get("ok")),
        "code": doc.get("code"),
        "goal_waves": doc.get("goal_waves"),
        "goal_tickets": doc.get("goal_tickets"),
    }


def _spend_goal(project: Path, root: Path, text: str, *, deadline: float | None) -> dict:
    reply = _engine_reply(project, root, ["goal", text], deadline=deadline, prefix="GOAL")
    if "document" not in reply:
        return reply
    doc = reply["document"]
    return {
        "ok": bool(doc.get("ok")),
        "code": doc.get("code"),
        "ticket": doc.get("ticket"),
        "phase": doc.get("phase"),
        "next_action": doc.get("next_action"),
        "goal_waves": doc.get("goal_waves"),
        "goal_tickets": doc.get("goal_tickets"),
    }


def _spend_grant(project: Path, root: Path, text: str, *, deadline: float | None) -> dict:
    import tempfile

    with tempfile.NamedTemporaryFile(
        "wb", prefix="saipen-grant-", suffix=".json", delete=False
    ) as handle:
        handle.write(text.encode("utf-8"))
        handle_name = handle.name
    try:
        reply = _engine_reply(
            project,
            root,
            ["goal", "authorize", "--file", handle_name],
            deadline=deadline,
            prefix="GRANT",
        )
    finally:
        with suppress(OSError):
            Path(handle_name).unlink()
    if "document" not in reply:
        return reply
    doc = reply["document"]
    return {
        "ok": bool(doc.get("ok")),
        "code": doc.get("code"),
        "authority_source": doc.get("authority_source"),
        "authorization_receipt": doc.get("authorization_receipt"),
    }


def read_command_line(argv: list[str] | None = None) -> tuple[argparse.Namespace, str | None]:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--host", nargs="?", default="antigravity")
    parser.add_argument("--saipen-root", type=Path, nargs="?")
    parser.add_argument("--home", type=Path, nargs="?")
    parser.add_argument("--event", type=str, nargs="?")
    parser.add_argument("--self-test", action="store_true")
    try:
        args, unread = parser.parse_known_args(argv)
    except SystemExit as exc:
        ns = argparse.Namespace(
            host="antigravity", saipen_root=None, home=None, event=None, self_test=False, unread=0
        )
        return ns, f"hook command line: {exc}"
    args.unread = len(unread)
    if args.host not in (None, "antigravity"):
        return args, f"hook command line names host {args.host!r}; this artifact serves antigravity"
    if args.self_test:
        return args, None
    if args.saipen_root is None:
        return args, "hook command line names no --saipen-root"
    return args, None


def detect_event(event: dict, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    name = event.get("hook_event_name") or event.get("hookEventName") or event.get("event")
    if name:
        return str(name)
    if "terminationReason" in event or "executionNum" in event:
        return "Stop"
    if "toolCall" in event:
        if "result" in event or "error" in event or "overwriteResult" in event:
            return "PostToolUse"
        return "PreToolUse"
    if "modelOutput" in event or "modelThinking" in event:
        return "PostInvocation"
    if "invocationNum" in event or "initialNumSteps" in event:
        return "PreInvocation"
    return "SessionStart"


def main() -> int:
    deadline = time.monotonic() + HOOK_WORK_BUDGET
    args, fault = read_command_line()
    if getattr(args, "self_test", False):
        print(json.dumps({"ok": True, "self_test": True}))
        return 0
    if fault:
        if "names host" in str(fault):
            print(f"SAIPEN_GUARD_REFUSAL: FORGED_HOST_IDENTITY: {fault}", file=sys.stderr)
            return 2
        print(
            json.dumps(
                {"ok": False, "code": "HOOK_COMMAND_FAULT", "detail": fault, "injectSteps": []}
            )
        )
        return 0

    try:
        event = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        event = {}
    if not isinstance(event, dict):
        event = {}

    host = "antigravity"
    root = args.saipen_root
    home = args.home
    explicit_event = args.event

    if root is not None:
        tools = root / "tools"
        if str(tools) not in sys.path:
            sys.path.insert(0, str(tools))

    detected_event = detect_event(event, explicit_event)

    # Resolve project root: check workspacePaths, cwd, or process cwd
    wp = event.get("workspacePaths")
    cwd = event.get("cwd") if isinstance(event.get("cwd"), str) else None
    project = project_root(cwd, wp if isinstance(wp, list) else None)

    # Outside SAIPEN project: stay silent / exit 0
    if project is None:
        return 0

    session = event.get("conversationId") or event.get("session_id") or event.get("sessionId") or ""

    # Event dispatch
    if detected_event == "SessionStart":
        try:
            from saipen_engine import host_authority_client as HAC

            HAC.invalidate(project=project, session=str(session), host=host, home=home)
        except Exception:
            pass
        print(json.dumps({"injectSteps": []}))
        return 0

    if detected_event == "PreToolUse":
        tool_call = event.get("toolCall") if isinstance(event.get("toolCall"), dict) else {}
        tool_name = str(tool_call.get("name") or "")
        read_tools = {
            "view_file",
            "view_file_outline",
            "view_code_item",
            "view_content_chunk",
            "grep_search",
            "list_directory",
            "code_search",
            "find",
            "read_url_content",
            "read_terminal",
            "read_resource",
        }
        if tool_name in read_tools:
            print(json.dumps({"decision": "allow"}))
            return 0
        # Mutating tool: Antigravity cannot attest human approval cryptographically
        # (NATIVE_APPROVAL_UNAVAILABLE). Normal execution proceeds:
        print(json.dumps({"decision": "allow"}))
        return 0

    if detected_event == "PostToolUse":
        print(json.dumps({}))
        return 0

    if detected_event == "PostInvocation":
        print(json.dumps({"injectSteps": []}))
        return 0

    if detected_event == "Stop":
        print(json.dumps({"decision": "allow"}))
        return 0

    # Remaining: PreInvocation (or UserPromptSubmit)
    ingress = _declared_ingress(event)
    if ingress is None:
        if event.get("hook_event_name") == "UserPromptSubmit":
            print(json.dumps({"ok": True, "ingress_id": None, "sealed": False}))
        else:
            print(json.dumps({"injectSteps": []}))
        return 0

    text = str(ingress.get("request_text") or "")
    message_id = str(ingress.get("message_id") or "")
    action = declared_action(text, root)

    try:
        from saipen_engine import host_authority_client as HAC
        from saipen_engine import operator_task
    except Exception as exc:
        msg = f"SAIPEN: runtime import failed ({type(exc).__name__}). Proceeding unverified."
        if event.get("hook_event_name") == "UserPromptSubmit":
            print(json.dumps({"ok": False, "code": "ENGINE_UNREACHABLE", "detail": msg}))
        else:
            print(
                json.dumps(
                    {
                        "injectSteps": [
                            {
                                "systemMessage": {
                                    "systemMessage": msg,
                                    "metadata": {"user_markdown": msg},
                                }
                            }
                        ],
                        "terminationBehavior": "",
                    }
                )
            )
        return 0

    origin = None
    fault = None
    sealed = False
    worker_result = None
    worker_fault = None
    try:
        origin_res = HAC.issue_operator_origin(
            project=project,
            session=str(session),
            host=host,
            request_text=text,
            event_id=message_id,
            action=action,
            authority_root=root,
            home=home,
            diagnose=True,
            deadline=deadline,
        )
        if isinstance(origin_res, tuple) and len(origin_res) == 2:
            origin, fault = origin_res
        else:
            origin, fault = origin_res, None
    except Exception as exc:
        origin = {"ok": False, "code": "ENGINE_UNREACHABLE", "detail": f"{type(exc).__name__}"}
        fault = "engine"

    proof = (
        origin.get("proof")
        if (isinstance(origin, dict) and isinstance(origin.get("proof"), dict))
        else origin
    )
    if isinstance(origin, dict) and origin.get("ok") is True and isinstance(proof, dict):
        sealed = True
        try:
            worker = os.getpid()
            reg_res = HAC.register_operator_worker(
                proof, worker, home=home, diagnose=True, deadline=deadline
            )
            if isinstance(reg_res, tuple) and len(reg_res) == 2:
                worker_result, worker_fault = reg_res
            else:
                worker_result, worker_fault = reg_res, None
            if not (isinstance(worker_result, dict) and worker_result.get("ok") is True):
                sealed = False
        except Exception as exc:
            sealed = False
            worker_fault = "engine"
            worker_result = {
                "ok": False,
                "code": "ENGINE_UNREACHABLE",
                "detail": f"{type(exc).__name__}",
            }

    envelope = dict(ingress)
    if sealed and isinstance(proof, dict):
        envelope["operator_origin"] = proof

    try:
        result = operator_task.admit_host_ingress(
            envelope, project, event_session=str(session) or None
        )
    except Exception as exc:
        msg = f"SAIPEN: admission failed ({type(exc).__name__}). Proceeding unverified."
        if event.get("hook_event_name") == "UserPromptSubmit":
            print(json.dumps({"ok": False, "code": "ENGINE_UNREACHABLE", "detail": msg}))
        else:
            print(
                json.dumps(
                    {
                        "injectSteps": [
                            {
                                "systemMessage": {
                                    "systemMessage": msg,
                                    "metadata": {"user_markdown": msg},
                                }
                            }
                        ],
                        "terminationBehavior": "",
                    }
                )
            )
        return 0

    if not isinstance(result, dict):
        result = {"ok": False, "code": "ENGINE_UNREACHABLE", "detail": "no admission answer"}
    result["sealed"] = sealed
    result["authenticated"] = sealed
    seal_info = seal_diagnostic(origin, fault, worker_result, worker_fault, sealed)
    result["seal"] = seal_info
    if sealed and isinstance(proof, dict):
        result["operator_origin"] = proof

    inject_steps: list[dict] = []
    if not sealed:
        notice = _seal_notice(seal_info)["systemMessage"]
        inject_steps.append(
            {"systemMessage": {"systemMessage": notice, "metadata": {"user_markdown": notice}}}
        )

    # If sealed continue reached spent budget, renew it under this worker
    if sealed and result.get("destination_op") == "continue" and _valve_tripped(project, root):
        renewal = _renew(project, root, deadline=deadline)
        if renewal is not None:
            result["renewal"] = renewal

    if sealed and isinstance(result.get("renewal"), dict) and not result["renewal"].get("ok"):
        renewal_code = result["renewal"].get("code") or "no code"
        notice = (
            "SAIPEN: operator cc was sealed but the bounded grant was not renewed "
            f"({renewal_code}). Do this: {_launcher_text(root)} continue"
        )
        inject_steps.append(
            {"systemMessage": {"systemMessage": notice, "metadata": {"user_markdown": notice}}}
        )

    # If sealed goal or authorize-goal, spend under this worker
    if sealed and root is not None and action == "goal":
        objective = _goal_objective(text, root)
        if objective:
            result["goal_entry"] = _spend_goal(project, root, objective, deadline=deadline)
    elif sealed and root is not None and action == "authorize-goal":
        capsule = grant_capsule_text(text, project)
        if capsule is not None:
            result["goal_authorization"] = _spend_grant(project, root, capsule, deadline=deadline)

    # Deliver output
    if event.get("hook_event_name") == "UserPromptSubmit" or event.get("self_test_compat"):
        result["injectSteps"] = inject_steps
        print(json.dumps(result))
    else:
        output = {"injectSteps": inject_steps, "terminationBehavior": ""}
        print(json.dumps(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
