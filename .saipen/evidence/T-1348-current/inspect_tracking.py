"""Read the intent flag as a bit mask after the initial exact-mask error."""

from __future__ import annotations

import hashlib
import json
import re
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


if __name__ == "__main__":
    record_path = ROOT / ".saipen/evidence/core-unit/73a0535196e5c013-20261003T164017Z.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    current = tree_fingerprint(ROOT)
    assert current == record["fingerprint"]
    assert record["verdict"] == "PASS" and record["ran"] == 4876
    assert not git("diff", "--cached", "--raw")
    debug = git("ls-files", "--debug", "--", *OWNED)
    flags = [int(value, 16) for value in re.findall(r"flags: ([0-9a-f]+)", debug)]
    assert len(flags) == 2 and all(value & 0x20000000 for value in flags), debug
    stage = git("ls-files", "--stage", "--", *OWNED)
    assert stage.count("e69de29bb2d1d6434b8b29ae775ad8c2e48c5391") == 2
    result = {"owned_intent_to_add": list(OWNED), "source_unchanged": True,
              "fingerprint": current, "actual_flags": [hex(value) for value in flags],
              "required_intent_bit": "0x20000000", "staged_blobs_empty": True,
              "native_family_record": str(record_path.relative_to(ROOT)),
              "native_family_record_sha256": hashlib.sha256(record_path.read_bytes()).hexdigest(),
              "initial_wrapper_error": "Exact 20104000 mask rejected valid 20004000 flags",
              "foreign_index_preservation": "Initial track_owned.py passed foreign-entry and staged-blob comparisons before line 46 failed; no mutation repeated",
              "published": False}
    (EVIDENCE / "tracking-inspected.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
