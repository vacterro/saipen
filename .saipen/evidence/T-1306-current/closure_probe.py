"""Determine which public invocation committed the default closure."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from test_closure_provenance import ProvenanceFixture, _tree_digest
from saipen_engine import closure
from saipen_engine.operations import apply_claim, finish_ticket

fixture = ProvenanceFixture()
try:
    project = fixture.make_project(active=True)
    (project / "main.py").write_text("shared = 1\n", encoding="utf-8")
    second = fixture.add(project, "second shared member")
    fixture.to_ship(project, "T-7")
    first = finish_ticket(project, "T-7", "tester", closure_mode="cohort",
                          closure_cohort="C-001", closure_paths=("main.py",))
    assert first.ok, first.to_dict()
    (project / "main.py").write_text("shared = 2\n", encoding="utf-8")
    assert apply_claim(project, second, "tester", explicit=True).ok
    fixture.to_ship(project, second)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("SAIPEN_")}
    def invoke(args):
        native = subprocess.run([sys.executable, str(ROOT / "tools/saipen.py"),
                                 "--project-root", str(project), *args, "--json"],
                                cwd=project, env=env, capture_output=True,
                                text=True, encoding="utf-8", timeout=90)
        return {"exit": native.returncode, "payload": json.loads(native.stdout),
                "stderr": native.stderr}
    before = _tree_digest(project)
    refused = invoke(["ticket", "done", second, "--closure-mode", "cohort",
                      "--closure-cohort", "C-001", "--paths", "main.py"])
    after_refusal = _tree_digest(project)
    continued = invoke(["continue"])
    print(json.dumps({"refused": refused, "refusal_zero_write": before == after_refusal,
                      "continuation": continued,
                      "after_row": fixture.board(project)["tickets"][second],
                      "cohort_members": sorted(closure.read_registry(project)["cohorts"]["C-001"]["members"]),
                      "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
                     indent=2))
finally:
    fixture.doCleanups()
