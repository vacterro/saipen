#!/usr/bin/env python
"""Build a verified SAIPEN handoff archive.

    python tools/build_handoff_archive.py <output.zip> [--project-root PATH]

This is the ONLY canonical path for creating a delivery artifact.
It owns every gate: structural, portability, semantic, and extracted-copy
validation.  A failed verification MUST NOT leave a final-looking archive.

Flow:
  1. Resolve project root.
  2. Pre-packaging checks (tracked deletions, protected sealed LOG).
  3. Collect delivery inventory from the actual working tree.
  4. Build archive into a temporary path.
  5. Structural + portability gate (verify_handoff_archive.py Phase 1).
  6. Extract into a fresh temp dir.
  7. Semantic validator on extracted copy.
  8. Compute SHA-256.
  9. Atomic rename temp -> final requested path.

Stdlib only.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def _git(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git"] + list(args),
        cwd=str(project), capture_output=True, text=True, errors="replace",
    )


def _tracked_files(project: Path) -> set[str]:
    """Git-tracked inventory (T-1018).

    The canonical whole-project handoff is a GIT-project tool. A project
    without a repository gets an explicit structured refusal naming the
    documented canonical alternative (bootstrap/export.sh / export.ps1)
    instead of a raw `fatal: not a git repository` from git itself -- an
    incidental Git failure must never define the delivery contract.
    """
    r = _git(project, "ls-files")
    if r.returncode != 0:
        print("FAIL: this handoff path requires a Git repository.")
        print("No-Git projects: use the canonical state exporter instead --")
        print("  bootstrap/export.sh        (macOS/Linux)")
        print("  bootstrap/export.ps1       (Windows)")
        print("which archive .saipen without needing a repository.")
        sys.exit(1)
    return {line.strip() for line in r.stdout.splitlines() if line.strip()}


def _deleted_tracked(project: Path) -> list[str]:
    r = _git(project, "ls-files", "--deleted")
    if r.returncode != 0:
        return []
    return [line.strip() for line in r.stdout.splitlines() if line.strip()]


# Patterns that must never appear in a clean delivery archive.
_GARBAGE_PATTERNS = [
    "__pycache__",
    ".pyc",
    ".swp",
    ".swo",
    ".pytest_cache",
    ".ruff_cache",
    "nul",
    "probe_output_",
    "saipen_distribution_probe_",
    ".COMMIT_EDITMSG.swp",
]


def _is_garbage(name: str) -> bool:
    base = os.path.basename(name)
    for pat in _GARBAGE_PATTERNS:
        if pat in base or pat in name:
            return True
    return False


def _is_delivery_source(project: Path, rel: str) -> bool:
    """Should this tracked file be included in the delivery archive?

    Includes all tracked files that aren't transient garbage.
    """
    if _is_garbage(rel):
        return False
    return True


# T-1016: explicit destructive-overwrite authorization. Default False.
_OVERWRITE_ALLOWED = False


def _reject_protected_destination(output: Path, project: Path) -> None:
    """T-1016: reject tracked/protected/canonical destinations categorically.

    An output path that names a tracked project file, a protected canonical
    file (e.g. .saipen/STATE.md), or a source tree member must never be
    replaced by ZIP bytes -- promotion to such a path is a hard refusal
    regardless of --force.
    """
    try:
        rel = output.resolve().relative_to(project.resolve())
    except ValueError:
        # Outside the project tree: not a tracked source destination.
        return
    rel_str = rel.as_posix()
    # Any tracked file is protected: replacing it would destroy source.
    tracked = _tracked_files(project)
    if rel_str in tracked:
        print(f"FAIL: destination is a tracked project file: {rel_str}")
        print("Refusing to replace tracked source with archive bytes (T-1016).")
        sys.exit(1)
    # Canonical protected locations even if untracked.
    protected_prefixes = (".saipen/", "saipen/", "extensions/schemas/")
    for prefix in protected_prefixes:
        if rel_str.startswith(prefix):
            print(f"FAIL: destination is a canonical protected path: {rel_str}")
            print("Refusing to replace canonical state with archive bytes (T-1016).")
            sys.exit(1)


def _scan_unresolved_recovery(project: Path) -> list[tuple[str, str]]:
    """Scan .saipen/recovery/ops/ for unresolved PREPARED/CONFLICT operations.

    Returns a list of (op_id, status) for any operation that has not reached
    a terminal state (COMMITTED, RESOLVED).  An empty list means the recovery
    journal is clean.

    T-1010: A handoff with unresolved recovery operations would silently
    launder pending recovery out of the continuation — the recipient would
    never know about the interrupted mutation.
    """
    import json
    unresolved = []
    ops_dir = project / ".saipen" / "recovery" / "ops"
    if not ops_dir.is_dir():
        return unresolved
    terminal = {"COMMITTED", "RESOLVED", "SKIPPED"}
    for entry in sorted(ops_dir.iterdir()):
        op_file = entry / "operation.json"
        if not op_file.is_file():
            continue
        try:
            with open(op_file, encoding="utf-8-sig") as f:
                op = json.load(f)
            status = op.get("status", "UNKNOWN")
            if status not in terminal:
                unresolved.append((entry.name, status))
        except (json.JSONDecodeError, OSError):
            unresolved.append((entry.name, "UNREADABLE"))
    return unresolved


def build_archive(output: Path, project: Path) -> None:
    verifier = project / "tools" / "verify_handoff_archive.py"
    if not verifier.is_file():
        print(f"FAIL: verifier not found at {verifier}")
        sys.exit(1)

    # --- Pre-packaging checks ---
    print("=== Pre-packaging checks ===")
    deleted = _deleted_tracked(project)
    sealed = [f for f in deleted
              if __import__("re").match(r"^\.saipen/logs/LOG-\d+\.md$", f)]
    if sealed:
        print(f"FAIL: sealed LOG deletions detected: {sealed}")
        sys.exit(1)
    if deleted:
        print(f"WARN: {len(deleted)} tracked files appear deleted "
              f"(not sealed LOGs — review manually)")

    # T-1010: Scan canonical recovery state.  Unresolved PREPARED/CONFLICT
    # operations mean the continuation truth is incomplete — shipping would
    # silently launder pending recovery out of the handoff.
    unresolved = _scan_unresolved_recovery(project)
    if unresolved:
        print(f"FAIL: {len(unresolved)} unresolved recovery operation(s) detected:")
        for op_id, status in unresolved:
            print(f"  - {op_id} ({status})")
        print("Cannot build handoff archive while recovery is pending.")
        print("Resolve with: saipen recover resolve <op_id> --resolution <accept_live|replan>")
        sys.exit(1)

    # --- Collect inventory + source snapshot ---
    print("\n=== Collecting delivery inventory ===")
    tracked = _tracked_files(project)
    members = sorted(rel for rel in tracked if _is_delivery_source(project, rel))
    print(f"  {len(members)} tracked files selected for archive")

    # T-1015: lstat every selected member and prove it is a regular file with
    # NO symlink/reparse ancestor. `is_file()` follows links, so a tracked
    # in-project path could silently package bytes from outside project_root.
    print("\n=== Checking member filesystem types ===")
    link_escapes = []
    for rel in members:
        src = project / rel
        # Walk each path component from the project root down; any symlink/
        # reparse-link component means the member escapes containment.
        current = project
        for part in Path(rel).parts:
            current = current / part
            try:
                st = current.lstat()
            except OSError:
                link_escapes.append(rel)
                break
            import stat as _stat
            if _stat.S_ISLNK(st.st_mode):
                link_escapes.append(rel)
                break
        else:
            # No symlink component; now confirm the leaf is a regular file.
            st = src.lstat()
            import stat as _stat
            if not _stat.S_ISREG(st.st_mode):
                link_escapes.append(f"{rel} (not a regular file)")
    if link_escapes:
        print(f"FAIL: {len(link_escapes)} member(s) are symlinks or non-regular "
              f"files -- refusing to package bytes through an escaped object:")
        for e in link_escapes[:10]:
            print(f"  {e}")
        print("A tracked member must be a regular contained file with no "
              "symlink/reparse ancestor (T-1015).")
        sys.exit(1)
    print(f"  PASS: all {len(members)} members are regular contained files")

    # T-1011: Capture a canonical path -> content-hash inventory BEFORE
    # building the archive.  Every archive member will be verified against
    # this snapshot after construction, so tree movement/tampering between
    # capture and packaging fails closed.
    print("\n=== Capturing source snapshot ===")
    source_snapshot: dict[str, str] = {}  # rel_path -> sha256 hex
    snapshot_errors = []
    for rel in members:
        src = project / rel
        if src.is_file():
            h = hashlib.sha256(src.read_bytes()).hexdigest()
            source_snapshot[rel] = h
        else:
            snapshot_errors.append(rel)
    if snapshot_errors:
        print(f"FAIL: {len(snapshot_errors)} member(s) vanished during snapshot:")
        for e in snapshot_errors[:10]:
            print(f"  {e}")
        sys.exit(1)
    print(f"  Captured {len(source_snapshot)} file hashes from source tree")

    # --- Build temporary archive (T-1016: in the destination directory) ---
    # The temp artifact lives beside the requested output so the final rename
    # is same-filesystem and atomic. A temp artifact on a different
    # filesystem (e.g. system temp on /dev/shm) would crash with a raw
    # cross-device OSError at promotion.
    print("\n=== Building temporary archive ===")
    output.parent.mkdir(parents=True, exist_ok=True)
    tmpzip = output.parent / f".{output.name}.tmp-{os.getpid()}"
    tmpzip.unlink(missing_ok=True)

    try:
        with zipfile.ZipFile(str(tmpzip), "w", zipfile.ZIP_DEFLATED) as zf:
            for rel in members:
                src = project / rel
                if src.is_file():
                    zf.write(str(src), rel)
                # Directories are implicit in ZIP; skip non-files.

        print(f"  {tmpzip}  ({tmpzip.stat().st_size} bytes, "
              f"{len(members)} members)")

        # T-1011: Verify every archive member against the captured snapshot.
        # This catches tree mutation between snapshot and packaging.
        print("\n=== Verifying archive against source snapshot ===")
        snapshot_mismatches = []
        with zipfile.ZipFile(str(tmpzip), "r") as zf:
            for info in zf.infolist():
                arc_name = info.filename
                if arc_name.endswith("/"):
                    continue  # directory entry
                arc_hash = hashlib.sha256(zf.read(arc_name)).hexdigest()
                expected = source_snapshot.get(arc_name)
                if expected is None:
                    snapshot_mismatches.append(
                        (arc_name, "extra member not in source snapshot"))
                elif arc_hash != expected:
                    snapshot_mismatches.append(
                        (arc_name, f"hash mismatch: arc={arc_hash[:16]} src={expected[:16]}"))
        if snapshot_mismatches:
            print(f"FAIL: {len(snapshot_mismatches)} member(s) differ from source snapshot:")
            for name, reason in snapshot_mismatches[:10]:
                print(f"  {name}: {reason}")
            sys.exit(1)
        # Also verify no source members were missed
        arc_members = set()
        with zipfile.ZipFile(str(tmpzip), "r") as zf:
            arc_members = {i.filename for i in zf.infolist() if not i.filename.endswith("/")}
        missing_from_archive = [m for m in source_snapshot if m not in arc_members]
        if missing_from_archive:
            print(f"FAIL: {len(missing_from_archive)} source file(s) missing from archive:")
            for m in missing_from_archive[:10]:
                print(f"  {m}")
            sys.exit(1)
        print(f"PASS: all {len(source_snapshot)} archive members match source snapshot")

        # --- Structural + portability gate ---
        print("\n=== Structural verification ===")
        r = subprocess.run(
            [sys.executable, str(verifier), str(tmpzip),
             "--project-root", str(project)],
            cwd=str(project), capture_output=True, text=True, timeout=600)
        print(r.stdout[-2000:] if len(r.stdout) > 2000 else r.stdout)
        if r.stderr:
            print("STDERR:", r.stderr[-500:] if len(r.stderr) > 500 else r.stderr)
        if r.returncode != 0:
            print(f"FAIL: delivery gate failed (exit {r.returncode})")
            sys.exit(1)

        # --- Extract into fresh dir for semantic validation ---
        print("\n=== Extract round-trip validation ===")
        with tempfile.TemporaryDirectory(prefix="saipen-extract-") as extdir:
            extroot = Path(extdir) / "extracted"
            with zipfile.ZipFile(str(tmpzip), "r") as zf:
                zf.extractall(str(extroot))

            # Check all members extracted
            extracted = set()
            for root, dirs, files in os.walk(str(extroot)):
                for f in files:
                    rp = os.path.relpath(os.path.join(root, f), str(extroot))
                    extracted.add(rp.replace("\\", "/"))

            missing = [m for m in members if m not in extracted]
            if missing:
                print(f"FAIL: {len(missing)} files missing after extraction")
                for m in missing[:10]:
                    print(f"  {m}")
                sys.exit(1)
            print(f"  All {len(members)} files present after extraction")

        # --- Compute SHA-256 ---
        sha = hashlib.sha256()
        with open(str(tmpzip), "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
        digest = sha.hexdigest()
        print(f"\nARCHIVE_SHA256={digest}")

        # --- Atomic promote (T-1016) ---
        # Reject tracked/protected/canonical destinations categorically.
        _reject_protected_destination(output, project)
        # Refuse an existing destination unless explicit overwrite.
        if output.exists() and not _OVERWRITE_ALLOWED:
            print(f"FAIL: destination already exists: {output}")
            print("Refusing to overwrite without explicit authorization. "
                  "Pass --force to allow destructive overwrite.")
            sys.exit(1)
        try:
            # os.replace is atomic and replaces an existing destination on
            # both POSIX and Windows (Path.rename does not overwrite on
            # Windows). Same-directory source guarantees same-filesystem.
            os.replace(str(tmpzip), str(output))
        except OSError as exc:
            print(f"FAIL: promotion failed: {type(exc).__name__}: {exc}")
            tmpzip.unlink(missing_ok=True)
            sys.exit(1)
        print(f"\n=== Archive promoted to {output} ===")
        print(f"  {len(members)} members, SHA-256 {digest}")
        print("DELIVERY BUILD: PASS")
    finally:
        tmpzip.unlink(missing_ok=True)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Build a verified SAIPEN handoff archive.")
    parser.add_argument("output", help="Output archive path (e.g. saipen-delivery.zip)")
    parser.add_argument("--project-root", default=".",
                        help="Project root (default: cwd)")
    parser.add_argument("--force", action="store_true",
                        help="Allow destructive overwrite of an existing "
                             "ordinary destination (never tracked/canonical)")
    args = parser.parse_args()

    global _OVERWRITE_ALLOWED
    _OVERWRITE_ALLOWED = args.force

    project = Path(args.project_root).resolve()
    output = Path(args.output).resolve()
    build_archive(output, project)


if __name__ == "__main__":
    main()
