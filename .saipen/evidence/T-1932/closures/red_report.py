"""R027/PERF-004 red-before/green-after controls for bounded report transport.

Each probe mounts a fake SAIPAL CLI that emits a chosen report, then measures
what the adapter does with it: bounded paging, resumable cursor, replay
deduplication, and the refusal shapes that must stay explicit.
"""

from __future__ import annotations

import base64
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from saipen_engine import saipal_adapter as SA  # noqa: E402


def mount(payload: dict, *, raw: bytes | None = None, stderr: bytes = b"", returncode: int = 0):
    """Build a temp SAIPAL home whose CLI emits exactly this response."""
    root = Path(tempfile.mkdtemp(prefix="saipen-r027-"))
    home = root / "backend"
    (home / "tools").mkdir(parents=True)
    (home / ".saipal").mkdir()
    cli = home / "tools" / "saipal.py"
    cli.write_text(
        "import base64,json,pathlib,sys\n"
        "d=json.loads(pathlib.Path(__file__).with_suffix('.response.json')"
        ".read_text(encoding='utf-8'))\n"
        "sys.stdout.buffer.write(base64.b64decode(d['stdout'])); sys.stdout.flush()\n"
        "sys.stderr.buffer.write(base64.b64decode(d['stderr'])); sys.stderr.flush()\n"
        "sys.exit(d['returncode'])\n",
        encoding="utf-8",
    )
    body = raw if raw is not None else json.dumps(payload).encode("utf-8")
    cli.with_suffix(".response.json").write_text(
        json.dumps(
            {
                "stdout": base64.b64encode(body).decode(),
                "stderr": base64.b64encode(stderr).decode(),
                "returncode": returncode,
            }
        ),
        encoding="utf-8",
    )
    project = root / "project"
    (project / ".saipen" / "campaign").mkdir(parents=True)
    return home, project


def report(findings, **extra):
    return {
        "ok": True,
        "command": "report",
        "findings": findings,
        "counts": {"total": len(findings)},
        **extra,
    }


def big_report(count: int, pad: int = 200):
    return report(
        [
            {
                "finding_id": f"PAL-{i:05d}",
                "state": "QUALIFIED" if i % 2 == 0 else "DRAFT",
                "pad": "x" * pad,
            }
            for i in range(count)
        ]
    )


def probe_large_valid_report_is_accepted():
    """A report above the ordinary response bound is VALID, not a resource error."""
    # Large enough to exceed MAX_BACKEND_STDOUT_BYTES (~4 MiB) but still well
    # inside the declared report spool ceiling.
    payload = big_report(20000, pad=300)
    home, project = mount(payload)
    adapter = SA.SaipalAdapter(home)
    size = len(json.dumps(payload).encode("utf-8"))
    res = adapter.collect_findings()
    return {
        "report_bytes": size,
        "generic_stdout_limit": SA.MAX_BACKEND_STDOUT_BYTES,
        "report_spool_limit": SA.REPORT_SPOOL_LIMIT_BYTES,
        "exceeds_generic_limit": size > SA.MAX_BACKEND_STDOUT_BYTES,
        "within_report_limit": size < SA.REPORT_SPOOL_LIMIT_BYTES,
        "ok": res.get("ok"),
        "status": res.get("status"),
        "finding_count": len(res.get("findings") or []),
        "accepted_above_generic_bound": bool(res.get("ok")) and size > SA.MAX_BACKEND_STDOUT_BYTES,
    }


def probe_oversize_within_spool_still_resource_error():
    home, project = mount(big_report(4000))
    adapter = SA.SaipalAdapter(home)
    original = SA.REPORT_SPOOL_LIMIT_BYTES
    SA.REPORT_SPOOL_LIMIT_BYTES = 32768
    try:
        res = adapter._run_cmd("report")
    finally:
        SA.REPORT_SPOOL_LIMIT_BYTES = original
    return {
        "ok": res.get("ok"),
        "status": res.get("status"),
        "is_resource_limit": res.get("status") == SA.BACKEND_RESOURCE_LIMIT,
        "not_treated_as_no_new_evidence": res.get("status") != SA.NO_NEW_EVIDENCE,
    }


def probe_paging_yields_every_finding_once():
    home, project = mount(big_report(1000))
    adapter = SA.SaipalAdapter(home)
    seen: list[str] = []
    pages = 0
    identity = None
    for page in adapter.iter_finding_pages(page_size=128):
        pages += 1
        identity = identity or page[3]
        seen.extend(row["finding_id"] for row in page[2])
    return {
        "pages": pages,
        "total_pages_reported": page[1],
        "findings_seen": len(seen),
        "unique": len(set(seen)),
        "duplicates": len(seen) - len(set(seen)),
        "source_identity_stable": bool(identity and identity.get("source_digest")),
    }


def probe_resume_skips_already_delivered():
    home, project = mount(big_report(50))
    adapter = SA.SaipalAdapter(home)
    first = []
    for page in adapter.iter_new_qualified_findings(project, page_size=10):
        first.extend(r["finding_id"] for r in page["findings"])
        break  # interrupt after one page
    second = []
    for page in adapter.iter_new_qualified_findings(project, page_size=10):
        second.extend(r["finding_id"] for r in page["findings"])
    return {
        "first_batch": len(first),
        "second_run": len(second),
        "overlap": len(set(first) & set(second)),
        "total_distinct": len(set(first) | set(second)),
        "expected_qualified": len([i for i in range(50) if i % 2 == 0]),
        "no_skipped_findings": len(set(first) | set(second)) == len([i for i in range(50) if i % 2 == 0]),
    }


def probe_replay_does_not_duplicate():
    home, project = mount(big_report(20))
    adapter = SA.SaipalAdapter(home)
    totals = []
    for _ in range(3):
        batch = []
        for page in adapter.iter_new_qualified_findings(project, page_size=5):
            batch.extend(r["finding_id"] for r in page["findings"])
        totals.append(len(batch))
    return {
        "run_sizes": totals,
        "first_run": totals[0],
        "replays_empty": totals[1:] == [0, 0],
    }


def probe_changed_source_resets_cursor():
    """A genuinely different corpus must not be suppressed by an old cursor.

    "Different" means different finding identities, not different padding: a
    report that repeats the same ids IS the same corpus, and re-delivering it
    would be the duplicate-publication defect instead.
    """
    home, project = mount(big_report(10))
    adapter = SA.SaipalAdapter(home)
    for _ in adapter.iter_new_qualified_findings(project, page_size=5):
        pass

    new_payload = report(
        [
            {"finding_id": f"PAL-NEW-{i:03d}", "state": "QUALIFIED"}
            for i in range(8)
        ]
    )
    home2, _ = mount(new_payload)
    adapter2 = SA.SaipalAdapter(home2)
    got = []
    for page in adapter2.iter_new_qualified_findings(project, page_size=5):
        got.extend(r["finding_id"] for r in page["findings"])
    return {
        "first_corpus_qualified": 5,
        "new_source_findings": len(got),
        "expected_new": 8,
        "cursor_blocked_new_corpus": len(got) == 0,
        "new_corpus_delivered": len(got) == 8,
    }


def probe_truncated_report_is_explicit():
    body = json.dumps(big_report(50)).encode("utf-8")
    home, project = mount({}, raw=body[: len(body) // 2])
    adapter = SA.SaipalAdapter(home)
    res = adapter.collect_findings()
    return {
        "ok": res.get("ok"),
        "status": res.get("status"),
        "protocol_status": res.get("protocol_status"),
        "not_silently_truncated": res.get("status") != SA.NO_NEW_EVIDENCE,
    }


def probe_backend_refusal_still_propagates():
    home, project = mount(
        {"ok": False, "command": "report", "status": "ANALYSIS_BLOCKED", "error": "evidence missing"}
    )
    adapter = SA.SaipalAdapter(home)
    res = adapter.collect_findings()
    return {
        "ok": res.get("ok"),
        "status": res.get("status"),
        "kept_analysis_blocked": res.get("status") == "ANALYSIS_BLOCKED",
    }


def probe_small_report_unchanged():
    home, project = mount(
        report([{"finding_id": "PAL-1", "state": "QUALIFIED"}])
    )
    adapter = SA.SaipalAdapter(home)
    res = adapter.collect_findings()
    return {
        "ok": res.get("ok"),
        "finding_count": len(res.get("findings") or []),
        "status": res.get("status"),
    }


def probe_invalid_page_size_clamped():
    home, project = mount(big_report(10))
    adapter = SA.SaipalAdapter(home)
    return {
        "zero": adapter.report_page_size(0),
        "negative": adapter.report_page_size(-5),
        "huge": adapter.report_page_size(10**9),
        "max_allowed": SA.REPORT_PAGE_MAX,
    }


PROBES = {
    "large_valid_report_is_accepted": probe_large_valid_report_is_accepted,
    "oversize_within_spool_is_resource_error": probe_oversize_within_spool_still_resource_error,
    "paging_yields_every_finding_once": probe_paging_yields_every_finding_once,
    "resume_skips_already_delivered": probe_resume_skips_already_delivered,
    "replay_does_not_duplicate": probe_replay_does_not_duplicate,
    "changed_source_resets_cursor": probe_changed_source_resets_cursor,
    "truncated_report_is_explicit": probe_truncated_report_is_explicit,
    "backend_refusal_still_propagates": probe_backend_refusal_still_propagates,
    "small_report_unchanged": probe_small_report_unchanged,
    "invalid_page_size_clamped": probe_invalid_page_size_clamped,
}


if __name__ == "__main__":
    out = {}
    for name, fn in PROBES.items():
        try:
            out[name] = fn()
        except Exception as exc:  # noqa: BLE001 - a probe failure is the measurement
            out[name] = {"probe_error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(out, indent=2))
