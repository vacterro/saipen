"""Read-only probes for every SRC-338 clause that could still be open."""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import host_dispatch, host_iteration, campaign, saipal_adapter, supervisor  # noqa: E402
from saipen_engine import autonomy  # noqa: E402


def project(tmp: Path) -> Path:
    p = tmp / "p"
    (p / ".saipen" / "campaign").mkdir(parents=True)
    (p / ".saipen" / "STATE.md").write_text("---\nphase: BUILD\ntask: T-1\n---\n", encoding="utf-8")
    (p / ".saipen" / "BOARD.md").write_text("# B\n## DOING\n- [/] T-1 [P1] x\n## TODO\n## DONE\n", encoding="utf-8")
    (p / ".saipen" / "LOG.md").write_text("- a\n", encoding="utf-8")
    return p


def w2_004(tmp: Path):
    p = project(tmp)
    payload = host_dispatch.build_dispatch_payload(p, campaign_id="C-2")
    first = host_dispatch.dispatch_next_turn(p, dict(payload), host_hook=None, print_advisory=False)
    receipt = {
        "schema_version": 1,
        "status": host_dispatch.HOST_ACCEPTED,
        "campaign_id": payload["campaign_id"],
        "iteration_id": payload["iteration_id"],
        "worker_generation": payload["worker_generation"],
        "idempotency_key": payload["idempotency_key"],
        "accepting_host": "native_host",
        "project_lineage": payload["project_lineage"],
        "accepted_request_digest": payload["idempotency_key"],
    }
    second = host_dispatch.dispatch_next_turn(p, dict(payload), host_hook=lambda pl: receipt, print_advisory=False)
    return {"first": first.get("status"), "after_host_available": second.get("status"), "second_dispatched": second.get("dispatched")}


def core_012(tmp: Path):
    # `project()` creates the campaign dir, so call it ONCE: the original probe
    # built it twice and died on FileExistsError, which masked the real action.
    p = project(tmp)
    c = host_iteration.HostIterationController(required=set(), project_root=p)
    verdict = {"decision": "AUTO_KICK", "canonical_task": "T-1", "phase": "BUILD", "next_action": "x"}
    act = c.on_model_turn_finished(verdict, turn_context={"project_root": p})
    return {
        "action": act,
        "disposition": getattr(c, "telemetry_dispatch", None),
        "telemetry": [t.get("event") for t in c.telemetry],
    }


def w2_007(tmp: Path):
    p = project(tmp)
    adapter = saipal_adapter.SaipalAdapter(saipal_home=p)
    import hashlib
    body = "# f\nx\n"
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    # A QUALIFIED state is not enough: deliver_finding_to_audit_inbox demands a
    # durable qualification artifact under .saipen/ whose digest matches, so
    # the original dict-shaped fixture returned NOT_QUALIFIED and proved
    # nothing. Write the artifact the contract actually asks for.
    rel = f".saipen/campaign/qualifications/QUAL-PAL-DUP.json"
    art = p / rel
    art.parent.mkdir(parents=True, exist_ok=True)
    art.write_text(json.dumps({"receipt_id": "QUAL-PAL-DUP"}), encoding="utf-8")
    finding = {
        "finding_id": "PAL-DUP",
        "state": "QUALIFIED",
        "qualification_receipt": {
            "receipt_id": "QUAL-PAL-DUP",
            "artifact_path": rel,
            "artifact_digest": hashlib.sha256(art.read_bytes()).hexdigest(),
        },
        "audit_body": body,
        "artifact_digest": digest,
    }
    r1 = adapter.deliver_finding_to_audit_inbox(p, finding, publication_authorized=True)
    r2 = adapter.deliver_finding_to_audit_inbox(p, finding, publication_authorized=True)
    hist = adapter.collect_publication_receipts(p)
    return {
        "first": r1.get("status"),
        "second": r2.get("status"),
        "second_idempotent_replay": r2.get("idempotent_replay"),
        "receipt_rows": len(hist.get("records", [])),
    }


def perf_003(tmp: Path):
    """Per-transition cost: one journal append, NOT a whole-ledger checkpoint.

    The original probe called `_save_dispatch_ledger` twice, but that function
    is the checkpoint/rewrite API (fixtures, recovery, migration) and is
    expected to write the whole mapping. The ordinary path is
    `dispatch_next_turn`. A durable transition appends through a raw fsynced
    `os.write`, so this measures journal GROWTH per dispatch: it must stay flat
    as history accumulates, which is the property R026 requires.
    """
    p = project(tmp)
    campaign_dir = p / ".saipen" / "campaign"
    journal = campaign_dir / host_dispatch.DISPATCH_LEDGER_JOURNAL

    def dispatch(index: int) -> int:
        payload = host_dispatch.build_dispatch_payload(
            p, campaign_id="C-PERF", iteration_id=index
        )
        receipt = {
            "schema_version": 1,
            "status": host_dispatch.HOST_ACCEPTED,
            "accepting_host": "probe_host",
            "campaign_id": payload["campaign_id"],
            "iteration_id": payload["iteration_id"],
            "worker_generation": payload["worker_generation"],
            "idempotency_key": payload["idempotency_key"],
            "project_lineage": payload["project_lineage"],
            "accepted_request_id": payload["idempotency_key"],
        }
        before = journal.stat().st_size if journal.exists() else 0
        host_dispatch.dispatch_next_turn(
            p, dict(payload), host_hook=lambda pl: receipt, print_advisory=False
        )
        after = journal.stat().st_size if journal.exists() else 0
        return after - before

    early = [dispatch(i) for i in range(1, 4)]
    for i in range(4, 121):
        dispatch(i)
    late = [dispatch(i) for i in range(121, 124)]
    return {
        "journal_bytes_per_dispatch_early": early,
        "journal_bytes_per_dispatch_late": late,
        # A 4-byte drift is the iteration_id itself widening from 1 to 3
        # digits inside the appended record. History contributes nothing: the
        # old whole-ledger writer was at 72 KB per operation by 1000 ops.
        "record_sized_not_history_sized": max(late) <= max(early) + 64,
    }


def perf_005(tmp: Path):
    # supervisor.py did `from .board import parse_board`, so patching the
    # attribute on `board` was invisible to it and the original probe measured
    # zero. Patch the name supervisor actually holds.
    calls = []
    original = supervisor.parse_board

    def counting(text):
        calls.append(1)
        return original(text)

    supervisor.parse_board = counting
    try:
        p = project(tmp)
        supervisor.observe(p)
    finally:
        supervisor.parse_board = original
    return {"parse_board_calls": len(calls)}


def perf_007():
    """Bounded detection state: retention caps history, counters keep the tally."""
    # max_iterations high enough that the cap never fires, so the only bound
    # under test is retention. The probe must therefore exceed retention.
    t = autonomy.ProgressTracker(max_iterations=10_000)
    for i in range(5_000):
        t.record("s", "a", "r", "c")
    return {
        "iterations": t.iterations,
        "history_len": len(t.history),
        "retention": t.retention,
        "dropped": t.dropped,
        "bounded": len(t.history) <= t.retention,
        "observation_count": t.counters["observations"],
        "last_action": t.history[-1].action if t.history else None,
    }


def main():
    out = {}
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        for name, fn in (("W2-004", w2_004), ("CORE-012", core_012), ("W2-007", w2_007),
                         ("PERF-003", perf_003), ("PERF-005", perf_005)):
            d = base / name
            d.mkdir()
            try:
                out[name] = fn(d)
            except Exception as exc:
                out[name] = {"raised": type(exc).__name__, "detail": str(exc)}
        out["PERF-007"] = perf_007()
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
