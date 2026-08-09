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

_FINDING_RE = re.compile(r"^IMP-(\d+)", re.MULTILINE)
_SWEEP_RE = re.compile(
    r"^- IMP-(\d+) \[([A-Z_]+)\]", re.MULTILINE)

_IMP_DIR = ".saipen/improve"


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
    """Deterministic unique cycle id: imp-<key>-<date>-<nn>."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "-", project_key).lower()
    return f"imp-{safe}-{now}"


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


def _field(text: str, key: str) -> str:
    match = re.search(rf"(?m)^{key}:\s*(.+)$", text)
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


def _finding_ids(report_text: str) -> list[str]:
    """Every IMP-### in the report, in order."""
    return [f"IMP-{m.group(1)}"
            for m in re.finditer(_FINDING_RE, report_text)]


def _disposed_ids(sweep_text: str) -> list[str]:
    """Every IMP-### with a disposition in the Core sweep ledger."""
    return [f"IMP-{m.group(1)}" for m in re.finditer(_SWEEP_RE, sweep_text)]


def derive_status(report_ident: str, roster_text: str, report_text: str,
                  sweep_text: str) -> dict:
    """The visible status, DERIVED per seat.

    - roster entry for THIS seat (exact seat_id block) owns availability;
    - the report owns report_status;
    - the sweep ledger owns dispositions.

    `swept` means EVERY finding requiring disposition has a final Core
    disposition -- a single appearance of the report identifier in the ledger
    is NOT coverage.
    """
    seat = re.sub(r"^saipen_improve_", "", Path(report_ident).stem)
    availability = "expected"
    block = _block_for_report(roster_text, report_ident)
    if block is not None:
        availability = _field(block, "availability") or "expected"
    status = _field(report_text, "report_status")
    expected = set(_finding_ids(report_text))
    disposed = set(_disposed_ids(sweep_text))
    missing = sorted(expected - disposed)
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
            "disposed": sorted(disposed), "missing": missing}


def _project_root_of(path: Path) -> Path:
    """The project root owning a path under .saipen/ (walk up to .saipen)."""
    cursor = path
    while cursor.parent != cursor.parent.parent and cursor.name != ".saipen":
        cursor = cursor.parent
    if cursor.name == ".saipen":
        return cursor.parent
    raise ImproveError(f"cannot resolve a project root for {path}")


def write_sweep_entry(cycle_dir: Path, entry: dict) -> dict:
    """Append a disposition to the Core-owned SWEEP ledger (journaled write).

    Returns the transaction result; the caller MUST inspect it. An invalid
    disposition writes zero bytes.
    """
    disposition = entry.get("disposition")
    if disposition not in DISPOSITION:
        raise ImproveError(
            f"disposition {disposition!r} outside the closed set "
            f"{sorted(DISPOSITION)}")
    imp_raw = str(entry.get("imp_id", ""))
    if re.fullmatch(r"\d+", imp_raw):
        imp_id = f"IMP-{imp_raw}"
    elif re.fullmatch(r"IMP-\d+", imp_raw):
        imp_id = imp_raw
    else:
        raise ImproveError(f"imp_id {imp_raw!r} is not IMP-###")
    ledger = cycle_dir / "SWEEP.md"
    _prove_inside(_project_root_of(ledger), ledger)
    text = _read_maybe(ledger)
    if text and not text.startswith("# SWEEP"):
        text = "# SWEEP\n\n" + text
    line = ("- IMP-{imp_id} [{disposition}] {ticket} report={report} "
            "reproduced={reproduced}".format(
                imp_id=imp_id,
                disposition=disposition,
                ticket=entry.get("ticket", "-"),
                report=entry.get("report", "-"),
                reproduced=entry.get("reproduced", "-")))
    result = _journaled_write(ledger, text + line + "\n", "sweep")
    if not result.get("ok"):
        raise ImproveError(
            f"sweep entry for {imp_id} not committed: "
            f"{result.get('code')} {result.get('message', '')}")
    return result


def _journaled_write(path: Path, content: str, kind: str) -> dict:
    """Write one file through the common lock + journal + roll-forward
    machinery. Returns the transaction result; callers inspect and propagate.

    The target is a single ATOMIC_FILE transaction: one target, its own
    before/after hashes, staged exact bytes, post-write byte verification.
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
    before = _hash_file(path) if path.is_file() else ""
    with project_writer_lock(root):
        return run_mutation(
            root, op_id, kind, "saipen", _identity(root),
            hash_bytes(rel.encode("utf-8")),
            [{"path": rel, "role": "generic", "content": content_bytes,
              "before_hash": before,
              "after_hash": hash_bytes(content_bytes)}],
            preconditions={rel: before})


def _identity(root: Path) -> str:
    from saipen_engine.paths import project_identity
    return project_identity(root)


def register_cycle(project_root: Path, cycle_id: str,
                   roster_lines: str) -> Path:
    """Create a cycle directory journaled; refuse if ANY active cycle exists.

    A cycle is admitted only by a valid committed MANIFEST. A bare directory
    is incomplete runtime debris, never an admitted cycle. `register_cycle`
    refuses while another cycle's MANIFEST exists anywhere under the owner
    root: one active Improve cycle per project.
    """
    root = Path(project_root)
    cdir = cycle_dir(root, cycle_id)
    _prove_inside(root, cdir)
    owner = _owner_root(root)
    if owner.is_dir():
        for manifest in owner.glob("*/MANIFEST.md"):
            raise ImproveError(
                f"improve cycle {manifest.parent.name} already exists -- a "
                f"project has at most one active Improve cycle")
    if (cdir / "MANIFEST.md").exists():
        raise ImproveError(
            f"improve cycle {cycle_id} already exists -- a project has at "
            f"most one active Improve cycle")
    content = ("# IMPROVE CYCLE ROSTER\n\n" + roster_lines)
    result = _journaled_write(cdir / "MANIFEST.md", content, "cycle")
    if not result.get("ok"):
        raise ImproveError(
            f"cycle {cycle_id} not committed: {result.get('code')} "
            f"{result.get('message', '')}")
    return cdir


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
    manifest = cycle_dir / "MANIFEST.md"
    _prove_inside(_project_root_of(manifest), manifest)
    text = _read_maybe(manifest)
    if not text.startswith("# IMPROVE CYCLE ROSTER"):
        text = "# IMPROVE CYCLE ROSTER\n\n" + text
    if _seat_block(text, seat) is not None:
        raise ImproveError(f"duplicate seat registration: {seat}")
    line = (f"seat_id: {seat}\nrole: {role}\nreport_path: {report_path}\n"
            f"availability: {availability}\n")
    result = _journaled_write(manifest, text.rstrip() + "\n" + line, "seat")
    if not result.get("ok"):
        raise ImproveError(
            f"seat {seat} not committed: {result.get('code')} "
            f"{result.get('message', '')}")
    return result


def append_run(report_path: Path, run_text: str) -> dict:
    """Append an immutable RUN section to a seat report (T-551, migrated to
    the journal in NITRO M6).

    A second run from the same seat in the same cycle APPENDS; an earlier RUN
    is never overwritten. Once report_status is complete the report is
    immutable and further RUNs are refused. Returns the transaction result.
    """
    text = _read_maybe(report_path)
    if "report_status: complete" in text:
        raise ImproveError("seat report is complete and immutable; no "
                           "further RUN sections may be appended")
    run_count = len(re.findall(r"(?m)^## RUN \d+", text))
    run = f"## RUN {run_count + 1}\n\n{run_text.rstrip()}\n"
    result = _journaled_write(report_path, text.rstrip() + "\n\n" + run,
                              "run")
    if not result.get("ok"):
        raise ImproveError(
            f"RUN not committed: {result.get('code')} "
            f"{result.get('message', '')}")
    return result


def validate_report(text: str) -> list[str]:
    """Return every report violation; empty means valid."""
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
        if _FINDING_RE.match(line):
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
