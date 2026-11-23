"""T-10: continue's improve_cycle.submit_route must name a findings payload.

The installed `improve submit <cycle> <seat> <project> <findings.json>`
consumer reads args[4] as a JSON object with a non-empty string `run_text`.
The router in continue_fallback.cycle_liveness instead filled that argument
with the seat's markdown report path, so following the advertised route was
always refused ("findings file not found" / "not valid JSON").

Fix under test: the producer emits the documented `<findings.json>`
placeholder -- the same advisory improve.py:3515 and `improve --session`'s
`next` field give a seat -- and never the seat's own markdown report as the
payload argument. The seat writes its semantic audit into a real findings
file and fills the placeholder; the JSON consumer contract stays intact.

Run standalone:
    python tools/test_t10_submit_route.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import continue_fallback as cf  # noqa: E402

cycle_liveness = getattr(cf, "cycle_liveness", None)

CYCLE = "imp-_zaicoder-20261118-1"
SEAT = "codex-01"
REPORT = "saipen_improve_SAIPEN.md"
PROJECT = "_zaicoder"

MANIFEST = """# IMPROVE CYCLE ROSTER

manifest_schema: strict
cycle_id: {cycle}
created_at: {created}
project_identity: {project}
cycle_status: {status}
seat_id: {seat}
role: core
report_path: {report}
availability: expected
"""

DRAFT_REPORT = """agent: {seat}
role: core
model_or_runtime: unknown
project: {project}
saipen_version: 8.1.0
protocol_fingerprint: sha256:78a5433deacc5aab4ab7a3ac767cc79481e9699e5567cea76ec28fbea3b5c3f8
source_head: cbded0519deab0d1ffbf51c7ce38c6817382ecc3
source_tree_fingerprint: git-delta-v1:45369bcac4c52c56015fe376444b70c432805f7c26aa464c66f8ec6e7e69fd8c
discovery_model: git-delta-v1
context_scope: SAIPEN audit, phase DONE
context_available: partial
report_status: draft
"""

_EXPECTED_PREFIX = f"saipen improve submit {CYCLE} {SEAT} {PROJECT} "


def _cycle(root: Path, *, status: str = "active", report: str = DRAFT_REPORT) -> Path:
    manifest = root / ".saipen" / "improve" / CYCLE / "MANIFEST.md"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    created = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest.write_text(
        MANIFEST.format(
            cycle=CYCLE, created=created, project=PROJECT, status=status,
            seat=SEAT, report=REPORT,
        ),
        encoding="utf-8",
    )
    seat_dir = manifest.parent / SEAT
    seat_dir.mkdir(parents=True, exist_ok=True)
    (seat_dir / REPORT).write_text(report.format(seat=SEAT, project=PROJECT), encoding="utf-8")
    return root


class _NeedsRouter(unittest.TestCase):
    def setUp(self) -> None:
        if cycle_liveness is None:
            self.fail("saipen_engine.continue_fallback exposes no cycle_liveness")


class SubmitRoute(_NeedsRouter):
    def test_active_draft_route_names_the_documented_findings_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            live = cycle_liveness(_cycle(Path(tmp)), CYCLE)
            assert live is not None
            self.assertTrue(live["draft"])
            self.assertEqual(live["status"], "active")
            self.assertEqual(
                live["submit_route"],
                _EXPECTED_PREFIX + "<findings.json>",
            )

    def test_route_never_uses_the_markdown_report_as_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            live = cycle_liveness(_cycle(Path(tmp)), CYCLE)
            assert live is not None
            route = live["submit_route"]
            self.assertTrue(route.startswith(_EXPECTED_PREFIX))
            payload = route[len(_EXPECTED_PREFIX):]
            self.assertNotIn(".md", payload)
            self.assertNotIn(SEAT + "/", payload)
            self.assertEqual(payload, "<findings.json>")

    def test_complete_report_has_no_submit_route(self) -> None:
        complete = DRAFT_REPORT.replace("report_status: draft", "report_status: complete")
        complete += "\n## RUN 1\nIMP-001 the audit was submitted\n"
        with tempfile.TemporaryDirectory() as tmp:
            live = cycle_liveness(_cycle(Path(tmp), report=complete), CYCLE)
            assert live is not None
            self.assertFalse(live["draft"])
            self.assertEqual(live["submit_route"], "")


class _EndToEnd(unittest.TestCase):
    def test_advertised_route_commits_with_a_real_findings_payload(self) -> None:
        """Fill the placeholder and run the canonical CLI -- no hand repair."""
        import json as _json
        import subprocess as _subprocess

        from improve import create_cycle, create_report, register_seat
        from saipen_engine.paths import identity_file_content, new_project_lineage
        from test_fixture_support import CURRENT_STYLE_CONTRACT
        from test_hermetic_env import isolate_host_session

        isolate_host_session()
        with tempfile.TemporaryDirectory(prefix="t10-chain-") as td:
            root = Path(td).resolve() / "project"
            saipen = root / ".saipen"
            saipen.mkdir(parents=True)
            (saipen / "LOG.md").write_text(
                "- 20.09.26 00:00 [E-900] [T-none] DEC: base\n", encoding="utf-8"
            )
            (saipen / "BOARD.md").write_text(
                "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n", encoding="utf-8"
            )
            (saipen / "STATE.md").write_text(
                "---\nphase: DONE\ntask: none\nnext_action: \"saipen continue\"\n"
                "blocker: \"\"\ntransition_from: SHIP\nsaipen_version: 8\nschema_version: 3\n"
                "last_event: 900\nstyle_contract: " + CURRENT_STYLE_CONTRACT + "\n"
                "saipen_home: \".\"\nagent: probe\nmode: full\n"
                "updated: 2026-09-20T00:00:00Z\n---\n",
                encoding="utf-8",
            )
            (saipen / "IDENTITY.md").write_text(
                identity_file_content(new_project_lineage()), encoding="utf-8"
            )
            cycle = "imp-t10-chain-01"
            create_cycle(
                root, cycle, created_at="2026-11-18T00:00:00Z",
                project_identity="probe-project",
            )
            register_seat(saipen / "improve" / cycle, "seat-a", "core", "saipen_improve_PROBE.md")
            report = create_report(
                root, cycle, "seat-a", "probe-project",
                agent="seat-a", role="core", model_or_runtime="probe",
                context_scope="T-10 chain proof", context_available="complete",
            )

            live = cycle_liveness(root, cycle)
            assert live is not None
            route = live["submit_route"]
            self.assertTrue(route.endswith("<findings.json>"), route)

            payload = root / "findings.json"
            payload.write_text(
                _json.dumps({"run_text": "NO_FINDINGS -- T-10 advertised route chain proof"}),
                encoding="utf-8",
            )
            # Fill only the placeholder; pass argv elements directly. POSIX
            # shlex.split would eat Windows backslashes in the payload path.
            parts = route.split()
            parts[-1] = str(payload)
            cmd = [
                sys.executable, str(TOOLS / "saipen.py"),
                "--project-root", str(root), "--json", *parts[1:],
            ]
            proc = _subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            result = _json.loads(proc.stdout)
            self.assertTrue(result.get("ok"), result)
            self.assertEqual(result.get("code"), "COMMITTED", result)
            self.assertIn("## RUN 1", report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
