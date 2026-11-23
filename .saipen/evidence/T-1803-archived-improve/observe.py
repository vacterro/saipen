"""Read the real consumer; exercise mutators only on explicitly labelled copies."""
from __future__ import annotations

import hashlib
import inspect
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
ENGINE = EVIDENCE.parents[2]
CONSUMER = Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK")
CYCLES = ("imp-vacterro-audapack-20260918-1", "imp-vacterro-audapack-20260919-7")
EXPECTED_LINEAGE = "lineage-79944d6c0334416ebe1001e97de6c1cc"
sys.path.insert(0, str(ENGINE / "tools"))
import improve  # noqa: E402
from saipen_engine.continue_fallback import cycle_liveness  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "ABSENT"


def protected() -> dict[str, str]:
    files = [CONSUMER / ".saipen" / name for name in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md")]
    for cycle_id in CYCLES:
        directory = CONSUMER / ".saipen/improve" / cycle_id
        files.extend(path for path in directory.rglob("*") if path.is_file())
        files.append(directory / "SWEEP.md")
    return {path.relative_to(CONSUMER).as_posix(): digest(path) for path in sorted(set(files))}


def observe_call(callback) -> dict:
    try:
        return {"returned": callback()}
    except Exception as exc:
        return {"error_type": type(exc).__name__, "error": str(exc)}


def main() -> None:
    if EXPECTED_LINEAGE not in (CONSUMER / ".saipen/IDENTITY.md").read_text(encoding="utf-8"):
        raise RuntimeError("Consumer lineage mismatch; observation stopped")
    before = protected()
    scratch = Path(tempfile.mkdtemp(prefix="saipen-T1803-repro-")).resolve()
    # This disposable copy is deliberately NOT an admitted consumer execution seat.
    (scratch / ".saipen").mkdir()
    shutil.copy2(CONSUMER / ".saipen/IDENTITY.md", scratch / ".saipen/IDENTITY.md")
    observations = []
    for cycle_id in CYCLES:
        live = CONSUMER / ".saipen/improve" / cycle_id
        copied = scratch / ".saipen/improve" / cycle_id
        shutil.copytree(live, copied)
        roster = (copied / "MANIFEST.md").read_text(encoding="utf-8")
        seats = []
        for block in improve._seat_blocks(roster):
            seat = improve._field(block, "seat_id")
            report_name = improve._field(block, "report_path")
            report = copied / seat / report_name
            text = report.read_text(encoding="utf-8")
            parsed = improve.parse_report(text)
            seats.append({"seat": seat, "report": report_name, "sha256": digest(report),
                          "report_status": parsed.header.get("report_status"),
                          "errors": parsed.errors,
                          "findings": [{"ref": item.ref(), "expected": item.expected,
                                        "actual": item.actual, "evidence": item.evidence}
                                       for item in parsed.findings]})
        content_seat = next(item for item in seats if item["findings"])
        entry = {"run": "RUN-1", "imp_id": "IMP-001", "disposition": "INVALID",
                 "ticket": "-", "report": content_seat["seat"] + "/" + content_seat["report"],
                 "reproduced": "n", "verification": "T-1803-synthetic-api-probe"}
        report = copied / content_seat["seat"] / content_seat["report"]
        observations.append({"cycle": cycle_id, "scope": "MUTATORS ON DISPOSABLE COPY ONLY",
            "seats": seats, "live_read_only_liveness": cycle_liveness(CONSUMER, cycle_id),
            "reconcile": observe_call(lambda: improve.reconcile_cycle(copied, dry_run=True)),
            "retire": observe_call(lambda: improve.retire_seat(copied, seats[0]["seat"], "EMPTY_DRAFT", dry_run=True)),
            "sweep": observe_call(lambda: improve.write_sweep_entry(copied, entry)),
            "amend": observe_call(lambda: improve.write_sweep_entry(copied, dict(entry, amend=True))),
            "complete_report": observe_call(lambda: improve.complete_report(report, dry_run=True)),
            "abort": observe_call(lambda: improve.abort_cycle(copied, dry_run=True))})
    after = protected()
    result = {"observed_utc": datetime.now(timezone.utc).isoformat(), "consumer": str(CONSUMER),
              "consumer_lineage": EXPECTED_LINEAGE, "consumer_read_only": before == after,
              "protected_before": before, "protected_after": after, "scratch_copy": str(scratch),
              "module": str(Path(improve.__file__).resolve()), "module_sha256": digest(Path(improve.__file__)),
              "signatures": {name: str(inspect.signature(getattr(improve, name))) for name in
                             ("reconcile_cycle", "retire_seat", "write_sweep_entry", "_require_cycle_amendable", "complete_report", "abort_cycle")},
              "cycles": observations}
    (EVIDENCE / "baseline-observation.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"consumer_read_only": result["consumer_read_only"], "scratch_copy": str(scratch),
                      "cycles": [{"cycle": item["cycle"], "findings": sum(len(seat["findings"]) for seat in item["seats"]),
                                  "parse_errors": {seat["seat"]: seat["errors"] for seat in item["seats"]},
                                  "reconcile": item["reconcile"], "sweep": item["sweep"], "amend": item["amend"]}
                                 for item in observations]}, ensure_ascii=False))
    if before != after:
        raise RuntimeError("Consumer bytes changed during observation; no further mutation permitted")


if __name__ == "__main__":
    main()
