"""RED reproduction for the three handoff P0 defects in `_agent_view_payload`.

Run from the repository root:

    python tools/regression_t2089/t2089_p0_repro.py

Each check prints RED (defect reproduced) or GREEN (defect fixed). The script
exercises the live `tools/saipen.py` module directly, exactly like
`t2089_oracle.py` does.
"""

import importlib.util
import json
import os
import sys

SUBJECT = os.path.join("tools", "saipen.py")


def _load_subject():
    sys.path.insert(0, "tools")
    spec = importlib.util.spec_from_file_location("saipen", SUBJECT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["saipen"] = module
    spec.loader.exec_module(module)
    return module


def _projection_with(groups_spec):
    groups = [
        {
            "shared_blocker_id": f"EX-{i:06d}",
            "blocker_class": "WAIT_USER_DECISION",
            "cause": f"cause {i}",
            "owner": "saipen-cli",
            "root_tickets": [f"T-{i}-{j}" for j in range(roots)],
            "dependent_tickets": [f"T-dep-{i}-{j}" for j in range(deps)],
            "recovery_internally_authorized": False,
            "external_input_required": True,
            "read_only_work_may_proceed": True,
        }
        for i, (roots, deps) in enumerate(groups_spec)
    ]
    items = [f"T-item-{i}" for i in range(sum(d for _, d in groups_spec))]
    return {"groups": groups, "items": items}


def check_p0_a(module):
    """P0-A: group root_ticket_count must equal the true root count."""
    payload = {"blocker_projection": _projection_with([(3, 1)] * 5)}
    view = module._agent_view_payload(payload)
    groups = view["blocker_groups"]
    problems = []
    for idx, group in enumerate(groups):
        expected = 3
        got = group.get("root_ticket_count")
        if got != expected:
            problems.append(
                f"group[{idx}] root_ticket_count={got!r}, expected {expected}"
            )
    return problems


def check_p0_b(module):
    """P0-B: serialized view must honor a hard byte budget on adversarial
    input, and must report truncation honestly."""
    big = "X" * 1_000_000
    payload = {
        "appends": [{"text": big}] * 8,
        "waiting_on_you": [big] * 16,
        "ok": True,
        "code": "STATUS_OK",
    }
    view = module._agent_view_payload(payload)
    blob = json.dumps(view, ensure_ascii=False).encode("utf-8")
    problems = []
    if len(blob) > 32 * 1024:
        problems.append(f"serialized view {len(blob)} bytes exceeds 32 KiB budget")
    if not view.get("truncated"):
        problems.append("truncated=False while adversarial megabyte strings passed")
    return problems


def check_p0_c(module):
    """P0-C: building the view must not mutate the input payload."""
    payload = {
        "ok": True,
        "code": "STATUS_OK",
        "waiting_on_you": ["T-1: decide the thing: " + "y" * 300],
        "appends": [{"text": "a" * 400}],
        "conformance_status": {
            "receipt": {
                "status": "CURRENT_FAIL",
                "validator": "tools/validate.py",
                "disposition": "ENGINEERING_REQUIRED",
                "blocking_findings": {
                    "problem_count": 3,
                    "problems": [{"detail": "deep " * 100}],
                },
                "expensive_history": ["h" * 500] * 50,
            }
        },
        "blocker_projection": _projection_with([(2, 2)] * 6),
    }
    before = json.dumps(payload, sort_keys=True)
    module._agent_view_payload(payload)
    after = json.dumps(payload, sort_keys=True)
    if before != after:
        first_diff = next(
            (
                k
                for k in ("waiting_on_you", "appends", "conformance_status", "blocker_projection")
                if json.dumps(payload.get(k), sort_keys=True)
                not in before
            ),
            None,
        )
        return [f"input payload mutated (first differing key: {first_diff})"]
    return []


def main():
    module = _load_subject()
    results = [
        ("P0-A root_ticket_count", check_p0_a),
        ("P0-B byte budget", check_p0_b),
        ("P0-C input mutation", check_p0_c),
    ]
    red = 0
    for name, check in results:
        problems = check(module)
        if problems:
            red += 1
            print(f"RED  {name}")
            for p in problems:
                print(f"     - {p}")
        else:
            print(f"GREEN {name}")
    print(f"\n{red} RED / {len(results) - red} GREEN")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
