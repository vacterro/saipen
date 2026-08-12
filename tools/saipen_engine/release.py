"""One canonical release executor exposed by both `saipen ship` and
`saipen push` (T-635).

One immutable `ReleasePlan` and one execution function own the whole release
flow: worktree/index attribution, foreign-path detection, final metadata
preparation, version parity, exact staging, the post-metadata `--gate ship`,
the cached-diff check, commit -> current-branch push -> tag push ordering, and
release evidence. Both invocations dispatch here; after normalizing the
invocation name, their dry-runs are structurally identical (zero writes).
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReleasePlan:
    """The immutable release decision: what will be staged, committed, pushed
    and tagged, and in what order. Building the plan writes nothing; executing
    it is the only place bytes change."""
    invocation: str
    version: str
    branch: str
    commit_message: str
    tag: str
    release_paths: tuple[str, ...]
    foreign_staged: tuple[str, ...] = ()
    dry_run: bool = False

    def canonical(self) -> tuple:
        """The plan's identity, INVOCATION-NAME NORMALIZED -- `ship` and
        `push` plans for the same release are identical (T-635)."""
        return (self.version, self.branch, self.commit_message, self.tag,
                self.release_paths, self.foreign_staged)


def _git(root: Path, *args: str) -> tuple[int, str]:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True,
        errors="replace")
    return result.returncode, result.stdout.strip()


def _git_bytes(root: Path, *args: str) -> tuple[int, bytes]:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True)
    return result.returncode, result.stdout


def _installed_version(root: Path) -> str:
    version = root / "VERSION"
    if not version.is_file():
        raise ValueError("VERSION is missing from the repository root")
    return version.read_text(encoding="utf-8-sig").strip().split("\n")[0]


def _branch(root: Path) -> str:
    rc, out = _git(root, "branch", "--show-current")
    if rc != 0 or not out:
        raise ValueError("cannot determine the current branch")
    return out


def release_metadata_paths(root: Path) -> tuple[str, ...]:
    """The release surface: VERSION, README.md, CHANGELOG.md and every
    mechanically mirrored locale README under the translation kitchen -- the
    same set the binding `--gate ship` requires staged."""
    paths = ["VERSION", "README.md", "CHANGELOG.md"]
    kitchen = root / ".saipen" / "saitranslate" / "kitchen"
    if kitchen.is_dir():
        for directory in sorted(kitchen.iterdir()):
            if directory.is_dir():
                readme = directory / f"README_{directory.name.upper()}.md"
                if readme.is_file():
                    paths.append(readme.relative_to(root).as_posix())
    return tuple(paths)


def _version_badges(path: Path, expected: str) -> list[str]:
    badge = f"**v{expected}**"
    text = path.read_text(encoding="utf-8-sig")
    return [m for m in re.findall(r"\*\*v\d+\.\d+\.\d+\*\*", text)
            if m == badge]


def version_parity(root: Path, version: str) -> list[str]:
    """Every release metadata path must carry the version exactly once.
    READMEs use the `**vX.Y.Z**` badge; CHANGELOG.md uses a `## X.Y.Z`
    head entry -- each checked in its own canonical form."""
    problems: list[str] = []
    version_file = root / "VERSION"
    if version_file.read_text(encoding="utf-8-sig").strip().split("\n")[0] \
            != version:
        problems.append("VERSION does not read the release version")
    for rel in release_metadata_paths(root):
        if rel == "VERSION":
            continue
        path = root / rel
        if not path.is_file():
            problems.append(f"{rel} is missing")
            continue
        if rel == "CHANGELOG.md":
            text = path.read_text(encoding="utf-8-sig")
            heads = re.findall(r"(?m)^## (\d+\.\d+\.\d+)", text)
            if heads[:1] != [version]:
                problems.append(
                    f"{rel} head entry must be ## {version}")
            continue
        badges = _version_badges(path, version)
        if len(badges) != 1:
            problems.append(f"{rel} must carry **v{version}** exactly once")
    return problems


def _pre_ship_index(root: Path) -> str:
    """The exact pre-ship index tree (rollback source for release paths)."""
    rc, tree = _git(root, "write-tree")
    if rc != 0:
        raise ValueError("cannot snapshot the pre-ship index")
    return tree


def _staged_paths(root: Path) -> set[str]:
    rc, out = _git(root, "diff", "--cached", "--name-only")
    if rc != 0:
        raise ValueError("cannot read the staged set")
    return {line for line in out.splitlines() if line}


def _foreign_staged(root: Path, owned: set[str]) -> list[str]:
    """A pre-existing staged path this release does not own is foreign --
    never enter it, never reset it."""
    return sorted(_staged_paths(root) - owned)


def plan_release(root: Path, invocation: str, dry_run: bool = False) -> ReleasePlan:
    """Build the release plan with ZERO writes. Foreign staged paths are
    detected and excluded; version parity and the pre-ship index are checked
    here so the plan itself is a proven decision."""
    root = Path(root).resolve()
    version = _installed_version(root)
    branch = _branch(root)
    parity = version_parity(root, version)
    if parity:
        raise ValueError(
            "release version parity unmet:\n- " + "\n- ".join(parity[:8]))
    metadata = set(release_metadata_paths(root))
    foreign = _foreign_staged(root, metadata)
    if foreign:
        raise ValueError(
            "foreign pre-existing staged path(s) would enter this release: "
            + ", ".join(foreign)
            + " -- stage the release scope explicitly or leave it untouched")
    _pre_ship_index(root)
    message = (f"ship v{version}")
    return ReleasePlan(
        invocation=invocation, version=version, branch=branch,
        commit_message=message, tag=f"v{version}",
        release_paths=tuple(sorted(metadata)),
        foreign_staged=tuple(foreign), dry_run=dry_run)


def execute_release(root: Path, plan: ReleasePlan) -> dict:
    """The ONE execution function. Every write the release makes lives here;
    a dry-run returns the identical decision with zero bytes changed."""
    root = Path(root).resolve()
    owned = set(plan.release_paths)
    foreign = _staged_paths(root) - owned
    if foreign:
        return {"ok": False, "code": "FOREIGN_STAGING",
                "detail": "foreign staged paths would enter the release: "
                          + ", ".join(sorted(foreign))}
    if plan.dry_run:
        return {"ok": True, "code": "RELEASE_PLAN",
                "plan": plan.canonical(),
                "commit_message": plan.commit_message,
                "tag": plan.tag,
                "branch": plan.branch,
                "release_paths": list(plan.release_paths),
                "writes": "none"}
    rc, out = _git(root, "add", "--", *sorted(owned))
    if rc != 0:
        return {"ok": False, "code": "STAGING_FAILED", "detail": out}
    gate = subprocess.run(
        [sys.executable, str(root / "tools" / "validate.py"), "--gate",
         "ship"], cwd=str(root), capture_output=True, text=True,
        errors="replace")
    if gate.returncode != 0:
        return {"ok": False, "code": "SHIP_GATE_FAILED",
                "detail": (gate.stdout + gate.stderr)[-500:]}
    rc, out = _git(root, "diff", "--cached", "--check")
    if rc != 0:
        return {"ok": False, "code": "DIFF_CHECK_FAILED", "detail": out}
    rc, out = _git(root, "commit", "-m", plan.commit_message)
    if rc != 0:
        return {"ok": False, "code": "COMMIT_FAILED", "detail": out}
    commit = _git(root, "rev-parse", "HEAD")[1]
    rc, out = _git(root, "push", "origin", plan.branch)
    if rc != 0:
        return {"ok": False, "code": "PUSH_FAILED",
                "commit": commit, "detail": out}
    rc, out = _git(root, "tag", "-a", plan.tag, "-m", plan.commit_message)
    if rc != 0:
        return {"ok": False, "code": "TAG_FAILED",
                "commit": commit, "detail": out}
    rc, out = _git(root, "push", "origin",
                   f"refs/tags/{plan.tag}:refs/tags/{plan.tag}")
    if rc != 0:
        return {"ok": False, "code": "TAG_PUSH_FAILED",
                "commit": commit, "detail": out}
    return {"ok": True, "code": "RELEASED", "commit": commit, "tag": plan.tag,
            "branch": plan.branch}
