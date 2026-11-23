"""Restore the original bounded two-file candidate with exact compare-and-swap."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
owned = (
    ("tools/saipen_engine/audit_inbox.py", "audit_inbox.py",
     "7421355627f2b55b109e0df4644a5b49580f2f21173e6bf33d3544dc37968e06",
     "8be9ffadd25fc8d8c750ee7694f82e41fdbe2faa2ff593a44a59f3306477c53d"),
    ("tools/test_audit_inbox.py", "test_audit_inbox.py",
     "370927381ec5eb6db4db1a8723620963a4b6c22a2bee05cb4e9df7998e8e265a",
     "e702c8403074fb1584048c582bc234efd342a7bd0dabca8b3e7aa54740bb3a2e"),
)
prepared = []
for relative, name, expected_before, expected_after in owned:
    target = ROOT / relative
    candidate = ROOT / ".saipen/kitchen/failed/T-1698" / name
    before, after = target.read_bytes(), candidate.read_bytes()
    assert hashlib.sha256(before).hexdigest() == expected_before, relative
    assert hashlib.sha256(after).hexdigest() == expected_after, str(candidate)
    assert before == (OUT / "pre" / name).read_bytes(), relative
    prepared.append((target, before, after, relative, expected_before, expected_after))
for target, before, after, relative, expected_before, expected_after in prepared:
    assert target.read_bytes() == before, "concurrent change: " + relative
    target.write_bytes(after)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == expected_after, relative
record = {"owned": [{"path": item[3], "before": item[4], "after": item[5]} for item in prepared],
          "scope": "exact original T-1698 candidate only; no foreign source or staged blob changes"}
(OUT / "hot-seat-restoration.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
