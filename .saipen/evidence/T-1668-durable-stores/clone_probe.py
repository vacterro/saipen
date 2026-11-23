"""T-1668: what a real clone of this repository holds, and what it validates to.

Usage: clone_probe.py <repo> <work>

Publication waits on T-1644, so HEAD is days old. The probe publishes the
tree as a release would -- every file git tracks or would add
(`git ls-files -co --exclude-standard`), working-tree bytes -- into a fresh
repository, commits it, and `git clone`s that. In the clone it counts the BOARD
detail_refs (and the full records their metadata names) that resolve, and runs
`tools/validate.py --gate core`. The live repository is only read.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

repo, work = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
assert not work.exists(), work
source, clone = work / "published", work / "clone"
git = shutil.which("git")


def run(*args, cwd=None):
    proc = subprocess.run(args, cwd=cwd, capture_output=True, check=False)
    if proc.returncode:
        raise SystemExit(f"{args[1:4]} -> {proc.returncode}: {proc.stderr.decode(errors='replace')[-600:]}")
    return proc


listing = run(git, "-C", str(repo), "ls-files", "-co", "--exclude-standard", "-z").stdout
paths = [p for p in listing.decode("utf-8").split("\0") if p]
for rel in paths:
    src = repo / rel
    if not src.is_file():
        continue
    dst = source / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
if os.environ.get("PROBE_GITIGNORE"):
    # Red control: publish under another .gitignore (e.g. the pre-fix one).
    shutil.copy2(os.environ["PROBE_GITIGNORE"], source / ".gitignore")
run(git, "init", "-q", str(source))
run(git, "-C", str(source), "config", "core.longpaths", "true")
run(git, "-C", str(source), "add", "-A")
for forced in [p for p in os.environ.get("PROBE_FORCE", "").split(";") if p]:
    for src in sorted(repo.glob(forced)):
        dst = source / src.relative_to(repo)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        run(git, "-C", str(source), "add", "-f", str(dst.relative_to(source)))
run(git, "-C", str(source), "-c", "user.name=probe", "-c", "user.email=probe@local",
    "commit", "-q", "-m", "publication probe")
run(git, "clone", "-q", str(source), str(clone))
print(f"published {len(paths)} paths; clone at {clone}")

board = (clone / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
refs = re.findall(r"detail_ref: ([^\s|\]]+)", board)
refs = sorted(set(refs))
missing = []
for ref in refs:
    meta = clone / ref
    if not meta.is_file():
        missing.append(ref)
        continue
    original = json.loads(meta.read_text(encoding="utf-8")).get("original_record_path")
    if original and not (clone / original).is_file():
        missing.append(original)
print(f"BOARD detail_refs: {len(refs)} cited, {len(refs) - len(missing)} resolve, "
      f"{len(missing)} do not")
for item in missing[:10]:
    print("  missing:", item)

env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
env["PYTHONUTF8"] = "1"
proc = subprocess.run(
    [sys.executable, "-B", str(clone / "tools" / "validate.py"), "--gate", "core"],
    cwd=str(clone), env=env, capture_output=True, timeout=1800, check=False,
)
out = proc.stdout.decode("utf-8", errors="replace")
fails = [line for line in out.splitlines() if line.startswith("FAIL")]
print(f"validate --gate core in the clone: exit {proc.returncode}, FAIL {len(fails)}")
for line in fails[:12]:
    print("  " + line[:300])
print(out.strip().splitlines()[-1] if out.strip() else "(no output)")
shutil.rmtree(work, ignore_errors=True)
raise SystemExit(0 if not missing and not fails else 1)
