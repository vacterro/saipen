"""Recover only hash-identical missing Git objects from existing directories.

Candidate tree names/modes never become history unless their complete serialized
preimage hashes to an object Git already requests. No refs/index/worktree edits.
"""
import base64
import gzip
import hashlib
import json
import os
import stat
import subprocess
import time
from pathlib import Path

ROOT = Path.cwd().resolve()
EVIDENCE = ROOT / ".saipen/evidence/T-1829-cost-collapse"
ENV = {**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"}
START = time.monotonic()


def git(*args, data=None):
    return subprocess.run(
        ["git", "-c", "core.commitGraph=false", *args], input=data,
        capture_output=True, check=True, env=ENV,
    ).stdout


def oid(kind, raw):
    return hashlib.sha1(kind.encode() + b" " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def identity():
    index = Path(git("rev-parse", "--git-path", "index").decode().strip()).resolve()
    return {
        "head": git("rev-parse", "HEAD").decode().strip(),
        "refs": hashlib.sha256(git("for-each-ref", "--format=%(objectname) %(refname)")).hexdigest(),
        "index": hashlib.sha256(index.read_bytes()).hexdigest(),
        "entries": hashlib.sha256(git("ls-files", "--stage", "-z")).hexdigest(),
    }


before = identity()
missing = {line[1:].decode() for line in git("rev-list", "--objects", "--missing=print", "HEAD").splitlines()
           if line.startswith(b"?")}
initial_missing = sorted(missing)
control = git("rev-parse", "HEAD^{tree}").decode().strip()
if oid("tree", git("cat-file", "tree", control)) != control:
    raise RuntimeError("Tree serialization positive control failed")
if oid("tree", git("cat-file", "tree", control) + b"bad") == control:
    raise RuntimeError("Tree serialization negative control failed")

mode_map = {}
for entry in git("ls-files", "--stage", "-z").split(b"\0"):
    if entry:
        header, name = entry.split(b"\t", 1)
        mode_map[name.decode("utf-8")] = header.split()[0]

restored = []
candidates = {}
counts = {"files": 0, "directories": 0, "bytes": 0, "skipped": 0}
excluded = {".git", "__pycache__", ".ruff_cache", ".mypy_cache", ".pytest_cache"}
profiles = [(newline, modes) for newline in ("raw", "lf", "crlf")
            for modes in ("regular", "index")]


def admit(kind, raw, path, profile):
    digest = oid(kind, raw)
    if digest not in candidates:
        candidates[digest] = (kind, raw if kind in ("tree", "commit") else None, path, profile)
    if digest in missing:
        actual = git("hash-object", "-w", "-t", kind, "--stdin", data=raw).decode().strip()
        if actual != digest:
            raise RuntimeError("Git object identity disagreement")
        restored.append({"oid": digest, "type": kind, "path": path,
                         "profile": profile, "sha256": hashlib.sha256(raw).hexdigest()})
        missing.remove(digest)
    return bytes.fromhex(digest)


def visit(directory):
    entries = {profile: [] for profile in profiles}
    complete = True
    try:
        children = list(os.scandir(directory))
    except OSError:
        counts["skipped"] += 1
        return None
    for entry in children:
        if entry.name in excluded:
            continue
        path = Path(entry.path)
        rel = path.relative_to(ROOT).as_posix()
        try:
            info = entry.stat(follow_symlinks=False)
            if entry.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                counts["skipped"] += 1
                complete = False
                continue
            name = entry.name.encode("utf-8")
            if stat.S_ISDIR(info.st_mode):
                subtrees = visit(path)
                if subtrees is None:
                    complete = False
                    continue
                for profile in profiles:
                    entries[profile].append((name + b"/", b"40000 " + name + b"\0" + subtrees[profile]))
            elif stat.S_ISREG(info.st_mode) and info.st_size <= 32 * 1024 * 1024:
                raw = path.read_bytes()
                counts["files"] += 1
                counts["bytes"] += len(raw)
                text = b"\0" not in raw
                try:
                    if text:
                        raw.decode("utf-8")
                except UnicodeError:
                    text = False
                lf = raw.replace(b"\r\n", b"\n") if text else raw
                payloads = {"raw": raw, "lf": lf,
                            "crlf": lf.replace(b"\n", b"\r\n") if text else raw}
                blobs = {key: admit("blob", payload, rel, key) for key, payload in payloads.items()}
                for profile in profiles:
                    newline, modes = profile
                    mode = mode_map.get(rel, b"100644") if modes == "index" else b"100644"
                    if mode not in (b"100644", b"100755"):
                        return None
                    entries[profile].append((name, mode + b" " + name + b"\0" + blobs[newline]))
            else:
                counts["skipped"] += 1
                complete = False
        except OSError:
            counts["skipped"] += 1
            complete = False
    counts["directories"] += 1
    if not complete:
        return None
    result = {}
    for profile in profiles:
        raw_tree = b"".join(raw for _, raw in sorted(entries[profile]))
        result[profile] = admit("tree", raw_tree, directory.relative_to(ROOT).as_posix(), list(profile))
    return result


cache_path = ROOT / ".saipen/cache/git-recovery-candidates.json.gz"
if cache_path.is_file():
    cached = json.loads(gzip.decompress(cache_path.read_bytes()))
    for expected, item in cached.items():
        kind, payload, path, profile = item
        candidates[expected] = (kind, base64.b64decode(payload) if payload else None, path, profile)
else:
    visit(ROOT)
    cached = {expected: [kind, base64.b64encode(payload).decode() if payload is not None else None, path, profile]
              for expected, (kind, payload, path, profile) in candidates.items()}
    cache_path.parent.mkdir(exist_ok=True)
    cache_path.write_bytes(gzip.compress(json.dumps(cached).encode()))
reflogs = {}
for line in (ROOT / ".git/logs/HEAD").read_text().splitlines():
    if "\tcommit: " in line:
        header, message = line.split("\tcommit: ", 1)
        parent, target, person = header.split(" ", 2)
        reflogs.setdefault(target, []).append((parent, person, message))
candidate_tree_ids = [expected for expected, item in candidates.items() if item[0] == "tree"]
declined = []
while True:
    current = git("rev-list", "--objects", "--missing=print", "HEAD")
    missing = {line[1:].decode() for line in current.splitlines() if line.startswith(b"?")}
    matches = missing.intersection(candidates)
    if not matches:
        for target in missing.intersection(reflogs):
            for parent, person, message in reflogs[target]:
                for tree in candidate_tree_ids:
                    payload = (f"tree {tree}\nparent {parent}\nauthor {person}\n"
                               f"committer {person}\n\n{message}\n").encode()
                    if oid("commit", payload) == target:
                        candidates[target] = ("commit", payload, ".git/logs/HEAD", "exact-reflog-and-directory-tree")
        matches = missing.intersection(candidates)
    if not matches:
        break
    for expected in sorted(matches):
        kind, payload, path, profile = candidates[expected]
        if kind == "blob":
            payload = (ROOT / path).read_bytes()
            if profile in ("lf", "crlf"):
                payload = payload.replace(b"\r\n", b"\n")
                if profile == "crlf":
                    payload = payload.replace(b"\n", b"\r\n")
        if oid(kind, payload) != expected:
            declined.append(expected)
            del candidates[expected]
            continue
        admit(kind, payload, path, profile)
after = identity()
connectivity = git("rev-list", "--objects", "--missing=print", "HEAD")
(EVIDENCE / "head-connectivity-after-directories.txt").write_bytes(connectivity)
remaining = sorted(line[1:].decode() for line in connectivity.splitlines() if line.startswith(b"?"))
report = {"schema": 1, "initial_missing": initial_missing, "restored": restored,
          "remaining": remaining, "counts": counts, "elapsed_s": time.monotonic() - START,
          "declined_changed_preimages": declined,
          "before": before, "after": after, "identity_preserved": before == after,
          "positive_control": "PASS", "negative_control": "PASS",
          "scope": "Existing regular workspace inventories; exact requested object SHA1 only; no refs/index/source edits"}
receipt = EVIDENCE / ("directory-recovery-" + str(time.time_ns()) + ".json")
receipt.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
if before != after:
    raise RuntimeError("Repository identity changed")
print(json.dumps({"receipt": str(receipt), "restored": len(restored), "remaining": len(remaining),
                  "identity_preserved": True, "counts": counts, "elapsed_s": report["elapsed_s"]}))
