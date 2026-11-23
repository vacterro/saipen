"""T-1884 red control: remove the prevention rule, keep every test byte.

The rule is located by its own guarded block in `_plan_transition` and replaced
with the pre-fix behaviour (nothing), in a temp copy of `operations.py`. A
throwaway module tree is built so the CLI under test is the copy, never the
working tree.

The measured pre-fix behaviour was twofold, and the control proves BOTH halves:

  * a stale blocker was INHERITED by the next phase (3 tests red);
  * a GENUINE gate was RIDDEN OVER -- SHIP->BUILD succeeded while `HELD` was
    set, carrying it into BUILD (3 more tests red).

Only the clean-project test stays green, which is what makes the control
meaningful: the rule did not create refusal authority, it restored it.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

BEGIN = "    # T-1884 (E10/E11): a transition is a lifecycle event"
END = "    # SRC-305 DRIFT-05 / SRC-306 D-05 (T-1880)"

#: Blocker inheritance: the pre-fix transition kept the field.
INHERITANCE_RED = {
    "test_e10_a_stale_blocker_is_not_inherited_by_the_next_phase",
    "test_e11_leaving_blocked_clears_the_phase_own_blocker",
    "test_an_unrelated_blocked_ticket_does_not_block_the_transition",
}
#: Gate ride-over: the pre-fix transition ignored a genuine gate entirely.
RIDEOVER_RED = {
    "test_a_held_gate_refuses_and_is_preserved",
    "test_a_recognised_class_token_refuses_and_is_preserved",
    "test_a_causally_related_blocked_ticket_refuses",
}
EXPECTED_RED = INHERITANCE_RED | RIDEOVER_RED
EXPECTED_GREEN = {"test_a_clean_project_transitions_as_before"}


def _strip_rule(source: str) -> str:
    start = source.find(BEGIN)
    if start < 0:
        raise SystemExit("refusing: prevention rule not found")
    end = source.find(END, start)
    if end < 0:
        raise SystemExit("refusing: rule terminator not found")
    return source[:start] + source[end:]


def _build_tree() -> Path:
    """A throwaway project whose `tools/` carries the RED operations.py.

    Only the two source directories the CLI imports are copied; the point is a
    module tree, not a runnable SAIPEN project.
    """
    temp = Path(tempfile.mkdtemp(prefix="t1884-red-"))
    for name in ("tools", "saipen", "extensions", "bootstrap"):
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, temp / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    target = temp / "tools" / "saipen_engine" / "operations.py"
    original = target.read_text(encoding="utf-8")
    target.write_text(_strip_rule(original), encoding="utf-8")
    # The tests under test must be the SAME bytes.
    shutil.copy2(TOOLS / "test_t1884_transition_blocker_inheritance.py",
                 temp / "tools" / "test_t1884_transition_blocker_inheritance.py")
    for support in ("test_fixture_support.py", "test_hermetic_env.py"):
        shutil.copy2(TOOLS / support, temp / "tools" / support)
    return temp


def _run_suite(tree: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PWD", None)
    env.pop("OLDPWD", None)
    env["PYTHONPATH"] = str(tree / "tools")
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "-v",
         "test_t1884_transition_blocker_inheritance"],
        cwd=str(tree / "tools"), capture_output=True, text=True, env=env, timeout=900,
    )
    outcomes: dict[str, str] = {}
    for line in proc.stderr.splitlines():
        match = re.match(r"^(test_\w+) \(.*?\) \.\.\. (ok|FAIL|ERROR|skipped.*)$", line)
        if match:
            outcomes[match.group(1)] = (
                "PASS" if match.group(2) == "ok" else "FAIL"
            )
    if not outcomes:
        print(proc.stdout[-2000:])
        print(proc.stderr[-3000:])
    return outcomes


def main() -> int:
    tree = _build_tree()
    try:
        print(f"red tree: {tree}")
        outcomes = _run_suite(tree)
        red = {n for n, v in outcomes.items() if v != "PASS"}
        print(f"\nran {len(outcomes)}; failing: {sorted(red)}")

        unexpected = red - EXPECTED_RED
        missed = EXPECTED_RED - red
        broke = {n for n in EXPECTED_GREEN if outcomes.get(n) != "PASS"}

        if unexpected:
            print("UNEXPECTED red (test does not isolate the rule):")
            for name in sorted(unexpected):
                print(f"  {name}")
        if missed:
            print("EXPECTED-red stayed GREEN (control does not bite):")
            for name in sorted(missed):
                print(f"  {name}")
        if broke:
            print("SECURITY/clean tests broke under the control:")
            for name in sorted(broke):
                print(f"  {name}")

        ok = not unexpected and not missed and not broke
        print(
            f"\nRED CONTROL {'OK' if ok else 'BROKEN'}: "
            f"{len(INHERITANCE_RED & red)}/{len(INHERITANCE_RED)} inheritance "
            f"tests red, {len(RIDEOVER_RED & red)}/{len(RIDEOVER_RED)} "
            f"gate-ride-over tests red, "
            f"{len(EXPECTED_GREEN) - len(broke)}/{len(EXPECTED_GREEN)} "
            "clean-project test still green."
        )
        print(json.dumps({"outcomes": outcomes}, indent=1, sort_keys=True))
        return 0 if ok else 1
    finally:
        shutil.rmtree(tree, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
