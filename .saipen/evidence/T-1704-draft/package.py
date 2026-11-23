"""Package a reviewable draft; check applicability without applying it."""

import difflib
import hashlib
import json
import subprocess
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
location = json.loads((evidence / "location.json").read_text(encoding="utf-8"))
subject = Path(location["subject"])
files = (
    "tools/saipen_engine/state.py",
    "tools/saipen_engine/audit_route.py",
    "tools/saipen_engine/router.py",
    "tools/saipen_engine/operations.py",
    "tools/validate.py",
    "tools/test_t1704_goal_checkpoint_priority.py",
    "tests/fixtures/t1703-valve-audit.json",
)
digest = lambda content: hashlib.sha256(content).hexdigest()
chunks, records = [], []
for name in files:
    live = root / name
    before = live.read_bytes() if live.exists() else b""
    after = (subject / name).read_bytes()
    assert before != after, f"no change: {name}"
    chunks.extend(difflib.unified_diff(
        before.decode("utf-8").splitlines(keepends=True),
        after.decode("utf-8").splitlines(keepends=True),
        fromfile="a/" + name if live.exists() else "/dev/null",
        tofile="b/" + name,
    ))
    records.append({"path": name, "before_sha256": digest(before) if live.exists() else None,
                    "after_sha256": digest(after), "live_written": False})
patch = evidence / "repair.patch"
patch.write_text("".join(chunks).replace("\r\n", "\n"), encoding="utf-8", newline="\n")
argv = ["git", "apply", "--check", "--whitespace=error", str(patch)]
checked = subprocess.run(argv, cwd=root, capture_output=True, text=True)
record = {"files": records, "patch_sha256": digest(patch.read_bytes()), "argv": argv,
          "cwd": str(root), "exit_code": checked.returncode,
          "stdout": checked.stdout, "stderr": checked.stderr,
          "live_code_applied": False, "authority_granted": False}
(evidence / "package.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record, indent=2))
raise SystemExit(checked.returncode)
