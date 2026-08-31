"""Shared audit enqueue producer API (T-1230, SOURCE-AUDIT-ENQUEUE-01).

The acceptance bar of the Wave 6 roadmap doc
(`.saipen/KNOWLEDGE/roadmaps/next-2026-08-31/08_WAVE_6_SHARED_PRODUCER_API.md`): monotonic ids
that survive deletion, no collision between concurrent producers, an
idempotent retry, no overwrite and no path escape, a manual high-numbered drop
that advances the allocator instead of being clobbered, and a layer the native
inbox consumes with no special case.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import audit_enqueue, audit_inbox  # noqa: E402

SCENARIO = ROOT / "tests" / "scenarios" / "userperson-valid" / ".saipen"

BODY = b"# producer audit\n\nA finding.\n"


class EnqueueFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-audit-enqueue-")
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")
        (self.root / ".saipen" / "USERPERSON.md").unlink(missing_ok=True)
        self.config = Path(self.tmp.name) / "user-config"
        self.env = patch.dict(os.environ, {"SAIPEN_USER_CONFIG_HOME": str(self.config)})
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    def enqueue(self, op: str, body: bytes = BODY, producer: str = "audapack", **kw) -> dict:
        return audit_enqueue.enqueue(
            self.root,
            producer=producer,
            body=body,
            producer_operation_id=op,
            **kw,
        )

    def allocator(self) -> dict:
        return json.loads(
            (self.root / ".saipen" / "intake" / "audit_allocator.json").read_text("utf-8")
        )


class Allocation(EnqueueFixture):
    def test_first_enqueue_is_layer_one_and_places_exact_bytes(self) -> None:
        result = self.enqueue("op-1")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["layer"], 1)
        self.assertEqual(result["rel"], "audit/1.md")
        target = self.root / "audit" / "1.md"
        self.assertEqual(target.read_bytes(), BODY)
        self.assertEqual(result["sha256"], hashlib.sha256(BODY).hexdigest())

    def test_ids_are_monotonic_and_never_reuse_a_deleted_number(self) -> None:
        self.assertEqual(self.enqueue("op-1")["layer"], 1)
        self.assertEqual(self.enqueue("op-2")["layer"], 2)
        # A consumed layer is gone from the directory. The next allocation
        # must NOT fall back into the hole -- provenance keys on the number.
        (self.root / "audit" / "1.md").unlink()
        self.assertEqual(self.enqueue("op-3")["layer"], 3)

    def test_a_number_consumed_before_this_allocator_existed_is_never_reissued(self) -> None:
        """The binding outlives the file, and the allocator has to read it.

        A project that consumed `audit/1..3` through the journaled cleanup has
        an EMPTY directory and no allocator operations. A floor derived from
        the disk alone would hand `1` back out, and every provenance record
        keyed on `audit/1.md` would then name two different audits.
        """
        for layer in (1, 2, 3):
            audit_inbox.bind_layer(
                self.root,
                f"audit/{layer}.md",
                layer=layer,
                generation=1,
                file_sha256="a" * 64,
                size_bytes=1,
                receipt_id=f"SRC-{layer:03d}",
                receipt_sha256="a" * 64,
                binding="exact",
                linked_work=None,
                state=audit_inbox.DELETED,
            )
        self.assertEqual(list((self.root / "audit").glob("*.md")), [])
        self.assertEqual(self.enqueue("op-1")["layer"], 4)

    def test_manual_high_drop_advances_the_allocator_and_is_not_overwritten(self) -> None:
        manual = self.root / "audit" / "99.md"
        manual.parent.mkdir(parents=True, exist_ok=True)
        manual.write_bytes(b"# hand-dropped\n")
        result = self.enqueue("op-1")
        self.assertEqual(result["layer"], 100)
        self.assertEqual(manual.read_bytes(), b"# hand-dropped\n")

    def test_no_temp_file_survives_a_successful_enqueue(self) -> None:
        self.enqueue("op-1")
        leftovers = [p.name for p in (self.root / "audit").iterdir() if p.name.startswith(".")]
        self.assertEqual(leftovers, [])


class Idempotency(EnqueueFixture):
    def test_retry_with_same_operation_id_returns_the_original_allocation(self) -> None:
        first = self.enqueue("op-1")
        again = self.enqueue("op-1")
        self.assertTrue(again["ok"], again)
        self.assertEqual(again["layer"], first["layer"])
        self.assertTrue(again["idempotent"])
        self.assertEqual(self.allocator()["next_id"], 2)
        self.assertEqual(len(list((self.root / "audit").glob("*.md"))), 1)

    def test_crash_after_rename_before_commit_promotes_the_same_layer(self) -> None:
        self.enqueue("op-1")
        doc = self.allocator()
        key = next(iter(doc["operations"]))
        doc["operations"][key]["state"] = audit_enqueue.RESERVED
        audit_enqueue.write_allocator(self.root, doc)
        again = self.enqueue("op-1")
        self.assertEqual(again["layer"], 1)
        self.assertEqual(self.allocator()["operations"][key]["state"], audit_enqueue.COMMITTED)
        self.assertEqual(len(list((self.root / "audit").glob("*.md"))), 1)

    def test_crash_after_reservation_before_placement_finishes_the_same_layer(self) -> None:
        # The durable state a process death between reserve and place leaves:
        # the allocation is recorded, the file is not there yet.
        doc = audit_enqueue.read_allocator(self.root)
        doc["operations"][audit_enqueue._op_key("audapack", "op-1")] = {
            "layer": 1,
            "producer": "audapack",
            "producer_operation_id": "op-1",
            "producer_item_id": None,
            "created_at": "2026-08-31T00:00:00Z",
            "sha256": hashlib.sha256(BODY).hexdigest(),
            "state": audit_enqueue.RESERVED,
        }
        doc["next_id"] = 2
        audit_enqueue.write_allocator(self.root, doc)

        again = self.enqueue("op-1")
        self.assertTrue(again["ok"], again)
        self.assertEqual(again["layer"], 1)
        self.assertEqual((self.root / "audit" / "1.md").read_bytes(), BODY)
        self.assertEqual(audit_enqueue.read_allocator(self.root)["next_id"], 2)

    def test_a_refused_placement_frees_the_operation_but_never_the_id(self) -> None:
        with patch.object(
            audit_enqueue, "_place", return_value={"ok": False, "code": "CONFLICT", "detail": "x"}
        ):
            refused = self.enqueue("op-1")
        self.assertFalse(refused["ok"])
        doc = audit_enqueue.read_allocator(self.root)
        self.assertEqual(doc["operations"], {})
        self.assertEqual(doc["next_id"], 2)
        # The retry is a fresh allocation, never a reuse of the spent id.
        self.assertEqual(self.enqueue("op-1")["layer"], 2)

    def test_consumed_layer_does_not_get_re_placed_by_a_late_retry(self) -> None:
        self.enqueue("op-1")
        (self.root / "audit" / "1.md").unlink()
        again = self.enqueue("op-1")
        self.assertTrue(again["ok"], again)
        self.assertEqual(again["layer"], 1)
        self.assertFalse(again["present"])
        self.assertFalse((self.root / "audit" / "1.md").exists())

    def test_retry_with_different_bytes_is_refused_not_silently_reallocated(self) -> None:
        self.enqueue("op-1")
        clash = self.enqueue("op-1", body=b"# different\n")
        self.assertFalse(clash["ok"])
        self.assertEqual(clash["code"], "CONFLICT")
        self.assertEqual(len(list((self.root / "audit").glob("*.md"))), 1)

    def test_two_producers_may_share_an_operation_id_without_colliding(self) -> None:
        first = self.enqueue("run-7", producer="audapack")
        second = self.enqueue("run-7", producer="saipal")
        self.assertNotEqual(first["layer"], second["layer"])


class Concurrency(EnqueueFixture):
    def test_concurrent_enqueues_allocate_distinct_layers_with_no_overwrite(self) -> None:
        results: list[dict] = []
        guard = threading.Lock()
        start = threading.Barrier(4)

        def worker(index: int) -> None:
            start.wait()
            outcome = self.enqueue(f"op-{index}", body=f"# audit {index}\n".encode())
            with guard:
                results.append(outcome)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertTrue(all(r["ok"] for r in results), results)
        layers = sorted(r["layer"] for r in results)
        self.assertEqual(layers, [1, 2, 3, 4])
        for outcome in results:
            body = (self.root / "audit" / f"{outcome['layer']}.md").read_bytes()
            self.assertEqual(hashlib.sha256(body).hexdigest(), outcome["sha256"])

    def test_a_scanner_never_observes_a_partially_written_layer(self) -> None:
        """The bytes become a LAYER at the rename, never before it.

        The temp file lives in `audit/` (same directory, so the replace cannot
        cross a mount) but its name cannot match the canonical regex, which is
        what makes a concurrent `scan_layers` safe without any reader lock.
        """
        observed: list[list[str]] = []
        real_replace = os.replace

        def spy(src, dst):
            # The allocator commit also replaces a file; only the layer
            # placement is the moment under test.
            if str(dst).endswith(".md"):
                observed.append([item["rel"] for item in audit_inbox.scan_layers(self.root)])
            return real_replace(src, dst)

        with patch.object(audit_enqueue.os, "replace", spy):
            self.enqueue("op-1")
        self.assertEqual(observed, [[]])


class Containment(EnqueueFixture):
    def test_producer_name_must_be_a_stable_token(self) -> None:
        for bad in ("../escape", "AUDAPACK", "", "a/b", "x" * 40):
            outcome = self.enqueue("op-1", producer=bad)
            self.assertFalse(outcome["ok"], bad)
            self.assertEqual(outcome["code"], "VALIDATION_FAILED", bad)

    def test_operation_id_must_be_path_safe(self) -> None:
        for bad in ("../op", "op/1", "op\\1", ".."):
            outcome = self.enqueue(bad)
            self.assertFalse(outcome["ok"], bad)
            self.assertEqual(outcome["code"], "INVALID_ID", bad)

    def test_empty_body_is_refused(self) -> None:
        outcome = self.enqueue("op-1", body=b"   \n")
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["code"], "VALIDATION_FAILED")

    def test_enqueue_never_touches_board_state_or_log(self) -> None:
        watched = {}
        for name in ("BOARD.md", "STATE.md", "LOG.md"):
            path = self.root / ".saipen" / name
            watched[name] = (
                hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            )
        self.enqueue("op-1")
        for name, before in watched.items():
            path = self.root / ".saipen" / name
            after = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            self.assertEqual(after, before, name)

    def test_existing_layer_is_never_overwritten(self) -> None:
        doc = audit_enqueue.read_allocator(self.root)
        doc["next_id"] = 5
        audit_enqueue.write_allocator(self.root, doc)
        squatter = self.root / "audit" / "5.md"
        squatter.parent.mkdir(parents=True, exist_ok=True)
        squatter.write_bytes(b"# already here\n")
        # _reconcile normally steps over it; force the collision to prove the
        # placement itself refuses rather than trusting the allocator.
        with patch.object(audit_enqueue, "_reconcile", side_effect=lambda _root, d: d):
            outcome = self.enqueue("op-1")
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["code"], "CONFLICT")
        self.assertEqual(squatter.read_bytes(), b"# already here\n")


class NativeConsumption(EnqueueFixture):
    def test_native_inbox_discovers_an_api_created_layer_normally(self) -> None:
        result = self.enqueue("op-1")
        layers = audit_inbox.scan_layers(self.root)
        self.assertEqual([item["rel"] for item in layers], ["audit/1.md"])
        classified = audit_inbox.classify(self.root)["layers"]
        self.assertEqual(len(classified), 1)
        self.assertEqual(classified[0]["state"], audit_inbox.NEW)
        self.assertEqual(classified[0]["sha256"], result["sha256"])

    def test_allocator_status_is_read_only_and_carries_no_body_text(self) -> None:
        self.enqueue("op-1")
        projection = audit_enqueue.status(self.root)
        self.assertEqual(projection["last_allocated_id"], 1)
        self.assertEqual(projection["reserved"], 0)
        self.assertNotIn("producer audit", json.dumps(projection))


if __name__ == "__main__":
    unittest.main()
