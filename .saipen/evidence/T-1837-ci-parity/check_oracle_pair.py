"""Unchanged final oracles against controlled old subjects and current subjects."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
oracles = [
    ("test_runner", "DispatchTests.test_unit_cli_uses_existing_full_engine_without_a_lifecycle_citation"),
    ("core_unit", "EmptyPartitionTests.test_only_proved_empty_worker_is_neutral_and_raw_result_stays_visible"),
]
results = []
for name, oracle in oracles:
    for before in (True, False):
        subject = evidence / "prefix" / (name + ".py") if before else root / "tools/saipen_engine" / (name + ".py")
        code = (
            "import importlib.util,sys,unittest; "
            f"sys.path.insert(0,{str(root / 'tools')!r}); "
            "import saipen_engine; "
            f"spec=importlib.util.spec_from_file_location('saipen_engine.{name}',{str(subject)!r}); "
            "module=importlib.util.module_from_spec(spec); "
            f"sys.modules['saipen_engine.{name}']=module; "
            "spec.loader.exec_module(module); "
            f"setattr(saipen_engine,{name!r},module); "
            f"suite=unittest.defaultTestLoader.loadTestsFromName('test_t1837_ci_family_parity.{oracle}'); "
            "result=unittest.TextTestRunner(verbosity=2).run(suite); "
            "sys.exit(0 if result.wasSuccessful() else 1)"
        )
        run = subprocess.run([sys.executable, "-B", "-c", code], cwd=root, capture_output=True,
                             text=True, encoding="utf-8", timeout=45)
        label = name + ("-before" if before else "-corrected")
        (evidence / (label + ".log")).write_text(run.stdout + run.stderr, encoding="utf-8")
        results.append({"subject": label, "exit_code": run.returncode, "oracle": oracle,
                        "oracle_sha256": hashlib.sha256((root / "tools/test_t1837_ci_family_parity.py").read_bytes()).hexdigest(),
                        "subject_sha256": hashlib.sha256(subject.read_bytes()).hexdigest()})
(evidence / "oracle-pair.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
print(json.dumps(results, indent=2))
raise SystemExit(0 if [result["exit_code"] for result in results] == [1, 0, 1, 0] else 1)
