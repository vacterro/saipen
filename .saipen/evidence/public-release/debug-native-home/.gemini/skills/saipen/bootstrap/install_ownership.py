"""Record installed skill ownership; remove unchanged owned bytes only.

The ledger is local bookkeeping, not authorization. Unknown files and edited
files survive removal. An upgrade preserves extra files; edited runtime files
from the previous owned generation are retained in a sibling backup.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

LEDGER = ".saipen_install.json"
PROVENANCE = ".saipen_runtime.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_root(path: Path) -> Path:
    absolute = path.absolute()
    if absolute.is_symlink() or not absolute.resolve().is_relative_to(absolute.parent.resolve()):
        raise ValueError(f"installation root is a link outside its parent: {path}")
    return absolute.resolve()


def safe_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str):
        raise ValueError("installation ownership path must be text")
    parts = relative.split("/")
    if (
        not relative
        or "\\" in relative
        or any(p in ("", ".", "..") for p in parts)
        or ":" in relative
    ):
        raise ValueError("unsafe installation ownership path")
    candidate = root.joinpath(*parts)
    if candidate.is_symlink() or not candidate.resolve().is_relative_to(root):
        raise ValueError(f"installation ownership path escapes root: {relative}")
    return candidate


def load(root: Path) -> dict | None:
    path = safe_path(root, LEDGER)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != 1
        or not isinstance(data.get("files"), dict)
    ):
        raise ValueError("invalid installation ownership ledger")
    for relative, checksum in data["files"].items():
        safe_path(root, relative)
        if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
            raise ValueError("invalid installation ownership digest")
    return data


def files(root: Path) -> dict[str, str]:
    result = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        safe_path(root, relative)
        if path.is_file() and relative != LEDGER:
            result[relative] = digest(path)
    return result


def record(stage: Path, destination: Path) -> None:
    stage, destination = safe_root(stage), safe_root(destination)
    owned = files(stage)
    previous = load(destination) if destination.is_dir() else None
    if destination.is_dir():
        existing = files(destination)
        backup_root = safe_root(
            destination.parent
            / (
                ".saipen-user-backup-"
                + hashlib.sha256(json.dumps(existing, sort_keys=True).encode()).hexdigest()[:16]
            )
        )
        managed = json.loads((stage / "MANIFEST.json").read_text(encoding="utf-8")).get(
            "managed_dirs", []
        )
        for relative, checksum in existing.items():
            if relative == PROVENANCE:
                continue
            old_owned = (previous or {}).get("files", {}).get(relative)
            if old_owned == checksum:
                continue
            source = safe_path(destination, relative)
            legacy_managed = previous is None and any(
                relative.startswith(str(p) + "/") for p in managed
            )
            if relative in owned or legacy_managed:
                # A legacy install has no per-file proof. Keep its existing
                # generation separately; never overwrite user edits silently.
                backup = safe_path(backup_root, relative)
                backup.parent.mkdir(parents=True, exist_ok=True)
                if not backup.exists():
                    shutil.copyfile(source, backup)
            else:
                target = safe_path(stage, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
    (stage / LEDGER).write_text(
        json.dumps({"schema_version": 1, "files": owned}, indent=2) + "\n", encoding="utf-8"
    )


def stamp(destination: Path) -> None:
    destination = safe_root(destination)
    data = load(destination)
    if data is None:
        raise ValueError("installation ownership ledger missing")
    marker = safe_path(destination, PROVENANCE)
    if marker.is_file():
        data["files"][PROVENANCE] = digest(marker)
    (destination / LEDGER).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def remove(destination: Path) -> dict:
    destination = safe_root(destination)
    if not destination.exists():
        return {"removed": 0, "preserved": 0}
    data = load(destination)
    if data is None:
        # Unproved legacy directories are preserved, never recursively erased.
        return {"removed": 0, "preserved": len(files(destination)), "legacy": True}
    # Check every path before the first destructive operation.
    current = files(destination)
    removed = 0
    for relative, checksum in data["files"].items():
        path = safe_path(destination, relative)
        if current.get(relative) == checksum:
            path.unlink()
            removed += 1
    (destination / LEDGER).unlink()
    for directory in sorted(
        (p for p in destination.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True
    ):
        safe_path(destination, directory.relative_to(destination).as_posix())
        if not any(directory.iterdir()):
            directory.rmdir()
    preserved = len(files(destination))
    if not any(destination.iterdir()):
        destination.rmdir()
    return {"removed": removed, "preserved": preserved}


def remove_artifact(destination: Path, source: Path, home: Path) -> dict:
    """Remove an unchanged guard; preserve files modified by their owner."""
    home = home.resolve()
    destination = safe_path(home, destination.absolute().relative_to(home).as_posix())
    if not destination.exists():
        return {"removed": 0, "preserved": 0}
    if not destination.is_file():
        raise ValueError("hook artifact is not a file")
    if digest(destination) != digest(source):
        return {"removed": 0, "preserved": 1}
    destination.unlink()
    return {"removed": 1, "preserved": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("record", "stamp", "remove", "remove-artifact"))
    parser.add_argument("destination", type=Path)
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--home", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "record":
            if args.stage is None:
                raise ValueError("record requires --stage")
            record(args.stage, args.destination)
            result = {"recorded": True}
        elif args.action == "stamp":
            stamp(args.destination)
            result = {"stamped": True}
        elif args.action == "remove-artifact":
            if args.source is None or args.home is None:
                raise ValueError("remove-artifact requires --source and --home")
            result = remove_artifact(args.destination, args.source, args.home)
        else:
            result = remove(args.destination)
        print(json.dumps(result))
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAILED: installation ownership: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
