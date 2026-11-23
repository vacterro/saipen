"""Prepare an isolated draft subject while canonical bounded Work is paused."""

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
from saipen_engine.core_unit import tree_fingerprint  # noqa: E402
from saipen_engine.test_runner import _ignore_copy  # noqa: E402

evidence = Path(__file__).resolve().parent
workspace = Path(tempfile.mkdtemp(prefix="saipen-t1704-draft-"))
subject = workspace / "subject"


def ignore(directory, names):
    result = _ignore_copy(directory, names)
    if Path(directory) == root:
        result.update({".git", ".saipen"})
    return result


before = tree_fingerprint(root)
protected = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
             for name in (".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md")}
shutil.copytree(root, subject, symlinks=True, ignore=ignore)
copied = tree_fingerprint(subject)
after = tree_fingerprint(root)
if not before == copied == after:
    raise RuntimeError("Source changed during isolated draft copy; draft not admitted")
fixture = subject / "tests/fixtures/t1703-valve-audit.json"
fixture.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(root / ".saipen/evidence/T-1704-admission/counterexample.json", fixture)
record = {"root": str(root), "workspace": str(workspace), "subject": str(subject),
          "baseline_fingerprint": before, "canonical_sha256": protected,
          "canonical_state_copied": False, "persistent_authority_granted": False,
          "code_applied_to_live_root": False}
(evidence / "location.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record, indent=2))
