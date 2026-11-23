"""Disposable public-CLI control; synthetic ingress is never host evidence."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PREFIX = sys.argv[1] if len(sys.argv) > 1 else "hotswitch"
sys.path.insert(0, str(ROOT / "tools"))
from test_response_surface_contract import DiagnosisTests, REQUEST
from saipen_engine import operator_task, pending_ingress

case = DiagnosisTests("test_g_cited_diagnosis_with_bounded_uncertainty")
case.setUp()
try:
    original_evidence = case.root / ".saipen/evidence"
    case.root = case.root / "project"
    case.root.mkdir()
    env = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
    launcher = ROOT / "bin/saipen.cmd"
    env[operator_task.ENV_TASK_SHA256] = pending_ingress.ingress_digest(REQUEST)
    base = [str(launcher), "--project-root", str(case.root)]
    init = subprocess.run(base + ["init", "--json"], cwd=ROOT, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    (OUT / (PREFIX + "-cli-init.out.txt")).write_text(init.stdout + init.stderr, encoding="utf-8")
    assert init.returncode == 0, init.stdout + init.stderr
    evidence = case.root / ".saipen/evidence"
    evidence.mkdir(exist_ok=True)
    for fixture in original_evidence.iterdir():
        (evidence / fixture.name).write_bytes(fixture.read_bytes())
    checkpoint = {name: (case.root / ".saipen" / name).read_bytes()
                  for name in ("STATE.md", "BOARD.md", "LOG.md")}
    records = []
    for label, text, expected in [
        ("inventory", (case.root / ".saipen/evidence/a.md").read_text(encoding="utf-8"), False),
        ("diagnosis", json.dumps(case.packet()), True),
    ]:
        command = base + ["response", "check", "--stdin", "--classify", "--request", REQUEST,
                          "--json"]
        result = subprocess.run(command, cwd=ROOT, env=env, input=text,
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        (OUT / (PREFIX + "-cli-" + label + ".out.txt")).write_text(
            result.stdout + result.stderr, encoding="utf-8")
        verdict = json.loads(result.stdout)
        assert verdict["ok"] is expected, verdict
        assert (result.returncode == 0) is expected, verdict
        if expected:
            assert verdict["diagnosis_verification"] == "STRUCTURE_AND_CITATIONS_ONLY"
            assert verdict["semantic_review"] == "REQUIRED"
        records.append({"label": label, "command": command, "exit_code": result.returncode,
                        "verdict": verdict})
    assert all((case.root / ".saipen" / name).read_bytes() == raw
               for name, raw in checkpoint.items())
    payload = {"records": records, "checkpoint_unchanged": True,
               "subject_sha256": hashlib.sha256(
                   (ROOT / "tools/saipen_engine/response_surface.py").read_bytes()).hexdigest(),
               "limits": "Disposable project and synthetic witness; public source CLI only; "
                         "no native FreeBuff interception or real human provenance is proved."}
    (OUT / (PREFIX + "-cli.json")).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("Public CLI: inventory refused; bound diagnosis accepted; semantic review REQUIRED; "
          "disposable canonical checkpoint unchanged.")
finally:
    case.doCleanups()
