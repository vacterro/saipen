"""Exercise the candidate's real constructor without running the full matrix."""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CANDIDATE = ROOT / ".saipen/evidence/T-1726-closed-contracts/cache-candidate"
sys.path.insert(0, str(CANDIDATE / "tools"))
import run_scenarios

with tempfile.TemporaryDirectory(prefix="t1730-native-release-") as directory:
    project, origin, git, cli, version = run_scenarios.build_release_fixture(Path(directory))
    result = cli("ship", "--dry-run", "--json")
    body = json.loads(result.stdout)
    assert result.returncode == 0 and body.get("ok"), body
    print(json.dumps({"positive": True, "version": version, "code": body.get("code")}, indent=2))

with tempfile.TemporaryDirectory(prefix="t1730-declared-family-") as directory:
    project, origin, git, cli, version = run_scenarios.build_release_fixture(
        Path(directory), stop_at_review=True)
    declared = project / "tools/saipen_engine/test_runner.py"
    declared.write_bytes((CANDIDATE / "tools/saipen_engine/test_runner.py").read_bytes())
    from saipen_engine import codec
    from saipen_engine.state import parse_state
    state = project / ".saipen/STATE.md"
    before = state.read_bytes()
    ticket = parse_state(codec.read_doc(state))["task"]
    result = cli("transition", "SHIP", ticket, "--json")
    body = json.loads(result.stdout)
    assert result.returncode != 0 and body.get("code") == "INCOMPLETE_TICKET", body
    assert "core_unit" in (body.get("canonical_next_command") or ""), body
    assert state.read_bytes() == before
    print(json.dumps({"declared_family_refused_without_evidence": True,
                      "code": body["code"]}, indent=2))

with tempfile.TemporaryDirectory(prefix="t1730-no-publish-") as directory:
    project, origin, git, cli, version = run_scenarios.build_release_fixture(
        Path(directory), mode="no-publish")
    result = cli("ship", "--json")
    print(json.dumps({"no_publish_result": json.loads(result.stdout)}, indent=2))
