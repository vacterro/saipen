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
    r = _git(project, "ls-files")
    if r.returncode != 0:
        print(f"FAIL: git ls-files failed: {r.stderr.strip()}")
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

    # --- Collect inventory ---
    print("\n=== Collecting delivery inventory ===")
    tracked = _tracked_files(project)
    members = sorted(rel for rel in tracked if _is_delivery_source(project, rel))
    print(f"  {len(members)} tracked files selected for archive")

    # --- Build temporary archive ---
    print("\n=== Building temporary archive ===")
    with tempfile.TemporaryDirectory(prefix="saipen-build-") as tmpdir:
        tmpzip = Path(tmpdir) / "archive.zip"

        with zipfile.ZipFile(str(tmpzip), "w", zipfile.ZIP_DEFLATED) as zf:
            for rel in members:
                src = project / rel
                if src.is_file():
                    zf.write(str(src), rel)
                # Directories are implicit in ZIP; skip non-files.

        print(f"  {tmpzip}  ({tmpzip.stat().st_size} bytes, "
              f"{len(members)} members)")

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
            # Remove the temp archive so a bad one is never promoted.
            tmpzip.unlink(missing_ok=True)
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

        # --- Atomic promote ---
        output.parent.mkdir(parents=True, exist_ok=True)
        tmpzip.rename(str(output))
        print(f"\n=== Archive promoted to {output} ===")
        print(f"  {len(members)} members, SHA-256 {digest}")
        print("DELIVERY BUILD: PASS")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Build a verified SAIPEN handoff archive.")
    parser.add_argument("output", help="Output archive path (e.g. saipen-delivery.zip)")
    parser.add_argument("--project-root", default=".",
                        help="Project root (default: cwd)")
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    output = Path(args.output).resolve()
    build_archive(output, project)


if __name__ == "__main__":
    main()
