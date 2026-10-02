"""Emit a bounded apply_patch only for a hash-bound same-oracle red/green pair."""
from __future__ import annotations

import difflib
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
directory = (ROOT / sys.argv[1]).resolve()
if not directory.is_relative_to(ROOT / ".saipen/evidence"):
    raise RuntimeError("candidate must remain inside project evidence")
manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
controls = manifest["controls"]
if len(controls) != 2 or controls[0]["passed"] or not controls[1]["passed"]:
    raise RuntimeError("candidate lacks measured red before / green after")
oracle_hash = manifest["oracle"]["after_sha256"]
if any(control["oracle_sha256"] != oracle_hash for control in controls):
    raise RuntimeError("verifier changed between red and green")
patches = ["*** Begin Patch"]
for kind in ("subject", "oracle"):
    record = manifest[kind]
    rel = record["path"]
    target = (ROOT / rel).resolve()
    if not target.is_relative_to(ROOT):
        raise RuntimeError("candidate target escapes the project")
    draft = directory / (target.name + ".draft")
    updated = draft.read_bytes()
    if hashlib.sha256(updated).hexdigest() != record["after_sha256"]:
        raise RuntimeError("candidate bytes changed after controls")
    if "before_sha256" not in record:
        if target.exists():
            raise RuntimeError("new test target is no longer absent")
        patches.append("*** Add File: " + rel)
        patches.extend("+" + line for line in updated.decode("utf-8").splitlines())
        continue
    original = target.read_bytes()
    if hashlib.sha256(original).hexdigest() != record["before_sha256"]:
        raise RuntimeError("live subject changed after candidate construction")
    (directory / (target.name + ".before")).write_bytes(original)
    diff = list(difflib.unified_diff(
        original.decode("utf-8").splitlines(), updated.decode("utf-8").splitlines(), n=3,
    ))
    if not diff:
        raise RuntimeError("candidate is not a change")
    patches.append("*** Update File: " + rel)
    for line in diff[2:]:
        patches.append("@@" if line.startswith("@@") else line)
patches.append("*** End Patch")
print("\n".join(patches))
