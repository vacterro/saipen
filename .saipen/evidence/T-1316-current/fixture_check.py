"""Record real canonical validation on the existing disposable project fixture."""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from test_hermetic_env import hermetic_env
from test_orchestration_repair import OrchestrationFixture

fixture = OrchestrationFixture()
try:
    project = fixture.make_project(active=False)
    assert ROOT not in project.parents and not any((p / ".git").exists() for p in project.parents)
    command = [sys.executable, "-B", str(ROOT / "tools/saipen.py"), "validate",
               "--project-root", str(project), "--json"]
    run = subprocess.run(command, cwd=project, env=hermetic_env(),
                         capture_output=True, text=True, encoding="utf-8", timeout=300)
    (HERE / "fixture-validation.stdout").write_text(run.stdout, encoding="utf-8")
    (HERE / "fixture-validation.stderr").write_text(run.stderr, encoding="utf-8")
    payload = json.loads(run.stdout)
    record = {"command": command, "returncode": run.returncode,
              "fixture": "OrchestrationFixture.make_project(active=False)",
              "outside_worktree": True, "result": payload}
    (HERE / "fixture-validation.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=True))
    assert run.returncode == 0 and payload.get("ok") is True
    assert payload["conformance_status"]["status"] == "CURRENT_PASS"
finally:
    fixture.doCleanups()
