"""Real candidate phase/tag controls with independently initialized test history."""

import json
import shutil
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CANDIDATE = ROOT / ".saipen/evidence/T-1726-closed-contracts/cache-candidate"
sys.path.insert(0, str(CANDIDATE / "tools"))
import audit_checks as audit
from test_t1586_scenario_inputs import source_runtime_fixture

with tempfile.TemporaryDirectory(prefix="t1730-native-audit-") as directory:
    base = Path(directory).resolve()
    assert base.parent == Path(tempfile.gettempdir()).resolve()
    source = base / "source"
    source_runtime_fixture(CANDIDATE, source)
    shutil.copytree(CANDIDATE / "tests", source / "tests", dirs_exist_ok=True)
    evidence = source / ".saipen/evidence/opaque/proof.json"
    evidence.parent.mkdir(parents=True)
    original = b'{"phase": "SCOUT", "note": "synthetic immutable control"}\r\n'
    evidence.write_bytes(original)
    evidence.chmod(stat.S_IREAD)
    destination = base / "phase"
    destination.mkdir()
    error = audit.phase_rename_probe(source, destination)
    print(json.dumps({"phase_rename_problem": error}, indent=2), flush=True)
    assert error is None, error
    assert evidence.read_bytes() == original
    assert (destination / "phase-rename-history/.saipen/evidence/opaque/proof.json").exists() is False
    retained = destination / "phase-rename-history/evidence/opaque/proof.json"
    assert retained.read_bytes() == original
    context = audit.ProbeContext(base / "tag", [], None)
    context.tmp.mkdir()
    context.sandbox = context.tmp
    context.pristine = source
    error = audit.tag_query_probe(context)
    print(json.dumps({"tag_query_problem": error}, indent=2), flush=True)
    assert error is None, error
