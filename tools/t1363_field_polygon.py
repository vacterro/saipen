"""T-1363 field polygon: a real model, a real task, the INSTALLED runtime.

T-1363 exists because a weak free model, given one ordinary task in a real
project, never started work. Unit proof cannot close that: the defect was a
PROTOCOL UX defect, visible only as a transcript. So this drives the installed
OpenCode runtime with models from the local 9Router free pool over a matrix of
project conditions, and records -- per session -- the sequence a model actually
chose.

Read-only toward every real home: the installed engine is EXECUTED, never
written. Every project is disposable.

    python tools/t1363_field_polygon.py --models sairoute/SAIFREN --out DIR

Measured per session, from the host's own event stream:

* the FIRST saipen command the model chose;
* how many protocol commands it ran before a productive (non-protocol) action;
* every refusal code, in order, and whether any refusal repeated identically;
* whether it reached a productive action at all;
* whether canonical state in the project stayed byte-identical except through
  canonical operations.

STRONG acceptance: a healthy project answers in <= 1 entry command. With a
genuine operator decision: entry, ONE exact question, then productive action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

OPENCODE = shutil.which("opencode")
GIT = shutil.which("git")
HOME = Path(os.path.expanduser("~"))
INSTALLED = HOME / ".config" / "opencode" / "skills" / "saipen"


def _git_worktree(root: Path) -> Path:
    """Make the fixture a REAL git worktree before any model sees it.

    Measured the hard way: a fixture that is not a worktree does not bind as a
    project for the host, and a session started in it resolved its shell to the
    REPOSITORY instead -- so a free model ran `saipen start` against the live
    project and minted real tickets there. The sandbox is only a sandbox when
    the host can see its boundary.
    """
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    }
    for args in (
        [GIT, "init", "-q", str(root)],
        [GIT, "-C", str(root), "add", "-A"],
        [GIT, "-C", str(root), "commit", "-qm", "fixture"],
    ):
        subprocess.run(args, check=True, capture_output=True, env=env, timeout=300)
    return root

#: The EXACT shape the field incident carried: a Windows path in the task text.
FIELD_TASK = (
    r"add a docstring to the top of src/app.py explaining what it does; "
    r"the original notes are in V:\_TEMP_\fastprompter_drag\SAIPENVIEW_main.py"
)
SIMPLE_TASK = "add a one-line docstring to the top of src/app.py"

#: Commands that are PROTOCOL, not product. A session that runs many of these
#: before touching the work is the failure this ticket measures.
_PROTOCOL = re.compile(r"^\s*saipen\b")


def conditions() -> dict:
    """The eight project conditions the field matrix names."""
    import test_t1363_zero_manual_entry as fixtures

    class _Case:
        def addCleanup(self, _fn):  # fixtures keep themselves; we keep the tree
            return None

    holder = _Case()
    build = {
        "healthy": fixtures.healthy,
        "operator_decision": fixtures.blocker_project,
        "safety_valve": fixtures.valve_project,
        "repairable_debt": fixtures.unexecutable_next_action_project,
        "captured_unprojected": _captured_unprojected,
        "already_done": lambda case: fixtures.completed_request_project(case, SIMPLE_TASK),
        "foreign_owner": fixtures.foreign_owner_project,
        "windows_path_task": fixtures.healthy,
    }
    return {name: _git_worktree(maker(holder)) for name, maker in build.items()}


def _captured_unprojected(case) -> Path:
    """A receipt that was captured and never became Work (the SRC-044 shape)."""
    import test_t1363_zero_manual_entry as fixtures
    from saipen_engine import intake
    from saipen_engine.operations import USER_REQUEST_VERIFY, _user_request_body

    root = fixtures.healthy(case)
    body = _user_request_body(SIMPLE_TASK, "P1", USER_REQUEST_VERIFY, [])
    intake.capture(root, body, source_kind="user_instruction")
    return root


#: Every canonical carrier a wrong-project session can damage. `intake/index.json`
#: is on this list because the incident's FIRST durable trace was a receipt, not a
#: BOARD row -- a watcher that saw only STATE/BOARD/LOG would have reported the
#: contaminating run clean (T-1370, SRC-049:R011).
CANONICAL_CARRIERS = ("STATE.md", "BOARD.md", "LOG.md", "intake/index.json")


def _canonical_hashes(root: Path) -> dict:
    out = {}
    for name in CANONICAL_CARRIERS:
        path = root / ".saipen" / name
        out[name] = (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        )
    return out


def _owning_ledger(root: Path) -> dict:
    """What this project's OWN ledger says it owns.

    A model reporting "T-1371 created" is not evidence that T-1371 belongs to
    the fixture. This reads the fixture's files instead of believing the
    transcript.
    """
    from saipen_engine.board import parse_board

    board = root / ".saipen" / "BOARD.md"
    index = root / ".saipen" / "intake" / "index.json"
    tickets: list[str] = []
    receipts: list[str] = []
    if board.is_file():
        try:
            tickets = sorted(parse_board(board.read_text(encoding="utf-8-sig"))["tickets"])
        except (OSError, ValueError):
            tickets = []
    if index.is_file():
        try:
            receipts = sorted(json.loads(index.read_text(encoding="utf-8-sig")).get("active", {}))
        except (OSError, ValueError):
            receipts = []
    return {"tickets": tickets, "receipts": receipts}


def _tool_events(events: list[dict]) -> list[dict]:
    out = []
    for event in events:
        part = event.get("part") or {}
        if event.get("type") != "tool_use" or part.get("type") != "tool":
            continue
        state = part.get("state") or {}
        out.append(
            {
                "tool": part.get("tool"),
                "status": state.get("status"),
                "input": state.get("input") or {},
                "output": str(state.get("output") or "")[:2000],
                "error": str(state.get("error") or "")[:1200],
            }
        )
    return out


def _host_env(project: Path) -> dict:
    """The child's environment must agree with its cwd about where it is.

    `subprocess` sets the real working directory and leaves `PWD` alone, so a
    harness launched from the repository hands the host a `PWD` naming the
    REPOSITORY while its cwd is the fixture. Measured: the model's shell
    resolved to `PWD`, read the repository's files and ran `saipen start`
    against the repository's ledger -- a sandbox that fails silently, because
    every command succeeds against the wrong project.
    """
    env = {**os.environ}
    for key in ("SAIPEN_PROJECT_ROOT", "SAIPEN_PROJECT_LINEAGE", "SAIPEN_AGENT",
                "SAIPEN_SKILL_ROOT", "OLDPWD", "INIT_CWD"):
        env.pop(key, None)
    env["PWD"] = str(project)
    return env


def _shell_commands(tools: list[dict]) -> list[str]:
    commands = []
    for item in tools:
        command = item["input"].get("command")
        if isinstance(command, str) and command.strip():
            commands.append(command.strip())
    return commands


def _refusal_codes(tools: list[dict]) -> list[str]:
    codes = []
    for item in tools:
        blob = item["output"] + " " + item["error"]
        codes += re.findall(r"REFUSE \[([A-Z_]+)\]", blob)
        codes += re.findall(r"SAIPEN_(?:GUARD|FLEET)_REFUSAL: ([A-Z_]+)", blob)
        codes += re.findall(r'"code":\s*"([A-Z_]+)"', blob)
    return codes


def measure(tools: list[dict]) -> dict:
    """The transcript facts the acceptance is stated in."""
    commands = _shell_commands(tools)
    protocol = [c for c in commands if _PROTOCOL.match(c)]
    first = protocol[0] if protocol else None
    # A productive action is any tool effect that is not a protocol command:
    # a write/edit/patch, or a shell line that is not `saipen ...`.
    productive_at = None
    protocol_before = 0
    for item in tools:
        command = item["input"].get("command")
        if isinstance(command, str) and _PROTOCOL.match(command.strip()):
            protocol_before += 1
            continue
        if item["tool"] in ("write", "edit", "patch", "apply_patch", "multiedit"):
            productive_at = item["tool"]
            break
        if isinstance(command, str) and command.strip():
            productive_at = "shell"
            break
    refusals = _refusal_codes(tools)
    repeated = [
        code
        for index, code in enumerate(refusals[1:], start=1)
        if code == refusals[index - 1]
    ]
    return {
        "tools": len(tools),
        "first_saipen_command": first,
        "protocol_commands": protocol,
        "protocol_commands_before_productive": protocol_before,
        "productive_action": productive_at,
        "refusal_sequence": refusals[:20],
        "repeated_refusal": sorted(set(repeated)),
    }


def session(model: str, project: Path, task: str, timeout: int) -> dict:
    began = time.time()
    env = _host_env(project)
    proc = subprocess.run(
        [OPENCODE, "run", task, "--format", "json", "--auto", "--model", model],
        cwd=str(project),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    events = []
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    tools = _tool_events(events)
    return {
        "model": model,
        "returncode": proc.returncode,
        "elapsed_s": round(time.time() - began, 1),
        # SRC-049:R011 -- the binding a session actually ran under, recorded
        # from the environment that was HANDED to the host, not from prose.
        "binding": {
            "cwd": str(project),
            "PWD": env.get("PWD"),
            "SAIPEN_PROJECT_ROOT": env.get("SAIPEN_PROJECT_ROOT"),
            "OLDPWD": env.get("OLDPWD"),
            "INIT_CWD": env.get("INIT_CWD"),
            "resolved_project_root": str(project),
        },
        "text": "\n".join(
            (event.get("part") or {}).get("text", "")
            for event in events
            if event.get("type") == "text"
        )[:2000],
        "stderr_tail": proc.stderr[-800:],
        **measure(tools),
        "tool_names": [item["tool"] for item in tools],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=["sairoute/SAIFREN"])
    parser.add_argument("--conditions", nargs="+", default=None)
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if not OPENCODE:
        print("opencode runtime unavailable")
        return 3
    if not GIT:
        print("git unavailable: a fixture that is not a worktree is not a sandbox")
        return 3
    generation = subprocess.run(
        [sys.executable, str(INSTALLED / "tools" / "saipen.py"), "runtime", "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    ).stdout

    built = conditions()
    selected = args.conditions or list(built)
    report = {
        "installed_runtime": INSTALLED.exists(),
        "runtime_probe": generation[:4000],
        "sessions": [],
    }
    for model in args.models:
        for name in selected:
            project = built[name]
            task = FIELD_TASK if name == "windows_path_task" else SIMPLE_TASK
            before = _canonical_hashes(project)
            # SRC-049:R011 -- the MAIN repository is measured too. "the model
            # edited the fixture's file" is not isolation; "this repository's
            # canonical carriers are byte-identical" is.
            repo_before = _canonical_hashes(REPO)
            owned_before = _owning_ledger(project)
            try:
                record = session(model, project, task, args.timeout)
            except subprocess.TimeoutExpired:
                record = {"model": model, "timeout": True}
            after = _canonical_hashes(project)
            repo_after = _canonical_hashes(REPO)
            owned_after = _owning_ledger(project)
            record["condition"] = name
            record["task"] = task
            record["project"] = str(project)
            record["canonical_changed"] = sorted(
                key for key in before if before[key] != after[key]
            )
            record["repository_canonical_changed"] = sorted(
                key for key in repo_before if repo_before[key] != repo_after[key]
            )
            record["fixture_minted"] = {
                "tickets": [
                    t for t in owned_after["tickets"] if t not in owned_before["tickets"]
                ],
                "receipts": [
                    r for r in owned_after["receipts"] if r not in owned_before["receipts"]
                ],
            }
            # The verdict. A session passes ONLY if the fixture moved and this
            # repository did not -- and the ticket it claims to have made is
            # read back out of the fixture's own ledger, never believed.
            record["isolation"] = (
                "PASS"
                if record["canonical_changed"] and not record["repository_canonical_changed"]
                else "FAIL"
            )
            report["sessions"].append(record)
            print(
                f"{model} :: {name:22s} first={record.get('first_saipen_command')!r} "
                f"protocol_before={record.get('protocol_commands_before_productive')} "
                f"productive={record.get('productive_action')} "
                f"refusals={record.get('refusal_sequence')} "
                f"repeated={record.get('repeated_refusal')} "
                f"isolation={record.get('isolation')} "
                f"minted={record.get('fixture_minted')}"
            )
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "polygon.json").write_text(
            json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8"
        )
        print(f"wrote {out / 'polygon.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
