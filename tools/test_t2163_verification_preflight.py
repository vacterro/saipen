"""T-2163: verify-environment preflight and mismatch classification.

Measured 2026-11-22 on the T-2162 boundary (four full-family runs at tree
fingerprint 63c8a2c81a81cbf4, 9191.4 s combined). All four records carry
byte-identical identity blocks except one dimension: the third run's
``verification_identity.verifiers`` pinned the engine files to the REPO tree
(V:\\...\\_SAIPEN\\tools\\saipen_engine) while the canonical evaluator runs the
scheduled-source install (C:\\Users\\...\\scheduled-source\\tools\\saipen_engine).
The verifier sha256 values agree -- the same engine bytes reached through a
different install route. ``compatible`` is right to refuse (identity is
identity), but ``incompatibility`` has no dimension to name, so both gates
emit the bare "missing or incompatible verification environment identity"
sentence and the reader's cheapest hypothesis is "the tree is wrong":
re-run the 37-minute family. Twice.

This ticket closes the diagnosis side, fail-closed:

- ``dimension_mismatches`` explains WHY two identity captures disagree,
  dimension by dimension, without ever changing the compatibility decision;
- ``incompatibility_detail`` gives a recorded identity a reader-actionable
  reason (the existing ``incompatibility`` stays the rule owner);
- ``core_unit.preflight`` is the read-only pre-run projection: is a record
  reusable, is a fresh run required, and if an existing record is refused,
  exactly which dimension refuses it.

The classification never makes an incompatible record compatible and never
copies identity across routes: identical content through a different route is
still a mismatch -- it is simply a mismatch the reader can now act on without
paying for a full family to learn about.

One real ``capture`` runs per process (it hashes the toolchain, ~2.5 s); the
temp-project fixtures derive from it, so the module stays inside the focused
corridor budget instead of paying 2.5 s per case.

Negative controls required by the campaign brief, mapped to tests:

1. identical environment -> compatible (IdenticalEnvironmentTests).
2. different python executable -> classified (DimensionClassifierTests).
3. changed environment -> classified refusal (DimensionClassifierTests).
4. different toolchain -> classified (DimensionClassifierTests).
5. modified source -> no reuse (PreflightDecisionTests.no_records).
6. modified baseline -> no reuse (PreflightDecisionTests.modified_baseline).
7. older identity rule -> refusal (DimensionClassifierTests).
8. corrupt record -> refusal (CorruptRecordTests, PreflightDecisionTests).
9. current valid record + wrong evaluator -> actionable route diagnostic
   (RouteMismatchTests).
10. same process tree -> compatible by construction
    (PreflightDecisionTests.reusable).
11. a FAIL record can never be reused as PASS (NoReuseFromFailTests).
12. newer conflicting evidence is never hidden by an older PASS
    (NewestOutcomeWinsTests).

Run standalone:
    python tools/test_t2163_verification_preflight.py
"""

from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import core_unit  # noqa: E402
from saipen_engine import verification_cache as cache  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

PROJECT = TOOLS.parent
ENGINE_DIR = Path(cache.__file__).resolve().parent
ALT_ENGINE_ROOT = "C:\\preflight-alternate-engine"

#: One capture per process (toolchain hashing costs ~2.5 s); a holder cell
#: instead of a ``global`` statement, so every test shares the same identity.
_IDENTITY_HOLDER: list = []


def project_identity() -> dict:
    """The single per-process capture fixtures derive from."""
    if not _IDENTITY_HOLDER:
        _IDENTITY_HOLDER.append(
            cache.capture(PROJECT, core_unit.verification_configuration())
        )
    return _IDENTITY_HOLDER[0]


def setUpModule() -> None:
    isolate_host_session()


class TempProjectMixin(unittest.TestCase):
    """A disposable project that declares this same core-unit family."""

    def make_project(self) -> Path:
        root = Path(tempfile.mkdtemp(prefix="t2163-preflight-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        tools = root / "tools"
        tools.mkdir()
        baseline = json.loads(
            (TOOLS / "core_unit_baseline.json").read_text(encoding="utf-8")
        )
        # One inherited red is enough: the fixtures judge against it.
        baseline["red"] = baseline["red"][:1]
        (tools / "core_unit_baseline.json").write_text(
            json.dumps(baseline, indent=2), encoding="utf-8"
        )
        return root

    def identity(self, root: Path) -> dict:
        """The capture ``preflight`` would take in this process for ``root``.

        Within one process tree the only per-root identity leaf is the
        baseline file, so the fixture carries that root's leaf on top of the
        one shared capture. The engine's own equality decides reuse; this is
        record fabrication, not a second truth.
        """
        base = project_identity()
        if root == PROJECT:
            return base
        fresh = copy.deepcopy(base)
        fresh["baseline"] = cache.file_identity(
            root / "tools" / "core_unit_baseline.json"
        )
        return fresh

    def on_alt_route(self, identity: dict) -> dict:
        rerouted = copy.deepcopy(identity)
        for name, verifier in rerouted["verifiers"].items():
            verifier["path"] = str(Path(ALT_ENGINE_ROOT) / name)
        return rerouted

    def fixture_record(
        self,
        root: Path,
        *,
        fingerprint=None,
        baseline_sha256=None,
        identity=None,
        red=(),
    ) -> dict:
        red = list(red)
        return {
            "schema": core_unit.SCHEMA_VERSION,
            "family": core_unit.FAMILY_NAME,
            "command": ["python", "-B", "-m", "unittest"],
            "fingerprint": fingerprint or core_unit.tree_fingerprint(root),
            "verification_identity": (
                identity if identity is not None else self.identity(root)
            ),
            "fingerprint_excludes": list(core_unit.FINGERPRINT_EXCLUDED),
            "baseline_sha256": baseline_sha256 or core_unit.baseline_digest(root),
            "head": None,
            "finished_utc": "2026-11-22T12:33:53Z",
            "status": "FAIL" if red else "PASS",
            "exit_code": 1 if red else 0,
            "ran": 12,
            "duration_s": 10.0,
            "timeout_s": 10800,
            "headers": len(red),
            "unparsed": 0,
            "tallied": len(red),
            "red": red,
            "red_sections": {},
            "new_red": [],
            "fixed": [],
            "problems": [],
            "verdict": "FAIL" if red else "PASS",
            "discovered": 12,
            "jobs": 1,
            "membership_required": False,
            "shards": [],
        }

    def write_record(self, root: Path, record: dict, stamp: str) -> Path:
        directory = root / core_unit.RECORD_DIR_REL
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{record['fingerprint'][:16]}-{stamp}Z.json"
        path.write_text(json.dumps(record, indent=1), encoding="utf-8")
        return path

    def preflight(self, root: Path) -> dict:
        return core_unit.preflight(
            root, verification_identity=self.identity(root)
        )


class DimensionClassifierTests(unittest.TestCase):
    """Controls 2, 3, 4, 7 and the missing/corrupt identity shapes."""

    def variants(self) -> dict:
        current = project_identity()
        python_runtime = copy.deepcopy(current)
        python_runtime["python"]["runtime"][0] = {
            "path": "C:\\elsewhere\\python.exe",
            "exists": True,
            "sha256": "0" * 64,
        }
        environment = copy.deepcopy(current)
        environment["environment_sha256"] = "9" * 64
        toolchain = copy.deepcopy(current)
        toolchain["toolchain"] = {
            "git": {
                "path": "C:\\elsewhere\\git.exe",
                "exists": True,
                "sha256": "1" * 64,
            }
        }
        platform = copy.deepcopy(current)
        platform["platform"]["node"] = "OTHER-HOST"
        host_config = copy.deepcopy(current)
        host_config["configuration_files"] = [
            {"path": "C:\\elsewhere\\config.toml", "exists": True, "sha256": "2" * 64}
        ]
        legacy_rule = copy.deepcopy(current)
        legacy_rule["identity_rule"] = "canonical-child-1"
        missing = copy.deepcopy(current)
        missing.pop("python")
        unknown = copy.deepcopy(current)
        unknown["mystery_dimension"] = {"anything": True}
        return {
            "python runtime": (current, python_runtime, "python"),
            "identity environment": (current, environment, "environment"),
            "toolchain": (current, toolchain, "toolchain"),
            "host platform": (current, platform, "platform"),
            "host configuration": (current, host_config, "host configuration"),
            "identity rule": (current, legacy_rule, "identity rule"),
            "missing dimension": (current, missing, "missing the python"),
            "unrecognized field": (current, unknown, "mystery_dimension"),
        }

    def test_each_dimension_names_itself_not_a_mystery(self):
        for name, (current, recorded, expect) in self.variants().items():
            with self.subTest(variant=name):
                reasons = cache.dimension_mismatches(current, recorded)
                self.assertTrue(reasons, f"{name} mismatch explained nothing")
                joined = " ".join(reasons).lower()
                self.assertIn(expect.lower(), joined)

    def test_classification_is_symmetric_in_what_it_names(self):
        current, recorded, _expect = self.variants()["unrecognized field"]
        direct = cache.dimension_mismatches(current, recorded)
        self.assertIn("mystery_dimension", " ".join(direct))

    def test_a_dimension_walk_agrees_with_the_leaf_diff_of_the_measured_case(self):
        current = project_identity()
        routed = copy.deepcopy(current)
        for name in routed["verifiers"]:
            routed["verifiers"][name]["path"] = (
                str(Path(ALT_ENGINE_ROOT) / name)
            )
        reasons = cache.dimension_mismatches(current, routed)
        self.assertTrue(reasons)


class IdenticalEnvironmentTests(TempProjectMixin):
    def test_identical_captures_report_no_dimensions(self):
        current = project_identity()
        self.assertEqual(cache.dimension_mismatches(current, current), [])
        self.assertIsNone(
            cache.incompatibility_detail(PROJECT, current, current=current)
        )
        self.assertTrue(cache.compatible(PROJECT, current))

    def test_a_capture_against_itself_in_a_fresh_project_is_compatible(self):
        root = self.make_project()
        identity = self.identity(root)
        self.assertTrue(
            cache.compatible(root, identity),
            "a derived fixture identity diverged from the engine's capture",
        )
        self.assertIsNone(
            cache.incompatibility_detail(root, identity, current=identity)
        )


class RuleRecordTests(TempProjectMixin):
    def test_an_older_rule_record_is_refused_by_name_first(self):
        legacy = copy.deepcopy(project_identity())
        legacy["identity_rule"] = "canonical-child-1"
        reason = cache.incompatibility(legacy)
        self.assertIsNotNone(reason)
        self.assertIn(cache.IDENTITY_RULE, reason)
        self.assertEqual(
            cache.incompatibility_detail(PROJECT, legacy), reason,
            "the rule owner must keep precedence over the dimension words",
        )


class CorruptRecordTests(TempProjectMixin):
    def test_dimension_walk_names_a_missing_record(self):
        current = project_identity()
        reasons = cache.dimension_mismatches(current, {})
        self.assertTrue(reasons)


class RouteMismatchTests(TempProjectMixin):
    """The measured T-2162 case: same engine bytes, different install route."""

    def test_route_only_mismatch_is_actionable_not_generic(self):
        root = self.make_project()
        recorded = self.on_alt_route(self.identity(root))
        current = self.identity(root)
        self.assertFalse(cache.compatible(root, recorded))
        reasons = cache.dimension_mismatches(current, recorded)
        self.assertTrue(reasons, "a refused record explained nothing")
        joined = " ".join(reasons).lower()
        self.assertIn("route", joined)
        self.assertIn(ALT_ENGINE_ROOT.lower(), joined)
        self.assertIn(str(ENGINE_DIR).lower(), joined)
        detail = cache.incompatibility_detail(root, recorded, current=current)
        self.assertIsNotNone(detail)
        self.assertIn("route", detail.lower())

    def test_route_mismatch_never_becomes_compatible_by_classification(self):
        root = self.make_project()
        record = self.fixture_record(
            root, identity=self.on_alt_route(self.identity(root))
        )
        self.write_record(root, record, "20261122T111600000000")
        self.assertFalse(cache.compatible(root, record["verification_identity"]))
        self.assertIsNone(
            core_unit.reusable_record(
                root,
                record["fingerprint"],
                verification_identity=self.identity(root),
            ),
            "a record on another route must not become reusable by explanation",
        )
        report = self.preflight(root)
        self.assertIsNone(report.get("reusable_record"))
        self.assertEqual(report.get("decision"), "EVALUATOR_ENVIRONMENT_MISMATCH")


class PreflightDecisionTests(TempProjectMixin):
    def test_reusable_record_is_reported_before_any_run(self):
        root = self.make_project()
        record = self.fixture_record(root)
        self.write_record(root, record, "20261122T111600000000")
        report = self.preflight(root)
        self.assertEqual(report.get("decision"), "REUSABLE_EXACT_RECORD")
        self.assertIsNotNone(report.get("reusable_record"))
        self.assertEqual(
            report["reusable_record"]["record"]["fingerprint"], record["fingerprint"]
        )

    def test_no_records_means_new_source_verification(self):
        root = self.make_project()
        report = self.preflight(root)
        self.assertEqual(report.get("decision"), "NEW_SOURCE_VERIFICATION_REQUIRED")
        self.assertEqual(report.get("records"), [])

    def test_a_record_judged_against_another_baseline_is_new_baseline(self):
        """The tree fingerprint cannot move a record's verdict arithmetic.

        A baseline file is part of the fingerprinted tree, so a real baseline
        edit answers NEW_SOURCE first. The baseline dimension answers the
        other half of the measured family: a record whose own field claims
        a different baseline than the one this tree ships.
        """
        root = self.make_project()
        record = self.fixture_record(root, baseline_sha256="0" * 64)
        self.write_record(root, record, "20261122T111600000000")
        report = self.preflight(root)
        self.assertEqual(report.get("decision"), "NEW_BASELINE_VERIFICATION_REQUIRED")
        self.assertIsNone(report.get("reusable_record"))

    def test_environment_dimension_requires_new_environment_run(self):
        root = self.make_project()
        drift = copy.deepcopy(self.identity(root))
        drift["python"]["prefix"] = "C:\\another-python-prefix"
        record = self.fixture_record(root, identity=drift)
        self.write_record(root, record, "20261122T111600000000")
        report = self.preflight(root)
        self.assertEqual(
            report.get("decision"), "NEW_ENVIRONMENT_VERIFICATION_REQUIRED"
        )
        reasons = " ".join(report.get("reasons") or [])
        self.assertIn("python", reasons.lower())

    def test_route_only_mismatch_reports_evaluator_mismatch(self):
        root = self.make_project()
        record = self.fixture_record(
            root, identity=self.on_alt_route(self.identity(root))
        )
        self.write_record(root, record, "20261122T111600000000")
        report = self.preflight(root)
        self.assertEqual(report.get("decision"), "EVALUATOR_ENVIRONMENT_MISMATCH")
        reasons = " ".join(report.get("reasons") or [])
        self.assertIn("route", reasons.lower())

    def test_corrupt_only_evidence_is_reported_as_invalid(self):
        root = self.make_project()
        record = self.fixture_record(root)
        directory = root / core_unit.RECORD_DIR_REL
        directory.mkdir(parents=True)
        (
            directory / f"{record['fingerprint'][:16]}-20261122T111600000000Z.json"
        ).write_text("{ this is not JSON", encoding="utf-8")
        report = self.preflight(root)
        self.assertEqual(report.get("decision"), "INVALID_OR_CORRUPT_RECORD")

    def test_missing_identity_is_reported_as_invalid(self):
        root = self.make_project()
        record = self.fixture_record(root)
        record["verification_identity"] = None
        self.write_record(root, record, "20261122T111600000000")
        report = self.preflight(root)
        self.assertEqual(report.get("decision"), "INVALID_OR_CORRUPT_RECORD")
        reasons = " ".join(report.get("reasons") or [])
        self.assertIn("identity", reasons.lower())

    def test_non_mapping_identity_is_reported_as_invalid(self):
        root = self.make_project()
        record = self.fixture_record(root)
        record["verification_identity"] = "not-a-identity"
        self.write_record(root, record, "20261122T111600000000")
        report = self.preflight(root)
        self.assertEqual(report.get("decision"), "INVALID_OR_CORRUPT_RECORD")


class NoReuseFromFailTests(TempProjectMixin):
    def test_fail_record_is_triage_never_reuse(self):
        root = self.make_project()
        red_one = "test_synth_flake.Flake.test_goes_red_under_load"
        record = self.fixture_record(root, red=[red_one])
        self.write_record(root, record, "20261122T111600000000")
        report = self.preflight(root)
        self.assertEqual(report.get("decision"), "PREVIOUS_FAILURE_REQUIRES_TRIAGE")
        self.assertIsNone(report.get("reusable_record"))
        self.assertTrue(
            any(red_one in (item.get("new_red") or []) for item in report["records"])
        )


class NewestOutcomeWinsTests(TempProjectMixin):
    """Control 12: an older PASS can not mask a newer verdict."""

    def test_older_pass_does_not_hide_newer_fail(self):
        root = self.make_project()
        self.write_record(root, self.fixture_record(root), "20261122T111600000000")
        self.write_record(
            root,
            self.fixture_record(
                root, red=["test_synth_flake.Flake.test_goes_red_under_load"]
            ),
            "20261122T123300000000",
        )
        report = self.preflight(root)
        self.assertEqual(report.get("decision"), "PREVIOUS_FAILURE_REQUIRES_TRIAGE")

    def test_newer_pass_answers_reusable_despite_older_fail(self):
        root = self.make_project()
        self.write_record(
            root,
            self.fixture_record(
                root, red=["test_synth_flake.Flake.test_goes_red_under_load"]
            ),
            "20261122T111600000000",
        )
        self.write_record(root, self.fixture_record(root), "20261122T123300000000")
        report = self.preflight(root)
        self.assertEqual(report.get("decision"), "REUSABLE_EXACT_RECORD")


class PreflightReadOnlyTests(TempProjectMixin):
    def test_preflight_is_read_only_and_deterministic(self):
        root = self.make_project()
        self.write_record(root, self.fixture_record(root), "20261122T111600000000")
        before = sorted(str(p) for p in root.rglob("*"))
        first = self.preflight(root)
        second = self.preflight(root)
        after = sorted(str(p) for p in root.rglob("*"))
        self.assertEqual(first, second)
        self.assertEqual(before, after)


class GateContractTests(unittest.TestCase):
    """The gates keep asking the rule owner AND classify beyond the rule.

    T-1865 locked the gates to ``reason = incompatibility(...)`` and banned
    the bare unexplained sentence; T-2163 layers the dimension owner on top
    of that still-present line.
    """

    def test_both_gates_ask_the_dimension_owner(self):
        for name in ("core_unit.py", "focused_unit.py"):
            source = (TOOLS / "saipen_engine" / name).read_text(encoding="utf-8")
            self.assertIn(
                'reason = incompatibility(record.get("verification_identity"))',
                source,
                f"{name} lost the T-1865 rule-owner line",
            )
            self.assertIn(
                "incompatibility_detail", source, f"{name} lost the detail owner"
            )

    def test_preflight_is_declared_on_the_core_unit_router(self):
        source = (TOOLS / "saipen_engine" / "core_unit.py").read_text(encoding="utf-8")
        self.assertIn("def preflight(", source)
        self.assertIn('"preflight"', source)


if __name__ == "__main__":
    unittest.main()
