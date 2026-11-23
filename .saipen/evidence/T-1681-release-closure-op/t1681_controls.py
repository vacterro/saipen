"""T-1681: the regression pair on one verifier, and a red control per property.

Usage: t1681_controls.py <repo> <copy>

The copy holds tools/, tests/, saipen/, extensions/ and bin/ of the tree. The
unmutated control and every mutation run three times; a test red in some
repetitions only is reported. The pre-fix subject is the copy with both
halves of the repair taken out: the release no longer names its closure id,
and the ledger no longer resolves an id a release record names -- the engine
that closed T-1679 at E-13300/E-13301 under an unresolvable op id.
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

MODULE = "test_t1681_release_closure_op"
COMMAND = f"python -B -m unittest {MODULE}"
VERIFIER = (f"tools/{MODULE}.py",)
REL = "tools/saipen_engine/release.py"
JOURNAL = "tools/saipen_engine/journal.py"
SUBJECT = (REL, JOURNAL)

NOSHIP = "test_a_no_publish_ship_closes_under_an_id_the_ledger_resolves"
RECOVERED = "test_a_recovered_ship_closes_under_an_id_the_ledger_resolves"
FULL = "test_the_full_publish_closure_records_the_same_id"
GRAMMAR = "test_a_release_record_vouches_only_for_a_well_formed_id"

NO_NAME = (REL, '    _try_journal(journal, "update", closure_op_id=closure_op_id)\n',
           "    del closure_op_id\n")
NO_ALIAS = (JOURNAL,
            '            if name.startswith("release-"):\n'
            "                names.update(_release_closure_ids(base_dir / name))\n",
            "")
MUTATIONS = [
    ("M1 the release does not name its closure id", [NO_NAME], [NOSHIP, RECOVERED, FULL]),
    ("M2 the ledger ignores the id a release names", [NO_ALIAS],
     [NOSHIP, RECOVERED, FULL, GRAMMAR]),
    ("M3 any string a release record names resolves",
     [(JOURNAL,
       '    if isinstance(alias, str) and op_id_provenance(alias) == "canonical":\n',
       "    if isinstance(alias, str):\n")], [GRAMMAR]),
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

edit([NO_NAME, NO_ALIAS])
red_code, red_out = run(copy)
green_code, green_out = run(repo)
print(f"command: {COMMAND} (cwd tools/)")
print(f"verifier:{verifier[:16]}  ({VERIFIER[0]}, byte-identical in both trees)")
print(f"FAIL subject:{oracle.oracle_digest(copy, SUBJECT)[:16]}  exit {red_code}  "
      f"red: {', '.join(sorted(reds(red_out)))}")
print(f"PASS subject:{oracle.oracle_digest(repo, SUBJECT)[:16]}  exit {green_code}  "
      f"{(re.search(r'Ran [0-9]+ tests', green_out) or [''])[0]}")
print(f"mutations {len(MUTATIONS)}, undetected {undetected}, with an unstable test {unstable}")
shutil.rmtree(copy, ignore_errors=True)
raise SystemExit(0 if red_code != 0 and green_code == 0 and not undetected and not unstable else 1)
