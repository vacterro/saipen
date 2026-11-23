"""The per-user PATH launcher: `saipen` typed in any shell (T-1678, SRC-192).

PATH_LAUNCHER is the first transport of `SAIPEN_ENTRY.json`, and until this
module nothing created one. Measured on the operator's machine on 2026-10-08:
every host answered degraded `no_canonical_path_launcher`, and an executor
that typed `saipen` got "command not found" until two hand copies of the
launchers were put in a directory on PATH (E-13246). A hand copy goes stale the
moment the launcher it was copied from is re-rendered, and nothing reports it.

One owner, three facts:

* **Directory.** A DECLARED per-user directory: the first of `declared_dirs`
  that is already on PATH. Nothing outside the account's home is written, and
  PATH is never edited -- when no declared directory is on PATH the status
  says so and names the one to add.
* **Bytes.** Both launchers in the one form `bootstrap/cli_launcher.py`
  renders for a home's own `bin/`: the canonical engine run by an interpreter
  that exists. `entry_resolver.prove_launcher` proves them from their bytes,
  exactly as it proves any other launcher.
* **Ownership.** `<home>/.saipen/path-launcher.json` names every file this
  module wrote with its digest. A file is replaced or removed only while it is
  ours and unchanged, or while it already proves the canonical engine (a hand
  copy of this home's own launcher, which install adopts). Any other `saipen`
  in the directory belongs to someone else and is never touched.

The uninstallers read the same record (`bootstrap/install_ownership.py
remove-launcher`, or natively), so `install`, `status` and removal agree on
one definition of "ours".
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

from . import entry_resolver

SCHEMA = 1
KIND = "saipen-path-launcher"
RECORD = "path-launcher.json"
WINDOWS_NAME = "saipen.cmd"
POSIX_NAME = "saipen"

CODE_READY = "PATH_LAUNCHER_READY"
CODE_ABSENT = "PATH_LAUNCHER_ABSENT"
CODE_STALE = "PATH_LAUNCHER_STALE"
CODE_FOREIGN = "PATH_LAUNCHER_FOREIGN"
CODE_SHADOWED = "PATH_LAUNCHER_SHADOWED"
CODE_NO_DIRECTORY = "PATH_LAUNCHER_NO_DIRECTORY"
CODE_INSTALLED = "PATH_LAUNCHER_INSTALLED"
CODE_CURRENT = "PATH_LAUNCHER_CURRENT"
CODE_REMOVED = "PATH_LAUNCHER_REMOVED"

INSTALL_ACTION = "saipen host launcher install"
#: The states `host repair` brings back: a launcher that is missing, or ours
#: and no longer proving, or a hand copy that proves and is nobody's.
REPAIRABLE = (CODE_ABSENT, CODE_STALE)


def names() -> tuple[str, ...]:
    """The launcher files of this platform. Windows gets both, because Git
    Bash on Windows resolves the extensionless `saipen` and cmd.exe and
    PowerShell resolve `saipen.cmd`."""
    return (WINDOWS_NAME, POSIX_NAME) if os.name == "nt" else (POSIX_NAME,)


def declared_dirs(home: Path | str | None = None) -> list[Path]:
    """The per-user directories a PATH launcher may live in, in order. All of
    them are inside the account's home; none is created unless PATH already
    names it."""
    base = Path(home) if home is not None else Path.home()
    if os.name == "nt":
        return [base / "bin", base / ".local" / "bin"]
    return [base / ".local" / "bin", base / "bin"]


def record_path(home: Path | str | None = None) -> Path:
    base = Path(home) if home is not None else Path.home()
    return base / ".saipen" / RECORD


def render(python: str, engine: str) -> dict[str, bytes]:
    """The exact bytes `bootstrap/cli_launcher.render_launchers` writes (the
    test module pins the two equal): the form `prove_launcher` parses."""

    def dq(value: str) -> str:
        return '"' + str(value).replace('"', '\\"') + '"'

    windows = "@echo off\r\n" + dq(python) + " " + dq(engine) + " %*\r\n"
    posix = "#!/bin/sh\nexec " + dq(python) + " " + dq(engine) + ' "$@"\n'
    rendered = {WINDOWS_NAME: windows.encode("utf-8"), POSIX_NAME: posix.encode("utf-8")}
    return {name: rendered[name] for name in names()}


def _digest(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _norm(path: Path | str) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def _path_entries(env: dict) -> list[str]:
    return [_norm(item) for item in str(env.get("PATH") or "").split(os.pathsep) if item.strip()]


def select_dir(home: Path | str | None = None, env: dict | None = None) -> Path | None:
    """The first declared directory PATH names, or None."""
    entries = _path_entries(dict(os.environ if env is None else env))
    for candidate in declared_dirs(home):
        if _norm(candidate) in entries:
            return candidate
    return None


def read_record(home: Path | str | None = None) -> dict:
    """`{absolute path: sha256}` of the files this module wrote. A missing or
    unreadable record owns nothing."""
    try:
        payload = json.loads(record_path(home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, dict):
        return {}
    return {str(path): str(digest) for path, digest in files.items() if isinstance(digest, str)}


def _owned(path: Path, record: dict) -> bool:
    digest = _digest(path)
    return digest is not None and any(
        _norm(owned) == _norm(path) and expected == digest for owned, expected in record.items()
    )


def status(
    engine: Path | str,
    home: Path | str | None = None,
    env: dict | None = None,
) -> dict:
    """The PATH launcher as the doctor reports it. Read-only."""
    source_env = dict(os.environ if env is None else env)
    directory = select_dir(home, source_env)
    report: dict = {
        "ok": False,
        "code": CODE_NO_DIRECTORY,
        "directory": str(directory) if directory else None,
        "declared": [str(item) for item in declared_dirs(home)],
        "engine": str(engine),
        "files": {},
        "reasons": [],
        "action": None,
    }
    if directory is None:
        report["reasons"].append(
            "no declared per-user directory is on PATH: " + " or ".join(report["declared"])
        )
        report["action"] = f"add {report['declared'][0]} to PATH, then {INSTALL_ACTION}"
        return report
    record = read_record(home)
    present = absent = foreign = stale = 0
    for name in names():
        path = directory / name
        if not path.is_file():
            report["files"][name] = "absent"
            absent += 1
            continue
        present += 1
        proof = entry_resolver.prove_launcher(path, engine)
        owned = _owned(path, record)
        if owned and proof["ok"]:
            report["files"][name] = "owned"
        elif proof["ok"]:
            report["files"][name] = "unowned-proving"
            stale += 1
            report["reasons"].append(f"{path} proves the engine but no installer owns it")
        elif owned:
            report["files"][name] = "owned-stale"
            stale += 1
            report["reasons"].append(f"{path}: {proof['why']}")
        else:
            report["files"][name] = "foreign"
            foreign += 1
            report["reasons"].append(f"{path} is not ours and does not prove: {proof['why']}")
    if foreign:
        report["code"] = CODE_FOREIGN
        report["action"] = (
            f"remove or rename the foreign launcher in {directory}, then {INSTALL_ACTION}"
        )
        return report
    if not present:
        report["code"] = CODE_ABSENT
        report["action"] = INSTALL_ACTION
        return report
    if stale or absent:
        report["code"] = CODE_STALE
        if absent:
            report["reasons"].append("one launcher of the pair is missing")
        report["action"] = INSTALL_ACTION
        return report
    which = shutil.which("saipen", path=source_env.get("PATH", ""))
    if which is None or Path(_norm(which)).parent != Path(_norm(directory)):
        report["code"] = CODE_SHADOWED
        report["shadowed_by"] = which
        report["reasons"].append(f"`saipen` resolves to {which}, earlier on PATH than {directory}")
        report["action"] = f"move {directory} ahead of {Path(str(which)).parent} on PATH"
        return report
    report["ok"] = True
    report["code"] = CODE_READY
    return report


def install(
    engine: Path | str,
    home: Path | str | None = None,
    env: dict | None = None,
    python: str | None = None,
) -> dict:
    """Write both launchers into the selected directory and own them.

    Idempotent. Refuses, and writes nothing, when no declared directory is on
    PATH or when a launcher there is someone else's.
    """
    before = status(engine, home, env)
    if before["code"] in (CODE_NO_DIRECTORY, CODE_FOREIGN):
        return {**before, "ok": False}
    directory = Path(before["directory"])
    interpreter = str(Path(python or sys.executable))
    if not Path(interpreter).is_file():
        return {
            **before,
            "ok": False,
            "reasons": [f"the interpreter does not exist: {interpreter}"],
        }
    if before["code"] in (CODE_READY, CODE_SHADOWED):
        return {**before, "ok": True, "code": CODE_CURRENT, "status": before["code"]}
    record = read_record(home)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        for name, payload in render(interpreter, str(engine)).items():
            target = directory / name
            temporary = target.with_name(f".{name}.saipen-{os.getpid()}")
            temporary.write_bytes(payload)
            if name == POSIX_NAME:
                with contextlib.suppress(OSError):
                    temporary.chmod(0o755)
            os.replace(temporary, target)
            record = {
                path: digest for path, digest in record.items() if _norm(path) != _norm(target)
            }
            record[str(target)] = hashlib.sha256(payload).hexdigest()
        _write_record(home, record)
    except OSError as exc:
        return {**before, "ok": False, "reasons": [f"{type(exc).__name__}: {exc}"]}
    after = status(engine, home, env)
    return {
        **after,
        "ok": after["code"] in (CODE_READY, CODE_SHADOWED),
        "code": CODE_INSTALLED,
        "status": after["code"],
        "previous": before["code"],
    }


def remove(home: Path | str | None = None) -> dict:
    """Delete every launcher the record names whose bytes are still ours, then
    the record. A file someone changed since it was written stays."""
    record = read_record(home)
    declared = {_norm(item) for item in declared_dirs(home)}
    removed: list[str] = []
    kept: list[str] = []
    for owned, expected in record.items():
        path = Path(owned)
        if _norm(path.parent) not in declared or path.name not in (WINDOWS_NAME, POSIX_NAME):
            kept.append(owned)
            continue
        if _digest(path) == expected:
            with contextlib.suppress(FileNotFoundError):
                path.unlink()
            removed.append(owned)
        elif path.exists():
            kept.append(owned)
    with contextlib.suppress(FileNotFoundError):
        record_path(home).unlink()
    return {"ok": True, "code": CODE_REMOVED, "removed": removed, "kept": kept}


def _write_record(home: Path | str | None, files: dict) -> None:
    path = record_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps({"schema": SCHEMA, "kind": KIND, "files": files}, indent=2, sort_keys=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}")
    temporary.write_text(body + "\n", encoding="utf-8")
    os.replace(temporary, path)


__all__ = [
    "CODE_ABSENT",
    "CODE_CURRENT",
    "CODE_FOREIGN",
    "CODE_INSTALLED",
    "CODE_NO_DIRECTORY",
    "CODE_READY",
    "CODE_REMOVED",
    "CODE_SHADOWED",
    "CODE_STALE",
    "INSTALL_ACTION",
    "REPAIRABLE",
    "declared_dirs",
    "install",
    "names",
    "read_record",
    "record_path",
    "remove",
    "render",
    "select_dir",
    "status",
]
