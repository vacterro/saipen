"""Append only exact known object preimages; never edit refs, index or source."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

root = Path.cwd().resolve()
evidence = root / ".saipen/evidence/T-1829-cost-collapse"
recovery = evidence / "git-object-recovery"
recovery.mkdir(exist_ok=False)
inventory = json.loads((evidence / "local-blob-recovery-inventory.json").read_text())
env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never",
       "GIT_NO_LAZY_FETCH": "1"}


def git(*args, data=None, selected_env=env):
    return subprocess.run(["git", "-c", "core.commitGraph=false", *args],
                          input=data, capture_output=True, env=selected_env, check=True).stdout


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def object_id(kind, raw):
    return hashlib.sha1(kind.encode() + b" " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


head_before = git("rev-parse", "HEAD")
refs_before = git("for-each-ref", "--format=%(objectname) %(refname)")
entries_before = git("ls-files", "--stage", "-z")
index_path = Path(git("rev-parse", "--git-path", "index").decode().strip()).resolve()
index_before = index_path.read_bytes()
(recovery / "refs-before.txt").write_bytes(refs_before)
(recovery / "index-before.bin").write_bytes(index_before)
(recovery / "entries-before.bin").write_bytes(entries_before)

restored = []
declined = []
for expected, item in inventory["recoverable_blobs"].items():
    path = (root / item["path"]).resolve()
    path.relative_to(root)
    raw = path.read_bytes()
    if item["variant"] == "lf":
        raw = raw.replace(b"\r\n", b"\n")
    elif item["variant"] == "crlf":
        raw = raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    if digest(raw) != item["sha256"] or object_id("blob", raw) != expected:
        declined.append(expected)
        continue
    actual = git("hash-object", "-w", "-t", "blob", "--stdin", data=raw).decode().strip()
    if actual != expected:
        raise RuntimeError("Git rejected exact blob identity")
    restored.append({"oid": expected, "type": "blob", **item})

# Reconstruct authoritative staged directory inventories only in a private
# index/object store. Missing historical tree preimages may match unchanged
# staged directories; unrelated candidate trees stay private.
objects = recovery / "candidate-objects"
objects.mkdir()
root_objects = Path(git("rev-parse", "--git-path", "objects").decode().strip()).resolve()
private_env = {**env, "GIT_INDEX_FILE": str(recovery / "candidate-index"),
               "GIT_OBJECT_DIRECTORY": str(objects),
               "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(root_objects)}
git("update-index", "-z", "--index-info", data=entries_before, selected_env=private_env)
candidate_root = git("write-tree", "--missing-ok", selected_env=private_env).decode().strip()
known_missing = set(inventory["unmatched"])
trees = []
for directory in objects.iterdir():
    if not directory.is_dir() or len(directory.name) != 2:
        continue
    for path in directory.iterdir():
        expected = directory.name + path.name
        if expected not in known_missing:
            continue
        kind = git("cat-file", "-t", expected, selected_env=private_env).decode().strip()
        if kind != "tree":
            raise RuntimeError("Unexpected reconstructed object type")
        raw = git("cat-file", "tree", expected, selected_env=private_env)
        if object_id("tree", raw) != expected:
            raise RuntimeError("Candidate tree identity changed")
        actual = git("hash-object", "-w", "-t", "tree", "--stdin", data=raw).decode().strip()
        if actual != expected:
            raise RuntimeError("Git rejected exact tree identity")
        trees.append(expected)

checks = {"head_unchanged": git("rev-parse", "HEAD") == head_before,
          "refs_unchanged": git("for-each-ref", "--format=%(objectname) %(refname)") == refs_before,
          "index_bytes_unchanged": index_path.read_bytes() == index_before,
          "index_entries_unchanged": git("ls-files", "--stage", "-z") == entries_before}
report = {"checks": checks, "restored_blobs": restored, "declined_changed_preimages": declined,
          "restored_trees": trees, "candidate_root": candidate_root,
          "source": "exact local Git object preimages; no inferred/fabricated payload",
          "remaining_history": "must be measured again; no complete-recovery claim"}
(recovery / "receipt.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
if not all(checks.values()):
    raise RuntimeError("Repository identity preservation check failed")
print(json.dumps({"restored_blobs": len(restored), "restored_trees": len(trees),
                  "declined": len(declined), **checks}))
