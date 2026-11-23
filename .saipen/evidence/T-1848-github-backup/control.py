"""Deliberate bad artifact, unchanged verifier, then exact auxiliary-index restore."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

folder = Path(__file__).resolve().parent
root = folder.parents[2]
plan = json.loads((folder / "prepared.json").read_text(encoding="utf-8"))
aux = Path(plan["auxiliary_git_dir"]).resolve()
if aux.parent != Path("V:/_SAIPEN_VERIFY_/github-backups").resolve():
    raise RuntimeError("control target is outside the owned auxiliary namespace")
index = aux / "index"
before = index.read_bytes()
(folder / "auxiliary-index-before-control.bin").write_bytes(before)
env = os.environ.copy()
for key in ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
    env.pop(key, None)
env["GIT_OPTIONAL_LOCKS"] = "0"


def verify():
    return subprocess.run([sys.executable, "-B", str(folder / "verify.py")],
                          cwd=root, env=env, capture_output=True, timeout=90)


bad = None
try:
    empty = subprocess.run(["git", "--git-dir", str(aux), "hash-object", "-w", "--stdin"],
                           cwd=root, env=env, input=b"", capture_output=True, check=True).stdout.decode().strip()
    subprocess.run(["git", "--git-dir", str(aux), "update-index", "--cacheinfo",
                    "100644," + empty + "," + plan["manifest"]], cwd=root, env=env,
                   capture_output=True, check=True)
    bad = verify()
finally:
    index.write_bytes(before)
if bad is None or bad.returncode == 0:
    raise RuntimeError("the unchanged verifier failed to reject an empty manifest blob")
good = verify()
if good.returncode:
    raise RuntimeError(good.stderr.decode("utf-8", errors="replace"))
result = {"bad_exit": bad.returncode,
          "bad_diagnostic": bad.stderr.decode("utf-8", errors="replace").splitlines()[-1],
          "restored_exit": good.returncode,
          "auxiliary_index_restored_exactly": hashlib.sha256(index.read_bytes()).digest() == hashlib.sha256(before).digest(),
          "subject": "only the privately owned auxiliary Git index; main index untouched"}
(folder / "verifier-control.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
