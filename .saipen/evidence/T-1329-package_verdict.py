"""T-1329 acceptance: the verdict for a CURRENT package, from the FINAL ARCHIVE.

Discovery success is not acceptance. This reads what the delivery artifact
actually contains and compares it against the audit contract the protocol
declares, rather than against what the builder intended to collect. The source
tree is read too -- but only to answer "was this evidence PRESENT to be
exported", which is the difference between an omission and an absence.

Rules (operator specification):
  * MANDATORY missing                    -> NON_AUTHORITATIVE
  * PRESENT CONDITIONAL missing          -> NON_AUTHORITATIVE
  * OPTIONAL omission / truncation       -> reported, not disqualifying
  * NON-EXPORTABLE runtime/local state   -> must not appear at all

    python .saipen/evidence/T-1329-package_verdict.py <archive.zip> <project-root> [--json]

A refused build has no artifact; pass `-` as the archive to record that case
with its source-side evidence intact.
"""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

from saipen_engine.audit_manifest import (  # noqa: E402
    CONDITIONAL_DIRS,
    CONTRACT_VERSION,
    MANDATORY_FILES,
    MANIFEST_NAME,
    NON_EXPORTABLE,
    OPTIONAL_DIRS,
)
from saipen_engine.paths import SAIPEN_DIR  # noqa: E402


def _git(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(project),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def collected_inventory(project: Path) -> set[str]:
    """What the delivery path would collect: tracked + untracked non-ignored."""
    tracked = _git(project, "ls-files", "-z")
    others = _git(project, "ls-files", "--others", "--exclude-standard", "-z")
    out: set[str] = set()
    for result in (tracked, others):
        if result.returncode == 0:
            out |= {entry for entry in result.stdout.split("\0") if entry.strip()}
    return out


def _source_files_under(project: Path, rel: str) -> int:
    target = project / SAIPEN_DIR
    for part in rel.split("/"):
        target = target / part
    if not target.is_dir():
        return -1
    return sum(1 for entry in target.rglob("*") if entry.is_file())


def verdict(archive: Path | None, project: Path) -> dict:
    members: set[str] = set()
    if archive is not None:
        with zipfile.ZipFile(archive) as zf:
            members = {i.filename for i in zf.infolist() if not i.filename.endswith("/")}

    collected = collected_inventory(project)
    prefix = f"{SAIPEN_DIR}/"

    mandatory_required = [f"{prefix}{name}" for name in MANDATORY_FILES]
    mandatory_included = [name for name in mandatory_required if name in members]
    mandatory_missing = [name for name in mandatory_required if name not in members]

    conditional = []
    for rel, _recursive, cap in CONDITIONAL_DIRS:
        source_count = _source_files_under(project, rel)
        present_in_source = source_count > 0
        in_archive = sum(1 for m in members if m.startswith(f"{prefix}{rel}/"))
        conditional.append(
            {
                "path": rel,
                "required": present_in_source,
                "source_files": source_count,
                "included": in_archive,
                "missing": present_in_source and in_archive == 0,
                "truncated": present_in_source and 0 < in_archive < source_count,
                "over_cap": source_count > cap,
            }
        )

    optional = []
    for rel, _recursive, cap in OPTIONAL_DIRS:
        source_count = _source_files_under(project, rel)
        if source_count <= 0:
            continue
        in_archive = sum(1 for m in members if m.startswith(f"{prefix}{rel}/"))
        optional.append(
            {
                "path": rel,
                "source_files": source_count,
                "included": in_archive,
                "omitted": in_archive == 0,
                "truncated": 0 < in_archive < source_count,
                "over_cap": source_count > cap,
            }
        )

    leakage = sorted(
        m for m in members if any(m.startswith(f"{prefix}{p}") for p in NON_EXPORTABLE)
    )

    conditional_missing = [c["path"] for c in conditional if c["missing"]]
    conditional_truncated = [c["path"] for c in conditional if c["truncated"]]
    required_evidence_omitted = sorted(mandatory_missing + conditional_missing)

    reasons = []
    if archive is None:
        reasons.append("NO_ARTIFACT: the delivery build refused; no final archive exists")
    if mandatory_missing:
        reasons.append(f"MANDATORY_MISSING: {mandatory_missing}")
    if conditional_missing:
        reasons.append(f"PRESENT_CONDITIONAL_MISSING: {conditional_missing}")
    if leakage:
        reasons.append(f"NON_EXPORTABLE_LEAKAGE: {leakage[:10]}")

    version_file = project / "VERSION"
    manifest = project / SAIPEN_DIR / MANIFEST_NAME
    manifest_contract = None
    if f"{prefix}{MANIFEST_NAME}" in members and archive is not None:
        with zipfile.ZipFile(archive) as zf:
            try:
                manifest_contract = json.loads(
                    zf.read(f"{prefix}{MANIFEST_NAME}").decode("utf-8")
                ).get("contract_version")
            except (KeyError, ValueError):
                manifest_contract = "UNREADABLE"

    return {
        "project_root": str(project),
        "archive": str(archive) if archive else None,
        "verdict_basis": "FINAL_ARCHIVE" if archive is not None else "NO_ARTIFACT",
        "saipen_detected": (project / SAIPEN_DIR).is_dir(),
        "saipen_in_archive": any(m.startswith(prefix) for m in members),
        "protocol_version": (
            version_file.read_text(encoding="utf-8").strip()
            if version_file.is_file()
            else "NOT_PRESENT (project snapshot, not protocol source)"
        ),
        "audit_contract_version_reader": CONTRACT_VERSION,
        "audit_contract_version_archive": (
            manifest_contract
            if manifest_contract is not None
            else ("NOT_IN_ARCHIVE" if manifest.is_file() else "NOT_IN_SOURCE")
        ),
        "collected_count": len(collected),
        "final_archive_count": len(members),
        "mandatory_required": mandatory_required,
        "mandatory_included": mandatory_included,
        "mandatory_missing": mandatory_missing,
        "conditional": conditional,
        "conditional_missing": conditional_missing,
        "conditional_truncated": conditional_truncated,
        "optional": optional,
        "optional_omissions": [o["path"] for o in optional if o["omitted"]],
        "optional_truncations": [o["path"] for o in optional if o["truncated"]],
        "required_evidence_omitted": required_evidence_omitted,
        "non_exportable_leakage": leakage,
        "authoritative_state": "NON_AUTHORITATIVE" if reasons else "AUTHORITATIVE",
        "reasons": reasons,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    archive = None if argv[1] == "-" else Path(argv[1])
    project = Path(argv[2])
    report = verdict(archive, project)
    print(json.dumps(report, indent=2))
    return 0 if report["authoritative_state"] == "AUTHORITATIVE" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
