"""Evaluate strict launch candidates solely in disposable subject copies."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
evidence = Path(__file__).resolve().parent
sys.path.insert(0, str(root / "tools"))
from saipen_engine import core_unit  # noqa: E402
from saipen_engine.test_runner import _ignore_copy  # noqa: E402
from test_hermetic_env import hermetic_env  # noqa: E402

subjects = evidence / "subjects-prep"
subjects.mkdir()
before, after = subjects / "pre-fix", subjects / "candidate"

def ignored(directory, names):
    excluded = {".git", ".saipen"} if Path(directory).resolve() == root else set()
    return _ignore_copy(directory, names) | excluded

shutil.copytree(root, before, ignore=ignored)
shutil.copytree(before, after)
for item in json.loads((evidence / "subjects.json").read_text(encoding="utf-8")):
    actual = hashlib.sha256((root / item["path"]).read_bytes()).hexdigest()
    if actual != item["before_sha256"]:
        raise ValueError("live source moved while preparing queued candidate")
    shutil.copy2(evidence / "candidate" / item["path"], after / item["path"])

command = [sys.executable, "-B", str(evidence / "oracle.py"), "."]
verifier = hashlib.sha256((evidence / "oracle.py").read_bytes()
                          + json.dumps(command).encode()).hexdigest()[:16]
records = []
for label, subject in (("red-prep", before), ("green-prep", after)):
    run = subprocess.run(command, cwd=subject, env=hermetic_env(PYTHONUTF8="1"),
                         capture_output=True, encoding="utf-8", timeout=120)
    for stream in ("stdout", "stderr"):
        (evidence / f"{label}.{stream}.txt").write_text(getattr(run, stream), encoding="utf-8")
    record = {"queued_scratch_only": True, "subject_root": str(subject),
              "subject": core_unit.tree_fingerprint(subject), "verifier": verifier,
              "command": command, "exit_code": run.returncode}
    (evidence / f"{label}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    records.append(record)
print(json.dumps(records, indent=2))
