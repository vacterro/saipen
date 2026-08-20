"""V7 Producer Parallelism Hardening -- conformance matrix (A..N).

Run from the `tools/` directory:

    python test_v7_producer_parallelism.py

Covers every DONE/matrix case from the spec:
  A  ee + qq prepare concurrently from the same source
  B  ee + ee cannot corrupt one translation namespace
  C  qq + qq cannot corrupt one wiki namespace
  D  crash halfway through preparation exposes no READY package
  E  stale producer epoch cannot publish after takeover
  F  duplicate identical prepare is idempotent
  G  translate integrates first (irrelevant paths) -> wiki COMPATIBLE_DRIFT
  H  translate changes a wiki read dependency -> wiki STALE
  I  two packages target the same output -> second refused before any write
  J  Core changes an unrelated file -> package stays usable
  K  Core changes a declared producer input -> package STALE
  L  producer attempts Core mutation / ship -> CAPABILITY_DENIED, zero writes
  M  restart between staging and READY -> deterministic recovery, no false READY
  N  all integration serialized through the canonical Core writer lock
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from saipen_engine import producer as P  # noqa: E402
from saipen_engine.capability import (  # noqa: E402
    CAPABILITY_DENIED,
    assert_producer_capability,
    guard_core_mutation,
)
from saipen_engine.lock import ProducerLock, project_writer_lock  # noqa: E402


def wf(root: Path, rel: str, content: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def fake_identity(tree_fp: str):
    return type(
        "FakeIdentity",
        (),
        {
            "source_head": "no-git",
            "source_tree_fingerprint": tree_fp,
            "discovery_model": "no-git-tree-v1",
        },
    )()


def classify_now(pkg: P.ProducerPackage, root: Path, base_tree: str, cur_tree: str):
    base = fake_identity(base_tree)
    cur = fake_identity(cur_tree)
    keys = set(pkg.read_set) | set(pkg.write_set)
    cur_hashes = {k: P.file_sha256(Path(root) / k) for k in keys}
    return P.classify_integration(base, cur, pkg.read_set, pkg.write_set, cur_hashes)


class V7Test(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="v7_"))
        self.root = self.tmp / "project"
        self.root.mkdir()
        # canonical source surface used by the producer dependency sets
        wf(self.root, "src/core.py", "def core():\n    return 1\n")
        wf(self.root, "src/wiki.md", "# Wiki\n")
        wf(self.root, "shared/glossary.md", "glossary v1\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_pkg(self, producer, read_paths, write_paths, scope, epoch=0, status="ready"):
        read_set = P.read_set_from(self.root, read_paths)
        write_set = P.write_set_before(self.root, write_paths)
        return P.build_package(
            producer=producer,
            role_revision="sha256:role-" + producer,
            base_source_head="no-git",
            base_source_tree_fingerprint="tree:base",
            base_discovery_model="no-git-tree-v1",
            scope=scope,
            read_set=read_set,
            write_set=write_set,
            epoch=epoch,
            status=status,
        )

    # ------------------------------------------------------------------ A
    def test_A_concurrent_ee_qq_allowed(self):
        with ProducerLock(self.root, "saitranslate") as le, ProducerLock(self.root, "saiwiki") as lq:
            self.assertIsNotNone(le)
            self.assertIsNotNone(lq)
        # lock files are independent and never touch the canonical main tree
        self.assertTrue((self.root / ".saipen/locks/producer-saitranslate.lock").is_file())
        self.assertTrue((self.root / ".saipen/locks/producer-saiwiki.lock").is_file())

    # ------------------------------------------------------------------ B
    def test_B_ee_ee_serialized(self):
        with ProducerLock(self.root, "saitranslate") as held:
            self.assertIsNotNone(held)
            other = ProducerLock(self.root, "saitranslate")
            with self.assertRaises(PermissionError):
                other.acquire()

    # ------------------------------------------------------------------ C
    def test_C_qq_qq_serialized(self):
        with ProducerLock(self.root, "saiwiki") as held:
            self.assertIsNotNone(held)
            other = ProducerLock(self.root, "saiwiki")
            with self.assertRaises(PermissionError):
                other.acquire()

    # ------------------------------------------------------------------ D
    def test_D_crash_leaves_no_ready(self):
        ns = self.root / ".saipen/saitranslate"
        pkg = self._make_pkg("saitranslate", ["src/core.py"], ["translations/ru.md"], "ru")
        gen = P.StagingGeneration(ns, "saitranslate").begin()
        gen.add_payload("translations/ru.md", "partial-")  # incomplete payload
        gen.set_package(pkg)
        # crash: never call publish()
        self.assertFalse(P.StagingGeneration.is_ready(ns, pkg.package_identity))
        self.assertFalse((ns / P.READY_DIRNAME).exists())
        # incomplete staging evidence must remain, not a READY package
        self.assertTrue((ns / P.STAGING_DIRNAME).exists())

    # ------------------------------------------------------------------ E
    def test_E_stale_epoch_cannot_publish(self):
        ns = self.root / ".saipen/saitranslate"
        epoch1 = P.ProducerEpoch.claim(ns)
        pkg = self._make_pkg("saitranslate", ["src/core.py"], ["translations/ru.md"], "ru", epoch=epoch1)
        gen = P.StagingGeneration(ns, "saitranslate").begin()
        gen.add_payload("translations/ru.md", "complete content")
        gen.set_package(pkg)
        # takeover: a newer epoch is claimed by someone else
        epoch2 = P.ProducerEpoch.claim(ns)
        self.assertNotEqual(epoch1, epoch2)
        res = gen.publish()
        self.assertFalse(res["ok"])
        self.assertEqual(res["code"], "STALE_WORKER")
        self.assertFalse(P.StagingGeneration.is_ready(ns, pkg.package_identity))

    # ------------------------------------------------------------------ F
    def test_F_idempotent_duplicate_prepare(self):
        ns = self.root / ".saipen/saitranslate"
        epoch = P.ProducerEpoch.claim(ns)
        pkg = self._make_pkg("saitranslate", ["src/core.py"], ["translations/ru.md"], "ru", epoch=epoch)
        g1 = P.StagingGeneration(ns, "saitranslate").begin()
        g1.add_payload("translations/ru.md", "content")
        g1.set_package(pkg)
        r1 = g1.publish()
        self.assertEqual(r1["code"], "PUBLISHED")
        # identical work prepared again
        g2 = P.StagingGeneration(ns, "saitranslate").begin()
        g2.add_payload("translations/ru.md", "content")
        g2.set_package(pkg)
        r2 = g2.publish()
        self.assertEqual(r2["code"], "REUSED")
        ready_files = list((ns / P.READY_DIRNAME).glob("*.json"))
        self.assertEqual(len(ready_files), 1)  # no duplicate records

    # ------------------------------------------------------------------ G
    def test_G_translate_first_wiki_compatible_drift(self):
        translate = self._make_pkg("saitranslate", ["src/core.py"], ["translations/ru.md"], "ru")
        wiki = self._make_pkg(
            "saiwiki",
            ["src/core.py", "shared/glossary.md"],
            ["wiki/index.md"],
            "wiki",
        )
        # translate integrates first (only touches translations/ru.md)
        wf(self.root, "translations/ru.md", "ru translation\n")
        cls, _ = classify_now(wiki, self.root, "tree:base", "tree:after-ru")
        self.assertEqual(cls, P.IntegrationClass.COMPATIBLE_DRIFT)
        # plan confirms wiki needs no regeneration
        plan = P.plan_integration(
            [translate, wiki],
            fake_identity("tree:base"),
            current_identity_provider=lambda: fake_identity("tree:after-ru"),
            current_hashes_provider=lambda p: {
                k: P.file_sha256(self.root / k)
                for k in (set(p.read_set) | set(p.write_set))
            },
        )
        wiki_entry = next(e for e in plan["packages"] if e["producer"] == "saiwiki")
        self.assertEqual(wiki_entry["class"], "COMPATIBLE_DRIFT")
        self.assertFalse(wiki_entry["regenerate"])

    # ------------------------------------------------------------------ H
    def test_H_translate_changes_wiki_read_dep_stale(self):
        translate = self._make_pkg(
            "saitranslate",
            ["shared/glossary.md"],
            ["translations/ru.md", "shared/glossary.md"],
            "ru",
        )
        wiki = self._make_pkg(
            "saiwiki",
            ["src/core.py", "shared/glossary.md"],
            ["wiki/index.md"],
            "wiki",
        )
        # translate integration rewrites the glossary that wiki reads
        wf(self.root, "translations/ru.md", "ru\n")
        wf(self.root, "shared/glossary.md", "glossary v2 CHANGED\n")
        cls, reason = classify_now(wiki, self.root, "tree:base", "tree:after")
        self.assertEqual(cls, P.IntegrationClass.STALE)
        self.assertIn("glossary", reason)

    # ------------------------------------------------------------------ I
    def test_I_same_output_second_refused(self):
        a = self._make_pkg("saitranslate", ["src/core.py"], ["out/x.md"], "a")
        b = self._make_pkg("saiwiki", ["src/core.py"], ["out/x.md"], "b")
        written = []

        def apply(pkg, root):
            written.append(pkg.package_identity)
            wf(root, "out/x.md", "from " + pkg.producer)

        res = P.integrate_packages_core([a, b], self.root, apply_write=apply)
        a_res = next(r for r in res["results"] if r["producer"] == "saitranslate")
        b_res = next(r for r in res["results"] if r["producer"] == "saiwiki")
        self.assertEqual(a_res["result"], "INTEGRATED")
        self.assertEqual(b_res["result"], "REFUSED")
        self.assertFalse(b_res["wrote"])
        self.assertEqual(written, [a.package_identity])  # b never wrote
        # explicit conflict model must flag the write/write collision
        conf = P.derive_conflicts(a, b)
        self.assertFalse(conf["compatible"])
        self.assertTrue(conf["write_write"])

    # ------------------------------------------------------------------ J
    def test_J_core_unrelated_change_usable(self):
        pkg = self._make_pkg("saitranslate", ["src/core.py"], ["translations/ru.md"], "ru")
        wf(self.root, "src/unrelated_impl.py", "totally new code\n")  # irrelevant to pkg
        cls, _ = classify_now(pkg, self.root, "tree:base", "tree:unrelated")
        self.assertNotEqual(cls, P.IntegrationClass.STALE)
        self.assertEqual(cls, P.IntegrationClass.COMPATIBLE_DRIFT)

    # ------------------------------------------------------------------ K
    def test_K_core_changes_declared_input_stale(self):
        pkg = self._make_pkg("saitranslate", ["src/core.py"], ["translations/ru.md"], "ru")
        wf(self.root, "src/core.py", "def core():\n    return 999  # changed\n")  # declared input
        cls, reason = classify_now(pkg, self.root, "tree:base", "tree:changed")
        self.assertEqual(cls, P.IntegrationClass.STALE)
        self.assertIn("src/core.py", reason)

    # ------------------------------------------------------------------ L
    def test_L_producer_core_mutation_denied(self):
        ok, code, _ = assert_producer_capability("ship", producer="saitranslate")
        self.assertFalse(ok)
        self.assertEqual(code, CAPABILITY_DENIED)

        ok, code, _ = assert_producer_capability("mutate_core_state", producer="saiwiki")
        self.assertFalse(ok)
        self.assertEqual(code, CAPABILITY_DENIED)

        ok, code, _ = assert_producer_capability("read_source", producer="saitranslate")
        self.assertTrue(ok)

        # guard refuses any producer write that would touch Core canonical truth
        blocked, why = guard_core_mutation(self.root / ".saipen/STATE.md")
        self.assertTrue(blocked)
        # and a denied action performs ZERO canonical writes
        state_path = self.root / ".saipen/STATE.md"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("ORIGINAL\n")
        blocked, _ = guard_core_mutation(state_path)
        self.assertTrue(blocked)
        self.assertEqual(state_path.read_text(), "ORIGINAL\n")  # unchanged

    # ------------------------------------------------------------------ M
    def test_M_restart_recovery_no_false_ready(self):
        ns = self.root / ".saipen/saiwiki"
        # a valid published package exists first
        epoch = P.ProducerEpoch.claim(ns)
        good = self._make_pkg("saiwiki", ["src/wiki.md"], ["wiki/index.md"], "good", epoch=epoch)
        gg = P.StagingGeneration(ns, "saiwiki").begin()
        gg.add_payload("wiki/index.md", "good content")
        gg.set_package(good)
        gg.publish()
        self.assertTrue(P.StagingGeneration.is_ready(ns, good.package_identity))
        # now a crashed staging generation appears (incomplete, never published)
        crashed = P.StagingGeneration(ns, "saiwiki").begin()
        crashed.add_payload("wiki/index.md", "partial")  # never published
        crashed.set_package(self._make_pkg("saiwiki", ["src/wiki.md"], ["wiki/index.md"], "crashed", epoch=epoch))
        # restart -> deterministic recovery
        report = P.StagingGeneration.recover(ns)
        self.assertTrue(report["removed_staging"])
        self.assertFalse(report["false_ready"])
        # the valid READY package survives; the crashed staging generation is gone
        self.assertTrue(P.StagingGeneration.is_ready(ns, good.package_identity))
        self.assertFalse(list((ns / P.STAGING_DIRNAME).glob("*")))  # no orphan generations

    # ------------------------------------------------------------------ N
    def test_N_serialized_through_core_writer_lock(self):
        a = self._make_pkg("saitranslate", ["src/core.py"], ["translations/ru.md"], "a")
        b = self._make_pkg("saiwiki", ["src/wiki.md"], ["wiki/index.md"], "b")
        written = []

        def apply(pkg, root):
            written.append(pkg.package_identity)
            wf(root, list(pkg.write_set)[0], "payload")

        res = P.integrate_packages_core([a, b], self.root, apply_write=apply)
        for r in res["results"]:
            self.assertEqual(r["result"], "INTEGRATED")
        # deterministic order: by (producer, package_identity) -- translate before
        # wiki, never by incidental hash ordering.
        self.assertEqual(res["results"][0]["producer"], "saitranslate")
        self.assertEqual(res["results"][1]["producer"], "saiwiki")

        # N (hard): integration must go through project_writer_lock.
        # Hold the canonical lock in the main thread; a concurrent integration
        # in another thread must be refused (WRITER_BUSY) -> proves serialization.
        exc = {}

        def try_integrate():
            try:
                P.integrate_packages_core([a], self.root, apply_write=apply)
            except PermissionError as e:  # WRITER_BUSY from project_writer_lock
                exc["raised"] = e

        with project_writer_lock(self.root):
            t = threading.Thread(target=try_integrate)
            t.start()
            t.join(timeout=10)
        self.assertIn("raised", exc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
