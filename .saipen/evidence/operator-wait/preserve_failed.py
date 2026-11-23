"""Preserve the failed candidate and restore only this Work's owned edits."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
SAVED = ROOT / ".saipen/kitchen/failed/T-1606"
BEFORE = ROOT / ".saipen/evidence/operator-wait/before"
PATHS = (
    "saipen/REGISTRY.json", "saipen/COMMANDS.md", "tools/saipen.py", "tools/validate.py",
    "tools/saipen_engine/state.py", "tools/saipen_engine/phases.py",
    "tools/saipen_engine/fast_check.py", "tools/saipen_engine/reconcile.py",
    "tools/saipen_engine/operations.py", "tools/saipen_engine/subs.py",
    "tools/saipen_engine/router.py", "tools/test_next_action_deadlock.py",
    "tools/test_refusal_registry.py", "tools/test_recovery_reachability.py",
    "tools/test_next_action_grammar.py",
)
assert not SAVED.exists(), "failed candidate is already preserved"
SAVED.mkdir(parents=True)
rows = []
for relative in PATHS:
    source = ROOT / relative
    assert source.resolve().is_relative_to(ROOT.resolve()) and not source.is_symlink()
    raw = source.read_bytes()
    target = SAVED / "candidate" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    original = BEFORE / relative
    if original.is_file():
        restored = original.read_bytes()
    elif relative == "tools/saipen_engine/router.py":
        restored = subprocess.check_output(["git", "show", "HEAD:" + relative], cwd=ROOT)
    else:
        assert relative == "tools/test_next_action_grammar.py"
        restored = None
    rows.append({
        "path": relative, "candidate_sha256": hashlib.sha256(raw).hexdigest(),
        "restore_sha256": hashlib.sha256(restored).hexdigest() if restored is not None else None,
    })
    # New file is moved separately by native PowerShell after this save.
    if restored is not None:
        assert source.read_bytes() == raw, f"concurrent edit: {relative}"
        source.write_bytes(restored)
(SAVED / "manifest.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
patch = subprocess.check_output(
    ["git", "diff", "--no-index", "--", str(BEFORE), str(SAVED / "candidate")],
    cwd=ROOT,
) if False else None
print(json.dumps({"preserved": len(rows), "restored_tracked": len(rows) - 1,
                  "new_file": "tools/test_next_action_grammar.py", "directory": str(SAVED)}))
