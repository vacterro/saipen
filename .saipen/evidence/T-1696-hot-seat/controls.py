"""Refresh the six sacrificial probes; assert every hostile input really lands."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
OLD = ROOT / ".saipen/evidence/T-1696-queued-audapack/guardrails.py"
PREFIX = sys.argv[1]
spec = importlib.util.spec_from_file_location("t1696_preserved_carrier", OLD)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
old.OUT = OUT / PREFIX
old.OUT.mkdir(exist_ok=True)
old.results = []
old_hash = hashlib.sha256(OLD.read_bytes()).hexdigest()


def checked(change, predicate):
    def apply(root):
        before = old.docs(root)
        change(root)
        after = old.docs(root)
        assert before != after, "mutation changed no semantic document text"
        assert predicate(root, after), "requested hostile input did not land"
    return apply


duplicate = checked(old.duplicate, lambda root, docs: len(old.duplicate_records(docs[1], "T-1")) == 2)
old.duplicate = duplicate


def actual_unnumbered(root):
    path = root / ".saipen/LOG.md"
    payload = b"- 10.10.26 [T-1] RUN: ticket finished via SAIOPS -- completion (from SHIP)\n"
    path.write_bytes(payload + path.read_bytes())
    assert path.read_bytes().startswith(payload)


cases = (
    ("1-duplicate", duplicate),
    ("2-unadmitted-done", checked(old.closed_without_events,
        lambda root, docs: "- [x] T-2 [P1] unadmitted closure" in docs[1])),
    ("3-unnumbered-actual", checked(actual_unnumbered,
        lambda root, docs: docs[2].startswith("- 10.10.26 [T-1] RUN:"))),
    ("4-heading", checked(old.malformed,
        lambda root, docs: "## TODO## DOING" in docs[1] and "\n## TODO\n" not in docs[1])),
    ("5-evidence-no-event", checked(old.evidence_without_identity,
        lambda root, docs: "- [x] T-1" in docs[1]
        and ".saipen/evidence/closure.md reports PASS but has no event identity" in docs[1]
        and (root / ".saipen/evidence/closure.md").is_file())),
)
for name, change in cases:
    old.run(name, change)
    verdict = old.results[-1]
    assert verdict["exit_code"] != 0 and not verdict["verdict"].get("ok"), verdict
old.unrelated_reconciliation()
assert len(old.results) == 6
assert hashlib.sha256(OLD.read_bytes()).hexdigest() == old_hash
summary = {"six_controls": [
    {"case": item["case"], "exit_code": item["exit_code"],
     "code": item["verdict"]["code"], "canonical_docs_unchanged": item["canonical_docs_unchanged"]}
    for item in old.results], "original_carrier_sha256": old_hash,
    "hostile_payload_presence_asserted": True, "target_writes": 0}
(old.OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary))
