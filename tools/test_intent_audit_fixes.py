"""Regression tests for the SAIPEN AUDIT CORE fixes (CORE-001..CORE-010).

These pin the CORE_DONE_WHEN VERIFY sections to deterministic, side-effect-free
assertions so the autonomous command-family repairs are machine-checkable on a
full checkout.

Run standalone:
    python tools/test_intent_audit_fixes.py

Exit code 0 when every test passes; 1 on the first failure batch.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(TOOLS))

from saipen_engine import intent  # noqa: E402
from saipen_engine import producer as P  # noqa: E402
from saipen_engine import capability as CAP  # noqa: E402
from saipen_engine.conformance import _validate_conformance_containment  # noqa: E402
from saipen_engine.subs import SUBS_REL  # noqa: E402


def _hash_tree(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if ".git" in p.parts:
            continue
        if p.is_file():
            h.update(str(p.relative_to(root)).encode("utf-8"))
            h.update(p.read_bytes())
    return h.hexdigest()


class IntentAuditTests(unittest.TestCase):
    # ── CORE-001: capability boundary is negotiated, never hard-coded ──────
    def test_core001_readonly_refuses_mutation(self):
        root = Path(tempfile.mkdtemp())
        # A non-producer role with no instance: read-only must refuse the
        # spawn/prepare mutation WITHOUT invoking any writer.
        res = intent.ensure_producer_ready(root, "saihunt", current_capability="read-only")
        self.assertEqual(res["code"], "CAPABILITY_READ_ONLY")
        # Internal hard-coded resolver is gone.
        self.assertFalse(hasattr(intent, "_negotiate_capability_resolver_active"))
        with self.assertRaises(RuntimeError):
            intent._negotiate_capability(root)

    def test_core001_capability_default_is_full_when_unset(self):
        saved = os.environ.pop("SAIPEN_CAPABILITY", None)
        try:
            self.assertEqual(CAP.negotiate_capability(), "full")
        finally:
            if saved is not None:
                os.environ["SAIPEN_CAPABILITY"] = saved

    # ── CORE-002: --dry-run is a zero-write plan ───────────────────────────
    def test_core002_dryrun_zero_write(self):
        repo_root = TOOLS.parent  # tools/.. == project root
        before = _hash_tree(repo_root)
        res = intent.autonomous_crew_loop(repo_root, dry_run=True, current_capability="full")
        after = _hash_tree(repo_root)
        self.assertEqual(before, after, "dry-run mutated the filesystem")
        self.assertIn(res["code"], ("CREW_DRY_PLAN", "CREW_COMPLETE", "CREW_IDLE", "CREW_FINALIZED"))

    # ── CORE-003: no fabricated verified:PASS packages ─────────────────────
    def test_core003_no_fabrication_sub_role(self):
        root = Path(tempfile.mkdtemp())
        role_dir = root / SUBS_REL / "saihunt"
        role_dir.mkdir(parents=True)
        res = intent._prepare_role(root, "saihunt")
        self.assertEqual(res["code"], "ROLE_NOT_RUN")
        self.assertFalse((role_dir / "kitchen" / "OUTBOX.md").exists())

    def test_core003_no_fabrication_producer(self):
        root = Path(tempfile.mkdtemp())
        res = intent._prepare_role(root, "saitranslate")
        self.assertEqual(res["code"], "ROLE_NOT_RUN")
        ns = P.producer_namespace(root, "saitranslate")
        self.assertFalse((ns / "kitchen" / "OUTBOX.md").exists())
        # The real producer prepare refuses when the role emitted no evidence.
        res2 = intent._prepare_producer_role(root, "saitranslate")
        self.assertEqual(res2["code"], "ROLE_NOT_RUN")

    def test_core003_real_evidence_publishes_ready_package(self):
        # Positive path (CORE-003): when the role ACTUALLY emitted evidence, the
        # real producer pipeline must publish a genuine traceable READY package
        # (no synthetic verified:PASS fabrication) and it must be discoverable.
        root = Path(tempfile.mkdtemp())
        (root / ".saipen").mkdir()
        ns = P.producer_namespace(root, "saitranslate")
        outbox = ns / "kitchen" / "OUTBOX.md"
        outbox.parent.mkdir(parents=True)
        real_evidence = (
            "# OUTBOX\n## PKG-REAL-1\n"
            "status: ready\nrole_revision: r13\n"
            "source_head: abc123\n"
            "this is the actual emitted preparation evidence\n"
        )
        outbox.write_text(real_evidence, encoding="utf-8")

        res = intent._prepare_producer_role(root, "saitranslate")
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["code"], "PRODUCER_PREPARED")

        ready = P.StagingGeneration.list_ready(ns)
        self.assertTrue(ready, "a READY package must be discoverable after real prepare")
        self.assertEqual(ready[0].producer, "saitranslate")
        # The published content is the ORIGINAL evidence, not a fabricated PASS.
        ready_dir = ns / "READY"
        self.assertTrue(ready_dir.is_dir(), "READY directory must exist on disk")
        ready_files = list(ready_dir.glob("*.json"))
        self.assertTrue(ready_files, "a READY JSON artifact must exist on disk")
        pkg_dict = json.loads(ready_files[0].read_text(encoding="utf-8"))
        self.assertEqual(pkg_dict["package_identity"], ready[0].package_identity)
        # Decode the stored OUTBOX payload and confirm it is the REAL evidence.
        found = False
        for _rel, b64 in pkg_dict.get("payload_bytes", {}).items():
            content = base64.b64decode(b64).decode("utf-8")
            if "PKG-REAL-1" in content and "this is the actual emitted preparation evidence" in content:
                found = True
                break
        self.assertTrue(found, "READY must carry the original emitted evidence payload")
        self.assertNotIn("verified: PASS", json.dumps(pkg_dict))

    # ── CORE-004: pending worker tickets survive failure ──────────────────
    def test_core004_no_destruction(self):
        root = Path(tempfile.mkdtemp())
        board = root / ".saipen" / "extensions" / "subs" / "saihunt" / "BOARD.md"
        board.parent.mkdir(parents=True)
        original = (
            "# BOARD\n## TODO\n- [ ] HUNT-777 preserve this work\n"
            "## DONE\n- [x] old work\n"
        )
        board.write_text(original, encoding="utf-8")
        fixed = intent._auto_repair_role(root, "saihunt")
        self.assertFalse(fixed)
        after = board.read_text(encoding="utf-8")
        self.assertEqual(original, after)
        self.assertIn("HUNT-777", after)
        self.assertIn("## TODO", after)

    # ── CORE-005: recovery locks the canonical ProducerLock ────────────────
    def test_core005_recover_live_writer_no_delete(self):
        for producer in ("saitranslate", "saiwiki"):
            with self.subTest(producer=producer):
                root = Path(tempfile.mkdtemp())
                (root / ".saipen").mkdir()
                ns = P.producer_namespace(root, producer)
                ns.mkdir(parents=True)
                gen = P.StagingGeneration(ns, producer).begin()
                # Live writer holds the CANONICAL producer lock.
                with P.ProducerLock(root, producer):
                    report = P.StagingGeneration.recover(ns)
                    self.assertTrue(report["busy"], "recovery must no-op while writer holds lock")
                    self.assertTrue(gen.staging_dir.is_dir(), "live generation must survive")
                # Writer released; a takeover advances the epoch -> generation stale.
                P.ProducerEpoch.claim(ns)
                report = P.StagingGeneration.recover(ns)
                self.assertFalse(report["busy"])
                self.assertIn(gen.generation_id, report["removed_staging"])
                self.assertFalse(gen.staging_dir.is_dir())

    # ── CORE-006: saitranslate uses the canonical namespace ───────────────
    def test_core006_saitranslate_namespace(self):
        root = Path(tempfile.mkdtemp())
        self.assertEqual(intent._role_dir(root, "saitranslate"), root / ".saipen" / "saitranslate")
        self.assertEqual(intent._role_dir(root, "saiwiki"), P.producer_namespace(root, "saiwiki"))
        self.assertEqual(intent._role_dir(root, "saihunt"), root / SUBS_REL / "saihunt")
        # Dry-run ensure for a missing saitranslate instance must plan via the
        # canonical branch and NEVER hit the outdated sub_spawn signature.
        res = intent.ensure_producer_ready(root, "saitranslate", dry_run=True)
        self.assertEqual(res["code"], "PRODUCER_SPAWN_PLAN")

    # ── CORE-007: every planner action maps to one executor/refusal ─────────
    def test_core007_no_unknown_action(self):
        root = Path(tempfile.mkdtemp())
        agent = "tester"
        home = str(root)
        safe = {
            "RUN_ROLE": "saihunt",
            "COLLECT_ROLE": "saihunt",
            "CONVERGE_CORE": None,
            "PREPARE_TRANSLATE": None,
            "PREPARE_WIKI": None,
            "INTEGRATE_TRANSLATE": None,
            "INTEGRATE_WIKI": None,
            "SYNC_SHARED": None,
            "SPAWN_ROLE": "saihunt",
            "ADOPT_ROLE": "saihunt",
            "FINALIZE": None,
            "DEFER_FOR_CREW": None,
            "CLEAR_WAIT_ROLE": None,
            "DISPOSE_REVIEW": None,
            "REVERIFY_FIXED_POINT": None,
            "SHIP": None,
            "CONTINUE_CORE": None,
        }
        for at, role in safe.items():
            r = intent._execute_crew_action(root, at, role, "full", agent, home, dry_run=False)
            code = r.code if hasattr(r, "code") else r.get("code")
            self.assertNotEqual(code, "UNKNOWN_ACTION", f"{at} must not be UNKNOWN_ACTION")
            self.assertNotEqual(code, "UNHANDLED_ACTION", f"{at} must be handled")
        # A genuinely unknown action fails closed as UNHANDLED_ACTION, never
        # as UNKNOWN_ACTION (which would silently stall the loop).
        r = intent._execute_crew_action(root, "NONSENSE_X", None, "full", agent, home)
        code = r.code if hasattr(r, "code") else r.get("code")
        self.assertEqual(code, "UNHANDLED_ACTION")

    # ── CORE-008: producer dependency paths cannot escape the project ──────
    def test_core008_path_containment(self):
        root = Path(tempfile.mkdtemp())
        (root / "a.txt").write_text("hello", encoding="utf-8")
        # valid relative path
        self.assertEqual(
            P.read_set_from(root, ["a.txt"]), {"a.txt": P.file_sha256(root / "a.txt")}
        )
        # POSIX absolute
        with self.assertRaises(P.ProducerError):
            P.read_set_from(root, ["/etc/passwd"])
        # parent traversal
        with self.assertRaises(P.ProducerError):
            P.read_set_from(root, ["../escape.txt"])
        # Windows drive (host-independent)
        with self.assertRaises(P.ProducerError):
            P.read_set_from(root, ["C:\\Windows\\win.ini"])
        # UNC
        with self.assertRaises(P.ProducerError):
            P.read_set_from(root, ["\\\\server\\share\\x"])
        # write_set_before shares the same gate
        with self.assertRaises(P.ProducerError):
            P.write_set_before(root, ["/abs"])
        # deserialization validates keys
        with self.assertRaises(P.ProducerError):
            P.ProducerPackage.from_dict(
                {
                    "producer": "saitranslate",
                    "role_revision": "r",
                    "base_source_head": "h",
                    "base_source_tree_fingerprint": "t",
                    "scope": "s",
                    "read_set": {"../x": "y"},
                    "write_set": {},
                }
            )
        # _live_hashes rejects escaping write_set
        pkg = P.build_package(
            producer="saitranslate",
            role_revision="r",
            base_source_head="h",
            base_source_tree_fingerprint="t",
            base_discovery_model="",
            scope="s",
            read_set={},
            write_set={"/abs": "z"},
        )
        with self.assertRaises(P.ProducerError):
            P._live_hashes(root, pkg)

    # ── CORE-010: conformance containment fails closed, no NameError ────────
    def test_core010_conformance_containment(self):
        root = Path(tempfile.mkdtemp())
        (root / ".saipen").mkdir()
        (root / ".saipen" / "recovery").mkdir()
        # No conformance dir at all: must be a no-op (returns None).
        self.assertIsNone(_validate_conformance_containment(root))
        # A regular (in-root) conformance dir: no error.
        (root / ".saipen" / "recovery" / "conformance").mkdir()
        self.assertIsNone(_validate_conformance_containment(root))
        # A symlinked conformance dir pointing OUTSIDE the root: must raise a
        # deterministic ValueError, never an unrelated NameError.
        outside = Path(tempfile.mkdtemp())
        link = root / ".saipen" / "recovery" / "conformance"
        try:
            if link.is_dir():
                link.rmdir()
            link.symlink_to(outside)
        except (OSError, NotImplementedError, PermissionError):
            self.skipTest("symlinks not supported on this host")
        with self.assertRaises(ValueError):
            _validate_conformance_containment(root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
