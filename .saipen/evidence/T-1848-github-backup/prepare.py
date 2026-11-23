"""Prepare an explicit WIP source snapshot without touching the main index/HEAD."""

import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.core_unit import tree_fingerprint  # noqa: E402

env = os.environ.copy()
for selector in ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
    env.pop(selector, None)
env["GIT_OPTIONAL_LOCKS"] = "0"
env["GIT_TERMINAL_PROMPT"] = "0"


def git(*args, auxiliary=None):
    prefix = ["git"]
    if auxiliary is not None:
        prefix += ["--git-dir", str(auxiliary)]
    result = subprocess.run(prefix + list(args), cwd=ROOT, env=env,
                            capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-3000:])
    return result.stdout


def nul_paths(raw):
    return [os.fsdecode(value) for value in raw.split(b"\0") if value]


stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
branch = "backup/cc-all-" + stamp
auxiliary = Path("V:/_SAIPEN_VERIFY_/github-backups") / ("saipen-" + stamp + ".git")
if auxiliary.exists():
    raise RuntimeError("the new backup metadata path already exists")
auxiliary.parent.mkdir(parents=True, exist_ok=True)
head = git("rev-parse", "HEAD").decode().strip()
original_branch = git("symbolic-ref", "--short", "HEAD").decode().strip()
index = Path(git("rev-parse", "--path-format=absolute", "--git-path", "index").decode().strip())
objects = Path(git("rev-parse", "--path-format=absolute", "--git-path", "objects").decode().strip())
index_hash = hashlib.sha256(index.read_bytes()).hexdigest()
shutil.copy2(index, EVIDENCE / "original-index.bin")
fingerprint = tree_fingerprint(ROOT)
if fingerprint != "b6dc79950e87084614b6a070eeeca1f167410f736c65f40256a94762ca9a0c3c":
    raise RuntimeError("the source moved after its completed verification")
remote = git("remote", "get-url", "github-backup").decode().strip()
if remote != "https://github.com/vacterro/saipen.git":
    raise RuntimeError("the configured GitHub backup destination changed")

changed = nul_paths(git("diff", "--name-only", "--no-renames", "-z", "HEAD", "--"))
untracked = nul_paths(git("ls-files", "--others", "--exclude-standard", "-z", "--"))
paths = sorted(set(changed + untracked))
paths = [path for path in paths if PurePosixPath(path).parts[0] not in {".git", ".saipen", "audit"}]
checks = {
    "private_key": re.compile(rb"(?m)^-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "github_token": re.compile(rb"(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,})"),
    "gitlab_token": re.compile(rb"glpat-[A-Za-z0-9_-]{20,}"),
    "cloud_key": re.compile(rb"AKIA[0-9A-Z]{16}"),
}
files = []
findings = []
reviewed_fixtures = []
for relative in paths:
    rel = PurePosixPath(relative)
    if rel.is_absolute() or ".." in rel.parts or "\\" in relative:
        raise RuntimeError("unconfined snapshot path")
    path = ROOT / relative
    if not path.exists() and not path.is_symlink():
        files.append({"path": relative, "kind": "deleted"})
        continue
    if path.is_symlink():
        raw = os.fsencode(os.readlink(path))
        kind = "symlink"
    else:
        if not path.is_file():
            raise RuntimeError("snapshot path is not a regular source file")
        raw = path.read_bytes()
        kind = "file"
    if path.name.lower() in {".env", ".env.local", "credentials.json", "id_rsa", "id_ed25519"}:
        findings.append({"path": relative, "kind": "credential_file"})
    for name, expression in checks.items():
        for match in expression.finditer(raw):
            if relative == "tools/run_scenarios.py" and name == "github_token":
                prior = git("show", "HEAD:" + relative)
                context = raw[max(0, match.start() - 180):match.start()]
                if (b"T-1100: goal_entry credential redaction" in context
                        and b"cred_objective" in context and match.group() in prior):
                    reviewed_fixtures.append({"path": relative, "kind": name,
                                              "reason": "existing T-1100 synthetic redaction fixture, unchanged in HEAD"})
                    continue
            findings.append({"path": relative, "kind": name})
    files.append({"path": relative, "kind": kind, "bytes": len(raw),
                  "sha256": hashlib.sha256(raw).hexdigest()})
if findings:
    (EVIDENCE / "secret-review.json").write_text(json.dumps(findings, indent=2), encoding="utf-8")
    raise RuntimeError("snapshot needs secret review; only file names and finding classes were saved")

manifest_rel = EVIDENCE.relative_to(ROOT).as_posix() + "/snapshot-manifest.json"
manifest = {
    "kind": "WIP source backup; not a release or pending-cohort publication",
    "source_receipt": "SRC-288", "base": head, "branch": branch,
    "destination": remote, "source_fingerprint": fingerprint,
    "verification": {"full_unit": "7207 tests / 0 red", "independent_review": "140 tests / PASS",
                     "core_conformance": "PASS", "ruff": "0.16.0 / PASS"},
    "scope": "changed and new nonignored project source; local protocol evidence/cache and audit input excluded",
    "files": files, "reviewed_fixture_matches": reviewed_fixtures,
}
(ROOT / manifest_rel).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
git("init", "--bare", str(auxiliary))
(auxiliary / "objects/info/alternates").write_bytes((objects.as_posix() + "\n").encode("utf-8"))
git("config", "core.bare", "false", auxiliary=auxiliary)
git("config", "core.worktree", str(ROOT), auxiliary=auxiliary)
hooks = git("rev-parse", "--path-format=absolute", "--git-path", "hooks").decode().strip()
git("config", "core.hooksPath", hooks, auxiliary=auxiliary)
for option in ("core.autocrlf", "core.eol", "core.safecrlf", "core.filemode", "user.name",
               "user.email", "commit.gpgsign", "user.signingkey", "gpg.format", "gpg.program"):
    value = subprocess.run(["git", "config", "--get", option], cwd=ROOT, env=env,
                           capture_output=True, timeout=30)
    if value.returncode == 0:
        git("config", option, value.stdout.decode().strip(), auxiliary=auxiliary)
git("config", "credential.https://github.com.helper", "!gh auth git-credential", auxiliary=auxiliary)
git("remote", "add", "github-backup", remote, auxiliary=auxiliary)
git("symbolic-ref", "HEAD", "refs/heads/" + branch, auxiliary=auxiliary)
git("update-ref", "refs/heads/" + branch, head, "0" * 40, auxiliary=auxiliary)
git("read-tree", head, auxiliary=auxiliary)
selection = EVIDENCE / "snapshot-paths.nul"
selection.write_bytes(b"\0".join(os.fsencode(value) for value in [*paths, manifest_rel]) + b"\0")
git("--literal-pathspecs", "add", "--pathspec-from-file=" + str(selection),
    "--pathspec-file-nul", auxiliary=auxiliary)
tree = git("write-tree", auxiliary=auxiliary).decode().strip()
selected = nul_paths(git("diff", "--cached", "--name-only", "--no-renames", "-z", auxiliary=auxiliary))
if set(selected) != set(paths + [manifest_rel]):
    raise RuntimeError("the staged backup scope differs from its explicit selection")
if hashlib.sha256(index.read_bytes()).hexdigest() != index_hash or git("rev-parse", "HEAD").decode().strip() != head:
    raise RuntimeError("the original index or HEAD moved during preparation")
if tree_fingerprint(ROOT) != fingerprint:
    raise RuntimeError("the source moved during preparation")
result = {"kind": "prepared snapshot, not committed or pushed", "auxiliary_git_dir": str(auxiliary),
          "base": head, "original_branch": original_branch, "original_index_sha256": index_hash,
          "branch": branch, "remote": remote, "tree": tree, "manifest": manifest_rel,
          "selected_paths": len(selected), "source_fingerprint": fingerprint,
          "secret_findings": findings, "reviewed_fixture_matches": reviewed_fixtures}
(EVIDENCE / "prepared.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
