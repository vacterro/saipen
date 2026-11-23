"""Bounded readback of the two named incidents; writes only local evidence."""
from __future__ import annotations

import datetime
import hashlib
import json
import re
from pathlib import Path

SOURCE = Path("V:/___VAC/__K/__CODE/_TAMPERMONKEY/_WIN95THEME/Wintage")
HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "readback.json"
if OUTPUT.exists():
    raise SystemExit("Existing readback is immutable")

files = {}


def read(rel):
    path = SOURCE / rel
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        files[rel] = {"exists": False}
        return None
    files[rel] = {
        "exists": True, "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "text": raw.decode("utf-8-sig"),
    }
    return files[rel]["text"]


state = read(".saipen/STATE.md")
board = read(".saipen/BOARD.md")
log = read(".saipen/LOG.md")
selected_events = [line for line in log.splitlines() if re.search(
    r"\[E-(?:3286|348[0-9]|3490|3159|3160)\]", line
)]
files[".saipen/STATE.md"]["text"] = state.split("---", 2)[1]
files[".saipen/BOARD.md"]["text"] = "\n".join(
    line for line in board.splitlines() if re.search(r"\bT-359\b", line)
)
files[".saipen/LOG.md"]["text"] = "\n".join(selected_events)

read(".saipen/intake/tombstones/SRC-054.json")
read(".saipen/recovery/log-detail/E-3286-f56793e5c6d3f9370cd1be66.json")
read(".saipen/recovery/log-detail/E-3286-f56793e5c6d3f9370cd1be66.LOG.md")
read(".saipen/recovery/settled/checkpoint-d898f0b0e66644ea92a33f4c18909e6d/operation.json")

for event in selected_events:
    match = re.search(r"detail_ref: (\S+\.json)", event)
    if not match:
        continue
    text = read(match[1])
    if text:
        metadata = json.loads(text)
        original = metadata.get("original_event_path")
        if original:
            payload = read(original)
            if payload is not None:
                files[original]["matches_metadata"] = (
                    files[original]["sha256"] == metadata["original_event_sha256"]
                )

rel = ".saipen/recovery/board-compaction/T-359/T-359-37fb742f4b049ce4a42f35c8.json"
seen = set()
for _ in range(32):
    if not rel or rel in seen:
        break
    seen.add(rel)
    text = read(rel)
    if text is None:
        break
    metadata = json.loads(text)
    original = metadata["original_record_path"]
    if read(original) is not None:
        files[original]["matches_metadata"] = (
            files[original]["sha256"] == metadata["original_record_sha256"]
        )
    rel = metadata.get("supersedes_detail_ref")

report = {
    "root": str(SOURCE),
    "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "scope": "Named T-359 preimage chain, E-3480..3490, E-3286 citation and creating receipt",
    "files": files,
    "mutations_to_external_root": [],
    "limits": [
        "Readback is not a final audit verdict or an exhaustive recovery-source search.",
        "State, Board and Log text is selected; hashes bind the complete files read.",
        "Other agents may continue the live project; no claim or state transition was performed.",
    ],
}
OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"observed_files": len(files), "preimage_chain": len(seen),
                  "missing": [p for p, d in files.items() if not d["exists"]],
                  "evidence": str(OUTPUT)}))
