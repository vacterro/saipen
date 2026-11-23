"""Apply the reviewed parity delta, preserving the interrupted canonical Work."""
import hashlib
import json
import subprocess
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
package = json.loads((evidence / "package.json").read_text(encoding="utf-8"))
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
canonical = (".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md")
before = {name: sha(root / name) for name in canonical}
for item in package["files"]:
    assert sha(root / item["path"]) == item["before_sha256"], "source changed: " + item["path"]
patch = evidence / "repair.patch"
assert sha(patch) == package["patch_sha256"], "patch changed"
check = subprocess.run(["git", "apply", "--check", "--whitespace=error", str(patch)], cwd=root,
                       capture_output=True, text=True)
assert check.returncode == 0, check.stderr
argv = ["git", "apply", "--whitespace=error", str(patch)]
applied = subprocess.run(argv, cwd=root, capture_output=True, text=True)
assert applied.returncode == 0, applied.stderr
after = {name: sha(root / name) for name in canonical}
assert before == after, "canonical position changed during source repair"
for item in package["files"]:
    assert sha(root / item["path"]) == item["after_sha256"], "unexpected applied bytes"
record = {"argv": argv, "exit_code": applied.returncode, "stdout": applied.stdout,
          "stderr": applied.stderr, "canonical_before": before, "canonical_after": after,
          "files": package["files"], "persistent_authority_granted": False,
          "reason": "Operator renewed the maintenance request; engineering work is authorized. "
                    "The source repair neither resets the bounded lifecycle nor fabricates a grant."}
(evidence / "applied.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"exit_code": applied.returncode, "canonical_position_preserved": before == after,
                  "files": [item["path"] for item in package["files"]]}, indent=2))
