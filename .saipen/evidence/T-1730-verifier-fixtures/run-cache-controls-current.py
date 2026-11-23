"""Use one unchanged cache oracle against either preserved or candidate code."""

import importlib.util
from pathlib import Path
import sys
import subprocess
import unittest

directory = Path(__file__).resolve().parent
root = directory.parents[2]
sys.path.insert(0, str(root / "tools"))
variant = sys.argv[1]
variants = {"before": "before-cache-producer", "before-guard": "before-cache-input-guard",
            "after": "cache-candidate"}
if variant not in variants:
    raise SystemExit("Expected before, before-guard or after.")
subject = directory / variants[variant]
subject = subject / "tools/audit_checks.py"
spec = importlib.util.spec_from_file_location("audit_checks", subject)
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)
audit.HOME = root
oracle = directory / "cache-candidate/tools/test_t1581_phase_rename_knowledge.py"
spec = importlib.util.spec_from_file_location("audit_cache_control_oracle", oracle)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
names = sys.argv[2:] or ["FullAuditCacheTests"]
if names == ["all"]:
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromModule(module),
        unittest.defaultTestLoader.loadTestsFromName("test_t1586_scenario_inputs"),
    ])
else:
    suite = unittest.defaultTestLoader.loadTestsFromNames(names, module)
original_run = subprocess.run


def diagnostic_run(command, *args, **kwargs):
    outcome = original_run(command, *args, **kwargs)
    if outcome.returncode and any(str(part).endswith("validate.py") for part in command):
        body = (outcome.stdout or "") + (outcome.stderr or "")
        sys.stderr.write("\nNative validator diagnostics:\n" + "\n".join(
            line for line in body.splitlines() if line.startswith("FAIL:")
        ) + "\n")
    return outcome


subprocess.run = diagnostic_run
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
