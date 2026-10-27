"""Adversarial oracle for T-1709 / SRC-209.

Eliminate audit-inbox starvation with bounded fair selection and durable
named-generation first-seen order.
"""

from __future__ import annotations

import hashlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from test_audit_inbox import (  # noqa: E402
    BOARD_EMPTY,
    AuditInboxFixture,
    _live_claim_time,
    _state,
)
from saipen_engine import audit_inbox  # noqa: E402
from saipen_engine.router import route_next  # noqa: E402


class AuditStarvationOracleTests(AuditInboxFixture):
    def named(self, name="handoff.md", body=b"# Handoff\n\nOne requirement.\n"):
        path = self.root / "audit" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return path

    def test_replenished_nonurgent_p2_backlog_cannot_postpone_eligible_audit_intake(self):
        """SRC-209:R003: nonurgent P2 tickets cannot indefinitely postpone named audit intake."""
        self.named("handoff.md")
        board_p2 = BOARD_EMPTY.replace(
            "## TODO\n",
            "## TODO\n"
            "- [ ] T-10 [P2] nonurgent task 1 | verify: proof 1\n"
            "- [ ] T-11 [P2] nonurgent task 2 | verify: proof 2\n",
        )
        projection = audit_inbox.projection(self.root)
        routed = route_next(_state(), board_p2, audit_inbox=projection)
        # On vulnerable tree, routed['ticket'] is T-10 (starving the audit inbox).
        # On fixed tree, the eligible audit intake advances ahead of nonurgent P2 work.
        self.assertEqual(routed["action"], "saipen audit ingest")
        self.assertEqual(routed["audit_path"], "audit/handoff.md")

    def test_urgent_p0_and_p1_retain_priority_over_named_audit(self):
        """SRC-209:R003: urgent P0/P1 tickets retain priority over named audit intake."""
        self.named("handoff.md")
        board_urgent = BOARD_EMPTY.replace(
            "## TODO\n",
            "## TODO\n"
            "- [ ] T-1 [P1] urgent defect | verify: proof 1\n"
            "- [ ] T-2 [P2] nonurgent backlog | verify: proof 2\n",
        )
        projection = audit_inbox.projection(self.root)
        routed = route_next(_state(), board_urgent, audit_inbox=projection)
        self.assertEqual(routed["ticket"], "T-1")
        self.assertEqual(routed["action"], "PHASE SCOUT T-1")

    def test_active_work_is_never_preempted(self):
        """SRC-209:R003: live active BUILD/VERIFY/REVIEW/SHIP is never preempted."""
        self.named("handoff.md")
        board_live = (
            "# Board\n## DOING\n"
            "- [/] T-400 [P1] live | verify: proof | owner: probe | claim_time: "
            + _live_claim_time()
            + "\n## TODO\n## DONE\n## BLOCKED\n"
        )
        projection = audit_inbox.projection(self.root)
        for phase, previous in (
            ("BUILD", "SCOUT"), ("VERIFY", "BUILD"),
            ("REVIEW", "VERIFY"), ("SHIP", "REVIEW"),
        ):
            with self.subTest(phase=phase):
                state_live = _state(phase, "T-400", f"PHASE {phase} T-400", previous)
                routed = route_next(
                    state_live, board_live, current_agent="probe", audit_inbox=projection
                )
                self.assertEqual(routed["action"], f"PHASE {phase} T-400")

    def test_human_gates_and_recovery_retain_priority(self):
        """SRC-209:R003: human gates and recovery retain priority over audit intake."""
        self.named("handoff.md")
        state_wait = _state("DONE", "none", "WAIT: user brake -- operator paused")
        projection = audit_inbox.projection(self.root)
        routed = route_next(state_wait, BOARD_EMPTY, audit_inbox=projection)
        self.assertEqual(routed["reason"], "wait")
        self.assertEqual(routed["action"], "WAIT: user brake -- operator paused")
        routed = route_next(_state(), BOARD_EMPTY, pending_ops=["pending"], audit_inbox=projection)
        self.assertEqual(routed["reason"], "recovery-pending")
        self.assertEqual(routed["action"], "saipen recover")

    def test_numeric_layers_retain_order_and_outrank_named(self):
        """SRC-209:R004: numeric layers sort first by number and outrank named layers."""
        self.named("z_handoff.md")
        self.layer(2, "# layer 2")
        self.layer(1, "# layer 1")
        layers = audit_inbox.scan_layers(self.root)
        self.assertEqual([x["name"] for x in layers], ["1.md", "2.md", "z_handoff.md"])
        projection = audit_inbox.projection(self.root)
        self.assertEqual(projection["action"], "saipen audit ingest")
        self.assertEqual(projection["path"], "audit/1.md")

    def test_named_generations_retain_durable_first_seen_order_without_mtime(self):
        """SRC-209:R004: named generations retain first-seen order independent of mtime."""
        p_beta = self.named("beta.md", b"# Beta requirement\n")
        p_alpha = self.named("alpha.md", b"# Alpha requirement\n")
        # Persist first-seen order: beta first, alpha second
        doc = audit_inbox.read_binding(self.root)
        doc["named_first_seen"] = [
            {
                "rel": "audit/beta.md",
                "file_sha256": hashlib.sha256(p_beta.read_bytes()).hexdigest(),
                "first_seen_at": "2026-10-10T01:00:00Z",
            },
            {
                "rel": "audit/alpha.md",
                "file_sha256": hashlib.sha256(p_alpha.read_bytes()).hexdigest(),
                "first_seen_at": "2026-10-10T02:00:00Z",
            },
        ]
        audit_inbox.write_binding(self.root, doc)

        # Mutate filesystem mtimes so beta looks much newer than alpha
        os.utime(p_beta, (2000000000, 2000000000))
        os.utime(p_alpha, (100, 100))

        layers = audit_inbox.scan_layers(self.root)
        # Even though alpha is alphabetically first and has older mtime,
        # beta was first-seen and must sort first!
        self.assertEqual([x["name"] for x in layers], ["beta.md", "alpha.md"])

    def test_blocked_or_invalid_entry_retains_evidence_while_eligible_entry_advances(self):
        """SRC-209:R004: invalid entries retain evidence in status while eligible entry advances."""
        # Oversize layer is invalid
        oversize_body = b"x" * (audit_inbox.MAX_LAYER_BYTES + 10)
        self.layer(1, oversize_body)
        self.layer(2, b"# valid layer 2\n")

        status = audit_inbox.status(self.root)
        self.assertEqual(len(status["invalid"]), 1)
        self.assertEqual(status["invalid"][0]["layer"], 1)
        self.assertEqual(status["invalid"][0]["reason"], "oversize")

        projection = audit_inbox.projection(self.root)
        self.assertEqual(projection["action"], "saipen audit ingest")
        self.assertEqual(projection["path"], "audit/2.md")

    def test_cleanup_requires_proven_closure(self):
        """SRC-209:R005: cleanup requires proven closed receipt and matching current bytes."""
        self.named("audit_sample.md", b"# To be closed\n")
        gate_unbound = audit_inbox.delete_gate(self.root, "audit/audit_sample.md")
        self.assertFalse(gate_unbound.get("ok"))
        self.assertIn(gate_unbound.get("code"), ("AUDIT_NOT_BOUND", "SOURCE_UNRESOLVED"))

    def test_new_bytes_at_old_path_join_after_older_pending_generation(self):
        beta = self.named("beta.md", b"# Beta first\n")
        audit_inbox.record_named_first_seen(self.root)
        self.named("alpha.md", b"# Alpha second\n")
        audit_inbox.record_named_first_seen(self.root)
        beta.write_bytes(b"# Beta replacement\n")
        audit_inbox.record_named_first_seen(self.root)
        self.assertEqual(
            [x["name"] for x in audit_inbox.scan_layers(self.root)], ["alpha.md", "beta.md"]
        )
        seen = audit_inbox.read_binding(self.root)["named_first_seen"]
        self.assertEqual([x["rel"] for x in seen], [
            "audit/beta.md", "audit/alpha.md", "audit/beta.md",
        ])
        self.assertNotEqual(seen[0]["file_sha256"], seen[2]["file_sha256"])

    def test_observation_is_idempotent_and_read_only_scan_does_not_write(self):
        self.named("beta.md")
        added = audit_inbox.record_named_first_seen(self.root)
        self.assertEqual(len(added), 1)
        binding = self.root / audit_inbox.BINDING_REL
        before = binding.read_bytes()
        self.assertEqual(audit_inbox.record_named_first_seen(self.root), [])
        audit_inbox.scan_layers(self.root)
        audit_inbox.status(self.root)
        self.assertEqual(binding.read_bytes(), before)

    def test_invalid_named_entry_keeps_observation_when_repaired(self):
        invalid = self.named("alpha.md", b"\xff")
        audit_inbox.record_named_first_seen(self.root)
        self.named("beta.md", b"# Beta valid\n")
        audit_inbox.record_named_first_seen(self.root)
        invalid.write_bytes(b"# Alpha repaired\n")
        audit_inbox.record_named_first_seen(self.root)
        self.assertEqual(
            [x["name"] for x in audit_inbox.scan_layers(self.root)], ["beta.md", "alpha.md"]
        )
        self.assertEqual(len(audit_inbox.read_binding(self.root)["named_first_seen"]), 3)

    def test_corrupt_chronology_is_refused_without_rewriting_evidence(self):
        self.named("beta.md")
        doc = audit_inbox.read_binding(self.root)
        for bad in ({"not": "a list"}, [{"rel": "../escape.md"}], [None]):
            with self.subTest(bad=bad):
                doc["named_first_seen"] = bad
                audit_inbox.write_binding(self.root, doc)
                binding = self.root / audit_inbox.BINDING_REL
                before = binding.read_bytes()
                self.assertFalse(audit_inbox.classify(self.root)["ok"])
                with self.assertRaises(audit_inbox.BindingCorrupt):
                    audit_inbox.record_named_first_seen(self.root)
                self.assertEqual(binding.read_bytes(), before)

    def test_named_observation_uses_project_writer_lock(self):
        from contextlib import contextmanager

        self.named("beta.md")
        entered = []

        @contextmanager
        def observed_lock(root):
            entered.append(Path(root))
            yield

        with patch("saipen_engine.lock.project_writer_lock", observed_lock):
            audit_inbox.record_named_first_seen(self.root)
        self.assertEqual(entered, [self.root])

    def test_binding_cannot_clobber_concurrent_named_observations(self):
        self.named("beta.md")
        captured = audit_inbox.capture_layer(self.root, "audit/beta.md")
        self.assertTrue(captured["ok"], captured)
        original_write = audit_inbox.write_binding
        refused = []
        probing = [True]

        def concurrent_observation(root, doc):
            if probing[0]:
                probing[0] = False
                self.named("alpha.md", b"# Concurrently observed generation\n")
                try:
                    audit_inbox.record_named_first_seen(root)
                except PermissionError:
                    refused.append(True)
            original_write(root, doc)

        with patch.object(audit_inbox, "write_binding", side_effect=concurrent_observation):
            audit_inbox.bind_layer(
                self.root, "audit/beta.md", layer=None, generation=1,
                file_sha256=captured["file_sha256"], size_bytes=1,
                receipt_id=captured["receipt"], receipt_sha256=captured["file_sha256"],
                binding="exact", linked_work=None, state=audit_inbox.ACTIVE,
            )
        self.assertEqual(refused, [True], "binding must serialize with chronology writes")
        audit_inbox.record_named_first_seen(self.root)
        seen = audit_inbox.read_binding(self.root)["named_first_seen"]
        self.assertEqual([x["rel"] for x in seen], ["audit/beta.md", "audit/alpha.md"])


if __name__ == "__main__":
    unittest.main()
