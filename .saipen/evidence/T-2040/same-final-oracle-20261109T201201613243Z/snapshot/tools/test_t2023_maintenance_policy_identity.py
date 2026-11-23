"""T-2023/SRC-395: a standing maintenance grant is bound to the goal's POLICY,
not only its identity, and a refusal is never reported as available authority.

REPRODUCED DEFECTS (measured 2026-11-05 against live source, in disposable
projects driven by the repository's own simulated native-owner broker fixture):

P0. `maintenance_goal_digest` covered only the five IDENTITY fields of the
    registered PersistentGoal, so after a capsule was granted and applied the
    goal's POLICY could still be edited freely -- `success_criteria` (coverage
    target, capture sha, patch identity, the independent-verification
    requirement), `admission_policy` and `research_or_work_backlog_source` --
    with the digest UNCHANGED, `goal_authority.prove()` still returning no
    errors and `replenishment.maintenance_authority` still authorizing. The
    authenticated grant identity stayed the same while the policy that decides
    which Work is admitted and when the goal counts as done had moved. With the
    real `EvidenceGapLedgerProvider` the same ledger moved
    DISCOVERY_REQUIRED -> SATISFIED once independent verification was disabled.

P1. `extensions/adapters/zaicode/saipen-guard.py::_goal_management_preview`
    treated the mere PRESENCE of a parsed document as successful inspection, so
    an inner refusal (`ok=false`, `PROPOSAL_UNAVAILABLE`) was reported outward
    as `ok=true`, `GOAL_MANAGEMENT_PREVIEW` -- a failed proposal looked like
    available authority.

These are authorization-policy integrity defects. They do NOT establish a
real-world broker compromise: signatures, native operator origin, revocation,
expiration and checkpoint budgets are untouched.

Every control below runs the REAL functions against real files; no mock stands
between the assertion and the arithmetic (the only mocks replay one side of
the admission race and stand in for the host hook's engine call).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import codec, goal_authority, state  # noqa: E402
from saipen_engine.discovery_providers import EvidenceGapLedgerProvider  # noqa: E402
from saipen_engine.persistent_goal import (  # noqa: E402
    SCOPE_MAINTENANCE,
    STATUS_DISCOVERY_REQUIRED,
    STATUS_SATISFIED,
    PersistentGoal,
    delete_goal,
    get_goal,
    register_goal,
    save_goal,
)
from saipen_engine.replenishment import (  # noqa: E402
    granted_maintenance_policy_digest,
    maintenance_authority,
)

from test_t2023_goal_management_and_maintenance_binding import (  # noqa: E402
    MAINTENANCE_OBJECTIVE,
    _project,
    _read_history,
    _register_maintenance,
    _witnessed_apply,
)

HOOK = REPO / "extensions" / "adapters" / "zaicode" / "saipen-guard.py"

_EMPTY_BOARD = "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n\n## BLOCKED\n"

#: The pre-fix digest payload: identity only, no version tag. Fixed here as the
#: LEGACY anchor any grandfathering migration would have to reproduce.
_LEGACY_IDENTITY_FIELDS = (
    "goal_id",
    "project_id",
    "objective",
    "authorization_scope",
    "evidence_provider",
)


def _load_hook():
    spec = importlib.util.spec_from_file_location("t2023_pol_guard", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _prove(root: Path) -> list[str]:
    return goal_authority.prove(root, state.parse_state(codec.read_doc(root / ".saipen/STATE.md")))


class _Granted(unittest.TestCase):
    """One live, granted maintenance campaign in a disposable project."""

    def grant(self) -> tuple[Path, str]:
        root = _project(self, objective=MAINTENANCE_OBJECTIVE)
        _register_maintenance(root)
        st = state.parse_state(codec.read_doc(root / ".saipen/STATE.md"))
        proposal = goal_authority.propose_capsule(
            root, st, _read_history(root), until="continuous_maintenance"
        )
        self.assertTrue(proposal["ok"], proposal)
        applied = _witnessed_apply(self, root, proposal["capsule_text"])
        self.assertTrue(applied.ok, applied.to_dict())
        self.assertEqual(_prove(root), [], "the granted campaign must start proven")
        return root, proposal["capsule"]["maintenance_goal_digest"]

    def edit_goal(self, root: Path, **fields) -> PersistentGoal:
        """Mutate the REGISTERED goal exactly as a later writer would."""
        live = get_goal(root, "self-maintenance-core")
        self.assertIsNotNone(live)
        for key, value in fields.items():
            setattr(live, key, value)
        save_goal(root, live)
        return live

    def assert_invalidated(self, root: Path) -> None:
        errors = _prove(root)
        self.assertTrue(errors, "a material policy change must invalidate the grant")
        self.assertIn("no committed operator grant", " ".join(errors), errors)
        authority = maintenance_authority(root)
        self.assertFalse(authority["authorized"], authority)


class P0GrantBindsThePolicy(_Granted):
    """Controls 1 and 2: a material policy change invalidates the grant."""

    def test_independent_verification_requirement_is_bound(self):
        """Control 1: flipping require_independent_verification invalidates."""
        root, before = self.grant()
        live = get_goal(root, "self-maintenance-core")
        self.edit_goal(
            root,
            success_criteria={**live.success_criteria, "require_independent_verification": False},
        )
        self.assertNotEqual(goal_authority.maintenance_goal_digest(
            get_goal(root, "self-maintenance-core")), before)
        self.assert_invalidated(root)

    def test_capture_patch_and_coverage_constraints_are_bound(self):
        """Control 2: capture sha, patch identity and coverage target are bound."""
        root, before = self.grant()
        for criteria in (
            {"coverage_percent": 50.0},
            {"capture_sha256": "b" * 64},
            {"target_patch": "public-9.9.9"},
        ):
            with self.subTest(criteria=criteria):
                self.edit_goal(root, success_criteria=dict(criteria))
                self.assertNotEqual(goal_authority.maintenance_goal_digest(
                    get_goal(root, "self-maintenance-core")), before)
                self.assert_invalidated(root)

    def test_admission_policy_is_bound(self):
        """Control 2: provider-relevant admission rules are bound."""
        root, before = self.grant()
        self.edit_goal(root, admission_policy={"required_capture_sha256": "c" * 64})
        self.assert_invalidated(root)
        self.assertNotEqual(
            goal_authority.maintenance_goal_digest(get_goal(root, "self-maintenance-core")), before
        )

    def test_evidence_source_is_bound(self):
        """Control 2: the research/backlog source is bound."""
        root, before = self.grant()
        self.edit_goal(root, research_or_work_backlog_source=".saipen/evidence/other.json")
        self.assert_invalidated(root)
        self.assertNotEqual(
            goal_authority.maintenance_goal_digest(get_goal(root, "self-maintenance-core")), before
        )


class P0HarmlessProgressIsNotPolicy(_Granted):
    """Control 3: recording progress preserves the grant."""

    def test_progress_and_observation_state_preserve_the_grant(self):
        root, before = self.grant()
        self.edit_goal(
            root,
            current_progress={"total": 10, "resolved": 40},
            last_evaluation="2026-11-05T00:00:00Z",
            last_successful_work="T-999",
            last_discovery="G-LIN-FUN_1",
            blockers=["an unrelated observation"],
            resume_metadata={"cursor_index": 7, "source_digest": "deadbeef"},
            completion_evidence={"note": "observed"},
            title="a renamed title",
            target_progress={"total": 3},
        )
        self.assertEqual(
            goal_authority.maintenance_goal_digest(get_goal(root, "self-maintenance-core")),
            before,
            "harmless progress must not change the granted policy identity",
        )
        self.assertEqual(_prove(root), [])
        self.assertTrue(maintenance_authority(root)["authorized"])
        self.assertEqual(granted_maintenance_policy_digest(root), before)


class P0LegacyGrantsFailClosed(_Granted):
    """Control 4: a legacy grant cannot silently authorize a wider policy."""

    def test_a_legacy_digest_is_not_reproducible_by_the_current_rule(self):
        """The pre-fix payload is a different string for the SAME goal file."""
        root, current = self.grant()
        goal = get_goal(root, "self-maintenance-core")
        legacy_payload = {key: goal.to_dict().get(key) for key in _LEGACY_IDENTITY_FIELDS}
        legacy_material = json.dumps(
            legacy_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        legacy = "sha256:" + hashlib.sha256(legacy_material.encode("utf-8")).hexdigest()
        self.assertNotEqual(legacy, current)
        self.assertNotEqual(goal_authority.MAINTENANCE_POLICY_VERSION, 1)

    def test_a_grant_committed_under_the_legacy_rule_fails_closed(self):
        """A capsule minted and applied under the v1 rule proves NOTHING once
        the policy identity is v2: no grandfathering, no silent upgrade."""
        root = _project(self, objective=MAINTENANCE_OBJECTIVE)
        _register_maintenance(root)
        st = state.parse_state(codec.read_doc(root / ".saipen/STATE.md"))
        with mock.patch.object(goal_authority, "MAINTENANCE_POLICY_VERSION", 1):
            proposal = goal_authority.propose_capsule(
                root, st, _read_history(root), until="continuous_maintenance"
            )
            self.assertTrue(proposal["ok"], proposal)
            applied = _witnessed_apply(self, root, proposal["capsule_text"])
            self.assertTrue(applied.ok, applied.to_dict())
        # The legacy rule is gone; the committed v1 grant must not carry authority.
        self.assert_invalidated(root)

    def test_the_version_tag_alone_separates_legacy_from_current(self):
        root, current = self.grant()
        goal = get_goal(root, "self-maintenance-core")
        with mock.patch.object(goal_authority, "MAINTENANCE_POLICY_VERSION", 1):
            under_v1 = goal_authority.maintenance_goal_digest(goal)
        self.assertNotEqual(under_v1, current)
        self.assertEqual(goal_authority.maintenance_goal_digest(goal), current)


class P0AdmissionToctou(_Granted):
    """Control 5: a policy edit between evaluation and admission refuses."""

    def test_drift_helper_detects_a_policy_change_in_the_window(self):
        root, bound = self.grant()
        self.assertEqual(
            goal_authority.maintenance_policy_drift(root, "self-maintenance-core", bound), [])
        self.edit_goal(root, admission_policy={"required_patch": "public-9.9.9"})
        drift = goal_authority.maintenance_policy_drift(root, "self-maintenance-core", bound)
        self.assertTrue(drift, "the changed policy must be reported as drift")
        self.assertIn("between evaluation and admission", drift[0])

    def test_a_disappeared_goal_is_reported_as_drift(self):
        root, bound = self.grant()
        self.assertTrue(delete_goal(root, "self-maintenance-core"))
        drift = goal_authority.maintenance_policy_drift(root, "self-maintenance-core", bound)
        self.assertTrue(drift)
        self.assertIn("disappeared", drift[0])

    def test_an_absent_bound_digest_performs_no_comparison(self):
        """An unbound admission is refused by the authority gate, not this check."""
        root, _ = self.grant()
        self.assertEqual(
            goal_authority.maintenance_policy_drift(root, "self-maintenance-core", None), [])

    def _ledger_campaign(self) -> tuple[Path, PersistentGoal, str]:
        """A granted campaign whose next admission comes from a real ledger."""
        root = _project(self, objective=MAINTENANCE_OBJECTIVE)
        (root / ".saipen" / "evidence").mkdir(parents=True, exist_ok=True)
        capture = root / "capture.bin"
        capture.write_bytes(b"T2023-CAPTURE")
        capture_sha = hashlib.sha256(capture.read_bytes()).hexdigest()
        ledger_rel = ".saipen/evidence/coverage.json"
        (root / ledger_rel).write_text(json.dumps({
            "counts": {"procedures": 100, "described_procedures": 10, "gap_procedures": 90},
            "sources": {"capture": {"sha256": capture_sha, "path": "capture.bin",
                                    "patch": "public-2.0.185"}},
            "gap": [{"rva": "0x1", "name": "FUN_1", "bytes": 40}],
        }), encoding="utf-8")
        goal = PersistentGoal(
            goal_id="self-maintenance-core",
            project_id=root.name,
            title="Continuous Self-Maintenance",
            objective=MAINTENANCE_OBJECTIVE,
            authorization_scope=SCOPE_MAINTENANCE,
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=ledger_rel,
            success_criteria={"capture_sha256": capture_sha, "target_patch": "public-2.0.185"},
        )
        register_goal(root, goal)
        st = state.parse_state(codec.read_doc(root / ".saipen/STATE.md"))
        proposal = goal_authority.propose_capsule(
            root, st, _read_history(root), until="continuous_maintenance"
        )
        self.assertTrue(proposal["ok"], proposal)
        applied = _witnessed_apply(self, root, proposal["capsule_text"])
        self.assertTrue(applied.ok, applied.to_dict())
        (root / ".saipen" / "BOARD.md").write_text(_EMPTY_BOARD, encoding="utf-8")
        # The fixture STATE carries T-1 as DOING; the emptied board must agree
        # or the admission floor refuses before the drift check matters.
        state_text = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        (root / ".saipen" / "STATE.md").write_text(
            state_text.replace("task: T-1", "task: none"), encoding="utf-8"
        )
        return root, goal, proposal["capsule"]["maintenance_goal_digest"]

    def test_the_admission_path_refuses_a_drifted_policy_before_the_write(self):
        """The real race, replayed in-process: the authority gate answers on the
        pre-edit policy, the policy then moves, and the admission write must
        never happen."""
        import saipen_engine.replenishment as R

        root, goal, bound = self._ledger_campaign()
        stale = maintenance_authority(root)
        self.assertTrue(stale["authorized"], stale)
        self.assertEqual(stale["policy_digest"], bound)
        # The race edit: an ADDITIONAL policy knob the current provider does
        # not read yet. The digest moves, evaluation still yields the same
        # candidate, so the refusal must come from the drift check, not from
        # the provider blocking first.
        goal.success_criteria = {**goal.success_criteria, "future_policy_knob": "stricter"}
        save_goal(root, goal)
        with mock.patch.object(R, "maintenance_authority", return_value=stale):
            result = R.replenish_from_goals(root, "fix", dry_run=False)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], "ADMISSION_POLICY_DRIFT", result)
        self.assertIn("between evaluation and admission", result["detail"])
        self.assertEqual(result["goal_id"], "self-maintenance-core")
        board = (root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        self.assertEqual(board, _EMPTY_BOARD, "no admission write may follow a drifted policy")

    def test_an_unchanged_policy_still_admits(self):
        """The non-regression: the drift check blocks only real movement. (The
        fixture STATE cannot satisfy the full admission floor, so the run may
        fail downstream of the drift check -- but it must never fail ON it.)"""
        import saipen_engine.replenishment as R

        root, _goal, bound = self._ledger_campaign()
        stale = maintenance_authority(root)
        self.assertEqual(stale["policy_digest"], bound)
        with mock.patch.object(R, "maintenance_authority", return_value=stale):
            result = R.replenish_from_goals(root, "fix", dry_run=False)
        self.assertNotEqual(result.get("status"), "ADMISSION_POLICY_DRIFT", result)
        self.assertNotIn("between evaluation and admission", str(result.get("detail")))


class P1RefusalIsNotAvailability(_Granted):
    """Control 9: an inner proposal refusal produces an outer refusal."""

    def test_inner_refusal_code_reaches_the_outer_result(self):
        hook = _load_hook()
        refusal = {
            "ok": False,
            "code": "PROPOSAL_UNAVAILABLE",
            "detail": "ValueError: the current goal pivot does not describe the "
                      "registered maintenance goal",
        }
        with mock.patch.object(
            hook, "_engine_reply",
            return_value={"ok": False, "code": "PROPOSAL_UNAVAILABLE", "document": refusal},
        ):
            outer = hook._goal_management_preview(
                REPO, REPO, "saipen goal propose", deadline=None
            )
        self.assertFalse(outer["ok"], outer)
        self.assertEqual(outer["code"], "PROPOSAL_UNAVAILABLE")
        self.assertIsNone(outer["preview"])
        self.assertFalse(outer["mutated"])
        self.assertTrue(outer["operator_action"])

    def test_an_inner_success_still_reports_a_read_only_preview(self):
        hook = _load_hook()
        document = {"ok": True, "goals": []}
        with mock.patch.object(
            hook, "_engine_reply",
            return_value={"ok": True, "code": None, "document": document},
        ):
            outer = hook._goal_management_preview(
                REPO, REPO, "saipen goal status", deadline=None
            )
        self.assertTrue(outer["ok"], outer)
        self.assertEqual(outer["code"], "GOAL_MANAGEMENT_PREVIEW")
        self.assertFalse(outer["mutated"])
        self.assertEqual(outer["preview"], document)

    def test_an_unreachable_engine_never_claims_availability(self):
        hook = _load_hook()
        with mock.patch.object(
            hook, "_engine_reply",
            return_value={"ok": False, "code": "PREVIEW_UNAVAILABLE", "detail": "no engine entry point"},
        ):
            outer = hook._goal_management_preview(
                REPO, REPO, "saipen goal propose", deadline=None
            )
        self.assertFalse(outer["ok"], outer)
        self.assertEqual(outer["code"], "PREVIEW_UNAVAILABLE")

    def test_a_raising_engine_never_claims_availability(self):
        hook = _load_hook()
        with mock.patch.object(hook, "_engine_reply", side_effect=RuntimeError("boom")):
            outer = hook._goal_management_preview(
                REPO, REPO, "saipen goal propose", deadline=None
            )
        self.assertFalse(outer["ok"], outer)
        self.assertEqual(outer["code"], "GOAL_MANAGEMENT_PREVIEW_FAILED")

    def test_live_proposal_refusal_is_a_refusal_outward(self):
        """End to end on THIS project: propose is refused AND says so."""
        hook = _load_hook()
        outer = hook._goal_management_preview(
            REPO, REPO, "saipen goal propose", deadline=None
        )
        proposal = goal_authority.propose_capsule(
            REPO,
            state.parse_state(codec.read_doc(REPO / ".saipen/STATE.md")),
            _read_history(REPO),
            until="continuous_maintenance",
        )
        if proposal["ok"]:
            self.assertTrue(outer["ok"], outer)
            self.assertEqual(outer["code"], "GOAL_MANAGEMENT_PREVIEW")
        else:
            # Whatever layer refuses (here the CLI capability gate answers
            # before the proposer), the outward answer is that layer's
            # refusal -- never a successful preview.
            self.assertFalse(outer["ok"], outer)
            self.assertTrue(outer["code"], outer)
            self.assertNotEqual(outer["code"], "GOAL_MANAGEMENT_PREVIEW")


class P0ApprovalPathNamesTheGoal(_Granted):
    """Control 10: the operator is handed the exact goal identity, not a guess."""

    def test_a_mismatched_pivot_hands_over_the_exact_objective_and_command(self):
        root = _project(self, objective="T-1599 (SRC-164): test1")
        _register_maintenance(root)
        st = state.parse_state(codec.read_doc(root / ".saipen/STATE.md"))
        result = goal_authority.propose_capsule(
            root, st, _read_history(root), until="continuous_maintenance"
        )
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "PROPOSAL_OBJECTIVE_MISMATCH")
        self.assertEqual(result["maintenance_goal_id"], "self-maintenance-core")
        self.assertEqual(result["required_objective"], MAINTENANCE_OBJECTIVE)
        self.assertIn(MAINTENANCE_OBJECTIVE, result["operator_action"])

    def test_the_named_command_actually_enters_the_goal(self):
        """The handed-over command is executable, not decorative."""
        from saipen_engine.cold_recovery import goal_objective_text

        root = _project(self, objective="T-1599 (SRC-164): test1")
        _register_maintenance(root)
        st = state.parse_state(codec.read_doc(root / ".saipen/STATE.md"))
        result = goal_authority.propose_capsule(
            root, st, _read_history(root), until="continuous_maintenance"
        )
        command = result["operator_action"].split("paste as your next message): ", 1)[1].strip()
        self.assertEqual(command, f"saipen goal {MAINTENANCE_OBJECTIVE}")
        self.assertEqual(
            goal_objective_text(command, protocol_dir=REPO / "saipen"), MAINTENANCE_OBJECTIVE
        )

    def test_a_wrong_goal_named_explicitly_still_fails_closed(self):
        root = _project(self, objective=MAINTENANCE_OBJECTIVE)
        _register_maintenance(root)
        with self.assertRaises(ValueError):
            goal_authority.maintenance_binding_fields(
                root, MAINTENANCE_OBJECTIVE, goal_id="some-other-goal"
            )


class P0ProviderHonoursThePolicy(_Granted):
    """The policy the grant is bound to is the one the provider obeys."""

    def _ledger_project(self) -> tuple[Path, str]:
        root = Path(tempfile.mkdtemp(prefix="t2023-pol-"))
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        (root / ".saipen" / "evidence").mkdir(parents=True)
        capture = root / "capture.bin"
        capture.write_bytes(b"T2023-PROVIDER-CAPTURE")
        capture_sha = hashlib.sha256(capture.read_bytes()).hexdigest()
        (root / ".saipen" / "evidence" / "coverage.json").write_text(json.dumps({
            "counts": {"procedures": 10, "described_procedures": 10, "gap_procedures": 0},
            "sources": {"capture": {"sha256": capture_sha, "path": "capture.bin",
                                    "patch": "public-2.0.185"}},
        }), encoding="utf-8")
        return root, capture_sha

    def test_disabling_independent_verification_changes_the_provider_verdict(self):
        """The measured effect: DISCOVERY_REQUIRED -> SATISFIED. That is why the
        policy, not merely the identity, has to be inside the grant."""
        root, capture_sha = self._ledger_project()
        common = dict(
            goal_id="G", project_id=root.name, title="t", objective="o",
            evidence_provider="evidence_gap_ledger",
            research_or_work_backlog_source=".saipen/evidence/coverage.json",
        )
        strict = PersistentGoal(
            success_criteria={"capture_sha256": capture_sha, "target_patch": "public-2.0.185",
                              "require_independent_verification": True},
            **common,
        )
        relaxed = PersistentGoal(
            success_criteria={"capture_sha256": capture_sha, "target_patch": "public-2.0.185",
                              "require_independent_verification": False},
            **common,
        )
        provider = EvidenceGapLedgerProvider()
        self.assertEqual(provider.evaluate(root, strict).satisfaction_status,
                         STATUS_DISCOVERY_REQUIRED)
        self.assertEqual(provider.evaluate(root, relaxed).satisfaction_status,
                         STATUS_SATISFIED)
        self.assertNotEqual(
            goal_authority.maintenance_goal_digest(strict),
            goal_authority.maintenance_goal_digest(relaxed),
            "the two policies must not share a grant identity",
        )


def setUpModule():
    from test_hermetic_env import isolate_host_session

    isolate_host_session()


if __name__ == "__main__":
    unittest.main()
