"""Record installed skill ownership; remove unchanged owned bytes only.

The ledger is local bookkeeping, not authorization. Unknown files and edited
files survive removal. An upgrade preserves extra files; edited runtime files
from the previous owned generation are retained in a sibling backup.

Preservation stops at the shipped surface (T-1951). A file INSIDE a manifest-
declared runtime tree is not an extra: the runtime identity hashes every member
of that tree, so resurrecting a retired module into the new generation makes
the installed copy permanently unequal to the source it came from. The
scheduled injector reads that inequality as a failed install and rolls the
publication back, forever, because the next run resurrects the same file. Those
bytes are kept in the sibling backup instead, where nothing reads them and the
user still has them.
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
#: The sibling backup lives in the host's skill scan root, and every host
#: registers a directory holding `SKILL.md` as a skill: a kept `SKILL.md` made
#: the backup a second `saipen` skill claiming every shortcut (T-1786). Its
#: bytes are kept under a name no host loads.
SKILL_ENTRY = "SKILL.md"
INERT_SUFFIX = ".user-backup"


def backup_relpath(relative: str) -> str:
    return relative + INERT_SUFFIX if relative == SKILL_ENTRY else relative


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
        manifest = json.loads((stage / "MANIFEST.json").read_text(encoding="utf-8"))
        managed = manifest.get("managed_dirs", [])
        # Everything the new generation ships, not just the required entries:
        # a copy tree lands whole, so every path under its src is shipped.
        shipped = set(managed)
        for tree in manifest.get("copy_trees", []):
            src = tree.get("src") if isinstance(tree, dict) else None
            if isinstance(src, str) and src:
                shipped.add(src.rstrip("/"))
        for entry in manifest.get("files", []):
            src = entry.get("src") if isinstance(entry, dict) else None
            if isinstance(src, str) and src:
                shipped.add(src.rstrip("/"))

        def inside_shipped_surface(relative: str) -> bool:
            return any(
                relative == path or relative.startswith(path + "/") for path in shipped
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
            if relative in owned or legacy_managed or inside_shipped_surface(relative):
                # A legacy install has no per-file proof, and a retired file
                # inside the shipped surface would poison the identity. Keep
                # the existing bytes separately; never drop them silently.
                backup = safe_path(backup_root, backup_relpath(relative))
                backup.parent.mkdir(parents=True, exist_ok=True)
                if not backup.exists():
                    shutil.copyfile(source, backup)
            else:
                # Outside every declared tree this is the user's own file, not
                # part of what the identity hashes, so it travels with the
                # install as the preservation contract promises.
                target = safe_path(stage, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        # `owned` deliberately stays the PRE-merge set. A preserved file must
        # not enter the ledger: the next run treats a ledger entry whose digest
        # is unchanged as already installed and skips it, and the fresh stage
        # never contains it, so recording it here would delete it one run later
        # -- trading a resurrection for a disappearance.
    (stage / LEDGER).write_text(
        json.dumps({"schema_version": 1, "files": owned}, indent=2) + "\n", encoding="utf-8"
    )


def stamp(destination: Path) -> None:
    """Record the provenance marker's digest in the ownership ledger.

    A destination with no ledger owns nothing, so there is nothing to stamp:
    that is the legacy or partial-install shape, and `remove` already treats it
    as `legacy` rather than as damage. Failing the whole install over that
    bookkeeping detail turned a re-run into a hard error, and the installer's
    only correct recovery would have been to install again -- so this is a
    no-op, not a raise.
    """
    destination = safe_root(destination)
    data = load(destination)
    if data is None:
        return
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


#: The per-user PATH launcher's ownership record and the directories it may
#: name (`tools/saipen_engine/path_launcher.py` writes both; T-1678).
LAUNCHER_RECORD = (".saipen", "path-launcher.json")
LAUNCHER_DIRS = (("bin",), (".local", "bin"))
LAUNCHER_NAMES = ("saipen", "saipen.cmd")


def remove_launcher(home: Path) -> dict:
    """Remove the PATH launchers the record names while their bytes are as
    written, then the record. A path outside the declared directories, or a
    file someone changed, stays."""
    home = home.resolve()
    record = home.joinpath(*LAUNCHER_RECORD)
    if not record.is_file():
        return {"removed": 0, "preserved": 0}
    data = json.loads(record.read_text(encoding="utf-8"))
    owned = data.get("files") if isinstance(data, dict) else None
    if not isinstance(owned, dict):
        raise ValueError("invalid PATH launcher record")
    allowed = {home.joinpath(*parts) for parts in LAUNCHER_DIRS}
    removed = preserved = 0
    for name, checksum in owned.items():
        path = Path(name)
        if (
            not path.is_absolute()
            or path.parent.resolve() not in allowed
            or path.name.lower() not in LAUNCHER_NAMES
            or path.is_symlink()
        ):
            preserved += 1
            continue
        if path.is_file() and digest(path) == checksum:
            path.unlink()
            removed += 1
        elif path.exists():
            preserved += 1
    record.unlink()
    return {"removed": removed, "preserved": preserved}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "action", choices=("record", "stamp", "remove", "remove-artifact", "remove-launcher")
    )
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
        elif args.action == "remove-launcher":
            result = remove_launcher(args.destination)
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
