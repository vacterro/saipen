"""Read-only acquisition for the operator-authorized isolated recovery.

No original file is opened for writing. Evidence is created exclusively here.
This is an acquisition tool, not an INIT or lifecycle implementation.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = HERE.parents[2]
ORIGINAL = Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK")
RECOVERY = Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK_RECOVERY_20261010")
BASELINE = HOME / ".saipen/evidence/mission-audit-fairness/AUDAPACK-20261010T1522Z.json"
CASE = HOME / ".saipen/evidence/AUDAPACK-T299-forensics/snapshot-20261010T090700Z"
sys.path.insert(0, str(HOME / "tools"))


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_new(path: Path, value) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def git(root: Path, *args: str) -> bytes:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    result = subprocess.run(
        ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(root), *args],
        env=env, stdin=subprocess.DEVNULL, capture_output=True, check=False,
    )
    if result.returncode:
        raise RuntimeError((args, result.returncode, result.stderr.decode(errors="replace")))
    return result.stdout


def inventory(root: Path) -> dict:
    files, directories, risks = {}, [], []
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs.sort()
        for name in sorted(dirs + names):
            path = Path(base) / name
            before = path.lstat()
            relative = path.relative_to(root).as_posix()
            if stat.S_ISLNK(before.st_mode) or getattr(before, "st_file_attributes", 0) & 0x400:
                risks.append({"path": relative, "kind": "reparse-or-symlink"})
                if name in dirs:
                    dirs.remove(name)
                continue
            if stat.S_ISDIR(before.st_mode):
                directories.append(relative)
                continue
            if not stat.S_ISREG(before.st_mode):
                risks.append({"path": relative, "kind": "nonregular"})
                continue
            if before.st_nlink != 1:
                risks.append({"path": relative, "kind": "hardlink", "nlink": before.st_nlink})
            digest = sha(path)
            after = path.lstat()
            keys = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
            if any(getattr(before, key) != getattr(after, key) for key in keys):
                risks.append({"path": relative, "kind": "changed-during-read"})
            files[relative] = {"sha256": digest, "bytes": before.st_size,
                               "device": before.st_dev, "inode": before.st_ino,
                               "nlink": before.st_nlink, "mtime_ns": before.st_mtime_ns}
    content = {name: {"sha256": row["sha256"], "bytes": row["bytes"]}
               for name, row in files.items()}
    return {"files": files, "directories": directories, "risks": risks,
            "file_count": len(files), "bytes": sum(row["bytes"] for row in files.values()),
            "content_sha256": hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()}


def no_alias_destination() -> dict:
    if os.path.lexists(RECOVERY):
        raise RuntimeError("RECOVERY_DESTINATION_EXISTS (including a dangling alias)")
    chain = []
    for path in (RECOVERY.parent, *RECOVERY.parent.parents):
        info = path.lstat()
        chain.append({"path": str(path), "attributes": getattr(info, "st_file_attributes", 0)})
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise RuntimeError(f"RECOVERY_ANCESTOR_ALIAS: {path}")
    if RECOVERY.resolve() == ORIGINAL.resolve():
        raise RuntimeError("RECOVERY_ALIASES_ORIGINAL")
    return {"absent": True, "resolved": str(RECOVERY.resolve()), "ancestor_chain": chain}


def main() -> None:
    from saipen_engine import journal, mailbox

    target = HERE / "phase0.json"
    if target.exists():
        raise RuntimeError("Existing evidence is immutable")
    destination = no_alias_destination()
    spec = importlib.util.spec_from_file_location(
        "approved_recheck", HOME / ".saipen/evidence/mission-audit-fairness/recheck.py"
    )
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    reader.git = lambda *args: git(ORIGINAL, *args)
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    observed = reader.inventory()
    findings = []
    if observed != baseline["after"]:
        findings.append("ORIGINAL_APPROVED_BASELINE_MISMATCH")
    case = reader.case_check()
    if not case["unchanged"]:
        findings.append("SEALED_ACQUISITION_MISMATCH")
    if not (ORIGINAL / ".git").is_dir():
        findings.append("ORIGINAL_GIT_STORAGE_NOT_INDEPENDENT_DIRECTORY")
    git_alias_paths = ("commondir", "objects/info/alternates", "objects/info/http-alternates", "worktrees")
    git_aliases = [name for name in git_alias_paths if os.path.lexists(ORIGINAL / ".git" / name)]
    if git_aliases:
        findings.append("ORIGINAL_LINKED_GIT_STORAGE")
    local_worktree = git(ORIGINAL, "config", "--local", "--get-regexp", "^core[.]worktree$") if b"core.worktree" in git(ORIGINAL, "config", "--local", "--list") else b""
    if local_worktree:
        findings.append("ORIGINAL_EXTERNAL_GIT_WORKTREE_CONFIGURATION")
    lock_files = list((ORIGINAL / ".git").rglob("*.lock"))
    if lock_files:
        findings.append("ORIGINAL_GIT_LOCK_PRESENT")
    pending, conflicts = journal.scan_pending(ORIGINAL)
    home_pending, home_conflicts = journal.scan_pending(HOME)
    if pending or conflicts or home_pending or home_conflicts:
        findings.append("UNRESOLVED_CANONICAL_OPERATION")
    mutex = ORIGINAL / ".saipen/locks/core.lock"
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    kernel.CreateFileW.restype = wintypes.HANDLE
    # Open existing mutex for reading, deny writers/deleters. Never create it.
    handle = kernel.CreateFileW(str(mutex), 0x80000000, 1, None, 3, 0x80, None)
    invalid = ctypes.c_void_p(-1).value
    mutex_probe = {"path": str(mutex), "exists": mutex.exists(), "read_deny_write_open": handle != invalid}
    if handle == invalid:
        mutex_probe["winerror"] = ctypes.get_last_error()
        findings.append("ORIGINAL_WRITER_EXCLUSION_NOT_PROVEN")
    try:
        captured = inventory(ORIGINAL)
        if captured["risks"]:
            findings.append("ORIGINAL_ALIAS_OR_UNSTABLE_FILE")
        fsck = git(ORIGINAL, "fsck", "--full", "--no-reflogs").decode(errors="replace")
        after = reader.inventory()
        if after != observed:
            findings.append("ORIGINAL_CHANGED_DURING_ACQUISITION")
    finally:
        if handle != invalid:
            kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
            kernel.CloseHandle(handle)
    installation = {}
    for relative in ("bin/saipen.cmd", "tools/saipen.py", "tools/saipen_engine/init_project.py",
                     "saipen/STYLE.md", "extensions/templates/STATE.md", "extensions/templates/BOARD.md",
                     "extensions/templates/LOG.md"):
        installation[relative] = sha(HOME / relative)
    marker = mailbox.default_workspace() / mailbox.MARKER_NAME
    record = {"captured_utc": datetime.now(timezone.utc).isoformat(),
              "original": str(ORIGINAL), "recovery": str(RECOVERY),
              "python": sys.executable, "python_version": sys.version,
              "installation_home": str(HOME), "installation_hashes": installation,
              "destination": destination, "approved_baseline_equal": observed == baseline["after"],
              "baseline_sha256": sha(BASELINE), "sealed_acquisition": case,
              "git_aliases": git_aliases, "git_lock_files": [str(p) for p in lock_files],
              "core_mutex_probe": mutex_probe, "git_fsck": fsck,
              "git_status_v2": git(ORIGINAL, "status", "--porcelain=v2", "--branch", "--untracked-files=all").decode(),
              "git_ignored_paths": git(ORIGINAL, "ls-files", "--others", "--ignored", "--exclude-standard", "-z").decode().split("\0"),
              "git_untracked_paths": git(ORIGINAL, "ls-files", "--others", "--exclude-standard", "-z").decode().split("\0"),
              "git_raw_index_sha256": sha(ORIGINAL / ".git/index"), "git_projection": observed,
              "complete_original": captured, "original_pending": pending, "original_conflicts": conflicts,
              "home_pending": home_pending, "home_conflicts": home_conflicts,
              "mailbox_binding": str(mailbox.bound_workspace()),
              "mailbox_marker_sha256": sha(marker) if marker.is_file() else None,
              "findings": findings, "preflight_pass": not findings}
    write_new(target, record)
    print(json.dumps({"record": str(target), "preflight_pass": not findings,
                      "findings": findings, "original_files": captured["file_count"],
                      "original_bytes": captured["bytes"], "original_content_sha256": captured["content_sha256"],
                      "approved_baseline_equal": observed == baseline["after"],
                      "sealed_acquisition_equal": case["unchanged"], "mutex_probe": mutex_probe}, indent=2))
    if findings:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
