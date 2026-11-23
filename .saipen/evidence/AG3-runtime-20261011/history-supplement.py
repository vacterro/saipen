"""Read-only historical owner recovery and tracked-predecessor comparison."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
output = HERE / "history-supplement.json"
if output.exists():
    raise SystemExit("Historical supplement already exists")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def sha(data):
    return hashlib.sha256(data).hexdigest()


commits = {}
for commit in ("dbbfad946", "8f91d779", "b2343541", "c7e25f92", "c138bfd8", "HEAD"):
    commits[commit] = git("show", "-s", "--format=%H%n%aI%n%an%n%ae%n%B", commit).decode("utf-8")
comparisons = {}
for path in ("audit_manifest.py", "paths.py", "host_bootstrap.py", "reconcile.py", "init_project.py"):
    rel = "tools/saipen_engine/" + path
    tracked = git("show", "HEAD:" + rel)
    before = (HERE / "production-before" / rel).read_bytes()
    comparisons[rel] = {"tracked_HEAD_sha256": sha(tracked), "pre_fix_sha256": sha(before),
                        "pre_fix_identical_to_HEAD": tracked == before,
                        "tracked_HEAD_is_not_asserted_last_verified_predecessor": True}
sealed = {}
rows = {ticket: [] for ticket in ("T-1553", "T-1556", "T-1334", "T-1335", "T-1336")}
for path in sorted((ROOT / ".saipen/logs").glob("LOG-*.md")):
    data = path.read_bytes()
    sealed[path.name] = sha(data)
    for number, line in enumerate(data.decode("utf-8-sig").splitlines(), 1):
        for ticket in rows:
            if "[" + ticket + "]" in line:
                rows[ticket].append({"path": str(path.relative_to(ROOT)), "line": number,
                                     "event": line})
old_tests = git("show", "8f91d779:tools/test_audit_manifest.py")
(HERE / "historical-subjects/test_audit_manifest-8f91d779.py").write_bytes(old_tests)
result = {
    "commits": commits, "tracked_predecessor_comparison": comparisons,
    "canonical_owner_and_verification_rows": rows, "sealed_log_hashes": sealed,
    "original_manifest_test_sha256": sha(old_tests),
    "original_manifest_test_count": old_tests.decode("utf-8").count("    def test_"),
    "original_permission_error_literals_present": any(
        token in old_tests.lower() for token in (b"permissionerror", b"oserror", b"icacls", b"access is denied")
    ),
    "attribution_limit": "Owner labels and Git author/trailers do not authenticate a model. HEAD is a tracked predecessor, not proof of the last verified predecessor. No model-bound previous-Gemini change set is inferred.",
}
for name, digest in sealed.items():
    if sha((ROOT / ".saipen/logs" / name).read_bytes()) != digest:
        raise SystemExit("Sealed history changed during read-only diagnostics")
output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"comparison": comparisons, "original_test_count": result["original_manifest_test_count"],
                  "matching_owner_rows": {t: len(v) for t, v in rows.items()},
                  "sealed_history_unchanged": True}))
