"""Prepare an isolated A05 candidate; never apply source changes to the live tree."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.core_unit import tree_fingerprint
from saipen_engine.test_runner import _ignore_copy


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    output = HERE / "scratch-preparation.json"
    if output.exists():
        raise RuntimeError("scratch descriptor already exists; inspect it instead of overwriting")
    before = tree_fingerprint(ROOT)
    base = Path(tempfile.mkdtemp(prefix="saipen-a05-candidate-", dir="V:/_TEMP_"))
    project = base / "project"

    def ignore(directory: str, names: list[str]) -> set[str]:
        excluded = _ignore_copy(directory, names)
        if Path(directory) == ROOT:
            excluded |= {".git", ".saipen"}
        return excluded

    shutil.copytree(ROOT, project, symlinks=True, ignore=ignore)
    owned = ["tools/saipen_engine/reconcile.py", "tools/saipen.py",
             "tools/test_reconcile_history_ledger_blocked.py"]
    preimages = {}
    for relative in owned:
        raw = (ROOT / relative).read_bytes()
        if (project / relative).read_bytes() != raw:
            raise RuntimeError("scratch differs before preparation: " + relative)
        target = base / "before" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        preimages[relative] = {"sha256": sha(raw), "path": str(target)}
    if tree_fingerprint(ROOT) != before:
        raise RuntimeError("live source moved during scratch copy")
    descriptor = {"ok": True, "purpose": "A05 preparation while T-1713 owns VERIFY",
                  "project": str(project), "live_fingerprint": before,
                  "preimages": preimages, "live_source_mutated": False,
                  "limitations": "Root Git and protocol memory were deliberately excluded. "
                                  "This is not a copied AUDAPACK ledger or a canonical T-1714 phase proof."}
    output.write_text(json.dumps(descriptor, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(descriptor))


if __name__ == "__main__":
    main()
