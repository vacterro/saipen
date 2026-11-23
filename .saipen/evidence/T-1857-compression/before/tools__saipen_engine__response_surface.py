"""The default SAIPEN response surface -- EXEC-RESPONSE-01 (T-1419).

One schema for every ordinary user-facing operational boundary: typed machine
facts rendered as bounded inline fields, never a model retrospective.
The rule is prose in ``saipen/EXECUTION.md``; this module is its
behavioural projection so the contract can be decided without re-reading the
document, exactly as the guard shares one classifier with the router.

Two questions the surface answers mechanically:

* Is a rendered control block well-formed -- mandatory fields present, in
  canonical order, ``DETAILS`` optional and last, and a ``WAIT`` that actually
  tells the human what to do?
* Should the agent return to the user at all, or continue executing? A control
  block with no required human action and a canonically executable next step is
  NOT a response boundary (preserves T-1416).
"""

from __future__ import annotations

import hashlib
import re
import shlex
from collections import Counter
from dataclasses import dataclass

from .efficiency import LINE_CHAR_BUDGET as _EFFICIENCY_LINE_CHARS
from .efficiency import line_problem as _efficiency_line_problem
from .phases import ALL_PHASES

RULE_ID = "EXEC-RESPONSE-01"

#: The semantic control fields, in canonical order. NONE action fields may be
#: omitted from the inline renderer and are restored by the shared parser.
MANDATORY_FIELDS = (
    "STATUS",
    "RESULT",
    "BLOCKER",
    "OPERATOR ACTION",
    "NEXT EXACT ACTION",
    "VALIDATION",
)

#: Optional fields, rendered only AFTER the mandatory surface. EFFICIENCY
#: (T-1576) is the derived `efficiency` KPI line: final boundaries only, one
#: line, never quality evidence; DETAILS stays last.
OPTIONAL_FIELDS = ("EFFICIENCY", "DETAILS")

FIELD_ORDER = MANDATORY_FIELDS + OPTIONAL_FIELDS

_BLOCKER_CODE = re.compile(r"^[A-Z][A-Z0-9_]* -- \S")
_VAGUE_ACTIONS = frozenset(
    {"continue as appropriate", "investigate further", "proceed with next steps", "retry if needed"}
)
_AGENT_COMMAND = re.compile(
    r"^\s*(?:please\s+)?(?:run|execute|invoke|use\s+)?\s*`?"
    r"(?:saipen(?:\.cmd|\.py)?|python(?:\d+(?:\.\d+)*)?|py|git|uv|ruff|"
    r"pytest|npm|node|powershell|pwsh|cmd|bash)(?:`)?(?:\s|$)",
    re.IGNORECASE,
)
_AGENT_INSTRUCTION = re.compile(
    r"^\s*(?:please\s+)?(?:run|execute|invoke|continue|proceed|retry|investigate)\s+"
    r"(?:(?:the|an?)\s+)?(?:(?:next|remaining|internal|canonical)\s+)*"
    r"(?:command|phase|step|processing|tests?|validator|verification)\b",
    re.IGNORECASE,
)

#: The values that mean "no action" for the two always-present action fields.
NONE_VALUES = frozenset({"", "NONE"})

# ---------------------------------------------------------------------------
# T-1556 #1: DETAILS AUTHORIZATION IS A MACHINE FACT, NOT A STYLE CHOICE.
#
# A line budget alone made `DETAILS` free on every ordinary reply: the schema
# permitted eight lines wherever it liked. Authorization is one canonical
# machine-readable value owned HERE, derived from the HUMAN's request (never
# from the outgoing prose, which is the thing being authorized) and defaulting
# to forbidden. A host that supplies nothing gets the closed default.
DETAIL_MODE_NONE = "NONE"
DETAIL_MODE_REPORT = "EXPLICIT_REPORT"
DETAIL_MODE_AUDIT = "AUDIT"
DETAIL_MODE_HANDOFF = "HANDOFF"
DETAIL_MODE_BOUNDARY = "EXCEPTIONAL_BOUNDARY"
DETAIL_MODES = (
    DETAIL_MODE_NONE,
    DETAIL_MODE_REPORT,
    DETAIL_MODE_AUDIT,
    DETAIL_MODE_HANDOFF,
    DETAIL_MODE_BOUNDARY,
)

#: Only a direct request earns the exception. Searching anywhere in ingress
#: made "fix audit logging", negations and quoted examples authorize essays.
#: Ambiguous wording stays on the compact path; callers can transport an
#: explicitly authorized closed mode instead of guessing from a noun.
# Closed affirmative depth grammars. Summary/brief/final report and a claim
# of exceptional importance deliberately have no grant. A whole clause must
# match; quoted examples, nested requests, negations and extra instructions
# cannot supply authority. Reply language is unrelated to ingress language.
_EN_VERB = (
    r"(?:please\s+)?(?:(?:can|could|would) you (?:please )?)?"
    r"(?:write|prepare|produce|generate|give|send|render)\s+"
    r"(?:(?:me|us)\s+)?(?:(?:a|an|the)\s+)?"
)
_DEPTH = r"(?:(?:detailed|full|verbose|complete)\s+)+"
_TYPE = r"(?:(?:forensic|technical|implementation)\s+)?"
_TAIL = (
    r"(?:\s+(?:(?:with|including)\s+(?:all\s+)?(?:evidence|evidence and root cause)"
    r"|of (?:the findings|the change)))?"
)
_DETAIL_REQUEST_GRAMMARS = tuple(
    (mode, re.compile(r"\s*(?:" + grammar + r")\s*[.!?]?\s*", re.IGNORECASE))
    for mode, grammar in (
        (DETAIL_MODE_HANDOFF, _EN_VERB + _DEPTH + _TYPE + r"hand[\s-]?off"),
        (DETAIL_MODE_AUDIT, _EN_VERB + _DEPTH + _TYPE + r"audit" + _TAIL),
        (DETAIL_MODE_REPORT, _EN_VERB + _DEPTH + _TYPE + r"(?:report|write[\s-]?up)" + _TAIL),
        (
            DETAIL_MODE_REPORT,
            r"(?:please\s+)?explain everything in full detail including evidence and root cause",
        ),
        (
            DETAIL_MODE_HANDOFF,
            r"(?:дай|подготовь)\s+(?:(?:полный|подробный|детальный)\s+)+"
            r"(?:хендофф|хэнд[\u043e\u0430]фф|handoff)",
        ),
        (
            DETAIL_MODE_AUDIT,
            r"(?:сделай|дай|подготовь)\s+(?:(?:полный|подробный|детальный)\s+)+(?:технический\s+)?аудит",
        ),
        (
            DETAIL_MODE_REPORT,
            r"(?:дай|напиши|подготовь)\s+(?:(?:полный|подробный|детальный)\s+)+"
            r"(?:(?:технический|форензик)[\s-]+)?отч[её]т"
            r"(?:\s+\u0441\u043e всеми доказательствами)?",
        ),
        (
            DETAIL_MODE_HANDOFF,
            r"(?:anna|koosta)\s+(?:(?:täielik|detailne|põhjalik)\s+)+(?:handoff|üleandmine)",
        ),
        (
            DETAIL_MODE_AUDIT,
            r"(?:tee|koosta|anna)\s+(?:(?:täielik|detailne|põhjalik)\s+)+(?:tehniline\s+)?audit",
        ),
        (
            DETAIL_MODE_REPORT,
            r"(?:anna|koosta)\s+(?:(?:täielik|detailne|põhjalik)\s+)+"
            r"(?:tehniline\s+)?(?:aruanne|raport)(?:\s+koos tõenditega)?",
        ),
        # SRC-190: the operator's own short words for "show me more" -- details,
        # evidence, a technical breakdown, verbose output. Still one whole
        # affirmative clause. A bare `audit` stays a command name and grants
        # nothing; a question about one thing is ordinary conversation.
        (
            DETAIL_MODE_REPORT,
            r"(?:please\s+)?(?:give|show|send)\s+(?:(?:me|us)\s+)?(?:the\s+)?"
            r"(?:(?:full|complete|all)\s+(?:the\s+)?)?(?:details|evidence)(?:\s+please)?",
        ),
        (
            DETAIL_MODE_REPORT,
            _EN_VERB + r"(?:(?:detailed|full|verbose|complete)\s+)*technical\s+breakdown",
        ),
        (DETAIL_MODE_REPORT, _EN_VERB + r"verbose\s+output"),
        (
            DETAIL_MODE_REPORT,
            r"(?:(?:the\s+)?(?:full\s+)?details|full\s+report|detailed\s+report"
            r"|verbose(?:\s+output)?|technical\s+breakdown)(?:\s+please)?",
        ),
        (
            DETAIL_MODE_REPORT,
            r"(?:näita|anna)\s+(?:kõik\s+)?"
            r"(?:üksikasjad|üksikasju|detailid|detaile|tõendid|tõendeid)",
        ),
        (
            DETAIL_MODE_REPORT,
            r"(?:покажи|дай)\s+(?:все\s+)?(?:детали|подробности|доказательства)",
        ),
        (DETAIL_MODE_REPORT, r"(?:üksikasjad|detailid|подробности|детали)"),
    )
)

#: Per-field budgets count nonempty content lines. The response-reason ceiling
#: separately counts every visible line and character, including labels.
#: Without this the control surface degraded into a free-form report wearing six
#: headings: a RESULT of any length and a DETAILS field of any length both read
#: as VALID_BOUNDARY.
FIELD_LINE_BUDGETS = {
    "RESULT": 1,
    "BLOCKER": 1,
    "OPERATOR ACTION": 1,
    "NEXT EXACT ACTION": 1,
    "VALIDATION": 1,
    "EFFICIENCY": 1,
    # DETAILS stays permitted for the intentional detailed-report path, but it
    # is bounded: an unbounded DETAILS is the overflow bucket the surface
    # exists to remove.
    "DETAILS": 8,
}

#: T-1556 #2: LINE COUNT ALONE IS NOT A COMPACTNESS CONTRACT. One RESULT line
#: of twelve thousand characters satisfied every line budget, so the surface
#: still read as VALID_BOUNDARY while carrying a novel. These are the character
#: budgets over the same field CONTENT, machine-owned beside `FIELD_LINE_BUDGETS`
#: so no adapter has to know them and no document may drift from them.
FIELD_CHAR_BUDGETS = {
    "STATUS": 64,
    "RESULT": 300,
    "BLOCKER": 300,
    "OPERATOR ACTION": 300,
    "NEXT EXACT ACTION": 240,
    "VALIDATION": 160,
    "EFFICIENCY": _EFFICIENCY_LINE_CHARS,
    "DETAILS": 2400,
}

#: T-1558: prose plus fenced code together may not exceed this multiple of the
#: prose ceiling. Fenced code is exempt from the PROSE measures (it is fact), not
#: from every measure: without a total an essay wrapped in a fence passes. One
#: owner, here, beside the budgets it multiplies; `chat_style` reads it.
TOTAL_REPLY_CEILING_FACTOR = 1

#: Whole rendered boundary, labels included. It is deliberately BELOW the sum
#: of the per-field maxima: a response whose every field is individually legal
#: is still not a compact handback, and a ceiling that can never fire is
#: decoration rather than a contract.
ORDINARY_RESPONSE_CHAR_BUDGET = 900
#: The detailed path earns the DETAILS budget and nothing else.
DETAILED_RESPONSE_CHAR_BUDGET = 3600

SILENT_CONTINUATION = "SILENT_CONTINUATION"
COMPACT_FINAL = "COMPACT_FINAL"
STOP_HANDBACK = "STOP_HANDBACK"
HUMAN_ACTION_BLOCKER = "HUMAN_ACTION_BLOCKER"
SAFETY_BOUNDARY = "SAFETY_BOUNDARY"
EXPLICIT_DETAILED_REPORT = "EXPLICIT_DETAILED_REPORT"
REASON_BUDGETS = {
    SILENT_CONTINUATION: (0, 0),
    COMPACT_FINAL: (6, ORDINARY_RESPONSE_CHAR_BUDGET),
    STOP_HANDBACK: (6, ORDINARY_RESPONSE_CHAR_BUDGET),
    HUMAN_ACTION_BLOCKER: (8, 1200),
    SAFETY_BOUNDARY: (8, 1200),
    EXPLICIT_DETAILED_REPORT: (16, DETAILED_RESPONSE_CHAR_BUDGET),
}

# ---------------------------------------------------------------------------
# SRC-190 (T-1656): THE OPERATOR SURFACE AND THE EVIDENCE ARE TWO SURFACES.
#
# The budgets above were already the contract, and a reply could still arrive
# as one field carrying three thousand characters: the refusal was a sentence
# per broken rule, nothing a host could act on, and the compact form it was
# offered named no place where the detail lives -- so the detail went into the
# reply. Three additions, all owned here:
#
# * the overflow is DATA (`overflow_diagnostic`): which field, how large,
#   against which budget;
# * an ordinary boundary may POINT at evidence (`details_is_pointer`): one
#   short line of canonical references needs no depth authority, because it
#   carries no detail;
# * a rejected reply has one content-addressed home (`rejected_reference`), so
#   replacing it with the compact form loses nothing.
OVERFLOW_CODE = "OPERATOR_OUTPUT_OVERFLOW"
COMPACTION_SUCCEEDED = "SUCCEEDED"
COMPACTION_FAILED = "FAILED"
COMPACTION_NOT_ATTEMPTED = "NOT_ATTEMPTED"

#: Where a reply the gate refused is kept, losslessly, named by its content.
REJECTED_RESPONSE_DIR = ".saipen/evidence/response"

#: A pointer is short by definition; a long one is an inventory.
DETAILS_POINTER_CHAR_BUDGET = 120
#: A path reference names project memory and nothing else: every segment
#: starts with a letter, digit, `_` or `-`, so `.saipen/../x` is not a pointer.
_POINTER_REF = (
    r"(?:E-\d{1,8}(?:\.\.E-\d{1,8})?|T-\d{1,8}|SRC-\d{1,6}"
    r"|\.saipen(?:/[A-Za-z0-9_-][A-Za-z0-9_.-]{0,60}){1,6})"
)
_POINTER_REF_RE = re.compile(_POINTER_REF)
_DETAILS_POINTER = re.compile(rf"{_POINTER_REF}(?:[,;] {_POINTER_REF}){{0,5}}")
#: How many references the machine digest names; the rest stay in the ledger.
_DIGEST_POINTER_REFS = 4


def details_is_pointer(value: object) -> bool:
    """Is this DETAILS value only a short line of canonical references?

    Event ids and ranges, ticket and receipt ids, and paths under `.saipen/`,
    separated by `, ` or `; `. Any other word makes it prose, and prose in
    DETAILS still needs the human's depth authority.
    """
    if not isinstance(value, str):
        return False
    text = value.strip()
    return len(text) <= DETAILS_POINTER_CHAR_BUDGET and bool(_DETAILS_POINTER.fullmatch(text))


def details_pointer(refs: object) -> str:
    """One pointer line from machine-owned references, or `` when none is valid.

    Every reference is re-checked against the closed grammar: a facts carrier
    cannot smuggle prose into the reply through this field.
    """
    kept: list[str] = []
    for ref in refs if isinstance(refs, (list, tuple)) else ():
        text = str(ref).strip()
        if _POINTER_REF_RE.fullmatch(text) and text not in kept:
            kept.append(text)
    while kept:
        line = ", ".join(kept[:_DIGEST_POINTER_REFS])
        if details_is_pointer(line):
            return line
        kept.pop()
    return ""


def rejected_reference(text: object) -> str:
    """The one path a refused reply is preserved at, derived from its bytes."""
    body = (text if isinstance(text, str) else "").replace("\r\n", "\n").replace("\r", "\n")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    return f"{REJECTED_RESPONSE_DIR}/rejected-{digest}.txt"


def rejected_diagnostic_reference(reference: str) -> str:
    """Where the overflow account of a preserved reply is kept: beside it."""
    return reference[: -len(".txt")] + ".json"


def preserve_rejected(root, text: object) -> dict:
    """Keep a refused reply, byte for byte, at its content-addressed path.

    Called by whoever is about to replace the reply with the compact form, so
    the replacement loses nothing. Idempotent: the same reply is the same
    path, and a file already holding these bytes is not written again.
    """
    from pathlib import Path

    from .paths import safe_atomic_write_bytes

    base = Path(root)
    body = (text if isinstance(text, str) else "").replace("\r\n", "\n").replace("\r", "\n")
    if not body.strip():
        return {"ok": False, "code": "VALIDATION_FAILED", "detail": "no reply text to preserve"}
    if not (base / ".saipen").is_dir():
        return {"ok": False, "code": "NOT_SAIPEN_PROJECT", "detail": f"no .saipen/ under {base}"}
    reference = rejected_reference(body)
    data = body.encode("utf-8")
    target = base / reference
    written = False
    if not target.is_file() or target.read_bytes() != data:
        safe_atomic_write_bytes(target, data, kind="rejected response", ownership_root=base)
        written = True
    # T-1657: the size account is kept beside the bytes it describes. A host
    # that replaces or corrects a reply is handed this diagnostic by the
    # checker and had nowhere to put it; written here, whoever preserves the
    # reply keeps its account too. Derived from the reply alone, so the same
    # reply is the same record and a second call writes nothing.
    import json

    overflow = overflow_diagnostic(body)
    if overflow is not None:
        # What became of the reply is the caller's fact, not this record's.
        overflow = {key: value for key, value in overflow.items() if key != "compaction"}
    record = {
        "schema": 1,
        "kind": "saipen-rejected-response",
        "ref": reference,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "overflow": overflow,
    }
    diagnostic_ref = rejected_diagnostic_reference(reference)
    account = (json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    account_target = base / diagnostic_ref
    if not account_target.is_file() or account_target.read_bytes() != account:
        safe_atomic_write_bytes(
            account_target, account, kind="rejected response diagnostic", ownership_root=base
        )
        written = True
    return {
        "ok": True,
        "code": "RESPONSE_PRESERVED",
        "ref": reference,
        "diagnostic_ref": diagnostic_ref,
        "sha256": record["sha256"],
        "bytes": len(data),
        "overflow": overflow,
        "written": written,
    }


def overflow_diagnostic(
    rendered: object,
    *,
    detail_mode: str = DETAIL_MODE_NONE,
    response_class: str | None = None,
    operator_due: bool = False,
) -> dict | None:
    """`OPERATOR_OUTPUT_OVERFLOW` as data, or None when the reply fits.

    Names every field over its own budget with its measured size, and the
    whole reply against the budget of its boundary class. A reply that is not
    a control surface at all has one offender, the reply itself (`RESPONSE`).
    Measuring only: `response_errors` stays the rule, this is its account of
    the size rules in a form a host or a test can read.
    """
    text = rendered if isinstance(rendered, str) else ""
    if not text.strip():
        return None
    klass = response_class or response_reason(operator_due=operator_due, detail_mode=detail_mode)
    line_budget, char_budget = REASON_BUDGETS.get(klass, REASON_BUDGETS[COMPACT_FINAL])
    lines = text.splitlines()
    values, problems = parse_surface(text)
    is_surface = not any("STATUS" in problem for problem in problems)
    offenders: list[dict] = []
    if is_surface:
        for name in FIELD_ORDER:
            if name not in values:
                continue
            value = values[name]
            content = [line for line in value.splitlines() if line.strip()]
            char_limit = FIELD_CHAR_BUDGETS.get(name)
            line_limit = FIELD_LINE_BUDGETS.get(name, 1)
            if name == "DETAILS" and detail_mode == DETAIL_MODE_NONE:
                char_limit, line_limit = DETAILS_POINTER_CHAR_BUDGET, 1
            if (char_limit is not None and len(value) > char_limit) or len(content) > line_limit:
                offenders.append(
                    {
                        "field": name,
                        "chars": len(value),
                        "lines": len(content),
                        "char_budget": char_limit,
                        "line_budget": line_limit,
                    }
                )
    whole_over = len(lines) > line_budget or len(text) > char_budget
    if not offenders and not whole_over:
        return None
    if not offenders:
        offenders.append(
            {
                "field": "RESPONSE",
                "chars": len(text),
                "lines": len(lines),
                "char_budget": char_budget,
                "line_budget": line_budget,
            }
        )
    return {
        "code": OVERFLOW_CODE,
        "response_class": klass,
        "fields": offenders,
        "total": {
            "chars": len(text),
            "lines": len(lines),
            "char_budget": char_budget,
            "line_budget": line_budget,
        },
        "detail_ref": rejected_reference(text),
        "compaction": COMPACTION_NOT_ATTEMPTED,
    }


#: T-1556 #3: EXACTLY ONE ACTION. Chaining and sequencing are rejected by
#: shape; a value that names a canonical SAIPEN command is additionally held to
#: the canonical recognizer, so `saipen validate && saipen continue` and
#: `saipen frobnicate` are both refused for the same reason. No shell parser is
#: built here: a quoted canonical payload may legally contain a separator, and
#: the recognizer already knows that.
_ACTION_CHAIN = re.compile(r"&&|\|\||[;|&\n]")
_ACTION_SEQUENCE = re.compile(r"(?i)\b(?:then|after\s+that|afterwards?|followed\s+by|and\s+next)\b")
_ACTION_COMMAND_START = re.compile(
    r"^\s*`?(?:saipen(?:\.cmd|\.py)?|python(?:\d+(?:\.\d+)*)?|py|git|uv|ruff|"
    r"pytest|npm|node|powershell|pwsh|cmd|bash)\b",
    re.IGNORECASE,
)
#: The same vocabulary as bare tokens. A second occurrence means two commands
#: in one field, which is what `saipen validate saipen continue` is.
_ACTION_COMMAND_WORDS = frozenset(
    {
        "saipen",
        "saipen.cmd",
        "saipen.py",
        "python",
        "py",
        "git",
        "uv",
        "ruff",
        "pytest",
        "npm",
        "node",
        "powershell",
        "pwsh",
        "cmd",
        "bash",
    }
)


def _diagnosis_request(request: object) -> bool:
    """Closed affirmative ingress, never keywords found in an outgoing report.

    This recognizes a request, not the meaning or truth of its eventual answer.
    Ambiguous free prose remains subject to semantic review.
    """
    if not isinstance(request, str):
        return False
    return bool(
        re.fullmatch(
            r"\s*(?:explain why (?:the |an? )?agent deviated from SAIPEN|"
            r"(?:write|prepare) (?:a |an? )?handoff explaining why the agent deviated from SAIPEN|"
            r"объясни[ ,]+почему агент отклонился от (?:SAIPEN|протокола)|"
            r"(?:напиши|подготовь) хендофф[ ,]+почему агент отклонился от (?:SAIPEN|протокола)|"
            r"selgita[ ,]+miks agent kaldus SAIPENist kõrvale)\s*[.!?]?\s*",
            request,
            re.IGNORECASE,
        )
    )


def request_class_for_request(request: object) -> str:
    """Candidate intent; human_response_authority separately settles authority."""
    if _diagnosis_request(request):
        return "PROTOCOL_DIAGNOSIS"
    if isinstance(request, str) and request.strip().casefold() in {
        "report the recovery refusal",
        "report the operational wait",
    }:
        return "RECOVERY_REPORT"
    artifact = artifact_for_request(request)
    if artifact == "HANDOFF":
        return "IMPLEMENTATION_HANDOFF"
    if artifact == "AUDIT":
        return "AUDIT"
    if reason_for_request(request) == "summary":
        return "ENGINEERING_STATUS"
    return "ORDINARY"


def _diagnosis_errors(rendered: object, request: str, root: object) -> list[str]:
    """Bound structure and citations; DOES NOT prove semantic applicability.

    A cited quote remains attributed evidence, not a recovered project, a
    hidden motive, or verified host enforcement. Independent semantic review
    must judge request/delivery mismatch and rule applicability. No keyword
    score or a self-declared PASS stands in for that review.
    """
    import json
    from pathlib import Path

    from .paths import resolve_protocol_dir

    try:
        packet = json.loads(str(rendered))
    except (ValueError, TypeError, RecursionError):
        return [
            "protocol diagnosis requires an evidence-bound record; an inventory is not a diagnosis"
        ]
    fields = {
        "type",
        "request",
        "observed",
        "rule",
        "assessment",
        "cause",
        "correction",
        "recovery",
        "host",
        "enforcement",
        "semantic_review",
    }
    if not isinstance(packet, dict) or set(packet) != fields:
        return [
            "diagnosis must cover request, observation, evidence, rule/owner, "
            "uncertainty, cause and proposed correction"
        ]
    if any(
        not isinstance(packet[key], str)
        for key in (
            "type",
            "request",
            "assessment",
            "recovery",
            "host",
            "enforcement",
            "semantic_review",
        )
    ):
        return ["diagnosis scalar fields must be text"]
    if packet["type"] != "PROTOCOL_DIAGNOSIS" or packet["request"] != request:
        return ["diagnosis is not bound to the witnessed request"]
    if packet["semantic_review"] != "REQUIRED" or packet["assessment"] not in {
        "UNVERIFIED",
        "REPORTED",
        "LEGITIMATE_REFUSAL",
    }:
        return ["structural verification cannot assert a proven semantic violation"]
    cause = packet["cause"]
    if (
        not isinstance(cause, dict)
        or set(cause) != {"kind", "reason"}
        or cause["kind"] != "UNKNOWN"
        or not isinstance(cause["reason"], str)
        or not cause["reason"].strip()
        or len(cause["reason"]) > 1024
    ):
        return ["this carrier cannot prove an internal motive or infer a cause from a quote"]
    correction = packet["correction"]
    if (
        not isinstance(correction, dict)
        or set(correction) != {"status", "text"}
        or correction["status"] != "PROPOSED"
        or not isinstance(correction["text"], str)
        or not correction["text"].strip()
    ):
        return ["correction must be proposed; the diagnostic cannot claim it executed"]
    if packet["recovery"] not in {"UNVERIFIED", "REFUSED", "NOT_REQUESTED"}:
        return ["a diagnostic is not evidence of successful recovery"]
    engine = Path(__file__).resolve().parents[2]
    rule = packet["rule"]
    if not isinstance(rule, dict) or set(rule) != {"id", "owner"}:
        return ["an applicable rule needs its exact owner"]
    if not all(isinstance(rule[key], str) for key in ("id", "owner")):
        return ["rule identity and owner must be text"]
    # Existing owners only; no arbitrary file-read API or invented rule ID.
    owners = {
        "EXEC-RESPONSE-01": "saipen/EXECUTION.md",
        "PROTOCOL-ADMISSION-01": "saipen/EXECUTION.md",
    }
    if owners.get(rule.get("id")) != rule.get("owner"):
        return ["rule does not name its existing response/admission owner"]
    try:
        owner_text = (resolve_protocol_dir(engine) / "EXECUTION.md").read_text(encoding="utf-8")
        if f"RULE-OWNER: {rule['id']}" not in owner_text and rule["id"] != "PROTOCOL-ADMISSION-01":
            return ["rule owner document is unavailable"]
        registry = json.loads(
            (engine / "extensions/adapters/registry.json").read_text(encoding="utf-8")
        )
        adapter = next((a for a in registry["adapters"] if a["id"] == packet["host"]), None)
    except (OSError, ValueError, KeyError):
        return ["diagnosis owner or host capability is unverified"]
    # Registry is declared capability only; it cannot prove an active gate.
    if (
        adapter is None
        or packet["enforcement"] not in {"ADVISORY", "UNAVAILABLE", "UNVERIFIED"}
        or (
            packet["enforcement"] == "ADVISORY"
            and adapter.get("response_enforcement") != "ADVISORY"
        )
    ):
        return ["diagnostic cannot assert unproven mechanical host enforcement"]
    if not isinstance(root, (str, Path)):
        return ["diagnosis needs the caller's bound evidence root"]
    try:
        base = Path(root).resolve()
        evidence_root = (base / ".saipen/evidence").resolve()
        evidence_root.relative_to(base)
    except (OSError, ValueError):
        return ["evidence root is not bound to this project"]
    observed = packet["observed"]
    if not isinstance(observed, list) or not observed or len(observed) > 32:
        return ["diagnosis needs bounded cited observations"]
    for item in observed:
        if not isinstance(item, dict) or set(item) != {"ref", "sha256", "quote"}:
            return ["observation needs a source reference, digest and exact quote"]
        ref, quote = item["ref"], item["quote"]
        if (
            not isinstance(ref, str)
            or not ref.startswith(".saipen/evidence/")
            or not isinstance(quote, str)
            or not quote.strip()
        ):
            return ["observation is not bound to project evidence"]
        try:
            path = (base / ref).resolve()
            path.relative_to(evidence_root)
            with path.open("rb") as stream:
                raw = stream.read(256 * 1024 + 1)
            if len(raw) > 256 * 1024:
                return ["cited evidence exceeds its bounded reader"]
            if hashlib.sha256(raw).hexdigest() != item["sha256"] or quote not in raw.decode(
                "utf-8-sig"
            ):
                return ["observation quote or digest does not match its source"]
        except (OSError, ValueError, UnicodeError):
            return ["cited evidence is unavailable or outside the bound project"]
    return []


def detail_mode_for_request(request: object) -> str:
    """The authorized DETAILS mode for one human request, or DETAIL_MODE_NONE.

    The ONLY input is what the human asked for. The outgoing response is never
    read: authorizing a field from the text that carries it would let any
    response authorize itself.
    """
    if not isinstance(request, str) or not request.strip():
        return DETAIL_MODE_NONE
    if _diagnosis_request(request):
        return DETAIL_MODE_REPORT
    for mode, grammar in _DETAIL_REQUEST_GRAMMARS:
        if grammar.fullmatch(request):
            return mode
    return DETAIL_MODE_NONE


def detail_mode_is_valid(mode: object) -> bool:
    return isinstance(mode, str) and mode in DETAIL_MODES


def human_response_authority(
    request: object, provenance: object, *, root=None, receipt: str | None = None,
) -> bool:
    """The original, exact HUMAN carrier is the sole response expansion grant."""
    from .operator_task import authority_for_provenance
    from .pending_ingress import ingress_digest

    return bool(
        isinstance(request, str)
        and isinstance(provenance, dict)
        and provenance.get("compared_digest") == ingress_digest(request)
        and authority_for_provenance(
            provenance, root=root, receipt=receipt, existing_only=True,
        )["detailed_response"]
    )


def artifact_for_request(request: object) -> str | None:
    """Explicit requested document content, not a retrospective chosen by us.

    Artifact bytes have a separate bounded carrier; surrounding chat remains
    compact. A fence, filename or DETAILS in outgoing text is never a grant.
    """
    if not isinstance(request, str):
        return None
    if _diagnosis_request(request):
        return "PROTOCOL_DIAGNOSIS"
    mode = detail_mode_for_request(request)
    if mode == DETAIL_MODE_HANDOFF:
        return "HANDOFF"
    grammars = (
        ("HANDOFF", _EN_VERB + r"(?:implementation\s+)?hand[\s-]?off(?:\s+for this project)?"),
        ("AUDIT", _EN_VERB + r"(?:the\s+)?audit"),
        ("AUDIT", r"(?:please\s+)?audit (?:this project|the accepted debt)"),
        ("SPEC", _EN_VERB + r"(?:implementation\s+)?(?:spec|specification)"),
        ("AUDIT", r"(?:напиши|подготовь)\s+аудит"),
        ("SPEC", r"(?:напиши|подготовь)\s+(?:техническую\s+)?спецификацию"),
        ("AUDIT", r"(?:kirjuta|koosta)\s+audit"),
        ("SPEC", r"(?:kirjuta|koosta)\s+(?:tehniline\s+)?spetsifikatsioon"),
        (
            "INVENTORY",
            r"(?:please\s+)?(?:list every remaining blocker|list all "
            r"(?:blockers|commits|evidence records|changed files|test failures|workers|warnings))",
        ),
        ("RAW_LOG", r"(?:please\s+)?(?:show|provide|give me)\s+(?:the\s+)?raw logs"),
    )
    for kind, grammar in grammars:
        if re.fullmatch(r"\s*(?:" + grammar + r")\s*[.!?]?\s*", request, re.IGNORECASE):
            return kind
    if mode == DETAIL_MODE_AUDIT:
        return "AUDIT"
    return None


ARTIFACT_CHAR_BUDGET = 160_000


def response_reason(
    *,
    reason: str = "final",
    operator_due: bool = False,
    executable: bool = False,
    detail_mode: str = DETAIL_MODE_NONE,
) -> str:
    if detail_mode != DETAIL_MODE_NONE:
        return EXPLICIT_DETAILED_REPORT
    if reason in ("stop", STOP_HANDBACK):
        return STOP_HANDBACK
    if reason in ("safety", SAFETY_BOUNDARY):
        return SAFETY_BOUNDARY
    if operator_due:
        return HUMAN_ACTION_BLOCKER
    if executable and reason not in ("status", "summary"):
        return SILENT_CONTINUATION
    return COMPACT_FINAL


def parse_surface(rendered: str) -> tuple[dict[str, str], list[str]]:
    """One parser for canonical inline fields and legacy diagnostic records.

    Empty optional action fields have a canonical NONE value, not a second
    presentation. Legacy vertical records are readable but still pay their
    actual visible line budget at the delivery gate.
    """
    lines = rendered.splitlines()
    headings = []
    for index, line in enumerate(lines):
        name = line if line in FIELD_ORDER else line.split(":", 1)[0]
        if name in FIELD_ORDER and (line == name or line.startswith(name + ": ")):
            headings.append((index, name, line[len(name) + 2 :] if line != name else ""))
    names = [name for _, name, _ in headings]
    errors = []
    if not lines or not headings or headings[0][0] != 0 or headings[0][1] != "STATUS":
        errors.append("prose before STATUS or missing STATUS header")
    for name in ("STATUS", "RESULT", "NEXT EXACT ACTION", "VALIDATION"):
        if names.count(name) != 1:
            errors.append(f"{name} must occur exactly once")
    for name in FIELD_ORDER:
        if names.count(name) > 1:
            errors.append(f"{name} must occur at most once")
    if [FIELD_ORDER.index(name) for name in names] != sorted(
        FIELD_ORDER.index(name) for name in names
    ):
        errors.append("fields render outside the canonical order")
    values = {"BLOCKER": "NONE", "OPERATOR ACTION": "NONE"}
    for offset, (index, name, inline) in enumerate(headings):
        end = headings[offset + 1][0] if offset + 1 < len(headings) else len(lines)
        values[name] = "\n".join(([inline] if inline else []) + lines[index + 1 : end]).strip()
        if not values[name]:
            errors.append(f"{name} has no value")
    return values, errors


def _machine_scalar(value: object, *, limit: int, fallback: str) -> str:
    """Do not truncate claims. Invalid unbounded facts receive a closed sentinel."""
    text = str(value or "").strip()
    return text if text and len(text) <= limit and not re.search(r"[\r\n\x00]", text) else fallback


def _suite_validation(groups: object) -> str:
    """The declared suite's totals for VALIDATION, from typed record facts only.

    T-1658: the suite result of a project without the unit family existed as
    LOG prose alone, so the checkpoint could not state it. Every value here is
    an integer or a closed status read from an engine-written record; a
    malformed carrier renders nothing rather than a guessed number.
    """
    if not isinstance(groups, list) or not groups or not isinstance(groups[0], dict):
        return ""
    group = groups[0]

    def count(key: str) -> int | None:
        value = group.get(key)
        whole = isinstance(value, int) and not isinstance(value, bool)
        return value if whole and value >= 0 else None

    ran, red, skipped = count("ran"), count("red"), count("skipped")
    if group.get("status") == "TIMEOUT":
        return " | suite TIMEOUT"
    if ran is None or red is None:
        code = group.get("exit_code")
        if isinstance(code, int) and not isinstance(code, bool):
            return f" | suite exit {code}"
        return ""
    return f" | suite {ran} (red {red}" + (f", skipped {skipped}" if skipped else "") + ")"


def digest_from_facts(facts: dict, *, reason: str = "final", language: str = "et") -> str:
    """Fail compactly even when a facts carrier itself is malformed."""
    try:
        if not isinstance(facts, dict):
            raise TypeError("response facts must be a mapping")
        return _digest_from_facts(facts, reason=reason, language=language)
    except (TypeError, ValueError, AttributeError, OverflowError):
        return compact_failure(language=language)


def compact_failure(*, language: str = "et", operator_due: bool = False) -> str:
    """Closed failure carrier, never the rejected prose or a guessed state."""
    action = {
        "et": "Kinnita puuduv operaatori otsus; tõendid .saipen/evidence/response.",
        "ru": "Подтвердите требуемое решение; доказательства .saipen/evidence/response.",
        "en": "Confirm the required decision; evidence .saipen/evidence/response.",
    }.get(language, "Confirm the required decision; evidence .saipen/evidence/response.")
    return render_boundary(
        OperationalBoundary(
            "UNKNOWN",
            "RESPONSE_FACT_INVALID",
            "NONE",
            action if operator_due else "NONE",
            "NONE",
            "UNKNOWN | .saipen/evidence/response",
        )
    )


def _digest_from_facts(facts: dict, *, reason: str, language: str) -> str:
    """State -> fixed response facts -> canonical renderer, O(1) visible size.

    Full inventories remain in their canonical evidence/ledger carriers. We
    aggregate counts, never copy model retrospectives or truncate evidence.
    This builder has no free prose/report input and cannot authorize detail.
    """
    phase = _machine_scalar(facts.get("phase"), limit=24, fallback="UNKNOWN")
    task = str(facts.get("task") or "none")
    task = task if re.fullmatch(r"T-\d{1,8}", task) else "none"
    due = bool(
        facts.get("operator_due") or (facts.get("automation") or {}).get("operator_action_due")
    )
    auto = facts.get("automation") or {}
    executable = bool(
        facts.get("executable_action_remains")
        or (auto.get("disposition") == "CONTINUE" and auto.get("next_command"))
    )
    klass = response_reason(reason=reason, operator_due=due, executable=executable)
    if klass == SILENT_CONTINUATION:
        return ""
    words = {
        "et": (
            "Peatatud operaatori soovil",
            "Valmis",
            "Vajab operaatori otsust",
            "Töö säilitatud",
            "lõpetatud",
            "blokeeritud",
            "tõendid säilitatud",
        ),
        "ru": (
            "Остановлено оператором",
            "Готово",
            "Нужно решение оператора",
            "Работа сохранена",
            "завершено",
            "блокеров",
            "доказательства сохранены",
        ),
        "en": (
            "Stopped by operator",
            "Complete",
            "Operator decision required",
            "Work preserved",
            "completed",
            "blockers",
            "evidence recorded",
        ),
    }.get(
        language,
        (
            "Stopped by operator",
            "Complete",
            "Operator decision required",
            "Work preserved",
            "completed",
            "blockers",
            "evidence recorded",
        ),
    )
    result = (
        words[0]
        if klass == STOP_HANDBACK
        else words[2]
        if due
        else words[1]
        if phase == "DONE"
        and auto.get("disposition") not in {"BLOCKED", "WAIT_EXTERNAL", "INVALID"}
        else words[3]
    )
    completed = facts.get("completed") or []
    completed_ids = [str(t) for t in completed if re.fullmatch(r"T-\d{1,8}", str(t))]
    if completed_ids:
        result += (
            "; "
            + (completed_ids[0] if len(completed_ids) == 1 else str(len(completed_ids)))
            + " "
            + words[4]
        )
    blockers = facts.get("blockers") or []
    if blockers:
        counts = Counter(
            str(b.get("blocker") or "UNKNOWN").split(" -- ", 1)[0]
            for b in blockers
            if isinstance(b, dict)
        )
        # A bounded category summary, never a row/ticket inventory.
        categories = [
            (k, n)
            for k, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
            if re.fullmatch(r"[A-Z_]{1,30}", k)
        ][:3]
        result += f"; {len(blockers)} {words[5]}"
        if categories:
            result += " (" + ", ".join(f"{k} {n}" for k, n in categories) + ")"
    validation = _machine_scalar(facts.get("validation"), limit=40, fallback="UNKNOWN")
    groups = facts.get("test_groups") or []
    if groups:
        ran = sum(max(0, int(g.get("ran", 0))) for g in groups if isinstance(g, dict))
        red = sum(max(0, int(g.get("red", 0))) for g in groups if isinstance(g, dict))
        new_red = sum(max(0, int(g.get("new_red", 0))) for g in groups if isinstance(g, dict))
        validation += f" | full core {ran} | red {red} | new_red {new_red}"
    validation += _suite_validation(facts.get("suite_groups"))
    if facts.get("evidence"):
        validation += " | " + words[6]
    blocker = (
        "NONE"
        if _is_none(facts.get("blocker"))
        else _machine_scalar(
            facts.get("blocker"), limit=300, fallback="RESPONSE_FACT_INVALID -- evidence recorded"
        )
    )
    if _is_none(blocker):
        blocker = "NONE"
    elif not _BLOCKER_CODE.match(blocker):
        blocker = "RESPONSE_FACT_INVALID -- evidence recorded"
    action = _machine_scalar(facts.get("operator_action"), limit=300, fallback="NONE")
    if due and _is_none(action):
        action = {
            "et": "Anna puuduva otsuse volitus.",
            "ru": "Подтвердите требуемое решение.",
            "en": "Supply the required decision.",
        }.get(language, "Supply the required decision.")
    next_action = _machine_scalar(facts.get("next_action"), limit=240, fallback="NONE")
    if due and next_action.startswith("WAIT:"):
        next_action = "NONE"  # the human decision has exactly one owner: ACTION
    fields = (
        phase + (" " + task if task != "none" else ""),
        result,
        blocker,
        action,
        next_action,
        validation,
    )
    pointer = details_pointer(facts.get("detail_refs"))
    if pointer:
        # The pointer is where the detail lives, so a reader is never left to
        # choose between a wall and nothing. It yields to the boundary's own
        # line budget: the control fields come first.
        try:
            return render_boundary(OperationalBoundary(*fields, pointer), response_class=klass)
        except ValueError:
            pass
    return render_boundary(OperationalBoundary(*fields), response_class=klass)


#: The operations at which "what this run completed" starts over: a stop, and
#: every operator ingress (a user request, a goal). T-1659: the window used to
#: be the last stop alone, and a project that is never stopped never reset it
#: -- one answered `133 completed` after a run that finished a single ticket.
RUN_BOUNDARY_OPS = ("stop-", "userreq-", "goal-", "goal-entry-")


def canonical_facts(root, *, status: dict | None = None) -> dict:
    """Read owned state/evidence once; a host never supplies its own history."""
    from pathlib import Path
    from . import codec, core_unit
    from .board import parse_board
    from .conformance import conformance_status
    from .log import read_history_snapshot
    from .state import parse_state

    base = Path(root)
    state = parse_state(codec.read_doc(base / ".saipen/STATE.md"))
    board = parse_board(codec.read_doc(base / ".saipen/BOARD.md"))
    events = read_history_snapshot(base, lean=True).events
    since = max(
        (e["event"] for e in events if str(e.get("op_id") or "").startswith("stop-")), default=0
    )
    # `since` stays the last STOP: it alone decides the stop reason below.
    run_start = max(
        (e["event"] for e in events if str(e.get("op_id") or "").startswith(RUN_BOUNDARY_OPS)),
        default=0,
    )
    completed = sorted(
        {
            e.get("ticket")
            for e in events
            if e["event"] > run_start
            and str(e.get("op_id") or "").startswith("finish-")
            and str(e.get("text") or "").startswith("ticket finished via SAIOPS")
            and e.get("taxonomy") == "DEC"
            and e.get("ticket")
        }
    )
    # Where the detail of what was completed lives: for the ticket this run
    # finished last, its last verification verdict and its finish event.
    # Machine-written shapes only; the pointer never quotes what they say.
    # The NEWEST completion, not the first by name: the detail a reader wants
    # is of the last ticket the run finished.
    finishes = sorted(
        (e["event"], e.get("ticket"))
        for e in events
        if e["event"] > run_start
        and str(e.get("op_id") or "").startswith("finish-")
        and e.get("ticket") in completed
    )
    recent: list[str] = []
    for _number, ticket in reversed(finishes):
        if ticket not in recent:
            recent.append(ticket)
        if len(recent) == 1:
            break
    detail_refs: list[str] = []
    for ticket in reversed(recent):
        verified = [
            e["event"]
            for e in events
            if e.get("ticket") == ticket
            and e.get("taxonomy") == "RUN"
            and str(e.get("text") or "").startswith("verify -> PASS")
        ]
        finished = [number for number, name in finishes if name == ticket]
        for number in (verified[-1:] + finished[-1:]):
            detail_refs.append(f"E-{int(number):03d}")
    # The family record is found by hashing the whole tree. A project that
    # declares no family can hold none, and hashing a large product tree to
    # learn that cost 22 of the 25 seconds this function took there (measured
    # 2026-10-07): a compact form nobody can afford to ask for is not used.
    record = None
    if core_unit.declared(base) and (base / core_unit.RECORD_DIR_REL).is_dir():
        record = core_unit.reusable_record(base, core_unit.tree_fingerprint(base))
    # T-1658: the project's own declared suite, for any project. Only a record
    # of the declared command whose tree is the current tree; nothing is read
    # from LOG text, and a project that declares none pays no git call.
    from . import suite_record

    suite = suite_record.current_record(base)
    current = (status or {}).get("conformance_status") or conformance_status(base, gate="core")
    auto = (status or {}).get("automation") or {}
    facts = {
        **state,
        "validation": current.get("status", "UNKNOWN"),
        "completed": completed,
        "automation": auto,
        "operator_due": bool(auto.get("operator_action_due")),
        "blockers": [
            {"ticket": t["id"], "blocker": (t.get("fields") or {}).get("blocker", "UNKNOWN")}
            for t in board["tickets"].values()
            if t["section"] == "## BLOCKED"
        ],
        "evidence": [found["path"] for found in (record, suite) if found],
        "suite_groups": [suite_record.digest_group(suite["record"])] if suite else [],
        "detail_refs": detail_refs,
        "test_groups": [
            {
                "ran": record["record"].get("ran", 0),
                "red": len(record["record"].get("red", [])),
                "new_red": len(
                    core_unit.judge(
                        record["record"], (core_unit.load_baseline(base)[0] or {}).get("red", [])
                    )["new_red"]
                ),
            }
        ]
        if record
        else [],
        "response_reason": "stop" if since and state.get("last_event") == since else "final",
    }
    if auto.get("disposition") == "BLOCKED" and auto.get("reason_code") == "audit-inbox-unworkable":
        # The router's diagnostic is a stop, never another synthetic cc or a
        # request for operator authority. Preserve the actual lifecycle phase.
        facts["blocker"] = "AUDIT_INBOX_UNWORKABLE -- ACTIVE audit"
        facts["next_action"] = "NONE"
    invalid_stops = {
        "audit-inbox-invalid": "AUDIT_INBOX_INVALID -- unreadable audit layer",
        "queued-source-invalid": "QUEUED_SOURCE_INVALID -- unreadable queued Source",
    }
    if auto.get("disposition") == "INVALID" and auto.get("reason_code") in invalid_stops:
        facts["blocker"] = invalid_stops[auto["reason_code"]]
        facts["next_action"] = "NONE"
    if facts["operator_due"]:
        # STATE's legal WAIT owns the actual required decision. Do not print
        # the router's generic prose or assign its command to the operator.
        wait = str(state.get("next_action") or "")
        if wait.startswith("WAIT:"):
            facts["operator_action"] = wait[5:].strip()
    if auto.get("reason_code") in ("reconcile-decision", "reconcile-refused"):
        # T-1751: no STATE WAIT carries a reconcile refusal; the automation
        # block does, from its owner. The persisted next_action is the route
        # the continuation refuses, so it is never printed as the next step.
        code = str(auto.get("reconcile_code") or "RECONCILE_REFUSED")
        facts["blocker"] = f"{code} -- recovery refuses the continuation; saipen recover --json"
        if auto.get("operator_action"):
            facts["operator_action"] = auto["operator_action"]
        facts["next_action"] = "NONE"
    return facts


def reason_for_request(request: object) -> str:
    if not isinstance(request, str):
        return "final"
    if _diagnosis_request(request):
        return "summary"
    if re.fullmatch(
        r"\s*(?:(?:saipen\s+)?(?:stop|st)|peatu|стоп|остановись)\s*[.!]?\s*", request, re.IGNORECASE
    ):
        return "stop"
    if re.fullmatch(
        r"\s*(?:(?:saipen\s+)?(?:status|sss)|what happened\??|where are we\??|"
        r"give me a (?:summary|brief|final report)|(?:brief|quick) update|short (?:report|status)|"
        r"tell me the result|дай (?:сводку|краткий отч[её]т)|"
        r"что (?:там|сделал|получилось)\??|где мы\??|статус|"
        r"anna kokkuvõte|lühike raport|mis juhtus\??|staatus|kus me oleme\??)\s*[.!]?\s*",
        request,
        re.IGNORECASE,
    ):
        return "summary"
    return "final"


def _carries_a_second_command(text: str) -> bool:
    """Two canonical commands in one field, e.g. `saipen validate saipen continue`.

    Shell-quoted by the same canonical tokenizer the recognizer uses, so a
    quoted ingress payload that merely MENTIONS a command
    (`saipen start 'fix saipen guard'`) is one action, not two.
    """
    try:
        tokens = shlex.split(text)
    except ValueError:
        return False
    return any(token.lower() in _ACTION_COMMAND_WORDS for token in tokens[1:])


def _action_is_single(value: str) -> bool:
    """Is this one exact action rather than a chain, a sequence or a list?"""
    text = value.strip()
    if not text or _is_none(text):
        return True
    if _ACTION_CHAIN.search(text) or _ACTION_SEQUENCE.search(text):
        return False
    if not _ACTION_COMMAND_START.match(text):
        return True
    from .guard_events import saipen_line_problem

    return saipen_line_problem(text) is None and not _carries_a_second_command(text)


def _is_none(value: object) -> bool:
    return str(value if value is not None else "").strip().upper() in NONE_VALUES


#: The phases a ticket is still WORKING in; a STATUS led by one is not final.
_IN_FLIGHT_PHASES = frozenset({"SCOUT", "BUILD", "VERIFY", "REVIEW", "SHIP"})


def _names_in_flight_phase(status: object) -> bool:
    head = re.match(r"\s*(?:T-\d+\s+)?([A-Za-z][A-Za-z_]*)", str(status or ""))
    return bool(head) and head.group(1).upper() in _IN_FLIGHT_PHASES


@dataclass(frozen=True)
class OperationalBoundary:
    status: str
    result: str
    blocker: str
    operator_action: str
    next_exact_action: str
    validation: str
    details: str = ""
    # Declared after `details` so positional callers keep their meaning; it
    # still RENDERS before DETAILS (FIELD_ORDER decides order, not this class).
    efficiency: str = ""

    def fields(self) -> dict[str, str]:
        values = {
            "STATUS": self.status,
            "RESULT": self.result,
            "BLOCKER": self.blocker,
            "OPERATOR ACTION": self.operator_action,
            "NEXT EXACT ACTION": self.next_exact_action,
            "VALIDATION": self.validation,
        }
        if self.efficiency:
            values["EFFICIENCY"] = self.efficiency
        if self.details:
            values["DETAILS"] = self.details
        return values


#: T-1821: the separator between canonical fields is a MARKDOWN HARD BREAK
#: (two spaces then a newline), not a bare newline. The surface is delivered into
#: Markdown hosts, and CommonMark/GFM treats a newline inside a paragraph run as
#: a soft break -- the fields collapse into one paragraph. Measured on the
#: operator's own host (Streamdown: remark-gfm, no remark-breaks): the AST of
#: `"a\nb"` is ONE text node, while `"a  \nb"` is text/`break`/text, and
#: `parseMarkdownIntoBlocks` keeps both in one block either way. The report the
#: operator called "one enormous paragraph" was this renderer's output: six
#: correct fields delivered as one run of prose. A two-space hard break keeps
#: one visible line per field, so the line budget in EXECUTION.md ("labels,
#: blanks, fences included") is unchanged and nothing is granted.
FIELD_SEPARATOR = "  \n"


def _field_text(value: object) -> str:
    """One field's value, with every internal line hard-broken for Markdown.

    T-1821: the separator between fields was only half the collapse. An
    authorized DETAILS value that carries its own newlines (a reference list,
    an audit block) reintroduced exactly the same soft break one level down, so
    a report the operator explicitly asked for still arrived as one paragraph.
    The fix belongs to the value, not to the caller: normalize every line end
    inside the value to the same hard break the separator uses. The visible
    line count and the character budget are unchanged apart from the two spaces
    per break, which is what makes the lines visibly separate.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return FIELD_SEPARATOR.join(lines)


def render_boundary(
    boundary: OperationalBoundary,
    *,
    current_validation: str | None = None,
    detail_mode: str = DETAIL_MODE_NONE,
    response_class: str | None = None,
) -> str:
    """Assemble one operational handback from typed fields, then validate it."""
    fields = boundary.fields()
    rendered = FIELD_SEPARATOR.join(
        f"{key}: {_field_text(value)}"
        for key, value in fields.items()
        if key not in ("BLOCKER", "OPERATOR ACTION") or not _is_none(value)
    )
    errors = response_errors(
        rendered,
        current_validation=current_validation,
        detail_mode=detail_mode,
        response_class=response_class,
    )
    if errors:
        raise ValueError("; ".join(errors))
    return rendered


def response_errors(
    rendered: str,
    *,
    executable_action_remains: bool = False,
    response_boundary: bool = True,
    current_validation: str | None = None,
    current_phase: str | None = None,
    current_task: str | None = None,
    current_blocker: str | None = None,
    operator_due: bool = False,
    detail_mode: str = DETAIL_MODE_NONE,
    response_class: str | None = None,
) -> list[str]:
    """Validate the actual text a host will return, including its first byte."""
    if not detail_mode_is_valid(detail_mode):
        return [f"unknown detail_mode {detail_mode!r}; authorization requires a closed mode"]
    if not isinstance(rendered, str) or not rendered:
        return ["empty operational response"]
    lines = rendered.splitlines()
    values, errors = parse_surface(rendered)
    blocker = values.get("BLOCKER", "")
    if blocker and not _is_none(blocker) and not _BLOCKER_CODE.match(blocker):
        errors.append("BLOCKER needs a canonical code and bounded reason")
    operator_action = values.get("OPERATOR ACTION", "")
    if _AGENT_COMMAND.match(operator_action) or _AGENT_INSTRUCTION.match(operator_action):
        errors.append("OPERATOR ACTION cannot assign an agent command to the human")
    next_action = values.get("NEXT EXACT ACTION", "")
    if next_action.strip().lower() in _VAGUE_ACTIONS:
        errors.append("NEXT EXACT ACTION is vague")
    if not _action_is_single(next_action):
        errors.append(
            "NEXT EXACT ACTION must be exactly one action -- a chain (`&&`, `||`, "
            "`;`), a sequence (`then`) or a second command is not one action"
        )
    if values.get("STATUS", "").upper().startswith("WAIT") and _is_none(operator_action):
        errors.append("WAIT without OPERATOR ACTION is invalid")
    if should_continue(
        operator_action=operator_action,
        executable_action_remains=executable_action_remains,
        response_boundary=response_boundary,
    ):
        errors.append("eligible autonomous action remains; returning control is invalid")
    for name, budget in FIELD_LINE_BUDGETS.items():
        if name not in values:
            continue
        content = [line for line in values[name].splitlines() if line.strip()]
        if len(content) > budget:
            errors.append(
                f"{name} exceeds {budget} content line(s) -- the schema is bounded "
                "over field content, not over the mandatory labels"
            )
    for name, budget in FIELD_CHAR_BUDGETS.items():
        if name not in values:
            continue
        size = len(values[name])
        if size > budget:
            errors.append(
                f"{name} exceeds {budget} character(s) ({size}) -- a line count is "
                "not a compactness contract"
            )
    # T-1556 #1: DETAILS is authorization-gated before it is budgeted. A
    # forbidden field is refused whatever its size, and an authorized one is
    # still bounded.
    if (
        "DETAILS" in values
        and detail_mode == DETAIL_MODE_NONE
        and not details_is_pointer(values["DETAILS"])
    ):
        errors.append(
            "DETAILS is not authorized on an ordinary response -- the detailed "
            "path is an explicit report, audit, handoff or exceptional boundary; "
            "an ordinary response may carry one short line of references only"
        )
    # T-1576: EFFICIENCY is derived telemetry for the FINAL report. Silent
    # execution has no KPI heartbeat, so a STATUS that names an in-flight
    # phase may not carry it, and its value must be the owner's rendered
    # grammar -- which has no word in which it could claim quality.
    if "EFFICIENCY" in values:
        problem = _efficiency_line_problem(values["EFFICIENCY"])
        if problem:
            errors.append(problem)
        if _names_in_flight_phase(values.get("STATUS", "")):
            errors.append(
                "EFFICIENCY belongs to the final boundary -- an in-flight STATUS "
                "carries no KPI (silent execution)"
            )
    klass = response_class or response_reason(
        operator_due=operator_due or not _is_none(operator_action), detail_mode=detail_mode
    )
    if klass not in REASON_BUDGETS:
        return [*errors, f"unknown response_class {klass!r}"]
    if klass == EXPLICIT_DETAILED_REPORT and detail_mode == DETAIL_MODE_NONE:
        errors.append("detailed response class requires human depth authority")
    line_budget, total_budget = REASON_BUDGETS[klass]
    if len(lines) > line_budget:
        errors.append(f"actual rendered reply exceeds {line_budget} visible lines ({len(lines)})")
    if len(rendered) > total_budget:
        errors.append(
            f"the whole response is {len(rendered)} characters -- the budget for "
            f"this boundary is {total_budget}"
        )
    if detail_mode == DETAIL_MODE_NONE:
        for name in ("RESULT", "VALIDATION"):
            value = values.get(name, "")
            if len(re.findall(r"(?<![\w-])(?:T|SRC|E)-\d+(?![\w-])", value)) > 3:
                errors.append(
                    f"{name} contains an inventory; store rows and render aggregate counts"
                )
            if re.search(r"(?i)(?:[0-9a-f]{40,64}[ ,|;]*){2,}", value):
                errors.append(
                    f"{name} contains commit/evidence hashes; evidence is the durable owner"
                )
        result = values.get("RESULT", "")
        if re.search(
            r"\b(?:CURRENT_PASS|STALE_PASS|CURRENT_FAIL)\b|\b(?:red|new_red)\s+\d+", result
        ):
            errors.append("validation facts belong only to VALIDATION")
        for name in ("RESULT", "VALIDATION", "BLOCKER", "OPERATOR ACTION", "NEXT EXACT ACTION"):
            value = values.get(name, "")
            if len(value) > 15 and not _is_none(value):
                for other in (
                    "RESULT",
                    "VALIDATION",
                    "BLOCKER",
                    "OPERATOR ACTION",
                    "NEXT EXACT ACTION",
                ):
                    if other != name and value in values.get(other, ""):
                        errors.append(f"duplicate semantic fact across {name} and {other}")
    for name in ("BLOCKER", "OPERATOR ACTION", "NEXT EXACT ACTION"):
        value = values.get(name, "")
        if "\n" not in value and value.strip().startswith("-"):
            errors.append(f"{name} must be one action, not a list")
    if current_validation:
        first_validation = values.get("VALIDATION", "").splitlines()
        first_token = (
            first_validation[0].strip().split()[0]
            if first_validation and first_validation[0].strip()
            else ""
        )
        if first_token != current_validation:
            errors.append(f"VALIDATION must start with current {current_validation}")
    current_status = values.get("STATUS", "").upper()
    if current_phase:
        raw_status = values.get("STATUS", "")
        status_tokens = set(re.findall(r"(?<![\w-])[A-Z][A-Z_]*(?![\w-])", raw_status))
        named_phases = status_tokens & ALL_PHASES
        first_word = re.match(r"[A-Za-z][A-Za-z_]*", raw_status)
        if first_word and first_word.group().upper() in ALL_PHASES:
            named_phases.add(first_word.group().upper())
        head = re.match(r"(?:(T-\d+)\s+)?([A-Za-z][A-Za-z_]*)(?![\w-])", raw_status)
        leading_phase = head.group(2).upper() if head else ""
        leading_task = head.group(1) if head else None
        is_operator_wait = leading_task is None and leading_phase == "WAIT" and operator_due
        valid_head = (
            leading_phase == current_phase.upper()
            and (leading_task is None or leading_task == current_task)
        ) or is_operator_wait
        phase_matches = named_phases == {current_phase.upper()} or (
            is_operator_wait and not named_phases
        )
        if not valid_head or not phase_matches:
            errors.append(f"STATUS must name current phase {current_phase}")
    if current_task and current_task.lower() != "none":
        named_tasks = set(re.findall(r"(?<![\w-])T-\d+(?![\w-])", current_status))
        if named_tasks != {current_task.upper()}:
            errors.append(f"STATUS must name current task {current_task}")
    if current_blocker and current_blocker.strip() and not _is_none(current_blocker):
        # A project with no blocker reports the canonical `none` sentinel. That
        # is not a blocker CODE, so demanding the response name it refused every
        # `BLOCKER: NONE` surface on a healthy project -- the case the surface is
        # written for. `_is_none` is the one "no blocker" test.
        code = current_blocker.split(" -- ", 1)[0].split(":", 1)[0].strip()
        rendered_code = blocker.split(" -- ", 1)[0].strip()
        if code and rendered_code != code:
            errors.append(f"BLOCKER must name current {code}")
    if operator_due and _is_none(operator_action):
        errors.append("OPERATOR ACTION is required by the current route")
    if executable_action_remains and not operator_due and not _is_none(operator_action):
        errors.append("OPERATOR ACTION is not due on the current route")
    return errors


def surface_errors(fields: dict, *, status: str = "") -> list[str]:
    """Why a control block does not satisfy EXEC-RESPONSE-01, or []."""
    if not isinstance(fields, dict):
        return ["control surface must be a field mapping"]
    keys = [key for key in fields if key in FIELD_ORDER]
    errors: list[str] = []
    missing = [key for key in MANDATORY_FIELDS if key not in fields]
    if missing:
        errors.append("missing mandatory field(s): " + ", ".join(missing))
    positions = [FIELD_ORDER.index(key) for key in keys]
    if positions != sorted(positions):
        errors.append("fields render outside the canonical order")
    if "DETAILS" in fields and keys and keys[-1] != "DETAILS":
        errors.append("DETAILS must render last")
    if "EFFICIENCY" in fields:
        problem = _efficiency_line_problem(fields["EFFICIENCY"])
        if problem:
            errors.append(problem)
        if _names_in_flight_phase(status):
            errors.append("EFFICIENCY belongs to the final boundary (silent execution)")
    # A WAIT that names no human action is the exact ambiguity the surface
    # exists to remove: the human cannot discover whether they must act.
    if str(status).strip().upper().startswith("WAIT") and _is_none(fields.get("OPERATOR ACTION")):
        errors.append("WAIT without OPERATOR ACTION is invalid")
    return errors


def should_continue(
    *,
    operator_action: object,
    executable_action_remains: bool,
    response_boundary: bool,
) -> bool:
    """May the agent continue internally instead of returning to the user?

    True only when NO human action is required, a canonically executable action
    remains, and the moment is not a true response boundary. A required human
    action, an exhausted route, or a genuine boundary all return the control
    surface instead.
    """
    if response_boundary:
        return False
    if not _is_none(operator_action):
        return False
    return bool(executable_action_remains)


# ---------------------------------------------------------------------------
# Host final-response gates (T-1551): ONE classifier over the outgoing text.
#
# A host Stop/text hook sees only the final message. It must decide whether
# EXEC-RESPONSE-01 governs that message at all -- and it must decide it HERE,
# in the canonical authority, never in an adapter-local copy of the rules.
# `classify_final_response` answers the only new question (does this text
# claim operational finality?) and then delegates every structural rule to
# `response_errors`, so no host adapter can drift from the contract by
# reimplementing it. There is no second response validator.

CLASS_VALID_BOUNDARY = "VALID_BOUNDARY"
CLASS_INVALID_OPERATIONAL_PROSE = "INVALID_OPERATIONAL_PROSE"
CLASS_AUTONOMOUS_HANDBACK = "AUTONOMOUS_HANDBACK"
CLASS_ORDINARY_CHAT = "ORDINARY_CHAT"
#: T-1558: ordinary conversation that breaks the measurable chat contract of
#: STYLE.md (`chat_style`): an essay over the chat budget, a banned sentinel
#: phrase, the wrong pinned language. Before this class existed every reply
#: without a control-surface marker was ORDINARY_CHAT and passed unmeasured.
CLASS_CHAT_STYLE_DRIFT = "CHAT_STYLE_DRIFT"
#: PROTOCOL-ADMISSION-01: the speaker was not admitted, so no reply is permitted
#: whatever its form. Decided by `protocol_admission`, before every other layer.
CLASS_ADMISSION_BLOCKED = "ADMISSION_BLOCKED"
RESPONSE_CLASSES = (
    CLASS_VALID_BOUNDARY,
    CLASS_INVALID_OPERATIONAL_PROSE,
    CLASS_AUTONOMOUS_HANDBACK,
    CLASS_ORDINARY_CHAT,
    CLASS_CHAT_STYLE_DRIFT,
    CLASS_ADMISSION_BLOCKED,
)

LAYER_ADMISSION = "ADMISSION"
LAYER_EXEC_RESPONSE = "EXEC_RESPONSE"
LAYER_CHAT_STYLE = "CHAT_STYLE"
LAYER_NONE = "NONE"

#: Free-form report shapes that claim the response IS an operational boundary:
#: control-surface label usage (`STATUS: ...`) and canonical blocker codes
#: (`SOME_CODE -- reason`) outside a rendered block.
_CONTROL_LABEL_USE = re.compile(
    r"(?im)^\s*(?:STATUS|RESULT|BLOCKER|OPERATOR ACTION|NEXT EXACT ACTION|"
    r"VALIDATION|EFFICIENCY|DETAILS)\s*(?::|-|--)\s*\S"
)
_BLOCKER_CODE_LINE = re.compile(r"(?m)^\s*[A-Z][A-Z0-9_]{2,} -- \S")

#: The autonomy failures of `response_errors`, restated as class markers so a
#: host maps its verdict without parsing rule prose.
_AUTONOMY_ERROR_MARKERS = (
    "eligible autonomous action remains",
    "OPERATOR ACTION is not due on the current route",
    "OPERATOR ACTION is required by the current route",
)


def claims_operational_finality(text: object) -> bool:
    """Does this text claim to BE a canonical operational boundary/report?

    True for a rendered control block (a FIELD_ORDER heading on its own line)
    and for free-form operational report shapes (label usage, blocker codes).
    Ordinary conversation carries none of these.
    """
    if not isinstance(text, str) or not text.strip():
        return False
    if any(line.strip() in FIELD_ORDER for line in text.splitlines()):
        return True
    return bool(_CONTROL_LABEL_USE.search(text) or _BLOCKER_CODE_LINE.search(text))


def classify_final_response(
    rendered: object,
    *,
    operational_turn: bool,
    executable_action_remains: bool = False,
    style_contract: object | None = None,
    **check_context: object,
) -> tuple[str, list[str]]:
    """The ONE host-gate verdict over an outgoing final response.

    Returns ``(class, errors)`` with exactly one of ``RESPONSE_CLASSES``:

    * ``VALID_BOUNDARY`` -- a well-formed operational boundary; the host lets
      it through.
    * ``INVALID_OPERATIONAL_PROSE`` -- the response is governed by
      EXEC-RESPONSE-01 (an operational turn, or text claiming operational
      finality) but is not an accepted boundary.
    * ``AUTONOMOUS_HANDBACK`` -- an operational turn returns control while
      eligible canonical work remains (T-1416 autonomy).
    * ``ORDINARY_CHAT`` -- ordinary non-operational conversation that meets
      the measurable chat contract of STYLE.md.
    * ``CHAT_STYLE_DRIFT`` -- ordinary conversation that does not: over the
      chat budget, a banned sentinel phrase, or not the pinned
      ``reply_language`` (T-1558, ``chat_style``).

    ``operational_turn`` is the turn-context fact only the host/canonical
    state knows (the turn executed canonical work, or canonical state routes
    it as AUTO_KICK / OPERATOR_WAIT / RECOVER). ``executable_action_remains``
    is the canonical automation fact; it is enforced ONLY on operational
    turns, mirroring the OpenCode gate's ``enforceAutonomy``.
    """
    # Only a witnessed HUMAN carrier may expand delivery. A caller's closed
    # mode is a request, not authority. Low-level render/check remain useful
    # for diagnostic fixtures; the final delivery gate settles the grant.
    requested_mode = check_context.get("detail_mode", DETAIL_MODE_NONE)
    if not detail_mode_is_valid(requested_mode):
        return CLASS_INVALID_OPERATIONAL_PROSE, [
            f"unknown detail_mode {requested_mode!r}; authorization requires a closed mode"
        ]
    human_request = check_context.pop("human_request", "")
    request_authority = check_context.pop("request_authority", None)
    diagnosis_root = check_context.pop("diagnosis_root", None)
    witnessed = human_response_authority(human_request, request_authority, root=diagnosis_root)
    if _diagnosis_request(human_request) and not witnessed:
        return CLASS_INVALID_OPERATIONAL_PROSE, [
            "protocol diagnosis needs independently verified operator ingress and caller project"
        ]
    detail_mode = detail_mode_for_request(human_request) if witnessed else DETAIL_MODE_NONE
    if requested_mode != DETAIL_MODE_NONE and requested_mode != detail_mode:
        return CLASS_INVALID_OPERATIONAL_PROSE, [
            "detail_mode is not authorized by witnessed human ingress"
        ]
    check_context["detail_mode"] = detail_mode
    artifact = artifact_for_request(human_request) if witnessed else None
    if artifact == "PROTOCOL_DIAGNOSIS":
        text = rendered if isinstance(rendered, str) else ""
        if len(text) > ARTIFACT_CHAR_BUDGET:
            return CLASS_INVALID_OPERATIONAL_PROSE, [
                "diagnosis exceeds its bounded artifact carrier"
            ]
        errors = _diagnosis_errors(text, human_request, diagnosis_root)
        return (CLASS_INVALID_OPERATIONAL_PROSE, errors) if errors else (CLASS_ORDINARY_CHAT, [])
    if artifact and not operational_turn:
        text = rendered if isinstance(rendered, str) else ""
        if len(text) > ARTIFACT_CHAR_BUDGET:
            return CLASS_CHAT_STYLE_DRIFT, [
                "requested artifact exceeds its bounded carrier; provide the actual file"
            ]
        return CLASS_ORDINARY_CHAT, []
    if not detail_mode_is_valid(detail_mode):
        return CLASS_INVALID_OPERATIONAL_PROSE, [
            f"unknown detail_mode {detail_mode!r}; authorization requires a closed mode"
        ]
    text = rendered if isinstance(rendered, str) else ""
    claims = claims_operational_finality(text)
    if not operational_turn and not claims:
        if detail_mode != DETAIL_MODE_NONE and (
            len(text.splitlines()) > REASON_BUDGETS[EXPLICIT_DETAILED_REPORT][0]
            or len(text) > REASON_BUDGETS[EXPLICIT_DETAILED_REPORT][1]
        ):
            return CLASS_CHAT_STYLE_DRIFT, [
                "explicit report exceeds its bounded visible carrier; store the report"
            ]
        if style_contract is not None:
            from .chat_style import chat_style_errors

            drift = chat_style_errors(
                text,
                contract=style_contract,
                detail_authorized=check_context.get("detail_mode", DETAIL_MODE_NONE)
                != DETAIL_MODE_NONE,
            )
            if drift:
                return CLASS_CHAT_STYLE_DRIFT, drift
        return CLASS_ORDINARY_CHAT, []
    # T-1553: an OPERATOR ACTION that is DUE settles the autonomy question --
    # handing control back to a human who owes an answer is the required
    # behaviour, not a premature yield. Without this the classifier and the
    # plain checker disagreed on the SAME text for the same project: a fresh
    # INIT project (routing says `cc` stays legal, but the human owes the first
    # goal) passed `response check --auto-eligibility` and failed
    # `response check --classify --auto-eligibility`, so one host accepted the
    # handback and another livelocked on it. `operator_due` arrives in the check
    # context, so it is read here rather than re-derived.
    if check_context.get("operator_due"):
        executable_action_remains = False
    if operational_turn and executable_action_remains and not text.strip():
        return CLASS_VALID_BOUNDARY, []
    if operational_turn and executable_action_remains:
        return CLASS_AUTONOMOUS_HANDBACK, [
            "eligible autonomous action remains; returning control is invalid"
        ]
    if not claims:
        return CLASS_INVALID_OPERATIONAL_PROSE, [
            "operational turn returned free-form prose; an operational response "
            "must render the canonical control surface"
        ]
    errors = response_errors(
        text,
        executable_action_remains=False,
        response_boundary=True,
        **check_context,
    )
    if not errors:
        if style_contract is not None:
            # A valid surface still has to be in the pinned language: a green
            # structural layer does not compensate for a failed style layer.
            from .chat_style import boundary_style_errors

            drift = boundary_style_errors(text, contract=style_contract)
            if drift:
                return CLASS_CHAT_STYLE_DRIFT, drift
        return CLASS_VALID_BOUNDARY, []
    if any(marker in error for error in errors for marker in _AUTONOMY_ERROR_MARKERS):
        return CLASS_AUTONOMOUS_HANDBACK, errors
    return CLASS_INVALID_OPERATIONAL_PROSE, errors


def gate_operator_question(tool_input: object, *, context: dict | None = None) -> dict:
    """OPERATOR-QUESTION-01: a native question is the same control handback.

    Context is supplied by the canonical status/response owners in the CLI,
    never taken from the host's question payload, chat or session files.
    Without typed choices in the canonical facts, no choice may be invented.
    """
    from . import automation

    context = context if isinstance(context, dict) else {}
    status = context.get("status") or {}
    auto = status.get("automation") or {}
    disposition = auto.get("disposition")
    valid = (
        status.get("ok") is True and auto.get("schema_version") == automation.SCHEMA_VERSION
        and disposition in automation.DISPOSITIONS
        and isinstance(auto.get("operator_action_due"), bool)
    )
    eligible = valid and disposition != automation.INVALID and (
        auto.get("operator_action_due") is True
    )
    canonical = str(context.get("operator_action") or "").strip()
    questions = tool_input.get("questions") if isinstance(tool_input, dict) else None
    exact = (
        isinstance(questions, list) and len(questions) == 1
        and isinstance(questions[0], dict) and bool(canonical)
        and questions[0].get("question") == canonical
        and questions[0].get("options", []) == []
        and not questions[0].get("multiSelect")
        and not tool_input.get("answers")
    )
    admitted = bool(eligible and exact)
    klass = (
        CLASS_VALID_BOUNDARY if admitted else CLASS_AUTONOMOUS_HANDBACK
        if valid and disposition == automation.CONTINUE and not eligible
        else CLASS_INVALID_OPERATIONAL_PROSE
    )
    command = (
        "saipen continue --json" if valid and disposition == automation.CONTINUE and not eligible
        else "saipen status --json"
    )
    detail = (
        "canonical operator control surface admitted" if admitted else
        f"{klass} -- OPERATOR-QUESTION-01: "
        + ("present canonical_surface only; no improvised question or choices; " if eligible
           else "no canonical operator decision is due; " if valid
           else "canonical question authority unavailable; ")
        + f"use {command}"
    )
    return {
        "schema_version": 1, "rule": "OPERATOR-QUESTION-01", "class": klass,
        "eligible": bool(eligible), "admitted": admitted,
        "disposition": disposition if valid else automation.INVALID,
        "next_action": status.get("computed_next_action") if valid else None,
        "canonical_next_command": command, "detail": detail,
        "canonical_surface": context.get("canonical_surface") if eligible else None,
    }


def gate_final_response(
    text: object,
    *,
    admission: dict | None,
    admission_consulted: bool,
    operational_turn: bool,
    style_contract: object | None,
    admission_skip_reason: str = "NOT_ENFORCEABLE",
    executable_action_remains: bool = False,
    facts: dict | None = None,
    reason: str = "final",
    **check_context: object,
) -> dict:
    """The layered verdict over one outgoing reply (PROTOCOL-ADMISSION-01).

    The chain is fixed and each layer answers a different question:

        ADMISSION      was the speaker admitted? (`protocol_admission`)
        EXEC_RESPONSE  is an operational response structurally valid?
        CHAT_STYLE     does the visible reply obey language and style?

    The first layer that fails decides, and later layers are reported
    NOT_REACHED: a green later layer never compensates for a failed earlier one,
    and a perfectly formed reply from an unadmitted speaker is still blocked. A
    host that cannot enforce admission is reported `NOT_ENFORCEABLE` (or
    `NOT_CONSULTED` when the caller supplied no session), never passed off as
    admitted.
    """
    layers = {
        "admission": (
            admission["state"] if admission_consulted and admission else admission_skip_reason
        ),
        "exec_response": "NOT_REACHED",
        "chat_style": "NOT_REACHED",
    }
    if admission_consulted and not (admission or {}).get("permitted"):
        from .protocol_admission import diagnostic

        message = diagnostic(admission or {"state": "REFUSED", "problems": []})
        return {
            "ok": False,
            "layer": LAYER_ADMISSION,
            "class": CLASS_ADMISSION_BLOCKED,
            "errors": [message],
            "diagnostic": message,
            "layers": layers,
        }
    ingress = check_context.get("human_request", "")
    provenance = check_context.get("request_authority")
    authorized = human_response_authority(
        ingress, provenance, root=check_context.get("diagnosis_root"),
    )
    delivered_reason = (
        reason_for_request(ingress) if authorized else (facts or {}).get("response_reason", "final")
    )
    if facts is not None:
        # Canonical automation owns liveness even when an adapter forgot the
        # diagnostic --auto-eligibility flag. A runnable project must not emit
        # an empty digest and then reject it as an invalid empty boundary.
        auto = facts.get("automation") or {}
        executable_action_remains = bool(
            facts.get("executable_action_remains")
            or (auto.get("disposition") == "CONTINUE" and auto.get("next_command"))
        )
    if delivered_reason in ("stop", "status", "summary"):
        executable_action_remains = False
    klass, errors = classify_final_response(
        text,
        operational_turn=operational_turn,
        executable_action_remains=executable_action_remains,
        style_contract=style_contract,
        **check_context,
    )
    delivery = None
    delivery_validation = "NOT_APPLICABLE"
    expanded = authorized and (
        detail_mode_for_request(ingress) != DETAIL_MODE_NONE or artifact_for_request(ingress)
    )
    if (
        facts is not None
        and (operational_turn or claims_operational_finality(text))
        and not expanded
    ):
        # A model-provided --request/--reason cannot manufacture a stop/status
        # exception to silent execution. Canonical stop facts or exact HUMAN
        # ingress own that boundary, independent of the outgoing prose.
        language = getattr(style_contract, "reply_language", None) or "et"
        delivery = digest_from_facts(facts, reason=delivered_reason, language=language)
        # Validate the candidate that the capable host will actually deliver,
        # not only the model text it rejected. Current state/style constraints
        # cannot be bypassed by the fact that the renderer is machine-owned.
        candidate_class, _candidate_errors = classify_final_response(
            delivery,
            operational_turn=True,
            executable_action_remains=executable_action_remains,
            style_contract=style_contract,
            **check_context,
        )
        if candidate_class != CLASS_VALID_BOUNDARY:
            delivery = compact_failure(
                language=language, operator_due=bool(check_context.get("operator_due"))
            )
            # UNKNOWN is a failure disposition, not a conflicting assertion
            # about current Work. Validate that closed failure carrier against
            # its own schema/style, not as an implementation success claim.
            failure_class, _failure_errors = classify_final_response(
                delivery,
                operational_turn=True,
                style_contract=style_contract,
            )
            if failure_class != CLASS_VALID_BOUNDARY:
                delivery = None
            delivery_validation = "COMPACT_FAILURE"
            klass = CLASS_INVALID_OPERATIONAL_PROSE
            errors = ["canonical response facts failed delivery validation"]
        else:
            delivery_validation = "PASS"
        normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if klass == CLASS_VALID_BOUNDARY and normalized != delivery:
            klass = CLASS_INVALID_OPERATIONAL_PROSE
            errors = ["operational delivery must equal the canonical machine digest"]
    if klass in (CLASS_INVALID_OPERATIONAL_PROSE, CLASS_AUTONOMOUS_HANDBACK):
        layers["exec_response"] = "FAIL"
        layer = LAYER_EXEC_RESPONSE
    elif klass == CLASS_CHAT_STYLE_DRIFT:
        layers["exec_response"] = (
            "PASS" if operational_turn or claims_operational_finality(text) else "NOT_APPLICABLE"
        )
        layers["chat_style"] = "FAIL"
        layer = LAYER_CHAT_STYLE
    else:
        layers["exec_response"] = "PASS" if klass == CLASS_VALID_BOUNDARY else "NOT_APPLICABLE"
        layers["chat_style"] = "PASS" if style_contract is not None else "NOT_EVALUATED"
        layer = LAYER_NONE
    overflow = None
    if operational_turn or claims_operational_finality(text):
        # The size rules as data, with what became of the reply: a capable
        # host delivers the compact form, and the original has one home.
        overflow = overflow_diagnostic(
            text,
            detail_mode=detail_mode_for_request(ingress) if authorized else DETAIL_MODE_NONE,
            operator_due=bool(check_context.get("operator_due")),
        )
        if overflow is not None:
            overflow["compaction"] = (
                COMPACTION_SUCCEEDED
                if delivery is not None and delivery_validation == "PASS"
                else COMPACTION_FAILED
                if delivery_validation == "COMPACT_FAILURE"
                else COMPACTION_NOT_ATTEMPTED
            )
    return {
        "ok": klass in (CLASS_VALID_BOUNDARY, CLASS_ORDINARY_CHAT),
        "layer": layer,
        "class": klass,
        "errors": errors,
        "diagnostic": None,
        "layers": layers,
        "overflow": overflow,
        # This is the delivery candidate, not an apology or a second model
        # attempt. A capable host replaces operational model output with it.
        "delivery": delivery,
        "delivery_validation": delivery_validation,
        **({"diagnosis_verification": "STRUCTURE_AND_CITATIONS_ONLY",
            "semantic_review": "REQUIRED"}
           if authorized and artifact_for_request(ingress) == "PROTOCOL_DIAGNOSIS" else {}),
    }
