"""T-1669: the regression pair on one verifier, and red controls for each hunk.

Usage: t1669_controls.py <repo> <copy>

The repair was found in the tree with no LOG event behind it (written
2026-10-07 21:53Z, ticket still TODO). Adopting it means proving it the way a
fresh build would be proved: the unchanged verifier red against the pre-fix
subject and green against the tree, and each of the three hunks removed alone
with the tests named for it going red in every one of three repetitions.

The pre-fix subject is a disposable copy of tools/, tests/ and saipen/ with the
three T-1669 hunks of operations.py reversed: DONE plans `PHASE DONE` again,
nothing projects the router's answer, and the result echoes the planned value.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
copy = Path(sys.argv[2]).resolve()
assert repo != copy and repo not in copy.parents and not copy.exists(), copy
sys.path.insert(0, str(repo / "tools"))

from saipen_engine import oracle  # noqa: E402

MODULE = "test_t1669_clean_done_projection"
COMMAND = f"python -B -m unittest {MODULE}"
VERIFIER = (f"tools/{MODULE}.py",)
OPS = "tools/saipen_engine/operations.py"
SUBJECT = (OPS,)

PROVISIONAL = ('        na = "saipen continue"\n    else:\n',
               '        na = f"PHASE {destination}"\n    else:\n')
PROJECTION = ('    if destination == "DONE":\n        from .router import route_next\n',
              '    if False:\n        from .router import route_next\n')
REPORT = ('        # value here would let a Result disagree with the bytes on disk.\n'
          '        "next_action": parse_state(new_state).get("next_action"),\n',
          '        # value here would let a Result disagree with the bytes on disk.\n'
          '        "next_action": na,\n')

ROUTED = "test_clean_to_done_commits_the_routed_scout_before_any_claim"
CONTROL = "test_the_pre_fix_value_fails_the_same_fixture"
UNROUTED = "test_clean_to_done_without_routed_work_matches_the_router"

MUTATIONS = [
    ("M1 nothing projects the router's answer on DONE", [PROJECTION], [ROUTED, CONTROL]),
    ("M2 DONE plans PHASE DONE again", [PROVISIONAL], [UNROUTED]),
    ("M3 the result echoes the planned value, not the committed one", [REPORT], [ROUTED]),
]


def ignore(_directory: str, names: list[str]) -> list[str]:
    return [n for n in names if n in {"__pycache__", ".ruff_cache"} or n.endswith(".pyc")]


for part in ("tools", "tests", "saipen", "extensions", "bin"):
    shutil.copytree(repo / part, copy / part, ignore=ignore)
shutil.copy2(repo / "VERSION", copy / "VERSION")


def edit(edits: list[tuple[str, str]]) -> bytes:
    target = copy / OPS
    original = target.read_bytes()
    newline = "\r\n" if b"\r\n" in original else "\n"
    text = original.decode("utf-8")
    for old, new in edits:
        old, new = old.replace("\n", newline), new.replace("\n", newline)
        assert text.count(old) == 1, (text.count(old), old[:60])
        text = text.replace(old, new)
    target.write_bytes(text.encode("utf-8"))
    return original


def run(tree: Path) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", MODULE],
        cwd=str(tree / "tools"), env=env, stdin=subprocess.DEVNULL, capture_output=True,
        timeout=1800, check=False,
    )
    return proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", errors="replace")


def reds(out: str) -> frozenset[str]:
    return frozenset(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", out, flags=re.MULTILINE))


REPEAT = 3
assert (copy / VERIFIER[0]).read_bytes() == (repo / VERIFIER[0]).read_bytes()
verifier = oracle.verifier_identity(COMMAND, VERIFIER, repo)
for attempt in range(REPEAT):
    code, out = run(copy)
    ran = re.search(r"Ran \d+ tests", out)
    print(f"CONTROL {attempt + 1}/{REPEAT} unmutated copy: exit {code}, "
          f"{ran.group(0) if ran else out[-300:]}")
    assert code == 0, out[-2000:]

undetected = unstable = 0
for label, edits, expected in MUTATIONS:
    original = edit(edits)
    runs = [run(copy) for _ in range(REPEAT)]
    (copy / OPS).write_bytes(original)
    seen = [reds(out) for _code, out in runs]
    always = frozenset.intersection(*seen)
    sometimes = frozenset.union(*seen) - always
    missing = sorted(set(expected) - always)
    detected = all(code != 0 for code, _out in runs) and not missing
    undetected += 0 if detected else 1
    unstable += 1 if sometimes else 0
    print(f"{label}: {'DETECTED' if detected else 'NOT DETECTED'} in {REPEAT} of {REPEAT}")
    for name in sorted(always):
        print(f"      red: {name}" + ("" if name in expected else "  (not named for this mutation)"))
    for name in missing:
        print(f"      EXPECTED RED, STAYED GREEN: {name}")
    for name in sorted(sometimes):
        print(f"      UNSTABLE: {name}")

edit([PROVISIONAL, PROJECTION, REPORT])
red_code, red_out = run(copy)
green_code, green_out = run(repo)
print(f"command: {COMMAND} (cwd tools/)")
print(f"verifier:{verifier[:16]}  ({VERIFIER[0]}, byte-identical in both trees)")
print(f"FAIL subject:{oracle.oracle_digest(copy, SUBJECT)[:16]}  exit {red_code}  "
      f"red: {', '.join(sorted(reds(red_out)))}")
print(f"PASS subject:{oracle.oracle_digest(repo, SUBJECT)[:16]}  exit {green_code}  "
      f"{(re.search(r'Ran [0-9]+ tests', green_out) or [''])[0]}")
print(f"mutations {len(MUTATIONS)}, undetected {undetected}, with an unstable test {unstable}")
raise SystemExit(0 if red_code != 0 and green_code == 0 and not undetected and not unstable else 1)
