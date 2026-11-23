"""One fixed native oracle against original, earlier and corrected imports."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[2]
OLD = EVIDENCE.parent / "tool-module-identity"
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.evidence import EvidenceRun
from test_hermetic_env import hermetic_env

ORACLES = (
    "tools/test_tool_module_identity.py",
    "tools/test_module_duplication_guard.py",
    "tools/test_engine_module_identity.py",
    "tools/test_hermetic_env.py",
)
SUBJECTS = ("tools/__init__.py", "tools/_module_identity.py")
COMMAND = [sys.executable, "-B", "-m", "unittest", "tools.test_tool_module_identity",
           "tools.test_module_duplication_guard", "tools.test_engine_module_identity", "-q"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "ABSENT"


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def ignore(directory: str, names: list[str]) -> list[str]:
    excluded = {".git", "__pycache__", ".ruff_cache", ".pytest_cache"}
    if Path(directory).resolve() == ROOT:
        excluded.add(".saipen")
    return [name for name in names if name in excluded]


def hooked_init() -> bytes:
    original = (EVIDENCE / "pre-fix-init.py").read_text(encoding="utf-8")
    anchor = "from types import ModuleType\n"
    assert original.count(anchor) == 1
    insertion = "\nfrom ._module_identity import install as _install_tool_finder\n"
    return (original.replace(anchor, anchor + insertion, 1)
            + "\n_install_tool_finder(_TOOLS)\n").encode()


def run(label: str) -> int:
    durable = EVIDENCE / label
    if durable.exists():
        raise RuntimeError("immutable evidence label already exists")
    before = {name: sha(ROOT / name) for name in (*ORACLES, *SUBJECTS)}
    allocation = EvidenceRun("t1348-" + label, "T-1348", durable_dir=durable)
    ownership = allocation.temp_root / "ownership.json"
    ownership.write_text(json.dumps({"ticket": "T-1348", "label": label,
        "temp_root": str(allocation.temp_root), "pid": __import__("os").getpid()}), encoding="utf-8")
    allocation.retain(ownership)
    original, earlier, corrected = [allocation.temp_root / name
                                     for name in ("original", "earlier", "corrected")]
    allocation.register_ephemeral(original, earlier, corrected, ownership)
    shutil.copytree(ROOT, original, ignore=ignore)
    shutil.copyfile(EVIDENCE / "pre-fix-init.py", original / "tools/__init__.py")
    (original / "tools/_module_identity.py").unlink(missing_ok=True)
    shutil.copyfile(EVIDENCE / "candidate_tests.py", original / ORACLES[0])
    shutil.copyfile(EVIDENCE / "candidate_guard.py", original / ORACLES[1])
    for directory, helper in ((earlier, OLD / "candidate_module_identity.py"),
                              (corrected, EVIDENCE / "candidate_module_identity.py")):
        shutil.copytree(original, directory)
        (directory / "tools/__init__.py").write_bytes(hooked_init())
        shutil.copyfile(helper, directory / "tools/_module_identity.py")
    verifier = {"command": COMMAND, "timeout": 300,
                "files": {name: sha(original / name) for name in ORACLES}}
    records = []
    for name, subject in (("original", original), ("earlier", earlier), ("corrected", corrected)):
        assert all(sha(subject / path) == value for path, value in verifier["files"].items())
        identity = {path: sha(subject / path) for path in SUBJECTS}
        result = subprocess.run(COMMAND, cwd=subject, env=hermetic_env(),
                                capture_output=True, text=True, encoding="utf-8", timeout=300)
        output = result.stdout + result.stderr
        collected = re.search(r"Ran (\d+) tests?", output)
        record = {"name": name, "exit_code": result.returncode,
                  "collected": int(collected.group(1)) if collected else None,
                  "verifier": digest(verifier), "subject": digest(identity),
                  "verifier_identity": verifier, "subject_identity": identity,
                  "output_sha256": hashlib.sha256(output.encode()).hexdigest()}
        (durable / (name + ".txt")).write_text(output, encoding="utf-8")
        (durable / (name + ".json")).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        records.append(record)
        print(json.dumps({key: record[key] for key in ("name", "exit_code", "collected", "verifier", "subject")}), flush=True)
        print(output[-500:], flush=True)
    unchanged = before == {name: sha(ROOT / name) for name in before}
    live_matches_corrected = all(sha(ROOT / name) == sha(corrected / name)
                                 for name in (*ORACLES, *SUBJECTS))
    okay = (records[0]["exit_code"] != 0 and records[1]["exit_code"] != 0
            and records[2]["exit_code"] == 0 and unchanged
            and all(record["collected"] == records[2]["collected"] for record in records))
    summary = {"pair_ok": okay, "live_unchanged": unchanged,
               "live_matches_corrected": live_matches_corrected,
               "verifier": digest(verifier), "records": records,
               "driver_sha256": sha(Path(__file__)), "temp_root": str(allocation.temp_root),
               "root_metadata_excluded": True, "nested_metadata_retained": True}
    (durable / "result.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    allocation.finalize(verdict="PASS" if okay else "FAIL", extra={"pair_ok": okay})
    assert not allocation.temp_root.exists()
    print(json.dumps({"pair_ok": okay, "live_unchanged": unchanged,
                      "live_matches_corrected": live_matches_corrected, "temp_reclaimed": True}), flush=True)
    return 0 if okay else 1


if __name__ == "__main__":
    if len(sys.argv) != 2 or not re.fullmatch(r"[a-z][a-z0-9-]*", sys.argv[1]):
        raise SystemExit("one unique evidence label required")
    raise SystemExit(run(sys.argv[1]))
