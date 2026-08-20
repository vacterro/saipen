"""Regression tests for the SAIPEN AUDIT SECOND WAVE receipt-scanner fixes.

These pin the W2-001 / W2-002 / W2-003 / W2-005 repairs that the
operations-side (claim/handover/goal) 48/48 suite does not exercise:

  * W2-001 -- journal._scan_receipt_namespace routes every candidate through the
    ONE strict decoder; corrupt evidence is surfaced (not silently skipped);
    a duplicate op_id across ops/settled collapses only when both sides are
    equivalent terminal receipts.
  * W2-002 -- release / subs / journal scanners read BOTH recovery/ops and
    recovery/settled; sub_sync returns the ACTUAL receipt path, not a
    reconstructed recovery/ops guess.
  * W2-003 -- release recovery returns ALREADY_APPLIED only when BOTH the
    generic status AND release_stage are COMMITTED; a split truth is
    RELEASE_STAGE_INCOMPLETE.
  * W2-005 -- compact_committed drops staged payloads and removes the cleanup
    marker only after proving no staged payload remains; a failed drop retains
    the marker for retry.

Run standalone:
    python tools/test_second_wave_receipt_fixes.py

Exit code 0 when every assertion passes; 1 on the first failure batch.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest.mock as mock
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.journal import (  # noqa: E402
    OPS_DIR,
    SETTLED_DIR,
    compact_committed,
    semantic_receipt_snapshot,
)
from saipen_engine.release import (  # noqa: E402
    _committed_release_receipts,
    recover_release_op,
)
from saipen_engine.subs import _latest_sub_sync_inventory  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL"), name, ("" if cond else f"-- {detail}"))


# A minimal but strictly-valid target: role "generic" + action "write" with an
# owned .saipen path. A COMMITTED (settled) receipt needs no staged evidence.
_TARGET = {
    "path": ".saipen/kitchen/_receipt_test.json",
    "role": "generic",
    "before_hash": "",
    "after_hash": "x",
    "applied": True,
    "action": "write",
    "content": "{}",
}


def _write_receipt(
    root: Path,
    op_id: str,
    operation: str,
    status: str = "COMMITTED",
    ns: str = "ops",
    extra: dict | None = None,
) -> dict:
    """Write a strictly-valid operation.json under recovery/ops or
    recovery/settled for op_id, returning the record dict."""
    base = root / (OPS_DIR if ns == "ops" else SETTLED_DIR) / op_id
    base.mkdir(parents=True, exist_ok=True)
    rec = {
        "op_id": op_id,
        "status": status,
        "operation": operation,
        "semantic_payload_hash": "x",
        "created_at": "2026-08-20T00:00:00Z",
        "agent": "test-agent",
        "project_identity": "test-project",
        "verification_policy": "none",
        "preconditions": {},
        "progress_index": 0,
        "targets": [dict(_TARGET)],
    }
    if extra:
        rec.update(extra)
    (base / "operation.json").write_text(json.dumps(rec))
    return rec


def test_w2001_scanner() -> None:
    # (a) malformed receipt -> surfaced as error, never trusted as evidence.
    root = Path(tempfile.mkdtemp())
    bad = root / OPS_DIR / "bad1"
    bad.mkdir(parents=True)
    (bad / "operation.json").write_text("}{ not json")
    records, errors = semantic_receipt_snapshot(root)
    check("W2-001 malformed receipt surfaced as error", any("bad1" in e for e in errors), str(errors))
    check(
        "W2-001 malformed receipt not selected as evidence",
        all(r.get("op_id") != "bad1" for r in records),
    )

    # (b) equivalent duplicate across ops+settled collapses to ONE record.
    root2 = Path(tempfile.mkdtemp())
    payload = {"semantic_payload_hash": "h-eq", "created_at": "2026-08-20T01:00:00Z"}
    _write_receipt(root2, "dup", "converge_intent", ns="ops", extra=payload)
    _write_receipt(root2, "dup", "converge_intent", ns="settled", extra=payload)
    records2, errors2 = semantic_receipt_snapshot(root2)
    ops = [r for r in records2 if r.get("op_id") == "dup"]
    check("W2-001 equivalent duplicate collapses to one", len(ops) == 1, f"count={len(ops)} errors={errors2}")

    # (c) non-equivalent duplicate -> corrupt evidence, NEITHER selected.
    root3 = Path(tempfile.mkdtemp())
    _write_receipt(root3, "dup2", "converge_intent", ns="ops", extra={"semantic_payload_hash": "h-a"})
    _write_receipt(root3, "dup2", "converge_intent", ns="settled", extra={"semantic_payload_hash": "h-b"})
    records3, errors3 = semantic_receipt_snapshot(root3)
    check(
        "W2-001 non-equivalent duplicate reported corrupt",
        any("dup2" in e for e in errors3),
        str(errors3),
    )
    check(
        "W2-001 non-equivalent duplicate not selected",
        all(r.get("op_id") != "dup2" for r in records3),
    )


def test_w2002_ops_settled() -> None:
    # (a) settled release receipt is visible to crew finalize.
    root = Path(tempfile.mkdtemp())
    _write_receipt(
        root,
        "rel-1",
        "release",
        ns="settled",
        extra={"release_stage": "COMMITTED", "crew_epoch": "EPOCH-1"},
    )
    out = _committed_release_receipts(root)
    check("W2-002 settled release receipt discovered", any(r.get("op_id") == "rel-1" for r in out), str(out))

    # (b) ops release receipt still discovered (no regression).
    root2 = Path(tempfile.mkdtemp())
    _write_receipt(
        root2,
        "rel-2",
        "release",
        ns="ops",
        extra={"release_stage": "COMMITTED", "crew_epoch": "EPOCH-2"},
    )
    out2 = _committed_release_receipts(root2)
    check("W2-002 ops release receipt still discovered", any(r.get("op_id") == "rel-2" for r in out2))

    # (c) settled sub_sync receipt found with the ACTUAL settled path.
    inv = [{"path": "TEMPLATE", "kind": "directory", "source_hash": "delete-tree-sha256:" + "0" * 64}]
    root3 = Path(tempfile.mkdtemp())
    _write_receipt(root3, "sync-1", "sub_sync", ns="settled", extra={"receipt_metadata": {"owned_source_inventory": inv}})
    receipt, _inv, lineage = _latest_sub_sync_inventory(root3)
    check("W2-002 settled sub_sync discovered", receipt is not None and lineage == "ok", f"lineage={lineage}")
    check(
        "W2-002 sub_sync path is the actual settled path",
        receipt is not None and receipt.get("_receipt_path", "").startswith(SETTLED_DIR),
        str(receipt.get("_receipt_path") if receipt else None),
    )

    # (d) ops sub_sync still found (no regression).
    root4 = Path(tempfile.mkdtemp())
    _write_receipt(root4, "sync-2", "sub_sync", ns="ops", extra={"receipt_metadata": {"owned_source_inventory": inv}})
    receipt4, _inv4, lineage4 = _latest_sub_sync_inventory(root4)
    check("W2-002 ops sub_sync still discovered", receipt4 is not None and lineage4 == "ok", f"lineage={lineage4}")


def test_w2003_terminalization() -> None:
    # (a) fully committed (generic + release_stage) -> ALREADY_APPLIED.
    root = Path(tempfile.mkdtemp())
    _write_receipt(root, "rel-f", "release", ns="ops", extra={"release_stage": "COMMITTED"})
    res = recover_release_op(root, "rel-f")
    check("W2-003 fully committed release returns ALREADY_APPLIED", res.get("code") == "ALREADY_APPLIED", str(res))

    # (b) split truth (generic COMMITTED, stage not COMMITTED) -> NOT
    # ALREADY_APPLIED; RELEASE_STAGE_INCOMPLETE instead.
    root2 = Path(tempfile.mkdtemp())
    _write_receipt(root2, "rel-p", "release", ns="ops", extra={"release_stage": "CONTENT_COMMIT_CREATED"})
    res2 = recover_release_op(root2, "rel-p")
    check("W2-003 partial release is NOT ALREADY_APPLIED", res2.get("code") != "ALREADY_APPLIED", str(res2))
    check(
        "W2-003 partial release returns RELEASE_STAGE_INCOMPLETE",
        res2.get("code") == "RELEASE_STAGE_INCOMPLETE",
        str(res2),
    )


def test_w2005_cleanup_debt() -> None:
    # (a) success path: staged payload removed, marker cleared, entry compacted.
    root = Path(tempfile.mkdtemp())
    _write_receipt(root, "clean1", "converge_intent", ns="settled")
    entry = root / SETTLED_DIR / "clean1"
    (entry / "leftover.staged").write_text("payload")
    marker_dir = root / SETTLED_DIR / ".cleanup-needed"
    marker_dir.mkdir(parents=True)
    (marker_dir / "clean1").write_text("")
    res = compact_committed(root)
    check("W2-005 staged payload removed on success", not (entry / "leftover.staged").exists())
    check("W2-005 cleanup marker cleared on success", not (marker_dir / "clean1").exists())
    check("W2-005 entry reported compacted", "clean1" in res["compacted"], str(res))

    # (b) debt path: a failed unlink retains the staged payload AND the marker
    # and reports the entry as skipped (never compacted).
    root2 = Path(tempfile.mkdtemp())
    _write_receipt(root2, "clean2", "converge_intent", ns="settled")
    entry2 = root2 / SETTLED_DIR / "clean2"
    staged2 = entry2 / "leftover.staged"
    staged2.write_text("payload")
    marker_dir2 = root2 / SETTLED_DIR / ".cleanup-needed"
    marker_dir2.mkdir(parents=True)
    (marker_dir2 / "clean2").write_text("")

    def _boom(self, *a, **k):  # noqa: ANN001
        raise OSError("simulated device busy")

    with mock.patch.object(Path, "unlink", _boom):
        res2 = compact_committed(root2)
    check("W2-005 failed unlink retains staged payload", staged2.exists())
    check("W2-005 failed unlink retains cleanup marker", (marker_dir2 / "clean2").exists())
    check("W2-005 entry reported skipped (debt)", "clean2" in res2["skipped"], str(res2))
    check(
        "W2-005 entry NOT compacted while in debt",
        "clean2" not in res2["compacted"],
        str(res2),
    )


def main() -> int:
    test_w2001_scanner()
    test_w2002_ops_settled()
    test_w2003_terminalization()
    test_w2005_cleanup_debt()

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n{passed}/{total} SECOND-WAVE receipt regressions passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
