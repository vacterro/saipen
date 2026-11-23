"""Typed ownership of a validator finding (SRC-276 R005 / F-11).

The measured defect (SRC-276 F-11): the engine returned
``ENGINEERING_REQUIRED`` with ``owner: SAIPEN conformance/remediation`` and
``action: null``, and the host then rendered BOTH an internal engine repair and
a genuinely operator-gated authority grant as one "Blocking actions that need
you" list. Two different obligations collapsed into one human handoff:

* an internal engineering defect this protocol owes -- the agent must be able
  to continue without asking the operator anything, and
* an authority only the operator can grant -- which must never be inferred from
  the mere existence of a finding.

This module is a DERIVED projection, exactly like ``debt._safe_identity``'s
``attributed_work``: it reads a classified finding and answers who owns the
repair and what the one executable safe next action is. It is deliberately NOT
part of ``findings.RULE_TABLE``, is never mixed into ``finding_key`` and never
reaches ``ruleset_fingerprint()`` -- ownership is a routing opinion about a
finding, not part of its identity, so adding it must never stale a debt
snapshot.

Two invariants the rest of the engine depends on:

* a human action is rendered ONLY for ``OPERATOR_DECISION`` AND only when a
  witnessed decision actually exists (``decision`` supplied). The class alone
  never manufactures an operator obligation, and an unwitnessed "decision" is
  not an operator action.
* ``ENGINE_INTERNAL`` never yields a ``saipen start`` in a consumer project.
  The route is engine Work, which is what stops the ENGINEERING_REQUIRED ->
  new consumer start -> ENGINEERING_REQUIRED loop SRC-276 F-01/F-11 reported.
"""

from __future__ import annotations

from .findings import OWNER_CLASSES, OWNER_UNKNOWN

#: What an owner class means as one executable move. A route is a COMMAND
#: STRING for the engine-ownable class and NEVER a mutation for the other two:
#: an operator decision is granted by the operator, and an external obligation
#: is discharged in its own project.
ENGINE_ROUTE = "saipen continue"
OPERATOR_ROUTE = "saipen recover resolve-blocker <SRC-###>"
EXTERNAL_ROUTE = "saipen ticket block <T-###> \"BLOCKED_EXTERNAL: <owner> owes <subject>\""

#: Deterministic rule -> owner map. A rule absent from here is ``UNKNOWN`` on
#: purpose: an unowned family must be loud, never silently engine-ownable.
#:
#: ``source_credential_unsafe`` is the one operator-gated family: no agent may
#: authorize a replacement secret, so the repair needs an operator grant even
#: though the engine performs the refusal.
_RULE_OWNERS: dict[str, str] = {
    # -- intake/source carriers: this protocol owns the archive and ledger.
    "source_receipt_active_invalid": "ENGINE_INTERNAL",
    "source_receipt_clause_drift": "ENGINE_INTERNAL",
    "source_receipt_orphan": "ENGINE_INTERNAL",
    "source_receipt_closed_archive_invalid": "ENGINE_INTERNAL",
    "source_receipt_missing_board": "ENGINE_INTERNAL",
    "source_receipt_index_drift": "ENGINE_INTERNAL",
    "source_receipt_linkage_drift": "ENGINE_INTERNAL",
    "source_receipt_unresolved_work": "ENGINE_INTERNAL",
    # -- Work/LOG hygiene: the engine's own documents and evidence chain.
    "work_closure_evidence": "ENGINE_INTERNAL",
    "legacy_closure_evidence": "ENGINE_INTERNAL",
    "half_claim": "ENGINE_INTERNAL",
    "log_provenance_marker": "ENGINE_INTERNAL",
    "log_ticket_ref": "ENGINE_INTERNAL",
    "log_timestamp_inversion": "ENGINE_INTERNAL",
    "board_soft_cap": "ENGINE_INTERNAL",
    "log_soft_cap": "ENGINE_INTERNAL",
    "changelog_unarchived": "ENGINE_INTERNAL",
    "cross_doc_drift": "ENGINE_INTERNAL",
    "translation_stale": "ENGINE_INTERNAL",
    "wiki_mirror": "ENGINE_INTERNAL",
    "sub_role_revision_legacy": "ENGINE_INTERNAL",
    # -- T-1897: the validator's own manifest/provenance/coverage outputs are
    # this protocol's integrity debt. Each repair is one an agent performs --
    # commit the file or drop the entry, re-verify the closure at the current
    # engine generation, put the document under a check or exempt it. A project
    # whose PUBLICATION is separately gated does not change who owns the
    # finding; that gate is its own blocker, and reading it as this one would
    # hide the manifest defect behind it.
    "runtime_manifest_untracked": "ENGINE_INTERNAL",
    "closure_provenance_drift": "ENGINE_INTERNAL",
    "coverage_gap": "ENGINE_INTERNAL",
    # -- a foreign producer package is fixed where it is produced.
    "producer_package_malformed": "UNAVAILABLE_EXTERNAL",
    # -- only the operator can authorize a replacement credential.
    "source_credential_unsafe": "OPERATOR_DECISION",
}

#: Why a class exists at all, so a report never has to invent prose.
_OWNER_DETAIL = {
    "ENGINE_INTERNAL": (
        "this protocol owes the repair; the safe move is engine Work, and no "
        "operator decision is required to start it"
    ),
    "OPERATOR_DECISION": (
        "an authority only the operator can grant; the decision must be "
        "witnessed and scoped to this exact subject before it is rendered"
    ),
    "UNAVAILABLE_EXTERNAL": (
        "another managed project, host or resource owes it; no local mutation "
        "can discharge it"
    ),
    OWNER_UNKNOWN: (
        "ownership was not established from a known rule; treat as blocking "
        "and diagnose, never as engine-ownable or as a human action"
    ),
}


def owner_class(rule_id: str | None) -> str:
    """The typed owner for one rule id. ``UNKNOWN`` when not established."""
    if not isinstance(rule_id, str):
        return OWNER_UNKNOWN
    return _RULE_OWNERS.get(rule_id, OWNER_UNKNOWN)


def owner_detail(rule_id: str | None) -> str:
    """One sentence naming what the owner class obliges. Never empty."""
    return _OWNER_DETAIL[owner_class(rule_id)]


def safe_next_action(
    finding: dict,
    *,
    work: str | None = None,
    source: str | None = None,
    decision: dict | None = None,
) -> dict:
    """The ONE executable safe move for this finding, or none.

    Returns ``{"owner_class", "route", "operator_action_due", "detail"}``:

    * ``operator_action_due`` is True ONLY for a witnessed ``OPERATOR_DECISION``
      whose ``decision`` names this subject. That is the single value a host may
      render as a human obligation (OPERATOR-QUESTION-01's
      ``operator_action_due``).
    * ``route`` is None when no class establishes one: an ``UNKNOWN`` owner and
      an unwitnessed operator class both refuse to invent a move, and the
      detail says so. Refusing is the fail-closed answer, not a crash.
    """
    owner = owner_class(finding.get("rule_id"))
    detail = _OWNER_DETAIL[owner]
    if owner == "ENGINE_INTERNAL":
        return {
            "owner_class": owner,
            "route": ENGINE_ROUTE,
            "operator_action_due": False,
            "detail": detail,
        }
    if owner == "UNAVAILABLE_EXTERNAL":
        ticket = work or "<T-###>"
        return {
            "owner_class": owner,
            "route": EXTERNAL_ROUTE.replace("<T-###>", ticket),
            "operator_action_due": False,
            "detail": detail,
        }
    if owner == "OPERATOR_DECISION":
        witnessed = _witnesses_decision(decision, finding, source)
        return {
            "owner_class": owner,
            "route": OPERATOR_ROUTE if witnessed else None,
            "operator_action_due": witnessed,
            "detail": detail
            if witnessed
            else (
                "no witnessed operator decision names this subject, so no human "
                "action is rendered; the finding stays blocking and fail-closed"
            ),
            "decision": decision if witnessed else None,
        }
    return {
        "owner_class": OWNER_UNKNOWN,
        "route": None,
        "operator_action_due": False,
        "detail": detail,
    }


def _witnesses_decision(decision: dict | None, finding: dict, source: str | None) -> bool:
    """Is this a REAL operator decision about THIS subject?

    A decision is witness-bearing only when it carries an operator-origin
    witness AND names the finding's own subject (or the supplied source). A
    model-supplied capsule, an unrelated subject, or a bare ``{"decision": ...}``
    with no witness is refused: the class alone never manufactures authority.
    """
    if not isinstance(decision, dict):
        return False
    witness = str(decision.get("witness") or "").strip().lower()
    if witness not in ("operator", "operator_supplied", "operator_origin"):
        return False
    subject = str(finding.get("subject_id") or "").strip()
    named = [
        str(value).strip()
        for value in (
            decision.get("subject"),
            decision.get("source"),
            decision.get("work"),
        )
        if value
    ]
    subject = source or subject
    if not subject:
        return False
    return subject in named


def projection(finding: dict, **kwargs) -> dict:
    """Presentation-safe ownership block for a finding: identity + ownership."""
    action = safe_next_action(finding, **kwargs)
    return {
        "rule_id": finding.get("rule_id"),
        "subject_kind": finding.get("subject_kind"),
        "subject_id": finding.get("subject_id"),
        "finding_key": finding.get("finding_key"),
        **action,
    }


def partition(findings: list[dict], **kwargs) -> dict:
    """Group findings by owner class, preserving input order inside a group."""
    groups: dict[str, list[dict]] = {name: [] for name in OWNER_CLASSES}
    groups[OWNER_UNKNOWN] = []
    for finding in findings:
        action = safe_next_action(finding, **kwargs)
        groups[action["owner_class"]].append(
            {**projection(finding, **kwargs), "severity": finding.get("severity")}
        )
    return {
        "groups": groups,
        # The two counts a host must never conflate: what a human owes, and
        # what the engine owes without asking anyone.
        "operator_action_count": sum(
            1 for item in groups["OPERATOR_DECISION"] if item["operator_action_due"]
        ),
        "engine_work_count": len(groups["ENGINE_INTERNAL"]),
        "external_count": len(groups["UNAVAILABLE_EXTERNAL"]),
        "unknown_count": len(groups[OWNER_UNKNOWN]),
    }
