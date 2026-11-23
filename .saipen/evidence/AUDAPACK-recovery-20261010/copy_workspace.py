"""Independent, digest-verified copy; never opens the original for writing."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import shutil
import stat
import traceback
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

from preflight import HERE, HOME, ORIGINAL, RECOVERY, git, inventory, no_alias_destination, sha, write_new


def relative_destination(name: str) -> Path:
    p = Path(name)
    if name == ".saipen" or name.startswith(".saipen/"):
        return Path(".recovery-legacy/original") / p
    if name == ".venv" or name.startswith(".venv/"):
        return Path(".recovery-legacy/original") / p
    if name == ".git/worktrees" or name.startswith(".git/worktrees/"):
        return Path(".recovery-legacy/original") / p
    return p


def copy_bound(source: Path, destination: Path, expected: dict) -> dict:
    info = source.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or getattr(info, "st_file_attributes", 0) & 0x400:
        raise RuntimeError(f"Unsafe source node: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    for parent in (destination.parent, *destination.parent.parents):
        if parent == RECOVERY.parent:
            break
        details = parent.lstat()
        if not stat.S_ISDIR(details.st_mode) or getattr(details, "st_file_attributes", 0) & 0x400:
            raise RuntimeError(f"Unsafe destination ancestor: {parent}")
    with source.open("rb") as reader, destination.open("xb") as writer:
        shutil.copyfileobj(reader, writer, 1024 * 1024)
    observed = sha(destination)
    target_info = destination.lstat()
    if observed != expected["sha256"] or target_info.st_size != expected["bytes"]:
        raise RuntimeError(f"Digest mismatch at {destination}")
    if target_info.st_nlink != 1 or (target_info.st_dev, target_info.st_ino) == (info.st_dev, info.st_ino):
        raise RuntimeError(f"Shared mutable node at {destination}")
    if sha(source) != expected["sha256"]:
        raise RuntimeError(f"Original changed while copied: {source}")
    return {"source": str(source), "destination": destination.relative_to(RECOVERY).as_posix(),
            "sha256": observed, "bytes": target_info.st_size,
            "source_node": [info.st_dev, info.st_ino],
            "destination_node": [target_info.st_dev, target_info.st_ino]}


def main():
    p0 = json.loads((HERE / "phase0.json").read_text(encoding="utf-8"))
    admission = json.loads((HERE / "phase0-admission.json").read_text(encoding="utf-8"))
    controls = json.loads((HERE / "phase1-v5.json").read_text(encoding="utf-8"))
    assert admission["phase0_pass"] and controls["all_pass"]
    assert set(controls["outcomes"]) == set("ABCDEFG")
    for relative, digest in p0["installation_hashes"].items():
        assert sha(HOME / relative) == digest, f"Running installation changed: {relative}"
    no_alias_destination()
    before = inventory(ORIGINAL)
    assert before["content_sha256"] == p0["complete_original"]["content_sha256"], "Original changed since preflight"
    assert not before["risks"]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    kernel.CreateFileW.restype = wintypes.HANDLE
    handle = kernel.CreateFileW(str(ORIGINAL / ".saipen/locks/core.lock"), 0x80000000, 1, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise RuntimeError(f"Original writer exclusion failed: WinError {ctypes.get_last_error()}")
    record = {"started_utc": datetime.now(timezone.utc).isoformat(), "original": str(ORIGINAL),
              "recovery": str(RECOVERY), "original_lineage": "lineage-79944d6c0334416ebe1001e97de6c1cc",
              "original_files": [], "supporting_files": [], "copy_pass": False, "failure": None}
    try:
        no_alias_destination()
        RECOVERY.mkdir()
        for directory in before["directories"]:
            (RECOVERY / relative_destination(directory)).mkdir(parents=True, exist_ok=True)
        for name, expected in before["files"].items():
            record["original_files"].append(copy_bound(ORIGINAL / name, RECOVERY / relative_destination(name), expected))
        # Preserve the complete sealed external case and all its supporting evidence.
        for source, destination in (
            (HOME / ".saipen/evidence/AUDAPACK-T299-forensics", Path(".recovery-legacy/forensic-case")),
            (HOME / ".saipen/evidence/mission-audit-fairness", Path(".recovery-legacy/recovery-plan")),
            (HERE, Path(".recovery-legacy/recovery-execution")),
        ):
            acquisition = inventory(source)
            assert not acquisition["risks"], (source, acquisition["risks"])
            for directory in acquisition["directories"]:
                (RECOVERY / destination / directory).mkdir(parents=True, exist_ok=True)
            for name, expected in acquisition["files"].items():
                record["supporting_files"].append(copy_bound(source / name, RECOVERY / destination / name, expected))
        assert not os.path.lexists(RECOVERY / ".saipen"), "Legacy namespace occupies active authority"
        for name in ("worktrees", "commondir", "objects/info/alternates", "objects/info/http-alternates"):
            assert not os.path.lexists(RECOVERY / ".git" / name), f"Active Git alias: {name}"
        assert Path(git(RECOVERY, "rev-parse", "--absolute-git-dir").decode().strip()).resolve() == RECOVERY / ".git"
        refs = git(RECOVERY, "for-each-ref", "--format=%(refname) %(objectname)").decode()
        assert refs == p0["git_projection"]["refs"], "Git refs changed"
        assert git(RECOVERY, "rev-parse", "HEAD").decode().strip() == p0["git_projection"]["head"]
        reachable = hashlib.sha256(git(RECOVERY, "rev-list", "--all", "--objects")).hexdigest()
        assert reachable == p0["git_projection"]["reachable_history_sha256"]
        index = hashlib.sha256(git(RECOVERY, "ls-files", "--stage", "-z")).hexdigest()
        assert index == p0["git_projection"]["index_projection_sha256"]
        assert sha(RECOVERY / ".git/index") == p0["git_raw_index_sha256"]
        record["git_fsck"] = git(RECOVERY, "fsck", "--full", "--no-reflogs").decode(errors="replace")
        record["git_refs"] = refs
        record["reachable_history_sha256"] = reachable
        record["index_projection_sha256"] = index
        record["worktrees"] = git(RECOVERY, "worktree", "list", "--porcelain").decode()
        assert record["worktrees"].count("worktree ") == 1
        after = inventory(ORIGINAL)
        assert after["content_sha256"] == before["content_sha256"], "Original mutated during copy"
        destination = inventory(RECOVERY)
        assert not destination["risks"], destination["risks"]
        # Verify captured digests against the actual destination a SECOND time.
        for row in record["original_files"] + record["supporting_files"]:
            actual = destination["files"][row["destination"]]
            assert actual["sha256"] == row["sha256"] and actual["bytes"] == row["bytes"]
        record["original_before_content_sha256"] = before["content_sha256"]
        record["original_after_content_sha256"] = after["content_sha256"]
        record["destination_before_init"] = destination
        record["copy_pass"] = True
    except Exception:
        record["failure"] = traceback.format_exc()
    finally:
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle(handle)
        record["finished_utc"] = datetime.now(timezone.utc).isoformat()
        write_new(HERE / "phase2.json", record)
        if RECOVERY.is_dir():
            write_new(RECOVERY / ".recovery-legacy/COPY-VERIFICATION.json", record)
    print(json.dumps({"copy_pass": record["copy_pass"], "original_files_verified": len(record["original_files"]),
                      "supporting_files_verified": len(record["supporting_files"]), "failure": record["failure"],
                      "record": str(HERE / "phase2.json")}, indent=2))
    if not record["copy_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
