"""R021/W2-008 red-before/green-after controls for append-log reconciliation.

Each probe builds an isolated project fixture, damages one history log in one
specific way, and asserts the integrity status plus the repair outcome.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from saipen_engine import audit_enqueue, saipal_adapter as SA  # noqa: E402


def project() -> Path:
    root = Path(tempfile.mkdtemp(prefix="saipen-hist-"))
    (root / ".saipen" / "campaign").mkdir(parents=True, exist_ok=True)
    (root / ".saipen" / "locks").mkdir(parents=True, exist_ok=True)
    (root / "audit").mkdir(parents=True, exist_ok=True)
    return root


def line(row) -> bytes:
    return (json.dumps(row, sort_keys=True) + "\n").encode("utf-8")


def publish(root: Path, finding_id: str, body: str):
    """Produce one genuine publication: canonical enqueue plus receipt."""
    adapter = SA.SaipalAdapter(saipal_home=root)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    qual = f"QUAL-{finding_id}"
    qpath = root / ".saipen" / "campaign" / "qualifications" / f"{qual}.json"
    qpath.parent.mkdir(parents=True, exist_ok=True)
    qpath.write_text(json.dumps({"receipt_id": qual}), encoding="utf-8")
    finding = {
        "finding_id": finding_id,
        "state": "QUALIFIED",
        "qualification_receipt": {
            "receipt_id": qual,
            "artifact_path": qpath.relative_to(root).as_posix(),
            "qualification_digest": hashlib.sha256(qpath.read_bytes()).hexdigest(),
        },
        "audit_body": body,
        "artifact_digest": digest,
    }
    return adapter.deliver_finding_to_audit_inbox(root, finding, publication_authorized=True)


def probe_valid_log_reads_completely():
    root = project()
    publish(root, "PAL-H1", "# Audit H1\n")
    publish(root, "PAL-H2", "# Audit H2\n")
    adapter = SA.SaipalAdapter(saipal_home=root)
    res = adapter.collect_receipts_with_integrity(root)
    return {
        "status": res["status"],
        "record_count": len(res["records"]),
        "complete": res["ok"] and len(res["records"]) == 2,
    }


def probe_malformed_middle_record():
    root = project()
    # Two valid records, then garbage, then another valid record: the damaged
    # record is in the MIDDLE, so "read the prefix and stop" would silently
    # declare the trailing valid record absent.
    path = root / ".saipen" / "campaign" / "saipal_receipts.jsonl"
    path.write_bytes(
        line({"operation_id": "op-1", "finding_id": "PAL-A", "layer": 1})
        + b"{not json at all}\n"
        + line({"operation_id": "op-2", "finding_id": "PAL-B", "layer": 2})
    )
    adapter = SA.SaipalAdapter(saipal_home=root)
    res = adapter.collect_receipts_with_integrity(root)
    return {
        "status": res["status"],
        "valid_prefix_records": len(res["records"]),
        "error_line": res.get("error_line"),
        "damaged_hex_present": bool(res.get("damaged_record_hex")),
        "trailing_valid_record_still_on_disk": b"op-2" in path.read_bytes(),
        "declared_complete": res["ok"],
    }


def probe_torn_final_record():
    root = project()
    path = root / ".saipen" / "campaign" / "dispositions.jsonl"
    path.write_bytes(
        line({"finding_id": "PAL-A", "disposition": "VERIFIED"}) + b'{"finding_id": "PAL-B", "disp'
    )
    adapter = SA.SaipalAdapter(saipal_home=root)
    res = adapter.collect_dispositions_with_integrity(root)
    return {
        "status": res["status"],
        "valid_prefix_records": len(res["records"]),
        "ok": res["ok"],
        "suffix_status": res.get("suffix_status"),
    }


def probe_absent_log():
    root = project()
    adapter = SA.SaipalAdapter(saipal_home=root)
    res = adapter.collect_receipts_with_integrity(root)
    return {"status": res["status"], "ok": res["ok"], "record_count": len(res["records"])}


def probe_damaged_bytes_preserved():
    root = project()
    path = root / ".saipen" / "campaign" / "saipal_receipts.jsonl"
    damaged = b"\x00\xff broken bytes \xfe\n"
    path.write_bytes(line({"operation_id": "op-1", "finding_id": "PAL-A", "layer": 1}) + damaged)
    adapter = SA.SaipalAdapter(saipal_home=root)
    res = adapter.reconcile_history(root, kind="publication_receipts")
    quarantine = res.get("quarantine") or {}
    preserved = root / quarantine["path"] if quarantine.get("path") else None
    matches = bool(preserved and preserved.is_file() and preserved.read_bytes() == damaged)
    return {
        "status": res["status"],
        "quarantine_path": quarantine.get("path"),
        "original_damaged_bytes_recoverable": matches,
        "quarantine_digest": quarantine.get("digest"),
    }


def probe_reconcile_publication_receipts():
    root = project()
    first = publish(root, "PAL-R1", "# Audit R1\n")
    second = publish(root, "PAL-R2", "# Audit R2\n")
    path = root / ".saipen" / "campaign" / "saipal_receipts.jsonl"
    # Damage the log so the receipt file is not a complete canonical result.
    path.write_bytes(path.read_bytes() + b'{"finding_id": "PAL-HALF"')
    adapter = SA.SaipalAdapter(saipal_home=root)
    before = adapter.collect_receipts_with_integrity(root)
    res = adapter.reconcile_history(root, kind="publication_receipts")
    after = adapter.collect_receipts_with_integrity(root)
    by_op = {r.get("operation_id"): r for r in after["records"]}
    return {
        "status_before": before["status"],
        "status_after": after["status"],
        "reconciled_ok": res["ok"],
        "layer_r1": first.get("receipt", {}).get("layer"),
        "layer_r2": second.get("receipt", {}).get("layer"),
        "r1_receipt_present_after": f"saipal-pal-r1" in by_op,
        "r2_receipt_present_after": f"saipal-pal-r2" in by_op,
        "recovered_records": res.get("recovered_records"),
        "preserved_records": res.get("preserved_records"),
    }


def probe_reconcile_does_not_invent_dispositions():
    root = project()
    path = root / ".saipen" / "campaign" / "dispositions.jsonl"
    path.write_bytes(line({"finding_id": "PAL-A", "disposition": "VERIFIED"}) + b'{"finding_id":"PAL-B"')
    adapter = SA.SaipalAdapter(saipal_home=root)
    res = adapter.reconcile_history(root, kind="dispositions")
    return {
        "status": res["status"],
        "ok": res["ok"],
        "records_after": len(res.get("records") or []),
        "recovered_records": res.get("recovered_records"),
        "invented_disposition": len(res.get("records") or []) > 1,
        "recovery_note_present": bool(res.get("recovery_note")),
    }


def probe_reconcile_refuses_without_authority():
    """A damaged receipt whose enqueue is only RESERVED must not be rebuilt."""
    root = project()
    # A layer file exists, but the allocator never reached COMMITTED.
    (root / "audit" / "7.md").write_bytes(b"# Audit seven\n")
    digest = hashlib.sha256(b"# Audit seven\n").hexdigest()
    audit_enqueue.write_allocator(
        root,
        {
            "schema_version": 1,
            "next_id": 8,
            "operations": {
                "saipal saipal-pal-sev": {
                    "layer": 7,
                    "producer": "saipal",
                    "producer_operation_id": "saipal-pal-sev",
                    "producer_item_id": "PAL-SEV",
                    "created_at": "2026-01-01T00:00:00Z",
                    "sha256": digest,
                    "state": "RESERVED",
                }
            },
        },
    )
    path = root / ".saipen" / "campaign" / "saipal_receipts.jsonl"
    path.write_bytes(b"{broken\n")
    adapter = SA.SaipalAdapter(saipal_home=root)
    res = adapter.reconcile_history(root, kind="publication_receipts")
    return {
        "status": res["status"],
        "recovered_records": res.get("recovered_records"),
        "invented_receipt_from_reserved": len(res.get("records") or []) > 0,
        "unrecoverable": res.get("unrecoverable_operations"),
    }


def probe_crash_after_enqueue_reconstructs_receipt():
    """Enqueue committed, receipt append never happened: must be recoverable."""
    root = project()
    published = publish(root, "PAL-CRASH", "# Audit crash-after-enqueue\n")
    assert published.get("ok"), published
    path = root / ".saipen" / "campaign" / "saipal_receipts.jsonl"
    path.unlink()  # simulate the lost append
    adapter = SA.SaipalAdapter(saipal_home=root)
    before = adapter.collect_receipts_with_integrity(root)
    res = adapter.reconcile_history(root, kind="publication_receipts")
    after = adapter.collect_receipts_with_integrity(root)
    ops = [r.get("operation_id") for r in after["records"]]
    return {
        "status_before": before["status"],
        "status_after": after["status"],
        "recovered_records": res.get("recovered_records"),
        "receipt_reconstructed": "saipal-pal-crash" in ops,
        "duplicate_receipt_count": ops.count("saipal-pal-crash"),
        "layer": (res.get("records") or [{}])[0].get("layer"),
    }


def probe_crash_before_enqueue_claims_nothing():
    """No allocator record means no publication; reconciliation must stay empty."""
    root = project()
    adapter = SA.SaipalAdapter(saipal_home=root)
    res = adapter.reconcile_history(root, kind="publication_receipts")
    return {
        "status": res["status"],
        "ok": res["ok"],
        "repaired": res["repaired"],
        "records": len(res.get("records") or []),
        "claimed_delivery_without_enqueue": bool(res.get("records")),
    }


def probe_reconcile_is_idempotent():
    root = project()
    publish(root, "PAL-IDEM", "# Audit idempotent\n")
    path = root / ".saipen" / "campaign" / "saipal_receipts.jsonl"
    path.write_bytes(path.read_bytes() + b'{"partial":')
    adapter = SA.SaipalAdapter(saipal_home=root)
    first = adapter.reconcile_history(root, kind="publication_receipts")
    second = adapter.reconcile_history(root, kind="publication_receipts")
    records = second.get("records") or []
    ops = [r.get("operation_id") for r in records]
    return {
        "first_status": first["status"],
        "second_status": second["status"],
        "second_repaired": second["repaired"],
        "record_count": len(records),
        "duplicate_operations": len(ops) - len(set(ops)),
    }


def probe_concurrent_append_and_read():
    """Concurrent writers must not interleave records; readers never see half."""
    import threading

    root = project()
    adapter = SA.SaipalAdapter(saipal_home=root)
    path = root / ".saipen" / "campaign" / "dispositions.jsonl"
    errors: list[str] = []
    written: list[int] = []

    def writer(index: int) -> None:
        try:
            res = SA._append_history(
                root, "dispositions.jsonl", {"finding_id": f"PAL-C{index}", "index": index}
            )
            if not res.get("ok"):
                errors.append(res.get("status", "unknown"))
            else:
                written.append(index)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    final = adapter.collect_dispositions_with_integrity(root)
    parsed = final.get("records") or []
    indexes = [r.get("index") for r in parsed]
    return {
        "writers_succeeded": len(written),
        "write_errors": errors,
        "final_status": final["status"],
        "parsed_records": len(parsed),
        "unique_records": len(set(indexes)),
        "torn_or_interleaved": final["status"] != "LOG_VALID" or len(parsed) != len(set(indexes)),
    }


PROBES = {
    "valid_log_reads_completely": probe_valid_log_reads_completely,
    "malformed_middle_record": probe_malformed_middle_record,
    "torn_final_record": probe_torn_final_record,
    "absent_log": probe_absent_log,
    "damaged_bytes_preserved": probe_damaged_bytes_preserved,
    "reconcile_publication_receipts": probe_reconcile_publication_receipts,
    "reconcile_does_not_invent_dispositions": probe_reconcile_does_not_invent_dispositions,
    "reconcile_refuses_without_authority": probe_reconcile_refuses_without_authority,
    "crash_after_enqueue_reconstructs_receipt": probe_crash_after_enqueue_reconstructs_receipt,
    "crash_before_enqueue_claims_nothing": probe_crash_before_enqueue_claims_nothing,
    "reconcile_is_idempotent": probe_reconcile_is_idempotent,
    "concurrent_append_and_read": probe_concurrent_append_and_read,
}


if __name__ == "__main__":
    out = {}
    for name, fn in PROBES.items():
        try:
            out[name] = fn()
        except Exception as exc:  # noqa: BLE001 - a probe failure is the measurement
            out[name] = {"probe_error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(out, indent=2))
