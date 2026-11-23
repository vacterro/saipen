"""T-1883 red control: the SAME test bytes against a copy with the defect back.

The copy is made in a temp dir; the working tree file is never touched. The one
edit reintroduces the measured defect -- `if live_blocked or cls is not None:`,
i.e. the mere existence of ANY `## BLOCKED` ticket vetoes the repair -- and
nothing else. The suite is then imported normally, so the failure set is
evidence about the tests, not about a hand-written probe.

Expected RED set: exactly the tests that assert unrelated blocks are irrelevant.
Expected GREEN set: every related-gate / class-token test, i.e. the security
coverage the handoff said must not be lost.
"""

from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

DEFECT_LINE = "    if cls is not None or related:"
DEFECT_REPLACEMENT = (
    "    if live_blocked or cls is not None:  # RED CONTROL: presence veto\n"
    "        related = list(live_blocked)\n"
)

EXPECTED_RED = {
    "test_t1883_reconcile_causality.UnrelatedBlocksCannotVetoTests."
    "test_ac01_incident_shape_repairs_the_proven_stale_blocker",
    "test_t1883_reconcile_causality.UnrelatedBlocksCannotVetoTests."
    "test_ac02_no_blocked_tickets_gives_the_same_verdict",
    "test_t1883_reconcile_causality.UnrelatedBlocksCannotVetoTests."
    "test_ac03_one_unrelated_block_changes_nothing",
    "test_t1883_reconcile_causality.UnrelatedBlocksCannotVetoTests."
    "test_ac04_one_hundred_unrelated_blocks_change_nothing",
    "test_t1883_reconcile_causality.AmbiguityFailsClosedTests."
    "test_ac06_a_blocked_set_with_no_relation_is_reported_not_trusted",
    # End-to-end pair: the same defect, through `reconcile_protocol_state`.
    "test_t1883_reconcile_causality.EndToEndVerdictTests."
    "test_ac01_the_incident_project_repairs_through_the_real_pipeline",
    "test_t1883_reconcile_causality.EndToEndVerdictTests."
    "test_ac02_the_same_project_without_blocks_gives_the_same_repair",
}
EXPECTED_RED_REACHABILITY = {
    "test_recovery_reachability.BlockerClassificationTests."
    "test_an_unrelated_board_block_does_not_refuse",
}


def _build_red_copy() -> Path:
    source = (TOOLS / "saipen_engine" / "reconcile.py").read_text(encoding="utf-8")
    if source.count(DEFECT_LINE) != 1:
        raise SystemExit(
            f"refusing: defect site not unique ({source.count(DEFECT_LINE)} hits)"
        )
    red = source.replace(DEFECT_LINE, DEFECT_REPLACEMENT)
    target = Path(tempfile.mkdtemp(prefix="t1883-red-")) / "reconcile_red.py"
    target.write_text(red, encoding="utf-8")
    return target


def _load(path: Path):
    spec = importlib.util.spec_from_file_location("saipen_engine.reconcile_red", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Collector(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes: dict[str, str] = {}
        self._current = None

    def startTest(self, test):
        self._current = test.id()
        self.outcomes[self._current] = "ran"
        super().startTest(test)

    def addSuccess(self, test):
        self.outcomes[test.id()] = "PASS"
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.outcomes[test.id()] = "FAIL"
        super().addFailure(test, err)

    def addError(self, test, err):
        self.outcomes[test.id()] = "ERROR"
        super().addError(test, err)


def _run(module_name: str, red: dict) -> dict[str, str]:
    import saipen_engine  # noqa: F401  (real package for relative imports)
    sys.modules["saipen_engine.reconcile"] = red

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(module_name)
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=0, resultclass=_Collector)
    result = runner.run(suite)
    print(f"--- {module_name}: ran {result.testsRun} "
          f"failures {len(result.failures)} errors {len(result.errors)}")
    return result.outcomes


def main() -> int:
    red_path = _build_red_copy()
    print(f"red copy: {red_path}")
    red = _load(red_path)
    print(f"defect present: {'presence veto' if 'RED CONTROL' in Path(red_path).read_text(encoding='utf-8') else '?'}")

    outcomes = {}
    for module in ("test_t1883_reconcile_causality", "test_recovery_reachability"):
        outcomes.update(_run(module, red))

    failures = {tid for tid, verdict in outcomes.items() if verdict != "PASS"}
    expected_failures = EXPECTED_RED | EXPECTED_RED_REACHABILITY

    print("\nfailed under the defect:")
    for tid in sorted(failures):
        print(f"  {tid.split('.', 1)[1]}")
    unexpected = failures - expected_failures
    expected_still_green = expected_failures - failures
    print(f"\nexpected-red hit {len(expected_failures & failures)}/{len(expected_failures)}")
    if unexpected:
        print("UNEXPECTED failures (test does not isolate the defect):")
        for tid in sorted(unexpected):
            print(f"  {tid}")
    if expected_still_green:
        print("EXPECTED-red tests that stayed green (control does not bite):")
        for tid in sorted(expected_still_green):
            print(f"  {tid}")

    security_green = [
        tid for tid in outcomes
        if tid.endswith(("test_ac05_active_work_depending_on_a_blocked_ticket_refuses",
                         "test_ac05_a_blocked_ticket_that_needs_the_active_work_refuses",
                         "test_ac05_a_blocker_naming_the_blocked_ticket_refuses",
                         "test_a_recognised_class_token_still_refuses_with_unrelated_blocks",
                         "test_a_related_live_board_block_refuses"))
    ]
    for tid in security_green:
        print(f"security coverage {outcomes[tid]}: {tid.split('.', 1)[1]}")

    ok = (
        not unexpected
        and not expected_still_green
        and bool(security_green)
        and all(outcomes[tid] == "PASS" for tid in security_green)
    )
    print(f"\nRED CONTROL {'OK' if ok else 'BROKEN'}: the defect is caught only by "
          "the unrelated-veto tests; related gates keep refusing.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
