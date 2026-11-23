"""Cheap admission checks before a focused verification pays for its sandbox copy.

Night 8 tried to refuse a run whenever ANY prior record of the same sandbox
scope had measured a copy above the budget. The scope shape is not an identity:
every undeclared focused request on every tree resolves ``{"mode": "FULL",
"trees": []}``, so one 676 s record from a 1.8 GiB tree refused a fresh tiny
project. The same scan also stopped at the first entry >= 60 s, so a 650 s
witness hid behind a 90 s one depending on filename order.

Night 9 answers two different questions separately:

* DETERMINISTIC REFUSAL -- the request cannot run at all: a budget outside the
  focused route's contract, or a pattern set that selects no test file today.
  These are properties of the request, not of the past, so they may block.
* HISTORICAL TIMING ADVISORY -- the measured cost of THIS exact selection on
  THIS exact tree. It predicts cost, cites the witness and names a reachable
  next step. It never denies the run: yesterday's copy time is not a proof
  about today's tree, cache or disk, and a red record says nothing about
  admission.

The advisory matches on the resolved selection AND the source fingerprint, so
a changed tree, a different pattern set or a corpus that grew since the record
is simply not this measurement.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

FOCUSED_RECORD_DIR_REL = ".saipen/evidence/focused-unit"

#: A scope this much cheaper than the budget is never worth advising, even
#: when a record names it: measurement noise on a fast copy can exceed a
#: tiny budget without predicting this run. Kept small because its only job
#: is to point at measurements that are large in absolute terms.
MIN_MEASURED_COPY_S = 60.0


def _focused_cap() -> int:
    """The focused route's own hard ceiling, read from its owner module."""
    from .focused_unit import MAX_SECONDS

    return MAX_SECONDS


def budget_problem(root: Path, patterns: list[str], timeout: int) -> dict | None:
    """Why this request cannot use its budget, or None to proceed.

    Only the request's own contract is checked: the budget must be a positive
    whole number of seconds inside the focused route's limit. A prior slow copy
    is NOT part of this decision -- see :func:`timing_advisory`.
    """
    cap = _focused_cap()
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1:
        return {
            "code": "UNSUPPORTED_VERIFICATION_BUDGET",
            "detail": (
                f"focused timeout must be a positive whole number of seconds; "
                f"the focused route supports 1..{cap} s and the full evidence "
                "route covers a broader run"
            ),
        }
    if timeout > cap:
        return {
            "code": "UNSUPPORTED_VERIFICATION_BUDGET",
            "detail": (
                f"the focused route caps its budget at {cap} s; run the full "
                "evidence route instead of asking focused for a broader budget"
            ),
        }
    return None


def selection_problem(root: Path, patterns: list[str]) -> dict | None:
    """A pattern set that would run no tests, refused before the copy.

    Mirrors `run_focused`'s own no-match ValueError but answers BEFORE the
    sandbox is paid for, through the same selector the resolver uses. Only a
    full miss refuses: a broad pattern that matches today's files proceeds
    even when it also matched yesterday's.
    """
    from .sandbox_scope import select_modules

    tools = Path(root) / "tools"
    if not tools.is_dir():
        # An absent tree is not a dead selection: the run raises its own error
        # rather than having this cheap check guess about a tree it cannot see.
        return None
    _, unmatched = select_modules(Path(root), patterns)
    if not unmatched:
        return None
    return {
        "code": "EMPTY_TEST_SELECTION",
        "detail": (
            "pattern(s) select no test files in tools/ today: "
            + ", ".join(sorted(unmatched))
        ),
        "patterns": sorted(unmatched),
    }


def timing_advisory(
    root: Path,
    patterns: list[str],
    timeout: int,
    *,
    record_dir: Path | None = None,
    fingerprint: str | None = None,
    min_measured_copy_s: float = MIN_MEASURED_COPY_S,
) -> dict | None:
    """Measured cost of this exact selection, or None. NEVER a refusal.

    A record is a witness only when ALL of these hold:

    * it selected the same test modules (``patterns`` equal after dedup);
    * it resolved the same sandbox scope identity;
    * when the caller supplies today's ``fingerprint``, it measured the same
      source tree -- a changed tree is a different subject, not a slower one.

    Every record is scanned (no early break) and the maximum is chosen with a
    deterministic tie-break, so filename order cannot change the answer.
    Corrupt, unreadable or non-matching records are ignored: no evidence means
    no advisory, and the run measures itself for the next caller.
    """
    root = Path(root)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1:
        return None
    from .sandbox_scope import identity as scope_identity, resolve as resolve_scope

    patterns = sorted(set(patterns))
    scope = resolve_scope(root, patterns)
    this_identity = scope_identity(scope)
    directory = record_dir if record_dir is not None else root / FOCUSED_RECORD_DIR_REL
    measured: float | None = None
    witness: dict | None = None
    examined = 0
    try:
        paths = sorted(directory.glob("*.json"))
    except OSError:
        paths = []
    for path in paths:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        recorded_patterns = record.get("patterns")
        if not isinstance(recorded_patterns, list) or any(
            not isinstance(item, str) for item in recorded_patterns
        ):
            continue
        if sorted(set(recorded_patterns)) != patterns:
            continue
        if fingerprint is not None and record.get("fingerprint") != fingerprint:
            continue
        recorded_scope = record.get("sandbox_scope")
        if not isinstance(recorded_scope, dict):
            continue
        try:
            if scope_identity(recorded_scope) != this_identity:
                continue
        except (KeyError, TypeError):
            continue
        timings = record.get("timings_s")
        copy_s = (timings or {}).get("copy_wall_s") if isinstance(timings, dict) else None
        if not isinstance(copy_s, (int, float)) or isinstance(copy_s, bool):
            continue
        examined += 1
        try:
            age_s = max(0.0, time.time() - path.stat().st_mtime)
        except OSError:
            age_s = None
        candidate = {
            "path": path.name,
            "copy_wall_s": float(copy_s),
            "record_age_s": None if age_s is None else round(age_s, 1),
            "verdict": record.get("verdict"),
            "ran": record.get("ran"),
        }
        # Max with a name tie-break: independent of iteration order.
        if measured is None or (float(copy_s), path.name) > (measured, witness["path"]):
            measured = float(copy_s)
            witness = candidate
    if measured is None or measured <= timeout or measured < min_measured_copy_s:
        return None
    cap = _focused_cap()
    if scope["mode"] == "FULL":
        route = (
            "declare every selected module in tools/sandbox_scope.json after a "
            "narrowed run proves it reads no heavy tree, or run the full "
            "evidence route"
        )
    else:
        route = "run the full evidence route"
    if timeout >= cap:
        recommendation = (
            f"this request already sits at the {cap} s focused cap; {route}"
        )
    else:
        recommendation = f"raise the focused budget up to {cap} s, or {route}"
    return {
        "code": "HISTORICAL_TIMING_ADVISORY",
        "detail": (
            f"history, not a refusal: the most expensive prior record of this "
            f"exact selection and tree measured copy_wall_s={measured:.1f}, "
            f"above the whole {timeout}s budget; the run proceeds and measures "
            "itself"
        ),
        "expected_copy_s": measured,
        "budget_s": timeout,
        "scope": this_identity,
        "witness": witness,
        "records_examined": examined,
        "recommendation": recommendation,
    }
