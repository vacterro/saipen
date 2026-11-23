"""SAIPEN audit-evidence capture: the snapshot-integrity regression matrix.

THE DEFECT THIS PINS
--------------------
AUDAPACK's Git inventory is ``git ls-files`` plus ``git ls-files --others
--exclude-standard``. A project carrying ``.saipen/*`` in ``.gitignore``
therefore hid its whole protocol memory from discovery, and the archive
manifest still said ``accounting_reconciled: true`` -- the identity
``discovered == included + excluded + failed`` held because the missing
evidence was never discovered at all. Real consequence, measured: a LIMISAW
package shipped ``IDENTITY.md`` plus one stale ``SRC-007`` intake receipt and
no STATE/BOARD/LOG, so an external reviewer concluded work was blocked by a
source the live project had already moved past. 10 of 24 registered SAIPEN
projects were in that state.

The repair keeps Git visibility and audit evidence separate: SAIPEN declares
its own evidence in ``.saipen/MANIFEST.json`` and AUDAPACK collects exactly
that, bounded, without anyone weakening ``.gitignore``.

Every test below is a case from the required matrix and is named for it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from audapack import saipen_evidence as se
from audapack.config import PackingConfig
from audapack.packing import (
    MANIFEST_FILENAME,
    pack_single,
)
from audapack.source_inventory import (
    CODE_SYMLINK_UNSAFE,
    CODE_TRACKED_HARD_DENY_CONFLICT,
    SourceInventoryError,
    build_git_inventory,
)

# A manifest shaped exactly like the one `saipen audit manifest --write`
# emits. Written by hand here on purpose: these tests must fail if AUDAPACK
# drifts from the published contract, not merely if SAIPEN changes with it.
CONTRACT = {
    "schema_version": 1,
    "kind": "saipen_audit_manifest",
    "contract_version": 1,
    "protocol_version": "8.0.1",
    "generated_at": "2026-09-15T00:00:00Z",
    "generator": "saipen-audit-manifest/1",
    "memory_root": ".saipen",
    "required": ["STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md"],
    "evidence": {
        "mandatory": [
            {"path": "STATE.md", "kind": "file"},
            {"path": "BOARD.md", "kind": "file"},
            {"path": "LOG.md", "kind": "file"},
            {"path": "IDENTITY.md", "kind": "file"},
        ],
        "conditional": [
            {"path": "logs", "kind": "dir", "recursive": True, "max_files": 4000},
            {"path": "intake", "kind": "dir", "recursive": True, "max_files": 8000},
            {"path": "archive/source", "kind": "dir", "recursive": True, "max_files": 8000},
            {"path": "KNOWLEDGE", "kind": "dir", "recursive": True, "max_files": 4000},
            {"path": "evidence", "kind": "dir", "recursive": True, "max_files": 4000},
        ],
        "optional": [
            {"path": "extensions", "kind": "dir", "recursive": True, "max_files": 4000},
        ],
        "non_exportable": ["locks/", "recovery/", "LOCAL_STATE.json"],
    },
    "references": {
        "surfaces": ["evidence"],
        "carriers": [
            {"path": "STATE.md", "kind": "file"},
            {"path": "BOARD.md", "kind": "file"},
            {"path": "LOG.md", "kind": "file"},
            {"path": "logs", "kind": "dir", "recursive": True, "suffix": ".md", "max_files": 4000},
            {"path": "intake/coverage", "kind": "dir", "recursive": False, "suffix": ".json", "max_files": 8000},
            {"path": "archive/source", "kind": "dir", "recursive": False, "suffix": ".coverage.json", "max_files": 8000},
        ],
        "max_carrier_bytes": 8 * 1024 * 1024,
        "max_total_bytes": 64 * 1024 * 1024,
        "max_references": 20000,
    },
}

# The contract every project carried BEFORE SRC-054, byte-for-byte in shape:
# no `evidence` rule and no citation carriers. Problip still held exactly this
# when its archive read COMPLETE without the PERF-001 proof its LOG cited.
PRE_SRC054_CONTRACT = json.loads(json.dumps(CONTRACT))
PRE_SRC054_CONTRACT["evidence"]["conditional"] = [
    rule for rule in PRE_SRC054_CONTRACT["evidence"]["conditional"] if rule["path"] != "evidence"
]
del PRE_SRC054_CONTRACT["references"]

#: Canonical contract fixtures captured from the REAL SAIPEN generator (see
#: tests/fixtures/saipen/README.md). Loaded from disk rather than hand-typed,
#: so this suite fails when AUDAPACK drifts from what SAIPEN actually writes
#: instead of merely from what this file believes it writes. `CONTRACT` above
#: stays hand-written on purpose: it is the v1 shape pinned independently of
#: the captured documents.
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "saipen"


def contract_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


#: The current contract: `contract_version` 2, written by the installed
#: protocol. This is the document that reached PACK and was refused.
CONTRACT_V2 = contract_fixture("MANIFEST.v2.json")
#: The published v1 shape, taken from a project a v1-era generator enrolled:
#: a freshly generated v1 document no longer exists.
CONTRACT_V1_CANONICAL = contract_fixture("MANIFEST.v1.json")
#: v3 fixture: forward-compatible superset of v2 (COMPATIBLE_DEGRADED case).
CONTRACT_V3 = contract_fixture("MANIFEST.v3.json")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )


class SaipenEvidenceCase(unittest.TestCase):
    """Base fixture: a Git repo carrying a realistic `.saipen/` tree."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = self.root / "proj"
        self.repo.mkdir(parents=True)
        _git(self.repo, "init", "-q")
        self.output = self.root / "out"
        self.output.mkdir()
        (self.repo / "app.py").write_text("print('x')\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    # -- fixture helpers ---------------------------------------------------

    def write_saipen(self, *, manifest=True, mandatory=True, contract=None):
        sp = self.repo / ".saipen"
        sp.mkdir(exist_ok=True)
        if mandatory:
            (sp / "STATE.md").write_text("phase: DONE\n", encoding="utf-8")
            (sp / "BOARD.md").write_text("# Board\n", encoding="utf-8")
            (sp / "LOG.md").write_text("- E-1 start\n", encoding="utf-8")
            (sp / "IDENTITY.md").write_text("project_lineage: lineage-x\n", encoding="utf-8")
        (sp / "logs").mkdir(exist_ok=True)
        (sp / "logs" / "LOG-001.md").write_text("- E-0 sealed\n", encoding="utf-8")
        (sp / "intake" / "active").mkdir(parents=True, exist_ok=True)
        (sp / "intake" / "active" / "SRC-007.md").write_text("stale\n", encoding="utf-8")
        (sp / "archive" / "source").mkdir(parents=True, exist_ok=True)
        (sp / "archive" / "source" / "SRC-008.md").write_text("closed\n", encoding="utf-8")
        (sp / "KNOWLEDGE").mkdir(exist_ok=True)
        (sp / "KNOWLEDGE" / "evidence.md").write_text("proof\n", encoding="utf-8")
        # Private working state the contract marks non-exportable.
        (sp / "locks").mkdir(exist_ok=True)
        (sp / "locks" / "core.lock").write_text("lock\n", encoding="utf-8")
        (sp / "recovery").mkdir(exist_ok=True)
        (sp / "recovery" / "op.json").write_text("{}\n", encoding="utf-8")
        (sp / "LOCAL_STATE.json").write_text("{}\n", encoding="utf-8")
        if manifest:
            (sp / "MANIFEST.json").write_text(
                json.dumps(CONTRACT if contract is None else contract, indent=1),
                encoding="utf-8",
            )
        return sp

    def ignore(self, *lines: str):
        (self.repo / ".gitignore").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def commit(self):
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "w")

    def inventory(self, excludes=None, always_exclude=None):
        return build_git_inventory(
            self.repo,
            set(excludes or []),
            always_exclude=list(always_exclude or []),
        )

    def included(self, inv):
        return {e.rel for e in inv.included_entries()}


class TestEvidenceSurvivesGitInvisibility(SaipenEvidenceCase):
    """Cases 1-5: however Git is told to hide `.saipen`, evidence survives."""

    MANDATORY = {
        ".saipen/STATE.md",
        ".saipen/BOARD.md",
        ".saipen/LOG.md",
        ".saipen/IDENTITY.md",
    }

    def test_case01_no_git_ignores_mandatory_evidence_included(self):
        self.write_saipen()
        self.commit()
        inv = self.inventory()
        self.assertTrue(self.MANDATORY <= self.included(inv))
        self.assertEqual(inv.saipen["status"], se.STATUS_COMPLETE)

    def test_case02_star_ignore_mandatory_evidence_still_included(self):
        self.write_saipen()
        self.ignore(".saipen/*")
        self.commit()
        inv = self.inventory()
        # Git really is hiding it: that is the precondition, not a detail.
        hidden = subprocess.run(
            ["git", "-C", str(self.repo), "check-ignore", "-q", ".saipen/STATE.md"],
            capture_output=True,
        )
        self.assertEqual(hidden.returncode, 0, "fixture must actually be ignored")
        self.assertTrue(self.MANDATORY <= self.included(inv))
        self.assertEqual(inv.saipen["status"], se.STATUS_COMPLETE)

    def test_case03_doublestar_ignore_mandatory_evidence_still_included(self):
        self.write_saipen()
        self.ignore(".saipen/**")
        self.commit()
        inv = self.inventory()
        self.assertTrue(self.MANDATORY <= self.included(inv))
        self.assertEqual(inv.saipen["status"], se.STATUS_COMPLETE)

    def test_case04_global_core_excludesfile_hides_saipen_evidence_survives(self):
        self.write_saipen()
        self.commit()
        globals_file = self.root / "global_ignore"
        globals_file.write_text(".saipen/\n", encoding="utf-8")
        _git(self.repo, "config", "core.excludesFile", str(globals_file))
        inv = self.inventory()
        self.assertTrue(self.MANDATORY <= self.included(inv))
        self.assertEqual(inv.saipen["status"], se.STATUS_COMPLETE)

    def test_case05_git_info_exclude_hides_saipen_evidence_survives(self):
        self.write_saipen()
        self.commit()
        info = self.repo / ".git" / "info"
        info.mkdir(parents=True, exist_ok=True)
        (info / "exclude").write_text(".saipen/\n", encoding="utf-8")
        inv = self.inventory()
        self.assertTrue(self.MANDATORY <= self.included(inv))
        self.assertEqual(inv.saipen["status"], se.STATUS_COMPLETE)


class TestPrivateMaterialStaysOut(SaipenEvidenceCase):
    """Cases 6-7 plus the contract's own non-exportable list."""

    def test_case06_ignored_secret_outside_protocol_remains_excluded(self):
        self.write_saipen()
        (self.repo / "api.secret").write_text("SUPERSECRET", encoding="utf-8")
        self.ignore(".saipen/*", "api.secret")
        self.commit()
        inv = self.inventory()
        self.assertNotIn("api.secret", self.included(inv))

    def test_case07_ignored_cache_and_build_dirs_remain_excluded(self):
        self.write_saipen()
        (self.repo / "__pycache__").mkdir()
        (self.repo / "__pycache__" / "x.pyc").write_bytes(b"\x00")
        (self.repo / "build").mkdir()
        (self.repo / "build" / "out.bin").write_bytes(b"\x00" * 16)
        self.ignore(".saipen/*", "__pycache__/", "build/")
        self.commit()
        rels = self.included(self.inventory())
        self.assertFalse([r for r in rels if r.startswith(("__pycache__/", "build/"))])

    def test_non_exportable_protocol_paths_are_never_collected(self):
        self.write_saipen()
        self.ignore(".saipen/*")
        self.commit()
        rels = self.included(self.inventory())
        self.assertNotIn(".saipen/locks/core.lock", rels)
        self.assertNotIn(".saipen/recovery/op.json", rels)
        self.assertNotIn(".saipen/LOCAL_STATE.json", rels)

    def test_generic_configured_exclude_cannot_swallow_declared_evidence(self):
        """`logs` is a DEFAULT exclude; sealed LOG segments are evidence.

        Without the declared-evidence precedence this silently removed the
        segments that make LOG's parent chain resolvable -- and the package
        would still have looked healthy.
        """
        self.write_saipen()
        self.ignore(".saipen/*")
        self.commit()
        rels = self.included(self.inventory(excludes={"logs", "*.log"}))
        self.assertIn(".saipen/logs/LOG-001.md", rels)


class TestCompletenessVerdict(SaipenEvidenceCase):
    """Cases 8-12: the verdict must be earned, and must fail closed."""

    def test_case08_optional_artifact_absent_is_still_complete(self):
        sp = self.write_saipen()
        for leftover in (sp / "extensions",):
            self.assertFalse(leftover.exists())
        self.ignore(".saipen/*")
        self.commit()
        self.assertEqual(self.inventory().saipen["status"], se.STATUS_COMPLETE)

    def test_case09_mandatory_artifact_absent_is_protocol_incomplete(self):
        sp = self.write_saipen()
        (sp / "LOG.md").unlink()
        self.ignore(".saipen/*")
        self.commit()
        verdict = self.inventory().saipen
        self.assertEqual(verdict["status"], se.STATUS_PROTOCOL_INCOMPLETE)
        self.assertIn(".saipen/LOG.md", verdict["mandatory_missing"])
        self.assertFalse(verdict["authoritative_state"])

    def test_case10_mandatory_artifact_unreadable_is_never_silent_success(self):
        sp = self.write_saipen()
        board = sp / "BOARD.md"
        board.unlink()
        board.mkdir()  # a directory where a document must be: not evidence
        self.ignore(".saipen/*")
        self.commit()
        verdict = self.inventory().saipen
        self.assertEqual(verdict["status"], se.STATUS_PROTOCOL_INCOMPLETE)
        self.assertIn(".saipen/BOARD.md", verdict["mandatory_missing"])

    def test_case11_stale_active_intake_cannot_dominate_newer_state(self):
        """The exact LIMISAW failure mode, as a test.

        A package carrying only the stale receipt invites the wrong reading.
        The same package carrying STATE, BOARD, LOG and the archived closure
        cannot.
        """
        sp = self.write_saipen()
        (sp / "LOG.md").write_text(
            "- E-1 start\n- E-328 [T-48] DEC: ticket finished via SAIOPS\n",
            encoding="utf-8",
        )
        self.ignore(".saipen/*")
        self.commit()
        rels = self.included(self.inventory())
        self.assertIn(".saipen/intake/active/SRC-007.md", rels)
        for corrective in (
            ".saipen/STATE.md",
            ".saipen/BOARD.md",
            ".saipen/LOG.md",
            ".saipen/archive/source/SRC-008.md",
            ".saipen/KNOWLEDGE/evidence.md",
        ):
            self.assertIn(corrective, rels)

    def test_case12_archived_disposition_records_are_included(self):
        self.write_saipen()
        self.ignore(".saipen/*")
        self.commit()
        self.assertIn(".saipen/archive/source/SRC-008.md", self.included(self.inventory()))

    def test_operator_always_exclude_wins_but_is_reported_missing(self):
        """An explicit operator exclude still wins -- and is never hidden.

        This is the fail-closed edge: the file legitimately does not travel,
        so the package must stop claiming to represent current state.
        """
        self.write_saipen()
        self.ignore(".saipen/*")
        self.commit()
        inv = self.inventory(always_exclude=[".saipen/LOG.md"])
        self.assertNotIn(".saipen/LOG.md", self.included(inv))
        self.assertEqual(inv.saipen["status"], se.STATUS_PROTOCOL_INCOMPLETE)
        self.assertIn(".saipen/LOG.md", inv.saipen["mandatory_missing"])


class TestContractHandling(SaipenEvidenceCase):
    """Cases 13-14 plus protocol-version negotiation."""

    def test_case13_non_saipen_repository_is_unchanged(self):
        self.commit()
        inv = self.inventory()
        self.assertIsNone(inv.saipen)
        self.assertIn("app.py", self.included(inv))

    def test_case14_lookalike_saipen_dir_triggers_no_recursive_inclusion(self):
        sp = self.repo / ".saipen"
        sp.mkdir()
        (sp / "MANIFEST.json").write_text("this is not json", encoding="utf-8")
        (sp / "huge").mkdir()
        for i in range(5):
            (sp / "huge" / f"f{i}.bin").write_bytes(b"\x00" * 8)
        self.ignore(".saipen/*")
        self.commit()
        inv = self.inventory()
        self.assertEqual(inv.saipen["status"], se.STATUS_MANIFEST_MALFORMED)
        self.assertFalse([r for r in self.included(inv) if r.startswith(".saipen/huge/")])

    def test_manifest_absent_is_explicit_not_silent(self):
        self.write_saipen(manifest=False)
        self.ignore(".saipen/*")
        self.commit()
        verdict = self.inventory().saipen
        self.assertEqual(verdict["status"], se.STATUS_MANIFEST_ABSENT)
        self.assertFalse(verdict["authoritative_state"])
        self.assertIn("saipen audit manifest --write", verdict["detail"])

    def test_newer_contract_version_is_forward_compatible_when_structural(self):
        """MILESTONE K: newer version with present capabilities is not unknown.

        A contract_version beyond the implemented set is not automatically
        unknown if every required capability is structurally present. The
        generator/provenance mismatch is a separate gate-level check.
        """
        sp = self.write_saipen()
        future = dict(CONTRACT, contract_version=se.SUPPORTED_CONTRACT_VERSION + 1)
        (sp / "MANIFEST.json").write_text(json.dumps(future, indent=1), encoding="utf-8")
        self.ignore(".saipen/*")
        self.commit()
        contract = se.read_contract(self.repo)
        self.assertEqual(contract.admission, se.ManifestAdmission.COMPATIBLE_DEGRADED)
        self.assertEqual(contract.contract_version, se.SUPPORTED_CONTRACT_VERSION + 1)
        # The snapshot is authoritative once evidence is present.
        verdict = self.inventory().saipen
        self.assertEqual(verdict["admission"], se.ManifestAdmission.COMPATIBLE_DEGRADED)
        self.assertTrue(verdict["authoritative_state"])

    def test_older_contract_version_is_refused_not_guessed(self):
        """An older-than-implemented version is INCOMPATIBLE_UNSAFE: not a
        forward-compat case, so the consumer must not reinterpret it."""
        sp = self.write_saipen()
        future = dict(CONTRACT, contract_version=0)
        future["generator"] = "saipen-audit-manifest/0"
        (sp / "MANIFEST.json").write_text(json.dumps(future, indent=1), encoding="utf-8")
        self.ignore(".saipen/*")
        self.commit()
        contract = se.read_contract(self.repo)
        self.assertEqual(contract.status, se.STATUS_CONTRACT_UNKNOWN)
        self.assertEqual(contract.admission, se.ManifestAdmission.INCOMPATIBLE_UNSAFE)
        self.assertFalse(contract.mandatory)


class TestBoundsAndSafety(SaipenEvidenceCase):
    """Cases 15-17: containment, determinism, and honest truncation."""

    def test_case15_declared_path_cannot_escape_the_project(self):
        sp = self.write_saipen()
        escaping = dict(CONTRACT)
        escaping["evidence"] = dict(CONTRACT["evidence"])
        escaping["evidence"]["mandatory"] = CONTRACT["evidence"]["mandatory"] + [
            {"path": "../../outside.txt", "kind": "file"},
            {"path": "/etc/passwd", "kind": "file"},
            {"path": "C:/Windows/win.ini", "kind": "file"},
        ]
        (sp / "MANIFEST.json").write_text(json.dumps(escaping), encoding="utf-8")
        (self.root / "outside.txt").write_text("SECRET", encoding="utf-8")
        self.ignore(".saipen/*")
        self.commit()
        contract = se.read_contract(self.repo)
        for declared in contract.mandatory:
            self.assertTrue(declared.startswith(".saipen/"), declared)
        self.assertFalse([r for r in self.included(self.inventory()) if "outside" in r])

    def test_case16_case_collision_is_deterministic(self):
        self.write_saipen()
        self.ignore(".saipen/*")
        self.commit()
        first = sorted(self.included(self.inventory()))
        second = sorted(self.included(self.inventory()))
        self.assertEqual(first, second)

    def test_case17_directory_cap_truncation_is_reported_not_silent(self):
        sp = self.write_saipen()
        capped = json.loads(json.dumps(CONTRACT))
        for rule in capped["evidence"]["conditional"]:
            if rule["path"] == "KNOWLEDGE":
                rule["max_files"] = 1
        (sp / "MANIFEST.json").write_text(json.dumps(capped), encoding="utf-8")
        for i in range(4):
            (sp / "KNOWLEDGE" / f"extra{i}.md").write_text("x\n", encoding="utf-8")
        self.ignore(".saipen/*")
        self.commit()
        verdict = self.inventory().saipen
        self.assertIn(".saipen/KNOWLEDGE", verdict["truncated_dirs"])
        self.assertEqual(verdict["status"], se.STATUS_PROTOCOL_INCOMPLETE)


class TestArchiveProvenance(SaipenEvidenceCase):
    """Cases 18-20: what the produced archive actually says about itself."""

    def _pack(self, stem="Proj", excludes=None, always_exclude=None):
        return pack_single(
            source_path=self.repo,
            output_dir=self.output,
            archive_stem=stem,
            excludes=set(excludes or []),
            delete_old=True,
            include_timestamp=False,
            manifest_meta={"project_name": stem},
            packing=PackingConfig(always_exclude=list(always_exclude or [])),
        )

    def test_case18_generated_logs_excluded_without_breaking_completeness(self):
        self.write_saipen()
        self.ignore(".saipen/*")
        self.commit()
        # Untracked generated output: `*.log` is a default AUDAPACK exclude,
        # and a tracked file would legitimately beat that exclude (T-190), so
        # the fixture has to be the generated case it claims to be.
        (self.repo / "build.log").write_text("noise\n", encoding="utf-8")
        result = self._pack(excludes={"*.log"})
        self.assertTrue(result.success, result.error_message)
        with zipfile.ZipFile(result.output_path) as zf:
            names = set(zf.namelist())
            manifest = json.loads(zf.read(MANIFEST_FILENAME))
        self.assertNotIn("build.log", names)
        self.assertEqual(manifest["saipen_snapshot"]["status"], se.STATUS_COMPLETE)

    def test_case19_archive_manifest_reports_mandatory_evidence_exactly(self):
        self.write_saipen()
        self.ignore(".saipen/*")
        self.commit()
        result = self._pack()
        with zipfile.ZipFile(result.output_path) as zf:
            names = set(zf.namelist())
            snapshot = json.loads(zf.read(MANIFEST_FILENAME))["saipen_snapshot"]
        self.assertEqual(sorted(snapshot["mandatory_included"]), sorted(snapshot["mandatory_declared"]))
        self.assertEqual(snapshot["mandatory_missing"], [])
        self.assertTrue(snapshot["authoritative_state"])
        # The contract travels with the evidence it governs, so the verdict
        # can be re-derived from the archive alone.
        self.assertIn(".saipen/MANIFEST.json", names)
        for declared in snapshot["mandatory_declared"]:
            self.assertIn(declared, names)

    def test_case20_repeated_pack_of_unchanged_tree_is_deterministic(self):
        self.write_saipen()
        self.ignore(".saipen/*")
        self.commit()
        verdicts = []
        for stem in ("A", "B"):
            result = self._pack(stem)
            with zipfile.ZipFile(result.output_path) as zf:
                snapshot = json.loads(zf.read(MANIFEST_FILENAME))["saipen_snapshot"]
            snapshot.pop("manifest_generated_at", None)
            verdicts.append(snapshot)
        self.assertEqual(verdicts[0], verdicts[1])

    def test_incomplete_snapshot_does_not_claim_authority(self):
        """A project missing MANDATORY evidence does not claim authority.

        Missing mandatory evidence is an evidence incompleteness concern
        evaluated by saipen_evidence, NOT manifest staleness. The produced
        archive snapshot truthfully reports PROTOCOL_INCOMPLETE with
        authoritative_state=false and required_evidence_omitted=true.
        """
        sp = self.write_saipen()
        (sp / "STATE.md").unlink()
        self.ignore(".saipen/*")
        self.commit()
        result = self._pack()
        self.assertTrue(result.success, result.error_message)
        with zipfile.ZipFile(result.output_path) as zf:
            snapshot = json.loads(zf.read(MANIFEST_FILENAME))["saipen_snapshot"]
        self.assertFalse(snapshot["authoritative_state"])
        self.assertTrue(snapshot["required_evidence_omitted"])
        self.assertIn(".saipen/STATE.md", snapshot["mandatory_missing"])
        self.assertEqual(snapshot["status"], se.STATUS_PROTOCOL_INCOMPLETE)
        # The verdict layer independently refuses authority for the same tree.
        collection = se.collect_for_inventory(self.repo)
        verdict = se.evaluate(collection, included=set())
        self.assertFalse(verdict["authoritative_state"])
        self.assertTrue(verdict["required_evidence_omitted"])

    def test_non_saipen_archive_manifest_has_no_snapshot_key(self):
        self.commit()
        result = self._pack()
        with zipfile.ZipFile(result.output_path) as zf:
            manifest = json.loads(zf.read(MANIFEST_FILENAME))
        self.assertNotIn("saipen_snapshot", manifest)


class TestConditionalEvidenceInTheFinalVerdict(SaipenEvidenceCase):
    """Cases 21-30: the verdict is decided by the FINAL ARCHIVE, not discovery.

    THE DEFECT THESE PIN
    --------------------
    SAIPEN marks protocol paths conditionally required WHEN PRESENT
    (`.saipen/logs/**` is the canonical example: the sealed segments that make
    the event chain resolvable). AUDAPACK discovered that evidence correctly --
    and then, if a later stage removed one of those files from the package, the
    snapshot still read COMPLETE with ``authoritative_state: true``. The
    verdict was computed from what the collector FOUND, so nothing downstream
    could see what the archive LOST.

    The invariant, in one line: a conditional artifact the contract requires
    BECAUSE IT EXISTS, that does not survive into the archive, cannot leave a
    COMPLETE verdict behind.
    """

    #: The conditional evidence this fixture's contract makes required by
    #: existing: `logs/`, `intake/`, `archive/source/`, `KNOWLEDGE/`.
    CONDITIONAL = {
        ".saipen/logs/LOG-001.md",
        ".saipen/intake/active/SRC-007.md",
        ".saipen/archive/source/SRC-008.md",
        ".saipen/KNOWLEDGE/evidence.md",
    }

    def test_case21_conditional_evidence_present_and_surviving_is_complete(self):
        self.write_saipen()
        self.ignore(".saipen/*")
        self.commit()
        inv = self.inventory()
        self.assertTrue(self.CONDITIONAL <= self.included(inv))
        verdict = inv.saipen
        self.assertEqual(verdict["status"], se.STATUS_COMPLETE)
        self.assertTrue(verdict["authoritative_state"])
        self.assertFalse(verdict["required_evidence_omitted"])
        self.assertEqual(verdict["omitted_required"], [])
        self.assertEqual(verdict["verdict_basis"], "final_archive_content")

    def test_case22_conditional_evidence_absent_is_still_complete(self):
        """The contract makes a PRESENT artifact required; absence is allowed."""
        sp = self.write_saipen()
        for gone in (sp / "logs", sp / "KNOWLEDGE", sp / "archive"):
            shutil.rmtree(gone)
        self.ignore(".saipen/*")
        self.commit()
        collection = se.collect_for_inventory(self.repo)
        self.assertEqual(
            collection.conditional_found, [".saipen/intake/active/SRC-007.md"]
        )
        self.assertNotIn(".saipen/logs/LOG-001.md", collection.paths)
        verdict = self.inventory().saipen
        self.assertEqual(verdict["status"], se.STATUS_COMPLETE)
        self.assertTrue(verdict["authoritative_state"])

    def test_case23_explicit_exclude_of_conditional_evidence_is_not_complete(self):
        """THE reproduced case: discovered, then dropped by an explicit exclude."""
        self.write_saipen()
        self.ignore(".saipen/*")
        self.commit()
        inv = self.inventory(always_exclude=[".saipen/archive/source/SRC-008.md"])
        self.assertNotIn(".saipen/archive/source/SRC-008.md", self.included(inv))
        verdict = inv.saipen
        self.assertEqual(verdict["status"], se.STATUS_PROTOCOL_INCOMPLETE)
        self.assertFalse(verdict["authoritative_state"])
        self.assertTrue(verdict["required_evidence_omitted"])
        omitted = {item["path"]: item for item in verdict["omitted_required"]}
        self.assertEqual(
            omitted[".saipen/archive/source/SRC-008.md"]["tier"], se.TIER_CONDITIONAL
        )
        self.assertEqual(
            omitted[".saipen/archive/source/SRC-008.md"]["reason"],
            "configured_ignore",
        )

    def test_case24_conditional_evidence_removed_by_the_secret_policy_is_reasoned(self):
        """Unsafe evidence is refused AND named, never silently dropped."""
        sp = self.write_saipen()
        (sp / "KNOWLEDGE" / "token.txt").write_text("SECRET\n", encoding="utf-8")
        self.ignore(".saipen/*")
        self.commit()
        inv = self.inventory()
        self.assertNotIn(".saipen/KNOWLEDGE/token.txt", self.included(inv))
        verdict = inv.saipen
        self.assertEqual(verdict["status"], se.STATUS_PROTOCOL_INCOMPLETE)
        self.assertFalse(verdict["authoritative_state"])
        omitted = {item["path"]: item for item in verdict["omitted_required"]}
        entry = omitted[".saipen/KNOWLEDGE/token.txt"]
        self.assertEqual(entry["tier"], se.TIER_CONDITIONAL)
        self.assertEqual(entry["reason"], "secret_policy")

    def test_case25_unreadable_required_evidence_is_non_authoritative(self):
        """Required evidence that cannot be read is never a COMPLETE snapshot.

        Driven at the verdict boundary on purpose: the unreadable case is a
        filesystem condition a test host cannot always produce (a locked or
        permission-denied entry), and what must stay pinned is the verdict's
        behaviour when the collector reports it, not the host's ability to
        fabricate it.
        """
        self.write_saipen()
        self.ignore(".saipen/*")
        self.commit()
        collection = se.collect_for_inventory(self.repo)
        self.assertIn(".saipen/KNOWLEDGE/evidence.md", collection.conditional_found)
        collection.unreadable.append(".saipen/KNOWLEDGE/evidence.md")
        verdict = se.evaluate(collection, included=set(collection.paths))
        self.assertEqual(verdict["status"], se.STATUS_PROTOCOL_INCOMPLETE)
        self.assertFalse(verdict["authoritative_state"])

    def test_case26_unsafe_symlinked_evidence_fails_the_pack_closed(self):
        """A conditional artifact that is an unsafe link refuses the pack.

        It can never be quietly omitted: the archive must not exist at all
        rather than exist without evidence a reviewer believes it has.
        """
        sp = self.write_saipen()
        outside = self.root / "outside-evidence.md"
        outside.write_text("not project evidence\n", encoding="utf-8")
        link = sp / "KNOWLEDGE" / "escape.md"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on this host")
        self.ignore(".saipen/*")
        self.commit()
        with self.assertRaises(SourceInventoryError) as ctx:
            self.inventory()
        self.assertEqual(ctx.exception.code, CODE_SYMLINK_UNSAFE)

    def test_case27_ordinary_excluded_file_does_not_affect_saipen_completeness(self):
        self.write_saipen()
        (self.repo / "debug.log").write_text("noise\n", encoding="utf-8")
        (self.repo / "notes.tmp").write_text("noise\n", encoding="utf-8")
        self.ignore(".saipen/*", "*.log", "*.tmp")
        self.commit()
        inv = self.inventory(excludes={"*.log", "*.tmp"})
        self.assertNotIn("debug.log", self.included(inv))
        self.assertNotIn("notes.tmp", self.included(inv))
        self.assertEqual(inv.saipen["status"], se.STATUS_COMPLETE)
        self.assertEqual(inv.saipen["omitted_required"], [])

    def test_case28_omitted_optional_evidence_does_not_fail_the_snapshot(self):
        """Optional is optional: reported, and authoritative."""
        sp = self.write_saipen()
        (sp / "extensions" / "saiwiki").mkdir(parents=True)
        (sp / "extensions" / "saiwiki" / "STATE.md").write_text("x\n", encoding="utf-8")
        self.ignore(".saipen/*")
        self.commit()
        inv = self.inventory(always_exclude=[".saipen/extensions/saiwiki/STATE.md"])
        verdict = inv.saipen
        self.assertEqual(verdict["status"], se.STATUS_COMPLETE_WITH_OPTIONAL_OMISSIONS)
        self.assertTrue(verdict["authoritative_state"])
        self.assertEqual(verdict["omitted_required"], [])
        self.assertEqual(
            [item["path"] for item in verdict["omitted_optional"]],
            [".saipen/extensions/saiwiki/STATE.md"],
        )
        self.assertEqual(
            verdict["omitted_optional"][0]["tier"], se.TIER_OPTIONAL
        )

    def test_case29_archive_manifest_names_the_omitted_artifact_and_reason(self):
        """Requirement 9: the package itself says what it is missing."""
        self.write_saipen()
        self.ignore(".saipen/*")
        self.commit()
        result = pack_single(
            source_path=self.repo,
            output_dir=self.output,
            archive_stem="Omitted",
            excludes=set(),
            delete_old=True,
            include_timestamp=False,
            manifest_meta={"project_name": "Omitted"},
            packing=PackingConfig(
                always_exclude=[".saipen/archive/source/SRC-008.md"]
            ),
        )
        self.assertTrue(result.success, result.error_message)
        with zipfile.ZipFile(result.output_path) as zf:
            names = set(zf.namelist())
            snapshot = json.loads(zf.read(MANIFEST_FILENAME))["saipen_snapshot"]
        self.assertNotIn(".saipen/archive/source/SRC-008.md", names)
        self.assertEqual(snapshot["status"], se.STATUS_PROTOCOL_INCOMPLETE)
        self.assertFalse(snapshot["authoritative_state"])
        self.assertTrue(snapshot["required_evidence_omitted"])
        self.assertEqual(
            snapshot["omitted_required"],
            [
                {
                    "path": ".saipen/archive/source/SRC-008.md",
                    "tier": se.TIER_CONDITIONAL,
                    "reason": "configured_ignore",
                }
            ],
        )
        # The reconciliation counts real archive membership, not intent.
        self.assertLess(
            snapshot["evidence_files_in_archive"],
            snapshot["evidence_files_collected"],
        )

    def test_case30_optional_truncation_is_reported_not_fatal(self):
        """A cap on OPTIONAL material is a containment bound, not a loss of truth."""
        sp = self.write_saipen()
        capped = json.loads(json.dumps(CONTRACT))
        for rule in capped["evidence"]["optional"]:
            if rule["path"] == "extensions":
                rule["max_files"] = 1
        (sp / "MANIFEST.json").write_text(json.dumps(capped), encoding="utf-8")
        for i in range(4):
            (sp / "extensions" / "sub").mkdir(parents=True, exist_ok=True)
            (sp / "extensions" / "sub" / f"f{i}.md").write_text("x\n", encoding="utf-8")
        self.ignore(".saipen/*")
        self.commit()
        inv = self.inventory()
        verdict = inv.saipen
        self.assertIn(".saipen/extensions", verdict["truncated_optional_dirs"])
        self.assertEqual(verdict["truncated_required_dirs"], [])
        self.assertEqual(verdict["status"], se.STATUS_COMPLETE_WITH_OPTIONAL_OMISSIONS)
        self.assertTrue(verdict["authoritative_state"])

        # And the reverse: the same cap on CONDITIONAL evidence is fatal.
        capped = json.loads(json.dumps(CONTRACT))
        for rule in capped["evidence"]["conditional"]:
            if rule["path"] == "KNOWLEDGE":
                rule["max_files"] = 1
        (sp / "MANIFEST.json").write_text(json.dumps(capped), encoding="utf-8")
        for i in range(4):
            (sp / "KNOWLEDGE" / f"extra{i}.md").write_text("x\n", encoding="utf-8")
        verdict = self.inventory().saipen
        self.assertIn(".saipen/KNOWLEDGE", verdict["truncated_required_dirs"])
        self.assertEqual(verdict["status"], se.STATUS_PROTOCOL_INCOMPLETE)
        self.assertFalse(verdict["authoritative_state"])


class TestCitedEvidence(SaipenEvidenceCase):
    """Cases 31-42 (SRC-054): evidence a closure record CITES must travel.

    THE DEFECT THESE PIN
    --------------------
    Problip's LOG E-048 and its archived SRC-002 coverage cite
    ``.saipen/evidence/PERF-001_WINDOWS_EVIDENCE.md``. The contract never
    declared ``evidence/``, so the collector never discovered the file, so its
    absence could not be counted: the archive read ``COMPLETE`` with
    ``evidence_files_collected == evidence_files_in_archive == 142`` and
    ``required_evidence_omitted: false`` while the cited proof was not in it.
    Equal counts over an incomplete discovery set prove nothing.

    The invariant: a file a closure record cites is required evidence whether
    or not a directory rule found it, and an archive without it is never
    COMPLETE.
    """

    PROOF = b"# PERF closure proof\nsmoke PASS\n"

    def cite(self, sp, contract=None, *, log_line=None, coverage=None):
        (sp / "evidence").mkdir(exist_ok=True)
        (sp / "evidence" / "proof.md").write_bytes(self.PROOF)
        (sp / "LOG.md").write_text(
            "- E-1 start\n"
            + (log_line or "- E-2 RUN: final evidence gate PASS, proof at .saipen/evidence/proof.md\n"),
            encoding="utf-8",
        )
        if coverage is not None:
            (sp / "archive" / "source" / "SRC-002.coverage.json").write_text(
                json.dumps(coverage), encoding="utf-8"
            )
        # The contract is written last, as the protocol writes it after a
        # checkpoint, so the pack gate reads it as current.
        manifest = sp / "MANIFEST.json"
        body = json.dumps(contract, indent=1) if contract is not None else manifest.read_text(encoding="utf-8")
        manifest.write_text(body, encoding="utf-8")

    def _pack(self, stem="Cited", always_exclude=None):
        result = pack_single(
            source_path=self.repo,
            output_dir=self.output,
            archive_stem=stem,
            excludes=set(),
            delete_old=True,
            include_timestamp=False,
            manifest_meta={"project_name": stem},
            packing=PackingConfig(always_exclude=list(always_exclude or [])),
        )
        self.assertTrue(result.success, result.error_message)
        with zipfile.ZipFile(result.output_path) as zf:
            names = set(zf.namelist())
            blobs = {name: zf.read(name) for name in names if name.startswith(".saipen/evidence/")}
            snapshot = json.loads(zf.read(MANIFEST_FILENAME))["saipen_snapshot"]
        return names, blobs, snapshot

    def test_case31_cited_evidence_travels_and_the_snapshot_is_complete(self):
        sp = self.write_saipen()
        self.cite(sp)
        self.ignore(".saipen/*")
        self.commit()
        names, blobs, snapshot = self._pack()
        self.assertEqual(blobs[".saipen/evidence/proof.md"], self.PROOF)
        self.assertEqual(snapshot["status"], se.STATUS_COMPLETE)
        self.assertFalse(snapshot["required_evidence_omitted"])
        citations = snapshot["evidence_citations"]
        self.assertEqual(citations["rules_source"], "contract")
        self.assertEqual(citations["cited_files"], [".saipen/evidence/proof.md"])
        self.assertEqual(citations["cited_missing_on_disk"], [])
        self.assertFalse(citations["truncated"])

    def test_case32_pre_src054_contract_still_packs_cited_evidence(self):
        """The live Problip archive, reproduced: contract predates `evidence/`."""
        sp = self.write_saipen()
        self.cite(
            sp,
            PRE_SRC054_CONTRACT,
            log_line="- E-2 RUN: gate PASS\n",
            coverage={
                "requirements": {
                    "SRC-002:R001": {
                        "disposition": "VERIFIED",
                        "verification": "smoke PASS; transcript .saipen/evidence/proof.md",
                    }
                },
                "schema_version": 1,
            },
        )
        self.ignore(".saipen/*")
        self.commit()
        names, blobs, snapshot = self._pack()
        self.assertIn(".saipen/evidence/proof.md", names)
        self.assertEqual(blobs[".saipen/evidence/proof.md"], self.PROOF)
        self.assertEqual(snapshot["status"], se.STATUS_COMPLETE)
        citations = snapshot["evidence_citations"]
        self.assertEqual(citations["rules_source"], "consumer_default")
        self.assertEqual(
            citations["cited_by"][".saipen/evidence/proof.md"],
            [".saipen/archive/source/SRC-002.coverage.json"],
        )

    def test_case33_undiscovered_cited_evidence_can_never_read_complete(self):
        """SRC-054 TARGET D: cited, omitted from the ZIP -> never COMPLETE."""
        sp = self.write_saipen()
        self.cite(sp, PRE_SRC054_CONTRACT)
        self.ignore(".saipen/*")
        self.commit()
        names, _, snapshot = self._pack(always_exclude=[".saipen/evidence/proof.md"])
        self.assertNotIn(".saipen/evidence/proof.md", names)
        self.assertEqual(snapshot["status"], se.STATUS_PROTOCOL_INCOMPLETE)
        self.assertFalse(snapshot["authoritative_state"])
        self.assertTrue(snapshot["required_evidence_omitted"])
        omitted = {item["path"]: item for item in snapshot["omitted_required"]}
        entry = omitted[".saipen/evidence/proof.md"]
        self.assertEqual(entry["tier"], se.TIER_CITED)
        self.assertEqual(entry["reason"], "configured_ignore")
        self.assertEqual(entry["cited_by"], [".saipen/LOG.md"])
        self.assertLess(snapshot["evidence_files_in_archive"], snapshot["evidence_files_collected"])

    def test_case34_declared_and_cited_evidence_excluded_names_the_citation(self):
        sp = self.write_saipen()
        self.cite(sp, CONTRACT)
        self.ignore(".saipen/*")
        self.commit()
        _, _, snapshot = self._pack(always_exclude=[".saipen/evidence/proof.md"])
        self.assertEqual(snapshot["status"], se.STATUS_PROTOCOL_INCOMPLETE)
        omitted = [item for item in snapshot["omitted_required"] if item["path"] == ".saipen/evidence/proof.md"]
        self.assertEqual(len(omitted), 1, "one omission per file, not one per rule")
        self.assertEqual(omitted[0]["cited_by"], [".saipen/LOG.md"])

    def test_case35_cited_evidence_absent_on_disk_is_not_complete(self):
        sp = self.write_saipen()
        self.cite(sp)
        (sp / "evidence" / "proof.md").unlink()
        self.ignore(".saipen/*")
        self.commit()
        verdict = self.inventory().saipen
        self.assertEqual(verdict["status"], se.STATUS_PROTOCOL_INCOMPLETE)
        self.assertTrue(verdict["required_evidence_omitted"])
        omitted = {item["path"]: item for item in verdict["omitted_required"]}
        self.assertEqual(omitted[".saipen/evidence/proof.md"]["reason"], se.REASON_EVIDENCE_ABSENT)
        self.assertEqual(verdict["evidence_citations"]["cited_missing_on_disk"], [".saipen/evidence/proof.md"])

    def test_case36_project_without_evidence_packs_unchanged(self):
        """SRC-054 TARGET E: no evidence directory, no citation, no new obligation."""
        self.write_saipen()
        self.ignore(".saipen/*")
        self.commit()
        names, blobs, snapshot = self._pack()
        self.assertEqual(blobs, {})
        self.assertEqual(snapshot["status"], se.STATUS_COMPLETE)
        self.assertEqual(snapshot["omitted_required"], [])
        self.assertEqual(snapshot["evidence_citations"]["cited_files"], [])

    def test_case37_foreign_hypothetical_and_escaping_paths_are_not_citations(self):
        """A citation is the project-relative token inside a closure record.

        Another project's absolute path, a handoff body describing a fixture,
        a contract clause quoting the user and a `..` escape all mention the
        surface without citing this project's evidence.
        """
        sp = self.write_saipen()
        (sp / "LOG.md").write_text(
            "- E-1 start\n"
            "- E-2 RUN: compared V:/work/_PROBLIP/.saipen/evidence/other.md and "
            r"C:\x\proj\.saipen\evidence\win.md" "\n"
            "- E-3 RUN: escape .saipen/evidence/../STATE.md\n",
            encoding="utf-8",
        )
        (sp / "intake" / "active" / "SRC-007.md").write_text(
            "create project with `.saipen/evidence/hypothetical.md`\n", encoding="utf-8"
        )
        (sp / "intake" / "contracts").mkdir(parents=True)
        (sp / "intake" / "contracts" / "SRC-007.json").write_text(
            json.dumps({"clauses": {"SRC-007:R001": {"text": "reference .saipen/evidence/clause.md"}}}),
            encoding="utf-8",
        )
        self.ignore(".saipen/*")
        self.commit()
        verdict = self.inventory().saipen
        self.assertEqual(verdict["status"], se.STATUS_COMPLETE)
        self.assertEqual(verdict["evidence_citations"]["cited_files"], [])
        self.assertEqual(verdict["evidence_citations"]["cited_missing_on_disk"], [])

    def test_case38_citation_spellings_normalise(self):
        """Backslashes, a sentence period, `./` and backtick quoting name one file."""
        sp = self.write_saipen()
        (sp / "evidence" / "run-1").mkdir(parents=True)
        (sp / "evidence" / "run-1" / "quoted.md").write_text("q\n", encoding="utf-8")
        (sp / "evidence" / "win.md").write_text("w\n", encoding="utf-8")
        (sp / "evidence" / "json.md").write_text("j\n", encoding="utf-8")
        (sp / "LOG.md").write_text(
            "- E-1 start\n"
            "- E-2 RUN: kept .saipen\\evidence\\win.md.\n"
            "- E-3 RUN: kept `./.saipen/evidence/run-1/quoted.md`, and (.saipen/evidence/win.md)\n",
            encoding="utf-8",
        )
        (sp / "intake" / "coverage").mkdir(parents=True)
        (sp / "intake" / "coverage" / "SRC-007.json").write_text(
            json.dumps({"requirements": {"R": {"verification": ".saipen\\evidence\\json.md"}}}),
            encoding="utf-8",
        )
        self.ignore(".saipen/*")
        self.commit()
        inv = self.inventory()
        cited = inv.saipen["evidence_citations"]["cited_files"]
        self.assertEqual(
            cited,
            [
                ".saipen/evidence/json.md",
                ".saipen/evidence/run-1/quoted.md",
                ".saipen/evidence/win.md",
            ],
        )
        self.assertEqual(
            inv.saipen["evidence_citations"]["cited_by"][".saipen/evidence/win.md"],
            [".saipen/LOG.md"],
        )
        self.assertTrue(set(cited) <= self.included(inv))
        self.assertEqual(inv.saipen["status"], se.STATUS_COMPLETE)

    def test_case39_cited_directory_travels_under_a_pre_src054_contract(self):
        sp = self.write_saipen()
        (sp / "MANIFEST.json").write_text(json.dumps(PRE_SRC054_CONTRACT), encoding="utf-8")
        run = sp / "evidence" / "T-9-run"
        run.mkdir(parents=True)
        for name in ("a.json", "b.log"):
            (run / name).write_text(name, encoding="utf-8")
        (sp / "LOG.md").write_text(
            "- E-1 start\n- E-2 RUN: transcripts in .saipen/evidence/T-9-run/\n", encoding="utf-8"
        )
        self.ignore(".saipen/*")
        self.commit()
        inv = self.inventory()
        rels = self.included(inv)
        self.assertIn(".saipen/evidence/T-9-run/a.json", rels)
        self.assertIn(".saipen/evidence/T-9-run/b.log", rels)
        self.assertEqual(inv.saipen["status"], se.STATUS_COMPLETE)
        self.assertEqual(inv.saipen["evidence_citations"]["cited_dirs"], [".saipen/evidence/T-9-run"])

    def test_case40_citation_discovery_is_bounded_and_fails_closed(self):
        """A discovery that stopped early cannot certify what it did not read."""
        sp = self.write_saipen()
        self.cite(sp)
        (sp / "evidence" / "second.md").write_text("2\n", encoding="utf-8")
        with open(sp / "LOG.md", "a", encoding="utf-8") as handle:
            handle.write("- E-3 RUN: also .saipen/evidence/second.md\n")
        bounded = json.loads(json.dumps(CONTRACT))
        bounded["references"]["max_references"] = 1
        (sp / "MANIFEST.json").write_text(json.dumps(bounded), encoding="utf-8")
        self.ignore(".saipen/*")
        self.commit()
        verdict = self.inventory().saipen
        self.assertTrue(verdict["evidence_citations"]["truncated"])
        self.assertEqual(verdict["status"], se.STATUS_PROTOCOL_INCOMPLETE)

        bounded["references"]["max_references"] = 20000
        bounded["references"]["max_carrier_bytes"] = 16
        (sp / "MANIFEST.json").write_text(json.dumps(bounded), encoding="utf-8")
        verdict = self.inventory().saipen
        self.assertTrue(verdict["evidence_citations"]["truncated"])
        self.assertEqual(verdict["status"], se.STATUS_PROTOCOL_INCOMPLETE)

    def test_case41_malformed_citation_rules_are_refused(self):
        sp = self.write_saipen()
        broken = json.loads(json.dumps(CONTRACT))
        broken["references"]["carriers"] = "LOG.md"
        (sp / "MANIFEST.json").write_text(json.dumps(broken), encoding="utf-8")
        self.ignore(".saipen/*")
        self.commit()
        self.assertEqual(se.read_contract(self.repo).status, se.STATUS_MANIFEST_MALFORMED)

        broken["references"] = {**CONTRACT["references"], "surfaces": ["../outside"]}
        (sp / "MANIFEST.json").write_text(json.dumps(broken), encoding="utf-8")
        self.assertEqual(se.read_contract(self.repo).status, se.STATUS_MANIFEST_MALFORMED)

    def test_case43_citation_case_resolves_to_the_file_on_disk(self):
        """A citation spelled in another case names the file, not a second candidate.

        Windows resolves `PROOF.md` to `proof.md`; a candidate under the
        citation's own spelling next to the directory rule's one is a case
        collision, and the inventory refuses the whole pack over it.
        """
        sp = self.write_saipen()
        self.cite(sp, CONTRACT, log_line="- E-2 RUN: proof at .saipen/evidence/PROOF.md\n")
        self.ignore(".saipen/*")
        self.commit()
        names, blobs, snapshot = self._pack()
        self.assertEqual(
            [name for name in names if name.lower() == ".saipen/evidence/proof.md"],
            [".saipen/evidence/proof.md"],
        )
        self.assertEqual(blobs[".saipen/evidence/proof.md"], self.PROOF)
        self.assertEqual(snapshot["evidence_citations"]["cited_files"], [".saipen/evidence/proof.md"])
        self.assertEqual(snapshot["status"], se.STATUS_COMPLETE)

    def test_case42_repeated_export_cycles_keep_cited_evidence(self):
        """Two export cycles with a protocol-side rewrite of the contract between them."""
        sp = self.write_saipen()
        self.cite(sp, CONTRACT)
        self.ignore(".saipen/*")
        self.commit()
        _, first_blobs, first = self._pack("CycleA")
        # An older installed protocol regenerates the pre-SRC-054 contract.
        (sp / "MANIFEST.json").write_text(json.dumps(PRE_SRC054_CONTRACT), encoding="utf-8")
        _, second_blobs, second = self._pack("CycleB")
        for blobs, snapshot in ((first_blobs, first), (second_blobs, second)):
            self.assertEqual(blobs[".saipen/evidence/proof.md"], self.PROOF)
            self.assertEqual(snapshot["status"], se.STATUS_COMPLETE)
            self.assertFalse(snapshot["required_evidence_omitted"])

    def test_case44_a_glob_in_prose_is_not_a_citation(self):
        """`evidence/RAPORT-*` names a family, not a file.

        SAIPEN's LOG E-7055 describes a mailbox root as `.saipen/evidence/
        RAPORT-* (4 bodies)`. The literal prefix before the wildcard is not a
        path anyone could ever hold; requiring it degraded the operator's real
        SAIPEN archive. The family's actual members are still collected by the
        declared `evidence/` directory rule.
        """
        sp = self.write_saipen()
        self.cite(
            sp,
            log_line="- E-2 RUN: mailbox roots .saipen/evidence/RAPORT-* (4 bodies)\n",
        )
        self.ignore(".saipen/*")
        self.commit()
        verdict = self.inventory().saipen
        citations = verdict["evidence_citations"]
        self.assertEqual(citations["cited_files"], [])
        self.assertEqual(citations["cited_missing_on_disk"], [])
        self.assertEqual(citations["cited_ignored"], [])
        self.assertEqual(verdict["status"], se.STATUS_COMPLETE)
        self.assertFalse(verdict["required_evidence_omitted"])

    def test_case45_a_cleaned_up_extensionless_citation_requires_nothing(self):
        """A removed empty directory must not poison every later archive.

        E-7041 records `removed empty-directory residue .saipen/evidence/
        T-1354-1362-polygon-20260916 (0 files, 0 bytes)`. While the directory
        existed it required nothing -- directory citations add only the files
        they actually hold -- and after the canonical cleanup removed it, an
        extension-less token keeps requiring nothing, because it cannot be
        told apart from a directory name. A file-shaped absent citation
        (`proof.md`, case 35) is still a required omission.
        """
        sp = self.write_saipen()
        self.cite(
            sp,
            log_line=(
                "- E-2 RUN: removed empty-directory residue "
                ".saipen/evidence/T-1354-1362-polygon-20260916 (0 files, 0 bytes)\n"
            ),
        )
        self.ignore(".saipen/*")
        self.commit()
        verdict = self.inventory().saipen
        citations = verdict["evidence_citations"]
        self.assertEqual(citations["cited_missing_on_disk"], [])
        self.assertEqual(
            citations["cited_ignored"],
            [".saipen/evidence/T-1354-1362-polygon-20260916"],
        )
        self.assertEqual(verdict["status"], se.STATUS_COMPLETE)
        self.assertFalse(verdict["required_evidence_omitted"])


class TestContractV2(SaipenEvidenceCase):
    """TARGET I: the CURRENT contract packs, proves, and never overclaims.

    Every case below runs against the canonical document the real generator
    wrote (tests/fixtures/saipen/MANIFEST.v2.json), so this class tests the
    published contract rather than a hand-typed approximation of it. The red
    it exists for is exact: PACK of a current SAIPEN project failed with
    PROTOCOL_CONTRACT_UNKNOWN because the manifest declared contract_version 2
    while the consumer implemented 1.
    """

    def _pack(self, stem="Proj", excludes=None, always_exclude=None):
        return pack_single(
            source_path=self.repo,
            output_dir=self.output,
            archive_stem=stem,
            excludes=set(excludes or []),
            delete_old=True,
            include_timestamp=False,
            manifest_meta={"project_name": stem},
            packing=PackingConfig(always_exclude=list(always_exclude or [])),
        )

    def _reseal(self, contract=None):
        """Rewrite the manifest LAST, the way regeneration would.

        ``saipen_manifest_gate.prepare`` regenerates a manifest whose mandatory
        evidence is newer than the document itself, and this fixture has no
        reachable protocol CLI -- exactly the staleness rule a real project
        obeys. Tests that mutate STATE/BOARD/LOG therefore re-seal the
        document before packing instead of pretending the rule does not apply.
        """
        (self.repo / ".saipen" / "MANIFEST.json").write_text(
            json.dumps(CONTRACT_V2 if contract is None else contract, indent=1),
            encoding="utf-8",
        )

    # -- item 2: the current contract is read, not refused ----------------

    def test_case31_canonical_v2_fixture_is_accepted(self):
        self.write_saipen(contract=CONTRACT_V2)
        contract = se.read_contract(self.repo)
        self.assertEqual(contract.status, se.STATUS_COMPLETE)
        self.assertEqual(contract.contract_version, 2)
        self.assertEqual(contract.generator, "saipen-audit-manifest/2")
        self.assertEqual(contract.compatibility_policy, "refuse")
        self.assertEqual(contract.citations.source, se.RULES_FROM_CONTRACT)
        self.assertEqual(se.SUPPORTED_CONTRACT_VERSIONS, (1, 2))

    # -- items 3-4: v2 required material participates ---------------------

    def test_case32_v2_mandatory_and_conditional_evidence_is_collected(self):
        sp = self.write_saipen(contract=CONTRACT_V2)
        (sp / "audit").mkdir(exist_ok=True)
        (sp / "audit" / "10.md").write_text("audit layer\n", encoding="utf-8")
        self.ignore(".saipen/*")
        self.commit()
        collection = se.collect_for_inventory(self.repo)
        self.assertEqual(
            sorted(collection.mandatory_found),
            [
                ".saipen/BOARD.md",
                ".saipen/IDENTITY.md",
                ".saipen/LOG.md",
                ".saipen/STATE.md",
            ],
        )
        self.assertIn(".saipen/KNOWLEDGE/evidence.md", collection.conditional_found)
        self.assertIn(".saipen/audit/10.md", collection.conditional_found)
        verdict = self.inventory().saipen
        self.assertEqual(verdict["status"], se.STATUS_COMPLETE)
        self.assertTrue(verdict["authoritative_state"])
        self.assertEqual(verdict["contract_version"], 2)
        self.assertEqual(verdict["omitted_required"], [])

    def test_case33_v2_required_closure_is_honored_as_declared(self):
        """`required` is a requirement declaration, not decoration.

        A document that names a path in `required` while omitting it from
        `evidence.mandatory` still requires it, because either list may only
        ADD. Read as a union so a partially-declared document cannot drop a
        document it names.
        """
        document = json.loads(json.dumps(CONTRACT_V2))
        document["required"].append("extra/receipt.md")
        sp = self.write_saipen(contract=document)
        (sp / "extra").mkdir()
        (sp / "extra" / "receipt.md").write_text("receipt\n", encoding="utf-8")
        contract = se.read_contract(self.repo)
        self.assertIn(".saipen/extra/receipt.md", contract.required)
        self.assertIn(".saipen/extra/receipt.md", contract.mandatory)
        self.assertIn(".saipen/extra/receipt.md", self.included(self.inventory()))

    # -- item 5: optional absence stays honest ----------------------------

    def test_case34_v2_optional_omission_is_reported_and_authoritative(self):
        sp = self.write_saipen(contract=CONTRACT_V2)
        (sp / "extensions" / "saiwiki").mkdir(parents=True)
        (sp / "extensions" / "saiwiki" / "STATE.md").write_text("x\n", encoding="utf-8")
        self.ignore(".saipen/*")
        self.commit()
        verdict = self.inventory(
            always_exclude=[".saipen/extensions/saiwiki/STATE.md"]
        ).saipen
        self.assertEqual(verdict["status"], se.STATUS_COMPLETE_WITH_OPTIONAL_OMISSIONS)
        self.assertTrue(verdict["authoritative_state"])
        self.assertEqual(verdict["omitted_required"], [])
        self.assertEqual(
            [item["path"] for item in verdict["omitted_optional"]],
            [".saipen/extensions/saiwiki/STATE.md"],
        )

    # -- item 6: v2 non-exportable surfaces never leak --------------------

    def test_case35_v2_non_exportable_surface_never_leaks(self):
        sp = self.write_saipen(contract=CONTRACT_V2)
        (sp / "quarantine").mkdir(exist_ok=True)
        (sp / "quarantine" / "blocked.md").write_text("held\n", encoding="utf-8")
        self.ignore(".saipen/*")
        self.commit()
        contract = se.read_contract(self.repo)
        self.assertIn(".saipen/quarantine", contract.non_exportable)
        collection = se.collect_for_inventory(self.repo)
        for banned in (
            ".saipen/quarantine/blocked.md",
            ".saipen/locks/core.lock",
            ".saipen/recovery/op.json",
            ".saipen/LOCAL_STATE.json",
        ):
            self.assertNotIn(banned, collection.paths)
            self.assertNotIn(banned, self.included(self.inventory()))
        result = self._pack()
        self.assertTrue(result.success, result.error_message)
        with zipfile.ZipFile(result.output_path) as zf:
            names = set(zf.namelist())
        self.assertNotIn(".saipen/quarantine/blocked.md", names)
        self.assertNotIn(".saipen/LOCAL_STATE.json", names)

    def test_case36_v2_baseline_exclusion_survives_a_drifted_document(self):
        """A v2 document that drops `quarantine/` still cannot export it.

        The baseline is version knowledge, not a courtesy to the document: a
        drift or a hand-edit inside a v2 manifest must not be able to widen
        what the version bans.
        """
        document = json.loads(json.dumps(CONTRACT_V2))
        document["evidence"]["non_exportable"] = [
            rel for rel in document["evidence"]["non_exportable"] if rel != "quarantine/"
        ]
        self.assertNotIn("quarantine/", document["evidence"]["non_exportable"])
        sp = self.write_saipen(contract=document)
        (sp / "quarantine").mkdir(exist_ok=True)
        (sp / "quarantine" / "blocked.md").write_text("held\n", encoding="utf-8")
        contract = se.read_contract(self.repo)
        self.assertEqual(contract.status, se.STATUS_COMPLETE)
        self.assertIn(".saipen/quarantine", contract.non_exportable)
        collection = se.collect_for_inventory(self.repo)
        self.assertNotIn(".saipen/quarantine/blocked.md", collection.paths)

    # -- item 7: citations are honored ------------------------------------

    def test_case37_v2_citations_are_resolved_and_required(self):
        sp = self.write_saipen(contract=CONTRACT_V2)
        (sp / "evidence").mkdir(exist_ok=True)
        (sp / "evidence" / "proof.md").write_text("cited proof\n", encoding="utf-8")
        (sp / "LOG.md").write_text(
            "- E-2 closed; proof at .saipen/evidence/proof.md\n", encoding="utf-8"
        )
        self._reseal()
        self.ignore(".saipen/*")
        self.commit()
        collection = se.collect_for_inventory(self.repo)
        self.assertIn(".saipen/evidence/proof.md", collection.cited_files)
        self.assertIn(".saipen/evidence/proof.md", collection.cited_required)
        self.assertEqual(collection.cited_by[".saipen/evidence/proof.md"], [".saipen/LOG.md"])
        verdict = self.inventory().saipen
        self.assertFalse(verdict["required_evidence_omitted"])
        self.assertEqual(verdict["evidence_citations"]["rules_source"], se.RULES_FROM_CONTRACT)

    def test_case38_v2_citation_of_absent_proof_is_non_authoritative(self):
        sp = self.write_saipen(contract=CONTRACT_V2)
        (sp / "LOG.md").write_text(
            "- E-2 closed; proof at .saipen/evidence/never-written.md\n",
            encoding="utf-8",
        )
        self._reseal()
        self.ignore(".saipen/*")
        self.commit()
        verdict = self.inventory().saipen
        self.assertEqual(verdict["status"], se.STATUS_PROTOCOL_INCOMPLETE)
        self.assertFalse(verdict["authoritative_state"])
        omitted = {item["path"] for item in verdict["omitted_required"]}
        self.assertIn(".saipen/evidence/never-written.md", omitted)

    # -- items 8-9: the archive verdict -----------------------------------

    def test_case39_v2_archive_is_authoritative(self):
        self.write_saipen(contract=CONTRACT_V2)
        self.ignore(".saipen/*")
        self.commit()
        result = self._pack()
        self.assertTrue(result.success, result.error_message)
        with zipfile.ZipFile(result.output_path) as zf:
            names = set(zf.namelist())
            snapshot = json.loads(zf.read(MANIFEST_FILENAME))["saipen_snapshot"]
        self.assertEqual(snapshot["status"], se.STATUS_COMPLETE)
        self.assertTrue(snapshot["authoritative_state"])
        self.assertEqual(snapshot["contract_version"], 2)
        self.assertEqual(
            sorted(snapshot["mandatory_included"]), sorted(snapshot["mandatory_declared"])
        )
        # The contract travels with the evidence it governs.
        self.assertIn(".saipen/MANIFEST.json", names)

    def test_case40_v2_required_omission_makes_the_archive_non_authoritative(self):
        self.write_saipen(contract=CONTRACT_V2)
        self.ignore(".saipen/*")
        self.commit()
        result = self._pack(always_exclude=[".saipen/LOG.md"])
        self.assertTrue(result.success, result.error_message)
        with zipfile.ZipFile(result.output_path) as zf:
            names = set(zf.namelist())
            snapshot = json.loads(zf.read(MANIFEST_FILENAME))["saipen_snapshot"]
        self.assertNotIn(".saipen/LOG.md", names)
        self.assertEqual(snapshot["status"], se.STATUS_PROTOCOL_INCOMPLETE)
        self.assertFalse(snapshot["authoritative_state"])
        omitted = {item["path"] for item in snapshot["omitted_required"]}
        self.assertIn(".saipen/LOG.md", omitted)

    # -- items 10-11: a newer version is forward-compatible if capabilities match --

    def test_case41_v3_admits_as_compatible_degraded(self):
        """MILESTONE K: v3 with additive metadata.

        A v3 manifest declaring contract_version 3 is newer than implemented (v2)
        but carries all required capabilities structurally; it is admitted in
        COMPATIBLE_DEGRADED mode and read through the v2 parser. Unknown
        additive fields (nested_instance_files, non_exportable_filenames,
        non_exportable_segments, non_exportable_suffixes, precedence) are
        preserved, not rewritten.
        """
        future = json.loads(json.dumps(CONTRACT_V3))
        self.write_saipen(contract=future)
        contract = se.read_contract(self.repo)
        self.assertEqual(contract.status, se.STATUS_COMPLETE)
        self.assertEqual(contract.admission, se.ManifestAdmission.COMPATIBLE_DEGRADED)
        self.assertEqual(contract.contract_version, 3)
        # v3 reads through v2's rules since v3 is compatible.
        self.assertTrue(contract.mandatory)  # parsed, not empty
        self.assertTrue(contract.required)
        self.assertTrue(contract.citations is not None)
        # The v2 baseline quarantine/ exclusion carries forward.
        self.assertIn(".saipen/quarantine", contract.non_exportable)
        verdict = self.inventory().saipen
        self.assertEqual(verdict["status"], se.STATUS_COMPATIBLE_DEGRADED)
        self.assertEqual(verdict["admission"], se.ManifestAdmission.COMPATIBLE_DEGRADED)
        self.assertTrue(verdict["authoritative_state"])

    def test_case41b_v3_with_reshaped_exclusion_is_incompatible_unsafe(self):
        """Case 4: reshaped security semantics cause hard-block."""
        future = json.loads(json.dumps(CONTRACT_V3))
        future["evidence"]["non_exportable"] = [
            {"path": "locks", "kind": "dir"},
        ]
        self.write_saipen(contract=future)
        contract = se.read_contract(self.repo)
        self.assertEqual(contract.status, se.STATUS_CONTRACT_UNKNOWN)
        self.assertEqual(contract.admission, se.ManifestAdmission.INCOMPATIBLE_UNSAFE)
        self.assertIn("credential_protection_rules_understood", contract.admission_missing)

    def test_case42_incompatible_unsafe_detail_names_the_missing_capability(self):
        """MILESTONE K: hard-block reports the exact missing capability.

        The refusal must not prescribe a regeneration, and must name the
        specific capability this consumer cannot reconstruct.
        """
        # A v3 that reshapes an exclusion rule is INCOMPATIBLE_UNSAFE.
        future = json.loads(json.dumps(CONTRACT_V3))
        future["evidence"]["non_exportable"] = [
            {"path": "locks", "kind": "dir"},
        ]
        admission, missing = se.check_capabilities(future)
        self.assertEqual(admission, se.ManifestAdmission.INCOMPATIBLE_UNSAFE)
        self.assertIn("credential_protection_rules_understood", missing)
        detail = se.check_capabilities_detail(3, admission, missing)
        self.assertIn("credential_protection_rules_understood", detail)
        self.assertIn("INCOMPATIBLE_UNSAFE", detail)
        self.assertNotIn("audit manifest --write", detail)
        # An older-than-implemented version is reported honestly as well.
        older = se.contract_unknown_detail(0)
        self.assertNotIn("newer than", older)
        self.assertIn("refuses to reinterpret", older)

    # -- hardening: policy and shape --------------------------------------

    def test_case43_unimplemented_compatibility_policy_fails_closed(self):
        document = json.loads(json.dumps(CONTRACT_V2))
        document["compatibility"]["unknown_contract_version"] = "coerce"
        self.write_saipen(contract=document)
        contract = se.read_contract(self.repo)
        self.assertEqual(contract.status, se.STATUS_MANIFEST_MALFORMED)
        self.assertIn("not a policy this consumer implements", contract.detail)

    def test_case44_malformed_required_block_fails_closed(self):
        document = json.loads(json.dumps(CONTRACT_V2))
        document["required"] = {"STATE.md": True}
        self.write_saipen(contract=document)
        contract = se.read_contract(self.repo)
        self.assertEqual(contract.status, se.STATUS_MANIFEST_MALFORMED)
        self.assertEqual(contract.detail, "manifest required block is not a list")


class TestNonExportableAlwaysExcluded(SaipenEvidenceCase):
    """TARGET E/J: a contract ban is not a discretionary exclude.

    The inventory applied the contract's ban list only to UNTRACKED entries,
    so a project that happened to COMMIT `.saipen/locks/**` or
    `.saipen/recovery/**` shipped its private runtime state in a published
    archive: `git ls-files` enumerates a committed lock file exactly like any
    other tracked file, and the ban loop skipped it for that reason alone.
    Tracked material is the ordinary case in a project that does not ignore
    its memory root, which is what makes the hole worth a regression.
    """

    def _pack(self, stem="Proj"):
        return pack_single(
            source_path=self.repo,
            output_dir=self.output,
            archive_stem=stem,
            excludes=set(),
            delete_old=True,
            include_timestamp=False,
            manifest_meta={"project_name": stem},
            packing=PackingConfig(),
        )

    BANNED = (
        ".saipen/locks/core.lock",
        ".saipen/recovery/op.json",
        ".saipen/LOCAL_STATE.json",
        ".saipen/quarantine/blocked.md",
    )

    def test_case48_tracked_non_exportable_material_is_never_packed(self):
        sp = self.write_saipen(contract=CONTRACT_V2)
        (sp / "quarantine").mkdir(exist_ok=True)
        (sp / "quarantine" / "blocked.md").write_text("held\n", encoding="utf-8")
        # Deliberately NOT ignored: these files are committed, which is the
        # case the untracked-only guard let through.
        self.commit()
        tracked = subprocess.run(
            ["git", "-C", str(self.repo), "ls-files", ".saipen/locks", ".saipen/recovery"],
            capture_output=True,
            text=True,
        ).stdout
        self.assertIn(".saipen/locks/core.lock", tracked, "fixture must be tracked")

        inv = self.inventory()
        self.assertNotIn(".saipen/locks/core.lock", self.included(inv))
        excluded = {e.rel: e for e in inv.excluded_entries()}
        for banned in self.BANNED:
            self.assertIn(banned, excluded)
            self.assertEqual(
                excluded[banned].reason, se.REASON_SAIPEN_NON_EXPORTABLE, banned
            )
        result = self._pack()
        self.assertTrue(result.success, result.error_message)
        with zipfile.ZipFile(result.output_path) as zf:
            names = set(zf.namelist())
        for banned in self.BANNED:
            self.assertNotIn(banned, names)
        # The ban excludes private state without costing the snapshot its
        # authority: these surfaces are not evidence in any tier.
        snapshot = json.loads(zipfile.ZipFile(result.output_path).read(MANIFEST_FILENAME))[
            "saipen_snapshot"
        ]
        self.assertEqual(snapshot["status"], se.STATUS_COMPLETE)
        self.assertTrue(snapshot["authoritative_state"])

    def test_case49_tracked_non_exportable_ban_holds_for_v1_too(self):
        """The ban is version knowledge, and v1 declared the same surfaces."""
        self.write_saipen(contract=CONTRACT_V1_CANONICAL)
        self.commit()
        inv = self.inventory()
        for banned in (
            ".saipen/locks/core.lock",
            ".saipen/recovery/op.json",
            ".saipen/LOCAL_STATE.json",
        ):
            self.assertNotIn(banned, self.included(inv))
        result = self._pack()
        self.assertTrue(result.success, result.error_message)
        with zipfile.ZipFile(result.output_path) as zf:
            names = set(zf.namelist())
        self.assertNotIn(".saipen/locks/core.lock", names)
        self.assertNotIn(".saipen/LOCAL_STATE.json", names)


class TestMemoryRootIsContractAuthoritative(SaipenEvidenceCase):
    """CORE-001: the memory root is ALLOWLISTED by the contract, not by Git.

    The contract was applied to Git-enumerated files as a DENY list: whatever
    `export_decision` did not ban survived, even when the contract had never
    declared the file. An undeclared transient/debug file that Git happened to
    enumerate therefore bypassed the bounded collector and became ordinary
    archive payload. Measured on this very repository: 278
    `.saipen/scratch_*` files, 4,547,574 bytes, shipped as untracked payload.

    The repair inverts the authority: beneath `contract.memory_root` only what
    the collector declared is exportable, wherever the file came from.
    """

    UNDECLARED = (
        ".saipen/scratch_diag2.txt",
        ".saipen/scratch_rawlog.txt",
        ".saipen/random-runtime.json",
    )

    def _pack(self, stem="Proj"):
        return pack_single(
            source_path=self.repo,
            output_dir=self.output,
            archive_stem=stem,
            excludes=set(),
            delete_old=True,
            include_timestamp=False,
            manifest_meta={"project_name": stem},
            packing=PackingConfig(),
        )

    def _write_undeclared(self, sp):
        for rel in self.UNDECLARED:
            target = self.repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("private working state\n", encoding="utf-8")

    def _assert_excluded(self):
        inv = self.inventory()
        included = self.included(inv)
        excluded = {e.rel: e for e in inv.excluded_entries()}
        for rel in self.UNDECLARED:
            self.assertNotIn(rel, included, rel)
            self.assertIn(rel, excluded, rel)
            self.assertEqual(excluded[rel].reason, se.REASON_SAIPEN_UNDECLARED, rel)
        return inv

    def test_untracked_undeclared_memory_stays_out_of_inventory_and_zip(self):
        sp = self.write_saipen()
        self._write_undeclared(sp)

        self._assert_excluded()

        result = self._pack()
        self.assertTrue(result.success, result.error_message)
        with zipfile.ZipFile(result.output_path) as zf:
            names = set(zf.namelist())
        for rel in self.UNDECLARED:
            self.assertNotIn(rel, names, rel)

    def test_tracked_undeclared_memory_stays_out_inventory_and_zip(self):
        """Git tracking is not publication authority (the defect, verbatim)."""
        sp = self.write_saipen()
        self._write_undeclared(sp)
        self.commit()
        tracked = subprocess.run(
            ["git", "-C", str(self.repo), "ls-files", ".saipen"],
            capture_output=True,
            text=True,
        ).stdout
        self.assertIn(".saipen/scratch_diag2.txt", tracked, "fixture must be tracked")

        self._assert_excluded()

        result = self._pack()
        self.assertTrue(result.success, result.error_message)
        with zipfile.ZipFile(result.output_path) as zf:
            names = set(zf.namelist())
        for rel in self.UNDECLARED:
            self.assertNotIn(rel, names, rel)

    def test_declared_memory_survives_and_verdict_stays_authoritative(self):
        """Control: the allowlist must not cost the snapshot its authority."""
        contract = json.loads(json.dumps(CONTRACT))
        contract["evidence"]["optional"].append(
            {"path": "kitchen", "kind": "dir", "recursive": True, "max_files": 100}
        )
        sp = self.write_saipen(contract=contract)
        self._write_undeclared(sp)
        (sp / "kitchen").mkdir(exist_ok=True)
        (sp / "kitchen" / "probe.md").write_text("declared\n", encoding="utf-8")

        inv = self.inventory()
        included = self.included(inv)
        for declared in (
            ".saipen/STATE.md",
            ".saipen/BOARD.md",
            ".saipen/LOG.md",
            ".saipen/IDENTITY.md",
            ".saipen/MANIFEST.json",
            ".saipen/logs/LOG-001.md",
            ".saipen/intake/active/SRC-007.md",
            ".saipen/KNOWLEDGE/evidence.md",
            ".saipen/kitchen/probe.md",
        ):
            self.assertIn(declared, included, declared)

        result = self._pack()
        self.assertTrue(result.success, result.error_message)
        with zipfile.ZipFile(result.output_path) as zf:
            names = set(zf.namelist())
        for rel in self.UNDECLARED:
            self.assertNotIn(rel, names, rel)
        for declared in (
            ".saipen/STATE.md",
            ".saipen/BOARD.md",
            ".saipen/LOG.md",
            ".saipen/IDENTITY.md",
            ".saipen/kitchen/probe.md",
        ):
            self.assertIn(declared, names, declared)
        snapshot = json.loads(zipfile.ZipFile(result.output_path).read(MANIFEST_FILENAME))[
            "saipen_snapshot"
        ]
        self.assertEqual(snapshot["status"], se.STATUS_COMPLETE)
        self.assertTrue(snapshot["authoritative_state"])

    def test_files_outside_the_memory_root_are_untouched(self):
        sp = self.write_saipen()
        self._write_undeclared(sp)
        for rel in ("scratch_top.txt", "tools/scratch_diag2.txt", "app.py"):
            target = self.repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("ordinary project file\n", encoding="utf-8")

        included = self.included(self.inventory())
        for rel in ("scratch_top.txt", "tools/scratch_diag2.txt", "app.py"):
            self.assertIn(rel, included, rel)


class TestContractV1Compatibility(SaipenEvidenceCase):
    """TARGET D: v1 projects keep packing exactly as they always did.

    Learning v2 must not force every older project to regenerate its manifest,
    and must not re-read a v1 document through v2's rules.
    """

    def _pack(self, stem="Proj"):
        return pack_single(
            source_path=self.repo,
            output_dir=self.output,
            archive_stem=stem,
            excludes=set(),
            delete_old=True,
            include_timestamp=False,
            manifest_meta={"project_name": stem},
            packing=PackingConfig(),
        )

    def test_case45_canonical_v1_fixture_still_packs(self):
        self.write_saipen(contract=CONTRACT_V1_CANONICAL)
        contract = se.read_contract(self.repo)
        self.assertEqual(contract.status, se.STATUS_COMPLETE)
        self.assertEqual(contract.contract_version, 1)
        self.assertEqual(contract.citations.source, se.RULES_FROM_CONTRACT)
        self.ignore(".saipen/*")
        self.commit()
        verdict = self.inventory().saipen
        self.assertEqual(verdict["status"], se.STATUS_COMPLETE)
        self.assertTrue(verdict["authoritative_state"])
        self.assertEqual(verdict["contract_version"], 1)
        result = self._pack()
        self.assertTrue(result.success, result.error_message)
        with zipfile.ZipFile(result.output_path) as zf:
            snapshot = json.loads(zf.read(MANIFEST_FILENAME))["saipen_snapshot"]
        self.assertEqual(snapshot["status"], se.STATUS_COMPLETE)
        self.assertTrue(snapshot["authoritative_state"])

    def test_case46_v1_is_read_as_it_declares_itself(self):
        """v1 keeps the non-exportable set v1 published.

        The v2 baseline is version knowledge, not a retroactive edit: a v1
        document is held to the exclusions it declares. SAIPEN's own answer
        for such a project is migration on its next canonical write, not a
        consumer silently reinterpreting the shape it was given.
        """
        self.write_saipen(contract=CONTRACT_V1_CANONICAL)
        contract = se.read_contract(self.repo)
        self.assertIn(".saipen/locks", contract.non_exportable)
        self.assertIn(".saipen/recovery", contract.non_exportable)
        self.assertIn(".saipen/LOCAL_STATE.json", contract.non_exportable)
        self.assertNotIn(".saipen/quarantine", contract.non_exportable)
        self.assertNotIn("quarantine/", CONTRACT_V1_CANONICAL["evidence"]["non_exportable"])
        # And the v2 document really does declare it: the delta is real.
        self.assertIn("quarantine/", CONTRACT_V2["evidence"]["non_exportable"])

    def test_case47_hand_written_v1_fixture_still_packs(self):
        """The independent v1 shape keeps working too.

        `CONTRACT` at the top of this file predates the captured fixtures and
        is the real regression this change could have broken: if only the
        captured documents passed, AUDAPACK would have traded one uncovered
        shape for another.
        """
        self.write_saipen()
        self.ignore(".saipen/*")
        self.commit()
        verdict = self.inventory().saipen
        self.assertEqual(verdict["status"], se.STATUS_COMPLETE)
        self.assertEqual(verdict["contract_version"], 1)


class TestSaipenContractV3Precedence(SaipenEvidenceCase):
    """MILESTONE B: v3 precedence between durable recovery paths and non-exportable prefix.

    Contract v3 declares:
    - non_exportable: recovery/
    - conditional: recovery/board-compaction, recovery/log-detail
    - precedence:
      1. transient_segment_or_filename
      2. nested_instance_state
      3. declared_durable_path
      4. non_exportable_prefix
      5. directory_rule
    """

    def _pack(self, stem="Proj", always_exclude=None):
        return pack_single(
            source_path=self.repo,
            output_dir=self.output,
            archive_stem=stem,
            excludes=set(),
            delete_old=True,
            include_timestamp=False,
            manifest_meta={"project_name": stem},
            packing=PackingConfig(always_exclude=list(always_exclude or [])),
        )

    def _v3_contract(self):
        return {
            "contract_version": 3,
            "kind": "saipen_audit_manifest",
            "protocol_version": "8.0.1",
            "generator": "saipen-audit-manifest/3",
            "memory_root": ".saipen",
            "compatibility": {"unknown_contract_version": "refuse"},
            "evidence": {
                "mandatory": [
                    {"kind": "file", "path": "STATE.md"},
                    {"kind": "file", "path": "BOARD.md"},
                    {"kind": "file", "path": "LOG.md"},
                    {"kind": "file", "path": "IDENTITY.md"},
                ],
                "conditional": [
                    {"kind": "dir", "path": "recovery/board-compaction", "recursive": True, "max_files": 100},
                    {"kind": "dir", "path": "recovery/log-detail", "recursive": True, "max_files": 100},
                ],
                "non_exportable": [
                    "locks/",
                    "recovery/",
                    "quarantine/",
                    "LOCAL_STATE.json",
                ],
                "non_exportable_filenames": [
                    "LOCAL_STATE.json",
                    "producer_epoch.json",
                    "crew_epoch.json",
                    ".in-flight",
                ],
                "non_exportable_segments": [
                    ".staging",
                    ".in-flight",
                    ".cache",
                    "__pycache__",
                ],
                "non_exportable_suffixes": [
                    ".tmp",
                    ".lock",
                    ".partial",
                ],
                "nested_instance_files": [
                    "STATE.md",
                    "BOARD.md",
                    "LOG.md",
                    "IDENTITY.md",
                ],
                "precedence": [
                    "transient_segment_or_filename",
                    "nested_instance_state",
                    "declared_durable_path",
                    "non_exportable_prefix",
                    "directory_rule",
                ],
            },
            "required": ["STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md"],
            "references": {
                "surfaces": ["evidence", "recovery/log-detail", "recovery/board-compaction"],
                "carriers": [
                    {"kind": "file", "path": "STATE.md"},
                    {"kind": "file", "path": "BOARD.md"},
                    {"kind": "file", "path": "LOG.md"},
                ],
                "max_carrier_bytes": 1024 * 1024,
                "max_total_bytes": 10 * 1024 * 1024,
                "max_references": 1000,
            },
        }

    def _reseal(self, contract=None):
        (self.repo / ".saipen" / "MANIFEST.json").write_text(
            json.dumps(self._v3_contract() if contract is None else contract, indent=1),
            encoding="utf-8",
        )

    def test_red_control_v3_precedence_durable_recovery_exported_and_unrelated_banned(self):
        """RED control: declared durable recovery subtrees outrank generic recovery/ ban."""
        contract = self._v3_contract()
        sp = self.write_saipen(contract=contract)

        # Create durable recovery evidence
        bc_file = sp / "recovery" / "board-compaction" / "T-X" / "proof.json"
        bc_file.parent.mkdir(parents=True, exist_ok=True)
        bc_file.write_text('{"proof": "compaction"}\n', encoding="utf-8")

        ld_file = sp / "recovery" / "log-detail" / "E-X-proof.json"
        ld_file.parent.mkdir(parents=True, exist_ok=True)
        ld_file.write_text('{"proof": "log_detail"}\n', encoding="utf-8")

        # Create unrelated recovery runtime file
        unrelated = sp / "recovery" / "unrelated-runtime.json"
        unrelated.write_text('{"runtime": "unrelated"}\n', encoding="utf-8")

        # Cite the proofs in BOARD and LOG
        (sp / "BOARD.md").write_text(
            "# Board\n- [x] T-X done [detail_ref: .saipen/recovery/board-compaction/T-X/proof.json]\n",
            encoding="utf-8",
        )
        (sp / "LOG.md").write_text(
            "# Log\n- 24.09.26 [E-X] done [detail_ref: .saipen/recovery/log-detail/E-X-proof.json]\n",
            encoding="utf-8",
        )
        self._reseal(contract)

        parsed_contract = se.read_contract(self.repo)
        bc_rel = ".saipen/recovery/board-compaction/T-X/proof.json"
        ld_rel = ".saipen/recovery/log-detail/E-X-proof.json"
        unrelated_rel = ".saipen/recovery/unrelated-runtime.json"

        # Canonical exportability checks
        self.assertFalse(
            se.is_non_exportable(bc_rel, parsed_contract),
            f"{bc_rel} must be exportable under v3 precedence",
        )
        self.assertFalse(
            se.is_non_exportable(ld_rel, parsed_contract),
            f"{ld_rel} must be exportable under v3 precedence",
        )
        self.assertTrue(
            se.is_non_exportable(unrelated_rel, parsed_contract),
            f"{unrelated_rel} must remain non-exportable",
        )

        # Collection checks
        coll = se.collect(self.repo, parsed_contract)
        self.assertIn(bc_rel, coll.paths)
        self.assertIn(ld_rel, coll.paths)
        self.assertNotIn(unrelated_rel, coll.paths)

        # Inventory and pack checks
        inv = self.inventory()
        inc = self.included(inv)
        self.assertIn(bc_rel, inc)
        self.assertIn(ld_rel, inc)
        self.assertNotIn(unrelated_rel, inc)

        res = self._pack()
        self.assertTrue(res.success, res.error_message)
        with zipfile.ZipFile(res.output_path) as zf:
            names = set(zf.namelist())
            manifest = json.loads(zf.read(MANIFEST_FILENAME))

        self.assertIn(bc_rel, names)
        self.assertIn(ld_rel, names)
        self.assertNotIn(unrelated_rel, names)

        snap = manifest.get("saipen_snapshot", {})
        self.assertEqual(snap.get("status"), se.STATUS_COMPATIBLE_DEGRADED)
        self.assertTrue(snap.get("authoritative_state"))
        self.assertFalse(snap.get("required_evidence_omitted"))
        self.assertEqual(snap.get("omitted_required"), [])

    def test_v3_precedence_transient_overrides_durable(self):
        """Precedence 1 (transient) beats Precedence 3 (declared durable)."""
        contract = self._v3_contract()
        sp = self.write_saipen(contract=contract)

        tmp_file = sp / "recovery" / "board-compaction" / "T-X" / "draft.tmp"
        tmp_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file.write_text("temporary\n", encoding="utf-8")

        inflight_file = sp / "recovery" / "board-compaction" / "T-X" / ".in-flight"
        inflight_file.write_text("lock\n", encoding="utf-8")

        cache_file = sp / "recovery" / "board-compaction" / ".cache" / "cached.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("cached\n", encoding="utf-8")

        parsed_contract = se.read_contract(self.repo)
        for path in (
            ".saipen/recovery/board-compaction/T-X/draft.tmp",
            ".saipen/recovery/board-compaction/T-X/.in-flight",
            ".saipen/recovery/board-compaction/.cache/cached.json",
        ):
            self.assertTrue(
                se.is_non_exportable(path, parsed_contract),
                f"Transient path {path} must be non-exportable even under durable dir",
            )

        coll = se.collect(self.repo, parsed_contract)
        self.assertNotIn(".saipen/recovery/board-compaction/T-X/draft.tmp", coll.paths)
        self.assertNotIn(".saipen/recovery/board-compaction/T-X/.in-flight", coll.paths)
        self.assertNotIn(".saipen/recovery/board-compaction/.cache/cached.json", coll.paths)

    def test_v3_precedence_nested_instance_state_overrides_durable(self):
        """Precedence 2 (nested instance state) beats Precedence 3 (declared durable)."""
        contract = self._v3_contract()
        sp = self.write_saipen(contract=contract)

        nested = sp / "recovery" / "board-compaction" / "sub" / "STATE.md"
        nested.parent.mkdir(parents=True, exist_ok=True)
        nested.write_text("phase: DONE\n", encoding="utf-8")

        parsed_contract = se.read_contract(self.repo)
        nested_rel = ".saipen/recovery/board-compaction/sub/STATE.md"
        self.assertTrue(
            se.is_non_exportable(nested_rel, parsed_contract),
            "Nested instance state must remain non-exportable even under durable dir",
        )
        coll = se.collect(self.repo, parsed_contract)
        self.assertNotIn(nested_rel, coll.paths)

    def test_v3_precedence_hard_safety_secret_policy_remains_authoritative(self):
        """Hard safety secret policy excludes file regardless of contract durable tier."""
        contract = self._v3_contract()
        sp = self.write_saipen(contract=contract)

        secret_file = sp / "recovery" / "board-compaction" / "T-X" / "id_rsa"
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        secret_file.write_text("SECRET\n", encoding="utf-8")

        inv = self.inventory()
        secret_rel = ".saipen/recovery/board-compaction/T-X/id_rsa"
        self.assertNotIn(secret_rel, self.included(inv))
        excluded = {e.rel: e for e in inv.excluded_entries()}
        self.assertIn(secret_rel, excluded)
        self.assertEqual(excluded[secret_rel].reason, "secret_policy")

    def test_v3_precedence_operator_always_exclude_honest_omission(self):
        """Operator always_exclude wins over durable evidence and produces honest omission."""
        contract = self._v3_contract()
        sp = self.write_saipen(contract=contract)

        bc_file = sp / "recovery" / "board-compaction" / "T-X" / "proof.json"
        bc_file.parent.mkdir(parents=True, exist_ok=True)
        bc_file.write_text('{"proof": "compaction"}\n', encoding="utf-8")

        (sp / "BOARD.md").write_text(
            "# Board\n- [x] T-X done [detail_ref: .saipen/recovery/board-compaction/T-X/proof.json]\n",
            encoding="utf-8",
        )
        self._reseal(contract)

        bc_rel = ".saipen/recovery/board-compaction/T-X/proof.json"
        res = self._pack(always_exclude=[bc_rel])
        self.assertTrue(res.success, res.error_message)
        with zipfile.ZipFile(res.output_path) as zf:
            names = set(zf.namelist())
            manifest = json.loads(zf.read(MANIFEST_FILENAME))

        self.assertNotIn(bc_rel, names)
        snap = manifest.get("saipen_snapshot", {})
        self.assertTrue(snap.get("required_evidence_omitted"))
        self.assertFalse(snap.get("authoritative_state"))
        omitted_paths = [x["path"] for x in snap.get("omitted_required", [])]
        self.assertIn(bc_rel, omitted_paths)


class TestSaipenExportDecisionMatrix(unittest.TestCase):
    """T-239 regression matrix for the ONE canonical export decision."""

    def _v3(self, **evidence_overrides):
        doc = TestSaipenContractV3Precedence._v3_contract(None)
        doc["evidence"].update(evidence_overrides)
        return doc

    def _read(self, doc):
        contract = se.read_contract_from_document(doc)
        return contract

    def test_v3_is_admitted_degraded_not_native(self):
        contract = self._read(self._v3())
        self.assertEqual(contract.status, se.STATUS_COMPLETE)
        self.assertEqual(contract.admission, se.ManifestAdmission.COMPATIBLE_DEGRADED)
        self.assertNotIn(3, se.SUPPORTED_CONTRACT_VERSIONS)
        self.assertTrue(contract.durable_precedence)

    def test_decision_table(self):
        contract = self._read(self._v3())
        cases = {
            ".saipen/recovery/board-compaction/T-X/proof.json": (True, "declared_durable_path"),
            ".saipen/recovery/log-detail/E-X-proof.json": (True, "declared_durable_path"),
            ".saipen/recovery/unrelated-runtime.json": (False, "non_exportable_prefix"),
            ".saipen/recovery/board-compaction/T-X/draft.tmp": (False, "transient_segment_or_filename"),
            ".saipen/recovery/board-compaction/T-X/.in-flight": (False, "transient_segment_or_filename"),
            ".saipen/recovery/board-compaction/.cache/cached.json": (False, "transient_segment_or_filename"),
            ".saipen/recovery/board-compaction/T-X/run.lock": (False, "transient_segment_or_filename"),
            ".saipen/recovery/board-compaction/sub/STATE.md": (False, "nested_instance_state"),
            ".saipen/recovery/log-detail/IDENTITY.md": (False, "nested_instance_state"),
            ".saipen/extensions/subs/x/BOARD.md": (False, "nested_instance_state"),
            ".saipen/locks/owner.json": (False, "non_exportable_prefix"),
            ".saipen/LOCAL_STATE.json": (False, "transient_segment_or_filename"),
            ".saipen/kitchen/producer_epoch.json": (False, "transient_segment_or_filename"),
            "src/app.py": (True, ""),
        }
        for name in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md"):
            cases[f".saipen/{name}"] = (True, "declared_durable_path")
        for rel, expected in cases.items():
            with self.subTest(rel=rel):
                self.assertEqual(se.export_decision(rel, contract), expected)
                self.assertEqual(se.is_non_exportable(rel, contract), not expected[0])

    def test_non_recursive_durable_rule_covers_direct_children_only(self):
        doc = self._v3()
        doc["evidence"]["conditional"][0]["recursive"] = False
        contract = self._read(doc)
        self.assertFalse(se.is_non_exportable(".saipen/recovery/board-compaction/a.json", contract))
        self.assertTrue(se.is_non_exportable(".saipen/recovery/board-compaction/T-X/a.json", contract))

    def test_optional_dir_never_outranks_a_ban(self):
        doc = self._v3()
        doc["evidence"]["optional"] = [doc["evidence"].pop("conditional")[0] | {}]
        contract = self._read(doc)
        self.assertTrue(se.is_non_exportable(".saipen/recovery/board-compaction/T-X/proof.json", contract))

    def test_unknown_or_reordered_precedence_keeps_the_strict_prefix_ban(self):
        reordered = list(se.EXPORT_PRECEDENCE)
        reordered[2], reordered[3] = reordered[3], reordered[2]
        for precedence in (reordered, se.EXPORT_PRECEDENCE[:3], [*se.EXPORT_PRECEDENCE, "future_rule"]):
            with self.subTest(precedence=precedence):
                contract = self._read(self._v3(precedence=list(precedence)))
                self.assertFalse(contract.durable_precedence)
                self.assertTrue(
                    se.is_non_exportable(".saipen/recovery/board-compaction/T-X/proof.json", contract)
                )
                # Restrictive classes still apply without the loosening rule.
                self.assertTrue(se.is_non_exportable(".saipen/logs/x.tmp", contract))

    def test_malformed_class_lists_are_refused_not_ignored(self):
        for key, value in (
            ("non_exportable_segments", "not-a-list"),
            ("non_exportable_filenames", ["a/b"]),
            ("non_exportable_suffixes", [3]),
            ("nested_instance_files", [".."]),
            ("precedence", [""]),
            ("non_exportable_segments", ["x"] * (se.EXPORT_CLASS_LIST_LIMIT + 1)),
        ):
            with self.subTest(key=key, value=value if not isinstance(value, list) else value[:2]):
                contract = self._read(self._v3(**{key: value}))
                self.assertEqual(contract.status, se.STATUS_MANIFEST_MALFORMED)

    def test_v1_and_v2_documents_keep_plain_prefix_semantics(self):
        for version in (1, 2):
            doc = json.loads(json.dumps(CONTRACT))
            doc["contract_version"] = version
            doc["evidence"]["conditional"].append(
                {"path": "recovery/board-compaction", "kind": "dir", "recursive": True, "max_files": 10}
            )
            with self.subTest(version=version):
                contract = self._read(doc)
                self.assertEqual(contract.admission, se.ManifestAdmission.NATIVE)
                self.assertFalse(contract.durable_precedence)
                self.assertEqual(contract.transient_segments, ())
                self.assertTrue(
                    se.is_non_exportable(".saipen/recovery/board-compaction/T-X/proof.json", contract)
                )
                # No declared transient classes: v1/v2 do not invent them.
                self.assertFalse(se.is_non_exportable(".saipen/logs/x.tmp", contract))
                self.assertEqual(
                    se.is_non_exportable(".saipen/quarantine/q.md", contract), version == 2
                )

    def test_future_unsafe_contract_still_refused(self):
        doc = self._v3()
        doc["contract_version"] = 4
        doc["evidence"]["non_exportable"] = "recovery/"
        contract = self._read(doc)
        self.assertEqual(contract.status, se.STATUS_CONTRACT_UNKNOWN)


class TestCapturedProfileStoresAreNotEvidence(SaipenEvidenceCase):
    """T-275: a captured runtime profile is the machine, not the project.

    T-274 refused the reproducible browser caches, but the thing that actually
    lands under `.saipen/evidence/**` on a real soak capture is a whole machine
    profile: the agent's own `.zcode` store (session database, rollout
    transcripts, plugin caches), `.zaicode`, `.gemini`, `AppData`, a Chromium
    `session/` tree with Cookies and local storage, and the router/account state
    files beside them. Measured on T-274's own acceptance archive
    (`_ZAICODE_05.10.26-T23-02-51.zip`): 940 of those files shipped, 21.6 MB
    uncompressed, including six `rollout/*.jsonl` transcripts and
    `zaicode-router-key.json`.

    They shipped because `evidence` is a RECURSIVE conditional directory, so
    every path below it is a `declared_durable_path` and outranks a generic
    ban: the refusal has to be structural, and it has to name the container.
    """

    PROFILE = ".saipen/evidence/T-217-ui/profile-9R2uo5"

    #: Every store the real capture left behind. Enumerated so a reviewer can
    #: check the refusal one subtree at a time.
    REFUSED_STORES = (
        ".zcode/cli/rollout/model-io-sess_24c09051.jsonl",
        ".zcode/cli/db/db.sqlite",
        ".zcode/cli/db/db.sqlite-wal",
        ".zcode/cli/log/zcode-2026-10-04.jsonl",
        ".zcode/cli/plugins/cache/marketplaces.json",
        ".zcode/v2/setting.json",
        ".zaicode/state.json",
        ".gemini/settings.json",
        "AppData/Local/ZCode/Cache/data_0",
        "AppData/Roaming/ZCode/Preferences",
        "continuity-project/session.json",
        "session/Preferences",
        "session/Cookies",
        "session/Trust Tokens",
        "session/Local Storage/leveldb/000003.log",
        "session/DawnGraphiteCache/data_1",
        "zaicode-protrail/zaicode-protrail-input-b5469c7b8f18.cs",
        "zaicode-router-key.json",
        "zaicode-account-proxy.json",
        "zaicode-router-host.json",
        "zaicode-token-saver.json",
    )

    def _doc(self):
        doc = TestSaipenContractV3Precedence._v3_contract(None)
        doc["evidence"]["conditional"].append(
            {"kind": "dir", "path": "evidence", "recursive": True, "max_files": 4000}
        )
        return doc

    def _contract(self):
        return se.read_contract_from_document(self._doc())

    def _pack(self, stem="Proj"):
        return pack_single(
            source_path=self.repo,
            output_dir=self.output,
            archive_stem=stem,
            excludes=set(),
            delete_old=True,
            include_timestamp=False,
            manifest_meta={"project_name": stem},
            packing=PackingConfig(),
        )

    def test_every_store_of_a_captured_profile_is_refused(self):
        contract = self._contract()
        for tail in self.REFUSED_STORES:
            rel = f"{self.PROFILE}/{tail}"
            with self.subTest(rel=rel):
                self.assertEqual(
                    se.export_decision(rel, contract), (False, se.EXPORT_RULE_CAPTURED_PROFILE)
                )
                self.assertTrue(se.is_non_exportable(rel, contract))

    def test_the_named_rollout_transcript_is_refused(self):
        """The exact path the ticket names, on the real capture's own shape."""
        contract = self._contract()
        rel = (
            ".saipen/evidence/T-217-ui/profile-QOhTSI/.zcode/cli/rollout/"
            "model-io-sess_24c09051-6859-4523-9e7c-8c472d5455bf.jsonl"
        )
        self.assertEqual(se.export_decision(rel, contract), (False, se.EXPORT_RULE_CAPTURED_PROFILE))

    def test_a_bare_profile_directory_is_a_captured_profile_too(self):
        """The real archive also carries `.saipen/evidence/src119-soak-final/profile/`."""
        contract = self._contract()
        rel = ".saipen/evidence/src119-soak-final/profile/zaicode-account-proxy.json"
        self.assertEqual(se.export_decision(rel, contract), (False, se.EXPORT_RULE_CAPTURED_PROFILE))

    def test_the_capture_around_the_profile_stays_evidence(self):
        contract = self._contract()
        for rel in (
            ".saipen/evidence/T-217-ui/notes.md",
            ".saipen/evidence/T-217-ui/report/summary.json",
            ".saipen/evidence/src119-soak-final/run.json",
            ".saipen/STATE.md",
            ".saipen/evidence/T-217-ui/profile-notes.md",
            "src/app.py",
        ):
            with self.subTest(rel=rel):
                exportable, rule = se.export_decision(rel, contract)
                self.assertTrue(exportable, rel)
                self.assertIn(rule, ("", se.EXPORT_RULE_DURABLE))

    def test_a_profile_path_outside_the_memory_root_is_untouched(self):
        contract = self._contract()
        for rel in (
            "src/profile-data/junk.json",
            "zcode/.e2e-cache/usage-t181/profile-cFLvjj/a.json",
            "profile-a/settings.json",
        ):
            with self.subTest(rel=rel):
                self.assertEqual(se.export_decision(rel, contract), (True, ""))

    def test_the_real_dawn_gpu_cache_directories_are_refused(self):
        """T-274's cache class, spelled the way Chromium actually names them.

        The declared set held ``dawncache`` and ``dawn webgpu cache``; the real
        directories are ``DawnGraphiteCache`` and ``DawnWebGPUCache``, so 100
        entries (10.6 MB) of the very class the rule was written for survived
        T-274's archive untouched.
        """
        contract = self._contract()
        for rel in (
            ".saipen/evidence/T-217-ui/run/DawnGraphiteCache/data_1",
            ".saipen/evidence/T-217-ui/run/DawnWebGPUCache/data_1",
        ):
            with self.subTest(rel=rel):
                self.assertEqual(
                    se.export_decision(rel, contract),
                    (False, se.EXPORT_RULE_TRANSIENT),
                )

    def test_the_ban_is_named_and_the_pack_drops_the_profile(self):
        sp = self.write_saipen()
        (sp / "MANIFEST.json").write_text(json.dumps(self._doc(), indent=1), encoding="utf-8")
        profile = sp / "evidence" / "T-217-ui" / "profile-9R2uo5"
        (profile / ".zcode" / "cli" / "rollout").mkdir(parents=True)
        (profile / ".zcode" / "cli" / "rollout" / "model-io-sess_x.jsonl").write_text(
            "{}\n", encoding="utf-8"
        )
        (profile / "zaicode-router-key.json").write_text("{}\n", encoding="utf-8")
        (sp / "evidence" / "T-217-ui" / "notes.md").write_text("kept\n", encoding="utf-8")
        (sp / "evidence" / "T-217-ui" / "profile-notes.md").write_text("kept\n", encoding="utf-8")
        self.commit()

        rollout = (
            ".saipen/evidence/T-217-ui/profile-9R2uo5/.zcode/cli/rollout/model-io-sess_x.jsonl"
        )
        router_key = ".saipen/evidence/T-217-ui/profile-9R2uo5/zaicode-router-key.json"
        inv = self.inventory()
        included = self.included(inv)
        self.assertNotIn(rollout, included)
        self.assertNotIn(router_key, included)
        # Named, not silent: the refusal carries the inventory's own reason.
        excluded = {entry.rel: entry for entry in inv.excluded_entries()}
        self.assertEqual(excluded[rollout].reason, se.REASON_SAIPEN_NON_EXPORTABLE)
        self.assertEqual(excluded[router_key].reason, se.REASON_SAIPEN_NON_EXPORTABLE)
        # The capture itself is evidence and survives beside the profile.
        self.assertIn(".saipen/evidence/T-217-ui/notes.md", included)
        self.assertIn(".saipen/evidence/T-217-ui/profile-notes.md", included)

        result = self._pack()
        self.assertTrue(result.success, result.error_message)
        with zipfile.ZipFile(result.output_path) as zf:
            names = set(zf.namelist())
        self.assertNotIn(rollout, names)
        self.assertNotIn(router_key, names)
        self.assertIn(".saipen/evidence/T-217-ui/notes.md", names)
        snapshot = json.loads(zipfile.ZipFile(result.output_path).read(MANIFEST_FILENAME))[
            "saipen_snapshot"
        ]
        omitted = {entry["path"]: entry for entry in snapshot["omitted_required"]}
        # The refusal is NAMED on the inventory surface asserted above, and that
        # is the only surface that can name it: a contract-banned path is refused
        # BEFORE discovery, so it never acquires a tier and the snapshot has no
        # omission to report for it. Reporting it here would mean the ban ran
        # after collection -- too late, and the file would have been collected.
        self.assertNotIn(rollout, omitted)
        self.assertNotIn(router_key, omitted)
        self.assertFalse(
            [p for p in omitted if p.startswith(".saipen/evidence/T-217-ui/profile-9R2uo5/")],
            "a refused profile subtree must not be reported as an omission",
        )
        # Refusing machine state costs the snapshot nothing. The capture around
        # the profile is complete conditional evidence, so the verdict stays
        # authoritative instead of degrading over files the contract banned.
        self.assertFalse(snapshot["required_evidence_omitted"])
        self.assertTrue(snapshot["authoritative_state"], snapshot["detail"])


class TestNpmCacheBlobsAreNotEvidence(SaipenEvidenceCase):
    """T-299: a probe's npm cache is the machine, not the project.

    `.saipen/kitchen` is an OPTIONAL recursive evidence dir (real manifest),
    so a `tmp-control/ctrlv-probe` run that pointed `npm_config_cache` at a
    probe-local directory ships its whole `_cacache` blob store -- ~20.7 MB
    compressed -- in every audit bundle. The blobs are reproducible by
    running npm again and say nothing about the project, so they are refused
    wherever they sit INSIDE the memory root (T-274 precedent), as a NAMED
    transient omission. Probe notes, sources and tests are unaffected: the
    ban names cache segments only, and applies inside `.saipen` alone.
    """

    PROBE = ".saipen/kitchen/tmp-control/ctrlv-probe"

    #: The layout npm actually writes under a cache root.
    REFUSED_BLOBS = (
        "_cacache/content-v2/sha512/ab/cd/blobdata",
        "_cacache/content-v2/sha512/ef/01/moreblobdata",
        "_cacache/index-v5/11/22/entryjson",
        "_cacache/tmp/manifest-fetch-1a2b3c.json",
    )

    #: Probe material that must keep shipping.
    KEPT_NOTES = (
        "probe.json",
        "run.log",
        "ctrlv-probe.md",
    )

    def _doc(self):
        doc = TestSaipenContractV3Precedence._v3_contract(None)
        doc["evidence"]["optional"] = [
            {"kind": "dir", "path": "kitchen", "recursive": True, "max_files": 500},
        ]
        return doc

    def _contract(self):
        return se.read_contract_from_document(self._doc())

    def test_npm_cache_blobs_are_refused_as_transient(self):
        contract = self._contract()
        for tail in self.REFUSED_BLOBS:
            rel = f"{self.PROBE}/{tail}"
            with self.subTest(rel=rel):
                self.assertEqual(
                    se.export_decision(rel, contract),
                    (False, se.EXPORT_RULE_TRANSIENT),
                )
                self.assertTrue(se.is_non_exportable(rel, contract))

    def test_probe_notes_sources_and_tests_stay_exportable(self):
        contract = self._contract()
        for tail in self.KEPT_NOTES:
            rel = f"{self.PROBE}/{tail}"
            with self.subTest(rel=rel):
                exportable, _rule = se.export_decision(rel, contract)
                self.assertTrue(exportable, rel)
        for rel in (
            ".saipen/kitchen/T-158-validation.md",
            ".saipen/STATE.md",
            "src/app.py",
        ):
            with self.subTest(rel=rel):
                exportable, rule = se.export_decision(rel, contract)
                self.assertTrue(exportable, rel)
                self.assertIn(rule, ("", se.EXPORT_RULE_DURABLE))

    def test_the_ban_is_named_and_the_pack_drops_the_cache(self):
        sp = self.write_saipen(contract=self._doc())
        probe = sp / "kitchen" / "tmp-control" / "ctrlv-probe"
        for tail in self.REFUSED_BLOBS:
            blob = probe / tail
            blob.parent.mkdir(parents=True, exist_ok=True)
            blob.write_bytes(b"\x00" * 4096)
        for tail in self.KEPT_NOTES:
            (probe / tail).write_text("kept\n", encoding="utf-8")
        (sp / "kitchen" / "T-158-validation.md").write_text("kept\n", encoding="utf-8")
        self.commit()

        blob_rels = [f"{self.PROBE}/{tail}" for tail in self.REFUSED_BLOBS]
        inv = self.inventory()
        included = self.included(inv)
        for rel in blob_rels:
            with self.subTest(rel=rel):
                self.assertNotIn(rel, included)
        excluded = {entry.rel: entry for entry in inv.excluded_entries()}
        for rel in blob_rels:
            with self.subTest(rel=rel):
                self.assertEqual(excluded[rel].reason, se.REASON_SAIPEN_NON_EXPORTABLE)
        for tail in self.KEPT_NOTES:
            self.assertIn(f"{self.PROBE}/{tail}", included)
        self.assertIn(".saipen/kitchen/T-158-validation.md", included)

        result = pack_single(
            source_path=self.repo,
            output_dir=self.output,
            archive_stem="Proj",
            excludes=set(),
            delete_old=True,
            include_timestamp=False,
            manifest_meta={"project_name": "Proj"},
            packing=PackingConfig(),
        )
        self.assertTrue(result.success, result.error_message)
        with zipfile.ZipFile(result.output_path) as zf:
            names = set(zf.namelist())
        for rel in blob_rels:
            with self.subTest(rel=rel):
                self.assertNotIn(rel, names)
        for tail in self.KEPT_NOTES:
            self.assertIn(f"{self.PROBE}/{tail}", names)


class TestSaipenV3HardSafetyOrdering(TestSaipenContractV3Precedence):
    """Hard safety outranks SAIPEN export policy on both sides of a ban."""

    def test_secret_under_a_banned_prefix_keeps_the_secret_reason(self):
        sp = self.write_saipen(contract=self._v3_contract())
        for rel_parts in (("recovery", "unrelated", "id_ed25519"), ("recovery", "board-compaction", "T-X", "deploy.ppk")):
            path = sp.joinpath(*rel_parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("KEY\n", encoding="utf-8")
        inv = self.inventory()
        excluded = {e.rel: e for e in inv.excluded_entries()}
        for rel in (
            ".saipen/recovery/unrelated/id_ed25519",
            ".saipen/recovery/board-compaction/T-X/deploy.ppk",
        ):
            with self.subTest(rel=rel):
                self.assertNotIn(rel, self.included(inv))
                self.assertIn(rel, excluded)
                self.assertEqual(excluded[rel].reason, "secret_policy")

    def test_tracked_private_key_in_durable_subtree_fails_closed(self):
        sp = self.write_saipen(contract=self._v3_contract())
        key = sp / "recovery" / "board-compaction" / "T-X" / "id_rsa"
        key.parent.mkdir(parents=True, exist_ok=True)
        key.write_text("KEY\n", encoding="utf-8")
        subprocess.run(["git", "add", "-f", str(key)], cwd=self.repo, check=True)
        with self.assertRaises(SourceInventoryError) as ctx:
            self.inventory()
        self.assertEqual(ctx.exception.code, CODE_TRACKED_HARD_DENY_CONFLICT)

    def test_durable_evidence_survives_and_state_is_authoritative(self):
        sp = self.write_saipen(contract=self._v3_contract())
        proof = sp / "recovery" / "log-detail" / "E-9.json"
        proof.parent.mkdir(parents=True, exist_ok=True)
        proof.write_text("{}\n", encoding="utf-8")
        (sp / "recovery" / "stray.json").write_text("{}\n", encoding="utf-8")
        (sp / "LOG.md").write_text(
            "- [E-9] done [detail_ref: .saipen/recovery/log-detail/E-9.json]\n", encoding="utf-8"
        )
        self._reseal()
        res = self._pack()
        self.assertTrue(res.success, res.error_message)
        with zipfile.ZipFile(res.output_path) as zf:
            names = set(zf.namelist())
            snap = json.loads(zf.read(MANIFEST_FILENAME)).get("saipen_snapshot", {})
        self.assertIn(".saipen/recovery/log-detail/E-9.json", names)
        self.assertNotIn(".saipen/recovery/stray.json", names)
        for name in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md"):
            self.assertIn(f".saipen/{name}", names)
        self.assertEqual(snap.get("status"), se.STATUS_COMPATIBLE_DEGRADED)
        self.assertTrue(snap.get("authoritative_state"))
        self.assertEqual(snap.get("omitted_required"), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
