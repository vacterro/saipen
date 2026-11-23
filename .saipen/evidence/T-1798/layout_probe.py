"""Verify the manifest's actual flat layout and its T-1771 closure controls."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.install_identity import install_fingerprint

manifest = json.loads((ROOT / "saipen" / "MANIFEST.json").read_text(encoding="utf-8"))
with tempfile.TemporaryDirectory(prefix="saipen-t1798-flat-") as temporary:
    flat = Path(temporary)
    for entry in manifest["files"]:
        relative = entry["src"]
        destination = relative.removeprefix("saipen/")
        path = flat / destination
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, path)
    for entry in manifest["copy_trees"]:
        shutil.copytree(
            ROOT / entry["src"], flat / entry["dst"], dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    source_identity = install_fingerprint(ROOT)
    flat_identity = install_fingerprint(flat)
    assert source_identity == flat_identity, (source_identity, flat_identity)
    relative = "tools/saipen_engine/regression_execution.py"
    assert hashlib.sha256((ROOT / relative).read_bytes()).digest() == hashlib.sha256((flat / relative).read_bytes()).digest()
    result = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tools", "-p", "test_t1771_measure_then_finish.py"],
        cwd=flat, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )
    print(result.stdout + result.stderr)
    assert result.returncode == 0, result.returncode
    print(json.dumps({"layout_parity": "PASS", "install_fingerprint": source_identity, "request_clause_engine_bytes": "IDENTICAL"}))
