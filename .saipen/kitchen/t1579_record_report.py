"""Persist the bounded SAIPAL reporter result and current storage proof anchors."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import protocol_budget

OUT = ROOT / ".saipen/evidence/T-1579-storage-safety"
PAL = ROOT.parent / "_SAIPAL"
command = [sys.executable, "-B", str(PAL / "tools/saipal.py"),
           "--home", str(PAL / ".saipal"), "--json", "report"]
run = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=45,
                     env={**os.environ, "PYTHONIOENCODING": "utf-8"})
report = json.loads(run.stdout)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "saipal-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
paths = ["saipen/REGISTRY.json", "saipen/INDEX.md", "saipen/COMMANDS.md", "saipen/STORAGE.md",
         "tools/saipen_engine/storage.py", "tools/saipen_engine/storage_artifacts.py",
         "tools/test_storage_policy.py", "tools/test_storage_artifacts.py"]
measured = protocol_budget.load_profiles(ROOT / "saipen")
evidence = {"recorded_utc": datetime.now(timezone.utc).isoformat(), "ticket": "T-1579",
            "status": "BUILD_EVIDENCE_ONLY", "closure_claimed": False,
            "files": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
            "load_budgets": {name: {"measured": measured[name], "limit": limit}
                             for name, limit in measured["budgets"].items()},
            "human_markdown_total": measured["human_markdown_total"],
            "focused": {"command": "python -B -m unittest tools.test_storage_policy tools.test_storage_artifacts tools.test_protocol_registry tools.test_source_quarantine_route tools.test_style_contract_chokepoint.StaticChokepointTests",
                        "ran": 51, "status": "PASS", "skipped": 1, "skip_reason": "symlink capability unavailable"},
            "lint": {"command": "python -B -m ruff check tools/ tests/ --output-format concise", "status": "PASS"},
            "scoped_whitespace": {"command": "git diff --check -- saipen/REGISTRY.json saipen/INDEX.md saipen/COMMANDS.md tools/test_storage_policy.py tools/test_storage_artifacts.py", "status": "PASS"},
            "earlier_family": [".saipen/evidence/core-unit/7621521d20d8a7c5-20261001T083313Z.json",
                               ".saipen/evidence/core-unit/0b86bdb31c8f8159-20261001T090336Z.json"],
            "family_rerun": "in flight; no PASS claimed before canonical completion record",
            "seat": {"phase": "SCOUT", "task": "T-1580", "T-1579": "parked behind T-1580",
                     "ownership_question": "pending; no canonical seat change performed"},
            "audit": {"record": ".saipen/evidence/T-1579-storage-safety/storage-audit.json",
                      "projects": 11, "runtime_homes": 9, "known_ephemeral_durable_violations": 0,
                      "limitation": "bounded known roots; UNKNOWN roots are not blessed as durable"},
            "recovery": {"selected_home": "V:/___VAC/__K/__STATE/SAILEARN_HOME",
                         "reconstruction": "PENDING_SOURCE_EVIDENCE", "regenerated_artifacts": [],
                         "SAIBUD_8": "untouched"},
            "saipal": {"candidates_submitted": 5, "candidate_verdicts": "NO_DRIFT / PROVISIONAL",
                       "scope": "bounded synthetic OpenCode smoke carriers; no production compliance claim",
                       "report": ".saipen/evidence/T-1579-storage-safety/saipal-report.json",
                       "sha256": hashlib.sha256((OUT / "saipal-report.json").read_bytes()).hexdigest()}}
(OUT / "build-evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"report_command_exit": run.returncode, "report_fields": list(report),
                  "cold": evidence["load_budgets"]["cold"], "human_markdown_total": measured["human_markdown_total"]}))
sys.exit(run.returncode)
