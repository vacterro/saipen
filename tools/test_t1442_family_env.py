"""T-1442: a test family is evidence about the tree, not about its launcher.

Measured 2026-09-21: with SAIPEN_HOST_SESSION set -- any run launched from a
live OpenCode seat -- test_continue_chain and test_conformance_repair_boundary
failed and passed outside one: a fixture's resumed parent read as claimed by the
operator's session. The harness list `isolate_host_session` strips lacked the
carrier, and test_continue_chain kept its own remembered list. Both now follow
the engine's one list (`paths.PROJECT_BINDING_ENV`), and the family runner no
longer hands any family the operator's binding, host session or seat.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.paths import PROJECT_BINDING_ENV  # noqa: E402
from saipen_engine.test_runner import TestFamily, _run_family  # noqa: E402

OPERATOR = {
    "SAIPEN_HOST_SESSION": "ses_operator_live",
    "SAIPEN_PROJECT_ROOT": str(Path(tempfile.gettempdir()) / "saipen-live-project"),
    "SAIPEN_PROJECT_LINEAGE": "lineage-" + "e" * 32,
    "SAIPEN_AGENT": "astra",
    "PWD": str(Path(tempfile.gettempdir()) / "saipen-live-project"),
}
PROBE = (
    "import json, os; print(json.dumps({k: os.environ.get(k) for k in "
    + repr(sorted({*OPERATOR, *PROJECT_BINDING_ENV}))
    + "}))"
)


class FamilyEnvironmentTests(unittest.TestCase):
    def test_a_family_child_inherits_no_operator_binding_session_or_seat(self):
        with tempfile.TemporaryDirectory(prefix="saipen-t1442-") as tmp:
            root = Path(tmp)
            spool = root / "spool"
            spool.mkdir()
            with mock.patch.dict(os.environ, OPERATOR):
                report = _run_family(
                    root, TestFamily("probe", (sys.executable, "-c", PROBE), 60), spool=spool
                )
            self.assertEqual(report["status"], "PASS", report)
            seen = json.loads((spool / "stdout").read_text(encoding="utf-8"))
        self.assertEqual({key: value for key, value in seen.items() if value}, {})

    def test_a_family_never_shares_its_launchers_stdin(self):
        # T-1624. The launcher here holds a stdin pipe that is never written
        # and never closed -- what a family started from an agent's background
        # shell inherits. A family child that reads stdin must meet end-of-file
        # at once. While it inherited that pipe instead, the read never
        # returned, and on Windows the pending read also froze the startup of
        # every later child holding the same handle.
        reader = "import sys; print('EOF' if not sys.stdin.buffer.read() else 'DATA')"
        launcher = (
            "import json, sys\n"
            f"sys.path.insert(0, {str(TOOLS)!r})\n"
            "from pathlib import Path\n"
            "from saipen_engine.test_runner import TestFamily, _run_family\n"
            "root, spool = Path(sys.argv[1]), Path(sys.argv[2])\n"
            f"family = TestFamily('stdin-probe', (sys.executable, '-c', {reader!r}), 15)\n"
            "report = _run_family(root, family, spool=spool)\n"
            "print(json.dumps({'status': report['status'],\n"
            "                  'seen': (spool / 'stdout').read_text(encoding='utf-8').strip()}))\n"
        )
        with tempfile.TemporaryDirectory(prefix="saipen-t1624-stdin-") as tmp:
            root = Path(tmp)
            spool = root / "spool"
            spool.mkdir()
            process = subprocess.Popen(
                [sys.executable, "-c", launcher, str(root), str(spool)],
                stdin=subprocess.PIPE,  # held open, never written
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                # Not `communicate`: that would close the pipe and hand the
                # child the end-of-file this test says it must not depend on.
                process.wait(timeout=120)
                out, err = process.stdout.read(), process.stderr.read()
            finally:
                process.kill()
                for stream in (process.stdin, process.stdout, process.stderr):
                    stream.close()
                process.wait(timeout=30)
        self.assertEqual(process.returncode, 0, err.decode("utf-8", errors="replace"))
        self.assertEqual(
            json.loads(out.decode("utf-8").strip().splitlines()[-1]),
            {"status": "PASS", "seen": "EOF"},
        )


if __name__ == "__main__":
    unittest.main()
