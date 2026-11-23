"""Run the unchanged final real-transaction oracle on saved/current operations."""
import hashlib
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

directory = Path(__file__).resolve().parent
root = directory.parents[2]
tools = root / "tools"
sys.path.insert(0, str(tools))
target = "test_real_reconciliation_preserves_history_and_owes_publication"
if len(sys.argv) > 1:
    if sys.argv[1] == "prefix":
        import saipen_engine
        name = "saipen_engine.operations"
        spec = importlib.util.spec_from_file_location(name, tools / "saipen_engine/operations.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        saipen_engine.operations = module
        prefix = directory / "prefix/operations.py"
        exec(compile(prefix.read_bytes(), str(tools / "saipen_engine/operations.py"), "exec"), module.__dict__)
    suite = unittest.TestLoader().discover(str(tools), pattern="test_t1839_cohort_reconciliation.py")
    def flatten(item):
        if isinstance(item, unittest.TestSuite):
            return [case for child in item for case in flatten(child)]
        return [item]
    cases = [case for case in flatten(suite) if case.id().endswith("." + target)]
    if len(cases) != 1:
        raise SystemExit("final acceptance oracle must collect exactly once")
    from test_hermetic_env import isolate_host_session
    isolate_host_session()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(cases))
    raise SystemExit(0 if result.wasSuccessful() else 1)

oracle_files = [Path(__file__).resolve(), tools / "test_t1839_cohort_reconciliation.py",
                tools / "test_orchestration_repair.py", tools / "test_closure_provenance.py",
                tools / "test_hermetic_env.py"]
oracle = hashlib.sha256()
for path in sorted(oracle_files):
    oracle.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
context_files = [path for path in (tools / "saipen_engine").rglob("*.py")
                 if path.name != "operations.py"] + [tools / "saipen.py"]
context_files += list((root / "saipen").rglob("*.md")) + list((root / "saipen").rglob("*.json"))
def context_digest():
    digest = hashlib.sha256()
    for path in sorted(context_files):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()
context = context_digest()
rows = []
for mode in ("prefix", "current"):
    command = [sys.executable, "-B", str(Path(__file__).resolve()), mode]
    measured = subprocess.run(command, cwd=root, capture_output=True, text=True,
                              encoding="utf-8", timeout=120)
    log = measured.stdout + measured.stderr
    (directory / f"{mode}-final-oracle.log").write_text(log, encoding="utf-8")
    subject = directory / "prefix/operations.py" if mode == "prefix" else tools / "saipen_engine/operations.py"
    rows.append({"subject": mode, "exit_code": measured.returncode,
                 "oracle_sha256": oracle.hexdigest(),
                 "context_sha256": context,
                 "subject_sha256": hashlib.sha256(subject.read_bytes()).hexdigest(),
                 "command": command, "runtime": sys.version,
                 "scope": "controlled operations module; adjacent current infrastructure identical"})
    if "Ran 1 test" not in log or measured.returncode != (1 if mode == "prefix" else 0):
        raise SystemExit("pair did not reach its required executed verdict: " + log)
    if mode == "prefix" and "canonical cumulative-batch reconciliation is missing" not in log:
        raise SystemExit("prefix failure did not reproduce the owned mechanism")
    if context_digest() != context:
        raise SystemExit("shared execution context changed during the pair")
(directory / "regression-pair.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
print(json.dumps(rows))
