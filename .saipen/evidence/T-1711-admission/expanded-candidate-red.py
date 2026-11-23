"""The expanded oracle must detect the just-measured candidate's missing binding."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "expanded-candidate-red.json"
if OUTPUT.exists():
    raise SystemExit("Existing evidence is immutable")
scratch = json.loads((HERE / "prior-fix-scratch.json").read_text(encoding="utf-8"))
if scratch["exit_code"]:
    raise SystemExit("scratch positive control failed")
oracle_source = Path(scratch["project"]) / "tools/test_t1711_regression_execution.py"
expected = scratch["owned_paths"]["tools/test_t1711_regression_execution.py"]["scratch_sha256"]
if hashlib.sha256(oracle_source.read_bytes()).hexdigest() != expected:
    raise SystemExit("scratch oracle moved")
temp_root = Path(tempfile.gettempdir()).resolve()
with tempfile.TemporaryDirectory(prefix="saipen-t1711-prior-red-", dir=temp_root) as temporary:
    subject = Path(temporary).resolve() / "project"
    if not subject.is_relative_to(temp_root):
        raise SystemExit("candidate control escaped")

    def ignore(directory, names):
        skipped = {"__pycache__", ".pytest_cache", ".ruff_cache"}
        if Path(directory) == ROOT:
            skipped.update({".git", ".saipen"})
        return set(names) & skipped

    shutil.copytree(ROOT, subject, ignore=ignore)
    for relative, value in scratch["owned_paths"].items():
        if hashlib.sha256((subject / relative).read_bytes()).hexdigest() != value["live_before_sha256"]:
            raise SystemExit("live candidate moved before its red control")
    shutil.copy2(oracle_source, subject / "tools/test_t1711_regression_execution.py")
    oracle_paths = ["tools/test_t1711_regression_execution.py", "tools/test_regression_gate.py",
                    "tools/test_fixture_support.py", "tools/test_hermetic_env.py"]
    oracle = {relative: hashlib.sha256((subject / relative).read_bytes()).hexdigest()
              for relative in oracle_paths}
    verifier = hashlib.sha256(json.dumps({"command": "python -B tools/test_t1711_regression_execution.py",
                                          "files": oracle}, sort_keys=True).encode()).hexdigest()
    run = subprocess.run([sys.executable, "-B", "tools/test_t1711_regression_execution.py"],
                         cwd=subject, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=240)
    if hashlib.sha256((subject / "tools/test_t1711_regression_execution.py").read_bytes()).hexdigest() != expected:
        raise SystemExit("expanded oracle moved during candidate control")
    value = {"subject": "preserved 39-case candidate, with the final expanded oracle",
             "verifier": verifier, "oracle_files": oracle, "candidate_paths": scratch["owned_paths"],
             "exit_code": run.returncode, "stdout": run.stdout, "stderr": run.stderr,
             "scope": "disposable clone; live production and canonical state unchanged"}
    OUTPUT.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"exit_code": run.returncode, "verifier": verifier, "record": str(OUTPUT)}))
    print(" | ".join(run.stderr.splitlines()[-4:]))
    if run.returncode != 1:
        raise SystemExit("expanded negative control did not detect the candidate defect")
