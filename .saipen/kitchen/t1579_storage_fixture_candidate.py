"""Prepare hermetic storage fixtures while the tested tree is frozen."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import test_storage_artifacts as artifacts
import test_storage_policy as policy

addition = '''        # The family runs in an OS-temp copy. Give this fixture its own real
        # TEMP boundary so its explicit durable store is outside that boundary.
        os_temp = self.base / "os-temporary"
        os_temp.mkdir()
        self.enterContext(patch.dict(os.environ, {
            name: str(os_temp) for name in ("TEMP", "TMP", "TMPDIR")
        }))
        self.enterContext(patch.object(tempfile, "tempdir", str(os_temp)))
'''
candidate = ROOT / ".saipen/evidence/T-1579-storage-safety/fixture-candidate"
candidate.mkdir(parents=True, exist_ok=True)
records = []
for module in (policy, artifacts):
    source = ROOT / "tools" / (module.__name__ + ".py")
    text = source.read_text(encoding="utf-8")
    if module is policy:
        text = text.replace("from pathlib import Path\n", "from pathlib import Path\nfrom unittest.mock import patch\n", 1)
    anchor = "        self.base = Path(self.tmp.name)\n" if module is policy else "        self.base = Path(self.temp.name)\n"
    if text.count(anchor) != 1:
        raise RuntimeError("fixture anchor changed")
    updated = text.replace(anchor, anchor + addition, 1)
    (candidate / source.name).write_text(updated, encoding="utf-8", newline="")
    records.append({"path": source.relative_to(ROOT).as_posix(),
                    "before_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    "candidate": str(candidate / source.name)})
    exec(compile(updated, str(source), "exec"), module.__dict__)
(candidate / "manifest.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")

with tempfile.TemporaryDirectory(prefix="t1579-family-placement-") as location:
    policy.ROOT = artifacts.ROOT = Path(location)
    result = unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite([
        policy.StoragePolicyTests("test_operator_durable_root_allows_store_without_touching_user_file"),
        artifacts.StorageArtifactsTests("test_transient_checkpoint_promotes_before_registry_pointer"),
    ]))
sys.exit(0 if result.wasSuccessful() else 1)
