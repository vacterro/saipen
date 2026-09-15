"""T-1324: a proven-stale `STATE.blocker` must be repairable while braked.

The AUDAPACK deadlock class: CORE keeps `STATE.blocker` non-empty only in
`phase: BLOCKED`, but a legacy run persisted a non-empty blocker while the
phase was an ordinary ACTIVE phase. `binding_brake` -- the single hard-stop
truth shared by the router and the admission guard -- then refused EVERY
consequential tool as `WAIT_BLOCKED`, and no canonical verb owned clearing the
field: `recover` reconciled everything except the blocker and certified CLEAN.
Known root, hard brake, no legal repair action.

These tests prove the closed classification and the reachable repair:

  * active phase + no `## BLOCKED` board ticket + no recognised gate class ->
    SAFE_CANONICAL_REPAIR: the exact key is removed, the original STATE bytes
    are preserved as recovery evidence, and the work resumes;
  * live board block authority or a recognised gate class ->
    OPERATOR_DECISION_REQUIRED: refused with ZERO bytes written;
  * idempotent: a second pass is CLEAN.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from saipen_engine.reconcile import (
    _board_adoption_repairs,
    _legacy_next_action,
    _state_blocker_repairs,
    reconcile_protocol_state,
)
from saipen_engine.fleet import (
    CLASS_BLOCKED,
    CLASS_CONFLICT,
    CLASS_NON_SAIPEN,
    CLASS_SAFE,
    CLASS_UNBOUND,
    CLASS_VALID,
    _result,
    preflight,
)
from saipen_engine.state import binding_brake

from test_hermetic_env import isolate_host_session


def setUpModule() -> None:
    # An outer host session (SAIPEN_PROJECT_ROOT/LINEAGE, SAIPEN_AGENT, ...)
    # must never bind this module's disposable fixtures (test_hermetic_env).
    isolate_host_session()


_STALE = "legacy upstream outage -- no lifecycle authority"

class BlockerClassificationTests(unittest.TestCase):
    """The pure closed rule, independent of any project on disk."""

    def test_empty_and_none_own_no_repair(self):
        self.assertEqual(_state_blocker_repairs({"phase": "SCOUT", "blocker": ""}, {}), [])
        self.assertEqual(_state_blocker_repairs({"phase": "SCOUT", "blocker": "none"}, {}), [])
        self.assertEqual(_state_blocker_repairs({"phase": "SCOUT"}, {}), [])

    def test_blocked_phase_is_consistent(self):
        self.assertEqual(
            _state_blocker_repairs({"phase": "BLOCKED", "blocker": _STALE}, {}), []
        )

    def test_an_out_of_enum_phase_is_the_phase_repairers_business(self):
        self.assertEqual(
            _state_blocker_repairs({"phase": "IMPL", "blocker": _STALE}, {}), []
        )

    def test_a_malformed_blocker_is_not_read_as_stale(self):
        self.assertEqual(_state_blocker_repairs({"phase": "SCOUT", "blocker": 7}, {}), [])
        self.assertEqual(_state_blocker_repairs({"phase": "SCOUT", "blocker": ["x"]}, {}), [])

    def test_an_active_phase_without_authority_is_proven_stale(self):
        repairs = _state_blocker_repairs({"phase": "SCOUT", "blocker": _STALE}, {})
        self.assertEqual(len(repairs), 1, repairs)
        self.assertEqual(repairs[0]["to"], "none")
        self.assertEqual(repairs[0]["field"], "blocker")
        self.assertNotIn("refuse", repairs[0])

    def test_a_recognised_gate_class_requires_an_operator_decision(self):
        gates = (
            "BLOCKED_EXTERNAL -- waiting on vendor",
            "HELD -- until v8",
            "WAIT_USER_CONFIRMATION",
        )
        for blocker in gates:
            with self.subTest(blocker=blocker):
                repairs = _state_blocker_repairs({"phase": "SCOUT", "blocker": blocker}, {})
                self.assertEqual(len(repairs), 1, repairs)
                self.assertTrue(repairs[0]["refuse"], repairs)
                self.assertNotIn("remove", repairs[0])
                self.assertIn("OPERATOR_DECISION_REQUIRED", repairs[0]["reason"])

    def test_a_live_board_block_refuses(self):
        board = {
            "tickets": {
                "T-001": {
                    "id": "T-001",
                    "section": "## BLOCKED",
                    "fields": {"blocker": "HELD -- x"},
                }
            }
        }
        repairs = _state_blocker_repairs({"phase": "SCOUT", "blocker": _STALE}, board)
        self.assertEqual(len(repairs), 1, repairs)
        self.assertTrue(repairs[0]["refuse"], repairs)
        self.assertIn("T-001", repairs[0]["reason"])


_LOG = (
    "# Log\n"
    "- 14.09.26 00:00 [E-0001] [agent: tester] "
    f"[op: transition-{'a' * 32}] RUN: transition to SCOUT\n"
)


def _project(
    blocker: str = _STALE,
    board_blocked: bool = False,
    next_action: str = "PHASE SCOUT T-001",
) -> Path:
    root = Path(tempfile.mkdtemp(prefix="t1324-blocker-"))
    (root / ".saipen").mkdir(parents=True)
    (root / ".saipen" / "LOG.md").write_text(_LOG, encoding="utf-8")
    (root / ".saipen" / "STATE.md").write_text(
        "---\n"
        "phase: SCOUT\n"
        "task: T-001\n"
        f'next_action: "{next_action}"\n'
        f'blocker: "{blocker}"\n'
        "transition_from: DONE\n"
        "saipen_version: 7\n"
        "schema_version: 3\n"
        "last_event: 1\n"
        "style_contract: ded-4ae736e4\n"
        "agent: tester\n"
        "mode: full\n"
        "updated: 2026-09-14T00:00:00Z\n"
        "execution_intent: normal\n"
        "---\n",
        encoding="utf-8",
    )
    blocked = (
        "## BLOCKED\n- [ ] T-002 [P1] gate | verify: test | blocker: HELD -- x\n"
        if board_blocked
        else "## BLOCKED\n"
    )
    import datetime

    claim_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (root / ".saipen" / "BOARD.md").write_text(
        "## DOING\n"
        f"- [/] T-001 [P1] fix | verify: test | owner: tester | claim_time: {claim_time}\n"
        "## TODO\n## DONE\n" + blocked,
        encoding="utf-8",
    )
    return root


class StaleBlockerEndToEndTests(unittest.TestCase):
    """AUDAPACK shape through the real entry point, on a real tree."""

    def _make_project(self, **kwargs) -> Path:
        root = _project(**kwargs)
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        return root

    def _state(self, root: Path) -> str:
        return (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")

    def test_the_brake_binds_before_the_repair(self):
        root = self._make_project()
        from saipen_engine.state import parse_state_or_error

        state, _ = parse_state_or_error(self._state(root))
        self.assertIsNotNone(binding_brake(state))

    def test_the_stale_blocker_is_repaired_and_the_brake_lifts(self):
        root = self._make_project()
        original = (root / ".saipen" / "STATE.md").read_bytes()

        planned = reconcile_protocol_state(root, "tester", dry_run=True)
        self.assertTrue(planned["ok"], planned)
        self.assertEqual(planned["code"], "REPAIR_REQUIRED", planned)
        self.assertEqual([r["field"] for r in planned["changed"]["state"]], ["blocker"])

        applied = reconcile_protocol_state(root, "tester", dry_run=False)
        self.assertTrue(applied["ok"], applied)
        self.assertEqual(applied["code"], "REPAIRED", applied)

        from saipen_engine.state import parse_state_or_error

        state, error = parse_state_or_error(self._state(root))
        self.assertEqual(error, None)
        self.assertEqual(state.get("blocker"), "none")
        self.assertIsNone(binding_brake(state))

        # The DEC records the removed value and the original bytes survive.
        log = (root / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("blocker", log)
        artifacts = sorted((root / ".saipen" / "recovery").rglob("*.STATE.md"))
        self.assertEqual(len(artifacts), 1, artifacts)
        self.assertEqual(artifacts[0].read_bytes(), original)

    def test_the_repair_is_idempotent(self):
        root = self._make_project()
        self.assertTrue(reconcile_protocol_state(root, "tester")["ok"])
        state_after = (root / ".saipen" / "STATE.md").read_bytes()
        again = reconcile_protocol_state(root, "tester")
        self.assertEqual(again["code"], "CLEAN", again)
        self.assertEqual((root / ".saipen" / "STATE.md").read_bytes(), state_after)
        self.assertEqual(
            len(sorted((root / ".saipen" / "recovery").rglob("*.STATE.md"))), 1
        )

    def test_a_real_operator_gate_refuses_with_zero_writes(self):
        root = self._make_project(blocker="BLOCKED_EXTERNAL -- vendor cert pending")
        before = {
            name: (root / ".saipen" / name).read_bytes()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        }
        result = reconcile_protocol_state(root, "tester", dry_run=False)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "RECONCILE_REAUTH_REQUIRED", result)
        for name, raw in before.items():
            self.assertEqual((root / ".saipen" / name).read_bytes(), raw, name)
        self.assertFalse(list((root / ".saipen" / "recovery").rglob("*.STATE.md")))


SAIPEN_CLI = Path(__file__).resolve().parent / "saipen.py"


class StaleBlockerCliTests(unittest.TestCase):
    """The mission's exact witness: `saipen recover` on a braked known root."""

    def test_recover_lifts_a_proven_stale_brake(self):
        root = _project()
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        env = {**os.environ}
        env.pop("PWD", None)
        env.pop("OLDPWD", None)
        run = subprocess.run(
            [sys.executable, str(SAIPEN_CLI), "recover"],
            cwd=str(root), capture_output=True, text=True, env=env, timeout=600,
        )
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        first = (run.stdout + run.stderr).strip().splitlines()[0]
        self.assertEqual(first, "code: REPAIRED", run.stdout + run.stderr)
        state_text = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        self.assertIn("\nblocker: none\n", state_text)

    def test_recover_on_an_operator_gate_refuses(self):
        root = _project(blocker="BLOCKED_EXTERNAL -- vendor cert pending")
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        before = (root / ".saipen" / "STATE.md").read_bytes()
        env = {**os.environ}
        env.pop("PWD", None)
        env.pop("OLDPWD", None)
        run = subprocess.run(
            [sys.executable, str(SAIPEN_CLI), "recover"],
            cwd=str(root), capture_output=True, text=True, env=env, timeout=600,
        )
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual((root / ".saipen" / "STATE.md").read_bytes(), before)


def _bound_project(blocker: str = _STALE) -> tuple[Path, str]:
    from saipen_engine.paths import identity_file_content, new_project_lineage

    root = _project(blocker=blocker)
    lineage = new_project_lineage()
    (root / ".saipen" / "IDENTITY.md").write_text(
        identity_file_content(lineage), encoding="utf-8"
    )
    return root, lineage


class RemediationResultTests(unittest.TestCase):
    """Target G: every classification names its legal next move.

    The machine-readable half of the deadlock: a host that sees
    `BOUND_RECOVERY_REQUIRED_BLOCKED` plus a `reason_code` still needs to know
    whether IT can act, whether a human must decide, and what to run. The
    invariant these tests pin is closed: a braked classification ALWAYS offers
    an automatic repair or an operator decision, and always a canonical command.
    """

    _CLASSES = (
        CLASS_NON_SAIPEN,
        CLASS_UNBOUND,
        CLASS_VALID,
        CLASS_SAFE,
        CLASS_BLOCKED,
        CLASS_CONFLICT,
    )
    _CODES = (
        "CLEAN",
        "REPAIR_REQUIRED",
        "RECOVERY_REQUIRED",
        "RECONCILE_REAUTH_REQUIRED",
        "CORRUPT_JOURNAL",
        "WAIT_BLOCKED",
        "SOMETHING_UNRECOGNISED",
    )

    def test_every_result_carries_the_remediation_facts(self):
        for classification in self._CLASSES:
            for code in self._CODES:
                with self.subTest(classification=classification, code=code):
                    result = _result(classification, reason_code=code, reason="x")
                    for key in (
                        "needs_local_mutation",
                        "safe_auto_repair_available",
                        "operator_decision_available",
                        "canonical_next_command",
                        "read_only",
                        "blocking_surface",
                        "blocking_field",
                        "evidence_reference",
                    ):
                        self.assertIn(key, result)

    def test_a_blocked_state_surface_names_the_blocker_field(self):
        snapshot = {"state": {"phase": "SCOUT", "blocker": "legacy prose"}}
        result = _result(
            CLASS_BLOCKED, reason_code="WAIT_BLOCKED", reason="x", snapshot=snapshot
        )
        self.assertEqual(result["blocking_surface"], "state")
        self.assertEqual(result["blocking_field"], "blocker")
        self.assertEqual(result["evidence_reference"], ".saipen/STATE.md")
        self.assertTrue(result["read_only"])

    def test_a_braked_classification_is_never_a_dead_end(self):
        for classification in (CLASS_SAFE, CLASS_BLOCKED):
            for code in (*self._CODES, "ANYTHING_ELSE"):
                with self.subTest(classification=classification, code=code):
                    result = _result(classification, reason_code=code, reason="x")
                    self.assertTrue(
                        result["safe_auto_repair_available"]
                        or result["operator_decision_available"],
                        result,
                    )
                    self.assertTrue(result["canonical_next_command"], result)

    def test_a_legacy_unrecognised_block_code_still_has_a_route(self):
        result = _result(CLASS_BLOCKED, reason_code="LEGACY_UNKNOWN", reason="x")
        self.assertEqual(result["canonical_next_command"], "saipen recover")
        self.assertTrue(result["operator_decision_available"])

    def test_the_conflict_class_owns_no_repair_route(self):
        result = _result(CLASS_CONFLICT, reason_code="PROJECT_BINDING_INVALID", reason="x")
        self.assertIsNone(result["canonical_next_command"])
        self.assertFalse(result["safe_auto_repair_available"])

    def test_a_clean_valid_result_routes_to_continue(self):
        result = _result(CLASS_VALID, reason_code="CLEAN", reason="x")
        self.assertEqual(result["canonical_next_command"], "saipen continue")
        self.assertFalse(result["needs_local_mutation"])


class RemediationPreflightTests(unittest.TestCase):
    """The two braked shapes, classified end-to-end and read-only."""

    def _run(self, **kwargs):
        root, lineage = _bound_project(**kwargs)
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        return preflight(root, host_root=root, host_lineage=lineage)

    def test_a_proven_stale_brake_is_safe_with_an_automatic_route(self):
        result = self._run()
        self.assertEqual(result["classification"], CLASS_SAFE, result)
        self.assertEqual(result["reason_code"], "REPAIR_REQUIRED", result)
        self.assertTrue(result["safe_auto_repair_available"], result)
        self.assertTrue(result["needs_local_mutation"], result)
        self.assertEqual(result["canonical_next_command"], "saipen recover")

    def test_an_operator_gate_is_blocked_and_requires_a_decision(self):
        result = self._run(blocker="BLOCKED_EXTERNAL -- vendor cert pending")
        self.assertEqual(result["classification"], CLASS_BLOCKED, result)
        self.assertEqual(result["reason_code"], "RECONCILE_REAUTH_REQUIRED", result)
        self.assertTrue(result["operator_decision_available"], result)
        self.assertFalse(result["safe_auto_repair_available"], result)
        # Target C/G: the exact reachable operator-decision verb, not a generic
        # unblock and not a bare `recover` that would only refuse again.
        self.assertEqual(
            result["canonical_next_command"],
            'saipen recover resolve-blocker "<decision>"',
            result,
        )
        self.assertEqual(result["blocking_surface"], "state")
        self.assertEqual(result["blocking_field"], "blocker")
        self.assertTrue(result["read_only"])


class DiagnosisModeTests(unittest.TestCase):
    """Target I: a braked state is diagnosed read-only, never probed.

    A host that holds a refused consequential action must not spray
    `stop`/`transition`/`goal`/`ticket`/Bash/Edit/Write to discover what is
    admitted. The result carries an explicit mode token so that behaviour is
    machine-enforced rather than left to prose.
    """

    def test_a_no_auto_repair_block_is_read_only_diagnosis(self):
        result = _result(CLASS_BLOCKED, reason_code="WAIT_BLOCKED", reason="x")
        self.assertEqual(result["diagnosis"], "READ_ONLY_DIAGNOSIS_ONLY", result)
        self.assertTrue(result["read_only_diagnosis_only"])
        self.assertIn("saipen stop", result["forbidden_probes"])
        self.assertIn("Bash", result["forbidden_probes"])
        self.assertIn("saipen recover", result["instruction"])

    def test_a_safe_auto_repair_is_not_read_only(self):
        result = _result(CLASS_SAFE, reason_code="REPAIR_REQUIRED", reason="x")
        self.assertEqual(result["diagnosis"], "RUN_CANONICAL_REPAIR", result)
        self.assertNotIn("read_only_diagnosis_only", result)
        self.assertEqual(result["forbidden_probes"], [])

    def test_valid_and_non_saipen_carry_no_diagnosis_mode(self):
        for classification in (CLASS_VALID, CLASS_NON_SAIPEN):
            with self.subTest(classification=classification):
                result = _result(classification, reason_code="CLEAN", reason="x")
                self.assertEqual(result["diagnosis"], "NONE", result)
                self.assertEqual(result["forbidden_probes"], [])

    def test_the_operator_gate_names_the_only_sanctioned_mutation(self):
        result = _result(
            CLASS_BLOCKED, reason_code="RECONCILE_REAUTH_REQUIRED", reason="x",
            snapshot={"state": {"phase": "SCOUT", "blocker": "BLOCKED_EXTERNAL"}},
        )
        self.assertEqual(result["diagnosis"], "READ_ONLY_DIAGNOSIS_ONLY", result)
        self.assertIn("resolve-blocker", result["instruction"])


class LegacyNextActionClassificationTests(unittest.TestCase):
    """The grammar predicate is the fast_check predicate, never a new rule."""

    def test_legal_actions_are_not_legacy(self):
        for na in ("PHASE SCOUT T-001", "WAIT: operator input", "saipen continue",
                   "RUN: tests", "RESUME: build"):
            with self.subTest(na=na):
                self.assertFalse(_legacy_next_action(na))

    def test_freeform_prose_is_legacy(self):
        for na in ("work on the legacy thing", "keep going", "T-168: finish the task"):
            with self.subTest(na=na):
                self.assertTrue(_legacy_next_action(na))

    def test_a_malformed_phase_action_is_legacy(self):
        self.assertTrue(_legacy_next_action("PHASE IMPL T-001"))

    def test_an_empty_action_is_repaired_when_provable(self):
        root = _project(next_action="")
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        result = reconcile_protocol_state(root, "tester", dry_run=True)
        self.assertEqual(result["code"], "REPAIR_REQUIRED", result)
        fields = [r["field"] for r in result["changed"]["state"]]
        self.assertIn("next_action", fields)


class LegacyNextActionRepairTests(unittest.TestCase):
    """Target D end-to-end: a provable route is synthesized, prose preserved."""

    def _make(self, **kwargs) -> Path:
        root = _project(**kwargs)
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        return root

    def test_a_provable_legacy_action_is_repaired(self):
        root = self._make(next_action="keep working on T-168 the legacy way")
        original = (root / ".saipen" / "STATE.md").read_bytes()

        planned = reconcile_protocol_state(root, "tester", dry_run=True)
        self.assertTrue(planned["ok"], planned)
        self.assertEqual(planned["code"], "REPAIR_REQUIRED", planned)
        fields = [r["field"] for r in planned["changed"]["state"]]
        self.assertIn("next_action", fields)

        applied = reconcile_protocol_state(root, "tester", dry_run=False)
        self.assertTrue(applied["ok"], applied)
        self.assertEqual(applied["code"], "REPAIRED", applied)
        state = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        self.assertIn("next_action: \"PHASE SCOUT T-001\"", state)
        # The original prose survives in the forensic copy.
        artifacts = sorted((root / ".saipen" / "recovery").rglob("*.STATE.md"))
        self.assertEqual(len(artifacts), 1, artifacts)
        self.assertEqual(artifacts[0].read_bytes(), original)
        self.assertEqual(reconcile_protocol_state(root, "tester")["code"], "CLEAN")

    def test_an_ambiguous_legacy_action_refuses_with_zero_writes(self):
        root = self._make(next_action="do the important legacy thing")
        (root / ".saipen" / "STATE.md").write_text(
            (root / ".saipen" / "STATE.md")
            .read_text(encoding="utf-8")
            .replace("task: T-001", "task: T-999"),
            encoding="utf-8",
        )
        before = {
            name: (root / ".saipen" / name).read_bytes()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        }
        result = reconcile_protocol_state(root, "tester", dry_run=False)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "RECONCILE_REAUTH_REQUIRED", result)
        self.assertEqual(result["terminal_disposition"], "RECOVERY_BLOCKED", result)
        self.assertFalse(result["needs_local_mutation"], result)
        self.assertFalse(result["operator_decision_available"], result)
        self.assertIsNone(result["canonical_next_command"], result)
        self.assertEqual(result["blocking_surface"], "state", result)
        self.assertEqual(result["blocking_field"], "next_action", result)
        self.assertEqual(result["evidence_reference"], ".saipen/STATE.md", result)
        for name, raw in before.items():
            self.assertEqual((root / ".saipen" / name).read_bytes(), raw, name)
        self.assertFalse(list((root / ".saipen" / "recovery").rglob("*.STATE.md")))

    def test_fleet_does_not_route_ambiguous_truth_back_to_bare_recover(self):
        root, lineage = _bound_project(blocker="none")
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        state_path = root / ".saipen" / "STATE.md"
        state_path.write_text(
            state_path.read_text(encoding="utf-8")
            .replace("task: T-001", "task: T-999")
            .replace(
                'next_action: "PHASE SCOUT T-001"',
                'next_action: "do the important legacy thing"',
            ),
            encoding="utf-8",
        )

        result = preflight(root, host_root=root, host_lineage=lineage)

        self.assertEqual(result["classification"], CLASS_BLOCKED, result)
        self.assertEqual(result["reason_code"], "RECONCILE_REAUTH_REQUIRED", result)
        self.assertEqual(result["terminal_disposition"], "RECOVERY_BLOCKED", result)
        self.assertFalse(result["needs_local_mutation"], result)
        self.assertFalse(result["operator_decision_available"], result)
        self.assertIsNone(result["canonical_next_command"], result)
        self.assertEqual(result["blocking_field"], "next_action", result)

    def test_public_recover_emits_the_same_terminal_remediation_fields(self):
        root = self._make(next_action="do the important legacy thing")
        state_path = root / ".saipen" / "STATE.md"
        state_path.write_text(
            state_path.read_text(encoding="utf-8").replace("task: T-001", "task: T-999"),
            encoding="utf-8",
        )
        run = subprocess.run(
            [
                sys.executable,
                str(SAIPEN_CLI),
                "recover",
                "--json",
                "--project-root",
                str(root),
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=600,
        )
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual(result["terminal_disposition"], "RECOVERY_BLOCKED", result)
        self.assertFalse(result["needs_local_mutation"], result)
        self.assertFalse(result["operator_decision_available"], result)
        self.assertIsNone(result["canonical_next_command"], result)
        self.assertEqual(result["blocking_surface"], "state", result)
        self.assertEqual(result["blocking_field"], "next_action", result)
        self.assertEqual(result["evidence_reference"], ".saipen/STATE.md", result)


_LEGACY_LOG = (
    "# Log\n"
    "- 14.09.26 00:00 [E-0001] [T-001] [agent: tester] "
    "[op: ticket-00000000000000000000000000000001] DEC: ticket added\n"
    "- 14.09.26 00:01 [E-0002] [agent: tester] "
    "[op: transition-00000000000000000000000000000002] RUN: transition to SCOUT\n"
)

_LEGACY_TICKET_LINE = (
    "- [ ] T-777 [P1] legacy ticket recorded before allocation identity "
    "existed | verify: test\n"
)


def _legacy_project() -> Path:
    """A real allocation frontier (T-001) plus one unattested workable record.

    T-001 is named by a canonical `[T-###]` event, so the history HAS an
    allocation authority. T-777 sits in `## TODO` with no such event: the exact
    SAITULS shape -- a legacy record the allocation-identity gate refuses and
    the mutating verbs cannot legally allocate behind the brake.
    """
    import datetime

    root = Path(tempfile.mkdtemp(prefix="t1324-legacy-"))
    (root / ".saipen").mkdir(parents=True)
    (root / ".saipen" / "LOG.md").write_text(_LEGACY_LOG, encoding="utf-8")
    (root / ".saipen" / "STATE.md").write_text(
        "---\n"
        "phase: SCOUT\n"
        "task: T-001\n"
        'next_action: "PHASE SCOUT T-001"\n'
        'blocker: "none"\n'
        "transition_from: DONE\n"
        "saipen_version: 7\n"
        "schema_version: 3\n"
        "last_event: 2\n"
        "style_contract: ded-4ae736e4\n"
        "agent: tester\n"
        "mode: full\n"
        "updated: 2026-09-14T00:00:00Z\n"
        "execution_intent: normal\n"
        "---\n",
        encoding="utf-8",
    )
    claim_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (root / ".saipen" / "BOARD.md").write_text(
        "## DOING\n"
        f"- [/] T-001 [P1] fix | verify: test | owner: tester | claim_time: {claim_time}\n"
        "## TODO\n" + _LEGACY_TICKET_LINE + "## DONE\n## BLOCKED\n",
        encoding="utf-8",
    )
    return root


class LegacyAdoptionClassificationTests(unittest.TestCase):
    """The pure closed rule for Target E, independent of disk."""

    def test_no_allocation_frontier_means_no_adoption_authority(self):
        import types

        board = {"tickets": {"T-777": {"section": "## TODO"}}}
        history = types.SimpleNamespace(events=[], max_ticket_id=0)
        self.assertEqual(_board_adoption_repairs(board, history, ("T-777",)), [])
        self.assertEqual(_board_adoption_repairs(board, None, ("T-777",)), [])

    def test_an_attested_ticket_owns_no_repair(self):
        import types

        board = {"tickets": {"T-001": {"section": "## DOING"}}}
        history = types.SimpleNamespace(
            events=[{"event": 1, "ticket": "T-001"}], max_ticket_id=1
        )
        self.assertEqual(_board_adoption_repairs(board, history, ("T-001",)), [])

    def test_a_named_unattested_record_is_an_adoption(self):
        import types

        board = {"tickets": {"T-777": {"section": "## TODO"}}}
        history = types.SimpleNamespace(
            events=[{"event": 1, "ticket": "T-001"}], max_ticket_id=1
        )
        repairs = _board_adoption_repairs(board, history, ("T-777",))
        self.assertEqual(len(repairs), 1, repairs)
        self.assertEqual(repairs[0]["kind"], "adopt")
        self.assertEqual(repairs[0]["ticket"], "T-777")
        self.assertNotIn("refuse", repairs[0])

    def test_an_unnamed_unattested_record_refuses(self):
        import types

        board = {"tickets": {"T-777": {"section": "## TODO"}}}
        history = types.SimpleNamespace(
            events=[{"event": 1, "ticket": "T-001"}], max_ticket_id=1
        )
        repairs = _board_adoption_repairs(board, history, ())
        self.assertEqual(len(repairs), 1, repairs)
        self.assertTrue(repairs[0]["refuse"], repairs)
        self.assertIn("OPERATOR_DECISION_REQUIRED", repairs[0]["reason"])

    def test_a_parked_record_is_reachable_too(self):
        """T-1336: a parked record is still a record the validator judges.

        This case previously asserted the opposite -- that a `## BLOCKED`
        record owns no adoption -- on the reasoning that parked Work is not
        workable. But `validate.py` arms the allocation-identity check over
        EVERY section, so "no adoption" did not mean "not judged": it meant a
        RED gate with no operation able to see it. Reproduced on this very
        repository by nine parked records, which pinned the pre-commit gate
        closed, held the source dirty, and left all six installed agent homes
        stale. Workability decides what to DO with a record; it never decides
        whether a hard stop has an exit.
        """
        import types

        board = {"tickets": {"T-777": {"section": "## BLOCKED"}}}
        history = types.SimpleNamespace(
            events=[{"event": 1, "ticket": "T-001"}], max_ticket_id=1
        )
        refused = _board_adoption_repairs(board, history, ())
        self.assertEqual(len(refused), 1, refused)
        self.assertTrue(refused[0]["refuse"], refused)
        self.assertIn("OPERATOR_DECISION_REQUIRED", refused[0]["reason"])
        adopted = _board_adoption_repairs(board, history, ("T-777",))
        self.assertEqual(len(adopted), 1, adopted)
        self.assertEqual(adopted[0]["kind"], "adopt")
        self.assertNotIn("refuse", adopted[0])


class LegacyAdoptionRepairTests(unittest.TestCase):
    """Target E end-to-end: adoption is NOW-dated, truthful and idempotent."""

    def _make(self) -> Path:
        root = _legacy_project()
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        return root

    def _read(self, root: Path, name: str) -> str:
        return (root / ".saipen" / name).read_text(encoding="utf-8")

    def test_an_unattested_record_refuses_with_zero_writes(self):
        root = self._make()
        before = {
            name: (root / ".saipen" / name).read_bytes()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        }
        result = reconcile_protocol_state(root, "tester", dry_run=False)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "RECONCILE_REAUTH_REQUIRED", result)
        self.assertTrue(any("T-777" in r["reason"] for r in result["refused"]), result)
        for name, raw in before.items():
            self.assertEqual((root / ".saipen" / name).read_bytes(), raw, name)

    def test_fleet_names_the_exact_adoption_command(self):
        root = self._make()
        from saipen_engine.paths import identity_file_content, new_project_lineage

        lineage = new_project_lineage()
        (root / ".saipen" / "IDENTITY.md").write_text(
            identity_file_content(lineage), encoding="utf-8"
        )

        result = preflight(root, host_root=root, host_lineage=lineage)

        self.assertEqual(result["classification"], CLASS_BLOCKED, result)
        self.assertTrue(result["operator_decision_available"], result)
        self.assertEqual(
            result["canonical_next_command"],
            "saipen recover --adopt-legacy T-777",
            result,
        )
        self.assertIsNone(result.get("terminal_disposition"), result)

    def test_an_operator_adoption_lands_a_now_dated_dec(self):
        root = self._make()
        applied = reconcile_protocol_state(root, "tester", adopt_legacy=("T-777",))
        self.assertTrue(applied["ok"], applied)
        self.assertEqual(applied["code"], "REPAIRED", applied)
        self.assertEqual(applied["adopted"], ["T-777"], applied)

        log = self._read(root, "LOG.md")
        self.assertIn("LEGACY_ADOPTED T-777", log)
        # The original record survives byte-for-byte: adoption is additive.
        self.assertIn(_LEGACY_TICKET_LINE.strip(), self._read(root, "BOARD.md"))

    def test_no_historical_allocation_event_is_fabricated(self):
        root = self._make()
        self.assertTrue(reconcile_protocol_state(root, "tester", adopt_legacy=("T-777",))["ok"])
        lines = [
            line
            for line in self._read(root, "LOG.md").splitlines()
            if "[T-777]" in line
        ]
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("DEC:", lines[0])
        self.assertIn("LEGACY_ADOPTED T-777", lines[0])
        # Append-only: the prior history ended at event 2, so adoption is E-3.
        self.assertIn("[E-3]", lines[0])
        # And it never claims to have created or allocated the ticket.
        self.assertNotIn("ticket added", lines[0])
        self.assertNotIn("allocated", lines[0])

    def test_adoption_is_idempotent(self):
        root = self._make()
        self.assertTrue(reconcile_protocol_state(root, "tester", adopt_legacy=("T-777",))["ok"])
        log_after = self._read(root, "LOG.md")
        self.assertEqual(log_after.count("LEGACY_ADOPTED T-777"), 1)
        again = reconcile_protocol_state(root, "tester", adopt_legacy=("T-777",))
        self.assertEqual(again["code"], "CLEAN", again)
        self.assertEqual(self._read(root, "LOG.md"), log_after)

    def test_an_unknown_adopt_id_does_not_launder_the_record(self):
        root = self._make()
        before = (root / ".saipen" / "LOG.md").read_bytes()
        result = reconcile_protocol_state(root, "tester", adopt_legacy=("T-999",))
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "RECONCILE_REAUTH_REQUIRED", result)
        self.assertTrue(any("T-777" in r["reason"] for r in result["refused"]), result)
        self.assertEqual((root / ".saipen" / "LOG.md").read_bytes(), before)


class LegacyAdoptionCliTests(unittest.TestCase):
    """The operator's exact reachable verb: `recover --adopt-legacy`."""

    def _run(self, root: Path, *extra: str):
        env = {**os.environ}
        env.pop("PWD", None)
        env.pop("OLDPWD", None)
        return subprocess.run(
            [sys.executable, str(SAIPEN_CLI), "recover", *extra],
            cwd=str(root), capture_output=True, text=True, env=env, timeout=600,
        )

    def _make(self) -> Path:
        root = _legacy_project()
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        return root

    def test_recover_without_adoption_refuses_the_legacy_record(self):
        root = self._make()
        run = self._run(root)
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("RECONCILE_REAUTH_REQUIRED", run.stdout + run.stderr)

    def test_recover_adopts_the_named_legacy_ticket(self):
        root = self._make()
        run = self._run(root, "--adopt-legacy", "T-777")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        first = (run.stdout + run.stderr).strip().splitlines()[0]
        self.assertEqual(first, "code: REPAIRED", run.stdout + run.stderr)
        log = (root / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("LEGACY_ADOPTED T-777", log)

    def test_the_closed_grammar_refuses_a_missing_id(self):
        root = self._make()
        run = self._run(root, "--adopt-legacy")
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertIn("VALIDATION_FAILED", run.stdout + run.stderr)

    def test_the_closed_grammar_refuses_a_non_ticket_id(self):
        root = self._make()
        run = self._run(root, "--adopt-legacy", "777")
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertIn("VALIDATION_FAILED", run.stdout + run.stderr)

    def test_an_unknown_adopt_id_leaves_the_record_blocked(self):
        root = self._make()
        run = self._run(root, "--adopt-legacy", "T-999")
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("RECONCILE_REAUTH_REQUIRED", run.stdout + run.stderr)
        self.assertNotIn(
            "LEGACY_ADOPTED", (root / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        )


class OperatorBlockerDecisionTests(unittest.TestCase):
    """Target C: the operator-authorized, evidence-recording blocker clear.

    The gate refusal must never be a dead end: a real external/operator gate is
    preserved AND a specific canonical verb is exposed that records the
    operator's authority and clears only the field it owns. It is deliberately
    NOT a generic unblock: empty authority is refused, a live `## BLOCKED` board
    ticket is not owned here, and phase BLOCKED is not this verb's business.
    """

    _GATE = "BLOCKED_EXTERNAL -- vendor cert pending"

    def _make(self, **kwargs) -> Path:
        root = _project(**kwargs)
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        return root

    def _read(self, root: Path, name: str) -> str:
        return (root / ".saipen" / name).read_text(encoding="utf-8")

    def test_a_decision_turns_the_refusal_into_a_committing_repair(self):
        repairs = _state_blocker_repairs(
            {"phase": "SCOUT", "blocker": self._GATE}, {}, "vendor renewed"
        )
        self.assertEqual(len(repairs), 1, repairs)
        self.assertEqual(repairs[0]["to"], "none")
        self.assertTrue(repairs[0].get("operator_authorized"), repairs)
        self.assertNotIn("refuse", repairs[0])
        self.assertIn("vendor renewed", repairs[0]["reason"])

    def test_empty_authority_never_clears_a_gate(self):
        for blank in (None, "", "   "):
            with self.subTest(blank=repr(blank)):
                repairs = _state_blocker_repairs(
                    {"phase": "SCOUT", "blocker": self._GATE}, {}, blank
                )
                self.assertTrue(repairs[0]["refuse"], repairs)
                self.assertIn("resolve-blocker", repairs[0]["reason"])

    def test_the_engine_records_the_authority_and_lifts_the_brake(self):
        root = self._make(blocker=self._GATE)
        original = (root / ".saipen" / "STATE.md").read_bytes()

        planned = reconcile_protocol_state(
            root, "tester", dry_run=True, resolve_blocker="vendor renewed"
        )
        self.assertTrue(planned["ok"], planned)
        self.assertEqual(planned["code"], "REPAIR_REQUIRED", planned)

        applied = reconcile_protocol_state(
            root, "tester", resolve_blocker="vendor renewed"
        )
        self.assertTrue(applied["ok"], applied)
        self.assertEqual(applied["code"], "REPAIRED", applied)

        from saipen_engine.state import parse_state_or_error

        state, error = parse_state_or_error(self._read(root, "STATE.md"))
        self.assertEqual(error, None)
        self.assertEqual(state.get("blocker"), "none")
        self.assertIsNone(binding_brake(state))
        # The recorded DEC names the operator authority, and the original bytes
        # survive as the recovery-evidence artifact.
        self.assertIn("vendor renewed", self._read(root, "LOG.md"))
        artifacts = sorted((root / ".saipen" / "recovery").rglob("*.STATE.md"))
        self.assertEqual(len(artifacts), 1, artifacts)
        self.assertEqual(artifacts[0].read_bytes(), original)

        self.assertEqual(
            reconcile_protocol_state(
                root, "tester", resolve_blocker="vendor renewed"
            )["code"],
            "CLEAN",
        )

    def test_a_live_board_gate_is_cleared_but_the_ticket_is_not_owned(self):
        root = self._make(blocker=self._GATE, board_blocked=True)
        board_before = self._read(root, "BOARD.md")
        applied = reconcile_protocol_state(
            root, "tester", resolve_blocker="vendor renewed"
        )
        self.assertTrue(applied["ok"], applied)
        # Only STATE.blocker is owned; the parked ticket keeps its own block.
        self.assertEqual(
            self._read(root, "STATE.md").count("\nblocker: none\n"),
            1,
        )
        self.assertEqual(self._read(root, "BOARD.md"), board_before)
        self.assertIn("T-002", self._read(root, "LOG.md"))

    def test_the_verb_does_not_own_phase_blocked(self):
        root = self._make(blocker=self._GATE)
        state_path = root / ".saipen" / "STATE.md"
        state_path.write_text(
            self._read(root, "STATE.md").replace("phase: SCOUT", "phase: BLOCKED"),
            encoding="utf-8",
        )
        before = state_path.read_bytes()
        result = reconcile_protocol_state(
            root, "tester", resolve_blocker="vendor renewed"
        )
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "RECONCILE_REAUTH_REQUIRED", result)
        self.assertEqual(state_path.read_bytes(), before)


class OperatorBlockerCliTests(unittest.TestCase):
    """The exact reachable verb: `saipen recover resolve-blocker "<decision>"`."""

    def _run(self, root: Path, *extra: str):
        env = {**os.environ}
        env.pop("PWD", None)
        env.pop("OLDPWD", None)
        return subprocess.run(
            [sys.executable, str(SAIPEN_CLI), "recover", *extra],
            cwd=str(root), capture_output=True, text=True, env=env, timeout=600,
        )

    def _make(self) -> Path:
        root = _project(blocker="BLOCKED_EXTERNAL -- vendor cert pending")
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        return root

    def test_recover_resolves_the_gate_with_recorded_authority(self):
        root = self._make()
        run = self._run(root, "resolve-blocker", "vendor cert renewed")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        first = (run.stdout + run.stderr).strip().splitlines()[0]
        self.assertEqual(first, "code: REPAIRED", run.stdout + run.stderr)
        state = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        self.assertIn("\nblocker: none\n", state)

    def test_the_closed_grammar_refuses_a_missing_decision(self):
        root = self._make()
        run = self._run(root, "resolve-blocker")
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertIn("VALIDATION_FAILED", run.stdout + run.stderr)

    def test_an_unknown_flag_is_refused(self):
        root = self._make()
        run = self._run(root, "--force")
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertIn("VALIDATION_FAILED", run.stdout + run.stderr)


class GuardParityTests(unittest.TestCase):
    """Target H: the router, the fleet and the admission guard must agree.

    While braked, the guard admits exactly one mutating verb family (`recover`);
    the fleet must therefore only ever name a command in that family (or the
    ungated `continue`), and the router must still surface a read-only stop --
    never a mutation the executor would refuse. This is asserted against the
    REAL guard source so a drifted exemption breaks the test rather than the
    operator.
    """

    _GUARD = (
        Path(__file__).resolve().parent.parent
        / "extensions" / "adapters" / "opencode" / "saipen-guard.js"
    )

    _CODES = (
        "REPAIR_REQUIRED",
        "RECOVERY_REQUIRED",
        "RECONCILE_REAUTH_REQUIRED",
        "CORRUPT_JOURNAL",
        "WAIT_BLOCKED",
        "SOMETHING_UNRECOGNISED",
    )

    def test_the_guard_exempts_the_one_verb_the_fleet_names(self):
        source = self._GUARD.read_text(encoding="utf-8")
        self.assertIn('canonicalVerb === "recover"', source)
        self.assertIn("preflight|scan", source)
        # T-1326: the Fleet-named BOARD compaction repair is admitted too, but
        # ONLY the exact `saipen ticket compact T-###` form -- bare `ticket` and
        # every other subcommand stay on the strict fleet path.
        self.assertRegex(
            source,
            r'canonicalVerb === "ticket"\s*&&\s*/\^saipen ticket compact T-\\d\+',
        )

    def test_the_named_board_compaction_repair_is_guard_admitted(self):
        command = _result(
            CLASS_SAFE,
            reason_code="BOARD_RECORD_OVERSIZE",
            reason="x",
            snapshot={"board": {"tickets": {"T-9": {"raw": "z" * 3000}}}},
        )["canonical_next_command"]
        self.assertEqual(command, "saipen ticket compact T-9")
        self.assertRegex(self._GUARD.read_text(encoding="utf-8"), r"saipen ticket compact T-\\d\+")

    def test_every_braked_fleet_command_uses_a_guard_admitted_verb(self):
        admitted = {"recover", "continue"}
        for classification in (CLASS_SAFE, CLASS_BLOCKED):
            for code in (*self._CODES, "ANYTHING_ELSE"):
                with self.subTest(classification=classification, code=code):
                    command = _result(
                        classification, reason_code=code, reason="x"
                    )["canonical_next_command"]
                    self.assertTrue(command, (classification, code))
                    self.assertIn(command.split()[1], admitted, command)

    def test_the_router_brake_is_a_read_only_stop_not_a_mutation(self):
        from saipen_engine import router as router_mod

        state = (
            "---\nphase: BUILD\ntask: T-900\nnext_action: \"PHASE BUILD T-900\"\n"
            "transition_from: SCOUT\nblocker: \"BLOCKED_EXTERNAL -- vendor cert pending\"\n"
            "agent: probe\nsaipen_version: 8\nmode: full\n"
            "updated: 2026-09-11T00:00:00Z\n---\n"
        )
        board = (
            "# Board\n## DOING\n- [/] T-900 [P0] parity | verify: probe\n"
            "## TODO\n## DONE\n## BLOCKED\n"
        )
        routed = router_mod.route_next(state, board, pending_ops=[], conflict_ops=[])
        self.assertEqual(routed.get("action"), "saipen status", routed)
        self.assertEqual(routed.get("reason"), "unblock", routed)
        self.assertEqual(routed.get("executable_behavior"), "RESTATE_AND_STOP", routed)


class DeadlockReachabilityMatrixTests(unittest.TestCase):
    """Target K: ONE closed no-dead-end matrix over every classification.

    The original defect was a *dead end*: work was provably invalid, and no
    canonical action existed to clear it. These tests pin the closure at the
    level the operator cares about -- a state that says work is needed must name
    an action that reaches it, and a braked state must offer either an
    automatic repair or an explicit operator decision (never both, never
    neither), plus a machine-readable diagnosis token.
    """

    _CLASSES = (
        CLASS_NON_SAIPEN,
        CLASS_UNBOUND,
        CLASS_VALID,
        CLASS_SAFE,
        CLASS_BLOCKED,
        CLASS_CONFLICT,
    )
    _CODES = (
        "CLEAN",
        "REPAIR_REQUIRED",
        "RECOVERY_REQUIRED",
        "RECONCILE_REAUTH_REQUIRED",
        "CORRUPT_JOURNAL",
        "WAIT_BLOCKED",
        "PROJECT_BINDING_INVALID",
        "SOMETHING_UNRECOGNISED",
    )

    def test_no_classification_is_a_false_dead_end(self):
        in_scope = (CLASS_SAFE, CLASS_BLOCKED)
        out_of_scope = (CLASS_NON_SAIPEN, CLASS_UNBOUND, CLASS_CONFLICT, CLASS_VALID)
        for classification in (*in_scope, *out_of_scope):
            for code in self._CODES:
                with self.subTest(classification=classification, code=code):
                    result = _result(classification, reason_code=code, reason="x")
                    # Work is never demanded without an automatic route to it.
                    if result["needs_local_mutation"]:
                        self.assertTrue(result["safe_auto_repair_available"], result)
                    # The two authorities are mutually exclusive.
                    self.assertFalse(
                        result["safe_auto_repair_available"]
                        and result["operator_decision_available"],
                        result,
                    )
                    if classification in in_scope:
                        # An IN-SCOPE braked surface never leaves the host with
                        # nothing to do: an automatic repair or a decision, and
                        # a canonical command, and an explicit diagnosis mode.
                        self.assertTrue(
                            result["safe_auto_repair_available"]
                            or result["operator_decision_available"],
                            result,
                        )
                        self.assertTrue(result["canonical_next_command"], result)
                        self.assertIn(result["diagnosis"], (
                            "RUN_CANONICAL_REPAIR", "READ_ONLY_DIAGNOSIS_ONLY",
                        ), result)
                    else:
                        # An out-of-scope surface has no protocol repair (it is
                        # not SAIPEN work, or the binding itself is in conflict):
                        # it must never demand a local mutation, and its read-only
                        # mode must forbid speculative probes.
                        self.assertFalse(result["needs_local_mutation"], result)
                        self.assertIn(result["diagnosis"], (
                            "NONE", "READ_ONLY_DIAGNOSIS_ONLY",
                        ), result)

    def test_real_braked_surfaces_are_all_reachable(self):
        cases = (
            ({}, CLASS_SAFE, "REPAIR_REQUIRED"),
            ({"blocker": "BLOCKED_EXTERNAL -- vendor cert pending"},
             CLASS_BLOCKED, "RECONCILE_REAUTH_REQUIRED"),
        )
        for kwargs, expected_class, expected_code in cases:
            with self.subTest(expected=expected_class):
                root, lineage = _bound_project(**kwargs)
                self.addCleanup(lambda r=root: shutil.rmtree(r, ignore_errors=True))
                result = preflight(root, host_root=root, host_lineage=lineage)
                self.assertEqual(result["classification"], expected_class, result)
                self.assertEqual(result["reason_code"], expected_code, result)
                self.assertTrue(result["canonical_next_command"], result)
                if expected_class == CLASS_SAFE:
                    self.assertTrue(result["safe_auto_repair_available"], result)
                    self.assertEqual(result["diagnosis"], "RUN_CANONICAL_REPAIR", result)
                else:
                    self.assertTrue(result["operator_decision_available"], result)
                    self.assertEqual(result["diagnosis"], "READ_ONLY_DIAGNOSIS_ONLY", result)
                self.assertEqual(result["canonical_next_command"].split()[1], "recover", result)


if __name__ == "__main__":
    unittest.main()
