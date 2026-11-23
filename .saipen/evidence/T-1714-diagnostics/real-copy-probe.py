"""Probe an exact copied AUDAPACK memory surface, with no live consumer writes."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ORIGINAL = Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK")
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.core_unit import _copy_saipen_once
from saipen_engine.process_tree import run
from saipen_engine.test_runner import _ignore_copy


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def ignore(directory: str, names: list[str]) -> set[str]:
    excluded = _ignore_copy(directory, names)
    if Path(directory).name == "locks":
        excluded.update(name for name in names if name.endswith(".lock"))
    return excluded


def catalog(base: Path) -> dict:
    files = {}
    for directory, dirs, names in os.walk(base, followlinks=False):
        excluded = ignore(directory, [*dirs, *names])
        dirs[:] = [name for name in dirs if name not in excluded]
        for name in [*dirs, *(name for name in names if name not in excluded)]:
            path = Path(directory) / name
            info = path.lstat()
            if path.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                raise RuntimeError("downstream memory has a link boundary: " + str(path))
            if path.is_file():
                files[path.relative_to(base).as_posix()] = sha(path.read_bytes())
    return files


def main() -> None:
    output = HERE / "real-copy-probe.json"
    if output.exists():
        raise RuntimeError("real-copy evidence already exists")
    original_before = catalog(ORIGINAL / ".saipen")
    live_memory = {name: sha((ROOT / ".saipen" / name).read_bytes())
                   for name in ("STATE.md", "BOARD.md", "LOG.md")}
    environment = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
    environment.update(SAIPEN_CAPABILITY="no-publish", PYTHONDONTWRITEBYTECODE="1",
                       PYTHONIOENCODING="utf-8", FORBID_SAIPEN_PROJECT_WRITE=str(ORIGINAL))
    base = Path(tempfile.mkdtemp(prefix="saipen-a05-real-copy-", dir="V:/_TEMP_"))
    project = base / "project"
    project.mkdir()
    if not _copy_saipen_once(ORIGINAL, project / ".saipen", ignore, lock=False):
        raise RuntimeError("original canonical checkpoint moved during optimistic copy")
    if catalog(project / ".saipen") != original_before:
        raise RuntimeError("copied downstream memory does not match original regular bytes")
    # Only the new scratch repository receives Git metadata; no consumer/source
    # publication or consumer HEAD is changed. Disable EOL conversion explicitly.
    (project / ".gitattributes").write_text("* -text\n", encoding="utf-8")
    for words in (("init",), ("add", "--", ".gitattributes", ".saipen/STATE.md",
                              ".saipen/BOARD.md", ".saipen/LOG.md", ".saipen/IDENTITY.md"),
                  ("-c", "user.name=A05 fixture", "-c", "user.email=fixture@invalid",
                   "commit", "-m", "Preserve copied forensic checkpoint")):
        run(["git", "-C", str(project), "-c", "core.autocrlf=false", *words],
            capture_output=True, env=environment, timeout=60, check=True)
    records = []
    before = catalog(project / ".saipen")
    for words in (("status",), ("recover", "--dry-run"), ("next",), ("explain-next",)):
        command = [sys.executable, "-B", str(ROOT / "tools/saipen.py"),
                   "--project-root", str(project), *words, "--json"]
        completed = run(command, cwd=project, env=environment, capture_output=True, timeout=90)
        stdout = completed.stdout.decode("utf-8", errors="replace")
        value = json.loads(stdout)
        payload = value["carrier"] if words == ("explain-next",) else value
        records.append({"command": command, "exit_code": completed.returncode,
                        "value": value, "stderr": completed.stderr.decode("utf-8", errors="replace")})
        if payload.get("code") != "HISTORY_LEDGER_CORRUPT":
            raise RuntimeError("copied real shape has a different diagnostic: " + stdout)
        if payload.get("canonical_next_command") is not None or payload.get("action"):
            raise RuntimeError("copied real shape advertises an unavailable repair: " + stdout)
        if payload.get("terminal_disposition") != "FORENSICALLY_UNRECOVERABLE":
            raise RuntimeError("copied real shape was not an honest terminal diagnostic")
        if catalog(project / ".saipen") != before:
            raise RuntimeError("read-only probe mutated copied memory")
    if catalog(ORIGINAL / ".saipen") != original_before:
        raise RuntimeError("live original memory moved during the copy probe")
    if live_memory != {name: sha((ROOT / ".saipen" / name).read_bytes()) for name in live_memory}:
        raise RuntimeError("probe changed the live protocol checkpoint")
    result = {"ok": True, "original": str(ORIGINAL), "copy": str(project),
              "copied_regular_files": len(before), "memory_manifest": before,
              "commands": records, "original_memory_unchanged": True,
              "copy_memory_unchanged": True, "live_protocol_memory_unchanged": True,
              "limits": "All copied regular .saipen bytes and provenance retained; caches/ephemeral locks excluded. "
                        "The current source CLI runs under the original unchanged bound protocol home. "
                        "Only a new scratch Git baseline was created; it is not the consumer's historical HEAD. "
                        "No real consumer repair, new lineage, original Git write, permission or publication."}
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "copy": str(project), "copied_regular_files": len(before),
                      "commands": [{"exit_code": row["exit_code"], "command": row["command"][-3:]}
                                   for row in records], "record": str(output)}))


if __name__ == "__main__":
    main()
