"""Exercise a queued candidate in retained disposable subjects, not live source."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1]).resolve()
evidence = Path(__file__).resolve().parent
sys.path.insert(0, str(root / "tools"))
from saipen_engine.core_unit import tree_fingerprint  # noqa: E402
from saipen_engine.test_runner import _ignore_copy  # noqa: E402
from test_hermetic_env import hermetic_env  # noqa: E402

subjects = json.loads((evidence / "subjects.json").read_text())
for subject in subjects:
    if hashlib.sha256((root / subject["path"]).read_bytes()).hexdigest() != subject["before_sha256"]:
        raise RuntimeError("live subject moved; regenerate and review the candidate")

destination = Path(tempfile.mkdtemp(prefix="subjects-", dir=evidence))
if not destination.resolve().is_relative_to(evidence.resolve()):
    raise RuntimeError("scratch destination escapes the evidence directory")
before, after = destination / "pre-fix", destination / "candidate"


def ignored(directory, names):
    top = {".git", ".saipen"} if Path(directory).resolve() == root else set()
    return _ignore_copy(directory, names) | top


shutil.copytree(root, before, ignore=ignored)
shutil.copytree(before, after)
for subject in subjects:
    shutil.copyfile(evidence / "candidate" / subject["path"], after / subject["path"])

command = [sys.executable, "-B", str(evidence / "oracle.py"), "."]
verifier = hashlib.sha256((evidence / "oracle.py").read_bytes()
                          + json.dumps(command).encode()).hexdigest()[:16]
records = []
for label, tree in (("red-prep", before), ("green-prep", after)):
    subject = tree_fingerprint(tree)
    run = subprocess.run(command, cwd=tree, env=hermetic_env(), stdin=subprocess.DEVNULL,
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=900)
    (evidence / f"{label}.stderr.txt").write_text(run.stderr, encoding="utf-8")
    (evidence / f"{label}.stdout.txt").write_text(run.stdout, encoding="utf-8")
    record = {"command": command, "root": str(tree), "verifier": verifier,
              "subject": subject, "exit_code": run.returncode, "queued_scratch_only": True}
    (evidence / f"{label}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    records.append(record)
    print(json.dumps(record), flush=True)
    print(run.stderr[-5000:], flush=True)
sys.exit(0 if records[0]["exit_code"] != 0 and records[1]["exit_code"] == 0 else 1)
