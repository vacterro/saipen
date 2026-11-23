"""T-1889 RED CONTROL: the module must FAIL when the declaration is IGNORED.

This is a MUTATION control, and the choice is forced by the repository, not by
convenience: `tools/saipen_engine/focused_unit.py` is an intent-to-add index
entry (its index blob is 0 bytes and `git diff --cached` shows no diff), so
there is no git-recorded pre-fix baseline to fetch. `git show HEAD:...` reports
it "exists on disk, but not in 'HEAD'". Inventing a baseline would be worse
than not having one.

So the defect injected here is the one that actually threatens this feature:
the resolver exists, the wiring exists, and the copy IGNORES the decision. That
is how a selection-aware copy fails silently -- every declaration is recorded,
nothing narrows, and a reader sees "DECLARED" in a record while 1815 MiB is
copied. The mutation makes `resolve` always answer FULL and `copy_plan` always
ask for everything.

Expected RED shape, and what each failure means:

  * `test_a_declared_module_copies_no_history` fails because `.git` arrives
    anyway: the copy does not honour the decision;
  * `test_the_decision_is_in_the_evidence_record` fails because the record says
    FULL for a declared module;
  * `test_the_declaration_is_load_bearing_for_a_real_reader` fails in its
    STARVED arm: with the mutation the undeclared run still sees the evidence
    and passes, which is the false green the real test exists to prevent.

Pure-resolver tests stay GREEN, which is correct: the resolver is not the
mutated part, and a control that broke everything would prove nothing about
which assertions carry weight.

The copy is made with the project's own copier in FULL scope. Nothing in the
live tree is written.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import core_unit  # noqa: E402
from saipen_engine.test_runner import _ignore_copy  # noqa: E402

MODULE = "tools/saipen_engine/sandbox_scope.py"

#: One surgical edit: `resolve` keeps its signature, its manifest read and its
#: return shape, and answers FULL/empty for every input. Nothing else in the
#: module changes, so a failure can only be about the DECISION being ignored --
#: not about a helper having been deleted.
MUTATION_PAIRS = [
    (
        '    undeclared = [name for name in patterns if name not in modules]\n'
        '    if undeclared:\n',
        '    undeclared = [name for name in patterns if name not in modules]\n'
        '    undeclared = list(patterns)  # MUTATION: treat every module as undeclared\n'
        '    if undeclared:\n',
    ),
]


def main() -> int:
    held = Path(tempfile.mkdtemp(prefix="t1889-red-"))
    try:
        sandbox = held / "project"
        core_unit.copy_tree_consistent(ROOT, sandbox, _ignore_copy, scope=None)
        target = sandbox / MODULE
        original = target.read_text(encoding="utf-8")
        mutated = original
        for old, new in MUTATION_PAIRS:
            if old not in mutated:
                print(json.dumps({"control": "VOID", "reason":
                                  "mutation anchor not found", "anchor": old}, indent=2))
                return 3
            mutated = mutated.replace(old, new, 1)
        target.write_text(mutated, encoding="utf-8")
        facts = {
            "mutated_module": MODULE,
            "changed_bytes": len(mutated) - len(original),
            "mutation_applied": "MUTATION: treat every module as undeclared" in mutated,
            "resolver_helpers_intact": all(
                needle in mutated for needle in ("def identity(", "def problem(",
                                                 "def is_current(", "def copy_plan(")
            ),
            "test_module_present": (sandbox / "tools/test_t1889_sandbox_scope.py").is_file(),
        }
        print(json.dumps({"control": "mutation: declaration ignored", **facts}, indent=2))
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover",
             "-s", "tools", "-p", "test_t1889_sandbox_scope.py", "-v"],
            cwd=sandbox, capture_output=True, text=True,
        )
        print("--- stdout+stderr ---")
        print(completed.stdout[-9000:])
        print(completed.stderr[-6000:])
        verdict = ("RED (declaration ignored, as required)"
                   if completed.returncode != 0
                   else "GREEN (control is void: a copy that ignores the "
                        "declaration passes every test)")
        print("--- verdict ---")
        print(json.dumps({"returncode": completed.returncode, "verdict": verdict}, indent=2))
        return 0 if completed.returncode != 0 else 1
    finally:
        shutil.rmtree(held, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
