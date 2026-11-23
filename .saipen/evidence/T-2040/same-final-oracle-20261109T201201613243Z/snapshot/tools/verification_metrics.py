"""Read-only verification economics from existing execution and request records.

Stored measurements describe recorded work, never current acceptance. Summed
run, module-process and consumer durations are distinct; none measures human
waiting or active implementation. Missing observations remain unknown.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

_STAMP = re.compile(r"-(\d{8}T\d{6}(?:\d{6})?Z)\.json$")
_TICKET = re.compile(r"T-\d+\Z")


def _number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def _sum(values):
    known = [value for value in values if value is not None]
    return round(sum(known), 6) if known else None


def _percentile(values, percent):
    return sorted(values)[max(0, math.ceil(len(values) * percent / 100) - 1)] if values else None


def _objects(directory, diagnostics):
    if directory.is_symlink():
        diagnostics.append({"path": str(directory), "issue": "symlink directory not read"})
        return
    for path in sorted(directory.glob("*.json")):
        try:
            if path.is_symlink() or path.stat().st_size > 32 * 1024 * 1024:
                raise ValueError("non-regular or oversized record")
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict):
                raise ValueError("record is not an object")
        except (OSError, ValueError) as exc:
            diagnostics.append({"path": str(path), "issue": type(exc).__name__})
            continue
        yield path, data


def _record_time(path, data):
    raw = data.get("finished_utc")
    if isinstance(raw, str):
        try:
            at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if at.tzinfo is not None:
                return at.astimezone(timezone.utc)
        except ValueError:
            pass
    match = _STAMP.search(path.name)
    if match:
        for form in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S%fZ"):
            try:
                return datetime.strptime(match[1], form).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
    return None


def _reds(data):
    runs = data.get("runs")
    sources = [data] if data.get("family") == "unit" else \
        (runs if isinstance(runs, list) else [])
    known = bool(sources) and all(isinstance(source, dict)
                                  and isinstance(source.get("red"), list)
                                  and all(isinstance(value, str) for value in source["red"])
                                  for source in sources)
    names = sorted({value for source in sources if isinstance(source, dict)
                   for value in (source["red"] if isinstance(source.get("red"), list) else [])
                   if isinstance(value, str)})
    return names, known


def _records(root, since, diagnostics):
    rows = []
    for folder, family in (("core-unit", "unit"), ("focused-unit", "focused-unit")):
        for path, data in _objects(root / ".saipen/evidence" / folder, diagnostics):
            at = _record_time(path, data)
            if at is None or data.get("family") != family:
                diagnostics.append({"path": str(path), "issue": "unknown date or wrong family"})
                continue
            if at < since:
                continue
            identity = data.get("verification_identity")
            identity_hash = None
            if isinstance(identity, dict) and identity:
                identity_bytes = json.dumps(identity, sort_keys=True).encode()
                identity_hash = hashlib.sha256(identity_bytes).hexdigest()
            stages = data.get("timings_s") or data.get("timings") or {}
            modules = data.get("module_durations_s") or {}
            red, red_known = _reds(data)
            if not red_known:
                diagnostics.append({"path": str(path), "issue": "red inventory unavailable"})
            rows.append({
                "path": path.relative_to(root).as_posix(), "family": family,
                "tier": "FULL" if family == "unit" else "IMPACT"
                if data.get("verification_tier") == "IMPACT"
                and isinstance(data.get("impact_selection"), dict) else "FOCUSED",
                "day": at.date().isoformat(), "fingerprint": data.get("fingerprint"),
                "identity": identity_hash, "duration_s": _number(data.get("duration_s")),
                "recorded_verdict": data.get("verdict"), "red": red,
                "red_inventory_known": red_known,
                "module_process_s": _sum(_number(value) for value in modules.values())
                if isinstance(modules, dict) else None,
                "stages": {key: _number(value) for key, value in stages.items()}
                if isinstance(stages, dict) else {},
            })
    return rows


def _requests(root, since, diagnostics):
    rows = []
    for path, data in _objects(root / ".saipen/cache/verification-observations", diagnostics):
        try:
            stamp = data.get("requested_ns")
            if type(stamp) is not int or stamp < 0:
                raise ValueError("unknown request timestamp")
            at = datetime.fromtimestamp(stamp / 1e9, timezone.utc)
        except (ValueError, OverflowError, OSError):
            diagnostics.append({"path": str(path), "issue": "unknown request timestamp"})
            continue
        if data.get("kind") != "single-flight-request":
            diagnostics.append({"path": str(path), "issue": "unknown request kind"})
            continue
        if at >= since:
            rows.append(data)
    return rows


def _summary(rows):
    durations = [row["duration_s"] for row in rows if row["duration_s"] is not None]
    stage_names = sorted({key for row in rows for key in row["stages"]})
    red = sorted({name for row in rows for name in row["red"]})
    red_samples = sum(row["red_inventory_known"] for row in rows)
    return {
        "records": len(rows), "duration_samples": len(durations),
        "summed_record_wall_s": _sum(durations),
        "median_record_wall_s": statistics.median(durations) if durations else None,
        "p95_record_wall_s": _percentile(durations, 95),
        "summed_module_process_s": _sum(row["module_process_s"] for row in rows),
        "module_process_samples": sum(row["module_process_s"] is not None for row in rows),
        "stage_totals_s": {key: _sum(row["stages"].get(key) for row in rows)
                           for key in stage_names},
        "stage_samples": {key: sum(row["stages"].get(key) is not None for row in rows)
                          for key in stage_names},
        "recorded_verdicts": dict(Counter(str(row["recorded_verdict"]) for row in rows)),
        "recorded_red_ids": red if red or red_samples else None,
        "red_inventory_records": red_samples,
        "red_inventory_unknown_records": len(rows) - red_samples,
    }


def _completed(root, diagnostics):
    from saipen_engine.board import parse_board

    path = root / ".saipen/BOARD.md"
    try:
        board = parse_board(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        diagnostics.append({"path": str(path), "issue": "completion attribution unavailable"})
        return None
    if board["errors"]:
        diagnostics.append({"path": str(path), "issue": "completion attribution invalid"})
        return None
    return {ticket for ticket, row in board["tickets"].items() if row["section"] == "## DONE"}


def collect(root: Path | str, since="2026-08-01") -> dict:
    """Return measurements and their coverage; read no transcript or authority input."""
    root = Path(root).resolve()
    start = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    diagnostics = []
    records = _records(root, start, diagnostics)
    requests = _requests(root, start, diagnostics)
    completed = _completed(root, diagnostics)
    complete = [row for row in requests if row.get("status") == "COMPLETE"]
    reuse_known = [row for row in complete if type(row.get("reused")) is bool]
    feedback = [value for row in complete if (value := _number(row.get("elapsed_wall_s")))
                is not None]
    compatible, generations = Counter(), Counter()
    for row in records:
        if isinstance(row["fingerprint"], str) and row["fingerprint"]:
            generations[row["fingerprint"]] += 1
            if row["identity"]:
                compatible[(row["family"], row["fingerprint"], row["identity"])] += 1
    by_ticket = defaultdict(list)
    for row in requests:
        ticket = row.get("ticket")
        if isinstance(ticket, str) and _TICKET.fullmatch(ticket):
            by_ticket[ticket].append(row)
    full = [row for row in records if row["family"] == "unit"]
    impact = _summary([row for row in records if row["tier"] == "IMPACT"])
    impact.update(measured_wall_s=impact["summed_record_wall_s"],
                  reason=None if impact["records"] else "no typed impact records in this window")
    per_ticket = {
        ticket: {
            "completed": ticket in completed if completed is not None else None,
            "requests": len(rows),
            "timed_requests": sum(_number(row.get("elapsed_wall_s")) is not None for row in rows),
            "summed_request_wall_s": _sum(_number(row.get("elapsed_wall_s")) for row in rows),
            "distinct_execution_records": len({row["record"] for row in rows
                                               if isinstance(row.get("record"), str)}),
        } for ticket, rows in sorted(by_ticket.items())
    }
    return {
        "schema": 1, "advisory": True, "since_utc": since,
        "meaning": "stored observations, not current acceptance or operator elapsed time",
        "implementation_wall_s": None,
        "implementation_unknown": "actual active implementation time was not instrumented",
        "operator_elapsed_wall_s": None,
        "verification_share": None,
        "focused": _summary([row for row in records if row["tier"] == "FOCUSED"]),
        "full": _summary(full),
        "impact": impact,
        "requests": {
            "observed": len(requests), "by_status": dict(Counter(
                str(row.get("status")) for row in requests)),
            "completed": len(complete), "reuse_known": len(reuse_known),
            "reused": sum(row["reused"] for row in reuse_known),
            "cache_hit_rate": sum(row["reused"] for row in reuse_known) / len(reuse_known)
            if reuse_known else None,
            "feedback_samples": len(feedback),
            "median_feedback_wall_s": statistics.median(feedback) if feedback else None,
            "p95_feedback_wall_s": _percentile(feedback, 95),
            "summed_request_wall_s": _sum(_number(row.get("elapsed_wall_s")) for row in requests),
            "coordination_samples": sum(_number(row.get("coordination_wait_wall_s")) is not None
                                        for row in requests),
            "summed_coordination_wall_s": _sum(_number(row.get("coordination_wait_wall_s"))
                                                for row in requests),
            "unattributed_requests": len(requests) - sum(len(rows) for rows in by_ticket.values()),
        },
        "source_generations": len(generations),
        "same_fingerprint_repeat_candidates": sum(count - 1 for count in generations.values()),
        "compatible_repeat_candidates": sum(count - 1 for count in compatible.values()),
        "records_with_compatibility": sum(row["identity"] is not None for row in records),
        "redundant_verification_rate": None,
        "repeat_unknown": "a repeated compatible run may have been explicitly required fresh",
        "full_suite_fraction": len(full) / len(records) if records else None,
        "full_records_by_utc_day": dict(sorted(Counter(row["day"] for row in full).items())),
        "per_ticket": per_ticket,
        "regressions_escaping_earlier_tiers": None,
        "escape_unknown": "records do not prove per-regression earlier-tier coverage",
        "recovery_wall_s": None,
        "diagnostics": diagnostics,
    }


def render(data):
    def seconds(value):
        return "UNKNOWN" if value is None else f"{value:.3f} s"

    def tier(name, row):
        return [name, f"  {row['records']} records ({row['duration_samples']} timed); "
                "summed run wall "
                + seconds(row["summed_record_wall_s"]),
                "  summed known test-module process time "
                + seconds(row["summed_module_process_s"])
                + f" ({row['module_process_samples']} records with module timings)"]

    requests = data["requests"]
    return "\n".join([
        "Verification economics (advisory stored measurements)",
        "IMPLEMENTATION", "  UNKNOWN: " + data["implementation_unknown"],
        *tier("FOCUSED TESTS", data["focused"]),
        *(tier("IMPACT TESTS", data["impact"]) if data["impact"]["records"] else
          ["IMPACT TESTS", "  UNKNOWN: " + data["impact"]["reason"]]),
        *tier("FULL TESTS", data["full"]),
        "WAIT/RECOVERY", "  lock coordination "
        + seconds(requests["summed_coordination_wall_s"]) + "; recovery time UNKNOWN",
        "OTHER", f"  {requests['observed']} requests; {requests['reused']} recorded cache hits "
        f"among {requests['reuse_known']} requests with known reuse",
        "  feedback median/P95 " + seconds(requests["median_feedback_wall_s"]) + " / "
        + seconds(requests["p95_feedback_wall_s"]),
        f"  {data['source_generations']} source generations; "
        f"{len(data['per_ticket'])} tickets with request attribution",
        "  active-development share, operator elapsed time and escaped regressions UNKNOWN",
        "  summed parallel/request durations are not operator waiting time",
        f"  {len(data['diagnostics'])} input diagnostic(s); "
        "JSON includes coverage and ticket detail",
    ])
