"""Build the exact T-1298 release candidate in an alternate Git index.

ROLE_20260909_0242 steps 4-6. Starts from HEAD, stages ONLY the reviewed
T-1298 scope into a throwaway index (the user's default index is never
written), then materializes that index into a throwaway tree for verification.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KITCHEN = ROOT / ".saipen" / "kitchen"
SCOPE_FILE = KITCHEN / "t1298-candidate-scope.json"
ALT = ROOT / ".git" / "t1298-candidate.index"
TREE = Path(r"V:\_TEMP_\opencode\t1298-candidate")


def git(*args: str, env: dict | None = None) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], env=env, stderr=subprocess.DEVNULL)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def alt_env() -> dict:
    return dict(os.environ, GIT_INDEX_FILE=str(ALT))


def build() -> None:
    scope = json.loads(SCOPE_FILE.read_text(encoding="utf-8"))["scope"]
    missing = [p for p in scope if not (ROOT / p).is_file()]
    if missing:
        raise SystemExit(f"missing scope files: {missing}")

    if ALT.exists():
        ALT.unlink()
    env = alt_env()
    git("read-tree", "HEAD", env=env)
    git("add", "--", *scope, env=env)

    staged = [l for l in git("diff", "--cached", "--name-only", env=env).decode().splitlines() if l]
    if sorted(staged) != sorted(scope):
        raise SystemExit(f"alt index staged set != scope\nstaged={sorted(staged)}\nscope={sorted(scope)}")

    # Materialize HEAD+scope as a real git worktree with LF endings (the live
    # worktree is LF; core.autocrlf=true would otherwise rewrite text to CRLF
    # and break the byte-level line-ending tests).
    subprocess.run(["git", "-C", str(ROOT), "worktree", "remove", "--force", str(TREE)], stderr=subprocess.DEVNULL)
    if TREE.exists():
        shutil.rmtree(TREE)
    git("-c", "core.autocrlf=false", "-c", "core.eol=lf", "worktree", "add", "--detach", str(TREE), "HEAD")
    for p in scope:
        dst = TREE / p
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / p, dst)

    manifest = {
        "schema_version": 1,
        "ticket": "T-1298",
        "alt_index": str(ALT),
        "tree": str(TREE),
        "scope": scope,
        "files": {p: sha256(ROOT / p) for p in scope},
        "head": git("rev-parse", "HEAD").decode().strip(),
    }
    (KITCHEN / "t1298-candidate-build.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "scope_count": len(scope), "tree": str(TREE), "head": manifest["head"]}, indent=2))


def staged_show() -> None:
    env = alt_env()
    print(git("diff", "--cached", "--name-status", env=env).decode())


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "build"
    if action == "build":
        build()
    elif action == "staged":
        staged_show()
    else:
        raise SystemExit(f"unknown action {action!r}")
