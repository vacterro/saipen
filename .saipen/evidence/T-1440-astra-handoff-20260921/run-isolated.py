"""Verify the exact dirty runtime manifest without HOME transport-file noise."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
from test_validator_layout_parity import _build_home
from test_hermetic_env import hermetic_env

target = Path(tempfile.mkdtemp(prefix="saipen-t1439-verified-")).resolve()
assert target.parent == Path(tempfile.gettempdir()).resolve()
_build_home(target, flatten=False)
# The runtime manifest intentionally omits development scenario fixtures.
shutil.copytree(root / "tests", target / "tests", dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__"))
env = hermetic_env()
for command in (
    ["git", "init", "-q"],
    ["git", "add", "--all"],
    ["git", "-c", "user.name=SAIPEN fixture", "-c", "user.email=fixture@saipen.local",
     "commit", "-q", "-m", "Disposable current runtime fixture"],
):
    subprocess.run(command, cwd=target, env=env, check=True, capture_output=True)

tests = sys.argv[1:] or [
    "tools.test_t1412_conformance_truth",
    "tools.test_remediation_self_consistency",
    "tools.test_continue_chain",
    "tools.test_source_quarantine_route",
    "tools.test_source_multiwork",
    "tools.test_debt_gate",
]
command = [sys.executable, "-B", "-m", "unittest", "-v", *tests]
record = {"source_root": str(root), "materialized_root": str(target), "command": command,
          "materialization": "current runtime manifest plus repository test resources; git fixture; no source substitutions",
          "removed_environment_names": sorted(set(__import__("os").environ) - set(env))}
Path(__file__).with_name("isolated-run.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps(record), flush=True)
result = subprocess.run(command, cwd=target, env=env, timeout=600)
raise SystemExit(result.returncode)
