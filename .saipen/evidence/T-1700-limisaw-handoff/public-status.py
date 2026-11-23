"""Compare real human and JSON source-transport status without mutating Work."""
import hashlib
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
launcher = str(ROOT / "bin/saipen.cmd")
raw = subprocess.run([launcher, "status", "--json"], cwd=ROOT,
                     capture_output=True, timeout=120)
human = subprocess.run([launcher, "status"], cwd=ROOT,
                       capture_output=True, timeout=120)
(OUT / "public-status-json.txt").write_bytes(raw.stdout + raw.stderr)
(OUT / "public-status-human.txt").write_bytes(human.stdout + human.stderr)
assert raw.returncode == human.returncode == 0, (raw.stderr, human.stderr)
payload = json.loads(raw.stdout)
verdict = payload["conformance_status"]["status"]
text = human.stdout.decode("utf-8", "replace")
assert "Conformance: " + verdict in text, (verdict, text)
if payload.get("conformance_history"):
    assert "Validator history hint: " in text and "historical; not current authority" in text
assert payload["audit_inbox"]["pending"] == 5, payload["audit_inbox"]
assert payload["audit_inbox"]["error_state"] is None, payload["audit_inbox"]
record = {"authoritative_status": verdict, "human_and_json_agree": True,
          "history_is_labeled_as_history": bool(payload.get("conformance_history")),
          "source_named_inbox_pending": payload["audit_inbox"]["pending"],
          "source_binding_error": payload["audit_inbox"]["error_state"],
          "json_output_sha256": hashlib.sha256(raw.stdout).hexdigest(),
          "human_output_sha256": hashlib.sha256(human.stdout).hexdigest(),
          "scope": "source transport observation; no installed rollout claim"}
(OUT / "public-status-comparison.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
