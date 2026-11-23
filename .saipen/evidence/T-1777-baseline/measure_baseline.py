"""SRC-250 section 2: a reproducible protocol-cost baseline from existing evidence.

    python -B measure_baseline.py <project-root> [--out FILE]

Reads only what the project already records -- the active LOG, the BOARD and
the core-unit family records -- and builds no telemetry of its own. Every
figure names its source. Elapsed time (claim to finish) and an active-time
approximation (the same span with every gap of more than GAP_MIN minutes
between a ticket's own events removed) are reported separately, because
parked and blocked time is not work.
"""

from __future__ import annotations

import datetime as dt
import glob
import json
import os
import re
import statistics
import sys
from pathlib import Path

GAP_MIN = 45
EVENT = re.compile(
    r"^- (\d\d)\.(\d\d)\.(\d\d) (\d\d):(\d\d) \[E-(\d+)\](?: \[parent: E-\d+\])?"
    r"(?: \[(T-\d+)\])?(?: \[agent: [^\]]+\])?(?: \[op: ([^\]]+)\])? (RUN|DEC|ERR|FIX|WAIT|NOTE|[A-Z]+): (.*)$"
)


def parse_log(path: Path) -> list[dict]:
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = EVENT.match(line)
        if not match:
            continue
        day, month, year, hour, minute, number, ticket, op, taxonomy, text = match.groups()
        events.append(
            {
                "at": dt.datetime(2000 + int(year), int(month), int(day), int(hour), int(minute)),
                "event": int(number),
                "ticket": ticket,
                "op": op or "",
                "taxonomy": taxonomy,
                "text": text,
            }
        )
    return events


def percentile(values: list[float], share: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(share * (len(ordered) - 1))))
    return ordered[index]


def summary(values: list[float]) -> dict:
    return {
        "n": len(values),
        "median": round(statistics.median(values), 1) if values else None,
        "p90": round(percentile(values, 0.9), 1) if values else None,
        "max": round(max(values), 1) if values else None,
    }


def main(argv: list[str]) -> int:
    root = Path(argv[0]).resolve()
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else None
    events = parse_log(root / ".saipen" / "LOG.md")
    start, end = events[0]["at"], events[-1]["at"]
    by_ticket: dict[str, list[dict]] = {}
    for event in events:
        if event["ticket"]:
            by_ticket.setdefault(event["ticket"], []).append(event)

    finished = []
    for ticket, own in by_ticket.items():
        finish = [e for e in own if e["text"].startswith("ticket finished via SAIOPS")]
        claims = [e for e in own if e["text"].startswith("claimed via SAIOPS")]
        if not finish or not claims:
            continue
        first, last = claims[0]["at"], finish[-1]["at"]
        span = [e for e in own if first <= e["at"] <= last]
        active = 0.0
        for before, after in zip(span, span[1:]):
            gap = (after["at"] - before["at"]).total_seconds() / 60
            if gap <= GAP_MIN:
                active += gap
        transitions = [e for e in span if e["text"].startswith("transition to ")]
        rework = sum(
            1
            for before, after in zip(transitions, transitions[1:])
            if after["text"].startswith("transition to BUILD")
            and before["text"].split(" -- ")[0].split()[-1] in ("VERIFY", "REVIEW", "SHIP")
        )
        pairs = {e["op"] for e in span if e["text"].startswith("REGRESSION-EVIDENCE ")}
        families = [e for e in span if e["text"].startswith("CORE-UNIT-EVIDENCE ")]
        finished.append(
            {
                "ticket": ticket,
                "elapsed_min": round((last - first).total_seconds() / 60, 1),
                "active_min": round(active, 1),
                "events": len(span),
                "transitions": len(transitions),
                "rework_loops": rework,
                "regression_pairs": len(pairs),
                "family_citations": len(families),
                "family_fail_citations": sum("CORE-UNIT-EVIDENCE FAIL" in e["text"] for e in families),
                "stale_refusals_named": sum("STALE_REGRESSION_EVIDENCE" in e["text"] for e in span),
            }
        )

    records = []
    for path in glob.glob(str(root / ".saipen/evidence/core-unit/*.json")):
        try:
            record = json.load(open(path, encoding="utf-8"))
            at = dt.datetime.strptime(record["finished_utc"], "%Y-%m-%dT%H:%M:%SZ")
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if start - dt.timedelta(hours=3) <= at <= end + dt.timedelta(hours=3):
            records.append(record)
    fingerprints: dict[str, int] = {}
    for record in records:
        fingerprints[record.get("fingerprint", "")] = fingerprints.get(record.get("fingerprint", ""), 0) + 1

    board = (root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
    sections: dict[str, int] = {}
    current = None
    user_waits = 0
    for line in board.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
        elif line.startswith("- [") and current:
            sections[current] = sections.get(current, 0) + 1
            if current == "BLOCKED" and "WAIT_USER_DECISION" in line:
                user_waits += 1

    added = sum(1 for e in events if e["text"].startswith("ticket added via SAIOPS"))
    projected = sum(1 for e in events if e["text"].startswith("user request SRC-"))
    result = {
        "source": "active .saipen/LOG.md, .saipen/BOARD.md, .saipen/evidence/core-unit/*.json",
        "window": {"from": start.isoformat(), "to": end.isoformat(), "events": len(events)},
        "tickets_finished": len(finished),
        "tickets_added": added + projected,
        "elapsed_claim_to_finish_min": summary([t["elapsed_min"] for t in finished]),
        "active_claim_to_finish_min": summary([t["active_min"] for t in finished]),
        "events_per_finished_ticket": summary([float(t["events"]) for t in finished]),
        "rework_loops_total": sum(t["rework_loops"] for t in finished),
        "tickets_with_rework": sum(1 for t in finished if t["rework_loops"]),
        "regression_pairs_per_ticket": summary([float(t["regression_pairs"]) for t in finished]),
        "tickets_measured_more_than_once": sum(1 for t in finished if t["regression_pairs"] > 1),
        "family_runs": {
            "records": len(records),
            "pass": sum(1 for r in records if r.get("verdict") == "PASS"),
            "fail": sum(1 for r in records if r.get("verdict") != "PASS"),
            "hours": round(sum(float(r.get("duration_s") or 0) for r in records) / 3600, 1),
            "minutes_each": summary([float(r.get("duration_s") or 0) / 60 for r in records]),
            "distinct_trees": len(fingerprints),
        },
        "board_sections": sections,
        "blocked_on_operator_decision": user_waits,
        "recovery_operations": sum(1 for e in events if e["op"].startswith(("recover", "reconcile", "repair"))),
        "safety_valve_waits": sum(1 for e in events if "safety valve" in e["text"].lower() and e["taxonomy"] in ("WAIT", "DEC")),
        "corrections_logged": sum(1 for e in events if e["text"].lower().startswith("correction")),
        "per_ticket": sorted(finished, key=lambda t: t["elapsed_min"]),
    }
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if out:
        out.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text if not out else json.dumps({k: v for k, v in result.items() if k != "per_ticket"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
