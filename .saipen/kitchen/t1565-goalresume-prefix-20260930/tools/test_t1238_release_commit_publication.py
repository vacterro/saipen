"""T-1238: a receipt the project's own writer produced is publication evidence.

Measured on FastPrompter: 0.8.68 shipped -- EXE built at commit 1d7765b, the
packaged probe green on all 13 checks, the receipt written by
`tools/release_provenance.py` and published at
`.saipen/kitchen/release_receipt.json`. Closing the epic that the release
carried (`inherited_verified --implementation-source release:0.8.68`) was
refused with "no COMMITTED release receipt names '0.8.68'".

Cause: `tools/release_provenance.py` writes and verifies `release_commit` and
never writes a bare `commit`, while `closure._is_published` recognised only
`commit`. Every genuine receipt was therefore invisible as publication
evidence, so a release that really shipped could never prove it.

These controls pin the repaired contract:

* a receipt naming `release_commit` IS publication evidence (and matches by
  version, tag or commit);
* a receipt naming NEITHER commit spelling is still in flight and still
  refuses -- the "no commit, no publication" guard is not weakened;
* an unknown version still refuses.

Run standalone:
    python -m unittest tools.test_t1238_release_commit_publication
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _entry in (str(TOOLS), str(ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from saipen_engine.closure import resolve_implementation_source  # noqa: E402

_KITCHEN = ".saipen/kitchen/release_receipt.json"


def _receipt(**overrides) -> dict:
    """The shape `tools/release_provenance.py receipt` actually writes."""
    record = {
        "schema_version": 1,
        "operation": "release_receipt",
        "version": "0.8.68",
        "tag": "v0.8.68",
        "release_commit": "1d7765b677fe3275cf2cf5914eb73f6b17becbcc",
        "exe_sha256": "ca70",
        "product_version": "0.8.68.0",
    }
    record.update(overrides)
    return record


class ReleaseCommitPublicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t1238-pub-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()

    def _publish(self, record: dict) -> None:
        path = self.root / _KITCHEN
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record), encoding="utf-8")

    def test_a_receipt_with_release_commit_is_publication_evidence(self) -> None:
        self._publish(_receipt())
        for wanted in (
            "release:0.8.68",
            "release:v0.8.68",
            "release:1d7765b677fe3275cf2cf5914eb73f6b17becbcc",
        ):
            with self.subTest(wanted=wanted):
                verdict = resolve_implementation_source(self.root, wanted)
                self.assertTrue(verdict.ok, f"{wanted}: {verdict.detail}")
                self.assertEqual(verdict.kind, "release")

    def test_a_bare_commit_field_still_works(self) -> None:
        record = _receipt()
        record.pop("release_commit")
        record["commit"] = "1d7765b677fe3275cf2cf5914eb73f6b17becbcc"
        self._publish(record)
        self.assertTrue(resolve_implementation_source(self.root, "release:0.8.68").ok)

    def test_a_receipt_with_no_commit_is_still_in_flight(self) -> None:
        """The guard this fix touches is 'no commit, no publication'."""
        record = _receipt()
        record.pop("release_commit")
        self._publish(record)
        verdict = resolve_implementation_source(self.root, "release:0.8.68")
        self.assertFalse(verdict.ok)
        self.assertIn("no COMMITTED release receipt", str(verdict.detail))

    def test_an_unknown_version_still_refuses(self) -> None:
        self._publish(_receipt())
        verdict = resolve_implementation_source(self.root, "release:9.9.9")
        self.assertFalse(verdict.ok)


if __name__ == "__main__":
    unittest.main()
