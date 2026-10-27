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
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path

MAX_BYTES = 256 * 1024
#: The host gives a hook 30s and replaces the turn on timeout. A renewal that
#: cannot answer inside this budget is reported, never waited past.
RENEWAL_TIMEOUT = 20.0
HOOK_WORK_BUDGET = 27.0

#: What a transport failure kind means for the human reading the hook's answer
#: (SRC-324 A04): an absent service is repaired by starting it, an endpoint
#: served by an impostor is NEVER replaced -- the endpoint, not the start, is
#: the problem.
_FAULT_CLASS = {
    "absent": ("unavailable", "no broker service is listening on the endpoint"),
    "timeout": ("unavailable", "the broker did not answer inside the hook budget"),
    "io": ("unavailable", "the broker endpoint closed during the exchange"),
    "frame": ("unavailable", "the broker answered outside the frame contract"),
    "bind": ("conflict", "another process holds the broker endpoint"),
    "impostor": ("untrusted", "the endpoint failed server identity verification"),
}


def seal_diagnostic(origin, fault, worker_result, worker_fault, sealed: bool) -> dict:
    """Typed, non-secret answer for the SEALING half of this hook (SRC-324 A01).

    The measured incident shipped `ok: true, sealed: false`: the hook tried to
    staple an operator origin onto the envelope, failed, and printed the
    admission answer as if nothing had gone wrong -- so the operator saw a
    genuine prompt recorded as `model_supplied` with no clue which stage broke.

    Stages are distinct (A03): `issue-origin` is the broker declining to mint a
    proof, `register-worker` is a minted proof whose worker binding was refused.
    Categories separate an unavailable service from a responding broker that
    refused identity (A04), and an authenticated proof from its persistence
    in the envelope (A05). Nothing here is a secret and nothing here grants
    authority: the engine still owns admission.
    """
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
            category = "refused" if isinstance(recovery, dict) and recovery.get("state") == "not_a_host_client" else category
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
            # The broker ANSWERED and refused: its own exact code is kept (A02).
            code = str(reply["code"])
            category = "refused"
        else:
            code = f"{prefix}_UNREACHABLE"
            category = "unavailable"
        answer = {"ok": False, "stage": stage, "code": code,
                  "category": category, "detail": detail}
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


#: The registry row this hook reads: which declared shortcuts mean "enter a goal".
_GOAL_ROUTE = "saipen goal"

#: Used only when the runtime's own shortcut table cannot be read. `gg` is the
#: one stable spelling of the goal command; the table is authoritative whenever
#: it loads, and this is the fallback for a runtime too old to export it.
_GOAL_SHORTCUTS = frozenset({"gg"})

#: The closed capsule marker `goal_authority.parse_capsule` documents. A grant
#: is that exact document, never prose that happens to mention authorization.
_CAPSULE_KIND = "saipen-goal-continuation"

#: Host command sigils this hook understands as PREFIXES around a protocol
#: command (`/goal cc all` is the native spelling of `saipen cc all`).
_HOST_WRAPPERS = ("saipen", "goal")


def _goal_shortcut(token: str, root: Path | None) -> bool:
    """Is this whole token a DECLARED shortcut whose route is the goal command?

    The registry is the only authority (CMD-ROUTING-01): the token is folded by
    the engine's own normalizer and looked up exactly. No word list here, so a
    new spelling of the goal command needs no edit in this file.
    """
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
    """The objective when this operator text is UNAMBIGUOUSLY a goal entry.

    SRC-339 R001/R002. The hook sealed `action = "continue"` for every prompt,
    so `operator_origin` -- which reserves goal authority for `goal`/
    `authorize-goal` only -- could never mint a persistent grant for a ZAICODE
    operator. Every 20 tickets the valve therefore tripped into `hard_wait`
    demanding another manual cc, and the persistent-grant route was unreachable.

    The action is read from the operator's OWN bytes: the same `request_text`
    the broker hashes into `request_digest`. Nothing here reads a caller-named
    intent field, so a model cannot ask for a seal it was not handed.

    The accepted shapes cannot be prose:

    * `gg <objective>` -- a declared goal shortcut, never an English word;
    * `saipen goal <objective>` / `saipen gg <objective>` -- canonical form;
    * `/goal gg <objective>` / `/saipen goal <objective>` -- host syntax.

    A bare `goal <words>` is NOT one: "goal of this task is X" is prose, and
    reading it as a pivot would demote live Work on an operator's sentence.
    Neither is `/goal cc all`, which `host_command_body` reads as `cc all` --
    the native spelling of the continuation, which must stay `continue`.

    SRC-342 R002: this now delegates to `cold_recovery.goal_objective_text`,
    the same function the broker calls to choose what a goal proof binds. A
    second copy here was two parsers drifting apart, and they already had: the
    hook extracted `cc all` correctly while the broker hashed the raw
    `gg cc all`, so `prepare_goal` could never match the reserved target. The
    local grammar below stays as the fallback for a runtime too old to import
    the canonical one; it is never reached when the engine loads.
    """
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
            text, protocol_dir=registry if registry and (registry / "REGISTRY.json").is_file() else None
        )
    except Exception:
        pass
    return _goal_objective_local(text, root)


def _goal_objective_local(text: str, root: Path | None = None) -> str | None:
    """The fallback grammar, byte-identical in meaning to the canonical one.

    SRC-342 section 4: a multiline body is a document, not a command, so it is
    never promoted -- not even when its first line is `gg <words>`.
    """
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
            body = body[len(wrapper):].strip()
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
        # Bare `gg` / `saipen goal` is the protocol's own zero-write refusal
        # ("Use: gg <objective>"), not a goal entry to seal.
        return None
    if head.lower() == "goal" and (canonical or aliased):
        # `saipen goal authorize --file <capsule>` is the CLI's own documented
        # authorization spelling, an authorization rather than an entry. Sealing
        # it as a goal named after the flag string is the defect the canonical
        # parser now refuses upstream.
        if rest[0].lower() == "authorize":
            return None
        return " ".join(rest)
    if _goal_shortcut(head, root):
        return " ".join(rest)
    return None


def _grant_file(text: str) -> str | None:
    """The capsule path an operator named, when the text is the CLI's own form.

    Section 4 lists `saipen goal authorize --file <capsule>` as one of the
    three native actions that must classify correctly. Before this, it fell
    through to the goal branch and was sealed as a NEW goal whose objective was
    the literal string `authorize --file <path>` -- a grant turned into an
    entry, with the capsule never verified.

    Returns the path only; the bytes are read by the caller and validated by
    `operations.authorize_goal_continuation`, so this is classification and
    never proof. A path is a path: an absolute path, a `..` traversal or a
    path outside the project is refused here rather than handed to a reader.
    """
    compact = " ".join(str(text or "").split())
    aliased = compact.startswith("/")
    body = compact[1:].strip() if aliased else compact
    for wrapper in _HOST_WRAPPERS:
        if body.lower().startswith(wrapper + " "):
            body = body[len(wrapper):].strip()
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
    """True when this text IS an exact goal-authorization capsule.

    A capsule is a closed self-describing document, so nothing else can be
    mistaken for one. Shape only: the broker still parses it and requires it to
    equal `goal_authority.current_binding`, so a capsule naming any other goal
    is refused there rather than trusted here.
    """
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
    """The one action this operator text declares, from the closed set.

    `operator_origin.ACTIONS` is the broker's set; this hook declares only
    these three. Anything not provably a grant or a goal entry stays the
    continuation it already was, so the safety valve keeps tripping for a run
    that never asked for persistence.
    """
    if _grant_capsule(text):
        return "authorize-goal"
    if _grant_file(text) is not None:
        return "authorize-goal"
    if _goal_objective(text, root) is not None:
        return "goal"
    return "continue"


def grant_capsule_text(text: str, project: Path) -> str | None:
    """The capsule BYTES this operator text authorizes, or None.

    Two spellings name a grant: the capsule document itself pasted as the
    message, and the CLI's `saipen goal authorize --file <path>`. Both must end
    at the same place -- the exact bytes compared against
    `goal_authority.current_binding` -- so this is the ONE resolver for both.
    The path form is read here, from the project root, and the bytes are never
    rewritten; a missing or unreadable file yields None, which the caller
    reports rather than turning into a different action.
    """
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
    """Does this project's own STATE hold a spent bounded run? Read-only."""
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
    """Run the canonical engine from THIS hook and read its one JSON answer.

    The broker binds a proof to the OS worker that registered it and accepts a
    verifier only BELOW that worker. A model's shell tool call is the hook's
    sibling, not its child, so `saipen` run by the agent can never consume this
    seal -- measured: the same proof verifies from a child of the hook and is
    refused from a sibling. The engine started here is the one shape the kernel
    allows ("below the hook only the engine it started").

    A refusal code is prefixed per caller (`RENEWAL_*`, `GOAL_*`) so a reader
    can tell WHICH command the hook could not complete.
    """
    entry = root / "tools" / "saipen.py"
    if not entry.is_file():
        return {"ok": False, "code": f"{prefix}_UNAVAILABLE", "detail": "no engine entry point"}
    remaining = (deadline - time.monotonic()) if deadline is not None else (
        timeout if timeout is not None else RENEWAL_TIMEOUT
    )
    if remaining <= 0:
        return {"ok": False, "code": f"{prefix}_TIMEOUT", "detail": "hook callback budget exhausted"}
    try:
        proc = subprocess.run(
            [sys.executable, str(entry), *argv, "--json", "--project-root", str(project)],
            cwd=str(project), capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=min(RENEWAL_TIMEOUT, remaining),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "code": f"{prefix}_UNAVAILABLE", "detail": type(exc).__name__}
    # The canonical engine pretty-prints, so its answer spans many lines and a
    # line-by-line scan finds nothing to parse. Decode the whole stream first
    # and fall back to the last single-line object for any engine that streams.
    text = (proc.stdout or "").strip()
    doc = None
    if text:
        try:
            doc = json.loads(text)
        except ValueError:
            doc = None
    if not isinstance(doc, dict):
        for line in reversed(text.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                candidate = json.loads(line)
            except ValueError:
                continue
            if isinstance(candidate, dict):
                doc = candidate
                break
    if isinstance(doc, dict):
        return {"ok": bool(doc.get("ok")), "code": doc.get("code"), "document": doc}
    return {"ok": False, "code": f"{prefix}_UNREADABLE"}


def _renew(project: Path, root: Path | None, *, deadline: float | None = None) -> dict | None:
    """Complete the operator's cc from the engine THIS hook starts."""
    if root is None:
        return None
    if not (root / "tools" / "saipen.py").is_file():
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
    """Enter the goal this hook just sealed, from the hook's own child engine.

    The seal is only real if something below the registered worker spends it;
    that is the same constraint `_renew` exists for. The engine is handed the
    operator's EXACT bytes, because the broker's reserved `goal_ingress` is
    derived from the text it hashed -- a reworded objective could not match it.
    """
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
    """Authorize the existing goal with the capsule this hook just sealed.

    `saipen goal authorize` reads the capsule from a FILE, so the exact operator
    bytes are staged beside the project and removed whatever happens. Nothing is
    rewritten: the digest the broker verifies is of these unmodified bytes.
    """
    import tempfile

    handle = tempfile.NamedTemporaryFile(
        "wb", prefix="saipen-grant-", suffix=".json", delete=False
    )
    try:
        handle.write(text.encode("utf-8"))
        handle.close()
        reply = _engine_reply(
            project, root, ["goal", "authorize", "--file", handle.name],
            deadline=deadline, prefix="GRANT",
        )
    finally:
        with suppress(OSError):
            Path(handle.name).unlink()
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
    deadline = time.monotonic() + HOOK_WORK_BUDGET
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

    ingress = _declared_ingress(event)
    if ingress is None:
        print(json.dumps({"ok": True, "ingress_id": None, "sealed": False}))
        return 0

    text = str(ingress.get("request_text") or "")
    message_id = str(ingress.get("message_id") or "")
    action = declared_action(text, root)

    try:
        from saipen_engine import host_authority_client as HAC
        from saipen_engine import operator_task
    except Exception as exc:
        print(json.dumps({"ok": False, "code": "ENGINE_UNREACHABLE", "detail": f"runtime import failed: {type(exc).__name__}"}))
        return 0

    origin = None
    fault = None
    sealed = False
    worker_result = None
    worker_fault = None
    try:
        origin_res = HAC.issue_operator_origin(
            project=project,
            session=session,
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

    proof = origin.get("proof") if (isinstance(origin, dict) and isinstance(origin.get("proof"), dict)) else origin
    if isinstance(origin, dict) and origin.get("ok") is True and isinstance(proof, dict):
        sealed = True
        try:
            # This hook process, not its parent. ZAICODE spawns a hook from the
            # host's own execution port (`spawn(file, args)` in the host's
            # runner), so `getppid()` IS the host pid -- and the broker refuses
            # exactly that as a worker ("worker is not an observed child of the
            # proven native host"). Registering the host meant sealing failed on
            # every genuine prompt, so the operator's own cc was recorded as
            # `model_supplied` and the valve never cleared.
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
            worker_result = {"ok": False, "code": "ENGINE_UNREACHABLE", "detail": f"{type(exc).__name__}"}

    envelope = dict(ingress)
    if sealed and isinstance(proof, dict):
        envelope["operator_origin"] = proof

    try:
        result = operator_task.admit_host_ingress(envelope, project, event_session=session or None)
    except Exception as exc:
        print(json.dumps({"ok": False, "code": "ENGINE_UNREACHABLE", "detail": f"admit failed: {type(exc).__name__}"}))
        return 0

    if not isinstance(result, dict):
        result = {"ok": False, "code": "ENGINE_UNREACHABLE", "detail": "no admission answer"}
    result["sealed"] = sealed
    # The sealing verdict is its own typed answer (SRC-324 A01-A06). Admission
    # answering ok never proves the origin was sealed: `authenticated` states
    # the broker side, `seal` names the stage and the exact refusal code.
    result["authenticated"] = sealed
    result["seal"] = seal_diagnostic(origin, fault, worker_result, worker_fault, sealed)
    if sealed and isinstance(proof, dict):
        result["operator_origin"] = proof

    # A sealed cc that reached a project with a spent budget is the renewal the
    # operator already gave. Spend it from the engine THIS hook starts, because
    # the broker accepts a verifier only below the worker that registered the
    # proof -- the agent's own shell is that worker's sibling, not its child.
    # Only a continuation: a NEW task enters through `saipen start`, which owns
    # its own receipt path, so renewing here would judge the wrong command.
    if sealed and result.get("destination_op") == "continue" and _valve_tripped(project, root):
        renewal = _renew(project, root, deadline=deadline)
        if renewal is not None:
            result["renewal"] = renewal

    # The same constraint decides the two actions this hook can now declare
    # (SRC-339). Sealing `goal`/`authorize-goal` without spending them from
    # BELOW the registered worker would leave a proof nothing in the session
    # can ever verify: the broker refuses the agent's sibling shell. So the
    # hook completes exactly the command the operator's own bytes named, and
    # reports it under its own key so a reader can tell it apart from admission.
    if sealed and root is not None and action == "goal":
        objective = _goal_objective(text, root)
        if objective:
            result["goal_entry"] = _spend_goal(project, root, objective, deadline=deadline)
    elif sealed and root is not None and action == "authorize-goal":
        capsule = grant_capsule_text(text, project)
        if capsule is None:
            result["goal_authorization"] = {
                "ok": False,
                "code": "GRANT_CAPSULE_UNREADABLE",
                "detail": "the named capsule file is missing, escapes the project, "
                          "or is not UTF-8 JSON; nothing was authorized",
            }
        else:
            result["goal_authorization"] = _spend_grant(
                project, root, capsule, deadline=deadline
            )

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
