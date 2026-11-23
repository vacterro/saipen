"""Run the canonical budget checker on both command-contract variants in scratch."""

import json
import shutil
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
sys.path.insert(0, str(root / "tools"))
import protocol_budget

with tempfile.TemporaryDirectory(prefix="saipen-command-budget-") as temp:
    protocol = Path(temp) / "saipen"
    shutil.copytree(root / "saipen", protocol)
    before_errors = protocol_budget.check(protocol)
    before = protocol_budget.load_profiles(protocol)
    shutil.copyfile(evidence / "COMMANDS.compact.md", protocol / "COMMANDS.md")
    after_errors = protocol_budget.check(protocol)
    after = protocol_budget.load_profiles(protocol)
    result = {
        "checker": "tools/protocol_budget.py check/load_profiles, unchanged",
        "live_source_edited": False,
        "before_errors": before_errors,
        "after_errors": after_errors,
        "before_command_resolution": before["command_resolution"],
        "after_command_resolution": after["command_resolution"],
        "budgets_unchanged": before["budgets"] == after["budgets"],
        "budget": after["budgets"]["command_resolution"],
    }
    (evidence / "compact-preview-verdict.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result))
    if not before_errors or after_errors or not result["budgets_unchanged"]:
        sys.exit(1)
