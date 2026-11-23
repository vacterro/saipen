"""Copy only accepted production deltas into the isolated release worktree."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[3]
DEST = Path("V:/_SAIPEN_RELEASE_/public-20261004").resolve()
assert DEST.is_dir() and (DEST / ".git").is_file()
paths = [
    "saipen/BOOT.md", "saipen/COMMANDS.md", "saipen/COMMAND_EFFECTS.json",
    "saipen/CORE.md", "saipen/OPS.md",
    "tools/__init__.py", "tools/_module_identity.py",
    "tools/run_scenarios.py", "tools/saipen.py", "tools/saipen_engine/evidence.py",
    "tools/saipen_engine/journal.py",
    "tools/saipen_engine/operations.py", "tools/test_closure_provenance.py",
    "tools/test_evidence_hygiene.py", "tools/test_module_duplication_guard.py",
    "tools/test_protocol_registry.py", "tools/test_t1515_posix_shell_entry.py",
    "tools/test_tool_module_identity.py",
]
cohorts = json.loads((ROOT / ".saipen/kitchen/cohort_registry.json").read_text(encoding="utf-8"))["cohorts"]
owned = {}
for cid, cohort in cohorts.items():
    for tid, member in cohort["members"].items():
        for relative in member["paths"]:
            owned.setdefault(relative, []).append({"cohort": cid, "ticket": tid})
# T-1607 explicitly adopts the inspected BOOT shortcut correction: it routes
# cold agents to the one authoritative map without duplicating that map.
owned["saipen/BOOT.md"] = [{"ticket": "T-1607", "review": "inspected HEAD delta; cold-start acceptance SRC-168:R004"}]
missing = [relative for relative in paths if relative not in owned]
assert not missing, f"Unattributed accepted paths: {missing}"
manifest = []
before = ROOT / ".saipen/evidence/public-release/candidate-before"
for relative in paths:
    assert relative in owned, f"Unattributed accepted path: {relative}"
    src, dst = ROOT / relative, DEST / relative
    assert src.is_file() and dst.resolve().is_relative_to(DEST)
    if dst.exists():
        saved = before / relative
        saved.parent.mkdir(parents=True, exist_ok=True)
        assert not saved.exists(), f"do not overwrite evidence: {saved}"
        shutil.copyfile(dst, saved)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    # The source-normalization feature is blocked Work T-1507. It shares the
    # accepted CLI/docs paths but is outside this public stability release.
    text = dst.read_text(encoding="utf-8") if relative.endswith((".py", ".md", ".json")) else None
    if relative == "tools/saipen.py":
        start = text.index('    if action == "normalize":\n', text.index("def _source("))
        end = text.index('    if action == "recover":\n', start)
        text = text[:start] + text[end:]
        text = text.replace("recover|reconcile|normalize|", "recover|reconcile|")
        text = text.replace("|source normalize [--dry-run]|", "|")
    elif relative == "saipen/COMMANDS.md":
        text = "".join(line for line in text.splitlines(keepends=True) if not line.startswith("| `saipen source normalize "))
    elif relative == "saipen/COMMAND_EFFECTS.json":
        text = text.replace('        "normalize": "RECOVERY",\n', "")
    if text is not None and text != dst.read_text(encoding="utf-8"):
        dst.write_text(text, encoding="utf-8", newline="\n")
    manifest.append({"path": relative, "sha256": hashlib.sha256(src.read_bytes()).hexdigest(), "accepted_by": owned[relative]})
(ROOT / ".saipen/evidence/public-release/accepted-paths.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"copied": len(manifest), "destination": str(DEST)}))
