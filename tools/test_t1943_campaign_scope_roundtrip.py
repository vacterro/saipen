"""T-1943/SRC-342 R006: the campaign scope must be WRITABLE and READABLE.

MEASURED defect, 2026-10-27. `saipen/REGISTRY.json` declared

    "goal_authority": {"until": ["budget", "goal_complete"], ...}

while `goal_authority.GRANT_SCOPES` and `extensions/schemas/state.schema.json`
both carry a third legal scope, `continuous_maintenance`. `shape_errors` reads
its closed enum from the REGISTRY, so the third scope was refused there:

    grant_fields("SRC-304", until="continuous_maintenance")
        -> {"authority_until": "continuous_maintenance", "safety_valve_mode": "checkpoint"}
    shape_errors(that state)
        -> ["authority_until outside its closed enum"]

The canonical WRITER therefore emitted a grant the canonical READER called
CORRUPT. `state_contract_errors` calls `shape_errors`, so `parse_state` answered
`{"phase": "CORRUPT"}` for a state the protocol itself had just written:

    $ python -c "... grant -> parse_state ..."
    contract_errors: ['authority_until outside its closed enum']
    parse_state     : {'phase': 'CORRUPT', ...}

That is why the campaign scope was unreachable end to end even though the
authorization path could ask for it: `continuous_maintenance_proven` starts with
`is_continuous_maintenance`, which starts with `persistent`, which returns False
on any shape error. R006's "persistent grant survives a 20-ticket checkpoint"
was impossible on this tree, and the failure surfaced as three unrelated
`INVALID_RUNTIME` assertions in `test_campaign_continuation_assessment.py`
(C01, C12, C13) plus two in `test_t1875_maintenance_wiring.py`.

WHY THE FIX IS THE ENUM AND NOT THE PREDICATE. The alternative -- teach
`shape_errors` to accept the scope on a special case -- would leave the registry
lying about its own closed set and split the authority grammar into two. The
registry is the declared surface; it was simply missing a member every other
declaration already had. Adding it widens nothing: the bounded path still
refuses the campaign tuple (proved below), and an invented scope is still
rejected.

These tests assert the PRODUCT PROPERTY (write -> read -> prove), not the diff.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import goal_authority  # noqa: E402
from saipen_engine.state import parse_state, state_contract_errors  # noqa: E402

REGISTRY = REPO / "saipen" / "REGISTRY.json"
SCHEMA = REPO / "extensions" / "schemas" / "state.schema.json"

PERSISTENT = {
    "execution_intent": "goal",
    "continuation_authority": "operator_persistent",
    "authority_source": "E-5",
    "safety_valve_mode": "checkpoint",
    "goal_ingress": "goal-0123456789abcdef",
}


def state_document(fields: dict) -> str:
    """A complete STATE whose authority fields are exactly `fields`."""
    body = {
        "phase": "DONE",
        "task": "none",
        "next_action": '"saipen continue"',
        "blocker": "none",
        "transition_from": "SHIP",
        "saipen_version": 8,
        "schema_version": 3,
        "last_event": 100,
        "style_contract": "ded-069a4c52",
        "saipen_home": '".',
        "agent": "tester",
        "mode": "full",
        "updated": '"2026-10-27T00:00:00Z"',
        "execution_intent": "goal",
        "goal_waves": 0,
        "goal_tickets": 0,
        "authority_source": "E-5",
        "goal_ingress": "goal-0123456789abcdef",
    }
    body.update(fields)
    return "---\n" + "".join(f"{key}: {value}\n" for key, value in body.items()) + "---\n"


class TheClosedSetIsDeclaredInOnePlace(unittest.TestCase):
    """The registry, the schema and GRANT_SCOPES must agree."""

    def test_every_grant_scope_is_declared_by_the_registry(self) -> None:
        """The registry may also carry `budget`, never FEWER members than grants.

        `budget` is the BOUNDED scope: a state may declare it, and no operator
        grant can be minted with it. So the relation is a superset, not
        equality -- what must never happen is a granted scope the registry's
        own enum refuses, which is exactly the measured defect.
        """
        declared = set(
            json.loads(REGISTRY.read_text(encoding="utf-8-sig"))["goal_authority"]["until"]
        )
        self.assertTrue(
            set(goal_authority.GRANT_SCOPES) <= declared,
            "a scope the engine can grant is missing from the registry enum, so "
            "shape_errors will refuse the state this engine just wrote: "
            f"{sorted(set(goal_authority.GRANT_SCOPES) - declared)}",
        )

    def test_every_grant_scope_is_legal_in_the_state_schema(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8-sig"))
        legal = set(schema["properties"]["authority_until"]["enum"])
        self.assertTrue(
            set(goal_authority.GRANT_SCOPES) <= legal,
            "a scope the engine can grant is not representable in STATE: "
            f"{sorted(set(goal_authority.GRANT_SCOPES) - legal)}",
        )


class TheWriterAndTheReaderAgree(unittest.TestCase):
    """THE DEFECT. Write a grant, then read it back with the same engine."""

    def test_a_campaign_grant_reads_back_as_written(self) -> None:
        granted = goal_authority.grant_fields("SRC-304", until="continuous_maintenance")
        document = state_document(
            {
                "authority_until": granted["authority_until"],
                "safety_valve_mode": granted["safety_valve_mode"],
                "continuation_authority": granted["continuation_authority"],
                "authority_source": granted["authority_source"],
            }
        )
        parsed = parse_state(document)
        self.assertNotEqual(parsed.get("phase"), "CORRUPT", parsed.get("corrupt_detail"))
        self.assertEqual(parsed.get("authority_until"), "continuous_maintenance")
        self.assertEqual(parsed.get("safety_valve_mode"), "checkpoint")

    def test_the_written_state_survives_the_full_contract(self) -> None:
        granted = goal_authority.grant_fields("SRC-304", until="continuous_maintenance")
        state = {
            **PERSISTENT,
            "authority_until": granted["authority_until"],
            "authority_source": granted["authority_source"],
        }
        self.assertEqual(goal_authority.shape_errors(state), [])
        self.assertTrue(goal_authority.persistent(state))
        self.assertTrue(goal_authority.is_continuous_maintenance(state))

    def test_the_parsed_state_can_be_proved(self) -> None:
        """Round trip into the predicate the routing actually consumes."""
        granted = goal_authority.grant_fields("SRC-304", until="continuous_maintenance")
        state = parse_state(
            state_document(
                {
                    "authority_until": granted["authority_until"],
                    "safety_valve_mode": granted["safety_valve_mode"],
                    "continuation_authority": granted["continuation_authority"],
                    "authority_source": granted["authority_source"],
                }
            )
        )
        self.assertEqual(goal_authority.shape_errors(state), [])
        self.assertTrue(goal_authority.is_continuous_maintenance(state))


class NothingWasWidened(unittest.TestCase):
    """The negative controls: adding the scope must not loosen the tuple."""

    def test_a_bounded_grant_cannot_carry_the_campaign_scope(self) -> None:
        for valve in ("checkpoint", "hard_wait"):
            with self.subTest(valve=valve):
                state = {
                    "execution_intent": "goal",
                    "continuation_authority": "operator_required",
                    "authority_source": "E-5",
                    "authority_until": "continuous_maintenance",
                    "safety_valve_mode": valve,
                }
                self.assertEqual(
                    goal_authority.shape_errors(state),
                    ["continuation authority has an inconsistent scope/valve tuple"],
                )
                self.assertFalse(goal_authority.persistent(state))

    def test_an_invented_scope_is_still_refused(self) -> None:
        state = {**PERSISTENT, "authority_until": "forever"}
        self.assertEqual(
            goal_authority.shape_errors(state), ["authority_until outside its closed enum"]
        )

    def test_grant_fields_still_collapses_an_invented_scope(self) -> None:
        self.assertEqual(
            goal_authority.grant_fields("E-5", until="forever")["authority_until"],
            "goal_complete",
        )

    def test_a_persistent_grant_still_needs_its_goal_ingress(self) -> None:
        state = {
            **PERSISTENT,
            "authority_until": "continuous_maintenance",
            "goal_ingress": "",
        }
        self.assertEqual(
            goal_authority.shape_errors(state),
            ["persistent authority requires its goal_ingress binding"],
        )


class AReducedScopeIsNotACampaign(unittest.TestCase):
    """A grant narrowed to `goal_complete` must never read as maintenance."""

    def test_goal_complete_is_not_continuous_maintenance(self) -> None:
        state = {**PERSISTENT, "authority_until": "goal_complete"}
        self.assertTrue(goal_authority.persistent(state))
        self.assertFalse(
            goal_authority.is_continuous_maintenance(state),
            "a finite goal was read as a standing campaign",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
