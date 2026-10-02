"""Real HUSH runtime -- EXEC-HUSH-01 (T-1236).

`hush <task>` is an EXECUTION-POLICY MODIFIER, not a phase and not a command.
The lifecycle it wraps is the lifecycle it would have had without it: same
resolver, same Work, same phases, same tools, same source intake, same audit
inbox, same evidence, same recovery, same safety gates. Only narration
changes. That equivalence is the whole contract -- a HUSH that quietly picked
a different route would be a second execution model wearing a formatting flag.

Shape of one activation:

    hush cc
      -> strip the modifier            (this module)
      -> resolve `cc` normally         (commands.py / the router)
      -> run the normal route          (unchanged)
      -> suppress DISCRETIONARY output (this module's classifier)
      -> emit the bounded final report
      -> eject                         (task-local; never persisted)

Two invariants carry the risk.

**Mandatory output is not suppressible.** Safety and destructive
authorization, a missing human decision, terminal failure, protocol
corruption, an externally visible side effect needing acknowledgement, and the
final evidence report always print. A policy that could silence a
confirmation prompt would turn a formatting preference into a safety defect,
so the classifier answers from a CLOSED mandatory set and every unknown kind
is treated as mandatory rather than optional.

**It does not leak.** The policy lives in the resolution that created it and
is never written to `STATE.md`. A next task that did not ask for HUSH gets the
default policy, because there is nowhere for the old one to have been stored.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

RULE_ID = "EXEC-HUSH-01"
MODIFIER = "hush"

# Output kinds HUSH may drop. Everything here is a convenience for a human
# watching the run; nothing here is evidence.
DISCRETIONARY = frozenset(
    {
        "preamble",
        "progress",
        "plan",
        "tool_narration",
        "success_chatter",
        # T-1419 EXEC-RESPONSE-01: the optional DETAILS block is renderable
        # chatter, not control surface. HUSH may drop it and may NOT drop any
        # mandatory field (STATUS/RESULT/BLOCKER/OPERATOR ACTION/NEXT EXACT
        # ACTION/VALIDATION), so the control surface has one schema under both
        # policies.
        "details",
    }
)

# Output kinds HUSH may NEVER drop. This set is closed on purpose and the
# classifier fails toward it: an unrecognized kind prints.
MANDATORY = frozenset(
    {
        "safety_refusal",
        "destructive_confirmation",
        "missing_authority",
        "terminal_failure",
        "protocol_corruption",
        "side_effect_acknowledgement",
        "final_report",
        "evidence",
    }
)

FINAL_REPORT_MAX_LINES = 20
INTERMEDIATE = DISCRETIONARY - {"details"}
#: An EFFICIENCY field or its rendered headline (T-1576) -- final boundary only.
_KPI_LINE = re.compile(
    r"(?im)^\s*EFFICIENCY\b|conditional_efficiency_kpi|"
    r"^\s*(?:PRELIMINARY\s+)?~\d{1,3}%\s+(?:HIGH|MED|LOW)\s+\|"
)


def progress_requested(request: object) -> bool:
    """Conservative affirmative ingress grammar; quoted/negated text cannot opt in."""
    if not isinstance(request, str):
        return False
    return bool(re.fullmatch(
        r"\s*(?:please\s+)?(?:keep me updated|show (?:me )?progress|"
        r"tell me after every phase|explain what you(?: are|'re) doing|"
        r"anna vahearuandeid|näita edenemist|hoia mind kursis|"
        r"сообщай о ходе работы|держи меня в курсе|показывай прогресс)\s*[.!]?\s*",  # noqa: RUF001
        request, re.IGNORECASE,
    ))


@dataclass(frozen=True)
class Policy:
    """One task-local execution policy. Immutable; created per resolution."""

    hushed: bool = False
    progress_authorized: bool = False

    def suppresses(self, kind: str) -> bool:
        """May this output kind be dropped under the current policy?

        Mandatory and unknown kinds remain visible. Default execution drops
        intermediate narration unless this ingress explicitly requested it.
        HUSH additionally drops discretionary final detail.
        """
        if kind in MANDATORY:
            return False
        if self.hushed:
            return kind in DISCRETIONARY
        return kind in INTERMEDIATE and not self.progress_authorized

    def describe(self) -> dict:
        return {
            "rule_id": RULE_ID,
            "execution_policy": "hush" if self.hushed else "default",
            "silent_execution": not self.progress_authorized or self.hushed,
            "progress_authorized": self.progress_authorized and not self.hushed,
            "suppressed": sorted(k for k in DISCRETIONARY if self.suppresses(k)),
            "mandatory": sorted(MANDATORY),
            "final_report_max_lines": FINAL_REPORT_MAX_LINES if self.hushed else None,
        }


DEFAULT = Policy(hushed=False)
HUSHED = Policy(hushed=True)


def for_request(request: object) -> Policy:
    """One turn's policy; no preference leaks to the next human ingress."""
    return Policy(progress_authorized=progress_requested(request))


def intermediate_verdict(text: str, *, request: str = "", kind: str = "progress") -> dict:
    """Host boundary for model commentary; runtime/heartbeat data stay separate."""
    policy = for_request(request)
    if policy.suppresses(kind) and text.strip():
        return {"ok": False, "code": "INTERMEDIATE_TEXT_SUPPRESSED", "emit": False}
    # T-1576: the efficiency KPI is a FINAL-boundary field. Even authorized
    # progress chat may not carry it -- that is the KPI heartbeat silent
    # execution forbids.
    if kind in INTERMEDIATE and _KPI_LINE.search(text):
        return {
            "ok": False,
            "code": "INTERMEDIATE_TEXT_SUPPRESSED",
            "emit": False,
            "reason": "kpi_heartbeat",
        }
    if kind in INTERMEDIATE and text.strip():
        from .chat_style import chat_style_errors, running_style_contract

        errors = chat_style_errors(text, contract=running_style_contract())
        if errors:
            return {"ok": False, "code": "CHAT_STYLE_DRIFT", "emit": False, "errors": errors}
    return {"ok": True, "code": "OUTPUT_ALLOWED", "emit": bool(text.strip())}


def strip_modifier(message: str) -> tuple[Policy, str]:
    """Split a leading `hush` modifier off a task. Returns (policy, task).

    Only a LEADING whole token counts. `hush` inside a task ("ship the hush
    docs") is ordinary text: a modifier that could be triggered from the middle
    of a payload would let arbitrary prose change execution policy.

    A bare `hush` with no task is NOT an activation -- there is nothing to
    modify -- and comes back as the default policy with an empty task, which
    the caller reports rather than guessing an objective.
    """
    if not isinstance(message, str):
        return DEFAULT, ""
    text = message.strip()
    if not text:
        return DEFAULT, ""
    head, _, rest = text.partition(" ")
    if head.lower() != MODIFIER:
        return DEFAULT, text
    task = rest.strip()
    if not task:
        return DEFAULT, ""
    return HUSHED, task


def activate(message: str) -> dict:
    """Mechanical projection of one `hush <task>` resolution.

    Returns the policy plus the EXACT task text to hand to the normal
    resolver. This function decides nothing about routing on purpose -- that
    is what makes `hush cc` and `cc` provably the same route.
    """
    policy, task = strip_modifier(message)
    return {
        "ok": bool(task) or not message.strip().lower().startswith(MODIFIER),
        "code": "HUSH_ACTIVATED" if policy.hushed else "HUSH_NOT_ACTIVE",
        "policy": policy,
        "task": task,
        **policy.describe(),
    }
