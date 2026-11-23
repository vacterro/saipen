"""Read-only freshness scout; prior forensic claims remain historical evidence."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
TARGET = Path(r"V:\___VAC\__K\__CODE\_PY\_AUDAPACK")
OLD = ROOT / ".saipen/evidence/T-1696-queued-audapack"
records = {}
for label in ("live-snapshot", "durable-snapshot"):
    manifest = json.loads((OLD / label / "capture.json").read_text(encoding="utf-8"))
    for name, item in manifest["files"].items():
        path = TARGET / name
        info = path.lstat()
        assert stat.S_ISREG(info.st_mode) and not path.is_symlink() and not getattr(info, "st_file_attributes", 0) & 0x400, name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != item["sha256"]:
            records[name] = {"old": item["sha256"], "current": actual}
git = []
for arguments in (("rev-parse", "HEAD"), ("status", "--porcelain=v1", "-uall"),
                  ("diff", "--binary"), ("diff", "--cached", "--binary")):
    result = subprocess.run(["git", *arguments], cwd=TARGET,
                            env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"),
                            capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr
    git.append({"args": arguments, "sha256": hashlib.sha256(result.stdout).hexdigest(),
                "head": result.stdout.decode("utf-8").strip() if arguments[0] == "rev-parse" else None})
record = {"observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "target": str(TARGET), "changed_originals": records, "git": git,
          "scope": "read-only scout, no canonical target commands, no target writes, no new lifecycle verdict"}
(OUT / "next-audit-scout.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"changed_originals": len(records), "head": git[0]["head"], "target_writes": 0}))
