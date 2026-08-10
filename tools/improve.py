#!/usr/bin/env python
"""SAIPEN Improve mechanical core (T-551, T-554..T-560, NITRO M6 integrity).

The semantics live in saipen/IMPROVE.md; this module is the mechanical layer
that validates and writes the already-decided representation. It owns:

- deterministic, collision-safe cycle and seat admission;
- PATH-SAFE cycle/seat/report identity (no .., no separators, no absolute
  path, no newline/control injection, canonicalized and proven inside the
  owner root before any filesystem use);
- canonical report path resolution (never under the shared protocol install);
- report and finding schema validation (closed vocabularies);
- the Core-owned SWEEP ledger (dispositions, never written into reports);
- the derived visible status per SEAT, computed from roster + report + sweep.

Every mutation goes through the common lock + journal + roll-forward
machinery (NITRO M6) and PROPAGATES the transaction result: a public Improve
mutation never announces success unless the commit actually COMMITTED.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
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

_RUN_RE = re.compile(r"^## RUN (\d+)", re.MULTILINE)
_NO_FINDINGS_RE = re.compile(r"^NO_FINDINGS\b", re.MULTILINE)
# ONE finding reference grammar (DOGFOOD V, T-615): a composite finding is
# RUN-<N>/IMP-<NNN>; a legacy (pre-boundary) record is a bare IMP-<NNN>. The
# parser and the writer share exactly this pattern.

# The SWEEP ledger grammar, exactly as the consumers read it (DOGFOOD V,
# T-615): the finding_ref token carries RUN-N/IMP-NNN (strict schema) or a
# bare IMP-NNN (legacy cycles), and the `report=` identity on the same line
# completes the composite identity (cycle + seat/report + run + IMP id).
_SWEEP_LINE_RE = re.compile(
    r"^- (IMP-\d+|RUN-\d+/IMP-\d+)\s+\[([A-Z_]+)\]\s+(\S+)\s+"
    r"report=([^\s]+)\s+reproduced=(\S+)"
    r"(?:\s+fixed_by=(\S+))?(?:\s+verification=(\S+))?\s*$")

_IMP_DIR = ".saipen/improve"


@dataclass(frozen=True)
class Finding:
    """One parsed finding with its exact composite run identity.

    `run` is an int for an explicit `## RUN N` section, or None for a legacy
    (pre-boundary) report with no RUN sections. Two findings with the same
    IMP number in different RUNs are DIFFERENT findings.
    """
    run: int | None
    imp: str
    start: int
    severity: str
    cls: str
    confidence: str
    action: str
    expected: str
    actual: str
    evidence: str

    def ref(self) -> str:
        """Local finding reference: RUN-N/IMP-NNN, or bare IMP-NNN for legacy."""
        if self.run is None:
            return self.imp
        return f"RUN-{self.run}/{self.imp}"


@dataclass(frozen=True)
class ReportRuns:
    """The structural parse of a seat report: header + explicit RUN sections."""
    header: dict[str, str]
    findings: list[Finding]
    has_runs: bool
    runs: tuple[int, ...]
    no_findings_runs: frozenset[int]
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SweepRecord:
    """ONE structured sweep record shared by writer, parser, validator and
    status (DOGFOOD V, T-615). Never reconstructed from unrelated regexes."""
    finding_ref: str
    disposition: str
    ticket: str
    report: str
    reproduced: str
    fixed_by: str = "-"
    verification: str = "-"

    @property
    def legacy(self) -> bool:
        return "/" not in self.finding_ref

    def run(self) -> int | None:
        m = re.match(r"^RUN-(\d+)/", self.finding_ref)
        return int(m.group(1)) if m else None

    def imp(self) -> str:
        return self.finding_ref.split("/")[-1]

    def render(self) -> str:
        line = (f"- {self.finding_ref} [{self.disposition}] {self.ticket} "
                f"report={self.report} reproduced={self.reproduced}")
        if self.fixed_by and self.fixed_by != "-":
            line += f" fixed_by={self.fixed_by}"
        if self.verification and self.verification != "-":
            line += f" verification={self.verification}"
        return line


class ImproveError(ValueError):
    """A rejected Improve mutation; carries the refusal reason."""


def _validate_safe_id(value: str, kind: str) -> str:
    """Reject any identity that could escape the owner root or inject a
    field/newline. ONE shared primitive owns this: saipen_engine.safeid.
    (NITRO dogfood II -- no third sanitizer.)"""
    from saipen_engine.safeid import validate_safe_id as _shared
    try:
        return _shared(value or "", kind=kind)
    except ValueError as exc:
        raise ImproveError(str(exc)) from exc


def _validate_report_path(value: str, seat_id: str) -> str:
    """A report path must be a bare safe file name under the seat owner root."""
    return _validate_safe_id(value or "", "report_path")


def seat_key(seat_id: str, agent: str = "") -> str:
    """One concrete audit seat, never a model family."""
    return seat_id.strip()


def cycle_id(project_key: str, now: str) -> str:
    """Deterministic unique cycle id: imp-<key>-<date>-<nn>.

    Kept for compatibility with the existing signature; new code MUST use
    allocate_cycle_id() which implements the actual deterministic allocator
    (NITRO dogfood II): the NN counter is derived from the existing cycles on
    disk, never smuggled in by the caller.
    """
    safe = re.sub(r"[^A-Za-z0-9_-]", "-", project_key).lower()
    return f"imp-{safe}-{now}"


def allocate_cycle_id(project_root: Path, project_key: str,
                      now: str | None = None) -> str:
    """The real deterministic cycle-id allocator.

    Returns imp-<safe-project>-<YYYYMMDD>-<NN> where NN is one past the
    highest existing cycle number for this project prefix. Collision-safe by
    construction: two calls on the same tree yield different NN because the
    first committed MANIFEST is visible to the second scan. (NITRO dogfood II
    fixes the old contract that delegated uniqueness to the caller's `now`.)"""
    import datetime
    safe = re.sub(r"[^A-Za-z0-9_-]", "-", project_key).lower()
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
    prefix = f"imp-{safe}-{now}"
    owner = (Path(project_root) / _IMP_DIR)
    highest = 0
    if owner.is_dir():
        for entry in owner.iterdir():
            if not entry.is_dir():
                continue
            match = re.match(re.escape(prefix) + r"-(\d+)$", entry.name)
            if match:
                highest = max(highest, int(match.group(1)))
    return f"{prefix}-{highest + 1}"


def resolve_report_path(project_root: Path, cycle_id: str, seat_id: str,
                        project_name: str) -> Path:
    """Canonical report path for a Core seat, proven inside the owner root."""
    seat = _validate_safe_id(seat_id, "seat_id")
    cycle = _validate_safe_id(cycle_id, "cycle_id")
    name = _validate_safe_id(project_name, "project_name")
    path = Path(project_root) / _IMP_DIR / cycle / seat \
        / f"saipen_improve_{name}.md"
    _prove_inside(project_root, path)
    return path


def cycle_dir(project_root: Path, cycle_id: str) -> Path:
    cycle = _validate_safe_id(cycle_id, "cycle_id")
    root = Path(project_root)
    path = root / _IMP_DIR / cycle
    _prove_inside(root, path)
    return path


def _owner_root(project_root: Path) -> Path:
    return (project_root / _IMP_DIR).resolve()


def _prove_inside(project_root: Path, path: Path) -> None:
    """Canonicalize the owned path and prove it stays under the owner root.
    ONE shared primitive (saipen_engine.safeid.prove_inside) owns containment
    proof -- realpath + normcase, an escape raises rather than writes
    (NITRO dogfood II)."""
    from saipen_engine.safeid import prove_inside as _shared
    try:
        _shared(path, _owner_root(project_root), kind="Improve path")
    except ValueError as exc:
        raise ImproveError(str(exc)) from exc


def _read_maybe(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8-sig")


def _base_hash(path: Path) -> str:
    """The content-base hash a caller derived its plan from.

    Passed to _journaled_write so APPLY refuses STALE_STATE when the live
    file no longer matches the base the caller read -- stale content can
    never overwrite an intervening update (NITRO dogfood II)."""
    from saipen_engine.journal import hash_bytes
    try:
        return hash_bytes(path.read_bytes())
    except OSError:
        return ""


def _field(text: str, key: str) -> str:
    match = re.search(rf"(?m)^{key}:[ \t]*(.+)$", text)
    return match.group(1).strip() if match else ""


def _seat_block(text: str, seat_id: str) -> str | None:
    """Extract exactly ONE seat's roster block, structurally.

    Each seat's registration is a `seat_id: X` line followed by its
    role/report_path/availability lines until the next `seat_id:` line. The
    block is located by exact seat identity, never by the first field in the
    whole manifest.
    """
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if re.match(rf"^seat_id:\s*{re.escape(seat_id)}\s*$", line):
            start = index
            break
    if start is None:
        return None
    block = [lines[start]]
    for line in lines[start + 1:]:
        if re.match(r"^seat_id:\s*", line):
            break
        block.append(line)
    return "\n".join(block)


def _block_for_report(roster_text: str, report_ident: str) -> str | None:
    """Locate the roster block whose report_path names `report_ident`.

    A seat is found by its registered report path -- never by deriving the
    seat from the report file name, which would break multi-seat rosters.
    """
    for block in _seat_blocks(roster_text):
        if _field(block, "report_path") == report_ident:
            return block
    return None


def _seat_blocks(text: str) -> list[str]:
    lines = text.splitlines()
    blocks: list[str] = []
    current: list[str] = []
    for line in lines:
        if re.match(r"^seat_id:\s*", line):
            if current:
                blocks.append("\n".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def report_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def composite_finding_ref(cycle_id: str, seat_id: str, report_ident: str,
                          run: int | None, imp: str) -> str:
    """The ONE canonical composite finding reference (DOGFOOD V, T-615):
    <cycle_id>/<seat_id>/<report_ident>#<RUN-N|legacy>/<IMP-NNN>.

    Used identically by the report parser, SWEEP writer/parser, derive_status,
    complete_cycle, the validator and BOARD source_reports resolution. No
    subsystem ever resolves provenance by a bare IMP-### substring."""
    local = f"RUN-{run}/{imp}" if run is not None else imp
    return f"{cycle_id}/{seat_id}/{report_ident}#{local}"


def _parse_finding_ref(ref: str) -> tuple[int | None, str]:
    """Split a finding reference into (run, IMP). Legacy refs yield None run."""
    if "/" in ref:
        m = re.fullmatch(r"RUN-(\d+)/IMP-(\d+)", ref)
        if not m:
            raise ImproveError(f"malformed finding reference {ref!r}: "
                               "expected RUN-N/IMP-NNN or IMP-NNN")
        return int(m.group(1)), f"IMP-{m.group(2)}"
    m = re.fullmatch(r"IMP-(\d+)", ref)
    if not m:
        raise ImproveError(f"malformed finding reference {ref!r}: "
                           "expected RUN-N/IMP-NNN or IMP-NNN")
    return None, f"IMP-{m.group(1)}"


def _finding_brackets(line: str) -> list[str]:
    return re.findall(r"\[([^\]]+)\]", line)


def parse_report(text: str) -> ReportRuns:
    """Structure a report into header + run-scoped findings (DOGFOOD V).

    A `## RUN N` section scopes its findings to that run. A report with no
    RUN sections is legacy: its findings are run-less and may only be swept by
    legacy sweep records. Every finding therefore carries its exact composite
    identity; no IMP-### floats unanchored.
    """
    header: dict[str, str] = {}
    for match in re.finditer(r"(?m)^([A-Za-z_]+):[ \t]*(.*)$", text):
        header[match.group(1)] = match.group(2).strip()

    run_headers = list(re.finditer(_RUN_RE, text))
    has_runs = bool(run_headers)
    runs = tuple(int(m.group(1)) for m in run_headers)
    findings: list[Finding] = []
    no_findings_runs: set[int] = set()

    # Line offsets computed ONCE: text.find(line) returns the FIRST occurrence,
    # which misattributed RUN 2's findings to RUN 1 when both runs carry the
    # same IMP line (DOGFOOD V, T-615 -- reproduced and fixed here).
    _line_offsets: list[tuple[int, int, str]] = []
    _pos = 0
    for _raw in text.splitlines(keepends=True):
        _line_offsets.append((_pos, _pos + len(_raw), _raw))
        _pos += len(_raw)
    _line_offsets.append((_pos, _pos, ""))

    def _scan(segment_start: int, segment_end: int, run: int | None) -> None:
        segment = text[segment_start:segment_end]
        if run is not None and _NO_FINDINGS_RE.search(segment):
            no_findings_runs.add(run)
        current: dict | None = None
        for index, (_start, _end, line) in enumerate(_line_offsets[:-1], 1):
            if not (segment_start <= _start < segment_end):
                continue
            fm = re.match(r"^IMP-(\d+)", line)
            if fm:
                if current is not None:
                    findings.append(_finalize(current))
                current = {"start": index, "run": run,
                           "imp": f"IMP-{fm.group(1)}",
                           "brackets": _finding_brackets(line)}
                continue
            if current is not None:
                for fname in ("expected", "actual", "evidence"):
                    if re.match(rf"^[ \t]*{fname}:[ \t]*\S", line):
                        current[fname] = line.split(":", 1)[1].strip()
        if current is not None:
            findings.append(_finalize(current))

    def _finalize(raw: dict) -> Finding:
        brackets = raw.get("brackets", [])
        return Finding(
            run=raw.get("run"),
            imp=raw["imp"],
            start=raw["start"],
            severity=brackets[0] if len(brackets) > 0 else "",
            cls=brackets[1] if len(brackets) > 1 else "",
            confidence=brackets[2] if len(brackets) > 2 else "",
            action=brackets[3] if len(brackets) > 3 else "",
            expected=raw.get("expected", ""),
            actual=raw.get("actual", ""),
            evidence=raw.get("evidence", ""))

    if not has_runs:
        _scan(0, len(text), None)
    else:
        bounds = [m.start() for m in run_headers]
        for idx, start in enumerate(bounds):
            end = bounds[idx + 1] if idx + 1 < len(bounds) else len(text)
            run_number = int(run_headers[idx].group(1))
            _scan(start, end, run_number)
    return ReportRuns(header=header, findings=findings, has_runs=has_runs,
                      runs=runs, no_findings_runs=frozenset(no_findings_runs))


def _sweep_records(sweep_text: str) -> list[SweepRecord]:
    """Parse every sweep record in the ledger with the ONE structured parser."""
    records = []
    for line in sweep_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = _SWEEP_LINE_RE.match(stripped)
        if not m:
            continue
        finding_ref, disp, ticket, report, reproduced = m.group(1, 2, 3, 4, 5)
        records.append(SweepRecord(
            finding_ref=finding_ref, disposition=disp, ticket=ticket,
            report=report, reproduced=reproduced,
            fixed_by=m.group(6) or "-", verification=m.group(7) or "-"))
    return records


def _disposed_ids(sweep_text: str, report_ident: str | None = None
                  ) -> list[str]:
    """Every IMP-### with a disposition in the Core sweep ledger, optionally
    filtered to one report identity.

    FINDING IDENTITY IS COMPOSITE (NITRO dogfood II + DOGFOOD V, T-615): an
    IMP-### is not globally unique across seats OR runs. Coverage for report X
    counts ONLY records whose report identity equals X, and each record's run
    stays bound to its finding_ref -- one RUN's IMP-001 never satisfies
    another RUN's IMP-001."""
    disposed = []
    for record in _sweep_records(sweep_text):
        if report_ident is not None and record.report != report_ident:
            continue
        disposed.append(record.imp())
    return disposed


def derive_status(report_ident: str, roster_text: str, report_text: str,
                  sweep_text: str) -> dict:
    """The visible status, DERIVED per seat.

    - roster entry for THIS seat (exact seat_id block) owns availability;
    - the report owns report_status;
    - the sweep ledger owns dispositions, matched by EXACT composite identity.

    `swept` means EVERY finding requiring disposition has a final Core
    disposition FOR THIS REPORT AND THIS RUN -- a disposition against a
    different report's or different RUN's IMP-### is not coverage, and a bare
    appearance of the report identifier is not coverage either (DOGFOOD V,
    T-615: RUN-1/IMP-001 never satisfies RUN-2/IMP-001)."""
    seat = re.sub(r"^saipen_improve_", "", Path(report_ident).stem)
    availability = "expected"
    block = _block_for_report(roster_text, report_ident)
    if block is not None:
        availability = _field(block, "availability") or "expected"
    status = _field(report_text, "report_status")
    parsed = parse_report(report_text)
    expected = {(f.run, f.imp) for f in parsed.findings}
    disposed = {(r.run(), r.imp()) for r in _sweep_records(sweep_text)
                if r.report == report_ident}
    missing = sorted(f"{'' if f.run is None else f'RUN-{f.run}/'}{f.imp}"
                     for f in parsed.findings
                     if (f.run, f.imp) not in disposed)
    fully_swept = bool(expected) and not missing
    if availability == "unavailable":
        visible = "unavailable"
    elif not report_text:
        visible = "expected"
    elif status == "draft":
        visible = "draft"
    elif fully_swept:
        visible = "swept"
    else:
        visible = "complete"
    return {"availability": availability, "report_status": status,
            "visible": visible, "swept": fully_swept,
            "disposed": sorted({f"RUN-{r}/{i}" if r is not None else i
                                for r, i in disposed}),
            "missing": missing}


def _project_root_of(path: Path) -> Path:
    """The project root owning a path under .saipen/ (walk up to .saipen)."""
    cursor = path
    while cursor.parent != cursor.parent.parent and cursor.name != ".saipen":
        cursor = cursor.parent
    if cursor.name == ".saipen":
        return cursor.parent
    raise ImproveError(f"cannot resolve a project root for {path}")


def _freshness_errors(project_root: Path, report_text: str,
                      strict: bool, cycle_active: bool) -> list[str]:
    """Source-evidence freshness for a report (DOGFOOD V, T-619).

    A strict cycle's report is only fresh when its mechanically captured
    source_head + tree fingerprint match the CURRENT source identity. Same
    HEAD plus a changed/dirty tree is stale. Stale evidence can never
    authorize fresh canonical work without current reproduction."""
    errors: list[str] = []
    if not strict or not cycle_active:
        return errors
    head = _field(report_text, "source_head")
    tree = _field(report_text, "source_tree_fingerprint")
    if not head or not tree:
        errors.append("report carries no mechanically captured source "
                      "identity (source_head/source_tree_fingerprint)")
        return errors
    if not re.match(r"^(git-delta-v1|no-git-tree-v1):", tree):
        errors.append(f"source_tree_fingerprint {tree!r} is not a mechanical "
                      "fingerprint; a fabricated label cannot authorize fresh "
                      "work")
        return errors
    try:
        from freshness import FreshnessError, compute_source_identity
        current = compute_source_identity(project_root)
    except FreshnessError as exc:
        errors.append(f"cannot compute the current source identity: {exc}")
        return errors
    if current.source_head not in (head, head[:7]):
        errors.append(f"source_head {head[:12]}... != current HEAD "
                      f"{current.source_head[:12]}...; the audit did not "
                      "reload the current tree")
    elif current.source_tree_fingerprint != tree:
        errors.append(f"source_tree_fingerprint {tree[:24]}... != current "
                      f"tree {current.source_tree_fingerprint[:24]}... at the "
                      "same HEAD; the audited tree differs from the live one")
    return errors


def _report_fresh(project_root: Path, cycle_dir: Path, report_ident: str,
                  report_text: str, strict: bool) -> list[str]:
    """Freshness errors for the report owning `report_ident` in this cycle."""
    if not strict:
        return []
    manifest = cycle_dir / "MANIFEST.md"
    active = _cycle_status(manifest) == "active"
    return _freshness_errors(project_root, report_text, strict, active)


def _ticket_exists(project_root: Path, ticket: str) -> bool:
    """Does the canonical ticket exist on the board or in any LOG segment?"""
    if not re.fullmatch(r"T-\d+", ticket):
        return False
    root = Path(project_root)
    board = root / ".saipen" / "BOARD.md"
    if board.is_file() and ticket in board.read_text(encoding="utf-8-sig"):
        return True
    logs = root / ".saipen" / "logs"
    log = root / ".saipen" / "LOG.md"
    paths: list[Path] = []
    if log.is_file():
        paths.append(log)
    if logs.is_dir():
        paths.extend(sorted(logs.glob("LOG-*.md")))
    for path in paths:
        if path.is_file() and ticket in path.read_text(
                encoding="utf-8-sig"):
            return True
    return False


def _cycle_schema(manifest: Path) -> str:
    """The manifest schema: 'strict' when the manifest declares it, else
    'legacy' (the pre-boundary form the three historical cycles use)."""
    text = _read_maybe(manifest)
    if re.search(r"(?m)^manifest_schema:\s*strict\s*$", text):
        return "strict"
    return "legacy"


def _report_roster_block(cycle_dir: Path, report_ident: str) -> str | None:
    """The roster block owning `report_ident`, or None when no seat owns it."""
    manifest = cycle_dir / "MANIFEST.md"
    if not manifest.is_file():
        return None
    return _block_for_report(_read_maybe(manifest), report_ident)


def _require_finding(cycle_dir: Path, report_ident: str, run: int | None,
                     imp: str, strict: bool) -> None:
    """A Core sweep mutation must name a finding that ACTUALLY exists in the
    named run of the named report (DOGFOOD V, T-615). A nonexistent
    finding/run/report is a refusal, not a ledger append."""
    seat_dir = None
    for block in _seat_blocks(_read_maybe(cycle_dir / "MANIFEST.md")):
        if _field(block, "report_path") == report_ident:
            seat_dir = _field(block, "seat_id")
            break
    if seat_dir is None:
        raise ImproveError(
            f"write_sweep_entry refuses: report {report_ident!r} is not a "
            "registered seat report in this cycle")
    report = cycle_dir / seat_dir / report_ident
    if not report.is_file():
        raise ImproveError(
            f"write_sweep_entry refuses: report {report_ident!r} does not "
            "exist on disk")
    text = _read_maybe(report)
    if _field(text, "report_status") != "complete":
        raise ImproveError(
            f"write_sweep_entry refuses: report {report_ident!r} is not "
            "complete; only a complete report's findings may be disposed")
    parsed = parse_report(text)
    if strict:
        if not parsed.has_runs:
            raise ImproveError(
                f"write_sweep_entry refuses: report {report_ident!r} in a "
                "strict cycle carries no explicit ## RUN sections; a sweep "
                "must name the exact RUN")
        if run is None:
            raise ImproveError(
                "write_sweep_entry refuses: a strict cycle sweep must name "
                "the exact RUN (RUN-N/IMP-NNN)")
    matching = [f for f in parsed.findings if f.imp == imp
                and (run is None or f.run == run)]
    if not matching:
        target = f"RUN-{run}/{imp}" if run is not None else imp
        raise ImproveError(
            f"write_sweep_entry refuses: finding {target} does not exist in "
            f"report {report_ident!r}")


def write_sweep_entry(cycle_dir: Path, entry: dict) -> dict:
    """Append a disposition to the Core-owned SWEEP ledger (journaled write).

    A Core sweep mutation validates BEFORE write (DOGFOOD V, T-615): the
    named cycle is active, the named seat/report exists, the report is
    complete, the named run exists, the named IMP exists in that exact run,
    the disposition and reproduced values are legal, the disposition/ticket
    relation is legal, and a CONFIRMED disposition names a canonical ticket
    that actually exists. Fictional findings can never COMMIT.

    Returns the transaction result; the caller MUST inspect it. An invalid
    disposition writes zero bytes.
    """
    disposition = entry.get("disposition")
    if disposition not in DISPOSITION:
        raise ImproveError(
            f"disposition {disposition!r} outside the closed set "
            f"{sorted(DISPOSITION)}")
    report_ident = str(entry.get("report", ""))
    if not report_ident or report_ident in ("-", ""):
        raise ImproveError(
            "write_sweep_entry refuses: report identity is required -- a "
            "sweep disposition must name its exact report")
    strict = _cycle_schema(cycle_dir / "MANIFEST.md") == "strict"
    # DOGFOOD V (T-619): a CONFIRMED disposition on STALE evidence cannot
    # authorize fresh canonical work. The report's source identity must match
    # the current tree (same HEAD + dirty tree is stale); a stale report
    # demands current reproduction or a non-CONFIRMED disposition.
    if strict and disposition == "CONFIRMED":
        project_root = _project_root_of(cycle_dir)
        report_text = ""
        seat_dir = None
        for block in _seat_blocks(_read_maybe(cycle_dir / "MANIFEST.md")):
            if _field(block, "report_path") == report_ident:
                seat_dir = _field(block, "seat_id")
                break
        if seat_dir is not None:
            _rep = cycle_dir / seat_dir / report_ident
            if _rep.is_file():
                report_text = _read_maybe(_rep)
        fresh_errors = _freshness_errors(project_root, report_text, strict,
                                         True)
        if fresh_errors:
            raise ImproveError(
                "write_sweep_entry refuses CONFIRMED on stale evidence: "
                + "; ".join(fresh_errors)
                + " -- re-audit against the current tree (a new RUN) or use "
                "a non-CONFIRMED disposition")
    run_raw = entry.get("run")
    imp_raw = str(entry.get("imp_id", ""))
    if re.fullmatch(r"\d+", imp_raw):
        imp_num = imp_raw
    elif re.fullmatch(r"IMP-(\d+)", imp_raw):
        imp_num = re.match(r"IMP-(\d+)", imp_raw).group(1)
    else:
        raise ImproveError(f"imp_id {imp_raw!r} is not IMP-###")
    imp_id = f"IMP-{imp_num}"
    run = None
    if run_raw is not None:
        run_m = re.fullmatch(r"(?:RUN-)?(\d+)", str(run_raw).strip())
        if not run_m:
            raise ImproveError(f"run {run_raw!r} is not RUN-<N>")
        run = int(run_m.group(1))
    elif strict:
        # A strict cycle's sweep must always carry the exact run.
        raise ImproveError(
            "write_sweep_entry refuses: a strict cycle sweep must name the "
            "exact RUN (run='RUN-1')")
    finding_ref = f"RUN-{run}/{imp_id}" if run is not None else imp_id

    ledger = cycle_dir / "SWEEP.md"
    _prove_inside(_project_root_of(ledger), ledger)
    _require_cycle_active(cycle_dir, "write_sweep_entry")
    _require_finding(cycle_dir, report_ident, run, imp_id, strict)

    reproduced = str(entry.get("reproduced", "-"))
    if reproduced not in {"y", "n"}:
        raise ImproveError(
            f"write_sweep_entry refuses: reproduced {reproduced!r} outside "
            "the closed set y|n")
    ticket = str(entry.get("ticket", "-") or "-")
    if disposition == "CONFIRMED":
        if ticket == "-":
            raise ImproveError(
                "write_sweep_entry refuses: a CONFIRMED finding must name a "
                "canonical ticket; the ledger may not claim a ticket that "
                "does not exist")
        if not _ticket_exists(_project_root_of(ledger), ticket):
            raise ImproveError(
                f"write_sweep_entry refuses: CONFIRMED names ticket "
                f"{ticket} which does not exist on the board or in any LOG "
                "segment -- a fictional ticket cannot authorize canonical "
                "work")
    elif disposition in ("INVALID", "ALREADY_FIXED", "NOT_REPRODUCED"):
        if ticket != "-":
            raise ImproveError(
                f"write_sweep_entry refuses: {disposition} may not carry a "
                "ticket")
    elif ticket != "-" and not _ticket_exists(_project_root_of(ledger), ticket):
        raise ImproveError(
            f"write_sweep_entry refuses: ticket {ticket} does not exist on "
            "the board or in any LOG segment")

    text = _read_maybe(ledger)
    if not text.startswith("# SWEEP"):
        text = "# SWEEP\n\n" + text
    if any(r.finding_ref == finding_ref and r.report == report_ident
           for r in _sweep_records(text)):
        raise ImproveError(
            f"write_sweep_entry refuses: a disposition for "
            f"{finding_ref} in {report_ident} already exists in the ledger")

    record = SweepRecord(
        finding_ref=finding_ref, disposition=disposition, ticket=ticket,
        report=report_ident, reproduced=reproduced,
        fixed_by=str(entry.get("fixed_by", "-") or "-"),
        verification=str(entry.get("verification", "-") or "-"))
    result = _journaled_write(ledger, text.rstrip() + "\n" + record.render()
                              + "\n", "sweep", base_hash=_base_hash(ledger))
    if not result.get("ok"):
        raise ImproveError(
            f"sweep entry for {finding_ref} not committed: "
            f"{result.get('code')} {result.get('message', '')}")
    return result


def _journaled_write(path: Path, content: str, kind: str,
                     base_hash: str | None = None) -> dict:
    """Write one file through the common lock + journal + roll-forward
    machinery. Returns the transaction result; callers inspect and propagate.

    The target is a single ATOMIC_FILE transaction: one target, its own
    before/after hashes, staged exact bytes, post-write byte verification.

    CONTENT-BASE BINDING (NITRO dogfood II): the caller derived `content` from
    a specific base read of the file. That base's hash MUST be passed as
    `base_hash`; APPLY refuses STALE_STATE if the live file no longer matches
    it. No helper may silently refresh the before hash while preserving stale
    content -- a stale caller plan must never overwrite an intervening update.

    The journal carries the improve_atomic_file verification policy so
    recovery reruns the Improve semantic postcondition, not a silent None
    (NITRO dogfood III, T-594).
    """
    import uuid
    from saipen_engine import codec
    from saipen_engine.journal import _hash_file, hash_bytes, run_mutation
    from saipen_engine.lock import project_writer_lock

    root = path
    while root.parent != root.parent.parent and root.name != ".saipen":
        root = root.parent
    root = root.parent  # project root (parent of .saipen)
    rel = path.relative_to(root).as_posix()
    op_id = f"{kind}-" + uuid.uuid4().hex[:8]
    doc = codec.read_document(path)
    content_bytes = doc.encode(content)
    live = _hash_file(path) if path.is_file() else ""
    before = base_hash if base_hash is not None else live
    # TARGET ROLE (NITRO dogfood IV, T-601): the journal target must name the
    # DOMAIN the file belongs to (manifest/sweep/report), not a generic role,
    # so the target-aware semantic verifier validates the ACTUAL changed file
    # with the correct grammar -- a malformed SWEEP can never hide behind a
    # manifest-only scan, and APPLY + Recovery use one verifier.
    role = {"cycle": "manifest", "seat": "manifest", "sweep": "sweep",
            "run": "report"}.get(kind, "generic")
    with project_writer_lock(root):
        return run_mutation(
            root, op_id, kind, "saipen", _identity(root),
            hash_bytes(rel.encode("utf-8")),
            [{"path": rel, "role": role, "content": content_bytes,
              "before_hash": before,
              "after_hash": hash_bytes(content_bytes)}],
            preconditions={rel: before},
            verification_policy="improve_atomic_file")


def _identity(root: Path) -> str:
    from saipen_engine.paths import project_identity
    return project_identity(root)


def _cycle_status(manifest: Path) -> str:
    """The lifecycle status of a cycle manifest, defaulting to active for
    legacy manifests that predate the explicit lifecycle field."""
    text = _read_maybe(manifest)
    match = re.search(r"(?m)^cycle_status:\s*([A-Za-z]+)", text)
    return match.group(1) if match else "active"


def _require_cycle_active(cycle_dir: Path, mutator: str) -> Path:
    """Refuse any mutator on a cycle that is not ACTIVE (NITRO dogfood III,
    T-595). A completed/archived cycle is immutable under all normal writers."""
    manifest = cycle_dir / "MANIFEST.md"
    _prove_inside(_project_root_of(manifest), manifest)
    status = _cycle_status(manifest)
    if status != "active":
        raise ImproveError(
            f"{mutator} refuses: cycle {cycle_dir.name} is {status}, not "
            "active; a completed cycle is immutable except permitted archive "
            "metadata")
    return manifest


def portable_project_key(project_root: Path) -> str:
    """A deterministic PORTABLE project identity (DOGFOOD V, T-618).

    `paths.project_identity()` is an absolute machine-local path and must
    never be persisted inside portable Improve evidence. This key is derived
    from the Git remote origin when present (owner/repo, machine-independent),
    else from the project directory name -- either way a slug safe for
    cycle_id derivation, with no drive letter or local mount leak."""
    import subprocess
    root = Path(project_root)
    remote = ""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
        if result.returncode == 0:
            remote = result.stdout.decode("utf-8", "replace").strip()
    except (OSError, subprocess.SubprocessError):
        remote = ""
    if remote:
        base = remote.rstrip("/")
        if base.endswith(".git"):
            base = base[:-4]
        parts = [p for p in base.split("/") if p]
        tail = "/".join(parts[-2:]) if len(parts) >= 2 else base
    else:
        tail = root.name or "project"
    safe = re.sub(r"[^A-Za-z0-9_.-]", "-", tail)
    return safe.strip("-.").lower() or "project"


def create_cycle(project_root: Path, cycle_id: str, *,
                 created_at: str | None = None,
                 project_identity: str | None = None) -> Path:
    """Create a STRICT-schema cycle directory journaled (DOGFOOD V, T-618).

    Python owns the manifest formatting: no caller supplies preformatted
    roster prose. The strict manifest carries exactly one roster header, one
    manifest_schema: strict, one cycle_id, one UTC created_at, one portable
    project_identity and one lifecycle status -- the fields IMPROVE.md § 3
    requires and the three historical cycles lack. Refuses while another
    ACTIVE cycle exists, exactly like register_cycle."""
    import datetime
    if created_at is None:
        created_at = datetime.datetime.now(
            datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if project_identity is None:
        project_identity = portable_project_key(project_root)
    root = Path(project_root)
    cdir = cycle_dir(root, cycle_id)
    _prove_inside(root, cdir)
    owner = _owner_root(root)
    if owner.is_dir():
        for manifest in owner.glob("*/MANIFEST.md"):
            if _cycle_status(manifest) == "active":
                raise ImproveError(
                    f"improve cycle {manifest.parent.name} is ACTIVE -- a "
                    f"project has at most one active Improve cycle; complete "
                    "it first to admit the next")
    if (cdir / "MANIFEST.md").exists():
        raise ImproveError(
            f"improve cycle {cycle_id} already exists -- a project has at "
            f"most one active Improve cycle")
    content = ("# IMPROVE CYCLE ROSTER\n\n"
               "manifest_schema: strict\n"
               f"cycle_id: {cycle_id}\n"
               f"created_at: {created_at}\n"
               f"project_identity: {project_identity}\n"
               "cycle_status: active\n")
    result = _journaled_write(cdir / "MANIFEST.md", content, "cycle")
    if not result.get("ok"):
        raise ImproveError(
            f"cycle {cycle_id} not committed: {result.get('code')} "
            f"{result.get('message', '')}")
    return cdir


def register_cycle(project_root: Path, cycle_id: str,
                   roster_lines: str) -> Path:
    """LEGACY roster-cycle writer, kept for pre-boundary callers and tests.

    Creates a cycle whose manifest carries no `manifest_schema: strict`, so it
    validates under the legacy rules -- exactly the schema the three
    historical archived cycles carry. New cycles MUST use create_cycle() so
    the strict manifest contract (cycle_id/created_at/project_identity once,
    no duplicate header) applies. Refuses while another ACTIVE cycle exists
    (one active Improve cycle per project)."""
    root = Path(project_root)
    cdir = cycle_dir(root, cycle_id)
    _prove_inside(root, cdir)
    owner = _owner_root(root)
    if owner.is_dir():
        for manifest in owner.glob("*/MANIFEST.md"):
            if _cycle_status(manifest) == "active":
                raise ImproveError(
                    f"improve cycle {manifest.parent.name} is ACTIVE -- a "
                    f"project has at most one active Improve cycle; complete "
                    "it first to admit the next")
    if (cdir / "MANIFEST.md").exists():
        raise ImproveError(
            f"improve cycle {cycle_id} already exists -- a project has at "
            f"most one active Improve cycle")
    content = ("# IMPROVE CYCLE ROSTER\n\ncycle_status: active\n\n"
               + roster_lines)
    if re.search(r"(?m)^cycle_status:\s*active\s*$", roster_lines):
        content = ("# IMPROVE CYCLE ROSTER\n\n" + roster_lines)
    result = _journaled_write(cdir / "MANIFEST.md", content, "cycle")
    if not result.get("ok"):
        raise ImproveError(
            f"cycle {cycle_id} not committed: {result.get('code')} "
            f"{result.get('message', '')}")
    return cdir


def verify_cycle(cycle_dir: Path) -> list[str]:
    """Validate the COMPLETE cycle output (DOGFOOD V, T-615/T-616/T-618).

    The shared full-cycle bar used by `saipen improve verify`, complete_cycle
    and the validator: strict manifest schema, every expected seat resolved,
    every report full-valid (RUN evidence for strict cycles), exact composite
    sweep coverage, mechanically valid source identity fields. An artifact
    that merely resembles a writable target can never pass this."""
    errors = []
    manifest = cycle_dir / "MANIFEST.md"
    text = _read_maybe(manifest)
    if not text.strip():
        errors.append(f"cycle manifest missing: {manifest}")
        return errors
    manifest_errors = validate_manifest(text, expected_cycle_id=cycle_dir.name)
    errors.extend(manifest_errors)
    strict = bool(re.search(r"(?m)^manifest_schema:\s*strict\s*$", text))
    sweep_text = _read_maybe(cycle_dir / "SWEEP.md")
    for seat in _seat_blocks(text):
        if _field(seat, "availability") == "unavailable":
            continue
        seat_id = _field(seat, "seat_id") or "?"
        report_path = _field(seat, "report_path")
        if not report_path:
            errors.append(f"seat {seat_id}: missing report_path in roster")
            continue
        report = cycle_dir / seat_id / report_path
        if not report.is_file():
            errors.append(f"seat {seat_id}: expected report {report_path} "
                          "does not exist")
            continue
        report_text = _read_maybe(report)
        if _field(report_text, "report_status") != "complete":
            errors.append(f"seat {seat_id}: report {report_path} is not "
                          "complete")
            continue
        report_errors = validate_report(report_text, require_runs=strict)
        for err in report_errors:
            errors.append(f"seat {seat_id} report: {err}")
        # DOGFOOD V (T-619): verify_cycle validates source freshness for
        # strict active cycles -- a stale report can never PASS a complete
        # cycle, and complete_cycle inherits this bar.
        for err in _report_fresh(_project_root_of(cycle_dir), cycle_dir,
                                 report_path, report_text, strict):
            errors.append(f"seat {seat_id} report: {err}")
        derived = derive_status(report_path, text, report_text, sweep_text)
        for missing_ref in derived.get("missing", []):
            errors.append(f"seat {seat_id}: finding {missing_ref} has no "
                          "final Core disposition for its exact composite "
                          "identity")
    return errors


def abort_cycle(cycle_dir: Path) -> dict:
    """Mechanical abort for a STUCK DRAFT cycle (DOGFOOD V, T-621).

    An active cycle whose report fails the completion bar (a committed RUN
    missing a required field, an interrupted audit) can never complete and can
    never archive -- the only old escape was a raw filesystem delete, the
    exact raw-writer bypass the protocol bans.

    Abort is the sanctioned exit: it refuses once ANY disposition exists (a
    cycle whose sweep started is not abortable), flips the manifest to
    archived with a journaled `cycle_aborted` marker, and byte-preserves the
    never-completed draft reports under a `.discarded` suffix (a DRAFT is not
    yet evidence, so it stops being scanned as one, but no byte is deleted).
    The next cycle can then be admitted without destroying the trace."""
    manifest = cycle_dir / "MANIFEST.md"
    _prove_inside(_project_root_of(manifest), manifest)
    text = _read_maybe(manifest)
    if not text.strip():
        raise ImproveError(f"cycle manifest missing: {manifest}")
    if _cycle_status(manifest) != "active":
        raise ImproveError(
            f"abort refuses: cycle {cycle_dir.name} is {_cycle_status(manifest)}, "
            "not active; only an active stuck cycle may be aborted")
    sweep = _read_maybe(cycle_dir / "SWEEP.md")
    if _sweep_records(sweep):
        raise ImproveError(
            "abort refuses: the sweep ledger already carries dispositions; a "
            "cycle whose Core sweep started is not abortable -- finish or "
            "dispose it properly")
    discarded = []
    for block in _seat_blocks(text):
        seat_id = _field(block, "seat_id")
        report_path = _field(block, "report_path")
        if not seat_id or not report_path:
            continue
        report = cycle_dir / seat_id / report_path
        if not report.is_file():
            continue
        if _field(_read_maybe(report), "report_status") != "complete":
            discarded_name = report.name + ".discarded"
            report.rename(report.with_name(discarded_name))
            discarded.append(f"{seat_id}/{discarded_name}")
    new_text = re.sub(r"(?m)^cycle_status:\s*[A-Za-z]+",
                      "cycle_status: archived", text, count=1)
    new_text = new_text.rstrip() + "\ncycle_aborted: draft-discarded\n"
    result = _journaled_write(manifest, new_text, "cycle",
                              base_hash=_base_hash(manifest))
    if not result.get("ok"):
        raise ImproveError(
            f"cycle {cycle_dir.name} not aborted: {result.get('code')} "
            f"{result.get('message', '')}")
    result["discarded"] = discarded
    return result


def complete_cycle(cycle_dir: Path) -> dict:
    """Mark a cycle COMPLETE: no longer active, so the next cycle can start.
    The cycle's evidence stays in place (never deleted to admit the next
    cycle); only the lifecycle status changes, journaled (NITRO dogfood II).

    "Complete" must mean something (NITRO dogfood III, T-595 + IV, T-601 +
    DOGFOOD V, T-615/T-616): before marking complete, verify_cycle must pass
    -- strict manifest, every expected seat's report present and FULL-valid
    (a report containing only `report_status: complete` refuses), every
    finding carrying a final Core SWEEP disposition for its EXACT composite
    identity. complete_cycle is never a glorified report_status counter."""
    manifest = cycle_dir / "MANIFEST.md"
    _prove_inside(_project_root_of(manifest), manifest)
    text = _read_maybe(manifest)
    if not text.strip():
        raise ImproveError(f"cycle manifest missing: {manifest}")
    if _cycle_status(manifest) == "complete":
        raise ImproveError(f"cycle {cycle_dir.name} is already complete")
    errors = verify_cycle(cycle_dir)
    if errors:
        raise ImproveError(
            "complete_cycle refused -- the cycle bar is unmet:\n- "
            + "\n- ".join(errors[:20]))
    new_text = re.sub(r"(?m)^cycle_status:\s*[A-Za-z]+",
                      "cycle_status: complete", text, count=1)
    if new_text == text:
        new_text = text.rstrip() + "\ncycle_status: complete\n"
    result = _journaled_write(manifest, new_text, "cycle",
                              base_hash=_base_hash(manifest))
    if not result.get("ok"):
        raise ImproveError(
            f"cycle {cycle_dir.name} not completed: {result.get('code')} "
            f"{result.get('message', '')}")
    return result


def create_report(project_root: Path, cycle_id: str, seat_id: str,
                  project_name: str, *, agent: str, role: str,
                  model_or_runtime: str, protocol_fingerprint: str,
                  context_scope: str,
                  context_available: str = "complete") -> Path:
    """Create a DRAFT seat report mechanically and journaled (DOGFOOD V,
    T-616/T-618). No raw report construction by Core/agent after the
    migration boundary.

    The header is rendered by Python. Source identity is captured MECHANICALLY
    via freshness.compute_source_identity() -- source_head + the real tree
    fingerprint + discovery model, never a hand-typed hash or a friendly
    label pretending to be one. `saipen_version` is read from VERSION."""
    from freshness import FreshnessError, compute_source_identity
    root = Path(project_root)
    cdir = cycle_dir(root, cycle_id)
    _prove_inside(root, cdir)
    _require_cycle_active(cdir, "create_report")
    seat = _validate_safe_id(seat_id, "seat_id")
    roster_text = _read_maybe(cdir / "MANIFEST.md")
    if _block_for_report(roster_text, f"saipen_improve_{project_name}.md") \
            is None:
        raise ImproveError(
            f"create_report refuses: seat {seat} has no roster entry owning "
            f"saipen_improve_{project_name}.md -- register the seat first")
    try:
        ident = compute_source_identity(root)
    except FreshnessError as exc:
        raise ImproveError(
            f"create_report refuses: cannot capture mechanical source "
            f"identity: {exc}") from exc
    saipen_version = ""
    for candidate in (root / "VERSION",
                      Path(__file__).resolve().parent.parent / "VERSION"):
        if candidate.is_file():
            saipen_version = candidate.read_text(
                encoding="utf-8").strip().split("\n")[0]
            break
    header = (
        f"agent: {agent}\n"
        f"role: {role}\n"
        f"model_or_runtime: {model_or_runtime}\n"
        f"project: {portable_project_key(root)}\n"
        f"saipen_version: {saipen_version}\n"
        f"protocol_fingerprint: {protocol_fingerprint}\n"
        f"source_head: {ident.source_head}\n"
        f"source_tree_fingerprint: {ident.source_tree_fingerprint}\n"
        f"discovery_model: {ident.discovery_model}\n"
        f"context_scope: {context_scope}\n"
        f"context_available: {context_available}\n"
        "report_status: draft\n")
    report = resolve_report_path(root, cycle_id, seat, project_name)
    if report.is_file():
        raise ImproveError(
            f"create_report refuses: report already exists at {report}")
    report.parent.mkdir(parents=True, exist_ok=True)
    result = _journaled_write(report, header, "report",
                              base_hash=_base_hash(report))
    if not result.get("ok"):
        raise ImproveError(
            f"report for seat {seat} not committed: {result.get('code')} "
            f"{result.get('message', '')}")
    return report


def complete_report(report_path: Path) -> dict:
    """Mark a DRAFT report COMPLETE, journaled and immutable thereafter
    (DOGFOOD V, T-616). The FULL report validation must pass first -- a report
    with only `report_status: complete` and nothing else REFUSES."""
    if not report_path.is_file():
        raise ImproveError(f"complete_report refuses: no report at "
                           f"{report_path}")
    text = _read_maybe(report_path)
    if _field(text, "report_status") == "complete":
        raise ImproveError("complete_report refuses: report is already "
                           "complete and immutable")
    cycle_dir_of_report = report_path.parent.parent
    _require_cycle_active(cycle_dir_of_report, "complete_report")
    strict = _cycle_schema(cycle_dir_of_report / "MANIFEST.md") == "strict"
    # Validate against the completion bar as if the report WERE complete: a
    # draft whose stored status is still draft must not dodge the completion
    # schema, and a report with only report_status: complete refuses.
    completion_text = re.sub(r"(?m)^report_status:[ \t]*[A-Za-z]+",
                             "report_status: complete", text, count=1)
    errors = validate_report(completion_text, require_runs=strict)
    if errors:
        raise ImproveError(
            "complete_report refused -- the completion schema is unmet:\n- "
            + "\n- ".join(errors[:12]))
    new_text = re.sub(r"(?m)^report_status:\s*[A-Za-z]+",
                      "report_status: complete", text, count=1)
    if new_text == text:
        new_text = text.rstrip() + "\nreport_status: complete\n"
    result = _journaled_write(report_path, new_text, "report",
                              base_hash=_base_hash(report_path))
    if not result.get("ok"):
        raise ImproveError(
            f"report not completed: {result.get('code')} "
            f"{result.get('message', '')}")
    return result


def archive_cycle(cycle_dir: Path) -> dict:
    """ARCHIVE a completed cycle: retention state only (T-559, T-606).

    `saipen improve clean` is archive-with-provenance and nothing else. It
    refuses while the cycle is not COMPLETE (an active cycle is still
    mutation-producing; a complete cycle with unswept findings cannot exist
    because complete_cycle requires full sweep coverage). It preserves the
    original findings and the sweep ledger verbatim -- archived evidence keeps
    resolving through the [sweep-ticket-link] check. The mutation is the same
    journaled manifest write complete_cycle uses, changing only the lifecycle
    status to `archived`."""
    manifest = cycle_dir / "MANIFEST.md"
    _prove_inside(_project_root_of(manifest), manifest)
    text = _read_maybe(manifest)
    if not text.strip():
        raise ImproveError(f"cycle manifest missing: {manifest}")
    status = _cycle_status(manifest)
    if status == "archived":
        raise ImproveError(f"cycle {cycle_dir.name} is already archived")
    if status != "complete":
        raise ImproveError(
            f"archive refused: cycle {cycle_dir.name} is {status}, not "
            "complete; only a completed (fully swept) cycle may be archived "
            "-- archive-with-provenance never freezes active or unswept "
            "evidence (T-559)")
    new_text = re.sub(r"(?m)^cycle_status:\s*[A-Za-z]+",
                      "cycle_status: archived", text, count=1)
    if new_text == text:
        new_text = text.rstrip() + "\ncycle_status: archived\n"
    result = _journaled_write(manifest, new_text, "cycle",
                              base_hash=_base_hash(manifest))
    if not result.get("ok"):
        raise ImproveError(
            f"cycle {cycle_dir.name} not archived: {result.get('code')} "
            f"{result.get('message', '')}")
    return result


def register_seat(cycle_dir: Path, seat_id: str, role: str,
                  report_path: str, availability: str = "expected") -> dict:
    """Add a seat to the roster; a duplicate seat_id registration fails.

    seat_id is one concrete audit seat/session, never a model family. Inputs
    are validated BEFORE any planning mutation. The roster owns stable
    routing/identity only.
    """
    seat = _validate_safe_id(seat_id, "seat_id")
    _validate_safe_id(role, "role") if role else None
    _validate_report_path(report_path, seat)
    if availability not in AVAILABILITY:
        raise ImproveError(f"availability {availability!r} outside "
                           f"expected|unavailable")
    manifest = _require_cycle_active(cycle_dir, "register_seat")
    text = _read_maybe(manifest)
    if not text.startswith("# IMPROVE CYCLE ROSTER"):
        text = "# IMPROVE CYCLE ROSTER\n\n" + text
    if _seat_block(text, seat) is not None:
        raise ImproveError(f"duplicate seat registration: {seat}")
    line = (f"seat_id: {seat}\nrole: {role}\nreport_path: {report_path}\n"
            f"availability: {availability}\n")
    result = _journaled_write(manifest, text.rstrip() + "\n" + line, "seat",
                              base_hash=_base_hash(manifest))
    if not result.get("ok"):
        raise ImproveError(
            f"seat {seat} not committed: {result.get('code')} "
            f"{result.get('message', '')}")
    return result


def append_run(report_path: Path, run_text: str) -> dict:
    """Append an immutable RUN section to a seat report (T-551, migrated to
    the journal in NITRO M6; DOGFOOD V, T-616).

    A second run from the same seat in the same cycle APPENDS; an earlier RUN
    is never overwritten. Immutability is PARSER-derived (DOGFOOD V, T-616):
    once the parsed header says `report_status: complete` the report is
    immutable and further RUNs are refused -- a substring search that a
    mention of `report_status: complete` in evidence text could trip is never
    the lifecycle gate. Returns the transaction result.
    """
    text = _read_maybe(report_path)
    if _field(text, "report_status") == "complete":
        raise ImproveError("seat report is complete and immutable; no "
                           "further RUN sections may be appended")
    # The report lives under .saipen/improve/<cycle>/<seat>/; the cycle must
    # still be ACTIVE for its report to be appended (completed-cycle
    # immutability, NITRO dogfood III, T-595).
    try:
        cycle_dir_of_report = report_path.parent.parent
        _require_cycle_active(cycle_dir_of_report, "append_run")
    except (ImproveError, ValueError):
        raise
    strict = _cycle_schema(cycle_dir_of_report / "MANIFEST.md") == "strict"
    if strict and not _field(text, "report_status"):
        raise ImproveError(
            "append_run refuses: a strict-cycle report must be created "
            "through create_report (it needs the mechanical header) before "
            "any RUN is appended")
    run_count = len(re.findall(r"(?m)^## RUN \d+", text))
    run = f"## RUN {run_count + 1}\n\n{run_text.rstrip()}\n"
    result = _journaled_write(report_path, text.rstrip() + "\n\n" + run,
                              "run", base_hash=_base_hash(report_path))
    if not result.get("ok"):
        raise ImproveError(
            f"RUN not committed: {result.get('code')} "
            f"{result.get('message', '')}")
    return result


def validate_report(text: str, require_runs: bool = False) -> list[str]:
    """Return every report violation; empty means valid.

    `require_runs=True` applies the DOGFOOD V strict completion schema: a
    report declared `report_status: complete` MUST carry at least one explicit
    `## RUN N` section (or an explicit `NO_FINDINGS` run) -- an empty skeleton
    that merely says complete is never a completed audit. `validate_report`
    alone keeps the legacy report rules so the three historical archived
    cycles remain valid legacy evidence.
    """
    errors = []
    parsed = parse_report(text)
    header = parsed.header
    missing = sorted(REQUIRED_HEADER - set(header))
    if missing:
        errors.append("report header missing required fields: "
                      + ", ".join(sorted(missing)))

    if header.get("report_status") and header["report_status"] not in REPORT_STATUS:
        errors.append(f"report_status {header['report_status']!r} outside "
                      "draft|complete")
    avail = header.get("context_available")
    if avail and avail not in ("complete", "partial", "none"):
        errors.append(f"context_available {avail!r} outside "
                      "complete|partial|none")

    scope = header.get("context_scope") or ""
    if avail == "complete" and not scope:
        errors.append("context_available: complete refused over an empty "
                      "context_scope")
    if avail == "complete" and "partial" in scope.lower():
        errors.append("context_available: complete refused over a partial "
                      "context_scope -- a partial scope can never claim a "
                      "full-context result (red control 3, T-555)")
    if header.get("report_status") == "complete" and not scope:
        errors.append("report_status: complete without a context_scope -- "
                      "the completion bar is unmet (T-555)")

    if require_runs and header.get("report_status") == "complete":
        if not parsed.has_runs:
            errors.append("report_status: complete with no explicit ## RUN "
                          "section -- a completed audit needs intentional RUN "
                          "evidence (DOGFOOD V, T-616)")
        else:
            # A run with NO_FINDINGS must actually have zero findings.
            for run_number in sorted(parsed.no_findings_runs):
                if any(f.run == run_number for f in parsed.findings):
                    errors.append(
                        f"RUN {run_number} declares NO_FINDINGS but carries "
                        f"findings -- an intentional empty run must stay "
                        f"empty (DOGFOOD V, T-616)")
            # Every run must carry findings OR an explicit NO_FINDINGS marker:
            # an empty run without the marker is indistinguishable from an
            # interrupted audit (DOGFOOD V, T-616).
            run_numbers = {f.run for f in parsed.findings if f.run is not None}
            for run_number in parsed.runs:
                if (run_number not in run_numbers
                        and run_number not in parsed.no_findings_runs):
                    errors.append(
                        f"RUN {run_number} carries no findings and no "
                        "NO_FINDINGS marker -- an empty audit run is not "
                        "intentional evidence (DOGFOOD V, T-616)")

    for finding in parsed.findings:
        for fname in ("expected", "actual", "evidence"):
            if not getattr(finding, fname):
                errors.append(f"finding {finding.ref()} at line "
                              f"{finding.start} lacks required {fname} -- a "
                              "finding without an observable "
                              "expected/actual/evidence triple is rejected, "
                              "not softened")
        if finding.severity not in SEVERITY:
            errors.append(f"finding {finding.ref()} at line {finding.start}: "
                          f"severity {finding.severity!r} outside the closed "
                          "set")
        if finding.cls not in FINDING_CLASS:
            errors.append(f"finding {finding.ref()} at line {finding.start}: "
                          f"class {finding.cls!r} outside the closed set")
        if finding.confidence not in CONFIDENCE:
            errors.append(f"finding {finding.ref()} at line {finding.start}: "
                          f"confidence {finding.confidence!r} outside the "
                          "closed set")
        if finding.action not in ACTION:
            errors.append(f"finding {finding.ref()} at line {finding.start}: "
                          f"action {finding.action!r} outside the closed set")
    return errors


def validate_manifest(text: str,
                      expected_cycle_id: str | None = None) -> list[str]:
    """Roster manifest grammar (NITRO dogfood IV, T-601 + DOGFOOD V, T-618).

    Parsed with the SAME primitives the manifest's consumers read
    (_seat_blocks / _field / _cycle_status), so the semantic verifier and the
    writer can never disagree about what the file means.

    Schema is DECLARED by the manifest itself: a `manifest_schema: strict`
    line switches on the DOGFOOD V strict rules (exactly one roster header,
    exactly one cycle_id matching the directory identity, exactly one valid
    UTC created_at, exactly one portable project_identity, exactly one
    lifecycle status, no duplicate top-level fields). Its absence keeps the
    legacy pre-boundary rules, so the three historical cycles stay valid
    legacy evidence byte-identically."""
    errors = []
    strict = bool(re.search(r"(?m)^manifest_schema:\s*strict\s*$", text))
    if strict:
        # Exactly one roster header.
        header_count = len(re.findall(
            r"(?m)^# IMPROVE CYCLE ROSTER\s*$", text))
        if header_count != 1:
            errors.append(f"strict manifest must carry exactly one "
                          f"'# IMPROVE CYCLE ROSTER' header, found "
                          f"{header_count}")
        # Exactly one manifest_schema field.
        if len(re.findall(r"(?m)^manifest_schema:\s*strict\s*$", text)) != 1:
            errors.append("strict manifest must carry manifest_schema: "
                          "strict exactly once")
        # Exactly one cycle_id, matching the directory identity when known.
        cycle_ids = re.findall(r"(?m)^cycle_id:\s*(\S+)\s*$", text)
        if len(cycle_ids) != 1:
            errors.append(f"strict manifest must carry exactly one cycle_id, "
                          f"found {len(cycle_ids)}")
        elif expected_cycle_id is not None and cycle_ids[0] != expected_cycle_id:
            errors.append(f"strict manifest cycle_id {cycle_ids[0]!r} does "
                          f"not match the directory identity "
                          f"{expected_cycle_id!r}")
        # Exactly one created_at, valid UTC.
        created = re.findall(r"(?m)^created_at:\s*(\S+)\s*$", text)
        if len(created) != 1:
            errors.append(f"strict manifest must carry exactly one "
                          f"created_at, found {len(created)}")
        else:
            if not re.fullmatch(
                    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", created[0]):
                errors.append(f"strict manifest created_at {created[0]!r} is "
                              "not a valid UTC timestamp (YYYY-MM-DDTHH:MM:SSZ)")
        # Exactly one portable project identity.
        if len(re.findall(r"(?m)^project_identity:\s*(\S+)\s*$", text)) != 1:
            errors.append("strict manifest must carry exactly one "
                          "project_identity")
        # No machine-local absolute path may leak into portable identity.
        if re.search(r"^project_identity:\s*[A-Za-z]:[\\/]|"
                     r"^project_identity:\s*/",
                     text, re.MULTILINE):
            errors.append("strict manifest project_identity must be portable "
                          "-- an absolute machine-local path leaks into "
                          "portable evidence (DOGFOOD V, T-618)")
        # Exactly one lifecycle status.
        if len(re.findall(r"(?m)^cycle_status:\s*[A-Za-z]+\s*$", text)) != 1:
            errors.append("strict manifest must carry exactly one "
                          "cycle_status")
    if not text.startswith("# IMPROVE CYCLE ROSTER"):
        errors.append("manifest must open with '# IMPROVE CYCLE ROSTER'")
    status = re.search(r"(?m)^cycle_status:\s*([A-Za-z]+)", text)
    if status and status.group(1) not in ("active", "complete", "archived"):
        errors.append(f"cycle_status {status.group(1)!r} outside "
                      "active|complete|archived")
    seen: set[str] = set()
    report_owners: dict[str, str] = {}
    for block in _seat_blocks(text):
        seat_id = _field(block, "seat_id")
        if not seat_id:
            errors.append("roster has a seat block without seat_id")
            continue
        if seat_id in seen:
            errors.append(f"duplicate seat_id: {seat_id}")
        seen.add(seat_id)
        if not _field(block, "role"):
            errors.append(f"seat {seat_id}: missing role")
        report_path = _field(block, "report_path")
        if not report_path:
            errors.append(f"seat {seat_id}: missing report_path")
        else:
            try:
                _validate_report_path(report_path, seat_id)
            except ImproveError as exc:
                errors.append(f"seat {seat_id}: {exc}")
            # red control 8 (T-560): ONE report, ONE owner -- two seats must
            # never share a report path.
            if report_path in report_owners and report_owners[
                    report_path] != seat_id:
                errors.append(f"report_path {report_path!r} is owned by both "
                              f"{report_owners[report_path]} and {seat_id}; "
                              "one report has one owner (red control 8)")
            report_owners[report_path] = seat_id
        availability = _field(block, "availability")
        if availability and availability not in AVAILABILITY:
            errors.append(f"seat {seat_id}: availability {availability!r} "
                          "outside expected|unavailable")
    return errors


# The SWEEP ledger grammar lives ONCE at module top (_SWEEP_LINE_RE): the
# finding_ref (RUN-N/IMP-NNN strict, bare IMP-NNN legacy) + disposition token
# and the `report=` identity on the same line for the COMPOSITE finding
# identity (cycle + seat/report + run + IMP id). The validator below consumes
# exactly that parser.


def validate_sweep(text: str) -> list[str]:
    """SWEEP ledger grammar (NITRO dogfood IV, T-601 + DOGFOOD V, T-615).

    Validates the ACTUAL ledger grammar with the parser the consumers use:
    disposition enum, the composite `report=` identity, the exact finding_ref
    (RUN-N/IMP-NNN or legacy IMP-NNN), and the required ticket/reproduced
    fields. Arbitrary malformed garbage in SWEEP.md is a semantic violation --
    an otherwise-valid MANIFEST cannot excuse it."""
    errors = []
    if not text.strip():
        return errors
    if not text.startswith("# SWEEP"):
        errors.append("SWEEP ledger must open with '# SWEEP'")
    for index, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _SWEEP_LINE_RE.match(stripped)
        if not match:
            errors.append(
                f"SWEEP.md line {index}: {stripped!r} does not match the "
                "ledger grammar '- RUN-N/IMP-NNN [DISPOSITION] <ticket> "
                "report=<report_ident> reproduced=<y|n> [fixed_by=<ref>] "
                "[verification=<ref>]'")
            continue
        finding_ref, disposition, ticket, report, reproduced = match.group(
            1, 2, 3, 4, 5)
        if disposition not in DISPOSITION:
            errors.append(f"SWEEP.md line {index}: disposition "
                          f"{disposition!r} outside the closed set "
                          f"{sorted(DISPOSITION)}")
        if not report:
            errors.append(f"SWEEP.md line {index}: missing report identity -- "
                          "the composite finding identity is cycle + "
                          "seat/report + run + IMP id")
        if not ticket:
            errors.append(f"SWEEP.md line {index}: missing canonical ticket "
                          "reference")
        if not reproduced:
            errors.append(f"SWEEP.md line {index}: missing reproduced value")
        if finding_ref.count("/") > 1:
            errors.append(f"SWEEP.md line {index}: malformed finding "
                          f"reference {finding_ref!r}")
    return errors


def validate_report_target(text: str) -> list[str]:
    """Report/run target invariants available at the WRITE stage (NITRO
    dogfood IV, T-601). A report is constructed incrementally, so the full
    validate_report completion bar is checked at complete_cycle time; what is
    checkable the moment a report/run target commits is its closed-field
    vocabulary and the full-context claim."""
    errors = []
    status = _field(text, "report_status")
    if status and status not in REPORT_STATUS:
        errors.append(f"report_status {status!r} outside draft|complete")
    avail = _field(text, "context_available")
    if avail and avail not in ("complete", "partial", "none"):
        errors.append(f"context_available {avail!r} outside "
                      "complete|partial|none")
    if avail == "complete" and not _field(text, "context_scope"):
        errors.append("context_available: complete refused over an empty "
                      "context_scope")
    return errors
