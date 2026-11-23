"""T-1771 mutation controls after the ownership correction, in a disposable copy.

    python mutate1771_owner.py <copy-root> <evidence-dir> <scratch-profile>

The first cut derived the request clause before `_binding` admitted the caller,
so a call refused to another session wrote the owner's Contract (review probe,
2026-10-14). The corrected subject derives after the binding and after the
inputs load. Each mutation names the tests that must go red. The control and
every mutation run REPEATS times in fresh interpreters; a test red in some
repetitions only is reported as flaky. The copy is restored after each one.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPEATS = 3
MODULE = "test_t1771_measure_then_finish"
SUBJECT = "tools/saipen_engine/regression_execution.py"

CLOSES = "test_the_first_finish_after_one_measurement_closes"
STALE = "test_a_contract_changed_after_measurement_still_refuses"
FOREIGN = "test_a_call_refused_to_another_session_writes_no_clause"
INPUTS = "test_a_call_refused_for_its_inputs_writes_no_clause"

DERIVE = (
    "        # Derived only after the binding admitted this session as the owner of\n"
    "        # the active Work and its inputs loaded: a call refused before this\n"
    "        # point writes nothing.\n"
    "        if _derive_request_clauses(root, board, ticket):\n"
    "            docs, state, board, tail = ops._read(root)\n"
    "            binding = _binding(root, ticket, agent, docs, state)\n"
)
LOAD = "        material = _load(root, contract_path)\n"

#: name -> (edit, tests that must go red). An edit is (old, new) inside the
#: subject, or (None, key) for a whole file from WHOLE.
MUTATIONS = {
    "control": (None, set()),
    "the engine before this Work": ((None, "before"), {CLOSES}),
    "the first cut, derived before the ownership check": ((None, "first-cut"), {FOREIGN, INPUTS}),
    "the derivation is defined and never called": ((DERIVE, ""), {CLOSES}),
    "derived without retaking the binding": (
        (DERIVE, DERIVE.replace("            binding = _binding(root, ticket, agent, docs, state)\n", "")),
        {CLOSES},
    ),
    "derived before the inputs load": ((DERIVE, ""), {INPUTS}),
    "the binding stops covering the clauses": (
        (
            '            "contract_sha256": _sha(_json(contract)),\n',
            '            "contract_sha256": _sha(_json({key: value for key, value in '
            'contract.items() if key not in ("clauses", "interpretation_revision", '
            '"derived_at")})),\n',
        ),
        {STALE},
    ),
}


def run_once(copy: Path, env: dict) -> tuple[set, int]:
    done = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", MODULE, "-v"],
        cwd=copy / "tools",
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    red = set(re.findall(r"^(?:FAIL|ERROR): (\w+) ", done.stderr, re.MULTILINE))
    ran = re.search(r"^Ran (\d+) test", done.stderr, re.MULTILINE)
    if ran is None:
        raise RuntimeError("no unittest summary:\n" + done.stderr[-1500:])
    return red, int(ran.group(1))


def mutated(name: str, text: str, edit: tuple[str, str]) -> str:
    old, new = edit
    if text.count(old) != 1:
        raise RuntimeError(f"anchor not unique for {name!r}: {old.strip()[:70]!r}")
    text = text.replace(old, new)
    if name == "derived before the inputs load":
        if text.count(LOAD) != 1:
            raise RuntimeError("load anchor not unique")
        text = text.replace(LOAD, DERIVE + LOAD)
    return text


def main(argv: list[str]) -> int:
    copy, evidence, profile = (Path(item).resolve() for item in argv[:3])
    whole = {
        "before": evidence / "before" / "regression_execution.py",
        "first-cut": evidence / "first-cut" / "regression_execution.py",
    }
    env = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
    env.pop("CLAUDE_CONFIG_DIR", None)
    env.update(
        USERPROFILE=str(profile),
        HOME=str(profile),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONIOENCODING="utf-8",
    )
    target = copy / SUBJECT
    pristine = target.read_bytes()
    crlf = b"\r\n" in pristine
    problems = 0
    for name, (edit, expected) in MUTATIONS.items():
        try:
            if edit is not None:
                if edit[0] is None:
                    target.write_bytes(whole[edit[1]].read_bytes())
                else:
                    text = mutated(name, pristine.decode("utf-8").replace("\r\n", "\n"), edit)
                    target.write_bytes(
                        (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")
                    )
            runs = [run_once(copy, env) for _ in range(REPEATS)]
        finally:
            target.write_bytes(pristine)
        reds = [red for red, _ in runs]
        stable = all(red == reds[0] for red in reds)
        verdict = "as expected" if stable and reds[0] == expected else "UNEXPECTED"
        if not stable:
            verdict = "FLAKY"
        if verdict != "as expected":
            problems += 1
        print(f"{name}: ran {runs[0][1]}, red {len(reds[0])} -- {verdict}", flush=True)
        if verdict != "as expected":
            print(f"    expected: {sorted(expected)}")
            print(f"    got:      {[sorted(r) for r in reds]}")
    print(f"mutations: {len(MUTATIONS) - 1}, repetitions each: {REPEATS}, problems: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
