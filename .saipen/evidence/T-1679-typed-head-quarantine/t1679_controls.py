"""T-1679: the regression pair on one verifier, and a red control per property.

Usage: t1679_controls.py <repo> <copy>

The copy holds tools/, tests/, saipen/, extensions/ and bin/ of the tree. The
unmutated control and every mutation run three times; a test red in some
repetitions only is reported. The pre-fix subject is the copy with the journal
bound taken out of the cut and out of the loader, which is the engine as it
answered the live project: HISTORY_LEDGER_CORRUPT, FORENSICALLY_UNRECOVERABLE,
no command.
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

MODULE = "test_t1679_typed_head_quarantine"
COMMAND = f"python -B -m unittest {MODULE}"
VERIFIER = (f"tools/{MODULE}.py",)
LOG = "tools/saipen_engine/log.py"
OPS = "tools/saipen_engine/operations.py"
LA = "tools/saipen_engine/lifecycle_authority.py"
SUBJECT = (LOG, OPS, LA, "tools/saipen_engine/reconcile.py")

TWO = "test_recover_names_the_quarantine_and_the_two_commands_restore_the_project"
BETWEEN = "test_between_the_two_commands_the_quarantined_rows_still_refuse"
FLOOR = "test_the_floor_below_the_marker_is_the_boundary"
VOCAB = "test_an_adoption_is_not_a_closure_and_an_attestation_is"

NO_BOUND = (LOG,
            "    journal = journal_floor is not None and "
            "(last_event is None or journal_floor < last_event)\n",
            "    journal = False\n")
NO_FLOOR = (OPS,
            "                journal_floor=_journal_floor(root, snapshot.events)[0],\n",
            "                journal_floor=None,\n")
MUTATIONS = [
    ("M1 the cut ignores the journal floor", [NO_BOUND], [TWO, BETWEEN, FLOOR]),
    ("M2 the loader hands the cut no floor", [NO_FLOOR], [TWO, BETWEEN]),
    ("M3 the quarantine event names no rows",
     [(OPS,
       "        rows = _lifecycle_authority.typed_rows(\n"
       "            cut_events, _board, cut.snapshot.events, cut.journal_floor\n"
       "        )\n",
       "        rows = []\n")], [TWO, BETWEEN]),
    ("M4 assess does not read the rows back from the quarantine event",
     [(LA, "            and TYPED_HEAD_MARKER in text\n        ):\n",
       "            and False\n        ):\n")], [TWO, BETWEEN]),
    ("M5 the quarantine event carries the typed task as its tag",
     [(OPS, "        task = None\n\n    def mutate(text: str, event: int) -> str:\n"
            "        return patch_state(text, {\"last_event\": event, \"updated\": utc, "
            "\"agent\": agent})\n\n    plan = _state_only_plan(\n        root,\n"
            "        \"quarantine_log_tail\",\n",
       "        task = state.get(\"task\")\n\n    def mutate(text: str, event: int) -> str:\n"
       "        return patch_state(text, {\"last_event\": event, \"updated\": utc, "
       "\"agent\": agent})\n\n    plan = _state_only_plan(\n        root,\n"
       "        \"quarantine_log_tail\",\n")], [TWO]),
    ("M6 an adoption counts as a closure",
     [(LA, "            op_id.startswith(\"reconcile-\") and _ATTESTATION in text\n",
       "            op_id.startswith(\"reconcile-\")\n")], [VOCAB]),
    ("M7 the quarantine reads with the narrow observable set",
     [(OPS,
       "TYPED_HEAD_QUARANTINE_OBSERVABLE = (*TAIL_QUARANTINE_OBSERVABLE, \"state\", "
       "\"lifecycle_authority\")\n",
       "TYPED_HEAD_QUARANTINE_OBSERVABLE = TAIL_QUARANTINE_OBSERVABLE\n")], [TWO, BETWEEN]),
]


def ignore(_directory: str, names: list[str]) -> list[str]:
    return [n for n in names if n in {"__pycache__", ".ruff_cache"} or n.endswith(".pyc")]


for part in ("tools", "tests", "saipen", "extensions", "bin"):
    shutil.copytree(repo / part, copy / part, ignore=ignore)
shutil.copy2(repo / "VERSION", copy / "VERSION")


def edit(edits: list[tuple[str, str, str]]) -> dict[str, bytes]:
    originals: dict[str, bytes] = {}
    for rel, old, new in edits:
        target = copy / rel
        raw = target.read_bytes()
        originals.setdefault(rel, raw)
        newline = "\r\n" if b"\r\n" in raw else "\n"
        text = raw.decode("utf-8")
        old, new = old.replace("\n", newline), new.replace("\n", newline)
        assert text.count(old) == 1, (rel, text.count(old), old[:70])
        target.write_bytes(text.replace(old, new).encode("utf-8"))
    return originals


def restore(originals: dict[str, bytes]) -> None:
    for rel, raw in originals.items():
        (copy / rel).write_bytes(raw)


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
          f"{ran.group(0) if ran else out[-300:]}", flush=True)
    assert code == 0, out[-2000:]

undetected = unstable = 0
for label, edits, expected in MUTATIONS:
    originals = edit(edits)
    runs = [run(copy) for _ in range(REPEAT)]
    restore(originals)
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
    sys.stdout.flush()

edit([NO_BOUND, NO_FLOOR])
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
