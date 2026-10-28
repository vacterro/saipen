"""RED control for T-1951's binding half.

Runs the same two binding tests through the PRE-FIX `bootstrap/schedule-run.ps1`
carried under `pre/schedule-run.prefix.ps1`. The fixture copies the runner out
of the source tree, so the swap is a file replacement under the fixture root --
the production script is never edited.

A control that passes proves nothing: this script exits non-zero only when the
prefix run genuinely FAILS the assertions, which is what makes the post-fix
green a measurement rather than a claim.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE.parent
# .saipen/evidence/T-1951-install-residue/controls -> project root is 4 up.
ROOT = EVIDENCE.parent.parent.parent
PREFIX = EVIDENCE / "pre" / "schedule-run.prefix.ps1"

sys.path.insert(0, str(ROOT / "tools"))

from test_hermetic_env import isolate_host_session  # noqa: E402


def main() -> int:
    if not PREFIX.is_file():
        print(f"RED CONTROL BROKEN: no pre-fix carrier at {PREFIX}")
        return 2
    isolate_host_session()

    from test_t1613_publication_convergence import IS_WINDOWS, POWERSHELL

    if not (IS_WINDOWS and POWERSHELL):
        print("SKIP: the scheduled publisher is Windows-only")
        return 2

    # The fixture builds its source tree from ROOT, so the prefix has to be an
    # override the fixture applies, not a live edit of the canonical script.
    import test_t1613_publication_convergence as fixture

    original_build = fixture._Publisher._build_source

    def build_with_prefix(self) -> None:
        original_build(self)
        target = self.source / "bootstrap" / "schedule-run.ps1"
        shutil.copyfile(PREFIX, target)
        self._git("add", "--", "bootstrap/schedule-run.ps1")
        self._git(
            "-c", "user.name=fixture", "-c", "user.email=f@x",
            "commit", "-q", "-m", "fixture prefix runner",
        )

    fixture._Publisher._build_source = build_with_prefix
    try:
        import test_t1951_install_residue as subject

        suite = unittest.TestLoader().loadTestsFromTestCase(
            subject.ARollbackKeepsTheBindingsOnTheGenerationItLeftBehindTests
        )
        with tempfile.TemporaryFile("w+") as sink:
            result = unittest.TextTestRunner(stream=sink, verbosity=2).run(suite)
        broken = [str(case) for case, _ in result.failures + result.errors]
    finally:
        fixture._Publisher._build_source = original_build

    if result.wasSuccessful():
        print("RED CONTROL DID NOT RED: the pre-fix runner passed the binding tests")
        return 1
    print(f"RED CONTROL OK: {len(broken)} assertion(s) fail on the pre-fix runner")
    for name in broken:
        print("  " + name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
