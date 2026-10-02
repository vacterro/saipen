"""Host tool-event translation for the guard CLI (SRC-030 Part 6).

Host adapters (e.g. the OpenCode plugin) translate THEIR native payloads into
one bounded JSON event; this module maps that common event onto the admission
action/effect model. No host-specific protocol semantics live in admission.py:
adapters translate, admission decides.

Closed mapping, three hard rules (SRC-028:R012 / T-1317 P0-1, P0-5, P0-8):

1. Canonical-operation exemption is all-or-nothing. A shell command reads as
   ``saipen_op`` ONLY when the ENTIRE command line is one bounded SAIPEN
   invocation: closed verb vocabulary, bounded argument alphabet, and no shell
   control syntax anywhere. ``saipen recover && rm -f .saipen/STATE.md`` is an
   ordinary SHELL effect and is judged as one.
2. Effect is decided from a target SET, never a first hit. Multi-file patches
   and both endpoints of a move/rename are carried explicitly for every
   consequential target.
3. Tool names grant nothing. Only an exact verified built-in read-only tool
   identity earns the read class; a namespaced or unknown tool is classified
   conservatively even when its last segment spells ``read``.
4. An unclassified consequential tool never reaches admission as an ordinary
   healthy mutation (T-1317 Target A). ``control_bash_process`` -- the Kiro
   process-control surface -- is translated explicitly as an unresolved
   consequential effect because its event carries a process id and arbitrary
   stdin, never an inspectable command line or a filesystem target. Every
   other unknown tool stays ``unknown``/mutating and `admission` refuses it
   on a bound project even when the protocol state is healthy: a healthy
   state is not evidence that an unclassified effect is safe.
"""

from __future__ import annotations

import json
import shlex

from .admission import SAIPEN_CLI_VERBS, normalize_action

#: The guard accepts a bounded JSON document, never arbitrary structures.
MAX_EVENT_BYTES = 256 * 1024

#: tool_input keys consulted, in order, for a single file target. First hit wins.
_PATH_KEYS = (
    "file_path",
    "filePath",
    "notebook_path",
    "notebookPath",
    "target_file",
    "targetFile",
    "absolute_path",
    "absolutePath",
    "path",
    "file",
)

#: Move/rename endpoints. BOTH sides are consequential (P0-6): a move into
#: protected canonical state and a move out of it are different attacks and
#: neither may be classified from one first-hit path key.
_SOURCE_PATH_KEYS = (
    "source_path",
    "sourcePath",
    "src_path",
    "srcPath",
    "from_path",
    "fromPath",
    "old_path",
    "oldPath",
    "origin_path",
    "originPath",
)

_DESTINATION_PATH_KEYS = (
    "destination_path",
    "destinationPath",
    "dest_path",
    "destPath",
    "to_path",
    "toPath",
    "new_path",
    "newPath",
    "target_path",
    "targetPath",
)

#: Multi-target patch markers (OpenCode `apply_patch`/`patch` carry
#: ``patchText`` with no ``filePath`` at all). Bounded preflight grammar only:
#: target discovery, never a patch engine and never the diff body.
_PATCH_FILE_MARKERS = (
    "*** Add File:",
    "*** Update File:",
    "*** Delete File:",
    "*** Move to:",
    "*** Move File:",
    "*** Rename File:",
)

#: Verified exact OpenCode built-in read-only tool identities. Nothing else
#: earns the read class: no ``view``/``cat``/``find``/``search`` suffix trust
#: and no namespaced last-segment trust (P0-8).
_READ_TOOLS = frozenset(
    {
        "read",
        "glob",
        "grep",
        "list",
        "webfetch",
        # T-1317 APPEND: the bootstrap `skill` tool reads skill/protocol
        # material into context and writes nothing, so it earns the bounded
        # read class by verified identity. Bootstrap access must not fail
        # merely because mutation admission is unavailable.
        "skill",
    }
)

_SHELL_TOOLS = frozenset(
    {
        "bash",
        "shell",
        "sh",
        "zsh",
        "cmd",
        "powershell",
        "exec",
        "terminal",
        "run_command",
        "runcommand",
        "runterminalcmd",
        "command",
    }
)

#: Explicitly reviewed Kiro v3 surface translation (T-1317 Target A). The
#: Kiro shell surface is `execute_bash` (one bounded command line the guard
#: can inspect) and `control_bash_process` (resume/steer an already-spawned
#: OS process by id, feeding arbitrary stdin). `control_bash_process` is
#: CONSEQUENTIAL and its event names no filesystem target and no command
#: line the canonical-verb check could judge, so the reviewed translation
#: classifies it as an UNRESOLVED consequential mutation: refused before
#: host execution, never an admitted targetless unknown, never an ordinary
#: shell event, and never read-trusted from its friendly name.
#: ``process_control`` is the translated identity the Kiro transport
#: (tools/host_guard.py) sends for this class.
_PROCESS_CONTROL_TOOLS = frozenset({"control_bash_process", "process_control"})

_WRITE_TOOLS = frozenset(
    {
        "write",
        "writefile",
        "edit",
        "editfile",
        "multiedit",
        "apply_patch",
        "applypatch",
        "patch",
        "create",
        "createfile",
        "save",
        "replace",
        "str_replace",
        "str_replace_editor",
        "notebookedit",
        "edit_notebook",
    }
)

_DELETE_TOOLS = frozenset({"delete", "remove", "rm", "unlink", "trash"})

_MOVE_TOOLS = frozenset({"move", "rename", "mv"})

#: Any of these makes an entire command line a COMPOUND shell expression:
#: command chaining, pipelines, redirection, command substitution, subshells,
#: glob/brace expansion, escaping, quoting, comments or a second
#: newline-separated command. Presence of one disqualifies the canonical
#: exemption for the whole line -- never a substring or regex guess at intent.
_SHELL_SYNTAX_CHARS = frozenset("|&;<>(){}[]$`*?~!\\\"'#\n\r\t")

#: Bounded argument alphabet for the `saipen <verb> [args]` grammar that
#: canonical operations actually use (flags, ids, dotted names, paths without
#: whitespace). Anything outside it is not a canonical argument.
_SAIPEN_ARG_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.,:/=+-@"
)

#: A canonical operation never needs an unbounded argument list.
_SAIPEN_MAX_TOKENS = 12


class EventError(ValueError):
    """The event document is not a legal bounded guard event."""


def load_event(raw: str) -> dict:
    """Parse and validate one bounded JSON guard event document."""
    if len(raw.encode("utf-8", errors="replace")) > MAX_EVENT_BYTES:
        raise EventError(f"guard event exceeds {MAX_EVENT_BYTES} bytes")
    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EventError(f"guard event is not valid JSON: {exc}") from None
    if not isinstance(event, dict):
        raise EventError("guard event must be a JSON object")
    for field in ("event", "host", "cwd", "tool_name"):
        value = event.get(field)
        if not isinstance(value, str) or not value.strip():
            raise EventError(f"guard event field {field!r} must be a non-empty string")
    tool_input = event.get("tool_input", {})
    if tool_input is None:
        tool_input = {}
    if not isinstance(tool_input, dict):
        raise EventError("guard event field 'tool_input' must be an object when present")
    if event.get("actor") is not None and not isinstance(event.get("actor"), str):
        raise EventError("guard event field 'actor' must be a string when present")
    event["tool_input"] = tool_input
    return event


def _tool_identity(tool_name: str) -> str | None:
    """The exact built-in tool identity, or None for a namespaced tool.

    A namespaced name (``mcp__server__read``) is deliberately NOT reduced to
    its last segment: a friendly suffix is not evidence of effect safety, so
    the event falls through to the conservative unknown class and is sent to
    admission for judgement (P0-8).
    """
    raw = str(tool_name).strip().lower()
    if not raw or "__" in raw or "." in raw:
        return None
    return raw


def _patch_targets(patch_text: object) -> tuple[list[str], bool]:
    """Every file target the bounded patch-marker grammar names.

    Returns ``(targets, unresolved)``. ``unresolved`` is True when patch text
    exists but yields no trustworthy target set, which must fail closed rather
    than pass as an ordinary healthy mutation.
    """
    if not isinstance(patch_text, str) or not patch_text.strip():
        return [], False
    targets: list[str] = []
    unresolved = False
    for line in patch_text.splitlines():
        stripped = line.strip()
        for marker in _PATCH_FILE_MARKERS:
            if stripped.startswith(marker):
                candidate = stripped[len(marker) :].strip()
                if candidate:
                    targets.append(candidate)
                else:
                    unresolved = True
                break
    if not targets:
        # Patch-shaped mutation with no recognisable target marker: the target
        # set is unknown, so it is not an ordinary project mutation.
        return [], True
    return targets, unresolved


def _extract_targets(tool_input: dict) -> tuple[list[str], bool]:
    """The full normalized target set an event carries, in declaration order."""
    targets: list[str] = []
    for key in _PATH_KEYS + _SOURCE_PATH_KEYS + _DESTINATION_PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            targets.append(value.strip())
    patch_text = tool_input.get("patchText")
    if patch_text is None:
        patch_text = tool_input.get("patch_text")
    patched, patch_unresolved = _patch_targets(patch_text)
    targets.extend(patched)
    return list(dict.fromkeys(targets)), patch_unresolved


def _saipen_cli_verb(command: str) -> str | None:
    """Canonical `saipen <verb>` recognition over the WHOLE command line.

    The exemption is granted only when the entire shell expression is one
    bounded SAIPEN invocation: closed verb vocabulary (exact token equality),
    bounded argument alphabet, and no shell control syntax anywhere in the
    line. A compound expression -- chaining, pipeline, redirection, command
    substitution, subshell, background job, quoting/escaping, glob or a second
    newline-separated command -- is an ordinary SHELL effect for the whole
    line, so `saipen recover && rm -f .saipen/STATE.md` can never inherit the
    canonical recovery exemption.
    """
    if not isinstance(command, str) or not command.strip():
        return None
    for char in command:
        if char in _SHELL_SYNTAX_CHARS:
            return None
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    if not tokens or len(tokens) > _SAIPEN_MAX_TOKENS:
        return None
    if tokens[0] != "saipen":
        # Path-routed (`./saipen`), environment-prefixed (`FOO=1 saipen`) and
        # wrapper invocations (`bash -lc 'saipen ...'`) are never canonical.
        return None
    for token in tokens:
        if not token or not _SAIPEN_ARG_CHARS.issuperset(token):
            return None
    if len(tokens) == 1:
        return "bare"
    verb = tokens[1]
    if verb in SAIPEN_CLI_VERBS:
        return verb
    return None


def map_event(event: dict) -> dict:
    """Map a validated event onto the admission action/effect model.

    Returns ``{"action", "target_path", "target_paths", "targets_unresolved",
    "actor", "host", "event", "tool_name", "cwd", "saipen_verb", "detail"}``.
    The ACTION decides nothing by itself; `admission.evaluate_admission`
    decides -- and it decides over EVERY target, refusing if any is refused.
    """
    tool = _tool_identity(event["tool_name"])
    tool_input = event.get("tool_input", {})
    actor = event.get("actor") or None
    targets, targets_unresolved = _extract_targets(tool_input)
    detail = ""
    verb: str | None = None
    action: str

    if tool in _READ_TOOLS:
        action = "read"
    elif tool in _PROCESS_CONTROL_TOOLS:
        # Reviewed Kiro translation (T-1317 Target A): consequential process
        # control with no trustworthy target set. Fail closed BEFORE host
        # execution via the admission TARGET_UNRESOLVED refusal; the healthy
        # protocol state must never clear it.
        action = "unknown"
        targets_unresolved = True
        detail = (
            f"process-control tool event '{event['tool_name']}': consequential "
            "effect with no trustworthy target set; refused before execution"
        )
    elif tool in _SHELL_TOOLS:
        command = tool_input.get("command") if isinstance(tool_input.get("command"), str) else None
        verb = _saipen_cli_verb(command) if command else None
        if verb is not None:
            action = "saipen_op"
            detail = f"canonical saipen operation ({verb})"
        else:
            action = "shell"
    elif tool in _WRITE_TOOLS:
        action = "write"
    elif tool in _DELETE_TOOLS:
        action = "delete"
    elif tool in _MOVE_TOOLS:
        action = "move"
    else:
        # Unknown tool events are potentially mutating (T-1317 Target A:
        # admission refuses them on a bound project even when the protocol
        # state is healthy); a recognizable path argument is still classified
        # so protected/traversal shapes stay visible to admission.
        action = "unknown"
        detail = (
            f"unknown tool event '{event['tool_name']}': unclassified "
            "consequential effect, refused unless a reviewed translation names it"
        )

    if action in ("write", "delete", "move") and not targets:
        # A mutating file-oriented tool that cannot name its target is not an
        # ordinary healthy mutation: admission fails closed on the empty set.
        targets_unresolved = True
    if action == "move" and len(targets) < 2:
        # BOTH endpoints of a move/rename are consequential, so a move that
        # names only one side cannot be classified from the other side's
        # shape: an unnamed destination could be protected state.
        targets_unresolved = True

    return {
        "action": normalize_action(action),
        "target_path": targets[0] if targets else None,
        "target_paths": targets,
        "targets_unresolved": targets_unresolved,
        "actor": actor,
        "host": event["host"],
        "event": event["event"],
        "tool_name": event["tool_name"],
        "cwd": event["cwd"],
        "saipen_verb": verb,
        "detail": detail,
    }
