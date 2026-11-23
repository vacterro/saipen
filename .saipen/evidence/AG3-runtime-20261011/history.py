"""Bounded Git attribution and executable historical boundary reproduction."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))


def git(*args: str) -> bytes:
    run = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True)
    return run.stdout


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    snapshots = HERE / "historical-subjects"
    snapshots.mkdir(exist_ok=True)
    versions = {
        "paths-dbbfad946.py": ("dbbfad946", "tools/saipen_engine/paths.py"),
        "manifest-8f91d779.py": ("8f91d779", "tools/saipen_engine/audit_manifest.py"),
        "manifest-c7e25f92.py": ("c7e25f92", "tools/saipen_engine/audit_manifest.py"),
        "reconcile-b2343541.py": ("b2343541", "tools/saipen_engine/reconcile.py"),
    }
    subjects = {}
    for filename, (commit, path) in versions.items():
        data = git("show", f"{commit}:{path}")
        destination = snapshots / filename
        if destination.exists() and destination.read_bytes() != data:
            raise RuntimeError(f"historical snapshot changed: {destination}")
        destination.write_bytes(data)
        subjects[filename] = {"commit": git("rev-parse", commit).decode().strip(),
                              "git_path": path, "sha256": hashlib.sha256(data).hexdigest()}
    old_paths = load("saipen_engine.ag3_historical_paths", snapshots / "paths-dbbfad946.py")
    results = []
    for filename in ("manifest-8f91d779.py", "manifest-c7e25f92.py"):
        module = load("saipen_engine.ag3_" + filename.replace("-", "_").replace(".", "_"),
                      snapshots / filename)
        module.safe_atomic_write_bytes = old_paths.safe_atomic_write_bytes
        with tempfile.TemporaryDirectory(prefix="saipen-ag3-history-") as tmp:
            ancestor = Path(tmp)
            root = ancestor / "project"
            memory = root / ".saipen"
            memory.mkdir(parents=True)
            for name in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md"):
                (memory / name).write_text("fixture\n", encoding="utf-8")
            before = {p.name: p.read_bytes() for p in memory.iterdir()}
            denied = PermissionError(13, "Access is denied", str(ancestor))
            denied.winerror = 5
            original = Path.lstat

            def lstat(path, *args, **kwargs):
                if path == ancestor:
                    raise denied
                return original(path, *args, **kwargs)

            record = {"manifest_subject": filename, "paths_subject": "paths-dbbfad946.py",
                      "scope": "exact committed modules; current stdlib and explicit protocol_dir",
                      "injected_denial": True}
            with patch.object(Path, "lstat", lstat):
                try:
                    record["result"] = module.ensure(root, protocol_dir=ROOT / "saipen")
                except Exception as exc:
                    record["escaped"] = {"type": type(exc).__name__, "message": str(exc),
                                          "windows_error": getattr(exc.__context__, "winerror", None),
                                          "frames": [{"function": f.name, "line": f.lineno,
                                                      "file": f.filename}
                                                     for f in traceback.extract_tb(exc.__traceback__)]}
            record["canonical_bytes_unchanged"] = before == {p.name: p.read_bytes() for p in memory.iterdir()}
            results.append(record)
    history = {}
    for filename in ("audit_manifest.py", "paths.py", "host_bootstrap.py", "machine_runtime.py",
                     "protocol_admission.py", "admission.py", "state.py", "reconcile.py"):
        path = "tools/saipen_engine/" + filename
        history[path] = git("log", "-8", "--format=%H %aI %an %s", "--", path).decode()
    log = (ROOT / ".saipen/logs/LOG-017.md").read_text(encoding="utf-8")
    log_rows = [line for line in log.splitlines() if "[T-1328]" in line]
    historical_board = git("show", "dbbfad946:.saipen/BOARD.md").decode("utf-8-sig")
    owner_1171 = [line for line in historical_board.splitlines() if " T-1171 " in line]
    result = {"subjects": subjects, "reproductions": results, "history": history,
              "T1328_canonical_log": log_rows, "T1171_committed_board": owner_1171,
              "attribution_limit": "Git VAC34 is an author identity, not a model; T1328 codex records ownership of registration and verification, explicitly not original implementation. No verified previous Gemini executor boundary supplied."}
    (HERE / "history.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"historical_reproductions": results, "T1328_events": len(log_rows),
                      "T1171_owner_record": owner_1171, "evidence": str(HERE / "history.json")}, indent=2))


if __name__ == "__main__":
    main()
