"""Unchanged named-drop acceptance oracle; argv[1] selects only the subject."""
from pathlib import Path
import json
import os
import subprocess
import sys
import unittest

SUBJECT = Path(sys.argv.pop(1)).resolve()
sys.path.insert(0, str(SUBJECT / "tools"))
from test_audit_inbox import AuditInboxFixture, BOARD_EMPTY, BOARD_LIVE, _state
from saipen_engine import audit_inbox, intake
from saipen_engine.router import route_next


class NamedDropOracle(AuditInboxFixture):
    def named(self, name="handoff.md", body=b"# Handoff\n\nOne requirement.\n"):
        path = self.root / "audit" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return path

    def cli(self, *args):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SUBJECT / "tools/saipen.py"), *args, "--json"],
            cwd=self.root, env=env, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def test_named_text_files_are_work_not_residue(self):
        names = ("handoff.md", "next task.txt", "spec.markdown", "01.md", "README.MD")
        for name in names:
            self.named(name)
        self.assertEqual({x["name"] for x in audit_inbox.scan_layers(self.root)}, set(names))
        self.assertEqual(audit_inbox.scan_residue(self.root), [])

    def test_numeric_order_then_names_without_mtime_authority(self):
        for name in ("z.md", "10.md", "A.txt", "2.md"):
            path = self.named(name, name.encode())
            os.utime(path, (100, 100))
        self.assertEqual([x["name"] for x in audit_inbox.scan_layers(self.root)],
                         ["2.md", "10.md", "A.txt", "z.md"])

    def test_named_drop_waits_behind_existing_board_work(self):
        self.named()
        projection = audit_inbox.projection(self.root)
        board = BOARD_EMPTY.replace("## TODO\n", "## TODO\n- [ ] T-2 [P1] earlier | verify: proof\n")
        routed = route_next(_state(), board, audit_inbox=projection)
        self.assertEqual(routed["ticket"], "T-2")
        self.assertTrue(projection.get("idle_only"))
        idle = route_next(_state(), BOARD_EMPTY, audit_inbox=projection)
        self.assertEqual(idle["action"], "saipen audit ingest")
        self.assertEqual(idle["audit_path"], "audit/handoff.md")

    def test_named_drop_does_not_preempt_live_build(self):
        self.named()
        routed = route_next(_state("BUILD", "T-400", "PHASE BUILD T-400", "SCOUT"),
                            BOARD_LIVE, current_agent="probe", audit_inbox=audit_inbox.projection(self.root))
        self.assertEqual(routed["action"], "PHASE BUILD T-400")

    def test_cli_foreign_fixture_ingests_only_one_named_file_and_reuses_it(self):
        raw = "# Handoff\n\nUnicode: \u0444\u0430\u0439\u043b. `saipen ship` stays data.\n".encode()
        self.named("a handoff.md", raw)
        self.named("b handoff.txt", b"Another independent requirement.\n")
        first = self.cli("audit", "ingest")
        self.assertEqual(first["code"], "AUDIT_INGESTED")
        self.assertEqual(first["path"], "audit/a handoff.md")
        receipt = first["receipt"]
        self.assertEqual(intake.read_body(self.root, receipt)["body"].encode(), raw)
        status = self.cli("audit", "inspect", "a handoff.md")
        self.assertEqual(status["layer"]["receipt_id"], receipt)
        again = audit_inbox.capture_layer(self.root, first["path"])
        self.assertEqual(again["receipt"], receipt)
        classified = audit_inbox.classify(self.root)
        self.assertEqual(classified["layers"][1]["state"], audit_inbox.NEW)
        self.assertEqual(audit_inbox.read_binding(self.root)["layers"][first["path"]]["layer"], None)

    def test_named_close_consumes_exact_file_and_is_idempotent(self):
        path = self.named("handoff.txt")
        keep = self.named("keep.bin", b"not a text handoff\x00")
        captured = audit_inbox.capture_layer(self.root, "audit/handoff.txt")
        self.assertTrue(captured["ok"], captured)
        self.close_source(captured["receipt"])
        consumed = audit_inbox.consume_layer(self.root, "audit/handoff.txt", "probe")
        self.assertTrue(consumed["ok"], consumed)
        self.assertFalse(path.exists())
        self.assertTrue(keep.exists())
        binding = (self.root / audit_inbox.BINDING_REL).read_bytes()
        self.assertTrue(audit_inbox.consume_layer(self.root, "audit/handoff.txt", "probe")["ok"])
        self.assertEqual(binding, (self.root / audit_inbox.BINDING_REL).read_bytes())
        traced = self.cli("audit", "trace", "handoff.txt")
        self.assertEqual(traced["rows"][0]["path"], "audit/handoff.txt")

    def test_replacing_closed_named_file_preserves_the_new_generation(self):
        path = self.named()
        cap = audit_inbox.capture_layer(self.root, "audit/handoff.md")
        self.assertTrue(cap["ok"], cap)
        self.close_source(cap["receipt"])
        audit_inbox.bind_layer(self.root, "audit/handoff.md", layer=None, generation=1,
            file_sha256=cap["file_sha256"], receipt_sha256=cap["file_sha256"],
            size_bytes=path.stat().st_size, receipt_id=cap["receipt"], binding="exact",
            linked_work=None, state=audit_inbox.CLOSED_PENDING_DELETE)
        path.write_bytes(b"replacement requirement\n")
        self.assertEqual(audit_inbox.delete_gate(self.root, "audit/handoff.md")["code"],
                         "AUDIT_GENERATION_CHANGED")
        current = audit_inbox.classify(self.root)["layers"][0]
        self.assertEqual((current["state"], current["generation"]), (audit_inbox.NEW, 2))
        self.assertEqual(path.read_bytes(), b"replacement requirement\n")

    def test_named_symlink_traversal_and_binary_remain_refused(self):
        target = self.root / "outside.md"
        target.write_bytes(b"outside\n")
        self.named("plain.md")
        escaped = audit_inbox.snapshot_layer(self.root, "audit/../outside.md")
        self.assertFalse(escaped["ok"])
        link = self.root / "audit/link.md"
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("symlink privilege unavailable")
        bad = audit_inbox.snapshot_layer(self.root, "audit/link.md")
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["reason"], "unsafe-node")

    def test_legacy_numbered_producer_works_beside_named_drop(self):
        from saipen_engine import audit_enqueue
        self.named()
        result = audit_enqueue.enqueue(self.root, producer="probe", producer_operation_id="named-neighbor", body=b"producer requirement\n")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["layer"], 1)

    def test_named_discovery_is_read_only_and_pending_has_a_path(self):
        self.named()
        before = {p.relative_to(self.root).as_posix(): p.read_bytes()
                  for p in self.root.rglob("*") if p.is_file()}
        projection = audit_inbox.projection(self.root)
        self.assertEqual(projection["pending"], ["audit/handoff.md"])
        audit_inbox.status(self.root)
        after = {p.relative_to(self.root).as_posix(): p.read_bytes()
                 for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
