"""Mutation controls for T-1640: remove one property, the named tests must go red.

Usage: mutate1640.py <repo> <copy>

The copy is a disposable tree (no VCS, no project memory). Each mutation is
applied to the copy only, the named tests are run from the copy, and the file
is restored from the repository before the next one.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
copy = Path(sys.argv[2]).resolve()
assert repo != copy and repo not in copy.parents

if copy.exists():
    shutil.rmtree(copy)
skip = {".git", ".saipen", "__pycache__", ".pytest_cache", ".ruff_cache",
        ".workbuddy-ai", ".codenomad", ".freebuff", ".claude"}
shutil.copytree(
    repo, copy, ignore=lambda d, names: [n for n in names if n in skip or n.endswith(".pyc")]
)

OPS = "tools/saipen_engine/operations.py"
SCRUB = "tools/saipen_engine/board_scrub.py"
CLI = "tools/saipen.py"
VALIDATE = "tools/validate.py"
SEAL_T = "test_t1640_log_seal"
SCRUB_T = "test_t1640_board_scrub"

MUTATIONS = [
    (
        "M1 seal keeps the tree binding it writes into",
        OPS,
        [(
            '    preconditions = {k: v for k, v in plan.preconditions.items() if k != ".saipen/logs"}\n'
            "    preconditions.update(bindings)\n",
            "    preconditions = dict(plan.preconditions)\n",
        )],
        [f"{SEAL_T}.InterruptedSealTests", f"{SEAL_T}.BindingTests"],
    ),
    (
        "M2 seal shortens the LOG before the copy lands",
        OPS,
        [(
            "            *(t for t in plan.targets if t.path == segment),\n"
            "            *(t for t in plan.targets if t.path != segment),\n",
            "            *(t for t in plan.targets if t.path != segment),\n"
            "            *(t for t in plan.targets if t.path == segment),\n",
        )],
        [f"{SEAL_T}.InterruptedSealTests", f"{SEAL_T}.BindingTests"],
    ),
    (
        "M3 seal does not put the write gate to the standing ledger",
        OPS,
        [("    if standing:\n        return _refuse(\n", "    if False:\n        return _refuse(\n")],
        [f"{SEAL_T}.RefusalTests"],
    ),
    (
        "M4 seal runs outside CLEAN",
        OPS,
        [(
            '    if phase != "CLEAN":\n        return _refuse(\n            "ILLEGAL_PHASE",\n'
            '            f"the active LOG is sealed in CLEAN',
            '    if False:\n        return _refuse(\n            "ILLEGAL_PHASE",\n'
            '            f"the active LOG is sealed in CLEAN',
        )],
        [f"{SEAL_T}.RefusalTests"],
    ),
    (
        "M5 seal ignores the cap",
        OPS,
        [(
            "    if not seal_due(len(lines), len(sealed_bytes)) or not events:\n",
            "    if not events:\n",
        )],
        [f"{SEAL_T}.RefusalTests", f"{SEAL_T}.CleanRouteTests"],
    ),
    (
        "M6 scrub closure is one hop",
        SCRUB,
        [(
            '            kept[named] = "reference"\n            frontier.append(named)\n',
            '            kept[named] = "reference"\n',
        )],
        [f"{SCRUB_T}.RetentionRuleTests"],
    ),
    (
        "M7 scrub forgets what ACTIVE receipts name",
        SCRUB,
        [(
            "        if tid in receipt_works or _receipts_named(tickets[tid]) & active_receipts:\n",
            "        if False:\n",
        )],
        [f"{SCRUB_T}.ReceiptGuardTests"],
    ),
    (
        "M8 scrub prunes a row the LOG never closed",
        SCRUB,
        [("        elif tid not in proven:\n", "        elif False:\n")],
        [f"{SCRUB_T}.RetentionRuleTests", f"{SCRUB_T}.ScrubTests"],
    ),
    (
        "M9 scrub does not bind the receipts it read",
        OPS,
        [('    preconditions[".saipen/intake"] = intake_binding\n', "")],
        [f"{SCRUB_T}.ReceiptGuardTests"],
    ),
    (
        "M10 scrub drops the rows instead of keeping them",
        OPS,
        [(
            '            TargetPlan(evidence, "generic", pruned_bytes, "", hash_bytes(pruned_bytes)),\n',
            "",
        ), ("    preconditions[evidence] = \"\"\n", "")],
        [f"{SCRUB_T}.ScrubTests", f"{SCRUB_T}.InterruptedScrubTests"],
    ),
    (
        "M11 only the clean verb runs the entry steps",
        CLI,
        [(
            '        if result.ok and not dry_run and transition_result.get("phase") == "CLEAN":\n',
            "        if False:\n",
        )],
        [f"{SEAL_T}.CleanRouteTests", f"{SCRUB_T}.CleanRouteTests",
         f"{SEAL_T}.ValidatorFindingTests", f"{SCRUB_T}.ValidatorFindingTests"],
    ),
    (
        "M12 the validator measures the whole BOARD again",
        VALIDATE,
        [("if _scrub is not None and _scrub.due:\n", "if board_path.stat().st_size > 16 * 1024:\n")],
        [f"{SCRUB_T}.ValidatorFindingTests"],
    ),
    (
        "M13 the validator names the verb the guard refuses",
        VALIDATE,
        [("`saipen transition CLEAN` seals \"", "`saipen clean` seals \"")],
        [f"{SEAL_T}.ValidatorFindingTests", f"{SEAL_T}.CleanRouteTests"],
    ),
]


def run(tests: list[str]) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", *tests],
        cwd=str(copy / "tools"), env=env, stdin=subprocess.DEVNULL, capture_output=True,
        timeout=1800, check=False,
    )
    out = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
    return proc.returncode, out


code, out = run([SEAL_T, SCRUB_T])
ran = re.search(r"Ran (\d+) tests", out)
print(f"CONTROL unmutated copy: exit {code}, {ran.group(0) if ran else out[-200:]}")
assert code == 0, out[-2000:]

for label, rel, edits, tests in MUTATIONS:
    target = copy / rel
    original = (repo / rel).read_bytes()
    newline = "\r\n" if b"\r\n" in original else "\n"
    text = original.decode("utf-8")
    for old, new in edits:
        old, new = old.replace("\n", newline), new.replace("\n", newline)
        assert text.count(old) == 1, (label, text.count(old), old[:70])
        text = text.replace(old, new)
    target.write_bytes(text.encode("utf-8"))
    code, out = run(tests)
    verdict = re.search(r"FAILED \(([^)]*)\)", out)
    names = sorted(set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", out, flags=re.M)))
    print(f"{label}: exit {code} {verdict.group(1) if verdict else 'NOT RED'}")
    for name in names:
        print(f"      red: {name}")
    target.write_bytes(original)
print("restored; mutations", len(MUTATIONS))
