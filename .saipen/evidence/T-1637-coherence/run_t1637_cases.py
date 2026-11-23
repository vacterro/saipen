"""Drive only the T-1637 audit controls red, with audit_checks' own harness.

Usage: python run_t1637_cases.py <tree root with .saipen>
Each case runs in its own copy of the tree (tools/, saipen/, extensions/,
bin/, VERSION, root docs, .saipen/), so cases run in parallel.
"""
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

tree = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(tree / "tools"))
import audit_checks as A  # noqa: E402

cases = [case for case in A.CASES if str(case[0]).startswith("T-1637")]
assert len(cases) == 12, len(cases)
base = Path(tempfile.mkdtemp(prefix="t1637_cases_"))


def copy_tree(dest: Path) -> None:
    shutil.copytree(tree, dest, ignore=A.IGNORE)


pristine = base / "pristine"
copy_tree(pristine)
control = A.validator_output(pristine)


def run(index_case):
    index, case = index_case
    label, rel, mutation, expected = case[0], case[1], case[2], case[3]
    root = base / f"case{index}"
    copy_tree(root)
    target = root / rel
    before = target.read_text(encoding="utf-8")
    occurrences = A.anchor_occurrences(mutation, target)
    target.write_text(mutation(before), encoding="utf-8")
    output = A.validator_output(root)
    shutil.rmtree(root, ignore_errors=True)
    return label, expected, occurrences, expected in control, expected in output


try:
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run, enumerate(cases)))
finally:
    shutil.rmtree(base, ignore_errors=True)

ok = True
for label, expected, occurrences, in_control, in_mutant in results:
    verdict = "RED" if (in_mutant and not in_control) else "DEAD"
    ok &= verdict == "RED"
    print(f"{verdict} anchor={occurrences} control_has={in_control} {expected!r:28s} {label}")
print("ALL RED" if ok else "SOME DEAD")
