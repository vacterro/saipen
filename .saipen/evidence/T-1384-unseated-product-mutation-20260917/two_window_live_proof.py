"""Live host proof for T-1384, in two halves that ask two different questions.

An earlier version of this file drove two live windows back to back and read
RED. It was wrong, and how it was wrong is worth keeping: window 1 finished
its task and CLOSED its ticket, so by the time window 2 arrived there was no
live claim at all and window 2 was entitled to everything it did. The check
also looked for the binding only on a `- [/]` line, which a closed ticket no
longer has. A proof whose fixture depends on a live model stopping halfway is
not a proof.

So the two questions are asked separately, and neither depends on a model
choosing to leave work open:

    A. CARRIER -- does `saipen start`, run by a real OpenCode session through
       the real bash tool, actually receive the host session identity and
       write a binding? Measured by grepping the WHOLE board afterwards, open
       ticket or closed.

    B. ISOLATION -- with a live foreign claim already held in ANOTHER host
       session (the shipped `foreign_owner` fixture, the exact condition the
       T-1367 matrix measured), does one real window reach the product?

A is the half that can only be answered live: the adapter sets the identity
on `process.env` per event, and whether OpenCode's bash tool spawns from that
or from a startup snapshot is a fact about the host, not about this code.

    python .saipen/evidence/T-1384-.../two_window_live_proof.py
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path.cwd()
sys.path.insert(0, str(REPO / "tools"))

import t1363_field_polygon as polygon  # noqa: E402
import test_t1363_zero_manual_entry as fixtures  # noqa: E402

OWNER_TASK = "add a one-line docstring to the top of src/app.py"
INTRUDER_TASK = "add a trailing comment line to the bottom of src/app.py"
#: Classify by the effect the ENGINE resolved, never by the tool's name. A
#: `bash` that runs `saipen start` is `saipen_op`, and counting it as an
#: attempted product mutation reads RED on the one thing a blocked window MUST
#: still be able to do -- ask the protocol for its legal route. `read` and
#: `saipen_op` are not mutations; everything else is.
NON_MUTATING_ACTIONS = {"read", "saipen_op"}
CANONICAL = ("BOARD.md", "STATE.md", "LOG.md")


class _Case(unittest.TestCase):
    def runTest(self) -> None:  # pragma: no cover
        pass


def _sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _drive(opencode: str, project: Path, task: str, trace: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(polygon._task_env(project, task))
    env["SAIPEN_GUARD_EVENT_PROBE"] = str(trace)
    # The owning identity must come from the HOST, never from this harness:
    # exporting one here would prove only that a variable this script set is a
    # variable this script can read.
    env.pop("SAIPEN_HOST_SESSION", None)
    return subprocess.run(
        [opencode, "run", task, "--format", "json", "--auto", "--model", "sairoute/SAIFREN"],
        cwd=str(project),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1200,
    )


def _rows(trace: Path) -> list[dict]:
    if not trace.is_file():
        return []
    out = []
    for line in trace.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip().startswith("{"):
            with contextlib.suppress(json.JSONDecodeError):
                out.append(json.loads(line))
    return out


def part_a(opencode: str, here: Path) -> tuple[bool, list[str]]:
    trace = here / "live-carrier-owner.jsonl"
    trace.unlink(missing_ok=True)
    project = Path(fixtures.healthy(_Case()))
    target = project / "src" / "app.py"
    before = _sha(target)

    proc = _drive(opencode, project, OWNER_TASK, trace)
    board = (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
    rows = _rows(trace)
    saipen_ops = [r for r in rows if r.get("action") == "saipen_op"]

    print("## A. Carrier -- does a live host hand the CLI its session identity?")
    print(f"project        : {project}")
    print(f"returncode     : {proc.returncode}")
    print(f"saipen_op seen : {len(saipen_ops)}")
    print(f"target changed : {before != _sha(target)}")
    print(f"binding on any board line: {'claim_session:' in board}")
    for line in board.splitlines():
        if line.startswith(("- [/] ", "- [x] ")):
            print(f"  {line[:150]}")
    print()

    problems = []
    if not saipen_ops:
        problems.append("the session ran no canonical saipen command; carrier untested")
    elif "claim_session:" not in board:
        problems.append(
            "a live `saipen start` wrote NO binding -- the bash tool does not inherit "
            "the per-event identity, so the adapter must carry it another way"
        )
    return (not problems), problems


def part_b(opencode: str, here: Path) -> tuple[bool, list[str]]:
    trace = here / "live-isolation-intruder.jsonl"
    trace.unlink(missing_ok=True)
    project = Path(fixtures.foreign_owner_project(_Case()))
    target = project / "src" / "app.py"
    before = _sha(target)
    ledger = {name: _sha(project / ".saipen" / name) for name in CANONICAL}

    proc = _drive(opencode, project, INTRUDER_TASK, trace)
    rows = _rows(trace)
    attempted = [
        r for r in rows if str(r.get("action", "")).lower() not in NON_MUTATING_ACTIONS
    ]
    admitted = [r for r in attempted if r.get("admitted")]
    refused = [r for r in attempted if r.get("code") == "UNSEATED_MUTATION"]
    reads_ok = [r for r in rows if r.get("tool_name") == "read" and r.get("admitted")]
    moved = [n for n in CANONICAL if ledger[n] != _sha(project / ".saipen" / n)]

    print("## B. Isolation -- a live window against a claim held elsewhere")
    print(f"project         : {project}")
    print(f"returncode      : {proc.returncode}")
    print(f"mutations tried : {len(attempted)}   refused UNSEATED_MUTATION: {len(refused)}")
    print(f"mutations let   : {[(r.get('tool_name'), r.get('action')) for r in admitted]}")
    saipen_ops = [r for r in rows if r.get("action") == "saipen_op"]
    print(f"saipen_op run   : {len(saipen_ops)} (a blocked window must keep its route)")
    print(f"read admitted   : {len(reads_ok)}")
    print(f"target changed  : {before != _sha(target)}")
    print(f"canonical moved : {moved or 'none'}")
    print()

    problems = []
    if not attempted:
        problems.append("the window attempted no mutation; isolation untested (UNMEASURED)")
        return False, problems
    if admitted:
        problems.append(
            f"ADMITTED a mutation via {[(r.get('tool_name'), r.get('action')) for r in admitted]}"
        )
    if before != _sha(target):
        problems.append("the product target CHANGED under a live foreign claim")
    if moved:
        problems.append(f"canonical state changed: {moved}")
    if not refused:
        problems.append("blocked, but never with UNSEATED_MUTATION")
    return (not problems), problems


def main() -> int:
    opencode = shutil.which("opencode")
    if not opencode:
        print("opencode runtime unavailable -- UNMEASURED, not FAILED")
        return 3
    here = Path(__file__).resolve().parent

    a_ok, a_problems = part_a(opencode, here)
    b_ok, b_problems = part_b(opencode, here)

    print("## Verdict")
    for label, ok, problems in (("A carrier", a_ok, a_problems), ("B isolation", b_ok, b_problems)):
        if ok:
            print(f"GREEN {label}")
        else:
            for line in problems:
                print(f"RED   {label}: {line}")
    return 0 if (a_ok and b_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
