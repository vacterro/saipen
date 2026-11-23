"""T-1881 RED CONTROL: the prohibition gate removed, same tests, same fixture.

Two surgical neuterings, each restoring the pre-fix behaviour for exactly what
it touches and nothing else:

  RED-1  release._publication_forbidden -> None   (planner + apply gate gone)
  RED-2  release_attempt.record -> a no-op        (attempt ledger gone)

Both are applied to the LIVE modules in-process, so the module under test is
byte-identical to the one the green control runs. If either mechanism is
load-bearing, its assertions fail here.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = next(
    parent / "tools"
    for parent in Path(__file__).resolve().parents
    if (parent / "tools" / "saipen_engine").is_dir()
)
sys.path.insert(0, str(TOOLS))

import test_t1881_publication_prohibition as subject
from saipen_engine import release, release_attempt


def run(label, loader):
    print("=" * 72)
    print(label)
    print("=" * 72)
    suite = loader()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"\n{label}: failures={len(result.failures)} errors={len(result.errors)}"
          f" ran={result.testsRun}")
    return result


def plan_and_apply():
    return unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromName(
            "test_t1881_publication_prohibition.PlanTimeProhibitionTests"
        ),
        unittest.defaultTestLoader.loadTestsFromName(
            "test_t1881_publication_prohibition.ApplyTimeProhibitionTests"
        ),
        # The batch route RESOLVES its own carrier inside plan_release, so its
        # gate is measured separately: a check that lived only in plan_release
        # would go green above and still publish a forbidden batch.
        unittest.defaultTestLoader.loadTestsFromName(
            "test_t1881_publication_prohibition.BatchPlannerProhibitionTests"
        ),
    ])


def ledger():
    return unittest.defaultTestLoader.loadTestsFromName(
        "test_t1881_publication_prohibition.AttemptLedgerTests"
    )


with patch.object(release, "_publication_forbidden", return_value=None):
    r1 = run("RED-1: release._publication_forbidden neutered (no gate at all)", plan_and_apply)

with patch.object(release_attempt, "record",
                  return_value={"ok": True, "path": "(suppressed)", "row": {}}):
    r2 = run("RED-2: release_attempt.record neutered (no attempt ledger)", ledger)

print("=" * 72)
print(f"TOTAL RED CONTROL: failures={len(r1.failures) + len(r2.failures)}"
      f" errors={len(r1.errors) + len(r2.errors)}"
      f" ran={r1.testsRun + r2.testsRun}")
sys.exit(0 if (r1.failures or r1.errors or r2.failures or r2.errors) else 1)
