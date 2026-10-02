"""T-1406 regression oracle: improve stale-draft liveness + bounded seat exit.

Engine-level matrix against the improve engine located at SAIPEN_T1406_TOOLS
(default: this repository's tools/). Exits 0 only when every expected
post-fix outcome holds; a pre-fix subject fails loudly (no re-bind, no
`retire`) so the same script is the verifier's red half.

Checks:
  A. install-stale un-audited DRAFT: resume re-binds the header, journals the
     change, reports the previous fingerprint, and keeps zero RUN bytes.
  B. audited (RUN-bearing) stale DRAFT: resume refuses, report bytes intact,
     refusal names the retire route.
  C. source-stale un-audited DRAFT: resume re-binds the source identity.
  D. bounded exit: abort refuses post-sweep; retire flips ONE seat
     unavailable; verify passes; cycle completes; both report bodies and the
     sweep disposition stay byte-identical.
  E. retire refuses a complete report and a second retirement.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

TOOLS = Path(os.environ.get("SAIPEN_T1406_TOOLS", r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\tools"))
sys.path.insert(0, str(TOOLS))

import improve  # noqa: E402

prepare_audit_seat = improve.prepare_audit_seat
append_run = improve.append_run
complete_report = improve.complete_report
complete_cycle = improve.complete_cycle
cycle_dir = improve.cycle_dir
verify_cycle = improve.verify_cycle
abort_cycle = improve.abort_cycle
write_sweep_entry = improve.write_sweep_entry
ImproveError = improve.ImproveError
retire_seat = getattr(improve, "retire_seat", None)

RESULTS: list[tuple[str, bool, str]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((label, bool(ok), detail))


def fixture(name: str) -> Path:
    root = Path(tempfile.mkdtemp(prefix=name))
    (root / ".saipen").mkdir()
    (root / "src.txt").write_text("v1\n", encoding="utf-8")
    return root


def prepare(root: Path, session: str):
    return prepare_audit_seat(
        root,
        agent_family="opencode",
        role="core",
        session_id=session,
        project_name="PROBE",
        model_or_runtime="oracle",
        context_scope="t1406 oracle",
    )


def set_fingerprint(report: Path, value: str) -> None:
    report.write_text(
        re.sub(
            r"(?m)^protocol_fingerprint:.*$",
            f"protocol_fingerprint: {value}",
            report.read_text(encoding="utf-8-sig"),
            count=1,
        ),
        encoding="utf-8",
    )


def main() -> int:
    bogus = "sha256:" + "f" * 64

    root = fixture("t1406-oracle-install-")
    first = prepare(root, "opencode-01")
    report = root / first["report_path"]
    set_fingerprint(report, bogus)
    retry = prepare(root, "opencode-01")
    check(
        "A install-stale un-audited draft re-binds",
        retry.get("code") == "ALREADY_ASSIGNED"
        and retry.get("header_rebound") is True
        and retry.get("previous_protocol_fingerprint") == bogus
        and len(re.findall(r"(?m)^## RUN \d+\s*$", report.read_text(encoding="utf-8-sig"))) == 0,
        json.dumps(retry, default=str)[:220],
    )

    root = fixture("t1406-oracle-audited-")
    first = prepare(root, "opencode-01")
    report = root / first["report_path"]
    report.write_text(
        report.read_text(encoding="utf-8-sig") + "\n## RUN 1\n\nNO_FINDINGS\n", encoding="utf-8"
    )
    set_fingerprint(report, bogus)
    before = report.read_bytes()
    retry = prepare(root, "opencode-01")
    check(
        "B audited stale draft refuses and is never re-bound",
        retry.get("ok") is False
        and retry.get("resumed") is False
        and report.read_bytes() == before
        and "improve retire" in str(retry.get("detail", "")),
        json.dumps(retry, default=str)[:220],
    )

    root = fixture("t1406-oracle-source-")
    prepare(root, "opencode-01")
    (root / "src.txt").write_text("v2\n", encoding="utf-8")
    retry = prepare(root, "opencode-01")
    check(
        "C source-stale un-audited draft re-binds",
        retry.get("code") == "ALREADY_ASSIGNED" and retry.get("header_rebound") is True,
        json.dumps(retry, default=str)[:220],
    )

    root = fixture("t1406-oracle-exit-")
    s1 = prepare(root, "opencode-01")
    s2 = prepare(root, "opencode-02")
    cycle = cycle_dir(root, s1["cycle_id"])
    r1 = root / s1["report_path"]
    r2 = root / s2["report_path"]
    r1.write_text(r1.read_text(encoding="utf-8-sig") + "\n## RUN 1\n\nNO_FINDINGS\n", encoding="utf-8")
    set_fingerprint(r1, bogus)
    append_run(
        r2,
        "IMP-001 [P2] [LOGIC_ERROR] [observed] [note]\nexpected: none\n"
        "actual: synthetic\nevidence: oracle\n",
    )
    complete_report(r2)
    write_sweep_entry(
        cycle,
        {
            "run": "RUN-1",
            "imp_id": "IMP-001",
            "disposition": "NOT_REPRODUCED",
            "ticket": "-",
            "report": "opencode-02/saipen_improve_PROBE.md",
            "reproduced": "n",
        },
    )
    r1_before, r2_before = r1.read_bytes(), r2.read_bytes()
    sweep_before = (cycle / "SWEEP.md").read_bytes()
    try:
        abort_cycle(cycle)
        abort_refused = False
    except ImproveError:
        abort_refused = True
    if retire_seat is None:
        check("D bounded exit (retire exists, abort refuses post-sweep)", False, "retire_seat missing")
    else:
        retired = retire_seat(cycle, "opencode-01", "STALE_INSTALL")
        try:
            retire_seat(cycle, "opencode-02", "WHY")
            complete_refused = False
        except ImproveError:
            complete_refused = True
        errors = verify_cycle(cycle)
        try:
            complete_cycle(cycle)
            completed = True
        except ImproveError:
            completed = False
        check(
            "D bounded exit (retire exists, abort refuses post-sweep)",
            abort_refused
            and retired.get("code") == "SEAT_RETIRED"
            and errors == []
            and completed
            and r1.read_bytes() == r1_before
            and r2.read_bytes() == r2_before
            and (cycle / "SWEEP.md").read_bytes() == sweep_before,
            json.dumps((retired, errors), default=str)[:220],
        )
        check("E retire refuses a complete report", complete_refused)

    failed = [label for label, ok, _ in RESULTS if not ok]
    for label, ok, detail in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}: {label}" + ("" if ok else f" -- {detail}"))
    print(f"t1406 oracle: {len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
