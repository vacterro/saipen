"""T-1734: the read-only source-drift advisory for closed Work.

A DONE Work can close citing a core-unit family record whose fingerprint is a
digest of the verified source tree. Nothing re-reads that binding afterwards,
so the tree can drift away from the verified bytes silently. ``source_binding``
is the bounded read-only observation: CURRENT, DRIFTED or UNBOUND, naming the
Work and both fingerprints, mutating no history. The manual remedy
(``saipen work reverify``) is unchanged and is not exercised here.

Run standalone:
    python tools/test_t1734_source_drift.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import core_unit, source_binding  # noqa: E402

FAMILY_RECORD = ".saipen/evidence/core-unit/abcdef0123456789-20260101T000000Z.json"


def _citation_line(fingerprint: str, record: str = FAMILY_RECORD) -> str:
    sha = hashlib.sha256(b"record").hexdigest()
    return (
        "- 01.01.26 00:00 [E-002] [parent: E-001] [T-100] [agent: saipen-cli] "
        "RUN: CORE-UNIT-EVIDENCE PASS family:unit ran:6336 red:0 new_red:0 "
        f"fixed:0 fingerprint:{fingerprint} record:{record} sha256:{sha}"
    )


def _make_project(tmp: Path) -> Path:
    root = tmp / "project"
    (root / "tools" / "saipen_engine").mkdir(parents=True)
    (root / ".saipen" / "evidence" / "core-unit").mkdir(parents=True)
    (root / "tools" / "saipen_engine" / "test_runner.py").write_text("", encoding="utf-8")
    (root / "tools" / "core_unit_baseline.json").write_text(
        json.dumps({"schema": 1, "family": "unit", "command": ["python", "-m", "unittest"],
                    "red": []}) + "\n",
        encoding="utf-8",
    )
    (root / ".saipen" / "BOARD.md").write_text(
        "# BOARD\n\n## DOING\n\n## TODO\n\n## DONE\n"
        "- [x] T-100 closed work | verify: proof exists\n\n## BLOCKED\n",
        encoding="utf-8",
    )
    return root


class SourceDrift(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="saipen-source-drift-")
        self.addCleanup(self.temporary.cleanup)
        self.root = _make_project(Path(self.temporary.name))
        self.log = self.root / ".saipen" / "LOG.md"
        self.record = self.root / FAMILY_RECORD

    def _write_citation(self, fingerprint: str) -> None:
        self.log.write_text(_citation_line(fingerprint) + "\n", encoding="utf-8")
        self.record.write_text(
            json.dumps({"family": "unit", "fingerprint": fingerprint}) + "\n", encoding="utf-8"
        )

    def test_current_when_the_tree_matches_the_verified_bytes(self) -> None:
        self._write_citation(core_unit.tree_fingerprint(self.root))
        block = source_binding.advisory(self.root)
        self.assertEqual(block["works"][0]["binding"], source_binding.CURRENT)
        self.assertEqual(block["drifted"], [])
        self.assertEqual(block["unbound"], [])

    def test_drifted_when_the_tree_changed_after_closure(self) -> None:
        self._write_citation("0" * 16)
        block = source_binding.advisory(self.root)
        self.assertEqual(block["works"][0]["binding"], source_binding.DRIFTED)
        self.assertEqual(block["drifted"], ["T-100"])
        self.assertEqual(block["works"][0]["recorded_fingerprint"], "0" * 16)
        self.assertEqual(
            block["works"][0]["current_fingerprint"], core_unit.tree_fingerprint(self.root)[:16]
        )

    def test_unbound_when_no_family_run_is_cited(self) -> None:
        self.log.write_text("- 01.01.26 00:00 [E-001] [T-100] RUN: transition to VERIFY\n",
                            encoding="utf-8")
        block = source_binding.advisory(self.root)
        self.assertEqual(block["unbound"], ["T-100"])
        self.assertEqual(block["unbound_count"], 1)
        self.assertEqual(block["works"], [])

    def test_silent_when_the_project_declares_no_family(self) -> None:
        (self.root / "tools" / "saipen_engine" / "test_runner.py").unlink()
        self.assertEqual(source_binding.advisory(self.root), {})

    def test_read_only_no_history_is_mutated(self) -> None:
        self._write_citation("0" * 16)
        def snapshot() -> dict:
            return {
                str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob("*")
                if p.is_file()
            }
        before = snapshot()
        source_binding.advisory(self.root)
        self.assertEqual(before, snapshot())


if __name__ == "__main__":
    unittest.main()
