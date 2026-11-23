"""Read-only AUDAPACK acquisition. All writes target the separate case directory."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

CASE = Path(__file__).resolve().parent
ROOT = Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK").resolve()
assert CASE.resolve().is_relative_to(Path("V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_SAIPEN").resolve())
assert not CASE.resolve().is_relative_to(ROOT)
STAMP = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
DEST = CASE / ("snapshot-" + STAMP)
DEST.mkdir(exist_ok=False)

def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()

def inventory():
    chosen = []
    memory = ROOT / ".saipen"
    chosen.extend(path for path in memory.iterdir() if path.is_file())
    for name in ("logs", "recovery", "quarantine", "evidence", "intake", "archive"):
        base = memory / name
        if base.is_dir():
            for directory, dirs, files in os.walk(base, followlinks=False):
                dirs[:] = [name for name in dirs if not (Path(directory) / name).is_symlink()]
                chosen.extend(Path(directory) / name for name in files)
    for name in ("AGENTS.md", "VERSION", "pyproject.toml", "package.json", ".gitignore"):
        path = ROOT / name
        if path.is_file():
            chosen.append(path)
    return sorted(set(chosen))

records, skipped = [], []
paths = inventory()
for path in paths:
    rel = path.relative_to(ROOT)
    info = path.lstat()
    if (path.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400
            or not path.resolve().is_relative_to(ROOT)):
        skipped.append({"path": rel.as_posix(), "reason": "link/reparse/outside root"})
        continue
    target = DEST / rel
    assert target.resolve().is_relative_to(DEST.resolve())
    target.parent.mkdir(parents=True, exist_ok=True)
    before = digest(path)
    shutil.copyfile(path, target)
    copied, after = digest(target), digest(path)
    if not before == copied == after:
        raise RuntimeError("source changed during acquisition: " + str(rel))
    records.append({"path": rel.as_posix(), "sha256": before, "bytes": info.st_size,
                    "mtime_ns": info.st_mtime_ns, "copy": str(target)})
    target.chmod(stat.S_IREAD)

stable = all(digest(ROOT / item["path"]) == item["sha256"] for item in records)
names_stable = [path.relative_to(ROOT).as_posix() for path in paths] == [
    path.relative_to(ROOT).as_posix() for path in inventory()]
env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
commands = {
    "root": ["git", "rev-parse", "--show-toplevel"],
    "head": ["git", "rev-parse", "HEAD"],
    "branch": ["git", "branch", "--show-current"],
    "status": ["git", "status", "--porcelain=v1", "--untracked-files=all"],
    "recent_commits": ["git", "log", "-15", "--format=%H %aI %an %s"],
    "canonical_tracking": ["git", "ls-files", "--stage", ".saipen/STATE.md", ".saipen/BOARD.md",
                            ".saipen/LOG.md", ".saipen/MANIFEST.json"],
}
git = {}
for name, argv in commands.items():
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="backslashreplace", env=env)
    git[name] = {"argv": argv, "exit_code": result.returncode,
                 "stdout": result.stdout, "stderr": result.stderr}
    (DEST / ("git-" + name + ".txt")).write_text(result.stdout, encoding="utf-8")
manifest = {"schema": 1, "purpose": "Pre-repair forensic acquisition, no authority granted",
            "root": str(ROOT), "snapshot": str(DEST), "captured_utc": STAMP,
            "files": records, "skipped": skipped, "stable_content": stable,
            "stable_file_set": names_stable, "git": git, "originals_written": False}
encoded = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
(DEST / "ACQUISITION.json").write_bytes(encoded)
(DEST / "ACQUISITION.sha256").write_text(hashlib.sha256(encoded).hexdigest() + "\n")
(DEST / "ACQUISITION.json").chmod(stat.S_IREAD)
(DEST / "ACQUISITION.sha256").chmod(stat.S_IREAD)
(CASE / "location.json").write_text(json.dumps({"root": str(ROOT), "snapshot": str(DEST)}, indent=2) + "\n")
print(json.dumps({"snapshot": str(DEST), "files": len(records), "bytes": sum(x["bytes"] for x in records),
                  "stable_content": stable, "stable_file_set": names_stable,
                  "skipped": skipped, "head": git["head"]["stdout"].strip(),
                  "branch": git["branch"]["stdout"].strip(),
                  "dirty_entries": len(git["status"]["stdout"].splitlines()),
                  "canonical": [item for item in records if item["path"] in
                                (".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md",
                                 ".saipen/MANIFEST.json")]}, indent=2))
if not stable or not names_stable:
    raise SystemExit("Concurrent acquisition drift: NO_GO")
