"""The `tools` package -- one place that makes `saipen_engine` importable.

T-1339. Every module in this directory imports `saipen_engine` at top level and
used to rely on this directory reaching `sys.path` by accident. That is true
when a file is run AS A SCRIPT, because Python puts the script's own directory
on the path:

    python tools/saipen.py status          # works

and false for the module form, which puts the REPOSITORY ROOT there instead:

    python -m tools.saipen status          # ModuleNotFoundError: saipen_engine
    python -m unittest tools.test_cold_agent_truth

Both spellings look supported, nothing documents that one is not, and the
failure is the project's own CLI reporting `No module named 'saipen_engine'`.
An agent reaching for the module form reads that traceback as a broken protocol
install rather than as a wrong invocation -- and the repository disagreed with
itself about which form worked, since the test modules that DO insert the path
by hand ran fine under `python -m unittest` while fourteen others did not.

Importing `tools.anything` runs this file first, so the fix belongs here and
nowhere else: one owner, no per-file path munging to keep in sync, and nothing
changes for the script form, which already had the path it needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TOOLS = str(Path(__file__).resolve().parent)
if _TOOLS not in sys.path:
    # Appended, never prepended: the repository root stays ahead of this
    # directory, so a module form still resolves `tools.x` as `tools.x` and
    # this only ADDS the flat `saipen_engine` spelling the modules use.
    sys.path.append(_TOOLS)
