"""T-2164: _directory_or_none's annotation, docstring and body agree.

The helper never returns None; denial stays an OSError (the T-1647 contract
its own body implements). This test pins that shape so a caller cannot
write an `is None` branch that never fires.
"""

from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from saipen_engine.paths import _directory_or_none


class DirectoryOrNoneContractTests(unittest.TestCase):
    def test_annotation_and_docstring_match_the_body(self):
        self.assertEqual(str(inspect.signature(_directory_or_none).return_annotation), 'bool')
        doc = inspect.getdoc(_directory_or_none) or ""
        self.assertNotIn("``None`` when", doc)
        self.assertIn("Denial stays a raise", doc)

    def test_directory_true_absent_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertTrue(_directory_or_none(root))
            self.assertFalse(_directory_or_none(root / "absent"))

    def test_denial_propagates_as_oserror(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "blocked"
            target.mkdir()
            with patch("saipen_engine.paths.stat.S_ISDIR", side_effect=OSError("denied")):
                with self.assertRaises(OSError):
                    _directory_or_none(target)


if __name__ == "__main__":
    unittest.main()
