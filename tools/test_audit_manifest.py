"""Audit-evidence contract regression: `.saipen/MANIFEST.json`.

WHY THIS EXISTS
---------------
A packager cannot know which of `.saipen/` is load-bearing, and the guess it
used to make was silently coupled to Git: a project ignoring `.saipen/*`
hid its whole protocol memory from `git ls-files --others --exclude-standard`,
so an audit snapshot could carry one stale active intake receipt and nothing
able to contradict it. Measured across the registered fleet, 10 of 24 SAIPEN
projects were in that state.

This module owns the protocol half of the repair: SAIPEN declares its own
evidence, and the declaration must stay true without anyone weakening
`.gitignore`. These tests pin the properties a consumer is entitled to rely
on:

    THE MANIFEST IS DECLARATIVE, SO IT CANNOT GO STALE PER CHECKPOINT.
    MANDATORY MEANS CURRENT STATE IS UNREADABLE WITHOUT IT.
    NON-EXPORTABLE PATHS ARE NEVER EVIDENCE.
    AN UNKNOWN CONTRACT VERSION IS REFUSED, NEVER REINTERPRETED.

Run standalone:

    python tools/test_audit_manifest.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from saipen_engine import audit_manifest
from saipen_engine.reconcile import reconcile_protocol_state
from test_control_primitives import ControlFixture

TOOL = Path(__file__).resolve().parent / "saipen.py"


def _make_project(root: Path) -> Path:
    saipen = root / ".saipen"
    saipen.mkdir(parents=True)
    (saipen / "STATE.md").write_text("phase: DONE\ntask: none\n", encoding="utf-8")
    (saipen / "BOARD.md").write_text("# Board\n", encoding="utf-8")
    (saipen / "LOG.md").write_text("- E-1 start\n", encoding="utf-8")
    (saipen / "IDENTITY.md").write_text("project_lineage: lineage-x\n", encoding="utf-8")
    (saipen / "locks").mkdir()
    (saipen / "locks" / "core.lock").write_text("x", encoding="utf-8")
    (saipen / "LOCAL_STATE.json").write_text("{}", encoding="utf-8")
    return saipen


class TestContractShape(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.saipen = _make_project(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_mandatory_is_exactly_the_current_state_documents(self):
        """STATE, BOARD, LOG, IDENTITY. Nothing else is mandatory.

        Each earns it: STATE names the phase and claimed ticket, BOARD
        carries the Work, LOG is the append-only event authority, IDENTITY is
        the portable lineage carrier. A snapshot missing one cannot state the
        current lifecycle at all, which makes it misleading rather than
        merely thin.
        """
        manifest = audit_manifest.build(self.root)
        declared = [item["path"] for item in manifest["evidence"]["mandatory"]]
        self.assertEqual(declared, ["STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md"])
        self.assertEqual(manifest["required"], declared)

    def test_private_working_state_is_declared_non_exportable(self):
        manifest = audit_manifest.build(self.root)
        banned = manifest["evidence"]["non_exportable"]
        self.assertIn("locks/", banned)
        self.assertIn("recovery/", banned)
        self.assertIn("LOCAL_STATE.json", banned)
        every_declared = [
            item["path"]
            for tier in ("mandatory", "conditional", "optional")
            for item in manifest["evidence"][tier]
        ]
        for forbidden in ("locks", "recovery", "LOCAL_STATE.json"):
            self.assertNotIn(forbidden, every_declared)

    def test_every_evidence_dir_declares_a_finite_cap(self):
        """An uncapped rule is an unbounded walk waiting to happen."""
        manifest = audit_manifest.build(self.root)
        for tier in ("conditional", "optional"):
            for rule in manifest["evidence"][tier]:
                self.assertIsInstance(rule["max_files"], int)
                self.assertGreater(rule["max_files"], 0)
                self.assertIsInstance(rule["recursive"], bool)

    def test_declared_paths_are_relative_and_cannot_escape(self):
        manifest = audit_manifest.build(self.root)
        paths = [item["path"] for tier in manifest["evidence"] if tier != "non_exportable"
                 for item in manifest["evidence"][tier]]
        for path in paths:
            self.assertFalse(path.startswith("/"), path)
            self.assertNotIn("..", path.split("/"), path)
            self.assertFalse(len(path) >= 2 and path[1] == ":", path)

    def test_manifest_carries_no_machine_local_identity(self):
        """`project_identity` is a runtime lock identity, not provenance.

        Embedding it would churn the document per machine and invite a
        consumer to trust it as portable. The portable lineage already
        travels in IDENTITY.md, which this contract makes mandatory.
        """
        manifest = audit_manifest.build(self.root)
        self.assertNotIn("project_identity", manifest)
        blob = json.dumps(manifest)
        self.assertNotIn(str(self.root), blob)


class TestDeclarativeStability(unittest.TestCase):
    """The manifest must not need rewriting every time work happens."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.saipen = _make_project(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_write_is_idempotent_and_survives_project_mutation(self):
        first = audit_manifest.write(self.root)
        self.assertTrue(first["ok"])
        self.assertTrue(first["changed"])
        self.assertTrue(audit_manifest.is_current(self.root))

        # A checkpoint lands: LOG grows, a receipt closes, evidence appears.
        (self.saipen / "LOG.md").write_text("- E-1 start\n- E-2 done\n", encoding="utf-8")
        (self.saipen / "KNOWLEDGE").mkdir()
        (self.saipen / "KNOWLEDGE" / "proof.md").write_text("x\n", encoding="utf-8")

        self.assertTrue(
            audit_manifest.is_current(self.root),
            "a declarative contract must not go stale when the project moves",
        )
        second = audit_manifest.write(self.root)
        self.assertFalse(second["changed"])
        self.assertEqual(second["code"], "AUDIT_MANIFEST_CURRENT")

    def test_render_is_deterministic(self):
        a = audit_manifest.build(self.root)
        b = audit_manifest.build(self.root)
        a.pop("generated_at")
        b.pop("generated_at")
        self.assertEqual(audit_manifest.render(a), audit_manifest.render(b))

    def test_status_reports_missing_mandatory_as_protocol_incomplete(self):
        (self.saipen / "LOG.md").unlink()
        status = audit_manifest.status(self.root)
        self.assertFalse(status["ok"])
        self.assertEqual(status["code"], "PROTOCOL_INCOMPLETE")
        self.assertIn("LOG.md", status["mandatory_missing"])


class TestCommandSurface(unittest.TestCase):
    """`saipen audit manifest` end to end, through the real CLI."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.saipen = _make_project(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, *args):
        proc = subprocess.run(
            [sys.executable, str(TOOL), "audit", "manifest", *args,
             "--project-root", str(self.root), "--json"],
            capture_output=True,
            text=True,
        )
        try:
            return proc.returncode, json.loads(proc.stdout or "{}")
        except ValueError:
            return proc.returncode, {"_stdout": proc.stdout, "_stderr": proc.stderr}

    def test_read_only_by_default(self):
        """A packager must be able to ASK without mutating the project."""
        code, out = self._run()
        self.assertEqual(code, 0, out)
        self.assertTrue(out["ok"])
        self.assertFalse(audit_manifest.manifest_path(self.root).exists())

    def test_write_creates_the_contract(self):
        code, out = self._run("--write")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["code"], "AUDIT_MANIFEST_WRITTEN")
        written = json.loads(audit_manifest.manifest_path(self.root).read_text(encoding="utf-8"))
        self.assertEqual(written["kind"], "saipen_audit_manifest")
        self.assertEqual(written["contract_version"], audit_manifest.CONTRACT_VERSION)

    def test_dry_run_writes_nothing(self):
        code, out = self._run("--write", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertTrue(out["dry_run"])
        self.assertFalse(audit_manifest.manifest_path(self.root).exists())

    def test_force_requires_write(self):
        code, out = self._run("--force")
        self.assertEqual(code, 2)
        self.assertEqual(out["code"], "VALIDATION_FAILED")

    def test_unknown_flag_is_refused(self):
        code, out = self._run("--nonsense")
        self.assertEqual(code, 2)
        self.assertEqual(out["code"], "VALIDATION_FAILED")


def _existing_project(root: Path) -> Path:
    """An EXISTING valid SAIPEN project: history, evidence, private state."""
    saipen = root / ".saipen"
    saipen.mkdir(parents=True)
    (saipen / "STATE.md").write_text(
        "---\nphase: DONE\ntask: none\nlast_event: 328\n---\n", encoding="utf-8"
    )
    (saipen / "BOARD.md").write_text(
        "## DOING\n## TODO\n- [ ] T-46 [P1] close the sweep\n## DONE\n## BLOCKED\n",
        encoding="utf-8",
    )
    (saipen / "LOG.md").write_text(
        "- E-1 start\n- E-328 [T-48] DEC: ticket finished\n", encoding="utf-8"
    )
    (saipen / "IDENTITY.md").write_text("project_lineage: lineage-x\n", encoding="utf-8")
    (saipen / "logs").mkdir()
    (saipen / "logs" / "LOG-001.md").write_text("- E-0 sealed\n", encoding="utf-8")
    (saipen / "intake" / "active").mkdir(parents=True)
    (saipen / "intake" / "active" / "SRC-007.md").write_text("stale\n", encoding="utf-8")
    (saipen / "archive" / "source").mkdir(parents=True)
    (saipen / "archive" / "source" / "SRC-008.md").write_text("closed\n", encoding="utf-8")
    (saipen / "KNOWLEDGE").mkdir()
    (saipen / "KNOWLEDGE" / "evidence.md").write_text("proof\n", encoding="utf-8")
    (saipen / "locks").mkdir()
    (saipen / "locks" / "core.lock").write_text("lock\n", encoding="utf-8")
    (saipen / "recovery").mkdir()
    (saipen / "recovery" / "op.json").write_text("{}\n", encoding="utf-8")
    (saipen / "LOCAL_STATE.json").write_text("{}\n", encoding="utf-8")
    return saipen


def _evidence_bytes(root: Path) -> dict[str, bytes]:
    """Every byte of the project's protocol memory, for zero-loss proofs."""
    base = root / ".saipen"
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(base.rglob("*"))
        if path.is_file()
    }


class BootstrapCase(unittest.TestCase):
    """Shared fixture: an EXISTING valid project with no MANIFEST.json."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.saipen = _existing_project(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def manifest(self) -> dict:
        return json.loads(
            audit_manifest.manifest_path(self.root).read_text(encoding="utf-8")
        )

    def _git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
            cwd=str(self.root),
            check=True,
            capture_output=True,
        )


class TestExistingProjectEnrollment(BootstrapCase):
    """A valid project that predates the contract acquires it in place.

    This is the measured gap: the collector was correct, but real projects
    packaged as PROTOCOL_MANIFEST_ABSENT because nothing had ever enrolled them
    and nobody knew a flag existed.
    """

    def test_existing_valid_project_without_manifest_is_enrolled(self):
        self.assertFalse(audit_manifest.manifest_path(self.root).exists())
        before = _evidence_bytes(self.root)
        result = audit_manifest.ensure(self.root)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["code"], audit_manifest.CODE_WRITTEN)
        self.assertTrue(result["changed"])
        self.assertEqual(result["layout"], audit_manifest.LAYOUT_CURRENT)
        written = self.manifest()
        self.assertEqual(written["kind"], "saipen_audit_manifest")
        self.assertEqual(written["contract_version"], audit_manifest.CONTRACT_VERSION)
        self.assertTrue(audit_manifest.is_current(self.root))

        # Not one byte of existing evidence was rewritten, and nothing that
        # was there before is gone. Enrollment is ADDITIVE.
        after = _evidence_bytes(self.root)
        for rel, blob in before.items():
            self.assertIn(rel, after, rel)
            self.assertEqual(after[rel], blob, rel)
        self.assertEqual(set(after) - set(before), {".saipen/MANIFEST.json"})

    def test_fresh_project_is_enrolled(self):
        self.assertEqual(
            audit_manifest.classify_layout(self.root)["state"],
            audit_manifest.LAYOUT_CURRENT,
        )
        result = audit_manifest.ensure(self.root)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.manifest()["evidence"]["mandatory"][0]["path"], "STATE.md")

    def test_repeated_bootstrap_is_idempotent_and_stable(self):
        first = audit_manifest.ensure(self.root)
        self.assertEqual(first["code"], audit_manifest.CODE_WRITTEN)
        path = audit_manifest.manifest_path(self.root)
        blob = path.read_bytes()
        stamp = path.stat().st_mtime_ns

        for _ in range(3):
            again = audit_manifest.ensure(self.root)
            self.assertTrue(again["ok"], again)
            self.assertEqual(again["code"], audit_manifest.CODE_CURRENT)
            self.assertFalse(again["changed"])
        self.assertEqual(path.read_bytes(), blob)
        self.assertEqual(path.stat().st_mtime_ns, stamp)

    def test_current_manifest_is_never_rewritten(self):
        audit_manifest.ensure(self.root)
        path = audit_manifest.manifest_path(self.root)
        stamp = path.stat().st_mtime_ns
        result = audit_manifest.ensure(self.root, force=False)
        self.assertEqual(result["code"], audit_manifest.CODE_CURRENT)
        self.assertEqual(path.stat().st_mtime_ns, stamp)

    def test_generation_is_deterministic_from_the_contract(self):
        audit_manifest.ensure(self.root)
        on_disk = self.manifest()
        on_disk.pop("generated_at", None)
        expected = audit_manifest.build(
            self.root, protocol_dir=audit_manifest.default_protocol_dir()
        )
        expected.pop("generated_at", None)
        self.assertEqual(on_disk, expected)


class TestMigrationAndRefusal(BootstrapCase):
    """Older supported layouts migrate; anything else refuses loudly."""

    def _declare(self, payload: dict | str) -> Path:
        path = audit_manifest.manifest_path(self.root)
        if isinstance(payload, str):
            path.write_text(payload, encoding="utf-8")
        else:
            path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_stale_supported_manifest_is_migrated(self):
        # An older declaration of the SAME supported contract: the shape drifted
        # (a field was dropped, a cap changed) while the version still reads 1.
        stale = audit_manifest.build(self.root)
        stale["evidence"].pop("non_exportable")
        stale["evidence"]["conditional"] = stale["evidence"]["conditional"][:2]
        path = self._declare(stale)
        before = path.read_bytes()
        result = audit_manifest.ensure(self.root)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["code"], audit_manifest.CODE_UPGRADED)
        self.assertNotEqual(path.read_bytes(), before)
        self.assertTrue(audit_manifest.is_current(self.root))
        self.assertEqual(
            len(self.manifest()["evidence"]["conditional"]),
            len(audit_manifest.CONDITIONAL_DIRS),
        )

    def test_newer_contract_version_is_refused_not_downgraded(self):
        future = audit_manifest.build(self.root)
        future["contract_version"] = audit_manifest.CONTRACT_VERSION + 1
        path = self._declare(future)
        before = path.read_bytes()
        result = audit_manifest.ensure(self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], audit_manifest.CODE_REFUSED)
        self.assertEqual(result["reason_code"], audit_manifest.REASON_CONTRACT_UNSUPPORTED)
        self.assertEqual(path.read_bytes(), before, "a newer contract is never downgraded")

    def test_force_replaces_a_declaration_it_cannot_interpret(self):
        future = audit_manifest.build(self.root)
        future["contract_version"] = audit_manifest.CONTRACT_VERSION + 1
        self._declare(future)
        result = audit_manifest.ensure(self.root, force=True)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["code"], audit_manifest.CODE_UPGRADED)
        self.assertTrue(audit_manifest.is_current(self.root))

    def test_manifest_that_is_not_this_contract_is_refused(self):
        path = self._declare("this is not json")
        before = path.read_bytes()
        result = audit_manifest.ensure(self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason_code"], audit_manifest.REASON_CONTRACT_MALFORMED)
        self.assertEqual(path.read_bytes(), before)

    def test_malformed_checkpoint_is_refused_and_mints_nothing(self):
        (self.saipen / "LOG.md").unlink()
        result = audit_manifest.ensure(self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], audit_manifest.CODE_REFUSED)
        self.assertEqual(result["reason_code"], audit_manifest.REASON_LAYOUT_MALFORMED)
        self.assertEqual(result["layout"], audit_manifest.LAYOUT_MALFORMED)
        self.assertFalse(audit_manifest.manifest_path(self.root).exists())

    def test_directory_where_a_document_belongs_is_malformed(self):
        (self.saipen / "BOARD.md").unlink()
        (self.saipen / "BOARD.md").mkdir()
        result = audit_manifest.ensure(self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason_code"], audit_manifest.REASON_LAYOUT_MALFORMED)

    def test_project_without_protocol_memory_is_refused(self):
        empty = self.root / "nowhere"
        empty.mkdir()
        result = audit_manifest.ensure(empty)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason_code"], audit_manifest.REASON_MEMORY_ABSENT)
        self.assertFalse((empty / ".saipen").exists())

    def test_legacy_layout_without_lineage_is_enrolled_honestly(self):
        """A pre-T-1003 checkpoint is a SUPPORTED older layout.

        Enrollment proceeds, and the contract keeps declaring IDENTITY.md
        mandatory, so a consumer reports the snapshot incomplete rather than
        complete-over-a-stale-reading. The lineage itself is minted by the
        protocol's own journaled migration (`ensure_project_lineage`), never
        fabricated here.
        """
        (self.saipen / "IDENTITY.md").unlink()
        result = audit_manifest.ensure(self.root)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["layout"], audit_manifest.LAYOUT_LEGACY)
        self.assertIn("IDENTITY.md", self.manifest()["required"])
        self.assertFalse((self.saipen / "IDENTITY.md").exists())

    def test_enrollment_is_never_git_visibility(self):
        """`.gitignore`, global excludes and info/exclude change nothing.

        Publication visibility is a Git decision. Enrollment is a protocol
        decision, so all three hiding mechanisms must leave it identical.
        """
        self._git("init", "-q")
        (self.root / ".gitignore").write_text(".saipen/*\n", encoding="utf-8")
        globals_file = self.root / "global_ignore"
        globals_file.write_text(".saipen/\n", encoding="utf-8")
        self._git("config", "core.excludesFile", str(globals_file))
        info = self.root / ".git" / "info"
        info.mkdir(parents=True, exist_ok=True)
        (info / "exclude").write_text(".saipen/\n", encoding="utf-8")
        hidden = subprocess.run(
            ["git", "-C", str(self.root), "check-ignore", "-q", ".saipen/STATE.md"],
            capture_output=True,
        )
        self.assertEqual(hidden.returncode, 0, "fixture must actually be ignored")

        result = audit_manifest.ensure(self.root)
        self.assertTrue(result["ok"], result)
        self.assertTrue(audit_manifest.manifest_path(self.root).is_file())
        self.assertTrue(audit_manifest.is_current(self.root))


class TestLifecycleEnrollment(ControlFixture):
    """Enrollment happens by USING the protocol, not by remembering a flag.

    `reconcile_protocol_state` is the protocol's one self-healing entry -- every
    ordinary `continue`/`cc`, `recover` and fleet admission passes through it --
    so it is the lifecycle point where a project proves its checkpoint is real
    and may therefore be enrolled.
    """

    def test_first_transition_enrolls_an_existing_project(self):
        project = self.make_project()
        self.assertFalse(audit_manifest.manifest_path(project).exists())
        result = reconcile_protocol_state(project, "tester")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["code"], "CLEAN")
        self.assertTrue(audit_manifest.manifest_path(project).is_file())
        self.assertTrue(audit_manifest.is_current(project))
        self.assertTrue(result["audit_manifest"]["changed"])

    def test_steady_state_transition_is_unchanged_and_silent(self):
        project = self.make_project()
        reconcile_protocol_state(project, "tester")
        path = audit_manifest.manifest_path(project)
        stamp = path.stat().st_mtime_ns
        again = reconcile_protocol_state(project, "tester")
        self.assertEqual(again["code"], "CLEAN")
        self.assertNotIn("audit_manifest", again)
        self.assertEqual(path.stat().st_mtime_ns, stamp)

    def test_dry_run_transition_writes_nothing(self):
        project = self.make_project()
        preview = reconcile_protocol_state(project, "tester", dry_run=True)
        self.assertEqual(preview["code"], "CLEAN")
        self.assertNotIn("audit_manifest", preview)
        self.assertFalse(audit_manifest.manifest_path(project).exists())

    def test_unreconcilable_project_is_not_enrolled(self):
        """Fail closed: a refused repair must not certify an export contract."""
        project = self.make_project()
        state = project / ".saipen" / "STATE.md"
        state.write_text("", encoding="utf-8")
        result = reconcile_protocol_state(project, "tester")
        self.assertFalse(result["ok"], result)
        self.assertFalse(audit_manifest.manifest_path(project).exists())

    def test_cli_write_enrolls_and_then_reports_current(self):
        project = self.make_project()
        proc = subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "audit",
                "manifest",
                "--write",
                "--project-root",
                str(project),
                "--json",
            ],
            capture_output=True,
            text=True,
        )
        out = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0, out)
        self.assertEqual(out["code"], audit_manifest.CODE_WRITTEN)
        proc = subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "audit",
                "manifest",
                "--write",
                "--project-root",
                str(project),
                "--json",
            ],
            capture_output=True,
            text=True,
        )
        out = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0, out)
        self.assertEqual(out["code"], audit_manifest.CODE_CURRENT)
        self.assertFalse(out["changed"])

    def test_read_only_projection_reports_enrollment_state(self):
        project = self.make_project()
        proc = subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "audit",
                "manifest",
                "--project-root",
                str(project),
                "--json",
            ],
            capture_output=True,
            text=True,
        )
        out = json.loads(proc.stdout)
        self.assertEqual(out["layout"], audit_manifest.LAYOUT_CURRENT)
        self.assertEqual(out["declared"], audit_manifest.DECLARED_ABSENT)
        self.assertEqual(out["enrollment"]["code"], audit_manifest.CODE_PLAN)
        self.assertFalse(audit_manifest.manifest_path(project).exists())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
