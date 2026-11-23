"""Permission failures remain local hard boundaries, never CLI tracebacks."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from saipen_engine import audit_manifest, paths
from saipen_engine.reconcile import reconcile_protocol_state
from saipen_engine.router import route_next
from test_control_primitives import ControlFixture
from test_hermetic_env import isolate_host_session

UNAVAILABLE = "SAIPEN_HOST_RUNTIME_UNAVAILABLE"


def setUpModule():
    isolate_host_session()


def digest(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def denied(path):
    exc = PermissionError(13, "Access is denied", str(path))
    exc.winerror = 5
    return exc


def cli_module():
    spec = importlib.util.spec_from_file_location(
        "cli_t1712", Path(__file__).with_name("saipen.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ManifestRuntimeTests(ControlFixture):
    def failure(self, result, path, stage="validation"):
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], UNAVAILABLE, result)
        self.assertEqual(result["failure_kind"], "permission_denied", result)
        self.assertEqual(result["stage"], stage, result)
        self.assertEqual(result["offending_path"], str(path), result)
        self.assertEqual(result["os_error"]["winerror"], 5, result)
        self.assertEqual(result["os_error"]["errno"], 13, result)
        self.assertEqual(result["os_error"]["filename"], str(path), result)
        self.assertEqual(result["failure_scope"], "operation", result)
        self.assertIn("execution_identity", result)
        self.assertIn("remediation", result)
        self.assertIn("fingerprint", result)
        self.assertFalse(result["changed"], result)

    @contextlib.contextmanager
    def lstat_denied(self, target):
        original = Path.lstat

        def lstat(path, *args, **kwargs):
            if path == target:
                raise denied(target)
            return original(path, *args, **kwargs)

        with patch.object(Path, "lstat", lstat):
            yield

    def test_accessible_project_enrolls_and_second_call_writes_nothing(self):
        project = self.make_project()
        first = audit_manifest.ensure(project)
        self.assertTrue(first["ok"], first)
        before = digest(project)
        self.assertEqual(audit_manifest.ensure(project)["code"], audit_manifest.CODE_CURRENT)
        self.assertEqual(digest(project), before)

    def test_missing_project_is_absence_without_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "missing"
            result = audit_manifest.ensure(project)
            self.assertFalse(result["ok"])
            self.assertEqual(result["reason_code"], audit_manifest.REASON_MEMORY_ABSENT)
            self.assertFalse(project.exists())

    def test_unreadable_existing_ancestor_is_structured_and_zero_write(self):
        project = self.make_project()
        before = digest(project)
        with self.lstat_denied(project / ".saipen"), patch.object(Path, "mkdir") as mkdir:
            result = audit_manifest.ensure(project)
        self.failure(result, project / ".saipen")
        mkdir.assert_not_called()
        self.assertEqual(digest(project), before)

    def test_inaccessible_child_is_not_missing_or_corrupt(self):
        project = self.make_project()
        before = digest(project)
        child = project / ".saipen"
        with self.lstat_denied(child):
            result = audit_manifest.ensure(project)
        self.failure(result, child)
        self.assertEqual(digest(project), before)

    def test_denied_manifest_stat_cannot_authorize_replacement(self):
        project = self.make_project()
        self.assertTrue(audit_manifest.ensure(project)["ok"])
        before = digest(project)
        manifest = audit_manifest.manifest_path(project)
        with self.lstat_denied(manifest):
            result = audit_manifest.ensure(project, force=True)
        self.failure(result, manifest)
        self.assertEqual(digest(project), before)

    def test_denied_manifest_read_cannot_become_malformed_even_with_force(self):
        project = self.make_project()
        self.assertTrue(audit_manifest.ensure(project)["ok"])
        before = digest(project)
        manifest = audit_manifest.manifest_path(project)
        original = Path.read_text

        def read_text(path, *args, **kwargs):
            if path == manifest:
                raise denied(path)
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", read_text):
            result = audit_manifest.ensure(project, force=True)
        self.failure(result, manifest)
        self.assertEqual(digest(project), before)

    def test_denied_state_read_is_availability_not_corruption(self):
        project = self.make_project()
        before = digest(project)
        state = project / ".saipen/STATE.md"
        original = Path.read_bytes

        def read_bytes(path):
            if path == state:
                raise denied(path)
            return original(path)

        with patch.object(Path, "read_bytes", read_bytes):
            result = audit_manifest.ensure(project)
        self.failure(result, state)
        self.assertEqual(digest(project), before)

    def test_direct_write_contains_original_oserror(self):
        project = self.make_project()
        before = digest(project)
        manifest = audit_manifest.manifest_path(project)
        with patch.object(audit_manifest, "safe_atomic_write_bytes", side_effect=denied(manifest)):
            result = audit_manifest.write(project, force=True)
        self.failure(result, manifest)
        self.assertEqual(digest(project), before)

    def test_failed_atomic_replace_removes_own_temporary_and_preserves_manifest(self):
        project = self.make_project()
        self.assertTrue(audit_manifest.ensure(project)["ok"])
        before = digest(project)
        manifest = audit_manifest.manifest_path(project)
        with patch.object(paths.os, "replace", side_effect=denied(manifest)), patch.object(
            paths, "_REPLACE_ATTEMPTS", 1
        ):
            result = audit_manifest.write(project, force=True)
        self.failure(result, manifest)
        self.assertEqual(digest(project), before)

    def test_other_oserror_preserves_its_distinct_error(self):
        project = self.make_project()
        manifest = audit_manifest.manifest_path(project)
        before = digest(project)
        with patch.object(
            audit_manifest,
            "safe_atomic_write_bytes",
            side_effect=OSError(5, "I/O error", str(manifest)),
        ):
            result = audit_manifest.ensure(project)
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], UNAVAILABLE)
        self.assertEqual(result["failure_kind"], "filesystem_unavailable")
        self.assertEqual(result["os_error"]["errno"], 5)
        self.assertEqual(digest(project), before)

    def test_continue_json_is_hard_refusal_without_phase_or_claim_change(self):
        project = self.make_project(active=True)
        before = digest(project)
        output, errors = io.StringIO(), io.StringIO()
        cli = cli_module()
        with self.lstat_denied(project / ".saipen"), contextlib.redirect_stdout(
            output
        ), contextlib.redirect_stderr(errors):
            status = cli.main(["--project-root", str(project), "--json", "continue"])
        result = json.loads(output.getvalue())
        self.assertNotEqual(status, 0)
        self.failure(result, project / ".saipen", stage="before_admission")
        self.assertNotIn("Traceback", errors.getvalue())
        self.assertEqual(digest(project), before)

    def test_known_denial_precedes_any_canonical_reconciliation_repair(self):
        project = self.make_project(active=True)
        state = project / ".saipen/STATE.md"
        state.write_text(
            state.read_text().replace("last_event: 1", "last_event: 0"), encoding="utf-8"
        )
        before = digest(project)
        with self.lstat_denied(project / ".saipen"):
            result = reconcile_protocol_state(project, "tester")
        self.failure(result, project / ".saipen")
        self.assertEqual(digest(project), before)

    def test_manifest_write_denial_precedes_canonical_reconciliation_commit(self):
        project = self.make_project(active=True)
        state = project / ".saipen/STATE.md"
        state.write_text(
            state.read_text().replace("last_event: 1", "last_event: 0"), encoding="utf-8"
        )
        before = digest(project)
        manifest = audit_manifest.manifest_path(project)
        with patch.object(audit_manifest, "safe_atomic_write_bytes", side_effect=denied(manifest)):
            result = reconcile_protocol_state(project, "tester")
        self.failure(result, manifest)
        self.assertEqual(digest(project), before)

    def test_read_only_manifest_cli_denial_is_parseable_hard_refusal(self):
        project = self.make_project()
        before = digest(project)
        cli = cli_module()
        output, errors = io.StringIO(), io.StringIO()
        child = project / ".saipen"
        with self.lstat_denied(child), contextlib.redirect_stdout(
            output
        ), contextlib.redirect_stderr(errors):
            status = cli.main(["--project-root", str(project), "--json", "audit", "manifest"])
        result = json.loads(output.getvalue())
        self.assertNotEqual(status, 0)
        self.failure(result, child, stage="before_admission")
        self.assertNotIn("Traceback", errors.getvalue())
        self.assertEqual(digest(project), before)

    def test_read_only_manifest_inspection_reports_its_own_denial(self):
        project = self.make_project()
        self.assertTrue(audit_manifest.ensure(project)["ok"])
        before = digest(project)
        manifest = audit_manifest.manifest_path(project)
        output, errors = io.StringIO(), io.StringIO()
        cli = cli_module()
        with self.lstat_denied(manifest), contextlib.redirect_stdout(
            output
        ), contextlib.redirect_stderr(errors):
            status = cli.main(["--project-root", str(project), "--json", "audit", "manifest"])
        result = json.loads(output.getvalue())
        self.assertNotEqual(status, 0)
        self.failure(result, manifest)
        self.assertEqual(digest(project), before)

    def test_manifest_dry_run_denial_has_nonzero_cli_exit(self):
        project = self.make_project()
        before = digest(project)
        output, errors = io.StringIO(), io.StringIO()
        cli = cli_module()
        with self.lstat_denied(project / ".saipen"), contextlib.redirect_stdout(
            output
        ), contextlib.redirect_stderr(errors):
            status = cli.main(
                [
                    "--project-root",
                    str(project),
                    "--json",
                    "--dry-run",
                    "audit",
                    "manifest",
                    "--write",
                ]
            )
        result = json.loads(output.getvalue())
        self.assertNotEqual(status, 0)
        self.failure(result, project / ".saipen", stage="before_admission")
        self.assertEqual(digest(project), before)

    def test_init_permission_failure_is_json_and_never_init_completed(self):
        cli = cli_module()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            output, errors = io.StringIO(), io.StringIO()
            with patch(
                "saipen_engine.init_project.bootstrap_project", side_effect=denied(project)
            ), contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                status = cli.main(["--project-root", str(project), "--json", "init"])
            result = json.loads(output.getvalue())
            self.assertNotEqual(status, 0)
            self.failure(result, project, stage="before_admission")
            self.assertNotIn("INIT_COMPLETED", output.getvalue())
            self.assertNotIn("Traceback", errors.getvalue())
            self.assertEqual(digest(project), {})

    def test_init_late_materialization_denial_leaves_no_partial_canonical_files(self):
        cli = cli_module()
        original = Path.write_text
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            output, errors = io.StringIO(), io.StringIO()

            def write_text(path, *args, **kwargs):
                if path.name == "STATE.md":
                    raise denied(path)
                return original(path, *args, **kwargs)

            with patch.object(Path, "write_text", write_text), contextlib.redirect_stdout(
                output
            ), contextlib.redirect_stderr(errors):
                status = cli.main(["--project-root", str(project), "--json", "init"])
            result = json.loads(output.getvalue())
            self.assertNotEqual(status, 0)
            self.assertEqual(result["code"], UNAVAILABLE)
            self.assertNotIn("INIT_COMPLETED", output.getvalue())
            self.assertEqual(digest(project), {})
            self.assertEqual(list(project.iterdir()), [])

    def test_one_denied_project_does_not_stop_a_separate_eligible_goal(self):
        affected = self.make_project(active=True)
        independent = self.make_project(intent="goal")
        state = (independent / ".saipen/STATE.md").read_text(encoding="utf-8")
        board = (
            "## DOING\n## TODO\n- [ ] T-8 [P1] Independent Work | verify: real proof\n"
            "## DONE\n## BLOCKED\n- [ ] T-7 [P1] Host failure | "
            "blocker: SAIPEN_HOST_RUNTIME_UNAVAILABLE | blocker_scope: ticket\n"
        )
        with self.lstat_denied(affected / ".saipen"):
            failure = audit_manifest.ensure(affected)
            healthy = audit_manifest.ensure(independent)
            route = route_next(state, board)
        self.failure(failure, affected / ".saipen")
        self.assertTrue(healthy["ok"], healthy)
        self.assertEqual(route["ticket"], "T-8", route)

    def test_repeat_diagnostic_has_stable_fingerprint_without_writes(self):
        project = self.make_project()
        before = digest(project)
        with self.lstat_denied(project / ".saipen"):
            first = audit_manifest.ensure(project)
            second = audit_manifest.ensure(project, dry_run=True)
        self.failure(first, project / ".saipen")
        self.failure(second, project / ".saipen")
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        self.assertEqual(digest(project), before)

    def test_denied_ancestor_above_the_project_root_is_outside_the_boundary(self):
        # T-1743: a managed account granted only its project cannot read the
        # operator's directories above it. That is the isolation working, not
        # a fault: the owned-path proof stops at the project root, so the
        # manifest enrolls and continuation proceeds.
        project = self.make_project(active=True)
        with self.lstat_denied(project.parent):
            result = audit_manifest.ensure(project)
        self.assertTrue(result["ok"], result)
        output, errors = io.StringIO(), io.StringIO()
        cli = cli_module()
        with self.lstat_denied(project.parent), contextlib.redirect_stdout(
            output
        ), contextlib.redirect_stderr(errors):
            cli.main(["--project-root", str(project), "--json", "continue"])
        self.assertNotIn(UNAVAILABLE, output.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())

    def test_topology_refusal_is_still_a_hard_security_boundary(self):
        project = self.make_project()
        with patch.object(
            paths.os.path, "islink", side_effect=lambda path: Path(path) == project.parent
        ), self.assertRaisesRegex(ValueError, "link/reparse"):
            paths.prove_owned_dir_chain(project / ".saipen", kind="audit manifest")


if __name__ == "__main__":
    unittest.main()
