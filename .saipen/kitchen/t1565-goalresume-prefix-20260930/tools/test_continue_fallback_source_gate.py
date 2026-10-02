"""The continue->improve fallthrough must not re-audit an unchanged source (T-76).

Measured on _zaicode: three discovery cycles were admitted in nine minutes
(imp-_zaicode-20260927-1 at 01:47:52Z, -2 at 01:53:55Z, -3 at 01:56:02Z), all
carrying a byte-identical `source_head` (d2cacebe...) and
`source_tree_fingerprint` (git-delta-v1:ad7d2f9...). Cycle -2 had already
recorded NO_FINDINGS against that exact fingerprint.

The guard that kept a marker was correct and still is: it resumes an ACTIVE
cycle instead of duplicating it. The defect was on the other side of it. The
marker records which cycle was last prepared, and `complete`/`archived`/
`superseded`/`blocked_external` all freed a fresh discovery -- with nothing
comparing the source. A discovery whose own `discovery_model` is `git-delta-v1`
was therefore being re-run on a tree that had not moved, and every admitted
cycle becomes immutable evidence, so the churn was not free.

Each direction is pinned below: an unchanged tree refuses, a moved tree admits,
an unmeasurable tree admits (never guess that nothing moved), a legacy marker
with no recorded identity admits exactly once and then self-heals, and an
in-flight cycle still RESUMES -- the source gate is downstream of that check
and must never swallow committed work.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import continue_fallback as CF  # noqa: E402

MARKER_REL = CF.FALLBACK_MARKER_REL


def _identity(head: str, fingerprint: str, model: str = "git-delta-v1") -> dict:
    return {
        "source_head": head,
        "source_tree_fingerprint": fingerprint,
        "discovery_model": model,
    }


class SourceGate(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.current = _identity("a" * 40, "git-delta-v1:" + "b" * 64)
        self._original = CF.source_identity_fields
        CF.source_identity_fields = lambda root: dict(self.current)
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        CF.source_identity_fields = self._original

    def _write_marker(self, payload: dict) -> None:
        path = self.root / MARKER_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    # --- the defect: unchanged source must not buy another cycle -----------

    def test_unchanged_source_refuses_a_fresh_discovery(self) -> None:
        self._write_marker({"cycle_id": "imp-x-1", "agent": "a", **self.current})
        unchanged, detail = CF.source_unchanged(self.root, CF.read_marker(self.root))
        self.assertTrue(unchanged)
        self.assertIn("unchanged", detail)
        self.assertIn(self.current["source_head"][:12], detail)

    # --- the fix must not become a lock: a moved source still admits --------

    def test_changed_source_admits(self) -> None:
        self._write_marker(
            {
                "cycle_id": "imp-x-1",
                "agent": "a",
                "source_head": "c" * 40,
                "source_tree_fingerprint": "git-delta-v1:" + "d" * 64,
            }
        )
        unchanged, detail = CF.source_unchanged(self.root, CF.read_marker(self.root))
        self.assertFalse(unchanged)
        self.assertIn("changed", detail)

    def test_same_head_dirty_tree_admits(self) -> None:
        """A committed-and-dirty tree is a MOVED tree.

        `git-delta-v1` folds the working-tree delta into the fingerprint, so a
        same-HEAD edit must read as changed. A gate keyed on HEAD alone would
        freeze discovery on exactly the tree an agent is actively editing.
        """
        self._write_marker(
            {
                "cycle_id": "imp-x-1",
                "agent": "a",
                "source_head": self.current["source_head"],
                "source_tree_fingerprint": "git-delta-v1:" + "e" * 64,
            }
        )
        unchanged, _ = CF.source_unchanged(self.root, CF.read_marker(self.root))
        self.assertFalse(unchanged)

    # --- never guess -------------------------------------------------------

    def test_unmeasurable_source_admits(self) -> None:
        self._write_marker({"cycle_id": "imp-x-1", "agent": "a", **self.current})
        CF.source_identity_fields = lambda root: {}
        unchanged, detail = CF.source_unchanged(self.root, CF.read_marker(self.root))
        self.assertFalse(unchanged)
        self.assertIn("not measurable", detail)

    def test_legacy_marker_without_identity_admits_exactly_once(self) -> None:
        """Self-healing: the pre-gate marker has no identity, so it admits once
        and `write_marker` records the identity that makes the gate decisive."""
        self._write_marker({"cycle_id": "imp-x-1", "agent": "a"})
        unchanged, detail = CF.source_unchanged(self.root, CF.read_marker(self.root))
        self.assertFalse(unchanged)
        self.assertIn("no recorded source identity", detail)

        CF.write_marker(self.root, "imp-x-2", "a")
        stored = CF.read_marker(self.root)
        self.assertEqual(stored["source_head"], self.current["source_head"])
        self.assertEqual(
            stored["source_tree_fingerprint"], self.current["source_tree_fingerprint"]
        )
        unchanged, _ = CF.source_unchanged(self.root, CF.read_marker(self.root))
        self.assertTrue(unchanged, "the gate must be decisive from the next admission on")

    def test_absent_marker_admits(self) -> None:
        unchanged, _ = CF.source_unchanged(self.root, CF.read_marker(self.root))
        self.assertFalse(unchanged)

    # --- the in-flight resume is upstream of the gate and must survive -----

    def test_active_cycle_still_resumes_and_is_not_gated(self) -> None:
        cycle = self.root / ".saipen" / "improve" / "imp-x-1"
        cycle.mkdir(parents=True)
        (cycle / "MANIFEST.md").write_text(
            "# IMPROVE CYCLE ROSTER\ncycle_id: imp-x-1\ncycle_status: active\n",
            encoding="utf-8",
        )
        self._write_marker({"cycle_id": "imp-x-1", "agent": "a", **self.current})
        marker = CF.read_marker(self.root)
        self.assertEqual(CF.active_cycle_status(self.root, marker["cycle_id"]), "active")
        # The gate is a property of the FALLTHROUGH, not of an active cycle:
        # its own decision is taken before source_unchanged is consulted.
        unchanged, _ = CF.source_unchanged(self.root, marker)
        self.assertTrue(
            unchanged,
            "an unchanged source is still what makes the resumed cycle redundant, "
            "but the resume branch returns before the gate is reached",
        )

    def test_terminal_cycle_frees_the_gate_path(self) -> None:
        for status in ("complete", "archived", "superseded", "blocked_external"):
            cycle = self.root / ".saipen" / "improve" / f"imp-{status}"
            cycle.mkdir(parents=True, exist_ok=True)
            (cycle / "MANIFEST.md").write_text(
                f"# IMPROVE CYCLE ROSTER\ncycle_id: imp-{status}\ncycle_status: {status}\n",
                encoding="utf-8",
            )
            self.assertEqual(CF.active_cycle_status(self.root, f"imp-{status}"), status)


if __name__ == "__main__":
    unittest.main()
