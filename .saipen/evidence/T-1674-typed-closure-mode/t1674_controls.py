"""T-1674: the regression pair on one verifier, and a red control per property.

Usage: t1674_controls.py <repo> <copy>

The copy holds tools/, tests/, saipen/, extensions/ and bin/ of the tree. The
unmutated control and every mutation run three times; a test red in some
repetitions only is reported. The pre-fix subject is the copy with the new
recovery class switched off, which is the engine as it answered the AUDAPACK
copy: RESIDUAL_DEFECTS and no command.
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

MODULE = "test_t1674_typed_closure_mode"
COMMAND = f"python -B -m unittest {MODULE}"
VERIFIER = (f"tools/{MODULE}.py",)
REC = "tools/saipen_engine/reconcile.py"
SUBJECT = (REC,)

CLI = "test_recovery_names_one_approved_command_and_the_project_is_valid_after_it"
ONLY = "test_only_a_value_outside_the_closed_set_is_taken"
CLAIM = "test_the_claim_is_dropped_with_the_closure"
BOUND = "test_the_row_state_is_bound_to_is_left_to_the_current_done_classes"

OFF = ('            section == "## DONE"\n            and typed_mode\n',
       '            False\n            and typed_mode\n')
MUTATIONS = [
    ("M1 the class is switched off", [OFF], [CLI, ONLY, CLAIM, BOUND]),
    ("M2 a value inside the closed set is taken too",
     [("            and typed_mode.lower() not in CLOSURE_MODES\n",
       "            and typed_mode.lower()\n")], [ONLY]),
    ("M3 the reopen asks for no approval",
     [('                    "_class": "typed-closure-mode",\n'
       '                    "ticket": tid,\n'
       '                    "surface": "board",\n'
       '                    "from_section": "## DONE",\n'
       '                    "to_section": "## TODO",\n'
       '                    "fields": dropped,\n'
       '                    "requires_approval": True,\n',
       '                    "_class": "typed-closure-mode",\n'
       '                    "ticket": tid,\n'
       '                    "surface": "board",\n'
       '                    "from_section": "## DONE",\n'
       '                    "to_section": "## TODO",\n'
       '                    "fields": dropped,\n'
       '                    "requires_approval": False,\n')], [ONLY]),
    ("M4 the row STATE is bound to is taken",
     [('            and tid != (state or {}).get("task")\n', "            and True\n")], [BOUND]),
    ("M5 the claim stays on the reopened row",
     [('            dropped = _reopen_field_removals(ticket.get("raw", ""))\n'
       '            for name in ("owner", "claim_time"):\n',
       '            dropped = _reopen_field_removals(ticket.get("raw", ""))\n'
       '            for name in ():\n')], [CLAIM]),
]


def ignore(_directory: str, names: list[str]) -> list[str]:
    return [n for n in names if n in {"__pycache__", ".ruff_cache"} or n.endswith(".pyc")]


for part in ("tools", "tests", "saipen", "extensions", "bin"):
    shutil.copytree(repo / part, copy / part, ignore=ignore)
shutil.copy2(repo / "VERSION", copy / "VERSION")


def edit(edits: list[tuple[str, str]]) -> bytes:
    target = copy / REC
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
    (copy / REC).write_bytes(original)
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

edit([OFF])
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
