"""Test suite for Canonical Install Identity & Divergence Doctor (SRC-258 / T-1798).

Verifies:
- Normalize install content fingerprints across repository and flat layouts.
- Divergence classification (MATCH, COPIES_IDENTICAL, DIVERGENT).
- Block mutations under an install that diverges from STATE.saipen_home.
- Accurate saipen validate reporting (REBIND_REQUIRED and saipen rebind-home --auto).
- Proper rebind_home_auto convergence when persisted home differs from running engine.
- Continuation loop (continue_loop) handling of APPLY_REBIND_HOME.
- Live inspection of host surfaces.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from saipen_engine import admission, continue_loop, install_identity, operations, state
from saipen_engine.paths import identity_file_content, new_project_lineage
from saipen_engine.state import running_style_token
from test_hermetic_env import isolate_host_session

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent


def setUpModule():
    isolate_host_session()


class InstallIdentityDoctorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-test-install-")
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _full_home(self, name: str) -> Path:
        home = self.root / name
        for relative, content in {
            "VERSION": "8.1.0\n",
            "saipen/BOOT.md": "# BOOT\n",
            "extensions/subs/PROTOCOL.md": "# SUBS\n",
            "tools/saipen.py": "# independent engine\n",
            "tools/saipen_engine/operations.py": "VALUE = 1\n",
        }.items():
            path = home / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return home

    def _make_project(self, home: str | None) -> Path:
        project = self.root / "managed_project"
        saipen = project / ".saipen"
        saipen.mkdir(parents=True, exist_ok=True)
        (saipen / "IDENTITY.md").write_text(
            identity_file_content(new_project_lineage()), encoding="utf-8"
        )
        style_token = running_style_token()
        fields = [
            "---",
            "phase: BUILD",
            "task: T-1",
            "next_action: PHASE BUILD T-1",
            'blocker: ""',
            "transition_from: SCOUT",
            "saipen_version: 8",
            "schema_version: 3",
            "last_event: 2",
            f"style_contract: {style_token}",
            "agent: test-agent",
            "mode: full",
            'updated: "2026-09-20T00:00:00Z"',
        ]
        if home is not None:
            fields.append(f'saipen_home: "{home}"')
        fields.append("---")
        (saipen / "STATE.md").write_text("\n".join(fields) + "\n", encoding="utf-8")
        (saipen / "BOARD.md").write_text(
            "## DOING\n"
            "- [/] T-1 [P1] work | verify: the fixture change is demonstrated\n"
            "\n## TODO\n\n## DONE\n\n## BLOCKED\n",
            encoding="utf-8",
        )
        (saipen / "LOG.md").write_text(
            "- 20.09.26 00:00 [E-001] [T-1] [op: ticket-00000000000000000000000000000000] "
            "DEC: ticket added via SAIOPS\n"
            "- 20.09.26 00:00 [E-002] [parent: E-001] [T-none] DEC: base\n",
            encoding="utf-8",
        )
        (project / "src").mkdir(exist_ok=True)
        (project / "src" / "app.py").write_text("code\n", encoding="utf-8")
        return project

    def test_normalize_install_frames_across_repo_and_flat_layouts(self):
        """Repository clone layout and flat installed skill layout yield identical fingerprints."""
        repo_dir = self.root / "repo"
        flat_dir = self.root / "flat"

        # Repo layout: protocol under saipen/
        (repo_dir / "saipen" / "phases").mkdir(parents=True)
        (repo_dir / "tools" / "saipen_engine").mkdir(parents=True)
        (repo_dir / "VERSION").write_text("8.1.0\n", encoding="utf-8")
        (repo_dir / "saipen" / "BOOT.md").write_text("# BOOT\n", encoding="utf-8")
        (repo_dir / "saipen" / "CORE.md").write_text("# CORE\n", encoding="utf-8")
        (repo_dir / "saipen" / "REGISTRY.json").write_text(
            '{"schema_version": 1}\n', encoding="utf-8"
        )
        (repo_dir / "saipen" / "phases" / "scout.md").write_text("# SCOUT\n", encoding="utf-8")
        (repo_dir / "tools" / "saipen_engine" / "mod.py").write_text("# mod\n", encoding="utf-8")

        # Flat installed layout: protocol directly in root, no saipen/ dir
        (flat_dir / "phases").mkdir(parents=True)
        (flat_dir / "tools" / "saipen_engine").mkdir(parents=True)
        (flat_dir / "VERSION").write_text("8.1.0\n", encoding="utf-8")
        (flat_dir / "BOOT.md").write_text("# BOOT\n", encoding="utf-8")
        (flat_dir / "CORE.md").write_text("# CORE\n", encoding="utf-8")
        (flat_dir / "REGISTRY.json").write_text('{"schema_version": 1}\n', encoding="utf-8")
        (flat_dir / "phases" / "scout.md").write_text("# SCOUT\n", encoding="utf-8")
        (flat_dir / "tools" / "saipen_engine" / "mod.py").write_text("# mod\n", encoding="utf-8")
        # Add host metadata dotfiles that must be ignored
        (flat_dir / ".saipen_install.json").write_text('{"meta": true}\n', encoding="utf-8")
        (flat_dir / ".saipen_runtime.json").write_text('{"runtime": true}\n', encoding="utf-8")

        repo_fp = install_identity.install_fingerprint(repo_dir)
        flat_fp = install_identity.install_fingerprint(flat_dir)

        self.assertTrue(repo_fp.startswith("install-v1:"))
        self.assertEqual(repo_fp, flat_fp)

    def test_divergent_install_produces_different_fingerprint(self):
        """A difference in engine or protocol files changes the content fingerprint."""
        base_dir = self.root / "base"
        alt_dir = self.root / "alt"

        for d in (base_dir, alt_dir):
            (d / "saipen").mkdir(parents=True)
            (d / "tools").mkdir(parents=True)
            (d / "VERSION").write_text("8.1.0\n", encoding="utf-8")
            (d / "saipen" / "BOOT.md").write_text("# BOOT\n", encoding="utf-8")

        (base_dir / "tools" / "a.py").write_text("X = 1\n", encoding="utf-8")
        (alt_dir / "tools" / "a.py").write_text("X = 2\n", encoding="utf-8")

        base_fp = install_identity.install_fingerprint(base_dir)
        alt_fp = install_identity.install_fingerprint(alt_dir)

        self.assertNotEqual(base_fp, alt_fp)

    def test_diagnose_install_mismatch_classifications(self):
        """Diagnose correctly identifies MATCH, COPIES_IDENTICAL, and DIVERGENT."""
        dir1 = self.root / "dir1"
        dir2 = self.root / "dir2"
        dir3 = self.root / "dir3"

        for d in (dir1, dir2, dir3):
            (d / "saipen").mkdir(parents=True)
            (d / "tools").mkdir(parents=True)
            (d / "VERSION").write_text("8.1.0\n", encoding="utf-8")
            (d / "saipen" / "BOOT.md").write_text("# BOOT\n", encoding="utf-8")
            (d / "tools" / "saipen_engine").mkdir()
            (d / "tools" / "saipen_engine" / "a.py").write_text("VAL = 1\n", encoding="utf-8")

        # dir3 differs in a.py
        (dir3 / "tools" / "saipen_engine" / "a.py").write_text("VAL = 999\n", encoding="utf-8")

        # 1. MATCH: same directory
        diag_match = install_identity.diagnose_install_mismatch(str(dir1), running_home_path=dir1)
        self.assertEqual(diag_match["status"], install_identity.STATUS_MATCH)
        self.assertFalse(diag_match["is_blocking"])

        # 2. COPIES_IDENTICAL: different directories, same content fingerprint
        diag_identical = install_identity.diagnose_install_mismatch(
            str(dir2), running_home_path=dir1
        )
        self.assertEqual(diag_identical["status"], install_identity.STATUS_COPIES_IDENTICAL)
        self.assertFalse(diag_identical["is_blocking"])
        self.assertEqual(
            diag_identical["running_fingerprint"], diag_identical["persisted_fingerprint"]
        )

        # 3. DIVERGENT: different directories, divergent content fingerprint
        diag_divergent = install_identity.diagnose_install_mismatch(
            str(dir3), running_home_path=dir1
        )
        self.assertEqual(diag_divergent["status"], install_identity.STATUS_DIVERGENT)
        self.assertTrue(diag_divergent["is_blocking"])
        self.assertNotEqual(
            diag_divergent["running_fingerprint"], diag_divergent["persisted_fingerprint"]
        )

    def test_mutating_operations_refuse_when_home_is_divergent(self):
        """Mutating operations refuse before journaling when STATE.saipen_home is divergent."""
        divergent_home = self.root / "divergent_home"
        (divergent_home / "saipen").mkdir(parents=True)
        (divergent_home / "tools").mkdir(parents=True)
        (divergent_home / "VERSION").write_text("8.1.0\n", encoding="utf-8")
        (divergent_home / "saipen" / "BOOT.md").write_text("# DIVERGENT BOOT\n", encoding="utf-8")
        (divergent_home / "saipen" / "CORE.md").write_text("# CORE\n", encoding="utf-8")
        (divergent_home / "saipen" / "STYLE.md").write_text("# STYLE\n", encoding="utf-8")
        (divergent_home / "extensions" / "subs").mkdir(parents=True)
        (divergent_home / "extensions" / "subs" / "PROTOCOL.md").write_text(
            "# SUBS\n", encoding="utf-8"
        )
        (divergent_home / "tools" / "extra.py").write_text("# EXTRA DIVERGENT\n", encoding="utf-8")
        (divergent_home / "tools" / "saipen_engine").mkdir()
        (divergent_home / "tools" / "saipen_engine" / "operations.py").write_text(
            "# divergent engine\n", encoding="utf-8"
        )

        project = self._make_project(divergent_home.resolve().as_posix())

        res = operations.checkpoint(project, "test-agent", "RUN", "T-1", "test check")
        self.assertFalse(res.ok)
        self.assertEqual(res.code, "HOME_REQUIRED")
        self.assertIn("home-divergent", res.message)
        self.assertEqual(res.to_dict().get("next_action"), "saipen rebind-home --auto")

    def test_rebind_home_auto_converges_when_home_differed_from_running(self):
        """rebind_home_auto converges saipen_home onto running engine when they differ."""
        other_home = self._full_home("other_home")

        project = self._make_project(other_home.resolve().as_posix())

        # Running engine is REPO
        running = state.running_home().resolve().as_posix()
        self.assertNotEqual(other_home.resolve().as_posix(), running)
        self.assertEqual(state.persisted_home_access(other_home)[0], state.HOME_USABLE)

        result = operations.rebind_home_auto(project, "test-agent")
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(result.code, "HOST_BINDING_CONVERGED")

        # Verify STATE was updated to running
        state_text = (project / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        self.assertIn(running, state_text)

        # Idempotent second call returns HOME_ALREADY_BOUND
        second = operations.rebind_home_auto(project, "test-agent")
        self.assertTrue(second.ok, second.to_dict())
        self.assertEqual(second.code, "HOME_ALREADY_BOUND")

    def test_shared_home_gate_refuses_the_divergent_engine(self):
        home = self._full_home("shared-home-gate")
        refusal = state.home_refusal(home)
        self.assertIsNotNone(refusal)
        self.assertEqual(refusal[0], "HOME_REQUIRED")
        self.assertIn("home-divergent", refusal[1])
        self.assertEqual(refusal[2], "saipen rebind-home --auto")

    def test_tool_admission_refuses_the_same_divergent_engine(self):
        home = self._full_home("tool-admission")
        project = self._make_project(home.as_posix())
        snapshot = admission.protocol_snapshot(project, actor="test-agent")
        self.assertEqual(snapshot["block"], "HOME_REQUIRED", snapshot)
        self.assertEqual(snapshot.get("route"), "saipen rebind-home --auto")

    def test_a_partially_unreadable_home_is_not_a_proven_divergence(self):
        home = self._full_home("partially-unreadable")
        unreadable = home / "tools" / "saipen_engine" / "operations.py"
        read_bytes = Path.read_bytes

        def read(path):
            if path == unreadable:
                raise PermissionError("denied")
            return read_bytes(path)

        with mock.patch.object(Path, "read_bytes", read):
            refusal = state.home_refusal(home)
        self.assertEqual(refusal[0], state.CODE_HOME_INACCESSIBLE, refusal)
        self.assertIsNone(refusal[2])

    def test_auto_rebind_preserves_a_partially_unreadable_home(self):
        home = self._full_home("unreadable-rebind")
        project = self._make_project(home.as_posix())
        before = {
            name: (project / ".saipen" / name).read_bytes()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        }
        unreadable = home / "tools" / "saipen_engine" / "operations.py"
        read_bytes = Path.read_bytes

        def read(path):
            if path == unreadable:
                raise PermissionError("denied")
            return read_bytes(path)

        with mock.patch.object(Path, "read_bytes", read):
            result = operations.rebind_home_auto(project, "test-agent")
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, state.CODE_HOME_INACCESSIBLE)
        self.assertEqual(
            before, {name: (project / ".saipen" / name).read_bytes() for name in before}
        )

    def test_a_literal_naming_the_running_engine_cannot_hide_divergence(self):
        home = self._full_home("independent")
        (home / "tools" / "saipen.py").write_text(
            f"# runpy.run_path {REPO}\nraise RuntimeError('different engine')\n",
            encoding="utf-8",
        )
        diagnosis = install_identity.diagnose_install_mismatch(home, REPO)
        self.assertEqual(diagnosis["status"], install_identity.STATUS_DIVERGENT)
        self.assertTrue(diagnosis["is_blocking"])

    def test_an_unreadable_engine_file_cannot_yield_a_partial_fingerprint(self):
        home = self._full_home("partial")
        unreadable = home / "tools" / "saipen_engine" / "operations.py"
        read_bytes = Path.read_bytes

        def read(path):
            if path == unreadable:
                raise PermissionError("denied")
            return read_bytes(path)

        with mock.patch.object(Path, "read_bytes", read):
            self.assertEqual(install_identity.install_fingerprint(home), "missing-v1")

    def test_identical_copies_are_not_a_blocking_mismatch(self):
        left = self._full_home("left")
        right = self._full_home("right")
        with mock.patch.object(state, "running_home", return_value=left):
            self.assertIsNone(state.running_home_mismatch_error(right))

    def test_continue_converges_a_divergent_home_before_resuming_work(self):
        import json
        import subprocess
        import sys

        home = self._full_home("continued")
        project = self._make_project(home.as_posix())
        checkpoint = project / ".saipen" / "STATE.md"
        checkpoint.write_text(
            checkpoint.read_text(encoding="utf-8").replace(
                "mode: full\n",
                "mode: full\nexecution_intent: goal\ngoal_waves: 0\ngoal_tickets: 0\n",
            ),
            encoding="utf-8",
        )
        original = {p.relative_to(home): p.read_bytes() for p in home.rglob("*") if p.is_file()}
        process = subprocess.run(
            [
                sys.executable,
                str(REPO / "tools" / "saipen.py"),
                "continue",
                "--project-root",
                str(project),
                "--json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertTrue(json.loads(process.stdout)["ok"])
        fields, error = state.parse_frontmatter(checkpoint.read_text(encoding="utf-8"))
        self.assertIsNone(error)
        self.assertEqual(Path(fields["saipen_home"]), REPO)
        self.assertEqual(
            original, {p.relative_to(home): p.read_bytes() for p in home.rglob("*") if p.is_file()}
        )

    def test_continuation_brakes_preserve_the_recorded_install(self):
        import json
        import os
        import subprocess
        import sys

        for variant in ("dry-run", "read-only", "wait"):
            with self.subTest(variant=variant):
                home = self._full_home(variant)
                project = self._make_project(home.as_posix())
                checkpoint = project / ".saipen" / "STATE.md"
                text = checkpoint.read_text(encoding="utf-8").replace(
                    "mode: full\n",
                    "mode: full\nexecution_intent: goal\ngoal_waves: 0\ngoal_tickets: 0\n",
                )
                if variant == "wait":
                    text = text.replace(
                        "next_action: PHASE BUILD T-1", "next_action: WAIT: operator decision"
                    )
                checkpoint.write_text(text, encoding="utf-8")
                args = ["--dry-run"] if variant == "dry-run" else []
                env = dict(os.environ)
                if variant == "read-only":
                    env["SAIPEN_CAPABILITY"] = "read-only"
                process = subprocess.run(
                    [
                        sys.executable,
                        str(REPO / "tools" / "saipen.py"),
                        "continue",
                        "--project-root",
                        str(project),
                        "--json",
                        *args,
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                    env=env,
                )
                self.assertFalse(json.loads(process.stdout)["ok"], process.stdout)
                fields, error = state.parse_frontmatter(checkpoint.read_text(encoding="utf-8"))
                self.assertIsNone(error)
                self.assertEqual(Path(fields["saipen_home"]), home)

    def test_continue_chain_route_classification(self):
        """classify_route classifies saipen rebind-home --auto as APPLY_REBIND_HOME."""
        route = {
            "ok": True,
            "action": "saipen rebind-home --auto",
            "reason": "rebind-home",
        }
        kind = continue_loop.classify_route(route, {}, {})
        self.assertEqual(kind, continue_loop.APPLY_REBIND_HOME)

    def test_live_host_surfaces_inspection(self):
        """C: installed skill and V: repository clone can be diagnosed for divergence."""
        c_root = Path(r"C:\Users\vac34\.agents\skills\saipen")
        v_root = Path(r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN")
        try:
            c_exists = c_root.exists()
        except OSError:
            c_exists = False
        try:
            v_exists = v_root.exists()
        except OSError:
            v_exists = False
        if c_exists and v_exists:
            diag = install_identity.diagnose_install_mismatch(c_root, running_home_path=v_root)
            self.assertIn(
                diag["status"],
                (install_identity.STATUS_COPIES_IDENTICAL, install_identity.STATUS_DIVERGENT),
            )
            self.assertIn("running_fingerprint", diag)
            self.assertIn("persisted_fingerprint", diag)

    def test_validate_reports_rebind_required_on_mismatch(self):
        """saipen validate reports REBIND_REQUIRED and rebind-home --auto on install mismatch."""
        import json
        import subprocess
        import sys

        other_home = self._full_home("other_home")

        project = self._make_project(other_home.resolve().as_posix())

        proc = subprocess.run(
            [
                sys.executable,
                str(REPO / "tools" / "saipen.py"),
                "validate",
                "--project-root",
                str(project),
                "--json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "INSTALL_IDENTITY_MISMATCH")
        self.assertEqual(payload.get("repair_status"), "REBIND_REQUIRED")
        self.assertEqual(payload.get("canonical_next_command"), "saipen rebind-home --auto")
        self.assertEqual(payload.get("diagnostic"), "INSTALL_IDENTITY_MISMATCH")


if __name__ == "__main__":
    unittest.main()
