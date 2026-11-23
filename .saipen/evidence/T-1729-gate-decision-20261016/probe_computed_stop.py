"""TEST HARNESS: a limitation approval must not waive a computed budget stop."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from test_t1729_operator_gate import ScopedOperatorDecision, capsule, capture  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from saipen_engine.reconcile import reconcile_protocol_state  # noqa: E402
from saipen_engine.state import binding_brake, patch_state  # noqa: E402
from saipen_engine.router import route_next  # noqa: E402

isolate_host_session()
case = ScopedOperatorDecision()
try:
    project = case.make()
    log = project / ".saipen/LOG.md"
    text = log.read_text(encoding="utf-8")
    text += "- 14.09.26 00:02 [E-3] [parent: E-2] [agent: tester] DEC: goal pivot -- fixture\n"
    for index in range(20):
        text += (f"- 14.09.26 00:02 [E-{index + 4}] [parent: E-{index + 3}] "
                 f"[agent: tester] DEC: goal_tickets {index}->{index + 1}\n")
    log.write_text(text, encoding="utf-8")
    state = project / ".saipen/STATE.md"
    state.write_text(patch_state(state.read_text(encoding="utf-8"), {
        "last_event": 23, "execution_intent": "goal", "goal_tickets": 20, "goal_waves": 0,
        "continuation_authority": "operator_required", "authority_source": "E-3",
        "authority_until": "budget", "safety_valve_mode": "hard_wait",
    }), encoding="utf-8")
    before = case.canonical(project)
    diagnosis = reconcile_protocol_state(project, "tester", dry_run=True)
    value = capsule(project)
    value["next_action"] = "saipen continue"
    receipt = capture(project, value)
    result = case.resolve(project, receipt)
    route = route_next(state.read_text(encoding="utf-8"),
                       (project / ".saipen/BOARD.md").read_text(encoding="utf-8"),
                       current_agent="tester")
    print(json.dumps({"diagnosis": diagnosis, "resolve": result,
                      "canonical_unchanged": case.canonical(project) == before,
                      "brake": binding_brake(case.state(project)), "route": route}, indent=2))
finally:
    case.doCleanups()
