"""T-1746: COUNTERFACTUAL step for the disposable copy only.

usage: python wintage_copy_counterfactual.py <engine_tools_dir> <copy_root> <real_root>

The real project holds two ACTIVE receipts no BOARD Work projects (SRC-002,
SRC-069), and the source gate refuses a terminal closure over them. That
refusal is correct and is the downstream project's own Work. To learn whether
another ENGINE obstacle hides behind it, this script discharges both receipts
IN THE COPY with a probe disposition. It proves nothing about those receipts
and must never be run on the real project.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    tools, copy_root, real_root = sys.argv[1:4]
    for key in [key for key in os.environ if key.startswith("SAIPEN")]:
        del os.environ[key]
    os.environ["FORBID_SAIPEN_PROJECT_WRITE"] = real_root
    sys.path.insert(0, tools)
    root = Path(copy_root).resolve()
    if root == Path(real_root).resolve():
        raise SystemExit("refusing to run on the real project")
    os.chdir(root)

    from saipen_engine import intake

    out = {}
    for receipt in ("SRC-002", "SRC-069"):
        added = intake.add_requirement(
            root, receipt, rid="R001", text="counterfactual probe clause (copy only)"
        )
        resolved = intake.set_disposition(
            root,
            receipt,
            "R001",
            "VERIFIED",
            evidence="E-1",
            verification="copy-probe:PASS",
        )
        out[receipt] = {
            "add": {key: added.get(key) for key in ("ok", "code", "detail")},
            "disposition": {key: resolved.get(key) for key in ("ok", "code", "detail")},
            "coverage_complete": intake.coverage_complete(root, receipt),
        }
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
