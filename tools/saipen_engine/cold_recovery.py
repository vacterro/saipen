"""T-1446: cold recovery package + semantic progress invariant + ingress identity.

Three primitives, one module, zero canonical writes:

- ``recovery_package``: one DERIVED, regenerable carrier (never canonical truth)
  a cold worker reads INSTEAD of walking BOARD/LOG to become actionable. It is
  rebuilt from STATE/BOARD/LOG tail on every call, so it can never drift from
  the protocol authority it projects.
- ``goal_ingress_identity``: deterministic identity over a goal objective plus
  project identity. Equal identity + no new scope => the SAME goal, the reuse
  contract the cc-all incident (T-1449/T-1450) proved missing.
- ``SemanticProgressTracker``: SRP-100's five-cycle semantic no-progress
  contract. Timestamps and heartbeats are not progress; changed source bytes,
  changed authority, or a completed bounded attempt are.

A blocker string is freely readable prose by protocol design, so the package
carries the exact operator-actionable verdicts as structured fields instead of
parsing one.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

NO_PROGRESS_THRESHOLD = 5

STATE_EVENT_RE = re.compile(r"^last_event:\s*(\d+)\s*$", re.MULTILINE)
TICKET_RE = re.compile(r"^- \[[ x/]\] (T-\d+) \[(P\d)\]")
FIELD_RE = re.compile(r"\|\s*([a-z_]+):\s*([^|]+)")
CHECKPOINT_RE = re.compile(r"\[op: checkpoint-[0-9a-f]+\] RUN: (.+)$")
_EVIDENCE_SUFFIXES = ("INCOMPLETE", "NO_EVIDENCE", "UNVERIFIED")

KNOWN_REDS_PREFIXES = (
    "declared unittest family",
    "declared core-unit family",
)
WORKABLE_BLOCKER_PREFIXES = (
    "DUPLICATE GOAL INGRESS",
    "DUPLICATE OF",
    "ACCIDENTAL DUPLICATE INGRESS",
    "INVALID_INVOCATION",
)


def _redact_prose(text: str, limit: int = 80) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def goal_ingress_identity(objective: str, project_identity: str) -> str:
    """Deterministic identity of one semantic goal ingress.

    Pure function over (project identity, normalized objective). No LLM
    similarity, no timestamp: the same operator objective in the same project
    is the SAME ingress forever, which is what makes a repeat idempotent.
    """
    normalized = " ".join(str(objective or "").strip().lower().split())
    payload = f"{str(project_identity or '').strip().lower()}\n{normalized}"
    return "goal-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


#: The ONE class `board.blocker_class` cannot answer for, named here and
#: nowhere else. A dependency pause is recognized protocol state, but
#: `blocker_class` matches the head exactly and the head carries the child
#: ticket (`ACTIVE_DEPENDENCY:T-1446`). Everything else routes to that owner:
#: a second copy of the closed vocabulary is how the operator-gate flag drifted
#: in the first place.
DEPENDENCY_HOLD_PREFIX = "ACTIVE_DEPENDENCY"


def classify_blocker(blocker: str) -> dict:
    """One policy owner for the blocker verdicts a cold worker needs.

    SAIPEN blocker fields are free prose by contract, so the recovery package
    carries these structured judgments instead of making every cold agent
    re-parse the same strings.

    The defect this split ends (T-1429, measured 2026-09-22): ONE flag named
    ``is_operator_gate`` covered every recognized class, so a cold worker read
    ``ACTIVE_DEPENDENCY:T-1446`` and ``HELD -- unmet dependency`` as "a human
    must act", and the package's DUE list published every parked ticket as an
    operator action due NOW. The agent stopped and waited for a person nobody
    had asked for anything.

    * ``is_operator_gate`` -- a HUMAN owns the next move. Narrow, and it is
      `board.deferred_operator_class`, not a second copy of the vocabulary.
    * ``is_parked_hold`` -- recognized and parked, human or not. This is the
      "do not read as a red" judgment the package's DEFERRED list wants.
    * ``is_workable_side_block`` -- duplicate/bounded-evidence classes that
      must never read as a global stop.
    """
    from .board import blocker_class, deferred_operator_class

    text = str(blocker or "").strip()
    upper = " ".join(text.upper().split())
    is_gate = deferred_operator_class(text) is not None
    is_hold = (
        is_gate
        or blocker_class(text) is not None
        or upper.startswith(DEPENDENCY_HOLD_PREFIX)
    )
    duplicate = upper.startswith(WORKABLE_BLOCKER_PREFIXES)
    timeout = (
        "BOUNDED" in upper and ("600-SECOND" in upper or "WINDOW" in upper)
    ) or "TIMEOUT" in upper
    return {
        "is_operator_gate": is_gate,
        "is_parked_hold": is_hold,
        "is_workable_side_block": (duplicate or timeout) and not is_hold,
        "duplicate": duplicate,
        "bounded_timeout": timeout,
    }


@dataclass(frozen=True)
class Observation:
    """One bounded authoritative observation of an autonomous loop."""

    work_id: str
    phase: str
    blocker: str = ""
    next_action: str = ""
    evidence_identities: tuple[str, ...] = ()
    source_identity: str = ""
    authority_state: str = ""
    failure_ids: tuple[str, ...] = ()
    dependencies_terminal: bool = True
    completed_attempt: bool = False
    authoritative_changed: bool = False
    timestamp: str = ""  # deliberately NOT part of any fingerprint
    heartbeat: bool = False  # deliberately NOT part of any fingerprint

    def semantic_fingerprint(self) -> str:
        """Hash of every bounded semantic input; timestamps excluded."""
        payload = "|".join(
            [
                f"work={self.work_id}",
                f"phase={self.phase}",
                f"blocker={_redact_prose(self.blocker, 160)}",
                f"action={_redact_prose(self.next_action, 160)}",
                f"evidence={','.join(sorted(self.evidence_identities))}",
                f"source={self.source_identity}",
                f"authority={self.authority_state}",
                f"failures={','.join(sorted(self.failure_ids))}",
                f"deps_terminal={int(bool(self.dependencies_terminal))}",
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def as_dict(self) -> dict:
        return {
            "work_id": self.work_id,
            "phase": self.phase,
            "blocker": _redact_prose(self.blocker),
            "next_action": _redact_prose(self.next_action),
            "evidence_identities": list(self.evidence_identities),
            "source_identity": self.source_identity,
            "authority_state": self.authority_state,
            "failure_ids": list(self.failure_ids),
            "dependencies_terminal": bool(self.dependencies_terminal),
            "completed_attempt": bool(self.completed_attempt),
            "authoritative_changed": bool(self.authoritative_changed),
            "timestamp": self.timestamp,
        }


class SemanticProgressTracker:
    """Five semantically equivalent no-progress cycles => NO_PROGRESS_LOOP.

    Timestamp-only or heartbeat-only observations are never progress. Changed
    source identity, changed authority state, or a completed bounded attempt
    each make the next equivalent cycle a legitimate new attempt.
    """

    def __init__(self, threshold: int = NO_PROGRESS_THRESHOLD):
        self.threshold = max(2, int(threshold))
        # history entries: (fingerprint, legitimate_new_attempt, heartbeat)
        self.history: list[tuple[str, bool, bool]] = []
        self.observations: list[Observation] = []
        self._fingerprint: str | None = None

    def record(self, observation: Observation) -> bool:
        """Record one observation; False when NO_PROGRESS_LOOP trips.

        A changed semantic fingerprint IS progress (changed source bytes,
        changed authority, changed blocker...), as is an explicitly legitimate
        new attempt. A heartbeat observation is an IN-FLIGHT process, not a
        completed cycle, so it never counts toward the loop threshold.
        """
        fingerprint = observation.semantic_fingerprint()
        legit = (
            bool(observation.authoritative_changed)
            or bool(observation.completed_attempt)
        )
        moved = bool(self.history) and fingerprint != self.history[-1][0]
        self.history.append((fingerprint, legit, bool(observation.heartbeat)))
        self.observations.append(observation)
        self._fingerprint = fingerprint
        if legit or moved or observation.heartbeat:
            return True
        no_progress = sum(
            1 for fp, lg, hb in self.history if fp == fingerprint and not lg and not hb
        )
        return no_progress < self.threshold

    def verdict(self) -> str:
        """RUNNING | PROGRESS | NO_PROGRESS_LOOP (T-1428 precedent)."""
        if not self.history:
            return "RUNNING"
        fingerprint = self.history[-1][0]
        if any(lg for fp, lg, _hb in self.history if fp == fingerprint):
            return "PROGRESS"
        no_progress = sum(
            1 for fp, lg, hb in self.history if fp == fingerprint and not lg and not hb
        )
        if no_progress >= self.threshold:
            return "NO_PROGRESS_LOOP"
        if len(self.history) > 1 and fingerprint != self.history[-2][0]:
            return "PROGRESS"
        return "RUNNING"

    def no_progress_count(self) -> int:
        if not self._fingerprint:
            return 0
        return sum(
            1
            for fp, lg, hb in self.history
            if fp == self._fingerprint and not lg and not hb
        )


def build_recovery_package(
    state_text: str,
    board_text: str,
    log_tail: str,
    *,
    tree_identity: str = "",
    dirty_identity: str = "",
    runtime_state: dict | None = None,
) -> dict:
    """Build the bounded DERIVED recovery carrier from canonical bytes.

    Regenerable by construction: every field is computed from STATE/BOARD/LOG
    on each call. This carrier is DATA, never authority -- a cold worker still
    resolves its action through the canonical router.

    ``runtime_state`` carries runtime-local, reconstructable observations the
    canonical bytes cannot express (canonical root, project identity/lineage,
    watchdog lease observation, claim liveness classification). It is optional
    so the pure-bytes fixture keeps working; absent values surface as empty
    fields, never as inferred truth.
    """
    runtime = dict(runtime_state or {})
    state: dict[str, str] = {}
    for line in str(state_text or "").splitlines():
        kv = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if kv:
            value = kv.group(2).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            state[kv.group(1)] = value
    event_match = STATE_EVENT_RE.search(str(state_text or ""))
    last_event = int(event_match.group(1)) if event_match else None

    todos: list[dict] = []
    doing: list[dict] = []
    blocked: list[dict] = []
    done_ids: set[str] = set()
    fields_full: dict[str, str] = {}
    rnb_full: dict[str, str] = {}
    section = ""
    for line in str(board_text or "").splitlines():
        if line.startswith("## "):
            section = line.strip()
            continue
        match = TICKET_RE.match(line)
        if not match:
            continue
        tid, priority = match.group(1), match.group(2)
        fields = {k: v.strip() for k, v in FIELD_RE.findall(line)}
        entry = {"id": tid, "priority": priority, "fields": fields}
        needs_raw = ""
        marker = "| needs: "
        if marker in line:
            needs_raw = line.split(marker, 1)[1].split("|", 1)[0]
        entry["needs"] = [n for n in re.findall(r"T-\d+", needs_raw)]
        if section == "## DONE":
            done_ids.add(tid)
        elif section == "## TODO":
            todos.append(entry)
        elif section == "## DOING":
            doing.append(entry)
        elif section == "## BLOCKED":
            fields_full[tid] = fields.get("blocker", "")
            rnb_full[tid] = fields.get("retry_not_before", "")
            entry["blocker"] = _redact_prose(fields.get("blocker", ""))
            entry["blocked_on"] = fields.get("blocked_on", "")
            blocked.append(entry)

    deps_ok = {
        entry["id"]: all(n in done_ids for n in entry["needs"]) for entry in todos
    }
    # The seat is the ticket STATE.task names, whatever section holds it: a
    # claimed DOING ticket or a PAUSED BLOCKED corridor is still the Work a
    # cold worker resumes. Only when STATE carries no active task does the
    # first dependency-eligible TODO become the primary mission.
    by_id = {entry["id"]: entry for entry in (*doing, *todos, *blocked)}
    state_task = str(state.get("task") or "").strip()
    if state_task and state_task not in ("", "none") and state_task in by_id:
        active = by_id[state_task]
    else:
        active = next((e for e in todos if deps_ok[e["id"]]), None)
        if active is None and doing:
            active = doing[0]

    checkpoint_match = None
    last_event_line = ""
    for line in str(log_tail or "").splitlines():
        m = CHECKPOINT_RE.search(line)
        if m:
            checkpoint_match = m.group(1).strip()
        ev = re.search(r"\[E-(\d+)\]", line)
        if ev:
            last_event_line = ev.group(1)
    if last_event is None and last_event_line:
        last_event = int(last_event_line)

    # Classify each BLOCKED Work through the ONE blocker policy owner.
    unrelated_reds: list[str] = []
    known_reds: list[str] = []
    deferred: list[dict] = []
    from .board import deferred_state, retry_not_before

    operator_gate_rows: list[dict] = []
    for entry in blocked:
        raw_blocker = fields_full.get(entry["id"], "")
        verdict = classify_blocker(raw_blocker)
        entry["blocker_class"] = (
            "OPERATOR_GATE"
            if verdict["is_operator_gate"]
            else "PARKED_HOLD"
            if verdict["is_parked_hold"]
            else "BOUNDED_EVIDENCE"
            if verdict["is_workable_side_block"]
            else "OTHER"
        )
        if verdict["is_workable_side_block"]:
            known_reds.append(entry["id"])
        elif verdict["is_parked_hold"]:
            deferred.append({"id": entry["id"], "blocker": entry["blocker"]})
            if verdict["is_operator_gate"]:
                # T-1429: only an operator-owned class may carry a due instant,
                # and only the instant decides DUE. No field, no due.
                gate_ticket = {
                    "section": "## BLOCKED",
                    "fields": {
                        "blocker": raw_blocker,
                        "retry_not_before": rnb_full.get(entry["id"], ""),
                    },
                }
                operator_gate_rows.append(
                    {
                        "id": entry["id"],
                        "retry_not_before": retry_not_before(gate_ticket) or "",
                        "state": deferred_state(gate_ticket) or "OPERATOR_GATE_UNDATED",
                    }
                )
        else:
            unrelated_reds.append(entry["id"])

    # EVIDENCE: bounded op receipts from the LOG tail, so a cold worker can
    # locate the last durable operations without walking the journal.
    evidence: list[str] = []
    for line in str(log_tail or "").splitlines():
        for op in re.findall(r"\[op: ([A-Za-z0-9_-]+)\]", line):
            if op not in evidence:
                evidence.append(op)
    evidence = evidence[-8:]

    active_from_blocked = active is not None and any(
        entry is active for entry in blocked
    )
    active_fields = active["fields"] if active else {}

    # DO_NOT_REPEAT: INCOMPLETE/NO_EVIDENCE checkpoint outcomes are the exact
    # actions a cold agent must not burn another run on.
    do_not_repeat: list[str] = []
    for line in str(log_tail or "").splitlines():
        if "-> " + "INCOMPLETE" in line or "-> NO_EVIDENCE" in line:
            m = CHECKPOINT_RE.search(line)
            if m:
                do_not_repeat.append(_redact_prose(m.group(1), 160))
            tid = re.search(r"\[target: (T-\d+)\]", line)
            if tid and tid.group(1) not in known_reds:
                known_reds.append(tid.group(1))

    return {
        "schema_version": 1,
        "carrier": "derived-recovery-package",
        "authority": "STATE/BOARD/LOG remain canonical; this package is regenerable DATA",
        "PROJECT": state.get("saipen_home", ""),
        "CANONICAL_ROOT": runtime.get("canonical_root", ""),
        "PROJECT_IDENTITY": runtime.get("project_identity", ""),
        "PROJECT_LINEAGE": runtime.get("project_lineage", ""),
        "ACTIVE_WORK": active["id"] if active else None,
        "PHASE": state.get("phase", ""),
        "LAST_EVENT": f"E-{last_event}" if last_event else None,
        "LAST_CHECKPOINT": _redact_prose(checkpoint_match) if checkpoint_match else None,
        "LAST_VERIFIED_SLICE": _redact_prose(checkpoint_match) if checkpoint_match else None,
        "TREE_IDENTITY": tree_identity,
        "DIRTY_IDENTITY": dirty_identity,
        "OWNER": (active_fields.get("owner") or "").strip(),
        "CLAIM_TIME": (active_fields.get("claim_time") or "").strip(),
        "CLAIM_SESSION": (active_fields.get("claim_session") or "").strip(),
        "CLAIM_LIVENESS": str(runtime.get("claim_liveness") or ""),
        "MUTATION_LEASE": runtime.get("watchdog") or {},
        "BLOCKER": {
            "id": active["id"] if active else None,
            "unmet_needs": [
                n for n in (active["needs"] if active else []) if n not in done_ids
            ],
        },
        "BLOCKER_SCOPE": (active_fields.get("blocker_scope") or "ticket").strip()
        if active
        else "",
        "BLOCKED_ON": (active_fields.get("blocked_on") or "").strip(),
        "EVIDENCE": evidence,
        "DEFERRED": deferred,
        "OPERATOR_GATES": operator_gate_rows,
        # T-1429: DUE means a HUMAN must act NOW. Only an operator-owned class
        # carrying a machine due instant that has passed qualifies. Publishing
        # every parked ticket here was the false operator stop that ended
        # autonomous runs with nothing for the operator to actually do.
        "DUE": [
            row["id"] for row in operator_gate_rows if row["state"] == "DUE_OPERATOR_ACTION"
        ],
        "DUE_MODEL": "retry_not_before (strict UTC) on an operator-owned blocker; T-1429",
        "KNOWN_REDS": known_reds,
        "UNRELATED_REDS": unrelated_reds,
        "DO_NOT_REPEAT": do_not_repeat,
        "NEXT_ACTION": (
            str(state.get("next_action", ""))
            if (active is None or active_from_blocked)
            else f"PHASE SCOUT {active['id']}"
        ),
        "NEXT_COMMAND": "saipen continue --json",
        "TODO_ELIGIBLE": [
            {"id": e["id"], "priority": e["priority"], "needs": e["needs"]}
            for e in todos
            if deps_ok[e["id"]]
        ],
        "TODO_UNMET": [
            {"id": e["id"], "unmet": [n for n in e["needs"] if n not in done_ids]}
            for e in todos
            if not deps_ok[e["id"]]
        ],
    }
