"""T-1298 SRC-025 W2 reproductions against the LIVE v8.0.0 implementation.

Disposable temp projects only; the live tree is never mutated.
"""

import json
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import audit_enqueue, audit_inbox  # noqa: E402

OUT = []


def note(name, **kw):
    OUT.append({"probe": name, **kw})


def fresh(tmp: Path, name: str = "proj") -> Path:
    proj = tmp / f"{name}-{len([x for x in tmp.iterdir()])}"
    (proj / ".saipen" / "intake").mkdir(parents=True)
    (proj / ".saipen" / "locks").mkdir(parents=True)
    return proj


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t1298-w2-") as td:
        tmp = Path(td)

        # --- R005 / W2-001: allocator loss, independent op, equal bytes ---
        p = fresh(tmp, "p")
        r1 = audit_enqueue.enqueue(p, producer="audapack", body=b"X", producer_operation_id="op-1")
        (p / ".saipen/intake/audit_allocator.json").unlink()
        r2 = audit_enqueue.enqueue(p, producer="audapack", body=b"X", producer_operation_id="op-2")
        note(
            "W2-001-allocator-loss-equal-bytes",
            first=r1.get("layer"),
            second=r2.get("layer"),
            second_idempotent=r2.get("idempotent"),
            second_recovered_from=r2.get("recovered_from"),
        )

        # --- R005 / W2-001 stronger: virgin manual drop, first API op same bytes ---
        p2 = fresh(tmp, "p2")
        (p2 / "audit").mkdir()
        (p2 / "audit/99.md").write_bytes(b"X")
        r3 = audit_enqueue.enqueue(p2, producer="audapack", body=b"X", producer_operation_id="first-api-op")
        note(
            "W2-001-virgin-manual-99",
            layer=r3.get("layer"),
            idempotent=r3.get("idempotent"),
            recovered_from=r3.get("recovered_from"),
        )

        # --- R006 / W2-002: COMMITTED + layer absent ---
        p3 = fresh(tmp, "p3")
        ra = audit_enqueue.enqueue(p3, producer="audapack", body=b"Y", producer_operation_id="op-1")
        (p3 / "audit/1.md").unlink()  # vanished BEFORE capture, no binding
        rb = audit_enqueue.enqueue(p3, producer="audapack", body=b"Y", producer_operation_id="op-1")
        note(
            "W2-002-committed-absent-no-binding",
            retry_code=rb.get("code"),
            retry_ok=rb.get("ok"),
        )

        # case 3/4: absent layer + exact binding
        p4 = fresh(tmp, "p4")
        rc = audit_enqueue.enqueue(p4, producer="audapack", body=b"Z", producer_operation_id="op-1")
        (p4 / "audit/1.md").unlink()
        digest = audit_enqueue.layer_digest(b"Z")
        doc = {"schema_version": 1, "layers": {}}
        doc["layers"]["audit/1.md"] = {
            "layer": 1,
            "generation": 1,
            "file_sha256": digest,
            "receipt_sha256": digest,
            "binding": "exact",
            "size_bytes": 1,
            "receipt_id": "SRC-900",
            "linked_work": "T-900",
            "state": "ACTIVE",
            "captured_at": "2026-09-07T00:00:00Z",
            "closed_at": None,
        }
        (p4 / ".saipen/intake/audit_inbox.json").write_text(json.dumps(doc), encoding="utf-8")
        rd = audit_enqueue.enqueue(p4, producer="audapack", body=b"Z", producer_operation_id="op-1")
        note("W2-002-absent-binding-ACTIVE", code=rd.get("code"), ok=rd.get("ok"), binding_state=rd.get("binding_state"))
        # DELETED variant
        p5 = fresh(tmp, "p5")
        audit_enqueue.enqueue(p5, producer="audapack", body=b"Z", producer_operation_id="op-1")
        (p5 / "audit/1.md").unlink()
        doc2 = json.loads(json.dumps(doc))
        doc2["layers"]["audit/1.md"]["state"] = "DELETED"
        (p5 / ".saipen/intake/audit_inbox.json").write_text(json.dumps(doc2), encoding="utf-8")
        re_ = audit_enqueue.enqueue(p5, producer="audapack", body=b"Z", producer_operation_id="op-1")
        note("W2-002-absent-binding-DELETED", code=re_.get("code"), ok=rd.get("ok"), binding_state=re_.get("binding_state"))
        # same path different digest
        p6 = fresh(tmp, "p6")
        audit_enqueue.enqueue(p6, producer="audapack", body=b"Z", producer_operation_id="op-1")
        (p6 / "audit/1.md").unlink()
        doc3 = json.loads(json.dumps(doc))
        doc3["layers"]["audit/1.md"]["file_sha256"] = "f" * 64
        (p6 / ".saipen/intake/audit_inbox.json").write_text(json.dumps(doc3), encoding="utf-8")
        rf = audit_enqueue.enqueue(p6, producer="audapack", body=b"Z", producer_operation_id="op-1")
        note("W2-002-same-path-different-digest", code=rf.get("code"), ok=rf.get("ok"))
        # corrupt binding
        p7 = fresh(tmp, "p7")
        audit_enqueue.enqueue(p7, producer="audapack", body=b"Z", producer_operation_id="op-1")
        (p7 / "audit/1.md").unlink()
        (p7 / ".saipen/intake/audit_inbox.json").write_text("{broken", encoding="utf-8")
        rg_ = audit_enqueue.enqueue(p7, producer="audapack", body=b"Z", producer_operation_id="op-1")
        note("W2-002-corrupt-binding", code=rg_.get("code"), ok=rg_.get("ok"))

        # --- R007 / W2-003: concurrent bind_layer different layers ---
        p8 = fresh(tmp, "p8")
        outcomes = []

        def bind(rel, layer):
            try:
                audit_inbox.bind_layer(
                    p8,
                    rel,
                    layer=layer,
                    generation=1,
                    file_sha256=audit_enqueue.layer_digest(rel.encode()),
                    size_bytes=3,
                    receipt_id="SRC-910",
                    receipt_sha256=audit_enqueue.layer_digest(rel.encode()),
                    binding="exact",
                    linked_work=None,
                    state="ACTIVE",
                )
                outcomes.append(("ok", layer))
            except Exception as exc:  # noqa: BLE001
                outcomes.append(("exc", f"{type(exc).__name__}: {exc}"))

        threads = [threading.Thread(target=bind, args=(f"audit/{n}.md", n)) for n in (1, 2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        persisted = sorted((audit_inbox.read_binding_state(p8)[0].get("layers") or {}).keys())
        note("W2-003-concurrent-bind", outcomes=sorted(outcomes), persisted=persisted)

        # --- R008 / W2-004: allocator record layer=true ---
        p9 = fresh(tmp, "p9")
        audit_enqueue.enqueue(p9, producer="audapack", body=b"L", producer_operation_id="op-1")
        alloc_path = p9 / ".saipen/intake/audit_allocator.json"
        alloc = json.loads(alloc_path.read_text(encoding="utf-8"))
        alloc["operations"]["audapack op-1"]["layer"] = True
        alloc_path.write_text(json.dumps(alloc), encoding="utf-8")
        doc_state, state = audit_enqueue.read_allocator_state(p9)
        rh = audit_enqueue.enqueue(p9, producer="audapack", body=b"L", producer_operation_id="op-1")
        true_md = (p9 / "audit/True.md").exists()
        note(
            "W2-004-layer-true",
            read_state=state,
            retry_code=rh.get("code"),
            retry_layer=rh.get("layer"),
            created_audit_True_md=true_md,
        )

        # --- R009 / W2-005: symlinked audit dir ---
        p10 = fresh(tmp, "p10")
        outside = tmp / "outside"
        outside.mkdir()
        (outside / "1.md").write_bytes(b"HOSTILE")
        (p10 / "audit").symlink_to(outside, target_is_directory=True)
        layers = audit_inbox.scan_layers(p10)
        residue = audit_inbox.scan_residue(p10)
        cls = audit_inbox.classify(p10)
        st = audit_inbox.status(p10)
        note(
            "W2-005-symlink-audit-dir",
            layers=layers,
            residue=residue,
            classify_ok=cls.get("ok"),
            status_ok=st.get("ok"),
            status_clean=st.get("clean"),
        )

        # unreadable directory is hard to reproduce portably on Windows; skip live,
        # rely on code-path inspection + test monkeypatch.

    for row in OUT:
        print(json.dumps(row, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
