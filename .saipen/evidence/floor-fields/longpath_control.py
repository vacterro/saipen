"""Verify Git's path transport on identical owned bytes; change no check or subject."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="saipen-git-longpath-") as temporary:
    root = Path(temporary)
    relative = Path(*(["owned-path-" + "a" * 70] * 4)) / "control.json"
    target = root / relative
    target.parent.mkdir(parents=True)
    target.write_bytes(b'{"known_good": true}\n')
    initialized = subprocess.run(["git", "init", "--quiet"], cwd=root, capture_output=True)
    assert initialized.returncode == 0, initialized.stderr
    records = []
    for enabled in (False, True):
        command = ["git", "-c", f"core.longpaths={'true' if enabled else 'false'}",
                   "add", "--", relative.as_posix()]
        run = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8")
        records.append({"command": command, "exit_code": run.returncode,
                        "stdout": run.stdout, "stderr": run.stderr,
                        "subject_sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    observed = subprocess.run(["git", "-c", "core.longpaths=true", "ls-files", "--error-unmatch",
                               "--", relative.as_posix()], cwd=root, capture_output=True)
    assert records[0]["exit_code"] != 0, records
    assert records[1]["exit_code"] == 0, records
    assert observed.returncode == 0, observed.stderr
    assert records[0]["subject_sha256"] == records[1]["subject_sha256"]
    record = {"platform": os.name, "path_chars": len(str(target)), "runs": records,
              "assertions": "same known-good bytes fail without path support and are indexed with it"}
    (EVIDENCE / "longpath-control.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"path_chars": record["path_chars"], "exits": [r["exit_code"] for r in records]}))
