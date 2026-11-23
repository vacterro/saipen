"""Admit exact requested objects from retained index inventories and reflog.

The known original SHA is mandatory. Candidate guesses never enter the object
database unless their complete Git preimage reproduces that exact identity.
"""
import hashlib
import json
import os
import subprocess
import time
import zlib
from pathlib import Path

root = Path.cwd().resolve()
evidence = root / ".saipen/evidence/T-1829-cost-collapse"
env = {**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"}


def git(*args, data=None):
    return subprocess.run(["git", "-c", "core.commitGraph=false", *args], input=data,
                          capture_output=True, check=True, env=env).stdout


def identity():
    return {"head": git("rev-parse", "HEAD").decode().strip(),
            "refs": hashlib.sha256(git("for-each-ref", "--format=%(objectname) %(refname)")).hexdigest(),
            "index": hashlib.sha256((root / ".git/index").read_bytes()).hexdigest(),
            "entries": hashlib.sha256(git("ls-files", "--stage", "-z")).hexdigest()}


def oid(kind, body):
    return hashlib.sha1(kind.encode() + b" " + str(len(body)).encode() + b"\0" + body).hexdigest()


before = identity()
known = {}
for directory in [evidence / "git-object-recovery/candidate-objects",
                  *evidence.glob("auxiliary-recovery-*/objects-*")]:
    for folder in directory.iterdir():
        if not folder.is_dir() or len(folder.name) != 2:
            continue
        for item in folder.iterdir():
            header, body = zlib.decompress(item.read_bytes()).split(b"\0", 1)
            kind, size = header.split()
            kind = kind.decode()
            expected = folder.name + item.name
            if int(size) != len(body) or oid(kind, body) != expected:
                raise RuntimeError("Private candidate object integrity failure")
            known[expected] = (kind, body, str(item))

probe = json.loads((evidence / "commit-preimage-probe.json").read_text())
for match in probe["matches"]:
    body = match["payload"].encode()
    if oid("commit", body) != probe["target"]:
        raise RuntimeError("Reflog reconstruction is not the exact original commit")
    known[probe["target"]] = ("commit", body, "commit-preimage-probe.json")

restored = []
tree_listing = git("cat-file", "--batch-all-objects", "--batch-check=%(objectname) %(objecttype)")
trees = {line.split()[0].decode() for line in tree_listing.splitlines() if line.endswith(b" tree")}
trees.update(expected for expected, item in known.items() if item[0] == "tree")
reflogs = {}
for line in (root / ".git/logs/HEAD").read_text().splitlines():
    if "\tcommit: " not in line:
        continue
    header, message = line.split("\tcommit: ", 1)
    parent, target, person = header.split(" ", 2)
    reflogs.setdefault(target, []).append((parent, person, message, line))
reconstructed = []
while True:
    connectivity = git("rev-list", "--objects", "--missing=print", "HEAD")
    missing = {line[1:].decode() for line in connectivity.splitlines() if line.startswith(b"?")}
    matches = missing.intersection(known)
    if not matches:
        for target in missing.intersection(reflogs):
            for parent, person, message, original_line in reflogs[target]:
                for tree in trees:
                    body = (f"tree {tree}\nparent {parent}\nauthor {person}\n"
                            f"committer {person}\n\n{message}\n").encode()
                    if oid("commit", body) == target:
                        known[target] = ("commit", body, "exact-reflog-and-retained-tree")
                        reconstructed.append({"oid": target, "reflog": original_line,
                                              "tree": tree, "payload": body.decode()})
        matches = missing.intersection(known)
    if not matches:
        break
    for expected in sorted(matches):
        kind, body, source = known[expected]
        if git("hash-object", "-w", "-t", kind, "--stdin", data=body).decode().strip() != expected:
            raise RuntimeError("Git rejected the exact original identity")
        restored.append({"oid": expected, "type": kind, "source": source,
                         "sha256": hashlib.sha256(body).hexdigest()})

after = identity()
receipt = evidence / ("candidate-recovery-" + str(time.time_ns()) + ".json")
report = {"restored": restored, "reconstructed_commits": reconstructed,
          "remaining": sorted(missing), "candidate_count": len(known),
          "before": before, "after": after, "identity_preserved": before == after}
receipt.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
(evidence / "head-connectivity-after-candidates.txt").write_bytes(connectivity)
if before != after:
    raise RuntimeError("Original repository identity changed")
print(json.dumps({"receipt": str(receipt), "restored": len(restored),
                  "remaining": len(missing), "identity_preserved": True}))
