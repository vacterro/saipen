"""T-1897 red/green control: one verifier, two classifier generations.

The defect this proves was measured on a real `--gate core` run, not built to
fit a test: 41 problems, 40 of them `unclassified` with no subject, so
`finding_key` (rule|kind|subject) collapsed 38 distinct offending paths into
ONE key and `finding_ownership` routed the whole set to UNKNOWN.

This script loads BOTH classifier generations through the same loader and runs
the SAME assertions against each. The pre-fix module is the archived blob that
was live before the change; the post-fix module is the working tree.

Because the verifier is this script and it does not change between the two
halves, the recorded regression pair attributes the verdict to the SUBJECT
(the classifier) and nothing else.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PREFIX = Path(__file__).resolve().parent / "prefix-findings.py"
CURRENT = ROOT / "tools" / "saipen_engine" / "findings.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MANIFEST = (
    "runtime manifest names a file git does not track: {path} -- it exists here "
    "and in no clone, so this home ships complete and every checkout of it does not"
)
PROVENANCE = (
    "closure provenance does not resolve: EX-000022 was verified against "
    "installed engine generation sha256:aa... but the running engine is "
    "sha256:bb... -- the dependency moved (rollback or upgrade)"
)
COVERAGE = (
    "coverage gap -- 2 shipped document(s) are read by no check and declared "
    "exempt by none: saipen/COMMANDS_REFERENCE.md, docs/x.md"
)
LEGIT = "ticket T-1446 has no ticket-bearing closure event at file.py:12"


def assertions(mod) -> dict:
    """The measured conditions, as plain booleans -- a value, not a mood."""
    manifest_keys = {
        mod.classify("problem", MANIFEST.format(path=f"tools/probe_{index}.py"))[
            "finding_key"
        ]
        for index in range(40)
    }
    coverage = mod.classify("problem", COVERAGE)
    provenance = mod.classify("problem", PROVENANCE)
    legit = mod.classify("problem", LEGIT)
    manifest = mod.classify("problem", MANIFEST.format(path="tools/a.py"))
    return {
        # The collapse: 40 distinct offending files must be 40 findings.
        "manifest_keys_40": len(manifest_keys) == 40,
        # Each named family must reach a rule of its own.
        "manifest_named": manifest["rule_id"] != "unclassified",
        "manifest_subject": manifest["subject_id"] == "tools/a.py",
        "coverage_named": coverage["rule_id"] != "unclassified",
        "provenance_named": provenance["rule_id"] != "unclassified",
        "provenance_subject": provenance["subject_id"] == "EX-000022",
        # The control: an already-classified family must not be disturbed.
        "legit_still_work": legit["subject_kind"] == "work"
        and legit["subject_id"] == "T-1446",
    }


def main() -> int:
    prefix = load("t1897_prefix", PREFIX)
    current = load("t1897_current", CURRENT)
    before = assertions(prefix)
    after = assertions(current)

    red_half = not before["manifest_keys_40"] and not before["provenance_named"]
    green_half = all(after.values())
    control_ok = before["legit_still_work"] and after["legit_still_work"]

    print("PREFIX  ", before)
    print("NOW     ", after)
    print("CONTROL ", "OK" if control_ok else "BROKEN")
    print(
        "VERDICT ",
        "RED->GREEN" if red_half and green_half and control_ok else "NOT PROVEN",
    )
    return 0 if red_half and green_half and control_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
