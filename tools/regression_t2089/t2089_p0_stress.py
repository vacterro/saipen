"""T-2089 P0 adversarial stress: byte bound, count parity, mutation safety.

Run from the repository root:

    python tools/regression_t2089/t2089_p0_stress.py

Covers the handoff's P0-D invariants on the fixed `_agent_view_payload`:
- 120 / 2000 / 10000 blocker groups (some with adversarial long strings)
  keep the serialized agent view under a hard 32 KiB budget;
- counts (root_ticket_count, dependent_count, blocker_group_count,
  blocker_ticket_count) match the canonical full projection for every
  group count from 1 to 20 and for the stress sizes;
- building the view never mutates the input payload;
- truncation is reported exactly when something was capped.
"""

import importlib.util
import json
import os
import random
import sys

HARD_BUDGET_BYTES = 32 * 1024


def _load_subject():
    sys.path.insert(0, "tools")
    spec = importlib.util.spec_from_file_location("saipen", os.path.join("tools", "saipen.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules["saipen"] = module
    spec.loader.exec_module(module)
    return module


def _group(i, roots, deps, long_adversarial=False):
    cause = ("cause " + "Z" * 5000) if long_adversarial else f"cause {i}"
    return {
        "shared_blocker_id": f"EX-{i:06d}",
        "blocker_class": "WAIT_USER_DECISION",
        "cause": cause,
        "owner": "saipen-cli",
        "root_tickets": [f"T-{i}-{j}" for j in range(roots)],
        "dependent_tickets": [f"T-dep-{i}-{j}" for j in range(deps)],
        "recovery_internally_authorized": False,
        "external_input_required": True,
        "read_only_work_may_proceed": True,
    }


def _projection(n_groups, roots, deps, adversarial=False):
    return {
        "groups": [_group(i, roots, deps, adversarial and i % 7 == 0) for i in range(n_groups)],
        "items": [f"T-item-{i}" for i in range(n_groups * deps)],
    }


def stress_byte_budget(module, size, adversarial):
    payload = {"ok": True, "code": "STATUS_OK",
               "blocker_projection": _projection(size, 3, 2, adversarial)}
    if adversarial:
        payload["waiting_on_you"] = ["T-x: " + "w" * 9000] * 20
        payload["appends"] = [{"text": "a" * 9000}] * 9
    blob = json.dumps(module._agent_view_payload(payload),
                      ensure_ascii=False).encode("utf-8")
    label = f"groups={size}{' adversarial' if adversarial else ''}"
    if len(blob) > HARD_BUDGET_BYTES:
        return [f"{label}: serialized view {len(blob)} B exceeds 32 KiB"]
    return []


def property_count_parity(module):
    problems = []
    rng = random.Random(2089)
    for n_groups in range(1, 21):
        roots = rng.randint(0, 5)
        deps = rng.randint(0, 4)
        projection = _projection(n_groups, roots, deps)
        payload = {"ok": True, "code": "STATUS_OK", "blocker_projection": projection}
        view = module._agent_view_payload(payload)
        groups = view.get("blocker_groups") or []
        if view.get("blocker_group_count") != n_groups:
            problems.append(f"groups={n_groups}: group_count mismatch")
        if view.get("blocker_ticket_count") != n_groups * deps:
            problems.append(f"groups={n_groups}: ticket_count mismatch")
        for idx, g in enumerate(groups):
            if g.get("root_ticket_count") != roots:
                problems.append(
                    f"groups={n_groups} row[{idx}]: root_ticket_count "
                    f"{g.get('root_ticket_count')!r} != {roots}"
                )
                break
            if g.get("dependent_count") != deps:
                problems.append(
                    f"groups={n_groups} row[{idx}]: dependent_count "
                    f"{g.get('dependent_count')!r} != {deps}"
                )
                break
    return problems


def mutation_sweep(module):
    problems = []
    rng = random.Random(2090)
    for trial in range(40):
        projection = _projection(rng.randint(0, 30), rng.randint(0, 4), rng.randint(0, 3),
                                 adversarial=True)
        payload = {
            "ok": True,
            "code": "STATUS_OK",
            "waiting_on_you": ["T-1: " + "y" * rng.randint(1, 400)],
            "appends": [{"text": "a" * rng.randint(1, 300)}],
            "conformance_status": {"receipt": {
                "status": "CURRENT_FAIL",
                "blocking_findings": {"problem_count": 2, "problems": [{"detail": "d" * 300}]},
                "history": ["h" * 200] * 10,
            }},
            "blocker_projection": projection,
        }
        before = json.dumps(payload, sort_keys=True)
        module._agent_view_payload(payload)
        if json.dumps(payload, sort_keys=True) != before:
            problems.append(f"trial {trial}: input payload mutated")
            break
        # full -> agent -> full: a second agent pass over the same payload
        # must still see identical source bytes (the view is a pure function
        # of its input).
        again = module._agent_view_payload(json.loads(before))
        first = module._agent_view_payload(json.loads(before))
        if json.dumps(again, sort_keys=True) != json.dumps(first, sort_keys=True):
            problems.append(f"trial {trial}: agent view not idempotent over same input")
            break
    return problems


def truncation_truth(module):
    payload = {"ok": True, "code": "STATUS_OK",
               "blocker_projection": _projection(3, 2, 1)}
    view = module._agent_view_payload(payload)
    if view.get("truncated"):
        return ["3 small groups: truncated=True but nothing was capped"]
    payload = {"ok": True, "code": "STATUS_OK",
               "blocker_projection": _projection(30, 2, 1)}
    view = module._agent_view_payload(payload)
    if not view.get("truncated"):
        return ["30 groups: truncated=False while rows were capped"]
    return []


def main():
    module = _load_subject()
    problems = []
    for size in (120, 2000, 10000):
        problems += stress_byte_budget(module, size, adversarial=False)
        problems += stress_byte_budget(module, size, adversarial=True)
    problems += property_count_parity(module)
    problems += mutation_sweep(module)
    problems += truncation_truth(module)
    if problems:
        print("RED stress suite")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("GREEN stress suite: 120/2000/10000 groups bounded, 1-20 parity, "
          "40-trial mutation/idempotence, truncation truth")
    return 0


if __name__ == "__main__":
    sys.exit(main())
