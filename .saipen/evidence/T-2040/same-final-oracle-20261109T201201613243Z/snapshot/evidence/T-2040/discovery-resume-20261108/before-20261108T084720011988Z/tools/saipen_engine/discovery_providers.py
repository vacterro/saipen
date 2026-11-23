"""Discovery Provider Interface and Registry (SRC-367 Section 8 & 9).

Separates:
- SOURCE_CHANGE_DISCOVERY
- EVIDENCE_GAP_DISCOVERY
- BACKLOG_DISCOVERY
- FAILED_TEST_DISCOVERY
- RESEARCH_QUESTION_DISCOVERY
- RELEASE_GAP_DISCOVERY
- DEPENDENCY_DISCOVERY

Provides reusable, structured evaluation of persistent goals against actual project evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .persistent_goal import (
    PersistentGoal,
    STATUS_ACTIONABLE_GAPS,
    STATUS_BLOCKED_BY_EVIDENCE,
    STATUS_DISCOVERY_REQUIRED,
    STATUS_NO_ADMISSIBLE_WORK,
    STATUS_SATISFIED,
    STATUS_WAITING_AUTHORITY,
    STATUS_WAITING_DEPENDENCY,
)

# Provider Kinds
KIND_SOURCE_CHANGE = "SOURCE_CHANGE_DISCOVERY"
KIND_EVIDENCE_GAP = "EVIDENCE_GAP_DISCOVERY"
KIND_BACKLOG = "BACKLOG_DISCOVERY"
KIND_FAILED_TEST = "FAILED_TEST_DISCOVERY"
KIND_RESEARCH_QUESTION = "RESEARCH_QUESTION_DISCOVERY"
KIND_RELEASE_GAP = "RELEASE_GAP_DISCOVERY"
KIND_DEPENDENCY = "DEPENDENCY_DISCOVERY"

# Completeness Classifications
COMPLETION_FULL = "COMPLETE"
COMPLETION_PARTIAL = "PARTIAL"
COMPLETION_TRUNCATED = "TRUNCATED"
COMPLETION_UNKNOWN = "UNKNOWN"

# Freshness Classifications
FRESHNESS_CURRENT = "CURRENT"
FRESHNESS_STALE = "STALE"
FRESHNESS_UNMEASURED = "UNMEASURED"


@dataclass
class CandidateTask:
    candidate_id: str
    goal_id: str
    title: str
    priority: str = "P2"
    description: str = ""
    scope: str = ""
    target_locator: str = ""
    evidence_source: str = ""
    verification: str = "the requested change is present and demonstrated"
    needs: list[str] = field(default_factory=list)
    risk: str = "low"
    metadata: dict[str, Any] = field(default_factory=dict)
    evidence_fingerprint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProviderEvaluation:
    provider_name: str
    provider_kind: str
    evidence_identity: str
    evidence_freshness: str = FRESHNESS_CURRENT
    satisfaction_status: str = STATUS_ACTIONABLE_GAPS
    actionable_candidates: list[CandidateTask] = field(default_factory=list)
    candidate_ids: list[str] = field(default_factory=list)
    priority: str = "P2"
    dependencies: list[str] = field(default_factory=list)
    verification_criteria: str = ""
    blockers: list[str] = field(default_factory=list)
    completeness_status: str = COMPLETION_FULL
    metrics: dict[str, Any] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["actionable_candidates"] = [c.to_dict() for c in self.actionable_candidates]
        return d


class DiscoveryProvider(Protocol):
    name: str
    kind: str

    def evaluate(self, root: Path, goal: PersistentGoal) -> ProviderEvaluation:
        ...


#: Per-item evidence fields that decide whether ONE procedure's evidence changed.
#: Presentation churn elsewhere in the ledger (counts, timestamps, sources) never
#: reopens an unchanged DONE item; the item's own record does.
_ITEM_EVIDENCE_FIELDS = (
    "id",
    "procedure_id",
    "sub_id",
    "name",
    "symbol",
    "module",
    "rva",
    "va",
    "bytes",
    "size",
    "described",
    "resolved",
    "status",
    "evidence",
    "evidence_sha256",
    "evidence_generation",
    "generation",
    "verification",
    "verified",
    "citation",
    "citations",
)


def _item_identity(gap: Any) -> str:
    """Stable identity of one ledger item, independent of ledger-level churn."""
    if not isinstance(gap, dict):
        return f"id:{str(gap).strip().lower()}"
    item_id = str(gap.get("id") or gap.get("procedure_id") or gap.get("sub_id") or "").strip().lower()
    rva = str(gap.get("rva") or "").strip().lower()
    module = str(gap.get("module") or "").strip().lower()
    return "|".join((module, rva, item_id))


def _item_evidence_generation(
    gap: Any,
    *,
    goal_id: str,
    project_id: str,
    capture_sha: str,
    ledger_patch: str,
) -> str:
    """Per-item evidence generation: the item's own evidence bound to project, capture and patch."""
    if isinstance(gap, dict):
        evidence = {k: gap[k] for k in _ITEM_EVIDENCE_FIELDS if k in gap}
        if not evidence:
            evidence = dict(gap)
    else:
        evidence = {"id": str(gap)}
    payload = {
        "project": str(project_id or "").lower(),
        "goal": str(goal_id or ""),
        "item": _item_identity(gap),
        "capture_sha256": (capture_sha or "").lower(),
        "patch": (ledger_patch or "").lower(),
        "evidence": evidence,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


class EvidenceGapLedgerProvider:
    """Evaluates structured evidence gap ledgers (e.g. procedure inventories, reverse engineering coverage)."""
    name: str = "evidence_gap_ledger"
    kind: str = KIND_EVIDENCE_GAP

    def evaluate(self, root: Path, goal: PersistentGoal) -> ProviderEvaluation:
        source_rel = goal.research_or_work_backlog_source or ".saipen/evidence/coverage_gap.json"
        try:
            source_path = (root / source_rel).resolve()
            root_res = root.resolve()
            if not source_path.is_relative_to(root_res):
                return ProviderEvaluation(
                    provider_name=self.name,
                    provider_kind=self.kind,
                    evidence_identity="escaped",
                    evidence_freshness=FRESHNESS_UNMEASURED,
                    satisfaction_status=STATUS_BLOCKED_BY_EVIDENCE,
                    blockers=[f"Evidence ledger path {source_rel!r} escapes project root"],
                    completeness_status=COMPLETION_UNKNOWN,
                    summary=f"Path traversal detected in evidence source: {source_rel}",
                )
        except Exception as exc:
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity="invalid_path",
                evidence_freshness=FRESHNESS_UNMEASURED,
                satisfaction_status=STATUS_BLOCKED_BY_EVIDENCE,
                blockers=[f"Invalid evidence path: {exc}"],
                completeness_status=COMPLETION_UNKNOWN,
                summary=f"Invalid evidence path {source_rel}: {exc}",
            )

        if not source_path.is_file():
            # Check alternative locations
            alt = root / ".saipen" / "evidence" / "gap_ledger.json"
            if alt.is_file():
                source_path = alt.resolve()
            else:
                return ProviderEvaluation(
                    provider_name=self.name,
                    provider_kind=self.kind,
                    evidence_identity="absent",
                    evidence_freshness=FRESHNESS_UNMEASURED,
                    satisfaction_status=STATUS_NO_ADMISSIBLE_WORK,
                    blockers=[f"Evidence ledger file missing: {source_rel}"],
                    completeness_status=COMPLETION_UNKNOWN,
                    summary=f"Evidence ledger missing at {source_rel}",
                )

        try:
            content = source_path.read_text(encoding="utf-8")
            data = json.loads(content)
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        except (OSError, ValueError) as exc:
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity="unreadable",
                evidence_freshness=FRESHNESS_UNMEASURED,
                satisfaction_status=STATUS_BLOCKED_BY_EVIDENCE,
                blockers=[f"Evidence ledger unreadable: {exc}"],
                completeness_status=COMPLETION_UNKNOWN,
                summary=f"Failed to parse evidence ledger: {exc}",
            )

        # Expected format:
        # Native BZ coverage schema (with data["counts"] and data["gap"]),
        # flat schema { "total": N, "resolved": M, "gaps": [...], "target_coverage_percent": X },
        # or list of item records.
        total = 0
        resolved = 0
        anchored = 0
        gap_count_explicit = 0
        gaps: list[dict[str, Any]] = []
        counts: dict[str, Any] = {}

        if isinstance(data, dict):
            counts = data.get("counts") if isinstance(data.get("counts"), dict) else {}
            total = int(
                counts.get("procedures")
                or counts.get("total_procedures")
                or counts.get("total")
                or data.get("total_procedures")
                or data.get("total_items")
                or data.get("total")
                or 0
            )
            resolved = int(
                counts.get("described_procedures")
                or counts.get("resolved")
                or data.get("described_procedures")
                or data.get("resolved_items")
                or data.get("resolved")
                or 0
            )
            anchored = int(
                counts.get("anchored_procedures")
                or counts.get("anchored")
                or data.get("anchored_procedures")
                or data.get("anchored")
                or 0
            )
            gap_count_explicit = int(
                counts.get("gap_procedures")
                or counts.get("gaps")
                or data.get("gap_count")
                or data.get("gaps_count")
                or 0
            )
            items = (
                data.get("gap")
                or data.get("gaps")
                or data.get("gap_entries")
                or data.get("unresolved")
                or []
            )
            if isinstance(items, list):
                gaps = [item for item in items if isinstance(item, (dict, str))]
            elif isinstance(data.get("procedures"), list):
                # Full inventory list
                for p in data["procedures"]:
                    if isinstance(p, dict) and not p.get("described") and not p.get("resolved"):
                        gaps.append(p)
            # If total was not explicitly set but items list exists
            if total == 0 and isinstance(data.get("procedures"), list):
                total = len(data["procedures"])
                resolved = total - len(gaps)
            elif total == 0 and gaps:
                total = len(gaps) + resolved
        elif isinstance(data, list):
            total = len(data)
            for item in data:
                if isinstance(item, dict):
                    if not item.get("resolved") and not item.get("described") and not item.get("status") in ("resolved", "done"):
                        gaps.append(item)
                    else:
                        resolved += 1
                elif isinstance(item, str):
                    gaps.append({"id": item, "name": item})

        # Check empty or unknown denominator
        if total <= 0:
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity=f"sha256:{digest}",
                evidence_freshness=FRESHNESS_UNMEASURED,
                satisfaction_status=STATUS_NO_ADMISSIBLE_WORK,
                blockers=["Evidence ledger has empty or unknown denominator (total=0)"],
                completeness_status=COMPLETION_UNKNOWN,
                metrics={
                    "total": total,
                    "resolved": resolved,
                    "gap_count": len(gaps),
                    "current_coverage_percent": 0.0,
                    "target_coverage_percent": float(goal.success_criteria.get("coverage_percent", 100.0)),
                },
                summary=f"Evidence ledger total={total}; empty denominator does not establish complete coverage",
            )

        # Inconsistent metrics check
        if resolved > total:
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity=f"sha256:{digest}",
                evidence_freshness=FRESHNESS_CURRENT,
                satisfaction_status=STATUS_BLOCKED_BY_EVIDENCE,
                blockers=[f"Inconsistent coverage metrics: resolved ({resolved}) > total ({total})"],
                completeness_status=COMPLETION_UNKNOWN,
                metrics={
                    "total": total,
                    "resolved": resolved,
                    "gap_count": len(gaps),
                },
                summary="Evidence ledger is inconsistent: resolved exceeds total",
            )

        # Extract capture and source lineage. Lineage is validated BEFORE any
        # success verdict: a ledger that satisfies coverage but cannot bind the
        # exact executable and patch it measured fails closed (SRC-380 P0-01/P0-02).
        sources = data.get("sources") if isinstance(data, dict) and isinstance(data.get("sources"), dict) else {}
        capture = sources.get("capture") if isinstance(sources.get("capture"), dict) else {}
        capture_sha = str(capture.get("sha256") or data.get("capture_sha256") or "").strip().lower()
        capture_path = str(capture.get("path") or data.get("capture_path") or "")

        required_capture_sha = str(
            goal.success_criteria.get("capture_sha256")
            or goal.admission_policy.get("required_capture_sha256")
            or ""
        ).strip().lower()

        required_patch = str(
            goal.success_criteria.get("target_patch")
            or goal.success_criteria.get("patch")
            or goal.admission_policy.get("required_patch")
            or ""
        ).strip().lower()

        ledger_patch = str(
            capture.get("patch")
            or data.get("patch")
            or data.get("target_patch")
            or capture.get("version")
            or ""
        ).strip().lower()

        # Provenance of the capture digest. A self-reported SHA is not
        # authenticated executable provenance; only bytes this provider can
        # derive the digest from count as VERIFIED.
        capture_provenance = "UNREQUIRED"
        if capture_sha:
            capture_provenance = "SELF_REPORTED"
            if capture_path:
                try:
                    candidate_path = (root / capture_path).resolve()
                    if candidate_path.is_file() and candidate_path.is_relative_to(root.resolve()):
                        blob = candidate_path.read_bytes()
                        if hashlib.sha256(blob).hexdigest().lower() == capture_sha:
                            capture_provenance = "VERIFIED"
                except (OSError, ValueError):
                    capture_provenance = "SELF_REPORTED"
        elif required_capture_sha:
            capture_provenance = "MISSING"

        lineage_metrics = {
            "total": total,
            "resolved": resolved,
            "gap_count": gap_count_explicit or len(gaps),
            "capture_sha256": capture_sha,
            "capture_provenance": capture_provenance,
            "target_patch": ledger_patch,
            "covered_external_bytes": 0,
        }

        def _blocked(identity: str, blocker: str, summary: str) -> ProviderEvaluation:
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity=identity,
                evidence_freshness=FRESHNESS_UNMEASURED,
                satisfaction_status=STATUS_BLOCKED_BY_EVIDENCE,
                blockers=[blocker],
                completeness_status=COMPLETION_UNKNOWN,
                metrics=dict(lineage_metrics),
                summary=summary,
            )

        if required_capture_sha:
            if not capture_sha:
                return _blocked(
                    "unverifiable_capture",
                    f"Evidence ledger lacks required capture SHA (expected {required_capture_sha[:16]})",
                    f"Missing capture lineage: required {required_capture_sha}, ledger provides none",
                )
            if capture_sha != required_capture_sha:
                return _blocked(
                    "mismatched_capture",
                    f"Evidence ledger capture sha {capture_sha[:16]} does not match goal requirement {required_capture_sha[:16]}",
                    f"Capture lineage mismatch: required {required_capture_sha}, got {capture_sha}",
                )
            if capture_provenance != "VERIFIED":
                # Recorded, not fatal: a self-reported digest may still direct
                # bounded work, it just cannot certify completion (below).
                pass

        if required_patch:
            if not ledger_patch:
                return _blocked(
                    "absent_patch",
                    f"Evidence ledger provides no patch identity; goal requires {required_patch!r}",
                    f"Missing required patch identity: expected {required_patch}, ledger provides none",
                )
            if ledger_patch != required_patch:
                return _blocked(
                    "mismatched_patch",
                    f"Evidence ledger patch {ledger_patch!r} does not match goal requirement {required_patch!r}",
                    f"Patch lineage mismatch: required {required_patch}, got {ledger_patch}",
                )

        target_coverage = float(goal.success_criteria.get("coverage_percent", 100.0))
        current_coverage = (resolved / total * 100.0)

        # Producer pagination / truncation: an honestly bounded enumeration is
        # TRUNCATED and can never read as complete or satisfied.
        page = data.get("page") if isinstance(data, dict) and isinstance(data.get("page"), dict) else {}
        truncated = bool(isinstance(data, dict) and data.get("truncated"))
        if data.get("complete") is False or page.get("complete") is False:
            truncated = True
        page_cursor = str(page.get("next_cursor") or data.get("next_cursor") or "")
        if page_cursor:
            truncated = True

        enumerated = len(gaps)
        unresolved = gap_count_explicit or enumerated

        if truncated:
            completeness = COMPLETION_TRUNCATED
        elif enumerated:
            completeness = COMPLETION_PARTIAL
        elif unresolved > 0:
            # A positive unresolved count with nothing enumerated is an
            # incomplete inventory, never exhausted research (SRC-380 P1-03).
            completeness = COMPLETION_PARTIAL
        else:
            completeness = COMPLETION_FULL

        # Coverage tiers stay distinct: documentation is not independent
        # verification (SRC-380 P0-05).
        independent_count = 0
        if isinstance(counts, dict) or isinstance(data, dict):
            risk_counts = counts if isinstance(counts, dict) else {}
            independent_count = int(
                risk_counts.get("independently_verified_procedures")
                or risk_counts.get("verified_procedures")
                or (data.get("counts") or {}).get("independently_verified_procedures")
                or data.get("independently_verified_procedures")
                or 0
            )
        require_independent = bool(goal.success_criteria.get("require_independent_verification")) or bool(
            isinstance(counts, dict) and "independently_verified_procedures" in counts
        )
        independent_shortfall = total - independent_count

        if completeness is COMPLETION_PARTIAL and unresolved > 0 and enumerated == 0:
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity=f"sha256:{digest}",
                evidence_freshness=FRESHNESS_CURRENT,
                satisfaction_status=STATUS_DISCOVERY_REQUIRED,
                blockers=[
                    f"Ledger declares {unresolved} unresolved procedure(s) but enumerates {enumerated}; "
                    "incomplete inventory is not exhausted research -- re-run the bounded producer"
                ],
                completeness_status=COMPLETION_PARTIAL,
                metrics={**lineage_metrics, "unresolved": unresolved, "enumerated": enumerated},
                summary=f"Incomplete inventory: {unresolved} unresolved declared, {enumerated} enumerated",
            )

        if (
            not truncated
            and not gaps
            and (gap_count_explicit == 0)
            and current_coverage >= target_coverage
            and resolved >= total
            and (not required_capture_sha or capture_provenance == "VERIFIED")
            and (not require_independent or independent_count >= total)
        ):
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity=f"sha256:{digest}",
                evidence_freshness=FRESHNESS_CURRENT,
                satisfaction_status=STATUS_SATISFIED,
                actionable_candidates=[],
                candidate_ids=[],
                completeness_status=COMPLETION_FULL,
                metrics={
                    "total": total,
                    "resolved": resolved,
                    "anchored": anchored,
                    "gap_count": 0,
                    "current_coverage_percent": current_coverage,
                    "target_coverage_percent": target_coverage,
                    "inventoried": total,
                    "semantically_described": resolved,
                    "independently_verified": independent_count,
                    "unresolved": 0,
                    "capture_sha256": capture_sha,
                    "capture_provenance": capture_provenance,
                    "target_patch": ledger_patch,
                },
                summary=f"Goal satisfied: coverage {current_coverage:.1f}% >= target {target_coverage:.1f}% ({resolved}/{total})",
            )

        if (
            not truncated
            and not gaps
            and (gap_count_explicit == 0)
            and current_coverage >= target_coverage
            and resolved >= total
            and required_capture_sha
            and capture_provenance != "VERIFIED"
        ):
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity=f"sha256:{digest}",
                evidence_freshness=FRESHNESS_CURRENT,
                satisfaction_status=STATUS_BLOCKED_BY_EVIDENCE,
                blockers=[
                    f"Capture digest {capture_sha[:16]} is declared by the ledger but its derivation cannot be verified "
                    f"(capture path {capture_path!r}); a self-reported SHA is not authenticated executable provenance"
                ],
                completeness_status=COMPLETION_UNKNOWN,
                metrics={**lineage_metrics, "inventoried": total, "semantically_described": resolved},
                summary=f"Capture provenance unverified for {capture_sha}",
            )

        if (
            not truncated
            and not gaps
            and (gap_count_explicit == 0)
            and current_coverage >= target_coverage
            and resolved >= total
            and require_independent
            and independent_count < total
        ):
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity=f"sha256:{digest}",
                evidence_freshness=FRESHNESS_CURRENT,
                satisfaction_status=STATUS_DISCOVERY_REQUIRED,
                blockers=[
                    f"Independent verification shortfall: {independent_count} of {total} procedure(s) independently "
                    f"verified; documented coverage alone does not establish semantic completion"
                ],
                completeness_status=COMPLETION_PARTIAL,
                metrics={
                    **lineage_metrics,
                    "inventoried": total,
                    "semantically_described": resolved,
                    "independently_verified": independent_count,
                    "independent_shortfall": independent_shortfall,
                    "unresolved": unresolved,
                },
                summary=f"Documentation complete but only {independent_count}/{total} independently verified",
            )

        # Parse board to evaluate candidate eligibility against full authoritative inventory
        board_sections = None
        try:
            from .replenishment import _is_candidate_duplicate, _parse_board_tickets
            board_sections = _parse_board_tickets(root)
        except Exception:
            board_sections = None

        # Durable cursor management
        if not isinstance(goal.resume_metadata, dict):
            goal.resume_metadata = {}
        if goal.resume_metadata.get("source_digest") != digest:
            goal.resume_metadata["cursor_index"] = 0
            goal.resume_metadata["source_digest"] = digest

        cursor = int(goal.resume_metadata.get("cursor_index", 0))
        if cursor >= len(gaps) and gaps:
            cursor = 0
            goal.resume_metadata["cursor_index"] = 0

        # Build bounded candidate tasks from eligible gaps across the full inventory
        candidates: list[CandidateTask] = []
        candidate_ids: list[str] = []
        limit = int(goal.admission_policy.get("max_candidates_per_evaluation", 10))

        # Re-order gaps starting from cursor so traversal resumes efficiently
        ordered_gaps = gaps[cursor:] + gaps[:cursor] if (cursor > 0 and cursor < len(gaps)) else gaps

        for idx, gap in enumerate(ordered_gaps):
            if isinstance(gap, dict):
                rva = str(gap.get("rva") or "")
                va = str(gap.get("va") or "")
                nbytes = gap.get("bytes")
                module = gap.get("module")
                name = str(gap.get("name") or (f"sub_{rva}" if rva else gap.get("id") or ""))
                item_id = str(gap.get("id") or gap.get("procedure_id") or name or rva)
                
                if rva:
                    desc = f"Reverse engineer and document semantics for procedure {name} at RVA {rva} ({nbytes} bytes, capture sha256:{capture_sha[:16]})"
                    verify = f"Procedure {name} (RVA {rva}) documented with decompiled semantic behavior, caller/callee evidence, and verified decompilation against capture {capture_sha[:16]}"
                    prio = "P1" if (isinstance(nbytes, int) and nbytes > 1000) else str(gap.get("priority") or "P2")
                    scope = f"rva:{rva}"
                    target_locator = rva
                else:
                    desc = str(gap.get("description") or f"Investigate and document semantics for unresolved item {item_id}")
                    verify = str(gap.get("verify") or f"unresolved item {item_id} is documented and semantics verified")
                    prio = str(gap.get("priority") or "P2")
                    scope = f"item:{item_id}"
                    target_locator = item_id

                task_meta = {
                    "item_id": item_id,
                    "goal_id": goal.goal_id,
                    "rva": rva,
                    "va": va,
                    "bytes": nbytes,
                    "module": module,
                    "capture_sha256": capture_sha,
                    "capture_path": capture_path,
                }
            else:
                item_id = str(gap)
                name = item_id
                desc = f"Investigate and document semantics for unresolved procedure {item_id}"
                verify = f"procedure {item_id} semantics documented with caller/callee evidence"
                prio = "P2"
                scope = f"item:{item_id}"
                target_locator = item_id
                task_meta = {"item_id": item_id, "goal_id": goal.goal_id}

            cid = f"{goal.goal_id}-{item_id}".replace(" ", "_")
            task = CandidateTask(
                candidate_id=cid,
                goal_id=goal.goal_id,
                title=f"Investigate semantics of {name} [{goal.goal_id}]",
                priority=prio,
                description=desc,
                scope=scope,
                target_locator=target_locator,
                evidence_source=source_rel,
                verification=verify,
                risk="low",
                metadata=task_meta,
                evidence_fingerprint=_item_evidence_generation(
                    gap,
                    goal_id=goal.goal_id,
                    project_id=goal.project_id,
                    capture_sha=capture_sha,
                    ledger_patch=ledger_patch,
                ),
            )

            # Eligibility filter: filter completed, active, blocked and duplicate candidates before admission
            if board_sections is not None:
                is_dup, dup_reason = _is_candidate_duplicate(task, board_sections)
                if is_dup:
                    continue

            candidates.append(task)
            candidate_ids.append(cid)
            real_index = (cursor + idx + 1) % len(gaps) if gaps else 0
            goal.resume_metadata["cursor_index"] = real_index
            if len(candidates) >= limit:
                break

        # Distinguish the 7 required coverage tiers in metrics:
        cited_count = int(
            counts.get("topic_cited_procedures")
            or counts.get("any_cited_procedures")
            or (data.get("counts") or {}).get("topic_cited_procedures")
            or 0
        ) if isinstance(data, dict) else 0
        interface_only_count = int(
            counts.get("interface_only_procedures")
            or (data.get("counts") or {}).get("interface_only_procedures")
            or 0
        ) if isinstance(data, dict) else 0

        eval_metrics = {
            "total": total,
            "resolved": resolved,
            "anchored": anchored,
            "gap_count": gap_count_explicit or len(gaps),
            "current_coverage_percent": current_coverage,
            "target_coverage_percent": target_coverage,
            "inventoried": total,
            "semantically_described": resolved,
            "cited": cited_count,
            "interface_only": interface_only_count,
            "unresolved": unresolved,
            "enumerated": enumerated,
            "independently_verified": independent_count,
            "independent_shortfall": max(0, independent_shortfall),
            "capture_sha256": capture_sha,
            "capture_provenance": capture_provenance,
            "target_patch": ledger_patch,
        }

        blockers = []
        if truncated:
            blockers.append(
                f"Bound producer enumeration is incomplete ({enumerated} of {unresolved or enumerated} "
                f"unresolved item(s) enumerated); next page {page_cursor!r}"
                if page_cursor
                else f"Bound producer enumeration is incomplete ({enumerated} of {unresolved or enumerated} unresolved item(s) enumerated)"
            )
        if enumerated < unresolved:
            blockers.append(
                f"Inventory incomplete: {unresolved - enumerated} unresolved procedure(s) are declared but not enumerated"
            )

        return ProviderEvaluation(
            provider_name=self.name,
            provider_kind=self.kind,
            evidence_identity=f"sha256:{digest}",
            evidence_freshness=FRESHNESS_CURRENT,
            satisfaction_status=STATUS_ACTIONABLE_GAPS if candidates else STATUS_NO_ADMISSIBLE_WORK,
            actionable_candidates=candidates,
            candidate_ids=candidate_ids,
            blockers=blockers,
            completeness_status=completeness,
            metrics=eval_metrics,
            summary=f"Discovered {len(gaps)} actionable gaps ({len(candidates)} candidate tasks ready) in {source_rel}",
        )


class BacklogProvider:
    """Evaluates backlog task lists."""
    name: str = "backlog"
    kind: str = KIND_BACKLOG

    def evaluate(self, root: Path, goal: PersistentGoal) -> ProviderEvaluation:
        source_rel = goal.research_or_work_backlog_source or ".saipen/backlog/items.json"
        try:
            source_path = (root / source_rel).resolve()
            root_res = root.resolve()
            if not source_path.is_relative_to(root_res):
                return ProviderEvaluation(
                    provider_name=self.name,
                    provider_kind=self.kind,
                    evidence_identity="escaped",
                    evidence_freshness=FRESHNESS_UNMEASURED,
                    satisfaction_status=STATUS_BLOCKED_BY_EVIDENCE,
                    blockers=[f"Backlog path {source_rel!r} escapes project root"],
                    completeness_status=COMPLETION_UNKNOWN,
                    summary=f"Path traversal detected in backlog source: {source_rel}",
                )
        except Exception as exc:
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity="invalid_path",
                evidence_freshness=FRESHNESS_UNMEASURED,
                satisfaction_status=STATUS_BLOCKED_BY_EVIDENCE,
                blockers=[f"Invalid backlog path: {exc}"],
                completeness_status=COMPLETION_UNKNOWN,
                summary=f"Invalid backlog path {source_rel}: {exc}",
            )

        if not source_path.is_file():
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity="absent",
                evidence_freshness=FRESHNESS_UNMEASURED,
                satisfaction_status=STATUS_NO_ADMISSIBLE_WORK,
                blockers=[f"Backlog source missing: {source_rel}"],
                summary="Backlog source file missing",
            )
        try:
            content = source_path.read_text(encoding="utf-8")
            items = json.loads(content)
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        except (OSError, ValueError) as exc:
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity="unreadable",
                evidence_freshness=FRESHNESS_UNMEASURED,
                satisfaction_status=STATUS_BLOCKED_BY_EVIDENCE,
                blockers=[f"Backlog unreadable: {exc}"],
                summary=f"Failed to parse backlog: {exc}",
            )

        if not isinstance(items, list):
            items = items.get("items", []) if isinstance(items, dict) else []

        if not items:
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity=f"sha256:{digest}",
                evidence_freshness=FRESHNESS_UNMEASURED,
                satisfaction_status=STATUS_NO_ADMISSIBLE_WORK,
                blockers=["Backlog is empty (total_items=0)"],
                completeness_status=COMPLETION_UNKNOWN,
                actionable_candidates=[],
                candidate_ids=[],
                metrics={"total_items": 0, "pending_items": 0},
                summary="Backlog is empty; empty denominator does not establish complete coverage",
            )

        pending = [item for item in items if isinstance(item, dict) and not item.get("done") and not item.get("closed")]
        if not pending:
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity=f"sha256:{digest}",
                evidence_freshness=FRESHNESS_CURRENT,
                satisfaction_status=STATUS_SATISFIED,
                actionable_candidates=[],
                candidate_ids=[],
                completeness_status=COMPLETION_FULL,
                metrics={"total_items": len(items), "pending_items": 0},
                summary=f"All {len(items)} backlog items completed",
            )

        candidates = []
        candidate_ids = []
        for item in pending[:10]:
            cid = f"{goal.goal_id}-{item.get('id', len(candidates)+1)}"
            candidates.append(CandidateTask(
                candidate_id=cid,
                goal_id=goal.goal_id,
                title=str(item.get("title", f"Backlog item {cid}")),
                priority=str(item.get("priority", "P2")),
                description=str(item.get("description", "")),
                verification=str(item.get("verify", "the requested change is present and demonstrated")),
                needs=list(item.get("needs") or []),
            ))
            candidate_ids.append(cid)

        return ProviderEvaluation(
            provider_name=self.name,
            provider_kind=self.kind,
            evidence_identity=f"sha256:{digest}",
            evidence_freshness=FRESHNESS_CURRENT,
            satisfaction_status=STATUS_ACTIONABLE_GAPS,
            actionable_candidates=candidates,
            candidate_ids=candidate_ids,
            metrics={"total_items": len(items), "pending_items": len(pending)},
            summary=f"{len(pending)} pending backlog items discovered",
        )


class FailedTestProvider:
    """Evaluates failing tests and regressions against canonical core-unit evidence."""
    name: str = "failed_tests"
    kind: str = KIND_FAILED_TEST

    def evaluate(self, root: Path, goal: PersistentGoal) -> ProviderEvaluation:
        evidence_dir = root / ".saipen" / "evidence" / "core-unit"
        if not evidence_dir.is_dir():
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity="absent",
                evidence_freshness=FRESHNESS_UNMEASURED,
                satisfaction_status=STATUS_NO_ADMISSIBLE_WORK,
                completeness_status=COMPLETION_UNKNOWN,
                summary="No test evidence recorded",
                metrics={"classification": "MISSING_EVIDENCE"},
            )

        from .core_unit import tree_fingerprint, full_scope_problem, FAMILY_NAME
        try:
            current_fp = tree_fingerprint(root)
        except Exception:
            current_fp = ""

        # Collect and parse all candidate records
        parsed_records: list[dict[str, Any]] = []
        has_corrupt = False
        corrupt_details: list[str] = []

        for p in evidence_dir.glob("*.json"):
            try:
                content = p.read_text(encoding="utf-8")
                data = json.loads(content)
                if not isinstance(data, dict):
                    has_corrupt = True
                    corrupt_details.append(f"{p.name}: not a JSON object")
                    continue
                finished = data.get("finished_utc")
                ran_val = data.get("ran")
                status_val = data.get("status") or data.get("verdict")
                rec_fp = data.get("fingerprint")
                if not finished or ran_val is None or not status_val or not rec_fp:
                    has_corrupt = True
                    corrupt_details.append(f"{p.name}: missing required schema fields")
                    continue
                digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
                data["_file_path"] = p
                data["_digest"] = digest
                parsed_records.append(data)
            except (OSError, ValueError) as exc:
                has_corrupt = True
                corrupt_details.append(f"{p.name}: {exc}")

        if not parsed_records:
            if has_corrupt:
                return ProviderEvaluation(
                    provider_name=self.name,
                    provider_kind=self.kind,
                    evidence_identity="invalid",
                    evidence_freshness=FRESHNESS_UNMEASURED,
                    satisfaction_status=STATUS_BLOCKED_BY_EVIDENCE,
                    blockers=corrupt_details[:5],
                    completeness_status=COMPLETION_UNKNOWN,
                    summary=f"Invalid or corrupted test evidence records: {corrupt_details[0]}",
                    metrics={"classification": "INVALID_EVIDENCE"},
                )
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity="absent",
                evidence_freshness=FRESHNESS_UNMEASURED,
                satisfaction_status=STATUS_NO_ADMISSIBLE_WORK,
                completeness_status=COMPLETION_UNKNOWN,
                summary="No test records found",
                metrics={"classification": "MISSING_EVIDENCE"},
            )

        # Sort all parsed records by finished_utc descending (strictly chronological execution-time order)
        parsed_records.sort(key=lambda r: str(r.get("finished_utc") or ""), reverse=True)

        matching_current = [r for r in parsed_records if r.get("fingerprint") == current_fp]
        if matching_current:
            authoritative = matching_current[0]
            freshness = FRESHNESS_CURRENT
        else:
            authoritative = parsed_records[0]
            freshness = FRESHNESS_STALE

        digest = authoritative.get("_digest", "unknown")
        ran = int(authoritative.get("ran") or 0)
        rec_fp = str(authoritative.get("fingerprint") or "")

        # Denominator check
        if ran <= 0:
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity=f"sha256:{digest}",
                evidence_freshness=FRESHNESS_UNMEASURED,
                satisfaction_status=STATUS_NO_ADMISSIBLE_WORK,
                blockers=["Test evidence has empty denominator (ran=0)"],
                completeness_status=COMPLETION_UNKNOWN,
                summary="Test evidence reports 0 tests ran; empty denominator does not establish complete coverage",
                metrics={"ran": 0, "classification": "INCOMPLETE_COVERAGE"},
            )

        # Full scope / family check
        scope_issue = full_scope_problem(authoritative)
        if scope_issue or (authoritative.get("family") and authoritative.get("family") != FAMILY_NAME):
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity=f"sha256:{digest}",
                evidence_freshness=freshness,
                satisfaction_status=STATUS_NO_ADMISSIBLE_WORK,
                blockers=[f"Incomplete coverage: {scope_issue or 'record does not cover full unit family'}"],
                completeness_status=COMPLETION_UNKNOWN,
                summary=f"Incomplete coverage: {scope_issue or 'record does not cover full unit family'}",
                metrics={"ran": ran, "classification": "INCOMPLETE_COVERAGE"},
            )

        new_red = authoritative.get("new_red") or []
        red = authoritative.get("red") or []
        failures = authoritative.get("failures") or []
        failing_tests: list[str] = []
        if isinstance(new_red, list) and new_red:
            failing_tests.extend(str(t) for t in new_red)
        if isinstance(red, list) and red:
            for t in red:
                st = str(t)
                if st not in failing_tests:
                    failing_tests.append(st)
        if not failing_tests and isinstance(failures, list) and failures:
            failing_tests.extend([f.get("test") if isinstance(f, dict) else str(f) for f in failures])

        if freshness == FRESHNESS_STALE:
            if not failing_tests and authoritative.get("verdict") == "PASS" and authoritative.get("status") in ("PASS", "CLEAN", "OK"):
                return ProviderEvaluation(
                    provider_name=self.name,
                    provider_kind=self.kind,
                    evidence_identity=f"sha256:{digest}",
                    evidence_freshness=FRESHNESS_STALE,
                    satisfaction_status=STATUS_NO_ADMISSIBLE_WORK,
                    completeness_status=COMPLETION_UNKNOWN,
                    summary=f"Evidence is STALE_PASS: source modified since last run (current tree {current_fp[:16]} != evidence {rec_fp[:16]})",
                    metrics={"ran": ran, "failing_count": 0, "classification": "STALE_PASS", "current_fingerprint": current_fp, "evidence_fingerprint": rec_fp},
                )
            else:
                candidates = []
                candidate_ids = []
                for test_name in failing_tests[:5]:
                    cid = f"{goal.goal_id}-fix-{hashlib.sha256(str(test_name).encode()).hexdigest()[:8]}"
                    candidates.append(CandidateTask(
                        candidate_id=cid,
                        goal_id=goal.goal_id,
                        title=f"Repair failing test {test_name}",
                        priority="P1",
                        description=f"Fix regression in {test_name} (from prior generation {rec_fp[:16]})",
                        verification=f"python -m unittest {test_name}",
                    ))
                    candidate_ids.append(cid)
                return ProviderEvaluation(
                    provider_name=self.name,
                    provider_kind=self.kind,
                    evidence_identity=f"sha256:{digest}",
                    evidence_freshness=FRESHNESS_STALE,
                    satisfaction_status=STATUS_ACTIONABLE_GAPS,
                    actionable_candidates=candidates,
                    candidate_ids=candidate_ids,
                    completeness_status=COMPLETION_UNKNOWN,
                    summary=f"Evidence is STALE_FAIL: newest record failed ({len(failing_tests)} failing) on older tree {rec_fp[:16]}",
                    metrics={"ran": ran, "failing_count": len(failing_tests), "classification": "STALE_FAIL", "current_fingerprint": current_fp, "evidence_fingerprint": rec_fp},
                )

        # Freshness is CURRENT
        if isinstance(new_red, list) and len(new_red) == 0 and len(red) > 0:
            candidates = []
            candidate_ids = []
            for test_name in failing_tests[:5]:
                cid = f"{goal.goal_id}-fix-{hashlib.sha256(str(test_name).encode()).hexdigest()[:8]}"
                candidates.append(CandidateTask(
                    candidate_id=cid,
                    goal_id=goal.goal_id,
                    title=f"Repair baseline failing test {test_name}",
                    priority="P2",
                    description=f"Fix baseline failure in {test_name}",
                    verification=f"python -m unittest {test_name}",
                ))
                candidate_ids.append(cid)
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity=f"sha256:{digest}",
                evidence_freshness=FRESHNESS_CURRENT,
                satisfaction_status=STATUS_ACTIONABLE_GAPS,
                actionable_candidates=candidates,
                candidate_ids=candidate_ids,
                completeness_status=COMPLETION_PARTIAL,
                summary=f"Found {len(failing_tests)} baseline failing tests (0 new regressions, {ran} tests ran)",
                metrics={"ran": ran, "failing_count": len(failing_tests), "new_red_count": 0, "classification": "BASELINE_BLOCKED"},
            )

        if failing_tests or authoritative.get("verdict") == "FAIL" or authoritative.get("status") not in ("PASS", "CLEAN", "OK"):
            candidates = []
            candidate_ids = []
            for test_name in failing_tests[:5]:
                cid = f"{goal.goal_id}-fix-{hashlib.sha256(str(test_name).encode()).hexdigest()[:8]}"
                candidates.append(CandidateTask(
                    candidate_id=cid,
                    goal_id=goal.goal_id,
                    title=f"Repair failing test {test_name}",
                    priority="P1",
                    description=f"Fix legitimate regression in {test_name}",
                    verification=f"python -m unittest {test_name}",
                ))
                candidate_ids.append(cid)
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity=f"sha256:{digest}",
                evidence_freshness=FRESHNESS_CURRENT,
                satisfaction_status=STATUS_ACTIONABLE_GAPS,
                actionable_candidates=candidates,
                candidate_ids=candidate_ids,
                completeness_status=COMPLETION_PARTIAL,
                summary=f"Found {len(failing_tests)} failing tests to repair ({ran} tests ran)",
                metrics={"ran": ran, "failing_count": len(failing_tests), "classification": "CURRENT_FAIL"},
            )

        return ProviderEvaluation(
            provider_name=self.name,
            provider_kind=self.kind,
            evidence_identity=f"sha256:{digest}",
            evidence_freshness=FRESHNESS_CURRENT,
            satisfaction_status=STATUS_SATISFIED,
            actionable_candidates=[],
            candidate_ids=[],
            completeness_status=COMPLETION_FULL,
            summary=f"Test suite clean with zero failures ({ran} tests ran, fingerprint {current_fp[:16]})",
            metrics={"ran": ran, "failing_count": 0, "classification": "CURRENT_PASS"},
        )


class SourceChangeProvider:
    """Wraps git source-change discovery."""
    name: str = "source_change"
    kind: str = KIND_SOURCE_CHANGE

    def evaluate(self, root: Path, goal: PersistentGoal) -> ProviderEvaluation:
        from .continue_fallback import read_marker, source_unchanged
        marker = read_marker(root)
        unchanged, detail = source_unchanged(root, marker)
        if unchanged:
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity=str(marker.get("source_head", "unchanged")),
                evidence_freshness=FRESHNESS_CURRENT,
                satisfaction_status=STATUS_NO_ADMISSIBLE_WORK,
                summary=detail,
            )
        return ProviderEvaluation(
            provider_name=self.name,
            provider_kind=self.kind,
            evidence_identity="source_changed",
            evidence_freshness=FRESHNESS_CURRENT,
            satisfaction_status=STATUS_DISCOVERY_REQUIRED,
            summary=detail,
        )


class AuditInboxProvider:
    """Evaluates audit inbox layers and residue."""
    name: str = "audit_inbox"
    kind: str = "audit_inbox"

    def evaluate(self, root: Path, goal: PersistentGoal) -> ProviderEvaluation:
        from . import audit_inbox
        try:
            st = audit_inbox.status(root)
        except Exception as exc:
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity="unreadable",
                evidence_freshness=FRESHNESS_UNMEASURED,
                satisfaction_status=STATUS_BLOCKED_BY_EVIDENCE,
                blockers=[f"Failed to inspect audit inbox: {exc}"],
                summary=f"Audit inbox unreadable: {exc}",
            )
        pending = st.get("pending") or []
        residue = st.get("residue") or []
        unbound = st.get("unbound") or []
        all_items = list(pending) + list(residue) + list(unbound)
        if not all_items:
            if st.get("clean"):
                return ProviderEvaluation(
                    provider_name=self.name,
                    provider_kind=self.kind,
                    evidence_identity=f"audit-clean:{len(st.get('layers', []))}",
                    evidence_freshness=FRESHNESS_CURRENT,
                    satisfaction_status=STATUS_SATISFIED,
                    completeness_status=COMPLETION_FULL,
                    metrics={"pending_count": 0, "layers_count": len(st.get("layers", []))},
                    summary="Audit inbox clean with zero pending layers or residue",
                )
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity="empty",
                evidence_freshness=FRESHNESS_UNMEASURED,
                satisfaction_status=STATUS_NO_ADMISSIBLE_WORK,
                completeness_status=COMPLETION_UNKNOWN,
                summary="Audit inbox has no layers",
            )
        candidates = []
        candidate_ids = []
        for item in all_items[:5]:
            rel = str(item.get("rel") if isinstance(item, dict) else item)
            cid = f"{goal.goal_id}-audit-{hashlib.sha256(rel.encode()).hexdigest()[:8]}"
            candidates.append(CandidateTask(
                candidate_id=cid,
                goal_id=goal.goal_id,
                title=f"Consume audit layer {rel}",
                priority="P2",
                description=f"Triage and consume audit inbox entry {rel}",
                verification=f"saipen audit status",
            ))
            candidate_ids.append(cid)
        return ProviderEvaluation(
            provider_name=self.name,
            provider_kind=self.kind,
            evidence_identity=f"audit-pending:{len(all_items)}",
            evidence_freshness=FRESHNESS_CURRENT,
            satisfaction_status=STATUS_ACTIONABLE_GAPS,
            actionable_candidates=candidates,
            candidate_ids=candidate_ids,
            metrics={"pending_count": len(all_items)},
            summary=f"Found {len(all_items)} pending audit inbox items to process",
        )


class ComprehensiveMaintenanceProvider:
    """Multi-signal maintenance provider combining test defects, audit inbox, and backlog."""
    name: str = "comprehensive_maintenance"
    kind: str = "comprehensive_maintenance"

    def evaluate(self, root: Path, goal: PersistentGoal) -> ProviderEvaluation:
        providers = [
            FailedTestProvider(),
            AuditInboxProvider(),
            BacklogProvider(),
        ]
        candidates: list[CandidateTask] = []
        candidate_ids: list[str] = []
        blockers: list[str] = []
        metrics: dict[str, Any] = {}
        all_satisfied = True
        has_actionable = False

        for p in providers:
            res = p.evaluate(root, goal)
            metrics[p.name] = res.metrics
            if res.satisfaction_status != STATUS_SATISFIED:
                all_satisfied = False
            if res.actionable_candidates:
                has_actionable = True
                candidates.extend(res.actionable_candidates)
                candidate_ids.extend(res.candidate_ids)
            if res.blockers:
                blockers.extend(res.blockers)

        if all_satisfied:
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity="multi-signal:satisfied",
                evidence_freshness=FRESHNESS_CURRENT,
                satisfaction_status=STATUS_SATISFIED,
                completeness_status=COMPLETION_FULL,
                metrics=metrics,
                summary="All maintenance signals satisfied (tests clean, audit clear, backlog empty)",
            )
        if has_actionable:
            return ProviderEvaluation(
                provider_name=self.name,
                provider_kind=self.kind,
                evidence_identity="multi-signal:actionable",
                evidence_freshness=FRESHNESS_CURRENT,
                satisfaction_status=STATUS_ACTIONABLE_GAPS,
                actionable_candidates=candidates[:10],
                candidate_ids=candidate_ids[:10],
                blockers=blockers,
                metrics=metrics,
                summary=f"Maintenance has actionable gaps across signals ({len(candidates)} total candidates)",
            )
        return ProviderEvaluation(
            provider_name=self.name,
            provider_kind=self.kind,
            evidence_identity="multi-signal:quiescent",
            evidence_freshness=FRESHNESS_UNMEASURED,
            satisfaction_status=STATUS_NO_ADMISSIBLE_WORK,
            blockers=blockers,
            metrics=metrics,
            summary="No admissible work across maintenance signals; entering quiescence",
        )


# Global Provider Registry
_REGISTRY: dict[str, DiscoveryProvider] = {
    "evidence_gap_ledger": EvidenceGapLedgerProvider(),
    "backlog": BacklogProvider(),
    "failed_tests": FailedTestProvider(),
    "source_change": SourceChangeProvider(),
    "audit_inbox": AuditInboxProvider(),
    "comprehensive_maintenance": ComprehensiveMaintenanceProvider(),
}


def get_provider(name: str) -> DiscoveryProvider | None:
    return _REGISTRY.get(name)


def list_providers() -> list[str]:
    return sorted(_REGISTRY.keys())


def register_provider(name: str, provider: DiscoveryProvider) -> None:
    _REGISTRY[name] = provider

