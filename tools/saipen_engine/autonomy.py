"""Bounded progress detection for the legacy crew-only intent loop.

The compatibility ``autonomous_crew_loop`` lives in
:mod:`saipen_engine.intent`; canonical continue/converge and targeted producer
execution have separate CLI routes and do not enter it. This module owns only
the reusable, pure stall detector, so there is no dormant second control flow
with a different blocker taxonomy.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


#: How many recent observations the stall detector actually inspects. The
#: repeat rule needs a bounded window and the oscillation rule looks at six
#: entries; nothing in this module looks further back than that.
RECENT_WINDOW = 6
#: Diagnostic history retained for operators. Older observations keep
#: contributing to aggregate counters but are not kept as full records.
HISTORY_RETENTION = 64


@dataclass
class IterationRecord:
    state_hash: str
    action: str
    reason: str
    result_code: str


class ProgressTracker:
    """Detect repeated or oscillating autonomous-loop observations.

    PERF-007: the detector needs a bounded window, but ``history`` used to
    grow with every recorded observation, so a long-running loop kept every
    record forever to consult the last six. Detection is unchanged -- the
    repeat and oscillation thresholds are the ones that were here -- while the
    retained diagnostic window is now fixed and older observations are folded
    into ``counters``.
    """

    def __init__(self, max_iterations: int = 50, retention: int = HISTORY_RETENTION):
        self.max_iterations = max_iterations
        self.iterations = 0
        self.retention = max(RECENT_WINDOW, int(retention))
        self.history: list[IterationRecord] = []
        #: Aggregate counters for observations no longer retained verbatim.
        self.dropped = 0
        self.counters: Counter = Counter()
        self._repeats: Counter = Counter()

    def record(self, state_hash: str, action: str, reason: str, result_code: str) -> bool:
        """Record an observation; return ``False`` when progress has stalled."""
        self.iterations += 1
        current = (state_hash, action, reason, result_code)
        self._repeats[current] += 1
        self.counters["observations"] += 1
        # The observation is recorded before the terminal checks, so the
        # history always ends with what actually happened and
        # ``stalled_reason`` can describe the failing iteration.
        self._append(state_hash, action, reason, result_code)

        if self.iterations >= self.max_iterations:
            return False

        # `_repeats` counts the whole run, which is exactly the tally the old
        # scan of the unbounded history produced.
        if self._repeats[current] >= 3:
            return False

        recent = [
            (item.state_hash, item.action, item.reason, item.result_code)
            for item in self.history[-RECENT_WINDOW:]
        ]
        return not (
            len(recent) == RECENT_WINDOW
            and recent[0] == recent[2] == recent[4]
            and recent[1] == recent[3] == recent[5]
            and recent[0] != recent[1]
        )

    def _append(self, state_hash: str, action: str, reason: str, result_code: str) -> None:
        self.history.append(IterationRecord(state_hash, action, reason, result_code))
        overflow = len(self.history) - self.retention
        if overflow > 0:
            for _ in range(overflow):
                dropped = self.history.pop(0)
                self.dropped += 1
                self.counters[f"action:{dropped.action}"] += 1

    def stalled_reason(self) -> str:
        if not self.history:
            return "no iterations recorded"
        last = self.history[-1]
        return (
            f"loop stalled after {self.iterations} iterations; "
            f"last action={last.action} reason={last.reason} "
            f"code={last.result_code}"
        )
