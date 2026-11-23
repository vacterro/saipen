"""T-1670: the pre-fix control, the post-fix acceptance, a red control per property.

Usage: t1670_controls.py <old-tree> <new-tree> <work>

<old-tree> is the engine before T-1670, <new-tree> the one after. Both get the
SAME small clause appended to saipen/UI.md, a document no route loads, until
the protocol total passes the old 327 KiB aggregate cap. Then every single
mutation of the new tree runs the new test module three times.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

old_tree, new_tree, work = (Path(arg).resolve() for arg in sys.argv[1:4])
assert not work.exists(), work
CAP = 327 * 1024
CLAUSE = b"\nA small, valid clause of protocol law, routed nowhere.\n"
PB = "tools/protocol_budget.py"


def ignore(_directory, names):
    return [n for n in names if n in {"__pycache__", ".ruff_cache"} or n.endswith(".pyc")]


def copy_of(tree: Path, name: str) -> Path:
    target = work / name
    for part in ("tools", "tests", "saipen", "extensions", "bin", "bootstrap"):
        shutil.copytree(tree / part, target / part, ignore=ignore)
    shutil.copy2(tree / "VERSION", target / "VERSION")
    return target


def total(tree: Path) -> int:
    return sum(len(p.read_bytes().replace(b"\r\n", b"\n")) for p in (tree / "saipen").rglob("*.md"))


def grow_past_cap(tree: Path) -> int:
    ui = tree / "saipen" / "UI.md"
    need = CAP - total(tree) + 1
    ui.write_bytes(ui.read_bytes() + CLAUSE * (need // len(CLAUSE) + 1))
    return total(tree)


def run(tree: Path, *modules: str) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", *modules], cwd=str(tree / "tools"), env=env,
        stdin=subprocess.DEVNULL, capture_output=True, timeout=1800, check=False,
    )
    return proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", errors="replace")


def reds(out: str) -> frozenset:
    return frozenset(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", out, flags=re.MULTILINE))


ok = True
old = copy_of(old_tree, "old")
size = grow_past_cap(old)
code, out = run(old, "test_protocol_registry")
cause = re.findall(r"AssertionError: (\d+ not less than or equal to \d+)", out)
print(f"PRE-FIX  old engine, UI.md grown, total {size}: exit {code}, red {sorted(reds(out))}, "
      f"cause {cause}")
ok &= code != 0 and reds(out) == {"test_every_declared_load_budget_is_measured_from_registry"}
ok &= bool(cause)

new = copy_of(new_tree, "new")
size = grow_past_cap(new)
code, out = run(new, "test_protocol_registry", "test_t1670_route_budgets")
ran = re.search(r"Ran \d+ tests", out)
print(f"POST-FIX new engine, same clause, total {size}: exit {code}, "
      f"{ran.group(0) if ran else out[-300:]}")
ok &= code == 0
shutil.rmtree(old, ignore_errors=True)

MODULE = "test_t1670_route_budgets"
MUTATIONS = [
    ("M1 the aggregate is a gate again",
     [(PB, "    file_limit = measured[\"budgets\"].get(\"single_doc\")\n",
       "    if measured[\"human_markdown_total\"] > 327 * 1024:\n"
       "        errors.append(\"human_markdown_total over the aggregate cap\")\n"
       "    file_limit = measured[\"budgets\"].get(\"single_doc\")\n")],
     ["test_pre_fix_control_a_routed_nowhere_clause_tripped_only_the_aggregate"]),
    ("M2 a declared dependency is not followed",
     [(PB, "        for dep in requires.get(token, ()):\n            visit(dep, (*path, token))\n",
       "        pass\n")],
     ["test_a_declared_dependency_chain_is_counted_whole"]),
    ("M3 a conditional reference counts as mandatory",
     [(PB, "    mandatory = _closure(must, requires or {})\n",
       "    mandatory = _closure([*must, *conditional], requires or {})\n")],
     ["test_an_optional_reference_does_not_inflate_the_mandatory_load"]),
    ("M4 no per-document guard",
     [(PB, "    if isinstance(file_limit, int):\n", "    if False:\n")],
     ["test_one_enormous_document_fails_even_where_no_route_loads_it"]),
    ("M5 a cycle is not refused",
     [(PB, "        if token in path:\n", "        if False:\n")],
     ["test_a_dependency_cycle_is_a_declaration_error"]),
]
undetected = unstable = 0
control = [run(new, MODULE) for _ in range(3)]
print("CONTROL unmutated x3:", [c for c, _ in control])
ok &= all(c == 0 for c, _ in control)
for label, edits, expected in MUTATIONS:
    originals = {}
    for rel, before, after in edits:
        target = new / rel
        raw = target.read_bytes()
        originals.setdefault(rel, raw)
        nl = "\r\n" if b"\r\n" in raw else "\n"
        text = raw.decode("utf-8")
        before, after = before.replace("\n", nl), after.replace("\n", nl)
        assert text.count(before) == 1, (label, rel, before[:60])
        target.write_bytes(text.replace(before, after).encode("utf-8"))
    runs = [run(new, MODULE) for _ in range(3)]
    for rel, raw in originals.items():
        (new / rel).write_bytes(raw)
    seen = [reds(out) for _, out in runs]
    always = frozenset.intersection(*seen)
    sometimes = frozenset.union(*seen) - always
    detected = set(expected) <= always and all(c != 0 for c, _ in runs)
    undetected += 0 if detected else 1
    unstable += 1 if sometimes else 0
    print(f"{label}: {'DETECTED' if detected else 'NOT DETECTED'} 3 of 3 by {sorted(always)}"
          + (f"; UNSTABLE {sorted(sometimes)}" if sometimes else ""))
ok &= not undetected and not unstable
shutil.rmtree(work, ignore_errors=True)
print("held:", ok)
raise SystemExit(0 if ok else 1)
