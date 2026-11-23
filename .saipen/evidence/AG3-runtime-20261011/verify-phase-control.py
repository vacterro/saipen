"""Supplemental current VERIFY-phase refusal check; no frozen-source edits."""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import test_t1712_manifest_runtime as oracle


def setUpModule():
    oracle.isolate_host_session()


class VerifyPhase(oracle.ManifestRuntimeTests):
    def test_verify_phase_and_claim_are_unchanged_on_required_manifest_denial(self):
        project = self.make_project(active=True)
        state = project / ".saipen/STATE.md"
        state.write_text(state.read_text(encoding="utf-8").replace(
            "phase: BUILD", "phase: VERIFY"
        ).replace("transition_from: SCOUT", "transition_from: BUILD"), encoding="utf-8")
        before = oracle.digest(project)
        output, errors = io.StringIO(), io.StringIO()
        cli = oracle.cli_module()
        with self.lstat_denied(project.parent), contextlib.redirect_stdout(
            output
        ), contextlib.redirect_stderr(errors):
            status = cli.main(["--project-root", str(project), "--json", "continue"])
        result = json.loads(output.getvalue())
        self.assertNotEqual(status, 0)
        self.failure(result, project.parent)
        self.assertEqual(oracle.digest(project), before)
        self.assertIn("phase: VERIFY", state.read_text(encoding="utf-8"))
        self.assertNotIn("INIT_COMPLETED", output.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())


if __name__ == "__main__":
    unittest.main(defaultTest="VerifyPhase.test_verify_phase_and_claim_are_unchanged_on_required_manifest_denial")
