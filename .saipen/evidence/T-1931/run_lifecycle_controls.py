"""Re-run the fixed lifecycle oracle against preserved and current subjects."""

import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
evidence = Path(__file__).resolve().parent
baseline = "--baseline" in sys.argv
subject = evidence / "campaign.before.py" if baseline else root / "tools/saipen_engine/campaign.py"
if baseline:
    import saipen_engine

    spec = importlib.util.spec_from_file_location("saipen_engine.campaign", subject)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    saipen_engine.campaign = module
    spec.loader.exec_module(module)

from test_t1931_campaign_lifecycle import CampaignLifecycleTests

names = unittest.defaultTestLoader.getTestCaseNames(CampaignLifecycleTests)
if baseline:
    # This test intentionally imports the installed source in an OS child. Its
    # live-source positive proof is separate from the fixed-oracle baseline.
    names.remove("test_process_death_preserves_attempt_and_releases_lifecycle_lock")
suite = unittest.TestSuite(CampaignLifecycleTests(name) for name in names)
before = hashlib.sha256(subject.read_bytes()).hexdigest()
result = unittest.TextTestRunner(verbosity=1).run(suite)
after = hashlib.sha256(subject.read_bytes()).hexdigest()
record = {
    "subject": str(subject.relative_to(root)), "subject_sha256": before,
    "subject_unchanged": before == after,
    "oracle_sha256": hashlib.sha256((root / "tools/test_t1931_campaign_lifecycle.py").read_bytes()).hexdigest(),
    "tests_run": result.testsRun, "successful": result.wasSuccessful(),
    "failures": [test.id() for test, _ in result.failures],
    "errors": [test.id() for test, _ in result.errors],
    "scope": "local lifecycle contracts; no installed host or broker acceptance",
}
name = "lifecycle-baseline.json" if baseline else "lifecycle-current.json"
(evidence / name).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record, indent=2))
sys.exit(0 if before == after and result.wasSuccessful() != baseline else 1)
