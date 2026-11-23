"""Prepare a compact command-contract candidate without editing frozen source."""

import json
from pathlib import Path

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
current = (root / "saipen/COMMANDS.md").read_text(encoding="utf-8")
start = current.index("**Skill-only no-op is not continuation.**")
end = current.index("`saipen continue` routes:", start)
replacement = (evidence / "compact-continuation.txt").read_text(encoding="utf-8").rstrip() + "\n\n"
candidate = current[:start] + replacement + current[end:]
(evidence / "COMMANDS.compact.md").write_text(candidate, encoding="utf-8", newline="\n")
registry_bytes = len((root / "saipen/REGISTRY.json").read_text(encoding="utf-8").encode("utf-8"))
candidate_bytes = len(candidate.encode("utf-8"))
print(json.dumps({"old_section_bytes": len(current[start:end].encode("utf-8")),
                  "replacement_bytes": len(replacement.encode("utf-8")),
                  "candidate_command_resolution_bytes": registry_bytes + candidate_bytes,
                  "existing_budget": 55296,
                  "under_existing_budget": registry_bytes + candidate_bytes <= 55296}))
