"""Unchanged verifier; only the preserved/current production owners vary."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
TEST = ROOT / "tools/test_automation_block.py"
OWNERS = ["automation.py", "response_surface.py"]


def digest(paths):
    value = hashlib.sha256()
    for path in paths:
        raw = path.read_bytes()
        value.update(len(raw).to_bytes(8, "big") + raw)
    return value.hexdigest()


if sys.argv[1] == "run":
    sys.path.insert(0, str(ROOT / "tools"))
    import test_automation_block as AT

    if os.environ.get("SAIPEN_INVALID_STOP_SUBJECT") == "pre":
        for name, attribute in [("automation", "automation"), ("response_surface", "RS")]:
            qualified = "saipen_engine._t1695_" + name
            spec = importlib.util.spec_from_file_location(qualified, OUT / ("pre-" + name + ".py"))
            module = importlib.util.module_from_spec(spec)
            sys.modules[qualified] = module
            spec.loader.exec_module(module)
            setattr(AT, attribute, module)
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(AT.InvalidDataStops)
    )
    sys.exit(0 if result.wasSuccessful() else 1)

mode = sys.argv[1]
assert mode in ("pre", "pair")
prefix = sys.argv[2] if len(sys.argv) > 2 else "verify"
records = []
command = [sys.executable, "-B", str(Path(__file__).resolve()), "run"]
for subject in (["pre"] if mode == "pre" else ["pre", "current"]):
    env = dict(os.environ)
    env["SAIPEN_INVALID_STOP_SUBJECT"] = subject
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=120)
    output = result.stdout + result.stderr
    output_path = OUT / (prefix + "-" + subject + ".out.txt")
    output_path.write_text(output, encoding="utf-8")
    subjects = [OUT / ("pre-" + name) for name in OWNERS]
    if subject == "current":
        subjects = [ROOT / "tools/saipen_engine" / name for name in OWNERS]
    record = {
        "subject": subject, "command": command, "exit_code": result.returncode,
        "verifier_sha256": digest([Path(__file__).resolve(), TEST]),
        "subject_sha256": digest(subjects), "subject_paths": [str(p) for p in subjects],
        "output": output_path.name, "output_sha256": digest([output_path]),
    }
    records.append(record)
    assert "Ran 6 tests" in output, output
    assert result.returncode == (1 if subject == "pre" else 0), output
    assert ("FAILED (failures=4)" if subject == "pre" else "\nOK") in output, output
if mode == "pair":
    assert records[0]["verifier_sha256"] == records[1]["verifier_sha256"]
(OUT / (prefix + "-pair.json")).write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
for record in records:
    print(json.dumps(record), flush=True)
