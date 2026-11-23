"""The identical final oracle on preserved pre-fix versus current owners."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
prefix = sys.argv[1]
OUTPUT = HERE / (prefix + ".json")
if OUTPUT.exists():
    raise SystemExit("Existing paired evidence is immutable")
owners = json.loads((HERE / "owned-before.json").read_text(encoding="utf-8"))
owners.update(json.loads((HERE / "owned-before-extra.json").read_text(encoding="utf-8")))
owners.update(json.loads((HERE / "owned-before-schema.json").read_text(encoding="utf-8")))
owners.pop("tools/test_t1711_regression_execution.py")
oracle_paths = ["tools/test_t1711_regression_execution.py", "tools/test_regression_gate.py",
                "tools/test_fixture_support.py", "tools/test_hermetic_env.py"]
command = [sys.executable, "-B", "tools/test_t1711_regression_execution.py"]

def hashes(root, paths):
    return {relative: hashlib.sha256((root / relative).read_bytes()).hexdigest()
            if (root / relative).is_file() else None for relative in sorted(paths)}

def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

oracle = hashes(ROOT, oracle_paths)
verifier = identity({"command": "python -B tools/test_t1711_regression_execution.py", "files": oracle})
current = hashes(ROOT, owners)
runs = []
temp_root = Path(tempfile.gettempdir()).resolve()

def execute(stage, subject):
    result = subprocess.run(command, cwd=subject, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=240)
    if hashes(subject, oracle_paths) != oracle:
        raise SystemExit("Frozen oracle moved")
    runs.append({"stage": stage, "verifier": verifier, "verifier_files": oracle,
                 "subject": identity(hashes(subject, owners)), "subject_files": hashes(subject, owners),
                 "command": command, "exit_code": result.returncode,
                 "stdout": result.stdout, "stderr": result.stderr})

with tempfile.TemporaryDirectory(prefix="saipen-t1711-control-", dir=temp_root) as temporary:
    control = Path(temporary).resolve() / "project"
    if not control.is_relative_to(temp_root):
        raise SystemExit("Control subject escaped its temporary scope")

    def ignore(directory, names):
        skipped = {"__pycache__", ".pytest_cache", ".ruff_cache"}
        if Path(directory) == ROOT:
            skipped.update({".git", ".saipen"})
        return set(names) & skipped

    shutil.copytree(ROOT, control, ignore=ignore)
    for relative, expected in owners.items():
        target = control / relative
        if expected is None:
            target.unlink(missing_ok=True)
            continue
        preserved = HERE / "owned-before" / relative
        if hashlib.sha256(preserved.read_bytes()).hexdigest() != expected:
            raise SystemExit("Pre-image changed: " + relative)
        shutil.copy2(preserved, target)
    execute("before", control)
execute("current", ROOT)
if hashes(ROOT, owners) != current or hashes(ROOT, oracle_paths) != oracle:
    raise SystemExit("Current subject changed during control execution")
if runs[0]["exit_code"] != 1 or runs[1]["exit_code"] != 0:
    OUTPUT.write_text(json.dumps({"verifier": verifier, "runs": runs}, indent=2) + "\n", encoding="utf-8")
    raise SystemExit("Paired execution did not produce expected red/green")
OUTPUT.write_text(json.dumps({"verifier": verifier, "runs": runs}, indent=2) + "\n", encoding="utf-8")
for value in runs:
    print(json.dumps({key: value[key] for key in ("stage", "verifier", "subject", "exit_code")}))
    print(" | ".join(value["stderr"].splitlines()[-4:]))
