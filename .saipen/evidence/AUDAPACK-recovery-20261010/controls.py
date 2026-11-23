"""Isolated controls using the existing canonical INIT and operation owners.

Only fixture corruption and failure injection write canonical bytes directly.
No implementation, assertion, or consumer protocol file is replaced.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from preflight import HERE, HOME, ORIGINAL, RECOVERY, git, inventory, sha, write_new

sys.path.insert(0, str(HOME / "tools"))
from saipen_engine import codec, guard_events, init_project, journal, lifecycle_authority, log, paths, state
from saipen_engine.board import parse_board

LAUNCHER = HOME / "bin/saipen.cmd"
ACTOR = "buffy"
FIXTURES = HERE / "fixtures-v5"
RECORDS = []
OUTCOMES = {}


def environment(**overrides):
    env = paths.unbound_environment(os.environ)
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", GIT_OPTIONAL_LOCKS="0")
    env.update(overrides)
    return env


def cli(root, *args, env=None, actor=ACTOR, input=None, explicit=True):
    prefix = [str(LAUNCHER)]
    if explicit:
        prefix += ["--project-root", str(root)]
    prefix += ["--agent", actor]
    command = [*prefix, *args, "--json"]
    result = subprocess.run(command, cwd=root, input=input, capture_output=True,
                            env=env or environment(), check=False, timeout=300)
    stdout = result.stdout.decode("utf-8", errors="replace")
    try:
        payload = json.loads(stdout)
    except ValueError:
        payload = None
    record = {"argv": command, "cwd": str(root), "exit_code": result.returncode,
              "stdout": stdout, "stderr": result.stderr.decode("utf-8", errors="replace"),
              "payload": payload}
    RECORDS.append(record)
    return record


def core(root):
    return {p.name: sha(p) for p in (root / ".saipen").iterdir() if p.is_file()}


def require(answer, code=None, ok=True):
    payload = answer["payload"]
    assert isinstance(payload, dict), answer
    assert payload.get("ok") is ok, answer
    assert (answer["exit_code"] == 0) is ok, answer
    if code:
        assert payload.get("code") == code, answer
    return payload


def fresh(name):
    root = FIXTURES / name
    root.mkdir()
    # A nested directory would inherit the parent's Git storage. Each fixture
    # owns an independent repository and tracks its native portable carrier.
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    answer = require(cli(root, "init"), "INIT_COMPLETED")
    assert answer["mailbox"]["code"] == "MAILBOX_ATTACH_SKIPPED", answer
    subprocess.run(["git", "-C", str(root), "add", ".saipen/IDENTITY.md"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=SAIPEN Recovery Fixture",
                    "-c", "user.email=fixture@example.invalid", "commit", "-q",
                    "-m", "test: add recovery control identity"], check=True, capture_output=True)
    assert Path(git(root, "rev-parse", "--absolute-git-dir").decode().strip()).resolve() == root / ".git"
    return root


def seeded(name):
    root = fresh(name)
    request = root / "control-request.txt"
    request.write_text("Verify this disposable control fixture and preserve its canonical evidence.\n", encoding="utf-8")
    payload = require(cli(root, "start", "--file", str(request)), "STARTED")
    ticket = payload["ticket"]
    assert re.fullmatch(r"T-\d+", ticket), payload
    assert parse_board(codec.read_doc(root / ".saipen/BOARD.md"))["tickets"][ticket]["section"] == "## DOING"
    return root, ticket


def native(root):
    result = subprocess.run([sys.executable, "-B", str(HOME / "tools/validate.py"),
                             "--project-root", str(root), "--gate", "core", "--no-receipt"],
                            cwd=HOME, env=environment(), capture_output=True, timeout=300)
    answer = {"argv": result.args, "exit_code": result.returncode,
              "stdout": result.stdout.decode("utf-8", errors="replace"),
              "stderr": result.stderr.decode("utf-8", errors="replace")}
    RECORDS.append(answer)
    return answer


def run_controls():
    FIXTURES.mkdir()
    outcomes = OUTCOMES
    # A: real fresh INIT, complete native validation, actual generated identity.
    a = fresh("A-fresh")
    lineage = paths.project_lineage_identity(a)
    assert lineage and lineage != paths.project_lineage_identity(ORIGINAL)
    assert native(a)["exit_code"] == 0
    outcomes["A"] = {"pass": True, "lineage": lineage}
    # B: the same CLI refuses an existing namespace with every byte unchanged.
    before = inventory(a)
    require(cli(a, "init"), "INIT_REFUSED", ok=False)
    assert inventory(a)["content_sha256"] == before["content_sha256"]
    outcomes["B"] = {"pass": True, "code": "INIT_REFUSED", "bytes_unchanged": True}
    # C: actual mutation admission must not accept stale/foreign bindings.
    c = fresh("C-bindings")
    before = inventory(c)
    env = environment(SAIPEN_PROJECT_ROOT=str(c), SAIPEN_PROJECT_LINEAGE=lineage)
    foreign = require(cli(c, "checkpoint", "RUN", "none", "foreign binding probe", env=env),
                      "PROJECT_LINEAGE_MISMATCH", ok=False)
    env = environment(SAIPEN_PROJECT_ROOT=str(FIXTURES / "absent-root"))
    stale = cli(c, "checkpoint", "RUN", "none", "stale binding probe", env=env, explicit=False)
    require(stale, ok=False)
    assert stale["payload"]["code"] in ("PROJECT_BINDING_INVALID", "PROJECT_ROOT_NOT_FOUND", "PROJECT_ROOT_INVALID"), stale
    assert inventory(c)["content_sha256"] == before["content_sha256"]
    outcomes["C"] = {"pass": True, "foreign": foreign["code"], "stale": stale["payload"]["code"],
                     "bytes_unchanged": True}
    # D: corrupt historical parent cannot be adopted by INIT or a normal writer.
    d, dticket = seeded("D-corrupt-history")
    p = d / ".saipen/LOG.md"
    text = p.read_text(encoding="utf-8")
    text, changed = re.subn(r"\[parent: E-\d+\]", "[parent: E-999999]", text, count=1)
    assert changed == 1
    p.write_text(text, encoding="utf-8", newline="\n")
    before = inventory(d)
    require(cli(d, "init"), "INIT_REFUSED", ok=False)
    refused = cli(d, "checkpoint", "RUN", dticket, "corrupt ledger probe")
    require(refused, ok=False)
    history = log.read_history_snapshot(d)
    errors = log.snapshot_contract_errors(history)
    assert errors and any("999999" in error for error in errors), errors
    assert native(d)["exit_code"] != 0
    assert inventory(d)["content_sha256"] == before["content_sha256"]
    outcomes["D"] = {"pass": True, "code": refused["payload"]["code"],
                     "history_errors": errors, "bytes_unchanged": True}
    # E: inject the same hostile claim class against the ACTUAL allocated ID.
    # Existing test_t1671 carrier and every original assertion remain unchanged.
    e, eticket = seeded("E-unsupported-DONE")
    lp = e / ".saipen/LOG.md"
    typed = lp.read_text(encoding="utf-8")
    tail = max(int(m.group(1)) for m in re.finditer(r"\[E-(\d+)\]", typed))
    stamp = datetime.now(timezone.utc).strftime("%d.%m.%y %H:%M")
    for message in ("RUN: build -> fixture fabricated implementation",
                    "RUN: verify -> PASS conf: high -- fixture typed proof",
                    f"DEC: {eticket} DONE; fixture unsupported closure"):
        typed += f"- {stamp} [E-{tail + 1}] [parent: E-{tail}] [{eticket}] [agent: {ACTOR}] {message}\n"
        tail += 1
    lp.write_text(typed, encoding="utf-8", newline="\n")
    bp = e / ".saipen/BOARD.md"
    board = bp.read_text(encoding="utf-8")
    row = next(line for line in board.splitlines() if re.match(rf"^- \[/\] {re.escape(eticket)}(?: |$)", line))
    board = board.replace(row + "\n", "")
    done = row.replace("- [/]", "- [x]", 1) + " | closure_mode: own_patch"
    bp.write_text(board.replace("## DONE\n", "## DONE\n" + done + "\n"), encoding="utf-8", newline="\n")
    sp = e / ".saipen/STATE.md"
    text = sp.read_text(encoding="utf-8")
    for key, value in {"phase": "DONE", "transition_from": "SHIP", "task": "none",
                       "next_action": '"saipen continue"', "last_event": str(tail)}.items():
        text, count = re.subn(rf"^{key}: .*$", f"{key}: {value}", text, flags=re.MULTILINE)
        assert count == 1
    sp.write_text(text, encoding="utf-8", newline="\n")
    before = inventory(e)
    refused = cli(e, "status")
    require(refused, lifecycle_authority.CODE, ok=False)
    history = log.read_history_snapshot(e)
    assessment = lifecycle_authority.assess(
        e, state.parse_state(codec.read_doc(e / ".saipen/STATE.md")),
        parse_board(codec.read_doc(e / ".saipen/BOARD.md")), history.events,
    )
    assert assessment["status"] == "UNAUTHORIZED", assessment
    assert any(row["rule"] == "terminal-without-operation" for row in assessment["findings"])
    assert native(e)["exit_code"] != 0
    assert inventory(e)["content_sha256"] == before["content_sha256"]
    outcomes["E"] = {"pass": True, "code": refused["payload"]["code"],
                     "authority": assessment, "bytes_unchanged": True}
    # F: inject a late template-read failure, without replacing the INIT owner.
    f = FIXTURES / "F-partial-INIT"
    f.mkdir()
    original_template = init_project._template
    def fail_late(name):
        if name == "BOARD.md":
            raise OSError("fixture: injected BOARD template read failure after STATE materialization")
        return original_template(name)
    import saipen
    output = io.StringIO()
    error = None
    with patch("saipen_engine.init_project._template", side_effect=fail_late), contextlib.redirect_stdout(output):
        try:
            saipen.main(["--project-root", str(f), "--agent", ACTOR, "init", "--json"])
        except OSError as exc:
            error = str(exc)
    assert error and "INIT_COMPLETED" not in output.getvalue()
    assert (f / ".saipen/STATE.md").is_file() and not (f / ".saipen/BOARD.md").exists()
    before = inventory(f)
    require(cli(f, "init"), "INIT_REFUSED", ok=False)
    refused = cli(f, "status")
    require(refused, ok=False)
    assert native(f)["exit_code"] != 0
    assert inventory(f)["content_sha256"] == before["content_sha256"]
    outcomes["F"] = {"pass": True, "injected_failure": error, "status": refused["payload"]["code"],
                     "partial_workspace_preserved": str(f), "bytes_unchanged_after_failure": True}
    # G: the native pre-execution guard refuses a raw protected write.
    g, _gticket = seeded("G-unauthorized-write")
    before = inventory(g)
    event = {"event": "before_tool", "host": "opencode", "cwd": str(g), "actor": ACTOR,
             "tool_name": "write", "tool_input": {"filePath": str(g / ".saipen/STATE.md"),
                                                        "content": "fabricated DONE\n"}}
    guard = guard_events.evaluate_event(event)
    assert guard["admitted"] is False and guard["code"] == "PROTECTED_CANONICAL_NAMESPACE", guard
    assert inventory(g)["content_sha256"] == before["content_sha256"]
    outcomes["G"] = {"pass": True, "guard": guard, "bytes_unchanged": True}
    return outcomes


if __name__ == "__main__":
    failure = None
    outcomes = OUTCOMES
    try:
        outcomes = run_controls()
    except Exception:
        failure = traceback.format_exc()
    result = {"all_pass": failure is None and len(outcomes) == 7, "outcomes": outcomes,
              "failure": failure, "commands": RECORDS,
              "canonical_init_sha256": sha(HOME / "tools/saipen_engine/init_project.py"),
              "canonical_cli_sha256": sha(HOME / "tools/saipen.py")}
    write_new(HERE / "phase1-v5.json", result)
    print(json.dumps({"all_pass": result["all_pass"], "outcomes": outcomes,
                      "failure": failure, "record": str(HERE / "phase1-v5.json")}, indent=2))
    raise SystemExit(0 if result["all_pass"] else 1)
