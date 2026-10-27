"""Handoff reconciliation and pre-admission delta classification (SRC-323).

Defines bounded pre-admission analysis and clause-by-clause evidence matrices
to evaluate substantial incoming handoffs before creating redundant Work.
Enables evidence-backed zero-delta canonical settlement without operator cycles.
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import re
import subprocess
from pathlib import Path
from typing import Any

from . import codec, debt, effects, intake
from .board import parse_board
from .paths import project_lineage_identity

# Pre-admission result classes (SRC-323 §4)
EXACT_DUPLICATE = "EXACT_DUPLICATE"
EXISTING_IMPLEMENTATION_VERIFIED = "EXISTING_IMPLEMENTATION_VERIFIED"
EXISTING_IMPLEMENTATION_UNVERIFIED = "EXISTING_IMPLEMENTATION_UNVERIFIED"
PARTIAL_OVERLAP = "PARTIAL_OVERLAP"
NEW_IMPLEMENTATION_REQUIRED = "NEW_IMPLEMENTATION_REQUIRED"
REGRESSION_DETECTED = "REGRESSION_DETECTED"
CHANGED_ACCEPTANCE_CONTRACT = "CHANGED_ACCEPTANCE_CONTRACT"
INDEPENDENT_OPERATOR_GATE = "INDEPENDENT_OPERATOR_GATE"
UNKNOWN = "UNKNOWN"

ALL_RESULT_CLASSES = {
    EXACT_DUPLICATE,
    EXISTING_IMPLEMENTATION_VERIFIED,
    EXISTING_IMPLEMENTATION_UNVERIFIED,
    PARTIAL_OVERLAP,
    NEW_IMPLEMENTATION_REQUIRED,
    REGRESSION_DETECTED,
    CHANGED_ACCEPTANCE_CONTRACT,
    INDEPENDENT_OPERATOR_GATE,
    UNKNOWN,
}

# Clause-level equivalence verdicts (SRC-323 §5)
VERDICT_VERIFIED = "VERIFIED"
VERDICT_UNVERIFIED = "UNVERIFIED"
VERDICT_MISSING = "MISSING"
VERDICT_REGRESSION = "REGRESSION"
VERDICT_CHANGED_CONTRACT = "CHANGED_CONTRACT"
VERDICT_OPERATOR_GATE = "INDEPENDENT_OPERATOR_GATE"
VERDICT_UNKNOWN = "UNKNOWN"


@dataclasses.dataclass
class ClauseEvidenceRecord:
    """Bounded evidence record for a single acceptance clause (SRC-323 §5)."""

    clause_id: str
    clause_text: str
    request_source: str
    matched_existing_work: str | None = None
    matched_implementation: str | None = None
    source_revision: str | None = None
    source_fingerprint: str | None = None
    test_or_verifier: str | None = None
    current_test_result: str | None = None
    evidence_reference: str | None = None
    evidence_freshness: str | None = None
    equivalence_verdict: str = VERDICT_UNKNOWN
    remaining_delta: str = "none"
    required_action: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class HandoffAnalysis:
    """Pre-admission analysis outcome and diagnostics report (SRC-323 §4 & §12)."""

    status: str
    request_identity: str
    source_receipt: str
    matched_existing_work: list[str]
    clauses_total: int
    clauses_verified_existing: int
    clauses_require_repair: int
    clauses_unverified: int
    implementation_delta: int
    test_results: dict[str, str]
    source_settlement: str
    work_settlement: str
    authority_boundary: str
    next_exact_action: str
    matrix: list[ClauseEvidenceRecord]

    def to_dict(self) -> dict[str, Any]:
        result = dataclasses.asdict(self)
        result["matrix"] = [c.to_dict() for c in self.matrix]
        return result

    def format_compact_report(self) -> str:
        """Produce the exact §12 compact outcome contract."""
        matched_str = (
            ", ".join(self.matched_existing_work) if self.matched_existing_work else "none"
        )
        test_str = (
            ", ".join(f"{k}:{v}" for k, v in sorted(self.test_results.items()))
            if self.test_results
            else "none"
        )
        lines = [
            f"STATUS: {self.status}",
            f"REQUEST_IDENTITY: {self.request_identity}",
            f"SOURCE_RECEIPT: {self.source_receipt}",
            f"MATCHED_EXISTING_WORK: {matched_str}",
            f"CLAUSES_TOTAL: {self.clauses_total}",
            f"CLAUSES_VERIFIED_EXISTING: {self.clauses_verified_existing}",
            f"CLAUSES_REQUIRE_REPAIR: {self.clauses_require_repair}",
            f"CLAUSES_UNVERIFIED: {self.clauses_unverified}",
            f"IMPLEMENTATION_DELTA: {self.implementation_delta}",
            f"TEST_RESULTS: {test_str}",
            f"SOURCE_SETTLEMENT: {self.source_settlement}",
            f"WORK_SETTLEMENT: {self.work_settlement}",
            f"AUTHORITY_BOUNDARY: {self.authority_boundary}",
            f"NEXT_EXACT_ACTION: {self.next_exact_action}",
        ]
        return "\n".join(lines)


#: Words that carry no acceptance content. Without them, "deliver the canonical
#: artifact" would match any Work whose verify contract also says "artifact".
_STOPWORDS = frozenset(
    {
        "the", "and", "for", "that", "this", "from", "with", "into", "than",
        "when", "then", "must", "should", "will", "each", "every", "all", "one",
        "its", "are", "was", "has", "have", "been", "does", "not", "can", "may",
        "request", "requested", "change", "present", "demonstrated", "against",
        "user", "own", "description", "deliver", "ensure", "implement",
        "implementation", "pass", "passing", "test", "tests", "verify", "verifies",
        "verified", "verification", "existing", "work", "read", "reads", "written",
        "check", "checks", "assert", "asserts", "asserting", "file", "files",
        "path", "text", "utf", "encoding", "import",
    }
)

#: A clause is only worth comparing when it shares at least this many distinct
#: content words with a candidate. One shared word is prose, not equivalence.
_MATCH_THRESHOLD = 2

#: Evidence reading is bounded: a handoff must never turn into a repository walk.
_MAX_EVIDENCE_FILES = 4
_MAX_EVIDENCE_FILE_CHARS = 4000
_MAX_CANDIDATES = 5


def _normalize_tokens(text: str) -> set[str]:
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]", " ", str(text or "").lower())
    return {w for w in cleaned.split() if len(w) > 2 and w not in _STOPWORDS}


def _ticket_contract_text(ticket: dict) -> str:
    """The Work's own acceptance prose -- description plus its verify contract.

    `parse_board` nests the contract under `fields`; reading a top-level
    `verify` key answered nothing and left every clause unmatched (measured
    2026-10-25 on the SRC-323 classifier family).
    """
    fields = ticket.get("fields") or {}
    parts = [ticket.get("description"), ticket.get("verify"), fields.get("verify")]
    return " ".join(str(part) for part in parts if part)


def _command_paths(command: str) -> list[str]:
    paths = []
    for word in str(command or "").split():
        token = word.strip("'\"")
        if re.search(r"\.[A-Za-z0-9]{1,8}$", token):
            paths.append(token)
    return paths


def _bounded_file_text(root: Path, cwd: str | None, relative: str) -> str:
    base = Path(cwd) if cwd else root
    candidate = Path(relative)
    if not candidate.is_absolute():
        candidate = base / relative
    try:
        if not candidate.is_file():
            return ""
        return candidate.read_text(encoding="utf-8", errors="replace")[:_MAX_EVIDENCE_FILE_CHARS]
    except OSError:
        return ""


def _executed_evidence_text(root: Path, proof: dict) -> str:
    """What the executed verification actually asserted (SRC-323 §5).

    A passing receipt proves what its commands and the artifacts they read
    cover, not what a ticket title claims. Bounded: at most `_MAX_EVIDENCE_FILES`
    referenced files, each truncated.
    """
    parts: list[str] = []
    files = 0
    for entry in proof.get("verification") or []:
        if not isinstance(entry, dict):
            continue
        command = str(entry.get("command") or "")
        parts.append(command)
        for relative in _command_paths(command):
            if files >= _MAX_EVIDENCE_FILES:
                break
            content = _bounded_file_text(root, entry.get("cwd"), relative)
            if content:
                parts.append(content)
                files += 1
    contract = proof.get("verification_contract") or {}
    parts.extend(str(item) for item in contract.get("commands") or [])
    return " ".join(parts)


#: Better candidates first when a clause matches several Works: executed proof
#: outranks a bare DONE row, which outranks Work still in flight.
_SECTION_RANK = {"## DONE": 0, "## DOING": 1, "## TODO": 2, "## BLOCKED": 3}


def _best_candidate(
    root: Path, clause_text: str, tickets: dict
) -> tuple[str, dict, dict | None] | None:
    """The Work whose own acceptance contract and evidence cover this clause.

    Two passes keep the executed proof bounded: prose shortlists candidates,
    then only the shortlist pays for the (expensive) current-tree reverify.
    """
    clause = _normalize_tokens(clause_text)
    if not clause:
        return None
    scored = []
    for ticket_id, ticket in tickets.items():
        if not isinstance(ticket, dict):
            continue
        section = str(ticket.get("section") or "")
        overlap = len(clause & _normalize_tokens(_ticket_contract_text(ticket)))
        if overlap < _MATCH_THRESHOLD:
            continue
        scored.append((overlap, -_SECTION_RANK.get(section, 9), ticket_id, ticket))
    if not scored:
        return None
    scored.sort(reverse=True)
    best = None
    for overlap, _rank, ticket_id, ticket in scored[:_MAX_CANDIDATES]:
        proof = (
            debt.current_tree_reverify(root, ticket_id)
            if ticket.get("section") == "## DONE"
            else None
        )
        bag = _normalize_tokens(_ticket_contract_text(ticket))
        if proof:
            bag |= _normalize_tokens(_executed_evidence_text(root, proof))
        score = len(clause & bag)
        if score < _MATCH_THRESHOLD:
            continue
        key = (score, bool(proof), -_SECTION_RANK.get(str(ticket.get("section") or ""), 9))
        if best is None or key > best[0]:
            best = (key, ticket_id, ticket, proof)
    if best is None:
        return None
    _key, ticket_id, ticket, proof = best
    return ticket_id, ticket, proof


def analyze_handoff_delta(
    root: Path | str,
    request_text: str,
    *,
    source_receipt: str | None = None,
    tickets: dict | None = None,
    operator_repeat: bool = False,
    candidate_lineage: str | None = None,
    stronger_acceptance: bool = False,
    requires_publication: bool = False,
) -> HandoffAnalysis:
    """Critically evaluate an incoming handoff before creating implementation Work.

    Performs bounded clause-by-clause comparison against current implementation,
    canonical history and executed evidence (SRC-323 §4, §5).
    """
    root = Path(root)
    receipt_id = source_receipt or "SRC-PENDING"
    req_digest = hashlib.sha256(request_text.encode("utf-8")).hexdigest()[:16]
    req_identity = f"REQ-{req_digest}"

    # 1. Parse BOARD tickets if not supplied
    if tickets is None:
        board_file = root / ".saipen" / "BOARD.md"
        if board_file.is_file():
            try:
                tickets = parse_board(codec.read_doc(board_file)).get("tickets") or {}
            except Exception:
                tickets = {}
        else:
            tickets = {}

    current_lineage = project_lineage_identity(root)

    # 2. Extract discrete acceptance clauses
    extracted = intake.extract_request_clauses(request_text)
    if not extracted:
        # Atomic single request
        extracted = [request_text.strip()]

    matrix: list[ClauseEvidenceRecord] = []
    matched_works: set[str] = set()
    test_results: dict[str, str] = {}

    for idx, c_text in enumerate(extracted, start=1):
        cid = f"{receipt_id}:R{idx:03d}"
        record = ClauseEvidenceRecord(
            clause_id=cid,
            clause_text=c_text,
            request_source=receipt_id,
            source_fingerprint=req_digest,
        )

        # TEST-14: Operator repeat deliberately asks to repeat delivery
        if operator_repeat:
            record.equivalence_verdict = VERDICT_MISSING
            record.remaining_delta = "operator repeat requested"
            record.required_action = "implement_repeat"
            matrix.append(record)
            continue

        # TEST-13: Different project or lineage cannot claim equivalence
        if candidate_lineage and candidate_lineage != current_lineage:
            record.equivalence_verdict = VERDICT_MISSING
            record.remaining_delta = "foreign lineage cannot provide equivalence"
            record.required_action = "implement_local"
            matrix.append(record)
            continue

        # TEST-19: an external publication request is an operator gate whether
        # or not existing Work resembles it. A gate that only fires after a
        # title match would let an unmatched publication request project Work.
        if requires_publication:
            record.equivalence_verdict = VERDICT_OPERATOR_GATE
            record.remaining_delta = "external publication requires operator authority"
            record.required_action = "await_operator_publication"
            matrix.append(record)
            continue

        candidate = _best_candidate(root, c_text, tickets)
        if candidate is None:
            record.equivalence_verdict = VERDICT_MISSING
            record.remaining_delta = "no existing work covers this clause"
            record.required_action = "implement"
            matrix.append(record)
            continue

        matched_ticket_id, matched_ticket, proof = candidate
        record.matched_existing_work = matched_ticket_id
        record.matched_implementation = _ticket_contract_text(matched_ticket)[:400] or None
        matched_works.add(matched_ticket_id)

        # TEST-18: One of matching old tickets is BLOCKED
        if matched_ticket.get("section") == "## BLOCKED":
            record.equivalence_verdict = VERDICT_UNVERIFIED
            record.remaining_delta = f"matched work {matched_ticket_id} is BLOCKED"
            record.required_action = "unblock_dependency"
            matrix.append(record)
            continue

        # TEST-07: Current request has stronger acceptance contract
        if stronger_acceptance:
            record.equivalence_verdict = VERDICT_CHANGED_CONTRACT
            record.remaining_delta = "stronger acceptance contract unverified"
            record.required_action = "reverify_stronger_contract"
            matrix.append(record)
            continue

        # Check executed verification for matched DONE Work
        if matched_ticket.get("section") == "## DONE":
            if proof is not None:
                record.test_or_verifier = f"reverify:{proof.get('receipt_id')}"
                record.source_revision = proof.get("source_head")
                record.source_fingerprint = proof.get("source_tree_fingerprint")
                verdict = proof.get("verdict")
                # TEST-05: Failing current regression
                if verdict in ("FAIL", "CURRENT_REGRESSION") or proof.get("own_problem_keys"):
                    record.current_test_result = "FAIL"
                    record.evidence_freshness = "CURRENT"
                    record.equivalence_verdict = VERDICT_REGRESSION
                    record.remaining_delta = "regression detected on existing work"
                    record.required_action = "repair"
                    test_results[matched_ticket_id] = "FAIL"
                else:
                    record.current_test_result = "PASS"
                    record.evidence_freshness = "CURRENT"
                    record.evidence_reference = proof.get("receipt_id")
                    record.equivalence_verdict = VERDICT_VERIFIED
                    record.remaining_delta = "none"
                    record.required_action = "none"
                    test_results[matched_ticket_id] = "PASS"
            else:
                # TEST-06: Existing Work is DONE but evidence is stale/unverified
                record.equivalence_verdict = VERDICT_UNVERIFIED
                record.evidence_freshness = "STALE"
                record.remaining_delta = "verification stale on current tree"
                record.required_action = "reverify"
                test_results[matched_ticket_id] = "STALE"
        else:
            # Active (TODO/DOING) work
            record.equivalence_verdict = VERDICT_UNVERIFIED
            record.remaining_delta = f"matched work {matched_ticket_id} is in progress"
            record.required_action = "wait_work_completion"

        matrix.append(record)

    # 3. Aggregate totals
    total = len(matrix)
    verified = sum(1 for c in matrix if c.equivalence_verdict == VERDICT_VERIFIED)
    repair = sum(1 for c in matrix if c.equivalence_verdict == VERDICT_REGRESSION)
    unverified = sum(
        1
        for c in matrix
        if c.equivalence_verdict in (VERDICT_UNVERIFIED, VERDICT_CHANGED_CONTRACT)
    )
    missing = sum(1 for c in matrix if c.equivalence_verdict == VERDICT_MISSING)
    op_gates = sum(1 for c in matrix if c.equivalence_verdict == VERDICT_OPERATOR_GATE)

    delta = repair + unverified + missing + op_gates

    # 4. Classify overall status
    if operator_repeat:
        status = NEW_IMPLEMENTATION_REQUIRED
        source_settlement = "ACTIVE_REMAINDER"
        work_settlement = "FULL_WORK_REQUIRED"
        auth_boundary = "OPERATOR_REPEAT_HONORED"
        next_action = "PROJECT_NEW_WORK"
    elif op_gates > 0:
        status = INDEPENDENT_OPERATOR_GATE
        source_settlement = "HELD_ON_GATE"
        work_settlement = "OPERATOR_GATE_BLOCKED"
        auth_boundary = (
            "PUBLICATION_GATE_REQUIRED" if requires_publication else "OPERATOR_GATE_REQUIRED"
        )
        next_action = "WAIT: operator-authority-required"
    elif repair > 0:
        status = REGRESSION_DETECTED
        source_settlement = "REPAIR_REQUIRED"
        work_settlement = "REPAIR_WORK_REQUIRED"
        auth_boundary = "NO_NEW_AUTHORITY"
        next_action = "REPAIR_EXISTING_REGRESSION"
    elif total > 0 and verified == total:
        status = EXISTING_IMPLEMENTATION_VERIFIED
        source_settlement = "CANONICALLY_CLOSED"
        work_settlement = "NO_DUPLICATE_WORK"
        auth_boundary = "NO_NEW_AUTHORITY"
        next_action = "CONTINUE_EXISTING_WORK"
    elif verified > 0:
        status = PARTIAL_OVERLAP
        source_settlement = "PARTIAL_SETTLEMENT"
        work_settlement = "DELTA_WORK_PROJECTED"
        auth_boundary = "NO_NEW_AUTHORITY"
        next_action = "IMPLEMENT_MISSING_DELTA"
    elif unverified > 0:
        status = EXISTING_IMPLEMENTATION_UNVERIFIED
        source_settlement = "UNVERIFIED_HOLD"
        work_settlement = "REVERIFY_REQUIRED"
        auth_boundary = "NO_NEW_AUTHORITY"
        next_action = "REVERIFY_EXISTING_WORK"
    else:
        status = NEW_IMPLEMENTATION_REQUIRED
        source_settlement = "ACTIVE_REMAINDER"
        work_settlement = "FULL_WORK_REQUIRED"
        auth_boundary = "NO_NEW_AUTHORITY"
        next_action = "PROJECT_NEW_WORK"

    return HandoffAnalysis(
        status=status,
        request_identity=req_identity,
        source_receipt=receipt_id,
        matched_existing_work=sorted(matched_works),
        clauses_total=total,
        clauses_verified_existing=verified,
        clauses_require_repair=repair,
        clauses_unverified=unverified,
        implementation_delta=delta,
        test_results=test_results,
        source_settlement=source_settlement,
        work_settlement=work_settlement,
        authority_boundary=auth_boundary,
        next_exact_action=next_action,
        matrix=matrix,
    )


def settle_verified_clauses(root: Path | str, analysis: HandoffAnalysis) -> dict:
    """Discharge only the clauses a current executed receipt already proves.

    This is the coverage-ledger half of SRC-323 §7: an unresolved clause keeps
    its obligation, so the remaining Work is exactly the real delta.
    """
    root = Path(root)
    receipt_id = analysis.source_receipt
    if not receipt_id or receipt_id.startswith("SRC-PENDING"):
        return {
            "ok": False,
            "code": "RECEIPT_NOT_FOUND",
            "detail": "no durable source receipt to settle",
        }
    settled: list[str] = []
    for record in analysis.matrix:
        if record.equivalence_verdict != VERDICT_VERIFIED:
            continue
        if not record.matched_existing_work:
            return {
                "ok": False,
                "code": "CANONICAL_SETTLEMENT_REFUSED",
                "detail": f"{record.clause_id} has no implementation owner",
            }
        rid = record.clause_id.split(":")[-1]
        settled_result = intake.set_disposition(
            root,
            receipt_id,
            rid,
            "VERIFIED",
            work=record.matched_existing_work,
            evidence=(
                "pre-admission clause verified by "
                f"{record.evidence_reference or record.test_or_verifier}"
            ),
            verification=f"saipen work reverify {record.matched_existing_work}: executed PASS",
        )
        if not settled_result.get("ok"):
            return settled_result
        settled.append(rid)
    return {"ok": True, "code": "CLAUSES_SETTLED", "receipt": receipt_id, "clauses": settled}


def settle_proven_duplicate(root: Path | str, analysis: HandoffAnalysis) -> dict:
    """Canonically settle an already-verified duplicate handoff (SRC-323 §6).

    Only executes when implementation_delta == 0 and all clauses are verified.
    Does not fake code diffs or invent test results.
    """
    root = Path(root)
    if analysis.implementation_delta > 0 or analysis.status not in (
        EXACT_DUPLICATE,
        EXISTING_IMPLEMENTATION_VERIFIED,
    ):
        return {
            "ok": False,
            "code": "CANONICAL_SETTLEMENT_REFUSED",
            "detail": (
                "cannot settle handoff with delta "
                f"{analysis.implementation_delta} (status {analysis.status})"
            ),
        }

    receipt_id = analysis.source_receipt
    settled_clauses = settle_verified_clauses(root, analysis)
    if not settled_clauses.get("ok"):
        return settled_clauses

    # Check if receipt is now completely satisfied
    if intake.coverage_complete(root, receipt_id):
        return {
            "ok": True,
            "code": "CANONICALLY_CLOSED",
            "receipt": receipt_id,
            "clauses_settled": len(analysis.matrix),
            "next_exact_action": "CONTINUE_EXISTING_WORK",
        }

    return {
        "ok": True,
        "code": "PARTIALLY_SETTLED",
        "receipt": receipt_id,
        "clauses_settled": len(analysis.matrix),
    }


# ── External implementation evidence: work done OUTSIDE the ledger ────────
#
# SRC-325 §10. A blocked protocol state does not stop an operator from fixing
# code, and it does not stop an agent from editing files through workspace
# tools while the lifecycle refuses to move. That delta is REAL implementation
# evidence with no Source, no LOG event and no Work. This classifier reports it
# truthfully: it reads the worktree, attributes what the objective provably
# covers, and leaves everything else exactly as unresolved as it is. It never
# writes, never backdates and never turns a dirty tree into DONE.

EXTERNAL_NO_DELTA = "NO_DELTA"
EXTERNAL_ACCEPTED_FOR_ADMISSION = "ACCEPTED_FOR_ADMISSION"
EXTERNAL_PARTIAL_DELTA = "PARTIAL_DELTA"
EXTERNAL_QUARANTINED = "QUARANTINED"
EXTERNAL_UNAVAILABLE = "UNAVAILABLE"

#: Nothing in this classifier runs a verifier, so its evidence is always
#: explicitly this -- never "PASS".
EXTERNAL_NOT_EXECUTED = "NOT_EXECUTED"

_MAX_EXTERNAL_FILES = 60
_MAX_EXTERNAL_FILE_CHARS = 8000
_BINARY_SUFFIXES = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".zip", ".gz", ".pdf",
        ".pyc", ".so", ".dll", ".exe", ".woff", ".woff2",
    }
)


@dataclasses.dataclass
class ExternalWorkRecord:
    """Unadmitted implementation evidence, described without inventing history."""

    disposition: str
    delta_status: str
    receipt: str | None
    objective_identity: str | None
    clauses_total: int
    clauses_covered: int
    uncovered_clauses: list[str]
    paths: list[dict[str, Any]]
    verification: str
    history_written: bool
    publication_authority: str
    authority_boundary: str
    work_settlement: str
    next_exact_action: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _observed_stamp(path: Path) -> str | None:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    return (
        datetime.datetime.fromtimestamp(mtime, datetime.UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _observed_digest(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _attributable_text(root: Path, relative: str) -> str:
    """Bounded, text-only read of one changed file. Binary stays unattributed."""
    path = root / relative
    if not path.is_file() or path.suffix.lower() in _BINARY_SUFFIXES:
        return ""
    try:
        raw = path.read_bytes()[:_MAX_EXTERNAL_FILE_CHARS]
    except OSError:
        return ""
    if b"\x00" in raw:
        return ""
    return raw.decode("utf-8", "replace")


def _git_text(root: Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", "replace")


def _observed_paths(root: Path) -> tuple[str, list[str]]:
    """Changed FILES inside this project's own frame.

    Two distortions would misattribute the delta if taken raw: `git status
    --porcelain` collapses an untracked directory into one `dir/` entry, and a
    project nested inside a larger repository gets paths relative to THAT
    repository. Both are corrected here -- the repository top-level is
    consulted, its prefix stripped, and untracked directories expanded by
    file -- so the record names the bytes a later admission can point at.
    """
    snapshot = effects.tree_snapshot(root)
    status = str(snapshot.get("status") or "UNAVAILABLE")
    if status != "KNOWN":
        return status, []
    toplevel = _git_text(root, "rev-parse", "--show-toplevel")
    if toplevel is None:
        return "UNAVAILABLE", []
    repo_root = Path(toplevel.strip()).resolve()
    try:
        prefix = root.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        # The project is not inside the repository git resolved: nothing here
        # can be attributed to it.
        return "UNAVAILABLE", []
    prefix = "" if prefix == "." else prefix.rstrip("/")
    paths: list[str] = []
    for raw in snapshot.get("paths") or ():
        relative = str(raw)
        if prefix:
            if relative.startswith(prefix + "/"):
                relative = relative[len(prefix) + 1 :]
            else:
                continue  # outside the project's frame
        if relative.endswith("/") or relative == "":
            # An untracked directory, collapsed to one entry -- including the
            # project directory itself when nothing in it is tracked yet.
            args = ["ls-files", "--others", "--exclude-standard", "-z"]
            if relative:
                args.extend(["--", relative])
            listed = _git_text(root, *args)
            for entry in (listed or "").split("\0"):
                if entry and len(paths) < _MAX_EXTERNAL_FILES:
                    paths.append(entry)
            continue
        if relative:
            paths.append(relative)
        if len(paths) >= _MAX_EXTERNAL_FILES:
            break
    return "KNOWN", sorted(dict.fromkeys(paths))[:_MAX_EXTERNAL_FILES]


def _objective_clauses(
    root: Path, receipt: str | None, objective: str | None
) -> list[str]:
    """What the operator actually asked for -- from the receipt, else prose."""
    if objective:
        extracted = intake.extract_request_clauses(objective)
        return extracted or [objective.strip()]
    if not receipt:
        return []
    retrieved = intake.read_body(root, receipt)
    if not retrieved.get("ok"):
        return []
    body = str(retrieved.get("body") or "")
    extracted = intake.extract_request_clauses(body)
    return extracted or ([body.strip()] if body.strip() else [])


def classify_external_delta(
    root: Path | str,
    *,
    receipt: str | None = None,
    objective: str | None = None,
) -> ExternalWorkRecord:
    """Classify the worktree delta against the operator objective (SRC-325 §10).

    Dispositions:
      NO_DELTA                  the tree carries nothing unadmitted
      ACCEPTED_FOR_ADMISSION    every objective clause is covered by the delta --
                                admit it through ordinary Source/Work mechanics,
                                never call it verified
      PARTIAL_DELTA             some clauses are covered; the rest is real work
      QUARANTINED               a delta nothing can attribute to this objective
      UNAVAILABLE               no git worktree to observe; never a clean bill

    `paths` carries the exact changed-file identity and observed stamps, so a
    later admission can point at the bytes that existed now. This function
    performs no writes and mints no event: provenance stays what it is.
    """
    root = Path(root)
    receipt_id = str(receipt).upper() if receipt else None
    delta_status, observed = _observed_paths(root)

    if delta_status != "KNOWN":
        return ExternalWorkRecord(
            disposition=EXTERNAL_UNAVAILABLE,
            delta_status=delta_status,
            receipt=receipt_id,
            objective_identity=None,
            clauses_total=0,
            clauses_covered=0,
            uncovered_clauses=[],
            paths=[],
            verification=EXTERNAL_NOT_EXECUTED,
            history_written=False,
            publication_authority="CLOSED",
            authority_boundary="NO_NEW_AUTHORITY",
            work_settlement="UNOBSERVABLE",
            next_exact_action="saipen status",
            detail=(
                "no git worktree at this project root, so no delta can be "
                "observed; this is absence of evidence, not a clean tree"
            ),
        )

    paths: list[dict[str, Any]] = []
    for relative in observed:
        path = root / relative
        paths.append(
            {
                "path": relative,
                "sha256": _observed_digest(path),
                "observed_mtime": _observed_stamp(path),
                "present": path.is_file(),
                "class": "PROTOCOL_MEMORY" if relative.startswith(".saipen/") else "PROJECT",
            }
        )

    if not observed:
        return ExternalWorkRecord(
            disposition=EXTERNAL_NO_DELTA,
            delta_status=delta_status,
            receipt=receipt_id,
            objective_identity=None,
            clauses_total=0,
            clauses_covered=0,
            uncovered_clauses=[],
            paths=[],
            verification=EXTERNAL_NOT_EXECUTED,
            history_written=False,
            publication_authority="CLOSED",
            authority_boundary="NO_NEW_AUTHORITY",
            work_settlement="NO_UNADMITTED_DELTA",
            next_exact_action="CONTINUE_EXISTING_WORK",
            detail="the worktree is clean; there is no external work to reconcile",
        )

    clauses = _objective_clauses(root, receipt_id, objective)
    objective_digest = (
        hashlib.sha256("\n".join(clauses).encode("utf-8")).hexdigest()[:16] if clauses else None
    )

    # Attribution reads the CHANGED BYTES, not a claim about them: a clause is
    # covered when the delta itself carries its acceptance content.
    bags: dict[str, set[str]] = {}
    for relative in observed:
        bags[relative] = _normalize_tokens(relative) | _normalize_tokens(
            _attributable_text(root, relative)
        )

    covered: list[str] = []
    uncovered: list[str] = []
    for clause in clauses:
        tokens = _normalize_tokens(clause)
        named = [rel for rel in observed if Path(rel).name.lower() in clause.lower()]
        hit = bool(named) or any(
            len(tokens & bag) >= _MATCH_THRESHOLD for bag in bags.values()
        )
        (covered if hit else uncovered).append(clause)

    if not clauses:
        disposition = EXTERNAL_QUARANTINED
        work_settlement = "ATTRIBUTION_REQUIRED"
        next_exact_action = "saipen source status %s" % (receipt_id or "<SRC-###>")
        detail = (
            f"{len(observed)} unadmitted path(s) and no objective to compare them "
            "against; the delta is real but unattributable, so nothing may be "
            "settled, assumed verified or silently discarded"
        )
    elif not uncovered:
        disposition = EXTERNAL_ACCEPTED_FOR_ADMISSION
        work_settlement = "ADMISSION_REQUIRED"
        next_exact_action = "ADMIT_THEN_VERIFY"
        detail = (
            f"all {len(clauses)} objective clause(s) are covered by bytes already "
            f"on disk across {len(observed)} path(s); admit the work through the "
            "ordinary Source/Work lifecycle and verify it there -- this record "
            "proves presence, not a passing run"
        )
    elif covered:
        disposition = EXTERNAL_PARTIAL_DELTA
        work_settlement = "DELTA_WORK_REQUIRED"
        next_exact_action = "IMPLEMENT_MISSING_DELTA"
        detail = (
            f"{len(covered)} of {len(clauses)} clause(s) are covered by the "
            f"unadmitted delta; {len(uncovered)} remain outstanding and must not "
            "be re-implemented where they already are"
        )
    else:
        disposition = EXTERNAL_QUARANTINED
        work_settlement = "ATTRIBUTION_REQUIRED"
        next_exact_action = "saipen source delta %s" % (receipt_id or "<SRC-###>")
        detail = (
            f"{len(observed)} unadmitted path(s) match none of the {len(clauses)} "
            "objective clause(s); the work is not credited, not deleted and not "
            "called DONE"
        )

    return ExternalWorkRecord(
        disposition=disposition,
        delta_status=delta_status,
        receipt=receipt_id,
        objective_identity=(
            (f"REQ-{objective_digest}" if objective_digest else None)
        ),
        clauses_total=len(clauses),
        clauses_covered=len(covered),
        uncovered_clauses=uncovered,
        paths=paths,
        verification=EXTERNAL_NOT_EXECUTED,
        history_written=False,
        publication_authority="CLOSED",
        authority_boundary="NO_NEW_AUTHORITY",
        work_settlement=work_settlement,
        next_exact_action=next_exact_action,
        detail=detail,
    )
