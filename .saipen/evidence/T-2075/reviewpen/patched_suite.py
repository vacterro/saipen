"""Run the existing GC suite with the T-2062 pen module overlay."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

project_tools = Path.cwd() / "tools"
pen_engine = Path(__file__).parent / "patched" / "saipen_engine"
sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(project_tools))

import saipen_engine  # noqa: E402

saipen_engine.__path__.insert(0, str(pen_engine))
from tools import test_gc  # noqa: E402


suite = unittest.defaultTestLoader.loadTestsFromModule(test_gc)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
