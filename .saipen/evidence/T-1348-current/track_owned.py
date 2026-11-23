"""Add only new owned intent entries; preserve every existing index blob."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[2]
OWNED = ("tools/_module_identity.py", "tools/test_tool_module_identity.py")
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.core_unit import tree_fingerprint


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT).decode("utf-8")


def foreign_entries() -> str:
    return "\0".join(row for row in git("ls-files", "--stage", "-z").split("\0")
                     if row and row.split("\t", 1)[1] not in OWNED)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


if __name__ == "__main__":
    output = EVIDENCE / "tracking.json"
    assert not output.exists(), "immutable tracking receipt already exists"
    before = foreign_entries()
    before_cached = git("diff", "--cached", "--raw")
    assert not git("ls-files", "--", *OWNED)
    assert not before_cached, "unexpected existing staged blobs; preserve and inspect"
    subject = tree_fingerprint(ROOT)
    subprocess.run(["git", "add", "-N", "--", *OWNED], cwd=ROOT, check=True)
    after = foreign_entries()
    after_cached = git("diff", "--cached", "--raw")
    assert before == after, "foreign index entries changed"
    assert before_cached == after_cached, "staged blobs changed"
    assert subject == tree_fingerprint(ROOT), "source bytes changed"
    debug = git("ls-files", "--debug", "--", *OWNED)
    assert debug.count("flags: 20104000") == 2, debug
    result = {"owned_intent_to_add": list(OWNED), "fingerprint": subject,
              "source_unchanged": True, "foreign_index_entries_unchanged": True,
              "foreign_index_entries_sha256": sha(before),
              "staged_blobs_unchanged": True, "staged_blobs_empty": not after_cached,
              "index_debug": debug, "published": False}
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
