"""Claude Code transport for protocol admission and the final-response gate.

No protocol policy, no response schema, no style rule and no admission rule live
here. Claude Code hook events are forwarded to the SAME canonical authority the
Codex and OpenCode gates use -- ``tools/saipen.py`` -- and its one verdict is
mapped onto Claude Code hook output. The chain each verdict comes from is
binding, ADMISSION, EXEC-RESPONSE, chat style; a later layer never compensates
for an earlier failure (``saipen_engine.response_surface.gate_final_response``).

T-1563: this same-user transport cannot mint signing authority, and it still
cannot. T-1623 gave the admission events below a separated authority to talk to
instead: the canonical engine asks the SAIPEN host-authority broker, which runs
as its own process, proves from the operating system that the request comes
from this host's own hook invocation, mints a short-lived capability and owns
the ledger write. The hook gains no key, no minting call and no policy of its
own -- it keeps asking `tools/saipen.py` and transports the answer.

T-1624, the one rule this transport DOES hold, because it is the rule about the
engine being unavailable: a hook that cannot run its engine must not take the
host down with it. A missing interpreter, a moved or half-edited runtime, a
timeout or an unreadable answer is `ENGINE_UNREACHABLE`, and what happens next
is the operator's admission policy read from the operator's own file:

* DEGRADED_ALLOWED (the default) -- the prompt proceeds, and both the operator
  and the model are told in plain words that SAIPEN did not answer, that no
  protocol authority was delivered and that nothing is verified;
* STRICT (explicit opt-in) -- the prompt is blocked with the one exact action
  that restores the runtime.

The policy file is read here with the same tiny rule the engine uses
(`host_authority_client.authority_mode`): absent means the default, a
recognized value means itself, and an unreadable or unrecognized file means
STRICT -- a damaged policy is never read as a silent downgrade.

Two more shapes of the same failure are decided by that one rule, because each
was a lockout the policy never saw. An engine answer that is not an admission
verdict (the engine refusing its own command line, or a runtime of another
generation) is an engine that did not answer: read as a verdict, its missing
`permitted` was a refusal with nothing to show the operator. And a command line
this artifact cannot use never ends as an exit status: argparse exits 2, a host
reads 2 from a hook as "block", and a host keeps the command it loaded at start
while the artifact under it changes generation.

Events and what each one can honestly do:

* ``SessionStart`` -- the session is new, resumed, cleared, compacted or forked:
  the context the model held is gone or replaced, so the recorded admission is
  invalidated and the runtime delivers the authority again, in ONE engine call
  (``saipen admission establish --fresh``), as ``additionalContext``.
* ``UserPromptSubmit`` -- the pre-generation boundary. The runtime establishes
  admission and delivers the authority BEFORE the model runs. When the runtime
  REFUSES (a forged capability, a foreign project binding, or any failure under
  STRICT) the prompt is blocked (``decision: block``): the model does not run,
  and the only text that reaches the user is the bounded diagnostic the runtime
  wrote, with its one operator action. A DEGRADED permit proceeds and is marked.
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
``--home``, ``--authority-root`` and ``--runtime`` are diagnostic command-line
flags used by the test carriers. They are never environment variables: the
installed command line is the operator's, and an environment override would be
a way round the gate.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

MAX_BYTES = 256 * 1024
CHECK_TIMEOUT_SECONDS = 45
#: One admission handshake, recovery included (the client's own start budget is
#: a few seconds). It must stay below the hook timeout the installer writes, so
#: this transport -- not the host's kill -- decides what a slow engine means.
ADMISSION_TIMEOUT_SECONDS = 20
# One agentic turn is one human prompt followed by hundreds of tool results, so
# the request can sit megabytes behind the end of the transcript (measured: a 3 MB
# transcript whose only human entry was its first line).
TRANSCRIPT_MAX_BYTES = 64 * 1024 * 1024
MAX_REQUEST_CHARS = 2000

MODE_STRICT = "strict"
MODE_DEGRADED = "degraded"
_MODE_ALIASES = {
    "strict": MODE_STRICT,
    "degraded": MODE_DEGRADED,
    "degraded_allowed": MODE_DEGRADED,
    "degraded-allowed": MODE_DEGRADED,
}
CODE_ENGINE_UNREACHABLE = "ENGINE_UNREACHABLE"

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

#: Shown to the operator AND delivered to the model when the engine did not
#: answer and the policy lets the prompt through. Plain words first, the code
#: and the one action after.
ENGINE_DEGRADED = (
    "SAIPEN is running in degraded mode. Model access works, but the SAIPEN "
    "runtime behind this hook did not answer ({reason}), so no protocol "
    "authority was delivered and host admission is NOT verified "
    "(SAIPEN_ADMISSION_UNVERIFIED, {code}). To restore it run: {action}"
)

ENGINE_BLOCKED = (
    "SAIPEN blocked this prompt: the SAIPEN runtime behind this hook did not "
    "answer ({reason}) and the admission policy is STRICT ({code}). "
    "To restore it run: {action} -- or allow unverified work with: "
    "{launcher} host mode degraded"
)

#: A refusal the engine wrote no diagnostic for still reaches the operator with
#: its code and one action: a block that says nothing is a dead end.
REFUSED_WITHOUT_DIAGNOSTIC = (
    "SAIPEN PROTOCOL ADMISSION REFUSED [{code}] -- the SAIPEN runtime refused "
    "this prompt and gave no diagnostic. Do this: {launcher} host doctor"
)

_SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)
_INIT_COMMAND = re.compile(r"(?i)\bsaipen(?:\.cmd|\.py)?\b[^\n;&|]*\binit\b")
_PROJECT_ROOT_FLAG = re.compile(r"--project-root[ =]+(?:\"([^\"]+)\"|'([^']+)'|(\S+))")
TRANSPORT_ENV = "SAIPEN_ADMISSION_TRANSPORT"


class EngineUnreachable(Exception):
    """The canonical engine could not be run or did not answer in its schema."""


class CommandLineFault(Exception):
    """This artifact could not read the command line it was started with."""


class _Arguments(argparse.ArgumentParser):
    """argparse reports a bad command line by exiting with status 2. The fault
    is raised to `main` instead, which decides it by the operator's policy."""

    def error(self, message: str):
        raise CommandLineFault(message)


def project_root(cwd: str | None) -> Path | None:
    """The bound SAIPEN project for this event, or None.

    An explicit ``SAIPEN_PROJECT_ROOT`` naming a project wins; otherwise the
    nearest ancestor of the session cwd carrying canonical STATE. No project
    means no SAIPEN context at all, and the event is ordinary chat. This is
    only the cheap question "is there a project here at all": whether a
    carrier CONTRADICTS the project is the binding owner's decision, made by
    the engine from the event cwd.
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


def authority_mode(home: Path | None = None) -> str:
    """The operator's admission policy, by the engine's own rule.

    Absent file: the default, DEGRADED_ALLOWED. A recognized value: itself. A
    file that is present and unreadable or unrecognized: STRICT, so a damaged
    policy can never pass for the operator having chosen the weaker one.
    """
    path = (Path(home) if home is not None else Path.home()) / ".saipen" / "authority.json"
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return MODE_DEGRADED
    except OSError:
        return MODE_STRICT
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        return MODE_STRICT
    if not isinstance(payload, dict):
        return MODE_STRICT
    spelling = str(payload.get("mode") or "").strip().lower().replace(" ", "_")
    return _MODE_ALIASES.get(spelling, MODE_STRICT)


def _launcher(saipen_root: Path | None) -> str:
    if saipen_root is None:
        # The command line named no runtime: the logical command is all there is.
        return "saipen"
    name = "saipen.cmd" if os.name == "nt" else "saipen"
    return str(Path(saipen_root) / "bin" / name)


def _one_line(text: object, limit: int = 160) -> str:
    return " ".join(str(text or "").split())[:limit]


def _refusal(verdict: dict, saipen_root: Path | None) -> str:
    """The engine's own diagnostic for a refusal; never nothing."""
    said = str(verdict.get("diagnostic") or "").strip()
    if said:
        return said
    return REFUSED_WITHOUT_DIAGNOSTIC.format(
        code=_one_line(verdict.get("failure") or verdict.get("code") or "UNCLASSIFIED", 60),
        launcher=_launcher(saipen_root),
    )


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
    does not exist, and the encode would raise.

    Raises `EngineUnreachable` with a one-line reason for every way of not
    getting an answer; the caller decides what that means.
    """
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
    engine = Path(saipen_root) / "tools" / "saipen.py"
    if not engine.is_file():
        raise EngineUnreachable(f"runtime not found at {saipen_root}")
    try:
        proc = subprocess.run(
            [sys.executable, str(engine), *args],
            input=stdin.encode("utf-8") if stdin is not None else None,
            capture_output=True,
            timeout=timeout,
            cwd=str(project),
            env=env,
        )
    except subprocess.TimeoutExpired:
        raise EngineUnreachable(f"runtime did not answer within {timeout}s") from None
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise EngineUnreachable(f"runtime could not be started: {type(exc).__name__}") from None
    try:
        payload = json.loads((proc.stdout or b"").decode("utf-8", errors="replace") or "")
    except ValueError:
        tail = (proc.stderr or b"").decode("utf-8", errors="replace").strip().splitlines()
        raise EngineUnreachable(
            "runtime failed: " + _one_line(tail[-1] if tail else f"exit {proc.returncode}")
        ) from None
    if not isinstance(payload, dict):
        raise EngineUnreachable("runtime answer is not an object")
    return payload


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
    cwd = event.get("cwd")
    if isinstance(cwd, str) and cwd:
        # The binding owner judges carriers against the directory the session
        # is really in; this transport only reports where that is.
        args += ["--event-cwd", cwd]
    model = event.get("model") if isinstance(event.get("model"), str) else None
    model = model or last_model(event.get("transcript_path"))
    if model:
        args += ["--model", model]
    if options.home:
        args += ["--home", str(options.home)]
    if options.authority_root:
        args += ["--authority-root", str(options.authority_root)]
    if options.runtime:
        args += ["--runtime", str(options.runtime)]
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
    if options.runtime:
        args += ["--runtime", str(options.runtime)]
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
    except EngineUnreachable:
        return None
    if not isinstance(payload.get("ok"), bool):
        return None
    return payload


def preserve_refused(saipen_root: Path, project: Path, text: str) -> str | None:
    """Keep the reply the gate refused before anything corrects it; its reference.

    The correction that follows asks the model for a compact surface, and
    detail it wrote only into the refused reply would otherwise live in a host
    transcript alone. The engine owns the bytes and the overflow account kept
    beside them; this transport only hands the reply over. None when the
    engine cannot keep it: the stop is still handled, and nothing is claimed.
    """
    try:
        kept = _run_engine(
            saipen_root,
            project,
            ["response", "preserve", "--stdin", "--json", "--project-root", str(project)],
            stdin=text,
            timeout=CHECK_TIMEOUT_SECONDS,
        )
    except EngineUnreachable:
        return None
    reference = kept.get("ref") if kept.get("ok") is True else None
    return reference if isinstance(reference, str) and reference else None


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


def breadcrumb(options, event_name: str, state: str, started: float, **facts) -> None:
    """Leave the last observed outcome where `saipen doctor` can read it.

    Diagnostics only: nothing reads this file to decide anything, and failing
    to write it changes nothing about the event that was just handled.
    """
    try:
        home = Path(options.home) if options.home else Path.home()
        profile = os.path.normcase(os.path.abspath(os.environ.get("CLAUDE_CONFIG_DIR")
                                                 or home / ".claude"))
        default = os.path.normcase(os.path.abspath(home / ".claude"))
        suffix = ("" if profile == default
                  else "-" + hashlib.sha256(profile.encode("utf-8")).hexdigest()[:16])
        target = home / ".saipen" / "health" / f"claude{suffix}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        # Arguments of another generation were read past, not obeyed: say so.
        facts.setdefault("unread_arguments", getattr(options, "unread", 0) or None)
        payload = {
            "host": "claude",
            "event": event_name,
            "state": state,
            "at": time.time(),
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "saipen_root": str(options.saipen_root) if options.saipen_root else None,
            "hook": str(Path(__file__).resolve()),
            **{key: value for key, value in facts.items() if value is not None},
        }
        partial = target.with_name(target.name + f".{os.getpid()}.partial")
        partial.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(partial, target)
    except OSError:
        pass


def _admission(saipen_root: Path, project: Path, verb: str, event: dict, options, name: str):
    """The engine's admission answer. Raises `EngineUnreachable`."""
    args = ["admission", verb, "--json", *admission_args(event, project, options)]
    if verb == "invalidate":
        args += ["--reason", name]
    elif name.startswith("SessionStart"):
        # A new, resumed, cleared or compacted context holds nothing the old
        # record proved: drop it and deliver again, in the same engine call.
        args += ["--fresh", "--reason", name]
    verdict = _run_engine(
        saipen_root,
        project,
        args,
        stdin=None,
        timeout=ADMISSION_TIMEOUT_SECONDS,
        # No local signer, ever: this same-user process cannot prove host
        # provenance, and nothing it could put in an environment variable
        # counts. The canonical owner obtains admission from the separated
        # host-authority broker, recovers it when absent, and applies the
        # operator's policy when it cannot be proven.
        transport=None,
    )
    if verb == "establish" and not isinstance(verdict.get("permitted"), bool):
        # The engine answered, and not about this prompt: it refused its own
        # command line in its general schema, or it is another generation.
        said = verdict.get("detail") or verdict.get("code")
        if not said:
            said = "permitted is not a boolean" if "permitted" in verdict else "no verdict"
        raise EngineUnreachable(
            "runtime answer is not an admission verdict: " + _one_line(said, 120)
        )
    return verdict


def _inject(event_name: str, verdict: dict) -> None:
    parts = [
        str(verdict.get("notice") or "").strip(),
        str(verdict.get("delivery") or "").strip(),
        str(verdict.get("contract") or "").strip(),
    ]
    context = "\n\n".join(part for part in parts if part)
    payload: dict = {}
    if verdict.get("degraded"):
        # One output object, both keys: the operator sees the UNVERIFIED marker
        # in the host's own surface and the model is told the same thing. A
        # second JSON object on stdout would be a protocol error, not a louder
        # warning.
        payload["systemMessage"] = str(verdict.get("notice") or "").strip()
    if context:
        payload["hookSpecificOutput"] = {"hookEventName": event_name, "additionalContext": context}
    if payload:
        print(json.dumps(payload))


def engine_unreachable(
    event_name: str, saipen_root: Path, reason: str, options, *, can_block: bool
) -> str:
    """Apply the operator's policy to an engine that did not answer.

    Returns the state that was acted on. DEGRADED_ALLOWED never blocks: the
    notice goes to the operator and, where the event can carry context, to the
    model. STRICT blocks only where the event CAN block; elsewhere it says so.
    """
    launcher = _launcher(saipen_root)
    action = f"{launcher} host repair"
    strict = authority_mode(Path(options.home) if options.home else None) == MODE_STRICT
    if strict and can_block:
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": ENGINE_BLOCKED.format(
                        reason=reason,
                        code=CODE_ENGINE_UNREACHABLE,
                        action=action,
                        launcher=launcher,
                    ),
                }
            )
        )
        return "BLOCKED"
    notice = ENGINE_DEGRADED.format(reason=reason, code=CODE_ENGINE_UNREACHABLE, action=action)
    payload: dict = {"systemMessage": notice}
    if event_name in ("SessionStart", "UserPromptSubmit", "PostToolUse"):
        payload["hookSpecificOutput"] = {"hookEventName": event_name, "additionalContext": notice}
    print(json.dumps(payload))
    return "DEGRADED"


def handle_session_start(saipen_root: Path, project: Path, event: dict, options) -> int:
    started = time.perf_counter()
    source = str(event.get("source") or "startup")
    try:
        verdict = _admission(
            saipen_root, project, "establish", event, options, f"SessionStart:{source}"
        )
    except EngineUnreachable as exc:
        state = engine_unreachable("SessionStart", saipen_root, str(exc), options, can_block=False)
        breadcrumb(options, "SessionStart", state, started, code=CODE_ENGINE_UNREACHABLE)
        return 0
    if not verdict.get("permitted"):
        # SessionStart cannot block anything; the prompt boundary will.
        print(json.dumps({"systemMessage": _refusal(verdict, saipen_root)}))
        breadcrumb(options, "SessionStart", "REFUSED", started, code=verdict.get("failure"),
                   step=verdict.get("failure_step"))
        return 0
    _inject("SessionStart", verdict)
    breadcrumb(options, "SessionStart", str(verdict.get("state")), started,
               code=verdict.get("failure"), step=verdict.get("failure_step"))
    return 0


def handle_prompt(saipen_root: Path, project: Path, event: dict, options) -> int:
    """The pre-generation boundary: admit, deliver, degrade, or block."""
    started = time.perf_counter()
    try:
        verdict = _admission(saipen_root, project, "establish", event, options, "UserPromptSubmit")
    except EngineUnreachable as exc:
        state = engine_unreachable(
            "UserPromptSubmit", saipen_root, str(exc), options, can_block=True
        )
        breadcrumb(options, "UserPromptSubmit", state, started, code=CODE_ENGINE_UNREACHABLE)
        return 0
    if not verdict.get("permitted"):
        print(json.dumps({"decision": "block", "reason": _refusal(verdict, saipen_root)}))
        breadcrumb(options, "UserPromptSubmit", "REFUSED", started, code=verdict.get("failure"),
                   step=verdict.get("failure_step"))
        return 0
    # A degraded permit is permitted and visibly NOT admitted: the prompt
    # proceeds because the policy allows it, and the marker travels in the
    # same single hook output so neither the operator nor the model can mistake
    # it for mechanical admission.
    _inject("UserPromptSubmit", verdict)
    breadcrumb(options, "UserPromptSubmit", str(verdict.get("state")), started,
               code=verdict.get("failure"), step=verdict.get("failure_step"))
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
    try:
        verdict = _admission(saipen_root, project, "establish", event, options, "PostToolUse")
    except EngineUnreachable as exc:
        engine_unreachable("PostToolUse", saipen_root, str(exc), options, can_block=False)
        return 0
    if not verdict.get("permitted"):
        print(json.dumps({"systemMessage": _refusal(verdict, saipen_root)}))
        return 0
    _inject("PostToolUse", verdict)
    return 0


def command_line_fault(name: str, reason: str, options) -> int:
    """This artifact cannot use its own command line: the policy decides.

    It is an engine that cannot be run -- no runtime is named that could be
    asked -- so it gets that rule and no other: DEGRADED_ALLOWED proceeds and
    says so, STRICT blocks where the event can block, with the one action.
    """
    if name == "Stop":
        record(BOUNDARY_UNAVAILABLE.format(reason=reason))
    elif name in ("SessionStart", "UserPromptSubmit"):
        started = time.perf_counter()
        state = engine_unreachable(
            name, options.saipen_root, reason, options, can_block=name == "UserPromptSubmit"
        )
        breadcrumb(options, name, state, started, code=CODE_ENGINE_UNREACHABLE)
    return 0


def read_command_line(argv: list[str] | None = None) -> tuple[argparse.Namespace, str | None]:
    """The options, and what is wrong with the command line when something is.

    Never exits. Every value is optional to the parser and checked here, an
    argument this generation does not know is read past, and whatever argparse
    still refuses comes back as a fault beside the defaults.
    """
    parser = _Arguments(description=__doc__, allow_abbrev=False)
    parser.add_argument("--host", nargs="?")
    parser.add_argument("--saipen-root", type=Path, nargs="?")
    parser.add_argument("--home", type=Path, nargs="?", help="diagnostic: operator home")
    parser.add_argument(
        "--authority-root", type=Path, nargs="?", help="diagnostic: protocol authority root"
    )
    parser.add_argument(
        "--runtime", type=Path, nargs="?", help="diagnostic: authority endpoint root"
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="diagnostic: prove this artifact parses, imports and exits; reads no event",
    )
    try:
        args, unread = parser.parse_known_args(argv)
    except CommandLineFault as exc:
        args = argparse.Namespace(
            host=None, saipen_root=None, home=None, authority_root=None, runtime=None,
            self_test=False, unread=0,
        )
        return args, "hook command line: " + _one_line(exc)
    args.unread = len(unread)
    if args.host != "claude":
        return args, f"hook command line names host {args.host!r}; this artifact serves claude"
    if args.saipen_root is None:
        return args, "hook command line names no --saipen-root"
    return args, None


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
    # T-1657: the refused reply is kept BEFORE the correction is requested or
    # the boundary recorded, so what the model wrote only there is not left to
    # a host transcript. An admission refusal judges the session, not a reply.
    kept = None if klass == "ADMISSION_BLOCKED" else preserve_refused(saipen_root, project, text)
    kept_note = f" The refused reply is kept at {kept}." if kept else ""
    if reentry:
        record(BOUNDARY_REENTRY.format(klass=klass, errors="; ".join(errors)) + kept_note)
        return 0
    delivery = verdict.get("delivery")
    correction = (
        f"SAIPEN canonical delivery ({klass}; do not add prose):\n" + delivery
        if isinstance(delivery, str) and delivery
        else correction_reason(verdict, project) + kept_note
    )
    print(json.dumps({"decision": "block", "reason": correction}))
    return 0


def handle_question(saipen_root: Path, project: Path, event: dict) -> int:
    """Question-only PreToolUse; canonical guard owns the decision."""
    translated = {
        "event": "before_tool", "host": "claude", "cwd": str(project),
        "tool_name": "AskUserQuestion", "tool_input": event.get("tool_input") or {},
        "session_id": event.get("session_id"),
    }
    try:
        verdict = _run_engine(
            saipen_root, project, ["guard", "--event-json", "-", "--json"],
            stdin=json.dumps(translated), timeout=ADMISSION_TIMEOUT_SECONDS,
        )
    except EngineUnreachable as exc:
        verdict = {"admitted": False, "detail": f"canonical question authority unavailable: {exc}"}
    if verdict.get("admitted") is True:
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": verdict.get("detail") or "canonical question refused",
    }}))
    return 0


def main() -> int:
    args, fault = read_command_line()
    if args.self_test:
        # The installer runs this against the STAGED artifact before it is
        # allowed to replace the active one: a hook that cannot even start must
        # never become the hook every prompt waits on.
        answer = {"ok": fault is None, "code": "HOOK_SELF_TEST", "host": args.host}
        print(json.dumps(answer if fault is None else {**answer, "detail": fault}))
        return 0
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
    if name == "PreToolUse" and event.get("tool_name") != "AskUserQuestion":
        # Bootstrap and ordinary tools never inherit the question gate.
        return 0
    if name not in (
        "SessionStart", "UserPromptSubmit", "PostToolUse", "PostModelSwitch", "Stop", "PreToolUse",
    ):
        return 0
    project = project_root(event.get("cwd") or os.getcwd())
    if fault is not None:
        # Outside a SAIPEN project this transport does nothing, whatever its
        # command line says.
        return command_line_fault(name, fault, args) if project is not None else 0
    if name == "PostToolUse":
        return handle_post_tool(args.saipen_root, project, event, args)
    if project is None:
        # No SAIPEN project, whatever a carrier says: ordinary chat (T-1636).
        return 0
    if name == "PreToolUse":
        return handle_question(args.saipen_root, project, event)
    if name == "SessionStart":
        return handle_session_start(args.saipen_root, project, event, args)
    if name == "UserPromptSubmit":
        return handle_prompt(args.saipen_root, project, event, args)
    if name == "PostModelSwitch":
        with contextlib.suppress(EngineUnreachable):
            _admission(args.saipen_root, project, "invalidate", event, args, "PostModelSwitch")
        return 0
    return handle_stop(args.saipen_root, project, event, args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        # The last line of defense: an unexpected fault in this transport must
        # not become a host failure. Say what happened, block nothing.
        with contextlib.suppress(Exception):
            print(
                json.dumps(
                    {
                        "systemMessage": "SAIPEN hook fault ("
                        + type(exc).__name__
                        + "); this event was not gated. Run `saipen host doctor`."
                    }
                )
            )
        raise SystemExit(0) from None
