#!/usr/bin/env python
"""SAIPEN Improve mechanical core (T-551, T-554..T-560).

The semantics live in saipen/IMPROVE.md; this module is the mechanical layer
that validates and writes the already-decided representation. It owns:

- deterministic, collision-safe cycle and seat admission;
- canonical report path resolution (never under the shared protocol install);
- report and finding schema validation (closed vocabularies);
- the Core-owned SWEEP ledger (dispositions, never written into reports);
- the derived visible status for `saipen improve status`.

Observation (seat report) and judgment (SWEEP ledger) never share one writable
file. Report identity carries no absolute machine-local path.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

# Report header fields (no machine-local path; identity is version + fingerprint).
REQUIRED_HEADER = {
    "agent", "role", "model_or_runtime", "project",
    "saipen_version", "protocol_fingerprint",
    "source_head", "source_tree_fingerprint",
    "context_scope", "context_available", "report_status",
}

SEVERITY = {"P0", "P1", "P2", "P3"}
FINDING_CLASS = {
    "PROTOCOL_VIOLATION", "PROJECT_VIOLATION", "LOGIC_ERROR",
    "ACCIDENTAL_SUCCESS", "USERPERSON_MISS", "VAGUE", "OTHER",
}
CONFIDENCE = {"observed", "reproduced", "proven", "suspected"}
ACTION = {"fix", "ticket", "note", "reject"}
REPORT_STATUS = {"draft", "complete"}
AVAILABILITY = {"expected", "unavailable"}
DISPOSITION = {
    "CONFIRMED", "DUPLICATE", "ALREADY_FIXED", "SUPERSEDED", "LATER_RULE",
    "NOT_REPRODUCED", "INVALID", "NEEDS_EXTERNAL_EVIDENCE",
}

_MISSING = object()


def seat_key(seat_id: str, agent: str = "") -> str:
    """One concrete audit seat, never a model family.

    seat_id alone is the identity; `agent` is recorded but two sessions that
    share a seat_id ARE the same seat by registration. Two OpenCode sessions
    MUST register distinct seat_ids (e.g. opencode-01, opencode-02) to be
    distinct.
    """
    return seat_id.strip()


def cycle_id(project_key: str, now: str) -> str:
    """Deterministic unique cycle id: imp-<key>-<date>-<nn>.

    The nn counter is resolved by the caller against the cycle directory's
    existing entries (read to end-of-file), so two simultaneous attempts
    cannot silently mint the same id; the second admission refuses with the
    existing cycle named.
    """
    safe = re.sub(r"[^A-Za-z0-9_-]", "-", project_key).lower()
    return f"imp-{safe}-{now}"


def resolve_report_path(project_root: Path, cycle_id: str, seat_id: str,
                        project_name: str) -> Path:
    """Canonical report path for a Core seat.

    <project_root>/.saipen/improve/<cycle_id>/<seat_id>/
        saipen_improve_<PROJECTNAME>.md

    The exact requested basename is preserved. Never under saipen_home.
    """
    seat = re.sub(r"[^A-Za-z0-9_.-]", "-", seat_id)
    cycle = re.sub(r"[^A-Za-z0-9_.-]", "-", cycle_id)
    name = re.sub(r"[^A-Za-z0-9_.-]", "-", project_name)
    return (Path(project_root) / ".saipen" / "improve" / cycle / seat
            / f"saipen_improve_{name}.md")


def cycle_dir(project_root: Path, cycle_id: str) -> Path:
    return Path(project_root) / ".saipen" / "improve" / cycle_id


def _read_maybe(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8-sig")


def validate_report(text: str) -> list[str]:
    """Return every report violation; empty means valid.

    Headers must be present; report_status is draft|complete; every finding
    (IMP-### line) must carry severity/class/confidence/action brackets and an
    expected/actual/evidence triple; context_available: complete requires a
    full context_scope.
    """
    errors = []
    lines = text.splitlines()
    header = {}
    findings: list[dict] = []
    current: dict | None = None
    for index, line in enumerate(lines, 1):
        match = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if match:
            key, value = match.group(1), match.group(2).strip()
            if key in REQUIRED_HEADER:
                header[key] = value
            if key == "report_status" and value not in REPORT_STATUS:
                errors.append(f"line {index}: report_status {value!r} outside "
                              f"draft|complete")
            if key == "context_available" and value not in {
                    "complete", "partial", "none"}:
                errors.append(f"line {index}: context_available {value!r} "
                              f"outside complete|partial|none")
        if re.match(r"^IMP-\d+", line):
            if current is not None:
                findings.append(current)
            current = {"start": index,
                       "brackets": re.findall(r"\[([^\]]+)\]", line)}
        if current is not None:
            for field in ("expected", "actual", "evidence"):
                if re.match(rf"^{field}:\s*\S", line):
                    current[field] = line.split(":", 1)[1].strip()
    if current is not None:
        findings.append(current)

    missing = sorted(REQUIRED_HEADER - set(header))
    if missing:
        errors.append("report header missing required fields: "
                      + ", ".join(sorted(missing)))

    if header.get("context_available") == "complete" and not header.get(
            "context_scope"):
        errors.append("context_available: complete refused over an empty "
                      "context_scope")

    for finding in findings:
        for field in ("expected", "actual", "evidence"):
            if field not in finding:
                errors.append(f"finding at line {finding['start']} lacks "
                              f"required {field} -- a finding without an "
                              f"observable expected/actual/evidence triple is "
                              f"rejected, not softened")
        brackets = finding["brackets"]
        if len(brackets) < 4:
            errors.append(f"finding at line {finding['start']} lacks the four "
                          f"bracketed fields severity/class/confidence/action")
            continue
        severity, cls, confidence, action = brackets[:4]
        if severity not in SEVERITY:
            errors.append(f"finding at line {finding['start']}: severity "
                          f"{severity!r} outside the closed set")
        if cls not in FINDING_CLASS:
            errors.append(f"finding at line {finding['start']}: class "
                          f"{cls!r} outside the closed set")
        if confidence not in CONFIDENCE:
            errors.append(f"finding at line {finding['start']}: confidence "
                          f"{confidence!r} outside the closed set")
        if action not in ACTION:
            errors.append(f"finding at line {finding['start']}: action "
                          f"{action!r} outside the closed set")
    return errors


def _field(text: str, key: str) -> str:
    match = re.search(rf"(?m)^{key}:\s*(.+)$", text)
    return match.group(1).strip() if match else ""


def report_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def derive_status(report_ident: str, roster_text: str, report_text: str,
                  sweep_text: str) -> dict:
    """The visible status, DERIVED from roster + report + sweep.

    One fact, one owner: the roster records availability, the report owns
    report_status, the sweep ledger owns dispositions. A report is `swept`
    when the sweep ledger carries final disposition coverage for it -- judged
    by the report's stable identifier appearing in the ledger, never by the
    literal word.
    """
    availability = _field(roster_text, "availability") or "expected"
    status = _field(report_text, "report_status")
    swept = report_ident in sweep_text
    if availability == "unavailable":
        visible = "unavailable"
    elif not report_text:
        visible = "expected"
    elif status == "draft":
        visible = "draft"
    elif swept:
        visible = "swept"
    else:
        visible = "complete"
    return {"availability": availability, "report_status": status,
            "visible": visible, "swept": swept}


def write_sweep_entry(cycle_dir: Path, entry: dict) -> None:
    """Append a disposition to the Core-owned SWEEP ledger (atomic write).

    The seat report is never touched by sweep.
    """
    ledger = cycle_dir / "SWEEP.md"
    text = _read_maybe(ledger)
    if text and not text.startswith("# SWEEP"):
        text = "# SWEEP\n\n" + text
    line = ("- IMP-{imp_id} [{disposition}] {ticket} report={report} "
            "reproduced={reproduced}".format(
                imp_id=entry["imp_id"],
                disposition=entry["disposition"],
                ticket=entry.get("ticket", "-"),
                report=entry.get("report", "-"),
                reproduced=entry.get("reproduced", "-")))
    # Atomic write: sibling temp + rename.
    ledger.parent.mkdir(parents=True, exist_ok=True)
    tmp = ledger.with_suffix(".md.tmp")
    tmp.write_text(text + line + "\n", encoding="utf-8", newline="\n")
    tmp.replace(ledger)
