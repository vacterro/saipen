#!/usr/bin/env python
"""Re-derive `real-repository-proof.json` from THIS repository's current bytes.

T-1370 / SRC-049 acceptance: the retirement of T-1368/SRC-047 and T-1369/SRC-048
happened in the real project, not in a fixture, so its proof has to be
re-runnable against the real project. A JSON file full of `"ok": true` constants
written by hand proves only that somebody typed them; the defect class this
script eliminates is exactly that -- an acceptance artifact that cannot go red.

Every check below reads a canonical carrier (intake index, tombstone, meta,
coverage, the forensic record, BOARD, LOG, the working tree) or calls the
protocol's own reader, and each one CAN fail. Run it and compare:

    python .saipen/evidence/T-1370-retirement-20260916/real_repository_proof.py
    python .saipen/evidence/T-1370-retirement-20260916/real_repository_proof.py --write

Exit code is 0 only when every check is ok.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import intake, retirement  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402

PAIRS = (("SRC-047", "T-1368"), ("SRC-048", "T-1369"))
PROOF = HERE / "real-repository-proof.json"
RESIDUE = HERE / "src-app.py.residue"
PROVENANCE = HERE / "src-app-provenance.json"


def _read_json(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _index() -> dict:
    return _read_json(ROOT / ".saipen/intake/index.json") or {}


def _board_text() -> str:
    return (ROOT / ".saipen/BOARD.md").read_text(encoding="utf-8-sig")


def _log_text() -> str:
    return (ROOT / ".saipen/LOG.md").read_text(encoding="utf-8-sig")


def _check(checks: list[dict], name: str, ok: bool, detail: object = None) -> None:
    checks.append({"check": name, "ok": bool(ok), "detail": detail})


def _receipt_checks(checks: list[dict], receipt: str, work: str) -> None:
    index = _index()
    active = index.get("active", {})
    _check(checks, f"{receipt} absent from ACTIVE intake index", receipt not in active)

    bodies = [
        ROOT / f".saipen/intake/active/{receipt}.md",
        ROOT / f".saipen/intake/active/{receipt}.meta.json",
    ]
    present = [str(p.relative_to(ROOT)) for p in bodies if p.exists()]
    _check(checks, f"{receipt} active body/meta absent", not present, present or None)

    tomb = _read_json(ROOT / f".saipen/intake/tombstones/{receipt}.json")
    errors = (
        retirement.retirement_tombstone_errors(receipt, tomb)
        if isinstance(tomb, dict)
        else [f"{receipt}: no tombstone"]
    )
    schema_ok = (
        isinstance(tomb, dict)
        and not errors
        and tomb.get("status") == "INVALID"
        and tomb.get("schema_version") == retirement.RETIREMENT_SCHEMA_VERSION
        and retirement.is_retired_tombstone(tomb)
    )
    reported = tomb if isinstance(tomb, dict) else {}
    _check(
        checks,
        f"{receipt} INVALID retirement tombstone present (schema 2)",
        schema_ok,
        {
            "errors": errors,
            **{
                field: reported.get(field)
                for field in (
                    "status",
                    "reason",
                    "linked_work",
                    "retirement_event",
                    "evidence_bound_event",
                    "discovery_event",
                    "authority_grant",
                )
            },
        },
    )

    archive = ROOT / retirement.retired_source_ref(receipt)
    raw = archive.read_bytes() if archive.is_file() else None
    digest = hashlib.sha256(raw).hexdigest() if raw is not None else None
    declared = (tomb or {}).get("source_sha256") if isinstance(tomb, dict) else None
    _check(
        checks,
        f"{receipt} original request bytes exactly retrievable",
        raw is not None and digest == declared,
        {
            "archive_ref": retirement.retired_source_ref(receipt),
            "sha256": digest,
            "tombstone_sha256": declared,
            "text": raw.decode("utf-8") if raw is not None else None,
        },
    )

    meta = _read_json(ROOT / retirement.retired_meta_ref(receipt))
    meta_errors = (
        retirement.meta_retirement_errors(receipt, meta, tomb)
        if isinstance(meta, dict) and isinstance(tomb, dict)
        else [f"{receipt}: no archived meta"]
    )
    _check(
        checks,
        f"{receipt} archived meta agrees with the tombstone",
        not meta_errors,
        meta_errors or None,
    )

    coverage = _read_json(ROOT / f".saipen/intake/coverage/{receipt}.json") or {}
    contract = _read_json(ROOT / f".saipen/intake/contracts/{receipt}.json") or {}
    dispositions = coverage.get("dispositions") or coverage.get("clauses") or []
    requirements = contract.get("requirements") or []
    _check(
        checks,
        f"{receipt} no fabricated coverage",
        not dispositions and not requirements,
        {"dispositions": dispositions, "requirements": len(requirements)},
    )

    board = parse_board(_board_text())
    _check(
        checks,
        f"{work} absent from schedulable BOARD",
        work not in board["tickets"],
    )

    record, record_errors, legacy = retirement.load_ticket_retirement(ROOT, work)
    _check(
        checks,
        f"{work} forensic record retrievable and valid",
        record is not None and not record_errors,
        {
            "errors": record_errors,
            "legacy_schema": legacy,
            "retirement_event": (record or {}).get("retirement_event"),
            "evidence": (record or {}).get("evidence"),
            "restored_parent": (record or {}).get("restored_parent"),
        },
    )

    done_lines = [
        line
        for line in _log_text().splitlines()
        if f"[{work}]" in line and "finished" in line.lower()
    ]
    _check(checks, f"{work} no DONE claim anywhere in LOG history", not done_lines, done_lines)

    done_rows = [
        line
        for line in _board_text().splitlines()
        if line.lstrip().startswith("- [x]") and f" {work} " in f" {line} "
    ]
    _check(checks, f"{work} no DONE row on BOARD", not done_rows, done_rows or None)


def build() -> dict:
    checks: list[dict] = []
    for receipt, work in PAIRS:
        _receipt_checks(checks, receipt, work)

    fixture = ROOT / "src/app.py"
    _check(checks, "src/app.py absent", not fixture.exists())

    provenance = _read_json(PROVENANCE) or {}
    raw = RESIDUE.read_bytes() if RESIDUE.is_file() else None
    digest = hashlib.sha256(raw).hexdigest() if raw is not None else None
    _check(
        checks,
        "residue preserves the removed fixture bytes",
        raw is not None and digest == provenance.get("sha256"),
        {
            "sha256": digest,
            "provenance_sha256": provenance.get("sha256"),
            "bytes": len(raw) if raw is not None else None,
        },
    )

    findings = intake.validate_project(ROOT)
    _check(checks, "intake validation green", not findings, findings)

    return {
        "subject": "SRC-049/SRC-050 G -- real repository proof of the T-1368/T-1369 retirement",
        "generator": ".saipen/evidence/T-1370-retirement-20260916/real_repository_proof.py",
        "all_ok": all(entry["ok"] for entry in checks),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="rewrite real-repository-proof.json")
    args = parser.parse_args()

    report = build()
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.write:
        PROOF.write_text(text, encoding="utf-8", newline="\n")

    for entry in report["checks"]:
        if not entry["ok"]:
            print(f"FAIL {entry['check']}: {entry['detail']}")
    print(f"{sum(1 for e in report['checks'] if e['ok'])}/{len(report['checks'])} ok")
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
