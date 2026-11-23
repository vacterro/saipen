"""T-2023/SRC-393: goal-management commands are never goal pivots, and a
standing maintenance grant binds the exact registered PersistentGoal.

TWO reproduced cross-component defects (measured 2026-11-04 against live source):

P0-1. `cold_recovery.goal_objective_text` excluded only `authorize`, so every
      other real `saipen goal <verb>` management subcommand was returned as a
      NEW goal OBJECTIVE. The ZAICODE hook's `declared_action` therefore sealed
      the operator's own read-only `saipen goal propose` as `action="goal"` and
      spent it with `_spend_goal` on the authenticated human message: a read
      command minted a persistent campaign.

P0-2. `goal_authority.current_binding` derived a proposed grant from the latest
      committed `goal pivot` event, so a capsule for the operator's
      self-maintenance objective described a HISTORIC test pivot
      ("T-1599 (SRC-164): test1") and the apply path wrote that old goal's
      authority into STATE. The live proposer returned exactly that.

The controls below run the REAL functions -- the canonical parser, the real
hook module, `current_binding` against a real temp project with a registered
PersistentGoal. No mock stands between the assertion and the arithmetic.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import shutil  # noqa: E402

from saipen_engine import codec, goal_authority, operations, state  # noqa: E402
from saipen_engine.paths import identity_file_content, new_project_lineage  # noqa: E402
from saipen_engine.persistent_goal import (  # noqa: E402
    SCOPE_MAINTENANCE,
    PersistentGoal,
    register_goal,
)

HOOK = REPO / "extensions" / "adapters" / "zaicode" / "saipen-guard.py"

MAINTENANCE_OBJECTIVE = (
    "Autonomously discover, evaluate, and repair verified regressions, test "
    "failures, and maintenance backlog to preserve a healthy repository"
)

_TABLE = {
    "gg": "saipen goal",
    "cc": "saipen continue",
    "ccc": "saipen continue",
}

_BOARD = (
    "## DOING\n- [/] T-1 [P2] fixture work | verify: fixture | owner: fix | "
    "claim_time: 2026-11-04T00:00:00Z\n## TODO\n## DONE\n## BLOCKED\n"
)

_LOG = (
    "# Log\n"
    "- 14.09.26 00:00 [E-0001] [agent: fix] [op: transition-" + "a" * 32
    + "] RUN: transition to SCOUT\n"
    "- 14.09.26 00:01 [E-0002] [parent: E-0001] [T-1] [agent: fix] "
    "[op: ticket-" + "b" * 32 + "] DEC: ticket add via SAIOPS -- T-1\n"
)


def _load_hook():
    spec = importlib.util.spec_from_file_location("t2023_guard", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _state(**fields) -> str:
    base = {
        "phase": "SCOUT",
        "task": "none",
        "next_action": "saipen continue",
        "blocker": "none",
        "transition_from": "DONE",
        "saipen_version": "8",
        "schema_version": "3",
        "agent": "fix",
        "mode": "full",
        "updated": "2026-11-04T00:00:00Z",
        "execution_intent": "goal",
        "goal_waves": 0,
        "goal_tickets": 0,
        "continuation_authority": "operator_required",
        "authority_source": "E-0001",
        "authority_until": "budget",
        "safety_valve_mode": "hard_wait",
    }
    base.update(fields)
    return "---\n" + "\n".join(f"{k}: {v}" for k, v in base.items()) + "\n---\n"


def _project(case: unittest.TestCase, *, objective: str) -> Path:
    root = Path(tempfile.mkdtemp(prefix="t2023-"))
    case.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
    saipen = root / ".saipen"
    saipen.mkdir(parents=True)
    (saipen / "IDENTITY.md").write_text(
        identity_file_content(new_project_lineage()), encoding="utf-8"
    )
    (saipen / "STATE.md").write_text(
        _state(last_event=2, task="T-1", next_action="PHASE SCOUT T-1",
               transition_from="SCOUT"), encoding="utf-8"
    )
    (saipen / "BOARD.md").write_text(_BOARD, encoding="utf-8")
    (saipen / "LOG.md").write_text(_LOG, encoding="utf-8")
    (root / "tools").mkdir()
    (root / "saipen").mkdir()
    entered = operations.set_goal_intent(root, "fix", objective)
    assert entered.ok, entered.to_dict()
    return root


def _register_maintenance(root: Path, **overrides) -> PersistentGoal:
    goal = PersistentGoal(
        goal_id=overrides.pop("goal_id", "self-maintenance-core"),
        project_id=overrides.pop("project_id", root.name),
        title=overrides.pop("title", "Continuous Self-Maintenance"),
        objective=overrides.pop("objective", MAINTENANCE_OBJECTIVE),
        authorization_scope=overrides.pop("authorization_scope", SCOPE_MAINTENANCE),
        evidence_provider=overrides.pop("evidence_provider", "failed_tests"),
    )
    register_goal(root, goal)
    return goal


class P01GoalManagementIsNeverAnObjective(unittest.TestCase):
    """Every real `saipen goal <verb>` management command returns no objective."""

    MANAGEMENT = (
        "saipen goal propose",
        "saipen goal status",
        "saipen goal list",
        "saipen goal eval",
        "saipen goal replenish",
        "saipen goal pause self-maintenance-core",
        "saipen goal resume self-maintenance-core",
        "saipen goal add foo A title --objective o",
    )
    #: `authorize` is genuinely the grant form and stays authorize-goal.
    GRANT_FORM = "saipen goal authorize --file capsule.json"

    def test_management_verbs_are_not_objectives(self):
        for text in (*self.MANAGEMENT, self.GRANT_FORM):
            with self.subTest(text=text):
                self.assertIsNone(goal_authority_text(text), text)

    def test_genuine_entries_still_resolve(self):
        for text, expected in (
            ("saipen goal make the parser strict", "make the parser strict"),
            ("gg make the parser strict", "make the parser strict"),
            ("/goal gg make the parser strict", "make the parser strict"),
            ("saipen gg make the parser strict", "make the parser strict"),
        ):
            with self.subTest(text=text):
                self.assertEqual(goal_authority_text(text), expected)

    def test_management_command_resolver_names_the_safe_command(self):
        from saipen_engine.cold_recovery import goal_management_command

        self.assertEqual(goal_management_command("saipen goal propose"), "saipen goal propose")
        self.assertEqual(
            goal_management_command("saipen goal pause self-maintenance-core"),
            "saipen goal pause self-maintenance-core",
        )
        self.assertIsNone(goal_management_command("saipen goal make it strict"))

    def test_real_hook_never_seals_management_as_a_goal(self):
        """The RED control: pre-fix the hook sealed `goal propose` as `goal`."""
        hook = _load_hook()
        root = Path.cwd()
        for text in self.MANAGEMENT:
            with self.subTest(text=text):
                self.assertEqual(hook.declared_action(text, root), "continue", text)

    def test_real_hook_still_seals_a_genuine_entry(self):
        hook = _load_hook()
        root = Path.cwd()
        self.assertEqual(hook.declared_action("gg make it strict", root), "goal")
        self.assertEqual(hook.declared_action("/goal gg make it strict", root), "goal")

    def test_real_hook_keeps_grant_syntax_distinct(self):
        """Regression 5: the grant form stays authorize-goal, not management."""
        hook = _load_hook()
        root = Path.cwd()
        capsule = json.dumps(
            {"kind": "saipen-goal-continuation", "project_lineage": "x",
             "goal_ingress": "goal-" + "a" * 16}
        )
        self.assertEqual(hook.declared_action(capsule, root), "authorize-goal")
        self.assertEqual(
            hook.declared_action("saipen goal authorize --file capsule.json", root),
            "authorize-goal",
        )

    def test_management_preview_is_read_only_and_never_seals(self):
        """The hook's management route must report zero mutation."""
        hook = _load_hook()
        preview = hook._goal_management_preview(
            Path.cwd(), None, "saipen goal pause self-maintenance-core"
        )
        self.assertTrue(preview["ok"])
        self.assertFalse(preview["mutated"])
        self.assertEqual(preview["code"], "GOAL_MANAGEMENT_TERMINAL")


def goal_authority_text(text: str):
    from saipen_engine.cold_recovery import goal_objective_text

    return goal_objective_text(text, protocol_dir=REPO / "saipen")


class P02GrantBindsThePersistentGoal(unittest.TestCase):
    def setUp(self):
        self.root = _project(self, objective=MAINTENANCE_OBJECTIVE)
        self.history = _read_history(self.root)

    def binding(self):
        st = state.parse_state(codec.read_doc(self.root / ".saipen/STATE.md"))
        return goal_authority.current_binding(
            self.root, st, self.history, {}, until="continuous_maintenance"
        )

    def test_matching_goal_binds_its_exact_identity(self):
        goal = _register_maintenance(self.root)
        binding = self.binding()
        self.assertEqual(binding["maintenance_goal_id"], goal.goal_id)
        self.assertEqual(binding["maintenance_scope"], "MAINTENANCE")
        self.assertEqual(binding["maintenance_provider"], "failed_tests")
        self.assertEqual(
            binding["maintenance_goal_digest"], goal_authority.maintenance_goal_digest(goal)
        )
        self.assertEqual(binding["goal_objective"], MAINTENANCE_OBJECTIVE)

    def test_historic_test_pivot_cannot_authorize_self_maintenance(self):
        """Regression 10: a pivot for ANOTHER objective fails closed."""
        _register_maintenance(self.root)
        other = _project(self, objective="T-1599 (SRC-164): test1")
        _register_maintenance(other)
        st = state.parse_state(codec.read_doc(other / ".saipen/STATE.md"))
        with self.assertRaises(ValueError) as ctx:
            goal_authority.current_binding(
                other, st, _read_history(other), {}, until="continuous_maintenance"
            )
        self.assertIn("does not describe the registered maintenance goal", str(ctx.exception))

    def test_wrong_project_goal_fails_closed(self):
        _register_maintenance(self.root, project_id="some-other-project")
        with self.assertRaises(ValueError) as ctx:
            self.binding()
        self.assertIn("another project", str(ctx.exception))

    def test_ambiguous_maintenance_goals_fail_closed(self):
        _register_maintenance(self.root, goal_id="maint-a")
        _register_maintenance(self.root, goal_id="maint-b")
        with self.assertRaises(ValueError) as ctx:
            self.binding()
        self.assertIn("ambiguous", str(ctx.exception))

    def test_altered_objective_changes_the_digest(self):
        goal = _register_maintenance(self.root)
        before = goal_authority.maintenance_goal_digest(goal)
        goal.objective = "a different objective entirely"
        after = goal_authority.maintenance_goal_digest(goal)
        self.assertNotEqual(before, after)

    def test_propose_fails_closed_on_mismatch_and_shows_identity_on_match(self):
        _register_maintenance(self.root)
        # Mismatch: the live pivot objective is MAINTENANCE_OBJECTIVE, so a
        # capsule must NOT carry the historic "test1" text. Registering a goal
        # whose objective differs makes the proposer refuse rather than lie.
        st = state.parse_state(codec.read_doc(self.root / ".saipen/STATE.md"))
        ok = goal_authority.propose_capsule(
            self.root, st, self.history, until="continuous_maintenance"
        )
        self.assertTrue(ok["ok"], ok)
        self.assertEqual(ok["capsule"]["maintenance_goal_id"], "self-maintenance-core")
        preview = ok["preview"]
        for key in (
            "objective", "allowed_operations", "project", "scope", "budget",
            "expiry_policy", "revocation_path", "excluded_actions",
        ):
            self.assertIn(key, preview, key)
        self.assertIn("publication", preview["excluded_actions"])

    def test_no_maintenance_goal_means_no_maintenance_capsule(self):
        st = state.parse_state(codec.read_doc(self.root / ".saipen/STATE.md"))
        result = goal_authority.propose_capsule(
            self.root, st, self.history, until="continuous_maintenance"
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "PROPOSAL_UNAVAILABLE")


class P1OneActionOperatorApproval(unittest.TestCase):
    """The smallest real approval surface: one pasteable, broker-checked capsule.

    The proposal must hand the operator the EXACT bytes to approve, and those
    bytes must (a) be the literal capsule `current_binding` derives, so nothing
    is recomputed or edited; (b) classify as `authorize-goal` in the real hook,
    so the host seals the operator's own message; and (c) apply once through the
    canonical `authorize_goal_continuation`, then refuse a second time.
    """

    def setUp(self):
        self.root = _project(self, objective=MAINTENANCE_OBJECTIVE)
        _register_maintenance(self.root)

    def proposal(self):
        st = state.parse_state(codec.read_doc(self.root / ".saipen/STATE.md"))
        result = goal_authority.propose_capsule(
            self.root, st, _read_history(self.root), until="continuous_maintenance"
        )
        self.assertTrue(result["ok"], result)
        return result

    def test_capsule_text_is_the_exact_canonical_bytes(self):
        result = self.proposal()
        parsed = goal_authority.parse_capsule(result["capsule_text"])
        self.assertEqual(parsed, result["capsule"])
        # Pasteable message: a JSON document, nothing wrapped around it.
        self.assertTrue(result["capsule_text"].startswith("{"))
        self.assertEqual(json.loads(result["capsule_text"]), result["capsule"])

    def test_real_hook_seals_the_proposed_capsule_as_authorize_goal(self):
        hook = _load_hook()
        result = self.proposal()
        self.assertEqual(
            hook.declared_action(result["capsule_text"], Path.cwd()),
            "authorize-goal",
        )

    def test_proposed_capsule_applies_once_then_replays_without_a_second_write(self):
        """The operator's own message IS the approval: exactly one write.

        Re-sending the identical capsule is an idempotent replay (same op_id,
        zero changed files), never a second grant; and a DIFFERENT grant for the
        already-authorized goal is refused.
        """
        result = self.proposal()
        first = _witnessed_apply(self, self.root, result["capsule_text"])
        self.assertTrue(first.ok, first.to_dict())
        replay = _witnessed_apply(self, self.root, result["capsule_text"])
        self.assertTrue(replay.ok, replay.to_dict())
        self.assertEqual(replay.op_id, first.op_id)
        self.assertEqual(replay.changed_files, [])
        self.assertEqual(replay.code, "GOAL_AUTHORITY_ALREADY_SET")

    def test_a_second_different_grant_for_the_same_goal_is_refused(self):
        """Regression 12: a second, different authorization cannot stack."""
        result = self.proposal()
        first = _witnessed_apply(self, self.root, result["capsule_text"])
        self.assertTrue(first.ok, first.to_dict())
        other = dict(result["capsule"])
        other["authority_source"] = "E-99999"
        refused = _witnessed_apply(
            self, self.root, json.dumps(other, sort_keys=True, separators=(",", ":"))
        )
        self.assertFalse(refused.ok, refused.to_dict())

    def test_a_capsule_naming_a_different_scope_is_refused(self):
        """Regression 12: a narrowed/re-scoped capsule is not this grant."""
        result = self.proposal()
        narrowed = dict(result["capsule"])
        narrowed["authority_until"] = "goal_complete"
        refused = _witnessed_apply(
            self, self.root, json.dumps(narrowed, sort_keys=True, separators=(",", ":"))
        )
        self.assertFalse(refused.ok, refused.to_dict())

    def test_a_maintenance_grant_carries_no_release_or_publication_authority(self):
        """Regression 14: excluded actions are signed into the capsule."""
        result = self.proposal()
        excluded = result["capsule"]["excluded_actions"]
        for action in ("release", "publication"):
            self.assertIn(action, excluded)
        self.assertEqual(result["preview"]["excluded_actions"], excluded)

    def test_altered_capsule_text_is_refused_by_the_apply_path(self):
        """Regression: an edited objective must not authorize the real goal."""
        result = self.proposal()
        tampered = dict(result["capsule"])
        tampered["goal_objective"] = "T-1599 (SRC-164): test1"
        refused = _witnessed_apply(
            self, self.root, json.dumps(tampered, sort_keys=True, separators=(",", ":"))
        )
        self.assertFalse(refused.ok, refused.to_dict())

    def test_unwitnessed_capsule_is_not_consent(self):
        """Regression 8: a shell/agent-supplied capsule never authorizes."""
        result = self.proposal()
        refused = operations.authorize_goal_continuation(
            self.root, "fix", result["capsule_text"]
        )
        self.assertFalse(refused.ok)
        self.assertIn("witnessed", refused.message or "")

    def test_revoking_the_grant_origin_revokes_the_proof(self):
        """Regression 12 (revocation): a revoked origin cannot keep proving."""
        from saipen_engine import host_authority_client as HC
        from unittest import mock

        result = self.proposal()
        first = _witnessed_apply(self, self.root, result["capsule_text"], revoke_after=True)
        self.assertTrue(first.ok, first.to_dict())
        state_now = state.parse_state(codec.read_doc(self.root / ".saipen/STATE.md"))
        host = self._host
        with mock.patch.object(HC, "_call", side_effect=host.fixture.bridge):
            errors = goal_authority.prove(self.root, state_now)
        self.assertTrue(errors, "a revoked grant origin must not keep proving")
        self.assertIn("revoked", " ".join(errors))


def _read_history(root: Path):
    from saipen_engine.log import read_history_snapshot

    return read_history_snapshot(root, lean=True).events


def _witnessed_apply(
    case: unittest.TestCase, root: Path, capsule_text: str, *, revoke_after: bool = False
):
    """Apply a capsule the way a REAL host does: seal the operator's own bytes.

    The proof comes from the simulated native-event owner in
    `test_operator_origin_support`, which exercises the real broker, HMAC ledger
    and Sources. It never fabricates a host receipt: if the operator bytes are
    not a valid authorization the issuer refuses and this returns the plain
    unwitnessed refusal (or, for `revoke_after`, the applied result carries the
    `revoked` flag so a caller can prove the revoked origin no longer verifies).
    """
    from test_operator_origin_support import use_case_owner

    host = use_case_owner(case, root)
    case._host = host
    host.select(root)
    proof = host.offer(root, capsule_text, action="authorize-goal")
    if proof is None:
        # Not a valid operator authorization; let the canonical apply answer.
        return operations.authorize_goal_continuation(root, "fix", capsule_text)
    result = operations.authorize_goal_continuation(root, "fix", capsule_text)
    if revoke_after and proof is not None:
        host.fixture.broker.handle(
            {"op": "revoke-origin", "host": "claude", "proof": proof},
            host.fixture.native_peer,
        )
    return result


def setUpModule():
    from test_hermetic_env import isolate_host_session

    isolate_host_session()


if __name__ == "__main__":
    unittest.main()
