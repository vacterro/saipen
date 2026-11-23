"""Verify the actual backup Git tree against source bytes and the untouched main index."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parent
plan = json.loads((FOLDER / "prepared.json").read_text(encoding="utf-8"))
manifest = json.loads((ROOT / plan["manifest"]).read_text(encoding="utf-8"))
env = os.environ.copy()
for key in ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
    env.pop(key, None)
env["GIT_OPTIONAL_LOCKS"] = "0"
env["GIT_TERMINAL_PROMPT"] = "0"


def git(*args, auxiliary=False, data=None):
    command = ["git"]
    if auxiliary:
        command += ["--git-dir", plan["auxiliary_git_dir"]]
    result = subprocess.run(command + list(args), cwd=ROOT, env=env, input=data,
                            capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-2000:])
    return result.stdout


entries = {}
for entry in git("ls-files", "--stage", "-z", auxiliary=True).split(b"\0"):
    if not entry:
        continue
    header, path = entry.split(b"\t", 1)
    mode, blob, stage = header.decode("ascii").split()
    if stage != "0":
        raise RuntimeError("the backup index has an unresolved entry")
    entries[os.fsdecode(path)] = (mode, blob)
for item in manifest["files"]:
    path = ROOT / item["path"]
    if item["kind"] == "deleted":
        if path.exists() or path.is_symlink() or item["path"] in entries:
            raise RuntimeError("a declared deletion changed")
        continue
    raw = os.fsencode(os.readlink(path)) if item["kind"] == "symlink" else path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != item["sha256"]:
        raise RuntimeError("a source file moved: " + item["path"])
    expected = (
        git("hash-object", "--stdin", data=raw).decode().strip()
        if item["kind"] == "symlink"
        else git("hash-object", "--path=" + item["path"], item["path"]).decode().strip()
    )
    if entries.get(item["path"], (None, None))[1] != expected:
        raise RuntimeError("a backup blob differs from the source: " + item["path"])
expected_manifest = git("hash-object", "--path=" + plan["manifest"], plan["manifest"]).decode().strip()
if entries.get(plan["manifest"], (None, None))[1] != expected_manifest:
    raise RuntimeError("the staged manifest moved")
actual_tree = git("write-tree", auxiliary=True).decode().strip()
if actual_tree != plan["tree"]:
    raise RuntimeError("the prepared Git tree moved")
head = git("rev-parse", "HEAD").decode().strip()
branch = git("symbolic-ref", "--short", "HEAD").decode().strip()
index = Path(git("rev-parse", "--path-format=absolute", "--git-path", "index").decode().strip())
original_env = {**env, "GIT_INDEX_FILE": str(FOLDER / "original-index.bin")}
original_entries = subprocess.run(["git", "ls-files", "--stage", "-z"], cwd=ROOT,
                                  env=original_env, capture_output=True, check=True,
                                  timeout=30).stdout
current_entries = git("ls-files", "--stage", "-z")
if (head != plan["base"] or branch != plan["original_branch"]
        or current_entries != original_entries):
    raise RuntimeError("the main HEAD, branch or staged entries moved")
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.core_unit import tree_fingerprint  # noqa: E402

if tree_fingerprint(ROOT) != plan["source_fingerprint"]:
    raise RuntimeError("the tested working source changed")
result = {"verdict": "PASS", "checked_source_paths": len(manifest["files"]),
          "tree": actual_tree, "main_head_and_staged_entries_preserved": True,
          "original_index_bytes_unchanged": hashlib.sha256(index.read_bytes()).hexdigest() == plan["original_index_sha256"],
          "source_fingerprint": plan["source_fingerprint"], "push_pending": True}
(FOLDER / "prepared-verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
