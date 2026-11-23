"""Read-only AUDAPACK recovery evidence; writes only this SAIPEN evidence folder."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME_ROOT = HERE.parents[2]
TARGET = Path("V:/___VAC/__K/__CODE/_PY/_AUDAPACK")
CASE = HOME_ROOT / ".saipen/evidence/AUDAPACK-T299-forensics/snapshot-20261010T090700Z"
sys.path.insert(0, str(HOME_ROOT / "tools"))
from saipen_engine import board, codec, journal, lifecycle_authority, log, state
from saipen_engine.controls import milestone_status


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", "-C", str(TARGET), *args])


def inventory():
    names = git("ls-files", "--cached", "-z").decode("utf-8").split("\0")
    tracked = {name: sha(TARGET / name) for name in names if name and (TARGET / name).is_file()}
    protected = {}
    for directory in ("recovery", "logs", "intake", "archive", "quarantine", "evidence"):
        for path in (TARGET / ".saipen" / directory).rglob("*"):
            if path.is_file():
                if not path.resolve().is_relative_to(TARGET.resolve()):
                    raise RuntimeError(f"protected source escapes AUDAPACK: {path}")
                protected[path.relative_to(TARGET).as_posix()] = sha(path)
    protected.update({path.relative_to(TARGET).as_posix(): sha(path)
                      for path in (TARGET / ".saipen").iterdir() if path.is_file()})
    return {
        "head": git("rev-parse", "HEAD").decode().strip(),
        "refs": git("for-each-ref", "--format=%(refname) %(objectname)").decode(),
        "reachable_history_sha256": hashlib.sha256(git("rev-list", "--all", "--objects")).hexdigest(),
        "index_projection_sha256": hashlib.sha256(git("ls-files", "--stage", "-z")).hexdigest(),
        "dirty": git("status", "--porcelain=v1").decode(),
        "tracked_worktree": tracked, "protected": protected,
    }


def case_check():
    acquisition = json.loads((CASE / "ACQUISITION.json").read_text(encoding="utf-8"))
    findings = []
    for row in acquisition["files"]:
        for kind, path in (("original", TARGET / row["path"]), ("copy", Path(row["copy"]))):
            actual = sha(path) if path.is_file() else None
            if actual != row["sha256"]:
                findings.append({"kind": kind, "path": row["path"],
                                 "expected": row["sha256"], "actual": actual})
    return {"file_count": len(acquisition["files"]), "comparisons": 2 * len(acquisition["files"]),
            "unchanged": not findings, "findings": findings,
            "acquisition_sha256": sha(CASE / "ACQUISITION.json")}


def main():
    label = sys.argv[1]
    if Path(label).name != label:
        raise SystemExit("invalid label")
    destination = HERE / f"AUDAPACK-{label}.json"
    if destination.exists():
        raise SystemExit("existing evidence is immutable")
    before = inventory()
    preserved = case_check()
    history = log.read_history_snapshot(TARGET)
    parsed_board = board.parse_board(codec.read_doc(TARGET / ".saipen/BOARD.md"))
    parsed_state = state.parse_state(codec.read_doc(TARGET / ".saipen/STATE.md"))
    authority = lifecycle_authority.assess(TARGET, parsed_state, parsed_board, history.events)
    pending, conflicts = journal.scan_pending(TARGET)
    commands = []
    launcher = str(HOME_ROOT / "bin/saipen.cmd")
    for name, argv in (
        ("status", [launcher, "--project-root", str(TARGET), "status", "--json"]),
        ("recover", [launcher, "--project-root", str(TARGET), "recover", "--dry-run", "--json"]),
        ("next", [launcher, "--project-root", str(TARGET), "next", "--json"]),
        ("native", [sys.executable, "-B", str(HOME_ROOT / "tools/validate.py"),
                    "--project-root", str(TARGET), "--gate", "core", "--no-receipt"]),
    ):
        output = HERE / f"AUDAPACK-{label}-{name}.txt"
        if output.exists():
            raise SystemExit("existing output is immutable")
        run = subprocess.run(argv, cwd=TARGET, stdin=subprocess.DEVNULL,
                             capture_output=True, timeout=300, check=False)
        raw = run.stdout + run.stderr
        output.write_bytes(raw)
        try:
            payload = json.loads(run.stdout)
        except (ValueError, UnicodeError):
            payload = None
        commands.append({"name": name, "argv": argv, "exit_code": run.returncode,
                         "output": output.relative_to(HOME_ROOT).as_posix(),
                         "output_sha256": sha(output), "payload": payload,
                         "native_summary": re.findall(r"Validation (?:FAILED|complete)[^\r\n]*",
                                                       raw.decode("utf-8", errors="replace"))})
    after = inventory()
    record = {
        "checked_utc": datetime.now(timezone.utc).isoformat(), "target": str(TARGET),
        "before": before, "after": after, "protected_and_git_unchanged": before == after,
        "sealed_case": preserved, "state": parsed_state, "board_errors": parsed_board["errors"],
        "history_errors": log.snapshot_contract_errors(history), "history_tail": history.tail,
        "lifecycle_authority": authority, "pending": pending, "conflicts": conflicts,
        "milestone": milestone_status(TARGET), "commands": commands,
        "normal_agent_operations_permitted": False, "recovery_applied": False,
        "classification": "NO_GO; READ_ONLY_DIAGNOSIS_ONLY; operator decision on proposed new epoch",
        "limits": "Tracked source and named protected trees inventoried; the sealed acquisition is rechecked. "
                  "No claim that unavailable external backups or all ignored/untracked source files were acquired.",
    }
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"record": destination.relative_to(HOME_ROOT).as_posix(),
                      "protected_and_git_unchanged": before == after, "sealed_case": preserved,
                      "floor": authority.get("floor"), "authority": authority.get("status"),
                      "commands": [{"name": r["name"], "exit_code": r["exit_code"],
                                    "code": (r["payload"] or {}).get("code"),
                                    "native_summary": r["native_summary"]} for r in commands]}, indent=2))
    return 0 if before == after and preserved["unchanged"] else 1


if __name__ == "__main__":
    sys.exit(main())
