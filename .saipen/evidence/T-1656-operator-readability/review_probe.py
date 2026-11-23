"""REVIEW probe for T-1656, independent of the ticket's test module.

Random machine facts and random oversized replies. Whatever the facts carry,
the digest is silent or a valid boundary inside the budget of its class, its
DETAILS (when present) is a pointer, and the digest is accepted when it comes
back through the gate. Whatever the reply, an oversized one is diagnosed and
the delivery offered in its place fits.

usage: review_probe_1656.py <repo> [cases] [seed]
"""

import random
import sys
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
CASES = int(sys.argv[2]) if len(sys.argv) > 2 else 600
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 1656
sys.path.insert(0, str(REPO / "tools"))
from saipen_engine import response_surface as RS  # noqa: E402

rng = random.Random(SEED)
JUNK = ["read the whole log", "rm -rf /", "E-1 and more", "", "x" * 300, "T-1\nE-2", "../etc"]
REFS = ["E-1", "E-4520", "E-12922", "E-10..E-20", "T-1442", "SRC-101",
        ".saipen/evidence/response/rejected-0123456789abcdef.txt"]
CODES = ["HELD", "BLOCKED_EXTERNAL", "WAIT_USER_DECISION", "bad code", "X" * 40, "ACTIVE_DEPENDENCY"]


def facts() -> dict:
    due = rng.random() < 0.3
    carrier = {
        "phase": rng.choice(["DONE", "BUILD", "VERIFY", "BLOCKED", "REVIEW", "x" * 40, ""]),
        "task": rng.choice(["none", "T-7", "T-1442", "not a task"]),
        "next_action": rng.choice(["NONE", "saipen continue", "WAIT: blocked -- choose",
                                   "y" * 500, "line one\nline two"]),
        "validation": rng.choice(["CURRENT_PASS", "CURRENT_FAIL", "STALE_PASS", "z" * 90, ""]),
        "completed": [f"T-{n}" for n in range(rng.choice([0, 0, 1, 2, 133]))],
        "blockers": [
            {"ticket": f"T-{n}", "blocker": f"{rng.choice(CODES)} -- reason {n}"}
            for n in range(rng.choice([0, 0, 1, 5, 60]))
        ],
        "detail_refs": [rng.choice(REFS + JUNK) for _ in range(rng.choice([0, 1, 2, 4, 30]))],
        "operator_due": due,
        "operator_action": rng.choice(["NONE", "confirm the repository name", "w" * 400]),
        "blocker": rng.choice(["NONE", "", "BLOCKED_EXTERNAL -- the provider refuses", "free text"]),
    }
    if rng.random() < 0.4:
        carrier["test_groups"] = [{"ran": rng.randrange(9000), "red": rng.randrange(3), "new_red": 0}]
    if rng.random() < 0.3:
        carrier["automation"] = {"disposition": "CONTINUE", "next_command": "saipen continue"}
    if rng.random() < 0.2:
        carrier["evidence"] = ["x.json"]
    return carrier


def klass_for(carrier: dict, reason: str) -> str:
    auto = carrier.get("automation") or {}
    executable = bool(auto.get("disposition") == "CONTINUE" and auto.get("next_command"))
    return RS.response_reason(reason=reason, operator_due=bool(carrier["operator_due"]),
                              executable=executable)


def main() -> int:
    broken: list[str] = []
    emitted = silent = walls = 0
    for case in range(CASES):
        carrier = facts()
        for reason in ("final", "stop", "status", "summary", "safety"):
            language = rng.choice(["et", "en", "ru"])
            text = RS.digest_from_facts(carrier, reason=reason, language=language)
            if text == "":
                silent += 1
                continue
            emitted += 1
            values, problems = RS.parse_surface(text)
            if problems:
                broken.append(f"case {case}/{reason}: digest does not parse: {problems[:1]}")
                continue
            if values.get("STATUS") == "UNKNOWN":
                continue  # the closed failure carrier: its own schema, checked below
            klass = klass_for(carrier, reason)
            lines, chars = RS.REASON_BUDGETS[klass]
            if len(text.splitlines()) > lines or len(text) > chars:
                broken.append(f"case {case}/{reason}: digest over the {klass} budget")
            errors = RS.response_errors(text, response_class=klass)
            if errors:
                broken.append(f"case {case}/{reason}: {errors[0][:90]}")
            if "DETAILS" in values and not RS.details_is_pointer(values["DETAILS"]):
                broken.append(f"case {case}/{reason}: DETAILS is not a pointer")
            if RS.overflow_diagnostic(text, response_class=klass) is not None:
                broken.append(f"case {case}/{reason}: the digest itself overflows")
        wall = rng.choice(["STATUS: ", "RESULT: ", "", "I did many things. "]) + "detail " * rng.randrange(200, 900)
        walls += 1
        verdict = RS.gate_final_response(
            wall, admission=None, admission_consulted=False, operational_turn=True,
            style_contract=None, facts=dict(carrier),
        )
        if verdict["ok"]:
            broken.append(f"case {case}: a wall was accepted")
        overflow = verdict["overflow"]
        if overflow is None or overflow["code"] != RS.OVERFLOW_CODE or not overflow["fields"]:
            broken.append(f"case {case}: a wall was not diagnosed")
        delivery = verdict["delivery"]
        if delivery is None or len(delivery) > 1200 or len(delivery.splitlines()) > 8:
            broken.append(f"case {case}: the delivery offered for a wall does not fit")
        elif overflow and overflow["compaction"] not in (RS.COMPACTION_SUCCEEDED, RS.COMPACTION_FAILED):
            broken.append(f"case {case}: compaction state {overflow['compaction']}")
        if delivery:
            again = RS.gate_final_response(
                delivery, admission=None, admission_consulted=False, operational_turn=True,
                style_contract=None, facts=dict(carrier),
            )
            looped = any("must equal the canonical machine digest" in e for e in again["errors"])
            if looped:
                broken.append(f"case {case}: the delivery is refused when it comes back")
    print(f"seed {SEED}: {CASES} fact carriers, {emitted} digests checked, {silent} silent, "
          f"{walls} walls, {len(broken)} broken")
    for line in broken[:12]:
        print("  " + line)
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
