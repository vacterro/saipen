"""Bounded rule-owner/reference inventory. No protocol mutation or inferred grants."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
REG = json.loads((ROOT / "saipen/REGISTRY.json").read_text(encoding="utf-8-sig"))
FACTS = REG["semantic_baseline"]["facts"]
NAMES = ["CORE.md","COMMANDS.md","COMMANDS_REFERENCE.md","EXECUTION.md","OPS.md",
         "SOURCES.md","MAINTENANCE.md","IMPROVE.md","BOOT.md","INDEX.md"]
FILES = [ROOT / "saipen" / name for name in NAMES]
FILES += sorted((ROOT / "saipen/phases").glob("*.md"))
MARKER = re.compile(r"<!-- RULE-OWNER:\s*([A-Z0-9-]+)\s*-->")
owner_markers = {}
documents = {}
occurrences = []
for path in FILES:
    relative = path.relative_to(ROOT).as_posix()
    text = path.read_text(encoding="utf-8-sig").replace("\r\n","\n")
    documents[relative] = {"lf_bytes":len(text.encode()), "sha256":hashlib.sha256(text.encode()).hexdigest()}
    for index, line in enumerate(text.splitlines(), 1):
        for match in MARKER.finditer(line):
            owner_markers.setdefault(match.group(1), []).append({"file":relative,"line":index})
        for rule in FACTS:
            if re.search(r"(?<![A-Z0-9-])"+re.escape(rule)+r"(?![A-Z0-9-])", line):
                owner = FACTS[rule]["owner"]
                marker = bool(MARKER.search(line))
                if marker:
                    classification = "Normative source" if owner == relative else "Contradiction"
                elif relative.endswith(("COMMANDS_REFERENCE.md","BOOT.md","INDEX.md")):
                    classification = "Derived projection"
                else:
                    classification = "Helpful explanation"
                occurrences.append({"rule":rule,"owner":owner,"file":relative,"line":index,
                                    "classification":classification,"text":line.strip()})
contradictions = [row for row in occurrences if row["classification"] == "Contradiction"]
new_conditional = REG["load_profiles"]["profiles"]["command_resolution"]["routes"][0]["conditional"]
result = {
    "scope":"Complete syntactic read of the named owner documents and all phase deltas; registered rule references only",
    "semantic_limit":"Reference occurrence classification is not proof of equivalence of all independent unnumbered prose. Selected changed obligations are manually mapped in W4-OWNERSHIP.md.",
    "documents":documents, "canonical_rule_owners":FACTS,
    "owner_markers":owner_markers, "occurrences":occurrences,
    "explicit_marker_conflicts":contradictions,
    "conditional_command_reference":new_conditional,
    "graph_mcp":"Unavailable; no graph generation or coverage claim",
}
(OUT/"rule-ownership.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"documents":len(documents),"registered_rules":len(FACTS),
                  "occurrences":len(occurrences),"explicit_marker_conflicts":contradictions,
                  "unregistered_markers":{k:v for k,v in owner_markers.items() if k not in FACTS}},indent=2))

