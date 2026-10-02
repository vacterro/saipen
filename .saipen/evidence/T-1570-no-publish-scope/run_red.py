"""Run the unchanged T-1570 oracle with the pre-fix publication decision."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import test_no_publish_source_scope as oracle  # noqa: E402
from saipen_engine import release  # noqa: E402


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(oracle.LocalSourceClosure)
    # Before T-1570, every plan used release_gate's default publish=True.
    with patch.object(release, "_plan_publishes", return_value=True):
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
