"""T-1893: the four green probe scripts run under the canonical discovery.

Eight tracked `tools/` scripts were reachable by no test, no CI step and no
entry point, and five of them are named `regression_*.py`, so the declared
`-p test_*.py` discovery never collected them. Four were still green when this
ticket opened and between them ran 62 checks that nothing else in the suite
makes:

* ``regression_conformance_closure.py``   29 checks, §1-§10 closure hardening
* ``regression_second_wave_receipt_fixes.py`` 33 checks, W2-001..W2-005
* ``regression_second_wave.py``           T-1015 credential redaction
* ``second_wave_regressions.py``          the second-wave regression batch

Each is a standalone script with its own ``main()`` and its own exit contract
rather than a unittest module, so this wrapper runs each one as the script it
already is and asserts the exit code and the success line. That keeps the
probe's own verdict as the oracle: a probe that starts failing fails HERE, and
the failure text is the probe's own output.

The other four scripts stay out of this wrapper on purpose, because running
them would report a verdict they cannot honestly give:

* ``regression_core_audit_fixes.py`` -- its CORE-003 case reads
  ``operations.build_event``, which no longer exists in the engine
  (``AttributeError``). Wrapping it today would either fail the suite or, if
  the assertion were loosened, report a redaction control as proven when it is
  not running.
* ``regression_second_wave_audit_fixes.py`` -- its W2-003 cases assert a
  fixture STATE shape the current schema refuses
  (``current-schema STATE requires absolute saipen_home``), and one case
  indexes ``"T-9"`` in a board that no longer contains it.
* ``t1318_current_generation_probe.py`` / ``t1320_fleet_native_smoke.py`` --
  live host smoke probes. They require an installed OpenCode runtime and
  report ``RUNTIME_STALE`` / ``HOST_CHAIN_FAILED`` for the host's state, which
  is not this project's tree. A suite that wrapped them would turn an
  unrelated host fact into a tree verdict.

Those four are recorded in the ticket's evidence. Repairing or retiring them is
a separate decision this change does not take, and no file is deleted or
renamed here.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent

#: (script, the line it prints when every one of its checks passed, timeout).
#: The success line is asserted as well as the exit code: two of these scripts
#: return 0 from a ``main()`` that prints its verdict, and a bare exit-code
#: check would pass on a script that lost its last assertion.
PROBES = (
    ("regression_conformance_closure.py",
     "ALL GREEN -- terminal/converged/crew-closed + current validator FAIL is impossible.", 300),
    ("regression_second_wave_receipt_fixes.py",
     "SECOND-WAVE receipt regressions passed", 300),
    ("regression_second_wave.py", "ALL TESTS PASSED", 300),
    ("second_wave_regressions.py", "All Second Wave Regressions PASSED", 300),
)


class LegacyProbeTests(unittest.TestCase):
    def _run(self, script: str, success: str, timeout: int) -> None:
        result = subprocess.run(
            [sys.executable, str(TOOLS / script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        tail = "\n".join((result.stdout + result.stderr).strip().splitlines()[-25:])
        self.assertEqual(
            result.returncode,
            0,
            f"{script} exited {result.returncode}; its own verdict was:\n{tail}",
        )
        self.assertIn(
            success,
            result.stdout,
            f"{script} exited 0 without printing its success line; tail:\n{tail}",
        )

    def test_conformance_closure_probe(self):
        self._run(*PROBES[0])

    def test_second_wave_receipt_probe(self):
        self._run(*PROBES[1])

    def test_userperson_redaction_probe(self):
        self._run(*PROBES[2])

    def test_second_wave_probe(self):
        self._run(*PROBES[3])


if __name__ == "__main__":
    unittest.main()
