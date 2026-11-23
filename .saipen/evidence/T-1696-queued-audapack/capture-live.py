"""Read-only target capture; output belongs solely to SAIPEN forensic evidence."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

TARGET = Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK")
OUT = Path(__file__).resolve().parent / "live-snapshot"
OUT.mkdir(exist_ok=True)
PATHS = [".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md", ".saipen/MANIFEST.json",
         ".saipen/evidence/T-299-widget-trust-boundary-p1a-p1b.md", ".saipen/IDENTITY.md", "AGENTS.md"]
records = {}
for relative in PATHS:
    source = TARGET / relative
    info = source.lstat()
    assert stat.S_ISREG(info.st_mode) and not source.is_symlink(), relative
    assert not getattr(info, "st_file_attributes", 0) & 0x400, relative
    body = source.read_bytes()
    destination = OUT / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(body)
    records[relative] = {"sha256": hashlib.sha256(body).hexdigest(), "size": len(body),
                         "observed_mtime_ns": info.st_mtime_ns}
assert all(hashlib.sha256((TARGET / p).read_bytes()).hexdigest() == d["sha256"]
           for p, d in records.items()), "live checkpoint changed during capture"
commands = ["rev-parse --show-toplevel", "rev-parse HEAD", "status --porcelain=v1 -uall",
            "diff --binary", "diff --cached --binary", "log -6 --format=%H%x20%aI%x20%s"]
git = []
for index, arguments in enumerate(commands):
    result = subprocess.run(["git", *arguments.split()], cwd=TARGET,
                            env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"),
                            capture_output=True, timeout=60)
    destination = OUT / f"git-{index}.txt"
    destination.write_bytes(result.stdout + result.stderr)
    git.append({"command": "git " + arguments, "exit_code": result.returncode,
                "output": destination.name,
                "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()})
record = {"observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "registry": "codebase-memory list_projects: audapack, single normalized root",
          "target": str(TARGET.resolve()), "files": records, "git": git,
          "target_mutations": [], "copies_byte_identical": True}
(OUT / "capture.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"target": record["target"], "copies": len(records),
                  "head": (OUT / "git-1.txt").read_text().strip(),
                  "dirty_entries": len((OUT / "git-2.txt").read_text().splitlines()),
                  "files": records}, indent=2))
