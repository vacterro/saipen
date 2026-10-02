"""T-3: every improve refusal leaves through the structured result contract.

`ImproveError` subclasses `ValueError` and is raised across the whole improve
route, including `_validate_safe_id` on the route's OWN arguments -- which sits
outside every action-local `except ValueError`. Before T-3 the single handler
lived in one action, so an argument-shape refusal escaped `main()`: `--json`
wrote nothing at all on stdout and Python printed a raw traceback on stderr.
A `--json` consumer then had nothing to parse and no `code` to branch on.

The contract implemented here: `_public_improve` is the boundary, so EVERY
improve action's `ImproveError` is emitted as one JSON object carrying
`ok: false`, a stable `code`, and a `detail` -- with stderr left empty and no
machine-local path in the payload.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402

import improve  # noqa: E402
from saipen_engine.paths import identity_file_content, new_project_lineage  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

def setUpModule() -> None:
    isolate_host_session()

def run_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOLS / "saipen.py"), "--project-root", str(root), "--json", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class ImproveErrorBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t3-boundary-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve() / "project"
        saipen = self.root / ".saipen"
        saipen.mkdir(parents=True)
        (saipen / "LOG.md").write_text(
            "- 20.09.26 00:00 [E-900] [T-none] DEC: base\n", encoding="utf-8"
        )
        (saipen / "BOARD.md").write_text(
            "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n", encoding="utf-8"
        )
        (saipen / "STATE.md").write_text(
            '---\nphase: DONE\ntask: none\nnext_action: "saipen continue"\n'
            'blocker: ""\ntransition_from: SHIP\n'
            "saipen_version: 8\nschema_version: 3\n"
            'last_event: 900\nstyle_contract: ' + CURRENT_STYLE_CONTRACT + "\n"
            'saipen_home: "."\nagent: probe\nmode: full\n'
            "updated: 2026-09-20T00:00:00Z\n---\n",
            encoding="utf-8",
        )
        (saipen / "IDENTITY.md").write_text(
            identity_file_content(new_project_lineage()), encoding="utf-8"
        )
        self.cycle = improve.create_cycle(
            self.root,
            "imp-t3-20260920-01",
            created_at="2026-09-20T00:00:00Z",
            project_identity="probe-project",
        )
        improve.register_seat(self.cycle, "seat-a", "core", "saipen_improve_PROBE.md")
        self.payload = self.root / "findings.json"
        self.payload.write_text(json.dumps({"run_text": "NO_FINDINGS\n"}), encoding="utf-8")

    def assertStructuredRefusal(self, result: subprocess.CompletedProcess[str]) -> dict:
        """The contract: non-empty stdout JSON, a stable code, clean stderr."""
        self.assertEqual(result.stderr, "", result.stderr)
        self.assertTrue(result.stdout.strip(), "refusal wrote nothing to stdout")
        data = json.loads(result.stdout)
        self.assertFalse(data.get("ok"), data)
        self.assertEqual(data.get("code"), "VALIDATION_FAILED", data)
        self.assertTrue(data.get("detail"), data)
        return data

    def test_an_argument_shape_refusal_is_json_not_a_traceback(self):
        """The exact T-3 repro: `_validate_safe_id` rejects the project name.

        This call raises from `_resolve_report_path` BEFORE the submit
        action's own try block, so no action-local handler could ever see it.
        """
        result = run_cli(
            self.root,
            "improve",
            "submit",
            self.cycle.name,
            "seat-a",
            "_bad-project",
            str(self.payload),
        )
        self.assertEqual(result.returncode, 1)
        data = self.assertStructuredRefusal(result)
        self.assertIn("path-safe", data["detail"])

    def test_every_action_boundary_refusal_stays_structured(self):
        """The guard is the boundary, not one action: each id-shape refusal
        a caller can actually reach must emit the same contract shape."""
        for args in (
            ("improve", "submit", "cycle!", "seat-a", "PROBE", str(self.payload)),
            ("improve", "submit", self.cycle.name, "seat!", "PROBE", str(self.payload)),
            ("improve", "complete", self.cycle.name, "seat!", "PROBE"),
            ("improve", "sweep", self.cycle.name, "RUN-1/IMP-001", "CONFIRMED"),
        ):
            with self.subTest(args=args):
                self.assertStructuredRefusal(run_cli(self.root, *args))

    def test_a_coded_refusal_keeps_its_stable_code_through_the_boundary(self):
        """SRC-085 M2: a refusal carrying its own code reports THAT code at
        the boundary, not the historical VALIDATION_FAILED fallback."""
        self.payload.write_text(
            json.dumps({"run_text": "## RUN 1\n\nIMP-001 smuggled heading"}), encoding="utf-8"
        )
        result = run_cli(
            self.root,
            "improve",
            "submit",
            self.cycle.name,
            "seat-a",
            "PROBE",
            str(self.payload),
        )
        self.assertEqual(result.stderr, "", result.stderr)
        self.assertEqual(json.loads(result.stdout).get("code"), "RUN_BODY_REQUIRED")

    def test_a_non_improve_value_error_is_not_swallowed(self):
        """The boundary must not become a catch-all.

        `ImproveError` subclasses `ValueError`, so a boundary written as
        `except ValueError` would also swallow an unrelated ValueError and
        report it as an improve refusal. Patching `_improve` to raise a
        plain one proves the boundary names the improve type specifically.
        """
        import saipen as saipen_cli

        def raise_unrelated(*_args, **_kwargs):
            raise ValueError("not an improve refusal")

        with mock.patch.object(saipen_cli, "_improve", side_effect=raise_unrelated):
            with self.assertRaises(ValueError) as ctx:
                saipen_cli._public_improve(self.root, ["status"], True, False)
        self.assertEqual(str(ctx.exception), "not an improve refusal")


if __name__ == "__main__":
    unittest.main()