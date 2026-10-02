"""The conditional efficiency KPI: one derived, approximate view of a ticket (T-1576).

`conditional_efficiency_kpi` is an OPERATOR-ORIENTED APPROXIMATION, not a
physical efficiency measurement. It is derived telemetry, and it is NOT
lifecycle authority, acceptance evidence, a quality verdict or a ranking of
agents or models. QUALITY > TIME: quality stays on its own axis (VALIDATION),
and this value never feeds a lifecycle, validation or routing decision -- the
only importers are the read-only status and response surfaces, which a test
pins. Metrics observe behaviour; they never command it.

It is a VIEW over the LOG the machine already writes (`log.read_history_events`),
never a second lifecycle store, and it reads only machine-owned grammar:
`transition to <PHASE>`, `CORE-UNIT-EVIDENCE PASS|FAIL`, `verify|review ->
PASS|FAIL`, claims, block/unblock/resume and the finish event. A hand-authored
`[op: ...]` line (T-1577) is not evidence here either. The repository's
window metrics reporter under `tools/` stays separate; the engine never
imports it (that dependency is one-way and pinned).

FORMULA v1 (`FORMULA_VERSION`; changing a weight or a rule changes the version):

    progress  35  forward share of the ticket's phase steps; re-entering the
                  phase it is already in is a stall. A step that only resumes
                  the phase after a claim, unblock or dependency resume is not
                  a step, so a legitimate WAIT/BLOCKED costs nothing.
    rework    25  passing gate verdicts over all gate verdicts plus backward
                  phase steps -- a failed rerun and a VERIFY -> BUILD return
                  are both work done twice. A REGRESSION-EVIDENCE FAIL is the
                  required red half of a pair and is not counted.
    autonomy  25  executor continuity: consecutive ticket events by the same
                  agent. COARSE -- LOG agent ids are CLI identities that
                  different sessions share, so a session handoff can be
                  invisible; it always costs one confidence step.
    human     15  WITHHELD in v1: no machine signal separates avoidable
                  operator cost from a legitimate authorization boundary, and
                  inventing one would punish a required human decision.

Time is not an input: minute stamps cannot tell active execution from a
sleeping user, an owner holding the ticket or an intentional soak, so no
calendar duration can lower the value.

The headline is the weight-renormalized mean of the MEASURED components,
rounded to the nearest 5. Confidence describes evidence coverage, never whether
the number looks good: each missing or coarse component is one deficit --
0 HIGH, 1 MED, 2+ LOW -- and fewer than two measured components withholds the
percentage as UNKNOWN. A ticket that has not finished, or whose last gate
verdict is FAIL, or whose terminal validation is not CURRENT_PASS, is marked
PRELIMINARY: a fast broken run can never read as a finished efficient one.
"""

from __future__ import annotations

import re
from pathlib import Path

RULE_ID = "EFFICIENCY-KPI-01"
FORMULA_VERSION = 1
FIELD = "EFFICIENCY"
MACHINE_NAME = "conditional_efficiency_kpi"

#: Weights of formula v1, in render order; they total 100.
WEIGHTS = {"progress": 35, "rework": 25, "autonomy": 25, "human": 15}
#: Components whose evidence is measurable but coarse in v1.
COARSE = frozenset({"autonomy"})
HUMAN_WITHHELD = (
    "no machine signal separates avoidable operator cost from a legitimate authorization boundary"
)
INSUFFICIENT = "insufficient ticket-scoped telemetry"
NO_TICKET = "no ticket attribution; no session KPI is derived in formula v1"

#: The one-line budget, owned beside the value so the response surface reads it.
LINE_CHAR_BUDGET = 240

_PHASE_RANK = {"SCOUT": 0, "BUILD": 1, "VERIFY": 2, "REVIEW": 3, "SHIP": 4}
_TRANSITION = re.compile(r"^transition to (SCOUT|BUILD|VERIFY|REVIEW|SHIP)\b")
_GATE = re.compile(r"^(?:CORE-UNIT-EVIDENCE (PASS|FAIL)\b|(?:verify|review) -> (PASS|FAIL)\b)")
_CLAIM = re.compile(r"^claimed via SAIOPS\b")
_RESUME = re.compile(r"^(?:claimed via SAIOPS|ticket unblock via SAIOPS|blocked parent resumed)\b")
_FINISH = re.compile(r"^ticket finished via SAIOPS -- completion\b")
_TERMINAL_OK = "CURRENT_PASS"

#: The rendered line, and nothing else: an approximate headline, a coverage
#: word and every component, or an honest UNKNOWN with its reason.
_LINE = re.compile(
    r"^(?:PRELIMINARY )?~(?P<percent>\d{1,3})% (?:HIGH|MED|LOW)"
    r"(?P<components>(?: \| (?:progress|rework|autonomy|human) (?:\d{1,3}|n/a)){4})$"
)
_UNKNOWN_LINE = re.compile(r"^UNKNOWN \| [^\r\n|]+$")


def _round5(value: float) -> int:
    """Half-up to the nearest 5 -- deterministic, never banker's rounding."""
    return int(5 * int(value / 5 + 0.5))


def _hand_authored(event: dict) -> bool:
    from .journal import op_id_provenance

    return op_id_provenance(event.get("op_id")) == "hand_authored"


def kpi_for_ticket(
    events: list[dict], ticket: str | None, *, validation: str | None = None
) -> dict:
    """The KPI for one ticket over parsed LOG events (pure and deterministic)."""
    if not ticket:
        return {
            "scope": "session",
            "ticket": None,
            "percent": None,
            "approximate": True,
            "confidence": "UNKNOWN",
            "formula_version": FORMULA_VERSION,
            "components": dict.fromkeys(WEIGHTS),
            "preliminary": True,
            "withheld": NO_TICKET,
        }
    own = [ev for ev in events if ev.get("ticket") == ticket and not _hand_authored(ev)]
    forward = stalls = backward = 0
    passes = fails = 0
    last_gate = None
    finished = False
    current = None
    previous_text = ""
    for ev in own:
        text = str(ev.get("text", ""))
        taxonomy = ev.get("taxonomy")
        if taxonomy == "DEC" and _CLAIM.match(text):
            current = _PHASE_RANK["SCOUT"]
        if taxonomy == "DEC" and _FINISH.match(text):
            finished = True
        if taxonomy == "RUN":
            step = _TRANSITION.match(text)
            if step:
                rank = _PHASE_RANK[step.group(1)]
                if current is None or rank > current:
                    forward += 1
                elif rank < current:
                    backward += 1
                elif not _RESUME.match(previous_text):
                    stalls += 1
                current = rank
            gate = _GATE.match(text)
            if gate:
                last_gate = gate.group(1) or gate.group(2)
                if last_gate == "PASS":
                    passes += 1
                else:
                    fails += 1
        previous_text = text

    components: dict[str, int | None] = dict.fromkeys(WEIGHTS)
    notes: dict[str, str] = {"human": HUMAN_WITHHELD}
    steps = forward + stalls
    if steps >= 2:
        components["progress"] = round(100 * forward / steps)
    rework_total = passes + fails + backward
    if passes + fails:
        components["rework"] = round(100 * passes / rework_total)
    pairs = max(len(own) - 1, 0)
    if pairs:
        handoffs = sum(
            1 for before, after in zip(own, own[1:]) if before.get("agent") != after.get("agent")
        )
        components["autonomy"] = round(100 * (pairs - handoffs) / pairs)
        notes["autonomy"] = "coarse: LOG agent ids are CLI identities shared across sessions"

    measured = [name for name, value in components.items() if value is not None]
    preliminary = (
        not finished
        or last_gate == "FAIL"
        or (validation is not None and validation != _TERMINAL_OK)
    )
    result = {
        "scope": "ticket",
        "ticket": ticket,
        "percent": None,
        "approximate": True,
        "confidence": "UNKNOWN",
        "formula_version": FORMULA_VERSION,
        "components": components,
        "notes": notes,
        "preliminary": preliminary,
        "withheld": INSUFFICIENT,
    }
    if len(measured) < 2:
        return result
    weight = sum(WEIGHTS[name] for name in measured)
    headline = sum(WEIGHTS[name] * components[name] for name in measured) / weight
    deficits = (len(WEIGHTS) - len(measured)) + len(COARSE & set(measured))
    result.update(
        percent=_round5(headline),
        confidence="HIGH" if deficits == 0 else "MED" if deficits == 1 else "LOW",
        withheld=None,
    )
    return result


def kpi_for_project(root: Path | str, ticket: str | None, *, validation: str | None = None) -> dict:
    """The KPI for one ticket of a project, read from its complete LOG history."""
    from .log import read_history_events

    return kpi_for_ticket(list(read_history_events(Path(root))), ticket, validation=validation)


def render_line(kpi: dict) -> str:
    """The one EFFICIENCY line for a KPI record -- the only renderer."""
    if kpi.get("percent") is None:
        reason = str(kpi.get("withheld") or INSUFFICIENT).replace("|", "/")
        return f"UNKNOWN | {reason}"[:LINE_CHAR_BUDGET]
    parts = [
        f"{'PRELIMINARY ' if kpi.get('preliminary') else ''}~{kpi['percent']}% {kpi['confidence']}"
    ]
    for name in WEIGHTS:
        value = kpi["components"].get(name)
        parts.append(f"{name} {'n/a' if value is None else value}")
    return " | ".join(parts)


def line_problem(value: object) -> str | None:
    """Why a rendered EFFICIENCY value breaks the grammar, or None."""
    text = str(value if value is not None else "").strip()
    if "\n" in text:
        return "EFFICIENCY is one line"
    if len(text) > LINE_CHAR_BUDGET:
        return f"EFFICIENCY exceeds {LINE_CHAR_BUDGET} characters"
    if _UNKNOWN_LINE.match(text):
        return None
    match = _LINE.match(text)
    if not match:
        return (
            "EFFICIENCY must read `~NN% HIGH|MED|LOW | progress N | rework N | "
            "autonomy N | human N` (n/a for a withheld component) or "
            "`UNKNOWN | <reason>`"
        )
    percent = int(match.group("percent"))
    if percent > 100 or percent % 5:
        return "EFFICIENCY headline is a multiple of 5 between 0 and 100"
    names = re.findall(r"\| (\w+) ", match.group("components"))
    if names != list(WEIGHTS):
        return "EFFICIENCY lists progress, rework, autonomy, human in that order"
    if any(int(v) > 100 for v in re.findall(r"\b(\d{1,3})\b", match.group("components"))):
        return "EFFICIENCY components lie between 0 and 100"
    return None
