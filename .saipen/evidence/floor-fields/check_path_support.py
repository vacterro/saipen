"""Re-run the unchanged failed control with process-local Git path support."""

import contextlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import audit_checks as audit  # noqa: E402

count = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
os.environ[f"GIT_CONFIG_KEY_{count}"] = "core.longpaths"
os.environ[f"GIT_CONFIG_VALUE_{count}"] = "true"
os.environ["GIT_CONFIG_COUNT"] = str(count + 1)
with tempfile.TemporaryDirectory(prefix="saipen-path-support-") as temporary:
    context = audit.ProbeContext(Path(temporary), [], None)
    assert audit.build_pristine(context) is None
    error = audit.warn_ownership_probe(context.pristine, context.tmp)
    result = {"ok": error is None, "error": error,
              "verification_configuration": "process-local core.longpaths=true",
              "probe": "unchanged audit_checks.warn_ownership_probe"}
    evidence = Path(__file__).resolve().parent / "longpath-warn-control.json"
    evidence.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result), flush=True)
    raise SystemExit(0 if error is None else 1)
