"""Were the repeated PROTECTED_CANONICAL_NAMESPACE refusals a carousel?

SRC-057 section 2: before product bytes change again, prove from the host's own
structured events -- not from the polygon's summary -- whether each pair of
consecutive PCN refusals the polygon scored as `repeated_refusal` was

* PARALLEL_DUPLICATE: the second call was already issued (same assistant step,
  or started before the first refusal completed), so no route could reach it;
* SEQUENTIAL_EQUIVALENT_RETRY: the first refusal was observable, and the model
  later issued the SAME effect again -- the carousel T-1367 bans;
* SEQUENTIAL_REWORDED_RETRY: the first refusal was observable, and the second
  call ran the SAME canonical operation (`saipen <verb> ... T-###`) with only
  its free text changed -- a carousel an exact-bytes comparison would hide;
* SEQUENTIAL_DISTINCT_EFFECT: the first refusal was observable, and the second
  call attempted a DIFFERENT effect that happened to meet the same code.

Read-only: OpenCode's session store is opened `mode=ro`, fixtures are only read.

    python pcn_causality.py > pcn-causality.json
    python pcn_causality.py <fixture directory> <label> > rerun.json

With arguments, the session is resolved from the store by its directory, the
same identity rule the polygon uses when stdout named no session.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

STORE = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
CODE = "PROTECTED_CANONICAL_NAMESPACE"
MARKER = re.compile(r"SAIPEN_(?:GUARD|FLEET)_REFUSAL: ([A-Z_]+)")
REFUSE = re.compile(r"REFUSE \[[A-Z_]+\]|\"ok\"\s*:\s*false")

#: Every session the polygon evidence scored with a PCN in its refusal sequence
#: and `repeated_refusal` containing it, keyed by the evidence file that did so.
SESSIONS = {
    "ses_f5016f4c6ffe1NOZyPZ7KhoW6l": (
        "T-1367 smoke-probe gen-sha256:420e04e7 long_file_task",
        "V:/_TEMP_/t1363-ym10x47r",
    ),
    "ses_f5076c641ffeLV1NnwFbGjrI7b": (
        "T-1380 field-rerun-E6962 gen-sha256:b374ef1f captured_unprojected",
        "V:/_TEMP_/t1363-15gdqkgd",
    ),
    "ses_f50740ca9ffeJuU5anJUITaotw": (
        "T-1380 field-rerun-E6962 gen-sha256:b374ef1f windows_path_task",
        "V:/_TEMP_/t1363-q_02iu_z",
    ),
    "ses_f500173eaffe77ECIDxoJjYWhL": (
        "T-1385 smoke gen-sha256:a8290234 long_file_task",
        "V:/_TEMP_/t1363-gtj4k4e3",
    ),
}


def effect_fingerprint(tool: str, args: dict) -> tuple[str, str]:
    """(sha256 prefix, human form) of what the call tried to DO."""
    if isinstance(args.get("command"), str):
        shape = {"tool": tool, "command": args["command"].strip()}
        human = args["command"].strip()
    else:
        shape = {
            "tool": tool,
            "filePath": args.get("filePath"),
            "content": args.get("content"),
            "oldString": args.get("oldString"),
            "newString": args.get("newString"),
        }
        human = f"{tool} {args.get('filePath')}"
    digest = hashlib.sha256(json.dumps(shape, sort_keys=True).encode("utf-8")).hexdigest()
    return digest[:16], human[:240]


def operation(tool: str, args: dict) -> str:
    """The operation a call performs, with free text removed.

    Only a `saipen` line can be reduced safely: its verb, subverb and ticket
    name the operation and the quoted argument is evidence prose. Any other
    shell line is its own operation, because nothing proves two spellings do
    the same thing.
    """
    command = args.get("command")
    if isinstance(command, str):
        text = command.strip()
        if re.match(r"^saipen\s", text):
            head = re.split(r"""\s['"]""", text, maxsplit=1)[0]
            return head
        return text
    return f"{tool} {args.get('filePath')}"


def canonical_success(tool: dict) -> bool:
    """A completed `saipen` command whose output is not a refusal.

    Human-mode outputs carry no event id, so canonical position is measured as
    the NUMBER of canonical commands that succeeded before a call: two refusals
    with the same count saw the same canonical ledger.
    """
    state = tool["state"]
    command = (state.get("input") or {}).get("command")
    if not isinstance(command, str) or not re.match(r"^\s*saipen\s", command):
        return False
    if state.get("status") != "completed":
        return False
    output = str(state.get("output") or "")
    return bool(output.strip()) and not REFUSE.search(output)


def fixture_log(directory: str) -> list[str]:
    log = Path(directory) / ".saipen" / "LOG.md"
    if not log.is_file():
        return []
    return [line for line in log.read_text(encoding="utf-8").splitlines() if "[E-" in line]


def analyse(con: sqlite3.Connection, session_id: str, label: str, directory: str) -> dict:
    messages = {
        mid: json.loads(data)
        for mid, data in con.execute(
            "select id, data from message where session_id = ?", (session_id,)
        )
    }
    tools = []
    for part_id, message_id, data in con.execute(
        "select id, message_id, data from part where session_id = ? order by time_created",
        (session_id,),
    ):
        part = json.loads(data)
        if part.get("type") == "tool":
            tools.append({"part_id": part_id, "message_id": message_id, **part})

    occurrences = []
    successes = 0
    for index, tool in enumerate(tools):
        state = tool.get("state") or {}
        error = str(state.get("error") or "")
        marker = MARKER.search(error)
        if marker and marker.group(1) == CODE:
            args = state.get("input") or {}
            digest, human = effect_fingerprint(tool.get("tool"), args)
            message = messages.get(tool["message_id"], {})
            times = state.get("time") or {}
            occurrences.append(
                {
                    "tool_index": index,
                    "session_id": session_id,
                    "message_id": tool["message_id"],
                    "call_id": tool.get("callID"),
                    "tool": tool.get("tool"),
                    "effect_fingerprint": digest,
                    "operation": operation(tool.get("tool"), args),
                    "attempted": human,
                    "call_start_ms": times.get("start"),
                    "refusal_end_ms": times.get("end"),
                    "assistant_step_created_ms": (message.get("time") or {}).get("created"),
                    "assistant_step_completed_ms": (message.get("time") or {}).get("completed"),
                    "parent_message_id": message.get("parentID"),
                    "canonical_successes_before": successes,
                    "host_error_text": error,
                    "route_delivered": " next: " in error,
                }
            )
        if canonical_success(tool):
            successes += 1

    pairs = []
    for first, second in zip(occurrences, occurrences[1:]):
        between = tools[first["tool_index"] + 1 : second["tool_index"]]
        in_flight = second["message_id"] == first["message_id"] or (
            (second["call_start_ms"] or 0) < (first["refusal_end_ms"] or 0)
        )
        equivalent = second["effect_fingerprint"] == first["effect_fingerprint"]
        same_operation = second["operation"] == first["operation"]
        if in_flight:
            shape = "PARALLEL_DUPLICATE"
        elif equivalent:
            shape = "SEQUENTIAL_EQUIVALENT_RETRY"
        elif same_operation:
            shape = "SEQUENTIAL_REWORDED_RETRY"
        else:
            shape = "SEQUENTIAL_DISTINCT_EFFECT"
        pairs.append(
            {
                "first_call": first["call_id"],
                "second_call": second["call_id"],
                "same_assistant_step": second["message_id"] == first["message_id"],
                "second_started_after_first_refusal_ms": (second["call_start_ms"] or 0)
                - (first["refusal_end_ms"] or 0),
                "effect_equivalent": equivalent,
                "operation_equivalent": same_operation,
                "canonical_changed_between": second["canonical_successes_before"]
                != first["canonical_successes_before"],
                "calls_between": [
                    {
                        "tool": item.get("tool"),
                        "status": (item.get("state") or {}).get("status"),
                        "effect": effect_fingerprint(
                            item.get("tool"), (item.get("state") or {}).get("input") or {}
                        )[1][:120],
                    }
                    for item in between
                ],
                "shape": shape,
            }
        )
    return {
        "label": label,
        "fixture": directory,
        "fixture_log_events": fixture_log(directory),
        "tool_calls": len(tools),
        "occurrences": occurrences,
        "pairs": pairs,
    }


def main(argv: list[str]) -> int:
    con = sqlite3.connect(f"file:{STORE.as_posix()}?mode=ro", uri=True)
    try:
        sessions = SESSIONS
        if argv:
            directory, label = argv[0], argv[1]
            wanted = Path(directory).resolve()
            rows = con.execute("select id, directory from session").fetchall()
            matches = [sid for sid, where in rows if Path(where).resolve() == wanted]
            if len(matches) != 1:
                raise SystemExit(f"expected one session for {directory}, found {matches}")
            sessions = {matches[0]: (label, directory)}
        report = [
            analyse(con, session_id, label, directory)
            for session_id, (label, directory) in sessions.items()
        ]
    finally:
        con.close()
    json.dump(report, sys.stdout, indent=1, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
