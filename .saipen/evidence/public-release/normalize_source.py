"""Bind the public-release request to its canonical acceptance contract."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import intake

clauses = [
    ("R001", "requirement", "Publish the currently recommended stable SAIPEN implementation to vacterro/saipen canonical main now, after the release gates. Preserve useful changes from other branches; exclude known unfinished/WIP implementation and preserve ongoing local work."),
    ("R002", "acceptance-criterion", "A fresh clone from the published recommended version can be installed in a clean user environment using only the current README commands."),
    ("R003", "acceptance-criterion", "After installation, saipen set bootstraps a new project successfully."),
    ("R004", "acceptance-criterion", "After set, saipen continue cold-routes a new agent to exact protocol, project memory and a real next action; the instructions explain execution rather than merely acknowledging a skill."),
    ("R005", "acceptance-criterion", "Canonical validate passes on the clean installed project and the release candidate; complete declared tests and CI/validation are green before tag/release publication."),
    ("R006", "acceptance-criterion", "Uninstall succeeds and reverses only SAIPEN-owned changes, preserving unrelated user instructions, config, hooks, skills and project memory."),
    ("R007", "acceptance-criterion", "Installing again after uninstall succeeds; demonstrate the entire install/set/continue/validate/uninstall/reinstall lifecycle in a clean isolated environment."),
    ("R008", "acceptance-criterion", "GitHub main equals the verified version actually recommended in README; observe green GitHub CI on that exact published commit."),
    ("R009", "requirement", "README and Quick Start match the actual current installer and removal commands. Installation and removal are short and understandable; a stranger can reproduce all acceptance steps from README alone."),
    ("R010", "requirement", "If implementation has substantially advanced beyond v8.0.1, choose a proper new version and publish its matching new tag and GitHub release only after full green validation; release metadata must agree with the tested bytes."),
    ("R011", "invariant", "Preserve local-first behavior: no mandatory external services. Fix release-blocking defects immediately; do not start unrelated feature expansion."),
    ("R012", "context", "This new direct user message explicitly authorizes GitHub main push and, once the green gates pass, new release/tag publication for this public-stability objective. It supersedes the earlier cc-all source's publication exclusion only for this objective; the stored intake witness remains model_supplied and is not fabricated host authentication."),
]
result = intake.add_requirements(ROOT, "SRC-168", [
    {"rid": rid, "class": kind, "text": text} for rid, kind, text in clauses
])
print(json.dumps(result, indent=2))
raise SystemExit(0 if result.get("ok") else 1)
