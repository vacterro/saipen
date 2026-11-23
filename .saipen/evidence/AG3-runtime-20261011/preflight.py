"""Read-only subject probe with injected Windows denial; no real ACL changes."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import traceback
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import audit_manifest  # noqa: E402


def inventory(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


def probe() -> dict:
    cases = []
    for kind in ("accessible", "missing", "ancestor-denied", "manifest-inspection-denied"):
        with tempfile.TemporaryDirectory(prefix="saipen-ag3-boundary-") as tmp:
            base = Path(tmp)
            root = base / "granted-project"
            if kind != "missing":
                memory = root / ".saipen"
                memory.mkdir(parents=True)
                for name in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md"):
                    (memory / name).write_text("fixture\n", encoding="utf-8")
            before = inventory(base)
            blocked = base if kind == "ancestor-denied" else root / ".saipen" / "MANIFEST.json"
            error = PermissionError(13, "Access is denied", str(blocked))
            error.winerror = 5
            actual_lstat = Path.lstat

            def lstat(path, *args, **kwargs):
                if kind.endswith("denied") and path == blocked:
                    raise error
                return actual_lstat(path, *args, **kwargs)

            item = {"case": kind, "injected": kind.endswith("denied"), "blocked_path": str(blocked)}
            with patch.object(Path, "lstat", lstat):
                try:
                    item["result"] = audit_manifest.ensure(root)
                except Exception as exc:
                    context = exc.__context__
                    item["escaped"] = {
                        "type": type(exc).__name__, "message": str(exc),
                        "context_type": type(context).__name__ if context else None,
                        "context_errno": getattr(context, "errno", None),
                        "context_winerror": getattr(context, "winerror", None),
                        "context_filename": getattr(context, "filename", None),
                        "frames": [
                            {"name": f.name, "line": f.lineno, "file": f.filename}
                            for f in traceback.extract_tb(exc.__traceback__)
                        ],
                    }
            after = inventory(base)
            item["bytes_unchanged"] = before == after
            item["added_paths"] = sorted(set(after) - set(before))
            cases.append(item)
    subject = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in ("tools/saipen_engine/audit_manifest.py", "tools/saipen_engine/paths.py",
                     "tools/saipen_engine/reconcile.py")
    }
    return {"scope": "injected permission failure, current subject; not an AG3-token execution",
            "subject": subject, "cases": cases}


if __name__ == "__main__":
    result = probe()
    Path(__file__).with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
