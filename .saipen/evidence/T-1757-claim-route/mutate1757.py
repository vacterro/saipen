"""T-1757 mutation controls, run in a disposable copy of the tree.

    python mutate1757.py <copy-root> <evidence-dir> <scratch-profile>

Each mutation names the tests that must go red. The control and every mutation
run REPEATS times in fresh interpreters; a test red in some repetitions only is
reported as flaky and fails the script. The copy is restored after each one.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPEATS = 3
MODULE = "test_t1757_claim_follows_route"
OPERATIONS = "tools/saipen_engine/operations.py"
ENTRY = "tools/saipen_engine/entry.py"

ROUTER = "test_the_router_names_the_audit_work_below_the_pick_rule_top"
ADMITS = "test_the_claim_admits_what_the_router_prescribes"
NEITHER = "test_a_ticket_neither_rule_names_still_refuses"
BASIS = "test_a_stated_basis_is_named_instead_of_an_override"
START = "test_start_names_the_request_it_was_handed"
ONLY = "test_the_route_admits_only_the_work_it_names"
BARE = "test_a_bare_explicit_override_keeps_its_record"

WORK_CHECK = (
    '    if owns and isinstance(projection, dict) and projection.get("work") == ticket_id:\n'
)

#: name -> (edits, tests that must go red). An edit is (file, old, new) or
#: (file, None, <evidence before-file name>) for a whole-file restore.
MUTATIONS = {
    "control": ([], set()),
    "entry.py reverted to pre-fix": ([(ENTRY, None, "entry.py")], {START}),
    "operations.py reverted to pre-fix": (
        [(OPERATIONS, None, "operations.py")],
        {ADMITS, BASIS, START},
    ),
    "both subject files pre-fix": (
        [(OPERATIONS, None, "operations.py"), (ENTRY, None, "entry.py")],
        {ADMITS, BASIS, START},
    ),
    "route admits any ticket (work comparison dropped)": (
        [(OPERATIONS, WORK_CHECK, "    if owns and isinstance(projection, dict):\n")],
        {ONLY},
    ),
    "audit route never asked": (
        [(
            OPERATIONS,
            "        basis = _audit_route_basis(root, tickets, agent, instant, ticket_id)\n",
            "        basis = None\n",
        )],
        {ADMITS},
    ),
    "a basis no longer admits the claim": (
        [(
            OPERATIONS,
            "    if not explicit and basis is None:\n",
            "    if not explicit:\n",
        )],
        {ADMITS},
    ),
    "the DEC forgets the basis": (
        [(
            OPERATIONS,
            "    if stepped_over is not None and basis is not None:\n",
            "    if False:\n",
        )],
        {ADMITS, BASIS, START},
    ),
    "START passes no basis": (
        [(
            ENTRY,
            '        basis=f"user request {captured_receipt}" if captured_receipt else None,\n',
            "        basis=None,\n",
        )],
        {START},
    ),
}


def read(path: Path) -> tuple[str, bool]:
    raw = path.read_bytes()
    return raw.decode("utf-8").replace("\r\n", "\n"), b"\r\n" in raw


def write(path: Path, text: str, crlf: bool) -> None:
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))


def run_once(copy: Path, env: dict) -> tuple[set, int]:
    done = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", MODULE, "-v"],
        cwd=copy / "tools",
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    red = set(re.findall(r"^(?:FAIL|ERROR): (\w+) ", done.stderr, re.MULTILINE))
    ran = re.search(r"^Ran (\d+) test", done.stderr, re.MULTILINE)
    if ran is None:
        raise RuntimeError("no unittest summary:\n" + done.stderr[-1500:])
    return red, int(ran.group(1))


def main(argv: list[str]) -> int:
    copy, evidence, profile = (Path(item).resolve() for item in argv[:3])
    env = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
    env.update(
        USERPROFILE=str(profile),
        HOME=str(profile),
        CLAUDE_CONFIG_DIR=str(profile / ".claude"),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONIOENCODING="utf-8",
    )
    pristine = {name: (copy / name).read_bytes() for name in (OPERATIONS, ENTRY)}
    problems = 0
    for name, (edits, expected) in MUTATIONS.items():
        try:
            for target, old, new in edits:
                path = copy / target
                if old is None:
                    path.write_bytes((evidence / "before" / new).read_bytes())
                    continue
                text, crlf = read(path)
                if text.count(old) != 1:
                    raise RuntimeError(f"anchor not unique for {name!r}: {old.strip()!r}")
                write(path, text.replace(old, new), crlf)
            runs = [run_once(copy, env) for _ in range(REPEATS)]
        finally:
            for target, raw in pristine.items():
                (copy / target).write_bytes(raw)
        reds = [red for red, _ in runs]
        stable = all(red == reds[0] for red in reds)
        verdict = "as expected" if stable and reds[0] == expected else "UNEXPECTED"
        if not stable:
            verdict = "FLAKY"
        if verdict != "as expected":
            problems += 1
        print(f"{name}: ran {runs[0][1]}, red {sorted(reds[0])} -- {verdict}")
        if verdict != "as expected":
            print(f"    expected red: {sorted(expected)}; all repetitions: {[sorted(r) for r in reds]}")
    print(f"mutations: {len(MUTATIONS) - 1}, repetitions each: {REPEATS}, problems: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
