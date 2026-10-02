"""Where execution time goes, derived from the canonical LOG (SRC-108).

TIME IS OBSERVED. TIME DOES NOT DEFINE TRUTH.

The defect class this ends: an operator asking "how long has this Work taken",
"when did real progress last happen" or "what happened today" had to read the
raw LOG and count timestamps by hand, and an agent asked the same question
answered from its own impression of the session. Both answers were
unreproducible.

Everything here is a pure function of events SAIPEN already writes for other
reasons: every LOG event is a durable checkpoint carrying its own UTC minute.
Nothing is written, cached or gated, so deleting this module changes no Work
state, acceptance, PASS or DONE -- telemetry degrades to "unavailable", never
the protocol. Reading the whole history costs about 0.2 s, so aggregation is on
demand and no materialized rollup exists to go stale.

Honesty rules, each a named field rather than a silent assumption:

* LOG timestamps have minute precision; durations are reported in whole
  minutes (`precision: "minute"`), never with invented seconds.
* A silence longer than ``IDLE_GAP_S`` between two checkpoints, or any time
  after a stop checkpoint, is UNOBSERVED: nothing proves execution happened in
  it, so it is not counted as observed time.
* Time is classified from machine-owned events only (phase transitions, claims,
  blocks, stops, finishes, recovery operations). Prose in a RUN line never
  changes a class; what cannot be classified is UNKNOWN.
* A counter the LOG cannot reconstruct (worker generations, agent incarnations,
  manual recoveries in a project whose supervisor writes elsewhere) is reported
  as None, never as zero.

Quality and time stay separate: nothing here reads a verdict to score an agent,
and nothing here feeds a supervisor decision (QUALITY-TIME-01).
"""

from __future__ import annotations

import datetime as dt
import re
import statistics
from pathlib import Path

SCHEMA_VERSION = 1
#: Longer than this between two checkpoints is not observed execution.
IDLE_GAP_S = 30 * 60
PHASES = ("SCOUT", "BUILD", "VERIFY", "REVIEW", "SHIP")
CLASSES = (*PHASES, "RECOVERY", "WAIT", "BLOCKED", "UNKNOWN")
_INACTIVE = frozenset({"WAIT", "BLOCKED"})
_TRANSITION_RE = re.compile(r"^transition to ([A-Z]+)\b")
_RESUME_RE = re.compile(r"\bresumes at ([A-Z]+)\b")
_RECOVERY_OPS = ("reconcile", "log-repair", "recover", "migrate")
_EVIDENCE_MARKERS = ("CORE-UNIT-EVIDENCE ", "REGRESSION-EVIDENCE ")


def _at(event: dict) -> dt.datetime | None:
    raw = str(event.get("date") or "").strip()
    try:
        return dt.datetime.strptime(raw, "%d.%m.%y %H:%M").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def _op(event: dict) -> str:
    return str(event.get("op_id") or "")


def is_progress(event: dict) -> bool:
    """Durable progress, from machine-owned grammar only.

    A phase transition, a finished ticket and an anchored evidence record are
    written by operations that refuse without their preconditions; a RUN line
    saying "build -> done" is a claim and does not count.
    """
    text = str(event.get("text") or "")
    op = _op(event)
    return (
        (op.startswith("transition-") and _TRANSITION_RE.match(text) is not None)
        or (op.startswith("finish-") and "finished" in text)
        or text.startswith(_EVIDENCE_MARKERS)
    )


def load(root: Path | str) -> list[dict]:
    """Timestamped events, oldest first. Events without a date are dropped."""
    from .log import read_history_events

    out = []
    for event in read_history_events(root):
        at = _at(event)
        if at is not None:
            out.append({**event, "at": at})
    return out


def intervals(events: list[dict]) -> list[dict]:
    """One classified interval per pair of consecutive checkpoints.

    The class is the state in force at the interval's START, rebuilt from
    machine-owned events: the active ticket's phase after a transition, a
    claim or a resume; BLOCKED after that ticket is blocked; WAIT when the
    event says so; RECOVERY for a recovery operation; UNKNOWN otherwise.
    """
    ticket: str | None = None
    state = "UNKNOWN"
    stopped = False
    out = []
    for current, following in zip(events, events[1:]):
        text = str(current.get("text") or "")
        op = _op(current)
        subject = current.get("ticket")
        recovery = op.startswith(_RECOVERY_OPS)
        stopped = False
        if op.startswith("stop-") or text.startswith("operator stop"):
            stopped = True
        elif (match := _TRANSITION_RE.match(text)) and op.startswith("transition-"):
            ticket, state = subject, match.group(1) if match.group(1) in PHASES else "UNKNOWN"
        elif op.startswith("claim-") and subject:
            ticket, state = subject, "UNKNOWN"
        elif op.startswith("ticket-") and "unblock" in text and subject:
            resumed = _RESUME_RE.search(text)
            ticket = subject
            state = resumed.group(1) if resumed and resumed.group(1) in PHASES else "UNKNOWN"
        elif op.startswith("ticket-") and "ticket block" in text and subject == ticket:
            state = "BLOCKED"
        elif op.startswith("finish-") and subject == ticket:
            ticket, state = None, "UNKNOWN"
        klass = "WAIT" if text.startswith("WAIT:") else ("RECOVERY" if recovery else state)
        seconds = max(0, int((following["at"] - current["at"]).total_seconds()))
        observed = not stopped and seconds <= IDLE_GAP_S
        out.append(
            {
                "start": current["at"],
                "end": following["at"],
                "seconds": seconds,
                "observed": observed,
                "class": klass if observed else "UNOBSERVED",
                "ticket": ticket,
                "event": current.get("event"),
            }
        )
    return out


def _split_by_local_day(item: dict, tz) -> list[tuple[dt.date, int]]:
    """Seconds of one interval per local calendar day (midnight splits it)."""
    start, end = item["start"].astimezone(tz), item["end"].astimezone(tz)
    parts = []
    while start.date() < end.date():
        midnight = dt.datetime.combine(
            start.date() + dt.timedelta(days=1), dt.time(), tzinfo=start.tzinfo
        )
        parts.append((start.date(), int((midnight - start).total_seconds())))
        start = midnight
    parts.append((start.date(), int((end - start).total_seconds())))
    return parts


def _pace(events: list[dict]) -> dict:
    gaps = [
        int((b["at"] - a["at"]).total_seconds()) for a, b in zip(events, events[1:])
    ]
    if not gaps:
        return {"count": len(events), "average_s": None, "median_s": None, "longest_s": None}
    return {
        "count": len(events),
        "average_s": round(statistics.fmean(gaps)),
        "median_s": round(statistics.median(gaps)),
        "longest_s": max(gaps),
    }


def day(events: list[dict], date: dt.date, tz) -> dict:
    """One local day: observed/active/wait/blocked time and durable counts."""
    buckets = {name: 0 for name in CLASSES}
    for item in intervals(events):
        if not item["observed"]:
            continue
        for when, seconds in _split_by_local_day(item, tz):
            if when == date:
                buckets[item["class"]] += seconds
    todays = [event for event in events if event["at"].astimezone(tz).date() == date]
    observed = sum(buckets.values())
    inactive = sum(buckets[name] for name in _INACTIVE)
    return {
        "date": date.isoformat(),
        "observed_s": observed,
        "active_s": observed - inactive,
        "wait_s": buckets["WAIT"],
        "blocked_s": buckets["BLOCKED"],
        "by_class_s": {name: value for name, value in buckets.items() if value},
        "work_touched": len({e["ticket"] for e in todays if e.get("ticket")}),
        "work_completed": sum(1 for e in todays if _op(e).startswith("finish-")),
        "checkpoints": len(todays),
        "verified_slices": sum(
            1
            for e in todays
            if _op(e).startswith("transition-") and str(e.get("text")).startswith(
                "transition to REVIEW"
            )
        ),
        "recoveries": sum(1 for e in todays if _op(e).startswith(_RECOVERY_OPS)),
        "stops": sum(1 for e in todays if _op(e).startswith("stop-")),
        "agents": sorted({e["agent"] for e in todays if e.get("agent")}),
        "checkpoint_pace": _pace(todays),
        # Not reconstructible from this LOG: the supervisor records them in its
        # own run evidence. None is "unknown", never zero.
        "worker_generations": None,
        "agent_incarnations": None,
        "manual_recoveries": None,
    }


def work(events: list[dict], ticket: str) -> dict:
    """One Work item's time distribution, from its own events and intervals."""
    mine = [event for event in events if event.get("ticket") == ticket]
    if not mine:
        return {"ticket": ticket, "known": False}
    phases = {name: 0 for name in CLASSES}
    observed = 0
    for item in intervals(events):
        if item["observed"] and item["ticket"] == ticket:
            phases[item["class"]] += item["seconds"]
            observed += item["seconds"]
    first = mine[0]["at"]
    progress = next((event for event in mine if is_progress(event)), None)
    finished = next((event for event in mine if _op(event).startswith("finish-")), None)
    return {
        "ticket": ticket,
        "known": True,
        "first_event_at": first.isoformat(),
        "last_event_at": mine[-1]["at"].isoformat(),
        "observed_s": observed,
        "by_class_s": {name: value for name, value in phases.items() if value},
        "time_to_first_progress_s": (
            int((progress["at"] - first).total_seconds()) if progress else None
        ),
        "checkpoints": len(mine),
        "recoveries": sum(1 for event in mine if _op(event).startswith(_RECOVERY_OPS)),
        "agents": sorted({event["agent"] for event in mine if event.get("agent")}),
        "terminal": "DONE" if finished else None,
    }


def current(events: list[dict], state: dict, now: dt.datetime) -> dict:
    """The active Work right now: elapsed, phase elapsed, since checkpoint/progress."""
    task = str(state.get("task") or "")
    last = events[-1]["at"] if events else None
    out = {
        "task": task or None,
        "phase": state.get("phase"),
        "since_checkpoint_s": int((now - last).total_seconds()) if last else None,
        "work_elapsed_s": None,
        "phase_elapsed_s": None,
        "since_progress_s": None,
        "blocked": bool(str(state.get("blocker") or "").strip()),
        "waiting": str(state.get("next_action") or "").startswith("WAIT:"),
    }
    if not task or task == "none":
        return out
    mine = [event for event in events if event.get("ticket") == task]
    claims = [event for event in mine if _op(event).startswith("claim-")]
    started = (claims[-1] if claims else (mine[0] if mine else None))
    if started is not None:
        out["work_elapsed_s"] = int((now - started["at"]).total_seconds())
    phase = str(state.get("phase") or "")
    entered = [
        event
        for event in mine
        if (_op(event).startswith("transition-") and str(event.get("text")).startswith(
            f"transition to {phase}"
        ))
        or (_op(event).startswith("ticket-") and f"resumes at {phase}" in str(event.get("text")))
    ]
    if entered:
        out["phase_elapsed_s"] = int((now - entered[-1]["at"]).total_seconds())
    progressed = [event for event in mine if is_progress(event)]
    if progressed:
        out["since_progress_s"] = int((now - progressed[-1]["at"]).total_seconds())
    return out


def stats(
    root: Path | str,
    *,
    work_id: str | None = None,
    days: int = 1,
    now: dt.datetime | None = None,
    tz=None,
) -> dict:
    """The read-only projection `saipen stats` prints. Never writes."""
    from .codec import read_doc
    from .state import parse_state_or_error

    root = Path(root)
    now = now or dt.datetime.now(dt.timezone.utc)
    tz = tz or now.astimezone().tzinfo
    if not (root / ".saipen" / "LOG.md").is_file():
        return {"ok": False, "code": "TELEMETRY_UNAVAILABLE", "detail": ".saipen/LOG.md is missing"}
    try:
        events = load(root)
    except (OSError, ValueError) as exc:
        return {"ok": False, "code": "TELEMETRY_UNAVAILABLE", "detail": str(exc)}
    payload = {
        "ok": True,
        "code": "STATS",
        "schema": SCHEMA_VERSION,
        "precision": "minute",
        "idle_gap_s": IDLE_GAP_S,
        "timezone": str(tz),
        "authority": "derived from LOG; never decides Work state, acceptance or DONE",
    }
    if work_id:
        payload["work"] = work(events, work_id)
        return payload
    state, _error = parse_state_or_error(read_doc(root / ".saipen" / "STATE.md"))
    payload["current"] = current(events, state or {}, now)
    today = now.astimezone(tz).date()
    payload["days"] = [
        day(events, today - dt.timedelta(days=offset), tz) for offset in range(max(1, days))
    ]
    return payload


def _duration(seconds) -> str:
    if seconds is None:
        return "UNKNOWN"
    minutes = int(seconds) // 60
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def render(payload: dict) -> str:
    """Compact text for an operator; the JSON carries the same numbers."""
    if not payload.get("ok"):
        return f"telemetry unavailable: {payload.get('detail')}"
    lines = []
    if "work" in payload:
        item = payload["work"]
        if not item.get("known"):
            return f"{item['ticket']}: no timestamped events"
        lines += [
            item["ticket"],
            f"  Total observed          {_duration(item['observed_s'])}",
            f"  Time to first progress  {_duration(item['time_to_first_progress_s'])}",
        ]
        lines += [
            f"  {name:<22}  {_duration(seconds)}" for name, seconds in item["by_class_s"].items()
        ]
        lines += [
            f"  Checkpoints             {item['checkpoints']}",
            f"  Recoveries              {item['recoveries']}",
            f"  Terminal                {item['terminal'] or 'open'}",
        ]
        return "\n".join(lines)
    now = payload["current"]
    lines += [
        "CURRENT WORK",
        f"  {now['task'] or 'none'} {now['phase'] or ''}".rstrip(),
        f"  Work elapsed      {_duration(now['work_elapsed_s'])}",
        f"  Phase elapsed     {_duration(now['phase_elapsed_s'])}",
        f"  Since checkpoint  {_duration(now['since_checkpoint_s'])}",
        f"  Since progress    {_duration(now['since_progress_s'])}",
        "  State             "
        + ("blocked" if now["blocked"] else "waiting" if now["waiting"] else "running"),
    ]
    for item in payload["days"]:
        pace = item["checkpoint_pace"]
        lines += [
            "",
            f"DAY {item['date']}",
            f"  Observed          {_duration(item['observed_s'])}",
            f"  Active            {_duration(item['active_s'])}",
            f"  Waiting           {_duration(item['wait_s'])}",
            f"  Blocked           {_duration(item['blocked_s'])}",
            f"  Work touched      {item['work_touched']}",
            f"  Work completed    {item['work_completed']}",
            f"  Checkpoints       {item['checkpoints']}",
            f"  Verified slices   {item['verified_slices']}",
            f"  Recoveries        {item['recoveries']}",
            f"  Pace median/max   {_duration(pace['median_s'])} / {_duration(pace['longest_s'])}",
        ]
    lines.append("(minute precision; gaps over 30m and time after a stop are unobserved)")
    return "\n".join(lines)
