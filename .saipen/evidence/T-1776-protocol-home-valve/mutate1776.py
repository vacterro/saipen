"""T-1776 mutation controls in a disposable copy.

    python mutate1776.py <copy-root> <evidence-dir> <scratch-profile>

Each mutation names the tests that must go red. The control and every mutation
run REPEATS times in fresh interpreters; a test red in some repetitions only is
reported as flaky. The copy is restored after each one. Profile carriers are
redirected so no run can reach the operator's real profile.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPEATS = 3
MODULE = "test_t1776_protocol_home_valve"
ENGINE = "tools/saipen_engine/"

LINEAGE = "test_protocol_home_is_lineage_equality_with_the_running_engine"
CLEARS = "test_protocol_home_cc_clears_the_valve_without_an_operator_carrier"
CONSUMER = "test_consumer_project_keeps_the_bounded_operator_gate"
STATUS = "test_status_and_iteration_report_no_operator_action_in_the_protocol_home"
BLOCK = "test_status_automation_block_continues_through_the_home_valve"

#: name -> ({file: [(old, new), ...]} or "before", tests that must go red)
MUTATIONS = {
    "control": ({}, set()),
    "the engine before this Work": ("before", {LINEAGE, CLEARS, STATUS, BLOCK}),
    "protocol_home is never true": (
        {"goal_authority.py": [(
            "        return bool(own) and own == project_lineage_identity(running_home())\n",
            "        return False\n",
        )]},
        {LINEAGE, CLEARS, STATUS, BLOCK},
    ),
    "protocol_home ignores the lineage": (
        {"goal_authority.py": [(
            "        return bool(own) and own == project_lineage_identity(running_home())\n",
            "        return True\n",
        )]},
        {LINEAGE, CONSUMER, STATUS, BLOCK},
    ),
    "reset_authority loses its home branch": (
        {"goal_authority.py": [(
            "    if home:\n        return {\"mode\": \"reauthorize\", \"source\": \"protocol_home\"}\n",
            "",
        )]},
        {CLEARS},
    ),
    "describe loses its home branch": (
        {"goal_authority.py": [(
            "    if state.get(\"execution_intent\") == \"goal\" and protocol_home(root):\n"
            "        return {\n            \"state\": \"protocol_home\",\n",
            "    if False:\n        return {\n            \"state\": \"protocol_home\",\n",
        )]},
        {STATUS},
    ),
    "the iteration verdict ignores the home checkpoint": (
        {"iteration_verdict.py": [(
            "    checkpoint = goal_authority.persistent(state) or home_checkpoint\n",
            "    checkpoint = goal_authority.persistent(state)\n",
        )]},
        {STATUS},
    ),
    "the automation block keeps the valve a human wait": (
        {"automation.py": [(
            "            if protocol_home_checkpoint(project_root, state):\n"
            "                disposition = CONTINUE\n",
            "            if protocol_home_checkpoint(project_root, state):\n"
            "                pass\n",
        )]},
        {BLOCK},
    ),
    "auto recall treats the home valve as a wait": (
        {"cold_recovery.py": [(
            "        (goal_authority.persistent(state) or goal_authority.protocol_home(root))\n",
            "        goal_authority.persistent(state)\n",
        )]},
        {STATUS},
    ),
}


def run_once(copy: Path, env: dict) -> tuple[set, int]:
    done = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", MODULE, "-v"],
        cwd=copy / "tools",
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    red = set(re.findall(r"^(?:FAIL|ERROR): (\w+) ", done.stderr, re.MULTILINE))
    ran = re.search(r"^Ran (\d+) test", done.stderr, re.MULTILINE)
    if ran is None:
        raise RuntimeError("no unittest summary:\n" + done.stderr[-1500:])
    return red, int(ran.group(1))


def apply(copy: Path, evidence: Path, edit, pristine: dict) -> None:
    if edit == "before":
        for name in pristine:
            (copy / ENGINE / name).write_bytes((evidence / "before" / name).read_bytes())
        return
    for name, pairs in edit.items():
        raw = pristine[name]
        crlf = b"\r\n" in raw
        text = raw.decode("utf-8").replace("\r\n", "\n")
        for old, new in pairs:
            if text.count(old) != 1:
                raise RuntimeError(f"anchor not unique in {name}: {old.strip()[:70]!r}")
            text = text.replace(old, new)
        (copy / ENGINE / name).write_bytes(
            (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")
        )


def main(argv: list[str]) -> int:
    copy, evidence, profile = (Path(item).resolve() for item in argv[:3])
    names = ("goal_authority.py", "automation.py", "iteration_verdict.py", "cold_recovery.py")
    pristine = {name: (copy / ENGINE / name).read_bytes() for name in names}
    env = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
    env.pop("CLAUDE_CONFIG_DIR", None)
    env.update(
        USERPROFILE=str(profile),
        HOME=str(profile),
        CLAUDE_CONFIG_DIR=str(profile / ".claude"),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONIOENCODING="utf-8",
    )
    problems = 0
    for name, (edit, expected) in MUTATIONS.items():
        try:
            apply(copy, evidence, edit, pristine)
            runs = [run_once(copy, env) for _ in range(REPEATS)]
        finally:
            for item, raw in pristine.items():
                (copy / ENGINE / item).write_bytes(raw)
        reds = [red for red, _ in runs]
        stable = all(red == reds[0] for red in reds)
        verdict = "as expected" if stable and reds[0] == expected else "UNEXPECTED"
        if not stable:
            verdict = "FLAKY"
        if verdict != "as expected":
            problems += 1
        print(f"{name}: ran {runs[0][1]}, red {len(reds[0])} -- {verdict}", flush=True)
        if verdict != "as expected":
            print(f"    expected: {sorted(expected)}")
            print(f"    got:      {[sorted(r) for r in reds]}")
    print(f"mutations: {len(MUTATIONS) - 1}, repetitions each: {REPEATS}, problems: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
