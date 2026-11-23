"""Hash-only diagnosis of the environment seen through the real launcher shell."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.test_runner import TestFamily, family_environment
from saipen_engine.verification_cache import capture

reference = ROOT / ".saipen/evidence/focused-unit/9dc4b867ad1853be-20261020T163534873357Z.json"
identity = json.loads(reference.read_text())["verification_identity"]
current = capture(ROOT, identity["configuration"])
environment = family_environment(TestFamily("identity", (sys.executable,), 1))
Path(sys.argv[1]).write_text(json.dumps({key: hashlib.sha256(value.encode()).hexdigest()
                                      for key, value in environment.items()}), encoding="utf-8")
print(json.dumps({"changed_capture_fields": [key for key in current
                                           if current[key] != identity.get(key)]}))
