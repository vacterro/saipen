"""Normalize exact roadmap slice text through the canonical source CLI."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
source = ROOT / ".saipen/intake/active/SRC-205.md"
raw = source.read_bytes()
assert hashlib.sha256(raw).hexdigest() == "f43fe6b191c8e7449266b3d6ab1eb8c26b6247bfc8b8d5b02ab6cf1eef212f97"
body = raw.decode("utf-8").replace("\r\n", "\n")
slices = re.findall(r"^([A-E]\d{2}) (\[[^\n]+?\]: [^\n]+)$", body, re.MULTILINE)
assert len(slices) == 28 and len({item[0] for item in slices}) == 28
clauses = [(name, "requirement", name + " " + text) for name, text in slices]
clauses.extend([
    ("INVARIANTS", "invariant", "Preserve all I1-I10 source invariants: operation-backed lifecycle and authentic operator authority, separate Windows principal for an OS boundary, legitimate source/read-only work, truthful host capability, immutable history, disposable fixtures, denial/allowed/interruption/tamper/rollback controls, no automatic publication/policy/live destructive action, no overlapping source corridor."),
    ("WORKFLOW", "requirement", "Preserve the complete single-slice workflow in source sections 2, 8 and 10: future operator 1 selects one freshest earliest eligible S/M slice, narrow English SAIHANDOFF, no invented symbols/model metadata or archive hunt, independent returned-evidence audit; current completed prerequisites replace stale snapshot assumptions, no entire-roadmap dispatch or unauthorized live cutover."),
    ("ACCEPTANCE", "acceptance-criterion", "Retain source K1-K10 as actual milestone acceptance: no unbacked lifecycle or unauthorized OS-pilot writes, no forged DONE/approval or lost journals/unsupported mechanical claims/new reds; source-denial and repeated-refusal accounting, 20 controlled cold transfers with 90 percent success target, concise owner/next-action diagnostics. No warning-count or empty-board substitute."),
])
mapping = []
for number, (name, kind, text) in enumerate(clauses, 1):
    rid = f"R{number:03d}"
    result = subprocess.run([str(ROOT / "bin/saipen.cmd"), "source", "req", "SRC-205", rid,
                             kind, text, "--json"], cwd=ROOT, capture_output=True, timeout=60)
    value = json.loads(result.stdout)
    assert result.returncode == 0 and value.get("ok"), value
    mapping.append({"slice": name, "rid": rid, "class": kind, "text": text,
                    "contract_revision": value["revision"]})
(OUT / "slice-map.json").write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"receipt": "SRC-205", "exact_source_sha256": hashlib.sha256(raw).hexdigest(),
                  "slices": 28, "total_actionable_clauses": len(mapping),
                  "mapping": str(OUT / "slice-map.json")}))
