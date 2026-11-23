"""Exact-only recovery from Git's retained scratch files and private indices."""
import hashlib
import json
import os
import stat
import subprocess
import time
import zlib
from pathlib import Path

root = Path.cwd().resolve()
evidence = root / ".saipen/evidence/T-1829-cost-collapse"
store = evidence / ("auxiliary-recovery-" + str(time.time_ns()))
store.mkdir()
env = {**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"}


def git(*args, data=None, selected_env=env):
    return subprocess.run(["git", "-c", "core.commitGraph=false", *args], input=data,
                          capture_output=True, check=True, env=selected_env).stdout


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def identity():
    return {"head": git("rev-parse", "HEAD").decode().strip(),
            "refs": digest(git("for-each-ref", "--format=%(objectname) %(refname)")),
            "index": digest((root / ".git/index").read_bytes()),
            "entries": digest(git("ls-files", "--stage", "-z"))}


before = identity()
missing = {line[1:].decode() for line in git("rev-list", "--objects", "--missing=print", "HEAD").splitlines()
           if line.startswith(b"?")}
restored = []
inspected = 0


def admit(kind, raw, source, variant):
    oid = hashlib.sha1(kind.encode() + b" " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if oid not in missing:
        return
    actual = git("hash-object", "-w", "-t", kind, "--stdin", data=raw).decode().strip()
    if actual != oid:
        raise RuntimeError("Object identity mismatch")
    missing.remove(oid)
    restored.append({"oid": oid, "type": kind, "source": str(source),
                     "variant": variant, "sha256": digest(raw)})


# The main object database has already been queried. Scratch/lost-found files
# and nested test repositories were excluded by the earlier workspace search.
for directory, dirs, files in os.walk(root / ".git", followlinks=False):
    directory = Path(directory)
    dirs[:] = [name for name in dirs if not (directory == root / ".git" and name == "objects")
               and not (directory / name).is_symlink()]
    for name in files:
        path = directory / name
        info = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 32 * 1024 * 1024:
            continue
        raw = path.read_bytes()
        inspected += 1
        if path.parent.name + name in missing and len(path.parent.name) == 2:
            try:
                header, payload = zlib.decompress(raw).split(b"\0", 1)
                kind, size = header.split()
                if int(size) == len(payload):
                    admit(kind.decode(), payload, path, "loose-object")
            except (ValueError, zlib.error):
                pass
        lf = raw.replace(b"\r\n", b"\n")
        for variant, payload in (("raw", raw), ("lf", lf), ("crlf", lf.replace(b"\n", b"\r\n"))):
            for kind in ("blob", "commit", "tree", "tag"):
                admit(kind, payload, path, variant)

# Probe known installed runtime generations only, using exact source locators.
rows = json.loads((evidence / "missing-object-paths.json").read_text())
for runtime in (Path("C:/ProgramData/SAI/SAIPEN/runtime/06b7c9ab48edff45"),
                Path("C:/ProgramData/SAI/SAIPEN/runtime/b465d0bc64c60308")):
    for row in rows:
        if row["oid"] not in missing or row["mode"] != "100644":
            continue
        path = runtime / row["parent_path"] / row["name"]
        if not path.is_file():
            continue
        raw = path.read_bytes()
        lf = raw.replace(b"\r\n", b"\n")
        inspected += 1
        for variant, payload in (("raw", raw), ("lf", lf), ("crlf", lf.replace(b"\n", b"\r\n"))):
            admit("blob", payload, path, variant)

indices = list((root / ".git").glob("*.index"))
indices += list((root / ".git/worktrees").glob("*/index"))
index_results = []
for number, index in enumerate(indices):
    index_before = digest(index.read_bytes())
    objects = store / ("objects-" + str(number))
    objects.mkdir()
    candidate_env = {**env, "GIT_INDEX_FILE": str(store / ("index-" + str(number))),
                     "GIT_OBJECT_DIRECTORY": str(objects),
                     "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(root / ".git/objects")}
    row = {"source": str(index), "sha256_before": index_before}
    try:
        entries = git("ls-files", "--stage", "-z", selected_env={**env, "GIT_INDEX_FILE": str(index)})
        git("update-index", "-z", "--index-info", data=entries, selected_env=candidate_env)
        row["candidate_root"] = git("write-tree", "--missing-ok", selected_env=candidate_env).decode().strip()
        for folder in objects.iterdir():
            if folder.is_dir() and len(folder.name) == 2:
                for item in folder.iterdir():
                    if folder.name + item.name in missing:
                        raw = git("cat-file", "tree", folder.name + item.name, selected_env=candidate_env)
                        admit("tree", raw, index, "exact-index-inventory")
    except subprocess.CalledProcessError as exc:
        row["error"] = exc.stderr.decode(errors="replace")[:1000]
    row["sha256_after"] = digest(index.read_bytes())
    if row["sha256_before"] != row["sha256_after"]:
        raise RuntimeError("Original index changed")
    index_results.append(row)

after = identity()
connectivity = git("rev-list", "--objects", "--missing=print", "HEAD")
(store / "connectivity.txt").write_bytes(connectivity)
remaining = sorted(line[1:].decode() for line in connectivity.splitlines() if line.startswith(b"?"))
report = {"restored": restored, "remaining": remaining, "indices": index_results,
          "inspected_files": inspected, "before": before, "after": after,
          "identity_preserved": before == after}
(store / "receipt.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
if before != after:
    raise RuntimeError("Original repository identity changed")
print(json.dumps({"receipt": str(store / "receipt.json"), "restored": len(restored),
                  "remaining": len(remaining), "inspected_files": inspected,
                  "indices": len(indices), "identity_preserved": True}))
