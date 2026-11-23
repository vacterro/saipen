"""Repeat the T-1304 and T-1640 suites to expose a test whose outcome is a coin flip.

The family ran each of these once and one of them lost a toss: it compared the
position of two records that the engine orders by (created_at, op_id), where
created_at has one-second resolution and the op id is a random name. A focused
run passes half the time, so one green run proves nothing about that class.
This runs every module ROUNDS times in a fresh interpreter and reports each
test id that was not green in every round.

usage: python repeat_runs.py <repo-root> [rounds]
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

MODULES = (
    "test_t1304_r009_settled_wiring",
    "test_t1519_settled_index",
    "test_t1304_r005_verifier_boundary",
    "test_t1304_r006_boundary_refusals",
    "test_t1304_r011_empty_selection",
    "test_t1640_log_seal",
    "test_t1640_board_scrub",
)
NOT_GREEN = re.compile(r"^(?:FAIL|ERROR): (\S+) \((\S+)\)", re.MULTILINE)
RAN = re.compile(r"^Ran (\d+) tests? in", re.MULTILINE)


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    losses: Counter[str] = Counter()
    ran: Counter[str] = Counter()
    exits: Counter[str] = Counter()
    for _round in range(rounds):
        for module in MODULES:
            done = subprocess.run(
                [sys.executable, "-B", "-m", "unittest", module],
                cwd=root / "tools",
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            output = done.stdout + done.stderr
            counted = RAN.search(output)
            ran[module] += int(counted.group(1)) if counted else 0
            if done.returncode != 0:
                exits[module] += 1
            for _name, test_id in NOT_GREEN.findall(output):
                losses[test_id] += 1
    print(f"rounds: {rounds}")
    for module in MODULES:
        print(f"{module}: tests run {ran[module]}, rounds not green {exits[module]}")
    print(f"test ids not green in every round: {len(losses)}")
    for test_id, count in sorted(losses.items()):
        print(f"  {test_id}: {count} of {rounds}")
    return 1 if losses or any(exits.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
